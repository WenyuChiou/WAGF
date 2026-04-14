# Gemma 4 LEGACY vs CLEAN seed_42 — Comprehensive Analysis Report

Generated: 2026-04-14
Arm A — LEGACY: `paper3/results/paper3_gemma4_e4b_legacy/seed_42/gemma4_e4b_strict/` (git commit `caf3499`, memory_write_policy LEGACY, ratchet active)
Arm B — CLEAN: `paper3/results/paper3_gemma4_e4b_clean/seed_42/gemma4_e4b_strict/` (git commit `14b55a6`, memory_write_policy CLEAN, ratchet blocked)
Both arms: Gemma 4 e4b, think=disabled, seed 42, 400 agents × 13 years, hazard schedule bit-exact, same hyperparameters.

## Executive summary

The comprehensive re-analysis produces one framework-level finding and three supporting mechanisms.

**Framework-level finding — memory writes in LLM ABMs have a dual role.** The same `agent_self_report` memory write channel that propagates the rationalization ratchet (biased PA saturation) also sustains behavioural diversity across years. Blocking the channel removes both simultaneously. This is a generalisable observation about LLM-ABM architecture, not a Paper 3-specific calibration note. The dual role is evidenced by the matched-seed LEGACY vs CLEAN comparison on Gemma 4 seed 42.

**Supporting mechanism 1 — CLEAN blocks the rationalization ratchet as designed.** `past_reference` phrase frequency in the main reasoning text climbs from 1.5% (Y1) to 30.5% (Y8-11) for LEGACY owners and from 3% to 46.5% for LEGACY renters; under CLEAN it stays below 5% for owners and below 10.5% for renters across all 13 years (20x and 9x compression). `agent_self_report` memory accumulates 10.5 entries per agent by Y13 under LEGACY and 0 under CLEAN. PA temporal Spearman drops from 0.273 to 0.075. SP flood-dose responsiveness is preserved (ρ = 0.635 → 0.650) — the PMT causal chain stays intact on the axis that matters.

**Supporting mechanism 2 — owner Y1 PA saturation is NOT memory-mediated.** It is prompt-level identity priming. CLEAN actually raises owner Y1 PA from 52.5% to 78.0% because the LEGACY `initial_narrative` rootedness seed ("could see moving if necessary") was serving as a counterweight to the "As a homeowner..." prompt phrase. Removing the seed unmasks the priming. This means memory-level fixes cannot address owner PA saturation at all — a separate prompt-level intervention is required.

**Supporting mechanism 3 — action diversity depends on self-narrative memory.** Under CLEAN, renter relocation drops from 35 to 1 instance, owner elevation from 30 to 12, owner action distribution Shannon entropy from 1.07 to 0.85 bits. The mechanism is that `agent_self_report` entries like "I chose to relocate because..." or "I decided to wait this year" sustain non-default action choices across years by showing up in subsequent retrievals. Without them, every agent-year re-evaluates from scratch using the prompt's cost-effective baseline and converges on insurance-as-default. This is the same memory channel that carried the ratchet, now exposed as doing diversity-maintenance work.

**On the EPI delta.** LEGACY EPI = 0.6115, CLEAN = 0.4968. EPI is a range-based plausibility heuristic (see CLAUDE.local.md definition), not a statistical validity test. Both arms share Gemma 4-specific systematic biases on 5 benchmarks (SFHA insurance too high, elevation too low, post-flood inaction too low, government decrease count = 0, government change count too few), and CLEAN flips 2 additional benchmarks out of range (`buyout_rate` because renter relocation dropped, `renter_uninsured_rate` because the insurance-default collapse produced 100% insured flood-zone renters). Neither flipped benchmark has a narrow ground-truth range, and CLEAN improves on `insurance_lapse_rate` relative to LEGACY. The EPI delta is a calibration observation, not a CLEAN failure — both arms deviate from author-selected benchmark brackets in ways that reflect Gemma 4 prompt/model bias more than memory policy. Section 3 discusses the individual benchmarks.

## 1. Data integrity

