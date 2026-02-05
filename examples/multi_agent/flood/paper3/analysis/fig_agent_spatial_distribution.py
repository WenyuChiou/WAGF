"""
Agent Spatial Distribution Visualization for Paper 3

Generates publication-quality maps showing:
1. 400 agents spatial distribution with 4 types (MG-Owner, MG-Renter, NMG-Owner, NMG-Renter)
2. Flood depth overlay from PRB raster data
3. Census Tract boundaries from TIGER/Line shapefiles
4. Optional basemap from OpenStreetMap

Output: 300 DPI PNG/PDF for Water Resources Research submission

Usage:
    python fig_agent_spatial_distribution.py
    python fig_agent_spatial_distribution.py --no-basemap
    python fig_agent_spatial_distribution.py --year 2021
    python fig_agent_spatial_distribution.py --census-tracts
"""

import sys
from pathlib import Path
from typing import Tuple, Optional, Dict
import argparse
import zipfile
import urllib.request
import shutil

import numpy as np
import pandas as pd

# Setup paths
SCRIPT_DIR = Path(__file__).parent
FLOOD_DIR = SCRIPT_DIR.parent.parent  # examples/multi_agent/flood
DATA_DIR = FLOOD_DIR / "data"
INPUT_DIR = FLOOD_DIR / "input" / "PRB"
OUTPUT_DIR = SCRIPT_DIR / "figures"
CENSUS_DIR = FLOOD_DIR / "input" / "census"

# Census Tract shapefile URL (NJ TIGER/Line 2023)
CENSUS_TRACT_URL = "https://www2.census.gov/geo/tiger/TIGER2023/TRACT/tl_2023_34_tract.zip"
CENSUS_TRACT_FILENAME = "tl_2023_34_tract.shp"

# Add project root for imports
ROOT_DIR = FLOOD_DIR.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# Optional imports with fallbacks
try:
    import geopandas as gpd
    from shapely.geometry import Point
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False
    print("Warning: geopandas not available. Using matplotlib only.")

try:
    import contextily as ctx
    HAS_CONTEXTILY = True
except ImportError:
    HAS_CONTEXTILY = False
    print("Warning: contextily not available. Basemap disabled.")


# =============================================================================
# Configuration
# =============================================================================

# Agent type styling
AGENT_STYLES = {
    "MG-Owner": {
        "color": "#e74c3c",  # Red
        "alpha": 0.9,
        "marker": "o",
        "size": 40,
        "edgecolor": "white",
        "linewidth": 0.5,
    },
    "MG-Renter": {
        "color": "#e74c3c",  # Red (lighter via alpha)
        "alpha": 0.6,
        "marker": "o",
        "size": 30,
        "edgecolor": "#e74c3c",
        "linewidth": 1.0,
        "facecolor": "none",  # Hollow marker
    },
    "NMG-Owner": {
        "color": "#3498db",  # Blue
        "alpha": 0.9,
        "marker": "o",
        "size": 40,
        "edgecolor": "white",
        "linewidth": 0.5,
    },
    "NMG-Renter": {
        "color": "#3498db",  # Blue (lighter via alpha)
        "alpha": 0.6,
        "marker": "o",
        "size": 30,
        "edgecolor": "#3498db",
        "linewidth": 1.0,
        "facecolor": "none",  # Hollow marker
    },
}

# Census Tract boundary styling
TRACT_STYLE = {
    "edgecolor": "#444444",      # Dark gray boundaries
    "facecolor": "none",          # Transparent fill
    "linewidth": 0.6,
    "alpha": 0.7,
    "linestyle": "-",
    "zorder": 2,                  # Between flood raster and agents
}

# Flood depth colormap (matches prb_visualize.py)
FLOOD_COLORS = [
    (0.0, "#f7fbff"),    # Very light blue for dry
    (0.1, "#deebf7"),    # Light blue for near-dry
    (0.5, "#9ecae1"),    # Medium blue for shallow
    (1.0, "#4292c6"),    # Blue for moderate
    (2.0, "#2171b5"),    # Darker blue for deep
    (4.0, "#084594"),    # Very dark blue for very deep
]

