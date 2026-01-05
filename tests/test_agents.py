"""
Test Exp3 Agents

Verifies:
1. Household, Insurance, Government agent initialization.
2. State transitions.
3. Memory integration.
"""
import sys
import unittest

# Fix path
sys.path.insert(0, '.')
sys.path.insert(0, './examples/exp3_multi_agent')

from examples.exp3_multi_agent.agents import (
    HouseholdAgent, 
    InsuranceAgent, 
    GovernmentAgent
)

class TestExp3Agents(unittest.TestCase):
    
    def test_household(self):
        h = HouseholdAgent("H1", "MG_Owner", 30000, 250000)
        self.assertEqual(h.state.agent_type, "MG_Owner")
        self.assertFalse(h.state.has_insurance)
        
        # Test Decision Application
        h.apply_decision("buy_insurance", year=1)
        self.assertTrue(h.state.has_insurance)
        
        # Test Memory
        mem = h.memory.retrieve(top_k=5)
        self.assertTrue(any("buy_insurance" in str(m) for m in mem))
        
    def test_insurance(self):
        ins = InsuranceAgent()
        self.assertEqual(ins.state.premium_rate, 0.05)
        
        # Test Logic
        ins.state.claims_paid = 900
        ins.state.premium_collected = 1000
        self.assertEqual(ins.state.loss_ratio, 0.90)
        
        dec = ins.decide_strategy(year=1)
        self.assertEqual(dec, "raise_premium")
        self.assertGreater(ins.state.premium_rate, 0.05) # Should increase from 5%
        
    def test_government(self):
        gov = GovernmentAgent()
        self.assertEqual(gov.state.budget_remaining, 500_000)
        
        # Test Logic: Flood + Low Adoption -> Increase Subsidy
        gov.state.mg_adoption_rate = 0.10
        dec = gov.decide_policy(year=2, flood_occurred_prev_year=True)
        
        self.assertEqual(dec, "increase_subsidy")
        self.assertGreater(gov.state.subsidy_rate, 0.50)

if __name__ == '__main__':
    unittest.main()
