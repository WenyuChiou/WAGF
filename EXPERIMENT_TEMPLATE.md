# Experiment Template - Quick Start Guide

研究者只需提供這兩個文件即可創建新實驗：

## 📋 必要文件

### 1. `agent_types.yaml` - Agent 定義和規則

```yaml
# Agent 類型定義
household:
  description: "Household agents making flood adaptation decisions"
  
  # Skill 映射（數字 → 技能名稱）
  skill_map_non_elevated:
    "1": "buy_insurance"
    "2": "elevate_house"
    "3": "relocate"
    "4": "do_nothing"
  
  # 驗證規則
  validation_rules:
    - field: "trust_in_insurance"
      min_value: 0.0
      max_value: 1.0
      message: "Trust must be between 0 and 1"
  
  # Coherence 規則（可選 - PMT 檢查）
  coherence_rules:
    - rule_id: "high_threat_low_coping"
      condition:
        threat_level: "high"
        coping_level: "low"
      expected_behavior: "buy_insurance"
      severity: "warning"
  
  # Audit 設置
  audit:
    output_dir: "results"
    experiment_name: "my_experiment"
```

### 2. `skill_registry.yaml` - Skill 定義

```yaml
# Skill 註冊表
skills:
  buy_insurance:
    description: "Purchase flood insurance"
    agent_types: ["household"]
    mapping: "sim.buy_insurance"  # 映射到 simulation 方法
    
  elevate_house:
    description: "Elevate house to reduce flood risk"
    agent_types: ["household"]
    mapping: "sim.elevate_house"
    
  do_nothing:
    description: "Take no action this year"
    agent_types: ["household"]
    mapping: "sim.noop"
```

## 🚀 使用方式

```python
# run_my_experiment.py

from broker.experiment_runner import ExperimentRunner
from pathlib import Path

# 1. 指定實驗目錄（包含上述兩個文件）
experiment_dir = Path(__file__).parent

# 2. 創建並運行實驗
runner = ExperimentRunner.from_directory(experiment_dir)

# 3. 自定義 simulation（研究者提供自己的模擬邏輯）
from my_simulation import MySimulation  # 研究者的代碼

sim = MySimulation(num_agents=100)
broker = runner.create_broker(sim, model_name="gemma3:4b")

# 4. 運行
for year in range(10):
    for agent_id, agent in sim.agents.items():
        result = broker.process_step(context, agent)
        # ...
```

## 🎨 範例實驗結構

```
my_experiment/
├── agent_types.yaml          # ← 必需
├── skill_registry.yaml       # ← 必需
├── run_experiment.py         # ← 研究者編寫
├── my_simulation.py          # ← 研究者的模擬邏輯（可選）
└── results/                  # ← 自動創建
    └── gemma3_4b/
        ├── default_audit.jsonl
        └── summary.json
```

## ✨ 框架自動處理

- ✅ Parser (三階段)
- ✅ Validation (基於 agent_types.yaml)
- ✅ Coherence checking (PMT rules)
- ✅ Audit logging
- ✅ Retry logic
- ✅ Error handling

研究者只需專注於：
1. 定義 agent types 和 skills
2. 實現 simulation 邏輯
3. 分析結果

## 📚 進階客製化（可選）

### 自定義 Prompts

```yaml
# agent_types.yaml
household:
  prompt_template: |
    You are Agent {agent_id}.
    Current state: {state}
    
    Available options:
    {options}
    
    Decide: ...
```

### 自定義 Validation

```yaml
# agent_types.yaml
household:
  custom_validators:
    - module: "my_validators"
      class: "RiskAwareValidator"
```

---

**實現目標**：
- ✅ 兩個文件即可開始
- ✅ 完全客製化 skills 和 rules
- ✅ 框架處理所有基礎設施
- ✅ 研究者專注於研究邏輯