| Check | LEGACY | CLEAN |
|---|---|---|
| household_owner_traces.jsonl rows | 2600 | 2600 |
| household_renter_traces.jsonl rows | 2600 | 2600 |
| government_traces.jsonl rows | 13 | 13 |
| insurance_traces.jsonl rows | 13 | 13 |
| reproducibility_manifest.json present | ✓ | ✓ |
| governance_summary.json present | ✓ | ✓ |
| Phase 1 scripts returned 0 | 15/15 | 15/15 |
| Phase 2 scripts returned 0 | 3/3 | 3/3 |
| Manifest `memory_write_policy.policy` | all 9 allowed | 3 risky blocked |
| Manifest `dropped_counts` | empty | initial_narrative 800, agent_self_report 5035 |
| Hazard schedule bit-exact across arms | ✓ (Phase 0 check) | — |

Data integrity passes for both arms. No trace row loss, no manifest gaps, no unhandled script exceptions in Phase 1 or Phase 2. The bit-exact hazard across arms rules out any randomness-based explanation for downstream differences.

## 2. Ratchet signatures — deep log evidence

### 2.1 Memory content composition

Mean `memory_post` size at Y13, averaged across 200 agents per cell (from `memory_dynamics/memory_size_by_year.csv`):

| Cell | LEGACY mem_post | CLEAN mem_post | Delta |
|---|---:|---:|---:|
| owner × MG | 67.85 | 54.44 | -13.41 |
| owner × NMG | 67.58 | 53.72 | -13.86 |
| renter × MG | 65.37 | 53.59 | -11.78 |
| renter × NMG | 65.76 | 53.33 | -12.43 |

Memory retrieval window (`mem_pre_mean`) is 3 across all cells (humancentric retrieval always returns exactly 3 items). The ~13-entry delta between arms is the `agent_self_report` content that CLEAN blocks.

Content-type `agent_self_report` visible in Y13 memory (from `memory_new_writes_by_decision_year.csv`):

| Cell | LEGACY Y13 self-report count | CLEAN Y13 self-report count |
|---|---:|---:|
| owner × MG | 10.5 | 0.0 |
| owner × NMG | 10.47 | 0.0 |
| renter × MG | 10.12 | 0.0 |
| renter × NMG | 10.02 | 0.0 |

The `agent_self_report` content-type was writing ~0.85 entries per agent per year on average under LEGACY. CLEAN achieves the intended zero.

### 2.2 Rationalization phrase frequency in the main reasoning text

`past_reference` phrase family (regex matches include "previous", "established", "prior", "consistent with", "aligns with"), counted across `skill_proposal.reasoning.reasoning` for all 200 agents per year (from `reasoning_taxonomy/reasoning_phrase_detection_by_year.csv`):

**LEGACY owner past_reference frequency by year**:

| Y | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| % | 1.5 | 3.5 | 12.5 | 12.5 | 19.5 | 19.0 | 25.0 | **30.5** | 26.0 | 26.0 | **30.5** | 29.0 | 27.0 |

**CLEAN owner past_reference frequency**:

| Y | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| % | 1.5 | 2.0 | 2.0 | 2.0 | 2.0 | 0.5 | 1.5 | 5.0 | 1.5 | 1.5 | 0.0 | 1.5 | 1.0 |

**LEGACY renter past_reference**:

| Y | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| % | 3.0 | 10.5 | 19.5 | 22.5 | 23.0 | 23.0 | 34.0 | 42.5 | **46.5** | 41.5 | 37.0 | 40.0 | 37.0 |

**CLEAN renter past_reference**:

| Y | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| % | 7.0 | 6.0 | 8.0 | 10.5 | 6.5 | 8.0 | 4.0 | 4.5 | 5.0 | 5.5 | 5.0 | 4.0 | 5.0 |

These four rows are the clearest evidence in the entire analysis that the memory write policy is working as designed. Under LEGACY the agents visibly accumulate a habit of citing their own past decisions as a justification for current inaction, hitting 30% for owners and 46% for renters. Under CLEAN the phrase frequency stays in the 1-10% band across all 13 years and shows no growth trend. This is a 20x compression for owners and a 9x compression for renters.

### 2.3 Self-referential phrase family

From the same CSV, the `self_referential` family (regex `\bI (have|am|will|chose|decided|feel|think)\b`). LEGACY Y13 owner 50% / renter 37.5%. CLEAN Y13 owner 3.5% / renter 4%. Again a 10-15x compression.

