"""
Experiment 3: Multi-Agent Simulation (Consolidated Framework)

Components:
- Data Loader: Load agents
- Broker: Generic ContextBuilder, UnifiedAdapter
- Validators: Generic AgentValidator
- Agents: BaseAgent definitions (Household, Insurance, Government)
- Audit: AuditWriter
- LLM Client: Ollama

Output:
- household_audit.jsonl
- institutional_audit.jsonl
- audit_summary.json
"""

import sys
import os
import argparse
from typing import Dict, List, Any, Optional

sys.path.insert(0, '.')

from examples.exp3_multi_agent.data_loader import initialize_all_agents
from broker import GenericAuditWriter, GenericAuditConfig
from examples.exp3_multi_agent.agents import HouseholdAgent, HouseholdOutput
from examples.exp3_multi_agent.environment import SettlementModule
from examples.exp3_multi_agent.broker.memory_helpers import add_memory

# Consolidated Framework Imports
from broker.model_adapter import UnifiedAdapter
# from broker import create_context_builder # Used locally
from validators.agent_validator import AgentValidator
from examples.exp3_multi_agent.broker import Exp3ContextBuilder, create_exp3_context_builder

# Configuration
DEFAULT_YEARS = 10
OUTPUT_DIR = "examples/exp3_multi_agent/results"
SEED = 42
DEFAULT_MODEL = "llama3.2:3b"

CONFIG = {
    "years": DEFAULT_YEARS,
    "use_llm": True,
    "model": DEFAULT_MODEL,
    "output_dir": OUTPUT_DIR
}

# =============================================================================
# LLM CLIENT
# =============================================================================

def call_llm(prompt: str) -> Optional[str]:
    """Call Ollama LLM."""
    if not CONFIG["use_llm"]:
        return None
    
    try:
        import requests
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": CONFIG["model"], "prompt": prompt, "stream": False},
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get("response", "")
        print(f"[LLM] HTTP {response.status_code}")
        return None
    except Exception as e:
        print(f"[LLM] Error: {e}")
        return None

def generate_heuristic_response(agent: HouseholdAgent, context: dict) -> str:
    """Generate heuristic response in Unified/PMT format."""
    s = agent.state
    is_elevated = s.elevated
    is_owner = s.tenure == "Owner"
    
    # Calculate constructs
    tp = "H" if s.cumulative_damage > s.property_value * 0.1 else ("M" if s.cumulative_damage > 0 else "L")
    cp = "H" if s.income > 60000 else ("M" if s.income > 35000 else "L")
    sp = "H" if context.get("government_subsidy_rate", 0.5) >= 0.5 else "M"
    sc = "M"
    pa = "FULL" if s.elevated and s.has_insurance else ("PARTIAL" if s.elevated or s.has_insurance else "NONE")
    
    # Decision Logic
    decision = "do_nothing"
    reason = "Status quo"
    
    if s.relocated:
        pass
    elif tp == "H" and not s.has_insurance:
        decision = "buy_insurance" if is_owner else "buy_contents_insurance"
        reason = "High threat, need protection"
    elif tp in ["M", "H"] and not is_elevated and is_owner and sp == "H":
        decision = "elevate_house"
        reason = "Good subsidy for elevation"
    elif s.cumulative_damage > s.property_value * 0.5 and s.income < 40000:
        decision = "buyout_program" if is_owner else "relocate"
        reason = "Extreme damage, moving out"
        
    return f"""
INTERPRET: Heuristic decision based on damage ${s.cumulative_damage}
PMT_EVAL: TP={tp} CP={cp} SP={sp} SC={sc} PA={pa}
DECIDE: {decision}
REASON: {reason}
"""

# =============================================================================
# MAIN SIMULATION
# =============================================================================

