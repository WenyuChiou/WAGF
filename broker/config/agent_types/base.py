"""
Agent Type Base Definitions - Core types for SA/MA unified architecture.

This module defines the fundamental types for agent type configuration,
supporting both Single-Agent (SA) and Multi-Agent (MA) scenarios.

Part of Task-040: SA/MA Unified Architecture (Part 14.5)
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Literal
from enum import Enum


class PsychologicalFramework(str, Enum):
    """
    Psychological assessment framework types.

    Different agent types use different frameworks:
    - PMT: Protection Motivation Theory (households)
    - UTILITY: Utility Theory (government agents)
    - FINANCIAL: Financial Risk Theory (insurance agents)
    """
    PMT = "pmt"
    UTILITY = "utility"
    FINANCIAL = "financial"
    CUSTOM = "custom"


class AgentCategory(str, Enum):
    """
    Agent category classifications.
    """
    HOUSEHOLD = "household"
    INSTITUTIONAL = "institutional"
    ENVIRONMENTAL = "environmental"
    CUSTOM = "custom"


@dataclass
class ConstructDefinition:
    """
    Definition of a psychological construct.

    Constructs are the measurable dimensions of an agent's cognitive state.
    For PMT: TP_LABEL (Threat Perception), CP_LABEL (Coping Perception), etc.
    """
    name: str                          # Human-readable name
    key: str                           # Internal key (e.g., "TP_LABEL")
    values: List[str] = field(default_factory=list)  # Valid values
    description: str = ""
    required: bool = True

    def validate(self, value: Any) -> bool:
        """Check if a value is valid for this construct."""
        if not self.values:
            return True  # No constraint
        return str(value).upper() in [v.upper() for v in self.values]


@dataclass
class ResponseFieldDefinition:
    """
    Definition of a response format field.

    Specifies what fields are expected in an agent's response.
    """
    key: str                           # Field key in response
    field_type: str = "text"           # text, choice, appraisal, numeric
    required: bool = True
    construct: Optional[str] = None    # Link to ConstructDefinition
    valid_values: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ResponseFormatSpec:
    """
    Specification for agent response format.

    Defines how the LLM should structure its output.
    """
    delimiter_start: str = "<<<DECISION_START>>>"
    delimiter_end: str = "<<<DECISION_END>>>"
    fields: List[ResponseFieldDefinition] = field(default_factory=list)
    json_mode: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResponseFormatSpec":
        """Create ResponseFormatSpec from dictionary (YAML config)."""
        fields = []
        for f in data.get("fields", []):
            fields.append(ResponseFieldDefinition(
                key=f.get("key", ""),
                field_type=f.get("type", "text"),
                required=f.get("required", True),
                construct=f.get("construct"),
                valid_values=f.get("valid_values", []),
                description=f.get("description", ""),
            ))

        return cls(
            delimiter_start=data.get("delimiter_start", "<<<DECISION_START>>>"),
            delimiter_end=data.get("delimiter_end", "<<<DECISION_END>>>"),
            fields=fields,
            json_mode=data.get("json_mode", False),
        )


@dataclass
class ValidationRuleRef:
    """
    Reference to a validation rule.

    Rules are defined in the governance module; this is a reference
    for per-agent-type rule configuration.
    """
    rule_id: str
    precondition: Optional[str] = None      # State precondition
    construct: Optional[str] = None         # Construct to check
    when_above: List[str] = field(default_factory=list)
    blocked_skills: List[str] = field(default_factory=list)
    level: Literal["ERROR", "WARNING"] = "ERROR"
    message: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationRuleRef":
        """Create from dictionary."""
        return cls(
            rule_id=data.get("id", ""),
            precondition=data.get("precondition"),
            construct=data.get("construct"),
            when_above=data.get("when_above", []),
            blocked_skills=data.get("blocked_skills", []),
            level=data.get("level", "ERROR"),
            message=data.get("message", ""),
        )


@dataclass
class ValidationConfig:
    """
    Per-agent-type validation configuration.
    """
    identity_rules: List[ValidationRuleRef] = field(default_factory=list)
    thinking_rules: List[ValidationRuleRef] = field(default_factory=list)
    social_rules: List[ValidationRuleRef] = field(default_factory=list)
    financial_rules: List[ValidationRuleRef] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationConfig":
        """Create from dictionary."""
        return cls(
            identity_rules=[ValidationRuleRef.from_dict(r) for r in data.get("identity_rules", [])],
            thinking_rules=[ValidationRuleRef.from_dict(r) for r in data.get("thinking_rules", [])],
            social_rules=[ValidationRuleRef.from_dict(r) for r in data.get("social_rules", [])],
            financial_rules=[ValidationRuleRef.from_dict(r) for r in data.get("financial_rules", [])],
        )


@dataclass
class MemoryConfigSpec:
    """
    Per-agent-type memory configuration.
    """
    engine: str = "unified"
    surprise_strategy: str = "ema"       # ema, symbolic, hybrid
    arousal_threshold: float = 0.5
    ema_alpha: float = 0.3
    window_size: int = 5
    consolidation_threshold: float = 0.6

    # Weights (from v2 HumanCentric)
    emotional_weights: Dict[str, float] = field(default_factory=dict)
    source_weights: Dict[str, float] = field(default_factory=dict)
    retrieval_weights: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryConfigSpec":
        """Create from dictionary."""
        return cls(
            engine=data.get("engine", data.get("engine_type", "unified")),
            surprise_strategy=data.get("surprise_strategy", "ema"),
            arousal_threshold=data.get("arousal_threshold", 0.5),
            ema_alpha=data.get("ema_alpha", 0.3),
            window_size=data.get("window_size", 5),
            consolidation_threshold=data.get("consolidation_threshold", 0.6),
            emotional_weights=data.get("emotional_weights", {}),
            source_weights=data.get("source_weights", {}),
            retrieval_weights=data.get("retrieval_weights", {}),
        )


@dataclass
class AgentTypeDefinition:
    """
    Complete agent type definition.

    This is the central definition for an agent type, containing all
    configuration needed for context building, validation, and behavior.

    Examples:
        - household_owner: PMT framework, can elevate/relocate
        - household_renter: PMT framework, limited to insurance
        - government: Utility framework, policy decisions
        - insurance: Financial framework, claim processing
    """
    type_id: str                                    # Unique identifier
    category: AgentCategory                         # household, institutional, etc.

    # Psychological framework
    psychological_framework: PsychologicalFramework = PsychologicalFramework.PMT
    constructs: Dict[str, ConstructDefinition] = field(default_factory=dict)

    # Context and prompts
    context_template: str = ""                      # Template file path
    system_prompt: str = ""                         # System prompt (optional)

    # Response format
    response_format: Optional[ResponseFormatSpec] = None

    # Skills and validation
    eligible_skills: List[str] = field(default_factory=list)
    validation: Optional[ValidationConfig] = None

    # Memory configuration
    memory_config: Optional[MemoryConfigSpec] = None

    # Inheritance
    parent: Optional[str] = None                    # Parent type_id for inheritance

    # Additional metadata
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTypeDefinition":
        """Create AgentTypeDefinition from dictionary (YAML config)."""
        # Parse category
        category_str = data.get("category", "household")
        try:
            category = AgentCategory(category_str)
        except ValueError:
            category = AgentCategory.CUSTOM

        # Parse framework
        framework_str = data.get("psychological_framework", "pmt")
        try:
            framework = PsychologicalFramework(framework_str)
        except ValueError:
            framework = PsychologicalFramework.CUSTOM

        # Parse constructs
        constructs = {}
        for key, val in data.get("constructs", {}).items():
            if isinstance(val, dict):
                constructs[key] = ConstructDefinition(
                    name=val.get("name", key),
                    key=key,
                    values=val.get("values", []),
                    description=val.get("description", ""),
                    required=val.get("required", True),
                )
            else:
                constructs[key] = ConstructDefinition(name=key, key=key)

        # Parse response format
        response_format = None
        if "response_format" in data:
            response_format = ResponseFormatSpec.from_dict(data["response_format"])

        # Parse validation
        validation = None
        if "validation" in data:
            validation = ValidationConfig.from_dict(data["validation"])

        # Parse memory config
        memory_config = None
        if "memory_config" in data or "memory" in data:
            memory_data = data.get("memory_config", data.get("memory", {}))
            memory_config = MemoryConfigSpec.from_dict(memory_data)

        return cls(
            type_id=data.get("type_id", ""),
            category=category,
            psychological_framework=framework,
            constructs=constructs,
            context_template=data.get("context_template", ""),
            system_prompt=data.get("system_prompt", ""),
            response_format=response_format,
            eligible_skills=data.get("eligible_skills", []),
            validation=validation,
            memory_config=memory_config,
            parent=data.get("parent"),
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "type_id": self.type_id,
            "category": self.category.value,
            "psychological_framework": self.psychological_framework.value,
            "eligible_skills": self.eligible_skills,
            "description": self.description,
        }

        if self.constructs:
            result["constructs"] = {
                k: {"name": v.name, "values": v.values, "required": v.required}
                for k, v in self.constructs.items()
            }

        if self.context_template:
            result["context_template"] = self.context_template

        if self.parent:
            result["parent"] = self.parent

        return result

    def get_construct_keys(self) -> List[str]:
        """Get list of construct keys for this agent type."""
        return list(self.constructs.keys())

    def is_skill_eligible(self, skill_name: str) -> bool:
        """Check if a skill is eligible for this agent type."""
        if not self.eligible_skills:
            return True  # No restriction
        return skill_name in self.eligible_skills


# Default PMT constructs for households
DEFAULT_PMT_CONSTRUCTS = {
    "TP_LABEL": ConstructDefinition(
        name="Threat Perception",
        key="TP_LABEL",
        values=["VL", "L", "M", "H", "VH"],
        description="Agent's perceived threat level",
        required=True,
    ),
    "CP_LABEL": ConstructDefinition(
        name="Coping Perception",
        key="CP_LABEL",
        values=["VL", "L", "M", "H", "VH"],
        description="Agent's perceived ability to cope",
        required=True,
    ),
    "SP_LABEL": ConstructDefinition(
        name="Stakeholder Perception",
        key="SP_LABEL",
        values=["VL", "L", "M", "H", "VH"],
        description="Agent's perception of stakeholder support",
        required=False,
    ),
}

# Default Utility constructs for government
DEFAULT_UTILITY_CONSTRUCTS = {
    "BUDGET_UTIL": ConstructDefinition(
        name="Budget Utility",
        key="BUDGET_UTIL",
        values=["DEFICIT", "NEUTRAL", "SURPLUS"],
        description="Budget impact assessment",
        required=True,
    ),
    "EQUITY_GAP": ConstructDefinition(
        name="Equity Gap",
        key="EQUITY_GAP",
        values=["HIGH", "MEDIUM", "LOW"],
        description="Socioeconomic equity assessment",
        required=True,
    ),
}
