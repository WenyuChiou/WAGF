# R30 -- irrigation increase rate, grounded (environment) vs self-reported (WSA) conditioning

Source: `r30_grounded_coherence.py`. Every number below is read live from the `rows` list this script writes to the paired CSV.

## WSA-high denominator share (the reviewer's 37% vs 82% shift)

| model | arm | n_seeds | share of agent-years WSA in {H,VH} (mean +/- sd) |
|---|---|---|---|
| gemma3_4b | strict | 5 | 37.1% +/- 3.5% |
| gemma3_4b | ungoverned | 5 | 81.8% +/- 2.0% |
| gemma4_12b | strict | 5 | 27.7% +/- 1.7% |
| gemma4_12b | ungoverned | 5 | 75.9% +/- 3.1% |

## Precipitation-condition exogeneity check (2026-09-21 review round)

`precip_norm_reconstructed = 2*drought_index - mead_norm`, per agent-year, asserted equal across governed and ungoverned at the same (model, seed, year) -- raises on any disagreement beyond 1e-6, checked every run.

| model | seed | n_years_checked | max_abs_diff | result |
|---|---|---|---|---|
| gemma3_4b | 42 | 42 | 0.00e+00 | PASS |
| gemma3_4b | 43 | 42 | 0.00e+00 | PASS |
| gemma3_4b | 44 | 42 | 0.00e+00 | PASS |
| gemma3_4b | 45 | 42 | 0.00e+00 | PASS |
| gemma3_4b | 46 | 42 | 0.00e+00 | PASS |
| gemma4_12b | 42 | 42 | 0.00e+00 | PASS |
| gemma4_12b | 43 | 42 | 0.00e+00 | PASS |
| gemma4_12b | 44 | 42 | 0.00e+00 | PASS |
| gemma4_12b | 45 | 42 | 0.00e+00 | PASS |
| gemma4_12b | 46 | 42 | 0.00e+00 | PASS |

## Grounded-conditioning increase rate, per model x arm x condition (mean +/- sd over 5 seeds)

### gemma3_4b

| arm | condition | rate mean +/- sd (%) | mean numerator/denominator |
|---|---|---|---|
| strict | drought_index >= 0.35 (environment-conditioned, includes basin state) | 39.35 +/- 4.25 | 287.2 / 733.2 |
| strict | drought_index >= 0.50 (sensitivity, environment-conditioned) | 41.15 +/- 6.25 | 49.4 / 124.8 |
| strict | curtailment_ratio > 0 (environment-conditioned, includes basin state) | 41.10 +/- 3.98 | 487.6 / 1185.6 |
| strict | precip/baseline <= 0.78 (exogenous, precipitation term alone) | 42.88 +/- 3.78 | 301.0 / 702.0 |
| strict | self-reported WSA in {H, VH} (reference, post-treatment) | 31.41 +/- 5.47 | 383.0 / 1215.4 |
| ungoverned | drought_index >= 0.35 (environment-conditioned, includes basin state) | 58.41 +/- 1.43 | 1349.2 / 2308.8 |
| ungoverned | drought_index >= 0.50 (sensitivity, environment-conditioned) | 57.13 +/- 1.58 | 588.8 / 1029.6 |
| ungoverned | curtailment_ratio > 0 (environment-conditioned, includes basin state) | 58.96 +/- 1.97 | 1748.6 / 2964.0 |
| ungoverned | precip/baseline <= 0.78 (exogenous, precipitation term alone) | 65.36 +/- 1.90 | 458.8 / 702.0 |
| ungoverned | self-reported WSA in {H, VH} (reference, post-treatment) | 56.64 +/- 2.10 | 1518.0 / 2678.2 |

### gemma4_12b

