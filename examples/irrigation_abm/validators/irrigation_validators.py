"""
Irrigation domain governance validators.

Provides BuiltinCheck functions for the irrigation domain. These are
injected into the existing validator framework via the ``builtin_checks``
constructor parameter, and run in the LLM arms through the
``irrigation_governance_validator`` bridge at the bottom of this module
(``custom_validators``).

Design follows the same pattern as flood-domain built-in checks
(FLOOD_PERSONAL_CHECKS, FLOOD_PHYSICAL_CHECKS, etc.) established
in the Phase 1 validator refactoring (commit fd861cf).

v3 governance (WP3, ``irrigation_v3_spec_2026-09-28.md`` section 3) has
two rule families:

- Feasibility rules. The supply rule, ``supply_gap_block_increase``, is the
  ONLY check this module dispatches (``ALL_IRRIGATION_CHECKS``). The
  water-right cap and the minimum-use floor are YAML identity rules
  (``config/agent_types.yaml``, every profile): they hide their option from
  the menu and block an off-menu answer, with the skill registry's
  preconditions as a second backstop.
- Thinking rules. TR1 ``high_scarcity_no_increase`` and TR3
  ``low_scarcity_no_decrease`` are YAML thinking rules (``strict`` only),
  evaluated by the broker's ``AgentValidator`` on the water-scarcity
  appraisal as FIRST STATED in the decision (the first parsed attempt's,
  unless that attempt gave none; ``global_config.governance.
  appraisal_freeze``).

Every other check below is kept only because tests or replays of older
corpora call it directly; each says "not dispatched in v3".

References:
    Hung, F., & Yang, Y. C. E. (2021). WRR, 57, e2020WR029262.
    Colorado River Compact (1922) — Upper/Lower Basin allocation rules.
"""

from typing import Any, Dict, List

from broker.interfaces.skill_types import ValidationResult
from broker.governance.rule_types import GovernanceRule
from examples.irrigation_abm.irrigation_personas import (
    FULL_SUPPLY_RATIO,
    describe_gap_reason,
    format_share,
    supply_ratio,
)

