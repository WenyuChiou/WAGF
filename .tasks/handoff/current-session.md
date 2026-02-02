# Session Handoff — 2026-02-01 (v7 Pipeline & Experiment Session)

## Summary

Major v7 feature implementation, experiment pipeline preparation, and comprehensive code review.
Builds on prior Phase 5 (memory dedup) and Phase 6 (domain-agnostic refactor) sessions.

Key outcomes:
- 4 v7 features committed (reasoning ordering, magnitude, action feedback, reflection)
- All flood B/C results deleted for v7 re-run
- Irrigation v7 running (Year 4+/42 as of writing)
- Code review: 8.5/10, no critical issues
- WRR paper status assessed

All 1283 tests pass.

---

## Git Commits (3 sessions since Jan 28)

### Phase 5: Memory Deduplication
```
bb34af8 refactor(memory): consolidate dual create_memory_engine into single factory
6fa8313 refactor(memory): deduplicate Sensor/SignatureEngine in symbolic_core
f6a0fa5 refactor(memory): deduplicate EMAPredictor — import from canonical source
4261ed3 refactor(memory): remove unused SimpleMemory, SimpleRetrieval, MemoryAwareContextBuilder
```

### Phase 6: Domain-Agnostic Refactor
```
04d86c0 refactor(validators): extract flood checks from broker/ to examples/
5401520 refactor(adapters): move domain adapters from broker/ to examples/
41e93fa refactor(agent_initializer): make AgentProfile domain-agnostic
4a936e3 refactor(reflection): make decision_types configurable, no flood defaults
6d4c5bf refactor(psychometric): make PMTFramework action sets configurable
```

### Phase 7: v7 Features
```
22fe0d6 feat(prompt): reorder to Reasoning Before Rating (先推理，後評分)
a4ac94b fix(validators): make ThinkingValidator extreme_actions configurable
9da168f chore: untrack paper binaries from git, update .gitignore
13ccb4d refactor(magnitude): make magnitude_pct schema-driven, remove irrigation hacks
44237da feat(memory): universal action-outcome feedback for agent reflection
872268d refactor(reflection): make reflection questions configurable from YAML
48f3907 docs: update READMEs for v7 enhancements and clean old results
eab945a feat(flood): port action-outcome feedback to run_flood.py
```

---

## Three Verified v7 Changes

### 1. Reasoning Before Rating
`reasoning` field placed FIRST in `response_format.fields` across all 3 primary configs:
- `examples/single_agent/agent_types.yaml`
- `examples/governed_flood/config/agent_types.yaml`
- `examples/irrigation_abm/config/agent_types.yaml`

Multi-agent institutional agents (government, insurance) in `examples/multi_agent/flood/config/agents/agent_types.yaml` still have decision-first (out of scope — different cognitive model).

### 2. Schema-Driven magnitude_pct
Full pipeline verified:
```
LLM Output → model_adapter.parse_output() [SkillProposal.magnitude_pct]
  → skill_broker_engine.process_step() [validation_context["proposed_magnitude"]]
  → Validators check constraints
  → _build_approved_skill() [ApprovedSkill.parameters["magnitude_pct"]]
  → experiment._apply_state_changes() [agent._last_action_context["magnitude_pct"]]
  → Domain post-hooks use for feedback
```
- Extraction: `model_adapter.py:359-371` — JSON extraction, negative rejection, 100% clamp
- Injection: `skill_broker_engine.py:210-213` → validation_context
- Approval: `skill_broker_engine.py:578-579` → ApprovedSkill.parameters
- Rejection: `skill_broker_engine.py:611-613` → magnitude cleared, `magnitude_fallback=True`
- Only irrigation uses magnitude (flood has binary decisions)
- gemma3:4b outputs 0% magnitude → falls back to persona defaults (20/10/5%)

### 3. Reflection Module
- `generate_batch_reflection_prompt(reflection_questions=...)` in `reflection_engine.py:515-554`
- Questions loaded from YAML in both irrigation and flood runners
- `_last_action_context` stored by `ExperimentRunner._apply_state_changes()`
- Flood `run_flood.py` now has action feedback (commit `eab945a`)
- Irrigation `run_experiment.py` has full action+outcome feedback with magnitude