# Figure settings
FIGURE_SIZE = (10, 8)
DPI = 300
FONT_FAMILY = "serif"


# =============================================================================
# Census Tract Functions
# =============================================================================

def download_census_tracts(force: bool = False) -> Path:
    """
    Download NJ Census Tract shapefile from TIGER/Line if not present.

    Args:
        force: Force re-download even if file exists

    Returns:
        Path to the shapefile
    """
    CENSUS_DIR.mkdir(parents=True, exist_ok=True)
    shapefile_path = CENSUS_DIR / CENSUS_TRACT_FILENAME

    if shapefile_path.exists() and not force:
        print(f"Census tract shapefile already exists: {shapefile_path}")
        return shapefile_path

    print(f"Downloading Census Tract shapefile from TIGER/Line...")
    print(f"  URL: {CENSUS_TRACT_URL}")

    zip_path = CENSUS_DIR / "tl_2023_34_tract.zip"

    try:
        # Download zip file
        urllib.request.urlretrieve(CENSUS_TRACT_URL, zip_path)
        print(f"  Downloaded: {zip_path}")

        # Extract zip file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(CENSUS_DIR)
        print(f"  Extracted to: {CENSUS_DIR}")

        # Clean up zip file
        zip_path.unlink()

        if shapefile_path.exists():
            print(f"  Shapefile ready: {shapefile_path}")
            return shapefile_path
        else:
            raise FileNotFoundError(f"Extraction failed: {shapefile_path} not found")

    except Exception as e:
        print(f"Error downloading census tracts: {e}")
        print("Please download manually from:")
        print(f"  {CENSUS_TRACT_URL}")
        print(f"  Extract to: {CENSUS_DIR}")
        raise


def load_census_tracts(
    bounds: Optional[Tuple[float, float, float, float]] = None
) -> Optional["gpd.GeoDataFrame"]:
    """
    Load Census Tract boundaries, clipped to study area bounds.

    Args:
        bounds: (lon_min, lon_max, lat_min, lat_max) to clip tracts

    Returns:
        GeoDataFrame with tract boundaries, or None if unavailable
    """
    if not HAS_GEOPANDAS:
        print("Warning: geopandas required for census tract boundaries")
        return None

    shapefile_path = CENSUS_DIR / CENSUS_TRACT_FILENAME

    # Download if not present
    if not shapefile_path.exists():
        try:
            download_census_tracts()
        except Exception as e:
            print(f"Could not load census tracts: {e}")
            return None

    # Load shapefile
    print(f"Loading census tracts from: {shapefile_path}")
    tracts = gpd.read_file(shapefile_path)

    # Ensure CRS is WGS84
    if tracts.crs is None:
        tracts = tracts.set_crs("EPSG:4326")
    elif tracts.crs.to_epsg() != 4326:
        tracts = tracts.to_crs("EPSG:4326")

    # Clip to bounds if provided
    if bounds is not None:
        lon_min, lon_max, lat_min, lat_max = bounds
        # Create bounding box
        from shapely.geometry import box
        bbox = box(lon_min, lat_min, lon_max, lat_max)
        # Clip tracts
        tracts = tracts[tracts.intersects(bbox)]
        tracts = gpd.clip(tracts, bbox)
        print(f"  Clipped to study area: {len(tracts)} tracts")
    else:
        print(f"  Loaded {len(tracts)} tracts (NJ state)")

    return tracts


# =============================================================================
# Data Loading Functions
# =============================================================================

def load_agent_data(filepath: Optional[Path] = None) -> pd.DataFrame:
    """
    Load agent profiles with spatial coordinates.

    Returns:
        DataFrame with columns: agent_id, mg, tenure, longitude, latitude,
        flood_zone, flood_depth, and derived agent_type
    """
    if filepath is None:
        filepath = DATA_DIR / "agent_profiles_balanced.csv"

    df = pd.read_csv(filepath)

    # Create agent_type column
    def get_agent_type(row):
        mg_label = "MG" if row["mg"] else "NMG"
        return f"{mg_label}-{row['tenure']}"

    df["agent_type"] = df.apply(get_agent_type, axis=1)

    print(f"Loaded {len(df)} agents from {filepath.name}")
    print(f"Agent types: {df['agent_type'].value_counts().to_dict()}")

    return df


