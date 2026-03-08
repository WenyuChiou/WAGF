# Core Example Decoupling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce direct `broker/ -> examples/` runtime coupling without breaking the existing flood, irrigation, or multi-agent reference implementations.

**Architecture:** Keep runtime behavior unchanged for current examples, but move example-specific dispatch behind broker-domain adapters or generic fallback surfaces. Start with the lowest-risk coupling points: governance validator dispatch and artifact re-export behavior. Add regression tests first, then make the minimal refactor.

**Tech Stack:** Python, pytest, YAML-configured governance, water-domain adapters

---

### Task 1: Lock current validator dispatch behavior with tests

**Files:**
- Modify: `tests/test_irrigation_env.py`
- Create: `tests/test_domain_validator_dispatch.py`

**Step 1: Write the failing test**

Add tests that assert:
- `validate_all(domain="irrigation")` still returns irrigation validator results
- `validate_all(domain="flood")` still returns flood validator results
- the validator dispatch code no longer needs to import directly from `examples/...` inside `broker/validators/governance/__init__.py`

**Step 2: Run test to verify it fails**

Run:
`python -m pytest tests/test_domain_validator_dispatch.py -q`

Expected:
FAIL because the new adapter surface does not exist yet.

**Step 3: Implement minimal adapter surface**

Create a broker-domain adapter module under `broker/domains/water/` that exposes flood and irrigation builtin validator bundles.

**Step 4: Run targeted tests**

Run:
`python -m pytest tests/test_domain_validator_dispatch.py tests/test_irrigation_env.py -q`

Expected:
PASS

**Step 5: Commit**

`git commit -m "refactor: decouple validator dispatch from examples"`

### Task 2: Lock artifact fallback behavior with tests

**Files:**
- Create: `tests/test_artifact_fallbacks.py`
- Modify: `broker/interfaces/artifacts.py`

**Step 1: Write the failing test**

Add tests that assert:
- `broker.interfaces.artifacts` exposes `PolicyArtifact`, `MarketArtifact`, and `HouseholdIntention`
- those symbols are available without importing `examples.multi_agent.flood...`
- `ArtifactEnvelope` routing still works with the fallback classes

**Step 2: Run test to verify it fails**

Run:
`python -m pytest tests/test_artifact_fallbacks.py -q`

Expected:
FAIL because the module still attempts the optional example re-export path.

**Step 3: Implement minimal fallback-only surface**

Remove the optional example import from `broker/interfaces/artifacts.py` and keep the generic fallback classes as the stable broker-facing surface.

**Step 4: Run targeted tests**

Run:
`python -m pytest tests/test_artifact_fallbacks.py tests/test_artifacts.py tests/test_cross_agent_validation.py tests/test_058_integration.py -q`

Expected:
PASS

**Step 5: Commit**

`git commit -m "refactor: remove artifact example re-export coupling"`

### Task 3: Verify reference implementations still work

**Files:**
- No code changes required unless regression appears

**Step 1: Run focused regression checks**

Run:
- `python -m pytest tests/test_governance_rules.py tests/test_irrigation_env.py tests/test_artifacts.py tests/test_cross_agent_validation.py tests/test_058_integration.py -q`
- `python -m pytest tests/test_provider_smoke.py tests/test_multi_skill.py tests/test_multi_skill_integration.py -q`

**Step 2: Run smoke imports for main references**

Run:
- `python -c "import examples.single_agent.run_flood as m; print('single_agent import ok')"`
- `python -c "import examples.irrigation_abm.run_experiment as m; print('irrigation import ok')"`
- `python -c "import importlib.util, pathlib; p=pathlib.Path('examples/multi_agent/flood/run_unified_experiment.py'); spec=importlib.util.spec_from_file_location('maflood', p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('ma flood import ok')"`

**Step 3: Commit**

`git commit -m "test: verify reference implementations after decoupling"`
