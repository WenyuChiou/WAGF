import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from broker.simulation.environment import TieredEnvironment
# Mock Agent
class MockAgent:
    def __init__(self, id, decision=None):
        self.id = id
        self.fixed_attributes = {"tract_id": "T001", "property_value": 100000}
        self.dynamic_state = {"budget": 1000.0, "house_elevation": 0.0}
        self.last_decision = decision # For pricing model

from broker.simulation.environment import TieredEnvironment
try:
    from examples.multi_agent.flood.world_models.disaster_model import DisasterModel
except ModuleNotFoundError:
    try:
        from examples.archive.ma_legacy.world_models.disaster_model import DisasterModel
    except ModuleNotFoundError:
        DisasterModel = None
# PricingModel removed as it was part of the single-agent demo cleanup

class TestWorldModels(unittest.TestCase):
    
    # Pricing Model test removed
        
    def test_disaster_model(self):
        if DisasterModel is None:
            self.skipTest("DisasterModel not available in this workspace.")
        print("\nTesting Disaster Model (Spatial)...")
        env = TieredEnvironment()
        model = DisasterModel(env)
        
        # Setup Environment
        env.set_local("T001", "paving_density", 1.0) # High paving doubles hazard impact
        
        # Scenario: Surge Level 5.0
        # Agent has 0 elevation.
        # Depth = (5.0 * (1+1.0)) - 0 = 10.0
        # Damage = 10 * 0.1 = 1.0 (100% loss)
        agents = [MockAgent("A1")]
        
        model.step(agents, surge_level=5.0)
        
        loss = agents[0].dynamic_state["last_damage"]
        print(f" Agent Loss (Full Damage): {loss}")
        self.assertEqual(loss, 100000.0)
        
        # Scenario 2: Agent Elevates house to 15.0
        agents[0].dynamic_state["house_elevation"] = 15.0
        # Depth = 10.0 - 15.0 = -5.0 -> 0 (No Flood)
        
        model.step(agents, surge_level=5.0)
        loss_safe = agents[0].dynamic_state["last_damage"]
        print(f" Agent Loss (Elevated): {loss_safe}")
        self.assertEqual(loss_safe, 0.0)

if __name__ == '__main__':
    unittest.main()
