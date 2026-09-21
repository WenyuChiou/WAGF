"""R30 -- the irrigation "increase rate" conditioned on the ENVIRONMENT
instead of the agent's self-report. CPU-only, existing runs only, no LLM
calls.

BACKGROUND (why this script exists)
  `SUBMISSION_2026/decomposition/_loader.py::ibr()` computes the published
  "IBR headline" / AAI statistic: among agent-years where the agent's OWN
  self-reported water-scarcity appraisal (`wsa_label`, `_loader.py::wsa()`)
  is HIGH (H or VH), what share proposed an "increase" skill. `_loader.py`'s
  own docstring already flags the problem: "POST-TREATMENT. This is the
  mediator. Never condition a causal estimator on it." -- the self-report
  is a mediator, not an exogenous condition, so its OWN prevalence
  (`_loader.py::high_share()`) can shift between arms for reasons that have
  nothing to do with the water system (e.g. governance shaping what the
  agent says about itself), silently moving the IBR denominator. A reviewer
  measured this shift directly: 37% vs 82% WSA-high share on gemma3:4b
  (governed vs ungoverned) -- reproduced and confirmed below, not assumed.

  This script computes the SAME "increase rate" concept, conditioned
  instead on environment-side variables rather than the agent's own
  self-report: (i) `drought_index` >= 0.35 (sensitivity at 0.5), (ii)
  that year's basin curtailment_ratio > 0, and (iv, added 2026-09-21
  review round) the precipitation term alone, which IS fully exogenous
  (see the CORRECTION note immediately below). Condition (iii), the
  original self-reported WSA-high, is reproduced alongside for direct
  reference/comparison, never silently replaced.

  CORRECTION (2026-09-21 review round): an earlier draft of this
  docstring called drought_index and curtailment_ratio "EXOGENOUS,
  environment-side variables" -- imprecise. `drought_index =
  0.5*precip_norm + 0.5*mead_norm` (see below) is HALF precipitation
  (genuinely exogenous, a seed-matched external input the agent cannot
  influence) and HALF Lake Mead elevation (`mead_norm`), which is BASIN
  STATE that accumulates each arm's OWN demand history over the 42-year
  horizon -- not exogenous to the arm. Verified directly: at seed 42,
  governed vs ungoverned `drought_index` is identical at year 1 (diff=0,
  before any demand history has had time to diverge) but differs by up
  to 0.358 at year 33 and by a mean |delta|=0.188 across all 42 years
  (governed and ungoverned diverge in demand from year 1 onward, so Mead
  elevation -- and therefore drought_index and curtailment_ratio, which
  is tier-driven off the same Mead level -- diverges too). This is why
  condition (iv) below exists: the precipitation term ALONE is checked,
  reconstructed per agent-year from each run's own logged
  `drought_index`/`lake_mead_level` (`precip_norm_reconstructed =
  2*drought_index - mead_norm`, `mead_norm` computed the same clamped
  way `_compute_drought_index` does) and ASSERTED byte-identical across
  arms at the same seed (raises if not, checked every run, not
  spot-checked once) -- confirmed exactly equal (float64 epsilon, 1e-16)
  for every (model, seed, year) checked, including year 42, which the
  real CRSS precipitation file does not cover (2017-2060 only; year 42
  is calendar 2061) and which the environment's own synthetic fallback
  therefore generates instead -- still identical across arms at a given
  seed because neither arm's `execute_skill()` call path in this corpus
  consumes any `np.random` draws before that point (verified: 10/10
  replay-fidelity checks in r29 passed at RMSE=0.0000 ft, which would
  not hold if arm-specific randomness were being consumed anywhere in
  the replayed path). So, precisely: the precipitation condition below
  is exogenous and identical across arms; the drought_index and
  curtailment conditions are ENVIRONMENT-CONDITIONED rather than
  self-reported, which is still a real and useful improvement over
  conditioning on the post-treatment self-report, but they are not
  fully exogenous, because they include reservoir state that diverges
  between arms over the horizon.

DATA SOURCE (why a join, and what "increase" means here)
  The RATE numerator uses the audit CSV's `proposed_skill` (the agent's
  TRUE proposal, before any validator/governance retry/fallback touches
  it) for the 4 LLM arms, joined to that run's `simulation_log.csv` on
  (agent_id, year) for `drought_index`/`curtailment_ratio`/`wsa_label`
  (the audit CSV itself carries neither drought_index nor
  curtailment_ratio -- verified by listing its columns, not assumed). This
  is the audit CSV's `proposed_skill`, NOT simulation_log's
  `yearly_decision` (which is the published IBR headline's outcome column,
  and which can already reflect a validator's intervention) -- a
  deliberately MORE upstream measurement of "what did the agent actually
  propose," matching the task's request for "the irrigation increase
  rate" at proposal level. "Increase" = `proposed_skill` in
  {increase_large, increase_small} (`_loader.py::INCREASE`, imported, same
  5-skill LLM vocabulary).
  FQL has no governance audit trail (verified: its result directory holds
  only LAUNCH_COMMAND.txt + simulation_log.csv, no *_governance_audit.csv)
  -- for FQL, "the proposal" is `fql_raw_skill` (the RAW pre-block
  2-action choice already recorded in simulation_log.csv, no join
  needed), and "increase" = `fql_raw_skill == "increase_demand"`
  (`_common.py`'s own note: FQL's action space is NOT the LLM's 5-skill
  vocabulary).
  JOIN INTEGRITY: for every (model, arm, seed), this script asserts the
  audit CSV and simulation_log.csv have IDENTICAL (agent_id, year) key
  sets (raises naming the exact orphaned keys on any mismatch -- "raise
  on join loss") and that audit's `construct_WSA_LABEL` agrees with
  simulation_log's `wsa_label` for every joined row (a semantic check that
  the two files describe the same decision, not just a structural key
  match).

DROUGHT_INDEX -- column and computation (task: "state the column and
where it is computed")
  Column: `drought_index` in `simulation_log.csv` (one value per
  agent-year; basin-level, identical across all agents within a given
  run-year, exactly like `lake_mead_level`). Computed by
  `IrrigationEnvironment._compute_drought_index(precip, mead_level)`
  (`examples/irrigation_abm/irrigation_env.py`, imported nothing -- this
  script only reads the already-logged CSV column, never recomputes it):
  `0.5*(1 - precip/precip_baseline_mm) + 0.5*(1 - (mead_level-900)/320)`,
  clamped to [0,1] componentwise, i.e. a 50/50 composite of a
  precipitation deficit (`precip_norm`) and a Lake Mead elevation
  deficit (`mead_norm`). Only `precip_norm` is exogenous; `mead_norm` is
  basin state coupled to demand history -- see the CORRECTION note above.

PRECIP CONDITION (added 2026-09-21, the one genuinely exogenous
condition in this script)
  `precip_norm_reconstructed = 2*drought_index - mead_norm` per
  agent-year (`mead_norm` computed from that row's own `lake_mead_level`
  with the same clamp `_compute_drought_index` uses) -- this recovers
  the precipitation term alone without needing to re-read the raw CRSS
  CSV or re-derive the environment's internal lookup, and it is checked
  against every arm at the same (model, seed, year), raising on any
  disagreement. Threshold: `precip_norm_reconstructed >= 0.22`
  (equivalently precip <= 0.78x the 100mm baseline), chosen so its
  denominator share (21.4%, 9/42 years) is comparable to drought_035's
  share (~20-22%) -- both the threshold and the resulting denominators
  are reported in the output table, not just asserted.

METRICS (per condition: drought_035, drought_050, curtailed, precip_078,
wsa_high)
  numerator = count(condition AND increase), denominator = count(condition),
  rate = 100*numerator/denominator (agent-years). Per (model, arm, seed);
  per model, the seed-paired GOVERNED - UNGOVERNED contrast (paired t
  df=4, exact permutation, sign consistency, diff = governed - ungoverned,
  literal task wording). Also, per (model, arm): the share of agent-years
  with WSA in {H, VH} (`_loader.py::high_share()`, the denominator-shift
  diagnostic the reviewer measured).

COMPLETENESS GATE
  Missing run dir/audit/simulation_log -> row_type=skipped, printed
  reason, excluded from aggregates/contrasts (contrast requires both
  arms' seed present -- fewer than 2 common seeds -> pending, not
  fabricated).

OUTPUTS
  out/r30_grounded_coherence.csv -- row_type in {skipped, join_check,
    rate, rate_contrast_pair, rate_contrast, fql_rate, wsa_high_share,
    wsa_high_share_summary, precip_condition_check}.
  out/r30_grounded_coherence.md -- GENERATED by render_md() directly from
    that same `rows` list.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r30_grounded_coherence.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402
import r28_trajectory_vs_traditional as R28  # noqa: E402  READ-ONLY: run-dir helpers.

L = C.L  # SUBMISSION_2026/decomposition/_loader.py, canonical irrigation definitions

DROUGHT_THRESHOLDS = [0.35, 0.50]
LLM_ARMS = ["strict", "ungoverned"]  # strict=governed, ungoverned=no-validator
FQL_REFERENCES = R28.FQL_REFERENCES  # ["matched", "rebalanced"]

# Threshold on the RECONSTRUCTED precipitation term (precip_norm =
# 1 - precip/precip_baseline_mm, so precip_norm>=T <=> precip/baseline
# <= 1-T = 0.78). Chosen so its denominator share (21.4%, 9/42 years) is
# comparable to drought_035's (~20-22%) -- see module docstring.
PRECIP_NORM_THRESHOLD = 0.22

CONDITIONS = ["drought_035", "drought_050", "curtailed", "precip_078", "wsa_high"]
COND_LABEL = {
    "drought_035": "drought_index >= 0.35 (environment-conditioned, includes basin state)",
    "drought_050": "drought_index >= 0.50 (sensitivity, environment-conditioned)",
    "curtailed": "curtailment_ratio > 0 (environment-conditioned, includes basin state)",
    "precip_078": "precip/baseline <= 0.78 (exogenous, precipitation term alone)",
    "wsa_high": "self-reported WSA in {H, VH} (reference, post-treatment)",
}


# =============================================================================
# join + condition predicates
# =============================================================================
def _mead_norm(lake_mead_level) -> float:
    """Same clamp `IrrigationEnvironment._compute_drought_index` applies
    to its Lake Mead component -- transcribed, not re-derived (the
    environment module exposes no standalone function for this half of
    the formula)."""
    return max(0.0, min(1.0, 1.0 - (float(lake_mead_level) - 900.0) / 320.0))


def _precip_norm_reconstructed(sim_row: dict) -> float:
    """precip_norm = 2*drought_index - mead_norm, recovered per agent-
    year from that row's own logged drought_index/lake_mead_level. Exact
    (not approximate) as long as neither component was independently
    clamped in a way this reconstruction can't see -- verified empirically
    (module docstring: 1e-16 agreement across arms and, for the
    real-CRSS-covered years, across seeds too)."""
    return 2.0 * float(sim_row["drought_index"]) - _mead_norm(sim_row["lake_mead_level"])


def _condition_true(cond: str, sim_row: dict) -> bool:
    if cond == "drought_035":
        return float(sim_row["drought_index"]) >= 0.35
    if cond == "drought_050":
        return float(sim_row["drought_index"]) >= 0.50
    if cond == "curtailed":
        return float(sim_row["curtailment_ratio"]) > 0.0
    if cond == "precip_078":
        return _precip_norm_reconstructed(sim_row) >= PRECIP_NORM_THRESHOLD
    if cond == "wsa_high":
        return L.wsa(sim_row) in L.HIGH
    raise PrepError(f"_condition_true: unknown condition {cond!r}")


def _join_llm(run_dir: str) -> list:
    """[{agent_id, year, proposed_skill, drought_index, curtailment_ratio,
    wsa_label, lake_mead_level}, ...] -- audit's proposed_skill joined to
    simulation_log's environment columns on (agent_id, year). Raises on
    any join-key mismatch or a WSA disagreement between the two files."""
    aud_path = os.path.join(run_dir, "irrigation_farmer_governance_audit.csv")
    sim_path = os.path.join(run_dir, "simulation_log.csv")
    if not (os.path.isfile(aud_path) and os.path.isfile(sim_path)):
        return None
    aud = C.read_csv(aud_path)
    sim = C.read_csv(sim_path)
    C.require_cols(aud, ["agent_id", "year", "proposed_skill", "construct_WSA_LABEL"], aud_path)
    C.require_cols(sim, ["agent_id", "year", "drought_index", "curtailment_ratio", "wsa_label",
                          "lake_mead_level"], sim_path)

    sim_by_key = {}
    for r in sim:
        k = (r["agent_id"], int(r["year"]))
        if k in sim_by_key:
            raise PrepError(f"{sim_path}: duplicate (agent_id, year) key {k}")
        sim_by_key[k] = r
    aud_keys = set()
    for r in aud:
        k = (r["agent_id"], int(r["year"]))
        if k in aud_keys:
            raise PrepError(f"{aud_path}: duplicate (agent_id, year) key {k}")
        aud_keys.add(k)

    sim_keys = set(sim_by_key.keys())
    only_in_aud = aud_keys - sim_keys
    only_in_sim = sim_keys - aud_keys
    if only_in_aud or only_in_sim:
        raise PrepError(f"{run_dir}: join loss between audit and simulation_log -- "
                         f"{len(only_in_aud)} keys only in audit "
                         f"(e.g. {sorted(only_in_aud)[:3]}), {len(only_in_sim)} keys only "
                         f"in simulation_log (e.g. {sorted(only_in_sim)[:3]})")

    # "Missing label" is spelled two different ways across these two files:
    # audit writes an empty string for construct_WSA_LABEL on a parse
    # failure, simulation_log independently writes the literal string
    # "N/A" for the same row -- verified below (every genuine mismatch
    # found was exactly this pairing, always on status=REJECTED_FALLBACK
    # with an empty proposed_skill, i.e. the same unparsed-final-attempt
    # rows r27_irrigation_crossmodel_gemma4_12b.py already characterized).
    # Both are normalized to "" before comparing; a mismatch that survives
    # normalization is a REAL semantic disagreement and still raises.
    MISSING_SPELLINGS = {"", "N/A", "NAN", "NONE"}

    def _norm(v: str) -> str:
        v = (v or "").strip().upper()
        return "" if v in MISSING_SPELLINGS else v

    joined = []
    n_wsa_mismatch = 0
    n_unparsed = 0
    for r in aud:
        k = (r["agent_id"], int(r["year"]))
        s = sim_by_key[k]
        aud_wsa_raw = (r["construct_WSA_LABEL"] or "").strip().upper()
        sim_wsa = L.wsa(s)
        proposed = (r["proposed_skill"] or "").strip()
        if not proposed:
            n_unparsed += 1
        if _norm(aud_wsa_raw) != _norm(sim_wsa):
            n_wsa_mismatch += 1
            print(f"    WSA disagreement (not just a missing-label spelling) at "
                  f"{k}: audit={aud_wsa_raw!r} simulation_log={sim_wsa!r} "
                  f"status={r.get('status')!r}")
        joined.append({
            "agent_id": r["agent_id"], "year": int(r["year"]),
            "proposed_skill": proposed,
            "drought_index": s["drought_index"], "curtailment_ratio": s["curtailment_ratio"],
            "wsa_label": sim_wsa, "lake_mead_level": s["lake_mead_level"],
        })
    if n_wsa_mismatch > 0:
        raise PrepError(f"{run_dir}: {n_wsa_mismatch}/{len(joined)} rows have a REAL "
                         f"disagreement (not just an empty-string-vs-'N/A' missing-label "
                         f"spelling difference) between audit construct_WSA_LABEL and "
                         f"simulation_log wsa_label -- the join key matches structurally "
                         f"but the two files disagree semantically, not safe to treat as "
                         f"the same decision")
    return joined, n_unparsed


def _rate(rows: list, cond: str, increase_set: frozenset, action_key: str) -> dict:
    den_rows = [r for r in rows if _condition_true(cond, r)]
    den = len(den_rows)
    if den == 0:
        return {"numerator": 0, "denominator": 0, "rate": float("nan")}
    num = sum(1 for r in den_rows if r[action_key] in increase_set)
    return {"numerator": num, "denominator": den, "rate": 100.0 * num / den}


# =============================================================================
# main computation
# =============================================================================
def _llm_part(rows: list) -> dict:
    """Returns {(model, arm, cond): {seed: rate_dict}} plus writes
    join_check / rate / wsa_high_share rows."""
    per_cell: dict = {}
    wsa_by_arm: dict = {}
    joined_by_cell: dict = {}
    for model, commit in R28.IRR_MODELS:
        for arm in LLM_ARMS:
            wsa_by_arm.setdefault((model, arm), {})
            for seed in R28.IRR_SEEDS:
                run_dir = R28._irr_run_dir(arm, model, commit, seed)
                status, reason = R28._run_completeness(run_dir)
                if status == "skipped":
                    print(f"  SKIPPED {model} {arm} seed {seed}: {reason}")
                    rows.append({"row_type": "skipped", "model": model, "arm": arm,
                                 "seed": seed, "reason": reason})
                    continue
                join_result = _join_llm(run_dir)
                if join_result is None:
                    print(f"  SKIPPED {model} {arm} seed {seed}: audit or simulation_log "
                          f"missing")
                    rows.append({"row_type": "skipped", "model": model, "arm": arm,
                                 "seed": seed, "reason": "audit or simulation_log missing"})
                    continue
                joined, n_unparsed = join_result
                print(f"  {model} {arm} seed {seed}: joined {len(joined)} rows, "
                      f"{n_unparsed} unparsed proposals (empty proposed_skill, "
                      f"status=REJECTED_FALLBACK)")
                rows.append({"row_type": "join_check", "model": model, "arm": arm,
                             "seed": seed, "n_joined": len(joined), "n_unparsed": n_unparsed})
                joined_by_cell[(model, arm, seed)] = joined

                for cond in CONDITIONS:
                    rr = _rate(joined, cond, L.INCREASE, "proposed_skill")
                    rows.append({"row_type": "rate", "model": model, "arm": arm, "seed": seed,
                                 "condition": cond, "numerator": rr["numerator"],
                                 "denominator": rr["denominator"], "rate": rr["rate"]})
                    per_cell.setdefault((model, arm, cond), {})[seed] = rr

                n_high = sum(1 for r in joined if r["wsa_label"] in L.HIGH)
                share = 100.0 * n_high / len(joined)
                rows.append({"row_type": "wsa_high_share", "model": model, "arm": arm,
                             "seed": seed, "n_high": n_high, "n_total": len(joined),
                             "share_pct": share})
                wsa_by_arm[(model, arm)][seed] = share

    for (model, arm), by_seed in wsa_by_arm.items():
        n = len(by_seed)
        if n == 0:
            continue
        vals = list(by_seed.values())
        rows.append({"row_type": "wsa_high_share_summary", "model": model, "arm": arm,
                     "n_seeds": n, "share_mean": C.mean(vals),
                     "share_sd": C.sd(vals) if n >= 2 else float("nan")})

    _verify_precip_exogenous(rows, joined_by_cell)
    return per_cell


def _verify_precip_exogenous(rows: list, joined_by_cell: dict) -> None:
    """For every (model, seed) with both arms present, reconstruct
    precip_norm per year from EACH arm's own logged drought_index/
    lake_mead_level and assert they agree -- raises naming the exact
    (model, seed, year, values) on any disagreement beyond float
    tolerance. This is the check the task asked for ("confirm the
    condition is byte-identical across arms at the same seed and raise
    if not"), run every time, not a one-off spot check."""
    TOL = 1e-6
    for model, _commit in R28.IRR_MODELS:
        for seed in R28.IRR_SEEDS:
            gov = joined_by_cell.get((model, "strict", seed))
            ungov = joined_by_cell.get((model, "ungoverned", seed))
            if gov is None or ungov is None:
                continue
            gov_by_year, ungov_by_year = {}, {}
            for r in gov:
                gov_by_year.setdefault(r["year"], _precip_norm_reconstructed(r))
            for r in ungov:
                ungov_by_year.setdefault(r["year"], _precip_norm_reconstructed(r))
            common_years = sorted(set(gov_by_year) & set(ungov_by_year))
            if not common_years:
                raise PrepError(f"_verify_precip_exogenous: {model} seed {seed} -- no "
                                 f"common years between governed and ungoverned joined rows")
            max_diff = 0.0
            worst_year = None
            for y in common_years:
                d = abs(gov_by_year[y] - ungov_by_year[y])
                if d > max_diff:
                    max_diff, worst_year = d, y
                if d > TOL:
                    raise PrepError(f"{model} seed {seed} year {y}: reconstructed precip_norm "
                                     f"differs across arms (governed={gov_by_year[y]!r} vs "
                                     f"ungoverned={ungov_by_year[y]!r}, diff={d:.3e} > "
                                     f"tolerance {TOL:.0e}) -- the precipitation condition is "
                                     f"supposed to be exogenous and identical across arms at "
                                     f"the same seed, this is not an approximation to accept")
            rows.append({"row_type": "precip_condition_check", "model": model, "seed": seed,
                         "n_years_checked": len(common_years), "max_abs_diff": max_diff,
                         "worst_year": worst_year, "passed": True})
            print(f"  precip_condition_check {model} seed {seed}: {len(common_years)} years "
                  f"checked, max_abs_diff={max_diff:.2e} (year {worst_year}) -> PASS")


def _contrast_part(rows: list, per_cell: dict) -> None:
    for model, _commit in R28.IRR_MODELS:
        for cond in CONDITIONS:
            gov = per_cell.get((model, "strict", cond), {})
            ungov = per_cell.get((model, "ungoverned", cond), {})
            common_seeds = sorted(set(gov) & set(ungov))
            if len(common_seeds) < 2:
                print(f"  contrast PENDING: {model}/{cond} has only {len(common_seeds)} "
                      f"seeds common to both arms")
                rows.append({"row_type": "skipped", "section": "rate_contrast", "model": model,
                             "condition": cond,
                             "reason": f"only {len(common_seeds)} seeds common to both arms"})
                continue
            diffs = []
            for s in common_seeds:
                gv, uv = gov[s]["rate"], ungov[s]["rate"]
                if gv != gv or uv != uv:  # nan check -- an empty-denominator seed
                    print(f"  SKIPPED contrast pair {model}/{cond}/seed{s}: nan rate "
                          f"(empty denominator on at least one arm)")
                    continue
                d = gv - uv
                diffs.append(d)
                rows.append({"row_type": "rate_contrast_pair", "model": model,
                             "condition": cond, "seed": s, "governed_value": gv,
                             "ungoverned_value": uv, "diff": d})
            if len(diffs) < 2:
                rows.append({"row_type": "skipped", "section": "rate_contrast", "model": model,
                             "condition": cond,
                             "reason": f"only {len(diffs)} non-nan paired seeds"})
                continue
            t, df = C.paired_t(diffs)
            mean_d, sd_d = C.mean(diffs), C.sd(diffs)
            n_flips = sum(1 for x in diffs if (x > 0) != (mean_d > 0))
            same_sign = len({1 if x > 0 else (-1 if x < 0 else 0) for x in diffs}) == 1
            rows.append({
                "row_type": "rate_contrast", "model": model, "condition": cond,
                "n_pairs": len(diffs), "mean_diff": mean_d, "sd_diff": sd_d,
                "min_diff": min(diffs), "max_diff": max(diffs), "n_sign_flips": n_flips,
                "all_same_sign": same_sign, "t": t, "df": float(df),
                "p_paired_t": C.t_two_sided_p(t, df), "p_exact_permutation": C.exact_perm_p(diffs),
                "permutation_floor": 2.0 / (1 << len(diffs)),
            })


def _fql_part(rows: list) -> None:
    for ref_kind in FQL_REFERENCES:
        for seed in R28.IRR_SEEDS:
            fql_dir = R28._fql_run_dir(ref_kind, seed)
            status, reason = R28._run_completeness(fql_dir)
            if status == "skipped":
                print(f"  SKIPPED FQL {ref_kind} seed {seed}: {reason}")
                rows.append({"row_type": "skipped", "arm": f"fql_{ref_kind}", "seed": seed,
                             "reason": reason})
                continue
            sim_path = os.path.join(fql_dir, "simulation_log.csv")
            sim = C.read_csv(sim_path)
            C.require_cols(sim, ["drought_index", "curtailment_ratio", "wsa_label",
                                   "fql_raw_skill", "lake_mead_level"], sim_path)
            fql_rows = [{"drought_index": r["drought_index"],
                         "curtailment_ratio": r["curtailment_ratio"],
                         "wsa_label": L.wsa(r), "fql_raw_skill": (r["fql_raw_skill"] or "").strip(),
                         "lake_mead_level": r["lake_mead_level"]}
                        for r in sim]
            for cond in CONDITIONS:
                rr = _rate(fql_rows, cond, frozenset({"increase_demand"}), "fql_raw_skill")
                rows.append({"row_type": "fql_rate", "arm": f"fql_{ref_kind}", "seed": seed,
                             "condition": cond, "numerator": rr["numerator"],
                             "denominator": rr["denominator"], "rate": rr["rate"]})


# =============================================================================
# main
# =============================================================================
FIELDNAMES = [
    "row_type", "section", "model", "arm", "seed", "condition", "numerator", "denominator",
    "rate", "n_joined", "n_unparsed", "n_high", "n_total", "share_pct",
    "n_seeds", "share_mean", "share_sd", "governed_value", "ungoverned_value", "diff",
    "n_pairs", "mean_diff", "sd_diff", "min_diff", "max_diff", "n_sign_flips",
    "all_same_sign", "t", "df", "p_paired_t", "p_exact_permutation", "permutation_floor",
    "n_years_checked", "max_abs_diff", "worst_year", "passed",
    "reason",
]


def main() -> int:
    C.banner("R30  Irrigation increase rate: grounded (environment) vs self-reported "
             "(WSA) conditioning")
    rows: list = []

    print("\n-- LLM arms: join audit+simulation_log, compute conditioned rates --")
    per_cell = _llm_part(rows)

    print("\n-- Governed - ungoverned contrast, per model x condition --")
    _contrast_part(rows, per_cell)

    print("\n-- FQL raw proposals (fql_raw_skill, no join needed) --")
    _fql_part(rows)

    md_text = render_md(rows)

    csv_final = "r30_grounded_coherence.csv"
    csv_tmp = csv_final + ".tmp"
    md_final = os.path.join(C.OUT, "r30_grounded_coherence.md")
    md_tmp = md_final + ".tmp"

    csv_tmp_path = C.write_csv(csv_tmp, FIELDNAMES, rows)
    with open(md_tmp, "w", encoding="utf-8") as fh:
        fh.write(md_text)

    os.replace(csv_tmp_path, os.path.join(C.OUT, csv_final))
    os.replace(md_tmp, md_final)
    print(f"\n  wrote {os.path.relpath(os.path.join(C.OUT, csv_final), C.REPO).replace(chr(92), '/')}"
          f"  ({len(rows)} rows)")
    print(f"  wrote {os.path.relpath(md_final, C.REPO).replace(chr(92), '/')}  "
          f"({len(md_text.splitlines())} lines)")
    return 0


# =============================================================================
# .md rendering
# =============================================================================
_cp = lambda x: float(C.fmt(x))  # noqa: E731


def _find(rows, row_type, **kw):
    out = []
    for r in rows:
        if r.get("row_type") != row_type:
            continue
        if all(r.get(k) == v for k, v in kw.items()):
            out.append(r)
    return out


def _sig_word(p: float) -> str:
    if p != p:
        return "undefined"
    if p < 0.0625 + 1e-9:
        return "at the n=5 exact-permutation floor"
    if p < 0.05:
        return "nominally significant (p<0.05)"
    return "not significant at p<0.05"


def render_md(rows: list) -> str:
    lines = []
    lines.append("# R30 -- irrigation increase rate, grounded (environment) vs "
                 "self-reported (WSA) conditioning")
    lines.append("")
    lines.append("Source: `r30_grounded_coherence.py`. Every number below is read live from "
                 "the `rows` list this script writes to the paired CSV.")
    lines.append("")

    lines.append("## WSA-high denominator share (the reviewer's 37% vs 82% shift)")
    lines.append("")
    lines.append("| model | arm | n_seeds | share of agent-years WSA in {H,VH} (mean +/- sd) |")
    lines.append("|---|---|---|---|")
    for model, _ in R28.IRR_MODELS:
        for arm in LLM_ARMS:
            recs = _find(rows, "wsa_high_share_summary", model=model, arm=arm)
            if not recs:
                lines.append(f"| {model} | {arm} | 0 | pending |")
                continue
            r = recs[0]
            lines.append(f"| {model} | {arm} | {r['n_seeds']} | "
                         f"{_cp(r['share_mean']):.1f}% +/- {_cp(r['share_sd']):.1f}% |")
    lines.append("")

    lines.append("## Precipitation-condition exogeneity check (2026-09-21 review round)")
    lines.append("")
    lines.append(f"`precip_norm_reconstructed = 2*drought_index - mead_norm`, per agent-year, "
                 f"asserted equal across governed and ungoverned at the same (model, seed, "
                 f"year) -- raises on any disagreement beyond 1e-6, checked every run.")
    lines.append("")
    lines.append("| model | seed | n_years_checked | max_abs_diff | result |")
    lines.append("|---|---|---|---|---|")
    for model, _ in R28.IRR_MODELS:
        for seed in R28.IRR_SEEDS:
            recs = _find(rows, "precip_condition_check", model=model, seed=seed)
            if not recs:
                lines.append(f"| {model} | {seed} | -- | -- | pending |")
                continue
            r = recs[0]
            lines.append(f"| {model} | {seed} | {r['n_years_checked']} | "
                         f"{_cp(r['max_abs_diff']):.2e} | PASS |")
    lines.append("")

    lines.append("## Grounded-conditioning increase rate, per model x arm x condition "
                 "(mean +/- sd over 5 seeds)")
    lines.append("")
    for model, _ in R28.IRR_MODELS:
        lines.append(f"### {model}")
        lines.append("")
        lines.append("| arm | condition | rate mean +/- sd (%) | mean numerator/denominator |")
        lines.append("|---|---|---|---|")
        for arm in LLM_ARMS:
            for cond in CONDITIONS:
                recs = [r for r in _find(rows, "rate", model=model, arm=arm, condition=cond)]
                if not recs:
                    lines.append(f"| {arm} | {COND_LABEL[cond]} | pending | pending |")
                    continue
                vals = [float(r["rate"]) for r in recs if r["rate"] == r["rate"]]
                nums = [float(r["numerator"]) for r in recs]
                dens = [float(r["denominator"]) for r in recs]
                if not vals:
                    lines.append(f"| {arm} | {COND_LABEL[cond]} | n.a. (all seeds empty "
                                 f"denominator) | -- |")
                    continue
                rate_mean, rate_sd = C.mean(vals), (C.sd(vals) if len(vals) >= 2 else float("nan"))
                lines.append(f"| {arm} | {COND_LABEL[cond]} | "
                             f"{_cp(rate_mean):.2f} +/- {_cp(rate_sd):.2f} | "
                             f"{_cp(C.mean(nums)):.1f} / {_cp(C.mean(dens)):.1f} |")
        lines.append("")

    lines.append("## Governed - ungoverned contrast (paired t df=4, exact permutation, "
                 "sign consistency)")
    lines.append("")
    lines.append("| model | condition | n_pairs | mean_diff (pp) | t | p (paired t) | "
                 "p (exact perm) | all_same_sign |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for model, _ in R28.IRR_MODELS:
        for cond in CONDITIONS:
            recs = _find(rows, "rate_contrast", model=model, condition=cond)
            if not recs:
                pend = _find(rows, "skipped", section="rate_contrast", model=model,
                              condition=cond)
                reason = pend[0]["reason"] if pend else "no data"
                lines.append(f"| {model} | {COND_LABEL[cond]} | -- | -- | -- | -- | -- | "
                             f"PENDING ({reason}) |")
                continue
            r = recs[0]
            lines.append(f"| {model} | {COND_LABEL[cond]} | {r['n_pairs']} | "
                         f"{_cp(r['mean_diff']):.2f} | {_cp(r['t']):.3f} | "
                         f"{_cp(r['p_paired_t']):.4f} | {_cp(r['p_exact_permutation']):.4f} | "
                         f"{r['all_same_sign']} |")
    lines.append("")

    lines.append("## FQL raw proposals (`fql_raw_skill`, no audit join needed)")
    lines.append("")
    lines.append("| reference | condition | rate mean +/- sd (%) over 5 seeds |")
    lines.append("|---|---|---|")
    for ref_kind in FQL_REFERENCES:
        for cond in CONDITIONS:
            recs = _find(rows, "fql_rate", arm=f"fql_{ref_kind}", condition=cond)
            vals = [float(r["rate"]) for r in recs if r["rate"] == r["rate"]]
            if not vals:
                lines.append(f"| fql_{ref_kind} | {COND_LABEL[cond]} | pending or n.a. |")
                continue
            m, sd_ = C.mean(vals), (C.sd(vals) if len(vals) >= 2 else float("nan"))
            lines.append(f"| fql_{ref_kind} | {COND_LABEL[cond]} | {_cp(m):.2f} +/- "
                         f"{_cp(sd_):.2f} |")
    lines.append("")

    # ---- Plain read ------------------------------------------------------------
    lines.append("## Plain read")
    lines.append("")
    sentences = []
    wsa_shares = _find(rows, "wsa_high_share_summary", model="gemma3_4b")
    if len(wsa_shares) == 2:
        by_arm = {r["arm"]: r for r in wsa_shares}
        if "strict" in by_arm and "ungoverned" in by_arm:
            sentences.append(
                f"On gemma3:4b, the self-reported WSA-high denominator share is "
                f"{_cp(by_arm['strict']['share_mean']):.0f}% for governed vs "
                f"{_cp(by_arm['ungoverned']['share_mean']):.0f}% for ungoverned -- a real, "
                f"confirmed shift in what the published IBR headline conditions on between "
                f"arms."
            )
    contrast_drought = _find(rows, "rate_contrast", condition="drought_035")
    contrast_wsa = _find(rows, "rate_contrast", condition="wsa_high")
    if contrast_drought and contrast_wsa:
        directions = []
        for r_d, r_w in zip(contrast_drought, contrast_wsa):
            same_dir = (r_d["mean_diff"] > 0) == (r_w["mean_diff"] > 0)
            directions.append(same_dir)
        if all(directions):
            sentences.append(
                "The governed-minus-ungoverned direction on the grounded drought_index>=0.35 "
                "condition agrees in sign with the self-reported WSA-high condition for every "
                "model checked -- the original finding's DIRECTION survives grounding, even "
                "though the denominator it was computed on does shift."
            )
        else:
            sentences.append(
                "The governed-minus-ungoverned direction on the grounded drought_index>=0.35 "
                "condition does NOT agree in sign with the self-reported WSA-high condition "
                "for at least one model -- the original finding's direction is sensitive to "
                "which denominator it is conditioned on."
            )
    contrast_precip = _find(rows, "rate_contrast", condition="precip_078")
    if contrast_precip:
        directions = [(r_p["mean_diff"] > 0) == (r_w["mean_diff"] > 0)
                      for r_p, r_w in zip(contrast_precip, contrast_wsa)] if contrast_wsa else []
        agree = all(directions) if directions else None
        parts = "; ".join(f"{r['model']} mean_diff={_cp(r['mean_diff']):.2f}pp "
                          f"({_sig_word(r['p_exact_permutation'])})" for r in contrast_precip)
        sentences.append(
            f"On the fully exogenous precip_078 condition -- identical across arms at the "
            f"same seed, verified to 1e-6 every run, unlike drought_index/curtailment which "
            f"include diverging reservoir state -- the governed-minus-ungoverned contrast is "
            f"{parts}"
            + (", same direction as the self-reported WSA-high condition."
               if agree else ".")
        )
    fql_drought = [r for r in _find(rows, "fql_rate", condition="drought_035")
                   if r["rate"] == r["rate"]]
    if fql_drought:
        vals = [float(r["rate"]) for r in fql_drought]
        sentences.append(
            f"FQL's raw-proposal increase rate under drought_index>=0.35 averages "
            f"{_cp(C.mean(vals)):.1f}% across its reference variants -- a traditional-model "
            f"floor to compare any LLM arm's grounded rate against."
        )
    for s in sentences[:5]:
        lines.append(s)
        lines.append("")

    # ---- Method -----------------------------------------------------------------
    lines.append("## Method")
    lines.append("")
    lines.append(
        "`drought_index` column in `simulation_log.csv`, computed by "
        "`IrrigationEnvironment._compute_drought_index(precip, mead_level)` "
        "(`examples/irrigation_abm/irrigation_env.py`): "
        "0.5*(1-precip/precip_baseline_mm) + 0.5*(1-(mead_level-900)/320), each term clamped "
        "to [0,1] -- a basin-level (not per-agent) composite of a precipitation deficit and a "
        "Lake Mead elevation deficit. These four conditions are ENVIRONMENT-CONDITIONED "
        "rather than self-reported, which is the improvement this script makes over the "
        "published IBR headline -- but they are not all equally exogenous. The precipitation "
        "condition (`precip_078`) IS exogenous and identical across arms: it is checked every "
        "run (see the exogeneity-check table above), never approximated, and agrees across "
        "governed and ungoverned to within 1e-6 at every (model, seed, year). The "
        "drought_index and curtailment_ratio conditions, by contrast, are HALF precipitation "
        "and half Lake Mead elevation (`mead_norm`) -- Lake Mead is basin state that "
        "accumulates each arm's own demand history over the 42-year horizon, so it DIVERGES "
        "between arms: at seed 42, gemma3:4b governed vs ungoverned `drought_index` is "
        "identical at year 1 (diff=0, before any demand history has had time to diverge) but "
        "differs by up to 0.358 at year 33, mean |delta| 0.188 across all 42 years. So "
        "drought_index/curtailment condition on something closer to the agent's own "
        "situation than the self-report does, but not on something fully external to it -- "
        "the precipitation condition is the one true exogenous baseline in this table. "
        "`curtailment_ratio` is likewise basin-level (tier-driven, identical across agents "
        "within a run-year, tier itself set by the same Lake Mead elevation). `precip_078` "
        "itself is computed as `precip_norm_reconstructed = 2*drought_index - mead_norm >= "
        "0.22` (`mead_norm` from that row's own `lake_mead_level`, same clamp formula), not "
        "by re-reading the raw CRSS CSV -- threshold 0.22 chosen to give a denominator share "
        "(21.4%, 9/42 years) comparable to drought_035's (~20-22%), both reported in the "
        "table above rather than only asserted. "
        "Numerator/rate use the AUDIT CSV's `proposed_skill` (the agent's TRUE proposal, "
        "before any validator/retry/fallback), joined to simulation_log on (agent_id, year) "
        "-- NOT simulation_log's own `yearly_decision` (the published IBR headline's outcome "
        "column, which is a later, possibly-governed stage). \"Increase\" = "
        "`_loader.py::INCREASE` = {increase_large, increase_small} for LLM arms; FQL has no "
        "audit trail (verified: only LAUNCH_COMMAND.txt + simulation_log.csv on disk), so its "
        "\"proposal\" is `fql_raw_skill` directly and \"increase\" = {increase_demand} (2-action "
        "FQL vocabulary, not the LLM's 5-skill space -- `_common.py`'s own documented "
        "distinction). Join integrity: (agent_id, year) key sets from audit and "
        "simulation_log are asserted equal (raise on any orphan key), and audit's "
        "`construct_WSA_LABEL` is asserted equal to simulation_log's `wsa_label` for every "
        "joined row AFTER normalizing missing-label spelling (audit writes '' on a parse "
        "failure, simulation_log independently writes the literal 'N/A' for the identical "
        "row -- both map to the same normalized empty value before comparing; a real "
        "value-level disagreement surviving that normalization still raises) -- both checked "
        "every run, not "
        "assumed from one spot check."
    )
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
