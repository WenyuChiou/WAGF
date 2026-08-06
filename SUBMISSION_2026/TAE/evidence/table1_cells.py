"""Table 1 -- the per-cell inventory, both testbeds.

Emits, for every model cell in both testbeds:

    seeds present per arm, balance flag, enforcement pressure (both arms),
    HIGH-appraisal prevalence (both arms) and its Delta,
    and, for irrigation only, the conditional and unconditional increase rates
    (both arms) under BOTH action readings.

Everything comes from ``_data.py``. This script owns no path, no glob, and no
definition of its own.

    python SUBMISSION_2026/TAE/evidence/table1_cells.py

Writes ``SUBMISSION_2026/TAE/evidence/table1_cells.csv``.


BASIS -- stated once, applies to every number below
---------------------------------------------------
* The SEED (irrigation) / RUN INDEX (flood) is the inferential unit. A cell value
  is the MEAN OF THE PER-SEED RATES, never the pooled rate.
* Cells are computed on the PAIRED seed set -- seeds present in BOTH arms.
  Every cell is balanced as of 2026-08-03, so for all five that is every seed
  the cell has. The governed-arm value over all its seeds is still printed
  separately, which is now a restatement rather than a disclosure.
* Delta = no-validator MINUS with-validators. Positive = validators lowered it.
  Enforced by ``_data.DELTA``, which is keyword-only.
* CIs are two-sided 95% from a paired t on the per-seed deltas, df = n-1.
  No cell is excluded. ministral3:8b was, until its no-validator seed 44 run
  balanced it; on df = 2 its conditional interval is wide and its lower bound
  sits just above zero, which the row states rather than rounds away.

ACTION READINGS -- every rate is labelled with the one that produced it
-----------------------------------------------------------------------
* LAST-PROPOSED: ``yearly_decision`` as written. This is what the published
  statistics use.
* EXECUTED: the ``maintain_demand`` substitution applied on REJECTED /
  REJECTED_FALLBACK rows, i.e. what actually ran.
Both are reported for irrigation. Flood needs neither: INCREASE is an irrigation
action vocabulary, and the flood audit already records the post-substitution
action, so no second substitution is defined there.

FLOOD IS NOT A CONTROL. It is a cross-theory portability demonstration with no
action->environment feedback. Its rows carry that label in the ``role`` column.
The flood audit csv covers less than the nominal 1,000 design-expected decisions,
by design and not by loss: relocation is an absorbing state, so an agent that
relocates generates no further rows (NUMBERS.md section 8, item 2, verified
exactly on 5/5 ministral3:3b Group_C runs). It is NOT the F1 silent-drop.
``audit_rows`` and ``coverage_pct`` report the shortfall, and every flood rate is
a per-run rate over the rows that exist, never over a 1,000 denominator.
"""
from __future__ import annotations

import csv
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import _data as D                                                # noqa: E402
#: rule taxonomy (appraisal-conditioned vs world-conditioned) -- single source
#: of truth lives in fig1_rule_layers.py so the two scripts cannot drift.
import fig1_rule_layers as F1                                    # noqa: E402

OUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "table1_cells.csv")

#: verified values from the brief, for a line-by-line agreement check.
#: (n, cond_gov, cond_noval, cond_delta, uncond_gov, uncond_noval, uncond_delta)
BRIEF_IRRIGATION = {
    "gemma3:4b":     (5, 36.05, 59.07, +23.02, 40.90, 62.52, +21.62),
    "gemma3:12b":    (3,  5.45, 16.89, +11.44, 41.36, 41.52,  +0.16),
    "gemma4:e2b":    (5, 12.71, 31.65, +18.94, 22.80, 38.05, +15.25),
    "gemma4:e4b":    (5, 23.67, 41.08, +17.41, 36.36, 44.87,  +8.52),
    "ministral3:8b": (3,  3.25,  6.05,  +2.80, 54.35, 32.18, -22.17),
}
#: brief, anchor only: HIGH-appraisal prevalence
BRIEF_ANCHOR_HIGH = (37.08, 82.80, +45.73)
#: brief, anchor only: pooled enforcement pressure over 5 seeds
BRIEF_ANCHOR_PRESSURE = (39.5, 29.0)

TOL = 0.005


