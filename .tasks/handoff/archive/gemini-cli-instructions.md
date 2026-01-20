# Gemini CLI 任務指令

## Last Updated
2026-01-19T00:00:00Z

---

## 當前狀態摘要

| Task | Status | 說明 |
|:-----|:-------|:-----|
| Task-019 | ✅ completed | 配置增強完成 |
| Task-015 | 🔄 in-progress | V1 pass, V4 fail, V5 pass, V6 pending |
| Task-018 | ⚠️ partial | 腳本完成，待重跑 |

---

## 你的任務：Task-015-F (V6 Institutional Dynamics)

### 前置條件
- ✅ Non-ASCII path issue resolved (已搬到 `C:\Users\wenyu\Desktop\Lehigh`)
- ✅ Task-019 completed
- ⚠️ 需要完整實驗資料 (目前只有 partial run)

### 背景
Codex 已執行部分實驗，但 10 年 × 20 agents 實驗 timeout。目前有兩個 partial 輸出：
- `examples/multi_agent/v015_codex/llama3_2_3b_strict/raw/` (3 years × 10 agents)
- `examples/multi_agent/results_unified/v015_full_rerun/llama3_2_3b_strict/raw/` (partial)

### 驗證目標
**V6: Institutional Dynamics** - 確認政府和保險公司會根據情況調整政策

---

## 執行指令

### Step 1: 確認工作目錄
```bash
cd C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
```

### Step 2: 檢查現有資料
```bash
# 檢查 Codex 的實驗輸出
ls examples/multi_agent/v015_codex/llama3_2_3b_strict/raw/

# 檢查 government/insurance traces
ls examples/multi_agent/v015_codex/llama3_2_3b_strict/raw/*government* 2>/dev/null || echo "No gov traces"
ls examples/multi_agent/v015_codex/llama3_2_3b_strict/raw/*insurance* 2>/dev/null || echo "No ins traces"
```

### Step 3: 執行 V6 驗證
```bash
cd examples/multi_agent
python -c "
import json
from pathlib import Path

# 使用 Codex 的實驗輸出
traces_dir = Path('v015_codex/llama3_2_3b_strict/raw')

gov = []
ins = []

# 讀取 Government traces
gf = traces_dir / 'NJ_STATE_traces.jsonl'
if not gf.exists():
    gf = traces_dir / 'government_traces.jsonl'
if gf.exists():
    with open(gf) as f:
        for line in f:
            try:
                trace = json.loads(line)
                skill = trace.get('approved_skill', {}).get('skill_name', '')
                gov.append(skill)
            except:
                pass

# 讀取 Insurance traces
inf = traces_dir / 'FEMA_NFIP_traces.jsonl'
if not inf.exists():
    inf = traces_dir / 'insurance_traces.jsonl'
if inf.exists():
    with open(inf) as f:
        for line in f:
            try:
                trace = json.loads(line)
                skill = trace.get('approved_skill', {}).get('skill_name', '')
                ins.append(skill)
            except:
                pass

# 計算政策變化次數
maintain_gov = ['maintain_subsidy', 'MAINTAIN', '3', 'maintain']
maintain_ins = ['maintain_premium', 'MAINTAIN', '3', 'maintain']

gov_changes = sum(1 for d in gov if d and d not in maintain_gov)
ins_changes = sum(1 for d in ins if d and d not in maintain_ins)

print('='*50)
print('V6 INSTITUTIONAL DYNAMICS VERIFICATION')
print('='*50)
print(f'Government decisions ({len(gov)} total): {gov}')
print(f'Government policy changes: {gov_changes}')
print(f'Insurance decisions ({len(ins)} total): {ins}')
print(f'Insurance policy changes: {ins_changes}')
print()
print(f'Total policy changes: {gov_changes + ins_changes}')
print(f'V6 PASS: {(gov_changes > 0 or ins_changes > 0)}')
print('='*50)
"
```

---

## 驗收標準

| 指標 | 閾值 | 說明 |
|:-----|:-----|:-----|
| Gov/Ins 政策變化 | > 0 | 至少有 1 次非 maintain 決策 |

---

## 如果 V6 失敗

如果 V6 失敗 (所有決策都是 maintain)，可能原因：
1. 實驗年數太少 (需要更多時間讓政策變化)
2. Mock model 使用 (需要真實 LLM)
3. Prompt 設計問題 (政府/保險沒有足夠資訊決策)

### 建議的下一步
1. 檢查 trace 中的 reasoning 欄位，確認 LLM 有正確理解 prompt
2. 如果是 mock model，需要用真實 LLM 重跑
3. 如果是年數問題，可以跑更長的實驗 (10+ years)

---

## 回報格式

完成後請回報：

```
REPORT
agent: Gemini CLI
task_id: task-015-F
scope: examples/multi_agent/v015_codex/llama3_2_3b_strict/raw/
status: done | partial | blocked
metrics:
  - V6 gov_changes: N
  - V6 ins_changes: N
  - V6 PASS: true/false
issues: <any problems>
next: <next subtask>
```

---

## 額外任務：Task-019-E (Optional)

### 問題發現
經 Claude Code 檢核發現，`ma_agent_types.yaml` 中的 `memory_config` 和 `retrieval_config` **已定義但未被代碼讀取**。

目前 `MemoryEngine` 使用硬編碼的檢索邏輯，而非從 YAML 動態載入配置。

### 需要實現 (Low Priority)
1. 讀取 YAML 中的 `memory_config`，根據 agent_type 選擇 engine
2. 讀取 `retrieval_config`，套用 emotional_weights 和 source_weights
3. 修改 `run_unified_experiment.py` 載入這些配置

### 影響範圍
- `examples/multi_agent/run_unified_experiment.py` - 讀取 YAML config
- `broker/components/memory_engine.py` - 支援 config-based initialization

### 優先級
**Low** - 目前系統可運作，只是配置未被使用

---

## 文件位置

| 文件 | 用途 |
|:-----|:-----|
| `.tasks/registry.json` | 任務狀態追蹤 |
| `.tasks/handoff/task-015.md` | Task-015 完整說明 |
| `.tasks/handoff/task-019.md` | Task-019 完整說明 |
| `.tasks/handoff/current-session.md` | 當前 session 狀態 |

---

## 聯絡

完成後請更新 `.tasks/handoff/current-session.md` 的 Update 區塊。
