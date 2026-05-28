from __future__ import annotations

import warnings
import importlib
from pathlib import Path
from typing import Annotated, Dict, List, Optional, Literal, Any

import yaml
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# Silence the pydantic shadowing warning for the ``construct`` field on
# RuleCondition / GovernanceRule. "construct" is a domain term (cognitive
# constructs like TP / WSA / SC) used in 3000+ YAML condition rows;
# renaming would break all consumers. The field shadows the deprecated
# pydantic BaseModel.construct() classmethod (replaced by model_construct
# in pydantic 2), so keeping the field name carries no functional risk.
warnings.filterwarnings(
    "ignore",
    message=r'Field name "construct" in "(RuleCondition|GovernanceRule)"',
    category=UserWarning,
)

LEGACY_FRAMEWORK_SLOTS = ("pmt", "utility", "financial", "generic")
LEGACY_AGENT_TYPE_SLOTS = ("household", "government", "insurance")
AGENT_TYPE_RESERVED_KEYS = {
    "global_config",
    "shared",
    "agent_types",
    "governance",
    "metadata",
}
AGENT_TYPE_MARKER_KEYS = {
    "agent_type",
    "psychological_framework",
    "prompt_template",
    "prompt_template_file",
    "actions",
    "skills",
    "eligible_skills",
    "default_skill",
}


def validate_is_registered(name: str) -> str:
    """Validate a framework name against the runtime registry.

    The Phase 6Q-D FRAMEWORK_ESCAPE_HATCH sentinel (``""``) is
    registered explicitly in ``list_registered_frameworks()`` rather
    than special-cased here, so a YAML with
    ``psychological_framework: ""`` passes via the same code path as
    any other registered name. Silent bypass would risk masking a
    typo or migration-shim bug emitting empty strings.
    """
    registered = _list_registered_frameworks()
    if name not in registered:
        raise ValueError(
            f"framework {name!r} is not registered; known frameworks: "
            f"{sorted(registered)}. If you expected a domain framework, "
            "import the domain module before loading config "
            "(e.g. import broker.domains.water)."
        )
    return name


FrameworkStr = Annotated[str, AfterValidator(validate_is_registered)]


def _list_registered_frameworks() -> set[str]:
    from broker.validators.governance.frameworks import list_registered_frameworks

    return list_registered_frameworks()


def _fold_legacy_slots(
    data: Any,
    *,
    target_field: str,
    legacy_slots: tuple[str, ...],
    warning_template: str,
) -> Any:
    """Fold legacy top-level slots into a dict field before validation."""
    if not isinstance(data, dict):
        return data

    migrated = dict(data)
    target = dict(migrated.get(target_field) or {})

    for name in legacy_slots:
        if name not in migrated:
            continue
        if name in target:
            raise ValueError(
                f"Legacy slot '{name}' conflicts with {target_field} dict; remove one"
            )
        target[name] = migrated.pop(name)
        warnings.warn(
            warning_template.format(name=name),
            DeprecationWarning,
            stacklevel=3,
        )

    if target:
        migrated[target_field] = target
    return migrated


class MemoryConfig(BaseModel):
    """Memory engine configuration."""
    engine_type: Literal[
        "window",
        "importance",
        "humancentric",
        "hierarchical",
        "universal",
        "unified",
        "human_centric",
    ] = "window"
    window_size: int = Field(default=5, ge=1, le=20)
    decay_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    consolidation_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    consolidation_probability: float = Field(default=0.7, ge=0.0, le=1.0)
    top_k_significant: int = Field(default=2, ge=1)
    arousal_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    surprise_boost_factor: float = Field(default=1.5, ge=1.0, le=3.0)
    forgetting_threshold: float = Field(default=0.2, ge=0.0, le=1.0)

    model_config = ConfigDict(extra="allow")

    @field_validator("engine_type", mode="before")
    @classmethod
    def normalize_engine_type(cls, value: str) -> str:
        if value == "human_centric":
            return "humancentric"
        return value


