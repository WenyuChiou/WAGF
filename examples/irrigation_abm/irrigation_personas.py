"""
Irrigation agent persona builder.

Generates narrative personas and context strings for LLM prompt injection,
analogous to the flood experiment's memory_templates.py.  Personas are
derived from the three FQL behavioral clusters (Hung & Yang 2021).

Each agent receives:
- A narrative persona describing their water management style
- Water situation text describing current conditions
- Conservation status
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from examples.irrigation_abm.irrigation_env import CRSS_DEMAND_TARGET_AF


@dataclass
class IrrigationAgentProfile:
    """Profile for a single irrigation farmer agent.

    FQL parameters are stored for reference and Group A baseline,
    but the LLM groups (B, C) use persona text instead.
    """

    agent_id: str
    basin: str  # "upper_basin" or "lower_basin"
    cluster: str  # "aggressive", "forward_looking_conservative", "myopic_conservative"

    # FQL reference parameters (for Group A and audit)
    mu: float = 0.20
    sigma: float = 0.70
    alpha: float = 0.75
    gamma_param: float = 0.70  # Avoid shadowing builtins
    epsilon: float = 0.15
    regret: float = 1.50
    forget: bool = True

    # Farm characteristics
    farm_size_acres: float = 500.0
    water_right: float = 100_000.0  # acre-ft/year
    crop_type: str = "mixed"  # alfalfa, cotton, vegetables, mixed
    years_farming: int = 20
    has_efficient_system: bool = False
    actual_2018_diversion: Optional[float] = None  # Historical 2018 diversion (acre-ft)

    # Hung and Yang (2021) action model: step = (mu + |N(0, sigma)|) x
    # bin_size_af (mu and sigma above are that model's per-agent parameters).
    # bin_size_af = the step of the agent's discretised diversion grid
    # (Div_States/*_discrete_states.csv, agt_states[2] - agt_states[1]);
    # None = synthetic profile, the environment falls back to water_right / 25.
    # NOTE: bin_size_af is the Hung and Yang STEP size and is never touched
    # by the water_right history-anchor (see below); it always comes from
    # the grid regardless of which ceiling water_right ends up at.
    bin_size_af: Optional[float] = None

    # History-anchor ceiling (2026-09-26, water-right history-anchor):
    # water_right above is min(grid_top_af, (1 + paper_water_margin) *
    # peak_obs_af) for profiles built by create_profiles_from_data (see its
    # docstring); these three fields record
    # which bound applied and from what. None for profiles that do not go
    # through that path (create_profiles_from_csv, synthetic builders),
    # where water_right is set directly and grid_top_af/peak_obs_af have no
    # meaning.
    grid_top_af: Optional[float] = None  # top of the Div_States grid (Div_max)
    peak_obs_af: Optional[float] = None  # observed peak, 1971-2018, same series as actual_2018_diversion
    water_right_source: Optional[str] = None  # "grid_top" or "peak_scaled"

    # Narrative (generated)
    narrative_persona: str = ""
    water_situation_summary: str = ""


# ============================================================================
# Cluster-based persona templates
# ============================================================================

_PERSONA_OPENING = (
    "You are {agent_id}, an agriculture water user (an irrigation district "
    "or a group of water users) in the {basin_name} of the Colorado River "
    "Basin, holding a water right of {water_right:,.0f} acre-ft/year. "
)

_CLUSTER_PERSONAS = {
    "aggressive": [
        (
            _PERSONA_OPENING
            + "You are known for making bold, quick adjustments to your "
            "water orders. When water conditions change, you act "
            "immediately, sometimes requesting significantly more water "
            "when you sense an opportunity, and cutting back sharply when "
            "you detect shortages ahead. You would rather overshoot your "
            "water request and face a small penalty than be too cautious "
            "and miss a productive season. "
            "With your established water right, you feel confident in "
            "your ability to adapt your water use when needed."
        ),
        (
            _PERSONA_OPENING
            + "You have learned that waiting too long to adjust water "
            "demand can be costly. You respond swiftly to changes in "
            "precipitation patterns and river conditions. Your approach: "
            "it's better to request too much water and have some returned "
            "than to request too little and come up short. You aren't "
            "particularly worried about unmet demand penalties; you focus "
            "on maximising your water use. "
            "Your water allocation and operational flexibility give you "
            "strong capacity to adapt to changing conditions."
        ),
    ],
    "forward_looking_conservative": [
        (
            _PERSONA_OPENING
            + "You believe in steady, measured adjustments to water "
            "demand, never making dramatic changes. You learn quickly "
            "from each season's outcomes and always think about the long "
            "term. The thought of facing a water shortage deeply concerns "
            "you; you would rather use a little less water than risk a "
            "curtailment penalty. "
            "Your careful planning and willingness to invest in efficient "
            "systems give you moderate-to-good ability to adapt your "
            "water use."
        ),
        (
            _PERSONA_OPENING
            + "You are known as a careful planner. You adjust your water "
            "request only after thoroughly considering the evidence: "
            "precipitation data, Lake Mead levels, and your own past "
            "experience. You are willing to experiment with new "
            "approaches but always in small, measured steps. Running "
            "short of water is your worst-case scenario; you hate the "
            "idea of demand going unmet. You keep detailed records and "
            "plan ahead. "
            "Your proactive planning and openness to efficiency "
            "improvements provide you reasonable capacity to adapt when "
            "conditions change."
        ),
    ],
    "myopic_conservative": [
        (
            _PERSONA_OPENING
            + "You believe strongly in following the practices that have "
            "worked before. Why change what isn't broken? You make only "
            "minor adjustments to your water demand from year to year. "
            "You are sceptical of forecasts and new technologies. You "
            "rarely try completely new strategies, preferring to rely on "
            "your own accumulated knowledge and the patterns you've "
            "observed over decades of water management. "
            "Your limited technology investment constrains your options "
            "for adapting water use if conditions deteriorate."
        ),
        (
            _PERSONA_OPENING
            + "You trust your own experience above all else. You see "
            "other water users making dramatic changes to their water "
            "orders and think they're overreacting. You adjust your "
            "demand only slightly each year, steady as she goes. You're "
            "moderately concerned about water shortages but believe that "
            "staying the course has served you well so far. New ideas "
            "need to prove themselves elsewhere before you'll try them "
            "here. "
            "Your reliance on traditional methods and limited resources "
            "make it harder for you to adapt your water practices under "
            "pressure."
        ),
    ],
}

_BASIN_DISPLAY = {
    "upper_basin": "Upper Colorado River Basin",
    "lower_basin": "Lower Colorado River Basin",
}


def build_narrative_persona(
    profile: IrrigationAgentProfile,
    rng: Optional[np.random.Generator] = None,
) -> str:
    """Generate a narrative persona string from an agent profile.

    Randomly selects from cluster-specific templates and fills in
    agent-specific details.
    """
    rng = rng or np.random.default_rng()
    templates = _CLUSTER_PERSONAS.get(profile.cluster, _CLUSTER_PERSONAS["myopic_conservative"])
    template = templates[rng.integers(0, len(templates))]

    return template.format(
        agent_id=profile.agent_id,
        basin_name=_BASIN_DISPLAY.get(profile.basin, profile.basin),
        water_right=profile.water_right,
    )


# Supply-side redesign (2026-09-25, spec S1 to S6): ONE helper turns the
# settlement's gap_reason code into the phrase every message uses (situation
# text, the supply-gap and shortage rule messages, the yearly memory line),
# so the stated reason cannot drift between texts.
_TIER_BY_CUT = {0.05: 1, 0.10: 2, 0.20: 3}


def _tier_from_state(state: Dict[str, Any]) -> int:
    tier = state.get("shortage_tier")
    if isinstance(tier, (int, float)) and tier > 0:
        return int(tier)
    cut = round(float(state.get("curtailment_ratio", 0) or 0), 2)
    return _TIER_BY_CUT.get(cut, 0)


def describe_gap_reason(agent_state: Dict[str, Any]) -> str:
    """Phrase for why this agent's delivery is below its request.

    ``agent_state`` needs ``gap_reason`` (a settlement code from
    ``IrrigationEnvironment._settle``) and, for the Lower Basin shortage
    code, ``curtailment_ratio`` (and ``shortage_tier`` when available).
    Returns "" for ``none`` or a missing code; otherwise a phrase starting
    with "because", ready to follow a comma.
    """
    code = str(agent_state.get("gap_reason") or "none")
    if code == "none":
        return ""
    parts = []
    for c in code.split("+"):
        if c == "ub_capacity":
            cap = float(agent_state.get("ub_capacity_maf", 5.0) or 5.0)
            parts.append(f"Upper Basin deliveries are limited to the {cap:.1f} million "
                         f"acre-ft delivery capacity, shared pro-rata")
        elif c == "ub_powell_release":
            parts.append("Upper Basin deliveries were reduced pro-rata so Lake Powell can "
                         "make its minimum release to Lake Mead")
        elif c == "lb_shortage_tier":
            cut = float(agent_state.get("curtailment_ratio", 0) or 0)
            tier = _tier_from_state(agent_state)
            tier_text = f"Tier {tier} " if tier else ""
            parts.append(f"the {tier_text}Lower Basin shortage reduces Lower Basin "
                         f"deliveries by {cut:.0%}")
        elif c == "lb_mead_availability":
            parts.append("Lake Mead cannot meet all Lower Basin withdrawals this year "
                         "without falling below its minimum pool, so all Lower Basin "
                         "deliveries are reduced pro-rata")
    if not parts:
        return ""
    return "because " + " and ".join(parts)


def _with_reason(text: str, reason: str) -> str:
    return f"{text}, {reason}" if reason else text


def build_water_situation_text(
    env_context: Dict[str, Any],
    last_year: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate water situation text from environment context.

    This is injected into the prompt as ``{water_situation_text}``.

    Supply-side redesign (2026-09-25, spec S1): the Lower Basin shortage
    line appears only for Lower Basin agents (tiers bind the Lower Basin
    only); Upper Basin agents see natural flow and Lake Powell storage; every
    agent sees last year's request and delivery (``last_year``: the F05
    snapshot, with ``request``, ``diversion`` and ``gap_reason``) and the
    delivery it can expect at its current request, with the same reason
    phrase as the rule messages and the memory line (describe_gap_reason).
    "Full allocation is available" appears only when the expected delivery
    is the whole request.
    """
    year = env_context.get("year", "unknown")
    basin = env_context.get("basin", "unknown")
    drought = env_context.get("drought_index", 0)
    precip = env_context.get("precipitation", 0)
    mead = env_context.get("lake_mead_level", 0)
    curtailment = env_context.get("curtailment_ratio", 0)
    shortage_tier = env_context.get("shortage_tier", 0)
    current_req = env_context.get("current_request", 0)
    expected = env_context.get("current_diversion", 0)
    ratio = env_context.get("delivery_ratio", 1.0)
    water_right = env_context.get("water_right", 0)

    basin_display = _BASIN_DISPLAY.get(basin, basin)

    lines = [f"It is now the year {year}. You divert water in the {basin_display}."]

    # Drought signal: balanced framing (positive when low, negative when high).
    # Supply-side redesign follow-up (regression audit 2026-09-26, finding
    # N6): the headline used to be keyed on drought_index alone, so it could
    # read "favorable" or "adequate" while the expected-delivery sentence a
    # few lines below says the agent will receive under half its request
    # (560 strict prompts, 1904 disabled in the seed-42 pilot pair). The
    # headline now uses the MORE SEVERE of the drought-index tier and a
    # delivery-ratio tier: a ratio below 0.5 forces the most severe tier;
    # 0.5 up to (not including) 0.7 floors the headline at the "below
    # normal" tier. When the ratio tier is STRICTLY more severe than the
    # drought tier, the headline uses a supply-keyed sentence instead of the
    # drought-keyed one, so a delivery shortfall is never described as
    # drought; a tie (or drought more severe) keeps the drought-keyed
    # wording, byte-identical to before this fix.
    if drought < 0.2:
        drought_tier = 0
    elif drought < 0.5:
        drought_tier = 1
    elif drought < 0.8:
        drought_tier = 2
    else:
        drought_tier = 3

    if ratio < 0.5:
        ratio_tier = 3
    elif ratio < 0.7:
        ratio_tier = 1
    else:
        ratio_tier = 0

    if ratio_tier > drought_tier:
        if ratio_tier == 3:
            lines.append(
                "Water supply is critically short this year: expected "
                "deliveries fall well below requests."
            )
        else:
            lines.append("Water supply is below normal this year.")
    elif drought_tier == 0:
        lines.append(
            "Water supply conditions are favorable this year. "
            "Precipitation is near or above normal and reservoir levels are healthy."
        )
    elif drought_tier == 1:
        lines.append(
            "Water supply is adequate but slightly below normal. "
            "Mild dryness has marginally reduced availability."
        )
    elif drought_tier == 2:
        lines.append(
            "Water supply is tight this year. "
            "Below-normal precipitation has significantly reduced available water."
        )
    else:
        lines.append(
            "Water supply is critically short. "
            "Severe drought has sharply reduced available water."
        )

    # Basin-specific signal
    if basin == "upper_basin":
        lines.append(
            f"Winter precipitation in your region was {precip:.0f} mm "
            f"({'above' if env_context.get('preceding_factor', 0) else 'below'} last year)."
        )
        nf = env_context.get("natural_flow_maf")
        powell = env_context.get("powell_storage_maf")
        # Regression audit 2026-09-26, finding N7: a Powell at the dead-pool floor
        # (all of it dead storage) still read "Lake Powell holds 1.9 million
        # acre-ft on 1 January" as if that were usable water (1120 prompts in
        # the seed-42 pilot pair). powell_dead_pool_maf is threaded in from
        # irrigation_env.py (IrrigationEnvironment.get_agent_context); when
        # absent (an older context dict) the sentence stays byte-identical.
        powell_dead_pool = env_context.get("powell_dead_pool_maf")
        if nf:
            lines.append(f"Natural flow on the river this year is forecast at {nf:.1f} million acre-ft.")
        if powell:
            if powell_dead_pool is not None and powell <= powell_dead_pool + 1e-6:
                lines.append(
                    "Lake Powell is at its dead-pool floor on 1 January; "
                    "releases are limited to inflow."
                )
            else:
                lines.append(f"Lake Powell holds {powell:.1f} million acre-ft on 1 January.")
    else:
        lines.append(
            f"Lake Mead was at {mead:.0f} feet above sea level on 1 January "
            f"({'rising' if env_context.get('preceding_factor', 0) else 'declining'} from last year)."
        )
        if shortage_tier > 0:
            lines.append(
                f"The Bureau of Reclamation has declared a Tier {shortage_tier} Lower Basin "
                f"shortage: Lower Basin deliveries are reduced by {curtailment:.0%}."
            )
        else:
            lines.append("No Lower Basin shortage has been declared for this year.")

    # Last year's actual outcome (final settlement)
    if last_year and last_year.get("request", 0) > 0:
        lr = last_year.get("request", 0)
        ld = last_year.get("diversion", 0)
        lines.append(_with_reason(
            f"Last year you requested {lr:,.0f} acre-ft and received {ld:,.0f} acre-ft "
            f"({ld / lr:.0%} delivered)", describe_gap_reason(last_year)) + ".")

    # This year's expectation at the current request
    if ratio >= 1.0 - 1e-9:
        lines.append(
            f"At your current request of {current_req:,.0f} acre-ft you can expect full "
            f"delivery this year. Full allocation is available."
        )
    else:
        lines.append(_with_reason(
            f"At your current request of {current_req:,.0f} acre-ft, expected delivery this "
            f"year is {expected:,.0f} acre-ft ({ratio:.0%} of your request)",
            describe_gap_reason(env_context)) + ".")

    utilisation = (current_req / water_right * 100) if water_right > 0 else 0
    lines.append(
        f"Your request is {utilisation:.0f}% of your water right of "
        f"{water_right:,.0f} acre-ft/year."
    )

    # NOTE: Supply-demand gap feedback is also shown by the generic
    # FeedbackDashboardProvider via YAML assertions in agent_types.yaml.

    return "\n".join(lines)