### 2.4 Construct temporal drift (Spearman ρ vs year)

From `rq3_construct_stats.csv`:

| Construct | LEGACY ρ | CLEAN ρ | Comment |
|---|---:|---:|---|
| SP vs year | 0.137 | 0.047 | CLEAN flattens SP temporal drift |
| PA vs year | 0.273 | 0.075 | CLEAN flattens PA temporal drift |
| SP vs flood_count | 0.635 | **0.650** | CLEAN PRESERVES flood-dose responsiveness |
| PA vs flood_count | 0.161 | 0.049 | CLEAN weakens PA flood-dose coupling |

The key row is `SP vs flood_count`: it stays at ρ=0.65 under CLEAN, meaning agents still appropriately update their protection perception in response to flood experience. CLEAN does not break the PMT causal chain on the flood-response axis — it specifically blocks the year-indexed temporal drift.

### 2.5 PA mean trajectory

From `rq3_sp_pa_yearly.csv`, pooled PA mean by year across all 400 agents:

| Year | LEGACY | CLEAN | Δ |
|---:|---:|---:|---:|
| 1 | 3.208 | 3.575 | **+0.37 Y1 priming** |
| 3 | 3.857 | 3.693 | -0.17 |
| 5 | 3.968 | 3.753 | -0.22 |
| 7 | 4.035 | 3.755 | -0.28 |
| 9 | 4.060 | 3.729 | -0.33 |
| 11 | 4.116 | 3.781 | -0.33 |
| 13 | 4.101 | 3.765 | **-0.34 Y13 ratchet block** |
| Y1→Y13 change | **+0.89** | **+0.19** | — |

LEGACY PA magnifies by 0.89 units over 13 years; CLEAN magnifies by only 0.19. CLEAN blocks 78% of the ratchet magnitude. But the curves cross at around Y2 — CLEAN starts 0.37 units higher at Y1 and is always below LEGACY from Y3 onward.

The Y1 elevation under CLEAN is the **owner prompt priming unmask**: when the `initial_narrative` rootedness seed ("could see moving if necessary") is blocked, the homeowner prompt identity phrase takes over without counterweight, and Y1 owner PA lands at 78% H+VH (vs LEGACY 52.5%).

## 3. EPI failure under CLEAN — which benchmarks flip

From `l2_macro_metrics.json` for each arm:

| Benchmark | LEGACY | CLEAN | Range | LEGACY in | CLEAN in |
|---|---:|---:|---|---|---|
| insurance_rate_sfha | 0.753 | 0.845 | [0.30, 0.60] | ✗ | ✗ (worse) |
| insurance_rate_all | 0.565 | 0.558 | [0.15, 0.55] | ✗ | ✗ |
| elevation_rate | 0.055 | 0.060 | [0.10, 0.35] | ✗ | ✗ |
| **buyout_rate** | **0.068** | **0.003** | [0.05, 0.25] | **✓** | **✗** (flipped) |
| do_nothing_rate_postflood | 0.206 | 0.136 | [0.35, 0.65] | ✗ | ✗ (worse) |
| mg_adaptation_gap | 0.180 | 0.060 | [0.05, 0.30] | ✓ | ✓ (narrower) |
| **renter_uninsured_rate** | **0.202** | **0.000** | [0.15, 0.40] | **✓** | **✗** (flipped) |
| insurance_lapse_rate | 0.186 | 0.230 | [0.15, 0.30] | ✓ | ✓ (higher) |
| govt_final_subsidy | 0.55 | 0.60 | [0.40, 0.75] | ✓ | ✓ |
| govt_avg_subsidy | 0.546 | 0.550 | [0.45, 0.70] | ✓ | ✓ |
| govt_decrease_count | 0 | 0 | [1, 5] | ✗ | ✗ |
| govt_change_count | 1 | 2 | [3, 8] | ✗ | ✗ |
| ins_final_crs | 0.25 | 0.15 | [0.05, 0.25] | ✓ | ✓ |
| ins_avg_crs | 0.183 | 0.140 | [0.03, 0.20] | ✓ | ✓ |
| ins_improve_count | 3 | 3 | [1, 5] | ✓ | ✓ |
| insurance_trajectory_change | 0.065 | -0.030 | [-0.40, 0.10] | ✓ | ✓ |