| arm | condition | rate mean +/- sd (%) | mean numerator/denominator |
|---|---|---|---|
| strict | drought_index >= 0.35 (environment-conditioned, includes basin state) | 2.40 +/- 0.78 | 16.2 / 670.8 |
| strict | drought_index >= 0.50 (sensitivity, environment-conditioned) | 0.00 +/- 0.00 | 0.0 / 109.2 |
| strict | curtailment_ratio > 0 (environment-conditioned, includes basin state) | 3.71 +/- 1.77 | 40.8 / 1092.0 |
| strict | precip/baseline <= 0.78 (exogenous, precipitation term alone) | 2.31 +/- 0.80 | 16.2 / 702.0 |
| strict | self-reported WSA in {H, VH} (reference, post-treatment) | 0.00 +/- 0.00 | 0.0 / 908.0 |
| ungoverned | drought_index >= 0.35 (environment-conditioned, includes basin state) | 12.76 +/- 1.79 | 242.8 / 1903.2 |
| ungoverned | drought_index >= 0.50 (sensitivity, environment-conditioned) | 9.43 +/- 3.89 | 43.6 / 499.2 |
| ungoverned | curtailment_ratio > 0 (environment-conditioned, includes basin state) | 15.51 +/- 1.57 | 440.8 / 2839.2 |
| ungoverned | precip/baseline <= 0.78 (exogenous, precipitation term alone) | 20.43 +/- 2.74 | 143.4 / 702.0 |
| ungoverned | self-reported WSA in {H, VH} (reference, post-treatment) | 11.57 +/- 1.53 | 288.2 / 2485.8 |

## Governed - ungoverned contrast (paired t df=4, exact permutation, sign consistency)

| model | condition | n_pairs | mean_diff (pp) | t | p (paired t) | p (exact perm) | all_same_sign |
|---|---|---|---|---|---|---|---|
| gemma3_4b | drought_index >= 0.35 (environment-conditioned, includes basin state) | 5 | -19.06 | -9.662 | 0.0006 | 0.0625 | True |
| gemma3_4b | drought_index >= 0.50 (sensitivity, environment-conditioned) | 5 | -15.98 | -6.239 | 0.0034 | 0.0625 | True |
| gemma3_4b | curtailment_ratio > 0 (environment-conditioned, includes basin state) | 5 | -17.85 | -7.145 | 0.0020 | 0.0625 | True |
| gemma3_4b | precip/baseline <= 0.78 (exogenous, precipitation term alone) | 5 | -22.48 | -11.747 | 0.0003 | 0.0625 | True |
| gemma3_4b | self-reported WSA in {H, VH} (reference, post-treatment) | 5 | -25.23 | -7.997 | 0.0013 | 0.0625 | True |
| gemma4_12b | drought_index >= 0.35 (environment-conditioned, includes basin state) | 5 | -10.35 | -14.838 | 0.0001 | 0.0625 | True |
| gemma4_12b | drought_index >= 0.50 (sensitivity, environment-conditioned) | 5 | -9.43 | -5.423 | 0.0056 | 0.0625 | True |
| gemma4_12b | curtailment_ratio > 0 (environment-conditioned, includes basin state) | 5 | -11.80 | -17.089 | 0.0001 | 0.0625 | True |
| gemma4_12b | precip/baseline <= 0.78 (exogenous, precipitation term alone) | 5 | -18.12 | -15.784 | 0.0001 | 0.0625 | True |
| gemma4_12b | self-reported WSA in {H, VH} (reference, post-treatment) | 5 | -11.57 | -16.892 | 0.0001 | 0.0625 | True |

## FQL raw proposals (`fql_raw_skill`, no audit join needed)

| reference | condition | rate mean +/- sd (%) over 5 seeds |
|---|---|---|
| fql_matched | drought_index >= 0.35 (environment-conditioned, includes basin state) | 72.22 +/- 1.16 |
| fql_matched | drought_index >= 0.50 (sensitivity, environment-conditioned) | 87.18 +/- 2.56 |
| fql_matched | curtailment_ratio > 0 (environment-conditioned, includes basin state) | 72.56 +/- 1.50 |
| fql_matched | precip/baseline <= 0.78 (exogenous, precipitation term alone) | 67.61 +/- 0.74 |
| fql_matched | self-reported WSA in {H, VH} (reference, post-treatment) | 87.18 +/- 2.56 |
| fql_rebalanced | drought_index >= 0.35 (environment-conditioned, includes basin state) | 71.47 +/- 2.05 |
| fql_rebalanced | drought_index >= 0.50 (sensitivity, environment-conditioned) | 85.13 +/- 5.25 |
| fql_rebalanced | curtailment_ratio > 0 (environment-conditioned, includes basin state) | 72.38 +/- 2.06 |
| fql_rebalanced | precip/baseline <= 0.78 (exogenous, precipitation term alone) | 66.50 +/- 1.03 |
| fql_rebalanced | self-reported WSA in {H, VH} (reference, post-treatment) | 87.18 +/- 2.56 |

