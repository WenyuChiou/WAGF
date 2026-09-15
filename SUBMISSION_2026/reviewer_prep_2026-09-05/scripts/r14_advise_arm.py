"""R14 -- irrigation: the advise arm (strict profile + governance.advise_mode: feedback).

WHAT IT ANSWERS
  Tier-1 pre-registered question (plan Section 3, T1-2): does telling the model about
  a WARNING-level finding, without changing whether the decision is blocked, change
  what the model proposes? `docs/guides/governance_layers.md` (read from origin/main,
  since this branch's working tree does not carry the doc) defines the mechanism:
  under `advise_mode: feedback` a WARNING finding on an otherwise-APPROVED decision
  triggers one extra, non-blocking LLM call; the model's post-advice proposal is kept
  only if it is itself APPROVED, and the row's `status` is exactly what it would have
  been with the channel off.

RUN DISCOVERED
  examples/irrigation_abm/results/advise_feedback_42yr_gemma3_4b_e0eee08c_seed{N}/
  strict profile, advise_mode: feedback, gemma3:4b, 78 agents x 42 years, code
  e0eee08c. A run counts as COMPLETE only if it has an audit csv, a simulation_log
  and a run_integrity.json -- the GPU batch is writing seed 43 as this script is
  written, and that directory is deliberately NOT touched or waited on. Any
  incomplete seed is reported and skipped, never treated as zero rows.

REFERENCE ARMS (recomputed here, not read from another table's CSV)
  strict       examples/irrigation_abm/results/production_v21_42yr_seed{N}   (`_loader` "governed")
  no_validator examples/irrigation_abm/results/ungoverned_v21_42yr_seed{N}   (`_loader` "ungoverned")
  Both are DIFFERENT code commits / separate real-LLM runs from the advise arm (not a
  byte-identical harness rerun), so a status-share gap on the order of the LLM's own
  run-to-run sampling variance is expected and is not evidence advise_mode changed
  blocking. `_loader.paired_seeds` is not used for the strict/no-val reference rows
  here because this table's unit is a single seed against itself, not a cross-seed
  contrast.

DEFINITIONS -- none invented
  ibr_pct_proposal / increase_rate_pct_proposal / ehe_pooled_proposal
      `_loader.ibr` / `_loader.increase_rate`, applied to simulation_log
      `yearly_decision` (== proposed_skill == final_skill on non-fallback rows).
      This is the published-headline level. EHE is POOLED ONCE over the whole run's
      3276 decisions, H/log2(5) -- never averaged per year.
  ibr_pct_executed / increase_rate_pct_executed / ehe_pooled_executed
      Same statistics after the REJECTED* -> `maintain_demand` remap
      (`reproduce_published.py:51-53`, transcribed as `_common.irr_executed`).
  status shares  approved_first_attempt (APPROVED, retry_count==0), approved_after_retry
      (APPROVED, retry_count>0), rejected_to_fallback (status startswith REJECTED) --
      the same three buckets r3_rule_firing_census.py uses, and together they must
      cover every row exactly once.
  advice columns (`docs/guides/governance_layers.md` Section 1)
      advise_shown            the model was sent the extra prompt (set from
                              advise_reports_shown, never merely asserted)
      advise_skill_before/_after   the proposal immediately before / after the
                              advisory call
      advise_executed_stage   "pre" (post-advice proposal failed validation, the
                              pre-advice proposal executed) or "post"
      advise_post_validation_invalid   the post-advice proposal would NOT have
                              validated, whatever stage executed
      UPTAKE = share of ADVISED rows (advise_shown==True) whose advise_skill_after
      differs from advise_skill_before. Denominator is n_advised, stated explicitly
      in every output row as `uptake_denominator` so it is never confused with the
      run's 3276-row denominator.
  Mead / shortage  same thresholds as r1/r7: DEAD_POOL_FT=895.0 (FQL_BASELINE_NOTE),
      SHORTAGE_FT=1075.0. mead_min_ft = smallest per-year mean elevation;
      shortage_years = count of years whose per-year mean is below 1075 ft;
      first_dead_pool_year = smallest year whose per-year mean is <= 895 ft, or
      the literal "none" if no year reaches it.

INTEGRITY GATE (raises before computing anything if any seed fails)
  audit row count == 3276; run_integrity.json integrity_ok == true and
  audit_rows == 3276; reproducibility_manifest.json num_ctx == 8192 and
  num_predict == 4096; soft_advise_mode == "feedback" on every row of the seed.

OUTPUT
  out/r14_advise_arm.csv       one row per (arm, seed): advise / strict / no_validator
  out/r14_advise_findings.csv  per advise seed: which rule ids produced advice, and
                               the before->after direction of every changed proposal
  out/r14_advise_yearly.csv    per-year increase_rate (proposal level), advise vs
                               strict vs no_validator, plus advise-minus-strict diff
  out/r14_advise_stats_n5.csv  cross-seed paired/one-sample stats block (see note below)

# 2026-09-10 n=5: extended from the n=3 interim look (seeds 42-44) to all five
# COMPLETE advise seeds (42-46). Two changes from the interim version:
#   1. discover_advise_seeds() now SKIPS (does not raise on) any directory that
#      matches the advise prefix but not `..._seed<digits>` exactly -- concretely
#      the `..._seed46_PARTIAL_killed_2026-09-08` directory left behind by the
#      killed-and-restarted seed 46 run. It is excluded from consideration entirely,
#      not treated as an incomplete seed.
#   2. The cross-seed block now reports every pre-registered T1-2 metric --
#      uptake_share_pct (one-sample vs 0, no strict counterpart), rejected_to_fallback_pct,
#      ibr_pct_proposal, ibr_pct_executed, increase_rate_pct_proposal, ehe_pooled_proposal,
#      mead_min_ft, shortage_years (paired advise-minus-strict on the rest) -- each with
#      mean +/- sd per arm, a 95% CI on the paired (or one-sample) difference via a
#      stdlib bisection against `t_two_sided_p` (no scipy dependency, matching
#      `_loader.py`'s own stdlib-only stats), the parametric t p, the exact sign-flip
#      permutation p (n=5 floor 2/32 = 0.0625), and whether all 5 pairs share a sign.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r14_advise_arm.py
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import L, PrepError  # noqa: E402

ADVISE_PREFIX = "advise_feedback_42yr_gemma3_4b_e0eee08c_seed"
EXPECTED_ROWS = L.EXPECTED_ROWS
NUM_CTX_EXPECT = 8192
NUM_PREDICT_EXPECT = 4096
DEAD_POOL_FT = 895.0
SHORTAGE_FT = 1075.0
NAD = "N/A_by_design"   # doesn't apply to this row's arm -- distinct from a computed NaN


# ---------------------------------------------------------------------------
# discovery -- the advise arm uses its own directory shape, not _loader.run_dirs'
# ---------------------------------------------------------------------------
def discover_advise_seeds():
    pat = os.path.join(L.RESULTS, ADVISE_PREFIX + "*")
    hits = sorted(glob.glob(pat))
    if not hits:
        raise PrepError(f"no advise-arm run directories at all matched {pat}")
    complete, incomplete = [], []
    for d in hits:
        # 2026-09-10: a directory matching the prefix but not exactly
        # `<prefix><digits>` (e.g. the seed-46 killed-and-restarted
        # `..._PARTIAL_killed_2026-09-08` directory) is not a seed run at all --
        # skip it silently, do not raise and do not count it as incomplete.
        m = re.fullmatch(re.escape(ADVISE_PREFIX) + r"(\d+)", os.path.basename(d))
        if not m:
            print(f"  IGNORED (not a `seed<digits>` run directory): {os.path.basename(d)}")
            continue
        seed = m.group(1)
        need = [L.AUDIT_LOG, L.SIM_LOG, "run_integrity.json", "reproducibility_manifest.json"]
        missing = [f for f in need if not os.path.isfile(os.path.join(d, f))]
        if missing:
            incomplete.append((seed, d, f"missing {missing} -- run in progress or not finalized"))
        else:
            complete.append((seed, d))
    if not complete:
        raise PrepError(
            "no COMPLETE advise-arm run found (audit+sim+integrity+manifest all present). "
            f"Directories seen: {[(s, r) for s, _, r in incomplete]}"
        )
    return complete, incomplete


# ---------------------------------------------------------------------------
# integrity gate
# ---------------------------------------------------------------------------
def check_integrity(seed, d, aud):
    with open(os.path.join(d, "run_integrity.json"), encoding="utf-8") as fh:
        ri = json.load(fh)
    with open(os.path.join(d, "reproducibility_manifest.json"), encoding="utf-8") as fh:
        mf = json.load(fh)
    problems = []
    if len(aud) != EXPECTED_ROWS:
        problems.append(f"audit has {len(aud)} rows, expected {EXPECTED_ROWS}")
    if ri.get("integrity_ok") is not True:
        problems.append(f"run_integrity.integrity_ok = {ri.get('integrity_ok')!r}, not True")
    if ri.get("audit_rows") != EXPECTED_ROWS:
        problems.append(f"run_integrity.audit_rows = {ri.get('audit_rows')!r}")
    if mf.get("num_ctx") != NUM_CTX_EXPECT:
        problems.append(f"manifest num_ctx = {mf.get('num_ctx')!r}, expected {NUM_CTX_EXPECT}")
    if mf.get("num_predict") != NUM_PREDICT_EXPECT:
        problems.append(f"manifest num_predict = {mf.get('num_predict')!r}, expected {NUM_PREDICT_EXPECT}")
    if str(mf.get("seed")) != str(seed):
        problems.append(f"manifest seed = {mf.get('seed')!r}, directory says {seed!r}")
    modes = {(r.get("soft_advise_mode") or "").strip() for r in aud}
    if modes != {"feedback"}:
        problems.append(f"soft_advise_mode not uniformly 'feedback' across all rows: {modes}")
    if problems:
        raise PrepError(f"seed {seed} FAILED integrity gate:\n    " + "\n    ".join(problems))
    return ri, mf


# ---------------------------------------------------------------------------
# core metrics (sim-level = published headline; audit-level executed remap)
# ---------------------------------------------------------------------------
def _year(row) -> int:
    return int(float(row["year"]))


def sim_core_metrics(sim):
    if len(sim) != EXPECTED_ROWS:
        raise PrepError(f"sim has {len(sim)} rows, expected {EXPECTED_ROWS}")
    counts = {s: 0 for s in C.IRR_SKILLS}
    for r in sim:
        a = L.action(r)
        if a not in counts:
            raise PrepError(f"off-registry simulation_log action {a!r}")
        counts[a] += 1
    by_year_mead, by_year_incr, by_year_n = {}, {}, {}
    for r in sim:
        y = _year(r)
        by_year_mead.setdefault(y, []).append(float(r["lake_mead_level"]))
        by_year_incr.setdefault(y, []).append(1 if L.action(r) in L.INCREASE else 0)
    yearly_mead = {y: sum(v) / len(v) for y, v in sorted(by_year_mead.items())}
    yearly_incr_pct = {y: 100.0 * sum(v) / len(v) for y, v in sorted(by_year_incr.items())}
    mead_vals = list(yearly_mead.values())
    shortage_years = sum(1 for v in mead_vals if v < SHORTAGE_FT)
    dead_pool_years = [y for y, v in sorted(yearly_mead.items()) if v <= DEAD_POOL_FT + 1e-9]
    return {
        "ibr_pct_proposal": L.ibr(sim),
        "increase_rate_pct_proposal": L.increase_rate(sim),
        "ehe_pooled_proposal": C.normalized_entropy(counts, k=5),
        "mead_min_ft": min(mead_vals),
        "mead_mean_ft": C.mean(mead_vals),
        "shortage_years": shortage_years,
        "first_dead_pool_year": (dead_pool_years[0] if dead_pool_years else "none"),
    }, yearly_incr_pct


def audit_executed_metrics(aud):
    hi = [r for r in aud if C.irr_wsa_audit(r) in L.HIGH]
    if not hi:
        raise PrepError("empty high-WSA denominator on the executed level")
    counts = {s: 0 for s in C.IRR_SKILLS}
    for r in aud:
        a = C.irr_executed(r)
        if a not in counts:
            raise PrepError(f"off-registry executed action {a!r}")
        counts[a] += 1
    return {
        "ibr_pct_executed": 100.0 * sum(1 for r in hi if C.irr_executed(r) in L.INCREASE) / len(hi),
        "increase_rate_pct_executed": 100.0 * sum(
            1 for r in aud if C.irr_executed(r) in L.INCREASE) / len(aud),
        "ehe_pooled_executed": C.normalized_entropy(counts, k=5),
    }


def status_shares(aud):
    n = len(aud)
    rc = [int(float((r.get("retry_count") or "0").strip() or 0)) for r in aud]
    st = [(r.get("status") or "").strip() for r in aud]
    first = sum(1 for s, c in zip(st, rc) if s == "APPROVED" and c == 0)
    retry = sum(1 for s, c in zip(st, rc) if s == "APPROVED" and c > 0)
    fallback = sum(1 for s in st if s.startswith("REJECTED"))
    if first + retry + fallback != n:
        raise PrepError(f"status buckets cover {first + retry + fallback} of {n} rows")
    return {
        "approved_first_attempt_pct": 100.0 * first / n,
        "approved_after_retry_pct": 100.0 * retry / n,
        "rejected_to_fallback_pct": 100.0 * fallback / n,
    }


# ---------------------------------------------------------------------------
# advice-specific metrics -- advise arm only
# ---------------------------------------------------------------------------
def _truthy(v) -> bool:
    return (v or "").strip().lower() in ("true", "1")


def advice_metrics(aud):
    advised = [r for r in aud if _truthy(r.get("advise_shown"))]
    n_advised = len(advised)
    if n_advised == 0:
        raise PrepError("zero advise_shown=True rows -- advise_mode not actually active on this seed")
    finding_ids = Counter()
    for r in advised:
        for f in (r.get("advise_findings") or "").split(";"):
            f = f.strip()
            if f:
                finding_ids[f] += 1
    changed = [r for r in advised
               if (r.get("advise_skill_before") or "").strip()
               != (r.get("advise_skill_after") or "").strip()]
    directions = Counter(
        ((r.get("advise_skill_before") or "").strip(), (r.get("advise_skill_after") or "").strip())
        for r in changed)
    invalid = sum(1 for r in advised if _truthy(r.get("advise_post_validation_invalid")))
    stage = Counter((r.get("advise_executed_stage") or "").strip() for r in advised)
    parse_failed = sum(1 for r in advised if _truthy(r.get("advise_parse_failed")))
    unidentified_total = sum(
        int(float((r.get("soft_findings_unidentified") or "0").strip() or 0)) for r in aud)
    summary = {
        "n_advised": n_advised,
        "advised_share_of_rows_pct": 100.0 * n_advised / len(aud),
        "uptake_n_changed": len(changed),
        "uptake_denominator": n_advised,
        "uptake_share_pct": 100.0 * len(changed) / n_advised,
        "advise_post_validation_invalid_share_pct": 100.0 * invalid / n_advised,
        "advise_parse_failed_share_pct": 100.0 * parse_failed / n_advised,
        "advise_executed_stage_pre_n": stage.get("pre", 0),
        "advise_executed_stage_post_n": stage.get("post", 0),
        "soft_findings_unidentified_total_all_rows": unidentified_total,
    }
    return summary, finding_ids, directions


# ---------------------------------------------------------------------------
# reference arms (strict / no_validator), same seed, via _loader
# ---------------------------------------------------------------------------
def reference_row(arm_label, loader_arm, seed):
    d = L.run_dir(loader_arm, "", seed)
    sim = L.load_run(d)
    aud = L.load_audit(d)
    if len(sim) != EXPECTED_ROWS or len(aud) != EXPECTED_ROWS:
        raise PrepError(f"{arm_label} seed {seed}: sim/audit row count mismatch")
    core, yearly_incr = sim_core_metrics(sim)
    exe = audit_executed_metrics(aud)
    st = status_shares(aud)
    row = {"arm": arm_label, "seed": seed, "n_rows": len(sim), **core, **exe, **st}
    for k in ("n_advised", "advised_share_of_rows_pct", "uptake_n_changed",
              "uptake_denominator", "uptake_share_pct",
              "advise_post_validation_invalid_share_pct",
              "advise_parse_failed_share_pct", "advise_executed_stage_pre_n",
              "advise_executed_stage_post_n", "soft_findings_unidentified_total_all_rows"):
        row[k] = NAD
    return row, yearly_incr


def main() -> int:
    C.banner("R14  irrigation advise arm (strict + advise_mode: feedback)")

    complete, incomplete = discover_advise_seeds()
    print(f"advise-arm seeds COMPLETE: {[s for s, _ in complete]}")
    for s, d, reason in incomplete:
        print(f"  SKIPPED seed {s} ({os.path.basename(d)}): {reason}")
    if not complete:
        raise PrepError("no complete advise-arm seeds -- see skip reasons above")

    main_rows = []
    finding_rows = []
    yearly_rows = []
    per_seed_advise = {}

    for seed, d in complete:
        aud = L.load_audit(d)
        sim = L.load_run(d)
        ri, mf = check_integrity(seed, d, aud)
        print(f"\n  seed {seed}: integrity OK (audit_rows={ri['audit_rows']}, "
              f"num_ctx={mf['num_ctx']}, num_predict={mf['num_predict']}, "
              f"soft_advise_mode uniform 'feedback')")

        core, yearly_incr_advise = sim_core_metrics(sim)
        exe = audit_executed_metrics(aud)
        st = status_shares(aud)
        adv_summary, finding_ids, directions = advice_metrics(aud)
        per_seed_advise[seed] = (core, yearly_incr_advise)

        row = {"arm": "advise_feedback", "seed": seed, "n_rows": len(sim),
               **core, **exe, **st, **adv_summary}
        main_rows.append(row)

        for fid, cnt in sorted(finding_ids.items(), key=lambda kv: -kv[1]):
            finding_rows.append({
                "seed": seed, "kind": "finding_id", "key": fid, "n": cnt,
                "share_of_advised_pct": 100.0 * cnt / adv_summary["n_advised"],
            })
        for (before, after), cnt in sorted(directions.items(), key=lambda kv: -kv[1]):
            finding_rows.append({
                "seed": seed, "kind": "direction_change", "key": f"{before}->{after}",
                "n": cnt, "share_of_advised_pct": 100.0 * cnt / adv_summary["n_advised"],
            })

        print(f"  seed {seed}: n_advised={adv_summary['n_advised']} "
              f"({adv_summary['advised_share_of_rows_pct']:.2f}% of rows), "
              f"uptake={adv_summary['uptake_share_pct']:.2f}% "
              f"({adv_summary['uptake_n_changed']}/{adv_summary['uptake_denominator']})")
        print(f"  seed {seed}: rule ids producing advice: "
              + ", ".join(f"{k}={v}" for k, v in finding_ids.most_common()))
        print(f"  seed {seed}: before->after directions: "
              + ", ".join(f"{k[0]}->{k[1]}={v}" for k, v in directions.most_common()))

        # reference arms, same seed
        for arm_label, loader_arm in (("strict", "governed"), ("no_validator", "ungoverned")):
            try:
                ref_row, ref_yearly = reference_row(arm_label, loader_arm, seed)
            except PrepError as exc:
                print(f"  reference arm {arm_label} seed {seed} UNAVAILABLE: {exc}")
                continue
            main_rows.append(ref_row)
            if arm_label == "strict":
                for y in sorted(set(yearly_incr_advise) | set(ref_yearly)):
                    a_rate = yearly_incr_advise.get(y)
                    s_rate = ref_yearly.get(y)
                    yearly_rows.append({
                        "seed": seed, "year": y,
                        "increase_rate_pct_advise": a_rate if a_rate is not None else float("nan"),
                        "increase_rate_pct_strict": s_rate if s_rate is not None else float("nan"),
                        "diff_advise_minus_strict": (
                            (a_rate - s_rate) if (a_rate is not None and s_rate is not None)
                            else float("nan")),
                    })

    # -----------------------------------------------------------------
    # cross-seed stats, 2026-09-10 n=5 extension (see module docstring note).
    # Every T1-2 pre-registered metric gets: mean +/- sd per arm, a 95% CI on
    # the paired (or one-sample) difference, the parametric paired-t p, the
    # exact sign-flip permutation p, and a same-sign-on-every-seed check.
    # Written to its own out/r14_advise_stats_n5.csv rather than smuggled into
    # r14_advise_arm.csv's column union (which is how the n=3 interim script
    # did it, for only 3 metrics) -- the per-arm/per-seed rows in
    # r14_advise_arm.csv are otherwise unchanged.
    # -----------------------------------------------------------------
    adv_seeds = sorted(per_seed_advise)
    advise_by_seed = {r["seed"]: r for r in main_rows if r["arm"] == "advise_feedback"}
    strict_by_seed = {r["seed"]: r for r in main_rows if r["arm"] == "strict"}
    stats_rows = []

    def t_crit_95(df):
        """Two-sided 95% critical t for `df`, via bisection against
        C.t_two_sided_p (stdlib only -- no scipy, matching _loader.py)."""
        if df <= 0:
            return float("nan")
        lo, hi = 0.0, 1000.0
        for _ in range(200):
            mid = (lo + hi) / 2.0
            if C.t_two_sided_p(mid, df) > 0.05:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0

    def direction_note(vals):
        n_pos = sum(1 for v in vals if v > 0)
        n_neg = sum(1 for v in vals if v < 0)
        n_zero = len(vals) - n_pos - n_neg
        if n_zero == 0 and (n_pos == 0 or n_neg == 0):
            return f"consistent ({'all positive' if n_pos else 'all negative'}, {len(vals)}/{len(vals)})"
        return f"NOT consistent ({n_pos} positive / {n_neg} negative / {n_zero} zero of {len(vals)})"

    def emit_paired(metric, common):
        a_vals = [advise_by_seed[s][metric] for s in common]
        s_vals = [strict_by_seed[s][metric] for s in common]
        diffs = [a - b for a, b in zip(a_vals, s_vals)]
        n = len(diffs)
        t, df = C.paired_t(diffs)
        p_t = C.t_two_sided_p(t, df)
        p_perm = C.exact_perm_p(diffs)
        d_mean, d_sd = C.mean(diffs), C.sd(diffs)
        half = t_crit_95(df) * d_sd / (n ** 0.5) if d_sd == d_sd else float("nan")
        stats_rows.append({
            "metric": metric, "test": "paired advise-minus-strict", "n": n,
            "mean_advise": C.mean(a_vals), "sd_advise": C.sd(a_vals),
            "mean_strict": C.mean(s_vals), "sd_strict": C.sd(s_vals),
            "mean_diff": d_mean, "sd_diff": d_sd,
            "ci95_lo": d_mean - half, "ci95_hi": d_mean + half,
            "t": t, "df": float(df), "p_paired_t": p_t, "p_exact_perm": p_perm,
            "direction": direction_note(diffs),
        })
        print(f"  {metric:28s} diff {d_mean:+9.4f} +/- {d_sd:.4f}  "
              f"95% CI [{d_mean - half:+.4f}, {d_mean + half:+.4f}]  "
              f"t={t:.3f} df={df} p_t={p_t:.4f} p_perm={p_perm:.4f}  {direction_note(diffs)}")

    def emit_one_sample(metric, seeds_list, label):
        vals = [advise_by_seed[s][metric] for s in seeds_list]
        n = len(vals)
        t, df = C.paired_t(vals)   # one-sample t vs 0 == paired_t on the raw values
        p_t = C.t_two_sided_p(t, df)
        p_perm = C.exact_perm_p(vals)
        m, s = C.mean(vals), C.sd(vals)
        half = t_crit_95(df) * s / (n ** 0.5) if s == s else float("nan")
        stats_rows.append({
            "metric": metric, "test": f"one-sample vs 0 ({label})", "n": n,
            "mean_advise": m, "sd_advise": s, "mean_strict": "", "sd_strict": "",
            "mean_diff": m, "sd_diff": s,
            "ci95_lo": m - half, "ci95_hi": m + half,
            "t": t, "df": float(df), "p_paired_t": p_t, "p_exact_perm": p_perm,
            "direction": direction_note(vals),
        })
        print(f"  {metric:28s} mean {m:+9.4f} +/- {s:.4f}  "
              f"95% CI [{m - half:+.4f}, {m + half:+.4f}]  "
              f"t={t:.3f} df={df} p_t={p_t:.4f} p_perm={p_perm:.4f}  "
              f"{direction_note(vals)}  (one-sample vs 0)")

    if len(adv_seeds) >= 2:
        common = [s for s in adv_seeds if s in strict_by_seed]
        if len(common) >= 2:
            print(f"\n  cross-seed contrast computed on {len(common)} seeds: {common}")
            for metric in (
                "rejected_to_fallback_pct", "ibr_pct_proposal", "ibr_pct_executed",
                "increase_rate_pct_proposal", "ehe_pooled_proposal", "mead_min_ft",
                "shortage_years",
            ):
                emit_paired(metric, common)
            emit_one_sample("uptake_share_pct", adv_seeds, "uptake > 0, H-a")
        else:
            print("\n  fewer than 2 seeds common to advise+strict -- no paired-t rows emitted")
    else:
        print(f"\n  only {len(adv_seeds)} complete advise seed(s) ({adv_seeds}) -- "
              "reporting single-seed numbers only, no mean/sd/paired-t across advise seeds.")

    if stats_rows:
        C.write_csv(
            "r14_advise_stats_n5.csv",
            ["metric", "test", "n", "mean_advise", "sd_advise", "mean_strict", "sd_strict",
             "mean_diff", "sd_diff", "ci95_lo", "ci95_hi", "t", "df", "p_paired_t",
             "p_exact_perm", "direction"],
            stats_rows,
        )

    # column order: union of keys across all rows, arm/seed first
    all_keys = []
    for r in main_rows:
        for k in r:
            if k not in all_keys:
                all_keys.append(k)
    ordered = ["arm", "seed", "n_rows"] + [k for k in all_keys if k not in ("arm", "seed", "n_rows")]
    for r in main_rows:
        for k in ordered:
            r.setdefault(k, NAD)
    C.write_csv("r14_advise_arm.csv", ordered, main_rows)

    C.write_csv("r14_advise_findings.csv",
                ["seed", "kind", "key", "n", "share_of_advised_pct"], finding_rows)

    C.write_csv("r14_advise_yearly.csv",
                ["seed", "year", "increase_rate_pct_advise", "increase_rate_pct_strict",
                 "diff_advise_minus_strict"], yearly_rows)

    print("\n  --- headline comparison (first complete advise seed) ---")
    s0 = adv_seeds[0]
    adv_row = next(r for r in main_rows if r["arm"] == "advise_feedback" and r["seed"] == s0)
    strict_row = next((r for r in main_rows if r["arm"] == "strict" and r["seed"] == s0), None)
    noval_row = next((r for r in main_rows if r["arm"] == "no_validator" and r["seed"] == s0), None)
    for label, row in (("advise_feedback", adv_row), ("strict", strict_row), ("no_validator", noval_row)):
        if row is None:
            print(f"    {label:16s} UNAVAILABLE")
            continue
        print(f"    {label:16s} IBR(prop) {row['ibr_pct_proposal']:6.2f}%  "
              f"incr(prop) {row['increase_rate_pct_proposal']:6.2f}%  "
              f"EHE(prop) {row['ehe_pooled_proposal']:.4f}  "
              f"mead_min {row['mead_min_ft']:7.2f} ft  shortage_yrs {row['shortage_years']:>2}  "
              f"rejected_to_fallback {row['rejected_to_fallback_pct']:5.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
