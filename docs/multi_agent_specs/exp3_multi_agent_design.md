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

~~1. **Insurance/Government 是否也用 LLM?** 還是如上用規則式?~~  **✅ 用簡單 LLM**
~~2. **Prompt 結構是否合適?** MG/NMG 差異是否足夠?~~  **✅ 對齊現有 PMT**
3. **每年執行順序?** 上述 3 Phase 結構?

---

## 目前已建立的 Constructs

### 1. Skills (skill_registry.yaml)

| Agent Type | Skills | Skill ID |
|------------|--------|----------|
| Household Owner | 保險、升高、政府收購、無作為 | buy_insurance, elevate_house, buyout_program, do_nothing |
| Household Renter | 內容險、遷移、無作為 | buy_contents_insurance, relocate, do_nothing |
| Insurance | 調漲/調降/維持保費 | raise/lower/maintain_premium |
| Government | 調高/調低/維持補助、MG優先 | increase/decrease/maintain_subsidy, set_mg_priority |

### 2. Decision Constructs (基於傳統 ABM)

#### 傳統 ABM 公式 (ABM_Summary.pdf)

```
p(a),g = σ(w0 + w1*TP + w2*CP + w3*SP)
```

| Construct | 全名 | 定義 | 來源 |
|-----------|------|------|------|
| **TP** | Threat Perception | 威脅感知 (MG/NMG 各自) | 上年災損動態更新 |
| **CP** | Coping Perception | 應對能力感知 (affordability) | 收入、成本負擔 |
| **SP** | Stakeholder Perception | 利害關係人感知 | 政策、保險可用性 |
| **SC** | Self-Confidence | 自信心/社會資本 | 問卷 |
| **PA** | Previous Adaptation | 過去適應經驗 | 歷史記錄 |

#### LLM-ABM Construct 對應

| 傳統 ABM | LLM Prompt 對應 | Context 來源 |
|----------|----------------|--------------|
| **TP** (Threat) | Threat Appraisal 輸出 | memory, flood_event, prior_flood_experience |
| **CP** (Coping) | Coping Appraisal 輸出 | income, housing_cost_ratio, is_MG, subsidy_rate |
| **SP** (Stakeholder) | Context 資訊 | premium_rate, subsidy_rate, policy_mode |
| **SC** (Self-Confidence) | trust_in_insurance, trust_in_neighbors | 問卷直接載入 |
| **PA** (Previous Adaptation) | elevated, has_insurance, memory | 狀態 + 記憶 |

#### 設計方法: 明確 Construct 評估 (類似單 Agent)

**核心概念: 告知 Construct 定義 → LLM 逐項評估 → 輸出結構化結果 → 每年 Audit**

#### Prompt 結構 (明確要求各 Construct 評估)