# Supply-side redesign (2026-09-25, spec S3): the sharing sentence every
# supply-gap message ends with. Under pro-rata sharing a larger request DOES
# raise that agent's share; what it does not do is add water, so the old
# "System cannot deliver more" was removed.
#
# WP1b (item 20, 2026-09-29): made sub-basin aware -- a function of the
# triggering context, not a fixed string, since WHO shares a shortage with
# this agent now depends on its basin, its sub-basin's member count, and
# whether the basin-wide backstop or its own sub-basin's supply is what
# bound (IrrigationEnvironment._settle). True in both ub_supply_mode
# values: a Lower Basin agent, or an Upper Basin agent whose basin-wide
# backstop bound (gap_reason ub_natural_flow / ub_capacity, or
# ub_supply_mode="lees_ferry_pool"), shares with the whole relevant basin
# exactly as before WP1b; only an Upper Basin agent whose OWN sub-basin
# bound (gap_reason ub_subbasin_supply) is scoped to "your sub-basin", and
# only when that sub-basin has more than one member -- H&Y's UT2 is alone
# in its sub-basin, so a larger UT2 request when UT2's own supply is short
# has no one else's delivery to lower (memo section 9).
def _sharing_sentence(context: Dict[str, Any]) -> str:
    """The sharing sentence that ends the supply rule's block message
    (spec 3.7; see the comment above for who shares with whom).

    WP1b re-review (HIGH 1, 2026-09-29): a real UB agent with gap_reason
    ``ub_subbasin_supply`` ALWAYS has a known ``ub_subbasin_member_count``
    (IrrigationEnvironment._settle only ever produces that code for an
    agent in one of the nine real sub-basins, and initialize_from_profiles
    computes the count for every such agent) -- a missing count reaching
    here is a wiring defect (the found bug: IrrigationLifecycleHooks.
    pre_year not copying it into validator_fields), never a legitimate
    state. Raise rather than silently falling back to "other Upper Basin
    users", which names the wrong users.

    WP3 (spec 3.7): the spec wording ("shared in proportion to requests",
    "would not add water"), plus a junior-priority variant for a Lower Basin
    agent whose OWN junior water the declared tier cuts this year (gap code
    ``lb_junior_tier_cut``, item 22, the same fact the WP1c dashboard warning
    states): its keep request already exceeds its senior entitlement, so any
    increase would be junior water, cut by the tier before the rest is
    shared. The supply rule only reaches this sentence when a PHYSICAL limit
    binds (Lake Mead's phi below 1 for the Lower Basin), so "shared in
    proportion to requests" is true for that agent too.
    """
    basin = context.get("basin")
    if basin not in ("upper_basin", "lower_basin"):
        raise ValueError(
            f"_sharing_sentence: basin={basin!r} is neither 'upper_basin' nor "
            "'lower_basin'; refusing to guess which users share this shortage."
        )
    if basin == "lower_basin":
        gap_codes = str(context.get("gap_reason") or "").split("+")
        if "lb_junior_tier_cut" in gap_codes:
            # The tier cuts a SHARE f of the junior part, not all of it: the
            # increase adds (1 - f) of itself to the shared pool (orchestrator
            # sign-off of the reviewer's wording, WP3 review round 1).
            # Direct index: pre_year always copies the fraction, and a code
            # of lb_junior_tier_cut with no positive fraction is a wiring
            # defect, never a state to phrase around.
            fraction = context["lb_junior_tier_cut_fraction"]
            if not fraction or fraction <= 0:
                raise ValueError(
                    "_sharing_sentence: gap_reason names lb_junior_tier_cut but "
                    f"lb_junior_tier_cut_fraction is {fraction!r}; refusing to "
                    "state a junior-priority cut without its share."
                )
            return (
                "When water is short it is shared in proportion to requests: "
                "any increase would be junior-priority water, about "
                f"{fraction:.0%} of which the declared shortage tier cuts, and "
                "the rest would raise your share only by lowering the "
                "deliveries of other users in the Lower Basin; it would not "
                "add water to the Lower Basin."
            )
        pool = "the Lower Basin"
    else:
        gap_codes = str(context.get("gap_reason") or "").split("+")
        member_count = context.get("ub_subbasin_member_count")
        if "ub_subbasin_supply" in gap_codes:
            if member_count is None:
                raise ValueError(
                    "_sharing_sentence: gap_reason names ub_subbasin_supply "
                    "but ub_subbasin_member_count is missing from context -- "
                    "IrrigationLifecycleHooks.pre_year must copy it into "
                    "validator_fields (HIGH 1, 2026-09-29 re-review); "
                    "refusing to silently fall back to basin-wide wording "
                    "that would name the wrong users."
                )
            if member_count <= 1:
                return "When water is short, a larger request would not add water."
            pool = "your sub-basin"
        else:
            # The basin-wide backstop bound (ub_natural_flow / ub_capacity),
            # lees_ferry_pool mode, or no shortfall at all: the whole Upper
            # Basin shares here regardless of member_count, so a missing
            # count is not a defect in this branch.
            pool = "the Upper Basin"
    # Spec item 29c: under sharing in proportion to requests a larger request
    # DOES raise this agent's share, by lowering the others' deliveries; it
    # adds no water to the pool they share.
    return (
        "When water is short it is shared in proportion to requests, so a "
        "larger request would raise your share only by lowering the "
        f"deliveries of other users in {pool}; it would not add water to "
        f"{pool}."
    )


