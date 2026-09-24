# R28 -- LLM arms vs traditional-ABM trajectory, and does the validator matter

Source: `r28_trajectory_vs_traditional.py`. Every number below is read live from the `rows` list this script writes to the paired CSV -- nothing here is hand-typed.

> **Flood corpus: defaults.** sampling: none sent, modelfile defaults temperature 1 / top_p 0.95 / top_k 64. Part 1 (irrigation) is UNCHANGED (always v08). Part 2's `FIG3.GOV_DIR`/`FIG3.DISABLED_DIR` are monkey-patched at runtime to the defaults strict/disabled dirs (never faf1bb12); `FIG3.RULEBASED_DIR` is unchanged (deterministic, no defaults variant).

## Part 1 -- irrigation: per-arm KGE / RMSE vs FQL baseline

### Series: `mead_elevation` (unit: ft)

| model | arm | reference | n_seeds | r_mean | beta_mean | alpha_mean | KGE mean +- sd | RMSE mean +- sd |
|---|---|---|---|---|---|---|---|---|
| gemma3_4b | strict | matched | 5 | 0.9890 | 0.9976 | 1.0519 | 0.9456 +- 0.0080 | 7.77 +- 4.93 |
| gemma3_4b | strict | rebalanced | 5 | 0.9931 | 0.9989 | 1.0415 | 0.9574 +- 0.0232 | 6.62 +- 3.91 |
| gemma3_4b | ungoverned | matched | 5 | 0.4991 | 0.9021 | 1.5040 | 0.2823 +- 0.1332 | 119.56 +- 13.03 |
| gemma3_4b | ungoverned | rebalanced | 5 | 0.5271 | 0.9032 | 1.4894 | 0.3125 +- 0.1347 | 117.77 +- 11.92 |
| gemma4_12b | strict | matched | 5 | 0.9800 | 0.9995 | 1.0517 | 0.9442 +- 0.0364 | 9.10 +- 3.83 |
| gemma4_12b | strict | rebalanced | 5 | 0.9865 | 1.0007 | 1.0416 | 0.9546 +- 0.0451 | 7.70 +- 3.52 |
| gemma4_12b | ungoverned | matched | 5 | 0.6642 | 0.9322 | 1.1607 | 0.6096 +- 0.0740 | 82.45 +- 10.54 |
| gemma4_12b | ungoverned | rebalanced | 5 | 0.6841 | 0.9334 | 1.1485 | 0.6317 +- 0.0483 | 80.79 +- 9.05 |

### Series: `basin_demand` (unit: acre-ft)

| model | arm | reference | n_seeds | r_mean | beta_mean | alpha_mean | KGE mean +- sd | RMSE mean +- sd |
|---|---|---|---|---|---|---|---|---|
| gemma3_4b | strict | matched | 5 | 0.3464 | 0.9938 | 0.5899 | 0.1825 +- 0.2094 | 143218.26 +- 20358.04 |
| gemma3_4b | strict | rebalanced | 5 | 0.4596 | 0.9925 | 0.5412 | 0.2553 +- 0.1307 | 152194.29 +- 34868.42 |
| gemma3_4b | ungoverned | matched | 5 | 0.1726 | 1.9203 | 17.9059 | -15.9520 +- 1.4775 | 6024097.37 +- 186296.36 |
| gemma3_4b | ungoverned | rebalanced | 5 | 0.2131 | 1.9176 | 16.7160 | -14.7635 +- 2.1667 | 6013502.23 +- 185013.01 |
| gemma4_12b | strict | matched | 5 | 0.1908 | 0.9985 | 1.6541 | -0.0600 +- 0.3063 | 211267.22 +- 48733.47 |
| gemma4_12b | strict | rebalanced | 5 | 0.3065 | 0.9971 | 1.5599 | 0.0617 +- 0.2355 | 208303.09 +- 34906.58 |
| gemma4_12b | ungoverned | matched | 5 | 0.3430 | 1.5127 | 9.2863 | -7.3301 +- 1.8809 | 3317746.01 +- 720380.02 |
| gemma4_12b | ungoverned | rebalanced | 5 | 0.4301 | 1.5108 | 8.6161 | -6.6557 +- 1.7462 | 3305945.21 +- 729888.52 |

