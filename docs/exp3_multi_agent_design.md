# Experiment 3: Multi-Agent Design Document

## 概述

本實驗探索基於真實問卷資料的多 Agent 類型洪水適應決策模擬。

---

## Stacked PR 計劃

| PR # | Branch | 主題 | 狀態 |
|------|--------|------|------|
| 1 | `exp3/design-agent-types` | Agent Types 定義 | ✅ 完成 |
| 2 | `exp3/design-decision-making` | Decision-Making 機制 | 🟡 **進行中** |
| 3 | `exp3/design-behaviors` | Adaptation Behaviors | ⬜ 待討論 |
| 4 | `exp3/implementation` | 實作 | ⬜ 待實作 |

---

## PR 1: Agent Types

### 三大 Agent 類別

```
┌─────────────────────────────────────────────────────────────────┐
│                       AGENT HIERARCHY                           │
├─────────────────────────────────────────────────────────────────┤
│  1. HOUSEHOLD (居民)           ┌──────────────────────────────┐ │
│     ├── MG_Owner               │ MG = Marginalized Group      │ │
│     ├── MG_Renter              │ 定義: poverty +              │ │
│     ├── NMG_Owner              │       housing_cost_burden +  │ │
│     └── NMG_Renter             │       no_vehicle             │ │
│                                └──────────────────────────────┘ │
│  2. INSURANCE (保險公司)                                         │
│     └── InsuranceAgent                                          │
│                                                                 │
│  3. GOVERNMENT (政府)                                            │
│     └── GovernmentAgent                                         │
└─────────────────────────────────────────────────────────────────┘
```

### Household Agent 類型 (4 類)

| 類型 | 定義 | 問卷指標 |
|------|------|---------|
| **MG_Owner** | 邊緣化屋主 | `is_MG=True` + `homeownership=owner` |
| **MG_Renter** | 邊緣化租客 | `is_MG=True` + `homeownership=renter` |
| **NMG_Owner** | 非邊緣化屋主 | `is_MG=False` + `homeownership=owner` |
| **NMG_Renter** | 非邊緣化租客 | `is_MG=False` + `homeownership=renter` |

### MG (Marginalized Group) 定義

```python
def is_marginalized_group(agent: dict) -> bool:
    """MG 定義: 貧窮 + 住房成本負擔 + 無車"""
    poverty = agent["income"] < poverty_threshold
    housing_burden = agent["housing_cost_ratio"] > 0.30  # >30% income on housing
    no_vehicle = agent["has_vehicle"] == False
    
    # 滿足多少條件算 MG? (待確認)
    return sum([poverty, housing_burden, no_vehicle]) >= 2
```

### 問卷資料欄位 (已有)

| 欄位 | 類型 | 用途 | 來源 |
|------|------|------|------|
| `income` | float | 計算 poverty | 問卷 ✅ |
| `homeownership` | owner/renter | 分類 | 問卷 ✅ |
| `housing_cost_ratio` | float | 住房成本負擔 | 問卷? |
| `has_vehicle` | bool | MG 定義 | 問卷? |
| 其他 PMT 屬性 | | | 問卷 ✅ |

### 分佈比例 (來自問卷)

```
┌─────────────────────────────────────────┐
│         問卷實際分佈 (待填入)             │
├─────────────┬──────────┬────────────────┤
│             │  Owner   │    Renter      │
├─────────────┼──────────┼────────────────┤
│  MG         │  ??%     │    ??%         │
│  NMG        │  ??%     │    ??%         │
├─────────────┼──────────┼────────────────┤
│  Total      │  ??%     │    ??%         │
└─────────────┴──────────┴────────────────┘
```

### Agent 類型定義 (Python)

