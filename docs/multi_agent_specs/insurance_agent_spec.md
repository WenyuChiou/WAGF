# Insurance Agent 完整規格

## 1. 角色定位

**職責:** 洪水保險市場的供給端，動態調整保費以維持財務穩健。

**決策時機:** 每年 Phase 1 (在 Household 決策前)

---

## 2. State 定義

```python
@dataclass
class InsuranceAgentState:
    """Insurance Agent 完整狀態"""
    
    # === 身份 ===
    id: str = "InsuranceCo"
    
    # === 核心財務 ===
    premium_rate: float = 0.05        # 基礎保費率 (5% of coverage)
    payout_ratio: float = 0.80        # 理賠比例 (損失的80%)
    risk_pool: float = 1_000_000      # 風險池餘額
    
    # === 年度統計 ===
    premium_collected: float = 0      # 本年保費收入
    claims_paid: float = 0            # 本年理賠支出
    total_policies: int = 0           # 有效保單數
    
    # === 計算屬性 ===
    @property
    def loss_ratio(self) -> float:
        """損失率 = 理賠 / 保費收入"""
        return self.claims_paid / max(self.premium_collected, 1)
    
    @property
    def uptake_rate(self) -> float:
        """投保率 (需從 simulation 獲取)"""
        return self.total_policies / 100  # 假設 100 agents
    
    # === 歷史記錄 (用於 Memory) ===
    premium_history: List[float] = field(default_factory=list)
    claims_history: List[float] = field(default_factory=list)
    loss_ratio_history: List[float] = field(default_factory=list)
```

---

## 3. Memory 設計

### 3.1 記憶類型

| 類型 | 內容 | 用途 |
|------|------|------|
| **年度統計** | loss_ratio, claims, premium | 決策參考 |
| **重大事件** | 災年理賠高峰、政策變化 | 情景記憶 |
| **市場趨勢** | uptake 變化、續保率 | 長期策略 |

### 3.2 Memory 結構

```python
@dataclass
class InsuranceMemory:
    """Insurance Agent 記憶"""
    
    # 滑動窗口記錄 (最近 5 年)
    window_size: int = 5
    
    # 年度記錄
    yearly_records: List[Dict] = field(default_factory=list)
    # 結構: {"year": 1, "loss_ratio": 0.45, "claims": 50000, "uptake": 0.35}
    
    # 重大事件 (長期記憶)
    significant_events: List[str] = field(default_factory=list)
    # 例: "Year 3: Major flood, claims exceeded $200K"
    
    def add_year_record(self, year: int, loss_ratio: float, 
                        claims: float, uptake: float) -> None:
        """添加年度記錄"""
        self.yearly_records.append({
            "year": year,
            "loss_ratio": loss_ratio,
            "claims": claims,
            "uptake": uptake
        })
        # 保持窗口大小
        if len(self.yearly_records) > self.window_size:
            self.yearly_records.pop(0)
        
        # 檢測重大事件
        if loss_ratio > 1.0:
            self.significant_events.append(
                f"Year {year}: Loss ratio exceeded 100% ({loss_ratio:.1%})"
            )
    
    def get_avg_loss_ratio(self) -> float:
        """計算平均損失率 (用於決策)"""
        if not self.yearly_records:
            return 0.5
        return sum(r["loss_ratio"] for r in self.yearly_records) / len(self.yearly_records)
    
    def format_for_prompt(self) -> str:
        """格式化為 LLM prompt"""
        lines = ["Recent Performance:"]
        for r in self.yearly_records[-3:]:  # 最近 3 年
            lines.append(f"- Year {r['year']}: Loss ratio {r['loss_ratio']:.1%}, "
                        f"Claims ${r['claims']:,.0f}, Uptake {r['uptake']:.1%}")
        
        if self.significant_events:
            lines.append("\nSignificant Events:")
            for event in self.significant_events[-2:]:  # 最近 2 個
                lines.append(f"- {event}")
        
        return "\n".join(lines)
```

---

## 4. Skills

### 4.1 核心 Skills (Exp3 MVP)

