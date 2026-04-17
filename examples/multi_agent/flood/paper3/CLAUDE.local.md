# Paper 3: LLM-Governed Multi-Agent Flood Adaptation

## Quick Reference for AI Agents

This document enables AI agents to quickly understand the Paper 3 design and framework.

### What This Paper Does

- Uses LLM (**Gemma 4 e4b** — pivoted from Gemma 3 4B, 2026-04-10) to simulate 400 households' flood adaptation decisions
- 13-year simulation in Passaic River Basin, NJ
- 3-tier governance: Government → Insurance → Households
- Claims **structural plausibility** not prediction accuracy

### Target Journal

**Water Resources Research (WRR)**

---

## Gemma 4 Pivot Status (updated 2026-04-11 — memory policy fix)

**Primary model:** Gemma 4 e4b (8B, Q4_K_M). Gemma 3 4B kept only for cross-model comparison in Discussion.

### Pivot rationale
- Broker `think` flag bug fixed (commit `fc6c599`): `--thinking-mode disabled` now actually routes to Ollama top-level `think=false`. All prior Gemma 4 runs had uncontrolled thinking.
- PA prompt criteria added (commit `145198c`): explicit VL/L/M/H/VH anchors + buyout emotional priming removed from owner prompt.
- Per-agent exception isolation fix (`ac7faea`): experiment won't abort on single LLM failure.
- Conservatism Diagnostic module (`591eeb8`): CCA/CSI/ACI/ESRR metrics for model comparison.
- **Memory write policy fix (2026-04-11, this document)**: `broker/config/memory_policy.py` + `examples/multi_agent/flood/orchestration/lifecycle_hooks.py` gating. Blocks the rationalization ratchet (LLM self-report → memory → self-read → self-reinforce loop) that caused Gemma 4 Renter PA drift from 22% Y1 to 87% Y13. Also drops first-person PA/SP narrative seeds at initial memory load. See `.ai/broker_memory_policy_design.md` for full audit.

### Experiment status — ALL 6 ARMS COMPLETE (2026-04-17)

| Run | Condition | Seed | Policy | Status | Path | Commit |
|---|---|---|---|---|---|---|
| baseline | Full | 42 | LEGACY | ✅ COMPLETE | `paper3_gemma4_e4b_legacy/seed_42/gemma4_e4b_strict/` | `14b55a6` |
| 1 | Full | 42 | CLEAN | ✅ COMPLETE | `paper3_gemma4_e4b_clean/seed_42/` | `14b55a6` |
| 2 | Full | 123 | CLEAN | ✅ COMPLETE | `paper3_gemma4_e4b_clean/seed_123/` | `14b55a6` |
| 3 | Full | 456 | CLEAN | ❌ INTERRUPTED + CLEANED | (deleted, not rerun) | — |
| 4 | Ablation B (flat) | 42 | CLEAN | ✅ COMPLETE | `paper3_gemma4_ablation_flat_clean/seed_42/` | `5609508` |
| 5 | Ablation B (flat) | 123 | CLEAN | ✅ COMPLETE | `paper3_gemma4_ablation_flat_clean/seed_123/` | `5609508` |
| 6 | Ablation B (flat) | 456 | CLEAN | ✅ COMPLETE | `paper3_gemma4_ablation_flat_clean/seed_456/` | `5609508` |

**Preliminary results COMPLETE**. Analysis pipeline (15 Phase 1 + 3 Phase 2 scripts + 3 RQ-deep scripts) has been run on all 6 complete arms. Deep 6-arm synthesis with Pearson r, Mann-Whitney, chi-squared, ANOVA+Tukey HSD is in `paper3/analysis/deep_synthesis/`. Contribution positioning in `paper3/analysis/PAPER3_POSITIONING.md` (start here for Section 4 drafting). Navigation in `paper3/analysis/INDEX.md`.

CLEAN Full seed_456 was interrupted mid-Year-3 on 2026-04-14 and the partial data was deleted. It has not been rerun — the 2-seed CLEAN Full (42, 123) is treated as sufficient, with single-seed status flagged as a limitation.

Original launchers `run_gemma4_ma_pivot_clean.bat`, `run_gemma4_full_experiment.bat`, `run_gemma4_ablation_b_only.bat` are retained for reproducibility but should not be rerun. Paper 3 data is frozen.

### Dual-role narrative decision (2026-04-14)