```python
from dataclasses import dataclass
from typing import Literal
from enum import Enum

class AgentCategory(Enum):
    HOUSEHOLD = "household"
    INSURANCE = "insurance"
    GOVERNMENT = "government"

@dataclass
class HouseholdAgent:
    """居民 Agent (4 類型)"""
    id: str
    
    # MG 分類屬性 (來自問卷)
    income: float
    housing_cost_ratio: float
    has_vehicle: bool
    homeownership: Literal["owner", "renter"]
    
    # PMT 屬性 (來自問卷)
    trust_in_insurance: float
    trust_in_neighbors: float
    prior_flood_experience: bool
    
    # 狀態
    elevated: bool = False
    has_insurance: bool = False
    relocated: bool = False
    
    @property
    def is_MG(self) -> bool:
        """是否為邊緣化群體"""
        poverty = self.income < 30000  # 待確認閾值
        burden = self.housing_cost_ratio > 0.30
        no_car = not self.has_vehicle
        return sum([poverty, burden, no_car]) >= 2
    
    @property
    def agent_type(self) -> str:
        mg_status = "MG" if self.is_MG else "NMG"
        return f"{mg_status}_{self.homeownership.capitalize()}"

@dataclass
class InsuranceAgent:
    """保險公司 Agent"""
    id: str
    premium_rate: float = 0.02
    payout_ratio: float = 0.80
    
    # 可調整參數
    risk_assessment_model: str = "historical"

@dataclass
class GovernmentAgent:
    """政府 Agent"""
    id: str
    subsidy_rate: float = 0.50  # 補助比例
    budget: float = 1_000_000
    
    # 政策參數
    policy_mode: Literal["reactive", "proactive"] = "reactive"
    mg_priority: bool = True  # 是否優先補助 MG
```

### 各類型可用技能

| Agent Type | buy_insurance | elevate_house | relocate | do_nothing | 特殊 |
|------------|---------------|---------------|----------|------------|------|
| **MG_Owner** | ✅ | ✅ (補助優先) | ✅ | ✅ | 可申請補助 |
| **MG_Renter** | ✅ | ❌ | ✅ | ✅ | 遷移成本較低? |
| **NMG_Owner** | ✅ | ✅ | ✅ | ✅ | - |
| **NMG_Renter** | ✅ | ❌ | ✅ | ✅ | - |
| **Insurance** | - | - | - | - | set_premium, process_claim |
| **Government** | - | - | - | - | set_subsidy, announce_policy |

---

## 已確認參數 ✅

| 項目 | 確認值 |
|------|--------|
| MG 定義 | 滿足 **2/3** 條件 |
| 問卷欄位 | 全部都有 ✅ |
| MG:NMG 比例 | **1:4** (20% MG, 80% NMG) |
| Renter 比例 | 可調整參數 |
| 動態機制 | 保費調整、補助調整 |

### 分佈比例 (確認後)

假設 Renter = 35%：

| | Owner (65%) | Renter (35%) | Total |
|---|------------|--------------|-------|
| **MG (20%)** | 13% | 7% | 20% |
| **NMG (80%)** | 52% | 28% | 80% |

---

## 動態調整機制 (新增)

### Insurance Agent 動態行為

```python
@dataclass
class InsuranceAgent:
    id: str
    premium_rate: float = 0.02      # 初始保費率
    payout_ratio: float = 0.80      # 理賠比例
    risk_pool_balance: float = 0.0  # 風險池餘額
    
    def adjust_premium(self, claim_history: List[float]) -> float:
        """根據理賠歷史動態調整保費"""
        avg_claims = sum(claim_history) / len(claim_history) if claim_history else 0
        
        if avg_claims > self.risk_pool_balance * 0.8:
            self.premium_rate *= 1.10  # 理賠過多，漲 10%
        elif avg_claims < self.risk_pool_balance * 0.3:
            self.premium_rate *= 0.95  # 理賠少，降 5%
        
        return self.premium_rate
```

### Government Agent 動態行為

```python
@dataclass
class GovernmentAgent:
    id: str
    subsidy_rate: float = 0.50      # 補助比例
    budget: float = 1_000_000       # 年度預算
    spent: float = 0.0              # 已使用
    
    policy_mode: Literal["reactive", "proactive"] = "reactive"
    mg_priority: bool = True        # MG 優先
    
    def adjust_subsidy(self, flood_occurred: bool, mg_adoption_rate: float) -> float:
        """根據災害和採用率動態調整補助"""
        if flood_occurred and mg_adoption_rate < 0.30:
            # 災後 MG 採用率低 → 提高補助
            self.subsidy_rate = min(0.80, self.subsidy_rate * 1.20)
        elif mg_adoption_rate > 0.60:
            # 採用率高 → 可降低補助
            self.subsidy_rate = max(0.30, self.subsidy_rate * 0.90)
        
        return self.subsidy_rate
    
    def allocate_subsidy(self, applicant: HouseholdAgent) -> float:
        """分配補助金額"""
        if self.spent >= self.budget:
            return 0.0  # 預算用完
        
        # MG 優先且更高補助
        if self.mg_priority and applicant.is_MG:
            rate = self.subsidy_rate * 1.20  # MG 多 20%
        else:
            rate = self.subsidy_rate
        
        amount = min(rate * ELEVATION_COST, self.budget - self.spent)
        self.spent += amount
        return amount
```

