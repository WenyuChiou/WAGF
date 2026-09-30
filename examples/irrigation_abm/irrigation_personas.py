"""
Irrigation agent persona builder.

Generates narrative personas and context strings for LLM prompt injection,
analogous to the flood experiment's memory_templates.py.  Personas are
derived from the three FQL behavioral clusters (Hung & Yang 2021).

Each agent receives (v3, WP4, irrigation_v3_spec_2026-09-28.md 4.1-4.5):
- one fixed persona text per cluster (build_narrative_persona);
- the water situation text for the year (build_water_situation_text);
- the option texts (build_option_texts, WP2);
- one memory line per past year (build_action_outcome_feedback).
Every sentence states a model quantity or a Hung and Yang parameter; the
conservation-status line and the adaptive-capacity hint are gone.
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
# Cluster personas (v3, WP4, spec 4.1; provenance A5, A7, A8)
# ============================================================================

# Opening, all 78 agents. Hung and Yang (2021, p. 2): an agent "can be a
# single farm, an irrigation ditch, an irrigation district, American tribal
# water users, or a group of farming entities"; Eq. 5 (p. 4): the reward is
# production from the water received.
_PERSONA_OPENING = (
    "You are {agent_id}, an agricultural water user (an irrigation district, "
    "a tribal water user, or a group of water users) in the {basin_name} of "
    "the Colorado River, holding a water right of {water_right:,.0f} "
    "acre-ft/year. The more water you receive, the more you can produce."
)

# Upper Basin volumes are depletions (Hung and Yang 2021, p. 9).
_UB_VOLUME_SENTENCE = "All volumes shown to you are consumptive use."

_PERSONA_BASIN_NAME = {
    "upper_basin": "Upper Basin",
    "lower_basin": "Lower Basin",
}

# One fixed text per cluster (A8: no random wording variant). Spec item 29d
# (2026-09-30): each sentence is a statement about the agent's GROUP ("Users
# in your group tend to ...", the framing the PI approved), never about the
# agent itself, because an agent's own parameter can sit on the other side of
# a comparison its cluster's mean satisfies (63 of the 78 agents have at
# least one such parameter). It states a cluster tendency of Hung and Yang
# (2021) Table 1 (p. 13) and Fig. 7, as a comparison with the other
# clusters and without superlatives, for the three parameters whose cluster
# ordering holds in the calibrated parameter file
# (ref/RL-ABM-CRSS/ALL_colorado_ABM_params_cal_1108.csv), whether the cluster
# mean is taken over its 31 calibrated entities or over its agents:
# regret (concern about a shortfall) aggressive < myopic < forward-looking;
# alpha (how quickly expectations are revised) forward-looking above both
# others (aggressive against myopic flips between the two means, so it is
# not compared); gamma (weight on future years) myopic < aggressive <
# forward-looking. Exploration (epsilon) is not mentioned: its ordering does
# not hold. "More cautious users" are H&Y's two conservative clusters. Every
# comparison names its group: aggressive users give future years less weight
# than forward-looking users only, not than myopic users (WP4 re-review).
# test_v3_prompt.py (test_persona_claims_hold_for_cluster_means) checks every
# comparison against both means. Nothing about step size, finances,
# technology, tenure or neighbours (L3 M2, M3).
_CLUSTER_PERSONAS = {
    "aggressive": (
        "Users in your group tend to be less concerned by a shortfall between "
        "what they request and what they receive than more cautious users are. "
        "They tend to revise their expectations more slowly than "
        "forward-looking users do and to give future years less weight than "
        "forward-looking users do."
    ),
    "forward_looking_conservative": (
        "Users in your group tend to be more concerned by a shortfall between "
        "what they request and what they receive than other users are. They "
        "tend to revise their expectations more quickly than other users do "
        "and to give future years more weight than other users do."
    ),
    "myopic_conservative": (
        "Users in your group tend to be more concerned by a shortfall between "
        "what they request and what they receive than aggressive users are, "
        "but less than forward-looking users are. They tend to revise their "
        "expectations more slowly than forward-looking users do and to give "
        "future years less weight than other users do."
    ),
}

# The basin names of the situation text's first line ("You use water in the
# Upper Colorado River Basin.").
_BASIN_DISPLAY = {
    "upper_basin": "Upper Colorado River Basin",
    "lower_basin": "Lower Colorado River Basin",
}


def build_narrative_persona(
    profile: IrrigationAgentProfile,
    rng: Optional[np.random.Generator] = None,
) -> str:
    """The agent's fixed persona text (spec 4.1): the opening, the Upper
    Basin volume sentence for Upper Basin agents, and its cluster's text.

    ``rng``: the persona no longer depends on it (one text per cluster), but
    the one draw the retired two-variant pick made is still taken, so every
    caller's later draws (crop type and years farming of later profiles, the
    parameters of later synthetic profiles) stay the same numbers.
    """
    if rng is not None:
        rng.integers(0, 2)
    if profile.cluster not in _CLUSTER_PERSONAS:
        raise ValueError(
            f"{profile.agent_id}: cluster {profile.cluster!r} has no persona text "
            f"({sorted(_CLUSTER_PERSONAS)})."
        )
    if profile.basin not in _PERSONA_BASIN_NAME:
        raise ValueError(
            f"{profile.agent_id}: basin {profile.basin!r} is neither "
            "'upper_basin' nor 'lower_basin'."
        )
    parts = [_PERSONA_OPENING.format(
        agent_id=profile.agent_id,
        basin_name=_PERSONA_BASIN_NAME[profile.basin],
        water_right=profile.water_right,
    )]
    if profile.basin == "upper_basin":
        parts.append(_UB_VOLUME_SENTENCE)
    parts.append(_CLUSTER_PERSONAS[profile.cluster])
    return " ".join(parts)


# v3 (WP3, spec 3.3): the ONE "full supply" edge. A share of a request at or
# above it counts as a full delivery; below it, as a shortfall. The supply
# rule (validators/irrigation_validators.py, supply_gap_block_increase)
# blocks an increase below it, the situation text's headline and its
# "expected delivery" sentence switch at it, and the post hoc metrics read it.
# Every one of them imports this name; none holds a copy of the number, so an
# agent told that supply is sufficient can never be blocked by the supply
# rule. 0.999 is a tolerance (0.1 percent of the request), not a threshold
# with a source: item 2 of the PI decisions allows no other numeric threshold.
FULL_SUPPLY_RATIO = 0.999


def supply_ratio(expected_af: float, request_af: float) -> float:
    """r (spec conventions): the expected delivery at a request as a share of
    that request, rounded to 6 places; 1.0 when the request is 0 (nothing
    requested, nothing short). Shared by the supply rule's inputs and the
    situation text, so both compare the same number with FULL_SUPPLY_RATIO."""
    if request_af <= 0:
        return 1.0
    return round(float(expected_af) / float(request_af), 6)


def format_share(share: float) -> str:
    """Spec 4.3 share format, for every agent-facing share of a request (the
    situation text, the memory line's delivered share and the supply rule's
    message): a share at or above FULL_SUPPLY_RATIO counts as a full delivery
    and prints as "100%"; a share below it prints with one decimal, e.g.
    "99.7%". A share in [0.995, 0.999) therefore never prints as "100%" next
    to a shortfall, as ``f"{share:.0%}"`` would. Pass the share rounded as
    ``supply_ratio`` rounds it, so the comparison and the printed number
    agree."""
    if share >= FULL_SUPPLY_RATIO:
        return "100%"
    return f"{share:.1%}"


# ONE helper turns a settlement's gap_reason code into the phrase every text
# uses (situation text, supply-rule message, memory line), so the stated
# reason cannot drift between them (spec 4.4). Each code has a present form
# (this year's expected delivery) and a past form (last year's outcome).
_REASON_TEXT = {
    # WP1b (item 20): the agent's own sub-basin is short. Spec item 29b: what
    # falls short is the water the sub-basin can draw, A_s = c_s x Q_s, a
    # fixed share of the natural flow at its gauges (spec 1b.2), not the
    # natural flow itself, which is always larger than the requests.
    "ub_subbasin_supply": {
        "present": ("the water your sub-basin can draw this year, a fixed share of "
                    "the natural flow of its rivers, is below the combined requests "
                    "of its users, and the shortfall is shared in proportion to "
                    "requests"),
        "past": ("the water your sub-basin could draw that year, a fixed share of "
                 "the natural flow of its rivers, was below the combined requests "
                 "of its users, and the shortfall was shared in proportion to "
                 "requests"),
    },
    # The same code for the only member of its sub-basin (UT2): no other user
    # shares the shortfall, so neither "combined requests of its users" nor
    # "shared in proportion to requests" is true.
    "ub_subbasin_supply_alone": {
        "present": ("the water your sub-basin can draw this year, a fixed share of "
                    "the natural flow of its rivers, is below your own request"),
        "past": ("the water your sub-basin could draw that year, a fixed share of "
                 "the natural flow of its rivers, was below your own request"),
    },
    # The basin-wide backstop (and ub_supply_mode="lees_ferry_pool").
    "ub_natural_flow": {
        "present": ("Upper Basin deliveries are limited by this year's natural flow at "
                    "Lees Ferry, after Upper Basin non-farm use, and shared in "
                    "proportion to requests"),
        "past": ("Upper Basin deliveries were limited by that year's natural flow at "
                 "Lees Ferry, after Upper Basin non-farm use, and shared in "
                 "proportion to requests"),
    },
    "ub_capacity": {
        "present": ("Upper Basin deliveries are limited to the {cap:.1f} million acre-ft "
                    "delivery capacity and shared in proportion to requests"),
        "past": ("Upper Basin deliveries were limited to the {cap:.1f} million acre-ft "
                 "delivery capacity and shared in proportion to requests"),
    },
    # Item 14: Lake Mead cannot physically supply every withdrawal.
    "lb_mead_availability": {
        "present": ("Lake Mead cannot meet all Lower Basin withdrawals without falling "
                    "below its minimum pool, so all Lower Basin deliveries are reduced "
                    "in proportion to requests"),
        "past": ("Lake Mead could not meet all Lower Basin withdrawals without falling "
                 "below its minimum pool, so all Lower Basin deliveries were reduced "
                 "in proportion to requests"),
    },
    # Item 22 (WP1c): the declared tier cuts this agent's junior-priority part.
    "lb_junior_tier_cut": {
        "present": "the declared Lower Basin shortage tier cuts your junior-priority water by about {frac:.0%}",
        "past": "the declared Lower Basin shortage tier cut your junior-priority water by about {frac:.0%}",
    },
}


def describe_gap_reason(agent_state: Dict[str, Any], tense: str) -> str:
    """Phrase for why this agent's delivery is (present) or was (past) below
    its request, starting with "because", ready to follow a comma; "" for
    the code ``none`` or a missing code.

    ``agent_state`` carries ``gap_reason`` (a code from
    ``IrrigationEnvironment._settle``; two codes join with "+"), plus
    ``ub_subbasin_member_count`` for ``ub_subbasin_supply`` and
    ``lb_junior_tier_cut_fraction`` for ``lb_junior_tier_cut``. ``tense``
    is "present" (this year's expected delivery, the supply rule) or
    "past" (last year's outcome, the memory line).

    The retired codes ``ub_powell_release`` (item 4: the Upper Basin is never
    cut for a Powell release) and ``lb_shortage_tier`` (item 14: the declared
    tier falls on the non-agricultural aggregate) are no longer produced; an
    unknown code raises instead of being dropped from the sentence.
    """
    if tense not in ("present", "past"):
        raise ValueError(f"describe_gap_reason: tense must be 'present' or 'past', got {tense!r}.")
    code = str(agent_state.get("gap_reason") or "none")
    if code == "none":
        return ""
    parts = []
    for c in code.split("+"):
        if c == "ub_subbasin_supply":
            # A real agent with this code always has a member count (WP1b
            # re-review HIGH 1 / MEDIUM 5); a missing one is a wiring defect.
            member_count = agent_state.get("ub_subbasin_member_count")
            if member_count is None:
                raise ValueError(
                    "describe_gap_reason: gap_reason names ub_subbasin_supply "
                    "but ub_subbasin_member_count is missing from agent_state; "
                    "refusing to silently guess whether this sub-basin has "
                    "other members."
                )
            key = "ub_subbasin_supply_alone" if member_count <= 1 else "ub_subbasin_supply"
            parts.append(_REASON_TEXT[key][tense])
        elif c == "ub_capacity":
            cap = float(agent_state.get("ub_capacity_maf", 5.0) or 5.0)
            parts.append(_REASON_TEXT[c][tense].format(cap=cap))
        elif c == "lb_junior_tier_cut":
            # The percentage is the state's OWN f_g, never hand-copied, so
            # the phrase and _settle's actual cut cannot disagree.
            frac = agent_state.get("lb_junior_tier_cut_fraction")
            if not frac:
                raise ValueError(
                    "describe_gap_reason: gap_reason names lb_junior_tier_cut but "
                    "lb_junior_tier_cut_fraction is missing or 0 in agent_state; "
                    "refusing to silently guess the cut percentage."
                )
            parts.append(_REASON_TEXT[c][tense].format(frac=frac))
        elif c in _REASON_TEXT:
            parts.append(_REASON_TEXT[c][tense])
        else:
            raise ValueError(
                f"describe_gap_reason: unknown gap_reason code {c!r} in {code!r}; "
                "refusing to drop it from the stated reason."
            )
    return "because " + " and ".join(parts)


def _with_reason(text: str, reason: str) -> str:
    return f"{text}, {reason}" if reason else text


def _shortfall_reason(state: Dict[str, Any], tense: str, where: str) -> str:
    """describe_gap_reason for a share below FULL_SUPPLY_RATIO, which must
    carry a reason (``_settle`` sets a code whenever a delivery ratio is
    below 1); an empty one is a wiring defect, not a sentence to shorten."""
    reason = describe_gap_reason(state, tense)
    if not reason:
        raise ValueError(
            f"{where}: a share below FULL_SUPPLY_RATIO has gap_reason "
            f"{state.get('gap_reason')!r} and so no stated reason."
        )
    return reason


def build_water_situation_text(
    env_context: Dict[str, Any],
    last_year: Optional[Dict[str, Any]] = None,
) -> str:
    """The situation text of the prompt, ``{water_situation_text}`` (spec 4.3).

    In order: the year and basin; a headline on r, the expected delivery at
    the keep request as a share of it (five bands, "sufficient" only at r >=
    FULL_SUPPLY_RATIO, the edge below which the supply rule blocks an
    increase); the basin's water information (Upper Basin: the agent's own
    sub-basin winter precipitation, the sub-basin's natural flow as a share
    of its 1971-2018 average, Lake Powell storage; Lower Basin: Lake Mead's
    1 January level and trend, and the declared tier); last year's request,
    delivery and reason (in the first year, the 2018 use); the expected
    delivery at the keep request with its reason; the water right and last
    year's delivery as a share of it. No drought index anywhere.

    ``env_context`` is ``IrrigationEnvironment.get_agent_context``;
    ``current_request`` is the keep request (the base, WP2 spec 2.1) and
    ``current_diversion`` the provisional delivery at it. ``last_year`` is
    the snapshot ``IrrigationLifecycleHooks.post_year`` takes after the
    final settlement (``request``, ``diversion``, ``gap_reason`` and the
    fields ``describe_gap_reason`` reads); None in the first year.
    """
    year = env_context["year"]
    basin = env_context["basin"]
    if basin not in ("upper_basin", "lower_basin"):
        raise ValueError(f"build_water_situation_text: basin {basin!r} is neither Upper nor Lower Basin.")
    upper = basin == "upper_basin"
    base = float(env_context["current_request"])
    expected = float(env_context["current_diversion"])
    water_right = float(env_context["water_right"])
    # WP3 (spec 3.3): r, the share the supply rule compares with
    # FULL_SUPPLY_RATIO, drives the headline and the expected-delivery
    # sentence, so no text calls supply sufficient where the rule blocks.
    r_share = supply_ratio(expected, base)

    lines = [
        f"It is now the year {year}. You {'use' if upper else 'divert'} water in the "
        f"{_BASIN_DISPLAY[basin]}."
    ]

    # Headline on r only (spec 4.3; L3 A.1). The top edge is FULL_SUPPLY_RATIO.
    if r_share >= FULL_SUPPLY_RATIO:
        lines.append("Water supply is sufficient for your full request this year.")
    elif r_share >= 0.95:
        lines.append("Water supply is slightly short of your request this year.")
    elif r_share >= 0.80:
        lines.append("Water supply is short of your request this year.")
    elif r_share >= 0.50:
        lines.append("Water supply is well short of your request this year.")
    else:
        lines.append(
            "Water supply is critically short this year: expected deliveries fall "
            "well below requests."
        )

    if upper:
        # The agent's own sub-basin column and its strict ">" flag (spec 1.6;
        # H&Y p. 5, 9). A synthetic mock agent has no sub-basin and reads
        # the basin-level legacy mean, named as such.
        in_subbasin = env_context.get("supply_group") is not None
        where = "in your sub-basin" if in_subbasin else "averaged over the Upper Basin"
        # Direct index (review LOW 10): get_agent_context always sets the
        # agent's own flag; a missing one is a wiring defect, not "below".
        lines.append(
            f"Winter precipitation {where} this year was "
            f"{float(env_context['precipitation']):.0f} mm "
            f"({'above' if env_context['preceding_factor'] else 'below'} last year)."
        )
        subbasin_flow_share = env_context.get("ub_subbasin_flow_share")
        if subbasin_flow_share is not None:
            # WP1b (item 20, memo section 9): the flow that sets this
            # agent's supply, as a share, so it is not read against the
            # request in acre-ft.
            lines.append(
                "The natural flow of the rivers your sub-basin draws on is "
                f"{subbasin_flow_share:.0%} of its 1971-2018 average this year."
            )
        elif env_context.get("natural_flow_maf"):
            # Synthetic mock agents only (no sub-basin).
            lines.append(
                "Natural flow on the river this year is forecast at "
                f"{env_context['natural_flow_maf']:.1f} million acre-ft."
            )
        powell = env_context.get("powell_storage_maf")
        powell_dead_pool = env_context.get("powell_dead_pool_maf")
        if powell:
            if powell_dead_pool is not None and powell <= powell_dead_pool + 1e-6:
                lines.append(
                    "Lake Powell is at its dead-pool floor on 1 January; "
                    "releases are limited to inflow."
                )
            else:
                lines.append(f"Lake Powell holds {powell:.1f} million acre-ft on 1 January.")
    else:
        # ",.0f" as every other number in the prompt ("1,034 feet", review
        # LOW 8); the flag by direct index (LOW 10).
        lines.append(
            f"Lake Mead was at {env_context['lake_mead_level']:,.0f} feet above sea level "
            f"on 1 January ({'rising' if env_context['preceding_factor'] else 'declining'} "
            f"from last year)."
        )
        lines.append(_lower_basin_tier_text(env_context))

    # Last year's outcome (final settlement); in the first year, the 2018 use.
    if last_year is not None:
        requested = float(last_year["request"])
        received = float(last_year["diversion"])
        share = supply_ratio(received, requested)
        sentence = (
            f"Last year you requested {requested:,.0f} acre-ft and received "
            f"{received:,.0f} acre-ft ({format_share(share)} delivered)"
        )
        if share < FULL_SUPPLY_RATIO:
            sentence += ", " + _shortfall_reason(last_year, "past", "build_water_situation_text")
        lines.append(sentence + ".")
    else:
        lines.append(f"In {int(year) - 1} you {'used' if upper else 'diverted'} {base:,.0f} acre-ft.")

    # This year's expectation at the keep request (G9).
    if r_share >= FULL_SUPPLY_RATIO:
        lines.append(
            f"If you request the {base:,.0f} acre-ft you received last year, you can "
            f"expect full delivery this year."
        )
    else:
        lines.append(
            f"If you request the {base:,.0f} acre-ft you received last year, you can "
            f"expect {expected:,.0f} acre-ft ({format_share(r_share)}) this year, "
            f"{_shortfall_reason(env_context, 'present', 'build_water_situation_text')}."
        )

    share_of_right = base / water_right if water_right > 0 else 0.0
    lines.append(
        f"Your water right is {water_right:,.0f} acre-ft/year; last year's delivery "
        f"was {share_of_right:.0%} of it."
    )
    return "\n".join(lines)


def _lower_basin_tier_text(env_context: Dict[str, Any]) -> str:
    """The Lower Basin declared-shortage sentence (spec 4.3, items 14, 22).

    The declared tier's volume V (2007 ROD, 333/417/500 kaf) is borne by the
    non-agricultural aggregate (item 14) less whatever the tier cuts from
    junior-priority agricultural water (item 22, ``lb_priority_mode="split"``,
    the v3 default); the two together remove exactly V. So the sentence names
    both takers in split mode, and the non-agricultural users alone in
    ``senior_all`` mode, where no junior cut exists. An agent whose request at
    the keep request has a junior-priority part is told its own cut; every
    other agent is told that its delivery is reduced only if Lake Mead cannot
    supply all withdrawals, which is true for it in both modes (spec 4.3's
    "Agricultural deliveries, including yours, are reduced only if ..." is
    false in split mode for the junior-priority water of six agents, so it is
    stated per agent). No agency is named (L3 D3).

    Spec item 29f: an agent that holds junior-priority water but whose keep
    request lies within its senior entitlement (no junior part to cut this
    year) is told that the tier would cut any part of a request above that
    entitlement, since an increase beyond it would be junior-priority water
    (``_settle`` fills the senior entitlement first). An agent outside the
    priority table (``lb_junior_entitlement_af`` None, a synthetic mock
    agent the environment treats as fully senior) reads the senior sentence.
    """
    # Direct index (review LOW 10): get_agent_context always sets the tier.
    tier = int(env_context["shortage_tier"])
    if tier <= 0:
        return "No Lower Basin shortage applies this year."
    volume_maf = env_context.get("lb_shortage_volume_maf")
    threshold_ft = env_context.get("shortage_tier_threshold_ft")
    if volume_maf is None or threshold_ft is None:
        raise ValueError(
            f"build_water_situation_text: shortage_tier={tier} is declared but "
            "'lb_shortage_volume_maf' or 'shortage_tier_threshold_ft' is missing "
            "from env_context; refusing to state a tier without its volume and level."
        )
    missing = [k for k in ("lb_junior_request_af", "lb_junior_tier_cut_fraction",
                           "lb_junior_entitlement_af") if k not in env_context]
    if missing:
        raise ValueError(
            f"build_water_situation_text: shortage_tier={tier} is declared for a "
            f"Lower Basin agent but {missing} is missing from env_context; refusing "
            "to silently treat a real value as 0."
        )
    junior_fraction = env_context["lb_junior_tier_cut_fraction"] or 0.0
    junior_request_af = env_context["lb_junior_request_af"] or 0.0
    junior_entitlement_af = env_context["lb_junior_entitlement_af"]
    opening = (
        f"A Tier {tier} Lower Basin shortage applies this year (Lake Mead was below "
        f"{threshold_ft:,.0f} feet on 1 January): "
    )
    if junior_fraction > 0:
        opening += (
            f"it reduces Lower Basin deliveries by {volume_maf * 1e6:,.0f} acre-ft in "
            "total, taken from non-agricultural users and from junior-priority "
            "agricultural water."
        )
    else:
        opening += (
            f"it reduces deliveries to Lower Basin non-agricultural users by "
            f"{volume_maf * 1e6:,.0f} acre-ft in total."
        )
    if junior_request_af > 1e-6 and junior_fraction > 0:
        # WP1c review round 2 (MEDIUM 2): the three agents with no senior
        # entitlement (Cibola Valley IDD, Hopi Tribe, North Baja LLC) hold
        # junior-priority water only.
        senior_ent = env_context.get("lb_senior_entitlement_af")
        if senior_ent is None:
            raise ValueError(
                "build_water_situation_text: this decision has a positive "
                "lb_junior_request_af but 'lb_senior_entitlement_af' is missing "
                "from env_context; refusing to guess whether this agent holds "
                "any senior water at all."
            )
        share_word = "All" if senior_ent <= 1e-6 else "Part"
        return (
            f"{opening} {share_word} of your water right is junior-priority, and this "
            f"tier cuts your junior-priority water by about {junior_fraction:.0%}. The "
            "rest of your delivery is reduced only if Lake Mead cannot supply all "
            "Lower Basin withdrawals this year."
        )
    if junior_fraction > 0 and junior_entitlement_af is not None and junior_entitlement_af > 1e-6:
        # Item 29f: junior-priority water held, none requested at the keep
        # request; an increase beyond the senior entitlement would be cut.
        senior_ent = env_context.get("lb_senior_entitlement_af")
        if senior_ent is None:
            raise ValueError(
                "build_water_situation_text: this agent holds junior-priority water "
                "but 'lb_senior_entitlement_af' is missing from env_context; refusing "
                "to state where its junior-priority part begins."
            )
        if senior_ent <= 1e-6:
            return (
                f"{opening} All of your water right is junior-priority: this tier would "
                f"cut any request by about {junior_fraction:.0%}. The rest of your "
                "delivery is reduced only if Lake Mead cannot supply all Lower Basin "
                "withdrawals this year."
            )
        return (
            f"{opening} Part of your water right is junior-priority: this tier would cut "
            f"any part of a request above {senior_ent:,.0f} acre-ft by about "
            f"{junior_fraction:.0%}. Up to that amount, your delivery is reduced only if "
            "Lake Mead cannot supply all Lower Basin withdrawals this year."
        )
    return (
        f"{opening} Your delivery is reduced only if Lake Mead cannot supply all "
        "Lower Basin withdrawals this year."
    )


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
    ``execute_skill`` will never execute. WP3 (spec 3.1) puts the same
    edge (``below_minimum_utilisation``) into the identity-rule menu
    filter of every profile, ``disabled`` included, so the omission here
    and the menu filter agree; the omission stays this function's own
    contract, independent of which profile is running. The water-right cap has no matching omission
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


# The lines after the options (spec 2.6 and PI item 23), shown only when they
# apply (spec item 29e, refined by the coordinator on 2026-09-30): the
# random-step line names only the directions the menu offers, and the item-23
# sentence appears only when an increase is offered and last year's delivery
# was below the request.
OPTION_STEP_NOTE = "The exact size of an increase or a decrease is drawn at random around your typical step."
INCREASE_STEP_NOTE = "The exact size of an increase is drawn at random around your typical step."
DECREASE_STEP_NOTE = "The exact size of a decrease is drawn at random around your typical step."
KEEP_ASKS_RECEIVED_NOTE = (
    "If you received less than you requested last year, keeping your request asks only "
    "for the amount you received; an increase is the only option that asks for more."
)


def build_option_notes(increase_offered: bool, decrease_offered: bool,
                       last_year: Optional[Dict[str, Any]]) -> str:
    """``{option_notes}``, the text right after ``{options_text}`` (spec 2.6,
    item 23, item 29e).

    The random-step line names only the directions the menu offers: both
    (OPTION_STEP_NOTE), an increase only (INCREASE_STEP_NOTE, an agent at
    its minimum-use floor, whose decrease the identity rule hides) or a
    decrease only (DECREASE_STEP_NOTE, an agent at its water right, whose
    increase the identity rule hides); no line when neither is offered.
    KEEP_ASKS_RECEIVED_NOTE follows only when an increase is offered and last
    year's delivery was below its request (``last_year`` is the snapshot
    ``IrrigationLifecycleHooks.post_year`` took; None in the first year,
    which has no last-year request). "Below" uses FULL_SUPPLY_RATIO, the
    edge at which the memory line says "Demand fully met." Each line starts
    with a newline, so an empty result leaves the template unchanged."""
    lines = []
    if increase_offered and decrease_offered:
        lines.append(OPTION_STEP_NOTE)
    elif increase_offered:
        lines.append(INCREASE_STEP_NOTE)
    elif decrease_offered:
        lines.append(DECREASE_STEP_NOTE)
    if increase_offered and last_year is not None and supply_ratio(
            float(last_year["diversion"]), float(last_year["request"])) < FULL_SUPPLY_RATIO:
        lines.append(KEEP_ASKS_RECEIVED_NOTE)
    return "".join("\n" + line for line in lines)


def _build_trend_text(basin: str, preceding_factor: int, subbasin: bool = True) -> str:
    """The water-information sentence that ends a memory line (spec 4.5).

    Upper Basin: the agent's own sub-basin winter precipitation flag
    (H&Y's strict ">", spec 1.6); a synthetic mock agent without a
    sub-basin (``subbasin=False``) reads the basin-level legacy value,
    named as such. Lower Basin: Lake Mead's 1 January level against the
    year before (F15: the Lower Basin has no precipitation signal).
    """
    if basin == "upper_basin":
        where = "in your sub-basin" if subbasin else "in the Upper Basin"
        return (f"That winter's precipitation {where} was "
                f"{'above' if preceding_factor else 'below'} the previous winter's.")
    if basin == "lower_basin":
        return (f"On 1 January that year Lake Mead was "
                f"{'higher' if preceding_factor else 'lower'} than a year earlier.")
    # WP4 dropped build_action_outcome_feedback's drought_index argument; a
    # caller still passing it by position shifts preceding_factor into basin.
    raise ValueError(
        f"_build_trend_text: basin {basin!r} is neither 'upper_basin' nor 'lower_basin'."
    )


def dashboard_sharing_flags(agent_state: Dict[str, Any]) -> Dict[str, float]:
    """0/1 flags that pick the feedback-dashboard warning naming who shares a
    shortage (spec 4.6), decided from the settled ``gap_reason`` the way the
    supply rule's sharing sentence decides it
    (``validators/irrigation_validators.py (_sharing_sentence)``): the tier's
    cut of the agent's own junior-priority water; Lake Mead's availability
    (other Lower Basin users), split by whether the agent holds any
    junior-priority water (spec item 29f: for such an agent a declared
    shortage DOES cut the part of a request above its senior entitlement, so
    its warning cannot say a declared shortage never reduces its delivery);
    the agent's own sub-basin (other users in it, or nobody for the only
    member); the basin-wide Upper Basin backstop (other Upper Basin users).
    At most one flag is 1; all are 0 in a year with no shortfall. Numbers,
    not strings, because the dashboard's assertion evaluator compares numbers
    only; ``display: false`` in the YAML keeps them out of the table.

    A Lower Basin ``agent_state`` must carry ``lb_junior_entitlement_af``
    (``get_agent_context``; None for an agent outside the priority table,
    which the environment treats as fully senior).
    """
    flags = {
        "shortage_junior": 0.0,
        "shortage_lower_basin": 0.0,
        "shortage_lower_basin_junior_holder": 0.0,
        "shortage_subbasin": 0.0,
        "shortage_alone": 0.0,
        "shortage_upper_basin": 0.0,
    }
    codes = set(str(agent_state.get("gap_reason") or "none").split("+"))
    basin = agent_state.get("basin")
    if basin == "lower_basin":
        if "lb_junior_entitlement_af" not in agent_state:
            raise ValueError(
                "dashboard_sharing_flags: a Lower Basin agent_state lacks "
                "lb_junior_entitlement_af; refusing to guess whether a declared "
                "shortage can cut this agent's water."
            )
        junior_ent = agent_state["lb_junior_entitlement_af"]
        if "lb_junior_tier_cut" in codes:
            flags["shortage_junior"] = 1.0
        elif "lb_mead_availability" in codes:
            holds_junior = junior_ent is not None and junior_ent > 1e-6
            flags["shortage_lower_basin_junior_holder" if holds_junior
                  else "shortage_lower_basin"] = 1.0
    elif basin == "upper_basin":
        if "ub_subbasin_supply" in codes:
            member_count = agent_state.get("ub_subbasin_member_count")
            if member_count is None:
                raise ValueError(
                    "dashboard_sharing_flags: gap_reason names ub_subbasin_supply "
                    "but ub_subbasin_member_count is missing; refusing to guess "
                    "who shares this shortage."
                )
            flags["shortage_alone" if member_count <= 1 else "shortage_subbasin"] = 1.0
        elif codes & {"ub_natural_flow", "ub_capacity"}:
            flags["shortage_upper_basin"] = 1.0
    else:
        raise ValueError(
            f"dashboard_sharing_flags: basin {basin!r} is neither 'upper_basin' "
            "nor 'lower_basin'."
        )
    return flags


# Plain-language label (with its article) for the first blocking rule in the
# neutral memory line of an overruled year. v3 (WP3, spec 3.6): exactly the
# five v3 rules -- the three feasibility rules (the supply rule and the two
# identity rules) and the two thinking rules (TR1, TR3). The registry
# backstop `precondition_violation` is not a sixth rule: it is the cap or the
# floor enforced a second time, and _precondition_violation_label names it
# by the direction of the blocked skill. Every entry of the retired rule set
# (curtailment_awareness, the old R1/R2/R4 and observed-scarcity rules, the
# zero-escape, consecutive-increase and zero-delivery checks) is gone.
_RULE_LABELS = {
    "supply_gap_block_increase": "the shortage-sharing rule",
    "water_right_cap": "the water-right cap",
    "minimum_utilisation_floor": "the minimum-use floor",
    "high_scarcity_no_increase": "the rule on increases under scarcity",
    "low_scarcity_no_decrease": "the rule on decreases without scarcity",
}


def _precondition_violation_label(rule_id: str, proposed_skill: str) -> str:
    """Disambiguate the generic ``precondition_violation`` rule id (any
    registry ``preconditions:`` failure, ``broker/core/skill_broker_engine.py``)
    by the DIRECTION of the proposed skill it was raised against (WP2, spec
    2.2): an increase can only have failed ``not at_allocation_cap`` (the
    water-right cap); a decrease can only have failed ``not
    below_minimum_utilisation`` (the minimum-use floor) -- the registry's
    only two preconditions, one per direction. Any other rule id is looked
    up in ``_RULE_LABELS``; an id that is not there (or a
    ``precondition_violation`` raised against a skill of neither direction,
    which the registry cannot produce) reads "a governance rule"."""
    if rule_id == "precondition_violation":
        if proposed_skill.startswith("increase"):
            return _RULE_LABELS["water_right_cap"]
        if proposed_skill.startswith("decrease"):
            return _RULE_LABELS["minimum_utilisation_floor"]
    return _RULE_LABELS.get(rule_id, "a governance rule")


def build_action_outcome_feedback(
    action_ctx: Optional[Dict[str, Any]],
    year: int,
    request: float,
    diversion: float,
    preceding_factor: int,
    basin: str = "upper_basin",
    gap_reason: str = "",
    rejection_line_style: str = "explicit",
    name_rule: bool = True,
    subbasin: bool = True,
) -> str:
    """One memory line for one past year (spec 4.5):

    "Year {Y}: You chose to {increase demand | maintain demand | decrease
    demand}{ (by N%)}. You requested R acre-ft and received D acre-ft.
    {Demand fully met. | Shortfall: x acre-ft (p% unmet), because {past
    reason}.} {water-information sentence}"

    ``year`` is the calendar year. "Demand fully met." when D / R is at or
    above FULL_SUPPLY_RATIO (the share format of spec 4.3); otherwise the
    unmet share with one decimal and ``gap_reason``, the past-tense
    ``describe_gap_reason`` phrase. N% is the realised change as a share
    of the base (``action_ctx["magnitude_pct"]``). No drought index.

    An overruled year (retries exhausted, the default applied) under
    ``rejection_line_style="neutral"`` reads "Year {Y}: maintain demand was
    applied under {label}." with the rule label of spec 3.6 when
    ``name_rule`` is True (strict, feasibility-only), or "under a governance
    rule" when False (placebo and silent, whose retries name no rule; L3
    M13). ``explicit`` is the pre-redesign ablation wording.
    ``subbasin``: an Upper Basin agent with a real sub-basin (False only for
    a synthetic mock agent).
    """
    share = supply_ratio(diversion, request)
    if share >= FULL_SUPPLY_RATIO:
        shortfall = "Demand fully met."
    else:
        gap = max(0.0, request - diversion)
        shortfall = _with_reason(
            f"Shortfall: {gap:,.0f} acre-ft ({(1.0 - share) * 100.0:.1f}% unmet)",
            gap_reason) + "."

    outcome = (
        f"You requested {request:,.0f} acre-ft and received "
        f"{diversion:,.0f} acre-ft. {shortfall} "
        f"{_build_trend_text(basin, preceding_factor, subbasin)}"
    )

    # Action portion (from _last_action_context stored by framework)
    if action_ctx and action_ctx.get("skill_name"):
        skill = action_ctx["skill_name"].replace("_", " ")
        if action_ctx.get("was_fallback") and rejection_line_style == "neutral":
            # Neutral style (memory.rejection_line_style): names the rule and
            # the action that was applied, not the rejected proposal.
            rules = action_ctx.get("blocking_rules") or []
            proposed_skill_for_label = action_ctx.get("proposed_skill")
            if proposed_skill_for_label and rules and name_rule:
                label = _precondition_violation_label(rules[0], proposed_skill_for_label)
                lead = f"Year {year}: {skill} was applied under {label}"
            elif proposed_skill_for_label:
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
