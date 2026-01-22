
from langchain_ollama import OllamaLLM
import yaml
from pathlib import Path
import sys

# 1. Check Group A (Baseline) Defaults
print("--- Group A (Baseline: LLMABMPMT-Final.py) ---")
llm_baseline = OllamaLLM(model="gemma3:4b")
print(f"Baseline Object: {llm_baseline}")
# defaults are often stored in valid_defaults or similar, or just distinct attributes
print(f"Explicit Temperature: {getattr(llm_baseline, 'temperature', 'Not Set (Uses Ollama Default)')}")
print(f"Explicit Top P: {getattr(llm_baseline, 'top_p', 'Not Set (Uses Ollama Default)')}")
print("Note: Ollama default is typically 0.8 temperature.\n")

# 2. Check Group B/C (Framework) Config
print("--- Group B/C (Framework: agent_types.yaml) ---")
try:
    with open('agent_types.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        global_llm = config.get('global_config', {}).get('llm', {})
        print(f"Global Config Temperature: {global_llm.get('temperature')}")
        print(f"Global Config Top P: {global_llm.get('top_p')}")
        
    # Check if household overrides it
    household_llm = config.get('household', {}).get('llm_params', {})
    print(f"Household Config Override: {household_llm}")
except Exception as e:
    print(f"Error loading yaml: {e}")
