
import random
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class FloodOutcome:
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

# Example usage for scenario-based modeling
class HistoricalFloodModel(FloodModel):
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