Paper 3 adopts the dual-role narrative: memory writes serve BOTH rationalization substrate (carrying the PA ratchet that inflates LLM PA from 32% to 91% by Y13 under LEGACY) AND action-diversity substrate (sustaining non-default action choices). Blocking them (CLEAN) compresses ratchet phrase frequency from ~30% to ~1-5% but also collapses renter relocation from 36 instances to 1-2 and owner elevation from 34 to 8-12. LEGACY and CLEAN are presented side-by-side in Section 4 Results as two experimental conditions that illuminate different aspects of the framework, not as fix-vs-broken. See Section 9 of `paper3/analysis/gemma4_legacy_clean_comprehensive_report.md` for the full framing argument.

### EXECUTED-ONLY rule (highest-priority analysis rule)

See the standalone section "EXECUTED-ONLY rule (2026-04-14)" earlier in this file. Every headline number uses `approved_skill` / `final_skill` / `state_after`. Proposed-skill fields are reserved for one explicit robustness footnote (Section 5.5 of `gemma4_legacy_clean_comprehensive_report.md`) and nowhere else.

### Analysis pipeline entry points

- `paper3/analysis/PAPER3_POSITIONING.md` — 8-section contribution catalog (start here)
- `paper3/analysis/INDEX.md` — navigation map for all 484 analysis files
- `paper3/analysis/deep_synthesis/DEEP_SYNTHESIS_REPORT.md` — 10-section 6-arm narrative synthesis
- `paper3/analysis/deep_synthesis/rq_deep/rq{1,2,3}_*_report.md` — three RQ-specific deep-analysis reports

### Cross-model verdict table (seed_42, Gemma 3 vs Gemma 4 post-fix)

| Finding | Gemma 3 4B | Gemma 4 e4b | Verdict |
|---|---|---|---|
| CP reversal | 3.6% / do_nothing 83.9% | 8.0% / do_nothing 79.8% | **persists** (not G3 artifact) |
| PA saturation | 17% H+VH (gradient intact) | 94.6% H+VH (saturated) | **G4 biased** (structural) |
| Deliberative override | Case A 30.1%, Case B 22.4% | Case A 11.1%, Case B 11.8% | **weakened in G4** |
| MG-Owner trapping | 67.0% vs 56.4% (+10.6pp) | 64.2% vs 35.8% (+28.4pp) | **amplified in G4** |

Source: `paper3/analysis/gemma4_rerun_vs_gemma3.md`.

### Broker-Level Memory Governance (2026-04-11, landed)

The earlier MA-scoped ratchet fix was promoted to a broker-level facility so any future MA experiment inherits the protection automatically. See `broker/components/memory/README.md` for the author-facing quickstart and `.ai/broker_memory_governance_architecture.md` for the architecture overview.

Key components:
- `broker/components/memory/content_types.py` — `MemoryContentType` enum (9 members: 6 safe + 3 risky)
- `broker/components/memory/policy_filter.py` — `PolicyFilteredMemoryEngine` proxy wrapping any memory engine
- `broker/components/memory/policy_classifier.py` — domain-neutral `classify()` helper
- `broker/components/memory/initial_loader.py` — reusable `load_initial_memories_from_json()` helper
- `broker/config/memory_policy.py` — refactored `MemoryWritePolicy` with `allow_*` content-type-aware fields
- `broker/core/experiment_builder.py` — `with_memory_write_policy()` fluent method
- `examples/multi_agent/flood/memory/content_type_mapping.py` — the ONLY flood-domain-specific file, defines `FLOOD_CATEGORY_TO_CONTENT_TYPE`

Enforcement contract: every `add_memory` call tagged with `content_type` in metadata is classified by the proxy and either forwarded or silently dropped based on the active `MemoryWritePolicy`. `CLEAN_POLICY` (default for new configs) blocks `AGENT_SELF_REPORT`, `AGENT_REFLECTION_QUOTE`, and `INITIAL_NARRATIVE`. `LEGACY_POLICY` allows all nine types (used for reproducing pre-2026-04-11 experiments). The reproducibility manifest now includes a `memory_write_policy` section with policy dict + per-type drop/allow counts for auditable drops.

Smoke verified 2026-04-11: 6-agent × 2-year run under `CLEAN_POLICY` produced `dropped_counts={"agent_self_report": 12, "initial_narrative": 12}` and `allowed_counts={"external_event": 34, "initial_factual": 18, "social_observation": 12, "agent_action": 12, "institutional_state": 4, "institutional_reflection": 4}`. Grep for `"I decided to.*because"`, `"I have deep emotional ties"`, and `"I trust government programs"` across the smoke output returned empty. Factual seeds (`"I experienced flooding"`, etc.) present in traces as expected.

Test coverage: 77 broker-level tests + 32 refactored MA flood tests + the existing 308 flood suite = 417 passes, with 1 pre-existing unrelated failure in `test_fig6_rq3_construct_profiles.py`.

### PA Handling Strategy (2026-04-10) — Survey-Grounded PA

