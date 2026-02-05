"""
Export Agent Initialization Data for Paper 3

Generates a complete CSV file with all agent attributes, initial memories,
PMT scores, and initial states for Supplementary Material Table S1.

Output: 42-column CSV with comprehensive agent initialization data

Usage:
    python export_agent_initialization.py
    python export_agent_initialization.py --output custom_path.csv
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# Setup paths
SCRIPT_DIR = Path(__file__).parent
FLOOD_DIR = SCRIPT_DIR.parent.parent  # examples/multi_agent/flood
DATA_DIR = FLOOD_DIR / "data"
OUTPUT_DIR = SCRIPT_DIR.parent / "data"  # paper3/data

# Input files
AGENT_PROFILES = DATA_DIR / "agent_profiles_balanced.csv"
INITIAL_MEMORIES = DATA_DIR / "initial_memories_balanced.json"


def load_agent_profiles() -> pd.DataFrame:
    """Load the agent profiles CSV."""
    df = pd.read_csv(AGENT_PROFILES)
    print(f"Loaded {len(df)} agent profiles from {AGENT_PROFILES.name}")
    return df


def load_initial_memories() -> Dict[str, List[Dict]]:
    """Load the initial memories JSON."""
    with open(INITIAL_MEMORIES, 'r', encoding='utf-8') as f:
        memories = json.load(f)
    print(f"Loaded memories for {len(memories)} agents from {INITIAL_MEMORIES.name}")
    return memories


def extract_memory_summary(memories: List[Dict], category: str, max_length: int = 100) -> str:
    """Extract a summary of a specific memory category."""
    for mem in memories:
        if mem.get('category') == category:
            content = mem.get('content', '')
            if len(content) > max_length:
                return content[:max_length - 3] + '...'
            return content
    return ''


def determine_cell(row: pd.Series) -> str:
    """Determine the 4-cell classification."""
    mg_label = "MG" if row['mg'] else "NMG"
    return f"{mg_label}-{row['tenure']}"


def export_agent_initialization(output_path: Optional[Path] = None) -> pd.DataFrame:
    """
    Export complete agent initialization data to CSV.

    Returns:
        DataFrame with all agent initialization data
    """
    # Load data
    profiles = load_agent_profiles()
    memories = load_initial_memories()

    # Create output dataframe
    output_data = []

    for _, row in profiles.iterrows():
        agent_id = row['agent_id']
        agent_memories = memories.get(agent_id, [])

        agent_data = {
            # Identification
            'agent_id': agent_id,
            'survey_id': row.get('survey_id', ''),
            'cell': determine_cell(row),

            # Demographics
            'mg': row['mg'],
            'tenure': row['tenure'],
            'income': row.get('income', 0),
            'income_bracket': row.get('income_bracket', ''),
            'household_size': row.get('household_size', 0),
            'generations': row.get('generations', 0),
            'has_vehicle': row.get('has_vehicle', False),
            'has_children': row.get('has_children', False),
            'has_elderly': row.get('has_elderly', False),
            'housing_cost_burden': row.get('housing_cost_burden', False),

            # MG Classification
            'mg_criteria_met': row.get('mg_criteria_met', ''),

            # Geographic Location
            'longitude': row.get('longitude', 0),
            'latitude': row.get('latitude', 0),
            'grid_x': row.get('grid_x', 0),
            'grid_y': row.get('grid_y', 0),
            'flood_zone': row.get('flood_zone', ''),
            'flood_depth': row.get('flood_depth', 0),
            'zipcode': row.get('zipcode', ''),

            # Financial
            'rcv_building': row.get('rcv_building', 0),
            'rcv_contents': row.get('rcv_contents', 0),

            # PMT Scores
            'tp_score': row.get('tp_score', 0),
            'cp_score': row.get('cp_score', 0),
            'sc_score': row.get('sc_score', 0),
            'pa_score': row.get('pa_score', 0),
            'sp_score': row.get('sp_score', 0),

            # Flood History
            'flood_experience': row.get('flood_experience', False),
            'flood_frequency': row.get('flood_frequency', 0),
            'sfha_awareness': row.get('sfha_awareness', False),

            # Initial State
            'elevated': row.get('elevated', False),
            'has_insurance': row.get('has_insurance', False),
            'relocated': row.get('relocated', False),
            'cumulative_damage': row.get('cumulative_damage', 0),
            'cumulative_oop': row.get('cumulative_oop', 0),

            # Initial Memory Summaries
            'memory_flood_exp': extract_memory_summary(agent_memories, 'flood_experience'),
            'memory_insurance': extract_memory_summary(agent_memories, 'insurance_history'),
            'memory_social': extract_memory_summary(agent_memories, 'social_connections'),
            'memory_gov_trust': extract_memory_summary(agent_memories, 'government_trust'),
            'memory_place': extract_memory_summary(agent_memories, 'place_attachment'),
            'memory_zone': extract_memory_summary(agent_memories, 'flood_zone'),
        }

        output_data.append(agent_data)

    df = pd.DataFrame(output_data)

    # Ensure output directory exists
    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / "agent_initialization_complete.csv"

    # Save to CSV
    df.to_csv(output_path, index=False, encoding='utf-8')
    print(f"\nExported {len(df)} agents to: {output_path}")
    print(f"Columns: {len(df.columns)}")

    # Print summary statistics
    print("\n" + "=" * 60)
    print("Summary Statistics")
    print("=" * 60)

    print(f"\nTotal Agents: {len(df)}")

    print("\n4-Cell Distribution:")
    cell_counts = df['cell'].value_counts()
    for cell, count in cell_counts.items():
        print(f"  {cell}: {count}")

    print("\nFlood Zone Distribution:")
    zone_counts = df['flood_zone'].value_counts()
    for zone, count in zone_counts.items():
        print(f"  {zone}: {count}")

    print("\nMG/NMG Distribution:")
    print(f"  MG: {df['mg'].sum()}")
    print(f"  NMG: {(~df['mg']).sum()}")

    print("\nTenure Distribution:")
    tenure_counts = df['tenure'].value_counts()
    for tenure, count in tenure_counts.items():
        print(f"  {tenure}: {count}")

    print("\nPMT Score Ranges:")
    for score in ['tp_score', 'cp_score', 'sc_score', 'pa_score', 'sp_score']:
        print(f"  {score}: {df[score].min():.2f} - {df[score].max():.2f} "
              f"(mean: {df[score].mean():.2f})")

    print("\nRCV Statistics:")
    owner_df = df[df['tenure'] == 'Owner']
    renter_df = df[df['tenure'] == 'Renter']

    if len(owner_df) > 0:
        print(f"  Owners - Building RCV: ${owner_df['rcv_building'].mean():,.0f} (mean)")
        print(f"  Owners - Contents RCV: ${owner_df['rcv_contents'].mean():,.0f} (mean)")

    if len(renter_df) > 0:
        print(f"  Renters - Contents RCV: ${renter_df['rcv_contents'].mean():,.0f} (mean)")

    return df


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export agent initialization data for Paper 3"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV path (default: paper3/data/agent_initialization_complete.csv)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Agent Initialization Data Export")
    print("=" * 60)

    output_path = Path(args.output) if args.output else None
    export_agent_initialization(output_path)

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
