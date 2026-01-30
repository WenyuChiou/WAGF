"""
PRB Flood Data Visualization Module

Provides matplotlib/seaborn visualizations for PRB flood analysis:
1. Spatial heatmaps per year
2. Time series of severity metrics
3. Depth distribution histograms
4. Hotspot visualization

Usage:
    python prb_visualize.py --data-dir "C:\\path\\to\\PRB" --output plots/
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Setup path
CURRENT_DIR = Path(__file__).parent
ROOT_DIR = CURRENT_DIR.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from matplotlib.colors import LinearSegmentedColormap
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

from examples.multi_agent.hazard.prb_analysis import PRBMultiYearAnalyzer

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class PRBVisualizer:
    """
    Visualization utilities for PRB flood data.

    Generates publication-quality figures using matplotlib and seaborn.
    """

    # Custom colormap for flood depth
    FLOOD_COLORS = [
        (0.95, 0.95, 0.95),  # Near-white for dry
        (0.7, 0.85, 0.95),   # Light blue for shallow
        (0.4, 0.7, 0.9),     # Blue for moderate
        (0.2, 0.4, 0.8),     # Dark blue for deep
        (0.6, 0.2, 0.6),     # Purple for very deep
        (0.5, 0.0, 0.0),     # Dark red for extreme
    ]

    def __init__(self, analyzer: PRBMultiYearAnalyzer, output_dir: str = "plots"):
        """
        Initialize visualizer.

        Args:
            analyzer: PRBMultiYearAnalyzer with loaded data
            output_dir: Directory for output plots
        """
        if not HAS_MATPLOTLIB:
            raise ImportError("matplotlib is required for visualization. Install with: pip install matplotlib")

        self.analyzer = analyzer
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create custom colormap
        self.depth_cmap = LinearSegmentedColormap.from_list(
            "flood_depth", self.FLOOD_COLORS, N=256
        )

        # Set style
        if HAS_SEABORN:
            sns.set_theme(style="whitegrid", palette="muted")

    def plot_depth_heatmap(
        self,
        year: int,
        save: bool = True,
        show: bool = False,
        vmax: float = 5.0
    ) -> Optional[plt.Figure]:
        """
        Create spatial heatmap of flood depths for a specific year.

        Args:
            year: Year to visualize
            save: Save plot to file
            show: Display plot interactively
            vmax: Maximum value for color scale

        Returns:
            matplotlib Figure object
        """
        if year not in self.analyzer.loader.grids:
            logger.warning(f"Year {year} not loaded. Skipping heatmap.")
            return None

        grid = self.analyzer.loader.grids[year]

        fig, ax = plt.subplots(figsize=(12, 10))

        # Mask NaN values
        masked_grid = np.ma.masked_invalid(grid)

        # Create heatmap
        im = ax.imshow(
            masked_grid,
            cmap=self.depth_cmap,
            vmin=0,
            vmax=vmax,
            aspect='auto'
        )

        # Colorbar
        cbar = fig.colorbar(im, ax=ax, shrink=0.8, label="Flood Depth (m)")

        # Labels
        ax.set_title(f"PRB Flood Depth Heatmap - Year {year}", fontsize=14, fontweight='bold')
        ax.set_xlabel("Column (Cell)")
        ax.set_ylabel("Row (Cell)")

        # Add statistics annotation
        stats = self.analyzer.summary.year_stats.get(year) if self.analyzer.summary else None
        if stats:
            stat_text = (f"Max: {stats.max_depth:.2f}m | "
                        f"Mean: {stats.mean_depth:.2f}m | "
                        f"Flooded: {stats.flood_ratio:.1%}")
            ax.annotate(stat_text, xy=(0.02, 0.02), xycoords='axes fraction',
                       fontsize=10, bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        plt.tight_layout()

        if save:
            filepath = self.output_dir / f"depth_heatmap_{year}.png"
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            logger.info(f"Saved heatmap: {filepath}")

        if show:
            plt.show()

        return fig

    def plot_all_heatmaps(self, vmax: float = 5.0) -> None:
        """Generate heatmaps for all loaded years."""
        for year in self.analyzer.loader.grids:
            self.plot_depth_heatmap(year, save=True, show=False, vmax=vmax)
            plt.close()

    def plot_severity_timeseries(
        self,
        save: bool = True,
        show: bool = False
    ) -> plt.Figure:
        """
        Create time series plot of flood severity metrics.

        Shows mean depth, max depth, and flood ratio over time.

        Args:
            save: Save plot to file
            show: Display plot

        Returns:
            matplotlib Figure object
        """
        if not self.analyzer.summary:
            self.analyzer.run_full_analysis()

        stats = self.analyzer.summary.year_stats
        years = sorted(stats.keys())

        mean_depths = [stats[y].mean_depth for y in years]
        max_depths = [stats[y].max_depth for y in years]
        p95_depths = [stats[y].p95_depth for y in years]
        flood_ratios = [stats[y].flood_ratio * 100 for y in years]  # Convert to %

        fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

        # Top: Depth metrics
        ax1 = axes[0]
        ax1.plot(years, max_depths, 'o-', color='darkred', label='Max Depth', linewidth=2, markersize=6)
        ax1.plot(years, p95_depths, 's-', color='orange', label='95th Percentile', linewidth=2, markersize=5)
        ax1.plot(years, mean_depths, '^-', color='steelblue', label='Mean Depth', linewidth=2, markersize=5)
        ax1.set_ylabel("Depth (m)")
        ax1.set_title("PRB Flood Severity Over Time (2011-2023)", fontsize=14, fontweight='bold')
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3)

        # Highlight peak years
        peak_years = self.analyzer.summary.peak_years[:3]
        for py in peak_years:
            if py in years:
                idx = years.index(py)
                ax1.axvline(x=py, color='red', linestyle='--', alpha=0.5)

        # Bottom: Flood ratio
        ax2 = axes[1]
        colors = ['darkred' if y in peak_years else 'steelblue' for y in years]
        ax2.bar(years, flood_ratios, color=colors, alpha=0.7, edgecolor='black')
        ax2.set_ylabel("Flood Extent (%)")
        ax2.set_xlabel("Year")
        ax2.set_xticks(years)
        ax2.set_xticklabels(years, rotation=45)
        ax2.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        if save:
            filepath = self.output_dir / "severity_timeseries.png"
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            logger.info(f"Saved time series: {filepath}")

        if show:
            plt.show()

        return fig

    def plot_depth_distribution_comparison(
        self,
        years_to_show: Optional[List[int]] = None,
        save: bool = True,
        show: bool = False
    ) -> plt.Figure:
        """
        Create histogram comparison of depth distributions across years.

        Args:
            years_to_show: Specific years to include (default: all)
            save: Save plot to file
            show: Display plot

        Returns:
            matplotlib Figure object
        """
        years = years_to_show or list(self.analyzer.loader.grids.keys())
        years = sorted(years)

        fig, ax = plt.subplots(figsize=(12, 6))

        # Collect depths for each year
        bins = np.linspace(0, 6, 30)

        if HAS_SEABORN:
            colors = sns.color_palette("husl", len(years))
        else:
            colors = plt.cm.viridis(np.linspace(0, 1, len(years)))

        for i, year in enumerate(years):
            if year not in self.analyzer.loader.grids:
                continue

            grid = self.analyzer.loader.grids[year]
            valid = grid[~np.isnan(grid)]
            flooded = valid[valid > 0]

            ax.hist(flooded, bins=bins, alpha=0.4, label=str(year),
                   color=colors[i], density=True)

        ax.set_xlabel("Flood Depth (m)")
        ax.set_ylabel("Density")
        ax.set_title("Depth Distribution Comparison Across Years", fontsize=14, fontweight='bold')
        ax.legend(title="Year", loc='upper right', ncol=2)
        ax.set_xlim(0, 6)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save:
            filepath = self.output_dir / "depth_distribution_comparison.png"
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            logger.info(f"Saved distribution plot: {filepath}")

        if show:
            plt.show()

        return fig

    def plot_hotspot_map(
        self,
        save: bool = True,
        show: bool = False
    ) -> plt.Figure:
        """
        Create heatmap showing flood frequency (hotspots).

        Args:
            save: Save plot to file
            show: Display plot

        Returns:
            matplotlib Figure object
        """
        flood_count = self.analyzer.get_hotspot_grid()
        n_years = len(self.analyzer.loader.grids)

        fig, ax = plt.subplots(figsize=(12, 10))

        # Create discrete colormap for year counts
        cmap = plt.cm.RdYlBu_r

        im = ax.imshow(
            flood_count,
            cmap=cmap,
            vmin=0,
            vmax=n_years
        )

        cbar = fig.colorbar(im, ax=ax, shrink=0.8, label="Number of Years Flooded")

        ax.set_title(f"PRB Flood Hotspots (Frequency Map)\n{n_years} Years Analyzed",
                    fontsize=14, fontweight='bold')
        ax.set_xlabel("Column (Cell)")
        ax.set_ylabel("Row (Cell)")

        # Add summary stats
        always_flooded = np.sum(flood_count == n_years)
        persistent = np.sum(flood_count >= n_years * 0.5)
        stat_text = f"Always flooded: {always_flooded:,} cells | Persistent (>50%): {persistent:,} cells"
        ax.annotate(stat_text, xy=(0.02, 0.02), xycoords='axes fraction',
                   fontsize=10, bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        plt.tight_layout()

        if save:
            filepath = self.output_dir / "flood_hotspots.png"
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            logger.info(f"Saved hotspot map: {filepath}")

        if show:
            plt.show()

        return fig

    def plot_category_breakdown(
        self,
        save: bool = True,
        show: bool = False
    ) -> plt.Figure:
        """
        Create stacked bar chart showing depth category breakdown by year.

        Args:
            save: Save plot to file
            show: Display plot

        Returns:
            matplotlib Figure object
        """
        if not self.analyzer.summary:
            self.analyzer.run_full_analysis()

        stats = self.analyzer.summary.year_stats
        years = sorted(stats.keys())

        categories = ['Dry', 'Shallow\n(0-0.5m)', 'Moderate\n(0.5-1m)',
                     'Deep\n(1-2m)', 'Very Deep\n(2-4m)', 'Extreme\n(>4m)']

        # Collect data as percentages
        data = {cat: [] for cat in categories}
        for year in years:
            s = stats[year]
            total = s.valid_cells
            data['Dry'].append(s.dry_cells / total * 100)
            data['Shallow\n(0-0.5m)'].append(s.shallow_count / total * 100)
            data['Moderate\n(0.5-1m)'].append(s.moderate_count / total * 100)
            data['Deep\n(1-2m)'].append(s.deep_count / total * 100)
            data['Very Deep\n(2-4m)'].append(s.very_deep_count / total * 100)
            data['Extreme\n(>4m)'].append(s.extreme_count / total * 100)

        fig, ax = plt.subplots(figsize=(14, 6))

        # Colors
        colors = ['#f0f0f0', '#a6cee3', '#1f78b4', '#6a3d9a', '#e31a1c', '#800000']

        # Create stacked bars
        x = np.arange(len(years))
        bottom = np.zeros(len(years))

        for i, (cat, values) in enumerate(data.items()):
            ax.bar(x, values, bottom=bottom, label=cat, color=colors[i], edgecolor='white')
            bottom += np.array(values)

        ax.set_xlabel("Year")
        ax.set_ylabel("Percentage of Cells (%)")
        ax.set_title("Flood Depth Category Breakdown by Year", fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(years, rotation=45)
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), title="Category")
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        if save:
            filepath = self.output_dir / "category_breakdown.png"
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            logger.info(f"Saved category breakdown: {filepath}")

        if show:
            plt.show()

        return fig

    def generate_all_plots(self, show: bool = False) -> None:
        """Generate all visualization plots."""
        logger.info("Generating all PRB visualizations...")

        # Run analysis if needed
        if not self.analyzer.summary:
            self.analyzer.run_full_analysis()

        # 1. Heatmaps for all years
        logger.info("Generating depth heatmaps...")
        self.plot_all_heatmaps()

        # 2. Time series
        logger.info("Generating time series...")
        self.plot_severity_timeseries(save=True, show=show)
        plt.close()

        # 3. Distribution comparison (show peak years + representative years)
        logger.info("Generating distribution comparison...")
        peak_years = self.analyzer.summary.peak_years[:3]
        # Add some contrasting years
        all_years = list(self.analyzer.loader.grids.keys())
        representative = [2012, 2015, 2018, 2022]  # Sample across range
        years_to_show = sorted(set(peak_years + [y for y in representative if y in all_years]))
        self.plot_depth_distribution_comparison(years_to_show=years_to_show, save=True, show=show)
        plt.close()

        # 4. Hotspot map
        logger.info("Generating hotspot map...")
        self.plot_hotspot_map(save=True, show=show)
        plt.close()

        # 5. Category breakdown
        logger.info("Generating category breakdown...")
        self.plot_category_breakdown(save=True, show=show)
        plt.close()

        logger.info(f"All plots saved to: {self.output_dir}")


def main():
    parser = argparse.ArgumentParser(description="PRB Flood Data Visualization")
    parser.add_argument("--data-dir", required=True, help="Path to PRB .asc files directory")
    parser.add_argument("--output", default="plots", help="Output directory for plots")
    parser.add_argument("--show", action="store_true", help="Display plots interactively")

    args = parser.parse_args()

    # Create analyzer and load data
    analyzer = PRBMultiYearAnalyzer(data_dir=args.data_dir)
    analyzer.load_data()

    if not analyzer.loader.grids:
        logger.error("No data loaded. Check the data directory path.")
        sys.exit(1)

    # Run analysis
    analyzer.run_full_analysis()
    analyzer.print_summary()

    # Generate plots
    visualizer = PRBVisualizer(analyzer, output_dir=args.output)
    visualizer.generate_all_plots(show=args.show)

    # Also export summary JSON
    summary_path = Path(args.output) / "prb_summary.json"
    analyzer.export_summary(str(summary_path))

    print(f"\nAll outputs saved to: {args.output}/")


if __name__ == "__main__":
    main()
