"""
Irrigation agent persona builder.

Generates narrative personas and context strings for LLM prompt injection,
analogous to the flood experiment's memory_templates.py.  Personas are
derived from the three FQL behavioral clusters (Hung & Yang 2021).

Each agent receives:
- A narrative persona describing their farming personality/style
- Water situation text describing current conditions
- Conservation status and trust levels
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


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

    # Magnitude parameters (v12: code-based Gaussian sampling)
    magnitude_default: float = 10.0  # Mean of Gaussian distribution (%)
    magnitude_sigma: float = 0.0     # Standard deviation for stochasticity
    magnitude_min: float = 1.0       # Lower bound for clipping
    magnitude_max: float = 30.0      # Upper bound for clipping

    # Narrative (generated)
    narrative_persona: str = ""
    water_situation_summary: str = ""


# ============================================================================
# Cluster-based persona templates
# ============================================================================

_CLUSTER_PERSONAS = {
    "aggressive": [
        (
            "You are {agent_id}, a decisive farmer in the {basin_name} of the "
            "Colorado River Basin. You manage {farm_size} acres of {crop_type} "
            "crops and have been farming for {years} years. You are known in your "
            "irrigation district for making bold, quick adjustments to your water "
            "orders. When water conditions change, you act immediately — sometimes "
            "requesting significantly more water when you sense an opportunity, and "
            "cutting back sharply when you detect shortages ahead. You would rather "
            "overshoot your water request and face a small penalty than be too "
            "cautious and miss a productive season. Your neighbors consider you "
            "aggressive but effective. "
            "With your large operation and established water rights, you feel "
            "confident in your ability to adapt your water use when needed."
        ),
        (
            "You are {agent_id}, an action-oriented farmer managing {farm_size} "
            "acres in the {basin_name}. With {years} years of experience growing "
            "{crop_type}, you have learned that waiting too long to adjust water "
            "demand can be costly. You respond swiftly to changes in precipitation "
            "patterns and river conditions. Your philosophy: it's better to request "
            "too much water and have some returned than to request too little and "
            "watch your crops suffer. You aren't particularly worried about unmet "
            "demand penalties — you focus on maximising your yield. "
            "Your sizeable water allocation and operational flexibility give you "
            "strong capacity to adapt to changing conditions."
        ),
    ],
    "forward_looking_conservative": [
        (
            "You are {agent_id}, a thoughtful and cautious farmer in the "
            "{basin_name}. You carefully manage {farm_size} acres of {crop_type} "
            "and have {years} years of experience. You believe in steady, measured "
            "adjustments to water demand — never making dramatic changes. You learn "
            "quickly from each season's outcomes and always think about the long "
            "term. The thought of facing a water shortage deeply concerns you; "
            "you would rather use a little less water than risk a curtailment "
            "penalty. You read climate forecasts carefully and consult with "
            "neighboring farmers before making decisions. "
            "Your careful planning and willingness to invest in efficient systems "
            "give you moderate-to-good ability to adapt your water use."
        ),
        (
            "You are {agent_id}, managing {farm_size} acres of {crop_type} in the "
            "{basin_name} for {years} years. You are known as a careful planner. "
            "You adjust your water request only after thoroughly considering the "
            "evidence — precipitation data, Lake Mead levels, and your own past "
            "experience. You are willing to experiment with new approaches but "
            "always in small, measured steps. Running short of water is your "
            "worst-case scenario; you hate the idea of crops suffering from "
            "inadequate irrigation. You keep detailed records and plan ahead. "
            "Your proactive planning and openness to efficiency improvements "
            "provide you reasonable capacity to adapt when conditions change."
        ),
    ],
    "myopic_conservative": [
        (
            "You are {agent_id}, a tradition-oriented farmer in the {basin_name}. "
            "Your family has farmed {farm_size} acres of {crop_type} for "
            "generations — you've been at it for {years} years yourself. You "
            "believe strongly in following the practices that have worked before. "
            "Why change what isn't broken? You make only minor adjustments to your "
            "water demand from year to year. You are sceptical of forecasts and "
            "new technologies. You rarely try completely new strategies, preferring "
            "to rely on your own accumulated knowledge and the patterns you've "
            "observed over decades of farming. "
            "Your smaller operation and limited technology investment constrain "
            "your options for adapting water use if conditions deteriorate."
        ),
        (
            "You are {agent_id}, managing {farm_size} acres of {crop_type} in the "
            "{basin_name}. You have {years} years of experience, and you trust "
            "that experience above all else. You see other farmers making dramatic "
            "changes to their water orders and think they're overreacting. You "
            "adjust your demand only slightly each year — steady as she goes. "
            "You're moderately concerned about water shortages but believe that "
            "staying the course has served you well so far. New ideas need to "
            "prove themselves elsewhere before you'll try them on your farm. "
            "Your reliance on traditional methods and limited resources make it "
            "harder for you to adapt your water practices under pressure."
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
        farm_size=int(profile.farm_size_acres),
        crop_type=profile.crop_type,
        years=profile.years_farming,
    )


def build_water_situation_text(
    env_context: Dict[str, Any],
) -> str:
    """Generate water situation text from environment context.

    This is injected into the prompt as ``{water_situation_text}``.
    """
    year = env_context.get("year", "unknown")
    basin = env_context.get("basin", "unknown")
    drought = env_context.get("drought_index", 0)
    precip = env_context.get("precipitation", 0)
    mead = env_context.get("lake_mead_level", 0)
    curtailment = env_context.get("curtailment_ratio", 0)
    shortage_tier = env_context.get("shortage_tier", 0)
    current_div = env_context.get("current_diversion", 0)
    water_right = env_context.get("water_right", 0)

    basin_display = _BASIN_DISPLAY.get(basin, basin)

    lines = [f"It is now the year {year}. You farm in the {basin_display}."]

    # Drought signal
    if drought < 0.2:
        lines.append("Water conditions are normal this year — no drought concerns.")
    elif drought < 0.5:
        lines.append("Mild drought conditions exist — water availability is slightly below normal.")
    elif drought < 0.8:
        lines.append("Moderate drought conditions prevail — water supply is significantly reduced.")
    else:
        lines.append("Severe drought conditions — water supply is critically low.")

    # Basin-specific signal
    if basin == "upper_basin":
        lines.append(
            f"Winter precipitation in your region was {precip:.0f} mm "
            f"({'above' if env_context.get('preceding_factor', 0) else 'below'} last year)."
        )
    else:
        lines.append(
            f"Lake Mead water level is at {mead:.0f} feet above sea level "
            f"({'rising' if env_context.get('preceding_factor', 0) else 'declining'} from last year)."
        )

    # Curtailment
    if shortage_tier > 0:
        lines.append(
            f"The Bureau of Reclamation has declared Tier {shortage_tier} "
            f"shortage conditions. Your water allocation is curtailed by "
            f"{curtailment:.0%}."
        )
    else:
        lines.append("No shortage has been declared. Full allocation is available.")

    # Agent's current position
    utilisation = (current_div / water_right * 100) if water_right > 0 else 0
    lines.append(
        f"Your current water use is {current_div:,.0f} acre-ft/year out of "
        f"your water right of {water_right:,.0f} acre-ft/year "
        f"({utilisation:.0f}% utilisation)."
    )

    # NOTE: Supply-demand gap feedback is now handled by the generic
    # FeedbackDashboardProvider via YAML assertions in agent_types.yaml.
    # See broker/components/feedback_provider.py

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


def build_trust_text(cluster: str) -> Dict[str, str]:
    """Return trust level strings based on cluster persona.

    Aggressive agents trust forecasts less, myopic agents trust
    neighbors less, forward-looking agents are balanced.
    """
    trust_map = {
        "aggressive": {
            "trust_forecasts_text": "are sceptical of",
            "trust_neighbors_text": "occasionally listen to",
        },
        "forward_looking_conservative": {
            "trust_forecasts_text": "carefully consider",
            "trust_neighbors_text": "regularly consult",
        },
        "myopic_conservative": {
            "trust_forecasts_text": "generally distrust",
            "trust_neighbors_text": "seldom seek out",
        },
    }
    return trust_map.get(cluster, trust_map["myopic_conservative"])


def build_regret_feedback(
    year: int,
    request: float,
    diversion: float,
    drought_index: float,
    preceding_factor: int,
) -> str:
    """Build factual shortfall feedback for memory storage."""
    gap = max(0.0, request - diversion)
    gap_pct = (gap / request * 100.0) if request > 0 else 0.0
    precip_text = "above" if preceding_factor else "below"

    if gap > 0:
        shortfall = f"Shortfall: {gap:,.0f} acre-ft ({gap_pct:.0f}% unmet)."
    else:
        shortfall = "Demand fully met."

    return (
        f"Year {year}: You requested {request:,.0f} acre-ft and received "
        f"{diversion:,.0f} acre-ft. {shortfall} "
        f"Drought index: {drought_index:.2f}. Precipitation was {precip_text} last year."
    )


def build_action_outcome_feedback(
    action_ctx: Optional[Dict[str, Any]],
    year: int,
    request: float,
    diversion: float,
    drought_index: float,
    preceding_factor: int,
) -> str:
    """Build combined action + outcome feedback for memory.

    Extends build_regret_feedback by prepending the agent's action choice
    (and magnitude if applicable) so the agent can form causal links
    between decisions and outcomes during reflection.
    """
    # Outcome portion (same logic as build_regret_feedback)
    gap = max(0.0, request - diversion)
    gap_pct = (gap / request * 100.0) if request > 0 else 0.0
    precip_text = "above" if preceding_factor else "below"

    if gap > 0:
        shortfall = f"Shortfall: {gap:,.0f} acre-ft ({gap_pct:.0f}% unmet)."
    else:
        shortfall = "Demand fully met."

    outcome = (
        f"You requested {request:,.0f} acre-ft and received "
        f"{diversion:,.0f} acre-ft. {shortfall} "
        f"Drought index: {drought_index:.2f}. Precipitation was {precip_text} last year."
    )

    # Action portion (from _last_action_context stored by framework)
    if action_ctx and action_ctx.get("skill_name"):
        skill = action_ctx["skill_name"].replace("_", " ")
        parts = [f"Year {year}: You chose to {skill}"]
        mag = action_ctx.get("magnitude_pct")
        if mag is not None:
            parts.append(f"(by {mag:.0f}%)")
        return " ".join(parts) + ". " + outcome

    # Fallback: outcome-only (year 1 or missing context)
    return f"Year {year}: {outcome}"


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
    """Simple cluster inference based on Hung & Yang (2021) centroids.

    Uses Euclidean distance to the three canonical cluster centroids.
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
    for sg, count in zip(_UB_STATE_GROUPS, _UB_GROUP_AGENT_COUNTS):
        for agent in ub_agent_names[offset: offset + count]:
            mapping[agent] = sg
        offset += count
    return mapping


