# 自定義指南 — Governed Broker Framework

## 概述

本指南說明如何自定義框架的各個組件以適應新的領域。所有範例同時展示洪水適應（PMT）與灌溉需求（雙評估）兩個領域的配置模式。

---

## 1. 自定義驗證器 (Validators)

每個檢查函數遵循 `BuiltinCheck` 可調用簽名：`(skill_name, rules, context) -> List[ValidationResult]`：

```python
from typing import List, Dict, Any
from broker.governance.rule_types import GovernanceRule
from broker.validators.governance.base_validator import ValidationResult

def my_physical_check(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """物理約束檢查 — 超出容量時阻止增加。"""
    if skill_name != "increase_demand":
        return []
    if not context.get("at_cap", False):
        return []
    return [ValidationResult(
        valid=False,                  # ERROR = 阻止並重試
        validator_name="DomainPhysicalValidator",
        errors=["已達到最大容量，無法增加需求。"],
        warnings=[],
        metadata={"rule_id": "capacity_cap_check", "level": "ERROR"},
    )]
```

驗證器分為五大類別：

| 類別 | 用途 | 範例 |
|------|------|------|
| **Physical** | 物理狀態約束 | 不能重複高架房屋、不能超過水權上限 |
| **Personal** | 個人資源約束 | 儲蓄不足以支付高架費用 |
| **Social** | 社區規範檢查 | 鄰居多數已適應但代理未行動 |
| **Semantic** | 推理一致性 | 引用不存在的鄰居、引用未發生的事件 |
| **Thinking** | 評估-行動一致性 | YAML 規則驅動（見 agent_types.yaml） |

### 註冊驗證器

聚合所有檢查函數並使用橋接函數連接到 `ExperimentBuilder`：

```python
ALL_CHECKS = [my_physical_check, my_social_check, my_semantic_check]

def my_domain_validator(proposal, context, skill_registry=None):
    """橋接領域檢查到 SkillBrokerEngine custom_validators。"""
    skill_name = getattr(proposal, "skill_name", str(proposal))
    results = []
    for check in ALL_CHECKS:
        results.extend(check(skill_name, [], context))
    return results
```

在 `ExperimentBuilder` 中注入：

```python
builder.with_custom_validators([my_domain_validator])
```

---

## 2. 自定義回應格式 (Response Format)

在 `agent_types.yaml` 的 `shared.response_format.fields` 中定義 LLM 輸出欄位：

```yaml
shared:
  response_format:
    delimiter_start: "<<<DECISION_START>>>"
    delimiter_end: "<<<DECISION_END>>>"
    fields:
      - { key: "reasoning", type: "text", required: false }
      - {
          key: "threat_assessment",
          type: "appraisal",
          required: true,
          construct: "THREAT_LABEL",
          reason_hint: "一句話說明威脅程度。"
        }
      - { key: "decision", type: "choice", required: true }
      # 可選：數值型態欄位
      - { key: "magnitude_pct", type: "numeric", min: 1, max: 30, required: false }
```

**欄位型態**：
- `text`：自由文字（推理分析）
- `appraisal`：JSON 物件 `{LABEL: "VL"..."VH", REASON: "..."}`
- `choice`：整數技能 ID
- `numeric`：有界數值（如百分比幅度）

---

## 3. 自定義記憶引擎 (Memory Engine)

### WRR 驗證配置（HumanCentric 基本排名模式）

```yaml
your_agent_type:
  memory:
    engine_type: "human_centric"
    window_size: 5                    # 短期記憶緩衝區
    top_k_significant: 2             # 按衰減重要性排名的頂部記憶

    emotion_keywords:
      crisis: ["drought", "shortage", "flood", "damage"]
      strategic: ["decision", "adopt", "reduce", "conservation"]
      positive: ["surplus", "adequate", "safe", "improved"]
      social: ["neighbor", "community", "upstream"]

    emotional_weights:
      crisis: 1.0
      strategic: 0.8
      positive: 0.6
      social: 0.4
      baseline_observation: 0.1

    source_patterns:
      personal: ["i ", "my ", "me "]
      neighbor: ["neighbor", "adjacent", "upstream"]
      community: ["basin", "community", "region"]
```

**重要性計算**：`importance = emotional_weight * source_weight`

**檢索模式**：基本排名模式結合最近 window（5 條最新記憶）與 top-k（2 條最高衰減重要性記憶）。

### 可用引擎

| 引擎 | 模式 | 適用情境 |
|------|------|----------|
| `HumanCentricMemoryEngine` | 基本排名 | **WRR 驗證**。推薦用於所有正式實驗。 |
| `ImportanceMemoryEngine` | 加權評分 | 實驗性。使用 recency/importance/context 權重。 |
| `WindowMemoryEngine` | FIFO | 基線。固定大小滑動窗口。 |

---

## 4. 自定義反思引擎 (Reflection)

### 配置反思引導問題

在 `agent_types.yaml` 中定義領域特定的反思引導問題：

```yaml
global_config:
  reflection:
    interval: 1                      # 每年反思一次
    batch_size: 10                   # 每批代理人數
    importance_boost: 0.9            # 反思見解的重要性分數
    method: hybrid
    questions:
      - "你的策略在當前條件下是否有效？"
      - "你的行動幅度與結果之間有什麼模式？"
      - "你應該如何調整未來的做法？"
```

### 行動-結果回饋