| Skill | 條件 | 調整幅度 | 約束 |
|-------|------|----------|------|
| `raise_premium` | loss_ratio > 0.80 | +5-15% | 年上限 18% |
| `lower_premium` | loss_ratio < 0.30 AND uptake < 0.40 | -5-10% | 最低 1% |
| `maintain_premium` | 其他情況 | 0% | 默認 |

### 4.2 擴展 Skills (候選名單)

| Skill | 說明 | 優先級 | 備註 |
|-------|------|--------|------|
| `explain_premium_change` | 向 Household 解釋保費調整 | P1 | LLM 獨有 |
| `send_risk_alert` | 災前發送風險警報 | P1 | 提高 uptake |
| `offer_mitigation_discount` | 減災戶優惠 | P2 | 鼓勵升高 |
| `send_retention_nudge` | 行為助推續保 | P2 | 社會證明 |
| `offer_parametric_policy` | 參數型快速理賠 | P3 | 創新產品 |
| `create_community_pool` | 社區團體保單 | P3 | 需協商機制 |

---

## 5. 決策流程

```
每年開始 (Phase 1):
┌─────────────────────────────────────────┐
│  1. 計算上年 loss_ratio                  │
│     loss_ratio = claims / premium        │
│                                         │
│  2. 更新 Memory                          │
│     memory.add_year_record(...)          │
│                                         │
│  3. 決策邏輯                             │
│     if loss_ratio > 0.80:               │
│         → raise_premium (5-15%)          │
│     elif loss_ratio < 0.30 AND          │
│          uptake < 0.40:                  │
│         → lower_premium (5-10%)          │
│     else:                                │
│         → maintain_premium               │
│                                         │
│  4. 應用約束                             │
│     - 年上限 18%                         │
│     - 最低保費 1%                        │
│                                         │
│  5. 更新 State                           │
│     self.premium_rate = new_rate         │
│     self.premium_history.append(new_rate)│
└─────────────────────────────────────────┘
```

---

## 6. Prompt 設計 (如使用 LLM)

```python
def build_insurance_prompt(agent: InsuranceAgentState, 
                           memory: InsuranceMemory) -> str:
    return f"""You are an insurance company managing flood insurance.

Current Situation:
- Premium rate: {agent.premium_rate*100:.1f}%
- Risk pool balance: ${agent.risk_pool:,.0f}
- Total policies: {agent.total_policies}
- Last year loss ratio: {agent.loss_ratio:.1%}

{memory.format_for_prompt()}

Policy Constraints:
- Maximum annual premium increase: 18%
- Minimum premium rate: 1%
- Goal: Balance financial sustainability with market competitiveness

Based on the loss ratio and market conditions, decide:
1. If loss ratio > 80%: Consider raising premium
2. If loss ratio < 30% AND uptake is low: Consider lowering premium
3. Otherwise: Maintain current rate

Respond in this format:
Analysis: [One sentence about current situation]
Decision: [raise/lower/maintain]
Adjustment: [percentage, e.g., 10%]
Reason: [Brief explanation]"""
```

---

## 7. 輸出結構

```python
@dataclass
class InsuranceOutput:
    """Insurance Agent 年度輸出"""
    year: int
    
    # 決策前狀態
    previous_premium_rate: float
    loss_ratio: float
    uptake_rate: float
    
    # 決策
    skill_name: str  # raise/lower/maintain_premium
    adjustment_pct: float
    reason: str
    
    # 決策後狀態
    new_premium_rate: float
    
    # 驗證
    validated: bool = True
    constraint_violations: List[str] = field(default_factory=list)
```

---

## 8. 與其他 Agent 互動

```
Insurance Agent
      │
      ├──→ Government Agent
      │     - 報告 loss_ratio 和市場狀況
      │     - 接收補貼政策資訊
      │
      └──→ Household Agents
            - 發布新保費 (透過 context)
            - 處理理賠 (透過 simulation)
```

---

## 9. 待決定事項

1. **LLM vs Rule-based?** MVP 建議 Rule-based + LLM 生成 reason
2. **Parametric 產品何時納入?** Phase 2 或 3
3. **Community pool 機制?** 需設計群體協商流程
