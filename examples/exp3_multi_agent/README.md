# Experiment 3: Multi-Agent Flood Adaptation

## 概述

Exp3 實現多 Agent 洪水適應模擬，包含 Household、Insurance、Government 三類 Agent。

**模擬時間:** 2011-2023 (歷史洪水事件)

---

## 1. Agent 類型總覽

| Agent | 數量 | 決策時機 | 主要職責 |
|-------|------|----------|----------|
| **Household** | 100+ | Phase 2 | 選擇減災行動 |
| **Insurance** | 1 | Phase 1 | 調整保費 |
| **Government** | 1 | Phase 1 | 調整補助 |

```
年度流程:
┌─────────────────────────────────────────────┐
│ Phase 1: Institutional Decisions            │
│   └─ Insurance: 調整保費                     │
│   └─ Government: 調整補助                    │
├─────────────────────────────────────────────┤
│ Phase 2: Household Decisions                │
│   └─ 基於 5 Constructs 評估，選擇行動        │
├─────────────────────────────────────────────┤
│ Phase 3: Settlement (Environment)           │
│   └─ 洪水損失計算                            │
│   └─ 理賠處理                                │
│   └─ 補助發放                                │
└─────────────────────────────────────────────┘
```

---

## 📊 10-Year LLM Simulation Results (2026-01-06)

**Model:** llama3.2:3b | **Total Decisions:** 1,058 | **Validation Errors:** 0

### Decision Distribution

| Decision | Count | Rate |
|----------|-------|------|
| buy_insurance | 48 | 27.0% |
| elevate_house | 15 | 8.4% |
| buyout_program | 55 | 30.9% |
| relocate | 10 | 5.6% |
| do_nothing | 50 | 28.1% |

### PMT Construct Distribution

| Construct | LOW | MODERATE | HIGH/FULL |
|-----------|-----|----------|-----------|
| **TP** (Threat) | 24 (13%) | 136 (76%) | 18 (10%) |
| **CP** (Coping) | 100 (56%) | 68 (38%) | 10 (6%) |
| **PA** (Prior Adapt) | 52 (29%) | 106 (60%) | 20 (11%) |

### Validation Metrics

- **Validation Errors:** 0 (全部決策符合約束)
- **Validation Warnings:** 46 (25.8%)
- **Warning 趨勢:** Year 3 最高 (36), Year 10 最低 (4)

### Key Findings

1. **CP 偏低:** 56% 的決策 CP=LOW，反映 MG 群體資源受限
2. **buyout_program 活躍:** 後期年度選擇 buyout 比例增加
3. **洪水事件影響:** Year 2, 7, 8, 10 發生洪水，觸發保險購買增加

### 圖表 (results/ 目錄)

- `decision_over_time.png` - 各年度決策分佈
- `construct_distribution.png` - PMT Construct 分佈
- `validation_warnings.png` - 驗證警告率趨勢
- `tp_decision_heatmap.png` - TP 等級 vs 決策選擇

---

## 2. Household Agent

### 2.1 分類

| 類型 | 定義 |
|------|------|
| **MG_Owner** | Marginalized Group + 屋主 |
| **MG_Renter** | Marginalized Group + 租戶 |
| **NMG_Owner** | Non-Marginalized + 屋主 |
| **NMG_Renter** | Non-Marginalized + 租戶 |

**MG 定義:** 收入 < 區域中位數 80% OR 教育 < 高中 OR 少數族裔

### 2.2 State

```python
@dataclass
class HouseholdAgentState:
    id: str
    agent_type: str          # MG_Owner, MG_Renter, etc.
    
    # 適應狀態
    elevated: bool = False
    has_insurance: bool = False
    relocated: bool = False
    
    # 信任度
    trust_in_insurance: float = 0.5  # 0-1
    trust_in_government: float = 0.5
    trust_in_neighbors: float = 0.5
    
    # 財務追蹤
    cumulative_damage: float = 0
    cumulative_oop: float = 0        # Out-of-Pocket
```

### 2.3 Memory

```python
@dataclass
class HouseholdMemory:
    window_size: int = 5
    
    # 經歷記錄
    experiences: List[str]           # "Year 3: Flood caused $10K damage"
    
    # 鄰居行為
    neighbor_actions: List[str]      # "Neighbor elevated house"
    
    # 政策資訊
    policy_announcements: List[str]  # "Government increased subsidy to 75%"
```

### 2.4 Skills

| Skill | 適用 | 說明 |
|-------|------|------|
| `buy_insurance` | Owner | 購買洪水保險 (建築+內容物) |
| `buy_contents_insurance` | Renter | 購買內容物保險 |
| `elevate_house` | Owner only | 升高房屋結構 |
| `buyout_program` | Owner only | 政府收購計畫 |
| `relocate` | Renter only | 搬遷到低風險區 |
| `do_nothing` | All | 維持現狀 |

### 2.5 決策輸出 (5 Constructs)

