#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

MODELS = [
    "gemma3_4b",
    "gemma3_12b",
    "gemma3_27b",
    "ministral3_3b",
    "ministral3_8b",
    "ministral3_14b",
]
GROUPS = ["Group_A", "Group_B", "Group_C"]

THINKING_RULE_IDS = {
    "extreme_threat_block",
    "elevation_threat_low",
    "relocation_threat_low",
}


def normalize_runs(run_tokens: str) -> list[str]:
    runs = [t.strip() for t in run_tokens.split(",") if t.strip()]
    return runs or ["Run_1"]


def extract_ta_label(text: str) -> str:
    t = (text or "").strip().upper()
    for token in ("VH", "VL", "H", "L", "M"):
        if re.search(rf"\b{token}\b", t):
            return token

    low = (text or "").lower()
    hi_kw = ["extreme", "severe", "catastrophic", "high risk", "very high", "afraid", "worried"]
    lo_kw = ["low", "minimal", "unlikely", "safe", "no risk"]

    if any(k in low for k in hi_kw):
        return "H"
    if any(k in low for k in lo_kw):
        return "L"
    return "M"


def norm_action_from_text(a: str) -> str | None:
    a = (a or "").strip().lower()
    if a in ("", "n/a", "relocated", "already relocated"):
        return None
    if "both" in a and "elevat" in a:
        return "both"
    if a in ("buy_insurance", "insurance") or "insur" in a:
        return "insurance"
    if a in ("elevate_house", "elevation") or "elevat" in a:
        return "elevation"
    if "relocat" in a:
        return "relocate"
    if a in ("do_nothing", "nothing") or "do nothing" in a:
        return "do_nothing"
    return "other"


def final_action(row: dict[str, str], group: str) -> str | None:
    if group == "Group_A":
        return norm_action_from_text(row.get("decision", "")) or norm_action_from_text(row.get("raw_llm_decision", ""))
    return norm_action_from_text(row.get("yearly_decision", ""))


def rr_flag_from_action(ta: str, action: str | None) -> bool:
    if action is None:
        return False
    if ta in ("H", "VH") and action == "do_nothing":
        return True
    if ta in ("L", "VL") and action == "relocate":
        return True
    if ta in ("L", "VL") and action in ("elevation", "both"):
        return True
    return False


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


def rejected_thinking_map(trace_path: Path) -> dict[tuple[str, str], bool]:
    out: dict[tuple[str, str], bool] = {}
    if not trace_path.exists():
        return out
    with open(trace_path, encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            if o.get("outcome") != "REJECTED":
                continue
            issues = o.get("validation_issues") or []
            rid_set = {str(it.get("rule_id", "")).strip().lower() for it in issues}
            if any(r in THINKING_RULE_IDS for r in rid_set):
                out[(str(o.get("agent_id")), str(o.get("year")))] = True
    return out


def compute_one(sim_path: Path, trace_path: Path, group: str) -> dict[str, float | int]:
    rows = list(csv.DictReader(open(sim_path, encoding="utf-8-sig")))
    rows.sort(key=lambda r: ((r.get("agent_id") or ""), int((r.get("year") or "0") or "0")))

    rej_thinking = rejected_thinking_map(trace_path) if group in ("Group_B", "Group_C") else {}

    prev_relocated = {}

    n_active = 0
    n_rr_final = 0
    n_rh_final = 0
    c4_final = Counter()

    for r in rows:
        aid = str(r.get("agent_id") or "")
        year = str(r.get("year") or "")

        was_relocated = prev_relocated.get(aid, False)
        now_relocated = str(r.get("relocated", "")).strip().lower() == "true"

        act = final_action(r, group)

        if (not was_relocated) and act is not None:
            n_active += 1
            ta = extract_ta_label(r.get("threat_appraisal", ""))

            if group == "Group_A":
                if rr_flag_from_action(ta, act):
                    n_rr_final += 1
            else:
                if rej_thinking.get((aid, year), False):
                    n_rr_final += 1

            # Strict feasibility contradiction channel (state-based)
            elevated_prev = str(r.get("elevated", "")).strip().lower() == "true"
            if elevated_prev and act in ("elevation", "both"):
                n_rh_final += 1

            a4 = "elevation" if act == "both" else act
            if a4 in ("do_nothing", "insurance", "elevation", "relocate"):
                c4_final[a4] += 1

        prev_relocated[aid] = now_relocated

    rr_final = (n_rr_final / n_active) if n_active else 0.0
    rh_final = (n_rh_final / n_active) if n_active else 0.0
    h4_final = shannon_norm(c4_final, 4)
    ehe4_final = h4_final * (1.0 - rh_final)

    return {
        "n_active": n_active,
        "n_rr_final": n_rr_final,
        "n_rh_final": n_rh_final,
        "R_R_final": rr_final,
        "R_H_final": rh_final,
        "H_norm_k4_final": h4_final,
        "EHE_k4_final": ehe4_final,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--joh-final-dir", default="examples/single_agent/results/JOH_FINAL")
    ap.add_argument("--runs", default="Run_1,Run_2,Run_3")
    ap.add_argument("--out-all", default="docs/wrr_metrics_rr_final_all_v1.csv")
    ap.add_argument("--out-summary", default="docs/wrr_metrics_rr_final_summary_v1.csv")
    args = ap.parse_args()

    runs = normalize_runs(args.runs)
    root = Path(args.joh_final_dir)

    all_rows: list[dict[str, str | int | float]] = []
    for m in MODELS:
        for g in GROUPS:
            for run in runs:
                sim = root / m / g / run / "simulation_log.csv"
                if not sim.exists():
                    continue
                trace = root / m / g / run / "raw" / "household_traces.jsonl"
                r = compute_one(sim, trace, g)
                r.update({"model": m, "group": g, "run": run})
                all_rows.append(r)

    fields = [
        "model",
        "group",
        "run",
        "n_active",
        "n_rr_final",
        "n_rh_final",
        "R_R_final",
        "R_H_final",
        "H_norm_k4_final",
        "EHE_k4_final",
    ]
    Path(args.out_all).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_all, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)

    by_group = defaultdict(list)
    for r in all_rows:
        by_group[r["group"]].append(r)

    sf = [
        "group",
        "n_cases",
        "R_R_final_mean",
        "R_H_final_mean",
        "H_norm_k4_final_mean",
        "EHE_k4_final_mean",
    ]
    with open(args.out_summary, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=sf)
        w.writeheader()
        for g in GROUPS:
            lst = by_group.get(g, [])
            if not lst:
                continue
            n = len(lst)

            def mean(k: str) -> float:
                return sum(float(x[k]) for x in lst) / n

            w.writerow(
                {
                    "group": g,
                    "n_cases": n,
                    "R_R_final_mean": mean("R_R_final"),
                    "R_H_final_mean": mean("R_H_final"),
                    "H_norm_k4_final_mean": mean("H_norm_k4_final"),
                    "EHE_k4_final_mean": mean("EHE_k4_final"),
                }
            )

    print(f"Wrote: {args.out_all}")
    print(f"Wrote: {args.out_summary}")
    print(f"Rows: {len(all_rows)}")


if __name__ == "__main__":
    main()

