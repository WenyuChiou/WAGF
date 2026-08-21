"""STEP 2 -- reproduce the published Nature Water irrigation headline from raw files.

TARGET (context from the brief, NOT ground truth): governed IBR 36.05 %, ungoverned 59.07 %,
published as a +23.0 pp "improvement". This script computes the same statistic with the
canonical loader and reports what the honest definition actually gives, per seed.

SIGN CONVENTION, in words: `gap` below is (governed - ungoverned). A NEGATIVE gap means
governance LOWERED the rate of "claimed high scarcity but increased anyway", which is the
direction the paper claims as the governance benefit. The paper quotes the same magnitude
with the opposite sign as a "+23.0 pp improvement"; that flip is cosmetic, not a discrepancy.

If the primary definition does not reproduce, the script does NOT tune it. It instead runs
the pre-listed diagnostics: blank labels, row counts, seed presence, and the four action
columns (simulation executed / audit final / audit proposed / audit executed-with-default).

Usage:  python reproduction/decomposition/reproduce_published.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _loader as L  # noqa: E402

PUB_GOV, PUB_UNG = 36.05, 59.07
TOL = 0.05   # pp; "reproduced" means within this of the published value


def _rate(rows, high_fn, act_fn):
    den = [r for r in rows if high_fn(r)]
    if not den:
        return float("nan"), 0, 0
    num = sum(1 for r in den if act_fn(r) in L.INCREASE)
    return 100.0 * num / len(den), num, len(den)


def audit_variants(path):
    """Four action definitions on the AUDIT csv, all with the audit's own WSA label."""
    rows = L.load_audit(path)

    def high(r):
        return (r.get("construct_WSA_LABEL") or "").strip().upper() in L.HIGH

    def final(r):
        return (r.get("final_skill") or "").strip()

    def proposed(r):
        return (r.get("proposed_skill") or "").strip()

    def executed(r):
        st = (r.get("status") or "").strip()
        return L.DEFAULT_SKILL if st.startswith("REJECTED") else final(r)

    return {
        "audit_final": _rate(rows, high, final),
        "audit_proposed": _rate(rows, high, proposed),
        "audit_exec_default": _rate(rows, high, executed),
        "_n": len(rows),
        "_blank_wsa": sum(1 for r in rows
                          if not (r.get("construct_WSA_LABEL") or "").strip()),
    }


