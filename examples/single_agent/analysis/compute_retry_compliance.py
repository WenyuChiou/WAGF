"""Retry Compliance Pattern Analysis (SI Table 8).

Classifies each validator-intercepted retry into three patterns per the
Methods section "Retry Compliance Pattern Analysis":

  - Pattern A (appraisal downgrade): threat label lowered from {H, VH}
    to a lower set while the originally-proposed action is retained.
  - Pattern B (action upgrade): threat label maintained while action
    shifts to a more protective alternative.
  - Pattern C (joint recalibration): both threat label and action change.

Scope: Gemma-4 family V2 governed runs (the retry subset is only
meaningful when validators are active).

Data source: household_traces.jsonl raw records, where `skill_proposal`
contains the FINAL (post-retry) proposal and the ORIGINAL pre-retry
proposal is recoverable from `validation_issues[*].errors` strings
(format: "[Rule: <rule_id>] ... <action> restricted by ..." style).

Final TP = `skill_proposal.construct.TP_LABEL` if present else parsed
from skill_proposal.reasoning / raw audit CSV.

Output: .ai/retry_compliance_gemma4_v2_2026-04-22.md
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_ROOT = REPO_ROOT / "examples" / "single_agent" / "results"
AI_DIR = REPO_ROOT / ".ai"

MODELS = ["gemma4_e2b", "gemma4_e4b", "gemma4_26b"]
HIGH_SET = {"H", "VH"}
ACTION_NAMES = {"do_nothing", "buy_insurance", "elevate_house", "relocate", "relocated"}
PROTECTIVENESS = {"do_nothing": 0, "buy_insurance": 1, "elevate_house": 2, "relocate": 3}


def _norm_action(a: str) -> str:
    a = str(a).lower().strip()
    if a == "relocated":
        return "relocate"
    return a


def extract_original_action(validation_issues) -> Optional[str]:
    """Parse the original pre-retry action from validation_issues errors."""
    if not validation_issues:
        return None
    if not isinstance(validation_issues, list):
        return None
    # Look through all errors in all issues for an action name.
    for vi in validation_issues:
        if not isinstance(vi, dict):
            continue
        errors = vi.get("errors") or []
        if not isinstance(errors, list):
            continue
        for e in errors:
            es = str(e).lower()
            # Look for known action tokens in the error string.
            for a in ("elevate_house", "do_nothing", "buy_insurance", "relocate", "relocated"):
                if a in es:
                    return _norm_action(a)
    return None


def load_audit_index(run_dir: Path) -> Dict[Tuple[str, int], Dict[str, str]]:
    """Return {(agent_id_str, year_int) -> {final_tp, final_act}} from audit CSV."""
    p = run_dir / "household_governance_audit.csv"
    if not p.exists():
        return {}
    df = pd.read_csv(p, encoding="utf-8-sig")
    out: Dict[Tuple[str, int], Dict[str, str]] = {}
    for _, r in df.iterrows():
        try:
            key = (str(r["agent_id"]), int(r["year"]))
        except Exception:
            continue
        out[key] = {
            "final_tp": str(r.get("construct_TP_LABEL", "")).upper().strip(),
            "final_act": _norm_action(r.get("final_skill", "")),
        }
    return out


def classify_trace_row(
    trace: dict,
    audit_idx: Dict[Tuple[int, int], Dict[str, str]],
) -> Optional[str]:
    rc = trace.get("retry_count", 0) or 0
    try:
        rc = int(rc)
    except (ValueError, TypeError):
        rc = 0
    if rc <= 0:
        return None

    vi = trace.get("validation_issues") or []
    orig_act = extract_original_action(vi)
    if orig_act is None:
        return None

    try:
        key = (str(trace["agent_id"]), int(trace["year"]))
    except Exception:
        return None
    audit = audit_idx.get(key)
    if audit is None:
        return None
    final_tp = audit["final_tp"]
    final_act = audit["final_act"]
    if not final_tp or not final_act:
        return None

    action_retained = orig_act == final_act
    action_upgraded = (
        PROTECTIVENESS.get(final_act, -1) > PROTECTIVENESS.get(orig_act, -1)
    )
    final_tp_low = final_tp not in HIGH_SET  # VL/L/M

    # Heuristic: original TP was HIGH because the block was extreme_threat_block
    # / inaction-under-threat style rule. That is the dominant R1 interception.
    # Pattern A: action retained + final TP dropped out of {H, VH}.
    # Pattern B: action upgraded to more-protective + final TP still {H, VH}.
    # Pattern C: action changed AND final TP dropped.
    if action_retained and final_tp_low:
        return "A"
    if (not action_retained) and action_upgraded and (not final_tp_low):
        return "B"
    if (not action_retained) and final_tp_low:
        return "C"
    return None


def analyse_model(model: str, family: str, group: str) -> Dict[str, object]:
    counts = {"A": 0, "B": 0, "C": 0, "other": 0, "n_retries": 0}
    for run_i in range(1, 6):
        run_dir = RESULTS_ROOT / family / model / group / f"Run_{run_i}"
        jsonl = run_dir / "raw" / "household_traces.jsonl"
        if not jsonl.exists():
            continue
        audit_idx = load_audit_index(run_dir)
        with open(jsonl, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rc = d.get("retry_count", 0) or 0
                try:
                    rc = int(rc)
                except (ValueError, TypeError):
                    rc = 0
                if rc <= 0:
                    continue
                counts["n_retries"] += 1
                label = classify_trace_row(d, audit_idx)
                if label in ("A", "B", "C"):
                    counts[label] += 1
                else:
                    counts["other"] += 1
    return {"model": model, **counts}


def fmt_pct(n: int, total: int) -> str:
    if total <= 0:
        return "—"
    return f"{100.0 * n / total:.1f}%"


def main() -> int:
    AI_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for model in MODELS:
        r = analyse_model(model, "JOH_FINAL_v2", "Group_C")
        r["condition"] = "governed (V2)"
        rows.append(r)

    lines = [
        "# Retry Compliance Pattern Analysis — Gemma-4 V2",
        "",
        "Pattern definitions per Methods: Retry Compliance Pattern Analysis.",
        "Scope: governed (validator-active) runs only, 5 seeds each.",
        "",
        "| Model | Retries | Pattern A (TP↓, action retained) | Pattern B (TP held, action↑) | Pattern C (both change) | Other |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        total = r["n_retries"]
        lines.append(
            f"| {r['model']} | {total} | "
            f"{r['A']} ({fmt_pct(r['A'], total)}) | "
            f"{r['B']} ({fmt_pct(r['B'], total)}) | "
            f"{r['C']} ({fmt_pct(r['C'], total)}) | "
            f"{r['other']} ({fmt_pct(r['other'], total)}) |"
        )
    lines.extend([
        "",
        "**Method**: Original pre-retry action extracted from the trace-level ",
        "`validation_issues[*].errors` string (the rule engine embeds the blocked ",
        "action name in its error payload). Final TP and final action are read ",
        "from the approved post-retry audit row. `Other` = retries where the ",
        "original action could not be recovered (e.g. format-only retry with no ",
        "rule block), or the change pattern does not match A/B/C (e.g. lateral ",
        "action change at maintained TP).",
    ])

    md = AI_DIR / "retry_compliance_gemma4_v2_2026-04-22.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    print(f"[write] {md}")
    for r in rows:
        print(r)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