```python
def build_construct_prompt(agent: HouseholdAgent, context: dict) -> str:
    """要求 LLM 對每個 construct 進行評估"""
    
    return f"""You are a {"homeowner" if agent.homeownership == "owner" else "renter"} in a flood-prone area.

**Your Current Situation:**
- Prior flood experience: {"Yes" if agent.prior_flood_experience else "No"}
- Current year: {"Flood occurred this year" if context["flood_event"] else "No flood this year"}
- House elevated: {"Yes" if agent.elevated else "No"}
- Has insurance: {"Yes" if agent.has_insurance else "No"}
- Income situation: {"Limited income, high housing cost burden" if agent.is_MG else "Adequate income"}

**Your Memories:**
{chr(10).join(f'- {m}' for m in agent.memory[-3:]) if agent.memory else "- No recent flood memories"}

**Your Trust Levels:**
- Trust in insurance: {"High" if agent.trust_in_insurance > 0.6 else "Moderate" if agent.trust_in_insurance > 0.3 else "Low"}
- Trust in neighbors: {"High" if agent.trust_in_neighbors > 0.6 else "Moderate" if agent.trust_in_neighbors > 0.3 else "Low"}

**Available Options:**
- Insurance premium rate: {context["premium_rate"]*100:.1f}%
- Government subsidy: {context["subsidy_rate"]*100:.0f}%{" (you may qualify)" if agent.is_MG else ""}

---

Please evaluate your situation using the following constructs:

**1. Threat Perception (TP):** How threatened do you feel by potential flood damage?
   Consider: past flood experience, current flood event, memories of damage

**2. Coping Perception (CP):** How capable do you feel of taking protective action?
   Consider: financial ability, available support (subsidy), existing protection (elevated/insured)

**3. Stakeholder Perception (SP):** How do you perceive the support from institutions?
   Consider: insurance availability, government programs, community actions

**4. Self-Confidence (SC):** How confident are you in making the right decision?
   Consider: trust in insurance, trust in neighbors' judgment

**5. Previous Adaptation (PA):** What protective measures have you already taken?
   Consider: current elevation status, insurance history, past decisions

---

{_get_options(agent)}

---

Please respond in this EXACT format:

TP Assessment: [LOW/MODERATE/HIGH] - [One sentence explanation]
CP Assessment: [LOW/MODERATE/HIGH] - [One sentence explanation]
SP Assessment: [LOW/MODERATE/HIGH] - [One sentence explanation]
SC Assessment: [LOW/MODERATE/HIGH] - [One sentence explanation]
PA Assessment: [NONE/PARTIAL/FULL] - [One sentence explanation]
Final Decision: [number only]"""
```

#### Output Structure (Yearly Record)

```python
@dataclass
class YearlyConstructRecord:
    """Yearly construct assessment record for audit"""
    year: int
    agent_id: str
    agent_type: str  # MG_Owner, MG_Renter, NMG_Owner, NMG_Renter
    
    # Context (input)
    context: Dict[str, Any]
    
    # LLM Construct Assessments (output)
    tp_level: Literal["LOW", "MODERATE", "HIGH"]
    tp_explanation: str
    cp_level: Literal["LOW", "MODERATE", "HIGH"]
    cp_explanation: str
    sp_level: Literal["LOW", "MODERATE", "HIGH"]
    sp_explanation: str
    sc_level: Literal["LOW", "MODERATE", "HIGH"]
    sc_explanation: str
    pa_level: Literal["NONE", "PARTIAL", "FULL"]
    pa_explanation: str
    
    # Decision
    decision: str  # skill_id
    
    # Validation
    validation_passed: bool
    validation_errors: List[str]
```

#### CSV Audit Output

```csv
year,agent_id,agent_type,is_MG,homeownership,flood_event,elevated,has_insurance,tp_level,tp_explanation,cp_level,cp_explanation,sp_level,sp_explanation,sc_level,sc_explanation,pa_level,pa_explanation,decision,valid
2015,HH_001,MG_Owner,True,owner,True,False,False,HIGH,"Flooded this year and last",LOW,"Cannot afford expensive options",MODERATE,"Subsidy available",LOW,"Distrust insurance",NONE,"No protection yet",do_nothing,True
2015,HH_002,NMG_Renter,False,renter,True,N/A,False,MODERATE,"First flood experience",HIGH,"Can afford insurance",HIGH,"Good rates",HIGH,"Neighbors recommended",PARTIAL,"Had insurance last year",buy_contents_insurance,True
```

#### Parser (LLM Output)

