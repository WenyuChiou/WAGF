# Government Agent 完整規格

## 1. 角色定位

**職責:** 透過補貼政策促進弱勢家庭 (MG) 採取洪水減災措施

**決策時機:** 每年 Phase 1 (與 Insurance 同時，在 Household 決策前)

**參考:** FEMA HMGP (75% 聯邦補助), FMA Program

---

## 2. State 定義

```python
@dataclass
class GovernmentAgentState:
    """Government Agent 完整狀態"""
    
    # === 身份 ===
    id: str = "Government"
    
    # === 預算 ===
    annual_budget: float = 500_000    # 年度預算
    budget_remaining: float = 500_000  # 剩餘預算
    total_spent: float = 0            # 累計支出
    
    # === 補助政策 ===
    subsidy_rate: float = 0.50        # 補助比例 (50%)
    mg_priority: bool = True          # MG 優先
    buyout_available: bool = True     # 收購計畫可用
    
    # === 統計 ===
    applications_received: int = 0    # 收到申請數
    applications_approved: int = 0    # 批准數
    
    # === 追蹤 ===
    mg_adoption_rate: float = 0.0     # MG 採用率
    nmg_adoption_rate: float = 0.0    # NMG 採用率
```

---

## 3. Memory 設計

```python
@dataclass
class GovernmentMemory:
    """Government Agent 記憶"""
    
    window_size: int = 5
    
    # 年度政策記錄
    policy_records: List[Dict] = field(default_factory=list)
    # 結構: {"year": 1, "subsidy_rate": 0.50, "mg_adoption": 0.25, 
    #        "budget_used": 100000, "flood_occurred": True}
    
    # 重大政策事件
    policy_events: List[str] = field(default_factory=list)
    # 例: "Year 3: Post-flood emergency subsidy increase to 80%"
    
    def add_year_record(self, year: int, subsidy_rate: float,
                        mg_adoption: float, budget_used: float,
                        flood_occurred: bool) -> None:
        """添加年度記錄"""
        self.policy_records.append({
            "year": year,
            "subsidy_rate": subsidy_rate,
            "mg_adoption": mg_adoption,
            "budget_used": budget_used,
            "flood_occurred": flood_occurred
        })
        if len(self.policy_records) > self.window_size:
            self.policy_records.pop(0)
        
        # 檢測重大事件
        if flood_occurred and mg_adoption < 0.30:
            self.policy_events.append(
                f"Year {year}: Low MG adoption ({mg_adoption:.0%}) during flood year"
            )
    
    def format_for_prompt(self) -> str:
        """格式化為 LLM prompt"""
        lines = ["Policy History:"]
        for r in self.policy_records[-3:]:
            flood_str = " [FLOOD]" if r["flood_occurred"] else ""
            lines.append(
                f"- Year {r['year']}{flood_str}: Subsidy {r['subsidy_rate']:.0%}, "
                f"MG adoption {r['mg_adoption']:.0%}, Spent ${r['budget_used']:,.0f}"
            )
        return "\n".join(lines)
```

---

## 4. Skills

### 4.1 核心 Skills (Exp3 MVP)

| Skill | 條件 | 調整幅度 | 約束 |
|-------|------|----------|------|
| `increase_subsidy` | 災後 + MG 採用率 < 30% | +10-20% | 最高 80% |
| `decrease_subsidy` | 預算不足 OR 採用率 > 60% | -10-20% | 最低 30% |
| `maintain_subsidy` | 其他情況 | 0% | 默認 |

### 4.2 擴展 Skills (候選名單)

| Skill | 說明 | 優先級 | 備註 |
|-------|------|--------|------|
| `announce_policy` | 公布政策變化 | P1 | LLM 生成公告 |
| `target_mg_outreach` | 針對 MG 戶主動聯繫 | P1 | 提高知曉度 |
| `approve_buyout` | 批准收購申請 | P2 | 個案決策 |
| `emergency_fund` | 災後緊急撥款 | P2 | 預算外機制 |
| `adjust_eligibility` | 調整補助資格 | P3 | 政策調整 |

