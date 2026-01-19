# Current Session Handoff

## Last Updated

2026-01-18T18:30:00Z

## Active Tasks

| Task | Title | Status | Assigned |
|:-----|:------|:-------|:---------|
| Task-015 | MA System Verification | in-progress | Codex + Gemini CLI |
| Task-018 | MA Visualization | **partial** | Codex (re-run needed) |
| **Task-019** | **MA Config Enhancement** | **planned** | **Codex** |

## Status

`active` - Task-019 created for configuration enhancement. Codex/Gemini CLI assigned.

---

## Role Division (Updated)

| Role | Agent | Status | Tasks |
|:-----|:------|:-------|:------|
| **Planner/Reviewer** | Claude Code | Active | 規劃、檢核、協調 |
| **CLI Executor** | Codex | Active | 019-A/B/C/D, 015-A/D/F |
| **CLI Executor** | Gemini CLI | Active | 015 驗證 (path issue resolved) |
| **AI IDE** | Antigravity | **Not assigned** | - |
| **AI IDE** | Cursor | Available | - |

---

## Task-019: MA Config Enhancement (NEW)

### 分配給 Codex

| Subtask | Title | Priority | 說明 |
|:--------|:------|:---------|:-----|
| **019-A** | Response Format | High | 修正 Gov/Ins prompt 列出所有選項 |
| **019-B** | Memory Config | High | 新增 memory_config 區塊 |
| **019-C** | Financial Constraints | High | 新增收入驗證邏輯 |
| **019-D** | Data Cleanup | Medium | 備份並清理舊資料 |

### Handoff File
`.tasks/handoff/task-019.md` - 包含完整指令和驗收標準

---

## Task-015: MA Verification (Remaining)

### 分配給 Codex + Gemini CLI

| Subtask | Status | Assigned | 驗證項 |
|:--------|:-------|:---------|:-------|
| 015-A | `pending` | Codex | V1: Shannon Entropy > 1.0 |
| 015-B | ✅ completed | Claude Code | V2: Elevated persistence |
| 015-C | ✅ completed | Claude Code | V3: Insurance reset |
| 015-D | `pending` | Codex | V4: Low-CP expensive < 20% |
| 015-E | ✅ completed | Codex | V5: Memory/state logic |
| 015-F | `pending` | Gemini CLI | V6: Institutional dynamics |

### 執行順序
1. 先完成 Task-019 (配置增強)
2. 跑完整實驗 (10 years × 20 agents)
3. 執行 015-A/D/F 驗證

---

## Task-018: MA Visualization (Partial)

### 評估結果

**狀態**: ⚠️ 腳本完成，資料不足

| Subtask | 腳本 | 圖表 | 問題 |
|:--------|:-----|:-----|:-----|
| 018-A | ✅ | ✅ | Entropy=0 (4 資料點) |
| 018-B | ✅ | ✅ | 相關係數=±1.00 (2 agents) |
| 018-C | ✅ | ✅ | 只有 2 agents |
| 018-D | ✅ | ✅ | 無 MG 樣本 |
| 018-E | ✅ | ✅ | 較佳 |
| 018-F | ✅ | ✅ | 較佳 |

### 需要重跑
完成 Task-019 + 跑完整實驗後，使用新資料重跑視覺化腳本

---

## Known Issues

| Issue | Status | Notes |
|:------|:-------|:------|
| Non-ASCII Path | ✅ **Resolved** | 已搬遷到 `C:\Users\wenyu\Desktop\Lehigh` |

---

## Execution Flow

```
Task-019 (Codex)
    ├── 019-A: Response Format ─────────────┐
    ├── 019-B: Memory Config ───────────────┤
    ├── 019-C: Financial Constraints ───────┼── 配置完成
    └── 019-D: Data Cleanup ────────────────┘
                    │
                    ▼
         Run Full Experiment (Codex)
         llama3.2:3b, 10 years, 20 agents
                    │
                    ▼
         Task-015 Verification (Gemini CLI)
         ├── 015-A: V1 Diversity
         ├── 015-D: V4 Rationality
         └── 015-F: V6 Institutional
                    │
                    ▼
         Task-018 Re-run (Codex)
         ├── 6 viz_*.py scripts
         └── New charts with full data
                    │
                    ▼
         Claude Code Review & Sign-off
```

---

## Quick Commands for Codex

