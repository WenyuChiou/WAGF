from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Literal, Any

import yaml
from pydantic import BaseModel, Field, validator


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

    class Config:
        extra = "allow"

    @validator("engine_type", pre=True)
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

    class Config:
        extra = "allow"

    @validator("numeric_range")
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
    pmt: Optional[RatingScaleConfig] = None
    utility: Optional[RatingScaleConfig] = None
    financial: Optional[RatingScaleConfig] = None
    generic: Optional[RatingScaleConfig] = None

    class Config:
        extra = "allow"  # Allow custom framework names


# =============================================================================
# Task-041 Phase 3: Construct & Multi-Condition Governance
# =============================================================================

class ConstructDefinition(BaseModel):
    """
    Single psychological construct definition.

    Task-041 Phase 3: Universal Construct & Governance Framework
    """
    id: str = Field(..., description="Construct ID (e.g., TP_LABEL, CP_LABEL)")
    name: str = Field(..., description="Human-readable name (e.g., 'Threat Perception')")
    description: Optional[str] = Field(default=None, description="Detailed description")
    scale: str = Field(default="pmt", description="Rating scale to use (pmt/utility/financial)")

    class Config:
        extra = "allow"


class FrameworkConstructs(BaseModel):
    """
    Constructs for a psychological framework.

    Task-041 Phase 3: Supports required (SA) and optional (MA) constructs.
    """
    required: List[ConstructDefinition] = Field(
        default_factory=list,
        description="Required constructs (e.g., TP_LABEL, CP_LABEL for SA)"
    )
    optional: List[ConstructDefinition] = Field(
        default_factory=list,
        description="Optional constructs (e.g., SP_LABEL, PA_LABEL, SC_LABEL for MA)"
    )

    class Config:
        extra = "allow"


class ConstructsConfig(BaseModel):
    """
    Container for all framework constructs.

    Task-041 Phase 3: Define which constructs each framework supports.
    """
    pmt: Optional[FrameworkConstructs] = None
    utility: Optional[FrameworkConstructs] = None
    financial: Optional[FrameworkConstructs] = None
    generic: Optional[FrameworkConstructs] = None

    class Config:
        extra = "allow"


class RuleCondition(BaseModel):
    """
    Single condition in a multi-condition governance rule.

    Task-041 Phase 3: Supports construct ratings and variable comparisons.
    """
    construct: Optional[str] = Field(
        default=None,
        description="Construct to check (e.g., TP_LABEL, CP_LABEL)"
    )
    variable: Optional[str] = Field(
        default=None,
        description="Non-construct variable (e.g., savings, income)"
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

    class Config:
        extra = "allow"


class GovernanceRule(BaseModel):
    """
    Enhanced governance rule with multi-condition support.

    Task-041 Phase 3: Supports both legacy single-construct and new multi-condition rules.
    """
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
    framework: Optional[Literal["pmt", "utility", "financial", "generic"]] = None

    class Config:
        extra = "allow"


class GovernanceProfile(BaseModel):
    """Governance profile (strict/relaxed/disabled)."""
    thinking_rules: List[GovernanceRule] = []
    identity_rules: List[GovernanceRule] = []

    class Config:
        extra = "allow"


class GovernanceProfiles(BaseModel):
    """Governance profiles container."""
    strict: Optional[GovernanceProfile] = None
    relaxed: Optional[GovernanceProfile] = None
    disabled: Optional[GovernanceProfile] = None

    class Config:
        extra = "allow"


class GlobalConfig(BaseModel):
    """Global experiment configuration."""
    memory: MemoryConfig = MemoryConfig()
    reflection: Optional[Dict[str, Any]] = None
    llm: Optional[Dict[str, Any]] = None
    governance: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"


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

    class Config:
        extra = "allow"


class AgentTypeSpecificConfig(BaseModel):
    """
    Per-agent-type configuration.

    Task-041: Universal Prompt/Context/Governance Framework
    """
    psychological_framework: Optional[Literal["pmt", "utility", "financial", "generic"]] = Field(
        default="pmt",
        description="Psychological framework for this agent type"
    )
    prompt_template: Optional[str] = None
    response_format: Optional[Dict[str, Any]] = None
    eligible_skills: Optional[List[str]] = None
    memory: Optional[MemoryConfig] = None

    class Config:
        extra = "allow"


class AgentTypeConfig(BaseModel):
    """Full agent_types.yaml configuration."""
    global_config: Optional[GlobalConfig] = None
    shared: Optional[SharedConfig] = None
    household: Optional[AgentTypeSpecificConfig] = None
    government: Optional[AgentTypeSpecificConfig] = None
    insurance: Optional[AgentTypeSpecificConfig] = None
    governance: Optional[GovernanceProfiles] = None

    class Config:
        extra = "allow"


def load_agent_config(config_path: Path) -> AgentTypeConfig:
    """Load and validate agent_types.yaml configuration."""
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return AgentTypeConfig(**raw)


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

    valid_frameworks = {"pmt", "utility", "financial", "generic"}

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
