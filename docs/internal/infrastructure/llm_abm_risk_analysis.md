# LLM-ABM 問題逐一驗證：框架緩解能力分析

## Overview

本文件逐一檢驗 12 個 LLM-ABM 問題，並說明：
1. **框架如何解決** (或未解決)
2. **單 Agent Case** (v1/v2 experiments)
3. **多 Agent Case** (exp3_multi_agent)

### Temperature 策略

> **保持 Temperature > 0** 以保留 LLM 的核心價值：行為異質性 (behavioral heterogeneity)

```python
LLM_CONFIG = {
    "temperature": 0.7,   # 保留變異性
    "seed": 42,           # 可控的隨機性
    "log_seed": True      # 記錄用於重現
}
```

**理由：**
- Temperature = 0 → 所有 agent 行為相同 → 失去 LLM 意義
- Temperature > 0 → 行為異質性 → 需要多次運行取統計結果

---

## ① Environment / Tools → Observation

### A. Hallucination of Knowledge (Over-knowledge)

| Aspect | Analysis |
|--------|----------|
| **問題** | Agent 可能「知道」超出 observation 範圍的資訊 |
| **框架解決** | ⚠️ Partial |

**單 Agent Case (v1/v2):**
```python
# 單 agent 只看到自己的 state
prompt = f"""
Your house is {elevated_status}.
You have ${damage:,.0f} cumulative damage.
"""
# 不會知道其他 agent 的資訊（因為沒有其他 agent）
```
✅ **單 Agent 無此問題** - 因為只有一個 agent

**多 Agent Case (exp3):**
```python
# exp3/prompts.py - 嚴格限制可見資訊
HOUSEHOLD_PROMPT = """
=== YOUR CURRENT SITUATION ===
{elevation_status}        # 只有自己
{insurance_status}        # 只有自己
{damage_history}          # 只有自己的歷史
"""
# 不提供: global_damage, neighbor_decisions, etc.
```
⚠️ **多 Agent 風險存在** - LLM 可能從預訓練知識推測他人行為

**未來改進：**
```python
class VA_KnowledgeBoundary(ValidationRule):
    """驗證 LLM 未使用 prompt 外知識"""
    forbidden_phrases = [
        "other residents", "neighbors decided", "statistics show",
        "most people", "on average", "typically"
    ]
```

---

### B. Context Contamination

| Aspect | Analysis |
|--------|----------|
| **問題** | Tool output + Prompt + History 混淆 |
| **框架解決** | ✅ Addressed |

**單 Agent Case:**
```python
# v2_skill_governed - 清楚區分
PROMPT = """
=== MEMORY ===          # 過去經驗
{memory}

=== CURRENT STATE ===   # Observation
{state}

=== TASK ===            # 指令
Choose an action...
"""
```

**多 Agent Case:**
```python
# exp3/prompts.py - 明確分隔 5 個區域
HOUSEHOLD_PROMPT = """
=== CONSTRUCT DEFINITIONS ===    # 系統說明 (不變)
...
=== YOUR CURRENT SITUATION ===   # Observation (State)
...
=== YOUR MEMORY ===              # Observation (Memory)
...
=== THIS YEAR'S CONDITIONS ===   # Environment (當年)
...
=== YOUR TASK ===                # 指令
...
=== OUTPUT FORMAT ===            # 輸出格式
...
"""
```

✅ **兩者都有結構化分隔**

---

## ② Observation → LLM Reasoning

### C. Context Distraction / Confusion

| Aspect | Analysis |
|--------|----------|
| **問題** | 重要事件被擠出 context window / Retrieval 語義偏差 |
| **框架解決** | ⚠️ Partial |

**單 Agent Case:**
```python
# broker/memory.py - SimpleMemory
class SimpleMemory:
    window = 5  # 只保留最近 5 個事件
    historical_recall = 1  # 隨機回顧 1 個歷史事件
```
⚠️ **風險**: 重要但較舊的事件可能被遺忘

**多 Agent Case:**
```python
# broker/memory.py - CognitiveMemory
class CognitiveMemory:
    working_capacity = 5      # 短期記憶
    episodic_memory = []      # 長期記憶 (無上限)
    
    def retrieve(self, top_k, current_year):
        # Scoring: recency * importance
        # 高重要性事件不會被遺忘
```
✅ **多 Agent 有更好的記憶機制** - Episodic memory 保留重要事件

**改進空間：**
```python
# 因果相關性 retrieval
def retrieve_for_decision(self, decision_type: str):
    """
    當考慮 buy_insurance → 優先 retrieval 過去的洪水損失
    當考慮 elevate → 優先 retrieval 補助相關記憶
    """
```

---

### D. Implicit Memory Drift

| Aspect | Analysis |
|--------|----------|
| **問題** | 記憶存在於 embedding/prompt，非系統 state |
| **框架解決** | ✅ Addressed |

**單 Agent Case:**
```python
# simulation/engine.py
class Agent:
    memory: SimpleMemory
    # memory 是 agent 的屬性，持久化於 state
```

