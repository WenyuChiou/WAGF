"""STEP 3 -- linkage and semantics between simulation_log.csv and the governance audit.

FOUR QUESTIONS, answered on data rather than on documentation:

  Q1  Do the two CSVs describe the same decisions, 1:1 on (agent_id, year)?
  Q2  Does simulation_log.yearly_decision equal the audit's final_skill?
  Q3  Does proposed_skill equal final_skill, per arm? (Does governance bite at the
      PROPOSAL stage, or only at execution?)
  Q4  What share of rows is REJECTED, and what share has fallback_activated true?
      Those are the rows where "what the agent said" and "what happened" can diverge.

  Q5 (added, and it is the one that matters most) -- IS yearly_decision ACTUALLY THE
      EXECUTED ACTION? The brief asserts it is. That assertion is testable without
      leaving simulation_log.csv: the file carries `request`, the quantity an
      increase/decrease/maintain skill is supposed to move. Cross-tabulating the label
      at year t against the sign of request(t) - request(t-1) for the same agent
      settles it. Sign convention: UP means request(t) > request(t-1).

Usage:  python reproduction/decomposition/linkage_check.py
"""
from __future__ import annotations

import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _loader as L  # noqa: E402

DIRECTION = {
    "increase_large": "UP", "increase_small": "UP",
    "decrease_large": "DOWN", "decrease_small": "DOWN",
    "maintain_demand": "SAME",
}


def movement(prev: str, cur: str, eps: float = 1e-9) -> str:
    a, b = float(prev), float(cur)
    if b > a + eps:
        return "UP"
    if b < a - eps:
        return "DOWN"
    return "SAME"


