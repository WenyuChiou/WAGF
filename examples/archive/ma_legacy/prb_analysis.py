"""
PRB Multi-Year Flood Analysis Module

Performs temporal and spatial analysis on 13 years of PRB flood depth data (2011-2023).

Features:
1. Multi-year data loading and validation
2. Year-by-year severity ranking
3. Hotspot identification (persistently flooded cells)
4. Inter-annual variability statistics
5. JSON summary export

Usage:
    python prb_analysis.py --data-dir "C:\\path\\to\\PRB" --output analysis_results/
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

# Setup path
CURRENT_DIR = Path(__file__).parent
ROOT_DIR = CURRENT_DIR.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from examples.multi_agent.flood.environment.prb_loader import PRBGridLoader, GridMetadata

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class YearStats:
    """Statistics for a single year's flood data."""
    year: int
    total_cells: int
    valid_cells: int
    flooded_cells: int
    dry_cells: int

    # Depth statistics
    mean_depth: float
    max_depth: float
    p50_depth: float
    p90_depth: float
    p95_depth: float
    p99_depth: float
    std_depth: float

    # Category counts
    shallow_count: int = 0  # 0-0.5m
    moderate_count: int = 0  # 0.5-1m
    deep_count: int = 0  # 1-2m
    very_deep_count: int = 0  # 2-4m
    extreme_count: int = 0  # 4m+

    # Derived
    flood_ratio: float = 0.0
    severity_score: float = 0.0  # Combined metric for ranking


@dataclass
class AnalysisSummary:
    """Complete multi-year analysis summary."""
    years_analyzed: List[int]
    total_years: int
    grid_shape: Tuple[int, int]

    # Per-year stats
    year_stats: Dict[int, YearStats] = field(default_factory=dict)

    # Rankings
    severity_ranking: List[Tuple[int, float]] = field(default_factory=list)
    peak_years: List[int] = field(default_factory=list)

    # Temporal variability
    mean_annual_depth: float = 0.0
    std_annual_depth: float = 0.0
    coefficient_of_variation: float = 0.0

    # Hotspots
    persistent_flood_cells: int = 0  # Flooded in 50%+ years
    always_flooded_cells: int = 0  # Flooded every year