def load_flood_raster(year: int = 2021) -> Tuple[np.ndarray, Dict]:
    """
    Load PRB flood depth raster from ESRI ASCII format.

    Args:
        year: Year to load (2011-2023)

    Returns:
        Tuple of (depth_array, metadata_dict)
    """
    # Find raster file
    pattern = f"*{year}*.asc"
    files = list(INPUT_DIR.glob(pattern))

    if not files:
        # Try maxDepth format
        filepath = INPUT_DIR / f"maxDepth{year}.asc"
        if not filepath.exists():
            raise FileNotFoundError(f"No raster found for year {year} in {INPUT_DIR}")
    else:
        filepath = files[0]

    # Parse ESRI ASCII header
    metadata = {}
    header_lines = 6

    with open(filepath, 'r') as f:
        for i in range(header_lines):
            line = f.readline().strip()
            key, value = line.split()
            key = key.lower()
            if key in ['ncols', 'nrows']:
                metadata[key] = int(value)
            else:
                metadata[key] = float(value)

    # Read data
    data = np.loadtxt(filepath, skiprows=header_lines)

    # Replace NODATA with NaN
    nodata = metadata.get('nodata_value', -9999)
    data = np.where(data == nodata, np.nan, data)

    # Calculate extent in geographic coordinates
    xmin = metadata['xllcorner']
    ymin = metadata['yllcorner']
    cellsize = metadata['cellsize']
    xmax = xmin + metadata['ncols'] * cellsize
    ymax = ymin + metadata['nrows'] * cellsize

    metadata['extent'] = [xmin, xmax, ymin, ymax]
    metadata['filepath'] = filepath

    print(f"Loaded raster: {filepath.name}")
    print(f"  Shape: {data.shape}")
    print(f"  Extent: [{xmin:.4f}, {xmax:.4f}] x [{ymin:.4f}, {ymax:.4f}]")
    print(f"  Depth range: {np.nanmin(data):.2f} - {np.nanmax(data):.2f} m")

    return data, metadata


def create_flood_colormap() -> LinearSegmentedColormap:
    """Create custom colormap for flood depth visualization."""
    # Normalize positions to 0-1 range
    max_depth = 4.0
    colors = []
    positions = []

    for pos, color in FLOOD_COLORS:
        positions.append(pos / max_depth)
        colors.append(mcolors.to_rgb(color))

    # Create colormap
    cmap = LinearSegmentedColormap.from_list(
        "flood_depth",
        list(zip(positions, colors)),
        N=256
    )

    return cmap


# =============================================================================
# Visualization Functions
# =============================================================================

