# Task-058B: Cross-Agent Validation & Arbitration

> **Assigned to:** ~~Gemini~~ → COMPLETED by Claude (generalized architecture)
> **Priority:** P1
> **Status:** ✅ COMPLETE — Generalized to `CrossAgentValidator` + `CrossValidationResult` + `domain_rules` injection. Flood rules moved to `ma_cross_validators.py`. Tests: 18 pass.
> **Depends on:** 058-A (uses `PolicyArtifact`, `MarketArtifact`, `HouseholdIntention`)
> **Branch:** `feat/memory-embedding-retrieval`

---

## Objective

Create a `CrossAgentValidator` that detects pathological inter-agent patterns: perverse incentives, echo chambers, deadlocks, and budget incoherence.

## Literature Reference

- **Concordia** (Zotero: `HITVU4HK`): Game Master arbitration and action resolution
- **AgentSociety** (Zotero: `KBENGEM8`): Population-level behavior monitoring

## File: `broker/validators/governance/cross_agent_validator.py` (NEW, ~150 lines)

### Existing Infrastructure

- `broker/interfaces/skill_types.py`: `ValidationResult(is_valid, level, rule_id, message, context)`
- `broker/interfaces/coordination.py`: `ActionResolution(agent_id, approved, ...)`
- `broker/interfaces/artifacts.py` (from 058-A): `PolicyArtifact`, `MarketArtifact`, `HouseholdIntention`, `ArtifactEnvelope`

### Class: `CrossAgentValidator`

```python
from typing import Dict, List, Optional
from broker.interfaces.skill_types import ValidationResult, ValidationLevel
from broker.interfaces.artifacts import PolicyArtifact, MarketArtifact, HouseholdIntention, ArtifactEnvelope
from broker.interfaces.coordination import ActionResolution
import math


class CrossAgentValidator:
    """Validates inter-agent consistency and detects pathological patterns."""

    def __init__(self, echo_threshold: float = 0.8, entropy_threshold: float = 0.5,
                 deadlock_threshold: float = 0.5):
        self.echo_threshold = echo_threshold
        self.entropy_threshold = entropy_threshold
        self.deadlock_threshold = deadlock_threshold
        self.history: List[Dict] = []  # Past validation results for trend analysis

    def perverse_incentive_check(
        self, policy: PolicyArtifact, market: MarketArtifact,
        prev_policy: Optional[PolicyArtifact] = None,
        prev_market: Optional[MarketArtifact] = None,
    ) -> ValidationResult:
        """Check if government and insurance actions cancel each other out.

        WARN conditions:
        - Govt increases subsidy AND insurance increases premium (cancellation)
        - Govt decreases subsidy while loss_ratio > 0.7 (abandoning vulnerable)
        """
        ...

    def echo_chamber_check(self, intentions: List[HouseholdIntention]) -> ValidationResult:
        """Check if >echo_threshold% of households choose the same skill.

        Also compute Shannon entropy and flag if < entropy_threshold.
        """
        ...

    def deadlock_check(self, resolutions: List[ActionResolution]) -> ValidationResult:
        """Check if >deadlock_threshold% of proposals were rejected in a phase."""
        ...

    def budget_coherence_check(
        self, policy: PolicyArtifact, household_count: int,
        avg_subsidy_cost: float = 5000.0,
    ) -> ValidationResult:
        """Check if budget can cover expected subsidy demand.

        ERROR if budget_remaining < expected_demand * subsidy_rate
        """
        ...

    def validate_round(
        self, artifacts: Dict[str, ArtifactEnvelope],
        resolutions: Optional[List[ActionResolution]] = None,
        prev_artifacts: Optional[Dict[str, ArtifactEnvelope]] = None,
    ) -> List[ValidationResult]:
        """Run all checks and return aggregated results.

        1. Extract PolicyArtifact and MarketArtifact from artifacts
        2. Extract HouseholdIntention list from artifacts
        3. Run all 4 checks
        4. Store results in history
        5. Return list of ValidationResult (only non-valid ones)
        """
        ...
```

### Validation Rules Summary

| Rule | Trigger | Level | Message |
|------|---------|-------|---------|
| Perverse Incentive | subsidy_rate increases AND premium_rate increases | WARNING | "Policy cancellation: subsidy and premium both increased" |
| Echo Chamber | >80% same skill | WARNING | "Echo chamber: {pct}% chose {skill}" |
| Low Entropy | entropy < 0.5 | WARNING | "Decision entropy {e:.2f} below threshold" |
| Deadlock | >50% rejected | WARNING | "Deadlock risk: {pct}% proposals rejected" |
| Budget Incoherence | budget < demand | ERROR | "Budget shortfall: {budget} < {demand}" |

## Test File: `tests/test_cross_agent_validation.py` (NEW)

Write tests for:
1. `perverse_incentive_check()` — triggers when both subsidy and premium increase
2. `perverse_incentive_check()` — no trigger when only one changes
3. `echo_chamber_check()` — triggers when >80% choose same skill
4. `echo_chamber_check()` — no trigger with diverse decisions
5. `echo_chamber_check()` — entropy calculation matches expected value
6. `deadlock_check()` — triggers when >50% rejected
7. `deadlock_check()` — no trigger with mostly approved
8. `budget_coherence_check()` — ERROR when budget insufficient
9. `budget_coherence_check()` — valid when budget sufficient
10. `validate_round()` — integrates all checks, returns only failed results

## DO NOT

- Do NOT modify `broker/validators/governance/base_validator.py`
- Do NOT modify `broker/interfaces/artifacts.py` (that's 058-A)
- Do NOT import `DriftDetector` (that's 058-C, separate concern)

## Verification

```bash
pytest tests/test_cross_agent_validation.py -v
pytest tests/test_broker_core.py -v  # no regression
```

---

## Completion (Codex takeover)

- Status: ✅ Completed
- Commit: `3795065`
- Tests: `pytest tests/test_cross_agent_validation.py -v`

### Files Added
- `broker/validators/governance/cross_agent_validator.py`
- `examples/multi_agent/ma_cross_validators.py`
- `tests/test_cross_agent_validation.py`
