"""Physical governance checks for the reservoir-control example."""
from __future__ import annotations

from typing import Any, Dict, List

from broker.governance.rule_types import GovernanceRule
from broker.interfaces.skill_types import ValidationResult

from examples.reservoir_control.ops_modules import ToyMassBalanceReservoir


def _ctx_get(context: Dict[str, Any], key: str, default: Any = None) -> Any:
    env = context.get("env_state")
    if isinstance(env, dict) and env.get(key) is not None:
        return env[key]
    if context.get(key) is not None:
        return context[key]
    return default


def _missing_result(validator: str, skill_name: str, missing: List[str]) -> List[ValidationResult]:
    return [
        ValidationResult(
            valid=False,
            validator_name=validator,
            errors=[
                f"{skill_name}: required reservoir field(s) absent from the "
                f"validation context: {missing}. Cannot verify the physical "
                "constraint; check runner dynamic_state/env wiring."
            ],
            metadata={
                "category": "physical",
                "rule_id": "missing_world_state",
                "deterministic": True,
                "missing": list(missing),
            },
        )
    ]


def dead_pool_violation(
    skill_name: str, rules: List[GovernanceRule], context: Dict[str, Any]
) -> List[ValidationResult]:
    """Block set_release if the linear one-year projection crosses dead pool.

    Projection:
      S_proj = storage_now + inflow_forecast_year - 12*release_target
               - 0.01*12*storage_now

    TIMING CONTRACT (review C1): under the hindcast-then-set decision cadence,
    ``storage_now`` is the end-of-year storage just simulated and
    ``inflow_forecast_year`` MUST be the COMING year's forecast (the runner
    feeds ``inflow_forecast_for_year(year + 1)``). Feeding the just-consumed
    year's inflow makes this wall fire for the wrong physical reason.

    This is a deliberately conservative linear evaporation approximation for
    a physical wall. The hosted model still computes monthly proportional
    evaporation exactly during committed simulation steps.
    """
    if skill_name != "set_release":
        return []

    missing: List[str] = []

    def req(key: str) -> Any:
        value = _ctx_get(context, key, None)
        if value is None:
            missing.append(key)
        return value

    storage_now = req("storage_now")
    inflow_forecast_year = req("inflow_forecast_year")
    proposed_magnitude = req("proposed_magnitude")
    if missing:
        return _missing_result("dead_pool_violation", skill_name, missing)

    release_target = (float(proposed_magnitude) / 100.0) * ToyMassBalanceReservoir.DEMAND_M
    projected = (
        float(storage_now)
        + float(inflow_forecast_year)
        - 12.0 * release_target
        - 0.01 * 12.0 * float(storage_now)
    )
    if projected < ToyMassBalanceReservoir.DEAD_POOL:
        return [
            ValidationResult(
                valid=False,
                validator_name="dead_pool_violation",
                errors=[
                    f"set_release at {float(proposed_magnitude):.1f}% projects "
                    f"end-of-year storage {projected:.3f} maf, below dead pool "
                    f"{ToyMassBalanceReservoir.DEAD_POOL:.3f} maf."
                ],
                metadata={
                    "category": "physical",
                    "rule_id": "dead_pool_violation",
                    "deterministic": True,
                    "storage_now": float(storage_now),
                    "inflow_forecast_year": float(inflow_forecast_year),
                    "proposed_magnitude": float(proposed_magnitude),
                    "release_target": release_target,
                    "projected_storage": projected,
                },
            )
        ]
    return []


def flood_control_overflow(
    skill_name: str, rules: List[GovernanceRule], context: Dict[str, Any]
) -> List[ValidationResult]:
    """When nearly full, block releases below demand."""
    if skill_name != "set_release":
        return []

    missing: List[str] = []

    def req(key: str) -> Any:
        value = _ctx_get(context, key, None)
        if value is None:
            missing.append(key)
        return value

    storage_now = req("storage_now")
    proposed_magnitude = req("proposed_magnitude")
    capacity = _ctx_get(context, "capacity", ToyMassBalanceReservoir.CAPACITY)
    if missing:
        return _missing_result("flood_control_overflow", skill_name, missing)

    if float(storage_now) > 0.9 * float(capacity) and float(proposed_magnitude) < 100.0:
        return [
            ValidationResult(
                valid=False,
                validator_name="flood_control_overflow",
                errors=[
                    "set_release below 100% demand is invalid while storage is "
                    "above 90% capacity; release at least demand for flood control."
                ],
                metadata={
                    "category": "physical",
                    "rule_id": "flood_control_overflow",
                    "deterministic": True,
                    "storage_now": float(storage_now),
                    "capacity": float(capacity),
                    "proposed_magnitude": float(proposed_magnitude),
                },
            )
        ]
    return []


RESERVOIR_CONTROL_PHYSICAL_CHECKS = (
    dead_pool_violation,
    flood_control_overflow,
)


__all__ = [
    "RESERVOIR_CONTROL_PHYSICAL_CHECKS",
    "dead_pool_violation",
    "flood_control_overflow",
]
