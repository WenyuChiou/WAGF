"""Context builder entrypoint with base interfaces and re-exports."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import string

from broker.utils.logging import setup_logger

logger = setup_logger(__name__)


class SafeFormatter(string.Formatter):
    """Formatter that handles missing keys gracefully by returning a placeholder."""

    def __init__(self, placeholder: str = "[N/A]"):
        self.placeholder = placeholder
        super().__init__()

    def get_value(self, key, args, kwargs):
        if isinstance(key, str):
            return kwargs.get(key, self.placeholder)
        return super().get_value(key, args, kwargs)

    def format_field(self, value, format_spec):
        try:
            return super().format_field(value, format_spec)
        except (ValueError, TypeError):
            return str(value)


class ContextBuilder(ABC):
    """Abstract base class for building LLM context."""

    @abstractmethod
    def build(self, agent_id: str, observable: Optional[List[str]] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def format_prompt(self, context: Dict[str, Any]) -> str:
        pass


from .context_providers import (  # noqa: E402
    ContextProvider,
    SystemPromptProvider,
    AttributeProvider,
    PrioritySchemaProvider,
    EnvironmentProvider,
    MemoryProvider,
    SocialProvider,
    InstitutionalProvider,
    DynamicStateProvider,
    NarrativeProvider,
)
from .tiered_builder import (  # noqa: E402
    BaseAgentContextBuilder,
    TieredContextBuilder,
    create_context_builder,
    load_prompt_templates,
    DEFAULT_PROMPT_TEMPLATE,
    VERBOSE_PROMPT_TEMPLATE,
)

__all__ = [
    "ContextBuilder",
    "SafeFormatter",
    "ContextProvider",
    "SystemPromptProvider",
    "AttributeProvider",
    "PrioritySchemaProvider",
    "EnvironmentProvider",
    "MemoryProvider",
    "SocialProvider",
    "InstitutionalProvider",
    "DynamicStateProvider",
    "NarrativeProvider",
    "BaseAgentContextBuilder",
    "TieredContextBuilder",
    "create_context_builder",
    "load_prompt_templates",
    "DEFAULT_PROMPT_TEMPLATE",
    "VERBOSE_PROMPT_TEMPLATE",
]