def build_conservation_status(profile: IrrigationAgentProfile) -> str:
    """Return conservation status string for prompt."""
    if profile.has_efficient_system:
        return "already use"
    return "have not yet adopted"


def build_aca_hint(cluster: str) -> str:
    """Return adaptive-capacity anchoring text per cluster.

    Provides an explicit cue so the LLM's ACA appraisal reflects
    the cluster's actual implementation capacity, improving construct
    discrimination across clusters.
    """
    _ACA_HINTS = {
        "aggressive": (
            "strong — you have the financial resources and operational "
            "flexibility to adapt your water use quickly when needed"
        ),
        "forward_looking_conservative": (
            "moderate — you plan carefully and can make measured "
            "adjustments, though large changes require significant effort"
        ),
        "myopic_conservative": (
            "limited — your smaller operation and reliance on traditional "
            "methods constrain what you can realistically change"
        ),
    }
    return _ACA_HINTS.get(cluster, _ACA_HINTS["myopic_conservative"])


def _build_trend_text(basin: str, preceding_factor: int) -> str:
    """Basin-appropriate "last year" trend sentence for memory feedback.

    F15 (2026-09-25 audit): for the 22 Lower Basin agents, ``preceding_factor``
    is the Lake Mead rising/declining flag (see
    ``IrrigationEnvironment._update_preceding_factors``), not a precipitation
    signal; Upper Basin precipitation is not even observed at a Lower Basin
    agent's location. ``build_water_situation_text`` already branches this
    way; the feedback builders below did not, so every Lower Basin memory
    line claimed a precipitation trend that was actually the reservoir
    trend.
    """
    if basin == "upper_basin":
        return f"Precipitation was {'above' if preceding_factor else 'below'} last year."
    return f"Lake Mead level was {'rising' if preceding_factor else 'declining'} last year."


