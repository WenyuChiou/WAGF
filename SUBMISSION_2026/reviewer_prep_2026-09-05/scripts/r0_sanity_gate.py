"""R0 -- SANITY GATE. Nothing else in this package is trustworthy until this passes.

Recomputes the published Nature Water irrigation headline (governed IBR 36.05 %,
no-validator 59.07 %) through THIS package's helpers rather than through
reproduce_published.py, and asserts agreement to 0.05 pp. If the two disagree the
script raises: it never tunes the definition to make the target appear.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r0_sanity_gate.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import L, PrepError  # noqa: E402

PUB = {"governed": 36.05, "ungoverned": 59.07}
TOL = 0.05
PREFIX = ""            # gemma3:4b anchor cell


def main() -> int:
    C.banner("R0  SANITY GATE -- irrigation headline IBR, gemma3:4b v21, 5 seeds")
    seeds = L.paired_seeds(PREFIX)
    if len(seeds) != 5:
        raise PrepError(f"expected 5 paired seeds for the anchor cell, got {seeds}")
    print(f"paired seeds: {seeds}\n")

    per = {"governed": [], "ungoverned": []}
    rows = []
    for s in seeds:
        for arm in ("governed", "ungoverned"):
            sim = L.load_run(L.run_dir(arm, PREFIX, s))
            if len(sim) != L.EXPECTED_ROWS:
                raise PrepError(f"{arm} seed {s}: {len(sim)} rows, expected {L.EXPECTED_ROWS}")
            v = L.ibr(sim)
            per[arm].append(v)
            rows.append({"seed": s, "arm": arm, "n_rows": len(sim),
                         "ibr_pct": v, "increase_rate_pct": L.increase_rate(sim),
                         "high_share_pct": L.high_share(sim)})
        print(f"  seed {s}   governed {per['governed'][-1]:6.2f} %   "
              f"ungoverned {per['ungoverned'][-1]:6.2f} %")

    ok = True
    print()
    for arm in ("governed", "ungoverned"):
        m, s_ = C.mean(per[arm]), C.sd(per[arm])
        hit = abs(m - PUB[arm]) <= TOL
        ok &= hit
        print(f"  {arm:11s} mean {m:6.2f} % (sd {s_:.2f})   published {PUB[arm]:6.2f}   "
              f"delta {m - PUB[arm]:+.3f} pp   {'MATCH' if hit else 'MISMATCH'}")

    diffs = [g - u for g, u in zip(per["governed"], per["ungoverned"])]
    t, df = C.paired_t(diffs)
    p = C.t_two_sided_p(t, df)
    print(f"\n  gap (governed - ungoverned) = {C.mean(diffs):+.2f} pp")
    print(f"  paired t = {t:.3f}, df = {df}, p = {p:.6f}")
    print(f"  exact sign-flip permutation p = {C.exact_perm_p(diffs):.4f} "
          f"(n=5 floor is 0.0625; the t-test p is the one the paper quotes)")

    C.write_csv("r0_sanity_gate.csv",
                ["seed", "arm", "n_rows", "ibr_pct", "increase_rate_pct", "high_share_pct"],
                rows)

    if not ok:
        raise PrepError("SANITY GATE FAILED -- do not trust any other table in this package")
    print("\nSANITY GATE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