# ---------------------------------------------------------------------------
def _stat_block(per_seed_gov: dict, per_seed_nov: dict, seeds) -> dict:
    """Cell means, Delta, and the paired t on the per-seed deltas."""
    g = {s: per_seed_gov[s] for s in seeds}
    n = {s: per_seed_nov[s] for s in seeds}
    gm, nm = D.cell_mean(g), D.cell_mean(n)
    deltas = [D.DELTA(noval=n[s], gov=g[s]) for s in seeds]
    t = D.paired_t(deltas)
    return {
        "gov": gm, "noval": nm, "delta": D.DELTA(noval=nm, gov=gm),
        "ci_lo": t.ci_lo, "ci_hi": t.ci_hi, "t": t.t, "df": t.df,
        "p": D.t_two_sided_p(t.t, t.df),
        "per_seed_gov": g, "per_seed_noval": n,
    }


def irrigation_rows() -> list[dict]:
    out = []
    for m in D.IRRIGATION_MODELS:
        bal = D.seed_sets(m.prefix)
        seeds = list(bal.paired_seeds)

        pressure = _stat_block(
            D.irrigation_per_seed("gov", m.prefix, D.rejection_pressure, source="audit"),
            D.irrigation_per_seed("noval", m.prefix, D.rejection_pressure, source="audit"),
            seeds)
        high = _stat_block(
            D.irrigation_per_seed("gov", m.prefix, D.high_share),
            D.irrigation_per_seed("noval", m.prefix, D.high_share),
            seeds)
        cond = _stat_block(
            D.irrigation_per_seed("gov", m.prefix, D.conditional_rate),
            D.irrigation_per_seed("noval", m.prefix, D.conditional_rate),
            seeds)
        uncond = _stat_block(
            D.irrigation_per_seed("gov", m.prefix, D.unconditional_rate),
            D.irrigation_per_seed("noval", m.prefix, D.unconditional_rate),
            seeds)
        cond_x = _stat_block(
            D.irrigation_per_seed_executed("gov", m.prefix, "conditional"),
            D.irrigation_per_seed_executed("noval", m.prefix, "conditional"),
            seeds)
        uncond_x = _stat_block(
            D.irrigation_per_seed_executed("gov", m.prefix, "unconditional"),
            D.irrigation_per_seed_executed("noval", m.prefix, "unconditional"),
            seeds)

        # unbalanced cell: what the governed arm looks like on ALL its seeds
        gov_all = None
        if not bal.balanced:
            gov_all = {
                "cond": D.cell_mean(D.irrigation_per_seed("gov", m.prefix, D.conditional_rate)),
                "uncond": D.cell_mean(D.irrigation_per_seed("gov", m.prefix, D.unconditional_rate)),
                "high": D.cell_mean(D.irrigation_per_seed("gov", m.prefix, D.high_share)),
                "seeds": list(bal.gov_seeds),
            }

        out.append({
            "testbed": "irrigation",
            "role": "identifying testbed (action->environment feedback)",
            "model": m.label,
            "gov_units": list(bal.gov_seeds),
            "noval_units": list(bal.noval_seeds),
            "balanced": bal.balanced,
            "paired_units": seeds,
            "n_paired": len(seeds),
            "excluded_from_paired": D.excluded_from_paired(m.prefix),
            "decisions_per_run_gov": sorted({
                len(D.load_sim(d)) for d in D.irrigation_runs("gov", m.prefix).values()}),
            "decisions_per_run_noval": sorted({
                len(D.load_sim(d)) for d in D.irrigation_runs("noval", m.prefix).values()}),
            "coverage_pct": 100.0,
            "pressure": pressure, "high": high,
            "cond": cond, "uncond": uncond,
            "cond_exec": cond_x, "uncond_exec": uncond_x,
            "gov_all_seeds": gov_all,
        })
    return out