**多 Agent Case:**
```python
# exp3/agents/household.py
class HouseholdAgent:
    state: HouseholdAgentState
    memory: CognitiveMemory  # 明確屬於 agent state
    
# Memory 是 dataclass，可序列化
@dataclass
class MemoryItem:
    content: str
    importance: float
    year: int
    timestamp: datetime
```

✅ **Memory 是 State 的一部分，不是 LLM 的隱式記憶**

**Audit 記錄:**
```python
# audit_writer.py - 記錄 memory 快照
trace = {
    "agent_id": ...,
    "memory_snapshot": memory.to_list(current_year),  # 可重現
    ...
}
```

---

## ③ LLM Reasoning (Core Black Box)

### E. Hallucination (Fabricated Facts)

| Aspect | Analysis |
|--------|----------|
| **問題** | LLM 編造未發生的損失、不存在的條件 |
| **框架解決** | ⚠️ Partial |

**單 Agent Case:**
```python
# 無專門驗證機制
# LLM 可能說「我去年損失 $100,000」但實際是 $50,000
```

**多 Agent Case:**
```python
# validators.py - R8 PA Consistency
class R8_PAConsistency(ValidationRule):
    """PA assessment 必須與實際 state 一致"""
    def check(self, output, state):
        actual_pa = compute_pa(state)
        if output.pa_level != actual_pa:
            return f"PA={output.pa_level} 與實際不符"
```

⚠️ **目前只驗證 PA，未驗證 TP/CP/SP/SC 的 explanation**

**改進方向：**
```python
class VE_FactConsistency(ValidationRule):
    """驗證 explanation 內容與 state 一致"""
    def check(self, output, state):
        # 如果 explanation 提到 "$X damage"
        # 驗證 X 與 state.cumulative_damage 一致
```

---

### F. Inconsistency (Reasoning-Action Mismatch) ✅

| Aspect | Analysis |
|--------|----------|
| **問題** | LLM 推理與行為不一致 |
| **框架解決** | ✅ Addressed |

**單 Agent Case:**
```python
# 無專門機制，但輸出格式要求 threat + coping appraisal
```

**多 Agent Case:**
```python
# validators.py - 多條 consistency rules
R1: HIGH TP + HIGH CP → 不應 do_nothing (warning)
R2: LOW TP + 採取行動 → 預防性行為 (acceptable, log)
R5: LOW CP + 高成本行動 → 負擔能力疑慮 (warning)
R7: FULL PA + relocate → 可能過度反應 (warning)
```

✅ **多 Agent Case 有完整的 reasoning-action consistency 檢查**

---

### G. Non-stationary Stochasticity

| Aspect | Analysis |
|--------|----------|
| **問題** | 同條件不同 sampling → 不同行為 |
| **框架解決** | ⚠️ Partial (by design) |

**策略：保留 Temperature，用統計方法處理**

```python
# 建議配置
LLM_CONFIG = {
    "temperature": 0.7,    # 保留異質性
    "seed": 42,            # 可控隨機
    "n_runs": 10           # 多次運行取統計
}

# Audit 記錄 sampling 參數
trace = {
    "llm_config": {
        "model": "llama3.2:3b",
        "temperature": 0.7,
        "seed": 42,
        "run_id": 3
    },
    ...
}
```

**分析方法：**
```python
# 多次運行後統計
results = [run_simulation(seed=i) for i in range(10)]
mean_adoption = np.mean([r.adoption_rate for r in results])
std_adoption = np.std([r.adoption_rate for r in results])
# 報告: "Adoption rate: 45% ± 8% (n=10)"
```

---

## ④ LLM Reasoning → Action

### H. Action Schema Ambiguity ✅

| Aspect | Analysis |
|--------|----------|
| **問題** | Action 定義不完整或模糊 |
| **框架解決** | ✅ Addressed |

**單 Agent Case:**
```python
# simulation/engine.py
DECISION_MAP = {
    1: "buy_insurance",
    2: "elevate_house",
    3: "relocate",
    4: "do_nothing"
}
```

**多 Agent Case:**
```yaml
# skill_registry.yaml - 完整定義
household_owner_skills:
  - skill_id: elevate_house
    description: "Elevate house structure..."
    eligible_agent_types: ["household_owner"]
    preconditions: ["not elevated"]
    institutional_constraints:
      once_only: true
      subsidy_eligible: true
    allowed_state_changes: [elevated]
```

✅ **多 Agent 有更完整的 action schema**

---

### I. Constraint Violation ✅

| Aspect | Analysis |
|--------|----------|
| **問題** | 忽略 budget/once-only/eligibility |
| **框架解決** | ✅ Addressed |

**單 Agent Case:**
```python
# 在 execute_decision 時檢查
if decision == "elevate" and agent.elevated:
    return  # 忽略重複執行
```

