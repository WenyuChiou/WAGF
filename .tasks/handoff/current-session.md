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

| 優先級 | 檔案 | 修改 |
|--------|------|------|
| 🔴 重度 | `llm_utils.py` | Mock LLM 通用化 |
| 🔴 重度 | `model_adapter.py` | audit 字段從配置讀取 |
| 🟡 中度 | `experiment.py` | agent_type 必須參數 |
| 🟡 中度 | `data_loader.py` | agent_type 必須參數 |
| 🟡 中度 | `async_adapter.py` | agent_type 必須參數 |
| 🟢 輕度 | 多個檔案 | 文檔/註釋通用化 |

**Git Commits**:
- `844a1c5` - refactor: Remove domain-specific hardcoding from core modules
- `1907d16` - refactor: Remove 'household' default values from core modules
- `d5f4e1b` - docs: Remove domain-specific examples from code comments

---

## 假設與前提

- 使用 Ollama 預設行為可提升多樣性（與原版一致）
- 核心模組不得出現實驗特定術語

---

## 待辦事項

### 優先級高
- [ ] 運行完整實驗測試（非 mock）確認多樣性恢復
- [ ] 測試 multi_agent 範例是否正常

### 優先級中
- [ ] 更新框架 README 說明新的配置方式
- [ ] 建立非洪水實驗的範例配置模板

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

| 檔案 | 用途 |
|------|------|
| `broker/utils/llm_utils.py` | LLM_CONFIG 全域配置 |
| `examples/single_agent/agent_types.yaml` | 實驗配置範例 |
| `examples/single_agent/run_flood.py` | 主要實驗腳本 |

---

## 測試命令

```bash
# 快速 Mock 測試
cd examples/single_agent
python run_flood.py --model mock --agents 3 --years 2

# 完整 LLM 測試
python run_flood.py --model llama3.2:3b --agents 10 --years 5
```

---

## 產物 (artifacts)

- `.tasks/artifacts/claude-code/task-001-20250115-summary.md`

---

## 回寫確認（總結前必填）

- [x] 已更新 `.tasks/handoff/current-session.md`
- [x] 已更新 `.tasks/registry.json`
- [x] 已更新 `.tasks/artifacts/`（若有產物）