```
TP Assessment: [LOW/MODERATE/HIGH] - 威脅感知
CP Assessment: [LOW/MODERATE/HIGH] - 應對能力
SP Assessment: [LOW/MODERATE/HIGH] - 補助感知
SC Assessment: [LOW/MODERATE/HIGH] - 社會資本
PA Assessment: [NONE/PARTIAL/FULL] - 既有適應
Final Decision: [1-4]
```

---

## 3. Insurance Agent

### 3.1 State

```python
@dataclass
class InsuranceAgentState:
    id: str = "InsuranceCo"
    
    # 定價
    premium_rate: float = 0.05       # 5% of coverage
    payout_ratio: float = 0.80       # 理賠 80%
    
    # 財務
    risk_pool: float = 1_000_000
    premium_collected: float = 0     # 年度收入
    claims_paid: float = 0           # 年度理賠
    
    # 市場
    total_policies: int = 0
    
    @property
    def loss_ratio(self) -> float:
        return self.claims_paid / max(self.premium_collected, 1)
```

### 3.2 Memory

```python
@dataclass
class InsuranceMemory:
    window_size: int = 5
    
    # 年度統計
    yearly_records: List[Dict]       # {year, loss_ratio, claims, uptake}
    
    # 重大事件
    significant_events: List[str]    # "Year 3: Loss ratio > 100%"
```

### 3.3 Skills

**核心 (MVP):**
| Skill | 條件 | 調整 |
|-------|------|------|
| `raise_premium` | loss_ratio > 80% | +5-15% |
| `lower_premium` | loss_ratio < 30% & uptake < 40% | -5-10% |
| `maintain_premium` | 其他 | 0% |

**候選 (P1-P3):**
| 優先級 | Skill | 說明 |
|--------|-------|------|
| P1 | `explain_premium_change` | LLM 生成解釋 |
| P1 | `send_risk_alert` | 災前警報 |
| P2 | `offer_mitigation_discount` | 減災戶優惠 |
| P2 | `send_retention_nudge` | 行為助推 |
| P3 | `offer_parametric_policy` | 參數型保險 |

---

## 4. Government Agent

### 4.1 State

```python
@dataclass
class GovernmentAgentState:
    id: str = "Government"
    
    # 預算
    annual_budget: float = 500_000
    budget_remaining: float = 500_000
    
    # 補助政策
    subsidy_rate: float = 0.50       # 50%
    mg_priority: bool = True
    
    # 追蹤
    mg_adoption_rate: float = 0.0
    nmg_adoption_rate: float = 0.0
```

### 4.2 Memory

```python
@dataclass
class GovernmentMemory:
    window_size: int = 5
    
    # 政策記錄
    policy_records: List[Dict]       # {year, subsidy_rate, mg_adoption, budget_used}
    
    # 重大事件
    policy_events: List[str]         # "Year 3: Emergency subsidy increase"
```

### 4.3 Skills

**核心 (MVP):**
| Skill | 條件 | 調整 |
|-------|------|------|
| `increase_subsidy` | 災後 + MG 採用 < 30% | +10-20% |
| `decrease_subsidy` | 預算不足 OR 採用 > 60% | -10-20% |
| `maintain_subsidy` | 其他 | 0% |

**候選 (P1-P3):**
| 優先級 | Skill | 說明 |
|--------|-------|------|
| P1 | `announce_policy` | 公布政策 |
| P1 | `target_mg_outreach` | MG 主動聯繫 |
| P2 | `approve_buyout` | 收購批准 |
| P2 | `emergency_fund` | 災後緊急撥款 |

### 4.4 補助參數 (基於 NY/NJ FEMA)

| 類別 | 補助比例 | 來源 |
|------|----------|------|
| MG + Severe Repetitive Loss | 100% | FEMA SRL |
| MG + Repetitive Loss | 90% | FEMA RL |
| MG 標準 | 75% | FEMA HMGP |
| NMG 標準 | 50% | 降低優先 |

---

## 5. Environment Layer (非 Agent)

**職責:** 系統規則計算，不是 Agent Skill

| 模組 | 職責 |
|------|------|
| **CatastropheModule** | 洪水損失計算 |
| **SubsidyModule** | 補助金額計算 |
| **SettlementModule** | 年度結算 |

```python
class CatastropheModule:
    def calculate_damage(agent, flood_severity) -> float
    def calculate_payout(agent, damage, insurance) -> float
    def calculate_oop(damage, payout) -> float
```

---

## 6. 檔案結構

```
examples/exp3_multi_agent/
├── README.md                 # 本文檔
├── skill_registry.yaml       # Skills 定義
├── run_experiment.py         # 主程式
├── agents/
│   ├── household.py          # Household Agent
│   ├── insurance.py          # Insurance Agent
│   └── government.py         # Government Agent
├── environment/
│   ├── catastrophe.py        # 災害模組
│   └── settlement.py         # 結算模組
└── validators/
    └── multi_agent_validators.py
```

---

## 7. 參考文獻

- FEMA HMGP/FMA Programs
- NYC Build It Back
- NJ Blue Acres
- Risk Rating 2.0

詳見: `docs/government_ny_nj_research.md`, `docs/insurance_agent_research.md`
