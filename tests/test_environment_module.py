"""
Test Environment Modules (Exp3)

Verifies Catastrophe, Subsidy, and Settlement logic.
"""
import sys
import unittest
from dataclasses import dataclass, field
from typing import List

# Fix path to allow importing from examples
sys.path.insert(0, '.')
sys.path.insert(0, './examples/exp3_multi_agent')

from examples.exp3_multi_agent.environment import (
    CatastropheModule, 
    SubsidyModule, 
    SettlementModule,
    FloodEvent
)
from broker.memory import CognitiveMemory

# Mock Agents
@dataclass
class MockHousehold:
    id: str
    agent_type: str = "NMG_Owner"
    property_value: float = 300_000
    elevated: bool = False
    has_insurance: bool = False
    
    cumulative_damage: float = 0
    cumulative_oop: float = 0
    trust_in_insurance: float = 0.5
    
    memory: CognitiveMemory = field(default_factory=lambda: CognitiveMemory("MockH"))

@dataclass
class MockInsurance:
    premium_rate: float = 0.05
    payout_ratio: float = 1.0
    risk_pool: float = 1_000_000
    premium_collected: float = 0
    claims_paid: float = 0
    loss_ratio: float = 0.0
    total_policies: int = 0

@dataclass
class MockGovernment:
    budget_remaining: float = 500_000
    subsidy_rate: float = 0.50
    mg_priority: bool = True
    memory: CognitiveMemory = field(default_factory=lambda: CognitiveMemory("MockG"))


class TestEnvironment(unittest.TestCase):
    
    def setUp(self):
        self.catastrophe = CatastropheModule()
        self.subsidy = SubsidyModule()
        self.settlement = SettlementModule(seed=123)
        
    def test_catastrophe_damage(self):
        # 1. Base Damage
        damage_ratio = self.catastrophe.calculate_damage_ratio(severity=0.5, elevated=False)
        # 0.5^2 = 0.25 base, plus lognormal noise
        self.assertTrue(0.0 < damage_ratio < 1.0, f"Damage ratio {damage_ratio} out of bounds")
        
        # 2. Elevation Reduction
        damage_elevated = self.catastrophe.calculate_damage_ratio(severity=0.5, elevated=True)
        self.assertLess(damage_elevated, damage_ratio, "Elevation should reduce damage")
        
    def test_insurance_payout(self):
        agent = MockHousehold("H1", has_insurance=True)
        insurance = MockInsurance()
        event = FloodEvent(year=1, severity=0.8)
        
        result = self.catastrophe.calculate_financials(agent.id, agent, event, insurance)
        
        self.assertGreater(result["payout_amount"], 0)
        self.assertLess(result["oop_cost"], result["damage_amount"])
        
        # Deductible check
        # damage = payout + deductible (approx)
        implied_deductible = result["damage_amount"] - result["payout_amount"] - result["oop_cost"] 
        # Wait, oop = damage - payout. So damage - payout - oop = 0.
        # But payout = max(0, damage - 2000). 
        # So oop = damage - (damage - 2000) = 2000 (if damage > 2000).
        if result["damage_amount"] > 2000:
             self.assertAlmostEqual(result["oop_cost"], 2000, delta=1.0) # Should be just deductible if fully covered within limit
        
    def test_subsidy_calculation(self):
        gov = MockGovernment()
        
        # 1. NMG Case
        agent_nmg = MockHousehold("H_NMG", agent_type="NMG_Owner")
        res_nmg = self.subsidy.calculate_subsidy(agent_nmg, "elevate_house", gov)
        self.assertEqual(res_nmg["applied_rate"], 0.50)
        self.assertEqual(res_nmg["subsidy_amount"], 75_000) # 150k * 0.5
        
        # 2. MG Priority Case
        agent_mg = MockHousehold("H_MG", agent_type="MG_Owner")
        res_mg = self.subsidy.calculate_subsidy(agent_mg, "elevate_house", gov)
        self.assertEqual(res_mg["applied_rate"], 0.75) # 0.5 + 0.25 bonus
        self.assertEqual(res_mg["subsidy_amount"], 112_500)
        
        # 3. Budget Exhaustion
        gov.budget_remaining = 10_000
        res_poor_gov = self.subsidy.calculate_subsidy(agent_nmg, "elevate_house", gov)
        self.assertEqual(res_poor_gov["subsidy_amount"], 10_000)
        
    def test_settlement_process(self):
        # Setup
        households = [
            MockHousehold("H1", has_insurance=True),
            MockHousehold("H2", has_insurance=False)  
        ]
        insurance = MockInsurance()
        government = MockGovernment()
        
        # Force a flood
        self.settlement.flood_probability = 1.0 
        
        report = self.settlement.process_year(1, households, insurance, government)
        
        self.assertTrue(report.flood_occurred)
        self.assertGreater(report.total_damage, 0)
        self.assertGreater(report.total_claims, 0)
        
        # Verify H1 got paid, H2 didn't
        # Access H1 memory to see if event logged
        self.assertGreater(len(households[0].memory._episodic), 0)
        self.assertTrue("payout" in str(households[0].memory._episodic[0]).lower())
        
        # Verify Insurance Financials
        self.assertGreater(insurance.claims_paid, 0)
        self.assertEqual(insurance.total_policies, 1)

if __name__ == '__main__':
    unittest.main()
