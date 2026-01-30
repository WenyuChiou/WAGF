"""
Flood Zone Assigner

Assigns household agents to spatial locations based on:
1. Flood experience (from survey)
2. Flood depth data (from ESRI ASCII Grid)

Assignment Rules:
- Experienced (Q14=Yes): 70% HIGH zone, 30% MEDIUM zone
- Inexperienced (Q14=No): 30% MEDIUM zone, 70% LOW zone

Flood Zone Classification:
- HIGH: depth > 1.0m
- MEDIUM: 0.3m < depth <= 1.0m
- LOW: 0 < depth <= 0.3m

References:
- maxDepth2012.asc: Passaic River Basin flood model output
- ABM_Summary.pdf: Coupled ABM-flood model design
"""

import numpy as np
import pandas as pd
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
import random

# Configuration
SEED = 42
NODATA = -9999
INPUT_DIR = Path("examples/multi_agent/input")
DATA_DIR = Path("examples/multi_agent/data")

# Flood zone thresholds (meters)
HIGH_THRESHOLD = 1.0    # depth > 1.0m
MEDIUM_THRESHOLD = 0.3  # 0.3m < depth <= 1.0m
# LOW: 0 < depth <= 0.3m

# Assignment probabilities
EXPERIENCED_PROBS = {"HIGH": 0.70, "MEDIUM": 0.30, "LOW": 0.00}
INEXPERIENCED_PROBS = {"HIGH": 0.00, "MEDIUM": 0.30, "LOW": 0.70}


@dataclass
class FloodGridMeta:
    """ESRI ASCII Grid metadata."""
    ncols: int
    nrows: int
    xllcorner: float
    yllcorner: float
    cellsize: float
    nodata_value: float


@dataclass
class GridLocation:
    """Agent grid location with flood data."""
    grid_x: int
    grid_y: int
    depth: float
    flood_zone: str
    longitude: float
    latitude: float


def load_asc_grid(filepath: Path) -> Tuple[np.ndarray, FloodGridMeta]:
    """
    Load ESRI ASCII Grid file.

    Returns:
        Tuple of (depth_array, metadata)
    """
    with open(filepath, 'r') as f:
        # Read header (6 lines)
        ncols = int(f.readline().split()[1])
        nrows = int(f.readline().split()[1])
        xllcorner = float(f.readline().split()[1])
        yllcorner = float(f.readline().split()[1])
        cellsize = float(f.readline().split()[1])
        nodata_value = float(f.readline().split()[1])

        meta = FloodGridMeta(
            ncols=ncols,
            nrows=nrows,
            xllcorner=xllcorner,
            yllcorner=yllcorner,
            cellsize=cellsize,
            nodata_value=nodata_value
        )

        # Read data rows
        data = []
        for line in f:
            values = [float(v) for v in line.strip().split()]
            data.append(values)

        grid = np.array(data)

    print(f"[INFO] Loaded grid: {nrows}x{ncols} cells")
    print(f"[INFO] Bounds: ({xllcorner:.4f}, {yllcorner:.4f}) to "
          f"({xllcorner + ncols*cellsize:.4f}, {yllcorner + nrows*cellsize:.4f})")

    return grid, meta


def classify_flood_zones(grid: np.ndarray, nodata: float = NODATA) -> Dict[str, List[Tuple[int, int]]]:
    """
    Classify grid cells into flood zones.

    Returns:
        Dictionary mapping zone name to list of (row, col) coordinates
    """
    zones = {"HIGH": [], "MEDIUM": [], "LOW": []}

    nrows, ncols = grid.shape
    for row in range(nrows):
        for col in range(ncols):
            depth = grid[row, col]

            # Skip NODATA and zero depth
            if depth == nodata or depth <= 0:
                continue

            if depth > HIGH_THRESHOLD:
                zones["HIGH"].append((row, col))
            elif depth > MEDIUM_THRESHOLD:
                zones["MEDIUM"].append((row, col))
            else:  # 0 < depth <= 0.3
                zones["LOW"].append((row, col))

    print(f"\n[INFO] Flood zone classification:")
    print(f"  HIGH (>{HIGH_THRESHOLD}m): {len(zones['HIGH'])} cells")
    print(f"  MEDIUM ({MEDIUM_THRESHOLD}-{HIGH_THRESHOLD}m): {len(zones['MEDIUM'])} cells")
    print(f"  LOW (0-{MEDIUM_THRESHOLD}m): {len(zones['LOW'])} cells")

    return zones


def grid_to_coords(row: int, col: int, meta: FloodGridMeta) -> Tuple[float, float]:
    """Convert grid (row, col) to geographic coordinates (lon, lat)."""
    # Note: row 0 is top of grid (highest latitude)
    lon = meta.xllcorner + (col + 0.5) * meta.cellsize
    lat = meta.yllcorner + (meta.nrows - row - 0.5) * meta.cellsize
    return lon, lat


