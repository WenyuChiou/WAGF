# Independently verified facts (Claude direct, 2026-07-28)

These were verified by reading code/data directly, NOT via subagent. Use as ground truth
to cross-check the workflow output.

## Dataset scale (verified by counting every audit CSV)
| Family | runs | decision rows |
|---|---:|---:|
| single_agent (flood, Paper 1b) | 117 | 156,705 |
| multi_agent/flood (Paper 3) | 178 | 140,912 |
| irrigation_abm (Paper 1b) | 41 | 134,316 |
| governed_flood | 1 | 115 |
| cat_model (coupling) | 7 | 25 |
| reservoir_control (coupling) | 2 | 8 |
| quickstart | 1 | 2 |
| **TOTAL** | **347** | **432,083** |

Command used: walk `examples/`, count lines-1 of every `*governance_audit.csv`.
CAVEAT: includes smoke/pilot/quarantined runs — a paper-grade subset will be smaller.
Must be filtered before any headline "N decisions" claim.

## Audit trace schema (~60 cols) — the dataset asset
Per decision row: `proposed_skill`, `final_skill`, `status`, `retry_count`,
`failed_rules`, `rules_triggered`, `validated`, `fallback_activated`,
construct labels (`construct_WSA_LABEL`, `construct_ACA_LABEL` / TP/CP for flood),
free-text appraisal reasoning (`reason_water_scarcity_assessment`,
`reason_adaptive_capacity_assessment`), memory retrieval (`mem_*`),
social signals (`social_*`), cognitive (`cog_*`), `raw_output`, `prompt_tokens`.
=> Each row is a PAIRED (stated appraisal, proposed action, validator verdict, retry,
executed action) record. This is the strongest benchmark/dataset asset.

## Paper-grade experiment matrix (verified by directory + CSV enumeration)

### Irrigation (78 CRSS agents x 42 yr = 3,276 decisions/run), 41 runs
| model | strict seeds | disabled seeds |
|---|---|---|
| gemma3:4b (default dirs) | 42,43,44,45,46 | 42,43,44,45,46 |
| gemma3:12b | 42,43,44 | 42,43,44 |
| gemma4:e2b | 42,43,44,45,46 | 42,43,44,45,46 |
| gemma4:e4b | 42,43,44,45,46 | 42,43,44,45,46 |
| ministral3:8b | 42,43,44 | 42,43 (**seed44 MISSING**) |

### Single-agent flood (JOH_*), ~91 runs — 9 model configs x 2 arms x 5 seeds
| dir | model | runs | rows |
|---|---|---:|---:|
| JOH_FINAL_v2 (strict) | gemma4:26b / e2b / e4b | 5 / 5 / 5 | 4,999 / 4,019 / 4,921 |
| JOH_ABLATION_DISABLED_v2 | gemma4:26b / e2b / e4b | 5 / 5 / 5 | 5,000 / 3,755 / 4,907 |
| JOH_FINAL (strict) | gemma3:4b/12b/27b, ministral3:3b/8b/14b | 5 each (3b=6) | 4,468 / 4,840 / 4,989 / 16,428 / 4,195 / 4,634 |
| JOH_ABLATION_DISABLED | same 6 | 5 each | 4,786 / 4,890 / 4,984 / 3,755 / 4,440 / 4,448 |

=> Headline scale claim available TODAY: **9 LLM configurations spanning ~3B-27B, x 2 governance
   arms, x 5 seeds** on flood; **5 configurations x 2 arms x 3-5 seeds** on irrigation.
   That is a genuinely strong cross-model base for an empirical/analysis paper.
ANOMALY to check: ministral3:3b in JOH_FINAL has 6 runs / 16,428 rows vs ~4-5k for every other
   cell. MEMORY.md flags ministral3_3b as PRE-F1 partial data (65-73% complete). Exclude or
   re-run before using.
GAP: the third arm (WARNING-only) is missing from EVERY cell. That is the P0 run.