### 互動流程

```
每年循環:
┌─────────────────────────────────────────────────────────────┐
│  1. Environment: 判斷是否有 flood event                      │
│                                                             │
│  2. Government: 根據上年結果調整 subsidy_rate                │
│     └── 發布政策 (announce_policy skill)                    │
│                                                             │
│  3. Insurance: 根據理賠歷史調整 premium_rate                 │
│     └── 更新保費 (set_premium skill)                        │
│                                                             │
│  4. Households: 根據政策和保費做決策                         │
│     ├── MG 可申請補助                                       │
│     └── 各類型執行各自可用的 skills                         │
│                                                             │
│  5. Execution: 執行已批准的 skills                          │
│                                                             │
│  6. Settlement: 結算保險理賠 (如有 flood)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 下一步: PR 2 Decision-Making

現在 Agent Types 已確認，接下來討論：

1. **Household 決策**: 不同類型如何使用 PMT 評估？
2. **Insurance 決策**: 何時調整保費？調整幅度？
3. **Government 決策**: 何時調整補助？觸發條件？

是否繼續 PR 2?

---

## PR 2: Decision-Making 機制

### 備註: MG 直接來自資料

```python
# MG 欄位直接從問卷資料讀取，不需計算
agent.is_MG = survey_data["is_MG"]  # True/False
```

### 2.1 Household Decision-Making (對齊現有單 Agent)

#### 現有 Prompt 結構 (v2_skill_governed)

```python
# 來自 run_experiment.py FloodContextBuilder
"""You are a homeowner in a city, with a strong attachment to your community. {elevation_status}
Your memory includes:
{memory}

You currently {insurance_status} flood insurance.
You {trust_ins_text} the insurance company. You {trust_neighbors_text} your neighbors' judgment.

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
Threat Appraisal: [One sentence]
Coping Appraisal: [One sentence]
Final Decision: [Choose {valid_choices} only]"""
```

#### Multi-Agent 擴展 (新增 MG/Owner/Renter 差異)

```python
class MultiAgentContextBuilder(FloodContextBuilder):
    """擴展現有 FloodContextBuilder 以支援 multi-agent"""
    
    def format_prompt(self, context: Dict[str, Any]) -> str:
        agent = self.simulation.agents[context["agent_id"]]
        
        # 基礎 PMT prompt (保持與單 agent 一致)
        base_prompt = self._build_base_pmt_prompt(context)
        
        # Owner vs Renter 選項差異
        if agent.homeownership == "owner":
            if context.get("elevated"):
                options = """1. Buy flood insurance (Lower cost, provides partial financial protection.)
2. Apply for buyout program (Government purchase, permanently leave flood zone.)
3. Do nothing (No investment this year, but exposed to future damage.)"""
            else:
                options = """1. Buy flood insurance (Lower cost, provides partial financial protection.)
2. Elevate your house (High upfront cost but prevents most physical damage.)
3. Apply for buyout program (Government purchase, permanently leave flood zone.)
4. Do nothing (No investment this year, but exposed to future damage.)"""
        else:  # renter
            options = """1. Buy contents-only insurance (Protects your belongings, not the structure.)
2. Relocate to safer area (Find housing in lower flood-risk area.)
3. Do nothing (No investment this year, but exposed to future damage.)"""
        
        # MG 補助資訊
        if agent.is_MG and not context.get("elevated"):
            subsidy_note = f"\nNote: You may qualify for government subsidy ({context['subsidy_rate']*100:.0f}% of elevation cost)."
        else:
            subsidy_note = ""
        
        return base_prompt + f"\n\n{options}{subsidy_note}\n\n" + self._build_output_format(agent)
