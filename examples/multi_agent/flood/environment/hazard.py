"""
Hazard Module (MA)

Uses PRB ASCII grid depth data (meters) as the primary source of hazard history.
Provides FEMA-style fine-grained depth-damage curves via the shared core module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, List, Tuple

import numpy as np

from .prb_loader import PRBGridLoader
from .depth_sampler import (
    DepthSampler,
    DepthCategory,
    PositionAssignment,
    sample_flood_depth_for_year,
)
from .year_mapping import YearMapping
from .vulnerability import VulnerabilityCalculator, FEET_PER_METER, VulnerabilityModule, depth_damage_building, depth_damage_contents


@dataclass
class FloodEvent:
    """Represents a flood event for a location."""
    year: int
    depth_m: float
    row: Optional[int] = None
    col: Optional[int] = None
    agent_id: Optional[str] = None  # For per-agent events

    @property
    def depth_ft(self) -> float:
        return self.depth_m * FEET_PER_METER

    @property
    def severity(self) -> str:
        """Classify flood severity based on depth in meters."""
        if self.depth_m >= 1.2:  # ~4 ft
            return "SEVERE"
        if self.depth_m >= 0.6:  # ~2 ft
            return "MODERATE"
        if self.depth_m > 0:
            return "MINOR"
        return "NONE"


class HazardModule:
    """
    Load and query PRB ASCII grid depth data (meters).

    Supports:
    - ASCII grid loading via PRBGridLoader
    - Sampling depth by agent flood experience (DepthSampler)
    - Fallback synthetic sampling when grid data is not available
    """

    def __init__(
        self,
        grid_dir: Optional[Path] = None,
        years: Optional[List[int]] = None,
        seed: int = 42,
    ):
        self.rng = np.random.default_rng(seed)
        self.grid_dir = Path(grid_dir) if grid_dir else None
        self.years = years
        self.loader: Optional[PRBGridLoader] = None
        self._cell_pools: Optional[Dict[DepthCategory, List[Tuple[int, int, float]]]] = None

        if self.grid_dir and self.grid_dir.exists():
            self.loader = PRBGridLoader(self.grid_dir, years=self.years)
            self.loader.load_all_years()

    def _ensure_cell_pools(self) -> None:
        if not self.loader:
            return
        if self._cell_pools is not None:
            return
        year = self.loader.sample_representative_year()
        self._cell_pools = self.loader.get_cells_by_depth_category(year)

    def get_depth_at_cell(self, year: int, row: int, col: int) -> Optional[float]:
        """Return grid depth in meters for a given cell."""
        if not self.loader:
            return None
        return self.loader.get_depth_at_cell(year, row, col)

    def assign_position(self, record) -> PositionAssignment:
        """Assign a flood position based on agent flood experience."""
        self._ensure_cell_pools()
        sampler = DepthSampler(seed=int(self.rng.integers(0, 1_000_000)), cell_pools=self._cell_pools)
        return sampler.assign_position(record)

    def get_flood_event(
        self,
        year: int,
        position: Optional[PositionAssignment] = None,
        row: Optional[int] = None,
        col: Optional[int] = None,
        year_severity: float = 1.0,
    ) -> FloodEvent:
        """
        Get flood event for a specific location or assignment.

        Priority:
        - explicit grid cell (row/col)
        - PositionAssignment (base_depth_m)
        - fallback synthetic depth (meters)
        """
        depth_m = 0.0

        if row is not None and col is not None and self.loader:
            depth = self.get_depth_at_cell(year, row, col)
            depth_m = depth if depth is not None else 0.0
        elif position is not None:
            depth_m = sample_flood_depth_for_year(position.base_depth_m, year_severity, self.rng)
        else:
            depth_m = self._sample_depth_from_grid(year) if self.loader else self._generate_synthetic_depth_m()

        return FloodEvent(year=year, depth_m=depth_m, row=row, col=col)

    def get_agent_flood_event(
        self,
        sim_year: int,
        grid_x: int,
        grid_y: int,
        agent_id: Optional[str] = None,
        year_mapping: Optional[YearMapping] = None,
    ) -> FloodEvent:
        """
        Get flood event for a specific agent's grid position.

        This method enables per-agent flood depth based on their location
        in the PRB grid, providing spatial heterogeneity in flood exposure.

        Args:
            sim_year: Simulation year (1, 2, 3, ...)
            grid_x: Agent's column in PRB grid (0-456)
            grid_y: Agent's row in PRB grid (0-410)
            agent_id: Optional agent identifier for logging
            year_mapping: Optional year mapping config (defaults to standard 2011 start)

        Returns:
            FloodEvent with agent-specific depth from their grid cell
        """
        # Convert simulation year to PRB data year
        if year_mapping:
            prb_year = year_mapping.sim_to_prb(sim_year)
        else:
            # Default mapping: sim year 1 = PRB 2011
            prb_year = 2010 + sim_year
            # Clamp to available years
            if prb_year > 2023:
                prb_year = 2011 + ((prb_year - 2011) % 13)

        # Query depth at agent's grid cell
        depth_m = 0.0
        if self.loader:
            depth = self.get_depth_at_cell(prb_year, grid_y, grid_x)
            depth_m = depth if depth is not None else 0.0
        else:
            # Fallback to synthetic if no grid data
            depth_m = self._generate_synthetic_depth_m()

        return FloodEvent(
            year=prb_year,
            depth_m=depth_m,
            row=grid_y,
            col=grid_x,
            agent_id=agent_id,
        )

    def get_flood_events_for_agents(
        self,
        sim_year: int,
        agent_positions: Dict[str, Tuple[int, int]],
        year_mapping: Optional[YearMapping] = None,
    ) -> Dict[str, FloodEvent]:
        """
        Get flood events for all agents based on their grid positions.

        Args:
            sim_year: Simulation year
            agent_positions: Dict mapping agent_id to (grid_x, grid_y)
            year_mapping: Optional year mapping config

        Returns:
            Dict mapping agent_id to FloodEvent
        """
        events = {}
        for agent_id, (grid_x, grid_y) in agent_positions.items():
            events[agent_id] = self.get_agent_flood_event(
                sim_year=sim_year,
                grid_x=grid_x,
                grid_y=grid_y,
                agent_id=agent_id,
                year_mapping=year_mapping,
            )
        return events

    def _sample_depth_from_grid(self, year: int) -> float:
        """
        Sample a depth (meters) from PRB grid data.

        If the requested year isn't available, uses a representative year.
        """
        if not self.loader:
            return 0.0

        if year in self.loader.grids:
            grid_year = year
        else:
            grid_year = self.loader.sample_representative_year()

        cells = self.loader.get_cells_by_depth_category(grid_year)
        all_cells = []
        for pool in cells.values():
            all_cells.extend(pool)

        if not all_cells:
            return 0.0

        idx = int(self.rng.integers(0, len(all_cells)))
        return float(all_cells[idx][2])

    def _generate_synthetic_depth_m(
        self,
        flood_prob: float = 0.3,
        mean_depth_m: float = 0.6,
        std_depth_m: float = 0.45,
    ) -> float:
        """Generate synthetic flood depth in meters."""
        if self.rng.random() < flood_prob:
            depth = max(0, self.rng.normal(mean_depth_m, std_depth_m))
            return round(float(depth), 3)
        return 0.0


if __name__ == "__main__":
    hazard = HazardModule(seed=42)
    event = hazard.get_flood_event(year=1)
    print(f"Year 1: {event.severity} flood ({event.depth_m:.2f} m)")

    vuln = VulnerabilityModule()
    damage = vuln.calculate_damage(depth_ft=3.5, rcv_building=300_000, rcv_contents=100_000, is_elevated=False)
    print(f"Non-elevated damage at 3.5ft: ${damage['total_damage']:,.0f}")
