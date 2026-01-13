"""
LLM Utilities - Shared model invocation methods.

Provides common logic for:
- Initializing LLM providers (e.g., ChatOllama)
- Standardized invocation with error handling
- Model-specific parameter tuning (e.g., num_predict)
"""
import logging
from typing import Callable, Optional

_LOGGER = logging.getLogger(__name__)

def create_llm_invoke(model: str, verbose: bool = False) -> Callable[[str], str]:
    """
    Creates an invocation function for a given model using LangChain-Ollama.
    Includes robust error collection and diagnostic logging.
    """
    # Simple Mock for testing if model starts with 'mock'
    if model.lower().startswith("mock"):
        def mock_invoke(prompt: str) -> str:
            # Simple heuristic for mock responses
            if "buy_insurance" in prompt: decision = "buy_insurance"
            elif "relocate" in prompt: decision = "relocate"
            else: decision = "do_nothing"
            
            threat_level = "High" if "damage" in prompt.lower() else "Low"
            coping_level = "High" if "manage" in prompt.lower() else "Low"
            
            return f"""Threat Appraisal: {threat_level} because I feel {threat_level.lower()} threat from flood risks.
Coping Appraisal: {coping_level} because I feel {coping_level.lower()} ability to cope.
Final Decision: {decision}"""
        return mock_invoke
    
    try:
        from langchain_ollama import ChatOllama
        
        # Increase num_predict for DeepSeek models to accommodate <think> tags
        # Also include gpt-oss which models after reasoning models
        num_predict = 2048 if any(m in model.lower() for m in ["deepseek", "gpt-oss", "r1"]) else 512
        
        llm = ChatOllama(model=model, num_predict=num_predict)
        
        def invoke(prompt: str) -> str:
            import os
            debug_llm = os.getenv("LLM_DEBUG") == "1"

            if debug_llm:
                # Log a small snippet of the prompt
                print(f"\n [LLM:Input] (len={len(prompt)}) Prompt begins: {repr(prompt[:100])}...")
            
            # Retry loop for empty responses (common with DeepSeek reasoning models)
            max_llm_retries = 3
            for attempt in range(max_llm_retries):
                try:
                    response = llm.invoke(prompt)
                    content = response.content
                    
                    if debug_llm:
                        print(f" [LLM:Output] Raw Content: {repr(content[:200] if content else '')}...")
                    
                    if content and content.strip():
                        return content
                    else:
                        if attempt < max_llm_retries - 1:
                            print(f" [LLM:Retry] Model '{model}' returned empty content. Retrying ({attempt+1}/{max_llm_retries})...")
                        else:
                            print(f" [LLM:Error] Model '{model}' returned empty content after {max_llm_retries} attempts.")
                            _LOGGER.error(f"Empty raw output from {model} after {max_llm_retries} attempts")
                            return ""
                except Exception as e:
                    print(f" [LLM:Error] Exception during call to '{model}': {e}")
                    _LOGGER.exception(f"Exception during LLM invoke for {model}")
                    if attempt < max_llm_retries - 1:
                        continue
                    return ""
            return ""
        
        return invoke
    except ImportError:
        print("Warning: langchain-ollama not found. Falling back to mock LLM.")
        return lambda p: "Final Decision: do_nothing"
    except Exception as e:
        print(f"Warning: Falling back to mock LLM due to: {e}")
        return lambda p: "Final Decision: do_nothing"
