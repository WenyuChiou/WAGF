"""
Irrigation domain governance validators.

Provides BuiltinCheck functions for the irrigation domain that enforce
water allocation rules, compact constraints, and physical feasibility.
These are injected into the existing validator framework via the
``builtin_checks`` constructor parameter.

Design follows the same pattern as flood-domain built-in checks
(FLOOD_PERSONAL_CHECKS, FLOOD_PHYSICAL_CHECKS, etc.) established
in the Phase 1 validator refactoring (commit fd861cf).

Architecture note:
    The standard ThinkingValidator, PersonalValidator, and SemanticValidator
    are intentionally left empty (no builtin_checks) for the irrigation
    domain. All irrigation governance is routed through ``custom_validators``
    via the ``irrigation_governance_validator`` bridge at the bottom of this
    module. This is by design — the irrigation domain uses numeric-decision
    output (1-3) validated by output_schema and custom checks, rather than
    PMT-based construct validation used by the flood domain.

References:
    Hung, F., & Yang, Y. C. E. (2021). WRR, 57, e2020WR029262.
    Colorado River Compact (1922) — Upper/Lower Basin allocation rules.
"""

from typing import Any, Dict, List

from broker.interfaces.skill_types import ValidationResult
from broker.governance.rule_types import GovernanceRule


# =============================================================================
# Skill group constants (v17: 5-skill model)
# =============================================================================
INCREASE_SKILLS = frozenset({"increase_large", "increase_small", "increase_demand"})
DECREASE_SKILLS = frozenset({"decrease_large", "decrease_small", "decrease_demand"})


# =============================================================================
# Individual BuiltinCheck functions
# =============================================================================

