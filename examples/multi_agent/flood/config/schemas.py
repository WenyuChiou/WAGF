"""
Flood Adaptation Schemas - Domain specific column definitions.
"""

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
    
    # Life/Social indices [0-1 normalized]
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
        "years_in_residence": {"type": "int", "range": [0, 50], "example": 10, "desc": "Years at address"},
    }
}

NORMALIZATION_GUIDE = {
    "income": {"min": 20000, "max": 150000},
    "property_value": {"min": 0, "max": 500000},
    "trust_*": {"min": 0.0, "max": 1.0},
}

# Note: Cognitive constructs (TP, CP, SP, etc.) are defined in ma_agent_types.yaml 
# to ensure the LLM prompt and validator use a single source of truth.
