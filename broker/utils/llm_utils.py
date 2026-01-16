"""
LLM Utilities - Shared model invocation methods.

Provides common logic for:
- Initializing LLM providers (e.g., ChatOllama)
- Standardized invocation with error handling
- Model-specific parameter tuning (e.g., num_predict)
- LLM-level retry tracking for audit

v2.0: invoke functions now return (content, stats) tuple for thread-safety.
v2.1: Added global LLM_CONFIG for configurable parameters.
"""
import logging
from typing import Callable, Dict, Tuple, Union, Optional, Any
from dataclasses import dataclass, field

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# Global LLM Configuration (can be modified before creating invoke functions)
# =============================================================================
@dataclass
class LLMConfig:
    """
    Global configuration for LLM parameters.

    Modify these values before calling create_llm_invoke() to customize behavior.
    Set a value to None to use Ollama's default.

    Example:
        from broker.utils.llm_utils import LLM_CONFIG
        LLM_CONFIG.temperature = 1.0
        LLM_CONFIG.top_p = 0.95
    """
    # Sampling parameters (None = use Ollama default)
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None

    # Context/generation limits
    num_predict: int = -1      # -1 = unlimited
    num_ctx: int = 16384       # Context window size

    # Provider selection
    use_chat_api: bool = False  # False = OllamaLLM (completion), True = ChatOllama (chat)

    # Retry settings (Phase 40: Configurable)
    max_retries: int = 2

    def to_ollama_params(self) -> Dict[str, Any]:
        """Convert config to Ollama parameter dict, excluding None values."""
        params = {
            "num_predict": self.num_predict,
            "num_ctx": self.num_ctx,
        }
        # Only include sampling params if explicitly set
        if self.temperature is not None:
            params["temperature"] = self.temperature
        if self.top_p is not None:
            params["top_p"] = self.top_p
        if self.top_k is not None:
            params["top_k"] = self.top_k
        return params


# Global instance - modify this to change default behavior
LLM_CONFIG = LLMConfig()

@dataclass
class LLMStats:
    """Statistics from a single LLM invocation."""
    retries: int = 0
    success: bool = True
    
    def to_dict(self) -> Dict:
        return {"llm_retries": self.retries, "llm_success": self.success}