def main() -> int:
    label, prefix = L.ANCHOR
    print(f"STEP 2 -- reproduction, anchor model {label}\n")
    print(f"Published pair quoted in the brief: governed {PUB_GOV:.2f} %  "
          f"ungoverned {PUB_UNG:.2f} %  gap {PUB_GOV - PUB_UNG:+.2f} pp\n")

    seeds = L.paired_seeds(prefix)
    g_all = {a: L.seeds(a, prefix) for a in ("governed", "ungoverned")}
    print(f"seeds present  governed  : {g_all['governed']}")
    print(f"seeds present  ungoverned: {g_all['ungoverned']}")
    print(f"paired seeds used        : {seeds}\n")

    # ---- primary definition -------------------------------------------------
    print("PRIMARY DEFINITION -- simulation_log.csv, wsa_label in {H,VH}, "
          "yearly_decision in {increase_large, increase_small}\n")
    hdr = (f"{'seed':>5s} {'arm':11s} {'rows':>6s} {'unparsed':>10s} "
           f"{'HIGH n':>7s} {'high%':>7s} {'incr|HIGH':>10s} {'IBR %':>8s} "
           f"{'uncond incr%':>13s}")
    print(hdr)
    print("-" * len(hdr))
    per = {"governed": {}, "ungoverned": {}}
    highsh = {"governed": {}, "ungoverned": {}}
    uncond = {"governed": {}, "ungoverned": {}}
    for s in seeds:
        for arm in ("governed", "ungoverned"):
            rows = L.load_run(L.run_dir(arm, prefix, s))
            r, num, den = _rate(rows, L.is_high, L.action)
            per[arm][s] = r
            highsh[arm][s] = L.high_share(rows)
            uncond[arm][s] = L.increase_rate(rows)
            # "unparsed" = wsa_label outside {VL,L,M,H,VH}. In simulation_log these are
            # the literal string "N/A", so an emptiness test would report zero and hide
            # them. They are counted here and excluded from no denominator by hand.
            blank = sum(1 for x in rows if L.wsa(x) not in L.LABEL_LEVELS)
            print(f"{s:>5s} {arm:11s} {len(rows):>6d} {blank:>10d} "
                  f"{den:>7d} {highsh[arm][s]:>6.2f}% {num:>10d} {r:>7.2f}% "
                  f"{uncond[arm][s]:>12.2f}%")
        print()

    gm = L.mean(per["governed"][s] for s in seeds)
    um = L.mean(per["ungoverned"][s] for s in seeds)
    gsd = L.sd(per["governed"][s] for s in seeds)
    usd = L.sd(per["ungoverned"][s] for s in seeds)
    diffs = [per["governed"][s] - per["ungoverned"][s] for s in seeds]
    t, df = L.paired_t(diffs)
    p = L.t_two_sided_p(t, df)

    print("=" * 78)
    print(f"MEAN over {len(seeds)} seeds (mean of per-seed rates, unweighted):")
    print(f"  governed   IBR = {gm:.2f} %  (sd {gsd:.2f})   published {PUB_GOV:.2f}  "
          f"delta {gm - PUB_GOV:+.2f} pp")
    print(f"  ungoverned IBR = {um:.2f} %  (sd {usd:.2f})   published {PUB_UNG:.2f}  "
          f"delta {um - PUB_UNG:+.2f} pp")
    print(f"  gap (governed - ungoverned) = {gm - um:+.2f} pp   "
          f"[negative = governance lowered the rate]")
    print(f"  paired t on per-seed differences: t = {t:.3f}, df = {df}, p = {p:.6f}")
    print(f"  per-seed differences: {[round(d, 2) for d in diffs]}")

    # pooled (decision-weighted) for contrast -- NOT the inferential unit
    allg = [r for s in seeds for r in L.load_run(L.run_dir("governed", prefix, s))]
    allu = [r for s in seeds for r in L.load_run(L.run_dir("ungoverned", prefix, s))]
    print(f"\n  POOLED across seeds (decision-weighted, reported only for contrast):")
    print(f"    governed {L.ibr(allg):.2f} %   ungoverned {L.ibr(allu):.2f} %   "
          f"gap {L.ibr(allg) - L.ibr(allu):+.2f} pp")

    okg = abs(gm - PUB_GOV) <= TOL
    oku = abs(um - PUB_UNG) <= TOL
    print(f"\n  REPRODUCED? governed: {'YES' if okg else 'NO'}   "
          f"ungoverned: {'YES' if oku else 'NO'}   (tolerance {TOL} pp)")

    # ---- composition, the reason this whole analysis exists -----------------
    print("\n" + "=" * 78)
    print("THE CONDITIONING VARIABLE ITSELF (this is the defect, not a side note):")
    ghs = L.mean(highsh["governed"][s] for s in seeds)
    uhs = L.mean(highsh["ungoverned"][s] for s in seeds)
    print(f"  share of decisions with HIGH self-reported scarcity")
    print(f"    governed   {ghs:.2f} %")
    print(f"    ungoverned {uhs:.2f} %")
    print(f"    shift (ungoverned - governed) = {uhs - ghs:+.2f} pp")
    print("  -> the two arms' IBR denominators are different populations of decisions.")
    ghp = L.mean(L.high_share_parsed(L.load_run(L.run_dir("governed", prefix, s)))
                 for s in seeds)
    uhp = L.mean(L.high_share_parsed(L.load_run(L.run_dir("ungoverned", prefix, s)))
                 for s in seeds)
    print(f"    same, restricted to parsed labels (the prior-art convention):")
    print(f"      governed {ghp:.2f} %   ungoverned {uhp:.2f} %   "
          f"shift {uhp - ghp:+.2f} pp")
    gun = L.mean(uncond["governed"][s] for s in seeds)
    uun = L.mean(uncond["ungoverned"][s] for s in seeds)
    print(f"\n  UNCONDITIONAL executed-increase rate (denominator fixed by design):")
    print(f"    governed {gun:.2f} %   ungoverned {uun:.2f} %   "
          f"gap {gun - uun:+.2f} pp  [negative = governance lowered it]")

    # ---- diagnostics --------------------------------------------------------
    print("\n" + "=" * 78)
    print("DIAGNOSTICS -- alternative action columns, from the AUDIT csv "
          "(audit's own construct_WSA_LABEL)\n")
    head = (f"{'seed':>5s} {'arm':11s} {'audit rows':>10s} {'blank WSA':>9s} "
            f"{'final':>8s} {'proposed':>9s} {'exec+dflt':>10s}")
    print(head)
    print("-" * len(head))
    var_acc = {}
    for s in seeds:
        for arm in ("governed", "ungoverned"):
            v = audit_variants(L.run_dir(arm, prefix, s))
            var_acc.setdefault(arm, []).append(v)
            print(f"{s:>5s} {arm:11s} {v['_n']:>10d} {v['_blank_wsa']:>9d} "
                  f"{v['audit_final'][0]:>7.2f}% {v['audit_proposed'][0]:>8.2f}% "
                  f"{v['audit_exec_default'][0]:>9.2f}%")
        print()
    for arm in ("governed", "ungoverned"):
        vs = var_acc[arm]
        print(f"  mean {arm:11s} final {L.mean(v['audit_final'][0] for v in vs):6.2f}%  "
              f"proposed {L.mean(v['audit_proposed'][0] for v in vs):6.2f}%  "
              f"exec+default {L.mean(v['audit_exec_default'][0] for v in vs):6.2f}%")

    print("\nNOTE ON THE DIAGNOSTIC TABLE: the audit csv and simulation_log are two views of")
    print("the same decisions. Any difference between 'audit_final' and the primary number")
    print("above is a linkage question, answered in linkage_check.py, not a definition to pick.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