```python
def parse_construct_output(raw_output: str) -> dict:
    """Parse LLM construct output"""
    
    # Regex matching
    tp_match = re.search(r'TP Assessment:\s*(LOW|MODERATE|HIGH)\s*-\s*(.+?)(?=\n|CP)', raw_output, re.I)
    cp_match = re.search(r'CP Assessment:\s*(LOW|MODERATE|HIGH)\s*-\s*(.+?)(?=\n|SP)', raw_output, re.I)
    sp_match = re.search(r'SP Assessment:\s*(LOW|MODERATE|HIGH)\s*-\s*(.+?)(?=\n|SC)', raw_output, re.I)
    sc_match = re.search(r'SC Assessment:\s*(LOW|MODERATE|HIGH)\s*-\s*(.+?)(?=\n|PA)', raw_output, re.I)
    pa_match = re.search(r'PA Assessment:\s*(NONE|PARTIAL|FULL)\s*-\s*(.+?)(?=\n|Final)', raw_output, re.I)
    decision_match = re.search(r'Final Decision:\s*(\d+)', raw_output, re.I)
    
    return {
        "tp_level": tp_match.group(1).upper() if tp_match else "UNKNOWN",
        "tp_explanation": tp_match.group(2).strip() if tp_match else "",
        "cp_level": cp_match.group(1).upper() if cp_match else "UNKNOWN",
        "cp_explanation": cp_match.group(2).strip() if cp_match else "",
        "sp_level": sp_match.group(1).upper() if sp_match else "UNKNOWN",
        "sp_explanation": sp_match.group(2).strip() if sp_match else "",
        "sc_level": sc_match.group(1).upper() if sc_match else "UNKNOWN",
        "sc_explanation": sc_match.group(2).strip() if sc_match else "",
        "pa_level": pa_match.group(1).upper() if pa_match else "UNKNOWN",
        "pa_explanation": pa_match.group(2).strip() if pa_match else "",
        "decision": int(decision_match.group(1)) if decision_match else None
    }
```

#### Construct-based Validation

```python
class ConstructConsistencyValidator(SkillValidator):
    """Validate consistency between constructs and decision"""
    
    name = "ConstructConsistencyValidator"
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        errors = []
        
        tp = context.get("parsed_tp_level", "MODERATE")
        cp = context.get("parsed_cp_level", "MODERATE")
        pa = context.get("parsed_pa_level", "NONE")
        skill = proposal.skill_name
        
        # Rule 1: HIGH TP + HIGH CP + do_nothing = inconsistent
        if tp == "HIGH" and cp == "HIGH" and skill == "do_nothing":
            errors.append("Construct inconsistency: HIGH threat + HIGH coping but chose do_nothing")
        
        # Rule 2: LOW TP + relocate = overreaction
        if tp == "LOW" and skill == "relocate":
            errors.append("Construct inconsistency: LOW threat but chose extreme action (relocate)")
        
        # Rule 3: LOW CP + expensive action = inconsistent
        if cp == "LOW" and skill in ["elevate_house", "relocate"]:
            errors.append("Construct inconsistency: LOW coping capacity but chose expensive action")
        
        # Rule 4: FULL PA + elevate_house = already done
        if pa == "FULL" and skill == "elevate_house":
            errors.append("Construct inconsistency: FULL previous adaptation but chose elevate again")
        
        return ValidationResult(valid=len(errors) == 0, errors=errors)
```

#### Analysis Use Cases

Yearly audit data can be used for:

1. **Construct Distribution Analysis**: TP/CP/SP/SC/PA distribution by agent type
2. **Decision-Construct Relationship**: Does HIGH TP lead to buy_insurance?
3. **MG vs NMG Comparison**: Is CP systematically lower for MG?
4. **Temporal Analysis**: How does TP change after flood events?
5. **Traditional ABM Comparison**: LLM TP distribution vs formula-calculated TP

### 3. Prompts (對齊現有 PMT)

| Agent Type | Prompt 內容 |
|------------|------------|
| **Household** | PMT 6 因素 + Owner/Renter 選項 + MG 補助資訊 |
| **Insurance** | Loss ratio + Premium adjustment |
| **Government** | MG adoption rate + Subsidy adjustment |

### 3. 現有 Validators (validators/skill_validators.py)

| Validator | 功能 | 層級 |
|-----------|------|------|
| **SkillAdmissibilityValidator** | Skill 存在? Agent type 允許? | 1 |
| **ContextFeasibilityValidator** | Preconditions 滿足? | 2 |
| **InstitutionalConstraintValidator** | Once-only, permanent | 3 |
| **EffectSafetyValidator** | 只改允許的 state fields? | 4 |
| **PMTConsistencyValidator** | 威脅-應對邏輯一致? | 5 |
| **UncertaintyValidator** | 不確定語言? (disabled) | 6 |