## Governance severity model — VERIFIED
`docs/modules/governance_core.md:148-159`:
- ERROR -> `valid=False`, blocks, triggers retry (max 3), message fed back as System-2 feedback.
- WARNING -> `valid=True`, executes anyway, logged to `warnings[]` + `warning_rules` CSV col.
Implementation: `base_validator.py`, `validate()` sets `valid = not is_error`.

## *** THE HEADLINE CLAIM HAS NO CONTROLLED DATASET *** (P0 blocker)
The in-house claim "WARNING rules = 0% behavior change for small LLMs" is a lab lesson,
NOT a controlled ablation. Verified:
- No `relaxed_*` result directory exists in `examples/irrigation_abm/results/` or
  `examples/single_agent/results/`. Only governed(strict) + ungoverned(disabled).
- => The single most defensible contribution per the June-2026 novelty assessment
  is currently UNSUPPORTED BY DATA.

## Two concrete blockers to running that experiment cleanly

### Blocker 1 — irrigation runner hardcodes the profile
`examples/irrigation_abm/run_experiment.py:666` -> `.with_governance("strict", ...)`
There is NO `--governance` CLI flag. `--pilot-phase {A,B,C,D}` only toggles EXTRA
validators (`ENABLE_CONSECUTIVE_CAP`, `ENABLE_ZERO_ESCAPE`); its help text still says
"A=baseline, B=BLOCK+retry" but line 485 shows those were merged into agent_types.yaml
— the A/B enforcement contrast is NOT runnable today. Needs a small patch.
Flood is fine: `run_flood.py:1320` already exposes
`--governance-mode {strict,relaxed,disabled,strict_no_etb}` and wires it at line 1202.

### Blocker 2 — `relaxed` is NOT a severity-only mirror (CONFOUND)
Running `--governance-mode relaxed` today would confound RULE-SET change with SEVERITY change.

Flood (`examples/single_agent/agent_types.yaml:340-395`):
- strict = 4 thinking rules (extreme_threat_block ERROR, low_coping_block WARNING,
  relocation_threat_low ERROR, elevation_threat_low ERROR) + 1 identity rule ERROR.
- relaxed = 1 thinking rule (unnamed, `when_above:["H"]` not `["H","VH"]`, WARNING)
  + 1 identity rule WARNING. Three rules DROPPED and one condition CHANGED.

Irrigation (`examples/irrigation_abm/config/agent_types.yaml:332-405`):
- strict = 3 thinking (1 WARNING + 2 ERROR) + 2 identity ERROR.
- relaxed = 1 thinking WARNING (different id + threshold) + 1 identity WARNING.

FIX (cheap, ~30 min): add a new profile `strict_warning` = byte-for-byte copy of `strict`
with every `level: ERROR` -> `level: WARNING`, same ids/conditions/blocked_skills/messages.
Then the ladder is clean:
  strict          = same rules, ERROR, blocks + retries
  strict_warning  = same rules, WARNING, logs only, never blocks, never retries
  disabled        = no thinking rules
Only the ENFORCEMENT varies. This is the experiment the whole paper rests on.

## *** "Ungoverned" is NOT ungoverned *** (must be stated precisely)
`ungoverned_v21_42yr_gemma4_e4b_seed42/governance_summary.json`:
  total_interventions=224, all `precondition_violation`, retry_success=176, retry_exhausted=48.
The `disabled` profile empties `thinking_rules` + `identity_rules` but HARD/physical
preconditions still fire and still retry. So the existing contrast is
"with vs without BEHAVIORAL-THEORY rules", holding hard feasibility constant.
That is actually a CLEANER claim — but the paper must say it, or a reviewer catches it.

Governed same seed/model: total_interventions=4,423
  (high_threat_high_cope_no_increase 2,763 / low_threat_no_increase 1,660),
  retry_success=521, retry_exhausted=556, warnings total=34
  (high_threat_no_maintain, the one WARNING rule) on 3,276 decisions.