def run_simulation():
    print(f"=" * 60)
    print(f"Exp3 Consolidated Multi-Agent Simulation")
    print(f"Model: {CONFIG['model']}, LLM: {CONFIG['use_llm']}")
    print(f"=" * 60)
    
    # Initialize Agents & Modules
    # Initialize Agents & Modules
    households, govs, ins = initialize_all_agents(seed=SEED)
    settlement = SettlementModule(seed=SEED)
    
    # Generic Audit Writer
    audit = GenericAuditWriter(GenericAuditConfig(
        output_dir=CONFIG["output_dir"],
        experiment_name=f"exp3_{CONFIG['model']}"
    ))
    
    # Initialize Generic Components
    validator = AgentValidator()
    
    # Context Builder (Generic)
    all_agents_map = {}
    all_agents_map[ins.state.id] = ins
    for gid, g in govs.items():
        all_agents_map[gid] = g
    for hh in households:
        all_agents_map[hh.state.id] = hh
        
    # Adapters per type
    adapters = {
        "insurance": UnifiedAdapter(agent_type="insurance"),
        "government": UnifiedAdapter(agent_type="government"),
        "household": UnifiedAdapter(agent_type="household")
    }
    
    # Track flood history
    prev_year_flood = False
    
    for year in range(1, CONFIG['years'] + 1):
        print(f"\n{'='*40}\nYEAR {year}\n{'='*40}")
        
        # --- Phase 0: Reset & Observation ---
        for hh in households:
            hh.reset_insurance()
            
        elevated_count = sum(1 for h in households if h.state.elevated)
        insured_count = sum(1 for h in households if h.state.has_insurance)
        
        # Shared Environment State
        env_state = {
            "year": year,
            "flood_occurred": prev_year_flood,
            "elevated_count_norm": elevated_count / len(households),
            "insured_count_norm": insured_count / len(households)
        }
        
        # Create ContextBuilder for this year's environment (Exp3 Specific)
        # Using local extension to handle SP calculation and environment mapping
        context_builder = create_exp3_context_builder(
            agents=all_agents_map,
            environment=env_state,
            load_yaml=True
        )
        
        # --- Phase 1: Institutional Decisions ---
        # 1. Insurance Agent
        ins.reset_annual_metrics()
        prev_premium = ins.state.premium_rate
        
        # Build Context & Prompt
        ctx = context_builder.build(ins.state.id, include_raw=True)
        prompt = context_builder.format_prompt(ctx)
        
        # Get Response
        response = call_llm(prompt)
        
        # Parse & Execute
        prop = adapters["insurance"].parse_output(response or "", {"agent_id": ins.state.id})
        
        # Fallback if no LLM
        if not response:
            # Simple heuristic
            action = ins.decide_strategy(year) # Legacy method
            prop.skill_name = action
            if action == "raise_premium": prop.reasoning["adjustment"] = 0.10
            elif action == "lower_premium": prop.reasoning["adjustment"] = 0.05
        
        # Validation
        val_res = validator.validate(
            agent_type="insurance",
            agent_id=ins.state.id,
            decision=prop.skill_name,
            state={"premium_rate": ins.state.premium_rate, "solvency": ins.solvency}, # Simplified state check
            prev_state={"premium_rate": prev_premium}
        )
        
        # Execute (Simplified for Exp3)
        if prop.skill_name in ["RAISE", "raise_premium"]:
            adj = prop.reasoning.get("adjustment", 0.05)
            ins.state.premium_rate = min(0.15, ins.state.premium_rate * (1 + adj))
        elif prop.skill_name in ["LOWER", "lower_premium"]:
            adj = prop.reasoning.get("adjustment", 0.05)
            ins.state.premium_rate = max(0.02, ins.state.premium_rate * (1 - adj))

        # Audit
        trace = {
            "agent_id": ins.state.id,
            "year": year,
            "decision": prop.skill_name,
            "reasoning": prop.reasoning,
            "state": ins.get_all_state_raw()
        }
        audit.write_trace("insurance", trace, val_res)
        
        # 2. Government Agents
        for gov_id, gov in govs.items():
            gov.reset_annual_budget(year)
            
            # Update env for specific region if needed
            env_state["government_subsidy_rate"] = gov.state.subsidy_rate
            env_state["insurance_premium_rate"] = ins.state.premium_rate
            
            ctx = context_builder.build(gov.state.id, include_raw=True)
            prompt = context_builder.format_prompt(ctx)
            
            response = call_llm(prompt)
            prop = adapters["government"].parse_output(response or "", {"agent_id": gov_id})
            
            if not response:
                action = gov.decide_policy(year, prev_year_flood)
                prop.skill_name = action
                if "increase" in action: prop.reasoning["adjustment"] = 0.10
                elif "decrease" in action: prop.reasoning["adjustment"] = 0.10
            
            val_res = validator.validate(
                agent_type="government",
                agent_id=gov_id,
                decision=prop.skill_name,
                state=gov.get_all_state()
            )
            
            # Execute
            if prop.skill_name in ["INCREASE", "increase_subsidy"]:
                adj = prop.reasoning.get("adjustment", 0.10)
                gov.state.subsidy_rate = min(0.95, gov.state.subsidy_rate + adj)
            elif prop.skill_name in ["DECREASE", "decrease_subsidy"]:
                adj = prop.reasoning.get("adjustment", 0.10)
                gov.state.subsidy_rate = max(0.20, gov.state.subsidy_rate - adj)
            
            # Audit
            trace = {
                "agent_id": gov_id,
                "year": year,
                "decision": prop.skill_name,
                "reasoning": prop.reasoning,
                "state": gov.get_all_state_raw()
            }
            audit.write_trace("government", trace, val_res)

        # --- Phase 2: Household Decisions ---
        actions_count = {}
        total_hh = len(households)
        
        for i, hh in enumerate(households):
            if (i + 1) % 10 == 0:
                print(f"   [Progress] Year {year}: Processed {i+1}/{total_hh} agents...", flush=True)

            if hh.state.relocated:
                continue
            
            gov = govs.get(hh.state.region_id)
            env_state["government_subsidy_rate"] = gov.state.subsidy_rate
            env_state["insurance_premium_rate"] = ins.state.premium_rate
            env_state["subsidy_rate"] = gov.state.subsidy_rate
            env_state["premium_rate"] = ins.state.premium_rate
            env_state["flood"] = "YES" if prev_year_flood else "NO"
            env_state["flood_occurred"] = False # Before flood this year
            
            # Pass environment in context to context_builder (handled internally)
            context_builder.environment = env_state 
            
            ctx = context_builder.build(hh.state.id, include_memory=True, include_raw=True)
            
            # Note: SP (Subsidy Perception) is now automatically calculated by Exp3ContextBuilder
            # based on env_state["subsidy_rate"]
            
            prompt = context_builder.format_prompt(ctx)
            
            response = call_llm(prompt)
            if not response:
                response = generate_heuristic_response(hh, env_state)
                
            prop = adapters["household"].parse_output(response, {"agent_id": hh.state.id, "is_elevated": hh.state.elevated})
            
            # Validate
            val_res = validator.validate(
                agent_type=hh.agent_type,
                agent_id=hh.state.id,
                decision=prop.skill_name,
                state=hh.get_all_state(),
                reasoning=prop.reasoning  # Pass PMT labels for coherence check
            )
            prop.confidence = 1.0 if not val_res else 0.5 # Simple degradation
            
            # Execute
            # Map HouseholdOutput compatible structure for legacy apply_decision
            output = HouseholdOutput(
                agent_id=hh.state.id,
                mg=hh.state.mg,
                tenure=hh.state.tenure,
                year=year,
                tp_level=prop.reasoning.get("TP", "MODERATE"),
                tp_explanation=prop.reasoning.get("TP_REASON", ""),
                cp_level=prop.reasoning.get("CP", "MODERATE"),
                cp_explanation=prop.reasoning.get("CP_REASON", ""),
                sp_level=prop.reasoning.get("SP", "MODERATE"),
                sp_explanation=prop.reasoning.get("SP_REASON", ""),
                sc_level=prop.reasoning.get("SC", "MODERATE"),
                sc_explanation=prop.reasoning.get("SC_REASON", ""),
                pa_level=prop.reasoning.get("PA", "NONE"),
                pa_explanation=prop.reasoning.get("PA_REASON", ""),
                decision_number=0,
                decision_skill=prop.skill_name
            )
            
            hh.apply_decision(output)
            add_memory(hh.memory, "decision", {"skill_id": prop.skill_name}, year)
            
            # Audit
            constructs = {
                "TP": {"level": prop.reasoning.get("TP", "N/A"), "explanation": prop.reasoning.get("TP_REASON", "")},
                "CP": {"level": prop.reasoning.get("CP", "N/A"), "explanation": prop.reasoning.get("CP_REASON", "")},
                "SP": {"level": prop.reasoning.get("SP", "N/A"), "explanation": prop.reasoning.get("SP_REASON", "")},
                "SC": {"level": prop.reasoning.get("SC", "N/A"), "explanation": prop.reasoning.get("SC_REASON", "")},
                "PA": {"level": prop.reasoning.get("PA", "N/A"), "explanation": prop.reasoning.get("PA_REASON", "")}
            }
            
            trace = {
                "agent_id": hh.state.id,
                "year": year,
                "decision": prop.skill_name,
                "reasoning": prop.reasoning,
                "constructs": constructs,
                "state": hh.get_all_state_raw(),
                "state_norm": hh.get_all_state()
            }
            audit.write_trace("household", trace, val_res)
            
            actions_count[prop.skill_name] = actions_count.get(prop.skill_name, 0) + 1
            
        print(f"Actions: {actions_count}")
        
        # --- Phase 3: Settlement ---
        report = settlement.process_year(year, households, ins, govs["NJ"])
        if report.flood_occurred:
            print(f"🌊 FLOOD! Damage: ${report.total_damage:,.0f}")
            for hh in households:
                if not hh.state.relocated and hasattr(hh.state, 'last_year_damage'):
                    dmg = getattr(hh.state, 'last_year_damage', 0)
                    if dmg > 0:
                        add_memory(hh.memory, "flood", {"damage": dmg}, year)
        
        prev_year_flood = report.flood_occurred
        
    audit.finalize()
    print("SIMULATION COMPLETE")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=DEFAULT_YEARS)
    parser.add_argument("--use-llm", action="store_true")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    args = parser.parse_args()
    
    CONFIG.update(vars(args))
    run_simulation()
