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

NORMALIZATION_GUIDE = {
    "income": {"min": 20000, "max": 150000, "typical_mg": 35000, "typical_nmg": 75000},
    "property_value": {"min": 0, "max": 500000, "typical_mg": 220000, "typical_nmg": 350000},
    "trust_*": {"min": 0.0, "max": 1.0, "low": 0.3, "medium": 0.5, "high": 0.7},
    "household_size": {"min": 1, "max": 10, "typical": 3},
    "generations": {"min": 1, "max": 5, "typical_owner": 2, "typical_renter": 1},
    "age_of_head": {"min": 18, "max": 90, "typical": 45},
    "years_in_residence": {"min": 0, "max": 50, "typical_owner": 15, "typical_renter": 3}
}

# =============================================================================
# 5 PMT/PADM CONSTRUCTS (for LLM evaluation)
# =============================================================================
FIVE_CONSTRUCTS = {
    "TP": {
        "name": "Threat Perception",
        "description": "Captures both emotional and cognitive responses to risk. Corresponds to threat appraisal from PMT and threat perception from PADM.",
        "levels": ["LOW", "MODERATE", "HIGH"],
        "weight_factors": ["flood_experience", "neighbor_damage", "depth_info", "perceived_vulnerability"]
    },
    "CP": {
        "name": "Coping Perception",
        "description": "Merges coping appraisal (PMT) and protective action perception (PADM). Represents assessment of ability to reduce risk and perceived effectiveness of potential actions.",
        "levels": ["LOW", "MODERATE", "HIGH"],
        "weight_factors": ["income", "insurance_access", "elevation_feasibility", "self_efficacy", "response_efficacy"]
    },
    "SP": {
        "name": "Stakeholder Perception",
        "description": "How individuals view trustworthiness, expertise, involvement, and influence of stakeholders (governments, insurance companies, community organizations) in adaptation process.",
        "levels": ["LOW", "MODERATE", "HIGH"],
        "weight_factors": ["trust_gov", "trust_ins", "past_claim_experience", "policy_awareness"]
    },
    "SC": {
        "name": "Social Capital",
        "description": "A form of capital embedded in social networks, trust, and norms that can enhance disaster resilience.",
        "levels": ["LOW", "MODERATE", "HIGH"],
        "weight_factors": ["trust_neighbors", "generations", "community_participation", "information_sharing"]
    },
    "PA": {
        "name": "Place Attachment",
        "description": "The emotional and psychological bond between individuals, communities, and their living environment.",
        "levels": ["LOW", "MODERATE", "HIGH"],
        "weight_factors": ["generations", "years_in_residence", "family_ties", "community_identity"]
    }
}

# Construct → Decision influence mapping
CONSTRUCT_DECISION_MAP = {
    # HIGH TP + HIGH CP → likely to take protective action
    # HIGH PA → less likely to relocate
    # LOW SC → less influenced by neighbors
    "buy_insurance": {"TP": "+", "CP": "+", "SP": "+", "SC": "0", "PA": "0"},
    "elevate_house": {"TP": "+", "CP": "+", "SP": "+", "SC": "+", "PA": "+"},
    "buyout_program": {"TP": "+", "CP": "0", "SP": "+", "SC": "-", "PA": "-"},
    "relocate": {"TP": "+", "CP": "0", "SP": "0", "SC": "-", "PA": "-"},
    "do_nothing": {"TP": "-", "CP": "-", "SP": "-", "SC": "0", "PA": "+"}
}
