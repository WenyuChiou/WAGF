"""STEP 4 -- corpus inventory: which seeds exist, which model cells are balanced,
and what the three headline rates look like in every cell.

Nothing here is inferred from directory names alone: every run is opened and its rows
counted, and every rate is computed by the canonical loader.

Balance rule (a design property, checkable without looking at any outcome): a cell whose
two arms do not carry the same seed set cannot enter a paired contrast. Unbalanced cells
are printed, flagged, and kept out of the paired statistics -- never silently dropped.

Sign convention: `gap` columns are (governed - ungoverned). Negative = governance lowered
the quantity.

Usage:  python SUBMISSION_2026/decomposition/seed_inventory.py [--csv out.csv]
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _loader as L  # noqa: E402


def cell(prefix: str, arm: str):
    out = {}
    for s in L.seeds(arm, prefix):
        rows = L.load_run(L.run_dir(arm, prefix, s))
        out[s] = {
            "n": len(rows),
            "ibr": L.ibr(rows),
            "high": L.high_share(rows),
            "incr": L.increase_rate(rows),
            "blank": L.label_unparsed_share(rows),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()

    print("STEP 4 -- seed inventory across all five irrigation model cells\n")
    rows_out = []

    print(f"{'model':16s} {'gov seeds':18s} {'ung seeds':18s} {'balanced':>9s} "
          f"{'paired n':>9s}")
    print("-" * 76)
    inv = {}
    for label, prefix in L.MODELS:
        g = L.seeds("governed", prefix)
        u = L.seeds("ungoverned", prefix)
        bal = g == u
        inv[label] = (prefix, g, u, bal)
        print(f"{label:16s} {','.join(g):18s} {','.join(u):18s} {str(bal):>9s} "
              f"{len(L.paired_seeds(prefix)):>9d}"
              + ("" if bal else "   <- EXCLUDED from paired contrasts"))
    print()

    for label, prefix in L.MODELS:
        _, gs, us, bal = inv[label]
        print("=" * 92)
        print(f"{label}   ({'balanced' if bal else 'UNBALANCED -- report separately'})")
        gcell, ucell = cell(prefix, "governed"), cell(prefix, "ungoverned")
        hdr = (f"  {'seed':>5s} {'arm':11s} {'rows':>6s} {'unparsed %':>11s} "
               f"{'IBR %':>8s} {'high share %':>13s} {'uncond incr %':>14s}")
        print(hdr)
        for s in sorted(set(gs) | set(us)):
            for arm, c in (("governed", gcell), ("ungoverned", ucell)):
                if s not in c:
                    print(f"  {s:>5s} {arm:11s} {'--- run absent in this arm ---':>50s}")
                    continue
                v = c[s]
                print(f"  {s:>5s} {arm:11s} {v['n']:>6d} {v['blank']:>10.2f}% "
                      f"{v['ibr']:>7.2f}% {v['high']:>12.2f}% {v['incr']:>13.2f}%")
        ps = L.paired_seeds(prefix)
        if ps:
            gi = [gcell[s]["ibr"] for s in ps]
            ui = [ucell[s]["ibr"] for s in ps]
            gh = [gcell[s]["high"] for s in ps]
            uh = [ucell[s]["high"] for s in ps]
            gr = [gcell[s]["incr"] for s in ps]
            ur = [ucell[s]["incr"] for s in ps]
            d = [a - b for a, b in zip(gi, ui)]
            t, df = L.paired_t(d)
            p = L.t_two_sided_p(t, df)
            note = "" if bal else "   (NOT a valid paired contrast -- unbalanced arms)"
            print(f"\n  paired seeds {ps}{note}")
            print(f"    IBR            governed {L.mean(gi):6.2f}%  ungoverned {L.mean(ui):6.2f}%"
                  f"   gap {L.mean(gi) - L.mean(ui):+7.2f} pp")
            print(f"    high share     governed {L.mean(gh):6.2f}%  ungoverned {L.mean(uh):6.2f}%"
                  f"   gap {L.mean(gh) - L.mean(uh):+7.2f} pp"
                  f"   (composition shift ung-gov = {L.mean(uh) - L.mean(gh):+.2f} pp)")
            print(f"    uncond increase governed {L.mean(gr):5.2f}%  ungoverned {L.mean(ur):6.2f}%"
                  f"   gap {L.mean(gr) - L.mean(ur):+7.2f} pp")
            print(f"    paired t on IBR differences: t = {t:.3f}, df = {df}, p = {p:.6f}"
                  + ("" if bal else "   [INVALID -- shown only to prove it was not hidden]"))
            rows_out.append({
                "model": label, "balanced": bal, "paired_seeds": ";".join(ps),
                "ibr_gov": round(L.mean(gi), 4), "ibr_ung": round(L.mean(ui), 4),
                "ibr_gap_pp": round(L.mean(gi) - L.mean(ui), 4),
                "high_gov": round(L.mean(gh), 4), "high_ung": round(L.mean(uh), 4),
                "high_shift_ung_minus_gov_pp": round(L.mean(uh) - L.mean(gh), 4),
                "incr_gov": round(L.mean(gr), 4), "incr_ung": round(L.mean(ur), 4),
                "incr_gap_pp": round(L.mean(gr) - L.mean(ur), 4),
                "t": round(t, 4), "df": df, "p": round(p, 8),
            })
        print()

    bal_rows = [r for r in rows_out if r["balanced"]]
    if bal_rows:
        print("=" * 92)
        print("BALANCED CELLS ONLY -- the set any paired analysis may use")
        print(f"  models: {[r['model'] for r in bal_rows]}")
        print(f"  mean IBR gap (gov - ung)          {L.mean(r['ibr_gap_pp'] for r in bal_rows):+.2f} pp")
        print(f"  mean composition shift (ung - gov) "
              f"{L.mean(r['high_shift_ung_minus_gov_pp'] for r in bal_rows):+.2f} pp")
        print(f"  mean unconditional increase gap   "
              f"{L.mean(r['incr_gap_pp'] for r in bal_rows):+.2f} pp")

    if args.csv and rows_out:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows_out[0]))
            w.writeheader()
            w.writerows(rows_out)
        print(f"\nwrote {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
