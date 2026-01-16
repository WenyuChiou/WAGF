# AI 協作指南 (AI Collaboration Guide)

> **給所有 AI 代理的說明**：本文件定義了在此專案中工作的標準流程。
> 無論你是 Claude Code、Gemini、Codex 還是其他 AI，都請遵循此指南。

---

## 目錄

1. [開始工作前](#1-開始工作前)
2. [核心原則：模組與實驗分離](#2-核心原則模組與實驗分離)
3. [Plan 管理規則](#3-plan-管理規則)
4. [標準工作流程](#4-標準工作流程)
5. [Git Commit 規範](#5-git-commit-規範)
6. [修改-測試-驗證循環](#6-修改-測試-驗證循環)
7. [Stacked PR 指南](#7-stacked-pr-指南)
8. [記錄要求](#8-記錄要求)
9. [常見任務範例](#9-常見任務範例)

---

## 1. 開始工作前

### 1.1 必讀文件

在開始任何工作之前，**必須**閱讀以下文件：

```
.tasks/
├── handoff/current-session.md  ← 當前工作狀態（必讀）
├── registry.json               ← 任務註冊表
└── GUIDE.md                    ← 本文件
```

### 1.2 檢查清單

- [ ] 讀取 `.tasks/handoff/current-session.md` 了解當前狀態
- [ ] 讀取 `.tasks/registry.json` 確認待辦任務
- [ ] 執行 `git status` 確認當前分支和改動狀態
- [ ] 確認沒有其他 AI 正在進行衝突的工作

### 1.3 確認環境

```bash
# 確認 Git 狀態
git status

# 確認測試可運行（根據專案）
python -m pytest tests/ -v --tb=short
# 或
cd examples/single_agent && python run_flood.py --model mock --agents 3 --years 2
```

### 1.4 術語與縮寫

- `SA`：single agent（對應 `examples/single_agent/`）
- `MA`：multi agent（對應 `examples/multi_agent/`）

### 1.5 Read task 快捷規則

當使用者訊息為 `Read task` 時，必須：
1. 讀取 `.tasks/handoff/current-session.md`
2. 讀取 `.tasks/registry.json`
3. 回覆：任務摘要、當前狀態、下一步、阻塞原因（若有）
4. 若待辦為空且標記為「無」，請主動詢問是否要開始新計畫

---

### 1.6 關鍵指令（通用）

- `Start task <id>`：建立/切換任務並寫入 handoff/registry
- `Update task`：強制回寫進度
- `Block task <reason>`：設 `blocked_reason` 並回寫
- `Unblock task`：清除阻塞並回填 `next_step`
- `Switch task <id>`：回寫後切換任務
- `Add todo <item>`：新增待辦與 `next_step`
- `Clear todo`：清空待辦並寫「無」
- `Log artifact <path>`：登記產物
- `Run test <cmd>`：記錄測試命令與結果
- `Plan task`：建立/更新 Plan 區塊

---

## 2. 核心原則：模組與實驗分離

> **這是本專案最重要的架構原則，所有 AI 代理必須嚴格遵守。**

### 2.1 原則說明

```
┌─────────────────────────────────────────────────────────────────┐
│                        框架核心 (broker/)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   通用的    │  │   通用的    │  │   通用的    │              │
│  │  LLM 工具   │  │  代理基類   │  │  實驗運行器  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                                                                  │
│  ❌ 不允許：實驗特定的硬編碼（如 "flood", "household"）          │
│  ✅ 允許：從配置讀取的通用邏輯                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ 繼承/配置
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     實驗層 (examples/)                           │
│  ┌─────────────────────┐  ┌─────────────────────┐               │
│  │   洪水實驗           │  │   其他實驗           │               │
│  │   (single_agent/)   │  │   (future/)         │               │
│  │                     │  │                     │               │
│  │  ✅ flood, household│  │  ✅ 自定義術語       │               │
│  │  ✅ 特定技能        │  │  ✅ 特定技能        │               │
│  │  ✅ 特定配置        │  │  ✅ 特定配置        │               │
│  └─────────────────────┘  └─────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 禁止事項 (broker/ 核心模組)

| 類型 | 禁止範例 | 應該改為 |
|------|----------|----------|
| 硬編碼動作 | `if "buy_insurance" in prompt` | 從配置讀取動作列表 |
| 硬編碼字段 | `context.get("flood_experience")` | 從 YAML 配置讀取字段名 |
| 硬編碼停用詞 | `blacklist = {"flood", "water"}` | 從配置讀取 `audit_blacklist` |
| 默認代理類型 | `agent_type="household"` | `agent_type=None`（必須指定）|
| 領域特定註釋 | `# flood damage calculation` | `# damage calculation` |

### 2.3 檢查清單

在修改 `broker/` 目錄下的任何檔案前，請確認：

- [ ] **不包含實驗特定術語**（flood, household, insurance 等）
- [ ] **不包含硬編碼的動作/技能名稱**
- [ ] **所有可配置項都從 YAML 讀取**
- [ ] **默認值是通用的**（或無默認值需明確指定）
- [ ] **註釋和文檔使用通用範例**

### 2.4 實驗/模組邊界與升級準則

- **實驗產物隔離**：實驗結果、圖表、臨時腳本必須放在 `.tasks/artifacts/` 或 `examples/`
- **升級為模組的必要條件**：
  - 需求可配置化（不可寫死）
  - 至少一個測試或可重現驗證命令
  - handoff 內有決策記錄（為何升級）
  - 文件更新（README 或 GUIDE）

### 2.5 自我審查命令

在提交核心模組修改前，運行以下檢查：

```bash
# 檢查是否有洪水實驗特定術語洩漏到核心模組
grep -rn "flood\|household\|insurance\|elevate" broker/ --include="*.py" | grep -v "# Example:" | grep -v "test"

# 如果有輸出，需要檢查並移除
```

### 2.6 違規範例與修正

**❌ 違規範例（在 broker/utils/llm_utils.py）：**
```python
# Mock LLM 硬編碼洪水實驗動作
if "buy_insurance" in prompt:
    decision = "buy_insurance"
elif "relocate" in prompt:
    decision = "relocate"
else:
    decision = "do_nothing"
```

**✅ 正確做法：**
```python
# Mock LLM 從 prompt 提取選項（通用）
option_pattern = r'(\d+)\.\s+\w+'
options = re.findall(option_pattern, prompt)
decision_id = options[0] if options else "1"
```

---

## 3. Plan 管理規則

> **一次只能進行一個 Plan，必須完成當前 Plan 才能開始下一個。**

### 3.1 Plan 狀態

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   規劃中    │ →   │   執行中    │ →   │   已完成    │
│  Planning   │     │  Executing  │     │  Completed  │
└─────────────┘     └─────────────┘     └─────────────┘
       │                                       │
       └───────────────────────────────────────┘
                    下一個 Plan
```

### 3.2 規則

1. **一次一個 Plan**
   - 檢查 `.tasks/registry.json` 中是否有 `status: "in_progress"` 的任務
   - 如果有，必須先完成它

2. **完成標準**
   - 所有子任務都標記為完成
   - 測試通過
   - 已 commit 並記錄
   - handoff 文件已更新

3. **新 Plan 啟動條件**
   - 當前 Plan 狀態為 `completed` 或無進行中的 Plan
   - 用戶明確請求新任務

### 3.3 Plan 交接格式

當需要交接未完成的 Plan 時：

```markdown
## Plan 交接：[Plan 標題]

### 狀態
- [ ] 子任務 1（已完成）
- [ ] 子任務 2（進行中 - 80%）
- [ ] 子任務 3（未開始）

### 當前進度
[描述目前停在哪裡]

### 下一步
[接手後應該做什麼]

### 注意事項
[任何重要的上下文]
```

### 3.4 禁止事項

- ❌ 同時進行多個 Plan
- ❌ 未完成 Plan 就開始新 Plan
- ❌ 不記錄 Plan 狀態就結束工作
- ❌ 跳過測試直接標記完成

---

### 3.5 Registry 欄位要求

- `type`：明確標註 `experiment` / `module` / `ops`
- `priority` / `eta`：避免交接時無法排序
- `blocked_reason`：阻塞時必填
- `owner` / `reviewer`：明確負責與驗收人
- `scope` / `done_when`：任務範圍與完成標準
- `next_step`：下一步行動，無待辦則寫「無」

## 4. 標準工作流程

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  1. 接收    │ →  │  2. 閱讀    │ →  │  3. 規劃    │
│    任務     │    │   上下文    │    │   步驟      │
└─────────────┘    └─────────────┘    └─────────────┘
                                            │
                                            ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  7. 交接    │ ←  │  6. 記錄    │ ←  │  4. 實作    │
│   更新      │    │   結果      │    │   循環      │
└─────────────┘    └─────────────┘    └─────────────┘
                         ↑                  │
                         │                  ▼
                         │           ┌─────────────┐
                         └───────────│  5. 測試    │
                                     │   驗證      │
                                     └─────────────┘
```

### Step 1: 接收任務
- 理解用戶需求
- 確認任務範圍

### Step 2: 閱讀上下文
- 讀取 `.tasks/handoff/current-session.md`
- 讀取相關代碼文件
- 了解現有架構

### Step 3: 規劃步驟
- 拆分為可測試的小步驟
- 每個步驟應該是**原子性**的（可獨立 commit）
- 如果是大任務（> 5 個文件），規劃 Stacked PR 結構

### Step 4: 實作循環
對每個小步驟重複：
1. 修改代碼
2. 運行測試
3. 驗證結果
4. Git commit（如果成功）

### Step 5: 測試驗證
- 運行單元測試
- 運行整合測試
- 手動驗證（如需要）

### Step 6: 記錄結果
- 更新 `.tasks/handoff/current-session.md`
- 記錄做了什麼、為什麼這樣做

### Step 7: 交接更新
- 更新 `.tasks/registry.json`
- 確保下一個 AI 可以無縫接手

---

## 3. Git Commit 規範

### 3.1 Commit Message 格式

使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>(<scope>): <subject>

<body>

Why: <reason>
Refs: <references>
```

### 3.2 類型 (type)

| 類型 | 說明 | 範例 |
|------|------|------|
| `feat` | 新功能 | `feat(llm): Add temperature configuration` |
| `fix` | 修復 bug | `fix(parser): Handle empty response` |
| `refactor` | 重構（不改變功能）| `refactor(core): Remove hardcoded values` |
| `docs` | 文檔更新 | `docs(readme): Update installation guide` |
| `test` | 測試相關 | `test(agent): Add unit tests for parser` |
| `chore` | 雜項（構建、工具等）| `chore(deps): Update dependencies` |

### 3.3 範例

**好的 Commit Message：**

```
feat(llm): Add configurable temperature parameter

- Add LLM_CONFIG dataclass for global configuration
- Support CLI arguments: --temperature, --top-p, --top-k
- Default to Ollama defaults when not specified

Why: Framework version had lower output diversity than original
because it explicitly set temperature=0.8

Refs: .tasks/handoff/current-session.md
```

**不好的 Commit Message：**

```
fix stuff          ← 太模糊
update code        ← 沒有說明改了什麼
WIP               ← 不應該 commit 未完成的工作
```

### 3.4 何時 Commit

- **每完成一個邏輯單元就 commit**
- 測試通過後立即 commit
- 不要累積太多改動在一個 commit

---

## 4. 修改-測試-驗證循環

```
    ┌──────────────────────────────────────────────┐
    │                                              │
    ▼                                              │
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌────┴────┐
│  修改   │ →  │  運行   │ →  │  驗證   │ →  │  通過?  │
│  代碼   │    │  測試   │    │  結果   │    │         │
└─────────┘    └─────────┘    └─────────┘    └────┬────┘
                                                  │
                              ┌───────────────────┼───────────────────┐
                              │                   │                   │
                              ▼                   ▼                   ▼
                         ┌─────────┐         ┌─────────┐         ┌─────────┐
                         │  失敗   │         │  成功   │         │  部分   │
                         │  修復   │         │ Commit  │         │  記錄   │
                         └─────────┘         └─────────┘         └─────────┘
```

### 4.1 測試命令參考

```bash
# 快速 Mock 測試
cd examples/single_agent
python run_flood.py --model mock --agents 3 --years 2

# 完整 LLM 測試
python run_flood.py --model llama3.2:3b --agents 10 --years 5

# 單元測試（如果有）
python -m pytest tests/ -v
```

### 4.2 驗證清單

- [ ] 代碼語法正確（無 import 錯誤）
- [ ] 測試通過
- [ ] 現有功能未被破壞
- [ ] 新功能按預期工作

---

## 5. Stacked PR 指南

### 5.1 何時使用 Stacked PR

- 修改超過 **5 個檔案**
- 涉及多個**獨立的子任務**
- 需要分階段 review
- 大型重構

### 5.2 結構範例

```
main
  │
  └── feature/task-001-base          ← 基礎分支
        │
        ├── feature/task-001-part1   ← PR #1: 核心修改
        │
        ├── feature/task-001-part2   ← PR #2: 相關更新 (depends on #1)
        │
        └── feature/task-001-part3   ← PR #3: 測試和文檔 (depends on #2)
```

### 5.3 分支命名規範

```
feature/<task-id>-<description>
fix/<task-id>-<description>
refactor/<task-id>-<description>

例如：
feature/task-002-add-multi-agent
fix/task-003-parser-error
refactor/task-001-remove-hardcode
```

### 5.4 Stacked PR 工作流程

```bash
# 1. 創建基礎分支
git checkout main
git pull
git checkout -b feature/task-001-base

# 2. 完成 Part 1
# ... 修改代碼 ...
git add .
git commit -m "feat(core): Part 1 - Core changes"
git push -u origin feature/task-001-base

# 3. 創建 Part 2 分支（基於 Part 1）
git checkout -b feature/task-001-part2
# ... 修改代碼 ...
git commit -m "feat(core): Part 2 - Related updates"
git push -u origin feature/task-001-part2

# 4. 創建 PR
# PR #1: feature/task-001-base → main
# PR #2: feature/task-001-part2 → feature/task-001-base
```

---

## 6. 記錄要求

### 6.1 必須記錄的內容

每次工作結束時，必須更新 `.tasks/handoff/current-session.md`：

1. **做了什麼** - 完成的任務列表
2. **為什麼這樣做** - 決策理由
3. **改了哪些檔案** - 關鍵文件列表
4. **Git commits** - Commit hash 和說明
5. **待辦事項** - 下一步需要做的事
6. **測試結果** - 測試是否通過

### 6.2 結束回寫規則（強制）

每次 AI 在對外回覆「總結」之前，必須完成以下回寫：
- 更新 `.tasks/handoff/current-session.md`
- 更新 `.tasks/registry.json`
- 若有產物，列到 `.tasks/artifacts/` 並在 handoff 記錄

### 6.3 交接必填欄位

- `type`: experiment / module / ops
- `scope`: 涵蓋模組或資料夾
- `done_when`: Definition of Done
- `assumptions`: 重要前提
- `decisions`: 關鍵選擇與理由
- `risks` / `rollback`: 風險與回滾方案
- `tests_run`: 測試命令與結果
- `artifacts`: 產物清單與路徑

### 6.4 決策記錄 (ADR 風格)

對於重要決策，使用以下格式記錄：

```markdown
### 決策：[標題]
**狀態**：已決定 / 待討論
**上下文**：[為什麼需要做這個決策]
**選項**：
1. 選項 A - [優缺點]
2. 選項 B - [優缺點]
**決定**：選擇 [X]
**理由**：[為什麼選擇這個]
**後果**：[這個決定的影響]
```

### 6.5 範例：更新 handoff 文件

```markdown
## 今日工作 (2025-01-15)

### 已完成
- [x] 修復 LLM 參數配置問題
- [x] 移除核心模組的硬編碼

### Git Commits
- `844a1c5` - refactor: Remove domain-specific hardcoding
- `1907d16` - refactor: Remove 'household' default values

### 關鍵決策
選擇使用 OllamaLLM 而非 ChatOllama，因為原版使用此 API。

### 待辦
- [ ] 運行完整測試確認
- [ ] 更新 README
```

---

## 7. 常見任務範例

### 7.1 修復 Bug

```
1. 閱讀 handoff 了解上下文
2. 重現 bug（確認問題存在）
3. 定位問題代碼
4. 修復代碼
5. 運行測試驗證修復
6. Git commit: fix(scope): Fix description
7. 更新 handoff 記錄修復過程
```

### 7.2 添加新功能

```
1. 閱讀 handoff 了解現有架構
2. 規劃功能實現步驟
3. 如果大任務，設置 Stacked PR
4. 實現核心功能
5. 添加測試
6. 運行測試
7. Git commit: feat(scope): Add feature
8. 更新 handoff
```

### 7.3 重構代碼

```
1. 閱讀 handoff 了解代碼現狀
2. 確認所有測試通過（基準線）
3. 進行重構（保持功能不變）
4. 運行測試（確認功能未破壞）
5. Git commit: refactor(scope): Refactor description
6. 更新 handoff 記錄重構原因
```

### 7.4 接手他人工作

```
1. 閱讀 .tasks/handoff/current-session.md
2. 閱讀 .tasks/registry.json 了解任務狀態
3. 確認 Git 狀態
4. 閱讀相關代碼文件
5. 繼續待辦任務
6. 完成後更新 handoff
```

---

## 附錄 A：專案特定測試命令

### 洪水實驗框架

```bash
# 快速 Mock 測試
cd examples/single_agent
python run_flood.py --model mock --agents 3 --years 2

# 完整 LLM 測試
python run_flood.py --model llama3.2:3b --agents 10 --years 5

# 帶參數測試
python run_flood.py --model llama3.2:3b --agents 10 --years 5 \
    --temperature 1.0 --top-p 0.95
```

### Multi-Agent 測試

```bash
cd examples/multi_agent
python run_experiment.py --config config.yaml
```

---

## 附錄 B：關鍵檔案索引

| 檔案 | 用途 |
|------|------|
| `broker/utils/llm_utils.py` | LLM 呼叫和配置 |
| `broker/core/experiment.py` | 實驗運行主邏輯 |
| `broker/utils/model_adapter.py` | 模型適配器 |
| `examples/single_agent/agent_types.yaml` | 代理類型配置 |
| `examples/single_agent/run_flood.py` | 主要實驗腳本 |

---

## 附錄 C：MCP 工具說明

所有 AI 代理透過 MCP (Model Context Protocol) 存取共同工具：

| 工具 | 功能 |
|------|------|
| `read_file` | 讀取檔案內容 |
| `write_file` | 寫入檔案 |
| `edit_file` | 編輯現有檔案 |
| `run_command` | 執行終端命令 |
| `search_code` | 搜尋代碼 |

**注意**：不同 AI/IDE 的 MCP 工具名稱可能略有不同，但功能相同。

---

*最後更新：2025-01-15*
*版本：v1.0*
