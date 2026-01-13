
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from broker.components.context_builder import DynamicStateProvider, TieredContextBuilder, InteractionHub

# Mock Agents and InteractionHub
class MockAgent:
    def __init__(self, id, type="default"):
        self.id = id
        self.agent_type = type
        self.name = f"Agent_{id}"
        self.custom_attributes = {}
    
    def get_available_skills(self): return []
    def get_all_state(self): return {}

def test_dynamic_state_injection():
    print("--- Testing DynamicStateProvider ---")
    
    # 1. Setup
    whitelist = ["subsidy_level", "premium_rate"]
    provider = DynamicStateProvider(whitelist=whitelist)
    agent = MockAgent("Agent_1")
    agents = {"Agent_1": agent}
    
    # 2. Test Cases
    # Case A: Whitelisted variables should appear
    context_a = {}
    env_context_a = {"subsidy_level": 0.5, "premium_rate": 0.02, "secret_code": 999}
    provider.provide("Agent_1", agents, context_a, env_context=env_context_a)
    
    assert context_a.get("subsidy_level") == 0.5, "Failed to inject subsidy_level"
    assert context_a.get("premium_rate") == 0.02, "Failed to inject premium_rate"
    assert "secret_code" not in context_a, "Context pollution: secret_code injected"
    
    print("[PASS] DynamicStateProvider whitelist filtering works.")
    
    # 3. Test TieredContextBuilder Integration
    print("--- Testing TieredContextBuilder Integration ---")
    
    # Mock Hub
    class MockHub(InteractionHub):
        def __init__(self): 
            self.environment = None
        def build_tiered_context(self, *args): return {"personal": {"id": "Agent_1", "agent_type": "default"}}
        def get_spatial_context(self, *args): return {}
        def get_social_context(self, *args): return []

    hub = MockHub()
    builder = TieredContextBuilder(
        agents=agents, 
        hub=hub, 
        dynamic_whitelist=["active_tax", "flood_risk"]
    )
    
    # Build Context with env_context
    env_ctx = {"active_tax": 0.15, "flood_risk": "high", "ignored_var": "hidden"}
    ctx = builder.build("Agent_1", env_context=env_ctx)
    
    # Format Prompt to check variable flattening
    # We use a custom template that references the dynamic variable
    builder.prompt_templates["default"] = "Tax: {active_tax} | Risk: {flood_risk}"
    prompt = builder.format_prompt(ctx)
    
    # Assertions
    assert ctx.get("active_tax") == 0.15, "Builder failed to inject active_tax into context dict"
    assert "0.15" in prompt, "Builder failed to flatten active_tax into prompt"
    assert "high" in prompt, "Builder failed to flatten flood_risk into prompt"
    
    print("[PASS] TieredContextBuilder integration works.")
    print(f"Generated Prompt: {prompt}")

if __name__ == "__main__":
    try:
        test_dynamic_state_injection()
        print("\nAll dynamic context tests passed!")
    except AssertionError as e:
        print(f"\n[FAIL] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
