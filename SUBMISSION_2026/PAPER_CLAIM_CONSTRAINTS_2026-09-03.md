# Claim constraints from the framework audit and the 9-PR stack (2026-09-03)

Not paper prose. A ledger of what the code on `main` (`e0eee08c`) can and cannot
support, written so the paper never asserts more than the artifact does. Each
row names the file that makes the constraint checkable. Read this before drafting
any sentence about governance, coupling, calibration, deciders or ablation.

Source: `.research/framework_publication_readiness_2026-08-31.md` (13-agent
audit + two referee reports; gitignored, local) and the review history recorded
in the nine commit messages `b79e49ee..27f0d161` (now merged as PRs #26–#34).

## 1. What the published numbers are

| Constraint | Where it is enforced / documented |
|---|---|
| The published NW pair (irrigation 36.05 / 59.07, flood 0.87 / 7.41) is reproduced from the frozen corpus by `reproduction/`; every flag added by the stack is default-OFF and the mock recipes are byte-identical to the pre-stack baseline (sha256 551f7c99… / 5f485d3f…). The published 8.5 for flood is not the frozen-corpus value: per `SUMMARY.md`, "The published 8.5 reproduces only from the PRE-QUARANTINE no-validator arm (quarantined Run_1-3 + live Run_4-5). The live corpus gives 7.41". **(corrected 2026-09-22)** | `reproduction/README.md`; `broker.tools.compare_audit_csv`; clean-clone gate 2026-09-03; `SUBMISSION_2026/reviewer_prep_2026-09-05/out/SUMMARY.md` |
| `final_skill` / `yearly_decision` in the released corpus hold the **last proposal after retries**, not what executed; on REJECTED rows the registry default ran. The executed-column view gives irrigation 0.86 / 26.77. Report the headline as proposal-level or state the remap rule. | `metrics_definitions.md`; `docs/AUDIT_SCHEMA.md` known-limitation table; `audit.corrected_status_columns` (new runs only) |
| The IBR denominator (`WSA_LABEL ∈ {H,VH}` / `TP_LABEL`) is a post-treatment self-report. The design-fixed companion estimator is the unconditional −21.62 pp (CI [−26.80, −16.45]); the 16-cell specification curve exists. | `reproduction/decomposition/e1_total_effect.py`, `e3_decomposition.py` |
| `fallback_activated`, `rules_*_hit`, `mem_top_emotion`, `mem_top_source` are unreliable in every released corpus; ABORTED steps are absent from the CSV. Disclose, never backfill. | `docs/AUDIT_SCHEMA.md` §Known-limitation columns |
| "WARNING-only = 0 % behavioural change" is an architectural identity (a WARNING has no channel to the model), not a measurement. Never cite it. | `broker/core/_advise.py`; deleted from three docs in PR-1 |
| 10.47 % of the TAE gov_seed42 rows were decided by a stray digit at `parse_confidence` 0.95. Disclose the digit share; `parse_layer_digit_share` is a LOWER BOUND on pre-flag corpora. | `parsing.strict_layers` docs in `docs/AUDIT_SCHEMA.md` |

## 2. Governance (hard + soft rules)

| Constraint | Where |
|---|---|
| In every published run the production path constructed ONLY `AgentValidator`; `ThinkingValidator` (and with it every YAML `variable`/`expression` world rule) was **unreachable**. Every binding YAML *thinking* rule conditions on a label the model emitted in the same generation. **Correction 2026-09-06:** this does NOT mean every binding rule was label-conditioned — the Python-level `demand_ceiling_stabilizer` (block increase when basin-wide demand > 6.0 MAF ≈ 1.024 × CRSS target 5.86 MAF) and the identity precondition `water_right_cap` are world/state-conditioned and were the largest blockers in the released irrigation corpus (ceiling rule 1,420 triggers ≈ 80 % of rejections in the seed-42 expert-panel census; the cap precondition blocks 35.4 % of no-validator rows). The circularity critique applies to the label rules (`low_threat_no_increase`, `high_threat_high_cope_no_increase`), not to the whole governed effect. | `examples/irrigation_abm/validators/irrigation_validators.py:736-788`; `examples/irrigation_abm/config/agent_types.yaml` strict profile; `SUBMISSION_2026/reviewer_prep_2026-09-05/out/r3_rule_firing_census.csv` |
| `grounded_v1` (one world-conditioned ERROR rule per reference domain) is a **new** capability with no published run behind it. Any number from it is a new result. | `examples/single_agent/agent_types.yaml`, `examples/irrigation_abm/config/agent_types.yaml`; `docs/guides/governance_layers.md` |
| The irrigation grounded rule tests whether the model **used a drought index the prompt already quotes** — weaker than a hidden-variable contradiction; not tautological (compute_wsa_label feeds only the FQL baseline). | `governance_layers.md` §grounding |
| The soft channel (`governance.advise_mode`) holds blocking constant by construction: an invalid post-advice proposal is discarded and recorded. "Advice never blocks" is true only in that precise sense. | `broker/core/_advise_pass.py` docstring; `governance_layers.md` §Advice never blocks |
| Theory genericity is true at registration and, under `validators.framework_aware_labels`, at label resolution; OFF, a non-VL..VH alphabet (`financial`) truncates to "AG"/"CO" and never fires. Do not claim "swap PMT for TPB" beyond what a flag-ON run shows. | `broker/validators/agent/agent_validator.py` `get_label` |
| The irrigation drought threshold 0.08 was derived from the environment's own distribution (max 0.16 over 42 yr); two other thresholds on the same variable exist and are not cross-referenced. | irrigation `agent_types.yaml` comment; `governance_layers.md` |

## 3. Coupling

| Constraint | Where |
|---|---|
| The four contract checks (unit / cadence / direction / double-count) are enforced at **construction** (direction, double-count) and structurally (unit declared, lo ≤ hi). At **runtime** under `coupling.context_contract` the irrigation path enforces presence + finite numeric range + dtype ONLY; `check_units()` / `check_cadence()` are never called there and no unit conversion is verified. Do not attribute all four to the irrigation runtime. | `examples/irrigation_abm/irrigation_coupling.py` docstring; `docs/COUPLING_CONNECTORS.md`; `yaml_configuration_reference.md` §2.1.8 |
| Every published irrigation run bypassed the contract and defaulted fifteen physical-state fields to 0. `VarSpec.range_violation` was NaN- and type-blind until PR-9. Pre-stack "contract-validated" covered absence only. | `broker/coupling/contract.py`; PR-9 commit message |
| `upper_basin` never carries `lake_mead_level`; `lower_basin` never carries `precipitation` (deliberate). An upper-basin consumer reading `ctx["lake_mead_level"]` without the basin gate sees 0. | `_BASIN_SCOPED_FIELDS` in `irrigation_coupling.py` |
| Archetype C exists as a subprocess connector with a worked example; REST is deferred. | `broker/coupling/subprocess_source.py`; `examples/coupling_examples/archetype_c_subprocess/` |
| Evidence a reviewer should be pointed at: `coupling_contract_active` **and** `coupling_guard_calls` in `run_integrity.json`, not the YAML flag. | `run_integrity.json` keys |

## 4. Calibration / validation

| Constraint | Where |
|---|---|
| Two EPI formulas: paper3 hard-range (`paper3_l2_hard_range_v1`, canonical, the one that ran) vs generic tolerance-expanded pass rate (`legacy_epi_v1`): 0.7049 vs 0.8689 on one fixture. Never report an EPI without `formula_version`. | `docs/guides/calibration_guide.md` §Two EPI formulas |
| The two benchmark tables disagree on **six** metrics that share the same name (`buyout_rate`, `elevation_rate` [0.03,0.12] vs [0.10,0.35], `insurance_lapse_rate`, `insurance_rate_all`, `insurance_rate_sfha`, `mg_adaptation_gap`). **Correction 2026-09-06:** call it **seven** only if `rl_uninsured_rate` (table A) vs `renter_uninsured_rate` (table B) is also counted — same numeric range (0.15–0.40) but a different population (repetitive-loss households vs renters), i.e. a naming mismatch rather than a value disagreement in the same sense as the other six. Unreconciled — a human decision. | `broker/calibration/benchmark_diff.py` (`python -m` prints the table); `SUBMISSION_2026/reviewer_prep_2026-09-05/out/r8_flood_vs_benchmarks.csv` (`table_vs_table` rows, verified 2026-09-06) |
| The parametric calibration result is **not an estimate**: three aggregate metrics cannot identify four base rates (ordering comes out behaviourally backwards), and a larger budget over-fits (held-out 0.40 @ 40 evals → 1.58 @ 253). `calibration_result.json` carries both warnings. | `examples/multi_agent/flood/parametric/calibrate_parametric.py`; the JSON `warnings` list |
| No out-of-sample validation of any LLM run exists. The optimizer's held-out split is for parametric deciders. | `calibration_guide.md` |

## 5. Deciders / mixed populations

| Constraint | Where |
|---|---|
| Rule-based / hybrid / LLM agents share governance, retry and audit. The parametric arm's `TP_LABEL`/`CP_LABEL` are a deterministic transform of survey Likert scores the LLM arm never sees; comparing construct-label distributions across deciders compares a measurement artifact with a self-report. | `docs/guides/mixed_populations.md` §3 |
| Non-LLM rows carry fabricated-looking `llm_calls`/`llm_success`/token/`mem_*` columns; filter on `decider` before averaging. Blocked deterministic agents retry once. | `mixed_populations.md` §7; `docs/AUDIT_SCHEMA.md` |
| Social topology per agent type is deferred; `MessagePool`/`GameMaster` have no producers. | `mixed_populations.md` §8; PR-1 STATUS notes |

## 6. Ablation / intervention

| Constraint | Where |
|---|---|
| Fidelity is `prompt_only`: traces store the rendered prompt, not the per-provider context; masking is string substitution. | `broker/experiments/replay.py`; `docs/guides/ablation_guide.md` |
| ΔP is withheld unless the backend is deterministic on real decisions; local Gemma is not (Phase 6R-D-4). Every effect field nulls together. Wilcoxon needs ≥ 8 non-tied pairs. | `broker/experiments/ablation.py` `EFFECT_FIELDS`, `MIN_PAIRS` |
| Governance replay requires `--validators-module` AND traces that record `available_skills` (not recorded today) — effectively unavailable until the audit writer adds it. | `ablation_guide.md` refusals table |
| Seeds are recorded as NOT applied for every backend `create_llm_invoke` exposes today. | `ablation_guide.md` |

## 7. Repo / provenance

| Constraint | Where |
|---|---|
| `main` is framework-only; submission workspaces (`SUBMISSION_2026/`, `ICLR2027/`) live on `p0-1-governance-instrumentation` and are never merged. | user decision 2026-08-21 |
| The survey PII purge rewrites every SHA in this ledger's provenance; after it, cite commits by the rewritten map (`filter-repo/commit-map`). | `P0_1_PII_PURGE_RUNBOOK.md` |
| `examples/multi_agent/flood/parametric/` on `main` (PR-7/8) supersedes the monkeypatch version on this branch; `--mixed-population` + `ma_agent_types_mixed_population.yaml` replaces `_install_parametric_household_decider()`. | PR-8 commit message |

## 8. Corrections log

| Date | Section | What changed |
|---|---|---|
| 2026-09-06 | §2 | Corrected the claim that every binding YAML thinking rule in the released corpus was label-conditioned: the Python-level `demand_ceiling_stabilizer` and the `water_right_cap` precondition are world/state-conditioned and were the largest blockers in the released irrigation corpus; the circularity critique applies only to the label rules. |
| 2026-09-06 | §4 | Corrected the benchmark-table disagreement count from "seven" to "six" shared-name disagreements, with a seventh only if the `rl_uninsured_rate`/`renter_uninsured_rate` naming mismatch (same range, different population) is counted too; sourced to `SUBMISSION_2026/reviewer_prep_2026-09-05/out/r8_flood_vs_benchmarks.csv`. |
