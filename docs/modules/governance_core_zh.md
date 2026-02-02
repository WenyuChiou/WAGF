# 治理核心架構（Governance Core）

**語言： [English](governance_core.md) | [中文](governance_core_zh.md)**

Governance Core 確保 LLM 輸出的決策符合程式與領域規則，是整個系統的穩定性保障。

---

## 1. 技能生命週期（Skill Lifecycle）

### Step 1: 定義

所有技能必須在 `agent_types.yaml` 中註冊，這是唯一的真實來源。

```yaml
household:
  actions: ["do_nothing", "buy_insurance", "elevate_house"]
  alias:
    "wait": "do_nothing"
    "purchase": "buy_insurance"
```

### Step 2: 解析

LLM 輸出後，`UnifiedAdapter` 嘗試將其對應到已註冊的技能：

1. **正規化**：移除空白、轉小寫（例如 "Buy Insurance" → "buy_insurance"）
2. **別名查找**：檢查是否為別名（例如 "wait" → "do_nothing"）
3. **未知過濾**：若不在 `actions` 清單中，視為無效技能

### Step 3: 驗證

`AgentValidator` 以雙層規則檢查技能提案：

#### Tier 1: 身份與狀態

檢查代理人是否有**資格**執行此行動。

- 範例：只有 `savings > 5000` 時才能 `buy_insurance`
- 設定：定義在 `agent_types.yaml` 的 `identity_rules` 區塊

#### Tier 2: 認知一致性（思考）

檢查代理人的**推理是否合理**。

- 範例：如果 `threat_appraisal` 為 "High"，不應 `do_nothing`
- 設定：定義在 `agent_types.yaml` 的 `thinking_rules` 區塊

### 4. 教學範例：建立邏輯約束

#### 4.1 Step 1: 定義規則

假設您要求代理人提出 3 個選項，且必須依**風險**從低到高排列。

#### 4.2 Step 2: 實作驗證器

```python
def validate_risk_ordering(decision, context):
    """確保選項按風險排序（低 → 高）。"""
    options = decision.get("ranked_options", [])
    current_risk = 0

    for opt in options:
        opt_risk = get_risk_score(opt)
        if opt_risk < current_risk:
            return ValidationResult(
                is_valid=False,
                violation_type="logic_error",
                message=f"風險排序違規：{opt['name']}（風險 {opt_risk}）排在更高風險選項之後。",
                fix_hint="請按風險分數遞增重新排列。"
            )
        current_risk = opt_risk

    return ValidationResult(is_valid=True)
```

#### 4.3 Step 3: 在 YAML 中註冊

```yaml
agent_types:
  risk_analyst:
    governance:
      validators:
        tier1:
          - name: "risk_ordering_enforcement"
            enabled: true
            function: "validate_risk_ordering"
```

#### 4.4 Step 4: 稽核軌跡

當代理人試圖違規時，**Governance Auditor** 會攔截。稽核日誌中可見：

```json
{
  "agent_id": "Analyst_01",
  "cycle": 12,
  "status": "REJECTED",
  "intervention": {
    "type": "logic_error",
    "message": "風險排序違規：'Crypto-Bet'（風險 9）排在 'Bonds'（風險 1）之後。",
    "correction_count": 1
  }
}
```

系統隨後**自動修正**：將錯誤訊息回傳給 LLM（System 2 回饋），LLM 重新輸出正確排序。稽核日誌證明是_治理層_而非_模型_強制執行了規則。

---

## 2. 驗證器定義

驗證器完全由 YAML 驅動，而非硬編碼。

### 驗證規則範例（`agent_types.yaml`）

```yaml
thinking_rules:
  - id: "R_LOGIC_01"
    level: "WARNING"
    message: "高威脅感知暗示應採取行動。"
    conditions:
      - { construct: "threat_appraisal", values: ["H", "VH"] }
      - { construct: "coping_appraisal", values: ["H", "VH"] }
    blocked_skills: ["do_nothing"]
```

- **id**：規則唯一標識符（用於稽核日誌）
- **level**：`ERROR`（拒絕執行）或 `WARNING`（記錄但允許）
- **conditions**：觸發規則的前置條件
- **blocked_skills**：在此條件下禁止的行動

### ERROR 與 WARNING 語意

`level` 欄位控制執行時行為：

| 等級 | `valid` | 效果 | 稽核輸出 |
| :--- | :--- | :--- | :--- |
| **ERROR** | `False` | 阻擋執行，觸發重試（最多 3 次）。錯誤訊息作為 System 2 回饋傳給代理人。 | `errors[]`、`total_interventions` |
| **WARNING** | `True` | 允許執行，但記錄觀察。適用於監控行為異常而不阻擋。 | `warnings[]`、`warning_rules`、`warnings.total_warnings` |

**實作**：在 `base_validator.py` 中，`validate()` 方法設定 `valid = not is_error`。WARNING 等級的規則觸發產生 `ValidationResult(valid=True, warnings=[message])`，技能被允許但觀察被記錄。

**設計原理**：某些規則偵測的條件值得觀察但不應阻擋。例如 `low_coping_block`（CP 在 {VL, L} 時選擇 elevate/relocate）設為 WARNING，因為低應對能力的代理人_可能_仍合理選擇保護行動——這是異常但非不合邏輯。

---

## 2.5 跨代理人驗證（Multi-Agent）

`CrossAgentValidator`（`broker/validators/governance/cross_agent_validator.py`）提供**跨代理人**的模式偵測，而非單一代理人推理內部的檢查。

### 通用檢查