class RatingScaleConfig(BaseModel):
    """
    Framework-specific rating scale configuration.

    Task-041: Universal Prompt/Context/Governance Framework
    """
    levels: List[str] = Field(
        ...,
        min_length=2,
        max_length=10,
        description="Rating scale levels (e.g., ['VL', 'L', 'M', 'H', 'VH'])"
    )
    labels: Dict[str, str] = Field(
        default_factory=dict,
        description="Level-to-description mapping (e.g., {'VL': 'Very Low'})"
    )
    template: Optional[str] = Field(
        default=None,
        description="Prompt template for this scale"
    )
    numeric_range: Optional[List[float]] = Field(
        default=None,
        description="Optional numeric range [min, max] for utility/financial"
    )

    model_config = ConfigDict(extra="allow")

    @field_validator("numeric_range")
    @classmethod
    def validate_numeric_range(cls, v):
        if v is not None:
            if len(v) != 2:
                raise ValueError("numeric_range must have exactly 2 values [min, max]")
            if v[0] >= v[1]:
                raise ValueError("numeric_range[0] must be less than numeric_range[1]")
        return v


class RatingScalesConfig(BaseModel):
    """
    Container for all framework rating scales.

    Task-041: Universal Prompt/Context/Governance Framework
    """
    frameworks: Dict[str, RatingScaleConfig] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")  # Allow custom framework names

    @model_validator(mode="before")
    @classmethod
    def fold_legacy_framework_slots(cls, data: Any) -> Any:
        return _fold_legacy_slots(
            data,
            target_field="frameworks",
            legacy_slots=LEGACY_FRAMEWORK_SLOTS,
            warning_template=(
                "Top-level framework slot '{name}' is deprecated; "
                "place under frameworks: {{}} dict instead."
            ),
        )

    @field_validator("frameworks")
    @classmethod
    def validate_framework_names(cls, value: Dict[str, RatingScaleConfig]):
        for name in value:
            validate_is_registered(name)
        return value

    def __getattr__(self, name: str) -> Any:
        if name in LEGACY_FRAMEWORK_SLOTS:
            return self.frameworks.get(name)
        return super().__getattr__(name)


# =============================================================================
# Task-041 Phase 3: Construct & Multi-Condition Governance
# =============================================================================

class ConstructDefinition(BaseModel):
    """
    Single psychological construct definition.

    Task-041 Phase 3: Universal Construct & Governance Framework
    """
    id: str = Field(..., description="Construct ID (e.g., TP_LABEL, WSA_LABEL, BUDGET_UTIL)")
    name: str = Field(..., description="Human-readable name (e.g., 'Threat Perception')")
    description: Optional[str] = Field(default=None, description="Detailed description")
    scale: str = Field(default="pmt", description="Rating scale to use (pmt/utility/financial)")

    model_config = ConfigDict(extra="allow")


class FrameworkConstructs(BaseModel):
    """
    Constructs for a psychological framework.

    Task-041 Phase 3: Supports required (SA) and optional (MA) constructs.
    """
    required: List[ConstructDefinition] = Field(
        default_factory=list,
        description="Required constructs (e.g., TP_LABEL/CP_LABEL for PMT, WSA_LABEL/ACA_LABEL for cognitive appraisal)"
    )
    optional: List[ConstructDefinition] = Field(
        default_factory=list,
        description="Optional constructs (e.g., SP_LABEL for PMT, ADOPTION_RATE for utility)"
    )

    model_config = ConfigDict(extra="allow")


class ConstructsConfig(BaseModel):
    """
    Container for all framework constructs.

    Task-041 Phase 3: Define which constructs each framework supports.
    """
    frameworks: Dict[str, FrameworkConstructs] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def fold_legacy_framework_slots(cls, data: Any) -> Any:
        return _fold_legacy_slots(
            data,
            target_field="frameworks",
            legacy_slots=LEGACY_FRAMEWORK_SLOTS,
            warning_template=(
                "Top-level framework slot '{name}' is deprecated; "
                "place under frameworks: {{}} dict instead."
            ),
        )

    @field_validator("frameworks")
    @classmethod
    def validate_framework_names(cls, value: Dict[str, FrameworkConstructs]):
        for name in value:
            validate_is_registered(name)
        return value

    def __getattr__(self, name: str) -> Any:
        if name in LEGACY_FRAMEWORK_SLOTS:
            return self.frameworks.get(name)
        return super().__getattr__(name)