每年代理人會收到結合記憶，將決策與結果連結：

> "第 5 年：你選擇了 decrease_demand 15%。結果：供水充足，利用率降至 65%。"

這通過反思循環實現因果學習。

---

## 5. 自定義技能 (Skills)

在 `skill_registry.yaml` 中定義新技能：

```yaml
skills:
  - skill_id: your_new_skill
    description: "技能描述（會顯示在 LLM 提示中）。"
    eligible_agent_types: ["your_agent_type"]
    preconditions:
      - "not already_done"            # 布林狀態檢查
    institutional_constraints:
      once_only: true                 # 僅可執行一次
      cost_type: "one_time"
    allowed_state_changes:
      - has_done_it                   # 此技能修改的代理屬性
    implementation_mapping: "env.execute_skill"
    conflicts_with: [conflicting_skill]
```

**關鍵欄位**：
- `preconditions`：控制技能是否可用（如 `"not elevated"` 表示尚未高架）
- `institutional_constraints`：制度規則（如 `once_only`, `annual`, `max_magnitude_pct`）
- `conflicts_with`：互斥技能（如 increase_demand 與 decrease_demand）

### 幅度參數化（magnitude_pct）

對於需要量化決策的技能（如灌溉需求變化百分比），在回應格式中添加 `numeric` 欄位：

```yaml
# agent_types.yaml
fields:
  - { key: "magnitude_pct", type: "numeric", min: 1, max: 30, required: false }

# skill_registry.yaml
institutional_constraints:
  magnitude_type: "percentage"
  max_magnitude_pct: 30
  magnitude_default: 10              # LLM 省略時的預設值
```

---

## 6. 自定義治理規則 (Governance Rules)

### Thinking Rules（評估一致性）

基於 LLM 生成的構念標籤阻止不一致的行動：

```yaml
thinking_rules:
  - id: my_rule_id
    construct: THREAT_LABEL           # 單一構念
    when_above: ["VH"]                # 觸發條件
    blocked_skills: ["do_nothing"]    # 被阻止的技能
    level: ERROR                      # ERROR = 阻止; WARNING = 記錄
    message: "威脅極高時必須採取行動。"

  # 多構念規則
  - id: multi_construct_rule
    conditions:
      - { construct: THREAT_LABEL, values: ["H", "VH"] }
      - { construct: CAPACITY_LABEL, values: ["H", "VH"] }
    blocked_skills: ["aggressive_action"]
    level: WARNING
```

### Identity Rules（狀態約束）

基於代理物理狀態阻止不可能的行動：

```yaml
identity_rules:
  - id: physical_block
    precondition: already_done        # 布林狀態欄位
    blocked_skills: ["that_action"]
    level: ERROR
    message: "物理上不可能重複此行動。"
```

### 規則評估順序

```
1. Identity Rules    → 物理狀態約束（總是最先評估）
2. Thinking Rules    → 評估一致性（按 YAML 順序）
3. Domain Validators → 自定義檢查（物理、社會、語義）
```

第一個 ERROR 級別違規終止評估並觸發重新提示（最多 3 次治理重試）。

---

## 7. 自定義提示模板 (Prompt Templates)

在 `config/prompts/` 目錄中創建模板文件：

```text
You are {persona_narrative}.

=== 當前情況 (第 {year} 年) ===
{situation_context}

=== 你的近期記憶 ===
{memory_text}

=== 可用行動 ===
{skills_text}

=== 你的任務 ===
以以下格式回應：
<<<DECISION_START>>>
reasoning: [你的分析]
threat_assessment: {"THREAT_LABEL": "...", "THREAT_REASON": "..."}
decision: [數字]
<<<DECISION_END>>>
```

`TieredContextBuilder` 在運行時填充佔位符。

---

## 8. 自定義環境 (Simulation Environment)

環境管理物理狀態並執行已批准的技能：

```python
class YourEnvironment:
    def __init__(self, agents, seed=42):
        self.agents = agents
        self.year = 0

    def advance_year(self):
        """更新環境狀態。"""
        self.year += 1
        # 生成隨機事件、更新條件等

    def execute_skill(self, agent_id: str, skill_name: str, parameters: dict):
        """執行已批准的技能。"""
        agent = self.agents[agent_id]
        if skill_name == "increase_demand":
            magnitude = parameters.get("magnitude_pct", 10) / 100
            agent.request *= (1 + magnitude)
        elif skill_name == "adopt_technology":
            agent.has_technology = True
```

---

## 9. 生命週期掛鈎 (Lifecycle Hooks)

| 掛鈎 | 時機 | 用途 |
|------|------|------|
| `pre_year` | 每年開始前 | 注入記憶、更新上下文、同步狀態標誌 |
| `post_step` | 每個代理決策後 | 記錄決策到模擬日誌 |
| `post_year` | 每年結束後 | 觸發反思、保存輸出文件 |

```python
runner.hooks = {
    "pre_year":  hooks.pre_year,
    "post_step": hooks.post_step,
    "post_year": hooks.post_year,
}
```

---

## 10. 參考實現

| 實驗 | 理論 | 配置目錄 |
|------|------|----------|
| 洪水適應 | PMT (Rogers, 1983) | `examples/governed_flood/config/` |
| 灌溉 ABM | 雙評估 (Hung & Yang, 2021) | `examples/irrigation_abm/config/` |

詳見 [實驗設計指南](experiment_design_guide.md) 了解完整的建構流程。
