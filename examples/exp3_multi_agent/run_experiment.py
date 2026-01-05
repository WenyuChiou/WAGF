"""
Experiment 3: Multi-Agent Simulation (Full Integration)

Components:
- Data Loader: Load agents from CSV/Excel
- Prompts: Build LLM prompts with PMT constructs
- Parsers: Parse LLM responses
- Validators: Check PMT consistency
- Audit Writer: Record all decisions
- LLM Client: Call Ollama (optional, falls back to heuristic)

Output:
- household_audit.jsonl
- institutional_audit.jsonl
- audit_summary.json
"""

import sys
import os
import json

sys.path.insert(0, '.')

from typing import List, Dict, Optional
from dataclasses import asdict

from examples.exp3_multi_agent.data_loader import (
    load_households_from_csv, 
    initialize_all_agents
)
from examples.exp3_multi_agent.prompts import (
    build_household_prompt,
    build_insurance_prompt,
    build_government_prompt
)
from examples.exp3_multi_agent.parsers import (
    parse_household_response,
    parse_insurance_response,
    parse_government_response,
    HouseholdOutput
)
from examples.exp3_multi_agent.validators import HouseholdValidator
from examples.exp3_multi_agent.audit_writer import AuditWriter, AuditConfig
from examples.exp3_multi_agent.agents import HouseholdAgent
from examples.exp3_multi_agent.environment import SettlementModule

# Configuration
SIMULATION_YEARS = 10
OUTPUT_DIR = "examples/exp3_multi_agent/results"
SEED = 42
USE_LLM = False  # Set to True to use Ollama, False for heuristic


# =============================================================================
# LLM CLIENT (Ollama)
# =============================================================================

def call_llm(prompt: str, model: str = "llama3.2:3b") -> Optional[str]:
    """
    Call Ollama LLM for response.
    
    Returns None if LLM unavailable (falls back to heuristic).
    """
    if not USE_LLM:
        return None
    
    try:
        import requests
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60
        )
        if response.status_code == 200:
            return response.json().get("response", "")
    except Exception as e:
        print(f"[LLM] Error: {e}")
    
    return None


def generate_heuristic_response(agent: HouseholdAgent, year: int, context: dict) -> str:
    """
    Generate heuristic response when LLM unavailable.
    
    Simulates PMT-based decision making.
    """
    s = agent.state
    
    # Determine construct levels based on state
    tp = "HIGH" if s.cumulative_damage > s.property_value * 0.1 else ("MODERATE" if s.cumulative_damage > 0 else "LOW")
    cp = "HIGH" if s.income > 60000 else ("MODERATE" if s.income > 35000 else "LOW")
    sp = "HIGH" if context.get("government_subsidy_rate", 0.5) >= 0.5 else "MODERATE"
    sc = "MODERATE"
    pa = "FULL" if s.elevated and s.has_insurance else ("PARTIAL" if s.elevated or s.has_insurance else "NONE")
    
    # Determine decision
    if s.relocated:
        decision, num = "do_nothing", 4 if s.tenure == "Owner" else 3
    elif tp == "HIGH" and not s.has_insurance:
        decision, num = "buy_insurance", 1
    elif tp in ["MODERATE", "HIGH"] and not s.elevated and s.tenure == "Owner" and sp == "HIGH":
        decision, num = "elevate_house", 2
    elif s.cumulative_damage > s.property_value * 0.5 and s.income < 40000:
        decision, num = "relocate", 3 if s.tenure == "Owner" else 2
    else:
        decision, num = "do_nothing", 4 if s.tenure == "Owner" and not s.elevated else 3
    
    justification = f"Based on {tp} threat and {cp} coping ability, {decision} is appropriate."
    
    return f"""
TP Assessment: {tp} - Cumulative damage ${s.cumulative_damage:,.0f}
CP Assessment: {cp} - Income ${s.income:,.0f}
SP Assessment: {sp} - Subsidy {context.get('government_subsidy_rate', 0.5):.0%}
SC Assessment: {sc} - Moderate confidence in ability to act
PA Assessment: {pa} - Elevated: {s.elevated}, Insured: {s.has_insurance}
Final Decision: {num}
Justification: {justification}
"""


# =============================================================================
# MAIN SIMULATION
# =============================================================================

