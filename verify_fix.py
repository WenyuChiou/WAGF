import sys
import os
sys.path.insert(0, os.getcwd())

from broker.components.interaction_hub import InteractionHub
from broker.components.social_graph import NeighborhoodGraph
class MockAgent:
    def __init__(self, id):
        self.id = id
        self.agent_type = "household"
        self.custom_attributes = {}

def test_state_persistence():
    print("--- Verifying InteractionHub State Persistence ---")
    
    # 1. Create Agent with initial Custom Attributes
    agent = MockAgent(id="TestAgent")
    
    # Simulate loading from CSV (Initial State)
    # Trust starts at 0.5
    agent.custom_attributes = {"trust_in_insurance": 0.5}
    for k, v in agent.custom_attributes.items():
        setattr(agent, k, v)
        
    print(f"Initial State: Trust={agent.trust_in_insurance} (from custom_attributes)")

    # 2. Simulate Simulation Update (Year 1 Event)
    # Trust increases to 0.52
    agent.trust_in_insurance = 0.52
    print(f"Updated State (Runtime): Trust={agent.trust_in_insurance}")
    
    # 3. Build Context via Hub
    # This is where the bug was: it would revert to 0.5
    graph = NeighborhoodGraph(agent_ids=[agent.id])
    hub = InteractionHub(graph)
    agents = {agent.id: agent}
    
    context = hub.build_tiered_context(agent.id, agents)
    personal = context.get('personal', {})
    
    context_trust = personal.get('trust_in_insurance')
    print(f"Context Trust: {context_trust}")
    
    # 4. Assert
    if abs(context_trust - 0.52) < 0.001:
        print("✅ PASS: Context reflects updated runtime state.")
    else:
        print(f"❌ FAIL: Context reverted to {context_trust} (Expected 0.52). State persistence bug exists.")

if __name__ == "__main__":
    test_state_persistence()