# Plain-language label (with its article) for the first blocking rule in the
# neutral memory line.
_RULE_LABELS = {
    "curtailment_awareness": "the Lower Basin shortage rule",
    "supply_gap_block_increase": "the shortage-sharing rule",
    "high_threat_high_cope_no_increase": "the scarcity-capacity consistency rule",
    "low_threat_no_increase": "the low-scarcity rule",
    "observed_scarcity_low_wsa_increase": "the observed-scarcity rule",
    "water_right_cap": "the water-right cap",
    # Regression audit 2026-09-26, finding N5: the disabled arm's ONLY blocking
    # rule is this precondition check (an increase proposed while already
    # at the water-right cap), and it had no entry here, so every neutral
    # rejection line in the disabled pilot fell back to "a governance rule"
    # (910 lines). Same phrase as water_right_cap above: it is the same cap,
    # enforced as a precondition instead of an identity rule.
    "precondition_violation": "the water-right cap",
    "minimum_utilisation_floor": "the minimum-use floor",
    "zero_escape_floor": "the minimum-use rule for maintaining",
    "consecutive_increase_cap": "the consecutive-increase limit",
    "non_negative_diversion": "the zero-delivery rule",
}


def build_action_outcome_feedback(
    action_ctx: Optional[Dict[str, Any]],
    year: int,
    request: float,
    diversion: float,
    drought_index: float,
    preceding_factor: int,
    basin: str = "upper_basin",
    gap_reason: str = "",
    rejection_line_style: str = "explicit",
) -> str:
    """Build combined action + outcome feedback for memory.

    Prepends the agent's action choice (and magnitude if applicable) to the
    factual outcome (request/diversion/shortfall/drought index/basin trend)
    so the agent can form causal links between decisions and outcomes
    during reflection.

    ``basin`` selects the F15-corrected trend wording via
    ``_build_trend_text``; it defaults to ``"upper_basin"`` (the original,
    precipitation-only wording) so callers that predate the basin parameter
    keep their exact prior text.

    ``gap_reason`` is the ``describe_gap_reason`` phrase appended to the
    shortfall sentence ("" = the pre-redesign sentence).
    ``rejection_line_style`` (``explicit`` default, the shipped text naming
    the rejected proposal; ``neutral``: "Year N: <applied action> was
    applied under the <rule label>.", which does not name the proposal).
    """
    gap = max(0.0, request - diversion)
    gap_pct = (gap / request * 100.0) if request > 0 else 0.0

    if gap > 0:
        # gap_reason: the describe_gap_reason phrase (supply-side redesign,
        # spec S6); "" keeps the pre-redesign sentence byte-for-byte.
        shortfall = _with_reason(
            f"Shortfall: {gap:,.0f} acre-ft ({gap_pct:.0f}% unmet)", gap_reason) + "."
    else:
        shortfall = "Demand fully met."

    outcome = (
        f"You requested {request:,.0f} acre-ft and received "
        f"{diversion:,.0f} acre-ft. {shortfall} "
        f"Drought index: {drought_index:.2f}. {_build_trend_text(basin, preceding_factor)}"
    )

    # Action portion (from _last_action_context stored by framework)
    if action_ctx and action_ctx.get("skill_name"):
        skill = action_ctx["skill_name"].replace("_", " ")
        if action_ctx.get("was_fallback") and rejection_line_style == "neutral":
            # Neutral style (memory.rejection_line_style): names the rule and
            # the action that was applied, not the rejected proposal.
            rules = action_ctx.get("blocking_rules") or []
            if action_ctx.get("proposed_skill") and rules:
                label = _RULE_LABELS.get(rules[0], "a governance rule")
                lead = f"Year {year}: {skill} was applied under {label}"
            elif action_ctx.get("proposed_skill"):
                lead = f"Year {year}: {skill} was applied under a governance rule"
            else:
                lead = f"Year {year}: no valid decision was read; {skill} was applied"
            return lead + ". " + outcome
        if action_ctx.get("was_fallback"):
            # Governance rejected the proposal and the registry default skill
            # was executed in its place; "You chose" would be false here.
            proposed = action_ctx.get("proposed_skill")
            if proposed:
                lead = (f"Year {year}: your proposal to "
                        f"{proposed.replace('_', ' ')} was rejected; "
                        f"{skill} was applied")
            else:
                lead = (f"Year {year}: no valid proposal was made; "
                        f"{skill} was applied")
            return lead + ". " + outcome
        parts = [f"Year {year}: You chose to {skill}"]
        mag = action_ctx.get("magnitude_pct")
        if mag is not None:
            parts.append(f"(by {mag:.0f}%)")
        return " ".join(parts) + ". " + outcome

    # Fallback: outcome-only (year 1 or missing context)
    return f"Year {year}: {outcome}"


