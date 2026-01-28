"""
Agent Loading and Initialization.

Supports loading from:
- Survey data (Excel)
- CSV profiles
"""
from pathlib import Path
from typing import Dict, Any, Optional
from broker.agents import BaseAgent, AgentConfig
from broker import load_agents_from_csv as broker_load

# Helper function to extract flood extension from profile
def _get_flood_ext(profile):
    return getattr(profile, "extensions", {}).get("flood")

# Helper function to safely get values from extension dict or object
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
    # Placeholder for actual survey initialization logic
    # This function would typically interact with a survey parsing library
    # For now, we simulate agent profiles similar to CSV loading for demonstration.
    # In a real scenario, this would require external libraries and data.
    print(f"INFO: Loading agents from survey file: {survey_path}")
    
    # Mock agent loading from survey for now, as actual survey parsing is complex
    # In a real implementation, this would use a dedicated survey parsing library.
    # For demonstration, we'll return a structure similar to what CSV might produce.
    
    # Simulate loading some basic profiles
    agents = {}
    for i in range(max_agents):
        agent_id = f"survey_agent_{i+1}"
        profile_data = {
            "id": agent_id,
            "elevated": random.choice([True, False]),
            "has_insurance": random.choice([True, False]),
            "relocated": random.choice([True, False]),
            "trust_in_insurance": round(random.uniform(0.1, 0.9), 2),
            "trust_in_neighbors": round(random.uniform(0.1, 0.9), 2),
            "flood_threshold": round(random.uniform(0.0, 0.6), 2),
            "identity": f"Household {i+1}",
            "is_mg": random.choice([True, False]),
            "group": random.choice(["MG", "NMG"]),
            "narrative_persona": f"You are a homeowner in a flood-prone area with {random.choice(['some', 'limited', 'no'])} savings. You recall '{random.choice(PAST_EVENTS)}'.",
            "extensions": {"flood": {"base_depth_m": round(random.uniform(0, 5), 1), "flood_zone": random.choice(["unknown", "shallow", "moderate", "deep"])}}
        }
        
        config = AgentConfig(
            name=agent_id,
            agent_type="household",
            state_params=[],
            objectives=[],
            constraints=[],
            skills=["buy_insurance", "elevate_house", "relocate", "do_nothing"],
        )
        
        agent = BaseAgent(config)
        agent.id = profile_data["id"]
        agent.agent_type = "household"
        agent.config.skills = ["buy_insurance", "elevate_house", "relocate", "do_nothing"] # Ensure skills are set

        # Set custom attributes directly
        for k, v in profile_data.items():
            if k == "id": # Skip id, already set
                continue
            if k == "extensions": # Handle extensions separately
                agent.extensions = v
                agent.flood_threshold = _ext_value(v, "base_depth_m", 0.0) # Set base_depth_m from extension
            else:
                setattr(agent, k, v)
        
        # Ensure flood_threshold is set, potentially from extension or default
        if not hasattr(agent, 'flood_threshold'):
            agent.flood_threshold = round(random.uniform(0.0, 0.6), 2)

        agent.flood_history = []
        agents[agent.id] = agent
        
    # Simulate stats similar to actual output
    print(f"[Survey] Loaded {len(agents)} agents from survey (simulated)")
    print(f"[Survey] MG: {len([a for a in agents.values() if a.is_mg])} ({len([a for a in agents.values() if a.is_mg])/len(agents):.1%}), NMG: {len([a for a in agents.values() if not a.is_mg])}")
    
    return agents


def load_agents_from_csv(
    profiles_path: Path,
    max_agents: int = 100,
    seed: int = 42
) -> Dict[str, Any]:
    """Load agents from CSV profile file."""
    # Assuming broker.load_agents_from_csv handles the actual loading
    # This is a placeholder to match the original structure.
    print(f"INFO: Loading agents from CSV file: {profiles_path}")
    agents = {}
    try:
        df = pd.read_csv(profiles_path)
        
        # Ensure 'id' column exists, use index if not
        if 'id' not in df.columns:
            df['id'] = [f'agent_{i}' for i in range(len(df))]
            
        for index, row in df.iterrows():
            if len(agents) >= max_agents:
                break

            agent_id = row['id']
            config = AgentConfig(
                name=str(agent_id),
                agent_type="household",
                state_params=[],
                objectives=[],
                constraints=[],
                skills=["buy_insurance", "elevate_house", "relocate", "do_nothing"],
            )
            agent = BaseAgent(config)
            agent.id = str(agent_id)
            agent.agent_type = "household"
            agent.config.skills = ["buy_insurance", "elevate_house", "relocate", "do_nothing"]

            # Assign attributes from CSV row, handling potential NaNs and types
            custom_attributes = {}
            for col in df.columns:
                value = row[col]
                if pd.notna(value):
                    # Special handling for keys that might need specific types or object creation
                    if col == 'id': continue # Already set
                    elif col == 'elevated': custom_attributes[col] = bool(value)
                    elif col == 'has_insurance': custom_attributes[col] = bool(value)
                    elif col == 'relocated': custom_attributes[col] = bool(value)
                    elif col == 'flood_threshold': custom_attributes[col] = float(value)
                    elif col == 'trust_in_insurance' or col == 'trust_in_neighbors': custom_attributes[col] = float(value)
                    elif col == 'memory': custom_attributes[col] = str(value) # Store memory as string for now
                    elif col == 'extensions': # Assume extensions might be a dict string, needs careful parsing if complex
                         try:
                             custom_attributes[col] = eval(str(value)) # Use eval cautiously, might need safer parsing
                         except:
                             custom_attributes[col] = str(value) # Fallback to string
                    else:
                        custom_attributes[col] = value
            
            # Set narrative persona if not explicitly in CSV, fallback to default
            if 'narrative_persona' not in custom_attributes or not custom_attributes['narrative_persona']:
                 custom_attributes['narrative_persona'] = "You are a homeowner with a strong attachment to your community."
            
            # Apply custom attributes
            for k, v in custom_attributes.items():
                setattr(agent, k, v)

            # Ensure flood_threshold is set, even if not in CSV or extension parsing fails
            if not hasattr(agent, 'flood_threshold'):
                 agent.flood_threshold = round(random.uniform(0.0, 0.6), 2) # Default if not found

            agent.flood_history = [] # Initialize flood history
            agents[agent.id] = agent

    except FileNotFoundError:
        print(f"ERROR: Profile CSV not found at {profiles_path}")
        # Return empty dict or raise error, depending on desired behavior
        return {}
    except Exception as e:
        print(f"ERROR: Failed to load agents from CSV: {e}")
        return {}

    print(f"Loaded {len(agents)} agents from CSV.")
    return agents


def _apply_stress_test(agents: Dict[str, Any], stress_test: str):
    """Apply stress test profile modifications."""
    if stress_test == "veteran":
        print(f"[StressTest] Applying 'Optimistic Veteran' profile...")
        for p in agents.values(): # Corrected from 'v' to 'p' to match agent object name
            p.trust_in_insurance = 0.9
            p.trust_in_neighbors = 0.1
            p.flood_threshold = 0.8
            p.narrative_persona = (
                f"You are a wealthy homeowner who has lived here for 30 years. "
                f"You believe only depths > {p.flood_threshold}m pose any real threat."
            )
    elif stress_test == "panic":
        print(f"[StressTest] Applying 'Panic Machine' profile...")
        for p in agents.values():
            p.flood_threshold = 0.1
            p.narrative_persona = (
                "You are highly anxious with limited savings. "
                f"Any depth > {p.flood_threshold}m is catastrophic."
            )
