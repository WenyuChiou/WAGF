# 專案搬遷檢查清單

## 搬遷資訊

- **原始路徑**: `H:\我的雲端硬碟\github\governed_broker_framework`
- **新路徑**: `C:\Users\wenyu\Desktop\Lehigh`
- **搬遷原因**: 解決 Gemini CLI 非 ASCII 路徑問題

---

## 搬遷前檢查

### 1. Git 狀態確認

```bash
cd "H:\我的雲端硬碟\github\governed_broker_framework"
git status
git stash list
```

確認：
- [ ] 無未提交的重要變更
- [ ] 無遺留的 stash

### 2. 虛擬環境 (如有)

```bash
# 檢查是否有 venv
dir /b venv .venv env
```

- [ ] 虛擬環境將在新位置重新建立

---

## 搬遷步驟

### Windows 命令

```powershell
# 1. 複製整個專案 (保留 git history)
robocopy "H:\我的雲端硬碟\github\governed_broker_framework" "C:\Users\wenyu\Desktop\Lehigh" /E /COPYALL /R:3

# 2. 驗證複製
cd C:\Users\wenyu\Desktop\Lehigh
git status
git log --oneline -5
```

---

## 搬遷後驗證

### 1. Git 驗證

```bash
cd C:\Users\wenyu\Desktop\Lehigh
git status
git remote -v
git log --oneline -3
```

### 2. Python 環境重建

```bash
cd C:\Users\wenyu\Desktop\Lehigh
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 基本功能測試

```bash
# SA 測試
cd examples\single_agent
python run_flood.py --model mock --rounds 2

# MA 測試
cd examples\multi_agent
set GOVERNANCE_PROFILE=strict
python run_unified_experiment.py --model mock --years 2 --agents 5 --mode random
```

### 4. 更新 IDE/編輯器

- [ ] VSCode: 開啟新路徑的資料夾
- [ ] Claude Code: 重新連接到新路徑
- [ ] 其他 AI IDE (Cursor/Antigravity): 更新專案路徑

---

## 路徑相關檔案 (不需手動修改)

以下檔案包含舊路徑，但多為**說明文件或已完成的 log**，搬遷後不影響功能：

| 檔案 | 內容 | 處理 |
|:-----|:-----|:-----|
| `.tasks/handoff/current-session.md` | Known issue 說明 | 可選更新 |
| `.tasks/README.md` | 範例路徑說明 | 可選更新 |
| `.tasks/task_backup.md` | 備份紀錄 | 無需變更 |
| `.tasks/scripts/fix_registry.py` | 修復腳本 | 無需變更 |

**注意**: `config_snapshot.yaml` 檔案是實驗結果的快照，記錄當時的執行環境，**不需要修改**。

---

## 搬遷後更新 (可選)

### 更新 known_issues

搬遷完成後，可在 `registry.json` 中更新 issue 狀態：

```json
{
  "id": "issue-001",
  "title": "Non-ASCII Path Blocker",
  "status": "resolved",
  "resolution": "Project moved to C:\\Users\\wenyu\\Desktop\\Lehigh",
  "resolved_date": "2026-01-18"
}
```

### 解除 Gemini CLI 封鎖

搬遷後 Gemini CLI 可重新啟用：

```
// current-session.md 中的 Role Division
| **Executor (CLI)** | Gemini CLI | **Active** |
```

---

## 清理 (可選)

確認新位置運作正常後：

```powershell
# 刪除舊位置 (謹慎！)
# rmdir /s /q "H:\我的雲端硬碟\github\governed_broker_framework"

# 或保留舊位置作為備份
```

---

## 快速驗證腳本

搬遷後執行此腳本驗證：

```bash
cd C:\Users\wenyu\Desktop\Lehigh

echo === Git Check ===
git status
git log --oneline -1

echo === Python Check ===
python --version
python -c "import broker; print('broker module OK')"

echo === Task System Check ===
type .tasks\registry.json | findstr "version"

echo === Ready! ===
```