```

#### Validation Pipeline (保持不變)

| Validator | 檢查 | 範例 |
|-----------|------|------|
| Admissibility | Skill 存在? Agent type 允許? | Renter 選 "elevate_house" |
| Feasibility | 前置條件滿足? | 已 elevated 再選 elevate |
| PMTConsistency | 威脅-應對邏輯一致? | High threat + high efficacy + DN |
| FinancialConsistency | 成本邏輯一致? | "cannot afford" + expensive option |

### 2.2 Insurance Decision-Making (簡單 LLM)

```python
def build_insurance_prompt(insurance: InsuranceAgent, context: dict) -> str:
    """保險公司決策 prompt (簡化版)"""
    
    return f"""You are an insurance company managing flood insurance.

Current situation:
- Year: {context["year"]}
- Premium rate: {insurance.premium_rate*100:.1f}%
- Total policies: {context["total_policies"]}
- Claims last year: ${context["claims_last_year"]:,.0f}
- Premium collected: ${context["premium_collected"]:,.0f}
- Loss ratio: {context["loss_ratio"]:.1%}

Based on the loss ratio, decide premium adjustment:
- If losses are high (>80%), consider raising premium
- If losses are low (<30%), consider lowering premium
- Otherwise, maintain current rate

Respond:
Decision: [raise/lower/maintain]
Adjustment: [percentage, e.g., 5% or 10%]
Reason: [brief explanation]"""
```

**可用技能:**
| Skill | 效果 |
|-------|------|
| `raise_premium` | 提高保費 (5-15%) |
| `lower_premium` | 降低保費 (5-10%) |
| `maintain_premium` | 維持現狀 |

### 2.3 Government Decision-Making (簡單 LLM)

```python
def build_government_prompt(gov: GovernmentAgent, context: dict) -> str:
    """政府決策 prompt (簡化版)"""
    
    return f"""You are a government agency managing flood adaptation subsidies.

Current situation:
- Year: {context["year"]}
- Subsidy rate: {gov.subsidy_rate*100:.0f}%
- Budget remaining: ${gov.budget - gov.spent:,.0f} / ${gov.budget:,.0f}
- MG household adoption rate: {context["mg_adoption_rate"]:.1%}
- NMG household adoption rate: {context["nmg_adoption_rate"]:.1%}
- Flood occurred this year: {"Yes" if context["flood_event"] else "No"}

Policy goal: Help marginalized households (MG) adopt flood protection measures.

Consider:
- If MG adoption is low and flood occurred, increase subsidy
- If budget is running low, decrease subsidy
- If adoption rates are healthy, maintain current policy

Respond:
Decision: [increase/decrease/maintain]
Adjustment: [percentage change]
Priority: [MG/all households]
Reason: [brief explanation]"""
```

**可用技能:**
| Skill | 效果 |
|-------|------|
| `increase_subsidy` | 提高補助 (10-20%) |
| `decrease_subsidy` | 降低補助 (10-20%) |
| `maintain_subsidy` | 維持現狀 |
| `set_mg_priority` | 設定 MG 優先 |

### 2.4 Decision Sequence per Year

```
每年決策順序:
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: Institutional Decisions (規則式)                  │
│  ├── Government: adjust_subsidy()                          │
│  └── Insurance: adjust_premium()                           │
│                                                             │
│  Phase 2: Household Decisions (LLM)                        │
│  ├── For each active household:                            │
│  │   ├── Build context (include new premium/subsidy)       │
│  │   ├── Generate prompt                                   │
│  │   ├── LLM inference                                     │
│  │   ├── Validate skill                                    │
│  │   └── Execute if approved                               │
│  │                                                         │
│  Phase 3: Settlement                                        │
│  ├── Process insurance claims (if flood)                   │
│  └── Update statistics for next year                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 待討論: PR 2

1. **Insurance/Government 是否也用 LLM?** 還是如上用規則式?
2. **Prompt 結構是否合適?** MG/NMG 差異是否足夠?
3. **每年執行順序?** 上述 3 Phase 結構?

---

## 參考: 傳統 ABM 設計 (ABM_Summary.pdf)

