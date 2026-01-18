# 自定義指南 - Governed Broker Framework

## 概述

本指南說明如何自定義框架的各個組件以適應您的領域。

---

## 1. 自定義驗證器 (Validators)

創建新驗證器繼承 `BaseValidator`:

```python
from validators.base import BaseValidator
from broker.types import DecisionRequest, ValidationResult

class MyDomainValidator(BaseValidator):
    name = "MyDomainValidator"
    
    def validate(self, request: DecisionRequest, context: dict) -> ValidationResult:
        errors = []
        
        # 您的驗證邏輯
        if some_condition_fails:
            errors.append("描述錯誤原因")
        
        return ValidationResult(valid=len(errors) == 0, errors=errors)
```

然後在配置中啟用:
```yaml
validators:
  domain_validators:
    - MyDomainValidator
```

---

## 2. 自定義 Audit 欄位

修改 `audit` 配置:

```yaml
audit:
  log_level: full  # full | summary | errors_only
  trace_fields:
    - run_id
    - step_id
    - your_custom_field  # 新增欄位
```

在 `AuditWriter.write_trace()` 調用時傳入:
```python
audit.write_trace({
    "run_id": run_id,
    "your_custom_field": your_value,
    ...
})
```

---

## 3. 自定義環境 (Environment)

繼承或修改 `ToyEnvironment`:

```python
from dataclasses import dataclass

@dataclass
class FloodEnvironment:
    year: int = 0
    flood_event: bool = False
    flood_severity: float = 0.0
    grant_available: bool = False
    
    def advance(self, seed: int):
        self.year += 1
        # 您的環境更新邏輯
        random.seed(seed + self.year)
        self.flood_event = random.random() < 0.2
```

---

## 4. 自定義 Actions

在 `action_catalog` 中定義:

```yaml
action_catalog:
  buy_flood_insurance:
    description: "購買洪水保險"
    cost: 500
    constraints:
      - "not agent.has_insurance"
    effects:
      has_insurance: true
      
  elevate_house:
    description: "房屋加高"
    cost: 10000
    constraints:
      - "not agent.elevated"
      - "agent.resources >= 10000"
    effects:
      elevated: true
      vulnerability: 0.1
```

在 Simulation Engine 中實現處理器:
```python
def _buy_flood_insurance(self, agent_id: str) -> dict:
    agent = self.get_agent(agent_id)
    agent.has_insurance = True
    return {"has_insurance": True}
```

---

## 5. 自定義 Context Builder

繼承 `ContextBuilder`:

```python
from broker.context_builder import ContextBuilder

class FloodContextBuilder(ContextBuilder):
    def build(self, agent_id: str) -> dict:
        # 返回您的 bounded context
        return {
            "elevation_status": "elevated" if agent.elevated else "not elevated",
            "insurance_status": "have" if agent.has_insurance else "do not have",
            "trust_text": self.verbalize_trust(agent.trust),
            "memory": agent.memory[-5:],
            "flood_status": self._get_flood_status(),
            ...
        }
```

---

## 6. 可觀察 vs 隱藏狀態

在配置中明確區分:

```yaml
observable_signals:
  # LLM 可以看到的
  - threat_perception
  - resources
  - memory

hidden_state:
  # LLM 不能看到的
  - seed
  - flood_threshold
  - internal_probability
```

---

## 7. Retry 策略

```yaml
retry_policy:
  max_retries: 2          # 最大重試次數
  retry_on:               # 哪些驗證失敗時重試
    - SchemaValidator
    - PolicyValidator
  fallback_action: do_nothing  # UNCERTAIN 時的默認動作
```

---

## 8. 整合範例 (Flood Adaptation)

參見 `examples/flood_adaptation/` 目錄的完整實現。
