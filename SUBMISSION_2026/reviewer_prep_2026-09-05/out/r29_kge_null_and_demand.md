# R29 -- constant-demand KGE null + basin-demand descriptive stats

Source: `r29_kge_null_and_demand.py`. Every number below is read live from the `rows` list this script writes to the paired CSV.

## Part (a) -- constant-demand null for the Mead-elevation KGE

### Replay-fidelity validation (replay ACTUAL history vs the source's own recorded Lake Mead trajectory; must pass before any null KGE is trusted)

| source | seed | rmse (ft) | max abs (ft) | status |
|---|---|---|---|---|
| fql_matched | 42 | 0.0000 | 0.0000 | PASS |
| fql_matched | 43 | 0.0000 | 0.0000 | PASS |
| fql_matched | 44 | 0.0000 | 0.0000 | PASS |
| fql_matched | 45 | 0.0000 | 0.0000 | PASS |
| fql_matched | 46 | 0.0000 | 0.0000 | PASS |
| governed | 42 | 0.0000 | 0.0000 | PASS |
| governed | 43 | 0.0000 | 0.0000 | PASS |
| governed | 44 | 0.0000 | 0.0000 | PASS |
| governed | 45 | 0.0000 | 0.0000 | PASS |
| governed | 46 | 0.0000 | 0.0000 | PASS |

### Null Mead-elevation KGE vs FQL matched (mean +/- sd over validated seeds)

| source | n_seeds | r | beta | alpha | KGE | RMSE (ft) |
|---|---|---|---|---|---|---|
| fql_matched | 5 | 0.9754 +/- 0.0085 | 1.0191 +/- 0.0025 | 1.1239 +/- 0.0106 | 0.8720 +/- 0.0110 | 23.3917 +/- 3.0089 |
| governed | 5 | 0.9887 +/- 0.0029 | 1.0108 +/- 0.0027 | 1.0954 +/- 0.0120 | 0.9033 +/- 0.0116 | 13.9777 +/- 2.6374 |

For comparison, the actual LLM/FQL-rebalanced Mead-elevation KGE against FQL-matched (from r28, not recomputed here): governed(strict)/gemma3:4b KGE=0.9456, ungoverned/gemma3:4b KGE=0.2823 (see out/r28_trajectory_vs_traditional.md for the full table).

## Part (b) -- basin-demand descriptive stats

Ceiling = `DEMAND_CEILING_AF` = 6,000,000 acre-ft/yr, imported from `examples/irrigation_abm/validators/irrigation_validators.py`, not hardcoded.

| arm | n_seeds | demand mean (AF) | demand sd (AF) | min (AF) | max (AF) | % years over ceiling | mean distance to ceiling (AF) |
|---|---|---|---|---|---|---|---|
| irrigation_strict_gemma3_4b | 5 | 6087065 +/- 65646 | 71378 | 5848678 | 6183852 | 86.7% | 87065 |
| irrigation_ungoverned_gemma3_4b | 5 | 11761867 +/- 196654 | 2166889 | 6231770 | 13508008 | 100.0% | 5761867 |
| irrigation_strict_gemma4_12b | 5 | 6115657 +/- 23611 | 201800 | 5621227 | 6322583 | 76.2% | 115657 |
| irrigation_ungoverned_gemma4_12b | 5 | 9265114 +/- 688668 | 1119910 | 6186623 | 10556306 | 100.0% | 3265114 |
| fql_matched | 5 | 6125065 +/- 27348 | 121492 | 5753842 | 6376043 | 89.5% | 125065 |
| fql_rebalanced | 5 | 6133741 +/- 34766 | 131041 | 5753514 | 6420971 | 87.1% | 133741 |

## Part (c) -- basin-demand KGE (carried verbatim from r28, not recomputed)