def _tier_reason(context: Dict[str, Any]) -> str:
    """Phrase naming the declared Lower Basin shortage tier, for the
    demand-increase block message.

    PI decision 2026-09-28: the declared tier's shortage volume is borne
    entirely by the Lower Basin non-agricultural bucket, never by an
    agricultural agent's own delivery (that is why
    ``describe_gap_reason``'s ``lb_shortage_tier`` case was removed --
    it no longer describes any agent's actual gap). This helper only
    names the tier as institutional context for the increase-block rule
    below (DCP mandatory conservation policy), and does not claim the
    tier reduced the requesting agent's own delivery.

    Used only by ``curtailment_awareness_check``, which is not dispatched
    in v3 (WP3, spec 3.2): no v3 rule blocks on a declared tier.
    """
    tier = int(context.get("shortage_tier", 0) or 0)
    if tier <= 0:
        return ""
    return f"because a Tier {tier} Lower Basin shortage has been declared"


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

    NOT DISPATCHED IN v3 (WP3, spec 3.2): a duplicate of the YAML identity
    rule ``water_right_cap``, which every profile carries (it hides the
    increase option at the cap and blocks an off-menu increase, with the
    registry precondition ``not at_allocation_cap`` as a second backstop).
    Kept only because tests call it directly.
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

    NOT DISPATCHED IN v3 (WP3, spec 3.2): it never fires (audit L4 2.1) --
    a zero base is at the minimum-use floor, whose identity rule already
    hides and blocks a decrease. Kept only because tests call it directly.
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

    NOT DISPATCHED IN v3 (WP3, spec 3.2, PI item 2): the declared-tier
    increase block, its Tier 1 differential and its years 1-3 cold-start
    grace are retired together. Item 2 merged this rule and the 0.70
    supply-gap rule into the one supply rule (``supply_gap_block_increase``),
    which responds only to a physical supply limit; under item 14 a declared
    tier alone reduces no agricultural agent's delivery except a junior-
    priority part (item 22), which the supply rule deliberately ignores.
    Kept only because tests and replays of pre-v3 corpora call it directly.
    """
    if skill_name not in INCREASE_SKILLS:
        return []

    curtailment = context.get("curtailment_ratio", 0)
    if curtailment <= 0:
        return []
    # Re-review 2026-09-29 (NIT, then round 4 LOW 2): the acre-feet figure
    # matching build_water_situation_text's own HIGH-2 wording, not the
    # bare curtailment_ratio percentage (informational V/N, not itself an
    # acre-foot quantity a reader can act on). Direct index, not
    # .get(..., 0): a declared tier (curtailment > 0, just checked above)
    # with no lb_shortage_volume_maf in context is a real wiring defect --
    # IRRIGATION_CONTEXT_PRODUCERS declares this key guaranteed present --
    # not a legitimate "no shortage" case to silently paper over with a
    # fabricated 0.
    shortage_volume_af = context["lb_shortage_volume_maf"] * 1e6

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
                    f"Cold-start grace period (Year {year}): increase allowed "
                    f"although a Tier 2 Lower Basin shortage is declared "
                    f"(the non-agricultural allocation is cut {shortage_volume_af:,.0f} "
                    f"acre-ft); your own delivery is governed by Lake Mead's "
                    f"physical availability, not by this tier directly."
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
                    f"Demand increase blocked {_tier_reason(context)} "
                    f"(Lake Mead at {context.get('lake_mead_level', 0):.0f} ft on "
                    f"1 January). At Tier 2 or above, Lower Basin users may not "
                    f"increase requests."
                ],
                warnings=[],
                metadata={
                    "rule_id": "curtailment_awareness",
                    "category": "institutional",
                    "blocked_skill": skill_name,
                    "level": "ERROR",
                    "suggestion": (
                        f"Tier {shortage_tier} shortage blocks all increases this year."
                    ),
                },
            )
        ]

    # Tier 1: v17 differential governance blocked increase_large and
    # warned increase_small. WP2 (spec 2.2) collapsed the menu to one
    # increase skill, increase_demand, with no small/large distinction
    # (review MEDIUM 6, 2026-09-29) -- so the differential itself is now
    # moot for any live proposal, and the message must not offer a "small
    # increase" alternative the menu no longer has. The BLOCK branch below
    # is what a real increase_demand proposal actually reaches; the WARN
    # branch stays dead code for a caller that still passes the legacy
    # "increase_small" string directly (a replay of a pre-WP2 corpus), and
    # is left as-is (this rule, and its dead branch, were retired
    # unchanged when WP3 removed curtailment_awareness_check from
    # dispatch, spec 3.2).
    if shortage_tier == 1:
        if skill_name in ("increase_large", "increase_demand"):
            return [
                ValidationResult(
                    valid=False,
                    validator_name="IrrigationCurtailmentValidator",
                    errors=[
                        f"Demand increase blocked {_tier_reason(context)}: a Tier 1 "
                        f"Lower Basin shortage is declared, and this rule blocks "
                        f"every increase at that tier (subject to Lake Mead's "
                        f"physical availability for any request already made)."
                    ],
                    warnings=[],
                    metadata={
                        "rule_id": "curtailment_awareness",
                        "category": "institutional",
                        "blocked_skill": skill_name,
                        "level": "ERROR",
                        "suggestion": "A Tier 1 shortage blocks demand increases this year.",
                    },
                )
            ]
        else:
            # increase_small: warning only at Tier 1 -- dead for a live
            # v3 proposal (see comment above); kept for a replayed
            # pre-WP2 decision that still carries the legacy skill name.
            return [
                ValidationResult(
                    valid=True,
                    validator_name="IrrigationCurtailmentValidator",
                    errors=[],
                    warnings=[
                        f"Small increase allowed although a Tier 1 Lower Basin "
                        f"shortage is declared (the non-agricultural allocation "
                        f"is cut {shortage_volume_af:,.0f} acre-ft); your own "
                        f"delivery is governed by Lake Mead's physical "
                        f"availability, not by this tier directly."
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
                f"non-agricultural allocation cut {shortage_volume_af:,.0f} "
                f"acre-ft). Increasing demand may result in unmet allocation."
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

    F04 (2026-09-25 audit): nothing in the pipeline ever writes
    ``basin_allocation``, so this check returns ``[]`` unconditionally and
    has fired zero times across 49,140 audited strict rows. Excluded from
    ``ALL_IRRIGATION_CHECKS`` for that reason; kept here because
    ``tests/test_irrigation_env.py`` calls it directly. NOT covered by
    ``assert_validator_inputs_have_producers`` at import time (that runs
    against ``ALL_IRRIGATION_CHECKS``, which excludes this function) --
    see ``test_assert_validator_inputs_have_producers_catches_dead_key``
    for a direct test that it WOULD raise on ``basin_allocation`` if
    re-added. Re-add to ``IRRIGATION_SOCIAL_CHECKS`` only once a producer
    for ``basin_allocation`` exists.
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

    F04 (2026-09-25 audit): the real CRSS-driven drought index never
    reaches 0.7 in the irrigation paper runs (per-run maximum observed
    about 0.62-0.69), so this check has fired zero times across 49,140
    audited strict rows. Excluded from ``ALL_IRRIGATION_CHECKS`` for that
    reason; kept here because ``tests/test_irrigation_env.py`` calls it
    directly. This function reads a key that DOES have a producer
    (``drought_index``), so it is not an example
    ``assert_validator_inputs_have_producers`` would catch; it is excluded
    on a threshold-calibration ground, not a missing-producer one. Re-add
    to ``IRRIGATION_PHYSICAL_CHECKS`` only after recalibrating the
    0.7/0.85 thresholds against the real index range.
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

    NOT DISPATCHED IN v3 (WP3, spec 3.2): a duplicate of the YAML identity
    rule ``minimum_utilisation_floor``, which every profile carries (menu
    filter + block, with the registry precondition ``not
    below_minimum_utilisation`` as a second backstop). Kept only because
    tests call it directly.
    """
    if skill_name not in DECREASE_SKILLS:
        return []

    below_min = context.get("below_minimum_utilisation", False)
    if not below_min:
        return []

    water_right = context.get("water_right", "unknown")
    # F18a (2026-09-25 code review): "request" is never produced (see
    # IRRIGATION_CONTEXT_PRODUCERS); the real key is "current_request",
    # written by IrrigationLifecycleHooks.pre_year. Message-only fix -- the
    # gate above (below_minimum_utilisation) is unaffected.
    request = context.get("current_request", 0)
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

    F04 (2026-09-25 audit): ``magnitude_pct`` is not a field in the
    irrigation ``response_format`` the paper runs use, so the broker never
    injects ``proposed_magnitude`` and this check has fired zero times
    across 49,140 audited strict rows (WARNING-only by design, so it never
    blocked anything even when reachable). Excluded from
    ``ALL_IRRIGATION_CHECKS`` for that reason; kept here because
    ``tests/test_irrigation_env.py`` calls it directly. NOT covered by
    ``assert_validator_inputs_have_producers`` at import time (that runs
    against ``ALL_IRRIGATION_CHECKS``, which excludes this function) --
    see ``test_assert_validator_inputs_have_producers_catches_dead_key``
    for a direct test that it WOULD raise on ``proposed_magnitude`` if
    re-added. Re-add to
    ``IRRIGATION_PHYSICAL_CHECKS`` only once ``magnitude_pct`` is back in
    the response format (or another producer sets ``proposed_magnitude``).
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


