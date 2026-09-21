# R31 -- flood relocation sensitivity

Source: `r31_flood_relocation_sensitivity.py`. Every number below is read live from the `rows` list this script writes to the paired CSV. Exclusion rule: an agent-year is dropped iff its normalized action is "relocate" (covers the raw spellings relocate/relocated/already_relocated -- see module docstring for the empirical spot-check confirming this captures every post-relocation year, not just the transition year).

## Part 1 -- IBR headline (uncond, final level), original vs relocate-excluded

| model | arm | version | n_seeds | mean +/- sd (%) | pooled (%) |
|---|---|---|---|---|---|
| gemma3_4b | strict | original | 5 | 0.79 +/- 0.43 | 0.78 |
| gemma3_4b | strict | relocate_excluded | 5 | 0.81 +/- 0.45 | 0.81 |
| gemma3_4b | disabled | original | 5 | 8.91 +/- 0.72 | 8.90 |
| gemma3_4b | disabled | relocate_excluded | 5 | 8.98 +/- 0.63 | 8.96 |
| gemma4_12b | strict | original | 5 | 0.08 +/- 0.11 | 0.08 |
| gemma4_12b | strict | relocate_excluded | 5 | 0.08 +/- 0.11 | 0.08 |
| gemma4_12b | disabled | original | 5 | 2.10 +/- 0.69 | 2.10 |
| gemma4_12b | disabled | relocate_excluded | 5 | 2.10 +/- 0.69 | 2.10 |

### Governed - no-validator contrast, IBR headline (uncond, final), both versions

| model | version | n_pairs | mean_diff (pp) | t | p (paired t) | p (exact perm) | all_same_sign |
|---|---|---|---|---|---|---|---|
| gemma3_4b | original | 5 | -8.12 | -33.476 | 0.0000 | 0.0625 | True |
| gemma3_4b | relocate_excluded | 5 | -8.16 | -35.264 | 0.0000 | 0.0625 | True |
| gemma4_12b | original | 5 | -2.02 | -6.128 | 0.0036 | 0.0625 | True |
| gemma4_12b | relocate_excluded | 5 | -2.02 | -6.126 | 0.0036 | 0.0625 | True |

## Part 2 -- JS distance to rule-based, original vs relocate-excluded

| comparison | version | n_seeds | mean_over_years mean +/- sd |
|---|---|---|---|
| gov_vs_rb | original | 5 | 0.4553 +/- 0.0339 |
| gov_vs_rb | relocate_excluded | 5 | 0.3739 +/- 0.0636 |
| dis_vs_rb | original | 5 | 0.4674 +/- 0.0408 |
| dis_vs_rb | relocate_excluded | 5 | 0.3960 +/- 0.0726 |
| gov_vs_dis | original | 5 | 0.1196 +/- 0.0183 |
| gov_vs_dis | relocate_excluded | 5 | 0.1094 +/- 0.0153 |

### Paired contrast (governed-to-rulebased minus no-validator-to-rulebased JS distance), both versions

| version | n_pairs | mean_diff | t | p (paired t) | p (exact perm) | all_same_sign |
|---|---|---|---|---|---|---|
| original | 5 | -0.0121 | -1.209 | 0.2934 | 0.3125 | False |
| relocate_excluded | 5 | -0.0221 | -2.683 | 0.0551 | 0.0625 | True |

## Part 3a -- relocation share (reused verbatim from r28)

| arm | n_seeds | share_min % | share_max % | share_mean +/- sd % |
|---|---|---|---|---|
| rulebased | 5 | 0.00 | 0.70 | 0.30 +/- 0.33 |
| gov | 5 | 11.50 | 22.20 | 15.72 +/- 4.02 |
| disabled | 5 | 9.50 | 26.60 | 13.82 +/- 7.19 |

## Part 3b -- diversity index (pooled 5-state normalized entropy on `prot_state`, common action set across LLM and rule-based arms)

| arm | version | n_agent_years | diversity_index |
|---|---|---|---|
| gov | original | 5000 | 0.8545 |
| gov | relocate_excluded | 4214 | 0.6932 |
| disabled | original | 5000 | 0.8404 |
| disabled | relocate_excluded | 4309 | 0.6856 |
| rulebased | original | 5000 | 0.7963 |
| rulebased | relocate_excluded | 4985 | 0.7860 |

## Plain read

Excluding relocate-final agent-years does NOT flip the sign of the governed-minus-no-validator IBR-headline contrast for any model checked.

The governed-vs-no-validator JS-distance-to-rulebased contrast moves from mean_diff=-0.0121 (original) to mean_diff=-0.0221 (relocate-excluded), the same sign -- context for how much of the original contrast the relocation-share difference alone was responsible for.

Rule-based relocates 0.30% of agent-years on average vs governed's 15.72% (reused from r28, not recomputed here).

On the common 5-state action set, governed's pooled diversity_index=0.855 vs rule-based's 0.796 (original, both arms) -- the same state space both the IBR and JS analyses above already share.

## Method

Exclusion rule stated once at the top of this document and in the module docstring: normalized action == "relocate" (via `_common.py::flood_normalize_action` for audit rows / `gen_fig3_regen.py::_normalise_decision` for simulation_log rows, both imported, neither re-derived), applied per agent-year. IBR headline = the unconditional, final-level flood IBR (`_common.py::flood_ibr_components`, R1+R3+R4 over total, same definition r23/r24/r25/r26 already use for this column) -- pooled = all 5 seeds' rows concatenated before one ibr_pct calculation, distinct from the mean of 5 per-seed rates (both reported). JS distance = `gen_fig3_regen.py`'s own 5-state `prot_state` classification (imported, not re-derived) with `_js_distance`/`_state_dist` TRANSCRIBED VERBATIM from `r28_trajectory_vs_traditional.py` (r28 is committed, not modified; these are private functions there with no seam for a relocate filter without editing r28 itself). Relocation share is READ, not recomputed, from `out/r28_trajectory_vs_traditional.csv`. diversity_index = `_common.py::normalized_entropy` (k=5) on the POOLED (all years x all seeds) `prot_state` count table per arm -- the same 5-state space rule-based and both LLM arms already share via `gen_fig3_regen.py`'s classification, which is what makes it a common action set across LLM and rule-based arms (as opposed to `_normalise_decision`'s 4-action vocabulary, which rule-based and LLM arms populate at different cardinalities).