NOTE: 34 WARNING triggers is a tiny natural sample but it is the ONLY existing
WARNING-arm evidence in the whole corpus.

## *** AUDIT-TRACE BLIND SPOT: the rejected first proposal is NOT persisted *** (P0, sequencing-critical)
Verified by direct counting, CSV **and** raw JSONL, all three domains:
| corpus | n | proposed != final | retry_count dist |
|---|---:|---:|---|
| irrigation gov (e4b s42-4x) | 16,380 | **0 (0.00%)** | rc3=10,241 rc1=2,460 rc0=2,206 rc2=1,473 |
| flood SA gov (JOH_FINAL_v2 e4b) | 4,921 | **0 (0.00%)** | rc0=4,510 rc1=312 rc2=61 rc3=38 |
| MA flood (paper3 e4b clean, household) | 15,600 | **0 (0.00%)** | rc0=14,367 rc1=958 rc2=160 rc3=115 |
Raw JSONL same story: `skill_proposal.skill_name` == `approved_skill.skill_name` on 3,276/3,276
records despite retry_count=3 on 2,113 of them.

=> `proposed_skill` records the **last (post-retry) proposal**, not the first. The first-attempt
   proposal is nowhere in the artifacts.
CONSEQUENCE A (good): validates the MEMORY.md "EXECUTED-ONLY" rule — there is no
   proposed-vs-executed asymmetry, so IBR/EHE on the executed distribution are sound.
CONSEQUENCE B (bad, for an AI venue): the most compelling narrative for an ML audience —
   "the validator rejected the agent's choice and it switched to a different action, X% of
   the time" — is **NOT RECOVERABLE** from existing data. Any metric defined as
   proposed != final is degenerate (identically 0).
   `examples/single_agent/results/JOH_FINAL/nw_table_stats.py:195-196` already half-noticed
   this ("If governance_intervention is False for all, then proposed == final").
   `run_flood.py:459` computes `governance_intervention = proposed_skill != skill_name`
   => always False. Any downstream use of that flag is dead.
   SAFE alternative already in use: `compute_ibr.py:405-408` derives the intervention rate
   from `status` (REJECTED / REJECTED_FALLBACK), not from proposed!=final. That path is fine.

PARTIAL RECOVERY: `validation_issues` in the raw JSONL ACCUMULATES across retry attempts.
Worked example (irrigation, retry_count=3): final proposal `decrease_small`, but
validation_issues lists `curtailment_awareness` + `high_threat_high_cope_no_increase`
(both block *increases*) alongside `demand_floor_stabilizer` (blocks the decrease).
=> the agent proposed an INCREASE earlier, got blocked, switched to a DECREASE, got blocked
   again, exhausted retries. The rejected trajectory's action CLASS is inferable from the
   rule-trigger set, though not the exact skill.

*** ACTION (must happen BEFORE the 2-3 week GPU run) ***: patch the audit writer to persist
`initial_proposal` (first-attempt skill + first-attempt appraisal labels) and a per-attempt
list. Otherwise the NEW experiments inherit the same blind spot and the headline
"enforcement changes behavior" claim stays unmeasurable at the decision level.
This is the single most important sequencing constraint in the whole plan.

## *** CONFIRMED: REJECTED rows label a BLOCKED PROPOSAL as if it executed *** (affects Paper 1b too)
Independently verified by me (not agent-reported). Method: read raw JSONL, sort by (agent, year),
compare each record's `execution_result.state_changes.request` against that agent's previous request,
and cross-tab the ACTUAL movement against the labelled skill.
Corpus: `production_v21_42yr_gemma4_e4b_seed42`, 3,276 records (1,900 REJECTED / 1,376 APPROVED).

| status | labelled skill | ACTUAL request movement |
|---|---|---|
| APPROVED | maintain_demand | UNCHANGED 820 |
| APPROVED | decrease_small | DECREASED 264 |
| APPROVED | increase_large | INCREASED 116 |
| APPROVED | increase_small | INCREASED 80 |
| APPROVED | decrease_large | DECREASED 53 |
| **REJECTED** | decrease_small | **UNCHANGED 676** |
| **REJECTED** | increase_small | **UNCHANGED 586** |
| **REJECTED** | increase_large | **UNCHANGED 393** |
| **REJECTED** | decrease_large | **UNCHANGED 210** |

