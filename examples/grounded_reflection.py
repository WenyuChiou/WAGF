"""Reflection configuration shared by the flood and irrigation paper runners."""

from broker.components.cognitive.reflection import GROUNDING_KEYS, reflection_question
from broker.utils.agent_config import AgentTypeConfig


def require_grounded_reflection(config: AgentTypeConfig, *, agent_type: str) -> None:
    """Validate the effective YAML settings before the runner starts.

    ``agent_type`` is the type the runner reflects for. Its topic is checked
    even when the YAML has no block of that name, so a run cannot pass this
    check and then fail at its first reflection, after model calls began."""
    reflection = config.get_reflection_config()
    agent_types = list(dict.fromkeys([agent_type, *(config.agent_type_names() or [])]))
    for agent_type in agent_types:
        effective = {**reflection, **((config.get(agent_type) or {}).get("reflection", {}) or {})}
        if "questions" in effective:
            raise ValueError(
                "reflection.questions was retired for the one-agent reflection on 2026-11-27. "
                "Set reflection.topic instead (a short noun phrase naming what the agent faces "
                "and what it decides about, with no action verb or direction; the framework "
                "asks 'What do your recent years tell you about <topic>?'). "
                "Reproduce old runs from tag v0.7.0."
            )
        reflection_question(config.get_reflection_topic(agent_type))
    invalid = [key for key in GROUNDING_KEYS if reflection.get(key) is not True]
    if invalid:
        raise ValueError(
            "Ungrounded and partly grounded reflection were retired on 2026-11-27. "
            "Reproduce old runs from tag v0.7.0. Set these reflection keys to true: "
            + ", ".join(invalid)
        )