**Problem**: Gemma 4 LLM-reported PA saturates at 94% H+VH in full MA context. 8-variant calibration test shows this is context-cumulative (model bias + context reinforcement), not prompt-fixable. V0 (current production) is already the best composite (0.601) and no variant beats it. Do not tune PA prompts further.

- Minimal context (Y1, no memory/gossip/governance): V0 → mean 3.43, SD 0.82, 23% H+VH (reasonable).
- Full MA context (13yr, 2600 decisions): V0 → 94.6% H+VH (saturated).
- LLM PA vs generations: Spearman +0.69 (strong).
- LLM PA vs survey `pa_score`: Spearman −0.17 (negative, unusable).

**Solution**: Switch PA variable source from LLM audit (`PA_LABEL`) to survey ground truth (`pa_score` in `agent_profiles_balanced.csv`). Justification:

1. `pa_score` is a survey-derived continuous variable (1–5, mean 3.08, SD 0.82, full distribution) computed from the 755-household NJ survey used to build agent profiles. It is the actual PA ground truth — LLM-reported PA was only a redundant re-derivation.
2. PA is a relatively static construct; loss of LLM year-to-year variation is negligible (Gemma 3 PA was also nearly static).
3. Other constructs (TP/CP/SP/SC) remain LLM-sourced — they are dynamic and context-dependent, so profile static values would wash out within-agent variation.
4. The LLM-vs-survey PA divergence becomes a **methodology finding**, not a limitation: language models can recover the observable proxy (`generations`, ρ=+0.69) but cannot reconstruct the latent affective component of place attachment from demographic profile features. 8-variant calibration is the evidence.

**Impact on RQ3** — remains 5-step (no downgrade):
- Step 1 Construct Validity: applies to SP and LLM PA (as diagnostic); survey PA has external survey validity by construction.
- Step 2 Cross-Sectional: SP → protection (LLM); PA → relocation for renters (**survey `pa_score`**, previously unusable in G4).
- Step 3 Within-Agent: SP dynamics only (LLM). Note that survey PA is static; within-agent PA dynamics are not analyzed.
- Step 4 Deliberative Override: report G3 vs G4 contrast (Case A 30% vs 11%, Case B 22% vs 12%) — weakens in G4 but still a finding.
- Step 5 MG-Owner Triple-Lock: **restored** — MG-Owner has lowest SP (LLM) + highest survey `pa_score` + highest DN rate + affordability validator blocking. Triple-lock mechanism intact with survey-grounded PA.

**LLM vs survey PA divergence** is reported as an additional finding in Discussion: evidence that LLM cognitive constructs can be biased even when the model receives calibrated survey inputs — use for "framework validation" section and as a concrete example of the "what language models can and cannot read from profiles" caveat.

Reference: `.ai/pa_prompt_calibration_plan.md`, `paper3/analysis/pa_prompt_calibration_results.md`, `paper3/analysis/gemma4_rerun_vs_gemma3.md`, memory `gemma4_pa_saturation.md`.

---

## EXECUTED-ONLY rule (2026-04-14 — applies to all Paper 3 analysis)

**Every headline result in Paper 3 uses the EXECUTED decision, never the proposed decision.** Headline means: any number that appears in a table, figure, CSV column, or narrative claim in Section 4 (Results) and the abstract.

- **Use**: `approved_skill.skill_name` in the JSONL trace, `final_skill` column in `*_governance_audit.csv`, `state_after` fields (`has_insurance`, `elevated`, `relocated`, `cumulative_damage`, `cumulative_oop`). These reflect what the 3-tier governance architecture actually produced after Government → Insurance → Household validator rounds.
- **Do NOT use as headline**: `skill_proposal.skill_name` or `proposed_skill` from governance_audit. These represent what the LLM first suggested before any validator check. They can be inspected only as part of a dedicated robustness/sanity footnote (e.g. "we confirmed the MG-Owner gap is not a validator artifact by checking that the proposal-stage gap is also 22.7pp").
- **Rationale**: (1) WAGF's framework claim is that 3-tier governance SHAPES household action — what matters is the action after all three tiers have acted. (2) Traditional FLOODABM reports only the Bernoulli-sampled outcome (no separate "proposal" step), so cross-paradigm comparison (RQ1) must use LLM executed decisions to stay apples-to-apples. (3) Empirical benchmarks (NFIP uptake, elevation rates, buyout rates) describe what households actually did, not what they considered.
- **Reasoning text is exempt from the rule**: construct labels (TP/CP/SP/SC/PA) and free-text `*_REASON` fields are captured at the proposal stage but are still the "correct" record of the LLM's deliberation, because validators do not rewrite reasoning. When joining reasoning text to an outcome variable, the outcome must still be the executed action, not the proposed action.
- **Existing writeups that need to honour this rule**: `paper3/analysis/gemma4_legacy_clean_comprehensive_report.md` Section 5.5 (Validator-layer contribution) should be labeled as a robustness check, not a headline. RQ2 narrative cannot use the prior "validators create equity gap" framing from G3 — in G4 both LEGACY and CLEAN runs show the MG-Owner gap originating at the LLM proposal stage, and the headline should report the executed gap directly.
- **Cross-references**: `.ai/codex_task_gemma4_legacy_clean_comprehensive.md` Rule 0 (highest priority), memory `gemma4_clean_vs_legacy_asymmetry.md`.

