import pandas as pd
from typing import Dict, Any, List, Optional
from cognitive_governance.agents import BaseAgent, AgentConfig, StateParam

def load_agents_from_csv(
    csv_path: str,
    mapping: Dict[str, str],
    agent_type: str,
    base_config: Optional[AgentConfig] = None
) -> Dict[str, BaseAgent]:
    """
    Loads agents from a CSV file using a column mapping.

    Args:
        csv_path: Path to the CSV file.
        mapping: Dictionary mapping CSV column names to agent attributes.
                 e.g. {"HH_ID": "id", "Income_Level": "income"}
        agent_type: Type label for the agents (e.g., "household", "trader").
                    Required - must match a type defined in agent_types.yaml.
        base_config: Optional Base config to use for all agents.

    Returns:
        Dict of agent_id -> BaseAgent
    """
    df = pd.read_csv(csv_path)
    agents = {}
    
    # Default config if none provided
    if not base_config:
        base_config = AgentConfig(
            name="Generic",
            agent_type=agent_type,
            state_params=[],
            objectives=[],
            constraints=[],
            skills=[]
        )
    
    for _, row in df.iterrows():
        # 1. Determine ID
        id_col = next((csv_col for csv_col, attr in mapping.items() if attr == "id"), None)
        agent_id = str(row[id_col]) if id_col else f"{agent_type}_{_}"
        
        # 2. Create Config for this specific agent (to keep name/id consistent)
        config = AgentConfig(
            name=agent_id,
            agent_type=agent_type,
            state_params=base_config.state_params,
            objectives=base_config.objectives,
            constraints=base_config.constraints,
            skills=base_config.skills,
            persona=base_config.persona,
            role_description=base_config.role_description
        )
        
        agent = BaseAgent(config)
        # agent.id is derived from config.name and is read-only
        
        # 3. Populate Custom Attributes from Mapping
        for csv_col, attr_name in mapping.items():
            if attr_name == "id":
                continue
            if csv_col in row:
                # Handle memory specifically to allow list-based initialization
                if attr_name == "memory":
                    val = row[csv_col]
                    if pd.notna(val) and isinstance(val, str):
                        agent.memory = [m.strip() for m in val.split('|')]
                    else:
                        agent.memory = []
                else:
                    agent.custom_attributes[attr_name] = row[csv_col]
        
        agents[agent_id] = agent
        
    return agents
