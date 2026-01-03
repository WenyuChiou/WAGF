"""
Flood Adaptation Prompt Template
完整對齊原始 LLMABMPMT-Final.py 的 prompt 設計
"""

# 主 Prompt 模板
PROMPT_TEMPLATE = """You are a homeowner in a city, with a strong attachment to your community. {elevation_status}
Your memory includes:
{memory}

You currently {insurance_status} flood insurance.
You {trust_insurance_text} the insurance company. You {trust_neighbors_text} your neighbors' judgment.

Using the Protection Motivation Theory, evaluate your current situation by considering the following factors:
- Perceived Severity: How serious the consequences of flooding feel to you.
- Perceived Vulnerability: How likely you think you are to be affected.
- Response Efficacy: How effective you believe each action is.
- Self-Efficacy: Your confidence in your ability to take that action.
- Response Cost: The financial and emotional cost of the action.
- Maladaptive Rewards: The benefit of doing nothing immediately.

Now, choose one of the following actions:
{options}
Note: If no flood occurred this year, since no immediate threat, most people would choose "Do Nothing."
{flood_status}

Please respond using the exact format below. Do NOT include any markdown symbols:
Threat Appraisal: [One sentence summary of how threatened you feel by any remaining flood risks.]
Coping Appraisal: [One sentence summary of how well you think you can cope or act.]
Final Decision: [Choose {valid_choices} only]
"""

# 加高狀態文字
ELEVATION_STATUS = {
    "elevated": "Your house is already elevated, which provides very good protection.",
    "not_elevated": "You have not elevated your home."
}

# 保險狀態文字
INSURANCE_STATUS = {
    "has_insurance": "have",
    "no_insurance": "do not have"
}

# 選項文字 (非加高)
OPTIONS_NON_ELEVATED = """1. Buy flood insurance (Lower cost, provides partial financial protection but does not reduce physical damage.)
2. Elevate your house (High upfront cost but can prevent most physical damage.)
3. Relocate (Requires leaving your neighborhood but eliminates flood risk permanently.)
4. Do nothing (Require no financial investment or effort this year, but it might leave you exposed to future flood damage.)"""

# 選項文字 (已加高)
OPTIONS_ELEVATED = """1. Buy flood insurance (Lower cost, provides partial financial protection but does not reduce physical damage.)
2. Relocate (Requires leaving your neighborhood but eliminates flood risk permanently.)
3. Do nothing (Require no financial investment or effort this year, but it might leave you exposed to future flood damage.)"""

# 洪水狀態文字
FLOOD_STATUS = {
    "flood": "A flood occurred this year, causing significant damage to the area.",
    "no_flood": "No flood occurred this year."
}


def verbalize_trust(trust_value: float, trust_type: str) -> str:
    """
    將數值信任轉換為自然語言描述
    對齊原始 LLMABMPMT-Final.py
    """
    if trust_type == "insurance":
        if trust_value >= 0.7:
            return "have high confidence in"
        elif trust_value >= 0.4:
            return "have moderate trust in"
        elif trust_value >= 0.2:
            return "have some doubts about"
        else:
            return "strongly distrust"
    elif trust_type == "neighbors":
        if trust_value >= 0.7:
            return "highly value"
        elif trust_value >= 0.4:
            return "somewhat consider"
        elif trust_value >= 0.2:
            return "slightly doubt"
        else:
            return "do not trust"
    return "have neutral feelings about"


def build_prompt(agent_state: dict, env_state: dict) -> str:
    """構建完整 prompt"""
    # 加高狀態
    elevation_status = ELEVATION_STATUS["elevated"] if agent_state["elevated"] else ELEVATION_STATUS["not_elevated"]
    
    # 保險狀態
    insurance_status = INSURANCE_STATUS["has_insurance"] if agent_state["has_insurance"] else INSURANCE_STATUS["no_insurance"]
    
    # 信任文字
    trust_insurance_text = verbalize_trust(agent_state["trust_in_insurance"], "insurance")
    trust_neighbors_text = verbalize_trust(agent_state["trust_in_neighbors"], "neighbors")
    
    # 記憶
    memory = "\n".join(f"- {m}" for m in agent_state.get("memory", []))
    
    # 選項
    if agent_state["elevated"]:
        options = OPTIONS_ELEVATED
        valid_choices = "1, 2, or 3"
    else:
        options = OPTIONS_NON_ELEVATED
        valid_choices = "1, 2, 3, or 4"
    
    # 洪水狀態
    flood_status = FLOOD_STATUS["flood"] if env_state.get("flood_event") else FLOOD_STATUS["no_flood"]
    
    return PROMPT_TEMPLATE.format(
        elevation_status=elevation_status,
        memory=memory,
        insurance_status=insurance_status,
        trust_insurance_text=trust_insurance_text,
        trust_neighbors_text=trust_neighbors_text,
        options=options,
        flood_status=flood_status,
        valid_choices=valid_choices
    )
