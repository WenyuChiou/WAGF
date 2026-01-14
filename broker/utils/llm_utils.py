"""
LLM Utilities - Shared model invocation methods.

Provides common logic for:
- Initializing LLM providers (e.g., ChatOllama)
- Standardized invocation with error handling
- Model-specific parameter tuning (e.g., num_predict)
- LLM-level retry tracking for audit

v2.0: invoke functions now return (content, stats) tuple for thread-safety.
"""
import logging
from typing import Callable, Dict, Tuple, Union
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)

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
    if model.lower().startswith("mock"):
        def mock_invoke(prompt: str) -> Tuple[str, LLMStats]:
            stats = LLMStats(retries=0, success=True)
            # Simple heuristic for mock responses
            if "buy_insurance" in prompt: decision = "buy_insurance"
            elif "relocate" in prompt: decision = "relocate"
            else: decision = "do_nothing"
            
            threat_level = "High" if "damage" in prompt.lower() else "Low"
            coping_level = "High" if "manage" in prompt.lower() else "Low"
            
            content = f"""<<<DECISION_START>>>
{{
  "threat_appraisal": {{
    "label": "{threat_level}",
    "reason": "I feel {threat_level.lower()} threat from the current situation."
  }},
  "coping_appraisal": {{
    "label": "{coping_level}",
    "reason": "I feel {coping_level.lower()} ability to cope."
  }},
  "decision": {1 if decision == "buy_insurance" else 3 if decision == "relocate" else 4}
}}
<<<DECISION_END>>>"""
            return content, stats
        return mock_invoke
    
    try:
        from langchain_ollama import ChatOllama
        
        # Default Ollama params - set to -1 (unlimited) by default
        # Users can override via agent_types.yaml llm_params
        ollama_params = {
            "num_predict": -1,  # Unlimited by default
            "num_ctx": 16384,   # Large context for complex prompts
        }
        
        # Apply overrides from configuration (takes priority)
        if overrides:
            ollama_params.update(overrides)
            
        llm = ChatOllama(model=model, **ollama_params)
        
        def invoke(prompt: str) -> Tuple[str, LLMStats]:
            # Strict control via verbose arg
            debug_llm = verbose

            if debug_llm:
                # Log a small snippet of the prompt
                _LOGGER.debug(f"\n [LLM:Input] (len={len(prompt)}) Prompt begins: {repr(prompt[:100])}...")
            
            # Retry loop for empty responses (common with DeepSeek reasoning models)
            max_llm_retries = 3
            llm_retries = 0
            for attempt in range(max_llm_retries):
                try:
                    response = llm.invoke(prompt)
                    content = response.content
                    
                    if debug_llm:
                        _LOGGER.debug(f" [LLM:Output] Raw Content: {repr(content[:200] if content else '')}...")
                    
                    if content and content.strip():
                        # Success - return content and stats
                        return content, LLMStats(retries=llm_retries, success=True)
                    else:
                        llm_retries += 1
                        if attempt < max_llm_retries - 1:
                            _LOGGER.warning(f" [LLM:Retry] Model '{model}' returned empty content. Retrying ({attempt+1}/{max_llm_retries})...")
                        else:
                            _LOGGER.error(f" [LLM:Error] Model '{model}' returned empty content after {max_llm_retries} attempts.")
                            _LOGGER.error(f"Empty raw output from {model} after {max_llm_retries} attempts")
                            return "", LLMStats(retries=llm_retries, success=False)
                except Exception as e:
                    llm_retries += 1
                    _LOGGER.error(f" [LLM:Error] Exception during call to '{model}': {e}")
                    _LOGGER.exception(f"Exception during LLM invoke for {model}")
                    if attempt < max_llm_retries - 1:
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