---

## Key Concepts

| Term | Meaning |
|------|---------|
| MG | Marginalized Group (income<$50K OR housing_burden>30% OR no_vehicle) |
| NMG | Non-Marginalized Group |
| TP | Threat Perception (VL/L/M/H/VH) - perceived flood risk |
| CP | Coping Perception (VL/L/M/H/VH) - perceived ability to respond |
| PMT | Protection Motivation Theory - TP×CP → Action |
| WAGF 3-Tier | 3-Tier Governance Ordering (Government → Insurance → Households) |
| ICC | Intraclass Correlation Coefficient (reliability measure) |
| EPI | Empirical Plausibility Index (range-based plausibility assessment, not statistical validation) |
| CACR | Construct-Action Coherence Rate (per-decision validation) |
| R_H | Hallucination Rate (impossible action rate) |
| PRB | Passaic River Basin (study area) |
| SFHA | Special Flood Hazard Area (FEMA designation) |
| RCV | Replacement Cost Value (building + contents) |

---

## Data Sources (CRITICAL - DO NOT CONFUSE)

| Source | N | Used For | Type |
|--------|---|----------|------|
| Survey (NJ households) | 755 → 400 | Agent initialization | Empirical |
| Archetypes | 15 | L3 validation (ICC probing) | Manually designed |
| LLM Probing | 2,700 | ICC/eta² computation | LLM-generated |

**IMPORTANT**:
- Archetypes are **NOT** sampled from survey data
- Archetypes are manually designed to span demographic-situational extremes
- L3 validation is **independent** of the primary experiment
- L1/L2 validation uses experiment traces (52,000 decisions)

---

## Three Research Questions (Revised 2026-03-31)

**Overarching question:** Can language-based agent reasoning, constrained by institutional governance, reproduce and extend the behavioral patterns generated by calibrated Bayesian ABMs in flood adaptation?

**Comparison baseline:** Traditional FLOODABM (Bayesian regression + Bernoulli trial, ~52K households, PRB 2011-2023, 15 MC runs, no institutional agents, no social network). Located at: `C:\Users\wenyu\OneDrive - Lehigh University\Desktop\Lehigh\NSF-project\ABM\paper\draft\mg_sensitivity\FLOODABM`

| RQ | Question | Key Findings | Key Figure |
|----|----------|-------------|------------|
| RQ1 | Where do agents that reason through natural-language deliberation **converge with and diverge from** agents governed by survey-calibrated Bayesian probability in flood adaptation outcomes? | 3 converge (EH 1.3pp, BP 0.5pp, Renter FI 3.6pp) + 3 diverge (Owner FI 15.6pp, Renter RL 20.8pp, Renter DN 20.2pp); reasoning traces reveal adaptation deficit + intention-action gap | Dual time series + reasoning keyword taxonomy |
| RQ2 | How do government subsidy and insurance pricing adjustments **alter household adaptation trajectories** compared to fixed-parameter institutional assumptions? | Aggregate NS (Owner p=0.47); equity channel: MG affordability blocking Full=100 vs Flat=247 (+147%); proposed vs executed gap: MG-Owner 44.5%→67.2% DN (+22.6pp) | Policy trajectory + equity 2×2 + proposed vs executed |
| RQ3 | How do psychological constructs **interact with deliberative reasoning** to shape adaptation decisions in language-based agents? | 5-step logic: (1) constructs semantically grounded, (2) SP/PA→behavior cross-sectional, (3) within-agent SP change→behavior change (chi²=129), (4) deliberative override (31% high-motivation inaction, 23.5% low-trust insurance), (5) MG-Owner trapped profile | Heatmap + SP-behavior change + override quadrant + 4-cell bubble |

