"""
Context Types - Universal context structures for SA/MA prompt generation.

This module defines the unified context structures used across Single-Agent (SA)
and Multi-Agent (MA) modes. These types enable consistent context building,
prompt assembly, governance validation, and reflection integration.

Part of Task-041: Universal Prompt/Context/Governance Framework
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum


class PsychologicalFrameworkType(Enum):
    """Psychological framework types for agent behavior modeling."""
    PMT = "pmt"           # Protection Motivation Theory (household)
    UTILITY = "utility"   # Utility Theory (government)
    FINANCIAL = "financial"  # Financial Risk Theory (insurance)
    GENERIC = "generic"   # Default/generic framework


@dataclass
class MemoryContext:
    """
    Structured memory context for prompt injection.

    This structure organizes agent memories into meaningful categories
    for use in prompt generation. It supports both legacy flat format
    and structured format.

    Attributes:
        core: Core state summary (key state variables)
        episodic: Recent event memories (chronological)
        semantic: Historical knowledge and patterns
        retrieval_info: Metadata about retrieval process (for audit)
    """
    core: Dict[str, Any] = field(default_factory=dict)
    episodic: List[str] = field(default_factory=list)
    semantic: List[str] = field(default_factory=list)
    retrieval_info: Dict[str, Any] = field(default_factory=dict)

    def format_for_prompt(self, style: str = "structured") -> str:
        """
        Format memory context for prompt injection.

        Args:
            style: Format style - "structured" (default) or "flat"

        Returns:
            Formatted string for prompt injection
        """
        if style == "flat":
            return self._format_flat()
        return self._format_structured()

    def _format_structured(self) -> str:
        """Format as structured memory sections."""
        lines = []

        if self.core:
            core_items = [f"{k}={v}" for k, v in self.core.items()]
            lines.append(f"CORE STATE: {' | '.join(core_items)}")

        if self.semantic:
            lines.append("HISTORICAL KNOWLEDGE:")
            for mem in self.semantic:
                lines.append(f"  - {mem}")

        if self.episodic:
            lines.append("RECENT EVENTS:")
            for mem in self.episodic:
                lines.append(f"  - {mem}")

        return "\n".join(lines) if lines else "No memory available"

    def _format_flat(self) -> str:
        """Format as flat memory list (legacy compatibility)."""
        all_memories = self.semantic + self.episodic
        if not all_memories:
            return "No memory available"
        return "\n".join([f"- {mem}" for mem in all_memories])

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "core": self.core,
            "episodic": self.episodic,
            "semantic": self.semantic,
            "retrieval_info": self.retrieval_info,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryContext":
        """Create from dictionary."""
        return cls(
            core=data.get("core", {}),
            episodic=data.get("episodic", []),
            semantic=data.get("semantic", []),
            retrieval_info=data.get("retrieval_info", {}),
        )

    @classmethod
    def from_legacy_list(cls, memories: List[str], core_state: Dict[str, Any] = None) -> "MemoryContext":
        """
        Create from legacy memory list format.

        Args:
            memories: List of memory strings
            core_state: Optional core state dictionary

        Returns:
            MemoryContext instance
        """
        return cls(
            core=core_state or {},
            episodic=memories,
            semantic=[],
            retrieval_info={"source": "legacy_list"},
        )


@dataclass
class ConstructAppraisal:
    """
    A psychological construct appraisal.

    Attributes:
        construct_key: The construct identifier (e.g., "TP_LABEL", "CP_LABEL")
        label: The assessed label value (e.g., "H", "VH")
        reason: Explanation for the appraisal
    """
    construct_key: str
    label: str
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "construct_key": self.construct_key,
            "label": self.label,
            "reason": self.reason,
        }


@dataclass
class PriorityItem:
    """
    A priority/critical factor item for prompt emphasis.

    Used to highlight important factors in the prompt that the agent
    should focus on when making decisions.
    """
    attribute: str
    value: Any
    priority: float = 1.0
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attribute": self.attribute,
            "value": self.value,
            "priority": self.priority,
            "reason": self.reason,
        }


@dataclass
class UniversalContext:
    """
    SA/MA universal context structure.

    This is the unified context structure that works across both Single-Agent (SA)
    and Multi-Agent (MA) modes. It consolidates all information needed for:
    - Prompt assembly
    - Governance validation
    - Retry formatting
    - Reflection generation

    Attributes:
        agent_id: Unique agent identifier
        agent_type: Agent type string (e.g., "household", "government")
        agent_name: Human-readable agent name
        agent_roles: Optional list of roles for multi-identity agents

        framework: Psychological framework type (PMT, Utility, Financial)
        constructs: Construct definitions from framework

        state: Core agent state attributes
        personal: Personal context (alias for backward compatibility)
        local: Local context (spatial, social, visible_actions)
        institutional: Institutional context (policies, announcements)
        global_context: Global news/events list

        memory: Structured memory context

        available_skills: List of all available skill IDs
        eligible_skills: List of eligible skill IDs for this agent type
        options_text: Formatted options text for prompt
        valid_choices_text: Formatted choices text (e.g., "1, 2, or 3")
        dynamic_skill_map: Mapping from option number to skill ID

        system_prompt: System-level prompt (from YAML)
        priority_schema: Critical factors to emphasize in prompt
        rating_scale: Rating scale text (VL/L/M/H/VH explanation)
        response_format: Response format block (delimiters + JSON structure)

        agent_type_definition: Full type definition (MA mode)
        year: Current simulation year
        retry_attempt: Current retry attempt number (for governance)
        max_retries: Maximum retry attempts allowed
    """
    # Identity (required)
    agent_id: str
    agent_type: str = "default"
    agent_name: str = ""
    agent_roles: List[str] = field(default_factory=list)  # Multi-identity support

    # Framework metadata (from AgentTypeRegistry)
    framework: PsychologicalFrameworkType = PsychologicalFrameworkType.PMT
    constructs: Dict[str, Any] = field(default_factory=dict)

    # State layers (tiered)
    state: Dict[str, Any] = field(default_factory=dict)
    personal: Dict[str, Any] = field(default_factory=dict)
    local: Dict[str, Any] = field(default_factory=dict)
    institutional: Dict[str, Any] = field(default_factory=dict)
    global_context: List[str] = field(default_factory=list)

    # Memory (structured)
    memory: MemoryContext = field(default_factory=MemoryContext)

    # Skills (filtered by agent type)
    available_skills: List[str] = field(default_factory=list)
    eligible_skills: List[str] = field(default_factory=list)

    # Prompt assembly helpers (computed)
    options_text: str = ""
    valid_choices_text: str = ""
    dynamic_skill_map: Dict[str, str] = field(default_factory=dict)

    # Prompt template components (from YAML/config)
    system_prompt: str = ""
    priority_schema: List[Any] = field(default_factory=list)  # List[PriorityItem]
    rating_scale: str = ""
    response_format: str = ""
    prompt_template: str = ""  # The template string itself

    # MA extensions
    agent_type_definition: Optional[Dict[str, Any]] = None
    year: Optional[int] = None

    # Governance context
    retry_attempt: int = 0
    max_retries: int = 3

    def get_framework_name(self) -> str:
        """Get the framework name as string."""
        return self.framework.value if isinstance(self.framework, PsychologicalFrameworkType) else str(self.framework)

    def get_personal_summary(self) -> str:
        """
        Generate a personal context summary string.

        Returns:
            Formatted string summarizing personal context
        """
        if not self.personal:
            return ""

        items = []
        for key, value in self.personal.items():
            if key not in ("id", "agent_id", "narrative"):
                items.append(f"{key}: {value}")

        return " | ".join(items)

    def get_local_summary(self) -> str:
        """
        Generate a local context summary string.

        Returns:
            Formatted string summarizing local context
        """
        if not self.local:
            return ""

        summaries = []

        # Spatial context
        if "spatial" in self.local:
            spatial = self.local["spatial"]
            summaries.append(f"Location: {spatial}")

        # Social context
        if "social" in self.local:
            social = self.local["social"]
            if isinstance(social, list):
                summaries.append(f"Social: {len(social)} interactions")
            else:
                summaries.append(f"Social: {social}")

        # Visible actions
        if "visible_actions" in self.local:
            actions = self.local["visible_actions"]
            if isinstance(actions, list):
                summaries.append(f"Observed: {len(actions)} actions")

        return " | ".join(summaries)

    def get_institutional_summary(self) -> str:
        """
        Generate an institutional context summary string.

        Returns:
            Formatted string summarizing institutional context
        """
        if not self.institutional:
            return ""

        items = []
        for key, value in self.institutional.items():
            items.append(f"{key}: {value}")

        return " | ".join(items)

    def get_global_summary(self) -> str:
        """
        Generate a global context summary string.

        Returns:
            Formatted string summarizing global events
        """
        if not self.global_context:
            return ""

        return "; ".join(self.global_context)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization or legacy compatibility.

        Returns:
            Dictionary representation of the context
        """
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "agent_name": self.agent_name,
            "agent_roles": self.agent_roles,
            "framework": self.get_framework_name(),
            "constructs": self.constructs,
            "state": self.state,
            "personal": self.personal,
            "local": self.local,
            "institutional": self.institutional,
            "global": self.global_context,
            "memory": self.memory.to_dict() if self.memory else {},
            "available_skills": self.available_skills,
            "eligible_skills": self.eligible_skills,
            "options_text": self.options_text,
            "valid_choices_text": self.valid_choices_text,
            "dynamic_skill_map": self.dynamic_skill_map,
            "system_prompt": self.system_prompt,
            "priority_schema": self.priority_schema,
            "rating_scale": self.rating_scale,
            "response_format": self.response_format,
            "prompt_template": self.prompt_template,
            "agent_type_definition": self.agent_type_definition,
            "year": self.year,
            "retry_attempt": self.retry_attempt,
            "max_retries": self.max_retries,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UniversalContext":
        """
        Create UniversalContext from dictionary.

        This supports both new structured format and legacy flat format.

        Args:
            data: Dictionary with context data

        Returns:
            UniversalContext instance
        """
        # Parse framework
        framework_str = data.get("framework", "pmt")
        try:
            framework = PsychologicalFrameworkType(framework_str.lower())
        except ValueError:
            framework = PsychologicalFrameworkType.GENERIC

        # Parse memory
        memory_data = data.get("memory", {})
        if isinstance(memory_data, MemoryContext):
            memory = memory_data
        elif isinstance(memory_data, dict):
            memory = MemoryContext.from_dict(memory_data)
        elif isinstance(memory_data, list):
            # Legacy format: list of memory strings
            memory = MemoryContext.from_legacy_list(memory_data)
        else:
            memory = MemoryContext()

        return cls(
            agent_id=data.get("agent_id", ""),
            agent_type=data.get("agent_type", "default"),
            agent_name=data.get("agent_name", data.get("agent_id", "")),
            agent_roles=data.get("agent_roles", []),
            framework=framework,
            constructs=data.get("constructs", {}),
            state=data.get("state", {}),
            personal=data.get("personal", data.get("state", {})),
            local=data.get("local", {}),
            institutional=data.get("institutional", {}),
            global_context=data.get("global", data.get("global_context", [])),
            memory=memory,
            available_skills=data.get("available_skills", []),
            eligible_skills=data.get("eligible_skills", data.get("available_skills", [])),
            options_text=data.get("options_text", ""),
            valid_choices_text=data.get("valid_choices_text", ""),
            dynamic_skill_map=data.get("dynamic_skill_map", {}),
            system_prompt=data.get("system_prompt", ""),
            priority_schema=data.get("priority_schema", []),
            rating_scale=data.get("rating_scale", ""),
            response_format=data.get("response_format", ""),
            prompt_template=data.get("prompt_template", ""),
            agent_type_definition=data.get("agent_type_definition"),
            year=data.get("year"),
            retry_attempt=data.get("retry_attempt", 0),
            max_retries=data.get("max_retries", 3),
        )

    def with_retry_context(self, attempt: int) -> "UniversalContext":
        """
        Create a copy with updated retry context.

        Args:
            attempt: Current retry attempt number

        Returns:
            New UniversalContext with updated retry_attempt
        """
        import copy
        ctx = copy.copy(self)
        ctx.retry_attempt = attempt
        return ctx


