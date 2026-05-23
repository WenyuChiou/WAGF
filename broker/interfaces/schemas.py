"""
Pydantic Schema Validation for Adapter Output.

Provides optional Pydantic-based validation for SkillProposal and related types.
Use these models when strict schema validation is required.

Phase 25 PR9: Priority 3 - Schema Validation
"""
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class SkillProposalSchema(BaseModel):
    """
    Pydantic schema for validating SkillProposal data.
    
    Use this for strict validation of adapter output before processing.
    """
    skill_name: str = Field(..., min_length=1, description="Abstract behavior name")
    agent_id: str = Field(..., min_length=1, description="Agent identifier")
    reasoning: Dict[str, Any] = Field(default_factory=dict, description="Construct appraisals (domain-defined keys)")
    agent_type: str = Field(default="default", description="Agent type for multi-agent scenarios")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    raw_output: str = Field(default="", description="Original LLM output")
    parsing_warnings: List[str] = Field(default_factory=list, description="Any parsing warnings")
    parse_layer: str = Field(default="", description="Which parsing method succeeded")
    
    @field_validator('skill_name')
    @classmethod
    def skill_name_lowercase(cls, v: str) -> str:
        """Normalize skill names to lowercase with underscores."""
        return v.lower().replace(" ", "_").replace("-", "_")
    
    @field_validator('confidence')
    @classmethod  
    def confidence_in_range(cls, v: float) -> float:
        """Ensure confidence is between 0 and 1."""
        return max(0.0, min(1.0, v))
    
    model_config = {
        "extra": "ignore",  # Ignore extra fields
        "validate_default": True
    }


# Phase 6M-A (2026-05-23): the former ``ReasoningSchema`` Pydantic
# template lived here with PMT-flavored ``threat_appraisal`` /
# ``coping_appraisal`` field names. It was dead code (verified by
# Phase 6M Explore: zero imports / instantiations / type annotations
# anywhere in broker/, examples/, or tests/). Deleted to remove the
# last PMT-construct identifier from generic broker/interfaces/.
# Reasoning payloads now flow through the construct-agnostic
# ``SkillProposalSchema.reasoning: Dict[str, Any]`` field, and the
# response-format builder reads construct names from YAML
# (``agent_types.yaml`` ``response_format.fields``). A future
# PMT-specific reference can be re-created at
# ``broker/domains/water/schemas.py`` if a caller genuinely needs it.


class ValidationResultSchema(BaseModel):
    """Schema for validation results."""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


def validate_proposal(data: Dict[str, Any]) -> tuple[bool, Optional[SkillProposalSchema], List[str]]:
    """
    Validate a dictionary against SkillProposalSchema.
    
    Args:
        data: Dictionary containing proposal data
        
    Returns:
        Tuple of (is_valid, validated_model, errors)
    """
    try:
        model = SkillProposalSchema(**data)
        return True, model, []
    except Exception as e:
        return False, None, [str(e)]


def schema_to_dataclass(schema: SkillProposalSchema):
    """
    Convert Pydantic schema to dataclass SkillProposal.
    
    Use this when you need to convert validated Pydantic model back to
    the standard dataclass format used by the broker.
    """
    from broker.interfaces.skill_types import SkillProposal
    
    return SkillProposal(
        skill_name=schema.skill_name,
        agent_id=schema.agent_id,
        reasoning=schema.reasoning,
        agent_type=schema.agent_type,
        confidence=schema.confidence,
        raw_output=schema.raw_output,
        parsing_warnings=schema.parsing_warnings,
        parse_layer=schema.parse_layer
    )
