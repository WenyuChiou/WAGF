"""
Generic Data Loader

Load agent data from CSV/Excel files without type-specific dependencies.
Returns raw Dict data that can be used to create any agent type.
"""

import os
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional


def load_agents_csv(
    filepath: str,
    required_columns: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Load agents from CSV file as list of dicts.
    
    Args:
        filepath: Path to CSV file
        required_columns: Optional list of required column names
    
    Returns:
        List of agent data dicts
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Agent data file not found: {filepath}")
    
    df = pd.read_csv(filepath)
    
    # Validate required columns
    if required_columns:
        missing = set(required_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
    
    # Convert to list of dicts, handling NaN
    agents = df.to_dict('records')
    
    # Clean up values
    for agent in agents:
        for key, val in agent.items():
            # Convert NaN to None
            if pd.isna(val):
                agent[key] = None
            # Parse boolean strings
            elif isinstance(val, str) and val.upper() in ['TRUE', 'FALSE']:
                agent[key] = val.upper() == 'TRUE'
    
    print(f"[DataLoader] Loaded {len(agents)} agents from {filepath}")
    return agents


def load_agents_excel(
    filepath: str,
    sheet_name: str = "Agents"
) -> List[Dict[str, Any]]:
    """
    Load agents from Excel file.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Agent data file not found: {filepath}")
    
    df = pd.read_excel(filepath, sheet_name=sheet_name)
    agents = df.to_dict('records')
    
    print(f"[DataLoader] Loaded {len(agents)} agents from {filepath} (sheet: {sheet_name})")
    return agents


def export_agents_csv(
    agents: List[Dict[str, Any]],
    filepath: str,
    columns: Optional[List[str]] = None
) -> None:
    """
    Export agent data to CSV.
    
    Args:
        agents: List of agent dicts
        filepath: Output path
        columns: Optional columns to include (default: all)
    """
    df = pd.DataFrame(agents)
    
    if columns:
        df = df[columns]
    
    df.to_csv(filepath, index=False)
    print(f"[DataLoader] Exported {len(agents)} agents to {filepath}")


def create_sample_config(output_path: str = "agent_data_template.csv") -> None:
    """
    Create a sample CSV template for agent data.
    """
    sample = pd.DataFrame([
        {
            "agent_id": "H001",
            "agent_type": "household",
            "mg": True,
            "tenure": "Owner",
            "region_id": "NJ",
            "income": 45000,
            "property_value": 280000,
            "trust_gov": 0.5,
            "trust_ins": 0.5,
            "trust_neighbors": 0.5
        },
        {
            "agent_id": "H002",
            "agent_type": "household",
            "mg": False,
            "tenure": "Renter",
            "region_id": "NY",
            "income": 65000,
            "property_value": 0,
            "trust_gov": 0.6,
            "trust_ins": 0.7,
            "trust_neighbors": 0.4
        }
    ])
    sample.to_csv(output_path, index=False)
    print(f"[DataLoader] Created template at {output_path}")


# =============================================================================
# Column Schema Definitions (Extensible)
# =============================================================================
# These are EXAMPLES - any additional columns will be loaded automatically.
# Parameters marked [0-1] should be normalized to 0.0-1.0 range.

HOUSEHOLD_SCHEMA = {
    # Required fields
    "required": ["agent_id"],
    
    # Core demographic fields
    "core": {
        "agent_id": {"type": "str", "example": "H001", "desc": "Unique identifier"},
        "mg": {"type": "bool", "example": True, "desc": "Marginalized Group"},
        "tenure": {"type": "str", "example": "Owner", "desc": "'Owner' or 'Renter'"},
        "region_id": {"type": "str", "example": "NJ", "desc": "Region identifier"},
        "income": {"type": "float", "range": [20000, 150000], "example": 45000, "desc": "Annual income ($)"},
        "property_value": {"type": "float", "range": [0, 500000], "example": 280000, "desc": "Property value ($, 0 for renters)"}
    },
    
    # Trust/Social fields [0-1 normalized]
    "trust": {
        "trust_gov": {"type": "float", "range": [0.0, 1.0], "example": 0.5, "desc": "Trust in government"},
        "trust_ins": {"type": "float", "range": [0.0, 1.0], "example": 0.5, "desc": "Trust in insurance"},
        "trust_neighbors": {"type": "float", "range": [0.0, 1.0], "example": 0.5, "desc": "Trust in neighbors"}
    },
    
    # Extensible demographic fields
    "demographics": {
        "household_size": {"type": "int", "range": [1, 10], "example": 3, "desc": "Number of people"},
        "generations": {"type": "int", "range": [1, 5], "example": 2, "desc": "Generations in this area"},
        "has_vehicle": {"type": "bool", "example": True, "desc": "Has evacuation vehicle"},
        "age_of_head": {"type": "int", "range": [18, 90], "example": 45, "desc": "Age of household head"},
        "education_level": {"type": "str", "example": "college", "desc": "high_school/college/graduate"},
        "employment_status": {"type": "str", "example": "employed", "desc": "employed/unemployed/retired"},
        "years_in_residence": {"type": "int", "range": [0, 50], "example": 10, "desc": "Years at address"},
        "flood_experience_count": {"type": "int", "range": [0, 10], "example": 2, "desc": "Floods experienced"},
        "language_barrier": {"type": "bool", "example": False, "desc": "Has language barrier"}
    },
    
    # Derived/State fields (typically computed, not input)
    "state": {
        "cumulative_damage": {"type": "float", "range": [0.0, 1.0], "desc": "Normalized cumulative damage"},
        "elevated": {"type": "bool", "desc": "House is elevated"},
        "insured": {"type": "bool", "desc": "Has flood insurance"},
        "relocated": {"type": "bool", "desc": "Has relocated"}
    }
}

INSTITUTIONAL_SCHEMA = {
    "required": ["agent_id", "agent_type"],
    "fields": {
        "agent_id": {"type": "str", "example": "InsuranceCo", "desc": "Unique identifier"},
        "agent_type": {"type": "str", "example": "insurance", "desc": "insurance/government"},
        "region_id": {"type": "str", "example": "NJ", "desc": "Coverage region"},
        "initial_rate": {"type": "float", "range": [0.02, 0.15], "example": 0.05, "desc": "Initial premium/subsidy rate"},
        "annual_budget": {"type": "float", "range": [100000, 1000000], "example": 500000, "desc": "Annual budget ($)"},
        "risk_tolerance": {"type": "float", "range": [0.0, 1.0], "example": 0.5, "desc": "Risk tolerance level"}
    }
}

# Reference values for normalization
NORMALIZATION_GUIDE = {
    "income": {"min": 20000, "max": 150000, "typical_mg": 35000, "typical_nmg": 75000},
    "property_value": {"min": 0, "max": 500000, "typical_mg": 220000, "typical_nmg": 350000},
    "trust_*": {"min": 0.0, "max": 1.0, "low": 0.3, "medium": 0.5, "high": 0.7},
    "household_size": {"min": 1, "max": 10, "typical": 3},
    "generations": {"min": 1, "max": 5, "typical_owner": 2, "typical_renter": 1},
    "age_of_head": {"min": 18, "max": 90, "typical": 45},
    "years_in_residence": {"min": 0, "max": 50, "typical_owner": 15, "typical_renter": 3}
}

# For backward compatibility
HOUSEHOLD_REQUIRED_COLUMNS = HOUSEHOLD_SCHEMA["required"]
HOUSEHOLD_OPTIONAL_COLUMNS = (
    list(HOUSEHOLD_SCHEMA["core"].keys()) +
    list(HOUSEHOLD_SCHEMA["trust"].keys()) +
    list(HOUSEHOLD_SCHEMA["demographics"].keys())
)

INSTITUTIONAL_REQUIRED_COLUMNS = INSTITUTIONAL_SCHEMA["required"]
INSTITUTIONAL_OPTIONAL_COLUMNS = list(INSTITUTIONAL_SCHEMA["fields"].keys())


def get_schema_info(agent_type: str = "household") -> str:
    """
    Get human-readable schema info for CSV preparation.
    
    Usage:
        print(get_schema_info("household"))
    """
    if agent_type == "household":
        schema = HOUSEHOLD_SCHEMA
    else:
        schema = INSTITUTIONAL_SCHEMA
    
    lines = [f"=== {agent_type.upper()} SCHEMA ===", ""]
    lines.append(f"Required: {schema['required']}")
    lines.append("")
    
    for section, fields in schema.items():
        if section == "required":
            continue
        if isinstance(fields, dict):
            lines.append(f"[{section}]")
            for field, info in fields.items():
                if isinstance(info, dict):
                    range_str = f" [{info.get('range', ['?', '?'])[0]}-{info.get('range', ['?', '?'])[1]}]" if 'range' in info else ""
                    example_str = f" (e.g., {info.get('example', '?')})" if 'example' in info else ""
                    lines.append(f"  {field}: {info.get('type', '?')}{range_str}{example_str} - {info.get('desc', '')}")
                else:
                    lines.append(f"  {field}: {info}")
            lines.append("")
    
    lines.append("Note: Trust fields (trust_*) should be normalized to 0.0-1.0")
    lines.append("Note: Any additional columns are automatically loaded.")
    return "\n".join(lines)


def get_normalization_guide() -> str:
    """Get normalization reference values."""
    lines = ["=== NORMALIZATION GUIDE ===", ""]
    for field, info in NORMALIZATION_GUIDE.items():
        lines.append(f"{field}:")
        for k, v in info.items():
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)

