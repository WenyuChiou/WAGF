# Experiment 3: Multi-Agent Design Document

## 概述

本實驗探索基於真實問卷資料的多 Agent 類型洪水適應決策模擬。

---

## Stacked PR 計劃

| PR # | Branch | 主題 | 依賴 |
|------|--------|------|------|
| 1 | `exp3/design-agent-types` | Agent Types 定義 | - |
| 2 | `exp3/design-decision-making` | Decision-Making 機制 | PR 1 |
| 3 | `exp3/design-behaviors` | Adaptation Behaviors | PR 2 |
| 4 | `exp3/implementation` | 實作 | PR 3 |

---

## PR 1: Agent Types (本 PR)

### 問卷資料欄位

| 欄位 | 類型 | 值域 | 用途 |
|------|------|------|------|
| `income` | categorical | low/middle/high | 可負擔選項 |
| `household_size` | int | 1-6+ | 遷移成本考量 |
| `homeownership` | categorical | owner/renter | 可用選項集 |
| `education` | categorical | hs/bachelor/master/phd | 風險認知 |
| `age` | int | 18-80 | 適應傾向 |
| `years_in_community` | int | 0-50 | 遷移意願 |
| `prior_flood_experience` | bool | true/false | 威脅感知 |

### Agent 類型定義 (推薦方案)

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class SurveyAgent:
    """基於問卷資料的 Agent 類型"""
    id: str
    
    # 問卷屬性
    income: Literal["low", "middle", "high"]
    homeownership: Literal["owner", "renter"]
    household_size: int
    education: Literal["hs", "bachelor", "master", "phd"]
    age: int
    years_in_community: int
    prior_flood_experience: bool
    
    # 狀態屬性
    elevated: bool = False
    has_insurance: bool = False
    relocated: bool = False
    
    # PMT 屬性
    trust_in_insurance: float = 0.3
    trust_in_neighbors: float = 0.4
    
    @property
    def agent_type(self) -> str:
        """派生 Agent 類型"""
        return f"{self.income}_{self.homeownership}"
    
    @property
    def can_elevate(self) -> bool:
        """只有屋主可以升高房屋"""
        return self.homeownership == "owner"
    
    @property
    def relocation_reluctance(self) -> float:
        """久居者較不願遷移"""
        return min(1.0, self.years_in_community / 20)
```

### Agent 類型與可用技能

| Agent Type | buy_insurance | elevate_house | relocate | do_nothing |
|------------|---------------|---------------|----------|------------|
| low_owner | ✅ | ✅ (補助?) | ✅ | ✅ |
| low_renter | ✅ | ❌ | ✅ | ✅ |
| middle_owner | ✅ | ✅ | ✅ | ✅ |
| middle_renter | ✅ | ❌ | ✅ | ✅ |
| high_owner | ✅ | ✅ | ✅ | ✅ |
| high_renter | ✅ | ❌ | ✅ | ✅ |

### 問卷資料範例 CSV

```csv
id,income,homeownership,household_size,education,age,years_in_community,prior_flood_experience,trust_in_insurance,trust_in_neighbors
Agent_1,low,owner,4,hs,55,25,true,0.25,0.45
Agent_2,middle,renter,2,bachelor,32,5,false,0.50,0.35
Agent_3,high,owner,3,master,48,15,true,0.60,0.55
```

---

## 待討論問題

### Q1: Agent 數量分佈

| Income \ Ownership | Owner | Renter | Total |
|--------------------|-------|--------|-------|
| Low | 20% | 15% | 35% |
| Middle | 25% | 15% | 40% |
| High | 20% | 5% | 25% |
| **Total** | 65% | 35% | 100% |

> 這個分佈合理嗎？還是應該根據真實問卷資料？

### Q2: 收入如何影響決策成本感知？

| Income | elevate_house 感知 | relocate 感知 |
|--------|-------------------|---------------|
| Low | "極度昂貴" | "無法負擔" |
| Middle | "昂貴但可行" | "困難但可能" |
| High | "可負擔" | "可考慮" |

### Q3: 特殊規則

- **低收入屋主**: 是否有政府補助 elevate？
- **租客**: relocate 成本較低？
- **久居者**: 是否有額外的遷移阻力？

---

## 下一步

請確認：
1. 以上 Agent 類型定義是否符合需求？
2. 問卷資料欄位是否完整？
3. 分佈比例是否需要調整？
