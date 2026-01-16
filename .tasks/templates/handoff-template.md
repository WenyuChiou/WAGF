# 工作階段交接 - [任務標題]

> **日期**：YYYY-MM-DD
> **AI 代理**：[Claude Code / Gemini / Codex / ...]
> **任務 ID**：task-XXX
> **類型**：experiment / module / ops
> **範圍**：[broker/, examples/, config/, ...]
> **Done When**：[完成條件]
> **Owner / Reviewer**：[name / name]

---

## 任務摘要

[用 2-3 句話描述這次工作的目標]

---

## 假設與前提

- [重要前提 1]
- [重要前提 2]

---

## 已完成任務

### 1. [子任務標題]
**問題**：[描述要解決的問題]

**根因**：
- [原因 1]
- [原因 2]

**解決方案**：
- [做了什麼修改]
- [使用了什麼方法]

**影響的檔案**：
- `path/to/file1.py` - [修改說明]
- `path/to/file2.yaml` - [修改說明]

### 2. [下一個子任務標題]
...

---

## Git Commits

| Hash | 類型 | 說明 |
|------|------|------|
| `xxxxxxx` | feat | [說明] |
| `yyyyyyy` | fix | [說明] |
| `zzzzzzz` | refactor | [說明] |

---

## 重要決策

### 決策 1：[標題]
**上下文**：[為什麼需要做這個決策]
**選項**：
1. [選項 A] - 優點：... / 缺點：...
2. [選項 B] - 優點：... / 缺點：...

**決定**：選擇 [X]
**理由**：[為什麼選擇這個]

---

## 風險與回滾

**風險**：
- [風險 1]
- [風險 2]

**回滾**：
- [回滾方式或指令]

---

## 待辦事項

### 優先級高
- [ ] [任務描述]
- [ ] [任務描述]

### 優先級中
- [ ] [任務描述]

### 優先級低
- [ ] [任務描述]

---

## 測試結果

### 已通過
- [x] Mock 測試 (`python run_flood.py --model mock --agents 3 --years 2`)
- [x] [其他測試]

### 待驗證
- [ ] 完整 LLM 測試
- [ ] Multi-agent 測試

---

## 產物 (artifacts)

- `.tasks/artifacts/codex/task-XXX-YYYYMMDD-summary.md`
- [其他產物]

---

## 關鍵檔案參考

| 檔案 | 用途 |
|------|------|
| `path/to/file1.py` | [用途說明] |
| `path/to/file2.yaml` | [用途說明] |

---

## 回寫確認（總結前必填）

- [ ] 已更新 `.tasks/handoff/current-session.md`
- [ ] 已更新 `.tasks/registry.json`
- [ ] 已更新 `.tasks/artifacts/`（若有產物）

---

## 給下一位 AI 的備註

[任何對接手此工作的 AI 有幫助的資訊]

例如：
- 注意 XXX 文件有特殊格式
- YYY 功能目前有已知限制
- 建議先閱讀 ZZZ 了解架構

---

*上次更新：YYYY-MM-DD HH:MM*
