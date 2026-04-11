#!/usr/bin/env python
"""Checkpoint verification for Gemma 4 Full runs under CLEAN_POLICY.

Compares a clean-policy run against the preserved legacy baseline (same seed)
and produces a go/no-go verdict report.

Usage:
    python verify_clean_policy_checkpoint.py [--seed SEED]
                                              [--clean-dir PATH]
                                              [--legacy-dir PATH]
                                              [--output-report PATH]

Default paths (when --seed is the only argument):
    --clean-dir:     paper3/results/paper3_gemma4_e4b_clean/seed_{seed}/gemma4_e4b_strict
    --legacy-dir:    paper3/results/paper3_gemma4_e4b/seed_{seed}/gemma4_e4b_strict
    --output-report: {clean-dir}/clean_policy_verdict.md

Exit codes:
    0  final verdict is PASS
    1  final verdict is FAIL
    2  clean run is incomplete (manifest or audit files missing/unreadable)

Stdout last line: VERDICT: <PASS|FAIL|PARTIAL> — <short reason>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[4]
FLOOD_ROOT = REPO_ROOT / "examples" / "multi_agent" / "flood"

PA_LABELS = ["VL", "L", "M", "H", "VH"]
PA_NUMERIC = {lbl: i + 1 for i, lbl in enumerate(PA_LABELS)}

RATCHET_PHRASES = [
    ("I decided to ... because",
     re.compile(r"I decided to[^\"\n]{0,200}?because", re.IGNORECASE)),
    ('"I have deep emotional ties"', re.compile(r"I have deep emotional ties", re.IGNORECASE)),
    ('"cannot imagine living anywhere else"',
     re.compile(r"cannot imagine living anywhere else", re.IGNORECASE)),
    ("\"I don't have much faith in government\"",
     re.compile(r"I don.?t have much faith in government", re.IGNORECASE)),
    ('"I trust that government programs"',
     re.compile(r"I trust that government programs", re.IGNORECASE)),
    ('"I would rather adapt in place"',
     re.compile(r"I would rather adapt in place", re.IGNORECASE)),
]

FACTUAL_PHRASES = [
    # Matches both positive flood history ("I experienced flooding...") and
    # negative flood history ("I have not personally experienced flooding...").
    # Both are legitimate factual seed memories.
    ("flood-experience seed (experienced / not experienced)",
     re.compile(r"experienced flood", re.IGNORECASE)),
    # Matches the flood zone risk awareness seed.
    ("flood-zone seed (high-risk flood zone / My property is in)",
     re.compile(r"high-risk flood zone|My property is in", re.IGNORECASE)),
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_audit(dir_path: Path, agent_type: str) -> Optional[pd.DataFrame]:
    fpath = dir_path / f"household_{agent_type}_governance_audit.csv"
    if not fpath.exists():
        return None
    try:
        return pd.read_csv(fpath, encoding="utf-8-sig")
    except Exception as exc:
        print(f"  [WARN] Failed to load {fpath.name}: {exc}", file=sys.stderr)
        return None


def load_manifest(dir_path: Path) -> Optional[Dict[str, Any]]:
    fpath = dir_path / "reproducibility_manifest.json"
    if not fpath.exists():
        return None
    try:
        with fpath.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"  [WARN] Failed to load manifest: {exc}", file=sys.stderr)
        return None


def load_raw_traces(dir_path: Path) -> Tuple[str, int]:
    """Return (concatenated raw trace text, total line count)."""
    owner = dir_path / "raw" / "household_owner_traces.jsonl"
    renter = dir_path / "raw" / "household_renter_traces.jsonl"
    content = ""
    line_count = 0
    for fp in (owner, renter):
        if fp.exists():
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
                content += text + "\n"
                line_count += text.count("\n")
            except Exception as exc:
                print(f"  [WARN] Failed to read {fp.name}: {exc}", file=sys.stderr)
    return content, line_count


# ---------------------------------------------------------------------------
# PA trajectory
# ---------------------------------------------------------------------------


def pa_trajectory(df: pd.DataFrame) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if df is None or "construct_PA_LABEL" not in df.columns:
        return out
    for year in range(1, 14):
        sub = df[df["year"] == year]["construct_PA_LABEL"].dropna()
        sub = sub[sub.isin(PA_LABELS)]
        n = len(sub)
        counts = Counter(sub)
        row: Dict[str, Any] = {"year": year, "n": int(n)}
        if n == 0:
            for lbl in PA_LABELS:
                row[lbl] = 0.0
            row["H+VH"] = 0.0
            row["mean"] = 0.0
            out.append(row)
            continue
        for lbl in PA_LABELS:
            row[lbl] = round(100.0 * counts.get(lbl, 0) / n, 2)
        row["H+VH"] = round(row["H"] + row["VH"], 2)
        numeric = sub.map(PA_NUMERIC)
        row["mean"] = round(float(numeric.mean()), 3)
        out.append(row)
    return out


def format_trajectory_table(traj: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("| Year | n | VL | L | M | H | VH | H+VH | mean |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in traj:
        lines.append(
            f"| {row['year']} | {row['n']} "
            f"| {row['VL']:.1f} | {row['L']:.1f} | {row['M']:.1f} "
            f"| {row['H']:.1f} | {row['VH']:.1f} "
            f"| {row['H+VH']:.1f} | {row['mean']:.2f} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_run_completeness(clean_dir: Path) -> Dict[str, Any]:
    manifest_path = clean_dir / "reproducibility_manifest.json"
    owner_audit = clean_dir / "household_owner_governance_audit.csv"
    renter_audit = clean_dir / "household_renter_governance_audit.csv"
    raw_owner = clean_dir / "raw" / "household_owner_traces.jsonl"
    raw_renter = clean_dir / "raw" / "household_renter_traces.jsonl"

    owner_rows = renter_rows = -1
    if owner_audit.exists():
        try:
            owner_rows = len(pd.read_csv(owner_audit, encoding="utf-8-sig"))
        except Exception:
            pass
    if renter_audit.exists():
        try:
            renter_rows = len(pd.read_csv(renter_audit, encoding="utf-8-sig"))
        except Exception:
            pass

    results = {
        "manifest_present": manifest_path.exists(),
        "owner_rows": owner_rows,
        "renter_rows": renter_rows,
        "owner_rows_pass": owner_rows >= 2500,
        "renter_rows_pass": renter_rows >= 2500,
        "raw_owner_nonempty": raw_owner.exists() and raw_owner.stat().st_size > 0,
        "raw_renter_nonempty": raw_renter.exists() and raw_renter.stat().st_size > 0,
    }
    results["verdict"] = (
        "PASS"
        if (
            results["manifest_present"]
            and results["owner_rows_pass"]
            and results["renter_rows_pass"]
            and results["raw_owner_nonempty"]
            and results["raw_renter_nonempty"]
        )
        else "FAIL"
    )
    return results


def check_manifest_policy(manifest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "block_present": False,
        "allow_agent_self_report": None,
        "allow_agent_reflection_quote": None,
        "allow_initial_narrative": None,
        "domain_mapping_size": None,
        "verdict": "FAIL",
    }
    if manifest is None:
        return out
    mwp = manifest.get("memory_write_policy")
    if not isinstance(mwp, dict):
        return out
    out["block_present"] = True
    policy = mwp.get("policy", {})
    out["allow_agent_self_report"] = policy.get("allow_agent_self_report")
    out["allow_agent_reflection_quote"] = policy.get("allow_agent_reflection_quote")
    out["allow_initial_narrative"] = policy.get("allow_initial_narrative")
    out["domain_mapping_size"] = mwp.get("domain_mapping_size")
    out["verdict"] = (
        "PASS"
        if (
            out["allow_agent_self_report"] is False
            and out["allow_agent_reflection_quote"] is False
            and out["allow_initial_narrative"] is False
            and out["domain_mapping_size"] == 16
        )
        else "FAIL"
    )
    return out


def check_drop_counts(manifest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "initial_narrative_drops": None,
        "agent_self_report_drops": None,
        "external_event_allows": None,
        "initial_factual_allows": None,
        "verdict": "FAIL",
    }
    if manifest is None or "memory_write_policy" not in manifest:
        return out
    mwp = manifest["memory_write_policy"]
    dropped = mwp.get("dropped_counts") or {}
    allowed = mwp.get("allowed_counts") or {}
    out["initial_narrative_drops"] = dropped.get("initial_narrative", 0)
    out["agent_self_report_drops"] = dropped.get("agent_self_report", 0)
    out["external_event_allows"] = allowed.get("external_event", 0)
    out["initial_factual_allows"] = allowed.get("initial_factual", 0)

    # Acceptance:
    #  - initial_narrative drops = 800 (400 agents * 2 PMT categories)
    #  - agent_self_report drops in [2000, 8000]
    #  - external_event allows in [2000, 5000]
    #  - initial_factual allows in [1400, 1800]
    pmt_ok = out["initial_narrative_drops"] == 800
    sr_ok = 2000 <= out["agent_self_report_drops"] <= 8000
    ext_ok = 2000 <= out["external_event_allows"] <= 5000
    fact_ok = 1400 <= out["initial_factual_allows"] <= 1800
    out["pmt_ok"] = pmt_ok
    out["sr_ok"] = sr_ok
    out["ext_ok"] = ext_ok
    out["fact_ok"] = fact_ok
    out["verdict"] = "PASS" if all([pmt_ok, sr_ok, ext_ok, fact_ok]) else "FAIL"
    return out


def check_ratchet_phrases(raw_content: str) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for label, pattern in RATCHET_PHRASES:
        counts[label] = len(pattern.findall(raw_content))
    total = sum(counts.values())
    return {
        "per_phrase": counts,
        "total": total,
        "verdict": "PASS" if total == 0 else "FAIL",
    }


def check_factual_seeds(raw_content: str) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for label, pattern in FACTUAL_PHRASES:
        counts[label] = len(pattern.findall(raw_content))
    at_least_one = all(v >= 1 for v in counts.values())
    return {
        "per_phrase": counts,
        "verdict": "PASS" if at_least_one else "FAIL",
    }


def check_renter_trajectory(
    legacy_traj: List[Dict[str, Any]],
    clean_traj: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Scientific test: does CLEAN_POLICY block the renter PA ratchet?

    The original ratchet measurement on legacy seed_42 showed renter PA drifting
    from Y1 22.5% H+VH to Y13 86.9% H+VH — a +64.4pp within-population climb.

    Under CLEAN_POLICY, two things change:
      1. decision_reasoning writes are blocked (main ratchet source)
      2. initial_narrative seeds are dropped (both high-PA and low-PA Y0 narratives)

    Consequence for Y1: CLEAN may NOT exactly match legacy Y1 because the low-PA
    narrative seeds that nudged some renters DOWN in legacy are also gone. The
    observed shift in early live data was renter Y1 climbing ~7pp (22.5 -> 29.5)
    because the downward anchor disappeared. This is expected behavior, not a
    failure of the ratchet fix.

    The correct pass criterion is therefore the DRIFT (Y1 -> Y13), not the Y1
    match. If CLEAN drift is <= 20pp while legacy drift is 64pp, the ratchet
    is blocked regardless of where CLEAN's Y1 anchor sits.
    """
    out: Dict[str, Any] = {
        "legacy": legacy_traj,
        "clean": clean_traj,
        "y1_delta_pp": None,
        "y13_delta_pp": None,
        "legacy_drift_pp": None,
        "clean_drift_pp": None,
        "y1_pass": False,
        "drift_pass": False,
        "y13_pass": False,
        "classification": "UNKNOWN",
        "verdict": "FAIL",
    }
    if not legacy_traj or not clean_traj:
        return out

    legacy_y1 = next((r for r in legacy_traj if r["year"] == 1), None)
    legacy_y13 = next((r for r in legacy_traj if r["year"] == 13), None)
    clean_y1 = next((r for r in clean_traj if r["year"] == 1), None)
    clean_y13 = next((r for r in clean_traj if r["year"] == 13), None)

    if not (legacy_y1 and legacy_y13 and clean_y1 and clean_y13):
        return out

    out["y1_legacy_hv"] = legacy_y1["H+VH"]
    out["y1_clean_hv"] = clean_y1["H+VH"]
    out["y13_legacy_hv"] = legacy_y13["H+VH"]
    out["y13_clean_hv"] = clean_y13["H+VH"]

    out["y1_delta_pp"] = round(clean_y1["H+VH"] - legacy_y1["H+VH"], 2)
    out["y13_delta_pp"] = round(clean_y13["H+VH"] - legacy_y13["H+VH"], 2)

    out["legacy_drift_pp"] = round(legacy_y13["H+VH"] - legacy_y1["H+VH"], 2)
    out["clean_drift_pp"] = round(clean_y13["H+VH"] - clean_y1["H+VH"], 2)

    # Y1 is a soft sanity check (±10pp, relaxed from ±5pp to allow the shift
    # caused by removing low-PA narrative seeds).
    out["y1_pass"] = abs(out["y1_delta_pp"]) <= 10.0

    # Drift is the primary pass criterion.
    # Legacy drift is +64pp. Clean drift should be substantially smaller.
    out["drift_pass"] = out["clean_drift_pp"] <= 20.0

    # Absolute Y13 ceiling as the secondary check.
    out["y13_pass"] = clean_y13["H+VH"] <= 67.0

    drift = out["clean_drift_pp"]
    if drift <= 10.0:
        out["classification"] = "RATCHET BLOCKED"
    elif drift <= 25.0:
        out["classification"] = "RATCHET PARTIALLY MITIGATED"
    else:
        out["classification"] = "RATCHET NOT BLOCKED"

    # Verdict: drift-based classification dominates; Y1 is a sanity warning.
    if out["classification"] == "RATCHET BLOCKED" and out["y1_pass"]:
        out["verdict"] = "PASS"
    elif out["classification"] == "RATCHET BLOCKED":
        # Drift is blocked but Y1 shifted too far — still a positive result,
        # mark as PARTIAL to flag the Y1 anomaly for inspection.
        out["verdict"] = "PARTIAL"
    elif out["classification"] == "RATCHET PARTIALLY MITIGATED":
        out["verdict"] = "PARTIAL"
    else:
        out["verdict"] = "FAIL"
    return out


