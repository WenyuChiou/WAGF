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

## 待討論問題

### Q1: MG 定義確認
- 需要滿足幾個條件算 MG? (2/3 或 3/3?)
- poverty threshold 是多少?

### Q2: 問卷欄位確認
- `housing_cost_ratio` 和 `has_vehicle` 欄位是否存在於問卷?
- 如果沒有，如何推斷?

### Q3: Insurance 和 Government Agent 的行為
- 是否為每輪決策的 active agent?
- 還是只在特定條件下才行動?

---

## 下一步

請確認：
1. MG 定義的確切條件
2. 問卷中實際的分佈比例
3. Insurance/Government 的角色定位