# =============================================================================
# The v3 supply rule (WP3, spec 3.3; PI items 1 and 2)
# =============================================================================

# The per-decision inputs of the supply rule, in the order the audit writes
# them (config/agent_types.yaml, global_config.audit.state_columns ->
# state_<key> columns of the governance audit CSV). The WP6 post hoc
# evaluator re-applies the rule from exactly these logged values and
# FULL_SUPPLY_RATIO, in every arm (the disabled arm runs no supply rule).
SUPPLY_RULE_FIELDS = (
    "supply_keep_request_af",
    "supply_expected_at_keep_af",
    "supply_ratio",
    "supply_physical_ratio",
    "full_supply_ratio",
)


def supply_rule_fields(
    agent_context: Dict[str, Any],
    agent_state: Dict[str, Any],
) -> Dict[str, float]:
    """The supply rule's inputs for one agent-year, computed ONCE, before any
    decision (``IrrigationLifecycleHooks.pre_year``; the FQL runner uses the
    same helper), from the provisional settlement at every agent's keep
    request (``IrrigationEnvironment.advance_year``, provenance G9).

    - ``supply_keep_request_af``: the keep request, i.e. last year's receipt
      (WP2 spec 2.1 resets every request to it before the provisional
      settlement; ``agent_context["current_request"]``).
    - ``supply_expected_at_keep_af``: this year's expected delivery at that
      request (``agent_context["current_diversion"]``), including any
      declared junior-priority cut (item 22).
    - ``supply_ratio``: r = expected / keep, 6 places, 1.0 at a zero keep
      request (``irrigation_personas.supply_ratio``) -- the share the
      situation text and the block message show.
    - ``supply_physical_ratio``: the same share with the declared
      junior-priority cut taken out, i.e. only the PHYSICAL limits: for a
      Lower Basin agent Lake Mead's phi (the one physical limit on its
      delivery, ``IrrigationEnvironment._write_agent_deliveries``); for an
      Upper Basin agent r itself (its sub-basin supply and the basin-wide
      backstop are both physical; no declared cut exists there). 1.0 at a
      zero keep request, like r. This is what the rule compares with
      FULL_SUPPLY_RATIO. r <= physical ratio always, so an agent the rule
      blocks always reads a shortfall in r too.
    - ``full_supply_ratio``: the constant itself, logged beside the inputs.

    Raises on a Lower Basin agent without ``lb_phys_ratio`` (a wiring defect,
    never a legitimate "no physical limit" case) and on an unknown basin.
    """
    keep_af = float(agent_context["current_request"])
    expected_af = float(agent_context["current_diversion"])
    basin = agent_context["basin"]
    ratio = supply_ratio(expected_af, keep_af)
    if basin == "upper_basin":
        physical_ratio = ratio
    elif basin == "lower_basin":
        phi = agent_state["lb_phys_ratio"]
        if phi is None:
            raise ValueError(
                f"supply_rule_fields: Lower Basin agent "
                f"{agent_context.get('agent_id')!r} has lb_phys_ratio=None; "
                "IrrigationEnvironment._write_agent_deliveries sets it for "
                "every Lower Basin agent on every settlement."
            )
        physical_ratio = 1.0 if keep_af <= 0 else round(float(phi), 6)
    else:
        raise ValueError(
            f"supply_rule_fields: basin={basin!r} is neither 'upper_basin' "
            "nor 'lower_basin'."
        )
    return {
        "supply_keep_request_af": keep_af,
        "supply_expected_at_keep_af": expected_af,
        "supply_ratio": ratio,
        "supply_physical_ratio": physical_ratio,
        "full_supply_ratio": FULL_SUPPLY_RATIO,
    }


