"""P0-1e: re-derive governance metrics on the EXECUTED action.

WHY. On a REJECTED decision the broker executes the registry DEFAULT skill as
fallback (skill_broker_engine.py:418-435), but the audit CSV writes the BLOCKED
proposal into ``final_skill``. Any metric computed on ``final_skill`` therefore
counts blocked proposals as if they had executed.

Verified empirically before writing this script (irrigation, gemma4:e4b seed42,
3,276 records): cross-tabulating the labelled skill against the actual
``execution_result.state_changes.request`` movement gives

    APPROVED rows -> label matches the real movement 100% of the time
    REJECTED rows -> 1,865 / 1,865 UNCHANGED, i.e. the proposal NEVER executed

So for runs predating the ``executed_skill_columns`` flag the executed action is
recoverable exactly:

    executed = final_skill            if status == APPROVED
    executed = <registry default>     if status startswith REJECTED

Runs produced with the flag ON carry a real ``executed_skill`` column, which
this script prefers when present.

Usage
-----
    python AAMAS2027/experiments/rederive_executed_levels.py            # irrigation + flood
    python AAMAS2027/experiments/rederive_executed_levels.py --domain irrigation

Outputs a per-arm table of the headline conditional rate computed BOTH ways so
the size of the correction is visible, and writes a CSV next to this script.
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import statistics
import sys
from collections import defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Registry default per domain — what actually runs on a REJECTED decision.
DEFAULTS = {"irrigation": "maintain_demand", "flood": "do_nothing"}

# Headline metric per domain. Irrigation: the conditional high-scarcity
# increase rate (denominator = high-WSA rows only) — the definition that
# reproduces the published 36.05 / 59.07 figures to 2dp.
INCREASE_SKILLS = {"increase_large", "increase_small"}
HIGH_WSA = {"H", "VH"}

DOMAIN_GLOBS = {
    "irrigation": [
        ("strict", "examples/irrigation_abm/results/production_v21_*/irrigation_farmer_governance_audit.csv"),
        ("disabled", "examples/irrigation_abm/results/ungoverned_v21_*/irrigation_farmer_governance_audit.csv"),
    ],
    "flood": [
        ("strict", "examples/single_agent/results/JOH_FINAL/**/*governance_audit.csv"),
        ("strict", "examples/single_agent/results/JOH_FINAL_v2/**/*governance_audit.csv"),
        ("disabled", "examples/single_agent/results/JOH_ABLATION_DISABLED/**/*governance_audit.csv"),
        ("disabled", "examples/single_agent/results/JOH_ABLATION_DISABLED_v2/**/*governance_audit.csv"),
    ],
}


def _model_of(path, domain):
    """Recover the model tag from a results path.

    Irrigation dirs look like ``production_v21_42yr_<model>_seed42`` (the
    gemma3:4b baseline omits the model segment entirely). Flood dirs carry the
    model as the first path segment under the bundle.
    """
    parts = os.path.normpath(path).split(os.sep)
    if domain == "flood":
        for i, p in enumerate(parts):
            if p.startswith("JOH_") and i + 1 < len(parts):
                return parts[i + 1]
        return "unknown"
    for p in parts:
        if p.startswith(("production_v21_", "ungoverned_v21_")):
            body = p.split("_v21_", 1)[1]
            body = body.replace("42yr_", "", 1)
            seg = body.rsplit("_seed", 1)[0]
            # The published v21 baseline dirs omit the model segment entirely
            # (production_v21_42yr_seed42), leaving only "seedNN" here.
            if not seg or seg.startswith("seed"):
                return "gemma3_4b(v21 baseline)"
            return seg
    return "unknown"


def executed_action(row, default_skill):
    """The action that actually mutated the world for this decision."""
    # Flag-ON runs record it directly; prefer the recorded truth.
    recorded = (row.get("executed_skill") or "").strip()
    if recorded:
        return recorded
    status = (row.get("status") or "").strip()
    if status.startswith("REJECTED"):
        return default_skill
    return (row.get("final_skill") or "").strip()


def run_stats(path, default_skill):
    """Return (labelled_rate, executed_rate, n_conditional, n_rows) for one run.

    Rates are the conditional high-scarcity increase rate. Returns None when the
    run carries no WSA label column (i.e. not the irrigation schema).
    """
    n = cond = lab_hits = exe_hits = 0
    saw_wsa = False
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            n += 1
            wsa = (row.get("construct_WSA_LABEL") or "").strip().upper()
            if wsa:
                saw_wsa = True
            if wsa not in HIGH_WSA:
                continue
            cond += 1
            if (row.get("final_skill") or "").strip() in INCREASE_SKILLS:
                lab_hits += 1
            if executed_action(row, default_skill) in INCREASE_SKILLS:
                exe_hits += 1
    if not saw_wsa or cond == 0:
        return None
    return (100.0 * lab_hits / cond, 100.0 * exe_hits / cond, cond, n)


def rejected_share(path):
    n = rej = 0
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            n += 1
            if (row.get("status") or "").strip().startswith("REJECTED"):
                rej += 1
    return rej, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=sorted(DOMAIN_GLOBS), default=None)
    args = ap.parse_args()
    domains = [args.domain] if args.domain else sorted(DOMAIN_GLOBS)

    out_rows = []
    for domain in domains:
        default_skill = DEFAULTS[domain]
        print(f"\n{'=' * 78}\n{domain.upper()}  (registry default on REJECTED = {default_skill!r})\n{'=' * 78}")
        per_arm = defaultdict(list)
        per_model = defaultdict(lambda: defaultdict(list))
        rej_tot = n_tot = 0
        for arm, pattern in DOMAIN_GLOBS[domain]:
            for path in sorted(glob.glob(os.path.join(REPO, pattern), recursive=True)):
                r, n = rejected_share(path)
                rej_tot += r
                n_tot += n
                st = run_stats(path, default_skill)
                if st:
                    per_arm[arm].append(st)
                    per_model[_model_of(path, domain)][arm].append(st)

        print(f"REJECTED share across corpus: {rej_tot:,}/{n_tot:,} = {100.0 * rej_tot / max(n_tot, 1):.2f}%")
        if not per_arm:
            print("(no runs carry the conditional-metric schema; REJECTED share above is the "
                  "whole story for this domain)")
            continue

        print(f"\nPOOLED ACROSS MODELS (indicative only — the published figures are per-model)")
        print(f"{'arm':10s} {'runs':>5s} {'labelled %':>12s} {'executed %':>12s} {'delta pp':>10s}")
        summary = {}
        for arm in ("strict", "disabled"):
            runs = per_arm.get(arm, [])
            if not runs:
                continue
            lab = statistics.mean(x[0] for x in runs)
            exe = statistics.mean(x[1] for x in runs)
            summary[arm] = (lab, exe)
            print(f"{arm:10s} {len(runs):>5d} {lab:>11.2f}% {exe:>11.2f}% {exe - lab:>+9.2f}")
            out_rows.append({
                "domain": domain, "model": "ALL_POOLED", "arm": arm, "runs": len(runs),
                "labelled_rate": round(lab, 4), "executed_rate": round(exe, 4),
            })

        # Per-model breakdown — this is what the manuscripts actually quote.
        if per_model:
            print(f"\nPER MODEL")
            print(f"{'model':22s} {'arm':10s} {'n':>3s} {'labelled %':>12s} {'executed %':>12s} {'delta pp':>10s}")
            for model in sorted(per_model):
                for arm in ("strict", "disabled"):
                    runs = per_model[model].get(arm, [])
                    if not runs:
                        continue
                    lab = statistics.mean(x[0] for x in runs)
                    exe = statistics.mean(x[1] for x in runs)
                    print(f"{model:22s} {arm:10s} {len(runs):>3d} {lab:>11.2f}% {exe:>11.2f}% {exe - lab:>+9.2f}")
                    out_rows.append({
                        "domain": domain, "model": model, "arm": arm, "runs": len(runs),
                        "labelled_rate": round(lab, 4), "executed_rate": round(exe, 4),
                    })
                s = per_model[model]
                if s.get("strict") and s.get("disabled"):
                    dl = statistics.mean(x[0] for x in s["disabled"]) - statistics.mean(x[0] for x in s["strict"])
                    de = statistics.mean(x[1] for x in s["disabled"]) - statistics.mean(x[1] for x in s["strict"])
                    print(f"{'':22s} {'GAP':10s} {'':>3s} {dl:>+11.2f}  {de:>+11.2f}  {de - dl:>+9.2f}")
        if "strict" in summary and "disabled" in summary:
            d_lab = summary["disabled"][0] - summary["strict"][0]
            d_exe = summary["disabled"][1] - summary["strict"][1]
            print(f"\n  governed-vs-no-validator GAP, labelled : {d_lab:+.2f} pp")
            print(f"  governed-vs-no-validator GAP, executed : {d_exe:+.2f} pp")
            print(f"  -> the LEVELS move, the GAP is {'STABLE' if abs(d_exe - d_lab) < 3 else 'ALSO AFFECTED'} "
                  f"(shift {d_exe - d_lab:+.2f} pp)")

    if out_rows:
        dest = os.path.join(os.path.dirname(__file__), "executed_level_correction.csv")
        with open(dest, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out_rows[0]))
            w.writeheader()
            w.writerows(out_rows)
        print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
