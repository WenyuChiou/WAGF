"""
Core type definitions for Governed Broker Framework.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class OutcomeType(Enum):
    """Decision step outcomes."""
    EXECUTED = "EXECUTED"
    RETRY_SUCCESS = "RETRY_SUCCESS"
    UNCERTAIN = "UNCERTAIN"
    ABORTED = "ABORTED"


@dataclass
class DecisionRequest:
    """LLM's structured decision output."""
    action_code: str
    reasoning: Dict[str, str]  # e.g., {"threat": "...", "coping": "..."}
    raw_output: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_code": self.action_code,
            "reasoning": self.reasoning,
            "raw_output": self.raw_output[:500]
        }


@dataclass
class ValidationResult:
    """Result from a validator."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionRequest:
    """Intent-only action request (Step ④)."""
    agent_id: str
    action_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AdmissibleCommand:
    """System-validated command ready for execution (Step ⑤)."""
    agent_id: str
    action_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    admissibility_check: str = "PASSED"


@dataclass
class ExecutionResult:
    """Result from simulation engine execution (Step ⑥)."""
    success: bool
    state_changes: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class BrokerResult:
    """Complete result from broker processing."""
    outcome: OutcomeType
    action_request: Optional[ActionRequest]
    admissible_command: Optional[AdmissibleCommand]
    execution_result: Optional[ExecutionResult]
    validation_errors: List[str] = field(default_factory=list)
    retry_count: int = 0