def create_agent_map(
    agents: pd.DataFrame,
    flood_data: Optional[np.ndarray] = None,
    flood_metadata: Optional[Dict] = None,
    census_tracts: Optional["gpd.GeoDataFrame"] = None,
    output_path: Optional[Path] = None,
    add_basemap: bool = True,
    title: str = "Agent Spatial Distribution in Passaic River Basin",
    show_flood: bool = True,
    show_tracts: bool = True,
) -> plt.Figure:
    """
    Create publication-quality map of agent distribution.

    Args:
        agents: DataFrame with agent data
        flood_data: 2D array of flood depths
        flood_metadata: Dict with extent, cellsize, etc.
        census_tracts: GeoDataFrame with census tract boundaries
        output_path: Path to save figure (PNG/PDF)
        add_basemap: Whether to add OpenStreetMap tiles
        title: Figure title
        show_flood: Whether to show flood depth overlay
        show_tracts: Whether to show census tract boundaries

    Returns:
        matplotlib Figure object
    """
    plt.rcParams['font.family'] = FONT_FAMILY

    fig, ax = plt.subplots(figsize=FIGURE_SIZE)

    # Get coordinate bounds
    lon_min = agents['longitude'].min() - 0.01
    lon_max = agents['longitude'].max() + 0.01
    lat_min = agents['latitude'].min() - 0.01
    lat_max = agents['latitude'].max() + 0.01

    # Plot flood depth raster if available
    if show_flood and flood_data is not None and flood_metadata is not None:
        cmap = create_flood_colormap()
        extent = flood_metadata['extent']

        # Mask areas with no flooding for transparency
        masked_data = np.ma.masked_where(
            (np.isnan(flood_data)) | (flood_data <= 0),
            flood_data
        )

        im = ax.imshow(
            masked_data,
            extent=extent,
            origin='upper',
            cmap=cmap,
            vmin=0,
            vmax=4.0,
            alpha=0.6,
            zorder=1,
        )

        # Add colorbar
        cbar = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
        cbar.set_label("Flood Depth (m)", fontsize=10)
        cbar.ax.tick_params(labelsize=8)

    # Plot census tract boundaries
    if show_tracts and census_tracts is not None and HAS_GEOPANDAS:
        try:
            census_tracts.plot(
                ax=ax,
                edgecolor=TRACT_STYLE['edgecolor'],
                facecolor=TRACT_STYLE['facecolor'],
                linewidth=TRACT_STYLE['linewidth'],
                alpha=TRACT_STYLE['alpha'],
                linestyle=TRACT_STYLE['linestyle'],
                zorder=TRACT_STYLE['zorder'],
            )
            print(f"  Plotted {len(census_tracts)} census tract boundaries")
        except Exception as e:
            print(f"Warning: Could not plot census tracts: {e}")

    # Add basemap if available and requested
    if add_basemap and HAS_GEOPANDAS and HAS_CONTEXTILY:
        try:
            # Create GeoDataFrame for proper CRS handling
            geometry = [Point(lon, lat) for lon, lat in
                       zip(agents['longitude'], agents['latitude'])]
            gdf = gpd.GeoDataFrame(agents, geometry=geometry, crs="EPSG:4326")

            # Convert to Web Mercator for basemap
            gdf_wm = gdf.to_crs(epsg=3857)

            # Get bounds in Web Mercator
            bounds = gdf_wm.total_bounds
            ax_wm = fig.add_axes(ax.get_position(), frameon=False)
            ax_wm.set_xlim(bounds[0] - 1000, bounds[2] + 1000)
            ax_wm.set_ylim(bounds[1] - 1000, bounds[3] + 1000)

            ctx.add_basemap(
                ax_wm,
                source=ctx.providers.OpenStreetMap.Mapnik,
                alpha=0.3,
            )
            ax_wm.set_axis_off()

            # Reproject agents for plotting on basemap
            agents_wm = gdf_wm.copy()

        except Exception as e:
            print(f"Warning: Could not add basemap: {e}")
            add_basemap = False

    # Plot agents by type (layered for visibility)
    plot_order = ["NMG-Renter", "NMG-Owner", "MG-Renter", "MG-Owner"]

    for agent_type in plot_order:
        style = AGENT_STYLES[agent_type]
        mask = agents['agent_type'] == agent_type
        subset = agents[mask]

        if len(subset) == 0:
            continue

        # Handle hollow markers for renters
        if "facecolor" in style and style["facecolor"] == "none":
            ax.scatter(
                subset['longitude'],
                subset['latitude'],
                c='none',
                edgecolors=style['color'],
                alpha=style['alpha'],
                s=style['size'],
                marker=style['marker'],
                linewidths=style['linewidth'],
                label=agent_type,
                zorder=3,
            )
        else:
            ax.scatter(
                subset['longitude'],
                subset['latitude'],
                c=style['color'],
                edgecolors=style['edgecolor'],
                alpha=style['alpha'],
                s=style['size'],
                marker=style['marker'],
                linewidths=style['linewidth'],
                label=agent_type,
                zorder=3,
            )

    # Set axis limits and labels
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_xlabel("Longitude", fontsize=11)
    ax.set_ylabel("Latitude", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight='bold', pad=10)

    # Format tick labels
    ax.tick_params(axis='both', labelsize=9)

    # Create custom legend
    legend_elements = []
    for agent_type in ["MG-Owner", "MG-Renter", "NMG-Owner", "NMG-Renter"]:
        style = AGENT_STYLES[agent_type]
        if "facecolor" in style and style["facecolor"] == "none":
            elem = Line2D(
                [0], [0],
                marker='o',
                color='w',
                markerfacecolor='none',
                markeredgecolor=style['color'],
                markersize=8,
                markeredgewidth=1.5,
                label=agent_type,
            )
        else:
            elem = Line2D(
                [0], [0],
                marker='o',
                color='w',
                markerfacecolor=style['color'],
                markeredgecolor=style['edgecolor'],
                markersize=8,
                markeredgewidth=0.5,
                label=agent_type,
            )
        legend_elements.append(elem)

    # Add census tract legend item if shown
    if show_tracts and census_tracts is not None:
        tract_elem = Line2D(
            [0], [0],
            color=TRACT_STYLE['edgecolor'],
            linewidth=1.5,
            linestyle='-',
            label='Census Tract',
        )
        legend_elements.append(tract_elem)

    # Add legend
    legend = ax.legend(
        handles=legend_elements,
        loc='upper left',
        title="Agent Types",
        fontsize=9,
        title_fontsize=10,
        framealpha=0.9,
        edgecolor='gray',
    )

    # Add statistics annotation
    stats_text = _get_stats_text(agents)
    ax.annotate(
        stats_text,
        xy=(0.98, 0.02),
        xycoords='axes fraction',
        fontsize=8,
        ha='right',
        va='bottom',
        bbox=dict(
            boxstyle='round,pad=0.3',
            facecolor='white',
            edgecolor='gray',
            alpha=0.9,
        ),
    )

    # Adjust layout
    plt.tight_layout()

    # Save figure
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save PNG
        fig.savefig(
            output_path,
            dpi=DPI,
            bbox_inches='tight',
            facecolor='white',
            edgecolor='none',
        )
        print(f"Saved: {output_path}")

        # Also save PDF for vector graphics
        pdf_path = output_path.with_suffix('.pdf')
        fig.savefig(
            pdf_path,
            dpi=DPI,
            bbox_inches='tight',
            facecolor='white',
            edgecolor='none',
        )
        print(f"Saved: {pdf_path}")

    return fig


