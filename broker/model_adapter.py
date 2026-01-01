"""
Model Adapter - Thin layer for multi-LLM support.

The Model Adapter has ONLY two responsibilities:
1. Parse LLM output → SkillProposal
2. Format rejection/retry → LLM prompt

NO domain logic should exist in adapters!

v0.3: Unified adapter with optional preprocessor for model-specific quirks.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
import re

from skill_types import SkillProposal


class ModelAdapter(ABC):
    """
    Abstract base class for model adapters.
    
    Each LLM type (Ollama, OpenAI, Anthropic) has its own adapter
    that normalizes output into SkillProposal format.
    """
    
    @abstractmethod
    def parse_output(self, raw_output: str, context: Dict[str, Any]) -> Optional[SkillProposal]:
        """
        Parse LLM output into SkillProposal.
        
        Args:
            raw_output: Raw text output from LLM
            context: Current context (for skill mapping)
            
        Returns:
            SkillProposal or None if parsing fails
        """
        pass
    
    @abstractmethod
    def format_retry_prompt(self, original_prompt: str, errors: List[str]) -> str:
        """
        Format retry prompt with validation errors.
        
        Args:
            original_prompt: The original prompt sent to LLM
            errors: List of validation errors
            
        Returns:
            Formatted retry prompt
        """
        pass


class UnifiedAdapter(ModelAdapter):
    """
    Unified adapter supporting all models with optional preprocessor.
    
    This replaces the need for separate OllamaAdapter, OpenAIAdapter, etc.
    Model-specific quirks (like DeepSeek's <think> tags) are handled via preprocessor.
    
    Usage:
        # Standard models (Llama, Gemma, GPT-OSS)
        adapter = UnifiedAdapter()
        
        # DeepSeek with <think> tag removal
        adapter = UnifiedAdapter(preprocessor=deepseek_preprocessor)
    """
    
    # Valid skill names (domain-agnostic, loaded from context or config)
    DEFAULT_VALID_SKILLS = {"buy_insurance", "elevate_house", "relocate", "do_nothing"}
    
    # Skill name mappings from decision codes (legacy support)
    SKILL_MAP_NON_ELEVATED = {
        "1": "buy_insurance",
        "2": "elevate_house",
        "3": "relocate",
        "4": "do_nothing"
    }
    
    SKILL_MAP_ELEVATED = {
        "1": "buy_insurance",
        "2": "relocate",
        "3": "do_nothing"
    }
    
    def __init__(
        self,
        preprocessor: Optional[Callable[[str], str]] = None,
        valid_skills: Optional[set] = None
    ):
        """
        Initialize unified adapter.
        
        Args:
            preprocessor: Optional function to preprocess raw output
                          (e.g., strip <think> tags for DeepSeek)
            valid_skills: Optional set of valid skill names
        """
        self.preprocessor = preprocessor or (lambda x: x)
        self.valid_skills = valid_skills or self.DEFAULT_VALID_SKILLS
    
    def parse_output(self, raw_output: str, context: Dict[str, Any]) -> Optional[SkillProposal]:
        """
        Parse LLM output into SkillProposal.
        
        Supports multiple output formats:
        - New format: 'Skill: buy_insurance'
        - Decision format: 'Decision: buy_insurance'
        - Legacy format: 'Final Decision: 1' or 'Final Decision: buy_insurance'
        """
        # Apply preprocessor (e.g., remove <think> tags)
        cleaned_output = self.preprocessor(raw_output)
        
        agent_id = context.get("agent_id", "unknown")
        is_elevated = context.get("is_elevated", False)
        
        # Extract reasoning
        threat_appraisal = ""
        coping_appraisal = ""
        skill_name = None
        
        lines = cleaned_output.strip().split('\n')
        for line in lines:
            line = line.strip()
            
            # Format 1: "Skill:" or "Decision:" (new format)
            if line.lower().startswith("skill:") or (line.lower().startswith("decision:") and not skill_name):
                decision_text = line.split(":", 1)[1].strip().lower() if ":" in line else ""
                for skill in self.valid_skills:
                    if skill in decision_text:
                        skill_name = skill
                        break
            
            # Extract PMT reasoning
            elif line.lower().startswith("threat appraisal:"):
                threat_appraisal = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line.lower().startswith("coping appraisal:"):
                coping_appraisal = line.split(":", 1)[1].strip() if ":" in line else ""
            
            # Format 2: "Final Decision:" (legacy format)
            elif line.lower().startswith("final decision:") and not skill_name:
                decision_text = line.split(":", 1)[1].strip().lower() if ":" in line else ""
                
                # Try to find skill name directly
                for skill in self.valid_skills:
                    if skill in decision_text:
                        skill_name = skill
                        break
                
                # Fallback: try to find digit for legacy code mapping
                if not skill_name:
                    for char in decision_text:
                        if char.isdigit():
                            skill_map = self.SKILL_MAP_ELEVATED if is_elevated else self.SKILL_MAP_NON_ELEVATED
                            skill_name = skill_map.get(char, "do_nothing")
                            break
        
        # Default to do_nothing if nothing found
        if not skill_name:
            skill_name = "do_nothing"
        
        return SkillProposal(
            skill_name=skill_name,
            agent_id=agent_id,
            reasoning={
                "threat": threat_appraisal,
                "coping": coping_appraisal
            },
            confidence=1.0,
            raw_output=raw_output
        )
    
    def format_retry_prompt(self, original_prompt: str, errors: List[str]) -> str:
        """Format retry prompt with validation errors."""
        error_text = ", ".join(errors)
        return f"""Your previous response was flagged for the following issues:
{error_text}

Please reconsider your decision and respond again.

{original_prompt}"""


# =============================================================================
# PREPROCESSORS for model-specific quirks
# =============================================================================

def deepseek_preprocessor(text: str) -> str:
    """
    Preprocessor for DeepSeek models.
    Removes <think>...</think> reasoning tags.
    """
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()


def json_preprocessor(text: str) -> str:
    """
    Preprocessor for models that may return JSON.
    Extracts text content from JSON if present.
    """
    import json
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            # Look for common fields
            for key in ['response', 'output', 'text', 'content']:
                if key in data:
                    return str(data[key])
        return text
    except json.JSONDecodeError:
        return text


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_adapter(model_name: str) -> ModelAdapter:
    """
    Get the appropriate adapter for a model.
    
    Uses UnifiedAdapter with model-specific preprocessor if needed.
    """
    model_lower = model_name.lower()
    
    # DeepSeek models use <think> tags
    if 'deepseek' in model_lower:
        return UnifiedAdapter(preprocessor=deepseek_preprocessor)
    
    # All other models use standard adapter
    # (Llama, Gemma, GPT-OSS, OpenAI, Anthropic, etc.)
    return UnifiedAdapter()


# =============================================================================
# LEGACY ALIASES (for backward compatibility)
# =============================================================================

class OllamaAdapter(UnifiedAdapter):
    """Alias for UnifiedAdapter (backward compatibility)."""
    pass


class OpenAIAdapter(UnifiedAdapter):
    """Alias for UnifiedAdapter (backward compatibility)."""
    pass
