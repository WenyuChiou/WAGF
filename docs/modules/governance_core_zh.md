# 核心治理架構 (Governance Core)

**🌐 Language: [English](governance_core.md) | [中文](governance_core_zh.md)**

governance core 是框架的「理性引擎」，確保 LLM 的輸出不僅僅是文字，而是**有效、安全且合邏輯的行動**。

---

## 1. 技能生命週期 (Skill Lifecycle)

一個技能從定義到執行的完整流程如下：

### 第 1 步：定義 (Definition)

所有的技能都必須在 `agent_types.yaml` 中註冊。這是唯一的真理來源。

```yaml
household:
  # 允許的動作列表
  actions: ["do_nothing", "buy_insurance", "elevate_house"]

  # 動作別名 (Alias) - 讓 LLM 使用更自然的語言
  alias:
    "wait": "do_nothing"
    "purchase": "buy_insurance"
```

### 第 2 步：解析 (Parsing)

當 LLM 輸出回應後，`UnifiedAdapter` 會嘗試將其映射到註冊的技能：

1.  **正規化**: 移除空白、轉小寫 (e.g., "Buy Insurance" -> "buy_insurance")。
2.  **別名查找**: 檢查是否為 Alias (e.g., "wait" -> "do_nothing")。
3.  **未知過濾**: 如果不在 `actions` 列表中，視為無效技能 (Invalid Skill)。

### 第 3 步：驗證 (Validation)

這是核心治理步驟。`AgentValidator` 會根據兩層規則檢查技能提案：

#### Tier 1: 身份與狀態 (Identity)

檢查 Agent **是否有權** 執行此動作。

- _規則範例_：只有 `savings > 5000` 才能 `buy_insurance`。
- _配置_：在 `agent_types.yaml` 的 `identity_rules` 區塊。

#### Tier 2: 認知一致性 (Thinking)

檢查 Agent 的 **推理是否合理**。

- _規則範例_：如果 `threat_appraisal` 是 "High"，則不應選擇 `do_nothing`。
- _配置_：在 `agent_types.yaml` 的 `thinking_rules` 區塊。

---

## 2. 驗證器定義 (Validator Definition)

驗證器並非硬編碼 (Hardcoded)，而是完全由 YAML 配置驅動。

### 驗證規則範例 (`agent_types.yaml`)

```yaml
thinking_rules:
  - id: "R_LOGIC_01"
    level: "WARNING"
    message: "High threat perception implies action."
    # 當 Threat 為 High 且 Coping 為 High 時
    conditions:
      - { construct: "threat_appraisal", values: ["H", "VH"] }
      - { construct: "coping_appraisal", values: ["H", "VH"] }
    # 禁止做什麼？
    blocked_skills: ["do_nothing"]
```

- **id**: 規則唯一標識符 (用於審計日誌)。
- **level**: `ERROR` (拒絕執行) 或 `WARNING` (允許但記錄)。
- **conditions**: 觸發規則的前提條件。
- **blocked_skills**: 在此條件下被禁止的動作。

---

## 3. 審計 (Auditing)

所有的驗證結果都會被記錄在 `simulation.log` 與 `audit_summary.json` 中。這讓我們可以追蹤：

- 多少次 Agent 試圖違反規則？
- 哪條規則被觸發最多次？
- LLM 的「理性程度」 (Alignment Score)。
