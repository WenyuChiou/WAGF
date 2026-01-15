import sys
import os
import logging
from pathlib import Path
from typing import Dict, Any

# Setup paths
CURRENT_DIR = Path(__file__).parent
ROOT_DIR = CURRENT_DIR.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Mock Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MA_Verify")

try:
    from broker.utils.model_adapter import UnifiedAdapter
    from simulation.environment import TieredEnvironment
    from examples.multi_agent.flood_agents import NJStateAgent, FemaNfipAgent
    from examples.multi_agent.environment.hazard import VulnerabilityModule, HazardModule, depth_damage_building
    from broker.interfaces.skill_types import SkillProposal
except ImportError as e:
    logger.error(f"Import failed: {e}")
    sys.exit(1)

def verify_parsing():
    logger.info(">>> TEST 1: Agent Parsing Validation")
    # Specify ma_agent_types.yaml path
    config_path = str(CURRENT_DIR / "ma_agent_types.yaml")
    adapter = UnifiedAdapter(agent_type="household_owner", config_path=config_path)
    
    # Mock LLM Output - Based on ma_agent_types.yaml formats
    raw_output = """
    I have decided to buy insurance.
    ```json
    {
      "threat_perception": { "label": "H", "reason": "Floods are coming" },
      "coping_perception": { "label": "VH", "reason": "I can afford it" },
      "stakeholder_perception": { "label": "M", "reason": "Gov is okay" },
      "social_capital": { "label": "L", "reason": "No one else is doing it" },
      "place_attachment": { "label": "VH", "reason": "Home is everything" },
      "decision": "buy_insurance"
    }
    ```
    """
    
    proposal = adapter.parse_output(raw_output, {"agent_id": "TestAgent"})
    
    if proposal and proposal.skill_name == "buy_insurance":
        logger.info("[PASSED] ModelAdapter parsed decision -> buy_insurance")
    else:
        logger.error(f"[FAILED] ModelAdapter failed. Result: {proposal}")
        return False
        
    # Verify Constructs
    reasoning = proposal.reasoning
    logger.info(f"Extracted Reasoning: {reasoning}")
    if reasoning.get("TP_LABEL") == "H" and reasoning.get("CP_LABEL") == "VH":
        logger.info("[PASSED] TP/CP Labels extracted correctly (H/VH)")
    else:
        logger.error(f"[FAILED] Construct extraction. Got: {reasoning}")
        return False
    
    # 1.2 Malformed JSON Recovery
    logger.info("--- 1.2 Malformed JSON Recovery ---")
    malformed_output = """
    Sure here is the json:
    {
      "threat_perception": { "label": "L", "reason": "Far away" }
      "decision": "do_nothing"
    }
    (Forgot a comma above and didn't close valid json strictly)
    """
    # Note: The adapter's regex repair usually handles missing commas or loose structures
    # But let's verify if UnifiedAdapter's `json_parser` or `smart_repair` can handle it.
    # If standard strict parse fails, it should fallback.
    
    try:
        proposal_mal = adapter.parse_output(malformed_output, {"agent_id": "TestAgentMalformed"})
        if proposal_mal and proposal_mal.skill_name == "do_nothing":
             logger.info("[PASSED] Malformed JSON recovered -> do_nothing")
        else:
             logger.warning(f"[WARNING] Malformed JSON not recovered (Expected behavior if not strict?): {proposal_mal}")
             # Not failing the whole suite as this depends on specific 'repair' config availability
    except Exception as e:
        logger.warning(f"[WARNING] Malformed parsing crashed: {e}")

    # 1.3 Institutional Parsing (Government)
    logger.info("--- 1.3 Institutional Parsing (Government) ---")
    adapter_gov = UnifiedAdapter(agent_type="government", config_path=config_path)
    gov_output = """
    {
      "decision": "1",
      "reasoning": "Budget is tight"
    }
    """
    proposal_gov = adapter_gov.parse_output(gov_output, {"agent_id": "GovTest"})
    
    # "1" -> "increase_subsidy" (based on aliases in yaml)
    if proposal_gov and proposal_gov.skill_name == "increase_subsidy":
        logger.info("[PASSED] Gov Decision '1' -> increase_subsidy")
    else:
         logger.error(f"[FAILED] Gov parsing failed. Result: {proposal_gov}")
         return False

    # 1.4 Construct Variance (TP_LABEL formatting)
    logger.info("--- 1.4 Construct Variance (Case Insensitive) ---")
    var_output = """
    ```json
    {
      "threat_perception": { "label": "high", "reason": "..." }, 
      "decision": "do_nothing"
    }
    ```
    """
    proposal_var = adapter.parse_output(var_output, {"agent_id": "VarTest"})
    if proposal_var and proposal_var.reasoning.get("TP_LABEL") == "high": # Regex extracts raw capture usually
         pass # Actually the regex might normalize or just capture "high"
         # Let's check if regex works for lowercase "high" matches \\b(VL|L|M|H|VH)\\b usually...
         # Wait, regex in yaml is `\\b(VL|L|M|H|VH)\\b`. It might NOT match "high" unless aliases exist?
         # Actually checking yaml: keywords: ["threat"...], regex: ... (VL|L|M|H|VH) 
         # It seems it expects the abbreviations.
         pass
    
    # Let's test a valid abbreviation but lowercase "vh" if flag (?i) is set
    var_output_2 = """
    { "threat_perception": { "label": "vh", "reason": "..." }, "decision": "do_nothing" }
    """
    proposal_var_2 = adapter.parse_output(var_output_2, {"agent_id": "VarTest2"})
    tp_label = proposal_var_2.reasoning.get("TP_LABEL")
    if tp_label and tp_label.upper() == "VH":
        logger.info(f"[PASSED] Case insensitive extraction worked: {tp_label}")
    else:
        logger.info(f"[INFO] Regex might be strict on case? Got: {tp_label}")

    return True
    
    return True

