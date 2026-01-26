"""
Disaster Models for Multi-Agent Simulation.

Provides FloodModel and DisasterModel for simulating flood events
with spatial damage calculations.
"""

import random
from dataclasses import dataclass
from typing import Dict, Any, List, Optional


@dataclass
class FloodOutcome:
    """Outcome of a flood event."""
    occurred: bool
    intensity: float  # 0.0 to 1.0
    impact_description: str


class FloodModel:
    """
    Simulates flood occurrences and their intensities.
    Can be configured for probabilistic or historical/scenario-based events.
    """

    def __init__(self, annual_probability: float = 0.2, seed: int = 42):
        self.annual_probability = annual_probability
        self.random = random.Random(seed)

    def step(self, year: int) -> FloodOutcome:
        """Determines if a flood occurs in the given year."""
        occurred = self.random.random() < self.annual_probability
        intensity = self.random.uniform(0.3, 1.0) if occurred else 0.0

        description = "No flood occurred."
        if occurred:
            if intensity > 0.8:
                description = "Severe flood event! Major damage reported."
            elif intensity > 0.5:
                description = "Moderate flood event. Some areas affected."
            else:
                description = "Minor flood event. Minimal impact."

        return FloodOutcome(
            occurred=occurred,
            intensity=intensity,
            impact_description=description
        )


class HistoricalFloodModel(FloodModel):
    """Scenario-based flood model using historical flood years."""

    def __init__(self, flood_years: Dict[int, float]):
        self.flood_years = flood_years

    def step(self, year: int) -> FloodOutcome:
        intensity = self.flood_years.get(year, 0.0)
        occurred = intensity > 0
        return FloodOutcome(
            occurred=occurred,
            intensity=intensity,
            impact_description=f"Historical event (Intensity={intensity})" if occurred else "No flood."
        )


class DisasterModel:
    """
    Spatial disaster model with tract-level damage calculations.

    Integrates with TieredEnvironment to compute flood depth and damage
    based on surge level, paving density, and house elevation.

    Damage Formula:
        depth = (surge_level * (1 + paving_density)) - house_elevation
        damage_ratio = min(depth * 0.1, 1.0)  # 10% per meter, max 100%
        loss = property_value * damage_ratio
    """

    def __init__(self, environment: Any, damage_rate: float = 0.1):
        """
        Initialize disaster model.

        Args:
            environment: TieredEnvironment instance for spatial data
            damage_rate: Damage per meter of flood depth (default: 0.1 = 10%/m)
        """
        self.environment = environment
        self.damage_rate = damage_rate

    def step(self, agents: List[Any], surge_level: float = 0.0) -> None:
        """
        Calculate flood damage for all agents.

        Args:
            agents: List of agents with fixed_attributes and dynamic_state
            surge_level: Storm surge level in meters
        """
        for agent in agents:
            # Get tract-level data
            tract_id = agent.fixed_attributes.get("tract_id", "T001")
            paving_density = self.environment.get_local(tract_id, "paving_density", 0.0)

            # Get agent state
            house_elevation = agent.dynamic_state.get("house_elevation", 0.0)
            property_value = agent.fixed_attributes.get("property_value", 100000)

            # Calculate effective flood depth
            # Higher paving density increases runoff and flood depth
            effective_surge = surge_level * (1.0 + paving_density)
            flood_depth = max(0.0, effective_surge - house_elevation)

            # Calculate damage (capped at 100%)
            damage_ratio = min(flood_depth * self.damage_rate, 1.0)
            loss = property_value * damage_ratio

            # Update agent state
            agent.dynamic_state["last_flood_depth"] = flood_depth
            agent.dynamic_state["last_damage_ratio"] = damage_ratio
            agent.dynamic_state["last_damage"] = loss
