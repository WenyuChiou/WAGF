# .tasks/ - 跨 AI/IDE 協作工作區

此資料夾用於多個 AI 代理和 IDE 之間的協作，**不上傳到 GitHub**。

## 目錄結構

```
.tasks/
├── README.md              # 本說明文件
├── registry.json          # 任務註冊表（所有代理共享）
├── artifacts/             # 各代理產出的工件
│   ├── claude-code/       # Claude Code 產出
│   ├── gemini/            # Gemini 產出
│   ├── codex/             # OpenAI Codex 產出
│   └── shared/            # 跨代理共享的工件
├── handoff/               # 代理間交接文件
│   └── {task-id}.md       # 交接說明（上下文、進度、待辦）
└── logs/                  # 執行日誌（可審計）
    └── {agent}-{timestamp}.log
```

## 使用方式

### 1. 任務交接 (Handoff)

當一個 AI 代理需要交接給另一個時，在 `handoff/` 建立文件：

```markdown
# handoff/{task-id}.md

## 任務摘要
[簡述任務目標]

## 已完成
- [x] 步驟 1
- [x] 步驟 2

## 待完成
- [ ] 步驟 3
- [ ] 步驟 4

## 關鍵文件
- `path/to/file1.py` - 描述
- `path/to/file2.yaml` - 描述

## 上下文
[重要的背景資訊、決策理由等]
```

### 2. 任務註冊表 (registry.json)

```json
{
  "tasks": [
    {
      "id": "task-001",
      "title": "修復框架污染",
      "status": "completed",
      "type": "module",
      "priority": "high",
      "eta": "2025-01-16",
      "blocked_reason": "",
      "owner": "claude-code",
      "reviewer": "codex",
      "assigned_to": "claude-code",
      "scope": ["broker/", "validators/"],
      "created_at": "2025-01-15T10:00:00Z",
      "completed_at": "2025-01-15T12:00:00Z",
      "done_when": [
        "核心模組無實驗硬編碼",
        "最少一次 mock 測試通過"
      ],
      "tests_run": ["python run_flood.py --model mock --agents 3 --years 2"],
      "risks": ["改動核心模組可能影響現有實驗"],
      "rollback": ["revert commits 844a1c5, 1907d16"],
      "artifacts": ["artifacts/codex/task-001-20250115-summary.md"],
      "handoff_file": "handoff/task-001.md"
    }
  ]
}
```

欄位定義（最小集合，其他可擴充）：
- `type`: `experiment` / `module` / `ops`
- `priority`: `low` / `medium` / `high`
- `eta`: 預期完成日期（YYYY-MM-DD）
- `blocked_reason`: 若阻塞，簡述原因
- `owner` / `reviewer`: 主要負責與驗收者
- `scope`: 涵蓋模組或資料夾清單
- `done_when`: 定義完成條件 (Definition of Done)
- `tests_run`: 已執行的測試指令
- `risks` / `rollback`: 風險與回滾方案
- `artifacts`: 產物清單（指向 `.tasks/artifacts/`）
- `next_step`: 下一步行動（若無待辦，寫「無」）

### 3. MCP 工具整合

所有代理透過 MCP 工具存取共同能力：
- 讀寫檔案
- 執行測試
- 查詢代碼引用
- 修改配置

## 協作原則

1. **寫入前先讀取** - 避免覆蓋其他代理的工作
2. **明確交接** - 使用 handoff 文件記錄上下文
3. **可審計** - 重要操作寫入 logs/
4. **原子操作** - 一個任務完成後再開始下一個
5. **實驗與模組分離** - 實驗產物僅進 artifacts；升級為模組需記錄決策與測試
6. **定義完成條件** - handoff/registry 需有 `done_when`
7. **風險與回滾** - 變更核心或資料時必須提供
8. **測試與產物對齊** - handoff 需標註 `tests_run` 與 `artifacts`
9. **結束必回寫** - 每次 AI 總結回覆前，必須更新 `.tasks/handoff/current-session.md` 與 `.tasks/registry.json`

## 快捷規則

- **Read task**：收到使用者訊息為 `Read task` 時，必讀 `.tasks/handoff/current-session.md` 與 `.tasks/registry.json`，並回覆任務摘要、當前狀態、下一步
- **縮寫**：`SA` = single agent（`examples/single_agent/`）；`MA` = multi agent（`examples/multi_agent/`）
- **待辦為空**：若 handoff 的待辦事項為空，請填寫「無」表示需要開始新計畫；Read task 回覆需提醒「目前無待辦，是否要開始新計畫」

## 關鍵指令（通用）

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