# =============================================================================
# Abstract LLM Provider Interface (Phase 25 PR7)
# =============================================================================
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    Enables multi-provider support (Ollama, OpenAI, Anthropic, etc.)
    without changing broker code.
    """
    
    @abstractmethod
    def invoke(self, prompt: str) -> Tuple[str, LLMStats]:
        """
        Invoke the LLM and return (content, stats) tuple.
        
        Args:
            prompt: The input prompt string
            
        Returns:
            Tuple of (response_content, LLMStats)
        """
        ...
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        ...


# Type alias for the invoke function signature (legacy compatibility)
LLMInvokeFunc = Callable[[str], Tuple[str, LLMStats]]


def create_llm_invoke(model: str, verbose: bool = False, overrides: Optional[Dict[str, Any]] = None) -> LLMInvokeFunc:
    """
    Creates an invocation function for a given model using LangChain-Ollama.
    Includes robust error collection and diagnostic logging.
    
    Args:
        model: Model identifier
        verbose: Enable diagnostic logging
        overrides: Optional parameter overrides (num_predict, num_ctx, etc.)
    
    Returns:
        A callable that takes prompt str and returns (content, LLMStats) tuple.
    """
    # Simple Mock for testing if model starts with 'mock'
    # This mock is domain-agnostic and returns a generic decision format
    if model.lower().startswith("mock"):
        def mock_invoke(prompt: str) -> Tuple[str, LLMStats]:
            import re
            stats = LLMStats(retries=0, success=True)

            # Extract available options from prompt (e.g., "1. Action A", "2. Action B")
            # This makes the mock work with any experiment's options
            option_pattern = r'(\d+)\.\s+\w+'
            options = re.findall(option_pattern, prompt)

            # Default to option "1" if options found, otherwise "1"
            decision_id = options[0] if options else "1"

            # Generic appraisal levels based on prompt keywords
            # These keywords are domain-agnostic
            threat_level = "M"  # Medium as default
            coping_level = "M"
            if any(word in prompt.lower() for word in ["severe", "danger", "critical", "damage", "loss"]):
                threat_level = "H"
            if any(word in prompt.lower() for word in ["safe", "secure", "protected", "capable"]):
                coping_level = "H"

            content = f"""<<<DECISION_START>>>
{{
  "threat_appraisal": {{
    "label": "{threat_level}",
    "reason": "Mock assessment of threat level."
  }},
  "coping_appraisal": {{
    "label": "{coping_level}",
    "reason": "Mock assessment of coping ability."
  }},
  "decision": {decision_id}
}}
<<<DECISION_END>>>"""
            return content, stats
        return mock_invoke
    
    try:
        from langchain_ollama import ChatOllama
        from langchain_ollama import OllamaLLM

        # Build params from global config
        ollama_params = LLM_CONFIG.to_ollama_params()

        # Apply any runtime overrides
        if overrides:
            ollama_params.update(overrides)

        # Select provider based on config
        if LLM_CONFIG.use_chat_api:
            _LOGGER.info(f" [LLM:Init] Using ChatOllama for model: {model}")
            llm = ChatOllama(model=model, **ollama_params)
        else:
            _LOGGER.info(f" [LLM:Init] Using OllamaLLM for model: {model}")
            llm = OllamaLLM(model=model, **ollama_params)
        
        def invoke(prompt: str) -> Tuple[str, LLMStats]:
            debug_llm = verbose

            if debug_llm:
                _LOGGER.debug(f"\n [LLM:Input] (len={len(prompt)}) Prompt begins: {repr(prompt[:100])}...")
            
            # Phase 40: Use global or override retry limit
            max_llm_retries = overrides.get("max_retries", LLM_CONFIG.max_retries) if overrides else LLM_CONFIG.max_retries
            llm_retries = 0
            current_prompt = prompt
            
            for attempt in range(max_llm_retries):
                try:
                    response = llm.invoke(current_prompt)
                    
                    # Handle return type difference: ChatOllama -> Message, OllamaLLM -> str
                    if hasattr(response, 'content'):
                        content = response.content
                    else:
                        content = str(response)
                    
                    if debug_llm:
                        _LOGGER.debug(f" [LLM:Output] Raw Content: {repr(content[:200] if content else '')}...")
                    
                    if content and content.strip():
                        return content, LLMStats(retries=llm_retries, success=True)
                    else:
                        llm_retries += 1
                        if attempt < max_llm_retries - 1:
                            _LOGGER.warning(f" [LLM:Retry] Model '{model}' returned empty content. Retrying...")
                            current_prompt += " " 
                        else:
                            _LOGGER.error(f" [LLM:Error] Model '{model}' returned empty content after {max_llm_retries} attempts.")
                            return "", LLMStats(retries=llm_retries, success=False)
                except Exception as e:
                    llm_retries += 1
                    _LOGGER.error(f" [LLM:Error] Exception during call to '{model}': {e}")
                    if attempt < max_llm_retries - 1:
                        current_prompt += " "
                        continue
                    return "", LLMStats(retries=llm_retries, success=False)
            return "", LLMStats(retries=llm_retries, success=False)
        
        return invoke
    except ImportError:
        _LOGGER.warning("langchain-ollama not found. Falling back to mock LLM.")
        return lambda p: ("Final Decision: do_nothing", LLMStats())
    except Exception as e:
        _LOGGER.warning(f"Falling back to mock LLM due to: {e}")
        return lambda p: ("Final Decision: do_nothing", LLMStats())


# =============================================================================
# LEGACY COMPATIBILITY (Deprecated - use tuple return directly)
# =============================================================================

# Thread-local storage for backward compatibility
_llm_stats = {"current_retries": 0, "current_success": True}

def get_llm_stats() -> dict:
    """
    DEPRECATED: Get the last LLM call's retry stats for audit logging.
    Prefer using the tuple return value from invoke directly.
    """
    return _llm_stats.copy()

def create_legacy_invoke(model: str, verbose: bool = False) -> Callable[[str], str]:
    """
    Creates a legacy invoke function that returns only content (not tuple).
    Updates global _llm_stats for backward compatibility.
    """
    tuple_invoke = create_llm_invoke(model, verbose)
    
    def legacy_invoke(prompt: str) -> str:
        global _llm_stats
        content, stats = tuple_invoke(prompt)
        _llm_stats = {"current_retries": stats.retries, "current_success": stats.success}
        return content
    
    return legacy_invoke


