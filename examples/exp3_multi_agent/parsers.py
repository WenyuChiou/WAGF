"""
Output Parsers for Multi-Agent LLM Responses (Exp3)

Simplified parsers for survey-based design:
- Household Agent: Reasoning + Decision (constructs are INPUT, not OUTPUT)
- Insurance Agent: Analysis + Decision + Adjustment
- Government Agent: Analysis + Decision + Priority
"""

import re
from dataclasses import dataclass, field
from typing import List, Literal, Tuple


@dataclass
class HouseholdOutput:
    """Parsed output from Household Agent LLM."""
    agent_id: str
    mg: bool
    tenure: str
    year: int
    
    # Survey Constructs (INPUT - stored for logging)
    tp_level: str
    cp_level: str
    sp_level: str
    sc_level: str
    pa_level: str
    
    # LLM Output
    reasoning: str
    decision_number: int
    decision_skill: str
    
    # Validation
    validated: bool = True
    validation_errors: List[str] = field(default_factory=list)
    raw_response: str = ""


@dataclass
class InsuranceOutput:
    """Parsed output from Insurance Agent LLM."""
    year: int
    analysis: str
    decision: Literal["RAISE", "LOWER", "MAINTAIN"]
    adjustment_pct: float
    reason: str
    validated: bool = True
    raw_response: str = ""


@dataclass
class GovernmentOutput:
    """Parsed output from Government Agent LLM."""
    year: int
    analysis: str
    decision: Literal["INCREASE", "DECREASE", "MAINTAIN"]
    adjustment_pct: float
    priority: Literal["MG", "ALL"]
    reason: str
    validated: bool = True
    raw_response: str = ""


# =============================================================================
# HOUSEHOLD PARSER
# =============================================================================

def parse_household_response(
    response: str,
    agent_id: str,
    mg: bool,
    tenure: str,
    year: int,
    constructs: dict,  # Survey constructs passed through for logging
    elevated: bool = False
) -> HouseholdOutput:
    """
    Parse LLM response into HouseholdOutput.
    
    Expected format:
    Reasoning: [explanation]
    Final Decision: [number]
    """
    errors = []
    
    # Parse reasoning
    reasoning_match = re.search(
        r"Reasoning:\s*(.+?)(?=Final\s*Decision:|$)", 
        response, 
        re.IGNORECASE | re.DOTALL
    )
    reasoning = reasoning_match.group(1).strip() if reasoning_match else ""
    if not reasoning:
        errors.append("Failed to parse Reasoning")
    
    # Parse decision
    decision_match = re.search(r"Final\s*Decision:\s*\[?(\d)\]?", response, re.IGNORECASE)
    decision_number = int(decision_match.group(1)) if decision_match else 0
    
    if decision_number == 0:
        errors.append("Failed to parse Final Decision")
    
    decision_skill = _number_to_skill(decision_number, tenure, elevated)
    
    return HouseholdOutput(
        agent_id=agent_id,
        mg=mg,
        tenure=tenure,
        year=year,
        # Pass through survey constructs for logging
        tp_level=constructs.get("TP", "UNKNOWN"),
        cp_level=constructs.get("CP", "UNKNOWN"),
        sp_level=constructs.get("SP", "UNKNOWN"),
        sc_level=constructs.get("SC", "UNKNOWN"),
        pa_level=constructs.get("PA", "UNKNOWN"),
        # LLM output
        reasoning=reasoning,
        decision_number=decision_number,
        decision_skill=decision_skill,
        validated=len(errors) == 0,
        validation_errors=errors,
        raw_response=response
    )


def _number_to_skill(num: int, tenure: str, elevated: bool) -> str:
    """Convert decision number to skill name based on agent type."""
    if tenure == "Renter":
        mapping = {1: "buy_insurance", 2: "relocate", 3: "do_nothing"}
    elif elevated:
        mapping = {1: "buy_insurance", 2: "relocate", 3: "do_nothing"}
    else:
        mapping = {1: "buy_insurance", 2: "elevate_house", 3: "relocate", 4: "do_nothing"}
    
    return mapping.get(num, "unknown")


# =============================================================================
# INSURANCE PARSER
# =============================================================================

def parse_insurance_response(response: str, year: int) -> InsuranceOutput:
    """Parse Insurance Agent LLM response."""
    
    # Parse analysis
    analysis_match = re.search(
        r"Analysis:\s*(.+?)(?=\n|Decision:)", 
        response, 
        re.IGNORECASE | re.DOTALL
    )
    analysis = analysis_match.group(1).strip() if analysis_match else ""
    
    # Parse decision
    decision_match = re.search(r"Decision:\s*\[?(\w+)\]?", response, re.IGNORECASE)
    decision = "MAINTAIN"
    if decision_match:
        dec = decision_match.group(1).upper()
        if dec in ["RAISE", "LOWER", "MAINTAIN"]:
            decision = dec
    
    # Parse adjustment
    adj_match = re.search(r"Adjustment:\s*\[?(\d+(?:\.\d+)?)\s*%?\]?", response, re.IGNORECASE)
    adjustment = float(adj_match.group(1)) / 100 if adj_match else 0.0
    
    # Parse reason
    reason_match = re.search(r"Reason:\s*(.+?)(?=\n|$)", response, re.IGNORECASE | re.DOTALL)
    reason = reason_match.group(1).strip() if reason_match else ""
    
    return InsuranceOutput(
        year=year,
        analysis=analysis,
        decision=decision,
        adjustment_pct=adjustment,
        reason=reason,
        validated=bool(analysis and reason),
        raw_response=response
    )


# =============================================================================
# GOVERNMENT PARSER
# =============================================================================

def parse_government_response(response: str, year: int) -> GovernmentOutput:
    """Parse Government Agent LLM response."""
    
    # Parse analysis
    analysis_match = re.search(
        r"Analysis:\s*(.+?)(?=\n|Decision:)", 
        response, 
        re.IGNORECASE | re.DOTALL
    )
    analysis = analysis_match.group(1).strip() if analysis_match else ""
    
    # Parse decision
    decision_match = re.search(r"Decision:\s*\[?(\w+)\]?", response, re.IGNORECASE)
    decision = "MAINTAIN"
    if decision_match:
        dec = decision_match.group(1).upper()
        if dec in ["INCREASE", "DECREASE", "MAINTAIN"]:
            decision = dec
    
    # Parse adjustment
    adj_match = re.search(r"Adjustment:\s*\[?(\d+(?:\.\d+)?)\s*%?\]?", response, re.IGNORECASE)
    adjustment = float(adj_match.group(1)) / 100 if adj_match else 0.0
    
    # Parse priority
    priority_match = re.search(r"Priority:\s*\[?(\w+)\]?", response, re.IGNORECASE)
    priority = "ALL"
    if priority_match:
        pri = priority_match.group(1).upper()
        if pri in ["MG", "ALL"]:
            priority = pri
    
    # Parse reason
    reason_match = re.search(r"Reason:\s*(.+?)(?=\n|$)", response, re.IGNORECASE | re.DOTALL)
    reason = reason_match.group(1).strip() if reason_match else ""
    
    return GovernmentOutput(
        year=year,
        analysis=analysis,
        decision=decision,
        adjustment_pct=adjustment,
        priority=priority,
        reason=reason,
        validated=bool(analysis and reason),
        raw_response=response
    )