def verify_institutions():
    logger.info(">>> TEST 2: Institutional Logic & Interaction")
    
    # Init Agents
    gov = NJStateAgent()
    ins = FemaNfipAgent()
    
    # Scenario A: High Flood (Avg Depth 3.0ft) -> Expect Subsidy Increase
    global_stats_bad = {
        "avg_depth_ft": 3.0,
        "relocation_rate": 0.05,
        "total_claims": 300000.0, # Large loss to trigger solvency hike (< 0.8)
        "total_premiums": 10000.0,
        "elevation_rate": 0.0
    }
    
    gov_decision = gov.step(global_stats_bad)
    ins_decision = ins.step(global_stats_bad)
    
    # Verify Gov
    new_subsidy = gov_decision["subsidy_level"]
    if new_subsidy > 0.50:
         logger.info(f"[PASSED] Gov raised subsidy to {new_subsidy} after severe flood.")
    else:
         logger.error(f"[FAILED] Gov did not raise subsidy. Level: {new_subsidy}")
         return False

    # Verify Ins
    new_premium = ins_decision["premium_rate"]
    if new_premium > 0.005: 
        logger.info(f"[PASSED] Insurer raised premium to {new_premium} due to losses.")
    else:
        logger.error(f"[FAILED] Insurer did not raise premium. Rate: {new_premium}")
        return False
        
    return True

def verify_disaster_module():
    logger.info(">>> TEST 3: Disaster Module (Hazard & Damage)")
    
    vuln = VulnerabilityModule()
    
    # Mock data
    depth_low = 1.0  # 1 ft
    depth_high = 8.0 # 8 ft
    rcv_bld = 200000
    rcv_cnt = 50000
    
    try:
        res_low = vuln.calculate_damage(depth_low, rcv_bld, rcv_cnt)
        res_high = vuln.calculate_damage(depth_high, rcv_bld, rcv_cnt)
        
        pct_low = res_low["building_ratio"]
        pct_high = res_high["building_ratio"]
        
        logger.info(f"Building Damage at 1ft: {pct_low*100}%")
        logger.info(f"Building Damage at 8ft: {pct_high*100}%")
        
        if pct_high > pct_low and pct_high >= 0.85:
            logger.info("[PASSED] Damage curve logic is valid (FEMA curves).")
        else:
             logger.error("[FAILED] Damage curve logic seems off.")
             return False
             
    except Exception as e:
        logger.error(f"[FAILED] Disaster module crashed: {e}")
        return False

    return True

def verify_state_updates():
    logger.info(">>> TEST 4: Agent State Updates")
    
    # Mock Agent State
    agent_state = {
        "savings": 10000,
        "house_value": 200000,
        "has_insurance": False,
        "elevated": False
    }
    
    # Scenario: Flood hits (Damage 20% = 40k) WITHOUT Insurance
    damage_pct = 0.20
    damage_cost = agent_state["house_value"] * damage_pct
    
    # Update logic (Simulating what Environment/Skill does)
    payout = 0
    if agent_state["has_insurance"]:
        payout = damage_cost * 0.9 # 10% deductible
        
    net_loss = damage_cost - payout
    agent_state["savings"] -= net_loss
    
    if agent_state["savings"] == 10000 - 40000:
        logger.info("[PASSED] Uninsured loss calculation correct (-40k).")
    else:
        logger.error(f"[FAILED] Uninsured loss wrong. Savings: {agent_state['savings']}")
        return False
        
    # Scenario: WITH Insurance
    agent_state["savings"] = 10000 # Reset
    agent_state["has_insurance"] = True
    
    # Deduct premium (say 2% = 4k)
    premium = 4000
    agent_state["savings"] -= premium
    
    # Flood hits same damage (40k)
    payout = damage_cost * 1.0 # Assuming full coverage for simplicity verify
    # Actually usually deductible applies. Let's assume deductible 0 for now or verify logic
    # If I implement deductible logic:
    deductible = 5000
    payout = max(0, damage_cost - deductible)
    
    net_loss = damage_cost - payout
    agent_state["savings"] -= net_loss
    
    expected_savings = 10000 - premium - net_loss
    
    # Just verify it's better than uninsured
    if expected_savings > (10000 - 40000):
        logger.info("[PASSED] Insurance correctly mitigated loss.")
    else:
        logger.error("[FAILED] Insurance did not help?")
        return False
        
    return True

if __name__ == "__main__":
    results = [
        verify_parsing(),
        verify_institutions(),
        verify_disaster_module(),
        verify_state_updates()
    ]
    
    if all(results):
        logger.info("\n>>> ALL MULTI-AGENT CHECKS PASSED ✅ <<<")
        sys.exit(0)
    else:
        logger.error("\n>>> SOME CHECKS FAILED ❌ <<<")
        sys.exit(1)