def create_profiles_from_data(
    params_csv_path: str,
    crss_db_dir: str,
    rng: Optional[np.random.Generator] = None,
) -> List[IrrigationAgentProfile]:
    """Create 78 individual agent profiles from paper data.

    Expands the 31-agent CSV to the full 78-agent CRSS resolution:
    - LB: 22 agents (1:1 match with CSV)
    - UB: 58 individual CRSS slots, each inheriting its state-group's
      FQL parameters.  Inactive agents (all-zero states) are skipped.

    Args:
        params_csv_path: Path to ALL_colorado_ABM_params_cal_1108.csv
        crss_db_dir: Path to ref/CRSS_DB/CRSS_DB/ directory
        rng: Random number generator for crop type and persona selection.

    Returns:
        List of ~78 IrrigationAgentProfile with real water_right values.
    """
    import os
    import pandas as pd

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

    # 4. Load historical 2018 actual diversions (Hung & Yang 2021 baseline)
    lb_hist_path = os.path.join(crss_db_dir, "HistoricalData", "LB_historical_annual_diversion.csv")
    ub_hist_path = os.path.join(crss_db_dir, "HistoricalData", "UB_historical_annual_depletion.csv")
    lb_2018, ub_2018 = None, None
    if os.path.isfile(lb_hist_path):
        lb_hist = pd.read_csv(lb_hist_path, index_col=0)
        lb_2018 = lb_hist.loc[2018] if 2018 in lb_hist.index else None
    if os.path.isfile(ub_hist_path):
        ub_hist = pd.read_csv(ub_hist_path, index_col=0)
        ub_2018 = ub_hist.loc[2018] * 1000 if 2018 in ub_hist.index else None  # thousands AF → AF

    # Pre-compute UB state-group water_right totals for proportional split
    ub_group_wr_totals: Dict[str, float] = {}
    for _name in ub_states.columns:
        _wr = float(ub_states[_name].iloc[-1])
        if _wr <= 0:
            continue
        _sg = ub_sg_map.get(_name)
        if _sg:
            ub_group_wr_totals[_sg] = ub_group_wr_totals.get(_sg, 0) + _wr

    profiles: List[IrrigationAgentProfile] = []

    # --- Lower Basin agents (22, direct CSV match) ---
    for agent_name in lb_states.columns:
        if agent_name not in params_df.columns:
            continue
        col = lb_states[agent_name]
        water_right = float(col.iloc[-1])
        if water_right <= 0:
            continue  # inactive

        p = params_df[agent_name]
        mu = float(p["mu"])
        sigma = float(p["sigma"])
        alpha = float(p["alpha"])
        gamma_p = float(p["gamma"])
        epsilon = float(p["epsilon"])
        regret_val = float(p["regret"])
        cluster = _infer_cluster(mu, sigma, alpha, regret_val)

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
        water_right = float(col.iloc[-1])
        if water_right <= 0:
            continue  # inactive

        # Look up state-group for FQL params
        state_group = ub_sg_map.get(agent_name)
        if state_group is None or state_group not in params_df.columns:
            continue

        p = params_df[state_group]
        mu = float(p["mu"])
        sigma = float(p["sigma"])
        alpha = float(p["alpha"])
        gamma_p = float(p["gamma"])
        epsilon = float(p["epsilon"])
        regret_val = float(p["regret"])
        cluster = _infer_cluster(mu, sigma, alpha, regret_val)

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
            crop_type=_assign_crop_type("upper_basin", rng),
            years_farming=int(rng.integers(5, 40)),
        )
        if ub_2018 is not None and state_group in ub_2018.index:
            group_total = ub_group_wr_totals.get(state_group, 1)
            if group_total > 0:
                profile.actual_2018_diversion = float(ub_2018[state_group]) * (water_right / group_total)
        profile.narrative_persona = build_narrative_persona(profile, rng)
        profiles.append(profile)

    return profiles
