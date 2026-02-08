# 範例與基準測試

**語言: [English](README.md) | [中文](README_zh.md)**

此目錄包含 Water Agent Governance Framework 的復現腳本、實驗配置與基準測試結果。

---

## 學習路徑（建議順序）

| # | 範例 | 複雜度 | 學習重點 |
| :--- | :--- | :--- | :--- |
| 1 | **[governed_flood/](governed_flood/)** | 入門 | 獨立的 Group C 示範 — 治理 + 以人為本記憶的實際運作 |
| 2 | **[single_agent/](single_agent/)** | 中階 | 完整 JOH 基準測試 — Groups A/B/C 消融研究、壓力測試、問卷模式 |
| 3 | **[multi_agent/](multi_agent/)** | 進階 | 社會動態 — 保險市場、政府補貼、同儕效應 |
| 4 | **[finance/](finance/)** | 延伸 | 跨領域示範 — 治理下的投資組合決策 |

---

## 目錄概覽

| 目錄 | 代理人數 | 社交 | 治理 | 記憶 | 狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[governed_flood/](governed_flood/)** | 100 | 無 | 僅嚴格 | HumanCentric | 活躍 |
| **[single_agent/](single_agent/)** | 100 | 可選 | 3 種配置（嚴格/寬鬆/停用） | 可配置 | 活躍 |
| **[multi_agent/](multi_agent/)** | 50+ | 有 | 進階 | 可配置 | 活躍 |
| **[finance/](finance/)** | 10 | 有 | 基礎 | 重要性 | 示範 |
| **[archive/](archive/)** | -- | -- | -- | -- | 已歸檔 |

---

## 快速上手

### 1. 最簡單：Governed Flood 示範

governed_flood 範例是一個獨立的 Group C 實驗，含完整治理和以人為本記憶。無需額外配置。

```bash
python examples/governed_flood/run_experiment.py --model gemma3:4b --years 3 --agents 10
```

### 2. 完整基準測試：單代理人（JOH 論文）

複製三組消融研究，100 代理人，10 年：

```bash
# Group A：基準組（無治理、無記憶）
python examples/single_agent/run_flood.py --model gemma3:4b --years 10 --agents 100 \
    --governance-mode disabled

# Group B：治理 + 視窗記憶
python examples/single_agent/run_flood.py --model gemma3:4b --years 10 --agents 100 \
    --memory-engine window --governance-mode strict

# Group C：完整認知（HumanCentric + Priority Schema）
python examples/single_agent/run_flood.py --model gemma3:4b --years 10 --agents 100 \
    --memory-engine humancentric --governance-mode strict --use-priority-schema
```

### 3. 多代理人：社會動態

運行含家戶、政府及保險代理人的多代理人實驗：

```bash
python examples/multi_agent/run_unified_experiment.py --model gemma3:4b
```

### 4. 跨領域：金融

展示治理在金融決策情境中的應用：

```bash
python examples/finance/run_finance.py --model gemma3:4b
```

---

## 輸出結構

每個實驗在其 `results/` 目錄中產生以下輸出：

| 檔案 | 說明 |
| :--- | :--- |
| `household_decisions.csv` | 每代理人、每年的決策日誌（動作、評估、推理） |
| `household_governance_audit.csv` | 治理審計軌跡（介入、重試、警告） |
| `governance_summary.json` | 治理統計彙總（介入次數、警告、結果） |
| `audit_summary.json` | 解析品質指標（驗證錯誤、警告） |
| `config_snapshot.yaml` | 完整實驗配置快照（可重現性） |
| `execution.log` | 控制台輸出日誌 |

---

## 模型

所有範例支援任何 Ollama 相容模型。推薦的基準測試模型：

| 模型 | 標籤 | 參數量 | 備註 |
| :--- | :--- | :--- | :--- |
| Gemma 3 | `gemma3:4b` | 4B | 主要基準 — 快速、良好的解析能力 |
| Gemma 3 | `gemma3:12b` | 12B | 更好的推理能力、較慢 |
| Gemma 3 | `gemma3:27b` | 27B | 最高品質、需要較大 VRAM |
| Llama 3.2 | `llama3.2:3b` | 3B | 輕量、解析挑戰較多 |
| DeepSeek R1 | `deepseek-r1:8b` | 8B | 思維鏈推理 |

---

## 延伸閱讀

- **[主 README](../README_zh.md)**：框架概覽與架構
- **[實驗設計指南](../docs/guides/experiment_design_guide.md)**：如何設計新實驗
- **[代理人組裝指南](../docs/guides/agent_assembly_zh.md)**：如何配置認知堆疊層級
