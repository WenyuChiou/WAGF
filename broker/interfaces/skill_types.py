"""
Skill Types - Core type definitions for Skill-Governed Architecture.

This module defines the fundamental types used in the skill-based governance system.
Skills are abstract behavioral intentions, NOT concrete actions or tools.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum


class SkillOutcome(Enum):
    """Skill processing outcomes."""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RETRY_SUCCESS = "RETRY_SUCCESS"
    UNCERTAIN = "UNCERTAIN"
    ABORTED = "ABORTED"

class ValidationLevel(Enum):
    ERROR = "ERROR"      # Must fix, decision rejected
    WARNING = "WARNING"  # Log but allow


@dataclass
class SkillProposal:
    """
    LLM's skill proposal output.
    
    The LLM proposes a skill (abstract behavior) rather than specifying
    concrete actions or tools. The Broker validates and maps to execution.
    """
    skill_name: str              # Abstract behavior name (e.g., "action_a", "skill_x")
    agent_id: str
    reasoning: Dict[str, str]    # PMT appraisals: {"threat": "...", "coping": "..."}
    agent_type: str = "default"  # Agent type for multi-agent scenarios
    confidence: float = 1.0      # Agent's confidence in this choice (0.0-1.0)
    raw_output: str = ""
    parsing_warnings: List[str] = field(default_factory=list)
    parse_layer: str = ""        # Which parsing method succeeded (enclosure/json/regex/digit/default)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "raw_output": self.raw_output,
            "parsing_warnings": self.parsing_warnings,
            "parse_layer": self.parse_layer
        }


@dataclass
class SkillDefinition:
    """
    Skill definition in the registry.
    
    This is the "institutional charter" for a skill - it defines what the skill
    means, who can use it, under what conditions, and what state changes it allows.
    """
    skill_id: str                          # Unique identifier
    description: str                       # Human-readable description
    eligible_agent_types: List[str]        # Agent types that can use this skill
    preconditions: List[str]               # Required context conditions
    institutional_constraints: Dict[str, Any]  # Domain-specific rules
    allowed_state_changes: List[str]       # Fields this skill can modify
    implementation_mapping: str            # Maps to simulation command


@dataclass
class ValidationResult:
    """Result from a skill validator."""
    valid: bool
    validator_name: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "validator": self.validator_name,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata
        }


@dataclass
class ApprovedSkill:
    """
    A skill that has passed all validation.
    
    Only approved skills can be executed by the simulation engine.
    """
    skill_name: str
    agent_id: str
    approval_status: str         # "APPROVED", "REJECTED", "DEFERRED"
    validation_results: List[ValidationResult] = field(default_factory=list)
    execution_mapping: str = ""  # What the simulation engine executes
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result from simulation engine execution."""
    success: bool
    state_changes: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "state_changes": self.state_changes,
            "error": self.error
        }


@dataclass
class InterventionReport:
    """
    Report generated when the Skill Broker blocks a proposed action.
    
    This report provides structured, human-readable feedback to inform
    the LLM's retry attempt. It is the core of Explainable Governance.
    """
    rule_id: str                           # ID of the rule that blocked the action
    blocked_skill: str                     # The skill that was blocked
    violation_summary: str                 # Human-readable explanation of the violation
    suggested_correction: Optional[str] = None  # Optional hint for the agent
    severity: str = "ERROR"                # ERROR, WARNING
    domain_context: Dict[str, Any] = field(default_factory=dict) # e.g., {"physical_constraint": "cannot elevate twice"}

    def to_prompt_string(self) -> str:
        """Format the report as a string suitable for injection into an LLM prompt."""
        s = f"- [{self.severity}] Your proposed action '{self.blocked_skill}' was BLOCKED.\n"
        s += f"  - Reason: {self.violation_summary}\n"
        if self.suggested_correction:
            s += f"  - Suggestion: {self.suggested_correction}\n"
        return s


@dataclass
class SkillBrokerResult:
    """Complete result from skill broker processing."""
    outcome: SkillOutcome
    skill_proposal: Optional[SkillProposal]
    approved_skill: Optional[ApprovedSkill]
    execution_result: Optional[ExecutionResult]
    validation_errors: List[str] = field(default_factory=list)
    retry_count: int = 0
