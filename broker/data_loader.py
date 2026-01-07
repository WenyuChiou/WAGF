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

HOUSEHOLD_SCHEMA = {
    # Required fields
    "required": ["agent_id"],
    
    # Core demographic fields
    "core": {
        "mg": "bool - Marginalized Group (True/False)",
        "tenure": "str - 'Owner' or 'Renter'",
        "region_id": "str - Region identifier (e.g., 'NJ', 'NY')",
        "income": "float - Annual household income",
        "property_value": "float - Property value (0 for renters)"
    },
    
    # Trust/Social fields
    "trust": {
        "trust_gov": "float 0-1 - Trust in government",
        "trust_ins": "float 0-1 - Trust in insurance companies",
        "trust_neighbors": "float 0-1 - Trust in neighbors"
    },
    
    # Extensible demographic fields (freely add more)
    "demographics": {
        "household_size": "int - Number of people in household",
        "generations": "int - Generations living in this area (1-4+)",
        "has_vehicle": "bool - Has personal vehicle for evacuation",
        "age_of_head": "int - Age of household head",
        "education_level": "str - Education level",
        "employment_status": "str - Employment status",
        "years_in_residence": "int - Years at current address",
        "flood_experience_count": "int - Number of flood events experienced",
        "language_barrier": "bool - Has language barrier"
    }
}

INSTITUTIONAL_SCHEMA = {
    "required": ["agent_id", "agent_type"],
    "fields": {
        "region_id": "str - Coverage region",
        "initial_rate": "float - Initial premium/subsidy rate",
        "annual_budget": "float - Annual budget (government)",
        "risk_tolerance": "float 0-1 - Risk tolerance level"
    }
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
            for field, desc in fields.items():
                lines.append(f"  {field}: {desc}")
            lines.append("")
    
    lines.append("Note: Any additional columns will be loaded automatically.")
    return "\n".join(lines)