### Traditional ABM (FLOODABM) Key Specs
- **Decision model**: Bayesian regression → Bernoulli trial (u < p_action)
- **Actions**: Owner: FI→EH→BP→DN (hierarchical); Renter: FI→RL→DN
- **Psychology**: TP dynamic (shock+decay), CP/SP/SC/PA static (Beta-distributed)
- **TP shock**: `TP' = min(1, TP + 0.3 × damage_ratio)` if ratio ≥ 0.10
- **TP decay**: `TP' = TP × exp(-ln2 × w × Eff)` where w = α(1-PA) + β×SC
- **Institutional**: None — subsidy/premium are fixed parameters
- **Social**: None — agents decide independently
- **Scale**: ~52K households, 27 census tracts
- **Calibration**: 15 MC runs, CV < 4% — highly stable
- **MG definition**: Tract-level mixed tenure (≠ LLM-ABM individual socioeconomic)

### Key Comparison Dimensions
| Dimension | Traditional ABM | LLM-ABM (WAGF) |
|-----------|----------------|-----------------|
| Decision mechanism | Bayesian posterior → Bernoulli | Language reasoning + validators |
| Action selection | Hard-coded hierarchy (FI→EH→BP) | Free choice, post-hoc constraint |
| Psychological factors | TP dynamic, rest static | All re-evaluated each year |
| Institutional layer | None (exogenous params) | 3-tier endogenous (Gov→Ins→HH) |
| Social interaction | None | Gossip + memory sharing |
| Heterogeneity source | Beta distribution + random draws | Narrative reasoning + context |
| Calibration | Survey-trained Bayesian posteriors | Prompt design + empirical benchmarks |

### Hybrid_v2 Results (3-seed pooled) — Key Numbers
- **CACR**: 0.855±0.006, **R_H**: 0.000, **EPI**: 0.809
- Owner FI=36.2%, EH=1.8%, BP=0.9%, DN=61.1% (executed, pooled)
- Renter FI=32.7%, RL=3.4%, DN=63.9% (executed, pooled)
- MG affordability blocking: Full=100 vs Flat=247 (+147%)
- Gov policy: crisis→recurring transition at Y6
- Insurance: Y9 reduce_crs (mitigation declining)

### Counterintuitive Findings (2026-03-31) — Must Address in Paper

1. **CP reversal**: CP=H agents are MORE passive than CP=M. Opposite of PMT prediction. In Gemma 3: CP=H share 3.6%, do_nothing 83.9%. In **Gemma 4** (post-fix): CP=H share 8.0%, do_nothing 79.8% — **still present**. Updated interpretation (2026-04-10): not a Gemma 3 artifact. Cross-model persistence suggests semantic interpretation of "high coping" as "I can cope with status quo" is robust across model scales. → **Limitation section** + cross-model contrast point, not primary finding.

2. **Gossip transmits inaction norms**: Gossip citation RR=0.75 (negative association with protection). First-movers cite gossip 43.9% vs never-adopters 66.9%. Social channels implemented but not causally driving protection. → Frame as "descriptive norm exposure" in Discussion.

3. **MG/NMG proposed behavior nearly identical** (1-2pp difference). LLM does not self-differentiate by income — RLHF bias toward protective action regardless of financial constraints. Real gap only emerges in EXECUTED behavior (12.2pp) after validator blocking. → Key for RQ2: validators create the equity gap, not LLM reasoning.

4. **Memory contributes but not independently causal**: 86% of reasoning cites memory-unique info, but key numeric facts (flood_count, cumulative_damage) overlap with agent_state. Cannot attribute insurance persistence (36% vs Traditional 21%) solely to memory without memory-ablation experiment. → Use "consistent with" language.

5. **SP flood-dose response (ρ=0.458) but time trend weak (ρ=0.097)**: SP jumps Y1→Y2 then plateaus. Not gradual trust-building — more like cold-start artifact. → Report cross-sectional SP→behavior (strong), not temporal SP dynamics.

### RQ3 Logic Chain (5-step, survey-grounded PA — updated 2026-04-10)

**Question**: How do psychological constructs interact with deliberative reasoning to shape adaptation decisions in language-based agents?

**PA source rule**: SP/CP/SC/TP use LLM audit values (dynamic). PA uses survey `pa_score` from `agent_profiles_balanced.csv` (static, ground truth). LLM `PA_LABEL` retained only as diagnostic for the LLM-vs-survey divergence finding.

**Step 1 — Construct Validity**: SP labels match reasoning text semantics (LLM construct → reasoning keyword alignment). Survey PA has external validity by construction (756-household NJ survey). Re-run on G4 data; expected intact.

**Step 2 — Cross-Sectional Association**: SP → protection (LLM construct, p<10⁻²⁷⁹ in G3 — retest on G4); PA → relocation for renters (**survey `pa_score`**, p<10⁻⁵ in G3 — restored for G4 via survey source). Both are unconstrained constructs (SP: no validator blocking; PA: does not gate renter relocation).

