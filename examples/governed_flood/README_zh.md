# 洪水治理示範實驗（Governed Flood）

獨立範例展示 **Group C（完整認知治理）**——Governed Broker Framework 在洪水適應 ABM 的最完整配置。

## 三大支柱

| 支柱 | 名稱 | 設定 | 效果 |
|------|------|------|------|
| 1 | **嚴格治理** | `governance_mode: strict` + PMT thinking/identity 規則 | 阻擋認知不一致的決策 |
| 2 | **認知記憶** | `HumanCentricMemoryEngine` + `ReflectionEngine` | 情緒編碼 + 年度整合 |
| 3 | **優先序架構** | `use_priority_schema: true` | 現實物理狀態先於偏好進入情境 |

## 快速開始

```bash
# 完整實驗（預設：gemma3:4b、10 年、100 名代理）
python run_experiment.py

# 小型測試
python run_experiment.py --model gemma3:4b --years 2 --agents 10

# 自訂模型與輸出路徑
python run_experiment.py --model gemma3:4b --years 10 --agents 100 --output results/my_run
```

## 治理規則（v22，嚴格模式）

本範例使用嚴格治理設定，阻擋認知不一致行為並記錄警示。

| 規則 | 嚴重度 | 說明 |
|------|--------|------|
| `extreme_threat_block` | ERROR | TP 在 {H, VH} 時阻擋 `do_nothing` |
| `low_coping_block` | WARNING | CP 在 {VL, L} 時觀察 `elevate`/`relocate` |
| `relocation_threat_low` | ERROR | TP 在 {VL, L} 時阻擋 `relocate` |
| `elevation_threat_low` | ERROR | TP 在 {VL, L} 時阻擋 `elevate` |
| `elevation_block` | ERROR | 已抬升的代理不可再次抬升 |

## 輸出檔案

```
results/
  simulation_log.csv               # 決策紀錄（代理 x 年）
  household_governance_audit.csv    # 治理驗證追蹤
  reflection_log.jsonl              # 年終反思記錄
  reproducibility_manifest.json     # seed、模型、設定快照
  config_snapshot.yaml              # 實際使用的 YAML 設定
  governance_summary.json           # 驗證統計
  raw/
    household_traces.jsonl          # 完整 LLM 互動紀錄
```

### 輸出解讀指南

| 檔案 | 說明 |
|------|------|
| `governance_summary.json` | `total_interventions` = ERROR 阻擋次數，`warnings.total_warnings` = WARNING 觀察次數，`retry_success` = 代理重試後修正成功 |
| `household_governance_audit.csv` | 每位代理的稽核紀錄。重要欄位：`failed_rules`, `warning_rules`, `warning_messages` |
| `audit_summary.json` | 解析品質：`validation_errors`（結構性解析失敗）、`validation_warnings`（治理警示） |
| `config_snapshot.yaml` | 完整實驗設定，用於可重現 |

## 與 `single_agent/run_flood.py` 的差異

| 面向 | `run_flood.py`（1048 行） | `run_experiment.py`（約 300 行） |
|------|---------------------------|-----------------------------------|
| 目的 | 比較實驗（Group A/B/C） | 只展示 Group C |
| 客製類別 | FinalContextBuilder, DecisionFilteredMemoryEngine, FinalParityHook | 無（直接使用 broker API） |
| 記憶引擎 | 動態選擇（window/importance/humancentric） | 固定：HumanCentricMemoryEngine |
| 治理 | 可設定（strict/relaxed/disabled） | 固定：strict |
| 壓力測試 | 4 種 profile | 無 |
| 問卷模式 | 支援 | 不含 |

## CLI 參數

| 參數 | 預設 | 說明 |
|------|------|------|
| `--model` | `gemma3:4b` | Ollama 模型名稱 |
| `--years` | `10` | 模擬年數 |
| `--agents` | `100` | 住戶代理數 |
| `--workers` | `1` | 並行 LLM workers |
| `--seed` | random | 可重現的亂數種子 |
| `--memory-seed` | `42` | 記憶引擎種子 |
| `--window-size` | `5` | 記憶視窗大小 |
| `--output` | `results/` | 輸出目錄 |
| `--num-ctx` | auto | Ollama context window 覆寫 |
| `--num-predict` | auto | Ollama max tokens 覆寫 |
