"""
Flood Adaptation Trust Update Rules
動態信任更新邏輯 (對齊 LLMABMPMT-Final.py)
"""


class TrustUpdateManager:
    """
    管理 PMT 信任動態更新
    完整對齊原始 LLMABMPMT-Final.py 的四種情境
    """
    
    def update_insurance_trust(
        self,
        current_trust: float,
        has_insurance: bool,
        flooded_this_year: bool
    ) -> float:
        """
        更新保險信任
        
        四種情境:
        A. 有保險 + 洪水 ("The Hassle") → -0.10
        B. 有保險 + 安全 ("Peace of Mind") → +0.02
        C. 無保險 + 洪水 ("Hard Lesson") → +0.05
        D. 無保險 + 安全 ("Gambler's Reward") → -0.02
        """
        if has_insurance:
            if flooded_this_year:
                # Scenario A: Insured + Flooded ("The Hassle")
                current_trust -= 0.10
            else:
                # Scenario B: Insured + Safe ("Peace of Mind")
                current_trust += 0.02
        else:
            if flooded_this_year:
                # Scenario C: Not Insured + Flooded ("Hard Lesson")
                current_trust += 0.05
            else:
                # Scenario D: Not Insured + Safe ("Gambler's Reward")
                current_trust -= 0.02
        
        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, current_trust))
    
    def update_neighbor_trust(
        self,
        current_trust: float,
        community_action_rate: float,
        flooded_this_year: bool
    ) -> float:
        """
        更新鄰居信任 (Social Proof)
        
        規則:
        - 社區行動率 > 30% → +0.04
        - 洪水發生 + 社區行動率 < 10% → -0.05
        - 其他 → -0.01 (默認衰減)
        """
        if community_action_rate > 0.30:
            current_trust += 0.04
        elif flooded_this_year and community_action_rate < 0.10:
            current_trust -= 0.05
        else:
            current_trust -= 0.01
        
        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, current_trust))


def update_trust_after_step(
    agent_state: dict,
    flooded_this_year: bool,
    community_action_rate: float
) -> dict:
    """
    完整的年度信任更新邏輯
    
    Returns:
        Updated trust values dict
    """
    manager = TrustUpdateManager()
    
    # 更新保險信任
    new_insurance_trust = manager.update_insurance_trust(
        agent_state["trust_in_insurance"],
        agent_state["has_insurance"],
        flooded_this_year
    )
    
    # 更新鄰居信任
    new_neighbor_trust = manager.update_neighbor_trust(
        agent_state["trust_in_neighbors"],
        community_action_rate,
        flooded_this_year
    )
    
    return {
        "trust_in_insurance": new_insurance_trust,
        "trust_in_neighbors": new_neighbor_trust,
        "trust_insurance_delta": new_insurance_trust - agent_state["trust_in_insurance"],
        "trust_neighbors_delta": new_neighbor_trust - agent_state["trust_in_neighbors"]
    }
