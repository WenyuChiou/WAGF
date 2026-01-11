"""
Disaster Model (Multi-Agent/Spatial).
Demonstrates a complex spatial World Model.

Simulates:
1. Environment: Hazard (Sea Level) & Tract (Paving).
2. Personal: Exposure (Elevation) & Vulnerability.
3. Interaction: Hazard + Exposure -> Damage.
"""
import random
from typing import Dict, Any, List
from simulation.environment import TieredEnvironment

class DisasterModel:
    def __init__(self, environment: TieredEnvironment):
        self.env = environment
        self.env.set_global("sea_level", 0.0) # Baseline
        
    def step(self, agents: List[Any], surge_level: float = 0.0):
        """
        Execute disaster logic.
        args:
            surge_level: Input forcing for this step (e.g., storm surge).
        """
        # 1. READ ENVIRONMENT
        sea_level = self.env.get_observable("global.sea_level")
        total_hazard = sea_level + surge_level
        
        # 2. CALCULATE DAMAGE PER AGENT
        for agent in agents:
            # Get fixed attributes (Location)
            tract_id = agent.fixed_attributes.get("tract_id", "T001")
            
            # Get local environment (Paving exacerbates flood)
            paving = self.env.get_observable(f"local.{tract_id}.paving_density", default=0.5)
            
            # Get Personal State (Elevation)
            elevation = agent.dynamic_state.get("house_elevation", 0.0)
            
            # LOGIC: Depth = (Hazard * Paving) - Elevation
            flood_depth = max(0, (total_hazard * (1 + paving)) - elevation)
            
            # LOGIC: Damage Ratio (Depth-Damage Curve)
            # Simplified: 10% damage per foot of depth
            damage_ratio = min(1.0, flood_depth * 0.1)
            
            # 3. UPDATE PERSONAL STATE
            # Financial Loss
            property_value = agent.fixed_attributes.get("property_value", 100000)
            loss = property_value * damage_ratio
            
            agent.dynamic_state["last_damage"] = loss
            agent.dynamic_state["cumulative_damage"] = \
                agent.dynamic_state.get("cumulative_damage", 0) + loss
