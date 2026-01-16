# 當前工作階段交接

> **日期**：2025-01-15
> **AI 代理**：Claude Code
> **任務 ID**：task-001
> **類型**：module
> **範圍**：broker/, validators/, examples/
> **Done When**：核心模組無實驗硬編碼；最少一次 mock 測試通過；README 更新
> **Owner / Reviewer**：claude-code / codex

## 已完成任務

### 1. LLM 參數配置修復

**問題**: 框架版 `run_flood.py` 輸出多樣性低於原版 `LLMABMPMT-Final.py`

**根因**:

- 框架明確設置 `temperature=0.8, top_p=0.9, top_k=40`
- 原版不設置這些參數，使用 Ollama 預設值
- 框架使用 `ChatOllama`，原版使用 `OllamaLLM`

**解決方案**:

- 新增 `LLM_CONFIG` 全域配置類別 (`broker/utils/llm_utils.py`)
- 預設不設置 temperature/top_p/top_k（使用 Ollama 預設）
- 改用 `OllamaLLM`（與原版一致）
- 新增 CLI 參數: `--temperature`, `--top-p`, `--top-k`, `--use-chat-api`

### 2. 框架通用性修復

**已修復的污染**:

| 優先級  | 檔案               | 修改                 |
| ------- | ------------------ | -------------------- |
| 🔴 重度 | `llm_utils.py`     | Mock LLM 通用化      |
| 🔴 重度 | `model_adapter.py` | audit 字段從配置讀取 |
| 🟡 中度 | `experiment.py`    | agent_type 必須參數  |
| 🟡 中度 | `data_loader.py`   | agent_type 必須參數  |
| 🟡 中度 | `async_adapter.py` | agent_type 必須參數  |
| 🟢 輕度 | 多個檔案           | 文檔/註釋通用化      |

**Git Commits**:

- `844a1c5` - refactor: Remove domain-specific hardcoding from core modules
- `1907d16` - refactor: Remove 'household' default values from core modules
- `d5f4e1b` - docs: Remove domain-specific examples from code comments

### 3. run_flood parity 對齊（部分完成）

**問題**: 框架與舊版在隨機性/洪水機制與記憶窗口行為不一致

**調整**:

- 補上隨機種子初始化，提升可重現性
- 記憶取樣 top_k 改用 CLI 的 `--window-size`
- 新增 `--flood-mode` 以支援固定年表/機率式洪水
- 記憶順序調整為 flood → grant → neighbor → recall
- 過濾「Decided to: ...」記憶以貼齊原版

**影響檔案**:

- `examples/single_agent/run_flood.py`

### 4. Gemma window vs humancentric 差異分析

**window**（results_window/gemma3_4b_strict）：

- 年 6–8 狀態仍以 Do Nothing / Only HE 為主，但有小幅變化
- Governance 觸發 5 次（elevation_threat_low），無 parse errors
- 例外規則觸發：Agent_20/Agent_87

**humancentric**（results_humancentric/gemma3_4b_strict）：

- 年 6–8 結構更偏向 Only HE（Do Nothing 減少）
- Governance 0 次，無 parse errors

**路徑調整**：

- 已將 humancentric 的 Gemma 結果移至 `examples/single_agent/results_humancentric/gemma3_4b_strict`

### 5. Gemma Memory Static Behavior Fix (Task 002)

**問題**: Gemma Window 版結果顯示大量 "Do Nothing"，缺乏 Reference 版的動態性。

**根因**:

- `run_flood.py` 每年生成的記憶項目過多（Flood, Grant, Obs_Elev, Obs_Reloc = 4 項）。
- Window Size=5 的情況下，只要兩年就會完全覆蓋舊記憶，導致 "Flood Frequency Increasing" 等初始上下文遺失。
- Reference 版在關鍵年份（無 Grant）僅生成 3 項，僥倖保留了上下文。

**解決方案**:

- 修改 `run_flood.py` 的 `FinalParityHook`。
- 將 `I observe % elevated` 與 `I observe % relocated` 合併為單行記憶。
- 每年記憶消耗減少 1 項，保證 Window=5 能容納前一年的上下文。

**驗證**:

- 執行 `test_merged_memory_v2` (5 agents, 3 years)。
- 確認 Agent 在 Year 2 即使有 Grant 或 Recall，仍能保留 Year 1 的關鍵記憶。
- 目前正在執行全量模擬 (`examples/single_agent/results_window`)。

---

## 假設與前提

- 使用 Ollama 預設行為可提升多樣性（與原版一致）
- 核心模組不得出現實驗特定術語

---

## 待辦事項

### 優先級高

- [x] 運行完整實驗測試（非 mock）確認多樣性恢復（Gemma window=5 fixed）
- [ ] 測試 multi_agent 範例是否正常
- [x] 對齊 run_flood.py 與舊版基準：固定種子、洪水機制一致、memory window 使用 CLI
- [x] 跑 Gemma humancentric window=5 fixed
- [x] 跑 Llama window=5 fixed 與 humancentric window=5 fixed

### 優先級中

- [ ] 更新框架 README 說明新的配置方式
- [ ] 建立非洪水實驗的範例配置模板
- [ ] 檢查提示詞是否含「無洪水 →Do Nothing」偏置並決定是否移除

### 優先級低

- [ ] 考慮添加多政府/多保險支援
- [ ] 考慮動態社交網絡重塑功能

---

## 風險與回滾

**風險**：

- 修改 LLM 呼叫與配置可能影響既有實驗輸出分布
- 強制要求 `agent_type` 參數可能影響舊腳本相容性

**回滾**：

