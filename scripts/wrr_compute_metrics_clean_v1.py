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


def normalize_runs(run_tokens: str) -> list[str]:
    runs = [t.strip() for t in run_tokens.split(",") if t.strip()]
    return runs or ["Run_1"]


def extract_ta_label(text: str) -> str:
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
    neg_kw = ("not", "no", "never", "hardly", "rarely", "without")

    if any(k in low for k in hi_kw):
        return "H"
    for k in lo_kw:
        for m in re.finditer(re.escape(k), low):
            pre = low[max(0, m.start() - 20) : m.start()]
            if any(n in pre.split() for n in neg_kw):
                continue
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


def intent_action(row: dict[str, str], group: str) -> str | None:
    if group == "Group_A":
        raw = norm_action_from_text(row.get("raw_llm_decision", ""))
        return raw if raw is not None else norm_action_from_text(row.get("decision", ""))
    return norm_action_from_text(row.get("yearly_decision", ""))


def rr_flag(ta: str, action: str | None) -> bool:
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


def compute_one(sim_path: Path, trace_path: Path, group: str):
    rows = list(csv.DictReader(open(sim_path, encoding="utf-8-sig")))
    rows.sort(key=lambda r: ((r.get("agent_id") or ""), int((r.get("year") or "0") or "0")))

    approved_by_agent_year: dict[tuple[str, str], bool] = {}
    if trace_path.exists():
        for line in open(trace_path, encoding="utf-8"):
            obj = json.loads(line)
            approved_by_agent_year[(obj.get("agent_id"), str(obj.get("year")))] = obj.get("outcome") == "APPROVED"

    prev_rel = {}

    n_active = 0
    n_rr_proposal = 0
    n_rr_executed = 0
    n_exec = 0

    # Keep RH aligned to strict feasibility currently used in manuscript pipeline.
    # (state contradiction: re-elevation after already elevated)
    prev_elev = {}
    n_rh_proposal = 0
    n_rh_executed = 0

    c4_proposal = Counter()
    c4_executed = Counter()

    for r in rows:
        aid = r.get("agent_id") or ""
        yr = str(r.get("year") or "")

        pr = prev_rel.get(aid, False)
        pe = prev_elev.get(aid, False)
        cur_rel = str(r.get("relocated", "")).strip().lower() == "true"
        cur_elev = str(r.get("elevated", "")).strip().lower() == "true"

        act = intent_action(r, group)
        if (not pr) and act is not None:
            n_active += 1
            ta = extract_ta_label(r.get("threat_appraisal", ""))

            if rr_flag(ta, act):
                n_rr_proposal += 1

            if pe and act in ("elevation", "both"):
                n_rh_proposal += 1

            # proposal diversity (/4)
            a4 = "elevation" if act == "both" else act
            if a4 in ("do_nothing", "insurance", "elevation", "relocate"):
                c4_proposal[a4] += 1

            approved = True if group == "Group_A" else approved_by_agent_year.get((aid, yr), False)
            if approved:
                n_exec += 1
                if rr_flag(ta, act):
                    n_rr_executed += 1
                if pe and act in ("elevation", "both"):
                    n_rh_executed += 1
                if a4 in ("do_nothing", "insurance", "elevation", "relocate"):
                    c4_executed[a4] += 1

        prev_rel[aid] = cur_rel
        prev_elev[aid] = cur_elev

    rh_p = (n_rh_proposal / n_active) if n_active else 0.0
    rr_p = (n_rr_proposal / n_active) if n_active else 0.0
    rh_e = (n_rh_executed / n_exec) if n_exec else 0.0
    rr_e = (n_rr_executed / n_exec) if n_exec else 0.0

    h4_p = shannon_norm(c4_proposal, 4)
    h4_e = shannon_norm(c4_executed, 4)

    return {
        "n_active": n_active,
        "n_executed": n_exec,
        "n_rr_proposal": n_rr_proposal,
        "n_rr_executed": n_rr_executed,
        "n_rh_proposal": n_rh_proposal,
        "n_rh_executed": n_rh_executed,
        "R_H_proposal": rh_p,
        "R_R_proposal": rr_p,
        "H_norm_k4_proposal": h4_p,
        "EHE_k4_proposal": h4_p * (1.0 - rh_p),
        "R_H_executed": rh_e,
        "R_R_executed": rr_e,
        "H_norm_k4_executed": h4_e,
        "EHE_k4_executed": h4_e * (1.0 - rh_e),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--joh-final-dir", default="examples/single_agent/results/JOH_FINAL")
    ap.add_argument("--runs", default="Run_1,Run_2")
    ap.add_argument("--out-all", default="docs/wrr_metrics_clean_all_v1.csv")
    ap.add_argument("--out-summary", default="docs/wrr_metrics_clean_summary_v1.csv")
    args = ap.parse_args()

    runs = normalize_runs(args.runs)
    root = Path(args.joh_final_dir)

    all_rows = []
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
        "n_executed",
        "n_rr_proposal",
        "n_rr_executed",
        "n_rh_proposal",
        "n_rh_executed",
        "R_H_proposal",
        "R_R_proposal",
        "H_norm_k4_proposal",
        "EHE_k4_proposal",
        "R_H_executed",
        "R_R_executed",
        "H_norm_k4_executed",
        "EHE_k4_executed",
    ]
    Path(args.out_all).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_all, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)

    by = defaultdict(list)
    for r in all_rows:
        by[r["group"]].append(r)

    sf = [
        "group",
        "n_cases",
        "R_R_proposal_mean",
        "R_R_executed_mean",
        "R_H_proposal_mean",
        "R_H_executed_mean",
        "H_norm_k4_proposal_mean",
        "H_norm_k4_executed_mean",
        "EHE_k4_proposal_mean",
        "EHE_k4_executed_mean",
    ]
    with open(args.out_summary, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=sf)
        w.writeheader()
        for g in GROUPS:
            lst = by.get(g, [])
            if not lst:
                continue
            n = len(lst)

            def m(k: str) -> float:
                return sum(float(x[k]) for x in lst) / n

            w.writerow(
                {
                    "group": g,
                    "n_cases": n,
                    "R_R_proposal_mean": m("R_R_proposal"),
                    "R_R_executed_mean": m("R_R_executed"),
                    "R_H_proposal_mean": m("R_H_proposal"),
                    "R_H_executed_mean": m("R_H_executed"),
                    "H_norm_k4_proposal_mean": m("H_norm_k4_proposal"),
                    "H_norm_k4_executed_mean": m("H_norm_k4_executed"),
                    "EHE_k4_proposal_mean": m("EHE_k4_proposal"),
                    "EHE_k4_executed_mean": m("EHE_k4_executed"),
                }
            )

    print(f"Wrote: {args.out_all}")
    print(f"Wrote: {args.out_summary}")
    print(f"Rows: {len(all_rows)}")


if __name__ == "__main__":
    main()
