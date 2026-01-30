# 治理核心架構（Governance Core）

**語言： [English](governance_core.md) | [中文](governance_core_zh.md)**

Governance Core 確保 LLM 輸出的決策符合認知與身份規則，是整個系統的安全閘門。

---

## 1. 技能生命週期（Skill Lifecycle）

### Step 1：定義（Definition）

在 `agent_types.yaml` 中定義可用技能與別名：

```yaml
household:
  actions: ["do_nothing", "buy_insurance", "elevate_house"]
  alias:
    "wait": "do_nothing"
    "purchase": "buy_insurance"
```

### Step 2：解析（Parsing）

`UnifiedAdapter` 將 LLM 輸出解析成結構化技能：

1. 標準化字串（如 "Buy Insurance" → "buy_insurance"）  
2. 別名對應（如 "wait" → "do_nothing"）  
3. 驗證是否在 `actions` 清單內

### Step 3：驗證（Validation）

`AgentValidator` 檢查認知一致性：

#### Tier 1：身份與狀態（Identity）

- 例：`savings > 5000` 才能買保險  

#### Tier 2：認知一致性（Thinking）

- 例：`threat_appraisal` 為高時不能 `do_nothing`

### 4. 教學：建立一條邏輯約束（Ordering 範例）

#### 4.1 Step 1：定義規則（Thinking Pattern）

定義條件與阻擋技能。

#### 4.2 Step 2：實作 Validator

將規則轉為程式化檢查。

#### 4.3 Step 3：在 YAML 註冊

把規則加入 `agent_types.yaml`。

#### 4.4 Step 4：稽核軌跡

驗證與阻擋紀錄會輸出到稽核檔案。

---

## 2. 驗證器定義（Validator Definition）

### 驗證規則範例（`agent_types.yaml`）

```yaml
thinking_rules:
  - id: "R_LOGIC_01"
    level: "WARNING"
    message: "High threat perception implies action."
    conditions:
      - { construct: "threat_appraisal", values: ["H", "VH"] }
      - { construct: "coping_appraisal", values: ["H", "VH"] }
    blocked_skills: ["do_nothing"]
```

### ERROR 與 WARNING 的行為差異

- **ERROR**：阻擋行為並要求重試  
- **WARNING**：保留行為但記錄警示

---

## 2.5 跨 Agent 驗證（Multi-Agent）

### 通用檢查

- 回音室（Echo Chamber）
- 死鎖風險（Deadlock）

### 可插拔領域規則

以領域特定規則擴充驗證（例如洪水預算一致性、逆向誘因）。

### 驗證等級（Validation Levels）

使用統一等級標記驗證結果：`ERROR`（阻擋）、`WARNING`（觀察）、`INFO`（提示）。

---

## 3. 稽核（Auditing）

驗證結果會輸出到 `simulation.log` 與 `audit_summary.json`：

- 觸發了哪些規則  
- 哪些規則被阻擋  
- LLM 對齊分數等指標  