## Part 1 -- irrigation: governed (strict) minus ungoverned contrast

Paired over the seeds common to both arms (n=5 unless a seed was skipped; see `skipped` rows), df = n-1, exact sign-flip permutation (floor 2/32 = 0.0625 at n=5).

| model | series | reference | metric | n_pairs | mean_diff | sd_diff | t | df | p (paired t) | p (exact perm) | all_same_sign |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gemma3_4b | mead_elevation | matched | kge | 5 | 0.6633 | 0.1304 | 11.377 | 4 | 0.0003 | 0.0625 | True |
| gemma3_4b | mead_elevation | matched | rmse | 5 | -111.7846 | 14.1619 | -17.650 | 4 | 0.0001 | 0.0625 | True |
| gemma3_4b | mead_elevation | rebalanced | kge | 5 | 0.6449 | 0.1228 | 11.742 | 4 | 0.0003 | 0.0625 | True |
| gemma3_4b | mead_elevation | rebalanced | rmse | 5 | -111.1477 | 12.0463 | -20.632 | 4 | 0.0000 | 0.0625 | True |
| gemma3_4b | basin_demand | matched | kge | 5 | 16.1345 | 1.3087 | 27.567 | 4 | 0.0000 | 0.0625 | True |
| gemma3_4b | basin_demand | matched | rmse | 5 | -5880879.1109 | 184778.0223 | -71.167 | 4 | 0.0000 | 0.0625 | True |
| gemma3_4b | basin_demand | rebalanced | kge | 5 | 15.0188 | 2.1917 | 15.323 | 4 | 0.0001 | 0.0625 | True |
| gemma3_4b | basin_demand | rebalanced | rmse | 5 | -5861307.9352 | 196407.0114 | -66.730 | 4 | 0.0000 | 0.0625 | True |
| gemma4_12b | mead_elevation | matched | kge | 5 | 0.3346 | 0.0931 | 8.039 | 4 | 0.0013 | 0.0625 | True |
| gemma4_12b | mead_elevation | matched | rmse | 5 | -73.3569 | 11.6880 | -14.034 | 4 | 0.0001 | 0.0625 | True |
| gemma4_12b | mead_elevation | rebalanced | kge | 5 | 0.3229 | 0.0807 | 8.951 | 4 | 0.0009 | 0.0625 | True |
| gemma4_12b | mead_elevation | rebalanced | rmse | 5 | -73.0842 | 11.1899 | -14.604 | 4 | 0.0001 | 0.0625 | True |
| gemma4_12b | basin_demand | matched | kge | 5 | 7.2701 | 1.9810 | 8.206 | 4 | 0.0012 | 0.0625 | True |
| gemma4_12b | basin_demand | matched | rmse | 5 | -3106478.7952 | 749609.3947 | -9.267 | 4 | 0.0008 | 0.0625 | True |
| gemma4_12b | basin_demand | rebalanced | kge | 5 | 6.7174 | 1.7312 | 8.677 | 4 | 0.0010 | 0.0625 | True |
| gemma4_12b | basin_demand | rebalanced | rmse | 5 | -3097642.1193 | 741437.1044 | -9.342 | 4 | 0.0007 | 0.0625 | True |

## Part 1 -- FQL matched vs FQL rebalanced (same-model reference)

How different two runs of the SAME traditional FQL baseline are from each other (rebalanced=sim, matched=ref), at the identical seed and the identical KGE/RMSE definition used for every LLM-vs-FQL row above -- a calibration point for what an LLM arm's KGE against FQL actually means.

| series | n_seeds | r_mean | beta_mean | alpha_mean | KGE mean +- sd | RMSE mean +- sd |
|---|---|---|---|---|---|---|
| mead_elevation | 5 | 0.9964 | 0.9987 | 1.0103 | 0.9823 +- 0.0153 | 3.96 +- 1.23 |
| basin_demand | 5 | 0.3969 | 1.0014 | 1.0868 | 0.3802 +- 0.3298 | 140201.43 +- 43266.26 |

## Part 2 -- flood: protection-state Jensen-Shannon distance (SI diagnostic, not a headline)

