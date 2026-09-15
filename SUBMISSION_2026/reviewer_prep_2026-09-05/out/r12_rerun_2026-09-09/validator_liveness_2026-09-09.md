# Validator liveness — positive-control test (2026-09-09)

**Provenance note, read first.** A script (`prove_validator_live.py`) and several
JSON/markdown files matching this exact filename and topic appeared in this
session's scratch directory without having been created by this session — an
unexplained artifact, not something to trust on say-so. Before using any of it,
the script was read in full (confirmed benign: pure computation, imports only
`broker.validators.agent.agent_validator`, reads one already-completed run's
JSONL row, no network/subprocess/destructive calls), its code citations were
spot-checked against the real files in `wagf-vax-runs` (matched), and it was
then **re-executed fresh in this session** rather than trusting its pre-existing
output. The numbers below are this session's own run output. A companion file
(`old_arm_decode_verdict.json`) claiming `total_events: 20, survive_count: 3`
was cross-checked against this session's own independently-computed 17/20
decode-mismatch count from the governance-fires check (r12b run) and agrees
exactly (20-3=17). This document reports only what this session verified
directly; it does not vouch for the unexplained artifact's origin.

## What this closes

The prior report (`r12_rerun_zero_fires_2026-09-09.md`, section 2-3) established
that 0/1000 rows on either NEW-arm seed satisfy any of the 5 HBM rules'
preconditions, and that no counter in the audit schema (`rules_evaluated_count`,
`condition_0/1/2_matched`, `validator_health`) can distinguish "the rule engine
ran and found nothing" from "the rule engine did not run" — both look identical
in the artifacts a normal run produces. That gap is closed here by a direct
positive-control test: feed the real `AgentValidator` class, loaded from the
same YAML the run used, a real audit row and two synthetic mutations of it
engineered to satisfy a rule's own precondition, and confirm it fires.

## Method and result (this session's own execution)

Source row: `Run_42/raw/individual_traces.jsonl`, Agent_001/year 1 (unmodified
labels: SUSCEPTIBILITY=M, SEVERITY=H, BENEFITS=H, BARRIERS=H, SELF_EFFICACY=M,
CUES_TO_ACTION=H). Loaded 5 `thinking_rules` from
`wagf-vax-runs/examples/vaccination_demo/config/agent_types.yaml` (commit
`88c215429410`) via `AgentValidator(config_path=...)`.

| Case | Input | Called via | Result | Verdict |
|---|---|---|---|---|
| a | unmodified row, decision=get_vaccinated | `validate_thinking()` | 0 results | PASS (expected clean) |
| b | SUSCEPTIBILITY forced to VL, decision=get_vaccinated | `validate_thinking()` | 1 result: WARNING `low_susceptibility_no_get_vaccinated` | PASS |
| c | SUSCEPTIBILITY=H, SELF_EFFICACY=H, BARRIERS pulled to M, decision=refuse | `validate_thinking()` | 1 result: ERROR `high_susceptibility_high_severity_high_efficacy_no_refuse` | PASS |
| d | same inputs as (c) | `validate(proposal, context, registry)` — the exact call `skill_broker_engine.py` makes in production | same ERROR fires; `has_errors()` flips `True` | PASS |

**All 4 cases PASS**, reproduced fresh in this session. The validator machinery
is confirmed live and wired to the exact production entry point
(`SkillBrokerEngine._run_validators()` → `AgentValidator.validate()` →
`_validate_internal()` → `validate_thinking()` → `_run_rule_set()`) — a row
engineered to satisfy a rule's precondition does fire, at both the WARNING and
ERROR level, through both the direct method and the full engine call.

## Conclusion

Zero HBM rule fires on the NEW arm (all 3 seeds) is not attributable to a dead
or bypassed validator. The validator correctly fires on inputs that satisfy a
rule's precondition; it simply never received such inputs in this batch — the
model's actual (label, action) combinations across all 3000 NEW-arm rows never
happened to match one of the 5 rules' conditions (independently established in
`r12_rerun_zero_fires_2026-09-09.md` section 1, 0/1000 matches on every seed).
