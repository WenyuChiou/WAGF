# ABM Generalization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor WAGF into a clearer domain-agnostic ABM governance framework while preserving existing flood, irrigation, and paper3 workflows at every checkpoint.

**Architecture:** Keep `broker/` as the stable governance core, treat water/flood/irrigation logic as explicit domain packs, and reposition multi-skill as a bounded composite-action feature rather than a generic planner. Execute the work in short, reversible stages with fresh verification after every stage before any commit or merge.

**Tech Stack:** Python 3.10+, pytest, YAML-driven config, existing broker validators, examples-based regression tests, git commits per checkpoint.

---

## Safety Rules

1. Never refactor `broker/` and `examples/` in the same task unless the task is documentation-only.
2. Every task must end with at least one fresh verification command.
3. If any checkpoint breaks `single_agent/flood`, `irrigation_abm`, or `multi_agent/flood/paper3`, stop and fix before continuing.
4. Do not remove PMT/flood behavior first. Abstract it behind a domain pack boundary, then rename documentation.
5. Multi-skill changes must preserve backward compatibility when `multi_skill.enabled` is false.

## Parallel Expert / Agent Structure

### Agent A: Core Architecture Reviewer

**Scope:** `broker/`, domain boundaries, abstraction seams.

**Deliverables:**
- Inventory of flood- or PMT-centric assumptions inside core modules
- Proposed moves to `broker/domains/water/`
- Risk list for any core refactor

**Primary files:**
- `broker/core/`
- `broker/validators/governance/`
- `broker/utils/agent_config.py`
- `broker/interfaces/`

**Verification commands:**
```bash
python -m pytest tests/test_thinking_validator.py tests/test_rating_scales.py -q
python -m pytest tests/test_agent_config_rating_scale.py tests/test_response_format_builder.py -q
```

### Agent B: Theory Abstraction Reviewer

**Scope:** psychological framework API, theory naming, developer extension path.

**Deliverables:**
- New external terminology: theory pack, construct-action coherence, reference domain pack
- Gap list in docs for adding non-water behavioral theories
- Proposed generic example constructs for a non-flood tutorial

**Primary files:**
- `broker/interfaces/rating_scales.py`
- `broker/validators/governance/thinking_validator.py`
- `docs/guides/experiment_design_guide.md`
- `README.md`

**Verification commands:**
```bash
python -m pytest tests/test_psychometric.py tests/test_thinking_validator.py -q
```

### Agent C: Multi-Skill Reviewer

**Scope:** bounded composite action semantics, execution ordering, audit safety.

**Deliverables:**
- Formal statement of current multi-skill semantics
- Required tests before changing naming or defaults
- Recommendation on whether to keep feature experimental

**Primary files:**
- `broker/core/skill_broker_engine.py`
- `broker/interfaces/skill_types.py`
- `broker/utils/parsing/unified_adapter.py`
- `broker/components/response_format.py`
- `tests/test_multi_skill.py`
- `tests/test_multi_skill_integration.py`

**Verification commands:**
```bash
python -m pytest tests/test_multi_skill.py tests/test_multi_skill_integration.py -q
```

### Agent D: ABM Developer Experience Reviewer

**Scope:** onboarding, examples, minimal templates, non-water extensibility.

**Deliverables:**
- Required doc changes for external ABM developers
- Proposed `examples/minimal_nonwater/` or equivalent generic tutorial
- Public-facing README wording changes

**Primary files:**
- `README.md`
- `examples/minimal/`
- `docs/guides/customization_guide.md`
- `docs/guides/experiment_design_guide.md`

**Verification commands:**
```bash
python -m pytest tests/test_config_schema.py tests/test_context_types.py -q
```

## Execution Stages

### Task 1: Freeze Baseline and Create Regression Gate

**Files:**
- Create: `docs/plans/2026-03-07-abm-generalization-plan.md`
- Create: `docs/checklists/abm_generalization_regression_gate.md`
- Modify: `.ai/PROJECT_STATE.md`
- Modify: `.ai/NEXT_TASK.md`

**Step 1: Write the checklist file**

Include the minimum must-pass checks:
- Provider smoke test
- Flood single-agent reasoning validation tests
- Irrigation config / rating-scale tests
- Multi-skill tests

