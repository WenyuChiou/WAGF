"""
Settlement Module (Environment Layer)

Orchestrates the annual settlement process:
1. Deteremines flood events.
2. Calculates damages and insurance claims (via CatastropheModule).
3. Processes mitigation costs and subsidies (via SubsidyModule).
4. Updates agent financial states and history.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import random

from .catastrophe import CatastropheModule, FloodEvent
from .subsidy import SubsidyModule

@dataclass
class SettlementReport:
    year: int
    flood_occurred: bool
    flood_severity: float
    total_damage: float
    total_claims: float
    total_subsidies: float
    insurance_loss_ratio: float
    government_budget_remaining: float

class SettlementModule:
    """
    Physics engine for the simulation.
    """
    
    def __init__(self, seed: int = 42):
        self.catastrophe = CatastropheModule(seed)
        self.subsidy = SubsidyModule()
        self.rng = random.Random(seed)
        
        # Simulation parameters
        self.flood_probability = 0.2  # Base probability
    
    def simulate_flood_event(self, year: int) -> Optional[FloodEvent]:
        """Determines if a flood occurs this year."""
        if self.rng.random() < self.flood_probability:
            # Severity 0.1 to 1.0
            severity = 0.5 + (self.rng.random() * 0.5) # Skewed towards severe? Or uniform?
            return FloodEvent(year, severity)
        return None
    
    def process_mitigation(self, 
                          household: Any, 
                          action: str, 
                          government: Any) -> Dict[str, float]:
        """
        Process a mitigation action (cost & subsidy).
        Updates Government budget immediately.
        Returns net cost to household.
        """
        result = self.subsidy.calculate_subsidy(household, action, government)
        
        if result['approved']:
            # Deduct from govt budget
            government.budget_remaining -= result['subsidy_amount']
            government.memory.add_episodic(
                f"Subsidy granted: ${result['subsidy_amount']:,.0f} for {action} to {household.id}",
                importance=0.2,
                year=government.memory.current_year if hasattr(government, 'memory') else 0
            )
            
        return result

    def process_year(self, 
                    year: int, 
                    households: List[Any], 
                    insurance: Any, 
                    government: Any) -> SettlementReport:
        """
        Runs the annual settlement physics.
        Updates all agent states in-place.
        """
        # 1. Flood Event
        flood_event = self.simulate_flood_event(year)
        flood_occurred = flood_event is not None
        severity = flood_event.severity if flood_occurred else 0.0
        
        total_damage = 0.0
        total_claims = 0.0
        
        # 2. Collect Premiums (Simplified: All active policies pay)
        # Assuming has_insurance means policy is active
        active_policies = sum(1 for h in households if getattr(h, 'has_insurance', False))
        premium_income = active_policies * insurance.premium_rate * 250_000 # Assuming fixed coverage basis? 
        # Or simple: insurance.premium_collected += ... (Agent logic might handle collection in Phase 1?)
        # Let's handle it here to be safe or verify.
        # Actually agent logic usually sets parameters, Env calculates flow. 
        insurance.premium_collected += premium_income
        insurance.total_policies = active_policies
        
        # 3. Calculate Damages & Claims (If Flood)
        if flood_occurred:
            for hh in households:
                outcome = self.catastrophe.calculate_financials(
                    hh.id, hh, flood_event, insurance
                )
                
                # Update Household
                hh.cumulative_damage += outcome['damage_amount']
                hh.cumulative_oop += outcome['oop_cost']
                
                # Update Memory
                if hasattr(hh, 'memory'):
                    event_desc = (f"Year {year}: Flood severity {severity:.2f}, "
                                 f"Damage ${outcome['damage_amount']:,.0f}, "
                                 f"Payout ${outcome['payout_amount']:,.0f}")
                    hh.memory.add_episodic(event_desc, importance=severity, year=year, tags=['flood'])
                    
                    if outcome['payout_amount'] > 0:
                         hh.trust_in_insurance = min(1.0, hh.trust_in_insurance + 0.1)
                    elif hh.has_insurance and outcome['damage_amount'] > 0:
                         # Claim denied or deductible too high?
                         hh.trust_in_insurance = max(0.0, hh.trust_in_insurance - 0.2)

                # Track Totals
                total_damage += outcome['damage_amount']
                total_claims += outcome['payout_amount']
        
        # 4. Update Insurance Financials
        insurance.claims_paid += total_claims
        insurance.risk_pool = insurance.risk_pool + premium_income - total_claims
        
        # 5. Generate Report
        report = SettlementReport(
            year=year,
            flood_occurred=flood_occurred,
            flood_severity=severity,
            total_damage=total_damage,
            total_claims=total_claims,
            total_subsidies=500_000 - government.budget_remaining, # Approx diff
            insurance_loss_ratio=insurance.loss_ratio,
            government_budget_remaining=government.budget_remaining
        )
        
        return report
