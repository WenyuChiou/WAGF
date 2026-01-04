# Experiment 3: Multi-Agent Design Document

## 概述

本實驗探索基於真實問卷資料的多 Agent 類型洪水適應決策模擬。

---

## Stacked PR 計劃

| PR # | Branch | 主題 | 狀態 |
|------|--------|------|------|
| 1 | `exp3/design-agent-types` | Agent Types 定義 | 🟡 討論中 |
| 2 | `exp3/design-decision-making` | Decision-Making 機制 | ⬜ 待討論 |
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

### 關鍵待決定問題

1. **TP 動態**: 傳統 ABM 用數學公式，LLM-ABM 用 memory - 如何對齊？
2. **概率 vs 確定**: 傳統 ABM 是概率決策，LLM 是確定輸出 - 需要引入隨機性？
3. **Tract-level vs HH-level**: 傳統 ABM 是 tract 層級 TP，LLM-ABM 是個體層級