class RuleCondition(BaseModel):
    """
    Single condition in a multi-condition governance rule.

    Task-041 Phase 3: Supports construct ratings and variable comparisons.

    The ``construct`` field shadows pydantic's ``BaseModel.construct()`` classmethod.
    We silence the shadow warning with ``protected_namespaces=()`` because
    "construct" is a domain term (a cognitive construct like TP / WSA) used
    pervasively in YAML configs and renaming would break 3000+ consumer sites.
    """
    model_config = ConfigDict(extra="allow", protected_namespaces=())

    construct: Optional[str] = Field(
        default=None,
        description="Construct to check (e.g., TP_LABEL, WSA_LABEL, BUDGET_UTIL)"
    )
    variable: Optional[str] = Field(
        default=None,
        description="Non-construct variable (e.g., savings, income, water_right)"
    )
    operator: Literal["in", "not_in", "==", "!=", "<", ">", "<=", ">="] = Field(
        default="in",
        description="Comparison operator"
    )
    values: Optional[List[str]] = Field(
        default=None,
        description="Values for 'in' or 'not_in' operators"
    )
    value: Optional[Any] = Field(
        default=None,
        description="Single value for comparison operators (==, <, >, etc.)"
    )


class GovernanceRule(BaseModel):
    """
    Enhanced governance rule with multi-condition support.

    Task-041 Phase 3: Supports both legacy single-construct and new multi-condition rules.

    Uses ``protected_namespaces=()`` for the same reason as ``RuleCondition``:
    the ``construct`` field is a domain term used pervasively in YAML configs.
    """
    model_config = ConfigDict(extra="allow", protected_namespaces=())

    id: str
    category: Optional[str] = Field(
        default="thinking",
        description="Rule category (thinking, identity, physical, social)"
    )
    # Legacy single-construct (backward compatible)
    construct: Optional[str] = None
    when_above: Optional[List[str]] = None
    # NEW: Multi-condition support (AND logic)
    conditions: Optional[List[RuleCondition]] = Field(
        default=None,
        description="List of conditions (all must match - AND logic)"
    )
    blocked_skills: List[str] = []
    level: Literal["ERROR", "WARNING"] = "ERROR"
    message: Optional[str] = None
    # Task-041: Add framework field for multi-framework support
    framework: Optional[FrameworkStr] = None


class GovernanceProfile(BaseModel):
    """Governance profile (strict/relaxed/disabled)."""
    thinking_rules: List[GovernanceRule] = []
    identity_rules: List[GovernanceRule] = []

    model_config = ConfigDict(extra="allow")


class GovernanceProfiles(BaseModel):
    """Governance profiles container."""
    strict: Optional[GovernanceProfile] = None
    relaxed: Optional[GovernanceProfile] = None
    disabled: Optional[GovernanceProfile] = None

    model_config = ConfigDict(extra="allow")


class GlobalConfig(BaseModel):
    """Global experiment configuration."""
    memory: MemoryConfig = MemoryConfig()
    reflection: Optional[Dict[str, Any]] = None
    llm: Optional[Dict[str, Any]] = None
    governance: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")


class SharedConfig(BaseModel):
    """
    Shared configuration section for all agent types.

    Task-041: Universal Prompt/Context/Governance Framework
    """
    rating_scale: Optional[str] = Field(
        default=None,
        description="Legacy single rating scale template (backward compatible)"
    )
    rating_scales: Optional[RatingScalesConfig] = Field(
        default=None,
        description="Framework-specific rating scales (Task-041)"
    )
    response_format: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")


class AgentTypeSpecificConfig(BaseModel):
    """
    Per-agent-type configuration.

    Task-041: Universal Prompt/Context/Governance Framework
    """
    psychological_framework: Optional[FrameworkStr] = Field(
        default=None,
        description="Psychological framework for this agent type"
    )
    prompt_template: Optional[str] = None
    response_format: Optional[Dict[str, Any]] = None
    eligible_skills: Optional[List[str]] = None
    memory: Optional[MemoryConfig] = None

    model_config = ConfigDict(extra="allow")