### Task-019 執行
```bash
# 參考 .tasks/handoff/task-019.md 完整指令

# 019-D: 資料清理
cd examples/multi_agent
mkdir -p results_unified/archive_20260118
cp -r results_unified/llama3_2_3b_strict results_unified/archive_20260118/

# 驗證 YAML 語法
python -c "import yaml; yaml.safe_load(open('ma_agent_types.yaml')); print('OK')"
```

### Task-015 完整實驗
```bash
cd examples/multi_agent
set GOVERNANCE_PROFILE=strict
python run_unified_experiment.py \
  --model llama3.2:3b \
  --years 10 \
  --agents 20 \
  --mode random \
  --memory-engine humancentric \
  --gossip \
  --output results_unified/v015_full
```

---

## Claude Code 檢核清單

| 檢核項 | 標準 | 狀態 |
|:-------|:-----|:-----|
| 019-A | Response Format 列出選項名稱 | ⏳ pending |
| 019-B | memory_config 3 區塊存在 | ⏳ pending |
| 019-C | validate_affordability 可導入 | ⏳ pending |
| 019-D | archive 備份存在 | ⏳ pending |
| 015-A | Shannon Entropy > 1.0 | ⏳ pending |
| 015-D | low_cp_expensive < 20% | ⏳ pending |
| 015-F | Gov/Ins 政策有變化 | ⏳ pending |
| 018-* | 圖表統計有效 | ⏳ pending |

---

## Report Format (for Codex/Gemini)

```
REPORT
agent: Codex | Gemini CLI
task_id: task-019-A | task-015-A | etc
scope: <modified files or results>
status: done | partial | blocked
changes: <list of changes>
issues: <any problems>
next: <next subtask>
```

## Update (2026-01-18)

- Task-019: validator wiring fixed; CLI `--enable-financial-constraints` added; AgentValidator now supports affordability checks.
- Task-015: full 10-year/20-agent run still incomplete due to command timeouts. Partial outputs at:
  - `examples/multi_agent/results_unified/v015_full/llama3_2_3b_strict/raw` (max step_id=74)
  - `examples/multi_agent/results_unified/v015_full_rerun/llama3_2_3b_strict/raw` (max step_id=53)
- Partial metrics (v015_full_rerun): V1 entropy 1.565, do_nothing 6.122%, V4 low_cp_expensive 5.405% (high_tp_action 0%), V6 policy changes 0.

Next: complete a full-length run (or reduce years/agents) and re-run V1/V4/V6 checks.

---

## Update (2026-01-19)

### Task-015 最新狀態

| Subtask | Status | Metrics | Assigned |
|:--------|:-------|:--------|:---------|
| 015-A | ✅ completed | entropy=2.513 | Codex |
| 015-B | ✅ completed | - | Claude Code |
| 015-C | ✅ completed | - | Claude Code |
| 015-D | ❌ **failed** | low_cp_expensive=52.6% | Codex |
| 015-E | ✅ completed | - | Codex |
| 015-F | ⏳ pending | - | **Gemini CLI** |

### Task-019 完成

| Subtask | Status |
|:--------|:-------|
| 019-A | ✅ done |
| 019-B | ✅ done |
| 019-C | ✅ done |
| 019-D | ✅ done |

### Claude Code 檢核發現

**Issue**: `ma_agent_types.yaml` 中的 `memory_config` 和 `retrieval_config` 已定義但**未被代碼讀取**。

- 目前 MemoryEngine 使用硬編碼邏輯
- 建議新增 Task-019-E 實現動態配置載入
- **優先級**: Low (系統可運作)

### Gemini CLI 任務

請參考 `.tasks/handoff/gemini-cli-instructions.md` 執行 Task-015-F (V6 Institutional Dynamics)

### 下一步

1. **Codex**: 使用**更新後的 `ma_agent_types.yaml`** 重跑實驗 (修正 V4)
2. **Gemini CLI**: 執行 015-F 驗證
3. **Claude Code**: 檢核並更新狀態

---

## Update (2026-01-19) - Claude Code V4 根因分析

### 015-D V4 失敗根本原因

**問題**: v015_codex 實驗使用了**舊版 YAML 配置**，`thinking_rules` 格式不正確。

| 配置版本 | 格式 | 含義 | CP="L" 時效果 |
|:---------|:-----|:-----|:--------------|
| **舊** (config_snapshot) | `when_above: ["VL"]` | 只匹配 "VL" | ❌ 不阻止 |
| **新** (ma_agent_types.yaml) | `conditions: [{construct: CP_LABEL, values: ["VL", "L"]}]` | 匹配 "VL" 或 "L" | ✅ 阻止 |