**Step 3 — Within-Agent Dynamics**: SP↑ → protective action switch (chi²=129 in G3); SP(t-1) predicts action(t) (chi²=140 in G3). Retest on G4. PA within-agent dynamics not analyzed — survey PA is static per agent.

**Step 4 — Deliberative Override**: (A) TP=H+SP=H → still do_nothing rate. (B) SP=L → insurance rate. G3: 31% / 22.4%. G4 seed_42: 11.1% / 11.8% (**weakens in G4**). Report as cross-model contrast: stronger models show tighter construct-action coupling. Still a finding, but framed as coupling-strengthens-with-capability.

**Step 5 — Group-Level Triple Lock**: MG-Owner has lowest SP (LLM, dynamic) + highest survey `pa_score` (static, ground truth) + highest DN rate + affordability validator blocking. Four-channel locking mechanism. G3 gap: +10.6pp; G4 gap: +28.4pp (**amplified in G4**). Use survey PA for the attachment channel, not LLM PA.

**Additional finding (new)** — LLM vs survey PA divergence: LLM PA correlates +0.69 with `generations` but −0.17 with survey `pa_score` across all 8 prompt variants tested. Language models reconstruct observable proxies (generational depth) from demographic profiles but cannot recover latent affective attachment. Report in Discussion as a concrete calibration finding — a methodology contribution, not a limitation.

**Figure plan**: Fig 6 (a) SP/survey-PA heatmap, (b) SP change→behavior change (within-agent), (c) cross-model override quadrant (G3 vs G4 side-by-side), (d) 4-cell triple-lock bubble (SP × survey PA × DN). New diagnostic panel: LLM PA saturation trajectory vs survey PA distribution (for Discussion, NOT Fig 6).

**Discussion material**: CP reversal persists in G4 (not G3 artifact — updated 2026-04-10); MG amplification in G4; deliberative override attenuation as model-capability effect; LLM PA vs survey PA divergence as a methodology contribution; framework implication that construct grounding should prefer calibrated inputs over LLM re-derivation when possible.

### TODO Status (updated 2026-04-17 — preliminary results complete)
- [x] Extract Traditional ABM results
- [x] RQ2 ablation on Gemma 3 (Ablation B: fixed subsidy=50%, CRS=0%)
- [x] Run Gemma 3 3 seeds (42, 123, 456) — kept for cross-model comparison only
- [x] Reasoning trace analysis on Gemma 3 (legacy)
- [x] Construct dynamics analysis on Gemma 3 (legacy)
- [x] Broker think flag bug fix (`fc6c599`) + PA prompt criteria (`145198c`) + runner exception isolation (`ac7faea`)
- [x] PA prompt 8-variant calibration (concluded: not prompt-fixable, structural G4 limit)
- [x] Gemma 4 seed_42 Full (re-run with think=false)
- [x] **Gemma 4 pivot batch** — all 6 arms complete 2026-04-16 (LEGACY Full 42, CLEAN Full 42/123, CLEAN Flat 42/123/456; CLEAN Full 456 interrupted and cleaned, not rerun)
- [x] Re-run Phase 1 + Phase 2 + RQ-deep analysis scripts on G4 data (commits `14b55a6`, `9fd89ba`, `4b595f3`, `5609508`, `d28ac74`)
- [x] Dual-role narrative framing decision (commit `14f705f`, 2026-04-14)
- [x] EXECUTED-ONLY rule propagated across CLAUDE.local.md + memory + Codex briefs (commit `14f705f`)
- [x] RQ3 Step 1 renter construct validity parser fix (integrated_prose fallback; 2026-04-17)
- [x] Paper 3 positioning document `PAPER3_POSITIONING.md` + `INDEX.md` (Codex, 2026-04-17)
- [ ] Reconcile MG definition in Methods (LLM=individual, Traditional=tract-level)
- [ ] Draft Section 4 Results (unblocked; data + positioning doc ready)
- [ ] Regenerate 6 figures from `deep_synthesis/figures/*.csv` (matplotlib)
- [ ] Prof Yang review of preliminary results before Section 4 drafting
- [ ] Rewrite Discussion + Conclusions drawing on dual-role framework contribution

---

## Validation Metrics (Pass/Fail)

| Level | Metric | Threshold | Current Status |
|-------|--------|-----------|----------------|
| L1 Micro | CACR | ≥0.80 | ✓ 0.853 (hybrid_v2/seed_42) |
| L1 Micro | R_H | ≤0.10 | ✓ 0.000 |
| L1 Micro | EBE | >0 | ✓ 1.438 (ratio=0.62) |
| L2 Macro | EPI | ≥0.60 | ✓ 0.809 (13/16 benchmarks) |
| L3 Cognitive | ICC(2,1) | ≥0.60 | ✓ 0.964 |
| L3 Cognitive | eta² | ≥0.25 | ✓ 0.33 |
| L3 Sensitivity | Directional | ≥75% | ✓ 75% |