def _get_stats_text(agents: pd.DataFrame) -> str:
    """Generate statistics text for annotation."""
    counts = agents['agent_type'].value_counts()
    zone_counts = agents['flood_zone'].value_counts()

    lines = [
        f"N = {len(agents)}",
        f"MG: {counts.get('MG-Owner', 0) + counts.get('MG-Renter', 0)} | "
        f"NMG: {counts.get('NMG-Owner', 0) + counts.get('NMG-Renter', 0)}",
        f"HIGH zone: {zone_counts.get('HIGH', 0)} | "
        f"MEDIUM: {zone_counts.get('MEDIUM', 0)} | "
        f"LOW: {zone_counts.get('LOW', 0)}",
    ]

    return "\n".join(lines)


def create_panel_map(
    agents: pd.DataFrame,
    flood_data: Optional[np.ndarray] = None,
    flood_metadata: Optional[Dict] = None,
    census_tracts: Optional["gpd.GeoDataFrame"] = None,
    output_path: Optional[Path] = None,
    show_tracts: bool = True,
) -> plt.Figure:
    """
    Create 2x2 panel map showing each agent type separately.

    Args:
        agents: DataFrame with agent data
        flood_data: 2D array of flood depths
        flood_metadata: Dict with extent, cellsize, etc.
        census_tracts: GeoDataFrame with census tract boundaries
        output_path: Path to save figure
        show_tracts: Whether to show census tract boundaries

    Returns:
        matplotlib Figure object
    """
    plt.rcParams['font.family'] = FONT_FAMILY

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    axes = axes.flatten()

    agent_types = ["MG-Owner", "MG-Renter", "NMG-Owner", "NMG-Renter"]

    # Get common bounds
    lon_min = agents['longitude'].min() - 0.01
    lon_max = agents['longitude'].max() + 0.01
    lat_min = agents['latitude'].min() - 0.01
    lat_max = agents['latitude'].max() + 0.01

    # Create flood colormap
    cmap = create_flood_colormap()

    for i, (ax, agent_type) in enumerate(zip(axes, agent_types)):
        style = AGENT_STYLES[agent_type]

        # Plot census tract boundaries first (lowest layer)
        if show_tracts and census_tracts is not None and HAS_GEOPANDAS:
            try:
                census_tracts.plot(
                    ax=ax,
                    edgecolor=TRACT_STYLE['edgecolor'],
                    facecolor=TRACT_STYLE['facecolor'],
                    linewidth=TRACT_STYLE['linewidth'] * 0.8,  # Slightly thinner for panels
                    alpha=TRACT_STYLE['alpha'],
                    linestyle=TRACT_STYLE['linestyle'],
                    zorder=1,
                )
            except Exception:
                pass  # Silent fail for panels

        # Plot flood background
        if flood_data is not None and flood_metadata is not None:
            extent = flood_metadata['extent']
            masked_data = np.ma.masked_where(
                (np.isnan(flood_data)) | (flood_data <= 0),
                flood_data
            )
            ax.imshow(
                masked_data,
                extent=extent,
                origin='upper',
                cmap=cmap,
                vmin=0,
                vmax=4.0,
                alpha=0.5,
            )

        # Plot this agent type
        subset = agents[agents['agent_type'] == agent_type]

        if "facecolor" in style and style["facecolor"] == "none":
            ax.scatter(
                subset['longitude'],
                subset['latitude'],
                c='none',
                edgecolors=style['color'],
                alpha=style['alpha'],
                s=style['size'] * 1.5,
                marker=style['marker'],
                linewidths=style['linewidth'],
            )
        else:
            ax.scatter(
                subset['longitude'],
                subset['latitude'],
                c=style['color'],
                edgecolors=style['edgecolor'],
                alpha=style['alpha'],
                s=style['size'] * 1.5,
                marker=style['marker'],
                linewidths=style['linewidth'],
            )

        # Set limits and labels
        ax.set_xlim(lon_min, lon_max)
        ax.set_ylim(lat_min, lat_max)
        ax.set_title(f"{agent_type} (N={len(subset)})", fontsize=11, fontweight='bold')
        ax.tick_params(axis='both', labelsize=8)

        # Add zone distribution
        zone_counts = subset['flood_zone'].value_counts()
        zone_text = f"HIGH: {zone_counts.get('HIGH', 0)} | MED: {zone_counts.get('MEDIUM', 0)} | LOW: {zone_counts.get('LOW', 0)}"
        ax.annotate(
            zone_text,
            xy=(0.5, 0.02),
            xycoords='axes fraction',
            fontsize=8,
            ha='center',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8),
        )

    # Common labels
    fig.text(0.5, 0.02, 'Longitude', ha='center', fontsize=11)
    fig.text(0.02, 0.5, 'Latitude', va='center', rotation='vertical', fontsize=11)

    # Add main title
    fig.suptitle(
        "Agent Spatial Distribution by Type",
        fontsize=14,
        fontweight='bold',
        y=0.98,
    )

    plt.tight_layout(rect=[0.03, 0.03, 1, 0.96])

    # Save figure
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fig.savefig(output_path, dpi=DPI, bbox_inches='tight', facecolor='white')
        print(f"Saved: {output_path}")

        pdf_path = output_path.with_suffix('.pdf')
        fig.savefig(pdf_path, dpi=DPI, bbox_inches='tight', facecolor='white')
        print(f"Saved: {pdf_path}")

    return fig