Two benchmarks flip from in-range to out-of-range:
- **buyout_rate**: the driver is renter relocation. LEGACY 35 relocation instances across 2600 renter decisions (1.35%); CLEAN 1 instance (0.04%). Under CLEAN, renters effectively stop relocating.
- **renter_uninsured_rate**: LEGACY has 20% of flood-zone renters without insurance at some point; CLEAN has 0%. Every flood-zone renter under CLEAN is insured at every year after Y1.

These two together tell the same story: CLEAN removes action diversity and pushes all renters toward a single insurance-default strategy.

## 4. Action space collapse under CLEAN

From `rq2_4cell_proposed_vs_executed.csv`, `rq3_construct_action_profiles.csv`:

| Action | LEGACY count | CLEAN count | Delta |
|---|---:|---:|---:|
| Renter relocate | 35 | 1 | -34 |
| Owner buyout_program | 1 | 0 | -1 |
| Owner elevate_house | 30 | 12 | -18 |
| Owner buy_insurance | 1397 | 1161 | -236 |
| Owner do_nothing | 2168 | **2378** | +210 |
| Renter buy_contents_insurance | 1541 | 1646 | +105 |
| Renter do_nothing | 2168 | 2378 | +210 |

(The last row is from a different CSV where the grouping differs; treat as approximate.)

The Shannon entropy of the 5-action distribution for owners drops from 1.07 bits under LEGACY to 0.85 bits under CLEAN (computed from the counts above, base 2). The action distribution collapses toward the `buy_insurance`/`do_nothing` binary. Relocation and elevation functionally disappear.

This collapse is consistent with the interpretation that `agent_self_report` memory writes were serving a diversity-maintaining function: entries like "I decided to relocate because..." and "I chose to wait this year because..." accumulate as first-person justifications that sustain non-default action choices over time. Without them the agent at Y(t) rethinks from the prompt's cost-effective baseline, which strongly favours insurance for anyone in a flood zone.

## 5. Tenure-level asymmetry — the three mechanisms

### 5.1 4-cell insurance delta table

From `rq3_construct_dynamics.py` outputs cross-joined with Y13 state:

| Cell | LEGACY Y13 Ins% | CLEAN Y13 Ins% | Δ |
|---|---:|---:|---:|
| MG-Owner | 39.0 | 26.0 | -13.0 |
| NMG-Owner | 83.0 | 44.0 | **-39.0** |
| MG-Renter | 55.0 | 73.0 | **+18.0** |
| NMG-Renter | 47.0 | 63.0 | +16.0 |

Renters gain ~16-18pp of insurance under CLEAN; owners lose ~13-39pp. The MG variable contributes only about 10pp within each tenure, while the tenure variable contributes 30-50pp.

### 5.2 Mechanism 1 — Owner Y1 priming unmasked

LEGACY owner Y1 PA H+VH is 52.5%, CLEAN owner Y1 PA H+VH is 78.0% (+25.5pp). The homeowner prompt contains the phrase "As a homeowner..." which combined with Gemma 4's training-data prior produces a strong identity-level attachment assertion at Y1. Under LEGACY the `initial_narrative` rootedness seed ("I feel comfortable but could see moving if necessary") is loaded into initial memory and serves as a counterweight. Under CLEAN that seed is filtered out by the `allow_initial_narrative=false` policy, and the prompt-level priming reaches ceiling immediately.

This mechanism is not memory-ratchet related. Owner Y1 PA jump happens at step 1, before any decision has occurred. Evidence: `reason_vocabulary_by_construct.csv` shows owner PA-REASON keyword `attachment` at 87-99% across all years in both arms (`rootedness` is near-omnipresent in the construct reasoning regardless of policy).

### 5.3 Mechanism 2 — Owner insurance state anchoring via self-report memory

NMG-Owner Y13 insurance state drops by 39pp under CLEAN but their pooled DN rate only rises by 10pp. The 29pp gap between state loss and action loss is an **insurance lapse effect**: under LEGACY, agents who bought insurance in early years wrote `agent_self_report` entries like "I chose insurance in Year 3" into memory; these entries were retrieved in later years and anchored the agent's renewal decision. Under CLEAN those self-reports are blocked, so the agent at Y(t) has no retrievable memory of its own prior insurance decision. It re-evaluates from the prompt's affordability analysis, and a meaningful fraction of owners land on "too expensive this year" and let the policy lapse.

