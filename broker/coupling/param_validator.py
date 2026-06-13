"""Phase 6W-B4 — generic per-field parameter-bounds ERROR validator.

The AR-6 home for numeric-parameter governance: ONE bounds vocabulary, reusing the
coupling ``VarSpec.lo/hi`` via ``VarSpec.range_violation``. This is a FACTORY whose
returned callable has the PHYSICAL-slot validator signature
``(skill_name, rules, context) -> List[ValidationResult]`` — the same registration
channel ``dead_pool_violation`` uses: register it via
``ValidatorRegistry.register(domain, "physical", [validator])`` (NOT the
``custom_validators`` path, whose signature is ``(proposal, context, registry)``).
The factory is built from a per-skill spec mapping (the value the SkillPack
param-specs hook returns). The hook->factory->ValidatorRegistry wiring lands with the
first multi-param worked example (B7); this module is just the reusable validator.

It NEVER clips: an out-of-bounds or missing setpoint BLOCKS (ERROR), and the named
violation is surfaced in the retry message — preserving the EXECUTED-ONLY
proposed-vs-executed distinction the Paper-3 rule depends on. Every result is
``deterministic`` so it composes with the retry loop's EarlyExit and the
REJECTED-fallback machinery automatically.

Lives under ``broker.coupling`` (imported only on a flag-ON coupled path), so it
adds nothing to the frozen default import path. Per INVARIANTS.md AR-6 this is the
documented resolution of "a non-coupled domain with numeric skill parameters that
need bounds" — and the SINGLE such validator (no second bounds registry, no rule
engine — Do-NOT-build).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List

from broker.coupling.contract import VarSpec
from broker.interfaces.skill_types import ValidationResult

# A PHYSICAL-slot validator (registered via ValidatorRegistry, like dead_pool_violation):
#   (skill_name, rules, context) -> List[ValidationResult]
ParameterBoundsValidator = Callable[[str, Any, Dict[str, Any]], List[ValidationResult]]


def make_parameter_bounds_validator(
    param_specs: Dict[str, List[VarSpec]],
) -> ParameterBoundsValidator:
    """Build a custom-validator that bounds each DECLARED setpoint of a skill.

    ``param_specs`` is a ``{skill_id: [VarSpec, ...]}`` mapping (typically the value
    returned by the SkillPack param-specs hook). The returned callable:
      * is INERT (returns ``[]``) for any skill with no declared specs — so it is
        safe to register globally; only declaring skills are governed;
      * iterates the SPEC ALLOWLIST, never the raw proposed dict — so non-setpoint
        keys (the bool ``magnitude_fallback``, the legacy ``magnitude_pct``) are
        never range-checked unless a spec explicitly names them;
      * BLOCKS (never clips) on a missing-required or out-of-range setpoint.
    """

    def parameter_bounds(
        skill_name: str, rules: Any, context: Dict[str, Any]
    ) -> List[ValidationResult]:
        specs = param_specs.get(skill_name) or []
        if not specs:
            return []  # skill declares no numeric setpoints -> inert
        proposed = context.get("proposed_parameters") or {}
        results: List[ValidationResult] = []
        for vs in specs:  # allowlist iteration: only declared setpoints are checked
            value = proposed.get(vs.name)
            if value is None:
                results.append(
                    ValidationResult(
                        valid=False,
                        validator_name="parameter_bounds",
                        errors=[
                            f"{skill_name} must propose a numeric value for setpoint "
                            f"'{vs.name}' ({vs.unit})."
                        ],
                        metadata={
                            "category": "physical",
                            "rule_id": f"param_missing_{vs.name}",
                            "deterministic": True,
                            "field": vs.name,
                        },
                    )
                )
                continue
            msg = vs.range_violation(value)
            if msg is not None:
                bounds = []
                if vs.lo is not None:
                    bounds.append(f">= {vs.lo}")
                if vs.hi is not None:
                    bounds.append(f"<= {vs.hi}")
                rng = " and ".join(bounds) or "the declared range"
                results.append(
                    ValidationResult(
                        valid=False,
                        validator_name="parameter_bounds",
                        errors=[
                            f"Setpoint out of bounds: {msg}. Re-propose "
                            f"'{vs.name}' {rng} ({vs.unit})."
                        ],
                        metadata={
                            "category": "physical",
                            "rule_id": f"param_bounds_{vs.name}",
                            "deterministic": True,
                            "field": vs.name,
                            "proposed_value": value,
                            "lo": vs.lo,
                            "hi": vs.hi,
                        },
                    )
                )
        return results

    return parameter_bounds