**Step 2: Run the regression gate**

Run:
```bash
python providers/smoke.py --providers ollama
python -m pytest tests/test_provider_smoke.py tests/test_multi_skill.py tests/test_multi_skill_integration.py -q
python -m pytest tests/test_thinking_validator.py tests/test_rating_scales.py tests/test_agent_config_rating_scale.py -q
```

**Expected:** all selected tests pass; Ollama reports `ready`.

**Step 3: Commit**

```bash
git add docs/plans/2026-03-07-abm-generalization-plan.md docs/checklists/abm_generalization_regression_gate.md
git commit -m "docs: add ABM generalization execution plan"
```

### Task 2: Document the True Core vs Water Pack Boundary

**Files:**
- Modify: `README.md`
- Modify: `docs/guides/experiment_design_guide.md`
- Create: `docs/guides/domain_pack_guide.md`

**Step 1: Write failing documentation acceptance checklist**

Checklist must answer:
- What lives in `broker/`?
- What belongs in `broker/domains/water/`?
- What is a reference experiment vs a reusable module?

**Step 2: Update docs with neutral terminology**

Required wording shifts:
- `PMT` -> reference theory pack where appropriate
- `flood` -> reference domain where appropriate
- `thinking validator` -> theory coherence validation layer

**Step 3: Verify docs do not overclaim**

Run:
```bash
rg -n "PMT-only|flood-only|general planner|fully domain-agnostic" README.md docs/guides broker
```

**Expected:** no misleading claims remain in edited docs.

**Step 4: Commit**

```bash
git add README.md docs/guides/experiment_design_guide.md docs/guides/domain_pack_guide.md
git commit -m "docs: define core and domain pack boundaries"
```

### Task 3: Make Theory Extension a First-Class Developer Path

**Files:**
- Modify: `broker/validators/governance/thinking_validator.py`
- Modify: `broker/utils/agent_config.py`
- Create: `tests/test_framework_registration_generic.py`
- Modify: `docs/guides/domain_pack_guide.md`

**Step 1: Write the failing test**

Create a test that registers a non-water framework with custom constructs and verifies:
- label normalization works
- YAML thinking rules run without PMT-specific assumptions
- framework-specific scale lookup works

**Step 2: Run the test to verify it fails**

Run:
```bash
python -m pytest tests/test_framework_registration_generic.py -q
```

**Expected:** fail on current missing or water-centric assumption.

**Step 3: Implement minimal core changes**

Keep changes narrow:
- remove any remaining PMT-specific fallback in generic paths where unsafe
- preserve PMT as compatibility default only at outer configuration boundary

**Step 4: Run verification**

Run:
```bash
python -m pytest tests/test_framework_registration_generic.py tests/test_thinking_validator.py tests/test_rating_scales.py tests/test_agent_config_rating_scale.py -q
```

**Expected:** all pass.

**Step 5: Commit**

```bash
git add broker/validators/governance/thinking_validator.py broker/utils/agent_config.py tests/test_framework_registration_generic.py docs/guides/domain_pack_guide.md
git commit -m "feat: support generic framework registration path"
```

### Task 4: Reposition Multi-Skill as Bounded Composite Action

**Files:**
- Modify: `broker/interfaces/skill_types.py`
- Modify: `broker/core/skill_broker_engine.py`
- Modify: `broker/utils/parsing/unified_adapter.py`
- Modify: `broker/components/response_format.py`
- Modify: `README.md`
- Modify: `docs/references/yaml_configuration_reference.md`

**Step 1: Write failing tests for missing semantics**

Add tests for:
- secondary execution only runs after primary success
- composite conflict blocks secondary cleanly
- audit output remains backward compatible when feature is off

**Step 2: Run tests to verify red**

Run:
```bash
python -m pytest tests/test_multi_skill.py tests/test_multi_skill_integration.py -q
```

**Expected:** at least one new test fails before implementation.

**Step 3: Implement minimal semantic cleanup**

Do not build a planner. Only:
- document and enforce `max_skills=2`
- clarify sequential composite behavior
- keep current off-by-default default

**Step 4: Verify**

Run:
```bash
python -m pytest tests/test_multi_skill.py tests/test_multi_skill_integration.py tests/test_response_format_builder.py -q
```