---

## PR 2.5: Literature Review - PMT & PADM Theoretical Basis

### Key Literature Citations

| Citation | Theory | Key Finding |
|----------|--------|-------------|
| **Rogers (1983)** | PMT Original | Threat Appraisal + Coping Appraisal → Protection Motivation |
| **Grothmann & Reusswig (2006)** | PMT for Flood | HIGH TP + HIGH CP → Action; HIGH TP + LOW CP → Denial/Fatalism |
| **Bamberg et al. (2017)** | Meta-analysis | CP (r=0.30) > TP (r=0.23) as predictor (N=35,419) |
| **Lindell & Perry (2012)** | PADM | 3 core perceptions: Threat, Protective Action, Stakeholder |

### Protection Motivation Theory (PMT) - Rogers (1983)

**Original Paper:** Rogers, R.W. (1983). Cognitive and physiological processes in fear appeals and attitude change: A revised theory of protection motivation. In J.T. Cacioppo & R.E. Petty (Eds.), *Social psychophysiology: A sourcebook* (pp. 153-176). Guilford Press.

**PMT Components:**

```
Protection Motivation = f(Threat Appraisal, Coping Appraisal)

Threat Appraisal:
├── Perceived Severity
└── Perceived Vulnerability

Coping Appraisal:
├── Response Efficacy (action effectiveness)
├── Self-Efficacy (ability to perform)
└── Response Costs
```

### Grothmann & Reusswig (2006) - Flood PMT Extension

**Paper:** Grothmann, T., & Reusswig, F. (2006). People at risk of flooding: Why some residents take precautionary action while others do not. *Natural Hazards*, 38, 101-120.

**Key Finding: TP × CP Interaction Matrix**

| TP | CP | Outcome | Validation Rule |
|----|----|---------|----------------|
| HIGH | HIGH | **Protection Motivation** → Action | R1: do_nothing = Error |
| HIGH | LOW | **Non-protective (denial/fatalism)** | VALID path |
| LOW | HIGH | Preventive action possible | OK |
| LOW | LOW | No action (rational) | OK |

**Non-Protective Responses:**
- Denial: Dismissing flood risk
- Fatalism: No control over outcome
- Wishful thinking: Hoping flood won't occur

### Bamberg et al. (2017) - Meta-Analysis

**Paper:** Bamberg, S., Masson, T., Brewitt, K., & Nemetschek, N. (2017). Threat, coping and flood prevention – A meta-analysis. *Journal of Environmental Psychology*, 54, 116-126.

**Key Findings:**
- 35 studies, 47 samples, N = 35,419
- **Coping Appraisal: r = 0.30** (stronger predictor)
- Threat Appraisal: r = 0.23

**Validation Implication:** LOW CP → expensive action is highly inconsistent (R2)

### PADM - Lindell & Perry (2012)

**Paper:** Lindell, M.K., & Perry, R.W. (2012). The Protective Action Decision Model: Theoretical modifications and additional evidence. *Risk Analysis*, 32(4), 616-632.

**Three Core Perceptions:**
1. Threat Perceptions
2. Protective Action Perceptions
3. **Stakeholder Perceptions** (trust in institutions)

**Stakeholder Perception Effects:**
- Low SP + Low TP → No motivation for protective action
- High trust may lower risk perception (reliance on institutions)
- Low trust + high risk may not lead to action if distrust in mechanism

---

## PR 2.5: Multi-Agent Validator Design

### Existing Validators (from v2_skill_governed)

| Validator | Function | Layer |
|-----------|----------|-------|
| **SkillAdmissibilityValidator** | Skill exists? Agent type allowed? | 1 |
| **ContextFeasibilityValidator** | Preconditions met? | 2 |
| **InstitutionalConstraintValidator** | Once-only, permanent | 3 |
| **EffectSafetyValidator** | Only modifies allowed state fields? | 4 |
| **PMTConsistencyValidator** | Threat-coping logic consistent? | 5 |
| **UncertaintyValidator** | Uncertain language? (disabled) | 6 |

