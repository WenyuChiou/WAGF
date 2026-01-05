"""
Validator Factory - Dynamic loading of validators from configuration.

Enables domain-specific validator loading without code changes.
Validators are specified in domain YAML and loaded dynamically.
"""
from typing import Dict, List, Type, Any, Optional
from pathlib import Path

from .skill_validators import (
    SkillValidator,
    SkillAdmissibilityValidator,
    ContextFeasibilityValidator,
    InstitutionalConstraintValidator,
    EffectSafetyValidator,
    PMTConsistencyValidator
)


# Registry of available validators
VALIDATOR_REGISTRY: Dict[str, Type[SkillValidator]] = {
    "SkillAdmissibilityValidator": SkillAdmissibilityValidator,
    "ContextFeasibilityValidator": ContextFeasibilityValidator,
    "InstitutionalConstraintValidator": InstitutionalConstraintValidator,
    "EffectSafetyValidator": EffectSafetyValidator,
    "PMTConsistencyValidator": PMTConsistencyValidator,
    # Aliases for shorter names
    "Admissibility": SkillAdmissibilityValidator,
    "Feasibility": ContextFeasibilityValidator,
    "Constraint": InstitutionalConstraintValidator,
    "EffectSafety": EffectSafetyValidator,
    "PMT": PMTConsistencyValidator,
    # Legacy names from domain YAML
    "SchemaValidator": SkillAdmissibilityValidator,
    "PolicyValidator": InstitutionalConstraintValidator,
    "FeasibilityValidator": ContextFeasibilityValidator,
    "LeakageValidator": EffectSafetyValidator,
    "MemoryIntegrityValidator": EffectSafetyValidator,
    "FloodResponseValidator": PMTConsistencyValidator,
}


def register_validator(name: str, validator_class: Type[SkillValidator]) -> None:
    """
    Register a custom validator class.
    
    Use this to add domain-specific validators.
    
    Args:
        name: Name to register under
        validator_class: Validator class (must extend SkillValidator)
    """
    VALIDATOR_REGISTRY[name] = validator_class


def get_validator_class(name: str) -> Type[SkillValidator]:
    """
    Get validator class by name.
    
    Args:
        name: Validator name (from VALIDATOR_REGISTRY)
        
    Returns:
        Validator class
        
    Raises:
        KeyError: If validator not found
    """
    if name not in VALIDATOR_REGISTRY:
        available = list(VALIDATOR_REGISTRY.keys())
        raise KeyError(f"Validator '{name}' not found. Available: {available}")
    return VALIDATOR_REGISTRY[name]


def create_validator(name: str, **kwargs) -> SkillValidator:
    """
    Create a validator instance by name.
    
    Args:
        name: Validator name
        **kwargs: Additional arguments for validator constructor
        
    Returns:
        Validator instance
    """
    validator_class = get_validator_class(name)
    return validator_class(**kwargs) if kwargs else validator_class()


def create_validators_from_config(
    validator_names: List[str],
    skip_missing: bool = False
) -> List[SkillValidator]:
    """
    Create multiple validators from a list of names.
    
    Args:
        validator_names: List of validator names
        skip_missing: If True, skip unknown validators instead of raising error
        
    Returns:
        List of validator instances
    """
    validators = []
    for name in validator_names:
        try:
            validators.append(create_validator(name))
        except KeyError as e:
            if not skip_missing:
                raise
            # Log warning but continue
            print(f"Warning: {e}")
    return validators


def load_validators_from_domain(loader: "DomainConfigLoader") -> List[SkillValidator]:
    """
    Load validators specified in domain configuration.
    
    Args:
        loader: DomainConfigLoader instance
        
    Returns:
        List of validator instances
        
    Example:
        loader = DomainConfigLoader.from_file("config/domains/flood_adaptation.yaml")
        validators = load_validators_from_domain(loader)
    """
    validator_names = loader.get_validator_names()
    return create_validators_from_config(validator_names, skip_missing=True)


def get_default_validators() -> List[SkillValidator]:
    """
    Get the default set of validators for most use cases.
    
    Returns:
        List with all core validators
    """
    return [
        SkillAdmissibilityValidator(),
        ContextFeasibilityValidator(),
        InstitutionalConstraintValidator(),
        EffectSafetyValidator(),
        PMTConsistencyValidator(),
    ]


def list_available_validators() -> List[str]:
    """List all registered validator names."""
    return list(VALIDATOR_REGISTRY.keys())
