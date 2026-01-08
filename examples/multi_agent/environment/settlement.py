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
        # Helper to get state
        def get_state(agent):
            return getattr(agent, 'state', agent)

        ins_state = get_state(insurance)
        gov_state = get_state(government)

        # 1. Flood Event
        flood_event = self.simulate_flood_event(year)
        flood_occurred = flood_event is not None
        severity = flood_event.severity if flood_occurred else 0.0
        
        total_damage = 0.0
        total_claims = 0.0
        
        # 2. Collect Premiums
        # Check has_insurance on household state
        active_policies = 0
        for h in households:
            h_state = get_state(h)
            if getattr(h_state, 'has_insurance', False):
                active_policies += 1
                
        premium_income = active_policies * ins_state.premium_rate * 250_000 
        
        ins_state.premium_collected += premium_income
        ins_state.total_policies = active_policies
        
        # 3. Calculate Damages & Claims (If Flood)
        if flood_occurred:
            for hh in households:
                h_state = get_state(hh)
                outcome = self.catastrophe.calculate_financials(
                    h_state.id, h_state, flood_event, ins_state
                )
                
                # Update Household
                h_state.cumulative_damage += outcome['damage_amount']
                h_state.cumulative_oop += outcome['oop_cost']
                
                # Update Memory
                if hasattr(hh, 'memory'):
                    event_desc = (f"Year {year}: Flood severity {severity:.2f}, "
                                 f"Damage ${outcome['damage_amount']:,.0f}, "
                                 f"Payout ${outcome['payout_amount']:,.0f}")
                    hh.memory.add_episodic(event_desc, importance=severity, year=year, tags=['flood'])
                    
                    if outcome['payout_amount'] > 0:
                         h_state.trust_in_insurance = min(1.0, h_state.trust_in_insurance + 0.1)
                    elif h_state.has_insurance and outcome['damage_amount'] > 0:
                         h_state.trust_in_insurance = max(0.0, h_state.trust_in_insurance - 0.2)
                
                # Track Totals
                total_damage += outcome['damage_amount']
                total_claims += outcome['payout_amount']
        
        # 4. Update Insurance Financials
        ins_state.claims_paid += total_claims
        ins_state.risk_pool = ins_state.risk_pool + premium_income - total_claims
        
        # 5. Generate Report
        report = SettlementReport(
            year=year,
            flood_occurred=flood_occurred,
            flood_severity=severity,
            total_damage=total_damage,
            total_claims=total_claims,
            total_subsidies=500_000 - gov_state.budget_remaining, 
            insurance_loss_ratio=ins_state.loss_ratio,
            government_budget_remaining=gov_state.budget_remaining
        )
        
        return report
