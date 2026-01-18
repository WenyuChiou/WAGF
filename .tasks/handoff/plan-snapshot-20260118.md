# Plan Snapshot (2026-01-18T17:15:00Z)

## 目的

記錄搬遷前的完整計畫狀態，確保搬遷後能無縫銜接。

---

## 當前任務總覽

| Task ID | Title | Status | Owner |
|:--------|:------|:-------|:------|
| Task-011 | Emergency Bug Fixes | ✅ completed | antigravity |
| Task-012 | Core State Persistence | ✅ completed | Claude Code |
| Task-013 | Memory & Reflection MA Integration | 🔄 in-progress | Claude Code |
| Task-014 | MA State Persistence Alignment | ✅ completed | Gemini CLI |
| Task-015 | MA System Verification | 🔄 in-progress | Claude Code + Codex |
| Task-016 | JOH Technical Note | ✅ completed | Antigravity |
| Task-017 | JOH Stress Testing | 📋 planned | Antigravity |
| **Task-018** | **MA Visualization** | 📋 **planned** | **Codex + Antigravity** |

---

## Task-015 子任務狀態

| ID | Title | Status | Assigned |
|:---|:------|:-------|:---------|
| 015-A | Decision diversity | `pending` | Codex |
| 015-B | Elevated persistence | ✅ `completed` | Claude Code |
| 015-C | Insurance annual reset | ✅ `completed` | Claude Code |
| 015-D | Behavior rationality | `pending` | Codex |
| 015-E | Memory & state logic | ✅ `completed` | Codex |
| 015-F | Institutional dynamics | `pending` | Codex |

---

## Task-018 子任務分配 (NEW)

### Codex (CLI)

| ID | Title | Priority |
|:---|:------|:---------|
| 018-A | Decision Distribution Charts | High |
| 018-B | PMT-Decision Correlation Heatmap | High |
| 018-E | Institutional Policy Impact | Medium |

### Antigravity (AI IDE)

| ID | Title | Priority |
|:---|:------|:---------|
| 018-C | Agent Trajectory Analysis | High |
| 018-D | MG Equity Analysis Charts | High |
| 018-F | PMT Construct Temporal Evolution | Medium |

---

## Task-017 子任務 (Antigravity)

| ID | Title | Status |
|:---|:------|:-------|
| 017-A | Script Configuration | pending |
| 017-B | Gemma 3 Stress Marathon | pending |
| 017-C | Llama 3 Stress Marathon | pending |
| 017-D | Analysis & Appendix Update | pending |

---

## Task-013 剩餘子任務

| ID | Title | Status | Assigned |
|:---|:------|:-------|:---------|
| 013-B | Survey data additional fields | `pending` | Antigravity |

(其他子任務 013-A/C/D/E 已完成)

---

## 已知問題

### issue-001: Non-ASCII Path Blocker
- **Status**: open → 搬遷後將 resolved
- **Affected**: Gemini CLI
- **Resolution**: 搬遷到 `C:\Users\wenyu\Desktop\Lehigh`

---

## V2/V4/V5/V6 驗證狀態

| Verification | Status | Notes |
|:-------------|:-------|:------|
| V1 Diversity | pending | 015-A |
| V2 Elevated | ✅ fixed | agent_validator.py L60-72 |
| V3 Insurance | ✅ fixed | pre_year hook |
| V4 Rationality | ❌ failing | low-CP expensive rate 29.4% > 20% |
| V5 Memory | ✅ passing | trace fields added |
| V6 Institutional | pending | need real LLM |

---

## 視覺化計畫 (Task-018)

### Phase 1 (High Priority)
1. **018-A**: 決策分布圖 + Shannon Entropy 趨勢
2. **018-B**: PMT-Decision 相關性熱力圖
3. **018-C**: Agent 決策軌跡時序圖
4. **018-D**: MG vs non-MG 適應率比較

### Phase 2 (Medium Priority)
5. **018-E**: 政策影響分析 (subsidy vs elevation)
6. **018-F**: PMT 構念時序演化

### 資料來源
- `simulation_log.csv` - 主要決策日誌
- `raw/*.jsonl` - 詳細 trace
- `governance_summary.json` - 環境變數歷史

---

## 搬遷資訊

- **原路徑**: `H:\我的雲端硬碟\github\governed_broker_framework`
- **新路徑**: `C:\Users\wenyu\Desktop\Lehigh`
- **搬遷後好處**:
  - Gemini CLI 可重新啟用
  - 路徑更短更穩定
  - 無 Unicode 編碼問題

---

## 搬遷後待辦

1. [ ] 驗證 Git 狀態
2. [ ] 重建 Python venv (如需要)
3. [ ] 更新 `registry.json` 中 issue-001 狀態為 resolved
4. [ ] 更新 Gemini CLI 為 Active
5. [ ] 繼續 Task-015 A/D/F 驗證
6. [ ] 開始 Task-018 視覺化工作

---

## Agent 角色分配 (最終版)

| Agent | Role | Tasks |
|:------|:-----|:------|
| **Claude Code** | Planner/Reviewer | 規劃、審核、協調 |
| **Codex** | CLI Executor | 015-A/D/F, 018-A/B/E |
| **Antigravity** | AI IDE Executor | 013-B, 017-A~D, 018-C/D/F |
| **Gemini CLI** | CLI Executor | 搬遷後可重新啟用 |
| **Cursor** | AI IDE Executor | 備用 |

---

## 重要檔案路徑 (相對)

```
.tasks/
├── registry.json           # 任務註冊表
├── handoff/
│   ├── current-session.md  # 當前 session handoff
│   ├── task-015.md         # Task-015 詳細 handoff
│   ├── task-018.md         # Task-018 視覺化 handoff
│   └── plan-snapshot-*.md  # Plan 快照
├── MIGRATION_CHECKLIST.md  # 搬遷檢查清單
└── README.md               # 任務系統說明

examples/multi_agent/
├── run_unified_experiment.py  # MA 主程式
├── results_unified/           # 實驗結果
└── tests/                     # 驗證腳本

validators/
└── agent_validator.py         # V2 fix 位置 (L60-72)
```
