# Governed Broker Framework

**🌐 Language / 語言: [English](README.md) | [中文](README_zh.md)**

<div align="center">

**LLM 驅動的 Agent-Based Model 治理中間件**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/Ollama-Local_Inference-000000?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)

</div>

---

## 📖 專案概覽

**Governed Broker Framework** 旨在解決 LLM 模擬中的「邏輯-行動差距 (Logic-Action Gap)」。雖然現代 LLM 具備極佳的流利性，但在長跨度模擬中常出現隨機不穩定、幻覺以及「記憶沖蝕 (Memory Erosion)」等問題。本框架提供了一個架構化的「超我 (Superego)」，負責驗證代理人的推理過程是否符合物理現實與制度規範。

![核心挑戰與解決方案](docs/challenges_solutions_v3.png)

---

## 🏗️ 系統架構

本框架被設計為位於代理人決策模型 (LLM) 與模擬環境 (ABM) 之間的**模組化認知中間件**。

![系統架構](docs/governed_broker_architecture_v3_1.png)

### 核心模組分解

| 模組                   | 角色                 | 位置                 | 說明                                     |
| :--------------------- | :------------------- | :------------------- | :--------------------------------------- |
| **`SkillRegistry`**    | 憲法 (Charter)       | `broker/core/`       | 定義動作空間、成本與物理限制。           |
| **`SkillBroker`**      | 法官 (Judge)         | `broker/core/`       | 驗證推理與行動的一致性規則。             |
| **`MemoryEngine`**     | 海馬迴 (Hippocampus) | `broker/components/` | 管理分層記憶（視窗、顯著性、以人為本）。 |
| **`ReflectionEngine`** | 反思 (Reflection)    | `broker/components/` | 進行高階語義固化（總結長期教訓）。       |
| **`ContextBuilder`**   | 感官 (Lens)          | `broker/components/` | 為提示詞合成有界的現實視圖。             |
| **`SimulationEngine`** | 世界 (World)         | `simulation/`        | 執行經核准的動作並管理環境演變。         |

---

## 🧠 目錄模組說明

### 1. 治理仲裁器 (`broker/`)

框架的核心調度器，處理「思考-行動」循環：

- **驗證器 (Validators)**：檢查 LLM 指標是否與決策相符。例如：若威脅評估為「高」但決策為「無作為」，則觸發自我修正。
- **審計軌跡 (Audit Trails)**：生成專業、機器可讀的決策全程追蹤。

### 2. 認知記憶層 (`broker/components/`)

靈感源自人類啟發式的記憶系統：

- **分層記憶 (Tiered Memory)**：區分近期（情節）與語義（長期）記憶。
- **反思引擎 (Reflection Engine)**：定期總結經驗為「長期教訓」。針對小模型 (Llama 3.2/Gemma) 優化了**多階段魯棒解析機制**。
- **顯著性檢索**：使用重要性/檢索公式抓取最相關的記憶片段。

### 3. 模擬環境 (`simulation/`)

模組化環境引擎，負責模擬外部衝擊（如：洪水）並計算物理後果（如：損害金額、保險理賠）。

### 4. 實驗套件 (`examples/`)

- **JOH (Just-In-Time Household)**：基準測試代理人在對抗性壓力下的適應性。
- **壓力測試馬拉松**：自動化腳本，測試跨年度的模型韌性。

---

## 🚀 快速上手

### 前置要求

- Python 3.10+
- [Ollama](https://ollama.com/) (用於本地 LLM 推理) 或 OpenAI API Key。

### 安裝步驟

```bash
git clone https://github.com/WenyuChiou/governed-broker-framework.git
cd governed-broker-framework
pip install -r requirements.txt
```

### 執行基準測試

執行標準的 10 年洪水適應基準測試：

```bash
python examples/single_agent/run_flood.py --model llama3.2:3b --years 10 --agents 100 --memory-engine humancentric
```

---

## 📊 實驗結果

### 以人為本的穩定性 (Group C)

最新基準測試顯示，**Governed Broker** 透過結構化反思，顯著降低了小模型在壓力下的「創傷放大」現象。

![隨機不穩定性視覺化](doc/images/Figure2_Stochastic_Instability.png)

---

## 🗺️ 發展藍圖

- [x] **v3.3**：針對 3B-7B 模型的「多階段魯棒反思解析」。
- [ ] **v3.4**：多代理人社交網絡影響傳播系統。
- [ ] **v4.0**：領域中立 (Domain-neutral) 的「思考守則」，用於廣義政策分析。

---

**聯絡方式**: [Wenyu Chiou](https://github.com/WenyuChiou)