## Plain read

On gemma3:4b, the self-reported WSA-high denominator share is 37% for governed vs 82% for ungoverned -- a real, confirmed shift in what the published IBR headline conditions on between arms.

The governed-minus-ungoverned direction on the grounded drought_index>=0.35 condition agrees in sign with the self-reported WSA-high condition for every model checked -- the original finding's DIRECTION survives grounding, even though the denominator it was computed on does shift.

On the fully exogenous precip_078 condition -- identical across arms at the same seed, verified to 1e-6 every run, unlike drought_index/curtailment which include diverging reservoir state -- the governed-minus-ungoverned contrast is gemma3_4b mean_diff=-22.48pp (at the n=5 exact-permutation floor); gemma4_12b mean_diff=-18.12pp (at the n=5 exact-permutation floor), same direction as the self-reported WSA-high condition.

FQL's raw-proposal increase rate under drought_index>=0.35 averages 71.8% across its reference variants -- a traditional-model floor to compare any LLM arm's grounded rate against.

## Method

`drought_index` column in `simulation_log.csv`, computed by `IrrigationEnvironment._compute_drought_index(precip, mead_level)` (`examples/irrigation_abm/irrigation_env.py`): 0.5*(1-precip/precip_baseline_mm) + 0.5*(1-(mead_level-900)/320), each term clamped to [0,1] -- a basin-level (not per-agent) composite of a precipitation deficit and a Lake Mead elevation deficit. These four conditions are ENVIRONMENT-CONDITIONED rather than self-reported, which is the improvement this script makes over the published IBR headline -- but they are not all equally exogenous. The precipitation condition (`precip_078`) IS exogenous and identical across arms: it is checked every run (see the exogeneity-check table above), never approximated, and agrees across governed and ungoverned to within 1e-6 at every (model, seed, year). The drought_index and curtailment_ratio conditions, by contrast, are HALF precipitation and half Lake Mead elevation (`mead_norm`) -- Lake Mead is basin state that accumulates each arm's own demand history over the 42-year horizon, so it DIVERGES between arms: at seed 42, gemma3:4b governed vs ungoverned `drought_index` is identical at year 1 (diff=0, before any demand history has had time to diverge) but differs by up to 0.358 at year 33, mean |delta| 0.188 across all 42 years. So drought_index/curtailment condition on something closer to the agent's own situation than the self-report does, but not on something fully external to it -- the precipitation condition is the one true exogenous baseline in this table. `curtailment_ratio` is likewise basin-level (tier-driven, identical across agents within a run-year, tier itself set by the same Lake Mead elevation). `precip_078` itself is computed as `precip_norm_reconstructed = 2*drought_index - mead_norm >= 0.22` (`mead_norm` from that row's own `lake_mead_level`, same clamp formula), not by re-reading the raw CRSS CSV -- threshold 0.22 chosen to give a denominator share (21.4%, 9/42 years) comparable to drought_035's (~20-22%), both reported in the table above rather than only asserted. Numerator/rate use the AUDIT CSV's `proposed_skill` (the agent's TRUE proposal, before any validator/retry/fallback), joined to simulation_log on (agent_id, year) -- NOT simulation_log's own `yearly_decision` (the published IBR headline's outcome column, which is a later, possibly-governed stage). "Increase" = `_loader.py::INCREASE` = {increase_large, increase_small} for LLM arms; FQL has no audit trail (verified: only LAUNCH_COMMAND.txt + simulation_log.csv on disk), so its "proposal" is `fql_raw_skill` directly and "increase" = {increase_demand} (2-action FQL vocabulary, not the LLM's 5-skill space -- `_common.py`'s own documented distinction). Join integrity: (agent_id, year) key sets from audit and simulation_log are asserted equal (raise on any orphan key), and audit's `construct_WSA_LABEL` is asserted equal to simulation_log's `wsa_label` for every joined row AFTER normalizing missing-label spelling (audit writes '' on a parse failure, simulation_log independently writes the literal 'N/A' for the identical row -- both map to the same normalized empty value before comparing; a real value-level disagreement surviving that normalization still raises) -- both checked every run, not assumed from one spot check.