class AgentTypeConfig(BaseModel):
    """Full agent_types.yaml configuration."""
    global_config: Optional[GlobalConfig] = None
    shared: Optional[SharedConfig] = None
    agent_types: Dict[str, AgentTypeSpecificConfig] = Field(default_factory=dict)
    governance: Optional[GovernanceProfiles] = None

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def fold_legacy_agent_type_slots(cls, data: Any) -> Any:
        migrated = _fold_legacy_slots(
            data,
            target_field="agent_types",
            legacy_slots=LEGACY_AGENT_TYPE_SLOTS,
            warning_template=(
                "Top-level agent-type slot '{name}' is deprecated; "
                "place under agent_types: {{}} dict instead."
            ),
        )
        if not isinstance(migrated, dict):
            return migrated

        migrated = dict(migrated)
        target = dict(migrated.get("agent_types") or {})
        for name in list(migrated):
            if name in AGENT_TYPE_RESERVED_KEYS:
                continue
            value = migrated[name]
            if not isinstance(value, dict):
                continue
            if not (AGENT_TYPE_MARKER_KEYS & set(value)):
                continue
            if name in target:
                raise ValueError(
                    f"Legacy slot '{name}' conflicts with agent_types dict; remove one"
                )
            target[name] = migrated.pop(name)
            warnings.warn(
                "Top-level agent-type slot "
                f"'{name}' is deprecated; place under agent_types: {{}} dict instead.",
                DeprecationWarning,
                stacklevel=3,
            )
        if target:
            migrated["agent_types"] = target
        return migrated

    def __getattr__(self, name: str) -> Any:
        if name in self.agent_types:
            return self.agent_types[name]
        return super().__getattr__(name)


def load_agent_config(config_path: Path) -> AgentTypeConfig:
    """Load and validate agent_types.yaml configuration."""
    _import_domain_for_config_path(Path(config_path))
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return AgentTypeConfig(**raw)


def _import_domain_for_config_path(config_path: Path) -> None:
    """Best-effort import of known example domain modules for registry side effects.

    Only fires when the config path matches a known example domain.
    No unconditional ``broker.domains.water`` import — that would
    reintroduce the reverse coupling Phase 6U-B eliminates and silently
    contaminate the framework registry for non-water domains. Unknown
    paths get no auto-import; the registry validator's error message
    instructs the caller to import the domain module explicitly.
    """
    normalized = config_path.as_posix()
    candidates: list[str] = []
    if "examples/vaccination_demo/" in normalized:
        candidates.append("examples.vaccination_demo")
    elif any(
        marker in normalized
        for marker in (
            "examples/irrigation_abm/",
            "examples/single_agent/",
            "examples/multi_agent/flood/",
            "examples/governed_flood/",
        )
    ):
        candidates.append("broker.domains.water")

    for module_name in candidates:
        try:
            importlib.import_module(module_name)
        except ImportError:
            continue


def validate_rating_scales(config: Dict[str, Any]) -> List[str]:
    """
    Validate rating_scales configuration.

    Task-041: Universal Prompt/Context/Governance Framework

    Args:
        config: The shared.rating_scales section from YAML

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if not config:
        return errors

    valid_frameworks = _list_registered_frameworks()

    if "frameworks" in config and isinstance(config["frameworks"], dict):
        config = config["frameworks"]

    for framework_name, scale_config in config.items():
        if framework_name not in valid_frameworks:
            # Allow custom frameworks but warn
            pass

        if not isinstance(scale_config, dict):
            errors.append(f"rating_scales.{framework_name} must be a dict")
            continue

        # Validate levels
        levels = scale_config.get("levels", [])
        if not levels:
            errors.append(f"rating_scales.{framework_name}.levels is required")
        elif len(levels) < 2:
            errors.append(f"rating_scales.{framework_name}.levels must have at least 2 items")

        # Validate labels match levels
        labels = scale_config.get("labels", {})
        if labels:
            for level in levels:
                if level not in labels:
                    errors.append(
                        f"rating_scales.{framework_name}.labels missing key '{level}'"
                    )

        # Validate numeric_range
        numeric_range = scale_config.get("numeric_range")
        if numeric_range is not None:
            if not isinstance(numeric_range, (list, tuple)) or len(numeric_range) != 2:
                errors.append(
                    f"rating_scales.{framework_name}.numeric_range must be [min, max]"
                )
            elif numeric_range[0] >= numeric_range[1]:
                errors.append(
                    f"rating_scales.{framework_name}.numeric_range: min must be < max"
                )

    return errors
