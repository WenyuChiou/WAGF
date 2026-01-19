# Task-019: MA System Configuration Enhancement

## Last Updated
2026-01-18T18:30:00Z

## Metadata

| Field | Value |
|:------|:------|
| **ID** | Task-019 |
| **Title** | MA System Configuration Enhancement |
| **Status** | `planned` |
| **Type** | configuration |
| **Priority** | High |
| **Owner** | Claude Code |
| **Dependencies** | Task-015, Task-018 |

---

## Overview

增強 MA 系統配置，包含：
1. 政府/保險 Response Format 修正
2. 記憶與檢索模組配置
3. 社交記憶 (Gossip) 配置
4. 財務限制實現

---

## Subtasks

### 019-A: Response Format 修正 (Codex)

**狀態**: `pending`
**分配**: Codex
**優先級**: High

**目標**: 修正 `ma_agent_types.yaml` 中的 Government/Insurance response format，列出所有選項而非只給 "1"

**修改檔案**: `examples/multi_agent/ma_agent_types.yaml`

**修改內容**:

#### nj_government (Line ~185-219)
```yaml
    ### POLICY OPTIONS
    Choose ONE of the following:
    - "increase_subsidy": Raise elevation subsidy by 5% to encourage more adaptation
    - "decrease_subsidy": Reduce subsidy by 5% to conserve budget
    - "maintain_subsidy": Keep current subsidy rate unchanged

    ### RESPONSE FORMAT
    Respond ONLY with a valid JSON object:
    {
      "decision": "increase_subsidy | decrease_subsidy | maintain_subsidy",
      "reasoning": "Your policy rationale here"
    }
```

#### fema_nfip (Line ~300-334)
```yaml
    ### POLICY OPTIONS
    Choose ONE of the following:
    - "raise_premium": Increase rates by 0.5% per Risk Rating 2.0 guidelines
    - "lower_premium": Reduce rates by 0.5% to improve affordability
    - "maintain_premium": Keep current premium structure

    ### RESPONSE FORMAT
    Respond ONLY with a valid JSON object:
    {
      "decision": "raise_premium | lower_premium | maintain_premium",
      "reasoning": "Your policy rationale here"
    }
```

**驗收標準**:
- [ ] nj_government prompt 列出 3 個選項名稱
- [ ] fema_nfip prompt 列出 3 個選項名稱
- [ ] Response format 使用選項名稱而非數字

---

### 019-B: Memory Config 區塊 (Codex)

**狀態**: `pending`
**分配**: Codex
**優先級**: High

**目標**: 在 `ma_agent_types.yaml` 末尾新增 memory_config 區塊

**修改檔案**: `examples/multi_agent/ma_agent_types.yaml`

**新增內容** (在 metadata 之前):
```yaml
# =============================================================================
# MEMORY CONFIGURATION
# =============================================================================
memory_config:
  household_owner:
    engine: "humancentric"
    window_size: 3
    top_k_significant: 2
    consolidation_prob: 0.7
    decay_rate: 0.1
  household_renter:
    engine: "humancentric"
    window_size: 3
    top_k_significant: 2
  government:
    engine: "window"
    window_size: 5
  insurance:
    engine: "window"
    window_size: 5

retrieval_config:
  household:
    strategy: "importance_weighted"
    emotional_weights:
      critical: 1.0
      major: 0.9
      positive: 0.8
      observation: 0.4
    source_weights:
      personal: 1.0
      neighbor: 0.7
      community: 0.5
  institutional:
    strategy: "recency"
    top_k: 5

social_memory_config:
  gossip_enabled: true
  max_gossip: 2
  gossip_categories:
    - "decision_reasoning"
    - "flood_experience"
    - "adaptation_outcome"
  gossip_importance_threshold: 0.5
```

**驗收標準**:
- [ ] memory_config 區塊存在
- [ ] retrieval_config 區塊存在
- [ ] social_memory_config 區塊存在
- [ ] YAML 語法正確 (`python -c "import yaml; yaml.safe_load(open('ma_agent_types.yaml'))"`)

---

### 019-C: Financial Constraints 實現 (Codex)

**狀態**: `pending`
**分配**: Codex
**優先級**: High

**目標**: 實現基於收入的財務限制驗證

#### 修改檔案 1: `validators/agent_validator.py`