# ============================================================================
# Shared simulation_log.csv row builder (LLM run + FQL baseline)
# ============================================================================

def read_lake_mead_level_for_log(env: Any) -> float:
    """Read ``lower_basin.lake_mead_level`` for a simulation-log row.

    Shared between ``run_experiment.py``'s
    ``IrrigationLifecycleHooks._log_lake_mead_level`` and
    ``run_fql_baseline.py``'s ``run_simulation`` (2026-09-27 fix) so both
    runners fail the same way instead of two different ones.

    Review P1-b: this was the one physical-state read that stayed outside
    the ``coupling.context_contract`` guard -- ``get_agent_context()``
    (guarded) and this logger (unguarded, ``get_local(..., 0)``) read the
    SAME field, so with the flag ON a missing reservoir level would raise
    for the prompt and quietly write 0 into the analysis CSV, the two
    artifacts of one run disagreeing about whether the value existed.
    With the flag OFF the expression is character-for-character the old
    one, so every frozen corpus reproduces byte-identically.
    """
    if getattr(env, "_coupling_contract_active", False):
        level = env.get_local("lower_basin", "lake_mead_level")
        if level is None:
            raise KeyError(
                "lake_mead_level is missing from lower_basin and "
                "coupling.context_contract is ON: refusing to log 0 ft for a "
                "reservoir level that was never set (the prompt path fails "
                "loud on the same field, and the two must not disagree)."
            )
        return level
    return env.get_local("lower_basin", "lake_mead_level", 0)


def build_simulation_log_row(
    *,
    agent_id: str,
    year: int,
    cluster: str,
    basin: str,
    yearly_decision: str,
    wsa_label: Any,
    aca_label: Any,
    agent_state: Dict[str, Any],
    drought_index: float,
    shortage_tier: int,
    lake_mead_level: float,
    mead_storage_maf: float,
    settlement: Dict[str, Any],
    basin_request_af: float,
    magnitude_pct: Optional[float] = None,
    magnitude_pct_sampled: Optional[float] = None,
    magnitude_af: Optional[float] = None,
    magnitude_class: Optional[str] = None,
    magnitude_fallback: bool = False,
    is_exploration: bool = False,
    memory: str = "",
) -> Dict[str, Any]:
    """Build one per-agent-year ``simulation_log.csv`` row.

    Single source of truth for the row schema (2026-09-27 fix,
    supply-side-redesign column gap): both
    ``run_experiment.py``'s ``IrrigationLifecycleHooks.post_year`` (the LLM
    runs) and ``run_fql_baseline.py``'s ``run_simulation`` (the FQL
    reference baseline) call this function, so the two CSVs cannot drift
    apart again the way they did after the supply-side redesign added
    ``delivered`` / ``delivery_ratio`` / ``gap_reason`` / the Powell/Mead
    settlement columns to the LLM path only.

    Callers must read every argument from the SAME environment state:

    - ``agent_state`` is ``env.get_agent_state(agent_id)`` taken AFTER
      ``env.settle_year()`` has run for this year, so ``diversion`` is the
      settled delivery (not the provisional value from execute_skill).
    - ``settlement`` is that same ``env.settle_year()`` return value.
    - ``lake_mead_level`` / ``mead_storage_maf`` are the 1 January values
      for the year (read before the year's settlement is committed by the
      NEXT ``advance_year()``) -- e.g. ``env.get_local("lower_basin",
      "lake_mead_level", 0)`` and ``env._mead_storage[-1]``. The
      ``*_end_maf`` fields below come from ``settlement`` and are this
      year's END-of-year storages instead.
    - ``basin_request_af`` is this year's FINAL total request across both
      basins (``(settlement["ub_request_maf"] + settlement["lb_request_maf"])
      * 1e6``), not the provisional total ``advance_year()`` published to
      the prompts/FQL state at the start of the year.

    Returns a dict whose key order IS the canonical LLM simulation-log
    column order (callers needing that order/set, e.g. a header-superset
    test, should read ``list(row.keys())`` from a row built here rather
    than hardcoding a second copy of the field list).
    """
    request = agent_state.get("request", 0)
    diversion = agent_state.get("diversion", 0)
    water_right = agent_state.get("water_right", 0)

    return {
        "agent_id": agent_id,
        "year": year,
        "cluster": cluster,
        "basin": basin,
        "yearly_decision": yearly_decision,
        "wsa_label": wsa_label,
        "aca_label": aca_label,
        "request": request,
        "diversion": diversion,
        "water_right": water_right,
        "curtailment_ratio": agent_state.get("curtailment_ratio", 0),
        "drought_index": drought_index,
        "shortage_tier": shortage_tier,
        "lake_mead_level": lake_mead_level,
        "mead_storage_maf": mead_storage_maf,
        # Supply-side redesign columns (appended; every older column keeps
        # its name). lake_mead_level / mead_storage_maf above are the
        # 1 January values the agents saw; *_end_maf are this year's
        # end-of-year storages from the final settlement.
        "delivered": diversion,
        "delivery_ratio": agent_state.get("delivery_ratio", 1.0),
        "gap_reason": agent_state.get("gap_reason", "none"),
        "utilisation_delivered_pct": (
            diversion / water_right * 100 if water_right > 0 else 0
        ),
        "mead_storage_end_maf": settlement["mead_storage_end_maf"],
        "powell_storage_maf": settlement["powell_storage_maf"],
        "powell_storage_end_maf": settlement["powell_storage_end_maf"],
        "powell_release_maf": settlement["powell_release_maf"],
        "natural_flow_maf": settlement["natural_flow_maf"],
        "ub_delivered_maf": settlement["ub_delivered_maf"],
        "lb_phys_ratio": settlement["lb_phys_ratio"],
        # This year's FINAL request total (after every decision), not the
        # provisional total advance_year() published to the prompts.
        "basin_request_af": basin_request_af,
        "basin_request_over_target": basin_request_af / CRSS_DEMAND_TARGET_AF,
        "has_efficient_system": agent_state.get("has_efficient_system", False),
        "below_minimum_utilisation": agent_state.get("below_minimum_utilisation", False),
        "utilisation_pct": (
            request / water_right * 100 if water_right > 0 else 0
        ),
        "magnitude_pct": magnitude_pct,
        "magnitude_pct_sampled": magnitude_pct_sampled,
        "magnitude_af": magnitude_af,
        "magnitude_class": magnitude_class,
        "magnitude_fallback": magnitude_fallback,
        "is_exploration": is_exploration,
        "memory": memory,
    }