APPROVED rows: label matches reality perfectly (100%).
REJECTED rows: **100% UNCHANGED, 1,865/1,865** — the blocked proposal NEVER executed; the default
(maintain) ran instead, exactly as MEMORY.md's "REJECTED fallback executes the default skill" says.
The FRAMEWORK BEHAVED CORRECTLY. The defect is purely in MEASUREMENT: the audit CSV writes the
blocked proposal into `final_skill`/`yearly_decision` instead of the executed default.

ARITHMETIC CHECK that this is the source of the published number:
  blocked "increase" proposals = 586 + 393 = 979; executed increases = 80 + 116 = 196.
  counting blocked as executed -> (979+196)/3276 = 35.9%  <-- matches the published governed
  IBR of 36.05% almost exactly. Executed-only -> 196/3276 = 6.0% unconditional.
=> The published "governed IBR 36.05%" is a PROPOSAL-STAGE rate mislabelled as executed.

*** GOOD NEWS — the DIRECTIONAL claim survives ***: the workflow's recomputation gives
0.96% governed vs 25.32% no-validator (executed, conditional). Delta = 24.4pp, versus the
published delta of ~23-25pp. So "validators sharply reduce boundary-violating behaviour" HOLDS;
only the LEVELS are wrong. The no-validator arm is barely affected because it has few rejections
(224 interventions, almost all precondition-type).
ACTION: recompute every IBR/EHE level on the executed action for BOTH the conference paper AND
Paper 1b / Nature Water, and re-check the SI. Report the delta, which is robust.
CAVEAT: I verified irrigation e4b seed42 only. Re-run this cross-tab per model/seed/domain before
trusting any specific corrected number. The flood domain has far fewer rejections (23/4,921) so the
distortion there is small; irrigation is the badly affected one.

## Two more artifact defects found in passing
- `rule_breakdown` is `{personal:0, social:0, thinking:0, physical:0, semantic:0}` on a record
  that demonstrably triggered 3 rules => the counters are never populated. Dead field.
- For `outcome=REJECTED` rows, `approved_skill.skill_name` is still the last ATTEMPTED skill
  while `status=REJECTED`; the actually-executed action is the domain default/fallback
  (MEMORY: "REJECTED fallback: execute default skill, not no-op"). So `final_skill` is NOT
  the executed action on rejected rows. Executed truth lives in `simulation_log.csv`
  `yearly_decision`. This is exactly why the EXECUTED-ONLY rule exists — keep obeying it,
  and state it explicitly in the paper's metric definitions.

## Retry-count confound (not yet controlled — needs a 4th arm)
strict makes MORE LLM calls than strict_warning (retries). So a strict-vs-warning
difference could be "more sampling" rather than "theory-coherent feedback".
Control needed: a SHAM/PLACEBO validator arm — blocks + retries at a MATCHED rate but
with rule content that is irrelevant/scrambled. If strict beats sham, enforcement content
matters; if sham == strict, the effect is just resampling. This is the single most
likely ML-reviewer kill shot and is cheap to run.

## Run cost (for scheduling)
irrigation: 78 agents x 42 yr = 3,276 decisions/run.
reproducibility_manifest.json records model/seed/governance_profile/git_commit/config_hash
(good provenance) but NOT wall-clock. Memory notes put a gemma3:4b backfill at ~3 h.
Estimate ~2-4 h/run on RTX 4080 SUPER + Ollama.
=> New WARNING arm only (strict + disabled already exist):
   1 arm x 3-5 models x 5 seeds = 15-25 runs x ~3 h ~= 45-75 GPU-h ~= 2-3 days continuous.
   Adding a sham arm doubles it -> ~4-6 days. Both fit the user's 2-3 week budget.