def flood_rows() -> list[dict]:
    out = []
    for fm in D.FLOOD_MODELS:
        bal = D.flood_seed_sets(fm)
        runs = list(bal.paired_seeds)
        pressure = _stat_block(
            D.flood_per_run("gov", fm, D.rejection_pressure),
            D.flood_per_run("noval", fm, D.rejection_pressure), runs)
        high = _stat_block(
            D.flood_per_run("gov", fm, D.high_share),
            D.flood_per_run("noval", fm, D.high_share), runs)
        cov_g = [D.flood_audit_coverage(d) for d in D.flood_runs("gov", fm).values()]
        cov_n = [D.flood_audit_coverage(d) for d in D.flood_runs("noval", fm).values()]
        align = D.flood_seed_alignment(fm)
        out.append({
            "testbed": "flood",
            "role": "cross-theory portability demonstration (NO action->environment feedback)",
            "model": fm.label,
            "gov_units": [f"Run_{r}" for r in bal.gov_seeds],
            "noval_units": [f"Run_{r}" for r in bal.noval_seeds],
            "balanced": bal.balanced,
            "paired_units": runs,
            "n_paired": len(runs),
            "excluded_from_paired": False,
            "decisions_per_run_gov": [len(D.load_audit(d))
                                      for _, d in sorted(D.flood_runs("gov", fm).items())],
            "decisions_per_run_noval": [len(D.load_audit(d))
                                        for _, d in sorted(D.flood_runs("noval", fm).items())],
            "coverage_pct": min(cov_g + cov_n),
            "manifest_seeds_aligned": align.aligned,
            "pressure": pressure, "high": high,
            "cond": None, "uncond": None, "cond_exec": None, "uncond_exec": None,
            "gov_all_seeds": None,
        })
    return out


# ---------------------------------------------------------------------------
#: Compact rendering of the ``role`` field for section A, keyed by the FULL role
#: string so that editing the role text raises a KeyError here rather than
#: leaving a stale tag on the page.
#:
#: The tag is printed INLINE on every row, not left to the footnote. Flood's
#: enforcement-pressure column is 0.00-1.07%, and a reader scanning section A
#: with no role beside it will read that as a low-pressure treatment level --
#: i.e. as a control -- which is the exact misreading DECISION.md section 10
#: forbids. Flood has no action->environment feedback at all
#: (examples/multi_agent/flood/run_flood.py:285-291), so its pressure column is
#: a property of the design and not a dose.
ROLE_TAG = {
    "identifying testbed (action->environment feedback)": "IDENTIFYING",
    "cross-theory portability demonstration (NO action->environment feedback)":
        "PORTABILITY",
}


def _f(x, w=7, p=2):
    return f"{x:{w}.{p}f}" if x is not None else " " * (w - 1) + "-"