def assign_locations(
    households: pd.DataFrame,
    grid: np.ndarray,
    meta: FloodGridMeta,
    zones: Dict[str, List[Tuple[int, int]]],
    seed: int = SEED
) -> pd.DataFrame:
    """
    Assign spatial locations to households based on flood experience.

    Args:
        households: DataFrame with 'flood_experience' column
        grid: Flood depth array
        meta: Grid metadata
        zones: Pre-classified flood zones
        seed: Random seed

    Returns:
        DataFrame with added location columns
    """
    random.seed(seed)
    np.random.seed(seed)

    # Add location columns
    households = households.copy()
    households["grid_x"] = 0
    households["grid_y"] = 0
    households["flood_zone"] = ""
    households["flood_depth"] = 0.0
    households["longitude"] = 0.0
    households["latitude"] = 0.0

    # Track used locations to avoid duplicates
    used_locations = set()

    for idx, row in households.iterrows():
        has_experience = row.get("flood_experience", False)

        # Select zone based on experience
        if has_experience:
            probs = EXPERIENCED_PROBS
        else:
            probs = INEXPERIENCED_PROBS

        # Weighted zone selection
        zone_choices = []
        zone_weights = []
        for zone, prob in probs.items():
            if prob > 0 and len(zones[zone]) > 0:
                zone_choices.append(zone)
                zone_weights.append(prob)

        if not zone_choices:
            # Fallback: use any available zone
            for zone in ["LOW", "MEDIUM", "HIGH"]:
                if len(zones[zone]) > 0:
                    zone_choices.append(zone)
                    zone_weights.append(1.0)
                    break

        # Normalize weights
        total = sum(zone_weights)
        zone_weights = [w / total for w in zone_weights]

        # Select zone
        selected_zone = np.random.choice(zone_choices, p=zone_weights)

        # Select random cell from zone (avoiding duplicates)
        available = [loc for loc in zones[selected_zone] if loc not in used_locations]

        if not available:
            # If all cells used, allow reuse
            available = zones[selected_zone]

        cell_row, cell_col = random.choice(available)
        used_locations.add((cell_row, cell_col))

        # Get depth and coordinates
        depth = grid[cell_row, cell_col]
        lon, lat = grid_to_coords(cell_row, cell_col, meta)

        # Update household
        households.at[idx, "grid_x"] = cell_col
        households.at[idx, "grid_y"] = cell_row
        households.at[idx, "flood_zone"] = selected_zone
        households.at[idx, "flood_depth"] = round(depth, 4)
        households.at[idx, "longitude"] = round(lon, 6)
        households.at[idx, "latitude"] = round(lat, 6)

    return households


def summarize_assignments(df: pd.DataFrame) -> None:
    """Print summary of zone assignments."""
    print("\n=== Zone Assignment Summary ===")

    # Overall distribution
    zone_counts = df["flood_zone"].value_counts()
    print("\nOverall zone distribution:")
    for zone in ["HIGH", "MEDIUM", "LOW"]:
        count = zone_counts.get(zone, 0)
        pct = count / len(df) * 100
        print(f"  {zone}: {count} ({pct:.1f}%)")

    # By flood experience
    print("\nBy flood experience:")
    for exp, label in [(True, "Experienced"), (False, "Inexperienced")]:
        subset = df[df["flood_experience"] == exp]
        if len(subset) > 0:
            print(f"\n  {label} (n={len(subset)}):")
            zone_counts = subset["flood_zone"].value_counts()
            for zone in ["HIGH", "MEDIUM", "LOW"]:
                count = zone_counts.get(zone, 0)
                pct = count / len(subset) * 100
                print(f"    {zone}: {count} ({pct:.1f}%)")

    # Depth statistics
    print(f"\nFlood depth statistics:")
    print(f"  Mean: {df['flood_depth'].mean():.3f}m")
    print(f"  Min: {df['flood_depth'].min():.3f}m")
    print(f"  Max: {df['flood_depth'].max():.3f}m")


def run_assignment(
    survey_csv: Optional[Path] = None,
    asc_file: Optional[Path] = None,
    output_csv: Optional[Path] = None,
    seed: int = SEED
) -> pd.DataFrame:
    """
    Main function to assign flood zones to households.

    Args:
        survey_csv: Path to cleaned survey CSV (default: data/cleaned_survey.csv)
        asc_file: Path to ASC flood grid (default: input/maxDepth2012.asc)
        output_csv: Path for output CSV (default: data/agents_with_location.csv)
        seed: Random seed

    Returns:
        DataFrame with assigned locations
    """
    # Set paths
    survey_csv = survey_csv or DATA_DIR / "cleaned_survey.csv"
    asc_file = asc_file or INPUT_DIR / "maxDepth2012.asc"
    output_csv = output_csv or DATA_DIR / "agents_with_location.csv"

    # Load data
    print(f"[INFO] Loading survey data from {survey_csv}")
    households = pd.read_csv(survey_csv)
    print(f"[INFO] Loaded {len(households)} households")

    # Load flood grid
    print(f"\n[INFO] Loading flood grid from {asc_file}")
    grid, meta = load_asc_grid(asc_file)

    # Classify zones
    zones = classify_flood_zones(grid, meta.nodata_value)

    # Assign locations
    print(f"\n[INFO] Assigning locations to {len(households)} households...")
    households = assign_locations(households, grid, meta, zones, seed)

    # Save output
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    households.to_csv(output_csv, index=False)
    print(f"\n[OK] Saved to {output_csv}")

    # Print summary
    summarize_assignments(households)

    return households


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Assign flood zones to households")
    parser.add_argument("--survey", type=str, default=None, help="Input survey CSV")
    parser.add_argument("--asc", type=str, default=None, help="Input ASC flood grid")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    survey_csv = Path(args.survey) if args.survey else None
    asc_file = Path(args.asc) if args.asc else None
    output_csv = Path(args.output) if args.output else None

    run_assignment(
        survey_csv=survey_csv,
        asc_file=asc_file,
        output_csv=output_csv,
        seed=args.seed
    )