---

## 5. 決策流程

```
每年開始 (Phase 1):
┌─────────────────────────────────────────┐
│  1. 收集上年數據                         │
│     - mg_adoption_rate                  │
│     - flood_occurred                    │
│     - budget_remaining                  │
│                                         │
│  2. 更新 Memory                          │
│     memory.add_year_record(...)          │
│                                         │
│  3. 決策邏輯                             │
│     if flood_occurred AND               │
│        mg_adoption_rate < 0.30:         │
│         → increase_subsidy (10-20%)      │
│     elif budget_remaining < 0.20 *      │
│          annual_budget:                  │
│         → decrease_subsidy (10%)         │
│     elif mg_adoption_rate > 0.60:       │
│         → decrease_subsidy (10%)         │
│     else:                                │
│         → maintain_subsidy               │
│                                         │
│  4. 應用約束                             │
│     - 最高 80%                           │
│     - 最低 30%                           │
│                                         │
│  5. 重置年度預算                         │
│     budget_remaining = annual_budget     │
└─────────────────────────────────────────┘
```

---

## 6. Prompt 設計 (如使用 LLM)

```python
def build_government_prompt(agent: GovernmentAgentState,
                            memory: GovernmentMemory,
                            context: dict) -> str:
    return f"""You are a government agency managing flood adaptation subsidies.

Current Situation:
- Year: {context["year"]}
- Subsidy rate: {agent.subsidy_rate*100:.0f}%
- Budget remaining: ${agent.budget_remaining:,.0f} / ${agent.annual_budget:,.0f}
- MG household adoption rate: {agent.mg_adoption_rate:.1%}
- NMG household adoption rate: {agent.nmg_adoption_rate:.1%}
- Flood occurred this year: {"Yes" if context["flood_event"] else "No"}

{memory.format_for_prompt()}

Policy Constraints:
- Maximum subsidy rate: 80%
- Minimum subsidy rate: 30%
- Priority: Help Marginalized Groups (MG) adopt flood protection

Decision Guidelines:
- If flood occurred AND MG adoption < 30%: Consider increasing subsidy
- If budget is running low: Consider decreasing subsidy
- If MG adoption > 60%: Program is successful, can reduce subsidy

Respond in this format:
Analysis: [One sentence about current policy effectiveness]
Decision: [increase/decrease/maintain]
Adjustment: [percentage, e.g., 10%]
Priority: [MG/all]
Reason: [Brief explanation]"""
```

---

## 7. 輸出結構

```python
@dataclass
class GovernmentOutput:
    """Government Agent 年度輸出"""
    year: int
    
    # 決策前狀態
    previous_subsidy_rate: float
    mg_adoption_rate: float
    budget_used_pct: float
    flood_occurred: bool
    
    # 決策
    skill_name: str  # increase/decrease/maintain_subsidy
    adjustment_pct: float
    priority: str  # "MG" or "all"
    reason: str
    
    # 決策後狀態
    new_subsidy_rate: float
    
    # 驗證
    validated: bool = True
```

---

## 8. 與其他 Agent 互動

```
Government Agent
      │
      ├──→ Insurance Agent
      │     - 協調政策 (如 Flood Re 公私合作)
      │     - 分享市場數據
      │
      └──→ Household Agents
            - 發布補助政策 (透過 context)
            - 處理補助申請 (透過 simulation)
            - MG 可獲得額外補助
```

---

## 9. 環境層職責 (非 Agent Skill)

| 職責 | 組件 | 說明 |
|------|------|------|
| 補助計算 | Simulation.SubsidyModule | `subsidy = cost * subsidy_rate` |
| 申請處理 | Simulation.Settlement | 扣除預算、更新統計 |
| 資格判定 | Environment | 判斷 MG 是否符合條件 |

---

## 10. 待決定事項

1. **Buyout 機制?** 是否納入 Exp3 MVP
2. **預算來源?** 固定年度 or 災後增加
3. **多政策協調?** 聯邦/州/地方層級
