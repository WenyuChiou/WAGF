"""
Pricing Model (Single-Agent Demo).
Demonstrates a non-disaster World Model: "Consumer Psychology".

Simulates:
1. Environment: Market Price & Supply.
2. Personal: Willingness to Pay & Budget.
3. Interaction: Price fluctuates based on Demand (Agent Decisions).
"""
import random
from typing import Dict, Any, List
from simulation.environment import TieredEnvironment

class PricingModel:
    def __init__(self, environment: TieredEnvironment):
        self.env = environment
        # Initialize Global Environment State
        self.env.set_global("market_price", 100.0)
        self.env.set_global("market_trend", "stable") # bull, bear, stable
        self.env.set_global("supply", 1000)
    
    def step(self, agents: List[Any]):
        """
        Execute one model step.
        1. Calculate Aggregate Demand from *previous* step decisions (or simulated).
        2. Update Market Price (Environment).
        3. Update Agent Budgets (Personal).
        """
        # 1. READ AGENT STATES (Aggregate Demand)
        # In a real sim, we'd count actua `buy` decisions. 
        # For this demo, we use a simulated 'desire' or recent action.
        total_demand = sum(1 for a in agents if getattr(a, 'last_decision', '') == 'buy')
        
        # 2. UPDATE ENVIRONMENT (Price Dynamics)
        current_price = self.env.get_observable("global.market_price")
        trend = self.env.get_observable("global.market_trend")
        
        # Trend influence
        trend_factor = 1.05 if trend == "bull" else (0.95 if trend == "bear" else 1.0)
        
        # Demand influence (scarcity)
        supply = self.env.get_observable("global.supply")
        demand_factor = 1.0 + (total_demand / max(supply, 1) * 0.1)
        
        new_price = current_price * trend_factor * demand_factor
        self.env.set_global("market_price", round(new_price, 2))
        
        # 3. UPDATE PERSONAL STATES (Budget Impact)
        # If agent bought last turn, deduct money.
        for agent in agents:
            if getattr(agent, 'last_decision', '') == 'buy':
                # Assuming dynamic_state is used
                current_budget = agent.dynamic_state.get('budget', 1000.0)
                agent.dynamic_state['budget'] = current_budget - current_price
