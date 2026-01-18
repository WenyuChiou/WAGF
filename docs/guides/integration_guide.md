# Framework Integration Guide
## 使用者必須定義的要素

本指南列出使用 Governed Broker Framework 時必須提供的所有要素。

---

## 必要要素清單

| # | 要素 | 位置 | 必填 | 說明 |
|---|------|------|------|------|
| 1 | **Domain Config** | `config/domains/your_domain.yaml` | ✅ 是 | 領域配置 |
| 2 | **State Schema** | 在 config YAML 內 | ✅ 是 | Agent 狀態結構 |
| 3 | **Action Catalog** | 在 config YAML 內 | ✅ 是 | 可用動作定義 |
| 4 | **Prompt Template** | `examples/your_domain/prompts.py` | ✅ 是 | LLM 提示模板 |
| 5 | **Validators** | `examples/your_domain/validators.py` | ⚠️ 可選 | 領域驗證規則 |
| 6 | **Memory Rules** | `examples/your_domain/memory.py` | ⚠️ 可選 | 記憶更新邏輯 |
| 7 | **Simulation Engine** | `examples/your_domain/simulation.py` | ✅ 是 | 狀態轉換邏輯 |

---

## 1️⃣ Domain Config (必填)

定義領域的所有配置選項:

```yaml
# config/domains/your_domain.yaml

domain_name: "your_domain"
description: "描述您的領域"

# Agent 狀態結構
state_schema:
  agent:
    field1: type    # 例如: health: float
    field2: type    # 例如: resources: int
  memory:
    events: list
    window_size: 5
  environment:
    year: int
    event_occurred: bool

# LLM 可觀察的信號 (會傳入 prompt)
observable_signals:
  - field1
  - field2
  - memory

# LLM 不可見的狀態
hidden_state:
  - internal_field
  - seed

# 動作目錄
action_catalog:
  action_a:
    code: "1"
    description: "描述動作 A"
    constraints: []
    effects:
      field1: new_value
  action_b:
    code: "2"
    description: "描述動作 B"
    constraints:
      - "agent.field2 >= 10"
    effects:
      field2: "field2 - 10"

# 驗證器
validators:
  enabled:
    - SchemaValidator
    - PolicyValidator
  domain_validators:
    - YourDomainValidator

# 重試策略
retry_policy:
  max_retries: 2
  fallback_action: action_a

# 審計配置
audit:
  log_level: full
```

---

## 2️⃣ Prompt Template (必填)

定義 LLM 看到的提示:

```python
# examples/your_domain/prompts.py

PROMPT_TEMPLATE = """You are a {role} in a {context}.

Current State:
- Field 1: {field1}
- Field 2: {field2}

Your memory:
{memory}

{situation_description}

Available actions:
{options}

Respond with:
Reasoning: [Your thought process]
Final Decision: [Choose {valid_choices}]
"""

def build_prompt(agent_state: dict, env_state: dict) -> str:
    """構建完整 prompt"""
    return PROMPT_TEMPLATE.format(
        role="...",
        context="...",
        field1=agent_state["field1"],
        field2=agent_state["field2"],
        memory=format_memory(agent_state["memory"]),
        situation_description=get_situation(env_state),
        options=get_options(agent_state),
        valid_choices="1, 2, or 3"
    )
```

---

## 3️⃣ State Schema (必填)

在 config 中定義 Agent 狀態:

```yaml
state_schema:
  agent:
    # 核心狀態 (隨動作改變)
    status: str          # 例如: "healthy", "sick"
    resources: float     # 例如: 100.0
    has_protection: bool # 例如: true/false
    
    # 信念/認知狀態 (影響決策)
    risk_perception: float
    trust_level: float
    
    # 歷史
    decision_history: list
    
  memory:
    events: list
    window_size: 5       # 記憶窗口大小
```

---

## 4️⃣ Action Catalog (必填)

定義所有可用動作:

```yaml
action_catalog:
  action_name:
    code: "1"                    # LLM 輸出代碼
    description: "動作描述"       # 給 LLM 看的描述
    constraints:                 # 執行條件
      - "agent.resources >= 10"
    effects:                     # 執行效果
      resources: "resources - 10"
      has_protection: true
```

---

## 5️⃣ Validators (可選)

創建領域特定驗證規則:

```python
# examples/your_domain/validators.py

from validators.base import BaseValidator
from broker.types import ValidationResult

class YourDomainValidator(BaseValidator):
    name = "YourDomainValidator"
    
    def validate(self, request, context) -> ValidationResult:
        errors = []
        
        # 您的驗證邏輯
        reasoning = request.reasoning.get("reasoning", "").lower()
        decision = request.action_code
        
        # 規則: 如果 X 則 Y 應該成立
        if "high risk" in reasoning and decision == "do_nothing_code":
            errors.append("矛盾: 高風險但選擇不行動")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors
        )
```

---

## 6️⃣ Memory Rules (可選)

定義記憶更新邏輯:

```python
# examples/your_domain/memory.py

MEMORY_WINDOW = 5

def update_memory(memory: list, year: int, event: str, decision: str) -> list:
    """更新 agent 記憶"""
    
    # 添加事件記憶
    memory.append(f"Year {year}: {event}")
    
    # 添加決策記憶
    memory.append(f"Year {year}: You chose {decision}")
    
    # 保持窗口大小
    return memory[-MEMORY_WINDOW:]
```

---

## 7️⃣ Simulation Engine (必填)

實現狀態轉換邏輯:

```python
# examples/your_domain/simulation.py

class YourDomainSimulation:
    def __init__(self, num_agents, seed):
        self.agents = self._init_agents(num_agents)
        self.environment = self._init_environment()
    
    def advance_step(self):
        """推進環境一步"""
        self.environment.step += 1
        # 更新環境狀態
    
    def execute_decision(self, agent_id: str, decision: str) -> dict:
        """執行決策並返回狀態變化"""
        agent = self.agents[agent_id]
        state_changes = {}
        
        if decision == "1":
            agent.field1 = new_value
            state_changes["field1"] = new_value
        # ... 其他動作
        
        return state_changes
```

---

## 整合範例 (Flood Adaptation)

參見 `examples/flood_adaptation/` 目錄:

```
examples/flood_adaptation/
├── run.py           # 主執行腳本
├── prompts.py       # PROMPT_TEMPLATE + build_prompt()
├── validators.py    # PMTConsistencyValidator + FloodResponseValidator
├── memory.py        # MemoryManager + PAST_EVENTS
└── trust_update.py  # TrustUpdateManager (領域特有)
```

---

## 快速開始

1. 複製 `examples/flood_adaptation/` 作為模板
2. 修改 `config/domains/your_domain.yaml`
3. 修改 `prompts.py` 中的 PROMPT_TEMPLATE
4. 創建您的 `validators.py` (如需要)
5. 實現 `simulation.py` 的狀態轉換
6. 運行: `python run.py --model your_model`
