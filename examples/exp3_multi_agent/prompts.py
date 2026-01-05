"""
Multi-Agent Prompt Templates (Exp3) - Full Construct Assessment

Design:
- Survey data provides CONTEXT (MG status, tenure, etc.)
- LLM EVALUATES and OUTPUTS each construct (level + explanation)
- LLM makes decision with JUSTIFICATION
- All outputs captured for AUDIT trail
"""

from typing import Dict, Any, List

# =============================================================================
# HOUSEHOLD AGENT PROMPT
# =============================================================================

HOUSEHOLD_PROMPT = """You are a {tenure_type} living in a flood-prone city{mg_context}.

=== CONSTRUCT DEFINITIONS ===
Evaluate your situation using these 5 psychological constructs:

1. **TP (Threat Perception)**: How serious and likely is flood damage to you?
   - LOW: Flood risk feels minimal or unlikely
   - MODERATE: Some flood risk exists but manageable
   - HIGH: Serious flood threat feels imminent or very likely

2. **CP (Coping Perception)**: Can you afford and implement protective actions?
   - LOW: Financial or practical barriers prevent action
   - MODERATE: Some ability to act with effort or sacrifice
   - HIGH: Confident you can afford and implement protections

3. **SP (Subsidy Perception)**: How helpful is government/institutional support?
   - LOW: Little or no support expected
   - MODERATE: Some assistance available but limited
   - HIGH: Substantial government support is accessible

4. **SC (Self-Confidence)**: Do you believe you can successfully protect yourself?
   - LOW: Doubt your ability to take effective action
   - MODERATE: Some confidence but uncertainty remains
   - HIGH: Confident you can successfully adapt

5. **PA (Prior Adaptation)**: What protections do you already have?
   - NONE: No protective measures in place
   - PARTIAL: Some protection (insurance OR elevation)
   - FULL: Comprehensive protection (insurance AND elevation)

=== YOUR CURRENT SITUATION ===
{elevation_status}
{insurance_status}
{damage_history}

=== YOUR MEMORY ===
{memory}

=== THIS YEAR'S CONDITIONS ===
Year: {year}
{flood_status}
Government subsidy: {subsidy_rate:.0%} for elevation
Insurance premium: {premium_rate:.1%} of property value

=== YOUR TASK ===
1. Assess each construct based on your situation
2. Choose ONE action
3. Justify your decision

Available Actions:
{options}

=== OUTPUT FORMAT ===
Respond using EXACTLY this format (no markdown):

TP Assessment: [LOW/MODERATE/HIGH] - [One sentence explanation]
CP Assessment: [LOW/MODERATE/HIGH] - [One sentence explanation]
SP Assessment: [LOW/MODERATE/HIGH] - [One sentence explanation]
SC Assessment: [LOW/MODERATE/HIGH] - [One sentence explanation]
PA Assessment: [NONE/PARTIAL/FULL] - [One sentence explanation]
Final Decision: [Number only: {valid_choices}]
Justification: [2-3 sentences explaining why you chose this action based on your construct assessments]
"""

# Options based on agent type
OPTIONS_OWNER_NON_ELEVATED = """1. Buy flood insurance (Annual cost, financial protection)
2. Elevate your house (High cost, subsidy available, prevents damage)
3. Relocate (Leave neighborhood permanently)
4. Do nothing (No cost, remain exposed)"""

OPTIONS_OWNER_ELEVATED = """1. Buy flood insurance (Additional financial protection)
2. Relocate (Leave neighborhood permanently)
3. Do nothing (Your house has elevation protection)"""

OPTIONS_RENTER = """1. Buy renter's flood insurance (Protect belongings)
2. Relocate (Move to safer area)
3. Do nothing (No cost, belongings at risk)"""

# Context templates
MG_CONTEXT = {
    True: ", with limited financial resources",
    False: ""
}

TENURE_TYPE = {
    "Owner": "homeowner",
    "Renter": "renter"
}


