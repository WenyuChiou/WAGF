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

from examples.irrigation_abm.irrigation_env import (
    CRSS_DEMAND_TARGET_AF,
    SYNTHETIC_HY_MU,
    SYNTHETIC_HY_SIGMA,
    hy_threshold_af,
    resolve_step_bin_af,
)


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
    # Historical 2017 diversion (acre-ft), same series/column/UB-split as
    # actual_2018_diversion above. Added for the FQL calibrated warm-start
    # (run_fql_baseline.py --fql-init calibrated): Hung & Yang's own first
    # year action bin is a_t = Div_2018 - Div_2017
    # (ABM_CRSS_coupling.py lines 505-508, 532-537). None whenever
    # actual_2018_diversion is None (synthetic profiles, or --real profiles
    # for which the 2017 row is absent from the historical file).
    actual_2017_diversion: Optional[float] = None

    # Hung and Yang (2021) action model: step = (mu + |N(0, sigma)|) x
    # bin_size_af (mu and sigma above are that model's per-agent parameters).
    # bin_size_af = the step of the agent's discretised diversion grid
    # (Div_States/*_discrete_states.csv, agt_states[2] - agt_states[1]),
    # converted to this agent's own delivery units (WP2 spec 2.3):
    # demand_per_grid_unit (k) x (grid[2] - grid[1]), k = 0.5 for Upper
    # Basin (the grid is in diversion units; H&Y p. 9 assumes 50 percent
    # of a diversion is depleted) or 1.0 for Lower Basin (the grid is
    # already consumptive use). None = synthetic profile, the environment
    # falls back to water_right / 25.
    # NOTE: bin_size_af is the Hung and Yang STEP size and is never touched
    # by the water_right history-anchor (see below); it always comes from
    # the grid regardless of which ceiling water_right ends up at.
    bin_size_af: Optional[float] = None

    # WP2 spec 2.3: k itself, kept on the profile so a caller needing the
    # RAW (unconverted, diversion-unit) grid step -- e.g. the FQL
    # baseline's own grid-state discretisation, which WP5 still runs on
    # H&Y's original units -- can recover it as
    # bin_size_af / demand_per_grid_unit. None for a profile this field
    # was never set on (pre-WP2 code path, synthetic profile): treated as
    # 1.0 (no conversion) wherever it is read back.
    demand_per_grid_unit: Optional[float] = None

    # WP2 spec 2.4: the FINAL step bin the LLM-agent path draws against
    # (hy_step_af/hy_threshold_af) and shows the agent as its "typical
    # step". Equals bin_size_af, UNLESS bin_size_af exceeds 20 percent of
    # this agent's 2018 use, in which case it is rescaled to 10 percent of
    # that use (H&Y p. 8's own description of the grid increment) --
    # exactly 8 agents, all with a grid built far from their actual scale.
    # None = synthetic profile; execute_skill/build_option_texts fall back
    # to bin_size_af, then to water_right / 25.
    step_bin_af: Optional[float] = None

    # "grid" (bin_size_af used as-is) or "rescaled" (the 10-percent-of-
    # 2018-use override fired) -- written to the manifest (spec 2.4).
    # None for a profile step_bin_af was never computed for.
    step_bin_source: Optional[str] = None

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

    # The agent's REAL Div_States column (all 21 values), for the FQL
    # calibrated warm-start's state_grid_mode="hy_exact" (P1-a fix,
    # 2026-09-27 review). 19 of 22 LB agents' real columns are NOT a
    # 0-to-top linspace (e.g. MohaveValleyIDD =
    # [0, 12000, 14000, ..., 50000] -- index 0 is a wide catch-all down
    # to 12000, not part of a uniform sequence from 0), so
    # np.linspace(0, grid_top_af, 21) reads the wrong FQL state for
    # those agents under calibrated init. None for profiles that do not
    # go through create_profiles_from_data (grid_top_af is also None
    # for those; --fql-init calibrated is not meaningful without both).
    div_states_grid: Optional[np.ndarray] = None

    # Upper Basin agents' own sub-basin winter precipitation column in
    # PrismWinterPrecip_ST_NOAA_Future.csv (v3, spec 1.6, L1-03): one of
    # WY, UT1, UT2, UT3, NM, CO1, CO2, CO3, AZ (AZ_UB agents read "AZ" --
    # see _UB_HIST_COLUMN_BY_GROUP, the same mapping
    # actual_2018_diversion's historical column already uses). None for
    # Lower Basin agents (their own information is Lake Mead's elevation,
    # unaffected) and for profiles built outside create_profiles_from_data
    # (synthetic/mock), which fall back to the basin-level legacy mean in
    # IrrigationEnvironment.get_agent_context.
    precip_group: Optional[str] = None

    # WP1b re-review (MEDIUM 2, 2026-09-29): an explicit, disclosed marker
    # that an Upper Basin profile with no precip_group is a mock-smoke-only
    # synthetic profile (run_experiment.py / run_fql_baseline.py
    # _create_synthetic_profiles), not a real create_profiles_from_data
    # profile that forgot to set one. IrrigationEnvironment.
    # initialize_from_profiles routes such a profile to the unconstrained
    # "no sub-basin" pool in ub_supply_mode="subbasin" (logging that it did
    # so) instead of raising; a REAL Upper Basin profile with no
    # precip_group and this flag left False still raises. Default False so
    # every existing profile (a real one, or an old test fixture that
    # never set this) keeps today's strict behaviour unless it opts in.
    synthetic_no_subbasin: bool = False

    # WP1c review round 2 (LOW 6, 2026-09-29): the SAME marker pattern as
    # synthetic_no_subbasin above, for the Lower Basin priority-split table
    # (lb_priority_split_v3.csv) instead of the Upper Basin sub-basin one.
    # A Lower Basin profile whose agent_id is not one of the 22 real names
    # in that table is either a mock-smoke-only synthetic profile (this
    # flag True; IrrigationEnvironment.initialize_from_profiles routes it
    # to fully senior, logging that it did so) or a real profile that
    # forgot to set one (this flag left False; initialize_from_profiles
    # raises). Default False for the same reason: every existing profile
    # keeps today's strict behaviour unless it opts in.
    synthetic_no_priority_split: bool = False

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