@dataclass
class PromptVariables:
    """
    Variables for prompt template rendering.

    This structure holds all the computed variables needed to render
    a prompt template using SafeFormatter or similar templating.

    Attributes:
        narrative_persona: Agent's narrative/persona description
        memory_text: Formatted memory section
        personal_context: Formatted personal context
        local_context: Formatted local context
        institutional_context: Formatted institutional context
        global_context: Formatted global news/events
        options_text: Skill options text
        valid_choices_text: Valid choices summary
        rating_scale: Rating scale text (VL/L/M/H/VH)
        response_format: Response format block (delimiters + JSON structure)
        year: Current year
        extra: Additional custom variables
    """
    narrative_persona: str = ""
    memory_text: str = ""
    personal_context: str = ""
    local_context: str = ""
    institutional_context: str = ""
    global_context: str = ""
    options_text: str = ""
    valid_choices_text: str = ""
    rating_scale: str = ""
    response_format: str = ""
    year: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering."""
        result = {
            "narrative_persona": self.narrative_persona,
            "memory": self.memory_text,
            "memory_text": self.memory_text,
            "personal_context": self.personal_context,
            "personal": self.personal_context,
            "local_context": self.local_context,
            "local": self.local_context,
            "institutional_context": self.institutional_context,
            "institutional": self.institutional_context,
            "global_context": self.global_context,
            "global": self.global_context,
            "options_text": self.options_text,
            "options": self.options_text,
            "valid_choices_text": self.valid_choices_text,
            "valid_choices": self.valid_choices_text,
            "rating_scale": self.rating_scale,
            "response_format": self.response_format,
            "year": self.year,
        }
        # Merge extra variables
        result.update(self.extra)
        return result

    @classmethod
    def from_universal_context(
        cls,
        ctx: UniversalContext,
        rating_scale: str = "",
        response_format: str = "",
    ) -> "PromptVariables":
        """
        Create PromptVariables from UniversalContext.

        Args:
            ctx: Universal context
            rating_scale: Rating scale text (overrides ctx.rating_scale if provided)
            response_format: Response format block (overrides ctx.response_format if provided)

        Returns:
            PromptVariables instance
        """
        # Get narrative from personal context
        narrative = ctx.personal.get("narrative", ctx.personal.get("description", ""))
        if not narrative and ctx.agent_name:
            narrative = f"You are {ctx.agent_name}, a {ctx.agent_type} agent."

        # Use context values as fallback if not provided
        final_rating_scale = rating_scale or ctx.rating_scale
        final_response_format = response_format or ctx.response_format

        return cls(
            narrative_persona=narrative,
            memory_text=ctx.memory.format_for_prompt() if ctx.memory else "",
            personal_context=ctx.get_personal_summary(),
            local_context=ctx.get_local_summary(),
            institutional_context=ctx.get_institutional_summary(),
            global_context=ctx.get_global_summary(),
            options_text=ctx.options_text,
            valid_choices_text=ctx.valid_choices_text,
            rating_scale=final_rating_scale,
            response_format=final_response_format,
            year=str(ctx.year) if ctx.year else "",
            extra={
                "agent_id": ctx.agent_id,
                "agent_type": ctx.agent_type,
                "agent_name": ctx.agent_name,
                "system_prompt": ctx.system_prompt,
                "agent_roles": ctx.agent_roles,
            },
        )


__all__ = [
    "PsychologicalFrameworkType",
    "MemoryContext",
    "ConstructAppraisal",
    "UniversalContext",
    "PromptVariables",
    "PriorityItem",
]