def generate_statistics_table(agents: pd.DataFrame) -> pd.DataFrame:
    """
    Generate summary statistics table for agent distribution.

    Args:
        agents: DataFrame with agent data

    Returns:
        DataFrame with statistics
    """
    stats = []

    for agent_type in ["MG-Owner", "MG-Renter", "NMG-Owner", "NMG-Renter"]:
        subset = agents[agents['agent_type'] == agent_type]
        zone_counts = subset['flood_zone'].value_counts()

        stats.append({
            'Agent Type': agent_type,
            'Count': len(subset),
            'HIGH Zone': zone_counts.get('HIGH', 0),
            'MEDIUM Zone': zone_counts.get('MEDIUM', 0),
            'LOW Zone': zone_counts.get('LOW', 0),
            'HIGH %': f"{zone_counts.get('HIGH', 0) / len(subset) * 100:.1f}%",
            'Mean Depth (m)': f"{subset['flood_depth'].mean():.3f}",
            'Max Depth (m)': f"{subset['flood_depth'].max():.3f}",
        })

    return pd.DataFrame(stats)


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate agent spatial distribution maps for Paper 3"
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2021,
        help="Flood year for raster overlay (default: 2021)",
    )
    parser.add_argument(
        "--no-basemap",
        action="store_true",
        help="Disable OpenStreetMap basemap",
    )
    parser.add_argument(
        "--no-flood",
        action="store_true",
        help="Disable flood depth overlay",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory (default: paper3/analysis/figures)",
    )
    parser.add_argument(
        "--census-tracts",
        action="store_true",
        default=True,
        help="Add Census Tract boundaries (default: enabled)",
    )
    parser.add_argument(
        "--no-census-tracts",
        action="store_true",
        help="Disable Census Tract boundaries",
    )
    parser.add_argument(
        "--download-census",
        action="store_true",
        help="Force re-download Census Tract shapefile",
    )

    args = parser.parse_args()

    # Handle census tract flags
    show_tracts = args.census_tracts and not args.no_census_tracts

    # Setup output directory
    output_dir = Path(args.output) if args.output else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Agent Spatial Distribution Visualization")
    print("=" * 60)

    # Load agent data
    print("\n[1] Loading agent data...")
    agents = load_agent_data()

    # Load flood raster
    flood_data = None
    flood_metadata = None
    if not args.no_flood:
        print(f"\n[2] Loading flood raster (year {args.year})...")
        try:
            flood_data, flood_metadata = load_flood_raster(args.year)
        except FileNotFoundError as e:
            print(f"Warning: {e}")
            print("Continuing without flood overlay...")

    # Load census tract boundaries
    census_tracts = None
    if show_tracts:
        print("\n[3] Loading Census Tract boundaries...")
        # Get bounds from agent data with buffer
        lon_min = agents['longitude'].min() - 0.02
        lon_max = agents['longitude'].max() + 0.02
        lat_min = agents['latitude'].min() - 0.02
        lat_max = agents['latitude'].max() + 0.02
        bounds = (lon_min, lon_max, lat_min, lat_max)

        if args.download_census:
            try:
                download_census_tracts(force=True)
            except Exception as e:
                print(f"Warning: Could not download census tracts: {e}")

        try:
            census_tracts = load_census_tracts(bounds=bounds)
        except Exception as e:
            print(f"Warning: Could not load census tracts: {e}")
            print("Continuing without tract boundaries...")

    # Generate main map
    print("\n[4] Generating main map...")
    main_output = output_dir / "agent_spatial_distribution.png"
    fig1 = create_agent_map(
        agents,
        flood_data=flood_data,
        flood_metadata=flood_metadata,
        census_tracts=census_tracts,
        output_path=main_output,
        add_basemap=not args.no_basemap,
        show_flood=not args.no_flood,
        show_tracts=show_tracts,
    )
    plt.close(fig1)

    # Generate panel map
    print("\n[5] Generating panel map...")
    panel_output = output_dir / "agent_spatial_distribution_panels.png"
    fig2 = create_panel_map(
        agents,
        flood_data=flood_data,
        flood_metadata=flood_metadata,
        census_tracts=census_tracts,
        output_path=panel_output,
        show_tracts=show_tracts,
    )
    plt.close(fig2)

    # Generate statistics table
    print("\n[6] Generating statistics...")
    stats = generate_statistics_table(agents)
    print("\nAgent Distribution Statistics:")
    print(stats.to_string(index=False))

    # Save statistics to CSV
    stats_output = output_dir / "agent_distribution_stats.csv"
    stats.to_csv(stats_output, index=False)
    print(f"\nSaved: {stats_output}")

    print("\n" + "=" * 60)
    print("Done! All outputs saved to:")
    print(f"  {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