**Expected:** all pass.

**Step 5: Commit**

```bash
git add broker/interfaces/skill_types.py broker/core/skill_broker_engine.py broker/utils/parsing/unified_adapter.py broker/components/response_format.py README.md docs/references/yaml_configuration_reference.md tests/test_multi_skill.py tests/test_multi_skill_integration.py
git commit -m "feat: formalize bounded composite action semantics"
```

### Task 5: Add a Non-Water Minimal Reference Example

**Files:**
- Create: `examples/minimal_nonwater/README.md`
- Create: `examples/minimal_nonwater/agent_types.yaml`
- Create: `examples/minimal_nonwater/skill_registry.yaml`
- Create: `examples/minimal_nonwater/run_demo.py`
- Create: `tests/test_minimal_nonwater_config.py`

**Step 1: Write failing config test**

The test must prove:
- a non-water framework can load
- valid actions parse
- response format renders correctly

**Step 2: Run the test to verify it fails**

Run:
```bash
python -m pytest tests/test_minimal_nonwater_config.py -q
```

**Expected:** fail until files exist.

**Step 3: Implement the minimal example**

Use generic constructs such as:
- `RISK_LABEL`
- `CAPACITY_LABEL`

Avoid flood, drought, insurance, or irrigation wording.

**Step 4: Verify**

Run:
```bash
python -m pytest tests/test_minimal_nonwater_config.py tests/test_config_schema.py tests/test_response_format_builder.py -q
python examples/minimal_nonwater/run_demo.py
```

**Expected:** tests pass; demo exits successfully.

**Step 5: Commit**

```bash
git add examples/minimal_nonwater tests/test_minimal_nonwater_config.py
git commit -m "feat: add non-water reference experiment"
```

### Task 6: Full Regression Checkpoint

**Files:**
- Modify: `.ai/SESSION_LOG.md`
- Modify: `.ai/PROJECT_STATE.md`
- Modify: `.ai/NEXT_TASK.md`

**Step 1: Run full checkpoint suite**

Run:
```bash
python providers/smoke.py --providers ollama
python -m pytest tests/test_provider_smoke.py tests/test_multi_skill.py tests/test_multi_skill_integration.py -q
python -m pytest tests/test_thinking_validator.py tests/test_rating_scales.py tests/test_agent_config_rating_scale.py tests/test_response_format_builder.py -q
python -m pytest tests/test_config_schema.py tests/test_context_types.py tests/test_psychometric.py -q
```

**Expected:** all pass.

**Step 2: Smoke test high-value runtime entry points**

Run:
```bash
python -c "from providers.smoke import run_smoke_checks; print([r.status for r in run_smoke_checks(providers=['ollama'])])"
python -c "from broker.utils.agent_config import AgentTypeConfig; cfg=AgentTypeConfig.load('examples/single_agent/agent_types.yaml'); print(cfg.get_framework_for_agent_type('household'))"
python -c "from broker.utils.agent_config import AgentTypeConfig; cfg=AgentTypeConfig.load('examples/irrigation_abm/config/agent_types.yaml'); print(cfg.get_framework_for_agent_type('irrigation_farmer'))"
```

**Expected:** commands complete without exception.

**Step 3: Record status**

Update `.ai` with:
- completed stages
- remaining risks
- next gated stage

**Step 4: Commit**

```bash
git add .ai/SESSION_LOG.md .ai/PROJECT_STATE.md .ai/NEXT_TASK.md
git commit -m "docs: record ABM generalization checkpoint"
```

## Stop Conditions

Stop the plan immediately if any of these occur:
- `tests/test_thinking_validator.py` fails after a generic-framework change
- `tests/test_multi_skill_integration.py` fails after composite-action changes
- `providers/smoke.py --providers ollama` stops reporting `ready`
- edited docs promise functionality not supported by tests

## Recommended Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6

## Recommended Dispatch Model

Use one fresh subagent per task, not multiple implementation agents editing code at once.

- Task 1: controller only
- Task 2: documentation agent
- Task 3: core-framework agent
- Task 4: multi-skill agent
- Task 5: example/SDK agent
- Task 6: verification agent

Review after each task:
- First: spec compliance review
- Second: code quality review
- Then: fresh verification commands
