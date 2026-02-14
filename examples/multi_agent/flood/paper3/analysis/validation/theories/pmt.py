"""
Protection Motivation Theory (PMT) Implementation.

Contains construct-action coherence rules, sensibility checking,
and PMTTheory class implementing the BehavioralTheory protocol.
"""

from typing import Dict, List, Tuple


# =============================================================================
# PMT Coherence Rules (module-level for backward compatibility)
# =============================================================================

PMT_OWNER_RULES = {
    # High Threat + High Coping
    ("VH", "VH"): ["buy_insurance", "elevate", "buyout", "retrofit"],
    ("VH", "H"): ["buy_insurance", "elevate", "buyout", "retrofit"],
    ("H", "VH"): ["buy_insurance", "elevate", "buyout"],
    ("H", "H"): ["buy_insurance", "elevate", "buyout"],
    ("VH", "M"): ["buy_insurance", "elevate", "buyout"],
    ("H", "M"): ["buy_insurance", "elevate", "buyout"],
    # High Threat + Low Coping
    ("VH", "L"): ["buy_insurance", "do_nothing"],
    ("VH", "VL"): ["do_nothing"],
    ("H", "L"): ["buy_insurance", "do_nothing"],
    ("H", "VL"): ["do_nothing"],
    # Moderate Threat (relaxed per Grothmann & Reusswig 2006, Bubeck 2012)
    ("M", "VH"): ["buy_insurance", "elevate", "do_nothing"],
    ("M", "H"): ["buy_insurance", "elevate", "do_nothing"],
    ("M", "M"): ["buy_insurance", "elevate", "do_nothing"],
    ("M", "L"): ["buy_insurance", "do_nothing"],
    ("M", "VL"): ["do_nothing"],
    # Low Threat (PADM: insurance as habitual behavior)
    ("L", "VH"): ["buy_insurance", "do_nothing"],
    ("L", "H"): ["buy_insurance", "do_nothing"],
    ("L", "M"): ["do_nothing", "buy_insurance"],
    ("L", "L"): ["do_nothing", "buy_insurance"],
    ("L", "VL"): ["do_nothing"],
    ("VL", "VH"): ["do_nothing", "buy_insurance"],
    ("VL", "H"): ["do_nothing", "buy_insurance"],
    ("VL", "M"): ["do_nothing"],
    ("VL", "L"): ["do_nothing"],
    ("VL", "VL"): ["do_nothing"],
}

PMT_RENTER_RULES = {
    ("VH", "VH"): ["buy_insurance", "relocate"],
    ("VH", "H"): ["buy_insurance", "relocate"],
    ("H", "VH"): ["buy_insurance", "relocate"],
    ("H", "H"): ["buy_insurance", "relocate"],
    ("VH", "M"): ["buy_insurance", "relocate"],
    ("H", "M"): ["buy_insurance", "relocate"],
    ("VH", "L"): ["buy_insurance", "do_nothing"],
    ("VH", "VL"): ["do_nothing"],
    ("H", "L"): ["buy_insurance", "do_nothing"],
    ("H", "VL"): ["do_nothing"],
    # Moderate Threat
    ("M", "VH"): ["buy_insurance", "do_nothing"],
    ("M", "H"): ["buy_insurance", "do_nothing"],
    ("M", "M"): ["buy_insurance", "do_nothing"],
    ("M", "L"): ["do_nothing", "buy_insurance"],
    ("M", "VL"): ["do_nothing"],
    # Low Threat
    ("L", "VH"): ["do_nothing", "buy_insurance"],
    ("L", "H"): ["do_nothing", "buy_insurance"],
    ("L", "M"): ["do_nothing", "buy_insurance"],
    ("L", "L"): ["do_nothing", "buy_insurance"],
    ("L", "VL"): ["do_nothing"],
    ("VL", "VH"): ["do_nothing", "buy_insurance"],
    ("VL", "H"): ["do_nothing", "buy_insurance"],
    ("VL", "M"): ["do_nothing"],
    ("VL", "L"): ["do_nothing"],
    ("VL", "VL"): ["do_nothing"],
}


# =============================================================================
# Sensibility Check (backward-compatible free function)
# =============================================================================

def _is_sensible_action(tp: str, cp: str, action: str, agent_type: str) -> bool:
    """Check if action is sensible given TP/CP even if not in exact rule table."""
    tp_level = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}.get(tp, 3)
    cp_level = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}.get(cp, 3)

    if tp_level >= 4 and cp_level >= 3:
        return action != "do_nothing"
    if tp_level <= 2:
        return True
    if cp_level <= 2 and action in ["elevate", "buyout", "relocate"]:
        return False
    return True


# =============================================================================
# PMTTheory — BehavioralTheory Protocol Implementation
# =============================================================================

class PMTTheory:
    """Protection Motivation Theory implementation of BehavioralTheory protocol.

    Paradigm A: Construct-Action Mapping.
    Two dimensions: TP (Threat Perception), CP (Coping Perception).
    """

    def __init__(
        self,
        owner_rules: Dict[Tuple[str, str], List[str]] = None,
        renter_rules: Dict[Tuple[str, str], List[str]] = None,
    ):
        self._owner_rules = owner_rules or PMT_OWNER_RULES
        self._renter_rules = renter_rules or PMT_RENTER_RULES

    @property
    def name(self) -> str:
        return "pmt"

    @property
    def dimensions(self) -> List[str]:
        return ["TP", "CP"]

    @property
    def agent_types(self) -> List[str]:
        return ["owner", "renter"]

    def get_coherent_actions(
        self, construct_levels: Dict[str, str], agent_type: str
    ) -> List[str]:
        rules = self._owner_rules if agent_type == "owner" else self._renter_rules
        key = (construct_levels.get("TP", "M"), construct_levels.get("CP", "M"))
        return rules.get(key, [])

    def extract_constructs(self, trace: Dict) -> Dict[str, str]:
        # Try nested path first: skill_proposal.reasoning.TP_LABEL
        skill_proposal = trace.get("skill_proposal", {})
        if isinstance(skill_proposal, dict):
            reasoning = skill_proposal.get("reasoning", {})
            if isinstance(reasoning, dict):
                tp = reasoning.get("TP_LABEL")
                cp = reasoning.get("CP_LABEL")
                if tp is not None or cp is not None:
                    return {
                        "TP": tp if tp is not None else "UNKNOWN",
                        "CP": cp if cp is not None else "UNKNOWN",
                    }
        # Fallback to top-level
        return {
            "TP": trace.get("TP_LABEL", "UNKNOWN"),
            "CP": trace.get("CP_LABEL", "UNKNOWN"),
        }

    def is_sensible_action(
        self, construct_levels: Dict[str, str], action: str, agent_type: str
    ) -> bool:
        tp = construct_levels.get("TP", "M")
        cp = construct_levels.get("CP", "M")
        return _is_sensible_action(tp, cp, action, agent_type)