def build_household_prompt(
    agent_state: Dict[str, Any],
    context: Dict[str, Any],
    memory: List[str]
) -> str:
    """
    Build prompt for Household Agent.
    
    Args:
        agent_state: Agent's current state (mg, tenure, elevated, etc.)
        context: Year's context (subsidy_rate, premium_rate, flood_occurred)
        memory: Retrieved memories from CognitiveMemory
    """
    
    # Demographics (from survey - as context)
    mg = agent_state.get("mg", False)
    tenure = agent_state.get("tenure", "Owner")
    elevated = agent_state.get("elevated", False)
    has_insurance = agent_state.get("has_insurance", False)
    cumulative_damage = agent_state.get("cumulative_damage", 0)
    property_value = agent_state.get("property_value", 300000)
    
    # Context
    subsidy_rate = context.get("government_subsidy_rate", 0.5)
    premium_rate = context.get("insurance_premium_rate", 0.05)
    flood_occurred = context.get("flood_occurred", False)
    year = context.get("year", 1)
    
    # Build components
    mg_context = MG_CONTEXT[mg]
    tenure_type = TENURE_TYPE[tenure]
    
    elevation_status = "Your house is ELEVATED (protected from most flood damage)." if elevated else "Your house is NOT elevated and vulnerable to flooding."
    insurance_status = "You currently HAVE flood insurance." if has_insurance else "You currently do NOT have flood insurance."
    
    if cumulative_damage > 0:
        damage_pct = cumulative_damage / property_value * 100 if property_value > 0 else 0
        damage_history = f"You have experienced ${cumulative_damage:,.0f} in past flood damage ({damage_pct:.1f}% of property value)."
    else:
        damage_history = "You have not experienced significant flood damage."
    
    # Memory
    if memory:
        memory_text = "\n".join(f"- {m}" for m in memory[-5:])
    else:
        memory_text = "- No significant past events recalled."
    
    # Flood status
    flood_status = "⚠️ A FLOOD occurred this year, causing damage in the area!" if flood_occurred else "No flood occurred this year."
    
    # Options
    if tenure == "Renter":
        options = OPTIONS_RENTER
        valid_choices = "1, 2, or 3"
    elif elevated:
        options = OPTIONS_OWNER_ELEVATED
        valid_choices = "1, 2, or 3"
    else:
        options = OPTIONS_OWNER_NON_ELEVATED
        valid_choices = "1, 2, 3, or 4"
    
    return HOUSEHOLD_PROMPT.format(
        tenure_type=tenure_type,
        mg_context=mg_context,
        elevation_status=elevation_status,
        insurance_status=insurance_status,
        damage_history=damage_history,
        memory=memory_text,
        year=year,
        flood_status=flood_status,
        subsidy_rate=subsidy_rate,
        premium_rate=premium_rate,
        options=options,
        valid_choices=valid_choices
    )


# =============================================================================
# INSURANCE AGENT PROMPT
# =============================================================================

INSURANCE_PROMPT = """You are the risk management AI for a flood insurance company.

=== CURRENT METRICS ===
- Loss Ratio: {loss_ratio:.1%} (Claims paid / Premiums collected)
- Active Policies: {total_policies}
- Risk Pool Balance: ${risk_pool:,.0f}
- Current Premium Rate: {premium_rate:.2%}

=== RECENT HISTORY ===
{history}

=== YOUR TASK ===
Analyze the current situation and decide on premium adjustment.

Options:
1. RAISE premium (improve solvency, may reduce uptake)
2. LOWER premium (attract customers, increase exposure)
3. MAINTAIN current premium

=== OUTPUT FORMAT ===
Analysis: [One sentence about current risk/financial situation]
Decision: [RAISE/LOWER/MAINTAIN]
Adjustment: [Percentage, e.g., 5%]
Justification: [Why this decision makes sense given the metrics]
"""

def build_insurance_prompt(state: Dict[str, Any], history: List[str]) -> str:
    """Build prompt for Insurance Agent."""
    history_text = "\n".join(f"- {h}" for h in history[-3:]) if history else "- No recent significant events."
    
    return INSURANCE_PROMPT.format(
        loss_ratio=state.get("loss_ratio", 0),
        total_policies=state.get("total_policies", 0),
        risk_pool=state.get("risk_pool", 1000000),
        premium_rate=state.get("premium_rate", 0.05),
        history=history_text
    )


# =============================================================================
# GOVERNMENT AGENT PROMPT
# =============================================================================

GOVERNMENT_PROMPT = """You are a government policy advisor managing flood mitigation subsidy programs.

=== BUDGET STATUS ===
- Annual Budget: ${annual_budget:,.0f}
- Remaining: ${budget_remaining:,.0f} ({budget_pct:.0%} remaining)
- Current Subsidy Rate: {subsidy_rate:.0%}

=== ADOPTION METRICS ===
- MG (Marginalized Group) Adoption Rate: {mg_adoption:.1%}
- NMG (Non-Marginalized) Adoption Rate: {nmg_adoption:.1%}

=== RECENT EVENTS ===
{events}

=== YOUR TASK ===
Analyze adoption rates and budget, then decide on subsidy policy.

Options:
1. INCREASE subsidy rate (faster adoption, faster budget depletion)
2. DECREASE subsidy rate (conserve budget, slower adoption)
3. MAINTAIN current rate

=== OUTPUT FORMAT ===
Analysis: [One sentence about adoption and budget situation]
Decision: [INCREASE/DECREASE/MAINTAIN]
Adjustment: [Percentage change, e.g., 10%]
Priority: [MG/ALL] - Which group to prioritize
Justification: [Why this policy decision serves the public interest]
"""

def build_government_prompt(state: Dict[str, Any], events: List[str]) -> str:
    """Build prompt for Government Agent."""
    events_text = "\n".join(f"- {e}" for e in events[-3:]) if events else "- No major recent events."
    
    budget_pct = state.get("budget_remaining", 500000) / state.get("annual_budget", 500000)
    
    return GOVERNMENT_PROMPT.format(
        annual_budget=state.get("annual_budget", 500000),
        budget_remaining=state.get("budget_remaining", 500000),
        budget_pct=budget_pct,
        subsidy_rate=state.get("subsidy_rate", 0.5),
        mg_adoption=state.get("mg_adoption_rate", 0),
        nmg_adoption=state.get("nmg_adoption_rate", 0),
        events=events_text
    )