def run_simulation():
    """Main simulation loop with full integration."""
    print(f"=" * 60)
    print(f"Exp3 Multi-Agent Simulation")
    print(f"Years: {SIMULATION_YEARS}, LLM: {'Enabled' if USE_LLM else 'Heuristic'}")
    print(f"=" * 60)
    
    # Initialize
    households, govs, ins = initialize_all_agents(seed=SEED)
    settlement = SettlementModule(seed=SEED)
    validator = HouseholdValidator()
    audit = AuditWriter(AuditConfig(output_dir=OUTPUT_DIR))
    
    print(f"Loaded {len(households)} household agents")
    print(f"Governments: {list(govs.keys())}")
    
    for year in range(1, SIMULATION_YEARS + 1):
        print(f"\n{'='*40}")
        print(f"YEAR {year}")
        print(f"{'='*40}")
        
        # =============================================
        # Phase 0: Annual Reset
        # =============================================
        for hh in households:
            hh.reset_insurance()
        
        # =============================================
        # Phase 1: Institutional Decisions
        # =============================================
        for gov_id, gov in govs.items():
            gov.reset_annual_budget(year)
        ins.reset_annual_metrics()
        
        # =============================================
        # Phase 2: Household Decisions
        # =============================================
        actions = {"do_nothing": 0, "buy_insurance": 0, "elevate_house": 0, "relocate": 0}
        validation_warnings = 0
        validation_errors = 0
        
        for hh in households:
            if hh.state.relocated:
                continue
            
            # Get region-specific government
            gov = govs.get(hh.state.region_id, govs["NJ"])
            
            # Build context
            context = {
                "government_subsidy_rate": gov.state.subsidy_rate,
                "insurance_premium_rate": ins.state.premium_rate,
                "flood_occurred": False,
                "year": year
            }
            
            # Get agent state dict
            state_dict = {
                "mg": hh.state.mg,
                "tenure": hh.state.tenure,
                "region_id": hh.state.region_id,
                "elevated": hh.state.elevated,
                "has_insurance": hh.state.has_insurance,
                "cumulative_damage": hh.state.cumulative_damage,
                "income": hh.state.income,
                "property_value": hh.state.property_value
            }
            
            # Get memory
            memories = hh.memory.retrieve(top_k=5, current_year=year)
            
            # Build prompt
            prompt = build_household_prompt(state_dict, context, memories)
            
            # Get LLM response or heuristic
            llm_response = call_llm(prompt)
            if llm_response is None:
                llm_response = generate_heuristic_response(hh, year, context)
            
            # Parse response
            output = parse_household_response(
                llm_response,
                hh.state.id,
                hh.state.mg,
                hh.state.tenure,
                year,
                hh.state.elevated
            )
            
            # Validate
            val_result = validator.validate(output, state_dict)
            if not val_result.valid:
                validation_errors += 1
                output.validated = False
                output.validation_errors.extend(val_result.errors)
            if val_result.warnings:
                validation_warnings += 1
            
            # Apply decision
            actions[output.decision_skill] = actions.get(output.decision_skill, 0) + 1
            hh.apply_decision(output)
            
            # Audit
            audit.write_household_trace(output, state_dict, context)
        
        print(f"Actions: {actions}")
        print(f"Validation: {validation_errors} errors, {validation_warnings} warnings")
        
        # =============================================
        # Phase 3: Settlement
        # =============================================
        report = settlement.process_year(year, households, ins, govs["NJ"])
        
        if report.flood_occurred:
            print(f"🌊 FLOOD! Damage: ${report.total_damage:,.0f}, Claims: ${report.total_claims:,.0f}")
        else:
            print("No flood.")
        
        # Cumulative stats
        cum_insured = sum(1 for h in households if h.state.has_insurance)
        cum_elevated = sum(1 for h in households if h.state.elevated)
        cum_relocated = sum(1 for h in households if h.state.relocated)
        print(f"Cumulative: Insured={cum_insured}, Elevated={cum_elevated}, Relocated={cum_relocated}")
    
    # =============================================
    # Finalize
    # =============================================
    summary = audit.finalize()
    print(f"\n{'='*60}")
    print("SIMULATION COMPLETE")
    print(f"{'='*60}")
    print(f"Total household decisions: {summary['total_household_decisions']}")
    print(f"Decision distribution: {summary.get('decision_rates', {})}")
    print(f"Validation failure rate: {summary.get('validation_failure_rate', 'N/A')}")


if __name__ == "__main__":
    run_simulation()