def supply_gap_block_increase(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """The supply rule (spec 3.3, PI items 1 and 2): block an increase when
    the water system cannot deliver even last year's receipt this year.

    Blocks ``increase_demand`` when the expected delivery at the keep request
    (last year's receipt), net of any declared junior-priority cut, is below
    ``FULL_SUPPLY_RATIO`` of that request -- ``supply_physical_ratio <
    FULL_SUPPLY_RATIO`` (see ``supply_rule_fields``). No other numeric
    threshold (item 2): the 0.70 supply-gap cutoff, the skip for Lower Basin
    rows under a declared Tier 2 or 3 and the separate zero-delivery branch
    are gone. The rule id is unchanged for audit continuity.

    It responds ONLY to physical supply limits: an Upper Basin sub-basin's
    own supply, the basin-wide Upper Basin backstop, and Lake Mead's physical
    availability (phi). A declared tier's proportional cut of a junior-
    priority part (item 22) is NOT one: a larger request still adds
    (1 - f) of the increase to the agent's own delivery, so blocking on the
    cut alone would ratchet the agent down under the WP2 base
    (request = last delivery). A declared tier alone never triggers it.

    The message states the numbers and the reason in plain words (spec
    3.7): the keep request, the expected delivery and r as a share, the
    present reason (``describe_gap_reason``) and who shares the shortage
    (``_sharing_sentence``: the sub-basin, the UT2-alone and the
    junior-priority variants). No rule id, law or agency, label code or
    appraisal field is named. ``metadata["grounding"] = "world"``: the
    rule reads only water-system state, which the model cannot write.
    """
    if skill_name not in INCREASE_SKILLS:
        return []

    physical_ratio = context["supply_physical_ratio"]
    if physical_ratio >= FULL_SUPPLY_RATIO:
        return []

    keep_af = context["supply_keep_request_af"]
    expected_af = context["supply_expected_at_keep_af"]
    ratio = context["supply_ratio"]
    reason = describe_gap_reason(context, "present")
    if not reason:
        # A physical ratio below FULL_SUPPLY_RATIO always comes with a
        # settlement gap code (IrrigationEnvironment._settle sets one
        # whenever a delivery ratio is below 1); none here means the gap
        # code never reached the validation context.
        raise ValueError(
            "supply_gap_block_increase: supply_physical_ratio="
            f"{physical_ratio} < FULL_SUPPLY_RATIO but gap_reason "
            f"{context.get('gap_reason')!r} gives no reason; refusing to "
            "state a block without its cause."
        )
    # Every share is the same within a sharing pool (a sub-basin's ratio,
    # the backstop factor, Lake Mead's phi), so a zero expected delivery
    # means nobody in the pool receives anything: a larger request would
    # then lower no one's delivery, and only "would not add water" is true.
    # A wording case only -- the trigger is the one condition above (the
    # pre-v3 separate zero-delivery TRIGGER branch is gone, spec 3.3).
    sharing = (
        "When water is short, a larger request would not add water."
        if expected_af <= 0 else _sharing_sentence(context)
    )
    message = (
        "Demand increase blocked under the shortage-sharing rule: if you "
        f"request the {keep_af:,.0f} acre-ft you received last year, you can "
        f"expect {expected_af:,.0f} acre-ft this year ({format_share(ratio)}), "
        f"{reason}. {sharing}"
    )
    return [
        ValidationResult(
            valid=False,
            validator_name="IrrigationSupplyGapValidator",
            errors=[message],
            warnings=[],
            metadata={
                "rule_id": "supply_gap_block_increase",
                "category": "physical",
                "blocked_skill": skill_name,
                "level": "ERROR",
                "suggestion": "The shortage-sharing rule blocks increases this year.",
                # Spec 3.9: a feasibility rule reads the world, not a label
                # the model wrote, so the audit grounding columns file its
                # blocks under rules_world_grounded.
                "grounding": "world",
                "supply_ratio": ratio,
                "supply_physical_ratio": physical_ratio,
                "full_supply_ratio": FULL_SUPPLY_RATIO,
            },
        )
    ]


# =============================================================================
# Phase C/D Pilot Validators — gated by module-level flags
# =============================================================================

# Feature flags. They gated the pilot-phase C/D checks below, which v3 no
# longer dispatches (WP3, spec 3.2); run_experiment.py now refuses
# --pilot-phase and --ablation-mode instead of setting them. They still gate
# a direct call (tests).
ENABLE_CONSECUTIVE_CAP = False
ENABLE_ZERO_ESCAPE = False
ENABLE_DEMAND_CEILING = True  # Gates demand_ceiling_stabilizer when called directly; the check is retired from dispatch

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

    NOT DISPATCHED IN v3 (WP3, spec 3.2): the pilot phases C and D that
    switched it on are refused by ``run_experiment.py`` (``--pilot-phase``).
    Kept only because tests call it directly.
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

    RETIRED FROM DISPATCH (supply-side redesign, 2026-09-25, decision Q3,
    retirement of both stabilizers):
    no longer in ``IRRIGATION_PHYSICAL_CHECKS``. It was motivated by the
    same 5.86 MAF CRSS basin target as the retired demand ceiling, and it
    bound for 61 of 78 agents from year 1 (their 2018 use sits below half
    of the top of their FQL diversion grid, F10). The governed corridor is
    now the 10 percent minimum-utilisation floor and the water right. Kept
    so older corpora can be reproduced and for direct tests.
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

    RETIRED FROM DISPATCH (supply-side redesign, 2026-09-25; decision D1 makes
    the basin limit supply-side availability, decision Q3 retires both
    stabilizers):
    no longer in ``IRRIGATION_PHYSICAL_CHECKS``. The basin limit is now
    physical availability, enforced on the supply side by the water balance
    (``IrrigationEnvironment._settle``: deliveries never exceed what Lake
    Powell and Lake Mead can supply, shared pro-rata), as in Hung and Yang
    (2021), where the delivered diversion comes from CRSS and nothing caps
    the basin request total. The quantity survives as a logged metric,
    ``basin_request_over_target`` (request total / 5.86 MAF) in
    ``simulation_log.csv``. Kept so older corpora can be reproduced and for
    direct tests; ``ENABLE_DEMAND_CEILING`` still gates it when called.
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

    NOT DISPATCHED IN v3 (WP3, spec 3.2): switched off with the pilot phase
    D that enabled it (``--pilot-phase`` is refused); no v3 rule blocks
    keep. Kept only because tests call it directly.
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

# F04 (2026-09-25 audit): drought_severity_check, compact_allocation_check
# and magnitude_cap_check are intentionally NOT in these lists. All three
# read a context key that nothing in the real pipeline ever produces (or,
# for drought_severity_check, a threshold the real CRSS data never
# reaches), so across 49,140 audited strict rows they fired zero times.
# The functions stay defined above (docstrings note why) because
# tests/test_irrigation_env.py exercises them directly. Correction (second
# code-review pass, 2026-09-25): they are NOT run through
# assert_validator_inputs_have_producers() below -- its default call only
# scans ALL_IRRIGATION_CHECKS, which excludes all three by design. Only
# an explicit call naming them (as
# test_assert_validator_inputs_have_producers_catches_dead_key does)
# exercises the self-check against them.
# Supply-side redesign (2026-09-25): demand_floor_stabilizer and
# demand_ceiling_stabilizer are retired from dispatch (decision Q3, on top of
# D1's supply-side basin limit; see
# their docstrings). The functions stay defined above and are tested
# directly.
# v3 (WP3, spec 3.2): the supply rule is the ONLY dispatched check.
# Removed from dispatch, each with a "not dispatched in v3" docstring:
# curtailment_awareness_check (merged into the supply rule, PI item 2),
# water_right_cap_check and minimum_utilisation_check (duplicates of the
# YAML identity rules every profile carries), non_negative_diversion_check
# (never fires), consecutive_increase_cap_check and zero_escape_check
# (switched off with the pilot phases). The empty lists stay so the
# ValidatorRegistry registration in validators/__init__.py and the
# importers of these names keep working.
IRRIGATION_PHYSICAL_CHECKS = [
    supply_gap_block_increase,
]

IRRIGATION_SOCIAL_CHECKS: List = []

IRRIGATION_TEMPORAL_CHECKS: List = []

IRRIGATION_BEHAVIORAL_CHECKS: List = []

# Combined list for convenience
ALL_IRRIGATION_CHECKS = (
    IRRIGATION_PHYSICAL_CHECKS + IRRIGATION_SOCIAL_CHECKS
    + IRRIGATION_TEMPORAL_CHECKS + IRRIGATION_BEHAVIORAL_CHECKS
)

# =============================================================================
# F04: startup self-check: every context key a registered check reads must
# have a producer somewhere in the pipeline
# =============================================================================

# Context keys guaranteed present before ANY irrigation governance check
# runs. Source of truth for the first block is
# ``examples/irrigation_abm/run_experiment.py``
# (``IrrigationLifecycleHooks.pre_year``'s ``validator_fields`` dict).
# Source of truth for the second block is
# ``broker/core/skill_broker_engine.py``'s ``validation_context``, which
# builds ``**flat_env`` from ``IrrigationEnvironment.advance_year()``'s
# returned ``self._global.copy()`` -- exactly these four keys, no more.
# "precipitation", "lake_mead_level" and "preceding_factor" live in
# ``self._basins``, a DIFFERENT dict ``advance_year()`` does not return;
# ``IrrigationEnvironment.get_agent_context()`` does expose them, but
# nothing in ``broker/`` calls that method on the validation path, so
# they are deliberately NOT listed here (2026-09-25 code review caught
# this: the first version of this list wrongly included them). Update
# this set whenever a new check is added or ``pre_year``/the broker's
# env merge stops writing one of these fields: that drift (a check
# reading a key nobody writes any more) is exactly what F04 found.
IRRIGATION_CONTEXT_PRODUCERS = frozenset({
    # written directly by IrrigationLifecycleHooks.pre_year
    "agent_id", "at_allocation_cap", "has_efficient_system",
    "below_minimum_utilisation", "water_right", "current_diversion",
    "current_request", "curtailment_ratio", "shortage_tier", "cluster",
    "basin", "loop_year",
    # supply-side redesign (2026-09-25): read by the rule messages
    "gap_reason", "delivery_ratio", "lake_mead_level",
    # re-review 2026-09-29 (NIT): read by curtailment_awareness_check's
    # acre-feet wording (IrrigationLifecycleHooks.pre_year's
    # validator_fields now wires it from ctx["lb_shortage_volume_maf"]).
    "lb_shortage_volume_maf",
    # WP1b re-review (HIGH 1, 2026-09-29): read by _sharing_sentence, a
    # helper supply_gap_block_increase calls (this static scan only reads
    # supply_gap_block_increase's own source text, so it will not catch
    # these two on its own -- listed here anyway to keep this registry an
    # honest record of every key the pipeline actually produces for a
    # governance-reachable message, not just what the scanner can see).
    "supply_group", "ub_subbasin_member_count",
    # v3 (WP3, spec 3.3): the supply rule's own inputs (supply_rule_fields,
    # copied into validator_fields by pre_year), and the junior-priority cut
    # fraction describe_gap_reason reads for the block message's reason
    # (gap code lb_junior_tier_cut).
    "supply_keep_request_af", "supply_expected_at_keep_af", "supply_ratio",
    "supply_physical_ratio", "full_supply_ratio",
    "lb_junior_tier_cut_fraction",
    # auto-injected from env_context by the broker's env merge
    "drought_index", "total_available_water", "total_basin_demand", "year",
})


def assert_validator_inputs_have_producers(
    checks=None,
    known_producers: frozenset = IRRIGATION_CONTEXT_PRODUCERS,
) -> None:
    """Fail fast if a registered check reads a context key nothing produces.

    Static, source-level scan: for every literal ``context.get("key", ...)``
    or ``context["key"]`` found in a check function's source, ``key`` must
    be in *known_producers*. This is the guard F04 asked for: it is what
    would have caught ``compact_allocation_check`` reading
    ``basin_allocation`` (nothing writes it) before the check shipped
    silently inert for the life of the irrigation paper runs.

    Not a substitute for behavioural review: a key CAN have a producer and
    still never carry the value a check needs (for example a real
    threshold the data never crosses, drought_severity_check's 0.7 floor);
    this only catches the "nothing writes this key, ever" class F04 was
    built around.

    Raises:
        RuntimeError: naming each offending check and its unproduced keys.
    """
    import inspect
    import re

    if checks is None:
        checks = ALL_IRRIGATION_CHECKS

    key_pattern = re.compile(
        r"""context\.get\(\s*["'](\w+)["']|context\[\s*["'](\w+)["']\s*\]"""
    )
    problems = []
    for check in checks:
        try:
            src = inspect.getsource(check)
        except (OSError, TypeError):
            continue
        keys = {m.group(1) or m.group(2) for m in key_pattern.finditer(src)}
        unknown = keys - known_producers
        if unknown:
            problems.append((getattr(check, "__name__", str(check)), sorted(unknown)))

    if problems:
        detail = "; ".join(f"{name} reads {keys}" for name, keys in problems)
        raise RuntimeError(
            "assert_validator_inputs_have_producers: the following "
            "irrigation governance checks in ALL_IRRIGATION_CHECKS read a "
            f"context key nothing in the pipeline writes: {detail}. Wire a "
            "producer for that key, add it to IRRIGATION_CONTEXT_PRODUCERS "
            "with a note why, or remove the check from ALL_IRRIGATION_CHECKS "
            "(see F04, .ai/framework_case_audit_2026-09-25.md)."
        )


# Run once at import time: this is pure source-level static analysis (no
# runtime state needed), so importing this module IS "experiment startup"
# for the purpose of failing fast.
assert_validator_inputs_have_producers()


# =============================================================================
# Custom validator adapter for SkillBrokerEngine
# =============================================================================

def irrigation_governance_validator(proposal, context, skill_registry=None):
    """Bridge irrigation builtin checks to SkillBrokerEngine custom_validators.

    SkillBrokerEngine.custom_validators expects:
        (proposal, context, skill_registry) -> List[ValidationResult]

    This adapter extracts skill_name from the proposal and runs the
    dispatched irrigation checks (``ALL_IRRIGATION_CHECKS``: in v3, the
    supply rule only) against the flattened context (the agent's validator
    fields from ``IrrigationLifecycleHooks.pre_year`` plus env_context keys).
    Wired in every profile but ``disabled`` (run_experiment.py).

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
