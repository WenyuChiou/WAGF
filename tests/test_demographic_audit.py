
import sys
import os

# Add root to python path to import broker modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from broker.utils.model_adapter import UnifiedAdapter

def test_demographic_audit():
    print("Testing Demographic Audit Logic...\n")
    # Point to the existing config to satisfy the constructor
    config_path = "examples/multi_agent/flood/config/ma_agent_types.yaml"
    adapter = UnifiedAdapter(config_path=config_path)
    
    # Mock Context with qualitative anchors
    context = {
        "narrative_persona": "You are a 2nd-generation resident managing a household of 4. High income.",
        "flood_experience_summary": "You experienced a flood in 2012. You received government assistance."
    }
    
    # Case 1: Strong Grounding (Cites generation and flood date)
    reasoning_strong = {
        "threat_appraisal": "Since I am a 2nd-generation resident, I know the risks.",
        "coping_appraisal": "I have high income so I can afford it.",
        "decision": "elevation"
    }
    
    print("--- Case 1: Strong Grounding ---")
    audit1 = adapter._audit_demographic_grounding(reasoning_strong, context)
    print(f"Score: {audit1['score']} (Expected: 1.0)")
    print(f"Cited: {audit1['cited_anchors']}")
    
    # Case 2: Weak Grounding (Generic)
    reasoning_weak = {
        "threat_appraisal": "Floods are bad.",
        "coping_appraisal": "I will do nothing.",
        "decision": "do_nothing"
    }
    
    print("\n--- Case 2: Weak Grounding ---")
    audit2 = adapter._audit_demographic_grounding(reasoning_weak, context)
    print(f"Score: {audit2['score']} (Expected: 0.0)")
    print(f"Cited: {audit2['cited_anchors']}")
    
    # Case 3: Partial Grounding
    reasoning_partial = {
        "threat_appraisal": "The flood in 2012 was scary.",
        "decision": "insurance"
    }
    
    print("\n--- Case 3: Partial Grounding ---")
    audit3 = adapter._audit_demographic_grounding(reasoning_partial, context)
    print(f"Score: {audit3['score']} (Expected: 0.5)")
    print(f"Cited: {audit3['cited_anchors']}")

if __name__ == "__main__":
    try:
        test_demographic_audit()
        print("\n[SUCCESS] Test completed.")
    except Exception as e:
        print(f"\n[FAILURE] {e}")
        import traceback
        traceback.print_exc()
