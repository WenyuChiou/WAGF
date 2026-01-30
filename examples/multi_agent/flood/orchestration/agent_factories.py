from cognitive_governance.agents import BaseAgent, AgentConfig, StateParam, Skill, PerceptionSource
from generate_agents import HouseholdProfile


def create_government_agent() -> BaseAgent:
    config = AgentConfig(
        name="NJ_STATE",
        agent_type="government",
        state_params=[
            StateParam("subsidy_rate", (0.2, 0.95), 0.50, "Adaptation subsidy %"),
            StateParam("budget_remaining", (0, 1_000_000), 500_000, "Annual grant budget")
        ],
        objectives=[],
        constraints=[],
        skills=[
            Skill("increase_subsidy", "Raise subsidy rate", "subsidy_rate", "increase"),
            Skill("decrease_subsidy", "Lower subsidy rate", "subsidy_rate", "decrease"),
            Skill("maintain_subsidy", "Keep current rate", None, "none")
        ],
        perception=[
            PerceptionSource("environment", "env", ["year", "flood_occurred"])
        ],
        role_description=(
            "You represent the NJ State Government. Your goal is to support household adaptation while managing budget."
        )
    )
    return BaseAgent(config)


def create_insurance_agent() -> BaseAgent:
    config = AgentConfig(
        name="FEMA_NFIP",
        agent_type="insurance",
        state_params=[
            StateParam("premium_rate", (0.01, 0.15), 0.02, "Flood insurance premium %"),
            StateParam("loss_ratio", (0, 2.0), 0.0, "Claims / Premiums ratio")
        ],
        objectives=[],
        constraints=[],
        skills=[
            Skill("raise_premium", "Increase premiums", "premium_rate", "increase"),
            Skill("lower_premium", "Decrease premiums", "premium_rate", "decrease"),
            Skill("maintain_premium", "Keep current rate", None, "none")
        ],
        perception=[
            PerceptionSource("environment", "env", ["year", "flood_occurred"])
        ],
        role_description=(
            "You represent FEMA/NFIP. Your goal is to maintain program solvency (RR 2.0)."
        )
    )
    return BaseAgent(config)


def pmt_score_to_rating(score: float) -> str:
    """Convert PMT score (1-5) to descriptive rating."""
    if score >= 4.0:
        return "High"
    if score >= 3.0:
        return "Moderate"
    if score >= 2.0:
        return "Low"
    return "Very Low"


def wrap_household(profile: HouseholdProfile) -> BaseAgent:
    """Wrap HouseholdProfile as BaseAgent compatible with the framework."""
    ma_type = "household_owner" if profile.tenure == "Owner" else "household_renter"

    config = AgentConfig(
        name=profile.agent_id,
        agent_type=ma_type,
        state_params=[],
        objectives=[],
        constraints=[],
        skills=[],
        perception=[
            PerceptionSource("environment", "env", ["year", "flood_occurred", "subsidy_rate", "premium_rate"])
        ]
    )
    agent = BaseAgent(config)

    agent.fixed_attributes = {
        "survey_id": profile.survey_id,
        "mg": profile.mg,
        "mg_criteria_met": profile.mg_criteria_met,
        "tenure": profile.tenure,
        "income": profile.income,
        "income_bracket": profile.income_bracket,
        "rcv_building": profile.rcv_building,
        "rcv_contents": profile.rcv_contents,
        "property_value": profile.rcv_building + profile.rcv_contents,
        "household_size": profile.household_size,
        "generations": profile.generations,
        "zipcode": profile.zipcode,
        "has_vehicle": profile.has_vehicle,
        "has_children": profile.has_children,
        "has_elderly": profile.has_elderly,
        "housing_cost_burden": profile.housing_cost_burden,
        "sfha_awareness": profile.sfha_awareness,
        "flood_zone": profile.flood_zone,
        "flood_depth": profile.flood_depth,
        "grid_x": profile.grid_x,
        "grid_y": profile.grid_y,
        "flood_experience": profile.flood_experience,
        "flood_frequency": profile.flood_frequency,
        "recent_flood_text": profile.recent_flood_text,
        "insurance_type": profile.insurance_type,
        "post_flood_action": profile.post_flood_action,
        # PMT constructs (Task-060C: SC/PA as trust indicators)
        "sc_score": profile.sc_score,
        "pa_score": profile.pa_score,
        "tp_score": profile.tp_score,
        "cp_score": profile.cp_score,
        "sp_score": profile.sp_score,
    }
    # Derive trust indicators from SC/PA (Task-060C)
    sc_norm = min(1.0, profile.sc_score / 5.0)
    pa_norm = min(1.0, profile.pa_score / 5.0)
    ins_factor = 1.2 if profile.has_insurance else 0.8
    trust_neighbors = round(sc_norm, 3)
    trust_insurance = round(min(1.0, sc_norm * ins_factor), 3)
    community_rootedness = round(pa_norm, 3)

    agent.dynamic_state = {
        "elevated": profile.elevated,
        "has_insurance": profile.has_insurance,
        "relocated": False,
        "cumulative_damage": 0.0,
        "elevation_status_text": ("Your house is elevated." if profile.elevated else "Your house is NOT elevated."),
        "insurance_status": ("have" if profile.has_insurance else "do NOT have"),
        "flood_experience_summary": (
            f"Experienced {profile.flood_frequency} flood event(s)" if profile.flood_experience else "No direct flood experience"
        ),
        # Trust indicators derived from SC/PA (Task-060C)
        "trust_in_neighbors": trust_neighbors,
        "trust_in_insurance": trust_insurance,
        "community_rootedness": community_rootedness,
    }

    agent.id = profile.agent_id
    return agent
