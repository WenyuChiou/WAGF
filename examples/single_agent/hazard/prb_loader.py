"""
PRB (Passaic River Basin) Flood Depth Grid Loader.

Loads ESRI ASCII Grid (.asc) files containing maximum flood depth data.
Supports multi-year scenarios from the PRB flood model.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class GridMetadata:
    """Metadata from ESRI ASCII Grid header."""

    ncols: int  # Number of columns
    nrows: int  # Number of rows
    xllcorner: float  # X coordinate of lower-left corner
    yllcorner: float  # Y coordinate of lower-left corner
    cellsize: float  # Cell size in coordinate units
    nodata_value: float  # Value representing no data

    @property
    def total_cells(self) -> int:
        return self.ncols * self.nrows

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """Return (xmin, ymin, xmax, ymax)."""
        xmax = self.xllcorner + self.ncols * self.cellsize
        ymax = self.yllcorner + self.nrows * self.cellsize
        return (self.xllcorner, self.yllcorner, xmax, ymax)


class PRBGridLoader:
    """
    Load ESRI ASCII Grid files for PRB flood depths.

    File naming convention: maxDepth{YYYY}.asc
    Special case: 2011 uses maxDepth2011_newXsecDS.asc
    """

    # Expected grid dimensions for PRB
    EXPECTED_NCOLS = 457
    EXPECTED_NROWS = 411

    def __init__(
        self,
        grid_dir: Path,
        years: Optional[List[int]] = None,
    ):
        """
        Initialize the grid loader.

        Args:
            grid_dir: Directory containing .asc files
            years: List of years to load (default: 2011-2023)
        """
        self.grid_dir = Path(grid_dir)
        self.years = years or list(range(2011, 2024))

        self.grids: Dict[int, np.ndarray] = {}
        self.metadata: Optional[GridMetadata] = None
        self._depth_stats: Optional[Dict[str, float]] = None

    def load_year(self, year: int) -> np.ndarray:
        """
        Load flood depth grid for a specific year.

        Args:
            year: Year to load (e.g., 2011)

        Returns:
            2D numpy array of flood depths in meters
        """
        # Handle special filename for 2011
        if year == 2011:
            filename = "maxDepth2011_newXsecDS.asc"
        else:
            filename = f"maxDepth{year}.asc"

        filepath = self.grid_dir / filename

        if not filepath.exists():
            raise FileNotFoundError(f"Grid file not found: {filepath}")

        grid, metadata = self._parse_esri_ascii(filepath)
        self.metadata = metadata
        self.grids[year] = grid

        logger.info(f"Loaded grid for {year}: {grid.shape}, depth range: {grid[grid >= 0].min():.2f}-{grid[grid >= 0].max():.2f}m")

        return grid

    def load_all_years(self) -> None:
        """Load all available years."""
        for year in self.years:
            try:
                self.load_year(year)
            except FileNotFoundError as e:
                logger.warning(f"Skipping year {year}: {e}")

        logger.info(f"Loaded {len(self.grids)} years of flood data")

    def _parse_esri_ascii(self, filepath: Path) -> Tuple[np.ndarray, GridMetadata]:
        """
        Parse ESRI ASCII Grid file.

        Format:
        ncols         457
        nrows         411
        xllcorner     -74.355
        yllcorner     40.8589
        cellsize      0.000277702
        NODATA_value  -9999
        [data rows...]
        """
        with open(filepath, "r") as f:
            # Parse header (6 lines)
            header = {}
            for _ in range(6):
                line = f.readline().strip()
                key, value = line.split()
                header[key.lower()] = float(value)

            metadata = GridMetadata(
                ncols=int(header["ncols"]),
                nrows=int(header["nrows"]),
                xllcorner=header["xllcorner"],
                yllcorner=header["yllcorner"],
                cellsize=header["cellsize"],
                nodata_value=header["nodata_value"],
            )

            # Parse data
            data = []
            for line in f:
                row = [float(x) for x in line.strip().split()]
                data.append(row)

            grid = np.array(data, dtype=np.float32)

            # Replace nodata with NaN
            grid[grid == metadata.nodata_value] = np.nan

        return grid, metadata

    def get_depth_at_cell(
        self, year: int, row: int, col: int
    ) -> Optional[float]:
        """
        Get flood depth at a specific grid cell.

        Args:
            year: Year of flood scenario
            row: Row index (0-based)
            col: Column index (0-based)

        Returns:
            Flood depth in meters, or None if invalid/nodata
        """
        if year not in self.grids:
            self.load_year(year)

        grid = self.grids[year]

        if row < 0 or row >= grid.shape[0] or col < 0 or col >= grid.shape[1]:
            return None

        depth = grid[row, col]
        return None if np.isnan(depth) else float(depth)

    def get_depth_distribution(self) -> Dict[str, float]:
        """
        Calculate depth distribution statistics across all loaded years.

        Returns:
            Dictionary with distribution statistics
        """
        if self._depth_stats is not None:
            return self._depth_stats

        if not self.grids:
            self.load_all_years()

        # Combine all valid depths
        all_depths = []
        for grid in self.grids.values():
            valid = grid[~np.isnan(grid)]
            all_depths.extend(valid.flatten())

        all_depths = np.array(all_depths)
        valid_depths = all_depths[all_depths >= 0]

        # Calculate statistics
        total = len(valid_depths)
        dry = np.sum(valid_depths == 0)

        self._depth_stats = {
            "total_cells": total,
            "dry_ratio": dry / total,
            "shallow_ratio": np.sum((valid_depths > 0) & (valid_depths <= 0.5)) / total,
            "moderate_ratio": np.sum((valid_depths > 0.5) & (valid_depths <= 1.0)) / total,
            "deep_ratio": np.sum((valid_depths > 1.0) & (valid_depths <= 2.0)) / total,
            "very_deep_ratio": np.sum((valid_depths > 2.0) & (valid_depths <= 4.0)) / total,
            "extreme_ratio": np.sum(valid_depths > 4.0) / total,
            "mean_depth": float(np.mean(valid_depths)),
            "max_depth": float(np.max(valid_depths)),
            "p50_depth": float(np.percentile(valid_depths, 50)),
            "p90_depth": float(np.percentile(valid_depths, 90)),
            "p95_depth": float(np.percentile(valid_depths, 95)),
            "p99_depth": float(np.percentile(valid_depths, 99)),
        }

        return self._depth_stats

    def get_cells_by_depth_category(
        self, year: int
    ) -> Dict[str, List[Tuple[int, int, float]]]:
        """
        Get cell coordinates categorized by depth.

        Args:
            year: Year to analyze

        Returns:
            Dict mapping category name to list of (row, col, depth) tuples
        """
        if year not in self.grids:
            self.load_year(year)

        grid = self.grids[year]
        categories = {
            "dry": [],
            "shallow": [],  # 0-0.5m
            "moderate": [],  # 0.5-1m
            "deep": [],  # 1-2m
            "very_deep": [],  # 2-4m
            "extreme": [],  # 4m+
        }

        for row in range(grid.shape[0]):
            for col in range(grid.shape[1]):
                depth = grid[row, col]
                if np.isnan(depth):
                    continue

                cell = (row, col, float(depth))

                if depth == 0:
                    categories["dry"].append(cell)
                elif depth <= 0.5:
                    categories["shallow"].append(cell)
                elif depth <= 1.0:
                    categories["moderate"].append(cell)
                elif depth <= 2.0:
                    categories["deep"].append(cell)
                elif depth <= 4.0:
                    categories["very_deep"].append(cell)
                else:
                    categories["extreme"].append(cell)

        return categories

    def sample_representative_year(self) -> int:
        """
        Return a representative year based on flood severity.

        Uses 2021 as default (second highest severity after 2011).
        """
        if not self.grids:
            self.load_all_years()

        # Calculate mean depth for each year
        year_means = {}
        for year, grid in self.grids.items():
            valid = grid[~np.isnan(grid) & (grid > 0)]
            if len(valid) > 0:
                year_means[year] = np.mean(valid)

        # Return year with median severity
        sorted_years = sorted(year_means.keys(), key=lambda y: year_means[y])
        return sorted_years[len(sorted_years) // 2] if sorted_years else 2021
