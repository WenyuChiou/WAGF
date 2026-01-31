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
import os
from pathlib import Path
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
from broker.utils.agent_config import load_agent_config

# ... (Previous code)

# Global instance - modify this to change default behavior
def _load_global_config() -> LLMConfig:
    try:
        # Load agent_types.yaml via helper
        config = load_agent_config()
        
        # Access global_config.llm using .get("global_config")
        # Note: AgentTypeConfig.get() works for any top-level key
        global_llm = config.get("global_config").get("llm", {})
        
        return LLMConfig(
            temperature=global_llm.get("temperature"), 
            top_p=global_llm.get("top_p"),
            top_k=global_llm.get("top_k"),
            num_ctx=global_llm.get("num_ctx", 16384),
            num_predict=global_llm.get("num_predict", 2048),
            max_retries=global_llm.get("max_retries", 2)
        )
    except Exception as e:
        _LOGGER.warning(f"Could not load global LLM config: {e}. Using defaults.")
        return LLMConfig()

LLM_CONFIG = _load_global_config()

@dataclass
class LLMStats:
    """Statistics from a single LLM invocation."""
    retries: int = 0
    success: bool = True
    # LLM-level retry tracking (045-H)
    empty_content_retries: int = 0  # LLM returned empty content, retry triggered
    empty_content_failure: bool = False  # Terminal: empty after all retries exhausted

    def to_dict(self) -> Dict:
        return {
            "llm_retries": self.retries,
            "llm_success": self.success,
            "empty_content_retries": self.empty_content_retries,
            "empty_content_failure": self.empty_content_failure
        }


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