# ============================================================================
# Factory: create profiles from calibrated parameters CSV
# ============================================================================

def create_profiles_from_csv(
    csv_path: str,
    cluster_assignments: Optional[Dict[str, str]] = None,
    rng: Optional[np.random.Generator] = None,
) -> List[IrrigationAgentProfile]:
    """Create agent profiles from the RL-ABM-CRSS calibrated parameters.

    Args:
        csv_path: Path to ALL_colorado_ABM_params_cal_1108.csv
        cluster_assignments: Optional {agent_name: cluster_name} mapping.
            If not provided, cluster is inferred from parameters.
        rng: Random number generator.

    Returns:
        List of IrrigationAgentProfile with narrative personas.
    """
    import pandas as pd

    rng = rng or np.random.default_rng()
    df = pd.read_csv(csv_path, index_col=0)
    profiles = []

    ub_prefixes = ("WY", "UT", "NM", "CO", "AZ_UB")

    for agent_name in df.columns:
        params = df[agent_name]
        mu = float(params["mu"])
        sigma = float(params["sigma"])
        alpha = float(params["alpha"])
        gamma_p = float(params["gamma"])
        epsilon = float(params["epsilon"])
        regret_val = float(params["regret"])

        basin = "upper_basin" if agent_name.startswith(ub_prefixes) else "lower_basin"

        # Infer cluster from parameters if not provided
        if cluster_assignments and agent_name in cluster_assignments:
            cluster = cluster_assignments[agent_name]
        else:
            cluster = _infer_cluster(mu, sigma, alpha, regret_val)

        # Assign crop type based on basin
        crop_type = _assign_crop_type(basin, rng)

        profile = IrrigationAgentProfile(
            agent_id=agent_name,
            basin=basin,
            cluster=cluster,
            mu=mu,
            sigma=sigma,
            alpha=alpha,
            gamma_param=gamma_p,
            epsilon=epsilon,
            regret=regret_val,
            forget=str(params.get("forget", "TRUE")).upper() == "TRUE",
            farm_size_acres=rng.uniform(200, 2000),
            water_right=rng.uniform(50_000, 200_000),
            crop_type=crop_type,
            years_farming=rng.integers(5, 40),
        )

        profile.narrative_persona = build_narrative_persona(profile, rng)
        profiles.append(profile)

    return profiles


def _infer_cluster(mu: float, sigma: float, alpha: float, regret: float) -> str:
    """Cluster inference by Euclidean distance to three 4-D centroids (mu, sigma, alpha, regret). PROVENANCE NOTE (2026-09-16): the centroid values below are not traced to a specific table of Hung & Yang (2021) in this repository; treat them as WAGF-side constants until a citation is added.
    """
    centroids = {
        "aggressive": np.array([0.36, 1.22, 0.62, 0.78]),
        "forward_looking_conservative": np.array([0.20, 0.60, 0.85, 2.22]),
        "myopic_conservative": np.array([0.16, 0.87, 0.67, 1.54]),
    }
    point = np.array([mu, sigma, alpha, regret])

    best_cluster = "myopic_conservative"
    best_dist = float("inf")
    for name, centroid in centroids.items():
        dist = np.linalg.norm(point - centroid)
        if dist < best_dist:
            best_dist = dist
            best_cluster = name

    return best_cluster


def rebalance_clusters(
    profiles: List[IrrigationAgentProfile],
    min_pct: float = 0.15,
    rng: Optional[np.random.Generator] = None,
) -> List[IrrigationAgentProfile]:
    """Rebalance cluster assignments so minority clusters meet *min_pct*.

    Uses each agent's FQL-parameter distance to all three centroids.
    Agents closest to a minority centroid (but currently assigned elsewhere)
    are reassigned until the minimum is met.  Persona text is regenerated
    to match the new cluster.

    Args:
        profiles: List of profiles with initial cluster assignments.
        min_pct: Minimum fraction per cluster (default 15% ≈ 12/78).
        rng: Random number generator for persona re-selection.

    Returns:
        The same list, mutated in place, with updated clusters and personas.
    """
    rng = rng or np.random.default_rng()
    centroids = {
        "aggressive": np.array([0.36, 1.22, 0.62, 0.78]),
        "forward_looking_conservative": np.array([0.20, 0.60, 0.85, 2.22]),
        "myopic_conservative": np.array([0.16, 0.87, 0.67, 1.54]),
    }
    n = len(profiles)
    min_count = max(1, int(n * min_pct))

    # Compute distance of each profile to every centroid
    dists = {}
    for i, p in enumerate(profiles):
        pt = np.array([p.mu, p.sigma, p.alpha, p.regret])
        dists[i] = {c: float(np.linalg.norm(pt - v)) for c, v in centroids.items()}

    from collections import Counter
    counts = Counter(p.cluster for p in profiles)

    for target_cluster in ["forward_looking_conservative", "myopic_conservative"]:
        deficit = min_count - counts.get(target_cluster, 0)
        if deficit <= 0:
            continue

        # Rank aggressive agents by their distance to target centroid (ascending)
        candidates = [
            (i, dists[i][target_cluster])
            for i, p in enumerate(profiles)
            if p.cluster == "aggressive"
        ]
        candidates.sort(key=lambda x: x[1])

        for idx, _ in candidates[:deficit]:
            old = profiles[idx].cluster
            profiles[idx].cluster = target_cluster
            profiles[idx].narrative_persona = build_narrative_persona(profiles[idx], rng)
            counts[old] -= 1
            counts[target_cluster] += 1

    return profiles


def rebalance_to_target(
    profiles: List[IrrigationAgentProfile],
    target_dist: Dict[str, float],
    rng: Optional[np.random.Generator] = None,
) -> None:
    """Rebalance clusters to exact target distribution (e.g., 50%-30%-20%).

    Uses FQL parameter distance to reassign agents to match target percentages.

    Args:
        profiles: Agent profiles (mutated in place)
        target_dist: {"aggressive": 0.5, "forward_looking_conservative": 0.3,
                      "myopic_conservative": 0.2}
        rng: Random generator
    """
    rng = rng or np.random.default_rng()
    n = len(profiles)

    # FQL centroids from Hung & Yang 2021
    centroids = {
        "aggressive": np.array([0.36, 1.22, 0.62, 0.78]),
        "forward_looking_conservative": np.array([0.20, 0.60, 0.85, 2.22]),
        "myopic_conservative": np.array([0.16, 0.87, 0.67, 1.54]),
    }

    # Compute FQL parameter distances
    dists = {}
    for i, p in enumerate(profiles):
        pt = np.array([p.mu, p.sigma, p.alpha, p.regret])
        dists[i] = {
            c: float(np.linalg.norm(pt - v))
            for c, v in centroids.items()
        }

    # Target counts with proportional rounding adjustment
    target_counts = {c: int(n * frac) for c, frac in target_dist.items()}
    remainder = n - sum(target_counts.values())
    if remainder > 0:
        # Distribute remainder based on fractional parts (largest first)
        fractional = {c: (n * frac) - int(n * frac) for c, frac in target_dist.items()}
        for _ in range(remainder):
            max_cluster = max(fractional, key=fractional.get)
            target_counts[max_cluster] += 1
            fractional[max_cluster] = 0  # Prevent double-assignment

    # Current counts
    from collections import Counter
    current_counts = Counter(p.cluster for p in profiles)

    # Track agents already reassigned (prevents double reassignment in same pass)
    reassigned_agents = set()

    # Greedy reassignment by FQL distance
    for target_cluster, target_count in target_counts.items():
        deficit = target_count - current_counts.get(target_cluster, 0)
        if deficit <= 0:
            continue

        # Find closest agents from other clusters (exclude already reassigned)
        candidates = [
            (i, dists[i][target_cluster])
            for i, p in enumerate(profiles)
            if p.cluster != target_cluster and i not in reassigned_agents
        ]
        candidates.sort(key=lambda x: x[1])  # Ascending by distance

        # Reassign top-deficit agents
        for idx, _ in candidates[:deficit]:
            reassigned_agents.add(idx)  # Mark as reassigned
            old_cluster = profiles[idx].cluster
            profiles[idx].cluster = target_cluster
            # Regenerate persona narrative
            profiles[idx].narrative_persona = build_narrative_persona(profiles[idx], rng)
            current_counts[old_cluster] -= 1
            current_counts[target_cluster] += 1