def _tier_from_state(state: Dict[str, Any]) -> int:
    """The declared tier, from ``shortage_tier`` only. Review 2026-09-28
    (fix 12): the earlier ``curtailment_ratio``-based fallback
    (``_TIER_BY_CUT``, keyed on the pre-v3 flat 0.05/0.10/0.20 cuts) is
    deleted -- ``curtailment_ratio`` is now V / N (PI decision
    2026-09-28), a different number that never matched those keys anyway
    once V stopped being a flat percentage. No silent fallback: a caller
    with no ``shortage_tier`` gets 0 (unknown), not a guess."""
    tier = state.get("shortage_tier")
    if isinstance(tier, (int, float)) and tier > 0:
        return int(tier)
    return 0


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
        if c == "ub_subbasin_supply":
            # WP1b (item 20, memo section 9): this agent's OWN sub-basin
            # is short, not the basin-wide backstop (ub_natural_flow /
            # ub_capacity below) -- true only in ub_supply_mode="subbasin"
            # (IrrigationEnvironment._settle never produces this code in
            # "lees_ferry_pool" mode). A real agent with this code always
            # has a known ub_subbasin_member_count (see _sharing_sentence's
            # docstring for why); a missing one is the same wiring defect
            # HIGH 1 found, not a legitimate state.
            member_count = agent_state.get("ub_subbasin_member_count")
            if member_count is None:
                raise ValueError(
                    "describe_gap_reason: gap_reason names ub_subbasin_supply "
                    "but ub_subbasin_member_count is missing from agent_state; "
                    "refusing to silently guess whether this sub-basin has "
                    "other members (MEDIUM 5, 2026-09-29 re-review)."
                )
            if member_count <= 1:
                # MEDIUM 5: the sole member of its sub-basin (UT2) shares
                # with no one -- "combined requests of its users" and
                # "shared in proportion to requests" would both be false.
                parts.append(
                    "the natural flow of the rivers your sub-basin draws on is "
                    "below your own request"
                )
            else:
                parts.append(
                    "the natural flow of the rivers your sub-basin draws on is below "
                    "the combined requests of its users, and the shortfall is shared "
                    "in proportion to requests"
                )
        elif c == "ub_natural_flow":
            # Review 2026-09-28 (fix 9): this year's (non-farm-net)
            # natural flow, not the 5.0 MAF delivery capacity, was the
            # binding constraint -- never name a limit that did not bind.
            parts.append("Upper Basin deliveries are limited by this year's natural flow "
                         "(net of Upper Basin non-farm use), shared pro-rata")
        elif c == "ub_capacity":
            cap = float(agent_state.get("ub_capacity_maf", 5.0) or 5.0)
            parts.append(f"Upper Basin deliveries are limited to the {cap:.1f} million "
                         f"acre-ft delivery capacity, shared pro-rata")
        elif c == "ub_powell_release":
            # No longer produced by IrrigationEnvironment._settle (PI
            # decision 4, 2026-09-28); kept so a state dict built before
            # that change still renders something rather than nothing.
            parts.append("Upper Basin deliveries were reduced pro-rata so Lake Powell can "
                         "make its minimum release to Lake Mead")
        elif c == "lb_junior_tier_cut":
            # WP1c (item 22): only one of the six Arizona 4th/5th/6th-
            # priority agents can carry this code, and only in
            # lb_priority_mode="split" (IrrigationEnvironment._settle never
            # produces it in "senior_all" mode or for the other 16 senior-
            # only agents). The percentage is the state's OWN
            # lb_junior_tier_cut_fraction (f_g), never hand-copied, so this
            # phrase and _settle's actual cut can never disagree.
            frac = agent_state.get("lb_junior_tier_cut_fraction")
            if not frac:
                raise ValueError(
                    "describe_gap_reason: gap_reason names lb_junior_tier_cut but "
                    "lb_junior_tier_cut_fraction is missing or 0 in agent_state; "
                    "refusing to silently guess the cut percentage."
                )
            parts.append(
                "the declared Lower Basin shortage tier cuts your junior-priority "
                f"water by about {frac:.0%}"
            )
        elif c == "lb_mead_availability":
            parts.append("Lake Mead cannot meet all Lower Basin withdrawals this year "
                         "without falling below its minimum pool, so all Lower Basin "
                         "deliveries are reduced pro-rata")
        # "lb_shortage_tier" is intentionally NOT handled: PI decision
        # 2026-09-28 has the declared shortage volume borne entirely by
        # the Lower Basin non-agricultural bucket, never by an
        # agricultural agent's own delivery, so IrrigationEnvironment.
        # _settle no longer produces this code for any agent. The
        # declared tier stays visible as information (shortage_tier,
        # curtailment_ratio = V / N) without implying it reduced this
        # agent's own delivery.
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
    shortage_tier = env_context.get("shortage_tier", 0)
    # Re-review 2026-09-29 (LOW D): no eager default here -- a Lower Basin
    # context with a declared tier and no lb_shortage_volume_maf is a real
    # data-shape defect (checked, and raised, at the actual point of use
    # below); an Upper Basin context never reads this value at all
    # (the sentence it feeds is Lower-Basin-only), so it must not raise
    # for a missing key that basin was never going to use.
    shortage_volume_maf = env_context.get("lb_shortage_volume_maf")
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
        # WP1b (item 20, memo section 9): the sub-basin's own flow as a
        # share of its 1971-2018 average replaces the absolute Lees Ferry
        # figure -- it is the sub-basin's own flow, not Lees Ferry's, that
        # sets this agent's supply (in ub_supply_mode="subbasin"), and an
        # absolute acre-foot figure invites comparison with a request that
        # is only a small part of it. True in both supply modes (a
        # descriptive fact about the sub-basin's own hydrology, not about
        # which rule governs deliveries this year); falls back to the
        # pre-WP1b absolute-flow sentence for a context with no sub-basin
        # flow share (a Lower Basin caller never reaches this branch; a
        # synthetic/mock Upper Basin context with no supply_group does).
        subbasin_flow_share = env_context.get("ub_subbasin_flow_share")
        if subbasin_flow_share is not None:
            lines.append(
                "The natural flow of the rivers your sub-basin draws on is "
                f"{subbasin_flow_share:.0%} of its 1971-2018 average this year."
            )
        elif nf:
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
            # Re-review 2026-09-29 (LOW D): a declared tier with no
            # lb_shortage_volume_maf reaching this point is a real
            # data-shape defect (get_agent_context should always set it
            # once a tier is declared) -- raise here, at the actual point
            # of use, rather than silently reporting a fabricated 0
            # acre-ft cut for a real declared shortage.
            if shortage_volume_maf is None:
                raise ValueError(
                    f"build_water_situation_text: shortage_tier={shortage_tier} "
                    "is declared but 'lb_shortage_volume_maf' is missing "
                    "from env_context; refusing to silently report a "
                    "fabricated 0 acre-ft cut."
                )
            # Re-review 2026-09-29 (HIGH 2): the declared tier's volume is
            # borne by the non-agricultural bucket (Arizona and Nevada's
            # stand-in) -- the old wording claimed a flat reduction that no
            # longer happens under the PI decision. curtailment_ratio (V/N)
            # is informational only; the real acre-feet cut is
            # lb_shortage_volume_maf x 1e6.
            #
            # WP1c review round 2 (MEDIUM 2): "non-agricultural Lower Basin
            # deliveries (Arizona and Nevada)" is no longer accurate for the
            # OPENING sentence either -- part of V now falls on junior farm
            # water (below), so the true statement is that the DECLARED
            # VOLUME, split between the non-agricultural bucket and any
            # junior farms, totals V; naming "Arizona and Nevada" without
            # "non-agricultural" covers both.
            #
            # WP1c (item 22): for the six agents who hold some Arizona
            # 4th/5th/6th-priority ("junior") water, "your own delivery is
            # reduced only if Lake Mead cannot physically supply ..." is no
            # longer true in a year the tier actually cuts their junior
            # water (lb_junior_request_af > 0 this decision) -- their
            # junior part is cut by the tier directly, before any physical
            # shortage. Everyone else's text (the other 16, and these same
            # six in a year their request has not exceeded their senior
            # entitlement) is BYTE-IDENTICAL to before item 22.
            #
            # WP1c review round 2 (LOW 6): direct index, not
            # ``.get(key) or 0.0`` -- a Lower Basin context with a declared
            # tier and no lb_junior_request_af / lb_junior_tier_cut_fraction
            # is a real wiring defect (get_agent_context always sets both
            # for a Lower Basin agent), not a legitimate "no junior water"
            # case to silently paper over with a fabricated 0.
            if "lb_junior_request_af" not in env_context or "lb_junior_tier_cut_fraction" not in env_context:
                raise ValueError(
                    f"build_water_situation_text: shortage_tier={shortage_tier} is "
                    "declared for a Lower Basin agent but 'lb_junior_request_af' or "
                    "'lb_junior_tier_cut_fraction' is missing from env_context; "
                    "refusing to silently treat a real value as 0."
                )
            junior_request_af = env_context["lb_junior_request_af"] or 0.0
            junior_cut_fraction = env_context["lb_junior_tier_cut_fraction"] or 0.0
            if junior_request_af > 1e-6 and junior_cut_fraction > 0:
                # WP1c review round 2 (MEDIUM 2): the three 100%-junior
                # agents (senior entitlement 0 -- Cibola Valley IDD, Hopi
                # Tribe, North Baja LLC) hold no senior water at all, so
                # "Part of your water right" is false for them; the other
                # three (Mohave Valley, Gila Monster Farms, Cocopah) hold
                # some senior water alongside their junior share.
                senior_ent = env_context.get("lb_senior_entitlement_af")
                if senior_ent is None:
                    raise ValueError(
                        "build_water_situation_text: this decision has a positive "
                        "lb_junior_request_af but 'lb_senior_entitlement_af' is "
                        "missing from env_context; refusing to silently guess "
                        "whether this agent holds any senior water at all."
                    )
                share_word = "All" if senior_ent <= 1e-6 else "Part"
                lines.append(
                    f"The Bureau of Reclamation has declared a Tier {shortage_tier} Lower Basin "
                    f"shortage: this cuts Arizona and Nevada deliveries by "
                    f"{shortage_volume_maf * 1e6:,.0f} acre-ft in total. "
                    f"{share_word} of your water right is junior-priority, and this tier cuts "
                    f"your junior-priority water by about {junior_cut_fraction:.0%}. The rest of "
                    f"your delivery is reduced only if Lake Mead cannot physically supply "
                    f"all Lower Basin withdrawals this year."
                )
            else:
                lines.append(
                    f"The Bureau of Reclamation has declared a Tier {shortage_tier} Lower Basin "
                    f"shortage: this cuts Arizona and Nevada deliveries by "
                    f"{shortage_volume_maf * 1e6:,.0f} acre-ft in total. "
                    f"Your own delivery is reduced only if Lake Mead cannot physically "
                    f"supply all Lower Basin withdrawals this year."
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


def build_option_texts(
    profile: IrrigationAgentProfile,
    base: float,
    water_right: float,
    floor: float,
) -> Dict[str, str]:
    """WP2 spec 2.6: ``{skill_id: option text}`` for the v3 skills, each
    stating the request that RESULTS, relative to ``base`` (the amount
    received last year -- the WP2 step base, spec 2.1). Numbers are
    formatted ``,.0f`` per spec.

    ``s``, the "typical step" shown in every option, is the median of the
    agent's own Hung and Yang distribution (spec 2.5), computed from
    ``resolve_step_bin_af`` (review round 1, LOW 8 -- the SAME resolver
    ``execute_skill`` and ``build_simulation_log_row`` use: prefer
    ``profile.step_bin_af``, else ``profile.bin_size_af``, else
    ``water_right / SYNTHETIC_BIN_DIVISOR`` for a profile with no real
    Hung and Yang grid at all).

    WP2 review round 1 (LOW 9): ``base``, ``s``, ``water_right`` and
    ``floor`` are rounded to whole acre-ft ONCE, and every target is then
    computed from those ROUNDED parts -- so the printed base plus the
    printed step always equals the printed target exactly (rounding each
    number independently at display time could disagree by 1 acre-ft).

    WP2 review round 1 (MEDIUM 5, PI decision): the minimum-use floor is
    a menu filter in EVERY arm, so a decrease is never offered once
    ``base`` is within 1 percent of the floor -- the returned dict OMITS
    ``"decrease_demand"`` entirely in that case (the same RAW,
    pre-rounding tolerance ``execute_skill``'s own no-op guard and
    ``below_minimum_utilisation`` use), rather than state a request
    ``execute_skill`` will never execute. WP3 wires this into the
    identity-rule menu filter for every profile INCLUDING ``disabled``
    (spec 3.1, not yet true of ``disabled`` at this commit); until then
    this omission is this function's own contract, independent of which
    profile is running. The water-right cap has no matching omission
    here: an increase at the cap still names a real, if capped, target
    (``water_right`` itself), unlike a decrease at the floor, which the
    old unconditional formula could describe as landing ABOVE base --
    the asymmetry review MEDIUM 5 flagged.

    ``IrrigationLifecycleHooks.pre_year`` stores the returned dict as
    ``option_text_overrides`` in the agent's ``custom_attributes``;
    ``SkillFilterMixin._inject_options_text`` (broker/core/
    _skill_filtering.py) reads it ahead of the skill registry's static
    description.
    """
    step_bin_af = resolve_step_bin_af(profile.step_bin_af, profile.bin_size_af, water_right)
    s = hy_threshold_af(profile.mu, profile.sigma, step_bin_af)

    base_r = round(base)
    s_r = round(s)
    w_r = round(water_right)
    f_r = round(floor)

    increase_to = min(base_r + s_r, w_r)
    text_increase = (
        f"Increase your request to about {increase_to:,.0f} acre-ft: the "
        f"{base_r:,.0f} acre-ft you received last year plus your typical "
        f"step of about {s_r:,.0f} acre-ft"
    )
    if base_r + s_r > w_r:
        text_increase += f" (your water right stops it at {w_r:,.0f} acre-ft)"
    text_increase += "."

    text_maintain = (
        f"Keep your request at {base_r:,.0f} acre-ft, the amount you "
        f"received last year."
    )

    texts: Dict[str, str] = {
        "increase_demand": text_increase,
        "maintain_demand": text_maintain,
    }

    if base > 1.01 * floor:  # RAW comparison: matches execute_skill's own gate exactly
        decrease_to = max(base_r - s_r, f_r)
        text_decrease = (
            f"Decrease your request to about {decrease_to:,.0f} acre-ft: the "
            f"{base_r:,.0f} acre-ft you received last year minus your typical "
            f"step of about {s_r:,.0f} acre-ft"
        )
        if base_r - s_r < f_r:
            text_decrease += f" (the minimum-use floor stops it at {f_r:,.0f} acre-ft)"
        text_decrease += "."
        texts["decrease_demand"] = text_decrease

    return texts


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
    # enforced as a precondition instead of an identity rule. WP2 (spec
    # 2.2) adds a SECOND registry precondition (decrease_demand's "not
    # below_minimum_utilisation"), so this fixed string is no longer
    # correct for every precondition_violation -- see
    # _precondition_violation_label below, which this entry is now only
    # the FALLBACK for (no proposed_skill to disambiguate by direction).
    "precondition_violation": "the water-right cap",
    "minimum_utilisation_floor": "the minimum-use floor",
    "zero_escape_floor": "the minimum-use rule for maintaining",
    "consecutive_increase_cap": "the consecutive-increase limit",
    "non_negative_diversion": "the zero-delivery rule",
}


