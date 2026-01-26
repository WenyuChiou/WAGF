"""
Reflection System Module.

Provides domain-specific reflection templates and memory integration for
agent introspection and learning consolidation.

Components:
- insight.py: ReflectionInsight and ReflectionTrace data structures
- templates.py: Domain-specific reflection prompts (flood, finance, education, health)
- integration.py: Memory feedback loop and batch processing

Usage:
    >>> from governed_ai_sdk.v1_prototype.reflection import (
    ...     ReflectionInsight,
    ...     get_reflection_template,
    ...     ReflectionMemoryIntegrator,
    ... )
    >>>
    >>> # Get domain template
    >>> template = get_reflection_template("flood")
    >>>
    >>> # Generate reflection prompt
    >>> prompt = template.generate_prompt(agent_id, memories, context)
    >>>
    >>> # Parse LLM response
    >>> insight = template.parse_response(llm_response, memories, context)
    >>>
    >>> # Or use integrator for full workflow with memory promotion
    >>> integrator = ReflectionMemoryIntegrator(
    ...     domain="flood",
    ...     memory_store_fn=memory_engine.add_memory,
    ...     auto_promote=True
    ... )
    >>> insight = integrator.generate_and_process(agent_id, memories, context, llm_call)
"""

from .insight import ReflectionInsight, ReflectionTrace

from .templates import (
    ReflectionTemplate,
    GenericReflectionTemplate,
    FloodReflectionTemplate,
    FinanceReflectionTemplate,
    EducationReflectionTemplate,
    HealthReflectionTemplate,
    get_reflection_template,
    register_reflection_template,
    REFLECTION_TEMPLATES,
)

from .integration import (
    ReflectionMemoryIntegrator,
    BatchReflectionProcessor,
)

__all__ = [
    # Insight data structures
    "ReflectionInsight",
    "ReflectionTrace",
    # Template base and implementations
    "ReflectionTemplate",
    "GenericReflectionTemplate",
    "FloodReflectionTemplate",
    "FinanceReflectionTemplate",
    "EducationReflectionTemplate",
    "HealthReflectionTemplate",
    # Registry functions
    "get_reflection_template",
    "register_reflection_template",
    "REFLECTION_TEMPLATES",
    # Integration
    "ReflectionMemoryIntegrator",
    "BatchReflectionProcessor",
]