---

## 8 Empirical Benchmarks

| # | Metric | Range | Weight | Category |
|---|--------|-------|--------|----------|
| B1 | insurance_rate_sfha | 0.30-0.60 | 1.0 | AGGREGATE |
| B2 | insurance_rate_all | 0.15-0.55 | 0.8 | AGGREGATE |
| B3 | elevation_rate | 0.10-0.35 | 1.0 | AGGREGATE |
| B4 | buyout_rate | 0.05-0.25 | 0.8 | AGGREGATE |
| B5 | do_nothing_rate_postflood | 0.35-0.65 | 1.5 | CONDITIONAL |
| B6 | mg_adaptation_gap | 0.05-0.30 | **2.0** | DEMOGRAPHIC |
| B7 | renter_uninsured_rate | 0.15-0.40 | 1.0 | CONDITIONAL |
| B8 | insurance_lapse_rate | 0.15-0.30 | 1.0 | TEMPORAL |

---

## Directory Structure

```text
paper3/
├── analysis/
│   ├── figures/              # All paper figures (PNG + PDF)
│   │   ├── fig1_system_architecture.png
│   │   ├── agent_spatial_distribution.png
│   │   └── agent_distribution_stats.csv
│   ├── tables/               # Paper tables (CSV)
│   ├── fig_agent_spatial_distribution.py
│   ├── fig_system_architecture.py
│   ├── compute_validation_metrics.py
│   └── export_agent_initialization.py
│
├── data/                     # Supplementary data CSVs
│   ├── agent_initialization_complete.csv
│   ├── empirical_benchmarks.csv
│   └── icc_archetypes_definition.csv
│
├── results/
│   ├── cv/                   # L3 validation (pre-experiment)
│   │   ├── icc_report.json
│   │   ├── icc_responses.csv
│   │   └── persona_sensitivity_report.json
│   │
│   ├── validation/           # L1/L2 validation (post-experiment)
│   │   ├── validation_report.json
│   │   ├── l1_micro_metrics.json
│   │   └── l2_macro_metrics.json
│   │
│   ├── paper3_primary/       # OLD experiment traces (single-tier)
│   │   └── seed_42/
│   │       └── gemma3_4b_strict/
│   │           └── raw/*.jsonl
│   │
│   └── paper3_hybrid_v2/     # CURRENT experiment (3-tier hybrid institutional)
│       └── seed_42/
│           └── gemma3_4b_strict/
│               ├── raw/*.jsonl
│               └── *_governance_audit.csv
│
├── configs/                  # Experiment configurations
│   ├── icc_archetypes.yaml
│   └── scenarios/
│
└── CLAUDE.local.md           # This file
```

---

## Key Commands

```bash
# Change to flood directory
cd examples/multi_agent/flood

# Generate spatial distribution figures
python paper3/analysis/fig_agent_spatial_distribution.py

# Run L3 validation (ICC probing)
python paper3/run_cv.py --mode icc --model gemma3:4b

# Run persona sensitivity test
python paper3/run_cv.py --mode persona_sensitivity --model gemma3:4b

# Compute L1/L2 metrics (after experiment)
python paper3/analysis/compute_validation_metrics.py \
    --traces paper3/results/paper3_primary/seed_42

# Export agent initialization data
python paper3/analysis/export_agent_initialization.py
```

---

## Governance Rules (PMT-based)

### Household Owners

| TP | CP | Allowed Actions |
|----|----|-----------------|
| VH/H | VH/H | elevate, buy_insurance, buyout |
| VH/H | M | buy_insurance, retrofit |
| VH/H | VL/L | do_nothing (fatalism allowed) |
| M | * | any reasonable action |
| VL/L | * | do_nothing, buy_insurance (optional) |

### Household Renters

| TP | CP | Allowed Actions |
|----|----|-----------------|
| VH/H | VH/H | buy_contents_insurance, relocate |
| VH/H | M | buy_contents_insurance |
| VH/H | VL/L | do_nothing (fatalism allowed) |
| M | * | any reasonable action |
| VL/L | * | do_nothing |

---

## WAGF 3-Tier 3-Tier Architecture

```text
Phase 1: Government (NJDEP)
    │ → Sets subsidy_rate
    ▼
Phase 2: Insurance (FEMA/CRS)
    │ → Sets crs_discount, premium_rate
    ▼
Phase 3: Households (400 agents)
    │ → Make adaptation decisions based on:
    │   - Updated subsidy/premium rates
    │   - Individual TP/CP assessments
    │   - Memory of past floods
    ▼
Environment Update
    │ → Apply PRB flood depths (2011-2023)
    │ → Calculate damages
    │ → Update agent memories
```

