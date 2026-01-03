"""
Base Validator Interface.

All validators must implement this interface.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

from broker.legacy.types import DecisionRequest, ValidationResult


class BaseValidator(ABC):
    """
    Abstract base class for validators.
    
    Validators check LLM outputs for:
    - Schema compliance
    - Policy compliance
    - Feasibility
    - Theory consistency
    - Information leakage
    - Memory integrity
    """
    
    name: str = "BaseValidator"
    
    @abstractmethod
    def validate(self, request: DecisionRequest, context: Dict[str, Any]) -> ValidationResult:
        """
        Validate a decision request.
        
        Args:
            request: Parsed LLM output
            context: Bounded context for this step
            
        Returns:
            ValidationResult with valid=True/False and any errors
        """
        pass


class SchemaValidator(BaseValidator):
    """Validates LLM output against JSON schema."""
    
    name = "SchemaValidator"
    
    def __init__(self, required_fields: list = None):
        self.required_fields = required_fields or ["action_code", "reasoning"]
    
    def validate(self, request: DecisionRequest, context: Dict[str, Any]) -> ValidationResult:
        errors = []
        
        if not request.action_code:
            errors.append("Missing action_code")
        
        if not request.reasoning:
            errors.append("Missing reasoning")
        
        return ValidationResult(valid=len(errors) == 0, errors=errors)


class PolicyValidator(BaseValidator):
    """Validates against role-based access policy."""
    
    name = "PolicyValidator"
    
    def __init__(self, allowed_actions: list = None):
        self.allowed_actions = allowed_actions or []
    
    def validate(self, request: DecisionRequest, context: Dict[str, Any]) -> ValidationResult:
        errors = []
        
        if self.allowed_actions and request.action_code not in self.allowed_actions:
            errors.append(f"Action {request.action_code} not in allowed actions: {self.allowed_actions}")
        
        return ValidationResult(valid=len(errors) == 0, errors=errors)


class FeasibilityValidator(BaseValidator):
    """Validates action feasibility against constraints."""
    
    name = "FeasibilityValidator"
    
    def __init__(self, constraints: dict = None):
        self.constraints = constraints or {}
    
    def validate(self, request: DecisionRequest, context: Dict[str, Any]) -> ValidationResult:
        errors = []
        
        # Check action-specific constraints
        action = request.action_code
        if action in self.constraints:
            for constraint_name, constraint_fn in self.constraints[action].items():
                if not constraint_fn(context):
                    errors.append(f"Constraint failed: {constraint_name}")
        
        return ValidationResult(valid=len(errors) == 0, errors=errors)


class LeakageValidator(BaseValidator):
    """Ensures LLM output doesn't reference hidden state."""
    
    name = "LeakageValidator"
    
    def __init__(self, hidden_fields: list = None):
        self.hidden_fields = hidden_fields or []
    
    def validate(self, request: DecisionRequest, context: Dict[str, Any]) -> ValidationResult:
        errors = []
        
        raw = request.raw_output.lower()
        for field in self.hidden_fields:
            if field.lower() in raw:
                errors.append(f"Information leakage detected: {field}")
        
        return ValidationResult(valid=len(errors) == 0, errors=errors)


class MemoryIntegrityValidator(BaseValidator):
    """Ensures LLM cannot write to memory/state."""
    
    name = "MemoryIntegrityValidator"
    
    def validate(self, request: DecisionRequest, context: Dict[str, Any]) -> ValidationResult:
        errors = []
        
        # Check for memory write attempts in output
        forbidden = ["update memory", "set memory", "write to", "modify state"]
        raw = request.raw_output.lower()
        
        for phrase in forbidden:
            if phrase in raw:
                errors.append(f"Memory write attempt detected: {phrase}")
        
        return ValidationResult(valid=len(errors) == 0, errors=errors)