def analyse_run(arm: str, prefix: str, seed: str) -> dict:
    d = L.run_dir(arm, prefix, seed)
    sim = L.load_run(d)
    aud = L.load_audit(d)

    # --- Q1 linkage ---------------------------------------------------------
    skey = [(r["agent_id"].strip(), r["year"].strip()) for r in sim]
    akey = [(r["agent_id"].strip(), r["year"].strip()) for r in aud]
    sset, aset = set(skey), set(akey)
    res = {
        "n_sim": len(sim), "n_aud": len(aud),
        "sim_dup": len(skey) - len(sset), "aud_dup": len(akey) - len(aset),
        "sim_only": len(sset - aset), "aud_only": len(aset - sset),
        "matched": len(sset & aset),
    }

    amap = {k: r for k, r in zip(akey, aud)}

    # --- Q2 / Q3 / Q4 -------------------------------------------------------
    same_yd_final = 0
    same_prop_final = 0
    rejected = 0
    fallback = 0
    status_counts = collections.Counter()
    for r in sim:
        a = amap.get((r["agent_id"].strip(), r["year"].strip()))
        if a is None:
            continue
        final = (a.get("final_skill") or "").strip()
        prop = (a.get("proposed_skill") or "").strip()
        st = (a.get("status") or "").strip()
        status_counts[st] += 1
        if L.action(r) == final:
            same_yd_final += 1
        if prop == final:
            same_prop_final += 1
        if st.startswith("REJECTED"):
            rejected += 1
        if (a.get("fallback_activated") or "").strip().lower() == "true":
            fallback += 1
    n = res["matched"]
    res.update({
        "pct_yd_eq_final": 100.0 * same_yd_final / n,
        "pct_prop_eq_final": 100.0 * same_prop_final / n,
        "pct_rejected": 100.0 * rejected / n,
        "pct_fallback": 100.0 * fallback / n,
        "status_counts": status_counts,
    })

    # --- Q5 does the label move the world? ----------------------------------
    by_agent = collections.defaultdict(dict)
    for r in sim:
        by_agent[r["agent_id"].strip()][int(r["year"])] = r
    xt = collections.Counter()
    for aid, yrs in by_agent.items():
        for y in sorted(yrs):
            if y - 1 not in yrs:
                continue
            r = yrs[y]
            mv = movement(yrs[y - 1]["request"], r["request"])
            a = amap.get((aid, r["year"].strip()))
            st = (a.get("status") or "").strip() if a else "NO_AUDIT_ROW"
            xt[(L.action(r), st, mv)] += 1
    res["crosstab"] = xt
    return res


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=L.ANCHOR[0],
                    choices=[m for m, _ in L.MODELS] + ["ALL"],
                    help="model cell to check; ALL loops over every cell")
    args = ap.parse_args()
    if args.model == "ALL":
        rc = 0
        for lab, _ in L.MODELS:
            sys.argv = [sys.argv[0], "--model", lab]
            print("\n" + "#" * 92 + f"\n# {lab}\n" + "#" * 92)
            rc |= main()
        return rc
    label = args.model
    prefix = dict(L.MODELS)[label]
    seeds = L.paired_seeds(prefix)
    print(f"STEP 3 -- linkage + semantics, anchor model {label}, seeds {seeds}\n")

    all_res = {}
    print("Q1-Q4  (per run)\n")
    hdr = (f"{'seed':>5s} {'arm':11s} {'n_sim':>6s} {'n_aud':>6s} {'dup':>4s} "
           f"{'simonly':>8s} {'audonly':>8s} {'yd==final':>10s} {'prop==final':>12s} "
           f"{'REJECTED':>9s} {'fallback':>9s}")
    print(hdr)
    print("-" * len(hdr))
    for s in seeds:
        for arm in ("governed", "ungoverned"):
            r = analyse_run(arm, prefix, s)
            all_res[(arm, s)] = r
            print(f"{s:>5s} {arm:11s} {r['n_sim']:>6d} {r['n_aud']:>6d} "
                  f"{r['sim_dup'] + r['aud_dup']:>4d} {r['sim_only']:>8d} "
                  f"{r['aud_only']:>8d} {r['pct_yd_eq_final']:>9.2f}% "
                  f"{r['pct_prop_eq_final']:>11.2f}% {r['pct_rejected']:>8.2f}% "
                  f"{r['pct_fallback']:>8.2f}%")
        print()

    for arm in ("governed", "ungoverned"):
        rs = [all_res[(arm, s)] for s in seeds]
        print(f"  mean {arm:11s}  yd==final {L.mean(r['pct_yd_eq_final'] for r in rs):6.2f}%   "
              f"proposed==final {L.mean(r['pct_prop_eq_final'] for r in rs):6.2f}%   "
              f"REJECTED {L.mean(r['pct_rejected'] for r in rs):6.2f}%   "
              f"fallback_activated {L.mean(r['pct_fallback'] for r in rs):5.2f}%")

    print("\nStatus vocabulary actually present (pooled over the 5 anchor seeds):")
    for arm in ("governed", "ungoverned"):
        c = collections.Counter()
        for s in seeds:
            c.update(all_res[(arm, s)]["status_counts"])
        tot = sum(c.values())
        pretty = "  ".join(f"{k}={v} ({100.0 * v / tot:.2f}%)" for k, v in c.most_common())
        print(f"  {arm:11s} {pretty}")

    # --- Q5 -----------------------------------------------------------------
    print("\n" + "=" * 78)
    print("Q5 -- IS yearly_decision THE EXECUTED ACTION?")
    print("Cross-tab of the label at year t against the movement of `request` from t-1 to t,")
    print("pooled over the 5 anchor seeds. Sign convention: UP = request rose.\n")
    for arm in ("governed", "ungoverned"):
        c = collections.Counter()
        for s in seeds:
            c.update(all_res[(arm, s)]["crosstab"])
        print(f"  --- {arm} ---")
        print(f"  {'label':16s} {'status':18s} {'movement':>9s} {'n':>8s} {'consistent?':>12s}")
        agree = disagree = 0
        for (lab, st, mv), n in sorted(c.items()):
            exp = DIRECTION.get(lab)
            ok = "yes" if exp == mv else "NO"
            (agree if exp == mv else disagree).__class__  # no-op to keep flake quiet
            if exp == mv:
                agree += n
            else:
                disagree += n
            print(f"  {lab:16s} {st:18s} {mv:>9s} {n:>8d} {ok:>12s}")
        tot = agree + disagree
        print(f"  label matches the world movement in {agree:,}/{tot:,} "
              f"= {100.0 * agree / tot:.2f}% of year-over-year transitions\n")

    print("=" * 78)
    print("READ THIS BEFORE USING yearly_decision AS 'THE EXECUTED ACTION'.")
    print("If the cross-tab above shows REJECTED rows whose request does not move while their")
    print("label says increase_*, then yearly_decision is the LABELLED / final-proposed skill,")
    print("not the action that mutated the world. The published IBR would then be a")
    print("proposal-stage statistic, and the executed-action statistic is a different number.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