---

## File Naming Convention

- **Figures**: `fig{N}_{short_name}.png/pdf` (e.g., `fig1_system_architecture.png`)
- **Tables**: `table{N}_{short_name}.csv`
- **Data**: `{descriptive_name}.csv`
- **Scripts**: `fig_{short_name}.py` or `{verb}_{noun}.py`

---

## Agent Initialization Summary

- **Total Agents**: 400 (100 per cell)
- **4-Cell Design**: MG-Owner, MG-Renter, NMG-Owner, NMG-Renter
- **MG Criteria**: income < $50K OR housing_burden > 30% OR no_vehicle
- **Flood Zone Assignment**:
  - MG: 70% flood-prone, 30% dry
  - NMG: 50% flood-prone, 50% dry
- **RCV Generation**:
  - Owners: lognormal($280K/$400K median), σ=0.3
  - Renters: contents only, income-based
- **Initial Memories**: 6 categories (flood_experience, insurance, social, gov_trust, place, zone)

---

## Prompt Design Rationale (Methods Section Material)

### De-quantification (v7, 2026-02-16)

Population-frequency percentages (e.g., "60-70% choose do_nothing") were removed from
household prompts because they are methodologically unsound: real agents cannot observe
global population statistics. They were replaced by a **Default-Override + Waterfall**
structure informed by a 3-expert panel (behavioral, water resources, LLM engineering).

**Key design principles:**
1. **Default-Override**: `do_nothing` declared as explicit default; alternatives require
   passing a 3-gate filter (urgent? affordable? worth the disruption?)
2. **Experiential barriers over descriptive norms**: Instead of "only 3-12% elevate,"
   the prompt describes concrete PRB obstacles (permits, contractor scarcity, grant competition)
3. **PRB-specific feasibility barriers for elevation**:
   - Local building permit + NJDEP flood hazard permit (3-6 months)
   - Specialized contractors (fewer than 12 firms in northern NJ, 12-24 month backlogs post-flood)
   - Federal grants (HMGP/FMA) are competitive, 2-5 year timeline, most applicants denied
   - Structural eligibility varies by foundation type (slab-on-grade much more expensive)
   - Temporary relocation required (6-12 months, must continue mortgage payments)
4. **Year-1 cold start**: `get_neighbor_action_summary()` returns an inaction baseline
   ("no neighbors taking major flood protection actions") instead of empty string
5. **Section title**: "YOUR DECISION PRIORITIES" (not "CALIBRATION" — avoids priming
   meta-calibration behavior in small LLMs)

**Literature grounding:**
- Status quo bias: Samuelson & Zeckhauser (1988)
- Present bias / hassle costs: O'Donoghue & Rabin (1999), Bertrand et al. (2006)
- Flood insurance lapse: Gallagher (2014), Michel-Kerjan et al. (2012)
- NFIP elevation barriers: FEMA P-312, Xian et al. (2017)
- RLHF action bias in small LLMs: documented in gemma3:4b behavior (50.3% elevation
  without quantitative anchors vs 3-12% empirical)

### Calibration History

| Version | Prompt Style | Owner do_nothing | Renter do_nothing | Renter ins | Elevation | Notes |
|---------|-------------|-----------------|-------------------|------------|-----------|-------|
| v5 | Hardcoded % | ~35% | — | — | ~10% | EPI=0.78 but methodologically unsound |
| v6 dequant | Qualitative ("small minority") | 0% | — | — | 62.7% | Too weak for 4B model |
| v7 | Default-Override + barriers | 57% | 33.5% | 66.5% | 1.0% | Renter ins too high ("most practical option" = directive) |
| v7b | Stronger do_nothing + remove gate | 96.5% | 96.5% | 3.5% | 0.5% | Overcorrected — all agents passive |
| v7c | Owner=v7, Renter=middle ground | 58% | 75% | 25% | 0.6% | EPI=0.58 (elev/buyout too low) |
| **v7d** | **Soften elev/buyout barriers** | **63%** | **70%** | **30%** | **7%** | **EPI=0.6923 PASS — production ready** |

---

## Common Issues

1. **Survey vs Archetypes confusion**: Remember they are separate data sources
2. **L3 validation timing**: Must run BEFORE primary experiment
3. **Census Tract data**: Auto-downloaded from TIGER/Line when generating figures
4. **PRB raster years**: 2011-2023 (13 years), cycles if simulation > 13 years

---

*Last updated: 2026-04-11 — Memory write policy fix deployed; Gemma 4 pivot ready to restart under CLEAN policy via run_gemma4_ma_pivot_clean.bat*