### New/Extended Validators for Multi-Agent

#### 1. AgentTypeAdmissibilityValidator (Extended)

```python
class AgentTypeAdmissibilityValidator(SkillAdmissibilityValidator):
    """Extended to support multi-agent types"""
    
    name = "AgentTypeAdmissibilityValidator"
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        errors = []
        agent_type = context.get("agent_type")  # household_owner, household_renter, insurance, government
        
        # Check if skill belongs to this agent type
        skill_def = registry.get(proposal.skill_name)
        if skill_def and agent_type not in skill_def.eligible_agents:
            errors.append(f"Skill '{proposal.skill_name}' not available for {agent_type}")
        
        # Renter cannot use owner-only skills
        if agent_type == "household_renter":
            if proposal.skill_name in ["elevate_house", "buyout_program"]:
                errors.append(f"Renter cannot use owner-only skill: {proposal.skill_name}")
        
        return ValidationResult(valid=len(errors) == 0, validator_name=self.name, errors=errors)
```

#### 2. ConstructConsistencyValidator (New - Core)

**Literature Basis:**
- **Bamberg et al. (2017)**: Meta-analysis of 35 studies (N=35,419) - CP (r=0.30) is stronger predictor than TP (r=0.23)
- **Grothmann & Reusswig (2006)**: HIGH TP + HIGH CP → Protection Motivation; HIGH TP + LOW CP → Non-protective responses (denial/fatalism)
- **PADM (Lindell & Perry, 2012)**: SP (Stakeholder Perception) influences trust and action

```python
class ConstructConsistencyValidator(SkillValidator):
    """
    Validate consistency between constructs (TP/CP/SP) and decision.
    
    Literature citations:
    - Bamberg et al. (2017): Meta-analysis confirms CP > TP as predictor
    - Grothmann & Reusswig (2006): TP × CP interaction model
    - Lindell & Perry (2012): PADM stakeholder perception
    """
    
    name = "ConstructConsistencyValidator"
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        errors = []
        warnings = []
        
        # Get parsed construct levels from LLM output
        tp = context.get("parsed_tp_level", "MODERATE")  # LOW/MODERATE/HIGH
        cp = context.get("parsed_cp_level", "MODERATE")
        sp = context.get("parsed_sp_level", "MODERATE")
        skill = proposal.skill_name
        
        expensive_actions = ["elevate_house", "relocate", "buyout_program"]
        
        # === STRONG EVIDENCE RULES (Error) ===
        
        # Rule 1: HIGH TP + HIGH CP + do_nothing = inconsistent
        # Citation: Grothmann & Reusswig (2006) - this combination should lead to protection motivation
        if tp == "HIGH" and cp == "HIGH" and skill == "do_nothing":
            errors.append("R1: HIGH TP + HIGH CP should motivate action [Grothmann & Reusswig 2006]")
        
        # Rule 2: LOW CP + expensive action = inconsistent
        # Citation: Bamberg et al. (2017) - CP is strongest predictor; LOW CP = cannot afford
        if cp == "LOW" and skill in expensive_actions:
            errors.append("R2: LOW CP cannot afford expensive action [Bamberg et al. 2017]")
        
        # Rule 3: LOW TP + extreme action = overreaction
        # Citation: Rogers (1983) PMT - threat appraisal necessary for extreme response
        if tp == "LOW" and skill in ["relocate", "buyout_program"]:
            errors.append("R3: LOW TP does not justify extreme action [Rogers 1983 PMT]")
        
        # Rule 4: LOW SP + LOW TP + buy_insurance = irrational
        # Citation: PADM - no threat + distrust = no motivation
        if sp == "LOW" and tp == "LOW" and skill == "buy_insurance":
            errors.append("R4: LOW SP + LOW TP makes insurance purchase irrational [PADM]")
        
        # === MODERATE EVIDENCE RULES (Warning) ===
        
        # Rule 5: LOW SP + buy_insurance (with threat) = unusual but possible
        # Citation: Trust literature - fear may override distrust
        if sp == "LOW" and tp in ["MODERATE", "HIGH"] and skill == "buy_insurance":
            warnings.append("R5: LOW SP but chose insurance - fear overrides distrust?")
        
        # === VALID NON-PROTECTIVE PATH ===
        # Note: HIGH TP + LOW CP + do_nothing is VALID (fatalism/denial)
        # Citation: Grothmann & Reusswig (2006) - non-protective responses are documented
        
        return ValidationResult(
            valid=len(errors) == 0, 
            validator_name=self.name, 
            errors=errors, 
            warnings=warnings
        )
```