**新增函數** (在 class 內):
```python
def validate_affordability(self, agent_id: str, decision: str, context: Dict) -> Tuple[bool, Optional[str]]:
    """
    Tier 0: Financial affordability check.

    Rules:
    - elevate_house: cost after subsidy <= 3x annual income
    - buy_insurance: annual premium <= 5% of income
    """
    agent_state = context.get('agent_state', {})
    fixed = agent_state.get('fixed_attributes', {})
    env = context.get('environment', {})

    income = fixed.get('income', 50000)
    subsidy_rate = env.get('subsidy_rate', 0.5)
    premium_rate = env.get('premium_rate', 0.02)
    property_value = fixed.get('property_value', 300000)

    if decision == "elevate_house":
        cost = 150_000 * (1 - subsidy_rate)
        if cost > income * 3.0:
            return False, f"AFFORDABILITY: Cannot afford elevation (${cost:,.0f} > 3x income ${income*3:,.0f})"

    if decision in ["buy_insurance", "buy_contents_insurance"]:
        premium = premium_rate * property_value
        if premium > income * 0.05:
            return False, f"AFFORDABILITY: Premium ${premium:,.0f} exceeds 5% of income ${income*0.05:,.0f}"

    return True, None
```

**修改 validate 方法**: 在 Tier 1 之前調用 `validate_affordability`

#### 修改檔案 2: `examples/multi_agent/run_unified_experiment.py`

**新增 CLI 參數** (Line ~356):
```python
parser.add_argument("--enable-financial-constraints", action="store_true",
                    help="Enable income-based affordability checks")
```

**修改 context builder** (Line ~476-491): 傳入 financial_constraints flag

**驗收標準**:
- [ ] `validate_affordability` 函數存在
- [ ] `--enable-financial-constraints` 參數可用
- [ ] 低收入 agent 選擇 elevate_house 被 block
- [ ] 測試: `python -c "from validators.agent_validator import AgentValidator; print('OK')"`

---

### 019-D: 資料清理 (Codex)

**狀態**: `pending`
**分配**: Codex
**優先級**: Medium

**目標**: 清理舊測試資料

**指令**:
```bash
cd examples/multi_agent

# 1. 備份現有資料
mkdir -p results_unified/archive_20260118
cp -r results_unified/llama3_2_3b_strict results_unified/archive_20260118/

# 2. 列出所有目錄
ls -la results_unified/

# 3. 刪除舊資料 (如有)
# rm -rf results_unified/mock_*
# rm -rf results_unified/llama3_1_*
```

**驗收標準**:
- [ ] archive_20260118 備份存在
- [ ] 無重複/過時的 results 目錄

---

## 執行指令總覽 (給 Codex)

```bash
# ===== 019-A: Response Format =====
# 編輯 examples/multi_agent/ma_agent_types.yaml
# 修改 nj_government 和 fema_nfip 的 prompt_template

# ===== 019-B: Memory Config =====
# 在 ma_agent_types.yaml 末尾 (metadata 之前) 新增 memory_config 區塊

# ===== 019-C: Financial Constraints =====
# 1. 編輯 validators/agent_validator.py - 新增 validate_affordability
# 2. 編輯 examples/multi_agent/run_unified_experiment.py - 新增 --enable-financial-constraints

# ===== 019-D: 資料清理 =====
cd examples/multi_agent
mkdir -p results_unified/archive_20260118
cp -r results_unified/llama3_2_3b_strict results_unified/archive_20260118/

# ===== 驗證語法 =====
cd examples/multi_agent
python -c "import yaml; yaml.safe_load(open('ma_agent_types.yaml')); print('YAML OK')"
python -c "from validators.agent_validator import AgentValidator; print('Validator OK')"
```

---

## 回報格式

完成後請回報：
```
REPORT
agent: Codex
task_id: task-019-X
scope: <modified files>
status: done|partial|blocked
changes: <list of changes>
issues: <any problems>
next: <next subtask>
```

---

## Claude Code 檢核項目

| 檢核項 | 標準 | 狀態 |
|:-------|:-----|:-----|
| YAML 語法 | 無 parse error | pending |
| Response Format | 列出所有選項名稱 | pending |
| Memory Config | 3 個區塊存在 | pending |
| Financial Validator | 函數可導入 | pending |
| 資料備份 | archive 存在 | pending |