---

## Experiment Status

### Irrigation v7
- **Status**: RUNNING (Year 4+/42 as of session)
- **Config**: gemma3:4b, 78 CRSS agents, 42 years, strict governance, humancentric memory
- **Output**: `examples/irrigation_abm/results/production_4b_42yr_v7/`
- **Verified**: action feedback ✅, real CRSS data ✅, governance ✅, reflection ✅
- **No restart needed** — all v7 code was in place before run started

### Flood JOH_FINAL

| Model | Group A | Group B | Group C |
|-------|---------|---------|---------|
| gemma3_4b | ✅ 1001 lines | DELETED | DELETED |
| gemma3_12b | ✅ 1001 lines | DELETED | DELETED |
| gemma3_27b | ✅ 1001 lines | DELETED | DELETED |
| ministral3_3b | ✅ 1001 lines | DELETED | DELETED |
| ministral3_8b | ✅ 1001 lines | DELETED | DELETED |
| ministral3_14b | ✅ 1001 lines | DELETED | DELETED |

### Run Queue
Script: `examples/single_agent/run_flood_BC_v7.ps1`
- 12 sequential experiments (6 models × 2 groups)
- Order: gemma3:4b → 12b → ministral-3:3b → 8b → 14b → gemma3:27b
- **No `--use-priority-schema`** for any group
- Common params: --years 10 --agents 100 --workers 1 --seed 42 --num-ctx 8192 --num-predict 1536

---

## WRR Paper Status

**Title**: "SAGE: A Governance Middleware for LLM-Driven Agent-Based Models of Human–Water Systems"
**Target**: Water Resources Research (WRR), Technical Reports: Methods

### Structure
7 sections, 4 main figures, 3 SI figures
- Fig 1: Architecture diagram ✅
- Fig 2: Flood governance 3-panel (adoption + entropy + R_H) ✅
- Fig 3: Cross-model EBE scaling — BLOCKED on flood B/C re-runs
- Fig 4: CRSS comparison — BLOCKED on irrigation v7 completion

### Key Metrics
- EBE (Effective Behavioral Entropy) = H_norm × (1 - R_H)
- Baseline: 33% hallucination rate → <2% with SAGE
- EBE 32% higher with full cognitive architecture

### Known Data Issues
- EBE text in paper draft doesn't match tables
- N denominator inconsistency between figures
- Will fix after all experiments complete

---

## Code Review (2026-02-01)

**Score: 8.5/10** — No critical issues

| ID | Severity | Issue | Status |
|----|----------|-------|--------|
| W1 | Low | No integration tests for run_flood.py pipeline | Noted |
| W2 | Low | single_agent/agent_types.yaml missing `reflection.triggers` | FIXING this session |
| W3 | Low | ~100 lines duplicated between run_flood.py and governed_flood/run_experiment.py | Noted |
| W4 | Info | run_flood.py is 1239 lines (monolithic) | Noted |

---

## Key Files

| File | Role |
|------|------|
| `examples/single_agent/run_flood.py` | Main flood runner (ALL JOH experiments), 1239 lines |
| `examples/single_agent/run_flood_BC_v7.ps1` | v7 re-run script for 12 flood B/C experiments |
| `examples/governed_flood/run_experiment.py` | Simplified flood demo, 490 lines |
| `examples/irrigation_abm/run_experiment.py` | Irrigation runner with full magnitude support |
| `broker/core/skill_broker_engine.py` | Core governance pipeline |
| `broker/adapters/model_adapter.py` | LLM output parsing (magnitude extraction) |
| `broker/core/experiment.py` | ExperimentRunner base (state application) |

---

## Next Steps

1. ~~Assess irrigation v7 restart~~ → No restart needed
2. Fix README.md (5 corrections)
3. Sync reflection.triggers to single_agent config (W2 fix)
4. Run tests, git commit
5. Wait for irrigation v7 to complete
6. Run flood B/C v7 via `run_flood_BC_v7.ps1`
7. After all experiments: generate Figs 3, 4, S3
8. Update paper DOCX with corrected data