def _assign_crop_type(basin: str, rng: np.random.Generator) -> str:
    """Assign crop type based on basin and stochastic selection."""
    ub_crops = ["alfalfa", "grass hay", "corn", "small grains"]
    lb_crops = ["alfalfa", "cotton", "vegetables", "citrus", "dates"]
    crops = ub_crops if basin == "upper_basin" else lb_crops
    return str(rng.choice(crops))


# ============================================================================
# UB state-group positional mapping (from Hung & Yang 2021 ABM_CRSS_coupling.py)
# ============================================================================
# 9 state-groups, each covering a contiguous slice of the 58 UB agent list.
# Agent order matches UB_ABM_Groups_and_Agents.csv expanded to Group_Slot format.
_UB_STATE_GROUPS = ["WY", "UT1", "UT2", "UT3", "NM", "CO1", "CO2", "CO3", "AZ_UB"]
_UB_GROUP_AGENT_COUNTS = [5, 11, 1, 2, 7, 5, 15, 9, 3]  # 58 total

# UB historical CSV column names do not all match the state-group label used
# above: HistoricalData/UB_historical_annual_depletion.csv's Arizona column
# is "AZ", not "AZ_UB" (the FQL calibration file's group label). A direct
# ``state_group in ub_hist.columns`` lookup silently misses for the 3
# ArizonaMiscUses_* agents, leaving their actual_2018_diversion (and, since
# 2026-09-26, peak_obs_af) at None (Change 2, AZ_UB history-column bug,
# found during the water-right history-anchor audit). Mapped explicitly
# rather than by stripping every group's "_UB"/basin suffix, which would
# risk a future group silently matching an unrelated column; a UB group
# still missing its mapped column after this is a loud error, not a
# silent None (see create_profiles_from_data).
_UB_HIST_COLUMN_BY_GROUP: Dict[str, str] = {sg: sg for sg in _UB_STATE_GROUPS}
_UB_HIST_COLUMN_BY_GROUP["AZ_UB"] = "AZ"