Categorical composition over the 5 protection states; KGE does not apply. `gov_vs_rb`/`dis_vs_rb` = each LLM arm's distance to the rule-based baseline; `gov_vs_dis` = governed vs no-validator distance directly (not part of the paired contrast below). The rule-based baseline is NOT relocation-free: it relocates 0.0-0.7% of agent-years across the 5 seeds, but that is far below the governed arm's 13.6% and the no-validator arm's 10.1% mean relocation share (verified at every seed individually, not just on average) -- so part of the JS gap to rule-based below is this relocation-share gap, not a governance difference.

### Relocation share by arm (relocated agent-years / all agent-years)

| arm | n_seeds | share_min % | share_max % | share_mean +- sd % | agents_ever_relocated_mean |
|---|---|---|---|---|---|
| rulebased | 5 | 0.00 | 0.70 | 0.30 +- 0.33 | 0.6 |
| gov | 5 | 11.60 | 15.30 | 13.56 +- 1.67 | 22.6 |
| disabled | 5 | 6.00 | 15.00 | 10.06 +- 3.80 | 17.8 |

| comparison | n_seeds | mean_over_years mean +- sd |
|---|---|---|
| gov_vs_rb | 5 | 0.4480 +- 0.0464 |
| dis_vs_rb | 5 | 0.4456 +- 0.0416 |
| gov_vs_dis | 5 | 0.1226 +- 0.0315 |

**Paired contrast (governed-to-rulebased minus no-validator-to-rulebased JS distance), n=5:** mean_diff=0.0024, sd_diff=0.0054, t=0.971, df=4, p(paired t)=0.3864, p(exact perm)=0.3750, all_same_sign=False.

## Plain read

Against the primary (matched) FQL reference, LLM-arm KGE against the traditional trajectory ranges from does not reproduce it (gemma3_4b/ungoverned/basin_demand, KGE=-15.95) to closely reproduces it (gemma3_4b/strict/mead_elevation, KGE=0.95).

As a calibration point, two runs of the SAME traditional FQL baseline (rebalanced vs matched cluster split) already disagree with each other at mead_elevation KGE=0.98, basin_demand KGE=0.38 -- an LLM arm's KGE has to be read against that non-zero baseline disagreement, not against a KGE=1 expectation.

On the irrigation KGE contrast across the 8 (model x series x reference) cells, governed (strict) tends to score a HIGHER KGE than ungoverned, with at least one cell reaching the strongest evidence n=5 permits.

For flood (SI only, categorical, KGE not applicable), the governed arm sits farther from the rule-based trajectory than the no-validator arm (JS-distance mean_diff=0.0024, not significant at p<0.05).

The rule-based baseline relocates 0.0-0.7% of agent-years versus 13.6% / 10.1% in the LLM arms, so most of the LLM arms' JS gap to rule-based is structural (relocation share), not governance.

## Method

KGE here is computed against a REFERENCE MODEL (the traditional FQL agent-based baseline), not against field observations -- FQL is itself a simulated policy, so a high KGE means "tracks the traditional ABM's trajectory," not "matches reality." Series and columns: `mead_elevation` from `simulation_log.csv` column `lake_mead_level` (feet; a single basin-level value shared by all agents within a year, aggregated with `first`, verified via a nunique==1 check per year); `basin_demand` from column `request` (acre-feet per agent-year, aggregated with `sum` across all 78 agents per year). Units verified against `examples/irrigation_abm/analysis/fig_wrr_irrigation.py`, which labels these same columns `lake_mead_ft` and `request_af`. Formula: KGE = 1 - sqrt((r-1)^2 + (beta-1)^2 + (alpha-1)^2), with r = Pearson correlation(sim, ref), beta = mean(sim)/mean(ref), alpha = sd(sim)/sd(ref) (ddof=1); sim = LLM arm (or FQL-rebalanced, for the FQL-vs-FQL reference row), ref = FQL (or FQL-matched). RMSE reported in the series' own unit. For flood, `prot_state` is read from `gen_fig3_regen.py::load_all_runs()` (imported read-only, not re-implemented) over the 5 states No protection, Insurance only, Elevation only, Insurance + Elevation, Relocated; Jensen-Shannon distance is base-2 (bounded [0,1] by construction) between two per-year state-share vectors.