| 檢查 | 規則 ID | 方法 | 偵測 |
| :--- | :--- | :--- | :--- |
| **迴聲室** | `ECHO_CHAMBER_DETECTED` | `echo_chamber_check()` | 當 > 80% 代理人選擇相同技能時標記 |
| **低熵** | `LOW_DECISION_ENTROPY` | （同上） | Shannon 熵 $H = -\sum p_i \log_2 p_i$ 低於閾值（預設 0.5 位元） |
| **死鎖** | `DEADLOCK_RISK` | `deadlock_check()` | 當 > 50% 提案被 GameMaster 拒絕時標記 |

### 可插拔領域規則

領域特定檢查透過 `domain_rules` 建構函式參數注入：

```python
validator = CrossAgentValidator(
    echo_threshold=0.8,
    entropy_threshold=0.5,
    deadlock_threshold=0.5,
    domain_rules=[perverse_incentive_check, budget_coherence_check],
)
```

每個領域規則是一個可呼叫的 `(artifacts, prev_artifacts) -> Optional[CrossValidationResult]`，檢查通過時回傳 `None`。

### 驗證等級

跨代理人結果使用 `ValidationLevel`（ERROR / WARNING / INFO）。所有通用檢查預設為 WARNING——標記模式供研究者審查，但不阻擋個別代理人行動。

---

## 2.7 領域驗證器（BuiltinCheck 模式）

除了 YAML 驅動的 thinking 和 identity 規則外，每個領域都使用 `BuiltinCheck` 模式實現 **自定義驗證器函數**。這些函數提供需要程式化邏輯的檢查（如算術比較、跨欄位驗證）：

```python
from broker.validators.governance.base_validator import ValidationResult

def my_physical_check(skill_name, rules, context):
    """超出物理容量時阻止增加。"""
    if skill_name != "increase_demand":
        return []
    if not context.get("at_cap", False):
        return []
    return [ValidationResult(
        valid=False,
        validator_name="DomainPhysicalValidator",
        errors=["已達到最大容量，無法增加。"],
        warnings=[],
        metadata={"rule_id": "capacity_cap_check", "level": "ERROR"},
    )]
```

驗證器分為 **5 大類別**：

| 類別 | 範圍 | 範例 |
|------|------|------|
| **Physical** | 狀態不可能性 | 不能重複高架、不能超過水權 |
| **Personal** | 資源約束 | 儲蓄不足以支付高架費用 |
| **Social** | 社區規範 | 多數鄰居已適應但代理未行動 |
| **Semantic** | 推理一致性 | 引用不存在的鄰居、引用未發生的事件 |
| **Thinking** | 評估一致性 | YAML 規則驅動（構念標籤 → 被阻止的技能） |

領域驗證器通過 `ExperimentBuilder.with_custom_validators()` 注入，在 identity 和 thinking 規則之後評估。參見 `examples/governed_flood/validators/flood_validators.py`（8 個檢查）和 `examples/irrigation_abm/validators/irrigation_validators.py`（8 個檢查）。

## 2.9 多技能複合驗證（Multi-Skill Composite Validation）

當 **Multi-Skill** 開關啟用時（`multi_skill.enabled: true`），Broker Engine 在標準 6 階段治理流程中新增兩個額外階段：

### Phase ④b：複合驗證（主要技能批准後）

主要技能通過個別驗證（identity rules、thinking rules、domain validators）後，引擎檢查是否有**次要技能**被提出。若有：

1. **個別驗證** — 次要技能經過與主要技能相同的驗證管線（資格、前置條件、thinking rules、identity rules）。
2. **複合衝突檢查** — `SkillRegistry.check_composite_conflicts()` 驗證該配對不互斥（見 [Skill Registry § 8](skill_registry_zh.md#8-複合衝突偵測multi-skill)）。
3. **重複拒絕** — 主要與次要不能是相同技能。

若複合驗證失敗，系統產生 `InterventionReport` 解釋哪個技能被阻擋及原因，然後觸發完整重試（主要和次要都重新生成）。在用盡最大重試次數後，次要技能被靜默丟棄，僅執行主要技能（**優雅降級**）。

### Phase ⑤b：循序次要執行

技能按嚴格順序執行：**先主要，後次要**。主要技能的 `state_changes` 在次要技能執行前先套用到 Agent。這確保：

- 次要技能的前置條件根據更新後的狀態評估。
- 因主要技能觸發的 identity rules（例如 `elevation_block`）被尊重。
- 無平行狀態變更衝突。

### 類型系統支援

`SkillBrokerResult` 資料類別攜帶可選的次要欄位：

| 欄位 | 類型 | 預設值 |
|------|------|--------|
| `secondary_proposal` | `Optional[SkillProposal]` | `None` |
| `secondary_approved` | `Optional[ApprovedSkill]` | `None` |
| `secondary_execution` | `Optional[ExecutionResult]` | `None` |
| `composite_validation_errors` | `List[str]` | `[]` |

當 `multi_skill.enabled: false`（預設）時，所有次要欄位保持 `None`，`to_dict()` 排除它們——現有稽核輸出零改變。

### 配置

```yaml
household:
  multi_skill:
    enabled: false              # 預設關閉
    max_skills: 2
    execution_order: "sequential"
    secondary_field: "secondary_decision"
    secondary_magnitude_field: "secondary_magnitude_pct"
```

`ResponseFormatBuilder` 在配置包含 `type: "secondary_choice"` 欄位時，有條件地在 LLM 提示模板中渲染 `secondary_choice` 欄位類型。該欄位標記為 OPTIONAL，使無法產生它的小型 LLM 仍能正常運作。

---

## 3. 稽核

所有驗證結果記錄在 `simulation.log` 和 `audit_summary.json` 中。可追蹤：

- 代理人嘗試違規的次數
- 哪條規則被觸發最多
- LLM 的「理性分數」（Alignment Score）