### 核心架構

```
每年循環:
Flood hazard → Loss computation → TP update → End-of-year decisions → Finance
```

### 關鍵元素對照

| 傳統 ABM | LLM-ABM 對應 |
|----------|-------------|
| Tract-level TP (Threat Perception) | Agent context → PMT prompt |
| Bayesian regression model | LLM + Skill-Governed validation |
| MG/NMG weighted probability | Agent type 分類 |
| Action sequences | SkillRegistry constraints |

### 傳統 ABM 決策公式

```
p(a),g = σ(w0 + w1*TP + w2*CP + w3*SP)

p(a) = wMG * p(a),MG + (1 - wMG) * p(a),NMG
```

- **TP**: Threat Perception (威脅感知)
- **CP**: Coping Perception (affordability/income effects)
- **SP**: Stakeholder Perception (利害關係人感知)

### Action Sequences

| Agent Type | 序列 |
|------------|------|
| **Owner** | FI → EH (once, +5ft) → BP (permanent) → DN |
| **Renter** | FI → RL (same or lower depth) → DN |

### TP 動態更新 (Tract-level)

```python
# Gate by damage ratio
if r_t > θ:  # θ = 0.5
    TP_gain = True

# Half-life decay
μ = ln(2) / τ(t) * (α*PA + β*SC)

# Annual update
TP_t = (1 - μ) * TP_{t-1} + Δψ * r_t
```

### Finance Module

- **Owner**: Building + Contents coverage
- **Renter**: Contents-only coverage
- **Outputs**: Take-up rate, payout ratio, OOP costs, AAL

### State Variables

**Per-Tract:**
- TP_MG, TP_NMG, SC, PA, wMG, CP, SP, depth, damage_ratio, RCV

**Per-Household:**
- owner/renter, has_EH, EH_height, removed_by_BP, tract_id, insured_type, action

---

## LLM-ABM vs 傳統 ABM 設計決策

| 面向 | 傳統 ABM | LLM-ABM (Exp 3) |
|------|----------|-----------------|
| 決策機制 | Bayesian regression | LLM + PMT prompt + validation |
| 概率計算 | 公式 σ(w*x) | LLM 推理 + 結構化輸出 |
| MG/NMG 加權 | 數學加權公式 | Agent type 區分 prompt |
| 約束執行 | 程式邏輯 | SkillRegistry + Validators |
| TP 更新 | Half-life decay 公式 | Memory + context 自然語言 |

### ✅ 已確認設計決策

| 問題 | 決定 |
|------|------|
| TP 動態對齊？ | ❌ **不需要** - 那是經驗公式，LLM 用 memory + PMT 自然推理 |
| 概率 vs 確定？ | **確定輸出** - 不需要概率機制 |
| 順序約束？ | **不強制** - 只需完整 audit trail 即可追蹤決策路徑 |

### Audit 需求

```python
# 每個決策需要記錄
audit_record = {
    "agent_id": "HH_001",
    "agent_type": "MG_Owner",
    "year": 2015,
    "context": {
        "income": 28000,
        "housing_cost_ratio": 0.35,
        "has_vehicle": False,
        "prior_flood": True,
        "memory": ["Year 2014: flooded, $10k damage"]
    },
    "llm_output": {
        "threat_appraisal": "High - recent flood experience",
        "coping_appraisal": "Can elevate with subsidy",
        "decision": "elevate_house"
    },
    "validation": {
        "passed": True,
        "validators": ["admissibility", "feasibility"]
    },
    "execution": {
        "skill": "elevate_house",
        "state_changes": {"elevated": True}
    }
}
```

---

## PR 1 完成總結

| 項目 | 狀態 |
|------|------|
| Agent 類別 (3 大類) | ✅ Household / Insurance / Government |
| Household 分類 (4 類) | ✅ MG/NMG × Owner/Renter |
| MG 定義 | ✅ 2/3 條件 |
| 比例 | ✅ MG:NMG = 1:4 |
| 動態機制 | ✅ 保費/補助調整 |
| TP 對齊 | ❌ 不需要 - LLM 自然推理 |
| 順序約束 | ❌ 不強制 - 只需 audit |

**準備進入 PR 2: Decision-Making**