def _invoke_ollama_direct(model: str, prompt: str, params: Dict[str, Any], verbose: bool) -> Tuple[str, LLMStats]:
    """
    Phase 46: Invoke Ollama direct via API to avoid LangChain/Python 3.14 issues
    and enable native JSON-mode.
    """
    import requests
    import json
    
    url = "http://localhost:11434/api/generate"
    
    # Standardize options — only include sampling params if explicitly set
    # (None / missing = use Ollama model default, e.g. temperature ~0.8)
    options = {
        "num_predict": params.get("num_predict", 2048),
        "num_ctx": params.get("num_ctx", 8192 if "8b" in model.lower() or "14b" in model.lower() else 4096),
    }
    if "temperature" in params:
        options["temperature"] = params["temperature"]
    if "top_p" in params:
        options["top_p"] = params["top_p"]
    if "top_k" in params:
        options["top_k"] = params["top_k"]
    
    # Phase 47: Global Disable of Strict JSON Mode
    # User Request: "Turn it off for all" to fix DeepSeek R1 <think> tokens.
    # We rely on the prompt to enforce JSON structure.
    
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": None, # DISABLED globally for Reasoning Model compatibility
        "options": options
    }
    
    try:
        # Increase timeout for 30B/32B models AND all DeepSeek R1 models (known to be slow)
        if any(x in model.lower() for x in ["27b", "30b", "32b", "70b", "deepseek"]):
            timeout = 600 # Extended to 10 minutes for DeepSeek R1 Thinking
        else:
            timeout = 120
        response = requests.post(url, json=data, timeout=timeout)
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('response', '')
            if verbose:
                _LOGGER.debug(f" [LLM:Direct] Model '{model}' responded successfully ({len(content)} chars).")
            return content, LLMStats(retries=0, success=True)
        else:
            _LOGGER.error(f" [LLM:Direct] Model '{model}' HTTP Error {response.status_code}: {response.text}")
            return "", LLMStats(retries=0, success=False)
    except Exception as e:
        _LOGGER.error(f" [LLM:Direct] Model '{model}' Request Exception: {e}")
        return "", LLMStats(retries=0, success=False)


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
    # Phase 0.3: Route to modern provider factory ONLY for known cloud providers
    # This prevents "gemma3:4b" from being split into provider="gemma3"
    KNOWN_PROVIDERS = ["gemini", "openai", "azure"]
    
    if ":" in model and not model.startswith("mock"):
        parts = model.split(":", 1)
        provider_type = parts[0].lower()
        
        # Only route to factory if it's a known cloud provider
        if provider_type in KNOWN_PROVIDERS:
            model_name = parts[1]
            
            # Build config dict for factory
            config = {
                "type": provider_type,
                "model": model_name
            }
            
            # Apply overrides if present (e.g. temperature)
            if overrides:
                config.update(overrides)
            
            return create_provider_invoke(config, verbose=verbose)


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

        # Remove 'model' from params if present (it's passed explicitly above)
        ollama_params.pop("model", None)

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
            
            # Phase 48: Increase retries for unstable DeepSeek models
            if "deepseek" in model.lower():
                max_llm_retries = max(max_llm_retries, 5)
                
            llm_retries = 0
            empty_content_retries = 0  # 045-H: Track empty content retries specifically
            current_prompt = prompt

            # Phase 46: Qwen3 models support /no_think to disable thinking mode
            # This prevents models from outputting <think>...</think> blocks
            if "qwen3" in model.lower() or "qwen-3" in model.lower():
                if "/no_think" not in current_prompt and "/think" not in current_prompt:
                    current_prompt = current_prompt + "\n/no_think"
            
            for attempt in range(max_llm_retries):
                try:
                    # Phase 46F: UNIVERSAL DIRECT API for ALL Ollama models
                    # This bypasses LangChain entirely and ensures:
                    # 1. Native JSON mode (format: "json") for strict output
                    # 2. Consistent behavior across all model families
                    # 3. Avoids Python 3.14 compatibility issues
                    # LangChain path is deprecated but preserved for potential cloud providers
                    content, stats = _invoke_ollama_direct(model, current_prompt, ollama_params, debug_llm)
                    
                    if debug_llm:
                        _LOGGER.debug(f" [LLM:Output] Raw Content: {repr(content[:200] if content else '')}...")
                    
                    # Phase 46: Strip Qwen3 thinking tokens before empty check
                    # Qwen3 models wrap reasoning in <think>...</think> tags
                    import re
                    stripped_content = content
                    if content:
                        # Remove thinking blocks to get actual response
                        stripped_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                        if debug_llm and stripped_content != content.strip():
                            _LOGGER.debug(f" [LLM:ThinkStrip] Removed thinking tokens, extracted: {repr(stripped_content[:100])}...")
                    
                    if stripped_content and stripped_content.strip():
                        return content, LLMStats(retries=llm_retries, success=True, empty_content_retries=empty_content_retries)  # Return full content for logging
                    else:
                        llm_retries += 1
                        empty_content_retries += 1  # 045-H: Track empty content retries
                        if attempt < max_llm_retries - 1:
                            if content and not stripped_content.strip():
                                _LOGGER.warning(f" [LLM:Retry] Model '{model}' returned ONLY thinking content. Appending 'Please continue'.")
                                current_prompt += " \nPlease continue and output the JSON."
                            else:
                                _LOGGER.warning(f" [LLM:Retry] Model '{model}' returned truly empty content. Retrying...")
                                current_prompt += " "
                        else:
                            _LOGGER.error(f" [LLM:Error] Model '{model}' returned empty content after {max_llm_retries} attempts.")
                            return "", LLMStats(retries=llm_retries, success=False, empty_content_retries=empty_content_retries, empty_content_failure=True)
                except Exception as e:
                    llm_retries += 1
                    _LOGGER.error(f" [LLM:Error] Exception during call to '{model}': {e}")
                    if attempt < max_llm_retries - 1:
                        current_prompt += " "
                        continue
                    return "", LLMStats(retries=llm_retries, success=False, empty_content_retries=empty_content_retries)
            return "", LLMStats(retries=llm_retries, success=False, empty_content_retries=empty_content_retries)
        
        return invoke
    except ImportError:
        _LOGGER.warning("langchain-ollama not found. Falling back to mock LLM.")
        return lambda p: ("Final Decision: do_nothing", LLMStats())
    except Exception as e:
        _LOGGER.warning(f"Falling back to mock LLM due to: {e}")
        return lambda p: ("Final Decision: do_nothing", LLMStats())


def create_provider_invoke(config: Dict[str, Any], verbose: bool = False) -> LLMInvokeFunc:
    """
    Creates an invocation function using the new v0.3 Provider Factory.
    This is the modern way to instantiate LLMs (Gemini, OpenAI, Ollama).
    
    Args:
        config: Provider configuration (type, model, temperature, etc.)
        verbose: Enable diagnostic logging
        
    Returns:
        A callable that takes prompt str and returns (content, LLMStats) tuple.
    """
    from providers.factory import create_provider
    provider = create_provider(config)
    
    def invoke(prompt: str) -> Tuple[str, LLMStats]:
        if verbose:
            _LOGGER.debug(f"\n [LLM:Input] {provider.provider_name}:{provider.config.model} Prompt begins: {repr(prompt[:100])}...")
        
        try:
            # Note: Provider handles its own internal configuration (temp, tokens)
            response = provider.invoke(prompt)
            
            # Map usage stats to framework standard
            stats = LLMStats(
                retries=0, 
                success=True
            )
            
            if verbose:
                _LOGGER.debug(f" [LLM:Output] Raw Content: {repr(response.content[:200])}...")
                
            return response.content, stats
        except Exception as e:
            _LOGGER.error(f" [LLM:Error] {provider.provider_name} call failed: {e}")
            return "", LLMStats(retries=0, success=False)
            
    return invoke


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