class PRBMultiYearAnalyzer:
    """
    Multi-year PRB flood depth analyzer.

    Provides comprehensive temporal and spatial analysis capabilities.
    """

    # Depth categories (meters)
    DEPTH_CATEGORIES = {
        "dry": (0, 0),
        "shallow": (0, 0.5),
        "moderate": (0.5, 1.0),
        "deep": (1.0, 2.0),
        "very_deep": (2.0, 4.0),
        "extreme": (4.0, float('inf'))
    }

    def __init__(self, data_dir: str, years: Optional[List[int]] = None):
        """
        Initialize the analyzer.

        Args:
            data_dir: Path to directory containing PRB .asc files
            years: List of years to analyze (default: 2011-2023)
        """
        self.data_dir = Path(data_dir)
        self.years = years or list(range(2011, 2024))

        self.loader = PRBGridLoader(self.data_dir, self.years)
        self.summary: Optional[AnalysisSummary] = None

    def load_data(self) -> int:
        """
        Load all years of flood data.

        Returns:
            Number of years successfully loaded
        """
        logger.info(f"Loading PRB data from: {self.data_dir}")

        loaded = 0
        for year in self.years:
            try:
                self.loader.load_year(year)
                loaded += 1
            except FileNotFoundError as e:
                logger.warning(f"Skipping year {year}: {e}")

        logger.info(f"Loaded {loaded}/{len(self.years)} years")
        return loaded

    def analyze_year(self, year: int) -> YearStats:
        """
        Analyze a single year's flood data.

        Args:
            year: Year to analyze

        Returns:
            YearStats dataclass with computed statistics
        """
        if year not in self.loader.grids:
            raise ValueError(f"Year {year} not loaded")

        grid = self.loader.grids[year]

        # Basic counts
        total_cells = grid.size
        valid_mask = ~np.isnan(grid)
        valid_cells = np.sum(valid_mask)
        valid_depths = grid[valid_mask]

        flooded_mask = valid_depths > 0
        flooded_cells = np.sum(flooded_mask)
        dry_cells = valid_cells - flooded_cells

        # Depth statistics (only for flooded cells)
        if flooded_cells > 0:
            flooded_depths = valid_depths[flooded_mask]
            mean_depth = float(np.mean(flooded_depths))
            max_depth = float(np.max(flooded_depths))
            p50 = float(np.percentile(flooded_depths, 50))
            p90 = float(np.percentile(flooded_depths, 90))
            p95 = float(np.percentile(flooded_depths, 95))
            p99 = float(np.percentile(flooded_depths, 99))
            std_depth = float(np.std(flooded_depths))
        else:
            mean_depth = max_depth = p50 = p90 = p95 = p99 = std_depth = 0.0

        # Category counts
        shallow = np.sum((valid_depths > 0) & (valid_depths <= 0.5))
        moderate = np.sum((valid_depths > 0.5) & (valid_depths <= 1.0))
        deep = np.sum((valid_depths > 1.0) & (valid_depths <= 2.0))
        very_deep = np.sum((valid_depths > 2.0) & (valid_depths <= 4.0))
        extreme = np.sum(valid_depths > 4.0)

        # Derived metrics
        flood_ratio = flooded_cells / valid_cells if valid_cells > 0 else 0

        # Severity score: weighted combination of extent and intensity
        # Score = flood_ratio * 0.4 + normalized_mean_depth * 0.3 + normalized_p95 * 0.3
        max_possible_depth = 10.0  # Normalize against
        severity_score = (
            flood_ratio * 0.4 +
            min(mean_depth / max_possible_depth, 1.0) * 0.3 +
            min(p95 / max_possible_depth, 1.0) * 0.3
        )

        return YearStats(
            year=year,
            total_cells=total_cells,
            valid_cells=int(valid_cells),
            flooded_cells=int(flooded_cells),
            dry_cells=int(dry_cells),
            mean_depth=round(mean_depth, 4),
            max_depth=round(max_depth, 4),
            p50_depth=round(p50, 4),
            p90_depth=round(p90, 4),
            p95_depth=round(p95, 4),
            p99_depth=round(p99, 4),
            std_depth=round(std_depth, 4),
            shallow_count=int(shallow),
            moderate_count=int(moderate),
            deep_count=int(deep),
            very_deep_count=int(very_deep),
            extreme_count=int(extreme),
            flood_ratio=round(flood_ratio, 4),
            severity_score=round(severity_score, 4)
        )

    def run_full_analysis(self) -> AnalysisSummary:
        """
        Run complete multi-year analysis.

        Returns:
            AnalysisSummary with all computed results
        """
        if not self.loader.grids:
            self.load_data()

        if not self.loader.grids:
            raise ValueError("No data loaded. Check data directory path.")

        # Initialize summary
        years_loaded = list(self.loader.grids.keys())
        grid_shape = list(self.loader.grids.values())[0].shape

        self.summary = AnalysisSummary(
            years_analyzed=sorted(years_loaded),
            total_years=len(years_loaded),
            grid_shape=grid_shape
        )

        # Analyze each year
        logger.info("Analyzing yearly statistics...")
        for year in years_loaded:
            stats = self.analyze_year(year)
            self.summary.year_stats[year] = stats

        # Compute rankings
        self._compute_severity_ranking()

        # Compute temporal variability
        self._compute_temporal_variability()

        # Identify hotspots
        self._identify_hotspots()

        return self.summary

    def _compute_severity_ranking(self) -> None:
        """Rank years by severity score."""
        if not self.summary:
            return

        rankings = [
            (year, stats.severity_score)
            for year, stats in self.summary.year_stats.items()
        ]
        rankings.sort(key=lambda x: x[1], reverse=True)

        self.summary.severity_ranking = rankings

        # Top 3 years are "peak years"
        self.summary.peak_years = [r[0] for r in rankings[:3]]

        logger.info(f"Peak flood years: {self.summary.peak_years}")

    def _compute_temporal_variability(self) -> None:
        """Compute inter-annual variability metrics."""
        if not self.summary:
            return

        mean_depths = [
            stats.mean_depth
            for stats in self.summary.year_stats.values()
            if stats.mean_depth > 0
        ]

        if mean_depths:
            self.summary.mean_annual_depth = round(float(np.mean(mean_depths)), 4)
            self.summary.std_annual_depth = round(float(np.std(mean_depths)), 4)

            if self.summary.mean_annual_depth > 0:
                self.summary.coefficient_of_variation = round(
                    self.summary.std_annual_depth / self.summary.mean_annual_depth, 4
                )

    def _identify_hotspots(self) -> None:
        """Identify cells that flood persistently across years."""
        if not self.summary or not self.loader.grids:
            return

        grids = list(self.loader.grids.values())
        n_years = len(grids)

        if n_years == 0:
            return

        # Stack all grids and count flood occurrences
        # A cell is "flooded" if depth > 0
        flood_count = np.zeros_like(grids[0], dtype=np.int32)

        for grid in grids:
            flooded = (grid > 0) & (~np.isnan(grid))
            flood_count += flooded.astype(np.int32)

        # Persistent: flooded in >= 50% of years
        persistent_threshold = n_years * 0.5
        persistent_mask = flood_count >= persistent_threshold
        self.summary.persistent_flood_cells = int(np.sum(persistent_mask))

        # Always flooded: flooded in all years
        always_mask = flood_count == n_years
        self.summary.always_flooded_cells = int(np.sum(always_mask))

        logger.info(f"Hotspots: {self.summary.persistent_flood_cells} persistent, "
                   f"{self.summary.always_flooded_cells} always flooded")

    def get_hotspot_grid(self) -> np.ndarray:
        """
        Get grid showing flood frequency (number of years flooded).

        Returns:
            2D array with count of years each cell was flooded
        """
        if not self.loader.grids:
            self.load_data()

        grids = list(self.loader.grids.values())
        flood_count = np.zeros_like(grids[0], dtype=np.int32)

        for grid in grids:
            flooded = (grid > 0) & (~np.isnan(grid))
            flood_count += flooded.astype(np.int32)

        return flood_count

    def export_summary(self, output_path: str) -> None:
        """
        Export analysis summary to JSON.

        Args:
            output_path: Path for output JSON file
        """
        if not self.summary:
            self.run_full_analysis()

        # Convert to serializable dict
        export_data = {
            "metadata": {
                "years_analyzed": self.summary.years_analyzed,
                "total_years": self.summary.total_years,
                "grid_shape": list(self.summary.grid_shape)
            },
            "year_statistics": {
                str(year): asdict(stats)
                for year, stats in self.summary.year_stats.items()
            },
            "rankings": {
                "severity_ranking": [
                    {"year": year, "score": score}
                    for year, score in self.summary.severity_ranking
                ],
                "peak_years": self.summary.peak_years
            },
            "temporal_variability": {
                "mean_annual_depth_m": self.summary.mean_annual_depth,
                "std_annual_depth_m": self.summary.std_annual_depth,
                "coefficient_of_variation": self.summary.coefficient_of_variation
            },
            "hotspots": {
                "persistent_flood_cells": self.summary.persistent_flood_cells,
                "always_flooded_cells": self.summary.always_flooded_cells
            }
        }

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Exported summary to: {output_path}")

    def print_summary(self) -> None:
        """Print analysis summary to console."""
        if not self.summary:
            self.run_full_analysis()

        print("\n" + "="*60)
        print("PRB MULTI-YEAR FLOOD ANALYSIS SUMMARY")
        print("="*60)

        print(f"\nYears Analyzed: {self.summary.total_years} ({self.summary.years_analyzed[0]}-{self.summary.years_analyzed[-1]})")
        print(f"Grid Shape: {self.summary.grid_shape[0]} rows x {self.summary.grid_shape[1]} cols")

        print("\n--- SEVERITY RANKING (Top 5) ---")
        for i, (year, score) in enumerate(self.summary.severity_ranking[:5], 1):
            stats = self.summary.year_stats[year]
            print(f"  {i}. Year {year}: Score={score:.4f}, MaxDepth={stats.max_depth:.2f}m, "
                  f"FloodRatio={stats.flood_ratio:.1%}")

        print("\n--- TEMPORAL VARIABILITY ---")
        print(f"  Mean Annual Depth: {self.summary.mean_annual_depth:.3f}m")
        print(f"  Std. Deviation: {self.summary.std_annual_depth:.3f}m")
        print(f"  Coefficient of Variation: {self.summary.coefficient_of_variation:.2f}")

        print("\n--- HOTSPOTS ---")
        print(f"  Persistent (>50% years): {self.summary.persistent_flood_cells:,} cells")
        print(f"  Always Flooded: {self.summary.always_flooded_cells:,} cells")

        print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(description="PRB Multi-Year Flood Analysis")
    parser.add_argument("--data-dir", required=True, help="Path to PRB .asc files directory")
    parser.add_argument("--output", default="prb_summary.json", help="Output JSON path")
    parser.add_argument("--years", nargs="+", type=int, help="Specific years to analyze")

    args = parser.parse_args()

    analyzer = PRBMultiYearAnalyzer(
        data_dir=args.data_dir,
        years=args.years
    )

    analyzer.run_full_analysis()
    analyzer.print_summary()
    analyzer.export_summary(args.output)

    print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
