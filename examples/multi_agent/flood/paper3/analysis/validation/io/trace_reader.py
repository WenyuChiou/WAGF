"""
Trace Field Extraction and Action Normalization.

Extracts TP/CP labels and action names from nested trace structures.
"""

from typing import Dict


def _extract_tp_label(trace: Dict) -> str:
    """Extract TP_LABEL from nested trace structure.

    Returns "UNKNOWN" if extraction fails (never silently defaults to "M").
    """
    skill_proposal = trace.get("skill_proposal", {})
    if isinstance(skill_proposal, dict):
        reasoning = skill_proposal.get("reasoning", {})
        if isinstance(reasoning, dict) and "TP_LABEL" in reasoning:
            return reasoning["TP_LABEL"]
    return trace.get("TP_LABEL", "UNKNOWN")


def _extract_cp_label(trace: Dict) -> str:
    """Extract CP_LABEL from nested trace structure.

    Returns "UNKNOWN" if extraction fails (never silently defaults to "M").
    """
    skill_proposal = trace.get("skill_proposal", {})
    if isinstance(skill_proposal, dict):
        reasoning = skill_proposal.get("reasoning", {})
        if isinstance(reasoning, dict) and "CP_LABEL" in reasoning:
            return reasoning["CP_LABEL"]
    return trace.get("CP_LABEL", "UNKNOWN")


def _extract_action(trace: Dict) -> str:
    """Extract action/skill name from nested trace structure."""
    approved = trace.get("approved_skill", {})
    if isinstance(approved, dict) and "skill_name" in approved:
        return approved["skill_name"]
    proposal = trace.get("skill_proposal", {})
    if isinstance(proposal, dict) and "skill_name" in proposal:
        return proposal["skill_name"]
    if isinstance(approved, str):
        return approved
    if isinstance(proposal, str):
        return proposal
    return "do_nothing"


def _normalize_action(action) -> str:
    """Normalize action names to standard form."""
    if isinstance(action, dict):
        action = action.get("skill_name", action.get("name", "do_nothing"))
    if not isinstance(action, str):
        return "do_nothing"
    action = action.lower().strip()

    mappings = {
        "buy_insurance": [
            "buy_insurance", "purchase_insurance", "get_insurance", "insurance",
            "buy_contents_insurance", "buy_structure_insurance", "contents_insurance",
        ],
        "elevate": ["elevate", "elevate_home", "home_elevation", "raise_home", "elevate_house"],
        "buyout": ["buyout", "voluntary_buyout", "accept_buyout", "buyout_program"],
        "relocate": ["relocate", "move", "relocation"],
        "retrofit": ["retrofit", "floodproof", "flood_retrofit"],
        "do_nothing": ["do_nothing", "no_action", "wait", "none"],
    }

    for standard, variants in mappings.items():
        if action in variants:
            return standard

    return action