- revert commits `844a1c5`, `1907d16`, `d5f4e1b`

---

## 關鍵檔案參考

| 檔案                                     | 用途                |
| ---------------------------------------- | ------------------- |
| `broker/utils/llm_utils.py`              | LLM_CONFIG 全域配置 |
| `examples/single_agent/agent_types.yaml` | 實驗配置範例        |
| `examples/single_agent/run_flood.py`     | 主要實驗腳本        |

---

## 測試命令

```bash
# 快速 Mock 測試
cd examples/single_agent
python run_flood.py --model mock --agents 3 --years 2

# 完整 LLM 測試
python run_flood.py --model llama3.2:3b --agents 10 --years 5

# Gemma window=5 (fixed flood)
python run_flood.py --model gemma3:4b --agents 100 --years 10 --memory-engine window --window-size 5 --flood-mode fixed --output examples/single_agent/results_window --workers 2

# Gemma humancentric window=5 (fixed flood)
python run_flood.py --model gemma3:4b --agents 100 --years 10 --memory-engine humancentric --window-size 5 --flood-mode fixed --output results_humancentric --workers 2

# Llama window=5 (fixed flood)
python run_flood.py --model llama3.2:3b --agents 100 --years 10 --memory-engine window --window-size 5 --flood-mode fixed --output examples/single_agent/results_window --workers 2

# Llama humancentric window=5 (fixed flood)
python run_flood.py --model llama3.2:3b --agents 100 --years 10 --memory-engine humancentric --window-size 5 --flood-mode fixed --output examples/single_agent/results_humancentric --workers 2
```

---

## 產物 (artifacts)

- `.tasks/artifacts/claude-code/task-001-20250115-summary.md`

---

## 回寫確認（總結前必填）

- [x] 已更新 `.tasks/handoff/current-session.md`
- [x] 已更新 `.tasks/registry.json`
- [x] 已更新 `.tasks/artifacts/`（若有產物）

---

## Update (2026-01-16)
- Added audit trace auto-clear (prevents mixed run_ids in `*_traces.jsonl`).
- Added `yearly_decision` to `simulation_log.csv` (approved skill per agent-year).

## Update (2026-01-16) - Repo cleanup
- Reviewed repo for removable artifacts (outputs, traces, temps, images, csv) and checked `git status` to identify tracked vs untracked files.
- Read `.tasks` key documents (`README.md`, `GUIDE.md`, `registry.json`, `handoff/current-session.md`, `handoff/task-002.md`) to follow collaboration workflow.
- Updated `.gitignore` to ignore common run artifacts:
  - `results_humancentric/`
  - `*_output.txt`, `trace_*.txt`
  - `temp_*.txt`, `temp_*.json`
  - `*.jpg`, `*.csv`
- Corrected handling of `.tasks/`:
  - User requirement: `.tasks` contents must not be deleted.
  - Removed `.tasks/` ignore rule from `.gitignore`.
  - Reverted staged deletions and re-added `.tasks` so files remain present.
- No destructive cleanup executed (no `git clean` run). Pending deletion/cleanup requires explicit confirmation.

---

## Update (2026-01-16)
- Removed untracked single-agent analysis scripts (cleanup before next run).

---

## Update (2026-01-16)
- Recorded changes in `broker/components/audit_writer.py` (auto-clear traces per run).
- Recorded changes in `examples/single_agent/run_flood.py` (yearly_decision in simulation_log).

---

## Update (2026-01-16)
- Rewrote `.tasks/README.md` and `.tasks/GUIDE.md` in clear ASCII with explicit logs purpose and task flow.

---

## Update (2026-01-16) - Cleanup wrap-up
- Deleted root-level image artifacts (`*.jpg`) generated by analysis runs.
- Deleted root-level artifact files:
  - `*.csv`: `agent_initial_profiles.csv`, `flood_adaptation_simulation_log.csv`, `flood_years.csv`
  - `*.txt`: `example_llm_prompts.txt`
- Deleted temporary/trace/output artifacts from repo root:
  - `*_output.txt`, `trace_*.txt`, `temp_*.txt`, `temp_*.json`
- Kept `.tasks/` intact (user requirement: do not delete `.tasks` contents).
- Notes:
  - No broad `git clean` was used; deletions were targeted to artifact patterns.
  - If any untracked analysis scripts remain (e.g. `examples/single_agent/analyze_new_log.py`), decide whether to keep as source, ignore, or delete before the next run.

---

## Update (2026-01-16)
- Removed `agent_initial_profiles.csv` and `example_llm_prompts.txt` per request.

---

## Update (2026-01-16)
- Added `.tasks/skills-mcp.md` to document sharing `.claude/skills` and MCP setup.

---

## Update (2026-01-16)
- Added MCP copy steps to `.tasks/skills-mcp.md`.

---

## Update (2026-01-16)
- Reviewed MA skill visibility: eligibility/identity rules are enforced at validation, options list is not state-filtered.
- Noted MA skill registry YAML format is not loaded by core SkillRegistry.

---

## Update (2026-01-16)
- MA: filter available skills at build time using ma_agent_types actions + identity rules; inject options_text and dynamic_skill_map into context.

---

## Update (2026-01-16)
- Scoped build-time skill filtering to MA only (skip base_type household) to avoid SA prompt changes.

---

## Handoff (2026-01-16)
- MA skill visibility now filtered at build time; SA explicitly excluded.
- Build-time options_text/dynamic_skill_map injected for MA after filtering.
- Latest commits: 148fd9a (MA filter), 5458d1c (limit filter to MA only).
- Outstanding: decide whether to ignore or delete `columns_check.txt` (untracked).