def _print(rows: list[dict]) -> list[str]:
    """Print the table. Returns a list of disagreement lines (empty = all agree)."""
    problems: list[str] = []

    print("=" * 118)
    print("TABLE 1 -- PER-CELL INVENTORY, BOTH TESTBEDS")
    print("=" * 118)
    print(D.DELTA_LABEL)
    print("Cell value = MEAN OF PER-SEED RATES (not pooled). Basis = seeds present in BOTH arms.")
    print("All rates are percentages. CI = two-sided 95% paired t on the per-seed deltas, df = n-1.")
    print()

    # ---------------- inventory + enforcement pressure + HIGH prevalence -----
    print("-" * 118)
    print("A. INVENTORY, ENFORCEMENT PRESSURE, AND THE CONDITIONING VARIABLE'S PREVALENCE")
    print("-" * 118)
    hdr = (f"{'testbed':10s} {'role':11s} {'model':14s} {'gov':7s} {'nov':7s} "
           f"{'bal':4s} {'n':>2s} "
           f"| {'press.gov':>9s} {'press.nov':>9s} {'D':>7s} "
           f"| {'HIGH.gov':>8s} {'HIGH.nov':>8s} {'Delta':>7s} {'95% CI':>18s} {'p':>6s}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        h = r["high"]
        mark = "  *EXCL" if r["excluded_from_paired"] else ""
        print(f"{r['testbed']:10s} {ROLE_TAG[r['role']]:11s} {r['model']:14s} "
              f"{len(r['gov_units']):>3d}    {len(r['noval_units']):>3d}    "
              f"{'Y' if r['balanced'] else 'N':4s} {r['n_paired']:>2d} "
              f"| {_f(r['pressure']['gov'], 9)} {_f(r['pressure']['noval'], 9)} "
              f"{_f(r['pressure']['delta'], 7)} "
              f"| {_f(h['gov'], 8)} {_f(h['noval'], 8)} {_f(h['delta'], 7)} "
              f"  ({h['ci_lo']:+7.2f},{h['ci_hi']:+7.2f}) {h['p']:>6.3f}{mark}")
    print()
    print("  role   = IDENTIFYING: the agent's action feeds back into the environment, so a")
    print("           within-testbed contrast identifies something. Irrigation only.")
    print("           PORTABILITY: a cross-theory portability demonstration with NO")
    print("           action->environment feedback. FLOOD IS NOT A CONTROL. Its enforcement")
    print("           pressure is near zero BY DESIGN, not because it is a low-pressure")
    print("           treatment level, and its press. columns must not be read as a dose.")
    print("  press. = enforcement pressure = % of audit rows whose proposal did not stand.")
    print("  HIGH   = % of decisions whose self-reported appraisal is H or VH")
    print("           (irrigation: simulation_log.wsa_label; flood: audit construct_TP_LABEL).")
    print()

    # ---------------- irrigation rates ---------------------------------------
    print("-" * 118)
    print("B. IRRIGATION INCREASE RATES -- BOTH ACTION READINGS")
    print("-" * 118)
    print("   LAST-PROPOSED = yearly_decision as written (what the published numbers use)")
    print("   EXECUTED      = maintain_demand substituted on REJECTED / REJECTED_FALLBACK rows")
    print()
    hdr = (f"{'model':14s} {'reading':14s} "
           f"| {'cond.gov':>8s} {'cond.nov':>8s} {'Delta':>7s} {'95% CI':>18s} {'p':>6s} "
           f"| {'unc.gov':>8s} {'unc.nov':>8s} {'Delta':>7s} {'95% CI':>18s} {'p':>6s}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        if r["testbed"] != "irrigation":
            continue
        for reading, ck, uk in (("LAST-PROPOSED", "cond", "uncond"),
                                ("EXECUTED", "cond_exec", "uncond_exec")):
            c, u = r[ck], r[uk]
            mark = "  *EXCL" if r["excluded_from_paired"] else ""
            print(f"{r['model']:14s} {reading:14s} "
                  f"| {_f(c['gov'], 8)} {_f(c['noval'], 8)} {_f(c['delta'], 7)} "
                  f"  ({c['ci_lo']:+7.2f},{c['ci_hi']:+7.2f}) {c['p']:>6.3f} "
                  f"| {_f(u['gov'], 8)} {_f(u['noval'], 8)} {_f(u['delta'], 7)} "
                  f"  ({u['ci_lo']:+7.2f},{u['ci_hi']:+7.2f}) {u['p']:>6.3f}{mark}")
        print()

    # ---------------- agreement check ---------------------------------------
    print("-" * 118)
    print("C. AGREEMENT WITH THE VERIFIED NUMBERS IN THE BRIEF")
    print("-" * 118)
    print("   (LAST-PROPOSED reading, paired basis -- the same basis the brief's list uses)")
    print()
    hdr = (f"{'model':14s} {'quantity':14s} {'computed':>9s} {'brief':>9s} {'diff':>8s}  verdict")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        if r["testbed"] != "irrigation":
            continue
        exp = BRIEF_IRRIGATION.get(r["model"])
        if exp is None:
            problems.append(f"{r['model']}: no brief entry to check against")
            continue
        n_e, cg, cn, cd, ug, un, ud = exp
        checks = [
            ("n (paired)", float(r["n_paired"]), float(n_e), 0.0),
            ("cond gov", r["cond"]["gov"], cg, TOL),
            ("cond noval", r["cond"]["noval"], cn, TOL),
            ("cond Delta", r["cond"]["delta"], cd, TOL),
            ("uncond gov", r["uncond"]["gov"], ug, TOL),
            ("uncond noval", r["uncond"]["noval"], un, TOL),
            ("uncond Delta", r["uncond"]["delta"], ud, TOL),
        ]
        for name, got, want, tol in checks:
            ok = abs(got - want) <= tol
            if not ok:
                problems.append(
                    f"DISAGREEMENT  {r['model']:14s} {name:12s} computed {got:.4f} "
                    f"vs brief {want:.4f}  (diff {got - want:+.4f})")
            print(f"{r['model']:14s} {name:14s} {got:>9.2f} {want:>9.2f} "
                  f"{got - want:>+8.2f}  {'agrees' if ok else '*** DISAGREES ***'}")
        print()

    anchor = next(r for r in rows if r["testbed"] == "irrigation" and r["model"] == "gemma3:4b")
    for name, got, want in (
        ("HIGH gov", anchor["high"]["gov"], BRIEF_ANCHOR_HIGH[0]),
        ("HIGH noval", anchor["high"]["noval"], BRIEF_ANCHOR_HIGH[1]),
        ("HIGH Delta", anchor["high"]["delta"], BRIEF_ANCHOR_HIGH[2]),
    ):
        ok = abs(got - want) <= TOL
        if not ok:
            problems.append(f"DISAGREEMENT  gemma3:4b {name}: computed {got:.4f} vs brief {want:.4f}")
        print(f"{'gemma3:4b':14s} {name:14s} {got:>9.2f} {want:>9.2f} "
              f"{got - want:>+8.2f}  {'agrees' if ok else '*** DISAGREES ***'}")
    print()

    # pooled enforcement pressure, anchor, 5 seeds -- the §7 two-layer result
    print("   Two-layer separation, anchor irrigation, POOLED over 5 seeds (rejection counts):")
    for arm, want in (("gov", BRIEF_ANCHOR_PRESSURE[0]), ("noval", BRIEF_ANCHOR_PRESSURE[1])):
        tot = rej = named = pc = appr = world = 0
        for d in D.irrigation_runs(arm, "").values():
            for row in D.load_audit(d):
                tot += 1
                c = D.rejection_cause(row)
                if c is None:
                    continue
                rej += 1
                named += c == "theory"
                pc += c == "precondition"
                if c == "theory":
                    names = {t.strip() for t in (row.get("failed_rules") or "").split("|")
                             if t.strip()}
                    if names & F1.APPRAISAL_CONDITIONED_RULES:
                        appr += 1
                    else:
                        world += 1
        rate = 100.0 * rej / tot
        ok = abs(rate - want) <= 0.05
        if not ok:
            problems.append(
                f"DISAGREEMENT  pooled pressure {D.ARM_DISPLAY[arm]}: {rate:.2f}% vs brief {want}%")
        split = (f"  [appraisal-conditioned {appr:,} ({100*appr/rej:.1f}%) / "
                 f"world-conditioned {world:,} ({100*world/rej:.1f}%)]" if named else "")
        print(f"     {D.ARM_DISPLAY[arm]:16s} {rej:>6,} / {tot:>6,} = {rate:>5.1f}%  "
              f"(brief {want}%)  named a validator rule {named:>6,} ({100*named/rej:>5.1f}%)  "
              f"precondition {pc:>6,} ({100*pc/rej:>5.1f}%){split}  "
              f"{'agrees' if ok else '*** DISAGREES ***'}")
    print()

    # ---------------- caveats ------------------------------------------------
    print("-" * 118)
    print("D. CAVEATS CARRIED BY THIS TABLE")
    print("-" * 118)
    for r in rows:
        if r["testbed"] == "irrigation" and r["gov_all_seeds"]:
            g = r["gov_all_seeds"]
            print(f"  {r['model']}: UNBALANCED. Table uses the paired basis "
                  f"{r['paired_units']}. Over the governed arm's own seeds {g['seeds']} the "
                  f"values are cond {g['cond']:.2f}, uncond {g['uncond']:.2f}, "
                  f"HIGH {g['high']:.2f}. Excluded from every paired contrast.")
    bad_align = [r["model"] for r in rows
                 if r["testbed"] == "flood" and not r.get("manifest_seeds_aligned", True)]
    if bad_align:
        print(f"  FLOOD manifest seeds disagree across arms for {len(bad_align)} of "
              f"{sum(1 for r in rows if r['testbed'] == 'flood')} models: {', '.join(bad_align)}.")
        print("    Governed Run_2/Run_3 record seeds 4202/4203 where the no-validator arm records")
        print("    43/44. Pairing is therefore by RUN INDEX, this project's published convention.")
    worst = min((r["coverage_pct"] for r in rows if r["testbed"] == "flood"), default=None)
    if worst is not None:
        print(f"  FLOOD audit csv covers under the nominal 1,000 BY DESIGN, not by loss: "
              f"relocation is an absorbing state (NUMBERS.md section 8 item 2). NOT F1 silent-drop.")
        print(f"    Worst per-run coverage across all flood cells: {worst:.1f}% of the 1,000")
        print("    design-expected decisions. Every flood rate here is a per-run rate over the")
        print("    rows that exist; none is pooled over a 1,000 denominator.")
    print("  FLOOD IS NOT A CONTROL -- it is a cross-theory portability demonstration with no")
    print("    action->environment feedback. Its enforcement pressure and prevalence are")
    print("    descriptive only and support no within-flood identification claim.")
    print("  The published conditional/unconditional rates use the LAST-PROPOSED reading.")
    print("    The EXECUTED reading is reported alongside; the two are not interchangeable.")
    print()
    return problems


# ---------------------------------------------------------------------------
CSV_FIELDS = [
    "testbed", "role", "model",
    "n_gov_units", "n_noval_units", "gov_units", "noval_units",
    "balanced", "n_paired", "paired_units", "excluded_from_paired",
    "decisions_per_run_gov", "decisions_per_run_noval", "audit_coverage_pct_min",
    "manifest_seeds_aligned",
    "pressure_gov", "pressure_noval", "pressure_delta",
    "high_gov", "high_noval", "high_delta", "high_ci_lo", "high_ci_hi",
    "high_t", "high_df", "high_p",
    "cond_gov", "cond_noval", "cond_delta", "cond_ci_lo", "cond_ci_hi", "cond_t", "cond_df", "cond_p",
    "uncond_gov", "uncond_noval", "uncond_delta", "uncond_ci_lo", "uncond_ci_hi",
    "uncond_t", "uncond_df", "uncond_p",
    "cond_exec_gov", "cond_exec_noval", "cond_exec_delta",
    "uncond_exec_gov", "uncond_exec_noval", "uncond_exec_delta",
    "action_reading_of_cond_uncond", "delta_convention",
]


def _blk(row: dict, key: str, prefix: str, full: bool = True) -> dict:
    b = row[key]
    if b is None:
        keys = ["gov", "noval", "delta"] + (["ci_lo", "ci_hi", "t", "df", "p"] if full else [])
        return {f"{prefix}_{k}": "" for k in keys}
    out = {f"{prefix}_{k}": round(b[k], 4) for k in ("gov", "noval", "delta")}
    if full:
        out.update({f"{prefix}_{k}": round(b[k], 4) for k in ("ci_lo", "ci_hi", "t", "p")})
        out[f"{prefix}_df"] = b["df"]
    return out


def write_csv(rows: list[dict], path: str = OUT_CSV) -> str:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            rec = {
                "testbed": r["testbed"], "role": r["role"], "model": r["model"],
                "n_gov_units": len(r["gov_units"]), "n_noval_units": len(r["noval_units"]),
                "gov_units": "|".join(str(x) for x in r["gov_units"]),
                "noval_units": "|".join(str(x) for x in r["noval_units"]),
                "balanced": r["balanced"], "n_paired": r["n_paired"],
                "paired_units": "|".join(str(x) for x in r["paired_units"]),
                "excluded_from_paired": r["excluded_from_paired"],
                "decisions_per_run_gov": "|".join(str(x) for x in r["decisions_per_run_gov"]),
                "decisions_per_run_noval": "|".join(str(x) for x in r["decisions_per_run_noval"]),
                "audit_coverage_pct_min": round(r["coverage_pct"], 2),
                "manifest_seeds_aligned": r.get("manifest_seeds_aligned", ""),
                "action_reading_of_cond_uncond": "last-proposed (cond_/uncond_); executed (cond_exec_/uncond_exec_)",
                "delta_convention": D.DELTA_LABEL,
            }
            rec.update(_blk(r, "pressure", "pressure", full=False))
            rec.update(_blk(r, "high", "high"))
            rec.update(_blk(r, "cond", "cond"))
            rec.update(_blk(r, "uncond", "uncond"))
            rec.update(_blk(r, "cond_exec", "cond_exec", full=False))
            rec.update(_blk(r, "uncond_exec", "uncond_exec", full=False))
            w.writerow(rec)
    return path


def main() -> int:
    rows = irrigation_rows() + flood_rows()
    problems = _print(rows)
    path = write_csv(rows)
    print("=" * 118)
    print(f"wrote {path}  ({len(rows)} cells: "
          f"{sum(1 for r in rows if r['testbed'] == 'irrigation')} irrigation + "
          f"{sum(1 for r in rows if r['testbed'] == 'flood')} flood)")
    if problems:
        print()
        print("*** DISAGREEMENTS WITH THE BRIEF -- REPORT THESE, DO NOT TUNE ***")
        for p in problems:
            print("   ", p)
    else:
        print("every value checkable against the brief AGREES to within 0.005 pp")
    print("=" * 118)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
