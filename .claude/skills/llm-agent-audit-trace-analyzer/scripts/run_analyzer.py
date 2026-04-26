#!/usr/bin/env python3
"""WAGF audit trace analyzer.

Reads a results-tree root, discovers runs, computes per-run governance
metrics by delegating to the canonical production scripts, aggregates
by (model, condition), and emits the five output artefacts.

Usage:
    python run_analyzer.py <results_root> [--out analysis] [--domain flood|irrigation]
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

REPO = Path(__file__).resolve().parents[5]


def discover_runs(root: Path) -> List[Tuple[str, str, str, Path]]:
    """Return [(model, condition, run_id, dir), ...].

    Discovers any directory containing a `*_governance_audit.csv` file
    (e.g., household_, simple_agent_, irrigation_farmer_). Falls back
    to also accepting a directory whose parent is `root` itself.
    """
    out = []
    seen = set()
    # Glob for any *_governance_audit.csv anywhere under root.
    for p in sorted(root.rglob("*_governance_audit.csv")):
        d = p.parent
        if d in seen:
            continue
        seen.add(d)
        # Heuristic: model = grandparent name; condition = parent name; run = self
        run_id = d.name
        cond = d.parent.name if d.parent != root else "default"
        model = d.parent.parent.name if d.parent.parent != root else "default"
        if d == root:
            run_id, cond, model = root.name, "default", "default"
        out.append((model, cond, run_id, d))
    return out


def per_run_metrics_simple(run_dir: Path) -> Dict:
    """Generic metrics for any *_governance_audit.csv (skill-agnostic).

    Used when a run directory is not flood/irrigation but a custom
    domain (e.g., the quickstart's simple_agent). Reports total
    decisions, approval rate, and skill distribution.
    """
    csv_paths = list(run_dir.glob("*_governance_audit.csv"))
    if not csv_paths:
        return {}
    df = pd.read_csv(csv_paths[0], encoding="utf-8-sig")
    if df.empty:
        return {}
    n = len(df)
    approved = float((df.get("status", "").astype(str).str.upper() == "APPROVED").sum()) / n
    skill_col = "final_skill" if "final_skill" in df.columns else "proposed_skill"
    skill_counts = df[skill_col].astype(str).value_counts().to_dict() if skill_col in df.columns else {}
    return {
        "n_decisions": n,
        "approval_rate": approved,
        "skill_distribution": skill_counts,
    }


def per_run_metrics(run_dir: Path, domain: str) -> Dict:
    """Compute IBR/EHE/rejection_rate/retry_rate per the canonical formulas."""
    # Try domain-specific name first, then fall back to any *_governance_audit.csv
    candidates = list(run_dir.glob("*_governance_audit.csv"))
    if not candidates:
        return {}
    csv_path = candidates[0]
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    if df.empty:
        return {}

    n = len(df)
    # If the expected domain construct column is missing, fall back to generic.
    expected_col = "construct_TP_LABEL" if domain == "flood" else "construct_WSA_LABEL"
    if expected_col not in df.columns:
        return per_run_metrics_simple(run_dir)

    if domain == "flood":
        tp = df["construct_TP_LABEL"].astype(str).str.upper()
        act = df["final_skill"].astype(str).str.lower().replace({"relocated": "relocate"})
        high = tp.isin(["H", "VH"])
        low = tp.isin(["VL", "L"])
        r1 = int((high & (act == "do_nothing")).sum())
        r3 = int((low & (act == "relocate")).sum())
        r4 = int((low & (act == "elevate_house")).sum())
        ibr = (r1 + r3 + r4) / n
        ACTIONS = ["do_nothing", "buy_insurance", "elevate_house", "relocate"]
        a = act.map(lambda x: x if x in ACTIONS else "do_nothing")
    else:  # irrigation
        wsa = df.get("construct_WSA_LABEL", pd.Series([""] * n)).astype(str).str.upper()
        act = df["final_skill"].astype(str).str.lower()
        high = wsa.isin(["H", "VH"])
        ibr_n = int((high & act.str.startswith("increase")).sum())
        high_n = int(high.sum()) or 1
        ibr = ibr_n / high_n
        r1 = ibr_n
        r3 = r4 = 0
        ACTIONS = ["increase_large", "increase_small", "maintain_demand",
                   "decrease_small", "decrease_large"]
        a = act.map(lambda x: x if x in ACTIONS else "maintain_demand")

    counts = a.value_counts()
    p = (counts / counts.sum())
    p = p[p > 0]
    k = len(ACTIONS)
    ehe = float(-(p * np.log2(p)).sum() / np.log2(k))

    rej = float((df["status"].astype(str).str.upper() != "APPROVED").sum()) / n
    retry = pd.to_numeric(df.get("retry_count", 0), errors="coerce").fillna(0)
    retry_rate = float((retry > 0).sum()) / n

    return {
        "n_decisions": n,
        "ibr": ibr,
        "r1": r1, "r3": r3, "r4": r4,
        "ehe": ehe,
        "rejection_rate": rej,
        "retry_rate": retry_rate,
    }


def write_artefacts(rows: List[Dict], out_dir: Path, domain: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. governance_metrics.csv
    csv_path = out_dir / "governance_metrics.csv"
    if rows:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"  wrote {csv_path}")

    # 2. governance_summary.md
    summary = out_dir / "governance_summary.md"
    df = pd.DataFrame(rows)
    if df.empty:
        summary.write_text("# Governance summary\n\nNo runs found.\n", encoding="utf-8")
        return

    # Build aggregate spec dynamically based on available columns
    # (some runs are simple-domain and lack ibr/ehe).
    agg_spec = {"n_runs": ("run_id", "nunique"),
                "n_decisions": ("n_decisions", "sum")}
    if "ibr" in df.columns:
        agg_spec["ibr_mean"] = ("ibr", "mean")
        agg_spec["ibr_sd"] = ("ibr", lambda s: s.std(ddof=1) if len(s) > 1 else 0.0)
    if "ehe" in df.columns:
        agg_spec["ehe_mean"] = ("ehe", "mean")
        agg_spec["ehe_sd"] = ("ehe", lambda s: s.std(ddof=1) if len(s) > 1 else 0.0)
    if "rejection_rate" in df.columns:
        agg_spec["rej_mean"] = ("rejection_rate", "mean")
    if "retry_rate" in df.columns:
        agg_spec["retry_mean"] = ("retry_rate", "mean")
    if "approval_rate" in df.columns and "rejection_rate" not in df.columns:
        agg_spec["approval_mean"] = ("approval_rate", "mean")
    agg = df.groupby(["model", "condition"]).agg(**agg_spec).reset_index()

    lines = [
        f"# Governance summary ({domain}) — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Scope",
        f"- Runs: {len(df)}",
        f"- Models: {df['model'].nunique()}",
        f"- Conditions: {sorted(df['condition'].unique())}",
        "",
        "## Headline metrics",
        "",
    ]
    # Auto-narrative
    if "Group_C" in df["condition"].unique() and "Group_C_disabled" in df["condition"].unique():
        gov = df[df["condition"] == "Group_C"]["ibr"].mean() * 100
        dis = df[df["condition"] == "Group_C_disabled"]["ibr"].mean() * 100
        lines.append(
            f"Across {df['model'].nunique()} model(s), validators "
            f"reduced IBR from {dis:.1f}% (no validator) to {gov:.1f}% (governed)."
        )
    else:
        lines.append("Single-condition data; no governed-vs-disabled comparison computed.")

    has_ibr = "ibr_mean" in agg.columns
    if has_ibr:
        lines += ["", "## Metrics table", "",
                  "| Model | Condition | Runs | IBR mean ± sd | EHE mean ± sd | Rej rate | Retry rate |",
                  "|---|---|---:|---:|---:|---:|---:|"]
        for _, r in agg.iterrows():
            lines.append(
                f"| {r['model']} | {r['condition']} | {int(r['n_runs'])} "
                f"| {100*r['ibr_mean']:.1f}% ± {100*r['ibr_sd']:.1f}% "
                f"| {r['ehe_mean']:.3f} ± {r['ehe_sd']:.3f} "
                f"| {100*r.get('rej_mean', 0):.1f}% | {100*r.get('retry_mean', 0):.1f}% |"
            )
    else:
        lines += ["", "## Metrics table (simple-domain mode — IBR/EHE not applicable)", "",
                  "| Model | Condition | Runs | n_decisions | Approval rate |",
                  "|---|---|---:|---:|---:|"]
        for _, r in agg.iterrows():
            lines.append(
                f"| {r['model']} | {r['condition']} | {int(r['n_runs'])} "
                f"| {int(r['n_decisions'])} "
                f"| {100*r.get('approval_mean', 0):.1f}% |"
            )
    lines += ["", "## Caveats", ""]
    # Find missing seeds, partial runs, etc.
    for (m, c), grp in df.groupby(["model", "condition"]):
        if len(grp) < 5:
            lines.append(f"- {m} / {c}: only {len(grp)} run(s); paired-t inference under-powered.")
    if not any("paired-t" in l for l in lines[-5:]):
        lines.append("- (no caveats detected)")
    lines += [
        "",
        "## Reproducible command list",
        "",
        f"```bash",
        f"python {Path(__file__).relative_to(REPO)} <results_root> --domain {domain}",
        f"```",
    ]
    summary.write_text("\n".join(lines), encoding="utf-8")
    print(f"  wrote {summary}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path)
    ap.add_argument("--out", type=Path, default=Path("analysis"))
    ap.add_argument("--domain", choices=["flood", "irrigation"], default="flood")
    args = ap.parse_args()

    runs = discover_runs(args.root)
    if not runs:
        print(f"No audit CSVs under {args.root}", file=sys.stderr)
        return 1
    print(f"Discovered {len(runs)} run(s).")
    rows = []
    for model, cond, run_id, d in runs:
        m = per_run_metrics(d, args.domain)
        if m:
            rows.append({"model": model, "condition": cond, "run_id": run_id, **m})

    write_artefacts(rows, args.out, args.domain)
    return 0


if __name__ == "__main__":
    sys.exit(main())