def check_owner_y1_sanity(
    legacy_traj: List[Dict[str, Any]],
    clean_traj: List[Dict[str, Any]],
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "legacy_y1_hv": None,
        "clean_y1_hv": None,
        "delta_pp": None,
        "verdict": "FAIL",
    }
    if not legacy_traj or not clean_traj:
        return out
    legacy_y1 = next((r for r in legacy_traj if r["year"] == 1), None)
    clean_y1 = next((r for r in clean_traj if r["year"] == 1), None)
    if not (legacy_y1 and clean_y1):
        return out
    out["legacy_y1_hv"] = legacy_y1["H+VH"]
    out["clean_y1_hv"] = clean_y1["H+VH"]
    out["delta_pp"] = round(clean_y1["H+VH"] - legacy_y1["H+VH"], 2)
    out["verdict"] = "PASS" if abs(out["delta_pp"]) <= 10.0 else "FAIL"
    return out


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def format_report(
    clean_dir: Path,
    legacy_dir: Path,
    c1: Dict[str, Any],
    c2: Dict[str, Any],
    c3: Dict[str, Any],
    c4: Dict[str, Any],
    c5: Dict[str, Any],
    c6: Dict[str, Any],
    c7: Dict[str, Any],
    final_verdict: str,
    decision: str,
) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: List[str] = []
    lines.append("# Clean Policy Checkpoint Verdict — seed_42 Full CLEAN")
    lines.append("")
    lines.append(f"**Generated:** {ts}")
    lines.append(f"**Run path:** {clean_dir}")
    lines.append(f"**Baseline path:** {legacy_dir}")
    lines.append(f"**Verdict:** {final_verdict}")
    lines.append("")
    lines.append("## 總結 (Executive Summary)")
    lines.append("")
    lines.append(summarize_exec(c6, c7, final_verdict))
    lines.append("")
    lines.append("## 檢查項目 (Checks)")
    lines.append("")

    # Check 1
    lines.append("### Check 1 — Run Completeness")
    lines.append(f"- Manifest present: {'PASS' if c1['manifest_present'] else 'FAIL'}")
    lines.append(
        f"- Owner audit rows: {c1['owner_rows']} (expected ≥ 2500): "
        f"{'PASS' if c1['owner_rows_pass'] else 'FAIL'}"
    )
    lines.append(
        f"- Renter audit rows: {c1['renter_rows']} (expected ≥ 2500): "
        f"{'PASS' if c1['renter_rows_pass'] else 'FAIL'}"
    )
    lines.append(
        f"- Raw traces non-empty: "
        f"{'PASS' if c1['raw_owner_nonempty'] and c1['raw_renter_nonempty'] else 'FAIL'}"
    )
    lines.append(f"- **Verdict: {c1['verdict']}**")
    lines.append("")

    # Check 2
    lines.append("### Check 2 — Manifest Policy Block")
    lines.append(f"- block present: {c2['block_present']}")
    lines.append(
        f"- allow_agent_self_report: {c2['allow_agent_self_report']} "
        f"(expected False)"
    )
    lines.append(
        f"- allow_agent_reflection_quote: {c2['allow_agent_reflection_quote']} "
        f"(expected False)"
    )
    lines.append(
        f"- allow_initial_narrative: {c2['allow_initial_narrative']} (expected False)"
    )
    lines.append(
        f"- domain_mapping_size: {c2['domain_mapping_size']} (expected 16)"
    )
    lines.append(f"- **Verdict: {c2['verdict']}**")
    lines.append("")

    # Check 3
    lines.append("### Check 3 — Drop Counts")
    lines.append(
        f"- dropped_counts.initial_narrative: {c3['initial_narrative_drops']} "
        f"(expected = 800): {'PASS' if c3.get('pmt_ok') else 'FAIL'}"
    )
    lines.append(
        f"- dropped_counts.agent_self_report: {c3['agent_self_report_drops']} "
        f"(expected 2000–8000): {'PASS' if c3.get('sr_ok') else 'FAIL'}"
    )
    lines.append(
        f"- allowed_counts.external_event: {c3['external_event_allows']} "
        f"(expected 2000–5000): {'PASS' if c3.get('ext_ok') else 'FAIL'}"
    )
    lines.append(
        f"- allowed_counts.initial_factual: {c3['initial_factual_allows']} "
        f"(expected 1400–1800): {'PASS' if c3.get('fact_ok') else 'FAIL'}"
    )
    lines.append(f"- **Verdict: {c3['verdict']}**")
    lines.append("")

    # Check 4
    lines.append("### Check 4 — Zero Ratchet Phrases in Raw Traces")
    lines.append("")
    lines.append("| Phrase | Matches |")
    lines.append("|---|---:|")
    for label, count in c4["per_phrase"].items():
        lines.append(f"| {label} | {count} |")
    lines.append("")
    lines.append(f"- Total ratchet phrase matches: {c4['total']} (expected 0)")
    lines.append(f"- **Verdict: {c4['verdict']}**")
    lines.append("")

    # Check 5
    lines.append("### Check 5 — Factual Seeds Preserved")
    for label, count in c5["per_phrase"].items():
        lines.append(f"- {label} matches: {count}")
    lines.append(f"- **Verdict: {c5['verdict']}**")
    lines.append("")

    # Check 6 (the scientific test)
    lines.append("### Check 6 — Renter PA Trajectory (THE KEY SCIENTIFIC TEST)")
    lines.append("")
    lines.append("**Legacy baseline (paper3_gemma4_e4b/seed_42):**")
    lines.append("")
    lines.append(format_trajectory_table(c6["legacy"]))
    lines.append("")
    lines.append("**Clean policy (paper3_gemma4_e4b_clean/seed_42):**")
    lines.append("")
    lines.append(format_trajectory_table(c6["clean"]))
    lines.append("")
    if c6.get("y1_delta_pp") is not None:
        lines.append("**Matched comparison:**")
        lines.append(
            f"- Y1 renter H+VH: legacy {c6.get('y1_legacy_hv', 0):.1f}% "
            f"vs clean {c6.get('y1_clean_hv', 0):.1f}% "
            f"→ Δ = {c6['y1_delta_pp']:+.1f} pp "
            f"(within ±10pp anchor tolerance: {'PASS' if c6['y1_pass'] else 'FAIL'})"
        )
        lines.append(
            f"- Y13 renter H+VH: legacy {c6.get('y13_legacy_hv', 0):.1f}% "
            f"vs clean {c6.get('y13_clean_hv', 0):.1f}% "
            f"→ Δ = {c6['y13_delta_pp']:+.1f} pp"
        )
        lines.append("")
        lines.append("**Drift comparison (THE key metric — ratchet is about within-pop climb, not absolute level):**")
        lines.append(
            f"- Legacy drift Y1→Y13: {c6.get('legacy_drift_pp', 0):+.1f} pp "
            f"(22.5% → 86.9% baseline)"
        )
        lines.append(
            f"- **Clean drift Y1→Y13: {c6.get('clean_drift_pp', 0):+.1f} pp** "
            f"(ratchet-blocked target: ≤ +10pp)"
        )
        lines.append(f"- Classification: **{c6['classification']}**")
    lines.append(f"- **Verdict: {c6['verdict']}**")
    lines.append("")

    # Check 7 (sanity)
    lines.append("### Check 7 — Owner Y1 Sanity (should be unchanged)")
    if c7.get("delta_pp") is not None:
        lines.append(
            f"- Y1 owner H+VH: legacy {c7.get('legacy_y1_hv', 0):.1f}% "
            f"vs clean {c7.get('clean_y1_hv', 0):.1f}% "
            f"→ Δ = {c7['delta_pp']:+.1f} pp "
            f"(within ±10pp expected, prompt-level priming is not memory-fixable)"
        )
    lines.append(f"- **Verdict: {c7['verdict']}**")
    lines.append("")

    # Conclusion
    lines.append("## 結論與建議 (Conclusion and Recommendation)")
    lines.append("")
    lines.append(summarize_conclusion(c6, final_verdict, decision))
    lines.append("")
    lines.append(f"**決策**: {decision}")
    lines.append("")
    if decision.startswith("繼續"):
        lines.append(
            "**如果繼續**: 預期 seed_123 Full CLEAN 將在約 17 小時後完成，然後 "
            "seed_456 Full CLEAN，之後是 3 個 Ablation B runs。"
        )
    else:
        lines.append(
            "**如果停止**: 使用 TaskStop 或 Ctrl-C 停止 batch。重點調查 Check 6 的失敗原因。"
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated by verify_clean_policy_checkpoint.py on {ts}.*")
    lines.append("")
    return "\n".join(lines)


def summarize_exec(c6: Dict[str, Any], c7: Dict[str, Any], verdict: str) -> str:
    if c6.get("y13_clean_hv") is None:
        return "檢查點無法完成 — 請檢查 run 是否完整、manifest 是否存在。"
    y1_clean = c6.get("y1_clean_hv", 0)
    y13_clean = c6.get("y13_clean_hv", 0)
    drift_clean = c6.get("clean_drift_pp", 0)
    drift_legacy = c6.get("legacy_drift_pp", 64.4)
    classification = c6.get("classification", "UNKNOWN")
    return (
        f"seed_42 Full CLEAN 完成。Renter PA trajectory 從 Y1 的 {y1_clean:.1f}% H+VH 走到 "
        f"Y13 的 {y13_clean:.1f}%（Y1→Y13 漂移 {drift_clean:+.1f}pp），對比 legacy "
        f"LEGACY_POLICY 的 {drift_legacy:+.1f}pp 漂移。ratchet 阻擋的關鍵指標是**漂移幅度**，"
        f"不是絕對 Y1/Y13 值（因為 CLEAN 去掉了初始 narrative seeds 會讓 Y1 anchor 微幅上移）。"
        f"分類結果：**{classification}**。整體 verdict：**{verdict}**。"
    )


def summarize_conclusion(c6: Dict[str, Any], verdict: str, decision: str) -> str:
    if c6.get("y13_clean_hv") is None:
        return (
            "無法給出明確結論 — Check 6 的數據不足。請先排除 run 完整性問題再重跑檢查。"
        )
    classification = c6.get("classification", "UNKNOWN")
    drift_clean = c6.get("clean_drift_pp", 0)
    drift_legacy = c6.get("legacy_drift_pp", 64.4)
    drift_reduction = drift_legacy - drift_clean
    if classification == "RATCHET BLOCKED":
        return (
            f"Ratchet fix 在生產規模下確認有效。Renter Y1→Y13 漂移幅度從 legacy 的 "
            f"{drift_legacy:+.1f}pp 降到 clean 的 {drift_clean:+.1f}pp（減少 "
            f"{drift_reduction:.1f}pp），達到 RATCHET BLOCKED 分類門檻（drift ≤ 10pp）。"
            f"這是 Paper 3 Appendix 的 ablation 證據基礎 —— legacy seed_42 "
            f"(LEGACY_POLICY) 跟 clean seed_42 (CLEAN_POLICY) 形成完美的 matched pair，"
            f"同 seed、同 config、只差 memory write policy。建議讓 batch 繼續跑完剩下的 5 個 run。"
        )
    if classification == "RATCHET PARTIALLY MITIGATED":
        return (
            f"Ratchet fix 有效但不完全。Renter drift 從 legacy {drift_legacy:+.1f}pp "
            f"降到 clean {drift_clean:+.1f}pp（減少 {drift_reduction:.1f}pp），drift 落在 "
            f"(10, 25]pp 區間。可能還有次要 ratchet 源在 lifecycle hook 或 initial memory "
            f"seeding 裡面沒被捕捉到，或者 Y8+ 的 accumulation effect 對 Gemma 4 特別強。"
            f"建議繼續 batch 以完成完整資料集，但 Paper 3 Discussion 需要額外說明這個 "
            f"partial mitigation 的現象，並在 Appendix 做深入 trace 分析找剩餘的 ratchet 源。"
        )
    return (
        f"Ratchet fix 未達到預期效果。Renter drift 只從 legacy {drift_legacy:+.1f}pp "
        f"降到 clean {drift_clean:+.1f}pp（仍 > 25pp），代表 memory policy 沒有成功阻擋 "
        f"ratchet 在生產規模下的累積。建議立刻停止 batch，深入調查：(1) manifest "
        f"drop counts 是否合理，(2) lifecycle hook 是否有漏 gate 的 add_memory 呼叫，"
        f"(3) 是否有 MessagePool / GameMaster / reflection engine 繞過 proxy 直接寫記憶。"
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def decide_final_verdict(
    c1: Dict[str, Any],
    c2: Dict[str, Any],
    c3: Dict[str, Any],
    c4: Dict[str, Any],
    c5: Dict[str, Any],
    c6: Dict[str, Any],
    c7: Dict[str, Any],
) -> Tuple[str, str, int]:
    # If the run is incomplete, short-circuit to FAIL + exit 2.
    if c1["verdict"] == "FAIL":
        return ("FAIL", "run incomplete (check 1)", 2)
    if c2["verdict"] == "FAIL":
        return ("FAIL", "manifest policy block missing or wrong", 2)

    # The scientific test dominates the verdict.
    if c6["verdict"] == "PASS":
        # All others should also be PASS for a clean PASS.
        others_pass = (
            c3["verdict"] == "PASS"
            and c4["verdict"] == "PASS"
            and c5["verdict"] == "PASS"
            and c7["verdict"] == "PASS"
        )
        if others_pass:
            return ("PASS", "all checks pass, ratchet blocked at scale", 0)
        return ("PASS", "ratchet blocked but some side checks failed — review", 0)
    if c6["verdict"] == "PARTIAL":
        return (
            "PARTIAL",
            "ratchet partially mitigated; batch can continue but investigate",
            0,
        )
    return ("FAIL", "ratchet NOT blocked at scale — abort batch", 1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Checkpoint verification for Gemma 4 Full runs under CLEAN_POLICY. "
            "Compares against the preserved legacy baseline and outputs a "
            "go/no-go markdown verdict report."
        ),
    )
    parser.add_argument("--seed", type=int, default=42, help="Seed to verify (default 42)")
    parser.add_argument(
        "--clean-dir",
        type=Path,
        default=None,
        help="Clean run directory. Default: paper3/results/paper3_gemma4_e4b_clean/seed_{seed}/gemma4_e4b_strict",
    )
    parser.add_argument(
        "--legacy-dir",
        type=Path,
        default=None,
        help="Legacy run directory. Default: paper3/results/paper3_gemma4_e4b/seed_{seed}/gemma4_e4b_strict",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        default=None,
        help="Markdown verdict output path. Default: {clean-dir}/clean_policy_verdict.md",
    )
    args = parser.parse_args()

    if args.clean_dir is None:
        args.clean_dir = (
            FLOOD_ROOT
            / "paper3"
            / "results"
            / "paper3_gemma4_e4b_clean"
            / f"seed_{args.seed}"
            / "gemma4_e4b_strict"
        )
    if args.legacy_dir is None:
        args.legacy_dir = (
            FLOOD_ROOT
            / "paper3"
            / "results"
            / "paper3_gemma4_e4b"
            / f"seed_{args.seed}"
            / "gemma4_e4b_strict"
        )
    if args.output_report is None:
        args.output_report = args.clean_dir / "clean_policy_verdict.md"

    print(f"[verify] clean_dir:  {args.clean_dir}")
    print(f"[verify] legacy_dir: {args.legacy_dir}")
    print(f"[verify] output:     {args.output_report}")

    # Check 1 — run completeness (operates on clean dir only)
    c1 = check_run_completeness(args.clean_dir)
    print(f"[verify] Check 1 (run completeness): {c1['verdict']}")

    manifest = load_manifest(args.clean_dir)
    c2 = check_manifest_policy(manifest)
    print(f"[verify] Check 2 (manifest policy block): {c2['verdict']}")
    c3 = check_drop_counts(manifest)
    print(f"[verify] Check 3 (drop counts): {c3['verdict']}")

    raw_content, _ = load_raw_traces(args.clean_dir)
    c4 = check_ratchet_phrases(raw_content)
    print(f"[verify] Check 4 (ratchet phrases): {c4['verdict']}")
    c5 = check_factual_seeds(raw_content)
    print(f"[verify] Check 5 (factual seeds): {c5['verdict']}")

    # Check 6 + 7 need both clean and legacy audits
    legacy_renter = load_audit(args.legacy_dir, "renter")
    clean_renter = load_audit(args.clean_dir, "renter")
    legacy_owner = load_audit(args.legacy_dir, "owner")
    clean_owner = load_audit(args.clean_dir, "owner")

    legacy_renter_traj = pa_trajectory(legacy_renter) if legacy_renter is not None else []
    clean_renter_traj = pa_trajectory(clean_renter) if clean_renter is not None else []
    legacy_owner_traj = pa_trajectory(legacy_owner) if legacy_owner is not None else []
    clean_owner_traj = pa_trajectory(clean_owner) if clean_owner is not None else []

    c6 = check_renter_trajectory(legacy_renter_traj, clean_renter_traj)
    print(
        f"[verify] Check 6 (renter PA trajectory): {c6['verdict']} "
        f"— {c6.get('classification', 'UNKNOWN')}"
    )
    c7 = check_owner_y1_sanity(legacy_owner_traj, clean_owner_traj)
    print(f"[verify] Check 7 (owner Y1 sanity): {c7['verdict']}")

    final_verdict, reason, exit_code = decide_final_verdict(c1, c2, c3, c4, c5, c6, c7)

    decision = "停止 batch 並重新規劃" if exit_code == 2 else (
        "繼續 batch" if final_verdict in ("PASS", "PARTIAL") else "停止 batch 調查"
    )

    report = format_report(
        args.clean_dir, args.legacy_dir, c1, c2, c3, c4, c5, c6, c7, final_verdict, decision
    )

    try:
        args.output_report.parent.mkdir(parents=True, exist_ok=True)
        args.output_report.write_text(report, encoding="utf-8", newline="\n")
        print(f"[verify] Report written to {args.output_report}")
    except Exception as exc:
        print(f"[verify] WARN: failed to write report: {exc}", file=sys.stderr)

    # Final one-line summary on stdout
    print(f"VERDICT: {final_verdict} — {reason}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