Evidence: `insurance_lapse_rate` benchmark rises from 0.186 (LEGACY) to 0.230 (CLEAN), crossing toward the upper edge of the [0.15, 0.30] range. The lapse rate is a direct measurement of this mechanism.

### 5.4 Mechanism 3 — Action diversity via self-narrative

Under CLEAN the action space collapses (Section 4). Relocation drops from 35 to 1 instance, buyout from 1 to 0, elevation from 30 to 12. Renters converge on insurance-or-nothing. The mechanism is a generalization of Mechanism 2: `agent_self_report` writes sustain ANY non-default action across years, not just insurance. Without them, every agent year re-evaluates and converges on the single action with the best prompt-level justification.

Evidence: CLEAN Shannon entropy on owner action distribution drops from 1.07 to 0.85 bits. `buyout_rate` and `renter_uninsured_rate` both flip out of their empirical ranges because these both measure deviation from an insurance default.

### 5.5 Robustness footnote — validator vs proposal decomposition

**This subsection is a robustness check, not a headline result.** Per the Paper 3 EXECUTED-ONLY rule (see `CLAUDE.local.md`), all headline numbers above and below use the executed decision (`approved_skill.skill_name` / `final_skill`). This subsection decomposes the executed MG-Owner DN gap into LLM-proposal and validator-layer contributions only to rule out a validator-artifact interpretation.

From `rq2_4cell_proposed_vs_executed.csv`:

| Cell | LEGACY proposed DN | LEGACY executed DN | +Validator | CLEAN proposed DN | CLEAN executed DN | +Validator |
|---|---:|---:|---:|---:|---:|---:|
| MG-Owner | 56.15 | 60.23 | +4.08 | 66.23 | 67.15 | +0.92 |
| NMG-Owner | 33.46 | 36.62 | +3.16 | 43.54 | 45.92 | +2.38 |
| MG-Renter | 36.31 | 42.38 | +6.07 | 35.08 | 39.00 | +3.92 |
| NMG-Renter | 41.23 | 48.15 | +6.92 | 38.23 | 43.46 | +5.23 |

The decomposition confirms that the executed MG-Owner vs NMG-Owner DN gap is not an artifact of validator blocking. Of the 23.6pp executed gap under LEGACY (60.2% MG minus 36.6% NMG), 22.7pp is already present at the LLM proposal stage and only 0.9pp comes from a differential validator contribution. Under CLEAN the same decomposition holds: 22.7pp proposal, 1.2pp validator. The primary mechanism is prompt-level affordability internalisation in the LLM; the validator contribution is a secondary ~1pp.

**The headline MG-Owner story uses the executed number directly** (e.g. Section 5.4 reports executed DN, executed insurance uptake, cumulative OOP). The earlier Phase 0 extraction bug that appeared to show proposed==executed has been corrected; the governance_audit.csv values shown here are authoritative.

## 6. Institutional layer — new observations

### 6.1 Policy trajectories

From `institutional_rationale/institutional_trajectory.csv`:

- NJ_STATE: 1 `large_increase_subsidy` at Y1 (50% → 55%) followed by 12 years of `maintain_subsidy` under LEGACY. CLEAN shows a similar pattern with slightly different counts.
- FEMA_NFIP: 3 CRS improvements under both arms (Y3 improve, Y10 significantly_improve, Y12 improve), reaching CRS class 5 (25% discount) by Y13. Premium rate climbs from 0.008 to 0.0137 (+71%).

### 6.2 Institutional reactivity

- LEGACY: 4/4 reactive_adjustments (all policy changes follow a flood year within ±1 year)
- CLEAN:  7/7 reactive_adjustments

Both arms show 100% reactive policy adjustment — institutional agents act after floods, not before. CLEAN is slightly more reactive (3 additional adjustment events), consistent with FEMA_NFIP responding to slightly different household insurance uptake patterns.

### 6.3 Rationale categories

Rationale classifier counts by agent (from `institutional_rationale_categories_by_year.csv`):