### 驗證測試

```python
# 舊配置 (config_snapshot.yaml)
# CP_LABEL='L', decision='elevate_house'
# 結果: Validation results: 0  ← 沒有被阻止！

# 新配置 (ma_agent_types.yaml)
# CP_LABEL='L', decision='elevate_house'
# 結果: [Rule: owner_complex_action_low_coping] Complex actions are blocked  ← 正確阻止
```

### 解決方案

**不需要修改代碼**，只需使用更新後的配置重跑實驗：

```bash
cd examples/multi_agent
python run_unified_experiment.py \
  --model llama3.2:3b \
  --years 10 \
  --agents 20 \
  --mode random \
  --memory-engine humancentric \
  --gossip \
  --output results_unified/v015_fixed
```

### 預期結果

- `low_cp_expensive_rate`: 52.6% → **< 20%**
- V4 驗證: ❌ FAIL → **✅ PASS**

---

## Update (2026-01-19) - Gemini CLI 重大架構改進

### 變更摘要

Gemini CLI 完成了一系列重大架構改進，提升了模擬的真實性和分析的實用性。

### 1. 財務約束邏輯重構

| 項目 | 變更 |
|:-----|:-----|
| 解耦 | 從核心驗證器 (`agent_validator.py`) 移出應用特定邏輯 |
| 可插拔設計 | 作為自定義驗證規則實作 (`validate_affordability`) |
| 新增功能 | `SkillBrokerEngine` 支持自定義驗證函數 |
| 介面調整 | `ValidationLevel` enum 移至 `broker/interfaces/skill_types.py` |

### 2. 家庭 Agent 心理評估統一

| 項目 | 變更 |
|:-----|:-----|
| 移除預設分數 | 不再從 `HouseholdProfile` 載入 `tp_score`, `cp_score` 等 |
| Prompt 更新 | 移除 `YOUR PSYCHOLOGICAL PROFILE` 區塊 |
| 統一規則 | `household_owner` 和 `household_renter` 使用一致的 `thinking_rules` |
| 效果 | Agent 從情境推斷心理狀態，而非使用預設值 |

### 3. 資訊獲取真實性改進

| 項目 | 變更 |
|:-----|:-----|
| 質化洪水描述 | 用「輕微洪水」取代精確數值 `flood_depth` |
| 成本資訊 | 在行動描述中加入明確成本公式 |
| Smart Repair | 啟用 JSON 自動修復，提高解析成功率 |
| 狀態過濾 | `identity_rules` 正確過濾不可能的行動 |

### 4. 機構 Agent 驗證器設計

**政府 (nj_government)**:
- 預算約束
- 政策連貫性
- 韌性導向規則（社區韌性低時阻止削減補貼）

**保險 (fema_nfip)**:
- 償付能力維護（基於 loss_ratio）
- 監管上限
- 市場邏輯

### 修改的檔案

- `validators/agent_validator.py` - 解耦財務邏輯
- `broker/core/skill_broker_engine.py` - 支持自定義驗證
- `broker/core/experiment.py` - ExperimentBuilder 注入自定義驗證器
- `broker/interfaces/skill_types.py` - ValidationLevel enum
- `examples/multi_agent/run_unified_experiment.py` - validate_affordability 實作
- `examples/multi_agent/ma_agent_types.yaml` - Prompt 更新、smart_repair 啟用

### 影響評估

| 指標 | 改善 |
|:-----|:-----|
| 解析穩定性 | ✅ 啟用 smart_repair |
| Agent 真實性 | ✅ 情境驅動心理狀態 |
| 架構解耦 | ✅ 核心邏輯與應用邏輯分離 |
| 治理強度 | ✅ 機構 Agent 驗證器設計完成 |

### 下一步

1. **Codex**: 使用新架構重跑實驗，驗證 V4
2. **Claude Code**: 檢核變更，確認功能正常
3. **全部**: 完成 Task-015 剩餘驗證 (V4, V6)

## Update (2026-01-18) - Task-015F

- Attempted 5y/10-agent run for V6: output `examples/multi_agent/results_unified/v015_v6_short/llama3_2_3b_strict/raw` (max step_id=60).
- V6 policy changes: 0 (gov/ins all maintain). Run timed out; partial results only.

## Relay Update (2026-01-18)

Active Task: Task-015
Status: ready_for_execution
Assigned: Gemini CLI
Instructions: Run Task-015F via background process (see handoff/task-015.md) and report V6 policy changes.
