"""
Agent Loading and Initialization.

Supports loading from:
- Survey data (Excel)
- CSV profiles
"""
from pathlib import Path
from typing import Dict, Any, Optional


def _get_flood_ext(profile):
    return getattr(profile, "extensions", {}).get("flood")


def _ext_value(ext, key, default=None):
    if ext is None:
        return default
    if isinstance(ext, dict):
        return ext.get(key, default)
    return getattr(ext, key, default)


def load_agents_from_survey(
    survey_path: Path,
    max_agents: int = 100,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Load agents from real survey data.

    Uses the survey module to:
    1. Parse Excel survey data
    2. Classify MG/NMG status
    3. Assign flood zones
    4. Generate RCV values
    """
    from broker.modules.survey.agent_initializer import initialize_agents_from_survey
    from cognitive_governance.agents import BaseAgent, AgentConfig

    profiles, stats = initialize_agents_from_survey(
        survey_path=survey_path,
        max_agents=max_agents,
        seed=seed,
        include_hazard=True,
        include_rcv=True
    )

    print(f"[Survey] Loaded {stats['total_agents']} agents from survey")
    print(f"[Survey] MG: {stats['mg_count']} ({stats['mg_ratio']:.1%}), NMG: {stats['nmg_count']}")

    agents = {}
    for profile in profiles:
        config = AgentConfig(
            name=profile.agent_id,
            agent_type="household",
            state_params=[],
            objectives=[],
            constraints=[],
            skills=[],
        )

        flood_ext = _get_flood_ext(profile)
        base_depth = _ext_value(flood_ext, "base_depth_m", 0.0)
        flood_zone = _ext_value(flood_ext, "flood_zone", "unknown")

        base_threshold = 0.3 if base_depth > 0 else 0.1
        if flood_zone in ("deep", "very_deep", "extreme"):
            base_threshold = 0.5
        elif flood_zone == "moderate":
            base_threshold = 0.4
        elif flood_zone == "shallow":
            base_threshold = 0.3

        agent = BaseAgent(config)
        agent.id = profile.agent_id
        agent.agent_type = "household"
        agent.config.skills = ["buy_insurance", "elevate_house", "relocate", "do_nothing"]

        agent.custom_attributes = {
            "elevated": False,
            "has_insurance": False,
            "relocated": False,
            "trust_in_insurance": 0.5,
            "trust_in_neighbors": 0.5,
            "flood_threshold": base_threshold,
            "identity": profile.identity,
            "is_mg": profile.is_mg,
            "group": profile.group_label,
            "narrative_persona": profile.generate_narrative_persona() or "You are a homeowner with a strong attachment to your community.",
        }

        for k, v in agent.custom_attributes.items():
            setattr(agent, k, v)

        agent.flood_history = []
        agents[agent.id] = agent

    return agents


def load_agents_from_csv(
    profiles_path: Path,
    stress_test: Optional[str] = None
) -> Dict[str, Any]:
    """Load agents from CSV profile file."""
    from broker import load_agents_from_csv as broker_load

    agents = broker_load(str(profiles_path), {
        "id": "id", "elevated": "elevated", "has_insurance": "has_insurance",
        "relocated": "relocated", "trust_in_insurance": "trust_in_insurance",
        "trust_in_neighbors": "trust_in_neighbors", "flood_threshold": "flood_threshold",
        "memory": "memory"
    }, agent_type="household")

    for a in agents.values():
        a.flood_history = []
        a.config.skills = ["buy_insurance", "elevate_house", "relocate", "do_nothing"]
        for k, v in a.custom_attributes.items():
            if k not in ["id", "agent_type"]:
                setattr(a, k, v)

        if not hasattr(a, 'narrative_persona') or not a.narrative_persona:
            a.narrative_persona = "You are a homeowner with a strong attachment to your community."
            a.custom_attributes['narrative_persona'] = a.narrative_persona

    # Apply stress test profiles if specified
    if stress_test:
        _apply_stress_test(agents, stress_test)

    return agents


def _apply_stress_test(agents: Dict[str, Any], stress_test: str):
    """Apply stress test profile modifications."""
    if stress_test == "veteran":
        print(f"[StressTest] Applying 'Optimistic Veteran' profile...")
        for v in agents.values():
            v.trust_in_insurance = 0.9
            v.trust_in_neighbors = 0.1
            v.flood_threshold = 0.8
            v.narrative_persona = (
                f"You are a wealthy homeowner who has lived here for 30 years. "
                f"You believe only depths > {v.flood_threshold}m pose any real threat."
            )
    elif stress_test == "panic":
        print(f"[StressTest] Applying 'Panic Machine' profile...")
        for p in agents.values():
            p.flood_threshold = 0.1
            p.narrative_persona = (
                "You are highly anxious with limited savings. "
                f"Any depth > {p.flood_threshold}m is catastrophic."
            )
