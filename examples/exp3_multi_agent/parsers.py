"""
Output Parsers for Multi-Agent LLM Responses (Exp3)

Parses full LLM output for AUDIT trail:
- Household: 5 Construct Assessments + Decision + Justification
- Insurance: Analysis + Decision + Adjustment + Justification
- Government: Analysis + Decision + Adjustment + Priority + Justification
"""

import re
from dataclasses import dataclass, field
from typing import List, Literal, Tuple


@dataclass
class HouseholdOutput:
    """Parsed output from Household Agent LLM - Full Audit Record."""
    agent_id: str
    mg: bool
    tenure: str
    year: int
    
    # Construct Assessments (LLM OUTPUT)
    tp_level: Literal["LOW", "MODERATE", "HIGH"]
    tp_explanation: str
    cp_level: Literal["LOW", "MODERATE", "HIGH"]
    cp_explanation: str
    sp_level: Literal["LOW", "MODERATE", "HIGH"]
    sp_explanation: str
    sc_level: Literal["LOW", "MODERATE", "HIGH"]
    sc_explanation: str
    pa_level: Literal["NONE", "PARTIAL", "FULL"]
    pa_explanation: str
    
    # Decision
    decision_number: int
    decision_skill: str
    justification: str
    
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
    justification: str
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
    justification: str
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
    elevated: bool = False
) -> HouseholdOutput:
    """
    Parse LLM response into HouseholdOutput for audit.
    
    Expected format:
    TP Assessment: [LEVEL] - [explanation]
    CP Assessment: [LEVEL] - [explanation]
    SP Assessment: [LEVEL] - [explanation]
    SC Assessment: [LEVEL] - [explanation]
    PA Assessment: [LEVEL] - [explanation]
    Final Decision: [number]
    Justification: [explanation]
    """
    errors = []
    
    # Parse constructs
    tp_level, tp_exp = _parse_construct(response, "TP", ["LOW", "MODERATE", "HIGH"])
    cp_level, cp_exp = _parse_construct(response, "CP", ["LOW", "MODERATE", "HIGH"])
    sp_level, sp_exp = _parse_construct(response, "SP", ["LOW", "MODERATE", "HIGH"])
    sc_level, sc_exp = _parse_construct(response, "SC", ["LOW", "MODERATE", "HIGH"])
    pa_level, pa_exp = _parse_construct(response, "PA", ["NONE", "PARTIAL", "FULL"])
    
    # Check for parse failures
    for name, level in [("TP", tp_level), ("CP", cp_level), ("SP", sp_level), 
                        ("SC", sc_level), ("PA", pa_level)]:
        if level == "UNKNOWN":
            errors.append(f"Failed to parse {name} Assessment")
    
    # Parse decision
    decision_match = re.search(r"Final\s*Decision:\s*\[?(\d)\]?", response, re.IGNORECASE)
    decision_number = int(decision_match.group(1)) if decision_match else 0
    if decision_number == 0:
        errors.append("Failed to parse Final Decision")
    
    decision_skill = _number_to_skill(decision_number, tenure, elevated)
    
    # Parse justification
    justification_match = re.search(
        r"Justification:\s*(.+?)(?=\n\n|$)", 
        response, 
        re.IGNORECASE | re.DOTALL
    )
    justification = justification_match.group(1).strip() if justification_match else ""
    if not justification:
        errors.append("Failed to parse Justification")
    
    return HouseholdOutput(
        agent_id=agent_id,
        mg=mg,
        tenure=tenure,
        year=year,
        tp_level=tp_level if tp_level != "UNKNOWN" else "MODERATE",
        tp_explanation=tp_exp,
        cp_level=cp_level if cp_level != "UNKNOWN" else "MODERATE",
        cp_explanation=cp_exp,
        sp_level=sp_level if sp_level != "UNKNOWN" else "MODERATE",
        sp_explanation=sp_exp,
        sc_level=sc_level if sc_level != "UNKNOWN" else "MODERATE",
        sc_explanation=sc_exp,
        pa_level=pa_level if pa_level != "UNKNOWN" else "NONE",
        pa_explanation=pa_exp,
        decision_number=decision_number,
        decision_skill=decision_skill,
        justification=justification,
        validated=len(errors) == 0,
        validation_errors=errors,
        raw_response=response
    )


def _parse_construct(response: str, construct: str, valid_levels: List[str]) -> Tuple[str, str]:
    """Parse a single construct from response."""
    pattern = rf"{construct}\s*Assessment:\s*\[?(\w+)\]?\s*[-–]\s*(.+?)(?=\n[A-Z]|$)"
    match = re.search(pattern, response, re.IGNORECASE | re.DOTALL)
    
    if match:
        level = match.group(1).upper()
        explanation = match.group(2).strip()
        if level in valid_levels:
            return level, explanation
        # Fuzzy match
        for valid in valid_levels:
            if valid in level or level in valid:
                return valid, explanation
    
    return "UNKNOWN", ""


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
    
    # Parse justification
    just_match = re.search(
        r"Justification:\s*(.+?)(?=\n\n|$)", 
        response, 
        re.IGNORECASE | re.DOTALL
    )
    justification = just_match.group(1).strip() if just_match else ""
    
    return InsuranceOutput(
        year=year,
        analysis=analysis,
        decision=decision,
        adjustment_pct=adjustment,
        justification=justification,
        validated=bool(analysis and justification),
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
    
    # Parse justification
    just_match = re.search(
        r"Justification:\s*(.+?)(?=\n\n|$)", 
        response, 
        re.IGNORECASE | re.DOTALL
    )
    justification = just_match.group(1).strip() if just_match else ""
    
    return GovernmentOutput(
        year=year,
        analysis=analysis,
        decision=decision,
        adjustment_pct=adjustment,
        priority=priority,
        justification=justification,
        validated=bool(analysis and justification),
        raw_response=response
    )
