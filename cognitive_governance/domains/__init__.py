"""
GovernedAI SDK Domain Packs.

Pre-configured domain-specific components for common research domains:
- flood: Flood risk adaptation (psychology, economics)
- finance: Financial decision-making (savings, investment)
- education: Educational progression (degree attainment)
- health: Health behavior change (exercise, diet, smoking)

Each domain pack provides:
- sensors.py: SensorConfig definitions with quantization
- rules.py: Default PolicyRule sets
- observer.py: Domain-specific SocialObserver and EnvironmentObserver

Usage:
    >>> from cognitive_governance.domains.flood import FLOOD_SENSORS, FLOOD_RULES
    >>> from cognitive_governance.domains.flood import FloodObserver, FloodEnvironmentObserver
"""

from typing import List, Dict, Any

# Domain identifiers
AVAILABLE_DOMAINS = ["flood", "finance", "education", "health"]


def list_domains() -> List[str]:
    """List available domain packs."""
    return AVAILABLE_DOMAINS.copy()


def get_domain_info(domain: str) -> Dict[str, Any]:
    """Get information about a domain pack."""
    info = {
        "flood": {
            "name": "Flood Risk Adaptation",
            "description": "Household flood adaptation decisions (insurance, elevation, relocation)",
            "literature": "See Tonn & Czajkowski (2024), Xiao et al. (2023)",
        },
        "finance": {
            "name": "Financial Decision-Making",
            "description": "Savings, investment, and debt management decisions",
            "literature": "See CFPB guidelines, behavioral economics literature",
        },
        "education": {
            "name": "Educational Progression",
            "description": "Degree attainment and educational transitions",
            "literature": "See education psychology literature",
        },
        "health": {
            "name": "Health Behavior Change",
            "description": "Exercise, diet, smoking cessation, and health behaviors",
            "literature": "See health behavior change models (TTM, HBM)",
        },
    }
    return info.get(domain, {"name": domain, "description": "Unknown domain"})


__all__ = [
    "AVAILABLE_DOMAINS",
    "list_domains",
    "get_domain_info",
]