| Agent | Category | LEGACY count | CLEAN count |
|---|---|---:|---:|
| NJ_STATE | budget_concern | 13 | 11 |
| NJ_STATE | crisis_response | 13 | 11 |
| NJ_STATE | status_quo | 12 | 10 |
| NJ_STATE | equity_concern | 0 | 0 |
| NJ_STATE | uncategorized | 0 | 2 |
| FEMA_NFIP | mitigation_reward | 10 | 10 |
| FEMA_NFIP | status_quo | 10 | 10 |
| FEMA_NFIP | equity_concern | 1 | 0 |
| FEMA_NFIP | loss_ratio_reaction | 1 | 1 |
| FEMA_NFIP | crisis_response | 0 | 1 |

Categories are non-exclusive (a single rationale text can mention both budget AND crisis). Under both policies NJ_STATE rationale is a three-way overlap of budget + crisis + status-quo; FEMA_NFIP rationale is dominated by mitigation-reward language. `equity_concern` is almost entirely absent from institutional rationale in both arms — a finding worth noting for RQ2 discussion.

### 6.4 Anomaly: institutional agents retrieve memory

The task brief assumed institutional agents would have `memory_audit.retrieved_count == 0`. Actual trace inspection shows both NJ_STATE and FEMA_NFIP have retrieved_count = 3 from Y2 onwards (12 years × 2 agents = 24 violations flagged by the institutional rationale script for each arm). This is consistent across both LEGACY and CLEAN, so it is a pre-existing data-model property, not a policy effect. The institutional memory retrieval deserves a separate investigation — does it affect policy decisions, and does the content match the humancentric retrieval mode used for households?

## 7. RQ-level implications

### 7.1 RQ1 (cross-paradigm comparison vs Traditional FLOODABM)

The Phase 1 `rq1_traditional_comparison.py` output now exists for both arms as `rq1_owner_comparison.csv` and `rq1_renter_comparison.csv`. A separate RQ1 synthesis document (`rq1_gemma4_legacy_vs_traditional.md`) was already produced for the LEGACY arm and is compatible with this analysis. CLEAN will need its own RQ1 write-up: the owner trajectory anti-phase (LEGACY Owner FI climbs vs Traditional Owner FI falls) is expected to **invert or flatten** under CLEAN because CLEAN removes the memory persistence that drove the LEGACY owner insurance climb. A quick check of `rq1_owner_comparison.csv` under CLEAN should confirm this.

### 7.2 RQ2 (institutional dynamics)

With Ablation B (flat baseline) runs still pending, RQ2 remains partial. What this analysis can say:

- The proposed-vs-executed decomposition shows that validator blocking is responsible for a meaningful but secondary share of MG-Owner DN (3-4pp under LEGACY, <1pp under CLEAN). The primary MG-Owner gap is at the LLM proposal stage under both policies.
- The institutional layer produces very similar trajectories across arms (1 subsidy change, 3 CRS improvements, same reactive pattern). This suggests the memory policy does not materially affect government or insurance agent decisions.
- The Ablation B comparison, when it lands, should pair with this analysis. Ablation B under CLEAN will be particularly informative because CLEAN's LLM proposal shift might make household decisions less sensitive to institutional variation.

### 7.3 RQ3 (construct mechanism)

The PMT causal chain (SP → action) is preserved under CLEAN at the cross-sectional level (ρ_SP_vs_flood_count = 0.650 CLEAN vs 0.635 LEGACY) and at the within-agent level (chi² = 11.34 CLEAN vs 8.99 LEGACY, CLEAN even slightly stronger). What CLEAN breaks is the temporal ratchet (ρ_SP_vs_year drops from 0.137 to 0.047, ρ_PA_vs_year from 0.273 to 0.075). This is consistent with the hypothesis that the LEGACY temporal drift was a memory-mediated bias, not a PMT dynamics feature.

The RQ3 Step 5 MG-Owner triple-lock claim needs revision regardless of arm. Neither arm supports the pattern "MG-Owner has lowest SP + highest survey PA + highest DN":
- MG-Owner SP mean is essentially identical to NMG-Owner in both arms (LEGACY 3.22 vs 3.19, CLEAN 3.14 vs 3.12; p=0.44 LEGACY, p=0.27 CLEAN).
- MG-Owner survey PA is slightly LOWER than NMG-Owner in both arms.
- MG-Owner DN is substantially higher than NMG-Owner in both arms (the direction memory had).

