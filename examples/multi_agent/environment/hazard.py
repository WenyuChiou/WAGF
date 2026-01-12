"""
Hazard Module

Loads and processes water depth data for flood simulation.

Data format (CSV):
- tract: Tract ID
- year: Simulation year
- depth_ft: Peak flood depth in feet

References:
- ABM_Summary.pdf: dt = (1/N_grid) * sum(max(depth_g,t))
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass


@dataclass
class FloodEvent:
    """Represents a flood event for a tract."""
    tract_id: str
    year: int
    depth_ft: float
    
    @property
    def severity(self) -> str:
        """Classify flood severity."""
        if self.depth_ft >= 4.0:
            return "SEVERE"
        elif self.depth_ft >= 2.0:
            return "MODERATE"
        elif self.depth_ft > 0:
            return "MINOR"
        return "NONE"


class HazardModule:
    """
    Load and query water depth data.
    
    Supports:
    - CSV loading (tract, year, depth_ft)
    - Synthetic depth generation
    - Effective depth calculation for elevated homes
    """
    
    def __init__(self, depth_data_path: Optional[Path] = None, seed: int = 42):
        """
        Initialize hazard module.
        
        Args:
            depth_data_path: Path to CSV with depth data. If None, use synthetic.
            seed: Random seed for synthetic generation.
        """
        self.rng = np.random.default_rng(seed)
        self.depth_data: Dict[str, Dict[int, float]] = {}  # {tract: {year: depth}}
        
        if depth_data_path and Path(depth_data_path).exists():
            self._load_csv(Path(depth_data_path))
        else:
            print("[HazardModule] No depth data provided, using synthetic generation")
    
    def _load_csv(self, path: Path) -> None:
        """Load depth data from CSV."""
        df = pd.read_csv(path)
        
        # Validate columns
        required = {"tract", "year", "depth_ft"}
        if not required.issubset(df.columns):
            raise ValueError(f"CSV must have columns: {required}")
        
        # Build lookup
        for _, row in df.iterrows():
            tract = str(row["tract"])
            year = int(row["year"])
            depth = float(row["depth_ft"])
            
            if tract not in self.depth_data:
                self.depth_data[tract] = {}
            self.depth_data[tract][year] = depth
        
        print(f"[HazardModule] Loaded {len(df)} depth records for {len(self.depth_data)} tracts")
    
    def get_tract_depth(self, tract_id: str, year: int, default: float = 0.0) -> float:
        """
        Get flood depth for a tract in a given year.
        
        Args:
            tract_id: Tract identifier
            year: Simulation year
            default: Default depth if no data
            
        Returns:
            Peak flood depth in feet
        """
        if tract_id in self.depth_data:
            return self.depth_data[tract_id].get(year, default)
        return default
    
    def generate_synthetic_depth(
        self, 
        tract_id: str, 
        year: int,
        flood_prob: float = 0.3,
        mean_depth: float = 2.0,
        std_depth: float = 1.5
    ) -> float:
        """
        Generate synthetic flood depth.
        
        Args:
            tract_id: Tract identifier
            year: Year (used for variation)
            flood_prob: Probability of flood occurring
            mean_depth: Mean depth when flood occurs
            std_depth: Std dev of depth
            
        Returns:
            Synthetic depth (0 if no flood)
        """
        # Use tract+year hash for reproducibility
        key = hash((tract_id, year)) % (2**31)
        self.rng = np.random.default_rng(key)
        
        if self.rng.random() < flood_prob:
            depth = max(0, self.rng.normal(mean_depth, std_depth))
            return round(depth, 2)
        return 0.0
    
    def get_effective_depth(self, base_depth: float, elevation_ft: float = 0.0) -> float:
        """
        Calculate effective depth after elevation.
        
        Formula: d_eff = max(d - elevation, 0)
        
        Args:
            base_depth: Raw flood depth
            elevation_ft: House elevation height
            
        Returns:
            Effective depth after elevation offset
        """
        return max(base_depth - elevation_ft, 0.0)
    
    def get_flood_event(self, tract_id: str, year: int, use_synthetic: bool = True) -> FloodEvent:
        """Get or generate a FloodEvent for tract/year."""
        depth = self.get_tract_depth(tract_id, year)
        
        if depth == 0.0 and use_synthetic:
            depth = self.generate_synthetic_depth(tract_id, year)
        
        return FloodEvent(tract_id=tract_id, year=year, depth_ft=depth)
    
    def get_all_flood_years(self, tract_id: str) -> List[int]:
        """Get all years with flood events for a tract."""
        if tract_id not in self.depth_data:
            return []
        return [y for y, d in self.depth_data[tract_id].items() if d > 0]


# =============================================================================
# DEPTH-DAMAGE CURVES (FEMA Standard)
# =============================================================================

def depth_damage_building(depth_ft: float) -> float:
    """
    Building damage ratio from depth (FEMA depth-damage curve).
    
    Args:
        depth_ft: Flood depth inside building
        
    Returns:
        Damage ratio (0-1)
    """
    if depth_ft <= 0:
        return 0.0
    elif depth_ft < 1:
        return 0.10 * depth_ft
    elif depth_ft < 2:
        return 0.10 + 0.15 * (depth_ft - 1)
    elif depth_ft < 4:
        return 0.25 + 0.10 * (depth_ft - 2)
    elif depth_ft < 8:
        return 0.45 + 0.10 * (depth_ft - 4)
    else:
        return min(0.85, 0.85 + 0.02 * (depth_ft - 8))


def depth_damage_contents(depth_ft: float) -> float:
    """
    Contents damage ratio from depth (FEMA depth-damage curve).
    
    Contents damage faster than building - furniture, appliances destroyed quickly.
    
    Args:
        depth_ft: Flood depth inside building
        
    Returns:
        Damage ratio (0-1)
    """
    if depth_ft <= 0:
        return 0.0
    elif depth_ft < 1:
        return 0.20 * depth_ft
    elif depth_ft < 2:
        return 0.20 + 0.20 * (depth_ft - 1)
    elif depth_ft < 4:
        return 0.40 + 0.15 * (depth_ft - 2)
    else:
        return min(0.90, 0.70 + 0.05 * (depth_ft - 4))


# =============================================================================
# VULNERABILITY MODULE
# =============================================================================

class VulnerabilityModule:
    """
    Calculate damage from hazard exposure.
    
    Combines:
    - Depth-damage curves
    - RCV (Replacement Cost Value)
    - Elevation offset
    """
    
    def __init__(self, elevation_height_ft: float = 5.0):
        """
        Args:
            elevation_height_ft: Standard elevation height for elevated homes
        """
        self.elevation_height = elevation_height_ft
    
    def calculate_damage(
        self,
        depth_ft: float,
        rcv_building: float,
        rcv_contents: float,
        is_elevated: bool = False
    ) -> Dict[str, float]:
        """
        Calculate building and contents damage.
        
        Args:
            depth_ft: Flood depth at location
            rcv_building: Building replacement cost
            rcv_contents: Contents replacement cost
            is_elevated: Whether home is elevated
            
        Returns:
            Dict with building_damage, contents_damage, total_damage
        """
        # Apply elevation offset
        effective_depth = depth_ft
        if is_elevated:
            effective_depth = max(0, depth_ft - self.elevation_height)
        
        # Calculate damage ratios
        bld_ratio = depth_damage_building(effective_depth)
        cnt_ratio = depth_damage_contents(effective_depth)
        
        # Calculate dollar amounts
        bld_damage = rcv_building * bld_ratio
        cnt_damage = rcv_contents * cnt_ratio
        
        return {
            "effective_depth": effective_depth,
            "building_damage": round(bld_damage, 2),
            "contents_damage": round(cnt_damage, 2),
            "total_damage": round(bld_damage + cnt_damage, 2),
            "building_ratio": round(bld_ratio, 4),
            "contents_ratio": round(cnt_ratio, 4)
        }
    
    def calculate_payout(
        self,
        damage: float,
        coverage_limit: float,
        deductible: float,
        payout_ratio: float = 0.80
    ) -> float:
        """
        Calculate insurance payout.
        
        Args:
            damage: Total damage amount
            coverage_limit: Maximum coverage
            deductible: Amount paid by policyholder first
            payout_ratio: Percentage of claim paid (e.g., 80%)
            
        Returns:
            Payout amount
        """
        covered_damage = max(0, min(damage, coverage_limit) - deductible)
        return round(covered_damage * payout_ratio, 2)
    
    def calculate_oop(
        self,
        total_damage: float,
        payout: float,
        subsidy: float = 0.0
    ) -> float:
        """
        Calculate out-of-pocket cost.
        
        Args:
            total_damage: Total damage
            payout: Insurance payout
            subsidy: Government subsidy
            
        Returns:
            Out-of-pocket cost
        """
        return max(0, round(total_damage - payout - subsidy, 2))


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Test hazard module
    hazard = HazardModule(seed=42)
    
    # Generate synthetic events
    for year in range(1, 11):
        event = hazard.get_flood_event("T001", year)
        if event.depth_ft > 0:
            print(f"Year {year}: {event.severity} flood ({event.depth_ft:.2f} ft)")
    
    # Test vulnerability
    vuln = VulnerabilityModule()
    
    # Non-elevated home
    damage = vuln.calculate_damage(
        depth_ft=3.5,
        rcv_building=300_000,
        rcv_contents=100_000,
        is_elevated=False
    )
    print(f"\nNon-elevated damage at 3.5ft: ${damage['total_damage']:,.0f}")
    
    # Elevated home (same depth)
    damage_elev = vuln.calculate_damage(
        depth_ft=3.5,
        rcv_building=300_000,
        rcv_contents=100_000,
        is_elevated=True
    )
    print(f"Elevated damage at 3.5ft: ${damage_elev['total_damage']:,.0f}")
    print(f"Reduction: {(1 - damage_elev['total_damage']/damage['total_damage'])*100:.0f}%")
