"""R7 -- seed robustness for every headline metric.

WHAT IT ANSWERS
  "Five seeds is not many. Show me every seed, show me whether any of them flips
   the sign, and show me a p-value that is honest about n = 5."

EVERY METRIC, PER SEED, BOTH ARMS, WITH THE PAIRED DIFFERENCE
  irrigation (gemma3:4b v21, 5 seeds, seed-matched)
    ibr_proposal        conditional high-WSA increase rate on `yearly_decision`
                        (== proposed_skill == final_skill). THE PUBLISHED HEADLINE.
    ibr_executed        the same statistic after the REJECTED -> maintain_demand remap
    increase_rate_proposal / increase_rate_executed   unconditional versions
    ehe_pooled_proposal / ehe_pooled_executed
                        POOLED-ONCE entropy H/log2(5) over the whole run's action
                        distribution. This is the headline EHE (~0.687 / ~0.848),
                        NOT the per-year entropy in r1.
    mead_min_ft         smallest per-year mean reservoir elevation
    shortage_years      count of years whose mean elevation is below 1,075 ft
  flood (gemma3_4b, 5 runs)
    ibr_flood_uncond / ibr_flood_tp_not_medium / ibr_flood_tp_high, at the `final`
    and `executed` levels; ehe_flood_pooled (H/log2(4)).

TWO NO-VALIDATOR ARMS FOR FLOOD (`noval_arm` column)
  live            examples/single_agent/results/JOH_ABLATION_DISABLED/... , the
                  current corpus. This is the default and the one to quote.
  prequarantine   the same arm as it stood before 2026-05-30: quarantined Run_1..3
                  from _QUARANTINE_reflection_missing_2026-05-30/gemma3_4b plus live
                  Run_4..5. Reconstructed ONLY because two published flood figures
                  (IBR 8.53 +/- 1.08 and EHE 0.815 +/- 0.053) reproduce from it and
                  from nothing else. It is not current data and is never the default.

TWO TEST FAMILIES (`test_family` column)
  paired_one_sample_t_on_differences   the design's own test: one difference per
                  unit, t on those differences. df = n - 1.
  unpaired_two_sample_t                the runs treated as independent groups.
                  df = n1 + n2 - 2 for the pooled-variance (Student) form, plus a
                  Welch unequal-variance form in its own columns. Included because
                  a published flood EHE p reproduces only this way, and because the
                  choice of family flips the verdict on the live arm. `p_paired_t`
                  carries the sentinel N/A_by_design on an unpaired row (and the
                  unpaired columns carry it on a paired row); the unpaired p values
                  live in `p_unpaired_student_t` and `p_unpaired_welch_t`.

PAIRING -- and why flood gets two answers
  Irrigation is seed-matched: seeds 42-46 in both arms, n = 5, df = 4.
  Flood v1 is NOT. Governed carries {42, 4202, 4203, 45, 46}; no-validator carries
  {42, 43, 44, 45, 46}. Three seeds are shared. This script reports BOTH the
  published run-index pairing (n = 5, df = 4) and the seed-matched pairing
  (n = 3, df = 2), and never presents the first as if it were the second.

THE n = 5 CAVEAT, stated as a number
  An exact two-sided sign-flip permutation test on five paired differences has
  2^5 = 32 arrangements. The smallest attainable p is 2/32 = 0.0625. So NO paired
  n = 5 contrast can ever be permutation-significant at 0.05, however large the
  effect. Every p < 0.05 in this package is a Student's t p, which buys its extra
  resolution with a normality assumption five points cannot test. Both are printed.
  For the n = 3 flood pairing the floor is 2/8 = 0.25.

OUTPUT
  out/r7_seed_robustness.csv

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r7_seed_robustness.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import L, PrepError  # noqa: E402

SHORTAGE_FT = 1075.0
FLOOD_MODEL = "gemma3_4b"
FLOOD_ARMS = {
    "governed": ("JOH_FINAL", "Group_C"),
    "ungoverned": ("JOH_ABLATION_DISABLED", "Group_C_disabled"),
}
#: Written into a cell that DOES NOT APPLY to this row's test family -- a paired
#: p on an unpaired row, a permutation floor on a two-sample t. Deliberately
#: distinct from the "NA" that _common.fmt writes for a genuinely computed NaN, so
#: "this quantity is undefined here" can never be read as "this quantity came out
#: empty".
NAD = "N/A_by_design"

QUARANTINE = os.path.join(C.FLOOD_RESULTS,
                          "_QUARANTINE_reflection_missing_2026-05-30", "gemma3_4b")
FLOOD_COND = {
    "uncond": lambda tp: True,
    "tp_not_medium": lambda tp: tp in ("VL", "L", "H", "VH"),
    "tp_high": lambda tp: tp in ("H", "VH"),
}


def irrigation_metrics(arm, seed):
    d = L.run_dir(arm, "", seed)
    sim = L.load_run(d)
    aud = L.load_audit(d)
    hi = [r for r in aud if C.irr_wsa_audit(r) in L.HIGH]
    if not hi:
        raise PrepError(f"{arm} seed {seed}: empty high-WSA denominator")
    out = {}
    for lvl, fn in (("proposal", C.irr_proposal), ("executed", C.irr_executed)):
        out[f"ibr_{lvl}"] = 100.0 * sum(1 for r in hi if fn(r) in L.INCREASE) / len(hi)
        out[f"increase_rate_{lvl}"] = 100.0 * sum(
            1 for r in aud if fn(r) in L.INCREASE) / len(aud)
        counts = {s: 0 for s in C.IRR_SKILLS}
        for r in aud:
            a = fn(r)
            if a in counts:
                counts[a] += 1
        out[f"ehe_pooled_{lvl}"] = C.normalized_entropy(counts, k=5)
    # the published EHE reads simulation_log.yearly_decision; carried separately
    counts = {s: 0 for s in C.IRR_SKILLS}
    for r in sim:
        a = L.action(r)
        if a in counts:
            counts[a] += 1
    out["ehe_pooled_simlog"] = C.normalized_entropy(counts, k=5)

    by = {}
    for r in sim:
        by.setdefault(int(float(r["year"])), []).append(float(r["lake_mead_level"]))
    yearly = [sum(v) / len(v) for _, v in sorted(by.items())]
    out["mead_min_ft"] = min(yearly)
    out["mead_mean_ft"] = C.mean(yearly)
    out["shortage_years"] = float(sum(1 for v in yearly if v < SHORTAGE_FT))
    return out


def flood_metrics(aud, sim):
    out = {}
    # THE PUBLISHED FLOOD EHE. Extended Data Table 2's 0.861 +/- 0.045 is the
    # simulation_log distribution over all 1000 agent-years with `relocated` mapped
    # to `relocate` -- NOT the audit csv, which drops post-relocation rows. Verified:
    # this cell reproduces 0.861 +/- 0.045 for the governed arm exactly.
    counts = {a: 0 for a in C.FLOOD_ACTION_ORDER}
    for r in sim:
        counts[C.flood_normalize_action(r.get("yearly_decision"))] += 1
    out["ehe_flood_pooled_simlog_PUBLISHED"] = C.normalized_entropy(counts, k=4)
    for cname, cfn in FLOOD_COND.items():
        sel = [r for r in aud if cfn(C.flood_normalize_tp(r.get("construct_TP_LABEL")))]
        if not sel:
            raise PrepError(f"flood: empty denominator for {cname}")
        for lvl, fn in (("final", C.flood_final), ("executed", C.flood_executed)):
            out[f"ibr_flood_{cname}_{lvl}"] = C.flood_ibr_components(sel, fn)["ibr_pct"]
    for lvl, fn in (("final", C.flood_final), ("executed", C.flood_executed)):
        counts = {a: 0 for a in C.FLOOD_ACTION_ORDER}
        for r in aud:
            counts[fn(r)] += 1
        out[f"ehe_flood_pooled_{lvl}"] = C.normalized_entropy(counts, k=4)
    return out


def contrast(domain, pairing, metric, pairs, noval_arm="live"):
    """pairs = [(unit_label, governed_value, ungoverned_value), ...]"""
    g = [p[1] for p in pairs]
    u = [p[2] for p in pairs]
    d = [a - b for a, b in zip(g, u)]
    n = len(d)
    t, df = C.paired_t(d)
    signs = {1 if x > 0 else (-1 if x < 0 else 0) for x in d}
    rec = {
        "domain": domain, "noval_arm": noval_arm,
        "test_family": "paired_one_sample_t_on_differences",
        "pairing": pairing, "metric": metric, "n_pairs": n,
        "mean_governed": C.mean(g), "sd_governed": C.sd(g),
        "mean_ungoverned": C.mean(u), "sd_ungoverned": C.sd(u),
        "mean_diff": C.mean(d), "sd_diff": C.sd(d),
        "min_diff": min(d), "max_diff": max(d),
        "n_sign_flips": sum(1 for x in d if (x > 0) != (C.mean(d) > 0)),
        "all_same_sign": len(signs) == 1,
        "t": t, "df": float(df), "p_paired_t": C.t_two_sided_p(t, df),
        "p_exact_permutation": C.exact_perm_p(d),
        "permutation_floor": 2.0 / (1 << n),
        "p_unpaired_student_t": NAD, "t_welch": NAD, "df_welch": NAD,
        "p_unpaired_welch_t": NAD,
    }
    for lab, gv, uv in pairs:
        rec[f"gov_{lab}"] = gv
        rec[f"noval_{lab}"] = uv
        rec[f"diff_{lab}"] = gv - uv
    return rec


def unpaired_contrast(domain, metric, g, u, noval_arm="live"):
    """Two-SAMPLE t: the runs are treated as independent groups, not as pairs.

    Reported because a published p-value can only be reproduced this way, and
    because which family you use changes the verdict. Two variants:
      Student  pooled variance, df = n1 + n2 - 2 (the classic two-sample t)
      Welch    unequal variance, Welch-Satterthwaite df
    Neither is a paired test, so neither is what a per-seed design licenses; both
    are here so the difference is visible instead of implicit.
    """
    import math
    n1, n2 = len(g), len(u)
    if n1 < 2 or n2 < 2:
        raise PrepError(f"unpaired contrast needs >=2 per group, got {n1}/{n2}")
    m1, m2 = C.mean(g), C.mean(u)
    v1, v2 = C.sd(g) ** 2, C.sd(u) ** 2
    sp2 = ((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2)
    se_pooled = math.sqrt(sp2 * (1.0 / n1 + 1.0 / n2))
    t_student = (m1 - m2) / se_pooled if se_pooled else float("nan")
    df_student = float(n1 + n2 - 2)
    se_w = math.sqrt(v1 / n1 + v2 / n2)
    t_welch = (m1 - m2) / se_w if se_w else float("nan")
    df_welch = ((v1 / n1 + v2 / n2) ** 2 /
                ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1))) \
        if se_w else float("nan")
    return {
        "domain": domain, "noval_arm": noval_arm,
        "test_family": "unpaired_two_sample_t",
        "pairing": f"unpaired_n{n1}x{n2}", "metric": metric, "n_pairs": n1,
        "mean_governed": m1, "sd_governed": C.sd(g),
        "mean_ungoverned": m2, "sd_ungoverned": C.sd(u),
        "mean_diff": m1 - m2, "sd_diff": NAD,
        "min_diff": NAD, "max_diff": NAD,
        "n_sign_flips": NAD, "all_same_sign": NAD,
        "t": t_student, "df": df_student,
        # `p_paired_t` carries the N/A_by_design sentinel on an unpaired row: a
        # column named "paired" must never carry an unpaired p, and a blank there
        # would be indistinguishable from a computation that failed.
        "p_paired_t": NAD,
        "p_unpaired_student_t": C.t_two_sided_p(t_student, df_student),
        "p_exact_permutation": NAD,
        "permutation_floor": NAD,
        "t_welch": t_welch, "df_welch": df_welch,
        "p_unpaired_welch_t": C.t_two_sided_p(t_welch, df_welch),
    }


def main() -> int:
    C.banner("R7  seed robustness")
    rows = []

    seeds = L.paired_seeds("")
    irr = {a: {s: irrigation_metrics(a, s) for s in seeds}
           for a in ("governed", "ungoverned")}
    for m in sorted(next(iter(irr["governed"].values())).keys()):
        rows.append(contrast("irrigation", "seed_matched_n5", m,
                             [(s, irr["governed"][s][m], irr["ungoverned"][s][m])
                              for s in seeds]))
    print(f"  irrigation: {len(seeds)} seed-matched pairs")

    def _load(runmap):
        return {run: (seed, flood_metrics(
            C.read_csv(os.path.join(rd, C.FLOOD_AUDIT)),
            C.read_csv(os.path.join(rd, C.FLOOD_SIM))))
            for run, (seed, rd) in runmap.items()}

    fl = {arm: _load(C.flood_runs(root, FLOOD_MODEL, group))
          for arm, (root, group) in FLOOD_ARMS.items()}

    # The PRE-QUARANTINE no-validator arm, reconstructed. Not current data: it is
    # the corpus as it stood before 2026-05-30, when Run_1..Run_3 were moved to
    # _QUARANTINE_reflection_missing_2026-05-30/ for the documented reflection-OFF
    # defect and re-run. It is built here because several published flood numbers
    # (IBR 8.53 +/- 1.08, EHE 0.815 +/- 0.053) reproduce from it and from nothing
    # else, and a package that cannot regenerate them cannot defend them.
    live_noval = C.flood_runs("JOH_ABLATION_DISABLED", FLOOD_MODEL, "Group_C_disabled")
    pq = {}
    for run in ("Run_1", "Run_2", "Run_3"):
        rd = os.path.join(QUARANTINE, run)
        if not os.path.isdir(rd):
            raise PrepError(f"missing quarantined run {rd}")
        pq[run] = (C.flood_seed_of(rd), rd)
    for run in ("Run_4", "Run_5"):
        pq[run] = live_noval[run]
    fl["ungoverned_prequarantine"] = _load(pq)

    runs = sorted(set(fl["governed"]) & set(fl["ungoverned"]))
    seed_g = {v[0]: v[1] for v in fl["governed"].values()}
    seed_u = {v[0]: v[1] for v in fl["ungoverned"].values()}
    shared = sorted(set(seed_g) & set(seed_u))
    print(f"  flood: {len(runs)} run-index pairs (PUBLISHED pairing); "
          f"{len(shared)} seed-matched pairs {shared}")
    print(f"  flood pre-quarantine arm: "
          f"{ {r: v[0] for r, v in fl['ungoverned_prequarantine'].items()} }")

    NOVAL = {"live": "ungoverned", "prequarantine": "ungoverned_prequarantine"}
    for m in sorted(next(iter(fl["governed"].values()))[1].keys()):
        for label, key in NOVAL.items():
            rows.append(contrast("flood", "run_index_n5_published", m,
                                 [(r, fl["governed"][r][1][m], fl[key][r][1][m])
                                  for r in runs], noval_arm=label))
            rows.append(unpaired_contrast(
                "flood", m,
                [fl["governed"][r][1][m] for r in runs],
                [fl[key][r][1][m] for r in runs], noval_arm=label))
        rows.append(contrast("flood", f"seed_matched_n{len(shared)}", m,
                             [(s, seed_g[s][m], seed_u[s][m]) for s in shared],
                             noval_arm="live"))

    base = ["domain", "noval_arm", "test_family", "pairing", "metric", "n_pairs",
            "mean_governed", "sd_governed",
            "mean_ungoverned", "sd_ungoverned", "mean_diff", "sd_diff", "min_diff",
            "max_diff", "n_sign_flips", "all_same_sign", "t", "df", "p_paired_t",
            "p_unpaired_student_t", "t_welch", "df_welch", "p_unpaired_welch_t",
            "p_exact_permutation", "permutation_floor"]
    extra = sorted({k for r in rows for k in r} - set(base))
    C.write_csv("r7_seed_robustness.csv", base + extra, rows)

    print(f"\n  {'domain':10s} {'noval arm':14s} {'pairing':22s} {'metric':38s} "
          f"{'gov':>9s} {'noval':>9s} {'diff':>9s} {'p':>9s} {'perm-p':>7s} "
          f"{'flips':>6s}")
    for r in rows:
        p = r["p_paired_t"] if r["test_family"].startswith("paired") \
            else r["p_unpaired_student_t"]
        perm = r["p_exact_permutation"]
        print(f"  {r['domain']:10s} {r.get('noval_arm', ''):14s} {r['pairing']:22s} "
              f"{r['metric']:38s} "
              f"{r['mean_governed']:9.3f} {r['mean_ungoverned']:9.3f} "
              f"{r['mean_diff']:9.3f} {p:9.5f} "
              f"{(f'{perm:7.4f}' if isinstance(perm, float) and perm == perm else '    n/a')} "
              f"{('n/a' if r['n_sign_flips'] == NAD else str(r['n_sign_flips'])):>6s}")
    print("\n  n=5 permutation floor 0.0625; n=3 floor 0.2500. "
          "No paired n=5 test can be permutation-significant at 0.05.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