**多 Agent Case:**
```python
# validators.py - 明確錯誤報告
R3: 已 elevated → 不能再 elevate (ERROR)
R4: Renter → 不能 elevate (ERROR)
R6: 已 relocated → 不能行動 (ERROR)
R9: Renter 只能 insurance/relocate/nothing (ERROR)

# 錯誤會被記錄到 audit
output.validation_errors = ["R4: Renters cannot elevate..."]
```

✅ **多 Agent 有完整的 constraint validation 並記錄**

---

## ⑤ Action → Environment Change

### J. Untraceable State Changes ✅

| Aspect | Analysis |
|--------|----------|
| **問題** | 無法追蹤 reasoning → action → state |
| **框架解決** | ✅ Addressed |

**單 Agent Case:**
```python
# 有 audit log，但較簡單
audit_log = {
    "step": step,
    "decision": decision,
    "state_after": agent.get_state()
}
```

**多 Agent Case:**
```python
# audit_writer.py - 完整 trace
trace = {
    "timestamp": ...,
    "year": output.year,
    "agent_id": output.agent_id,
    
    # STATE (before decision)
    "state": {
        "elevated": state.get("elevated"),
        "has_insurance": state.get("has_insurance"),
        "cumulative_damage": state.get("cumulative_damage")
    },
    
    # REASONING (LLM output)
    "constructs": {
        "TP": {"level": ..., "explanation": ...},
        "CP": {"level": ..., "explanation": ...},
        ...
    },
    
    # ACTION
    "decision_number": output.decision_number,
    "decision_skill": output.decision_skill,
    "justification": output.justification,
    
    # VALIDATION
    "validated": output.validated,
    "validation_errors": output.validation_errors,
    
    # CONTEXT
    "context": {...}
}
```

✅ **完整的 state → reasoning → action 因果鏈記錄**

---

## ⑥ 整個 Loop (系統性問題)

### K. Lack of Reproducibility

| Aspect | Analysis |
|--------|----------|
| **問題** | 結果不可重現 |
| **框架解決** | ⚠️ Partial |

**策略：控制隨機性 + 多運行統計**

```python
# 目前
SEED = 42  # Random seed

# 建議完整配置
REPRODUCIBILITY_CONFIG = {
    "random_seed": 42,
    "data_loader_seed": 42,
    "llm_seed": 42,           # Ollama 支援
    "llm_temperature": 0.7,   # 保留異質性
    "llm_model_hash": "abc123",  # 模型版本
    "retrieval_order": "deterministic",
    "n_runs": 10              # 多運行取統計
}
```

**單 Agent vs 多 Agent:**
- **單 Agent**: N 個獨立運行 → 統計分析
- **多 Agent**: N 個 simulation runs × M agents → Agent 間互動增加變異

---

### L. Lack of Traceability ✅

| Aspect | Analysis |
|--------|----------|
| **問題** | 無法建立因果鏈 |
| **框架解決** | ✅ Addressed |

**單 Agent Case:**
```
audit_trace.jsonl
├── step 1: state → decision → outcome
├── step 2: state → decision → outcome
└── ...
```

**多 Agent Case:**
```
results/
├── household_audit.jsonl      # 每個 household 的每年決策
│   ├── H001, Year 1: state → constructs → decision → validation
│   ├── H001, Year 2: ...
│   ├── H002, Year 1: ...
│   └── ...
├── institutional_audit.jsonl  # Insurance/Government
└── audit_summary.json         # 統計彙總
```

✅ **完整可審計的決策軌跡**

---

## 總結對照表

| ID | Problem | Single Agent | Multi Agent |
|----|---------|--------------|-------------|
| A | Over-knowledge | ✅ No issue | ⚠️ Risk exists |
| B | Context Contamination | ✅ Structured | ✅ Structured |
| C | Context Distraction | ⚠️ SimpleMemory | ✅ CognitiveMemory |
| D | Memory Drift | ✅ State-based | ✅ State-based |
| E | Fabricated Facts | ⚠️ No validation | ⚠️ R8 only |
| F | Reasoning-Action Mismatch | ⚠️ Basic | ✅ R1,R5,R7 |
| G | Stochasticity | ⚠️ Single run | ⚠️ N-runs needed |
| H | Action Schema | ✅ DECISION_MAP | ✅ Skill Registry |
| I | Constraint Violation | ⚠️ Implicit | ✅ Validators R3,R4,R6,R9 |
| J | Untraceable State | ⚠️ Basic log | ✅ Full trace |
| K | Reproducibility | ⚠️ Seed only | ⚠️ Multi-run stats |
| L | Traceability | ✅ Basic | ✅ Full audit |

### 結論

**多 Agent 框架 (exp3) 在以下方面顯著優於單 Agent:**
1. Reasoning-Action Consistency (R1, R5, R7 rules)
2. Constraint Validation (R3, R4, R6, R9 rules)  
3. Memory System (CognitiveMemory vs SimpleMemory)
4. Audit Trail (Full JSONL traces)
5. Action Schema (Skill Registry)

**仍需改進的領域:**
1. Knowledge Boundary Validation (A)
2. Fact Consistency in Explanations (E)
3. Multi-run Statistical Analysis (G, K)
