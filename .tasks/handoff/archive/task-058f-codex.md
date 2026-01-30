# Task-058F: Integration Wiring

> **Assigned to:** Codex
> **Priority:** P1
> **Depends on:** 058-A, 058-B, 058-C, 058-D, 058-E (all COMPLETED)
> **Branch:** `feat/memory-embedding-retrieval`

---

## Objective

Wire all Task-058 components into the existing multi-agent infrastructure:
1. GameMaster artifact submission + cross-validation
2. MessageProvider generic artifact formatting
3. PhaseOrchestrator saga integration
4. LifecycleHooks drift detection recording

---

## IMPORTANT: Architecture Context

All Task-058 modules follow a **generic broker/ + domain examples/** separation:

| Component | Generic (broker/) | Domain (examples/multi_agent/) |
|-----------|-------------------|-------------------------------|
| Artifacts | `AgentArtifact` ABC in `broker/interfaces/artifacts.py` | `PolicyArtifact`, `MarketArtifact`, `HouseholdIntention` in `ma_artifacts.py` |
| Cross-Validator | `CrossAgentValidator` in `broker/validators/governance/cross_agent_validator.py` | Rules in `ma_cross_validators.py` |
| Saga | `SagaCoordinator` in `broker/components/saga_coordinator.py` | Definitions in `ma_saga_definitions.py` |
| Drift | `DriftDetector` in `broker/components/drift_detector.py` | — |
| Roles | `RoleEnforcer` in `broker/components/role_permissions.py` | `FLOOD_ROLES` in `ma_role_config.py` |

**Key types to import:**

```python
# Generic types (use these in broker/ files)
from broker.interfaces.artifacts import ArtifactEnvelope, AgentArtifact
from broker.validators.governance.cross_agent_validator import (
    CrossAgentValidator, CrossValidationResult,
)
from broker.components.saga_coordinator import SagaCoordinator
from broker.components.drift_detector import DriftDetector
```

---

## File 1: `broker/components/coordinator.py` (MODIFY, ~30 lines added)

### Change 1: Add `cross_validator` parameter to `GameMaster.__init__`

Current signature:
```python
def __init__(
    self,
    strategy: Optional[CoordinatorStrategy] = None,
    message_pool: Optional[MessagePool] = None,
    event_statement_fn: Optional[Callable[[ActionResolution], str]] = None,
):
```

Add `cross_validator` parameter (Optional, default None):
```python
def __init__(
    self,
    strategy: Optional[CoordinatorStrategy] = None,
    message_pool: Optional[MessagePool] = None,
    event_statement_fn: Optional[Callable[[ActionResolution], str]] = None,
    cross_validator=None,  # Optional[CrossAgentValidator]
):
    # ... existing init ...
    self.cross_validator = cross_validator
    self._round_artifacts: Dict[str, Any] = {}  # Store submitted artifacts
```

### Change 2: Add `submit_artifact()` method

```python
def submit_artifact(self, envelope) -> None:
    """Submit a typed artifact and broadcast via MessagePool.

    Args:
        envelope: ArtifactEnvelope wrapping an AgentArtifact subclass
    """
    msg = envelope.to_agent_message()
    if self._message_pool:
        self._message_pool.publish(msg)
    # Store for cross-validation at end of phase
    atype = envelope.artifact.artifact_type()
    self._round_artifacts[atype] = envelope.artifact
```

### Change 3: Add cross-validation after `resolve_phase()`

At the end of `resolve_phase()`, before returning resolutions, add:

```python
# Cross-agent validation (if configured)
if self.cross_validator and self._round_artifacts:
    import logging
    logger = logging.getLogger(__name__)
    cv_results = self.cross_validator.validate_round(
        self._round_artifacts, resolutions=resolutions,
    )
    for r in cv_results:
        if not r.is_valid:
            logger.warning(f"[CrossValidation] {r.rule_id}: {r.message}")
    self._round_artifacts = {}  # Reset for next round
```

**NOTE:** `CrossValidationResult` has fields: `is_valid`, `rule_id`, `level`, `message`

---

## File 2: `broker/components/message_provider.py` (MODIFY, ~15 lines)

### Change: Add artifact-aware formatting in `provide()`

In the `MessagePoolProvider.provide()` method, when formatting messages, check for artifact data and format generically:

```python
def _format_artifact_message(self, msg) -> str:
    """Format artifact-carrying messages with structured data summaries."""
    if msg.data and msg.data.get("artifact_type"):
        atype = msg.data["artifact_type"]
        # Generic: use artifact_type as prefix, list domain-specific fields
        skip_keys = {"artifact_type", "agent_id", "year", "rationale"}
        fields = {k: v for k, v in msg.data.items() if k not in skip_keys}
        summary = ", ".join(f"{k}={v}" for k, v in fields.items())
        return f"[{atype}] {summary}"
    return msg.content
```

Call this in `provide()` when building the message list. **Do NOT hardcode `[GOV]`, `[INS]`, `[HH]` prefixes** — use `artifact_type` from the payload data for generic formatting.

---

## File 3: `broker/components/phase_orchestrator.py` (MODIFY, ~15 lines)

### Change 1: Add `saga_coordinator` parameter

Current signature:
```python
def __init__(
    self,
    phases: Optional[List[PhaseConfig]] = None,
    seed: int = 42,
):
```

Add `saga_coordinator` parameter:
```python
def __init__(
    self,
    phases: Optional[List[PhaseConfig]] = None,
    seed: int = 42,
    saga_coordinator=None,  # Optional[SagaCoordinator]
):
    # ... existing init ...
    self.saga_coordinator = saga_coordinator
```

### Change 2: Add saga advancement at phase boundaries

In `get_execution_plan()` or wherever phase transitions happen:

```python
def advance_sagas(self, current_step: int = 0) -> None:
    """Advance all active sagas. Called at phase boundaries."""
    if self.saga_coordinator:
        import logging
        logger = logging.getLogger(__name__)
        completed = self.saga_coordinator.advance_all()
        for result in completed:
            if result and result.status.value in ("rolled_back", "failed"):
                logger.warning(
                    f"[Saga] {result.saga_name} {result.status.value}: {result.error}"
                )
```

**NOTE:** SagaCoordinator API:
- `advance_all()` → returns list of `SagaResult` (completed in this tick)
- `SagaResult` fields: `saga_id`, `saga_name`, `status` (SagaStatus enum), `context`, `completed_steps`, `error`
- `SagaStatus` enum: `PENDING`, `RUNNING`, `COMPLETED`, `COMPENSATING`, `FAILED`, `ROLLED_BACK`

---

## File 4: `examples/multi_agent/orchestration/lifecycle_hooks.py` (MODIFY, ~35 lines)

### Change 1: Add `drift_detector` parameter to `__init__`

Current signature already has `game_master` and `message_pool`. Add `drift_detector`:

```python
def __init__(
    self,
    environment: Dict,
    memory_engine=None,
    hazard_module=None,
    media_hub=None,
    per_agent_depth: bool = False,
    year_mapping=None,
    game_master=None,
    message_pool=None,
    drift_detector=None,  # NEW: DriftDetector instance
):
    # ... existing init ...
    self.drift_detector = drift_detector
```

### Change 2: In `post_step()`, record agent decisions

After the existing resolution handling block (~line 183), add:

```python
# Record decision for drift detection
if self.drift_detector and result:
    decision = result.get("skill_name", result.get("decision", ""))
    if decision and hasattr(agent, "id"):
        self.drift_detector.record_decision(agent.id, decision)
```

**NOTE:** `DriftDetector.record_decision(agent_id: str, action: str)` stores one decision.

### Change 3: In `post_year()`, compute snapshot and log alerts

At the end of `post_year()`, after the existing MA reflection block, add:

```python
# Drift detection: compute snapshot and check alerts
if self.drift_detector:
    import logging
    logger = logging.getLogger(__name__)
    report = self.drift_detector.compute_snapshot(year=year)
    alerts = self.drift_detector.check_alerts()
    for alert in alerts:
        logger.warning(f"[Drift:{alert.alert_type}] Year {year}: {alert.message}")
```

**NOTE:** `DriftDetector` API:
- `compute_snapshot(year: int = 0) -> DriftReport` — computes entropy, dominant action, stagnation
- `check_alerts() -> List[DriftAlert]` — checks for low entropy, high stagnation, mode collapse
- `DriftAlert` fields: `alert_type`, `message`, `severity`, `data`

---

## Test File: `tests/test_058_integration.py` (NEW)

Write tests for:

### 1. GameMaster.submit_artifact() publishes to MessagePool
```python
def test_submit_artifact_publishes():
    from broker.components.coordinator import GameMaster
    from broker.components.message_pool import MessagePool
    from broker.interfaces.artifacts import ArtifactEnvelope
    from examples.multi_agent.ma_artifacts import PolicyArtifact

    pool = MessagePool()
    gm = GameMaster(message_pool=pool)
    artifact = PolicyArtifact(agent_id="GOV", year=1, rationale="test",
                              subsidy_rate=0.5, budget_remaining=10000)
    envelope = ArtifactEnvelope(artifact=artifact, source_agent="GOV")
    gm.submit_artifact(envelope)
    # Verify message published
    assert len(pool.get_messages()) >= 1
```

### 2. GameMaster with cross_validator logs warnings
```python
def test_cross_validation_after_resolve():
    from broker.validators.governance.cross_agent_validator import CrossAgentValidator
    # Create validator, submit artifacts, resolve, check history updated
    ...
```

### 3. PhaseOrchestrator.advance_sagas() works
```python
def test_orchestrator_advance_sagas():
    from broker.components.phase_orchestrator import PhaseOrchestrator
    from broker.components.saga_coordinator import SagaCoordinator, SagaDefinition, SagaStep
    # Register saga, start, advance via orchestrator
    ...
```

### 4. MultiAgentHooks with drift_detector records
```python
def test_hooks_drift_recording():
    from examples.multi_agent.orchestration.lifecycle_hooks import MultiAgentHooks
    from broker.components.drift_detector import DriftDetector
    # Create hooks with drift_detector, call post_step, verify recording
    ...
```

### 5. Backward compatibility — all new parameters are Optional
```python
def test_backward_compat():
    from broker.components.coordinator import GameMaster
    from broker.components.phase_orchestrator import PhaseOrchestrator
    gm = GameMaster()  # No cross_validator
    po = PhaseOrchestrator()  # No saga_coordinator
    # Both should work without new params
```

---

## DO NOT

- Do NOT modify `GameMaster.submit_proposal()` or `resolve_phase()` signatures
- Do NOT remove any existing functionality
- Do NOT change `MemoryBridge` integration (Task-056)
- Do NOT modify the reflection integration (Task-057D)
- Do NOT hardcode domain-specific formatting (e.g. `[GOV]`, `[INS]`) — use `artifact_type` from data
- Do NOT import domain types (`PolicyArtifact`, etc.) in `broker/` files — use generic `AgentArtifact` / `ArtifactEnvelope`
- Keep ALL new parameters Optional with None default for backward compatibility

---

## Verification

```bash
# New tests
pytest tests/test_058_integration.py -v

# No regression on existing tests
pytest tests/test_broker_core.py -v
pytest tests/test_artifacts.py tests/test_cross_agent_validation.py tests/test_drift_detector.py tests/test_saga_coordinator.py -v

# Full regression
pytest tests/ --ignore=tests/integration --ignore=tests/manual --ignore=tests/test_vector_db.py -v
```

**Success criteria:**
- All new tests pass
- 967+ existing tests still pass
- No `examples/` imports added to `broker/` files

---

## Completion (Codex takeover)

- Status: ✅ Completed
- Commit: `9599f68`
- Tests: `pytest tests/test_058_integration.py -v`

### Files Updated
- `broker/components/coordinator.py`
- `broker/components/message_provider.py`
- `broker/components/phase_orchestrator.py`
- `examples/multi_agent/orchestration/lifecycle_hooks.py`
- `tests/test_058_integration.py`