**Validation Rule Summary:**

| Rule | Logic | Citation | Severity |
|------|-------|----------|----------|
| R1 | HIGH TP + HIGH CP + do_nothing | Grothmann & Reusswig (2006) | Error |
| R2 | LOW CP + expensive action | Bamberg et al. (2017) meta-analysis | Error |
| R3 | LOW TP + extreme action | Rogers (1983) PMT | Error |
| R4 | LOW SP + LOW TP + buy_insurance | PADM (Lindell & Perry) | Error |
| R5 | LOW SP + buy_insurance (with threat) | Trust literature | Warning |

**Important Note:** 
- HIGH TP + LOW CP + do_nothing is **VALID** (fatalism/denial pathway, Grothmann & Reusswig 2006)

#### 3. MGSubsidyConsistencyValidator (New)

```python
class MGSubsidyConsistencyValidator(SkillValidator):
    """Validate MG subsidy logic consistency"""
    
    name = "MGSubsidyConsistencyValidator"
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        errors = []
        
        is_mg = context.get("is_MG", False)
        subsidy_rate = context.get("subsidy_rate", 0)
        skill = proposal.skill_name
        cp_explanation = context.get("parsed_cp_explanation", "").lower()
        
        # MG has subsidy but claims "cannot afford" + chose do_nothing
        if is_mg and subsidy_rate > 0.3:
            if "cannot afford" in cp_explanation and skill == "do_nothing":
                errors.append("MG has subsidy available but claims cannot afford")
        
        # NMG references subsidy (should not have this information)
        if not is_mg:
            sp_explanation = context.get("parsed_sp_explanation", "").lower()
            if "subsidy" in sp_explanation and "you may qualify" not in sp_explanation:
                errors.append("NMG references subsidy information incorrectly")
        
        return ValidationResult(valid=len(errors) == 0, validator_name=self.name, errors=errors)
```

#### 4. InsurancePolicyValidator (New)

```python
class InsurancePolicyValidator(SkillValidator):
    """Validate Insurance agent decision logic"""
    
    name = "InsurancePolicyValidator"
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        errors = []
        warnings = []
        
        loss_ratio = context.get("loss_ratio", 0)
        skill = proposal.skill_name
        
        # High loss ratio but chose lower_premium - unsustainable
        if loss_ratio > 0.80 and skill == "lower_premium":
            errors.append("High loss ratio (>80%) but chose to lower premium - unsustainable")
        
        # Low loss ratio but chose raise_premium - may be excessive (warning only)
        if loss_ratio < 0.30 and skill == "raise_premium":
            warnings.append("Low loss ratio (<30%) but chose to raise premium")
        
        return ValidationResult(valid=len(errors) == 0, validator_name=self.name, errors=errors, warnings=warnings)
```

#### 5. GovernmentBudgetValidator (New)

