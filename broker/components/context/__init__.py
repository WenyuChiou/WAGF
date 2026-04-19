"""Public API for broker.components.context.

Re-exports the symbols currently consumed via deep imports across the
repository so callers have a shorter canonical import path. Existing deep
imports remain supported.
"""

from importlib import import_module

_EXPORT_MAP = {
    "AttributeProvider": ("providers", "AttributeProvider"),
    "BaseAgentContextBuilder": ("tiered", "BaseAgentContextBuilder"),
    "ContextProvider": ("providers", "ContextProvider"),
    "DynamicStateProvider": ("providers", "DynamicStateProvider"),
    "EnvironmentEventProvider": ("providers", "EnvironmentEventProvider"),
    "EnvironmentObservationProvider": ("providers", "EnvironmentObservationProvider"),
    "InstitutionalProvider": ("providers", "InstitutionalProvider"),
    "InteractionHub": ("..analytics.interaction", "InteractionHub"),
    "MemoryProvider": ("providers", "MemoryProvider"),
    "NarrativeProvider": ("providers", "NarrativeProvider"),
    "ObservableStateProvider": ("providers", "ObservableStateProvider"),
    "PerceptionAwareProvider": ("providers", "PerceptionAwareProvider"),
    "PrioritySchemaProvider": ("providers", "PrioritySchemaProvider"),
    "SocialProvider": ("providers", "SocialProvider"),
    "TieredContextBuilder": ("tiered", "TieredContextBuilder"),
    "create_context_builder": ("tiered", "create_context_builder"),
    "load_prompt_templates": ("tiered", "load_prompt_templates"),
}

__all__ = list(_EXPORT_MAP)


def __getattr__(name: str):
    if name not in _EXPORT_MAP:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _EXPORT_MAP[name]
    if module_name.startswith(".."):
        module = import_module(module_name, package=__name__)
    else:
        module = import_module(f"{__name__}.{module_name}")
    return getattr(module, attr_name)


def __dir__():
    return sorted(set(globals()) | set(__all__))
