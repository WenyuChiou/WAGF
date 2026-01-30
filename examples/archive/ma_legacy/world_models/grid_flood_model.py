import numpy as np
import random
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

@dataclass
class GridFloodOutcome:
    year: int
    occurred: bool
    max_depth_m: float
    depth_distribution: Dict[str, float]  # grid_id -> depth_m
    impact_description: str

class GridFloodModel:
    """
    Manages flood events using a 2D grid and maps real agents to 'virtual' grid locations.
    
    Why: Real survey agents are distributed across various NJ ZIPs that don't overlap 
         with the specific Pompton River Basin (PRB) flood grid.
    How: We project real agents into the PRB grid by matching their reported 'flood history' 
         to high-hazard grid cells, preserving demographic identity while using real hazard data.
    """
    
    def __init__(self, historical_stats: Optional[Dict[int, Dict]] = None, seed: int = 42):
        self.random = random.Random(seed)
        # Summary derived from analysis of maxDepth2011-2023.asc
        self.historical_stats = historical_stats or {
            2011: {"max_m": 4.276, "prob_flood": 0.173},
            2012: {"max_m": 1.5, "prob_flood": 0.05},
            2023: {"max_m": 5.688, "prob_flood": 0.273}
        }
        
    def project_agents(self, agents: Dict[str, Any]) -> Dict[str, str]:
        """
        Maps agents to 'virtual' spatial zones: Severe, Moderate, Safe.
        Returns mapping of agent_id -> zone_id
        """
        mapping = {}
        for a_id, agent in agents.items():
            history = agent.fixed_attributes.get("flood_history", {})
            has_exp = history.get("has_experienced", False)
            
            # Logic: If they have experience, 80% chance they live in 'Severe/Moderate' zones
            if has_exp:
                if self.random.random() < 0.8:
                    zone = self.random.choice(["Severe", "Moderate"])
                else:
                    zone = "Safe"
            else:
                # No experience: 90% chance they live in 'Safe' or 'Minor' zones
                if self.random.random() < 0.9:
                    zone = self.random.choice(["Safe", "Minor"])
                else:
                    zone = "Moderate"
            
            mapping[a_id] = zone
            agent.dynamic_state["virtual_zone"] = zone
            
        return mapping

    def get_local_depth(self, zone: str, year: int) -> float:
        """
        Returns a depth in meters for a given zone and year based on historical distributions.
        """
        stats = self.historical_stats.get(year, {"max_m": 0.0, "prob_flood": 0.0})
        max_m = stats["max_m"]
        
        if max_m == 0:
            return 0.0
            
        if zone == "Severe":
            return self.random.uniform(max_m * 0.6, max_m)
        elif zone == "Moderate":
            return self.random.uniform(max_m * 0.2, max_m * 0.6)
        elif zone == "Minor":
            return self.random.uniform(0.01, max_m * 0.2)
        else: # Safe
            return 0.0

    def m_to_ft(self, m: float) -> float:
        """Convert meters (Grid unit) to feet (FEMA curve unit)."""
        return round(m * 3.28084, 3)

    def calculate_damage(self, depth_m: float, property_value: float, elevated: bool = False) -> Dict[str, float]:
        """
        Calculates damage using FEMA-inspired curves.
        Note: FEMA curves expect depth in feet.
        """
        from examples.multi_agent.flood.environment.hazard import VulnerabilityModule
        
        depth_ft = self.m_to_ft(depth_m)
        vuln = VulnerabilityModule()
        
        # We assume contents value is roughly 30% of building value if not specified
        rcv_building = property_value
        rcv_contents = property_value * 0.3
        
        damage = vuln.calculate_damage(
            depth_ft=depth_ft,
            rcv_building=rcv_building,
            rcv_contents=rcv_contents,
            is_elevated=elevated
        )
        return damage
