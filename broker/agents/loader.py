"""
YAML Configuration Loader for Base Agents

Allows users to define any agent type via YAML configuration.

Task-037: Migrated from agents/loader.py to SDK
"""

import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from .base import (
    AgentConfig,
    BaseAgent,
    StateParam,
    Objective,
    Constraint,
    PerceptionSource,
    Skill
)


def load_agent_configs(yaml_path: str) -> List[AgentConfig]:
    """
    Load institutional agent configurations from YAML file.

    Args:
        yaml_path: Path to YAML config file

    Returns:
        List of AgentConfig objects
    """
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    configs = []

    for agent_def in data.get("agents", []):
        # Parse state params
        state_params = [
            StateParam(
                name=s["name"],
                raw_range=tuple(s.get("raw_range", [0, 1])),
                initial_raw=s.get("initial", 0.5),
                description=s.get("description", "")
            )
            for s in agent_def.get("state", [])
        ]

        # Parse objectives
        objectives = [
            Objective(
                name=o["name"],
                param=o["param"],
                target=tuple(o.get("target", [0.4, 0.6])),
                weight=o.get("weight", 0.5),
                literature=o.get("literature", "")
            )
            for o in agent_def.get("objectives", [])
        ]

        # Parse constraints
        constraints = [
            Constraint(
                name=c["name"],
                param=c["param"],
                max_change=c.get("max_change", 0.15),
                bounds=tuple(c.get("bounds", [0, 1])),
                literature=c.get("literature", "")
            )
            for c in agent_def.get("constraints", [])
        ]

        # Parse perception
        perception = [
            PerceptionSource(
                source_type=p.get("type", "environment"),
                source_name=p.get("source", ""),
                params=p.get("params", [])
            )
            for p in agent_def.get("perception", [])
        ]

        # Parse skills
        skills = [
            Skill(
                skill_id=s["id"],
                description=s.get("description", ""),
                affected_param=s.get("affects", None),
                direction=s.get("direction", "none"),
                literature=s.get("literature", "")
            )
            for s in agent_def.get("skills", [])
        ]

        config = AgentConfig(
            name=agent_def["name"],
            agent_type=agent_def.get("type", "institutional"),
            state_params=state_params,
            objectives=objectives,
            constraints=constraints,
            perception=perception,
            skills=skills,
            persona=agent_def.get("persona", ""),
            role_description=agent_def.get("role", "")
        )

        configs.append(config)

    return configs


def load_agents(
    yaml_path: str,
    memory_factory: Optional[Callable[[str], Any]] = None
) -> Dict[str, BaseAgent]:
    """
    Load and instantiate agents from YAML config.

    Args:
        yaml_path: Path to YAML config file
        memory_factory: Optional callable to create memory for each agent

    Returns:
        Dict mapping agent names to BaseAgent instances
    """
    configs = load_agent_configs(yaml_path)

    agents = {}
    for config in configs:
        memory = memory_factory(config.name) if memory_factory else None
        agents[config.name] = BaseAgent(config, memory)

    return agents