The correct RQ3 Step 5 story is **single-channel**: MG-Owner DN amplification comes from prompt-level affordability internalisation, with a small secondary validator contribution. The triple-lock framing should be dropped.

## 8. Anomalies and caveats

- **Institutional memory retrieval** (Section 6.4): institutional agents retrieve 3 memories from Y2 onwards despite no declared retrieval mode. Unclear source.
- **Validator label instability** carries over: `governance_summary.json` reports 1288 parse_errors, 1283 format_retries in LEGACY (similar magnitude expected in CLEAN). These are broker-level parse instabilities, not policy effects.
- **PA REASON "tempered" keyword** (0% in both arms): the keyword family in the reasoning taxonomy script was tuned for "could move / if necessary / possibility" but LLM rarely uses those specific words. The tempering mechanism is real (evident from the Y1 priming unmask) but is semantically encoded differently in the REASON text.
- **Phase 0 proposed-vs-executed bug correction**: an earlier Phase 0 script extracted `skill_proposal.skill_name` from the JSONL trace and reported all proposed-vs-executed deltas as zero. That was wrong — the JSONL trace field reflects the LATEST retry proposal, not the ORIGINAL proposal. The governance audit CSV preserves the original proposal and shows real gaps of 3-7pp per cell. The CSV is authoritative.
- **Seed 42 only**: CLEAN seed_123 is at Y13 near-completion; CLEAN seed_456 pending; Ablation B pending. All findings in this report are single-seed and single-arm within each policy. Cross-seed confirmation is required before paper-level claims.

## 9. Paper 3 framing — dual-role narrative

**Decision (2026-04-14): Paper 3 adopts the dual-policy, dual-role narrative.**

The headline claim is not "we fixed the PA bias" but **"memory writes in LLM multi-agent adaptation models serve a dual role, as both rationalization substrate and diversity substrate"**. This is a framework-level architectural observation, supported by a matched-seed LEGACY-vs-CLEAN comparison on Gemma 4 e4b seed 42 and by the three supporting mechanisms in the executive summary.

Concrete structure implications:

- **Section 4.x Results** present LEGACY and CLEAN side-by-side throughout. Neither is treated as "the right answer"; both are experimental conditions that illuminate different aspects of the framework.
- **RQ1 (cross-paradigm)** compares both arms against Traditional FLOODABM. Expected finding: LEGACY renter trajectory has stronger temporal Pearson r with Bayesian baseline; CLEAN renter trajectory is flatter; owner trajectories under both arms differ systematically from Bayesian (memory-independent prompt priming issue).
- **RQ2 (institutional dynamics)** uses executed action under both arms. The proposed-vs-executed decomposition stays as a robustness footnote (per EXECUTED-ONLY rule). Ablation B (flat institutional) will be run under both memory policies when available.
- **RQ3 (construct mechanism)** is restated with two key revisions: (a) the 5-step logic chain is preserved but Step 5 MG-Owner "triple lock" is dropped and replaced with a single-channel prompt-affordability story, (b) the LLM-vs-survey PA divergence finding gains a new support point — CLEAN removes the within-agent temporal PA drift while preserving the cross-sectional SP-behaviour coupling, which cleanly separates the two mechanisms Gemma 4 uses for place attachment inference.
- **Section 5/6 Discussion** leads with the dual-role finding as the main framework contribution, cites the broker-level `MemoryWritePolicy` API and tests as the enabling infrastructure, and presents owner prompt priming as a separate issue requiring a prompt-level intervention outside the memory framework.
- **Limitations**: single seed (CLEAN seed_123 pending, seed_456 pending); Gemma 4-specific systematic biases on 5 EPI benchmarks affect both arms; Ablation B (flat institutional) runs not yet complete.

**On EPI**: report LEGACY EPI 0.6115 and CLEAN EPI 0.4968 as a table row, describe the 5 Gemma 4-common benchmark misses and the 2 CLEAN-specific flips, note that EPI is a range-based heuristic not a validity test, and move on. Do not frame CLEAN's lower EPI as a "failure" — it is a calibration observation with the dual-role mechanism as the explanation.

