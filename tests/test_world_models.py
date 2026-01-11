import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation.environment import TieredEnvironment
# Mock Agent
class MockAgent:
    def __init__(self, id, decision=None):
        self.id = id
        self.fixed_attributes = {"tract_id": "T001", "property_value": 100000}
        self.dynamic_state = {"budget": 1000.0, "house_elevation": 0.0}
        self.last_decision = decision # For pricing model

from examples.single_agent.world_models.pricing_model import PricingModel
from examples.single_agent.world_models.disaster_model import DisasterModel

class TestWorldModels(unittest.TestCase):
    
    def test_pricing_model(self):
        print("\nTesting Pricing Model (Single-Agent Demo)...")
        env = TieredEnvironment()
        model = PricingModel(env)
        
        # Scenario: Bull Market + Buying Agent
        env.set_global("market_trend", "bull")
        agents = [MockAgent("A1", decision="buy")]
        
        # Step 1
        model.step(agents)
        
        # Check Environment Update (Price should rise)
        # Base 100 * 1.05 (Bull) * (1 + 0.001 Demand) ~= 105.1
        new_price = env.get_observable("global.market_price")
        print(f" New Market Price: {new_price}")
        self.assertGreater(new_price, 100.0)
        
        # Check Personal Update (Budget should decrease)
        updated_budget = agents[0].dynamic_state['budget']
        print(f" Agent Budget: {updated_budget}")
        self.assertLess(updated_budget, 1000.0)
        
    def test_disaster_model(self):
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