| model | arm | reference | n_seeds | r | beta | alpha | KGE | RMSE (AF) |
|---|---|---|---|---|---|---|---|---|
| gemma3_4b | strict | matched | 5 | 0.3464 +/- 0.1937 | 0.9938 +/- 0.0135 | 0.5899 +/- 0.3119 | 0.1825 +/- 0.2094 | 143218 +/- 20358 |
| gemma3_4b | strict | rebalanced | 5 | 0.4596 +/- 0.1159 | 0.9925 +/- 0.0154 | 0.5412 +/- 0.2615 | 0.2553 +/- 0.1307 | 152194 +/- 34868 |
| gemma3_4b | ungoverned | matched | 5 | 0.1726 +/- 0.1774 | 1.9203 +/- 0.0299 | 17.9059 +/- 1.4786 | -15.9520 +/- 1.4775 | 6024097 +/- 186296 |
| gemma3_4b | ungoverned | rebalanced | 5 | 0.2131 +/- 0.1495 | 1.9176 +/- 0.0304 | 16.7160 +/- 2.1715 | -14.7635 +/- 2.1667 | 6013502 +/- 185013 |
| gemma4_12b | strict | matched | 5 | 0.1908 +/- 0.2733 | 0.9985 +/- 0.0013 | 1.6541 +/- 0.2651 | -0.0600 +/- 0.3063 | 211267 +/- 48733 |
| gemma4_12b | strict | rebalanced | 5 | 0.3065 +/- 0.0967 | 0.9971 +/- 0.0071 | 1.5599 +/- 0.3919 | 0.0617 +/- 0.2355 | 208303 +/- 34907 |
| gemma4_12b | ungoverned | matched | 5 | 0.3430 +/- 0.2378 | 1.5127 +/- 0.1136 | 9.2863 +/- 1.8736 | -7.3301 +/- 1.8809 | 3317746 +/- 720380 |
| gemma4_12b | ungoverned | rebalanced | 5 | 0.4301 +/- 0.1044 | 1.5108 +/- 0.1161 | 8.6161 +/- 1.7462 | -6.6557 +/- 1.7462 | 3305945 +/- 729889 |

## Plain read

The environment-replay fidelity check passed 10/10 (source, seed) pairs (RMSE <= 0.5 ft vs the source's own recorded Lake Mead trajectory), so the null-KGE numbers below are reported only where this held.

Holding demand at its year-1 level for 42 years (the constant-demand null) yields a Mead-elevation KGE of 0.87 against FQL-matched when seeded from FQL-matched's own year-1 requests, and 0.90 when seeded from governed-LLM's year-1 requests -- context for how much of any arm's real KGE against FQL reflects tracking the DEMAND trajectory specifically, versus just tracking the shared precipitation forcing that drives Mead regardless of demand.

Of the arms compared, irrigation_ungoverned_gemma3_4b spends the most years over the 6,000,000 acre-ft ceiling (100.0% of years).

## Method

Constant-demand null: `examples/irrigation_abm/irrigation_env.py`'s `IrrigationEnvironment` is seeded with the TRUE pre-simulation diversion baseline (`actual_2018_diversion` per agent, via `irrigation_personas.py::create_profiles_from_data()`, the same production function/paths the real runs use -- NOT year-1's already-decided request, which was tried first and produced a provable year-1-onward Mead error, see module docstring) plus static water_right/basin/cluster (read from the source's own year-1 `simulation_log.csv` row, never regenerated), then stepped 42 years via `update_agent_request(agent_id, year1_request)` called every year to hold demand at that source's OWN year-1 recorded request (never `execute_skill()`, which is the only rng-consuming path besides the unused synthetic-precipitation fallback -- see module docstring). Real CRSS winter precipitation is loaded from `ref/CRSS_DB/CRSS_DB/HistoricalData/PrismWinterPrecip_ST_NOAA_Future.csv`, the same file both fql_raw_norebalance_faf1bb12 and strict_42yr_gemma3_4b_faf1bb12 used (both ran with `--real`); only the strict run's LAUNCH_COMMAND.txt carries a SHA256 block for this file (matches the live file's own hash, `3094b4c5...`) -- the FQL run's LAUNCH_COMMAND.txt is 3 lines only (command + timestamps), no hash to check, not claimed otherwise. Fidelity is verified empirically per seed (replay actual history, compare to the source's own recorded lake_mead_level), not assumed. KGE formula and sim/ref convention: identical to r28 (`r28_trajectory_vs_traditional.py::_kge_and_rmse`, imported, not re-derived). Demand ceiling = `DEMAND_CEILING_AF` (`examples/irrigation_abm/validators/irrigation_validators.py`), imported, not hardcoded.