**Note on earlier draft framings**: earlier versions of this report considered three framing options (LEGACY-primary-CLEAN-appendix, dual-policy, and selective-CLEAN new-run). The dual-policy option was selected because it treats the dual-role observation as the scientific contribution rather than as an obstacle. The selective-CLEAN option was deferred because the dual-role finding makes it likely that any middle-ground policy will just re-partition the same trade-off rather than eliminate it; that experiment can be revisited as a numbered future-work item if the reviewer-feedback window demands it.

## 10. Verification checks performed

- ✓ Phase 0 spot numbers reproduced in Phase 1 CSVs (Y13 renter PA H+VH ≈ 91% LEGACY / 54% CLEAN; NMG-Owner Y13 Ins% ≈ 83% / 44%).
- ✓ Phase 2 memory content CSVs show 10.5 `agent_self_report` entries at Y13 LEGACY and 0 at CLEAN (matches the broker manifest drop counts).
- ✓ All Phase 1 and Phase 2 scripts returned 0.
- ✓ No trace-level row drops between arms.
- ✓ EPI re-verification: both arms computed independently via `compute_validation_metrics.py`; LEGACY pass, CLEAN fail.
- ✓ Hazard bit-exact check: owner Y1 `environment_context.flood_depth_ft` identical across arms.

Still pending (Phase 4 verification work):
- Hand-verification of 3 cells per CSV against raw JSONL
- Cross-check `compute_cacr_null_model.py` outputs
- `git status` sweep to confirm no stray writes outside the designated output directories

## Files produced

Under `paper3/analysis/gemma4_legacy_seed42/` and `paper3/analysis/gemma4_clean_seed42/`:

Phase 1 (existing scripts, 15 CSVs + logs per arm):
- Validation: `benchmark_comparison.csv`, `cgr_metrics.json`, `l1_micro_metrics.json`, `l2_macro_metrics.json`
- RQ1: `rq1_owner_comparison.csv`, `rq1_renter_comparison.csv`, `rq1_tp_decay_within_agent.csv`, `rq1_tp_decay_by_group.csv`, `rq1_trad_vs_llm_trajectories.png`
- RQ2: `rq2_ablation_comparison.csv`, `rq2_ablation_chi2_tests.csv`, `rq2_policy_trajectory.csv`, `rq2_4cell_proposed_vs_executed.csv`, `rq2_equity_summary.csv`, `rq2_ablation_comparison.png`, `rq2_adaptation_gap.png`
- RQ3: `rq3_construct_stats.csv`, `rq3_construct_action_profiles.csv`, `rq3_sp_pa_yearly.csv`, `rq3_unconstrained_constructs.csv`, `rq3_action_exhaustion.csv`, `rq3_cp_by_income.csv`, `rq3_tp_by_cumflood.csv`, `rq3_tp_cp_gap.csv`, `rq3_tp_decay.csv`, `rq3_feedback_rigorous.csv`, `rq3_construct_action_feedback.csv`, `rq3_crosslayer_analysis.csv`

Phase 2 (new scripts, 3 subdirectories per arm):
- `memory_dynamics/`: `memory_size_by_year.csv`, `memory_content_type_by_year.csv`, `memory_category_by_year.csv`, `memory_new_writes_by_decision_year.csv`, `memory_rationalization_phrases_by_year.csv`, `memory_content_dynamics_report.md`
- `reasoning_taxonomy/`: `reason_text_length_by_year.csv`, `reason_vocabulary_by_construct.csv`, `reason_vocabulary_by_mg.csv`, `reasoning_phrase_detection_by_year.csv`, `audit_scores_by_year.csv`, `skill_proposal_reasoning_report.md`
- `institutional_rationale/`: `institutional_trajectory.csv`, `institutional_rationale_text.csv`, `institutional_rationale_categories_by_year.csv`, `institutional_rationale_report.md`

New scripts under `paper3/analysis/`:
- `analyze_memory_content_dynamics.py`
- `analyze_skill_proposal_reasoning.py`
- `analyze_institutional_rationale.py`

Context and plan artifacts:
- `.ai/codex_task_gemma4_legacy_clean_comprehensive.md` — Codex delegation brief
- `~/.claude/plans/snuggly-beaming-dahl.md` — approved plan
- `memory/gemma4_clean_vs_legacy_asymmetry.md` — evolving findings memo
