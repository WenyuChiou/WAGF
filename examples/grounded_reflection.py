"""Reflection configuration shared by the flood and irrigation paper runners."""

from broker.components.cognitive.reflection import GROUNDING_KEYS
from broker.utils.agent_config import AgentTypeConfig


def require_grounded_reflection(config: AgentTypeConfig) -> None:
    """Validate the effective YAML settings before the runner starts."""
    reflection = config.get_reflection_config()
    invalid = [key for key in GROUNDING_KEYS if reflection.get(key) is not True]
    if invalid:
        raise ValueError(
            "Ungrounded and partly grounded reflection were retired on 2026-11-27. "
            "Reproduce old runs from tag v0.7.0. Set these reflection keys to true: "
            + ", ".join(invalid)
        )