def _precondition_violation_label(rule_id: str, proposed_skill: str) -> str:
    """Disambiguate the generic ``precondition_violation`` rule id (any
    registry ``preconditions:`` failure, ``broker/core/skill_broker_engine.py``)
    by the DIRECTION of the proposed skill it was raised against (WP2, spec
    2.2): an increase can only have failed ``not at_allocation_cap`` (the
    water-right cap); a decrease can only have failed ``not
    below_minimum_utilisation`` (the minimum-use floor) -- the registry's
    only two preconditions, one per direction. Any other rule id, or a
    ``proposed_skill`` that is neither, falls back to ``_RULE_LABELS``
    (its own "the water-right cap" default, kept for a caller that predates
    this disambiguation)."""
    if rule_id == "precondition_violation":
        if proposed_skill.startswith("increase"):
            return "the water-right cap"
        if proposed_skill.startswith("decrease"):
            return "the minimum-use floor"
    return _RULE_LABELS.get(rule_id, "a governance rule")


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
            proposed_skill_for_label = action_ctx.get("proposed_skill")
            if proposed_skill_for_label and rules:
                label = _precondition_violation_label(rules[0], proposed_skill_for_label)
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
    base_af: Optional[float] = None,
    precipitation_mm: Optional[float] = None,
    precipitation_flag: Optional[int] = None,
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

    v3 (spec 1.7, WP1) log columns. ``ub_non_farm_maf``, ``lb_tributary_maf``,
    ``powell_evap_maf``, ``mead_evap_maf``, ``powell_spill_maf``,
    ``mead_spill_maf``, ``lb_delivered_maf``, ``lb_non_ag_delivered_maf``,
    ``mexico_delivered_maf`` and ``lb_shortage_volume_maf`` all come
    straight from ``settlement`` (``IrrigationEnvironment._settle``
    already returns them); ``calendar_year`` likewise, when the snapshot
    that produced ``settlement`` carried one (real ``advance_year()`` runs
    always do; a hand-built settlement in an older test may not, and gets
    ``None``). ``step_bin_af`` / ``typical_step_af`` are computed here via
    ``resolve_step_bin_af`` (review round 1, LOW 8: the SAME resolver
    ``execute_skill`` and ``build_option_texts`` use -- ``agent_state``'s
    own ``step_bin_af``, WP2 spec 2.3/2.4's FINAL, UB-converted and
    possibly rescaled bin; else the legacy ``bin_size_af``; else
    ``water_right / 25`` -- never ``None``, so this column always reflects
    what the environment actually drew against) and ``mu`` / ``sigma``
    (already stored per agent; ``hy_threshold_af`` is the exact WP2 spec
    2.5 formula, ``(max(0, mu) + 0.6745 sigma) x step_bin_af``). ``base_af`` (the WP2
    "step base": the agent's request as of the last COMMITTED settlement,
    before this year's decision, spec 2.1) is ``agent_state["base_af"]``,
    set once a year by ``IrrigationEnvironment._reset_requests_to_base``
    -- callers still pass it explicitly (this function only ever reads
    ``agent_state``, never the environment directly), ``None`` for a
    hand-built ``agent_state`` from an older test that predates it.
    ``precipitation_mm`` / ``precipitation_flag`` are the
    agent's own value and flag for the year (``IrrigationEnvironment.
    get_agent_context(agent_id)["precipitation"]`` /
    ``["precipitation_flag"]``, spec 1.6) -- ``None`` unless the caller
    passes them, since this function receives ``agent_state`` (the
    environment's persistent per-agent dict), not the per-decision context.

    Returns a dict whose key order IS the canonical LLM simulation-log
    column order (callers needing that order/set, e.g. a header-superset
    test, should read ``list(row.keys())`` from a row built here rather
    than hardcoding a second copy of the field list).
    """
    request = agent_state.get("request", 0)
    diversion = agent_state.get("diversion", 0)
    water_right = agent_state.get("water_right", 0)
    # WP2 review round 1 (LOW 8): the SAME shared resolver execute_skill
    # and build_option_texts use, so the logged typical_step_af always
    # matches the value the environment actually drew against (including
    # the water_right / 25 synthetic fallback -- previously this function
    # logged None there instead of the value execute_skill really used).
    step_bin_af = resolve_step_bin_af(
        agent_state.get("step_bin_af"), agent_state.get("bin_size_af"), water_right,
    )

    # WP1b (item 20, spec 1b.4): the per-sub-basin record this year's
    # settlement carries (None for a Lower Basin agent, a lees_ferry_pool
    # settlement, or an Upper Basin agent with no sub-basin) -- looked up
    # by THIS agent's own supply_group, never fabricated for one it does
    # not have. Lower Basin rows stay blank (None), not 0 (spec: "Lower
    # Basin rows are blank, not 0").
    ub_subbasin_id = agent_state.get("supply_group") if basin == "upper_basin" else None
    ub_subbasin_rec = None
    if ub_subbasin_id and isinstance(settlement.get("ub_subbasin"), dict):
        ub_subbasin_rec = settlement["ub_subbasin"].get(ub_subbasin_id)
    typical_step_af = hy_threshold_af(
        agent_state.get("mu", SYNTHETIC_HY_MU),
        agent_state.get("sigma", SYNTHETIC_HY_SIGMA),
        step_bin_af,
    )

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
        # v3 (spec items 26/27): the declared Powell tier (EQ/UEB/MER/LEB,
        # or LROC for a pre-2008 hindcast year) and its governing ROD
        # sub-rule -- None in "storage_balancing" mode, which has no
        # tiers, or for a hand-built settlement from an older test.
        "powell_tier": settlement.get("powell_tier"),
        "powell_tier_rule": settlement.get("powell_tier_rule"),
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
        # v3 (spec 1.7, WP1)
        "calendar_year": settlement.get("calendar_year"),
        "base_af": base_af,
        "ub_non_farm_maf": settlement.get("ub_non_farm_maf"),
        "lb_tributary_maf": settlement.get("lb_tributary_maf"),
        "powell_evap_maf": settlement.get("powell_evap_maf"),
        "mead_evap_maf": settlement.get("mead_evap_maf"),
        "powell_spill_maf": settlement.get("powell_spill_maf"),
        "mead_spill_maf": settlement.get("mead_spill_maf"),
        "lb_delivered_maf": settlement.get("lb_delivered_maf"),
        "lb_non_ag_delivered_maf": settlement.get("lb_non_ag_delivered_maf"),
        "mexico_delivered_maf": settlement.get("mexico_delivered_maf"),
        "lb_shortage_volume_maf": settlement.get("lb_shortage_volume_maf"),
        "precipitation_mm": precipitation_mm,
        "precipitation_flag": precipitation_flag,
        "step_bin_af": step_bin_af,
        "typical_step_af": typical_step_af,
        # WP1b (item 20, spec 1b.4)
        "ub_subbasin": ub_subbasin_id if ub_subbasin_rec is not None else None,
        "ub_subbasin_available_af": ub_subbasin_rec["available_af"] if ub_subbasin_rec else None,
        "ub_subbasin_request_af": ub_subbasin_rec["request_af"] if ub_subbasin_rec else None,
        "ub_subbasin_ratio": ub_subbasin_rec["ratio"] if ub_subbasin_rec else None,
        # WP1c (item 22): this decision's Lower Basin senior/junior split
        # (AF, before and after the tier cut respectively) and the declared
        # tier's junior-cut fraction f_g. None for an Upper Basin agent
        # (agent_state never carries these keys there); 0 for a Lower Basin
        # agent with no junior entitlement or an untouched request, exactly
        # like curtailment_ratio's own 0-for-unaffected convention above.
        "lb_senior_af": agent_state.get("lb_senior_af"),
        "lb_junior_af": agent_state.get("lb_junior_af"),
        "lb_junior_cut_af": agent_state.get("lb_junior_cut_af"),
        "lb_junior_tier_cut_fraction": agent_state.get("lb_junior_tier_cut_fraction"),
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
    """Cluster inference by Euclidean distance to three 4-D centroids (mu, sigma, alpha, regret).

    PROVENANCE NOTE (corrected 2026-09-28, fix/irrigation-persona-clusters-hy2021):
    the four values per cluster below are exactly
    Hung & Yang (2021, WRR) Table 1 (p.13)'s "Mean: mu", "Standard deviation:
    sigma", "Learning rate: alpha" and "regret" columns (Table 1 has two more
    columns, "Discount rate: gamma" and "Epsilon: epsilon", which this 4-D
    nearest-centroid method does not use). What this function does NOT
    reproduce is the paper's actual clustering *procedure* (PCA on all six
    calibrated parameters to 2 components, then k=3 K-means on those
    components, Sec. 4.2 p.12) -- it is a nearest-centroid shortcut on a
    4-parameter subset instead, and it disagrees with the paper's own
    published per-entity assignment (Figure 7, p.13) for 15 of the 31
    calibrated entities (verified 2026-09-28 by recomputing this function
    against ``ALL_colorado_ABM_params_cal_1108.csv`` and diffing against a
    Figure 7 transcription; see ``HY2021_CLUSTER_LABELS`` below for that
    transcription and the full reproduction notes). This function is kept,
    unchanged, as the ``cluster_method="legacy_centroid"`` path of
    ``create_profiles_from_data`` for byte-identical reproduction of runs
    generated before ``cluster_method`` existed (e.g. the 431adb5e corpus);
    new runs should use the default ``cluster_method="hy2021"`` instead,
    which reads ``HY2021_CLUSTER_LABELS`` (the paper's published assignment)
    rather than approximating it.
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


# Hung & Yang (2021, WRR) Figure 7 (p.13): "The clusters of agents in the
# principal component space" -- a per-entity scatter of all 31 calibrated
# entities (22 Lower Basin agents + 9 Upper Basin state groups) in the 2-D
# PCA space described in Sec. 4.2 (p.12): PCA on all six calibrated
# parameters (mu, sigma, alpha, gamma, epsilon, regret), then k=3 K-means on
# the first two components. This dict is a direct transcription of that
# figure (blue diamond = Aggressive, orange square = Forward-looking
# Conservative, gray triangle = Myopic Conservative), read from the PDF at
# 6x render zoom with per-marker RGB sampling to disambiguate crowded
# points, cross-checked against the paper's text (p.13-14) and Table 1
# (p.13) wherever the text names a specific fact. It is the paper's
# published assignment and is treated as the source of truth for
# ``cluster_method="hy2021"`` in ``create_profiles_from_data`` -- NOT the
# output of our own from-scratch reproduction of the PCA+K-means procedure
# (see below).
#
# Reproduction attempt (2026-09-28): re-running Sec. 4.2's procedure
# from scratch (numpy PCA via SVD to 2 components, then an EXHAUSTIVE
# deterministic k=3 K-means -- every one of C(31,3)=4,495 combinations of
# 3 distinct entities as initial centroids, Lloyd's algorithm to
# convergence, lowest inertia kept; inertia cross-checked against
# sklearn.cluster.KMeans(n_init=200) and found identical, confirming the
# global optimum was found) does NOT exactly recover this table, in either
# of the two standardization choices tried (the paper does not say whether
# it standardized the six parameters before PCA):
#   - raw (unstandardized) 6-D input before PCA: 14 of 31 entities differ
#     from the table below; the fitted clusters do not put all 9 UB groups
#     in one cluster (UT2 lands with the aggressive-poor group) and do not
#     reproduce "LB agents all conservative except the named tribal
#     agents" either.
#   - standardized (z-scored) 6-D input before PCA: 19 of 31 entities
#     differ when clusters are named by nearest standardized Table-1 mean
#     (the paper's stated naming method, tried across all 3! = 6
#     cluster-to-label pairings, lowest total distance kept -- the same
#     bijective assignment used for the unstandardized case above). Taking
#     instead the best of those same 6 pairings by minimum disagreement
#     against Figure 7 directly (a post-hoc best case that Table 1 alone
#     cannot tell you to pick, since it does not look at Figure 7) drops
#     this to 15 of 31; still worse than the unstandardized attempt either
#     way, and still short of an exact reproduction.
# Neither run reproduces the paper's own stated facts (Sec. 4.2, p.13-14):
# "[all 9] UB agents ... are mostly Aggressive" and "the LB agents are all
# classified as conservative except three tribal water users". Because the
# reproduction does not agree, this table is transcribed from the figure
# directly rather than computed -- per this function's own module
# docstring and the file's anti-hallucination posture, an unreproduced
# procedure must not silently stand in for the paper's actual published
# result.
#
# One more disagreement worth recording here because it affects the table
# below directly: the paper's own text (p.13) says "the LB agents are all
# classified as conservative except three tribal water users (Fort Mohave
# Ind Res AZ, FtYumaReservation, and Chemehuevi Ind Res)" -- naming three
# exceptions. Figure 7 itself, however, plots a FOURTH Lower Basin agent,
# CocopahIndRes (also a tribal reservation, the Cocopah Indian
# Reservation), as a blue diamond (Aggressive) at approximately
# (x=-0.15, y=0.0), confirmed by direct RGB sampling of that marker: RGB
# (91, 155, 212), the exact fill color of every other Aggressive diamond
# in the figure (sampled directly, not assumed), and not the gray of the
# adjacent CRIR CA triangle. The text's "three" therefore
# undercounts its own figure by one. This table follows the figure (the
# actual per-entity assignment WAGF acts on) over the text's summary
# count, so CocopahIndRes is Aggressive here.
HY2021_CLUSTER_LABELS: Dict[str, str] = {
    # --- Lower Basin (22 agents; direct 1:1 match with the parameters CSV) ---
    "MohaveValleyIDD": "myopic_conservative",
    "Fort Mohave Ind Res AZ": "aggressive",
    "Fort Mohave Ind Res CA": "myopic_conservative",
    "CRIR AZ": "myopic_conservative",
    "CRIR CA": "myopic_conservative",
    "NorthGilaValleyIDD": "forward_looking_conservative",
    "YumaCountyWUA": "myopic_conservative",
    "UnitBIDD": "forward_looking_conservative",
    "CocopahIndRes": "aggressive",  # see note above: a 4th tribal exception the text does not name
    "GilaMonsterFarms": "forward_looking_conservative",
    "Powers": "forward_looking_conservative",
    "FtYumaReservation": "aggressive",
    "YumaIrrDist": "myopic_conservative",
    "YumaMesaIDD": "forward_looking_conservative",
    "WelltonMohawkIDD": "myopic_conservative",
    "CibolaValleyIDD": "myopic_conservative",
    "HopiTribe": "forward_looking_conservative",
    "NorthBajaLLC": "myopic_conservative",  # text's named exception: MC but plotted below the x-axis
    "PVIDDiversionAG": "forward_looking_conservative",
    "Bard Unit": "myopic_conservative",
    "Quechan Res Unit": "myopic_conservative",
    "Chemehuevi Ind Res": "aggressive",
    # --- Upper Basin (9 state groups; each group's ~58 individual CRSS
    # agents inherit the group's label, exactly as they inherit the
    # group's FQL parameters -- see create_profiles_from_data). All 9 are
    # Aggressive, matching Figure 7 and the text ("UB agents ... are
    # mostly Aggressive"). ---
    "WY": "aggressive",
    "UT1": "aggressive",
    "UT2": "aggressive",
    "UT3": "aggressive",
    "NM": "aggressive",
    "CO1": "aggressive",
    "CO2": "aggressive",
    "CO3": "aggressive",
    "AZ_UB": "aggressive",
}


def _resolve_cluster(
    entity_name: str,
    mu: float,
    sigma: float,
    alpha: float,
    regret: float,
    cluster_method: str,
) -> str:
    """Resolve one entity's (or UB state-group's) cluster label.

    ``cluster_method="hy2021"`` (default): look up ``entity_name`` in
    ``HY2021_CLUSTER_LABELS``, the paper's own published Figure 7
    assignment. Raises ``ValueError`` if ``entity_name`` is not one of the
    31 calibrated entities -- a parameters CSV with a new entity needs a
    new table entry (with its own Figure 7 provenance), not a silent guess.

    ``cluster_method="legacy_centroid"``: ``_infer_cluster(mu, sigma,
    alpha, regret)``, the pre-existing 4-D nearest-centroid method,
    byte-identical to behaviour before ``cluster_method`` existed.

    Any other value raises ``ValueError`` (callers should already have
    validated this; this is a defensive second check for direct callers of
    this function).
    """
    if cluster_method == "hy2021":
        if entity_name not in HY2021_CLUSTER_LABELS:
            raise ValueError(
                f"HY2021_CLUSTER_LABELS has no entry for {entity_name!r}. "
                "This table is a fixed transcription of Hung & Yang (2021) "
                "Figure 7 for the 31 calibrated entities; add an entry "
                "(with its Figure 7 provenance noted) before using "
                "cluster_method='hy2021' with a parameters CSV that adds a "
                "new entity, or pass cluster_method='legacy_centroid'."
            )
        return HY2021_CLUSTER_LABELS[entity_name]
    if cluster_method == "legacy_centroid":
        return _infer_cluster(mu, sigma, alpha, regret)
    raise ValueError(
        f"cluster_method must be 'hy2021' or 'legacy_centroid', got {cluster_method!r}"
    )


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
    cluster_method: str = "hy2021",
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
        cluster_method: How each entity's persona cluster ("aggressive" /
            "forward_looking_conservative" / "myopic_conservative") is
            assigned (enforced -- raises ``ValueError`` for any other
            value). ``"hy2021"`` (default, added 2026-09-28,
            fix/irrigation-persona-clusters-hy2021): look up
            ``HY2021_CLUSTER_LABELS``, a fixed transcription of Hung &
            Yang (2021) Figure 7's own published per-entity assignment
            (see the comment block above that dict for the full provenance
            and the disagreements found while verifying it).
            ``"legacy_centroid"``: ``_infer_cluster``'s 4-D nearest-centroid
            heuristic, today's pre-2026-09-28 behaviour, byte-identical --
            use this to reproduce a corpus generated before
            ``cluster_method`` existed (e.g. the 431adb5e corpus). The two
            methods disagree on 16 of the 78 real CRSS agents' cluster (10
            Lower Basin agents go aggressive->conservative, all 10 in that
            one direction; 3 more Lower Basin agents keep "conservative"
            but swap forward_looking_conservative<->myopic_conservative;
            and 3 Upper Basin agents in state groups UT2/UT3 go
            conservative->aggressive); only those agents'
            narrative persona and ACA-hint prompt text change between the
            two methods. Exposed end-to-end via ``--cluster-method`` on
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
    if cluster_method not in ("hy2021", "legacy_centroid"):
        raise ValueError(
            f"cluster_method must be 'hy2021' or 'legacy_centroid', got {cluster_method!r}"
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
    # Sibling 2017 row for the FQL calibrated warm-start's prev_action
    # (Div_2018 - Div_2017) and prev_diversion (P1-b fix, 2026-09-27
    # review: H&Y's first Q-update credits state(2017), not state(2018)).
    # REQUIRED, mirroring the 2018 check above (P1-b/(v)): calibrated
    # mode must never silently fall back to a made-up prev_action: better
    # to fail loudly here than have resolve_prev_action() degrade later.
    if 2017 not in lb_hist.index:
        raise ValueError(f"{lb_hist_path} has no row for year 2017; cannot compute actual_2017_diversion.")
    lb_2017 = lb_hist.loc[2017]
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
    # Sibling 2017 row (see lb_2017 above for rationale) -- REQUIRED,
    # same as LB.
    if 2017 not in ub_hist.index:
        raise ValueError(f"{ub_hist_path} has no row for year 2017; cannot compute actual_2017_diversion.")
    ub_2017 = ub_hist.loc[2017] * 1000

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

    def _step_bin_and_source(
        agent_name: str, bin_size_af: float, actual_2018_diversion: Optional[float],
    ) -> Tuple[float, str]:
        """WP2 spec 2.4: rescale the step bin to 10 percent of this
        agent's 2018 use where the (already UB-converted, spec 2.3)
        ``bin_size_af`` exceeds 20 percent of that use -- H&Y p. 8's own
        description of the grid increment ("approximately 10% of the
        2018 diversion"), for the 8 agents whose grid was evidently not
        built at their own scale. Requires a positive
        ``actual_2018_diversion``: create_profiles_from_data's own
        historical-data checks (Review P2, 2026-09-27) already guarantee
        one for every active real profile, so a missing value here is a
        wiring defect, not a legitimate gap to paper over with the
        unrescaled grid step.
        """
        if not actual_2018_diversion or actual_2018_diversion <= 0:
            raise ValueError(
                f"{agent_name}: actual_2018_diversion is required to "
                f"compute step_bin_af (WP2 spec 2.4) but is "
                f"{actual_2018_diversion!r}."
            )
        if bin_size_af > 0.20 * actual_2018_diversion:
            return 0.10 * actual_2018_diversion, "rescaled"
        return bin_size_af, "grid"

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
        cluster = _resolve_cluster(agent_name, mu, sigma, alpha, regret_val, cluster_method)

        # WP2 spec 2.3: k = 1.0 in the Lower Basin -- its grid already
        # reports consumptive use, so bin_size_af needs no conversion.
        demand_per_grid_unit = 1.0
        bin_size_af = demand_per_grid_unit * float(col.iloc[2] - col.iloc[1])
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
            demand_per_grid_unit=demand_per_grid_unit,
            grid_top_af=grid_top_af,
            peak_obs_af=peak_obs_af,
            water_right_source=water_right_source,
            div_states_grid=np.asarray(col, dtype=float),
            crop_type=_assign_crop_type("lower_basin", rng),
            years_farming=int(rng.integers(5, 40)),
        )
        if lb_2018 is not None and agent_name in lb_2018.index:
            profile.actual_2018_diversion = float(lb_2018[agent_name])
        if lb_2017 is not None and agent_name in lb_2017.index:
            profile.actual_2017_diversion = float(lb_2017[agent_name])
        profile.step_bin_af, profile.step_bin_source = _step_bin_and_source(
            agent_name, bin_size_af, profile.actual_2018_diversion,
        )
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
        cluster = _resolve_cluster(state_group, mu, sigma, alpha, regret_val, cluster_method)

        # WP2 spec 2.3 (L1-02, L2 H3): k = 0.5 in the Upper Basin -- the
        # grid is in DIVERSION units, and H&Y (2021, p. 9) assume 50
        # percent of a diversion is depleted (the CRSS convention), so a
        # step drawn on the raw grid overstates the depletion-unit change
        # by 2x unless converted here.
        demand_per_grid_unit = 0.5
        bin_size_af = demand_per_grid_unit * float(col.iloc[2] - col.iloc[1])
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
            demand_per_grid_unit=demand_per_grid_unit,
            grid_top_af=grid_top_af,
            peak_obs_af=peak_obs_af,
            water_right_source=water_right_source,
            div_states_grid=np.asarray(col, dtype=float),
            crop_type=_assign_crop_type("upper_basin", rng),
            years_farming=int(rng.integers(5, 40)),
            # v3 (spec 1.6): the PRISM precipitation CSV's column naming
            # matches _UB_STATE_GROUPS one-to-one except AZ_UB -> "AZ",
            # the exact mismatch _UB_HIST_COLUMN_BY_GROUP already maps.
            precip_group=_UB_HIST_COLUMN_BY_GROUP.get(state_group, state_group),
        )
        if ub_2018 is not None:
            hist_col = _UB_HIST_COLUMN_BY_GROUP.get(state_group, state_group)
            if hist_col in ub_2018.index:
                profile.actual_2018_diversion = float(ub_2018[hist_col]) * ratio
        if ub_2017 is not None:
            # Same per-agent `ratio` (this agent's share of its state
            # group's grid-top total) used for actual_2018_diversion
            # above -- an approximation of H&Y's own
            # Within_Group_Dist_*_Div_req.csv (ABM_CRSS_coupling.py
            # Calculate_Within_Group_Dist, lines 441-479), which we do
            # not have a static copy of; noted per (v)/2026-09-27 review.
            hist_col_2017 = _UB_HIST_COLUMN_BY_GROUP.get(state_group, state_group)
            if hist_col_2017 in ub_2017.index:
                profile.actual_2017_diversion = float(ub_2017[hist_col_2017]) * ratio
        profile.step_bin_af, profile.step_bin_source = _step_bin_and_source(
            agent_name, bin_size_af, profile.actual_2018_diversion,
        )
        profile.narrative_persona = build_narrative_persona(profile, rng)
        profiles.append(profile)

    return profiles