```python
class GovernmentBudgetValidator(SkillValidator):
    """Validate Government agent budget consistency"""
    
    name = "GovernmentBudgetValidator"
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        errors = []
        
        budget_remaining = context.get("budget_remaining", 0)
        budget_total = context.get("budget_total", 1)
        skill = proposal.skill_name
        
        # Budget nearly exhausted but chose increase_subsidy
        if budget_remaining < 0.20 * budget_total and skill == "increase_subsidy":
            errors.append("Budget nearly exhausted (<20%) but chose to increase subsidy")
        
        return ValidationResult(valid=len(errors) == 0, validator_name=self.name, errors=errors)
```

### Validator Pipeline (by Agent Type)

```
┌─────────────────────────────────────────────────────────────┐
│  Household Decision                                         │
│  ├── 1. AgentTypeAdmissibilityValidator                    │
│  ├── 2. ContextFeasibilityValidator                        │
│  ├── 3. InstitutionalConstraintValidator                   │
│  ├── 4. EffectSafetyValidator                              │
│  ├── 5. ConstructConsistencyValidator (NEW - uses 5 constructs)
│  └── 6. MGSubsidyConsistencyValidator (NEW)                │
│                                                             │
│  Insurance Decision                                         │
│  ├── 1. SkillAdmissibilityValidator                        │
│  └── 2. InsurancePolicyValidator (NEW)                     │
│                                                             │
│  Government Decision                                        │
│  ├── 1. SkillAdmissibilityValidator                        │
│  └── 2. GovernmentBudgetValidator (NEW)                    │
└─────────────────────────────────────────────────────────────┘
```

### Validation Factory

```python
def create_validators_for_agent(agent_type: str) -> List[SkillValidator]:
    """Create appropriate validator pipeline based on agent type"""
    
    if agent_type in ["household_owner", "household_renter"]:
        return [
            AgentTypeAdmissibilityValidator(),
            ContextFeasibilityValidator(),
            InstitutionalConstraintValidator(),
            EffectSafetyValidator(),
            ConstructConsistencyValidator(),
            MGSubsidyConsistencyValidator(),
        ]
    elif agent_type == "insurance":
        return [
            SkillAdmissibilityValidator(),
            InsurancePolicyValidator(),
        ]
    elif agent_type == "government":
        return [
            SkillAdmissibilityValidator(),
            GovernmentBudgetValidator(),
        ]
    else:
        return [SkillAdmissibilityValidator()]
```

---

## Next Steps

1. ✅ Skills defined (skill_registry.yaml)
2. ✅ Prompts aligned (5 constructs: TP/CP/SP/SC/PA)
3. ✅ **Validators designed** (5 new validators)
4. ✅ **Literature verified** (34 studies, all DOIs validated)
5. ⬜ Implementation

---

## Literature References

### BibTeX Files (Zotero Import Ready)

| File | Entries | Scope |
|------|---------|-------|
| `docs/references/pmt_flood_literature.bib` | 14 | PMT Global (2006-2024) |
| `docs/references/us_flood_literature.bib` | 20 | 🇺🇸 US Flood (2012-2024) |

### Validator Rule → Study Mapping

| Rule | Logic | Primary Study | DOI |
|------|-------|---------------|-----|
| R1 | HIGH TP + HIGH CP + do_nothing | Bamberg et al. (2017) Meta, N=35,419 | 10.1016/j.jenvp.2017.08.001 |
| R2 | LOW CP + expensive action | Bamberg et al. (2017) | 10.1016/j.jenvp.2017.08.001 |
| R3 | LOW TP + extreme action | Weyrich et al. (2020), N=1,019 | 10.5194/nhess-20-287-2020 |
| R4 | LOW SP + LOW TP + insurance | Lindell & Perry (2012) PADM | 10.1111/j.1539-6924.2011.01647.x |

### Key US Empirical Studies

| Study | Location | N | Key Finding |
|-------|----------|---|-------------|
| Botzen et al. (2019) | NYC | 1,000+ | High efficacy → action |
| Choi et al. (2024) | US County | - | +7% insurance post-flood |
| Mach et al. (2019) | Nationwide | 40,000+ | FEMA buyout patterns |
| Bukvic & Barnett (2023) | East Coast | 1,450 | Place attachment → relocation |

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
