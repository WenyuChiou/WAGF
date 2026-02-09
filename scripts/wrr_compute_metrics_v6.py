#!/usr/bin/env python
"""
Compute WRR v6 flood metrics from JOH_FINAL.

Default outputs:
- docs/wrr_metrics_all_models_v6.csv
- docs/wrr_metrics_group_summary_v6.csv
- docs/wrr_metrics_vs_groupA_v6.csv
- docs/wrr_metrics_completion_v6.csv

Design goals:
- Works during ongoing experiments (partial matrix is allowed).
- Supports Run_1 / Run_2 / Run_3 in one pass.
- Keeps formulas aligned with docs/wrr-metric-calculation-spec-v6.md.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple


def norm_action(row: Dict[str, str], group: str) -> Optional[str]:
    """Normalize final action to canonical labels used for entropy and rule checks."""
    if group == "Group_A":
        d = (row.get("decision") or "").strip().lower()
        if d in ("", "already relocated"):
            return None
        if "both" in d:
            return "both"
        if "only flood insurance" in d or "insurance" in d:
            return "insurance"
        if "only house elevation" in d or "elevat" in d:
            return "elevation"
        if "relocat" in d:
            return "relocate"
        if "do nothing" in d or "nothing" in d:
            return "do_nothing"
        return "other"

    d = (row.get("yearly_decision") or "").strip().lower()
    if d in ("", "n/a", "relocated"):
        return None
    if d == "buy_insurance":
        return "insurance"
    if d == "elevate_house":
        return "elevation"
    if d == "relocate":
        return "relocate"
    if d == "do_nothing":
        return "do_nothing"
    return "other"


def extract_ta_label(text: str) -> str:
    """
    Extract threat appraisal label.

    Priority:
    1) explicit categorical token: VH, VL, H, L, M
    2) fallback keyword mapping for free text (primarily Group_A)
    """
    t = (text or "").strip().upper()
    for token in ("VH", "VL", "H", "L", "M"):
        if re.search(rf"\b{token}\b", t):
            return token

    low = (text or "").lower()
    hi_kw = [
        "extreme",
        "severe",
        "catastrophic",
        "high risk",
        "very high",
        "dangerous",
        "afraid",
        "worried",
    ]
    lo_kw = ["low", "minimal", "unlikely", "safe", "no risk"]

    if any(k in low for k in hi_kw):
        return "H"
    if any(k in low for k in lo_kw):
        return "L"
    return "M"


def shannon_norm(counts: Counter, k: int) -> float:
    n = sum(counts.values())
    if n <= 0 or k <= 1:
        return 0.0
    h = 0.0
    for c in counts.values():
        if c > 0:
            p = c / n
            h -= p * math.log2(p)
    return h / math.log2(k)


MODELS = [
    "gemma3_4b",
    "gemma3_12b",
    "gemma3_27b",
    "ministral3_3b",
    "ministral3_8b",
    "ministral3_14b",
]
GROUPS = ["Group_A", "Group_B", "Group_C"]


def normalize_runs(run_tokens: str) -> list[str]:
    runs: list[str] = []
    for tok in run_tokens.split(","):
        t = tok.strip()
        if t:
            runs.append(t)
    return runs or ["Run_1"]


def discover_csv_paths(
    joh_final_dir: Path, runs: Iterable[str]
) -> list[Tuple[str, str, str, Path]]:
    out: list[Tuple[str, str, str, Path]] = []
    for model in MODELS:
        for group in GROUPS:
            for run in runs:
                p = joh_final_dir / model / group / run / "simulation_log.csv"
                if p.exists():
                    out.append((model, group, run, p))
    return out


def compute_all_rows(joh_final_dir: Path, runs: Iterable[str]):
    rows_out = []
    for model, group, run, p in sorted(discover_csv_paths(joh_final_dir, runs)):

        with open(p, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))

        rows.sort(
            key=lambda r: ((r.get("agent_id") or ""), int((r.get("year") or "0") or "0"))
        )

        prev_rel = {}
        prev_elev = {}

        n_total = 0
        n_active = 0

        action_counts = Counter()

        # Decision-level numerator counts
        n_id = 0
        n_think = 0

        # Workload metrics
        intervention_rows = 0
        retry_rows = 0
        retry_sum = 0

        for r in rows:
            n_total += 1
            agent = r.get("agent_id") or ""

            curr_rel = str(r.get("relocated", "")).strip().lower() == "true"
            curr_elev = str(r.get("elevated", "")).strip().lower() == "true"

            pr = prev_rel.get(agent, False)
            pe = prev_elev.get(agent, False)

            act = norm_action(r, group)

            # Governance workload counters (event-level)
            if str(r.get("governance_intervention", "")).strip().lower() == "true":
                intervention_rows += 1
            rc = str(r.get("retry_count", "")).strip()
            try:
                rc_i = int(float(rc)) if rc else 0
            except Exception:
                rc_i = 0
            if rc_i > 0:
                retry_rows += 1
                retry_sum += rc_i

            # Active decision unit: not previously relocated + current row has a real action
            if (not pr) and (act is not None):
                n_active += 1
                action_counts[act] += 1

                # Identity/feasibility violation: re-elevation after already elevated
                if pe and act in ("elevation", "both"):
                    n_id += 1

                # Thinking-rule deviations (decision-level)
                ta = extract_ta_label(r.get("threat_appraisal", ""))
                if ta in ("H", "VH") and act == "do_nothing":
                    n_think += 1
                if ta in ("L", "VL") and act == "relocate":
                    n_think += 1
                if ta in ("L", "VL") and act in ("elevation", "both"):
                    n_think += 1

            prev_rel[agent] = curr_rel
            prev_elev[agent] = curr_elev

        # 5-category diversity
        c5 = Counter(
            {
                k: v
                for k, v in action_counts.items()
                if k in ("do_nothing", "insurance", "elevation", "both", "relocate")
            }
        )
        h5 = shannon_norm(c5, 5)

        # 4-category diversity (/4): merge both into elevation
        c4 = Counter(c5)
        c4["elevation"] += c4.get("both", 0)
        if "both" in c4:
            del c4["both"]
        h4 = shannon_norm(
            Counter(
                {
                    k: v
                    for k, v in c4.items()
                    if k in ("do_nothing", "insurance", "elevation", "relocate")
                }
            ),
            4,
        )

        rh = (n_id / n_active) if n_active else 0.0
        rr = (n_think / n_active) if n_active else 0.0
        pass_ratio = 1.0 - rr

        rows_out.append(
            {
                "model": model,
                "group": group,
                "run": run,
                "n_total_rows": n_total,
                "n_active": n_active,
                "n_id_violation": n_id,
                "n_think_violation": n_think,
                "R_H": rh,
                "R_R": rr,
                "rationality_pass": pass_ratio,
                "H_norm_k5": h5,
                "EHE_k5": h5 * (1.0 - rh),
                "H_norm_k4": h4,
                "EHE_k4": h4 * (1.0 - rh),
                "intervention_rows": intervention_rows,
                "retry_rows": retry_rows,
                "retry_sum": retry_sum,
            }
        )

    return rows_out


def write_outputs(
    rows_out,
    out_all: Path,
    out_group: Path,
    out_vs_group_a: Path,
    out_completion: Path,
):
    out_all.parent.mkdir(parents=True, exist_ok=True)

    all_fields = [
        "model",
        "group",
        "run",
        "n_total_rows",
        "n_active",
        "n_id_violation",
        "n_think_violation",
        "R_H",
        "R_R",
        "rationality_pass",
        "H_norm_k5",
        "EHE_k5",
        "H_norm_k4",
        "EHE_k4",
        "intervention_rows",
        "retry_rows",
        "retry_sum",
    ]
    with open(out_all, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=all_fields)
        w.writeheader()
        for r in rows_out:
            w.writerow(r)

    # Completion matrix for experiment tracking.
    completion_fields = ["model", "group", "run", "has_simulation_log"]
    have = {(r["model"], r["group"], r["run"]) for r in rows_out}
    with open(out_completion, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=completion_fields)
        w.writeheader()
        for model in MODELS:
            for group in GROUPS:
                for run in sorted({r["run"] for r in rows_out} | {"Run_1", "Run_2", "Run_3"}):
                    w.writerow(
                        {
                            "model": model,
                            "group": group,
                            "run": run,
                            "has_simulation_log": int((model, group, run) in have),
                        }
                    )

    by = defaultdict(list)
    for r in rows_out:
        by[r["group"]].append(r)

    group_fields = [
        "group",
        "n_cases",
        "n_models_observed",
        "runs_observed",
        "R_H_mean",
        "R_R_mean",
        "rationality_pass_mean",
        "H_norm_k5_mean",
        "EHE_k5_mean",
        "H_norm_k4_mean",
        "EHE_k4_mean",
        "intervention_rows_mean",
        "retry_rows_mean",
        "retry_sum_mean",
    ]
    with open(out_group, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=group_fields)
        w.writeheader()
        for g in ("Group_A", "Group_B", "Group_C"):
            lst = by.get(g, [])
            if not lst:
                continue
            n = len(lst)
            models_observed = sorted({x["model"] for x in lst})
            runs_observed = sorted({x["run"] for x in lst})

            def m(k: str) -> float:
                return sum(float(x[k]) for x in lst) / n

            w.writerow(
                {
                    "group": g,
                    "n_cases": n,
                    "n_models_observed": len(models_observed),
                    "runs_observed": ",".join(runs_observed),
                    "R_H_mean": m("R_H"),
                    "R_R_mean": m("R_R"),
                    "rationality_pass_mean": m("rationality_pass"),
                    "H_norm_k5_mean": m("H_norm_k5"),
                    "EHE_k5_mean": m("EHE_k5"),
                    "H_norm_k4_mean": m("H_norm_k4"),
                    "EHE_k4_mean": m("EHE_k4"),
                    "intervention_rows_mean": m("intervention_rows"),
                    "retry_rows_mean": m("retry_rows"),
                    "retry_sum_mean": m("retry_sum"),
                }
            )

    # Delta vs Group A, paired by (model, run).
    idx: dict[tuple[str, str, str], dict] = {}
    for r in rows_out:
        idx[(r["model"], r["group"], r["run"])] = r

    vs_fields = [
        "model",
        "run",
        "group",
        "R_H",
        "R_R",
        "H_norm_k4",
        "EHE_k4",
        "pct_reduction_R_H_vs_A",
        "pct_reduction_R_R_vs_A",
        "pct_gain_EHE_vs_A",
    ]
    with open(out_vs_group_a, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=vs_fields)
        w.writeheader()
        for model in MODELS:
            runs_seen = sorted({k[2] for k in idx if k[0] == model})
            for run in runs_seen:
                base = idx.get((model, "Group_A", run))
                if not base:
                    continue
                base_rh = float(base["R_H"])
                base_rr = float(base["R_R"])
                base_ehe = float(base["EHE_k4"])
                for group in ("Group_B", "Group_C"):
                    cur = idx.get((model, group, run))
                    if not cur:
                        continue
                    rh = float(cur["R_H"])
                    rr = float(cur["R_R"])
                    ehe = float(cur["EHE_k4"])
                    w.writerow(
                        {
                            "model": model,
                            "run": run,
                            "group": group,
                            "R_H": rh,
                            "R_R": rr,
                            "H_norm_k4": float(cur["H_norm_k4"]),
                            "EHE_k4": ehe,
                            "pct_reduction_R_H_vs_A": (
                                ((base_rh - rh) / base_rh) * 100.0 if base_rh > 0 else 0.0
                            ),
                            "pct_reduction_R_R_vs_A": (
                                ((base_rr - rr) / base_rr) * 100.0 if base_rr > 0 else 0.0
                            ),
                            "pct_gain_EHE_vs_A": (
                                ((ehe - base_ehe) / base_ehe) * 100.0 if base_ehe > 0 else 0.0
                            ),
                        }
                    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--joh-final-dir",
        default="examples/single_agent/results/JOH_FINAL",
        help="Directory containing model/group/run simulation logs.",
    )
    parser.add_argument(
        "--runs",
        default="Run_1,Run_2,Run_3",
        help="Comma-separated run folders to include.",
    )
    parser.add_argument(
        "--out-all",
        default="docs/wrr_metrics_all_models_v6.csv",
        help="Output CSV path for full model x group table.",
    )
    parser.add_argument(
        "--out-group",
        default="docs/wrr_metrics_group_summary_v6.csv",
        help="Output CSV path for group-mean summary.",
    )
    parser.add_argument(
        "--out-vs-group-a",
        default="docs/wrr_metrics_vs_groupA_v6.csv",
        help="Output CSV path for Group B/C deltas vs Group A (paired by model+run).",
    )
    parser.add_argument(
        "--out-completion",
        default="docs/wrr_metrics_completion_v6.csv",
        help="Output CSV path for model/group/run completion matrix.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    runs = normalize_runs(args.runs)
    rows = compute_all_rows(Path(args.joh_final_dir), runs)
    write_outputs(
        rows,
        Path(args.out_all),
        Path(args.out_group),
        Path(args.out_vs_group_a),
        Path(args.out_completion),
    )
    print(f"Wrote: {args.out_all}")
    print(f"Wrote: {args.out_group}")
    print(f"Wrote: {args.out_vs_group_a}")
    print(f"Wrote: {args.out_completion}")
    print(f"Rows: {len(rows)} (included runs: {', '.join(runs)})")


if __name__ == "__main__":
    main()