## Coupling layer — v0.6 shipped, contract enforcement is REAL
`broker/coupling/contract.py` raises on: unknown reduce, empty sub-step series, bad
cadence/direction/on_missing enum, numeric var without unit, lo>hi, observation not
world_to_agent, input not agent_to_world.
Negative-control-style tests EXIST in `broker/tests/test_coupling_contract.py`:
  test_double_count_construction_raises, test_double_count_fixed_by_marking_one_diagnostic,
  test_varspec_range_violation, test_check_direction_lookup,
  test_check_cadence_requires_explicit_reduce_when_cadences_differ,
  test_adapter_advance_step_fails_loud_on_out_of_range, test_varspec_numeric_requires_unit.
=> The June-2026 assessment's contingent requirements #1 and #3 look SHIPPED.
   #2 (>=3 heterogeneous couplings incl. continuous control) — cat_model +
   reservoir_control + reservoir_control_multidim exist, BUT the coupling result dirs hold
   only 25 + 8 decision rows total => these are smoke-scale, NOT experiment-scale.
   reservoir_control_multidim is self-described in README as "Mock-validated skeleton;
   real-LLM run + baseline pending". So coupling is DEMONSTRATED, not EVALUATED.

## Paper 3 (multi-agent) is mid-redesign — NOT conference-ready as a headline
From `.research/`:
- `institutional_realism_verdict_2026-06-29.md`: VERDICT NO — the de-locked institutional
  agent is an unrealistic protective RAMP; real flood institutions are sticky (~0-3 changes
  in 13 yr, not 13). 3 confirmed prompt/mechanics bugs (a prompt fiction about budget
  collapse that is unimplemented; ~2x cost understatement; budget charges the raise not the
  outlay). Benchmark bands [3,8]/[1,5]/[1,5] are UNCITED designer priors — tuning to them
  is explicitly flagged as a cheating trap.
- `paper3_12b_headline_decision_2026-06-16.md`: headline model switched e4b -> 12b because
  e4b over-protects (SFHA insurance 0.776 vs band 0.30-0.60). The DECISIVE matched-forcing
  run (A2) is STAGED BUT NOT LAUNCHED. Also: validators were ACTIVE-BUT-NON-BINDING on e4b —
  proposed==final on all 15,600 decisions, model overrode ERROR-level renewal_fatigue 70%.
=> Recommend Paper-3 material be used as a SECONDARY/qualitative section at most, or held
   back entirely. Its institutional layer would not survive an application reviewer.
   NOTE the "validators active-but-non-binding, proposed==final on 15,600 decisions" datum
   is itself potentially a strong NEGATIVE result worth reporting honestly.

## Governance profiles: custom names ARE allowed — RESOLVED, fix is cheap
`broker/config/schema.py:364-370` — `GovernanceProfiles` declares strict/relaxed/disabled
BUT carries `model_config = ConfigDict(extra="allow")`, and `GovernanceProfile` likewise.
Proof by existence: `strict_no_etb` is already used in the flood config and runs fine.
=> Adding a `strict_warning` profile is a PURE YAML ADDITION. No schema patch needed.

Total P0 enabling work (small, ~1-2 h):
1. flood `agent_types.yaml`: add `strict_warning:` = copy of `strict` with ERROR->WARNING.
2. flood `run_flood.py:1320`: add `"strict_warning"` to the `--governance-mode` choices list.
3. irrigation `agent_types.yaml`: same `strict_warning` addition.
4. irrigation `run_experiment.py`: expose `--governance-mode` and replace the hardcoded
   `.with_governance("strict", ...)` at line 666 with the arg.
5. (for the sham arm) a `strict_sham` profile: same rule COUNT and same trigger RATE,
   ERROR level, but conditions rewired to a behaviorally irrelevant construct so the
   block+retry happens without carrying theory-coherent information.
   NOTE: matching the trigger rate takes a calibration pass — do a dry run and tune.