def water_right_cap_check(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Block demand increase if agent is at or above water right allocation.

    Checks ``context["at_allocation_cap"]`` — set by IrrigationEnvironment
    when the agent's request reaches their water right.

    Tier A suggestion: None (physical impossibility — reason is self-evident).
    """
    if skill_name not in INCREASE_SKILLS:
        return []

    at_cap = context.get("at_allocation_cap", False)
    if not at_cap:
        return []

    water_right = context.get("water_right", "unknown")
    return [
        ValidationResult(
            valid=False,
            validator_name="IrrigationWaterRightsValidator",
            errors=[
                f"Demand increase blocked: agent already at water right "
                f"cap ({water_right} acre-ft/year)."
            ],
            warnings=[],
            metadata={
                "rule_id": "water_right_cap",
                "category": "physical",
                "blocked_skill": skill_name,
                "level": "ERROR",
            },
        )
    ]


def non_negative_diversion_check(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Ensure diversion request cannot go below zero.

    When diversion is zero due to high curtailment (request > 0 but
    curtailment ate all of it), issue a WARNING instead of ERROR.
    Decreasing from zero is a harmless no-op and should not trigger
    retry loops that create double-bind traps.

    Tier A suggestion: None (physical impossibility).
    """
    if skill_name not in DECREASE_SKILLS:
        return []

    current_diversion = context.get("current_diversion", 0)
    if current_diversion > 0:
        return []

    # If request > 0 but diversion = 0, the shortfall is caused by
    # curtailment / Powell constraints, not agent choice.  Decreasing
    # is a no-op — warn, don't block.
    current_request = context.get("current_request", 0)
    if current_request > 0:
        return [
            ValidationResult(
                valid=True,
                validator_name="IrrigationPhysicalValidator",
                errors=[],
                warnings=[
                    "Diversion is zero due to curtailment (request "
                    f"{current_request:,.0f} AF). Decrease will be a no-op."
                ],
                metadata={
                    "rule_id": "non_negative_diversion",
                    "category": "physical",
                    "blocked_skill": skill_name,
                    "level": "WARNING",
                },
            )
        ]

    return [
        ValidationResult(
            valid=False,
            validator_name="IrrigationPhysicalValidator",
            errors=[
                "Demand decrease blocked: current diversion is already zero."
            ],
            warnings=[],
            metadata={
                "rule_id": "non_negative_diversion",
                "category": "physical",
                "blocked_skill": skill_name,
                "level": "ERROR",
            },
        )
    ]


def curtailment_awareness_check(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Warn or block demand increase during active curtailment.

    v17 differential governance:
        Tier 0:   WARNING for all increases
        Tier 1:   BLOCK increase_large, WARN increase_small
        Tier 2+:  BLOCK all increases (DCP mandatory conservation)

    Tier B suggestion: neutral enumeration of remaining feasible skills.
    """
    if skill_name not in INCREASE_SKILLS:
        return []

    curtailment = context.get("curtailment_ratio", 0)
    if curtailment <= 0:
        return []

    shortage_tier = context.get("shortage_tier", 0)
    # loop_year is 1-indexed from pre_year hook; default 99 skips grace period safely
    year = context.get("loop_year") or 99

    # Cold-start grace period: Y1-3 Tier 2 → warning only (not hard block)
    if year <= 3 and shortage_tier == 2:
        return [
            ValidationResult(
                valid=True,
                validator_name="IrrigationCurtailmentValidator",
                errors=[],
                warnings=[
                    f"Cold-start grace period (Year {year}): Tier 2 shortage "
                    f"({curtailment:.0%} curtailment) converted to warning. "
                    f"Consider conservation voluntarily."
                ],
                metadata={
                    "rule_id": "curtailment_awareness",
                    "category": "physical",
                    "blocked_skill": skill_name,
                    "level": "WARNING",
                    "cold_start_grace": True,
                },
            )
        ]

    # Tier 2+: hard block ALL increases (DCP mandatory conservation)
    if shortage_tier >= 2:
        return [
            ValidationResult(
                valid=False,
                validator_name="IrrigationCurtailmentValidator",
                errors=[
                    f"Demand increase blocked: Tier {shortage_tier} shortage "
                    f"({curtailment:.0%} curtailment). Conservation is mandatory "
                    f"under DCP operations."
                ],
                warnings=[],
                metadata={
                    "rule_id": "curtailment_awareness",
                    "category": "institutional",
                    "blocked_skill": skill_name,
                    "level": "ERROR",
                    "suggestion": (
                        f"Tier {shortage_tier} shortage blocks all increases. "
                        "Remaining feasible: maintain_demand, decrease_small, decrease_large."
                    ),
                },
            )
        ]

    # Tier 1: differential — block increase_large, warn increase_small
    if shortage_tier == 1:
        if skill_name in ("increase_large", "increase_demand"):
            return [
                ValidationResult(
                    valid=False,
                    validator_name="IrrigationCurtailmentValidator",
                    errors=[
                        f"Large demand increase blocked: Tier 1 shortage "
                        f"({curtailment:.0%} curtailment)."
                    ],
                    warnings=[],
                    metadata={
                        "rule_id": "curtailment_awareness",
                        "category": "institutional",
                        "blocked_skill": skill_name,
                        "level": "ERROR",
                        "suggestion": (
                            "Tier 1 shortage blocks increase_large. "
                            "Remaining feasible: increase_small, maintain_demand, "
                            "decrease_small, decrease_large."
                        ),
                    },
                )
            ]
        else:
            # increase_small: warning only at Tier 1
            return [
                ValidationResult(
                    valid=True,
                    validator_name="IrrigationCurtailmentValidator",
                    errors=[],
                    warnings=[
                        f"Tier 1 shortage active ({curtailment:.0%} curtailment). "
                        f"Small increase permitted but may face unmet demand."
                    ],
                    metadata={
                        "rule_id": "curtailment_awareness",
                        "category": "institutional",
                        "blocked_skill": skill_name,
                        "level": "WARNING",
                    },
                )
            ]

    # Tier 0: warning only
    return [
        ValidationResult(
            valid=True,
            validator_name="IrrigationCurtailmentValidator",
            errors=[],
            warnings=[
                f"Water curtailment active (Tier {shortage_tier}, "
                f"{curtailment:.0%} reduction). Increasing demand may "
                f"result in unmet allocation."
            ],
            metadata={
                "rule_id": "curtailment_awareness",
                "category": "institutional",
                "blocked_skill": skill_name,
                "level": "WARNING",
            },
        )
    ]


def compact_allocation_check(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Warn when basin-wide allocation exceeds Colorado River Compact share.

    This is a basin-level check — it validates that the aggregate of all
    agent requests in a basin does not exceed the compact allocation.

    Note: Requires ``total_basin_demand`` and ``basin_allocation`` in context.
    Currently a placeholder — the environment does not yet inject aggregate
    basin statistics into the per-agent validation context.
    """
    if skill_name not in INCREASE_SKILLS:
        return []

    basin = context.get("basin", "lower_basin")
    total_basin_demand = context.get("total_basin_demand", 0)
    basin_allocation = context.get("basin_allocation", 0)

    if basin_allocation <= 0 or total_basin_demand <= basin_allocation:
        return []

    overshoot_pct = (total_basin_demand - basin_allocation) / basin_allocation * 100
    return [
        ValidationResult(
            valid=True,  # Warning — individual agent not blocked
            validator_name="IrrigationCompactValidator",
            errors=[],
            warnings=[
                f"Basin ({basin}) aggregate demand exceeds Colorado River "
                f"Compact allocation by {overshoot_pct:.1f}%. "
                f"Individual increases will face curtailment."
            ],
            metadata={
                "rule_id": "compact_allocation",
                "category": "institutional",
                "blocked_skill": skill_name,
                "level": "WARNING",
            },
        )
    ]


def drought_severity_check(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Block demand increase during drought conditions.

    v17 differential governance:
        drought 0.7-0.84:  BLOCK increase_large, WARN increase_small
        drought >= 0.85:   BLOCK all increases

    Tier B suggestion: neutral enumeration of remaining feasible skills.
    """
    if skill_name not in INCREASE_SKILLS:
        return []

    drought_idx = context.get("drought_index", 0)
    if drought_idx < 0.7:
        return []

    # Extreme drought (≥ 0.85): block ALL increases
    if drought_idx >= 0.85:
        return [
            ValidationResult(
                valid=False,
                validator_name="IrrigationDroughtValidator",
                errors=[
                    f"Demand increase blocked: drought index = {drought_idx:.2f} "
                    f"(extreme). Water conservation is mandatory."
                ],
                warnings=[],
                metadata={
                    "rule_id": "drought_severity",
                    "category": "institutional",
                    "blocked_skill": skill_name,
                    "level": "ERROR",
                    "suggestion": (
                        "Extreme drought blocks all increases. "
                        "Remaining feasible: maintain_demand, decrease_small, decrease_large."
                    ),
                },
            )
        ]

    # Moderate drought (0.7-0.84): differential treatment
    if skill_name in ("increase_large", "increase_demand"):
        return [
            ValidationResult(
                valid=False,
                validator_name="IrrigationDroughtValidator",
                errors=[
                    f"Large demand increase blocked: drought index = {drought_idx:.2f} "
                    f"(moderate-severe)."
                ],
                warnings=[],
                metadata={
                    "rule_id": "drought_severity",
                    "category": "institutional",
                    "blocked_skill": skill_name,
                    "level": "ERROR",
                    "suggestion": (
                        "Drought conditions block increase_large. "
                        "Remaining feasible: increase_small, maintain_demand, "
                        "decrease_small, decrease_large."
                    ),
                },
            )
        ]

    # increase_small at moderate drought: warning only
    return [
        ValidationResult(
            valid=True,
            validator_name="IrrigationDroughtValidator",
            errors=[],
            warnings=[
                f"Drought index = {drought_idx:.2f} (moderate-severe). "
                f"Small increase permitted but may face supply constraints."
            ],
            metadata={
                "rule_id": "drought_severity",
                "category": "institutional",
                "blocked_skill": skill_name,
                "level": "WARNING",
            },
        )
    ]


def minimum_utilisation_check(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Block demand reduction when agent is already at minimum utilisation floor.

    Prevents "economic hallucination" — the LLM choosing to further reduce
    demand when utilisation is already at or below 10% of water right.

    Tier A suggestion: None (physical impossibility).
    """
    if skill_name not in DECREASE_SKILLS:
        return []

    below_min = context.get("below_minimum_utilisation", False)
    if not below_min:
        return []

    water_right = context.get("water_right", "unknown")
    request = context.get("request", 0)
    util_pct = (request / water_right * 100) if isinstance(water_right, (int, float)) and water_right > 0 else 0
    return [
        ValidationResult(
            valid=False,
            validator_name="IrrigationMinimumUtilisationValidator",
            errors=[
                f"Demand reduction blocked: agent at {util_pct:.1f}% utilisation "
                f"(floor = 10% of {water_right} AF water right). "
                f"Further reduction constitutes economic hallucination."
            ],
            warnings=[],
            metadata={
                "rule_id": "minimum_utilisation_floor",
                "category": "physical",
                "blocked_skill": skill_name,
                "hallucination_type": "economic",
                "level": "ERROR",
            },
        )
    ]


def magnitude_cap_check(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Block demand increase when proposed magnitude exceeds cluster bounds.

    Requires ``proposed_magnitude`` in context (injected by broker engine
    when ``SkillProposal.magnitude_pct`` is not None).
    """
    if skill_name not in INCREASE_SKILLS:
        return []

    magnitude = context.get("proposed_magnitude", 0)
    cluster = context.get("cluster", "myopic_conservative")

    caps = {
        "aggressive": 20,
        "forward_looking_conservative": 15,
        "myopic_conservative": 8,
    }
    max_mag = caps.get(cluster, 10)

    if abs(magnitude) > max_mag:
        # v12: execute_skill ignores LLM magnitude_pct and samples from
        # Gaussian (already clipped to cluster max). So this is a WARNING
        # (audit trail) not an ERROR (no retry needed for a value that
        # won't be used in execution anyway).
        return [
            ValidationResult(
                valid=True,
                validator_name="IrrigationMagnitudeValidator",
                errors=[],
                warnings=[
                    f"Magnitude {magnitude}% exceeds {cluster} cap ({max_mag}%). "
                    f"Execution will use Gaussian-sampled value (capped at {max_mag}%)."
                ],
                metadata={
                    "rule_id": "magnitude_cap",
                    "category": "physical",
                    "blocked_skill": skill_name,
                    "level": "WARNING",
                    "proposed_magnitude": magnitude,
                    "capped_magnitude": max_mag,
                },
            )
        ]
    return []


def supply_gap_block_increase(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Block demand increase when agent already has large unmet demand.

    P3: Physical rationale — requesting more water than the system can
    deliver cannot increase actual water received.

    Blocks when fulfilment ratio (diversion / request) < 70%.

    Tier B suggestion: neutral enumeration of remaining feasible skills.
    """
    if skill_name not in INCREASE_SKILLS:
        return []

    # Skip if Tier 2+ shortage already handled by curtailment_awareness_check
    shortage_tier = context.get("shortage_tier", 0)
    if shortage_tier >= 2:
        return []  # P4 handles this case with DCP block

    request = context.get("current_request", 0)
    diversion = context.get("current_diversion", 0)

    # Both zero → new agent expanding from zero baseline (Y1), allow
    if request <= 0 and diversion <= 0:
        return []

    # Positive request but zero delivery → complete supply failure, block
    if request > 0 and diversion <= 0:
        return [
            ValidationResult(
                valid=False,
                validator_name="IrrigationSupplyGapValidator",
                errors=[
                    f"Demand increase blocked: received zero water despite "
                    f"requesting {request:,.0f} AF. System cannot deliver more."
                ],
                warnings=[],
                metadata={
                    "rule_id": "supply_gap_block_increase",
                    "category": "physical",
                    "blocked_skill": skill_name,
                    "level": "ERROR",
                    "suggestion": (
                        "Supply gap blocks all increases. "
                        "Remaining feasible: maintain_demand, decrease_small, decrease_large."
                    ),
                },
            )
        ]

    fulfilment = diversion / request
    if fulfilment >= 0.70:
        return []

    unmet = request - diversion
    return [
        ValidationResult(
            valid=False,
            validator_name="IrrigationSupplyGapValidator",
            errors=[
                f"Demand increase blocked: only {fulfilment:.0%} of request "
                f"fulfilled ({unmet:,.0f} AF unmet). System cannot deliver more."
            ],
            warnings=[],
            metadata={
                "rule_id": "supply_gap_block_increase",
                "category": "physical",
                "blocked_skill": skill_name,
                "level": "ERROR",
                "suggestion": (
                    f"Supply gap ({fulfilment:.0%} fulfilled) blocks all increases. "
                    "Remaining feasible: maintain_demand, decrease_small, decrease_large."
                ),
            },
        )
    ]


# =============================================================================
# Phase C/D Pilot Validators — gated by module-level flags
# =============================================================================

# Feature flags — set by run_experiment.py based on --pilot-phase / --ablation-mode
ENABLE_CONSECUTIVE_CAP = False
ENABLE_ZERO_ESCAPE = False
ENABLE_DEMAND_CEILING = True  # Default ON; ablation sets False

# Module-level state for consecutive increase tracking (cleared per experiment)
_consecutive_increase_tracker: Dict[str, int] = {}

MAX_CONSECUTIVE_INCREASES = 3
ZERO_ESCAPE_FLOOR_RATIO = 0.15  # 15% of water_right


def reset_consecutive_tracker() -> None:
    """Reset the consecutive increase tracker. Call at experiment start."""
    _consecutive_increase_tracker.clear()


def update_consecutive_tracker(agent_id: str, skill_name: str) -> None:
    """Update consecutive increase counter after a decision is finalized.

    Call from post_step hook after each agent's decision.
    Both increase_large and increase_small count as consecutive increases.
    """
    if skill_name in INCREASE_SKILLS:
        _consecutive_increase_tracker[agent_id] = (
            _consecutive_increase_tracker.get(agent_id, 0) + 1
        )
    else:
        _consecutive_increase_tracker[agent_id] = 0


def consecutive_increase_cap_check(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Block increase_demand if agent has increased for N consecutive years.

    Prevents compound demand growth (8-11%/yr for 30+ years) that causes
    system-wide divergence from CRSS baseline.

    Exempt during genuinely wet periods (drought_index < 0.3) where
    increased demand is physically justified.
    """
    if not ENABLE_CONSECUTIVE_CAP:
        return []

    if skill_name not in INCREASE_SKILLS:
        return []

    agent_id = context.get("agent_id", "unknown")
    count = _consecutive_increase_tracker.get(agent_id, 0)

    if count < MAX_CONSECUTIVE_INCREASES:
        return []

    # Wet-period exemption: abundant water justifies continued increase
    drought_index = context.get("drought_index", 0.5)
    if drought_index < 0.3:
        return []

    return [
        ValidationResult(
            valid=False,
            validator_name="IrrigationConsecutiveCapValidator",
            errors=[
                f"Demand increase blocked: you have increased demand for "
                f"{count} consecutive years. Sustained demand growth is not "
                f"physically sustainable."
            ],
            warnings=[],
            metadata={
                "rule_id": "consecutive_increase_cap",
                "category": "temporal",
                "blocked_skill": skill_name,
                "level": "ERROR",
                "consecutive_count": count,
                "suggestion": (
                    f"Consecutive increase cap ({count} years) blocks all increases. "
                    "Remaining feasible: maintain_demand, decrease_small, decrease_large."
                ),
            },
        )
    ]


DEMAND_FLOOR_RATIO = 0.50  # 50% of water_right
DEMAND_CEILING_AF = 6_000_000  # 6.0 MAF ~ 1.024x CRSS target (5.86 MAF)


def demand_floor_stabilizer(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Block demand decrease when utilisation is below stability floor.

    Prevents over-correction during drought: agents may decrease during
    shortage, but not below a floor that ensures economic viability and
    supports basin-wide CRSS demand targets (5.86 MAF).

    Creates a corridor with minimum_utilisation_check (10% hard floor):
        10% ← hard floor (blocks all decrease)
        50% ← stability floor (blocks decrease, this validator)
       100% ← water right cap (blocks increase)

    Tier C suggestion: None (behavioral rule — agent decides autonomously).
    """
    if skill_name not in DECREASE_SKILLS:
        return []

    water_right = context.get("water_right", 0)
    current_request = context.get("current_request", 0)

    if water_right <= 0:
        return []

    utilisation = current_request / water_right
    if utilisation >= DEMAND_FLOOR_RATIO:
        return []

    return [
        ValidationResult(
            valid=False,
            validator_name="IrrigationDemandFloorValidator",
            errors=[
                f"Demand decrease blocked: current utilisation is {utilisation:.0%} "
                f"of water right, already below the {DEMAND_FLOOR_RATIO:.0%} "
                f"stability floor. Further reduction risks economic non-viability."
            ],
            warnings=[],
            metadata={
                "rule_id": "demand_floor_stabilizer",
                "category": "economic",
                "blocked_skill": skill_name,
                "level": "ERROR",
            },
        )
    ]


def demand_ceiling_stabilizer(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Block demand increase when basin-wide aggregate demand exceeds ceiling.

    Prevents collective overshoot during Tier 0 (no shortage) years when
    no other validator constrains increases.  Symmetric counterpart to
    demand_floor_stabilizer (prevents collapse from below).

    Checks total_basin_demand (sum of all agents' requests, computed in
    advance_year()) against DEMAND_CEILING_AF (6.0 MAF).  This acts as
    the institutional equivalent of the FQL reward function's regret
    penalty — in RL, over-demand is penalised via reward; here, it is
    blocked via governance.

    Tier C suggestion: None (behavioral rule — agent decides autonomously).
    """
    if not ENABLE_DEMAND_CEILING:
        return []

    if skill_name not in INCREASE_SKILLS:
        return []

    total_basin_demand = context.get("total_basin_demand", 0)
    if total_basin_demand <= DEMAND_CEILING_AF:
        return []

    overshoot_pct = (
        (total_basin_demand - DEMAND_CEILING_AF) / DEMAND_CEILING_AF * 100
        if DEMAND_CEILING_AF > 0 else 0
    )
    return [
        ValidationResult(
            valid=False,
            validator_name="IrrigationDemandCeilingValidator",
            errors=[
                f"Demand increase blocked: basin-wide aggregate demand "
                f"({total_basin_demand / 1e6:.2f} MAF) exceeds the "
                f"{DEMAND_CEILING_AF / 1e6:.1f} MAF stability ceiling "
                f"by {overshoot_pct:.1f}%. Conservation or maintenance "
                f"is required to stabilize basin supply-demand balance."
            ],
            warnings=[],
            metadata={
                "rule_id": "demand_ceiling_stabilizer",
                "category": "economic",
                "blocked_skill": skill_name,
                "level": "ERROR",
            },
        )
    ]


def zero_escape_check(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Block maintain_demand when demand is near minimum utilisation floor.

    Prevents the "maintain 0" trap where conservative agents lock into
    near-zero demand indefinitely. Combined with the existing
    minimum_utilisation_check (blocks decrease below 10%), this creates
    a corridor that forces agents to either increase or adopt efficiency.

    Threshold: 15% of water_right (above the 10% decrease floor).
    """
    if not ENABLE_ZERO_ESCAPE:
        return []

    if skill_name != "maintain_demand":
        return []

    request = context.get("current_request", 0)
    water_right = context.get("water_right", 0)

    if water_right <= 0:
        return []

    utilisation = request / water_right
    if utilisation >= ZERO_ESCAPE_FLOOR_RATIO:
        return []

    return [
        ValidationResult(
            valid=False,
            validator_name="IrrigationZeroEscapeValidator",
            errors=[
                f"Maintain demand blocked: your current water use is only "
                f"{utilisation:.0%} of your water right ({request:,.0f} / "
                f"{water_right:,.0f} AF). At this level, status quo is not "
                f"economically viable."
            ],
            warnings=[],
            metadata={
                "rule_id": "zero_escape_floor",
                "category": "behavioral",
                "blocked_skill": skill_name,
                "level": "ERROR",
                "utilisation_pct": utilisation * 100,
            },
        )
    ]


# =============================================================================
# Aggregated check lists for injection into validators
# =============================================================================

IRRIGATION_PHYSICAL_CHECKS = [
    water_right_cap_check,
    non_negative_diversion_check,
    minimum_utilisation_check,
    demand_floor_stabilizer,
    demand_ceiling_stabilizer,
    drought_severity_check,
    magnitude_cap_check,
    supply_gap_block_increase,
]

IRRIGATION_SOCIAL_CHECKS = [
    curtailment_awareness_check,
    compact_allocation_check,
]

IRRIGATION_TEMPORAL_CHECKS = [
    consecutive_increase_cap_check,
]

IRRIGATION_BEHAVIORAL_CHECKS = [
    zero_escape_check,
]

# Combined list for convenience
ALL_IRRIGATION_CHECKS = (
    IRRIGATION_PHYSICAL_CHECKS + IRRIGATION_SOCIAL_CHECKS
    + IRRIGATION_TEMPORAL_CHECKS + IRRIGATION_BEHAVIORAL_CHECKS
)


# =============================================================================
# Custom validator adapter for SkillBrokerEngine
# =============================================================================

def irrigation_governance_validator(proposal, context, skill_registry=None):
    """Bridge irrigation builtin checks to SkillBrokerEngine custom_validators.

    SkillBrokerEngine.custom_validators expects:
        (proposal, context, skill_registry) -> List[ValidationResult]

    This adapter extracts skill_name from the proposal and runs all
    irrigation builtin checks against the flattened context (which
    includes env_context keys like drought_index, curtailment_ratio, etc.).

    Usage in ExperimentBuilder::

        builder.with_custom_validators([irrigation_governance_validator])

    Or directly::

        broker = SkillBrokerEngine(
            ...,
            custom_validators=[irrigation_governance_validator],
        )
    """
    skill_name = getattr(proposal, "skill_name", str(proposal))
    results = []
    for check in ALL_IRRIGATION_CHECKS:
        results.extend(check(skill_name, [], context))
    return results