def _build_ub_agent_names(group_agt_path: str) -> List[str]:
    """Read UB group-agent file and return agent names in Group_Slot order.

    This mirrors ``Generate_Agt_Names`` from ABM_CRSS_coupling.py.
    """
    import csv

    agents: List[str] = []
    with open(group_agt_path, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            group = row[0]
            for slot in row[1:]:
                slot = slot.strip()
                if not slot:
                    continue
                agents.append(f"{group}_{slot}")
    return agents


def _build_ub_state_group_map(ub_agent_names: List[str]) -> Dict[str, str]:
    """Map each UB agent name to its CSV state-group using positional slicing."""
    mapping: Dict[str, str] = {}
    offset = 0
    assert sum(_UB_GROUP_AGENT_COUNTS) == len(ub_agent_names), ("_UB_GROUP_AGENT_COUNTS must sum to the number of UB agents", sum(_UB_GROUP_AGENT_COUNTS), len(ub_agent_names))
    for sg, count in zip(_UB_STATE_GROUPS, _UB_GROUP_AGENT_COUNTS):
        for agent in ub_agent_names[offset: offset + count]:
            mapping[agent] = sg
        offset += count
    return mapping


def create_profiles_from_data(
    params_csv_path: str,
    crss_db_dir: str,
    rng: Optional[np.random.Generator] = None,
    paper_water_margin: float = 0.4,
) -> List[IrrigationAgentProfile]:
    """Create 78 individual agent profiles from paper data.

    Expands the 31-agent CSV to the full 78-agent CRSS resolution:
    - LB: 22 agents (1:1 match with CSV)
    - UB: 58 individual CRSS slots, each inheriting its state-group's
      FQL parameters.  Inactive agents (all-zero states) are skipped.

    F10 (2026-09-25 audit; ceiling fixed 2026-09-26, water-right
    history-anchor): ``col.iloc[-1]`` is the TOP of that agent's
    discretised FQL diversion grid (``Div_States/*_discrete_states.csv``),
    i.e. Hung & Yang's ``Div_max`` (the ceiling the FQL state space
    discretises against), NOT a legal Colorado River entitlement. For the
    56 modelled Upper Basin agents that grid top sums to 10.54 MAF, 2.8x
    their 1971-2018 observed peak (3.54 MAF) and 3.5x their 2018 use
    (3.05 MAF); at that ceiling requests grow to 7-10 MAF within a few
    years, hit the 5.0 MAF Upper Basin delivery capacity from year 2, and
    Lake Powell sits at dead pool for roughly half the run. ``water_right``
    below is therefore ``min(grid_top_af, (1 + paper_water_margin) *
    peak_obs_af)`` for every one of the 78 agents (one rule, both basins)
    -- ``paper_water_margin`` is the share by which a district's legal
    ceiling may exceed its largest observed annual use, on ``[0, 1]``;
    ``peak_obs_af`` is the same agent's own observed peak over 1971-2018
    (the historical series ``actual_2018_diversion`` already reads, UB
    depletion file / LB diversion file, UB split proportionally across a
    state group exactly as ``actual_2018_diversion`` is), and
    ``grid_top_af``/``peak_obs_af``/``water_right_source`` are kept on the
    profile so a manifest or analysis script can see which bound applied.
    ``bin_size_af`` (the Hung & Yang STEP size) is unaffected -- it always
    comes from the grid, independent of which ceiling wins here.

    Derivation of the default ``paper_water_margin`` (0.4): the 56
    modelled Upper Basin agents used 3.0544 MAF in 2018. USBR's "Upper
    Colorado River Basin Consumptive Uses and Losses 2016-2020"
    (Provisional, Feb 2022), Table UC-4, gives 2018 Upper Basin irrigation
    consumptive use as 3,079.3 kaf (within 1% of the modelled agents'
    3.0544 MAF) against a 2018 Upper Basin total, including main-stem
    reservoir evaporation, of 4,752.8 kaf -- irrigation's share of 2018
    Upper Basin consumptive use is 3,079.3 / 4,752.8 = 0.648 (evaporation
    is included in the denominator because Compact accounting charges
    reservoir evaporation to the basin's apportionment). That share of
    the 7.5 MAF Compact Article III(a) apportionment is 0.648 x 7.5 =
    4.86 MAF; dividing by the 56 agents' observed-peak sum (3.536 MAF)
    gives 4.86 / 3.536 = 1.374, rounded to one decimal, 1.4 -- a margin
    of 0.4 over the observed peak. At the default, the 56 Upper Basin
    agents' water_right sums to about 4.93 MAF, below the 5.0 MAF Upper
    Basin delivery capacity (a margin of 0.5 would put the sum at about
    5.28 MAF, above that capacity; a margin of 0.0, i.e. capping at the
    bare observed peak, leaves most Upper Basin agents almost no room to
    increase -- their peak-to-2018-use ratio has a median of about 1.01).
    The Lower Basin is bound by the same rule and the same
    ``paper_water_margin`` (not a per-basin value); its grid tops stay
    the binding value for a narrow majority of its 22 agents, the
    peak-scaled ceiling for the rest. See ``docs/irrigation_physics.md``
    and ``docs/irrigation_model_caveats.md`` (item 11) for the
    corresponding physics-side and disclosure-side notes.

    Change 2 (AZ_UB history-column bug, found during the same audit): the
    3 ``ArizonaMiscUses_*`` agents (state group ``AZ_UB``) got
    ``actual_2018_diversion=None`` because the historical CSV's column is
    "AZ", not "AZ_UB" -- see ``_UB_HIST_COLUMN_BY_GROUP``. With
    ``actual_2018_diversion=None``,
    ``IrrigationEnvironment.initialize_from_profiles`` fell back to
    ``water_right * 0.8`` for the initial request/diversion, i.e. 80% of
    the (then-uncapped) grid top -- 32,000 / 14,400 / 16,000 acre-ft for
    the three agents respectively, roughly 30-60x their real 2018 use
    (about 513 / 231 / 256 acre-ft). Fixed here by mapping the state
    group to its historical column explicitly.

    Review P2 (2026-09-27): both HistoricalData files are now REQUIRED --
    a missing file, a missing 2018 row, or (for LB) an active agent absent
    from the file's columns all raise ``ValueError`` (mirroring the UB
    group-column check), instead of silently falling back to the grid top.
    ``IrrigationEnvironment.initialize_from_profiles``'s
    ``water_right * 0.8`` starting-request fallback therefore never fires
    for a profile built by this function -- it only ever applies to
    profiles that skip this function entirely (synthetic builders,
    ``create_profiles_from_csv``), which have no historical series to
    read at all. The peak window is restricted to ``.loc[:2018]`` so a
    historical file extended with later years cannot silently move
    ``peak_obs_af``.

    Args:
        params_csv_path: Path to ALL_colorado_ABM_params_cal_1108.csv
        crss_db_dir: Path to ref/CRSS_DB/CRSS_DB/ directory
        rng: Random number generator for crop type and persona selection.
        paper_water_margin: Share by which a district's legal ceiling may
            exceed its 1971-2018 observed peak diversion, on ``[0, 1]``
            (enforced -- raises ``ValueError`` outside that range);
            ``water_right = min(grid_top_af, (1 + paper_water_margin) *
            peak_obs_af)``. Default 0.4 (see derivation above). Exposed
            end-to-end via ``--paper-water-margin`` on
            ``run_experiment.py`` and ``run_fql_baseline.py``.

    Returns:
        List of ~78 IrrigationAgentProfile with real water_right values.
    """
    import os
    import pandas as pd

    if not (0.0 <= paper_water_margin <= 1.0):
        raise ValueError(
            f"paper_water_margin must be in [0, 1], got {paper_water_margin!r}"
        )

    rng = rng or np.random.default_rng()

    # 1. Load FQL parameters (31 state-group-level agents)
    params_df = pd.read_csv(params_csv_path, index_col=0)

    # 2. Load discrete states for water_right extraction
    ub_states = pd.read_csv(
        os.path.join(crss_db_dir, "Div_States", "UB_discrete_states.csv")
    )
    lb_states = pd.read_csv(
        os.path.join(crss_db_dir, "Div_States", "LB_discrete_states.csv")
    )

    # 3. Build UB agent → state-group mapping
    ub_group_file = os.path.join(
        crss_db_dir, "Group_Agt", "UB_ABM_Groups_and_Agents.csv"
    )
    ub_agent_names = _build_ub_agent_names(ub_group_file)
    ub_sg_map = _build_ub_state_group_map(ub_agent_names)

    # 4. Load historical 1971-2018 series (Hung & Yang 2021 baseline).
    # Review P2 (2026-09-27): both files, the 2018 row, and (for LB) every
    # active agent's column are now REQUIRED -- raised loudly rather than
    # silently degrading to the grid top, mirroring the UB group-column
    # check. lb_hist / ub_hist are kept in full (not just their 2018 row)
    # because peak_obs_af needs the max over every available year, sliced
    # to .loc[:2018] below so a file extended with later years cannot
    # silently move the peak.
    lb_hist_path = os.path.join(crss_db_dir, "HistoricalData", "LB_historical_annual_diversion.csv")
    ub_hist_path = os.path.join(crss_db_dir, "HistoricalData", "UB_historical_annual_depletion.csv")

    if not os.path.isfile(lb_hist_path):
        raise ValueError(
            f"{lb_hist_path} not found; create_profiles_from_data requires the "
            "historical LB diversion series (actual_2018_diversion, peak_obs_af) "
            "for every active LB agent. Synthetic profiles that do not need this "
            "data should use create_profiles_from_csv or a synthetic builder instead."
        )
    lb_hist = pd.read_csv(lb_hist_path, index_col=0)
    if 2018 not in lb_hist.index:
        raise ValueError(f"{lb_hist_path} has no row for year 2018; cannot compute actual_2018_diversion.")
    lb_2018 = lb_hist.loc[2018]
    # Only agents this function will actually build a profile for (present
    # in params_df and an active -- grid_top > 0 -- LB slot) need a column;
    # an agent skipped for either reason below is not checked here.
    missing_lb_agents = [
        a for a in lb_states.columns
        if a in params_df.columns and float(lb_states[a].iloc[-1]) > 0 and a not in lb_hist.columns
    ]
    if missing_lb_agents:
        raise ValueError(
            f"{lb_hist_path} has no column for LB agent(s) {missing_lb_agents}; "
            "cannot compute actual_2018_diversion or peak_obs_af for them."
        )

    if not os.path.isfile(ub_hist_path):
        raise ValueError(
            f"{ub_hist_path} not found; create_profiles_from_data requires the "
            "historical UB depletion series (actual_2018_diversion, peak_obs_af) "
            "for every active UB state group. Synthetic profiles that do not need "
            "this data should use create_profiles_from_csv or a synthetic builder instead."
        )
    ub_hist = pd.read_csv(ub_hist_path, index_col=0)
    # Change 2: every UB state group must resolve to a real historical
    # column via the explicit mapping -- a group that still does not
    # resolve fails loudly here rather than silently leaving None on
    # whichever agents happen to fall in it (the AZ_UB bug this closes).
    missing = [
        sg for sg in _UB_STATE_GROUPS
        if _UB_HIST_COLUMN_BY_GROUP[sg] not in ub_hist.columns
    ]
    if missing:
        raise ValueError(
            f"{ub_hist_path} has no column for UB state group(s) {missing} "
            f"(expected column(s) "
            f"{[_UB_HIST_COLUMN_BY_GROUP[sg] for sg in missing]!r}); cannot "
            "compute actual_2018_diversion or peak_obs_af for the agents "
            "in this group. Update _UB_HIST_COLUMN_BY_GROUP if the "
            "historical file's column naming changed."
        )
    if 2018 not in ub_hist.index:
        raise ValueError(f"{ub_hist_path} has no row for year 2018; cannot compute actual_2018_diversion.")
    ub_2018 = ub_hist.loc[2018] * 1000  # thousands AF → AF

    # Pre-compute UB state-group water_right (grid-top) totals for
    # proportional split, and each group's observed-peak / 2018 series in
    # acre-ft (thousands AF → AF), keyed by the FQL group label so the
    # per-agent loop below can look them up by state_group directly.
    ub_group_wr_totals: Dict[str, float] = {}
    for _name in ub_states.columns:
        _wr = float(ub_states[_name].iloc[-1])
        if _wr <= 0:
            continue
        _sg = ub_sg_map.get(_name)
        if _sg:
            ub_group_wr_totals[_sg] = ub_group_wr_totals.get(_sg, 0) + _wr

    # Peak window restricted to years <= 2018 (Review P2): an historical
    # file later extended past 2018 must not silently move the peak.
    ub_hist_to_2018 = ub_hist.loc[:2018]
    ub_group_peak_af: Dict[str, float] = {
        sg: float(ub_hist_to_2018[_UB_HIST_COLUMN_BY_GROUP[sg]].max()) * 1000
        for sg in _UB_STATE_GROUPS
    }

    # Local multiplier derived from paper_water_margin; not itself a second
    # exposed knob (only paper_water_margin is a parameter/CLI flag/manifest
    # key).
    _margin_multiplier = 1.0 + paper_water_margin

    def _capped_water_right(grid_top_af: float, peak_obs_af: Optional[float]) -> Tuple[float, str]:
        """``min(grid_top_af, (1 + paper_water_margin) * peak_obs_af)`` and its source label.

        Falls back to ``grid_top_af`` (source "grid_top") when no observed
        peak is available (e.g. the historical file was not found) -- the
        pre-history-anchor behaviour, never worse than before.
        """
        if peak_obs_af is None or peak_obs_af <= 0:
            return grid_top_af, "grid_top"
        scaled = _margin_multiplier * peak_obs_af
        if grid_top_af <= scaled:
            return grid_top_af, "grid_top"
        return scaled, "peak_scaled"

    profiles: List[IrrigationAgentProfile] = []

    # --- Lower Basin agents (22, direct CSV match) ---
    for agent_name in lb_states.columns:
        if agent_name not in params_df.columns:
            continue
        col = lb_states[agent_name]
        grid_top_af = float(col.iloc[-1])
        if grid_top_af <= 0:
            continue  # inactive

        # Peak window restricted to years <= 2018 (Review P2), same as UB.
        peak_obs_af = (
            float(lb_hist.loc[:2018, agent_name].max())
            if agent_name in lb_hist.columns
            else None
        )
        water_right, water_right_source = _capped_water_right(grid_top_af, peak_obs_af)

        p = params_df[agent_name]
        mu = float(p["mu"])
        sigma = float(p["sigma"])
        alpha = float(p["alpha"])
        gamma_p = float(p["gamma"])
        epsilon = float(p["epsilon"])
        regret_val = float(p["regret"])
        cluster = _infer_cluster(mu, sigma, alpha, regret_val)

        bin_size_af = float(col.iloc[2] - col.iloc[1])
        profile = IrrigationAgentProfile(
            agent_id=agent_name,
            basin="lower_basin",
            cluster=cluster,
            mu=mu,
            sigma=sigma,
            alpha=alpha,
            gamma_param=gamma_p,
            epsilon=epsilon,
            regret=regret_val,
            forget=str(p.get("forget", "TRUE")).upper() == "TRUE",
            farm_size_acres=water_right / 200.0,  # proportional to water_right
            water_right=water_right,
            bin_size_af=bin_size_af,
            grid_top_af=grid_top_af,
            peak_obs_af=peak_obs_af,
            water_right_source=water_right_source,
            crop_type=_assign_crop_type("lower_basin", rng),
            years_farming=int(rng.integers(5, 40)),
        )
        if lb_2018 is not None and agent_name in lb_2018.index:
            profile.actual_2018_diversion = float(lb_2018[agent_name])
        profile.narrative_persona = build_narrative_persona(profile, rng)
        profiles.append(profile)

    # --- Upper Basin agents (58, expanded from 9 state-groups) ---
    for agent_name in ub_states.columns:
        col = ub_states[agent_name]
        grid_top_af = float(col.iloc[-1])
        if grid_top_af <= 0:
            continue  # inactive

        # Look up state-group for FQL params
        state_group = ub_sg_map.get(agent_name)
        if state_group is None or state_group not in params_df.columns:
            continue

        # This agent's share of its state group's grid-top total; the same
        # ratio splits the group's observed-peak and 2018 series across its
        # agents (Change 1: peak_obs_af uses the same split as
        # actual_2018_diversion; Change 2: both now resolve via
        # _UB_HIST_COLUMN_BY_GROUP instead of the bare state_group label).
        group_total = ub_group_wr_totals.get(state_group, 1)
        ratio = grid_top_af / group_total if group_total > 0 else 0.0
        peak_obs_af = (
            ub_group_peak_af[state_group] * ratio
            if state_group in ub_group_peak_af
            else None
        )
        water_right, water_right_source = _capped_water_right(grid_top_af, peak_obs_af)

        p = params_df[state_group]
        mu = float(p["mu"])
        sigma = float(p["sigma"])
        alpha = float(p["alpha"])
        gamma_p = float(p["gamma"])
        epsilon = float(p["epsilon"])
        regret_val = float(p["regret"])
        cluster = _infer_cluster(mu, sigma, alpha, regret_val)

        bin_size_af = float(col.iloc[2] - col.iloc[1])
        profile = IrrigationAgentProfile(
            agent_id=agent_name,
            basin="upper_basin",
            cluster=cluster,
            mu=mu,
            sigma=sigma,
            alpha=alpha,
            gamma_param=gamma_p,
            epsilon=epsilon,
            regret=regret_val,
            forget=str(p.get("forget", "TRUE")).upper() == "TRUE",
            farm_size_acres=water_right / 200.0,
            water_right=water_right,
            bin_size_af=bin_size_af,
            grid_top_af=grid_top_af,
            peak_obs_af=peak_obs_af,
            water_right_source=water_right_source,
            crop_type=_assign_crop_type("upper_basin", rng),
            years_farming=int(rng.integers(5, 40)),
        )
        if ub_2018 is not None:
            hist_col = _UB_HIST_COLUMN_BY_GROUP.get(state_group, state_group)
            if hist_col in ub_2018.index:
                profile.actual_2018_diversion = float(ub_2018[hist_col]) * ratio
        profile.narrative_persona = build_narrative_persona(profile, rng)
        profiles.append(profile)

    return profiles
