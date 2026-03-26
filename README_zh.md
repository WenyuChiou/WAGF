# WAGF — Water Agent Governance Framework

<div align="center">

**LLM 驅動代理人模型的治理層，應用於人類-水資源耦合系統。**

每個 LLM 決策都會經過驗證管線——領域規則、行為理論檢查、附帶針對性反饋的重試——才能修改模擬狀態。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://github.com/WenyuChiou/WAGF/actions/workflows/test.yml/badge.svg)](https://github.com/WenyuChiou/WAGF/actions/workflows/test.yml)
[![Ollama](https://img.shields.io/badge/Ollama-Local_Inference-000000?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)

[**English**](README.md) | [**中文**](README_zh.md)

</div>

## WAGF 是什麼？

WAGF 是 LLM 驅動代理人模型的治理層。**治理仲裁器 (Governance Broker)** 在每個 LLM 決策執行前，依據物理約束、行為理論和財務可行性進行驗證。無效決策觸發附帶具體反饋的重試迴路——不只是重新提示。最終結果：可審計、可重現的代理人行為，而非原始 LLM 輸出。

本框架附帶兩個水資源領域的參考實作（洪水適應與灌溉管理），並可透過外掛系統擴展至其他 ABM 領域。

## 核心特色

- **治理管線** — 任何動作到達模擬前的 6 階段驗證：上下文 → LLM → 解析 → 驗證 → 核准/重試 → 執行
- **完整審計軌跡** — 每個決策、拒絕、重試及推理軌跡均以結構化 JSONL/CSV 記錄，供科學審查
- **領域包** — 新增領域只需 3 個檔案：`skill_registry.yaml` + `agent_types.yaml` + `lifecycle_hooks.py`
- **可插拔行為理論** — 內建保護動機理論 (PMT)；可透過 YAML 配置替換或擴展
- **研究就緒** — 消融模式（strict/relaxed/disabled）、6+ 個 LLM 系列的跨模型比較、多種子可重現性

## 為什麼需要治理？

| 挑戰 | 會出什麼問題 | WAGF 解決方案 |
|:---|:---|:---|
| **幻覺** | LLM 捏造不存在的動作 | 嚴格技能註冊表：僅接受已註冊的動作 |
| **邏輯漂移** | 推理與選擇的動作矛盾 | 思考驗證器強制構念-行動一致性 |
| **上下文溢出** | 無法將完整歷史塞入提示詞 | 加權記憶檢索（依近期性 + 重要性 + 上下文取 top-k） |
| **不透明決策** | 無供科學審查的審計軌跡 | 結構化 JSONL 軌跡：輸入、推理、驗證、結果 |
| **不安全修改** | LLM 直接修改模擬狀態 | 仲裁器閘控執行：驗證通過的技能由引擎執行，非 LLM |

---

## 快速上手

### 前置需求

- Python 3.10+
- [Ollama](https://ollama.com/download)（本地 LLM 推理，可選；有 mock 模式可用）

```bash
# 克隆並安裝
git clone https://github.com/WenyuChiou/WAGF.git
cd WAGF
pip install -e ".[llm]"

# 試試 mock 示範（不需要 Ollama）
python examples/quickstart/01_barebone.py

# 使用真實 LLM 執行
ollama pull gemma3:4b
python examples/single_agent/run_flood.py --model gemma3:4b --years 3 --agents 10
```

**雲端 LLM 提供者**（不需要本地 GPU）：

```bash
--model anthropic:claude-sonnet-4-5    # 需要 ANTHROPIC_API_KEY
--model openai:gpt-4o                  # 需要 OPENAI_API_KEY
--model gemini:gemini-2.5-flash        # 需要 GOOGLE_API_KEY
```

### 每一步發生了什麼

來自洪水模擬的具體軌跡：

```text
第 3 年，代理人 #42（低收入屋主，高洪水風險區）：

  LLM 提議：elevate_home（費用 $30,000）
    物理驗證器：  通過  （尚未加高）
    思考驗證器：  錯誤 — 威脅評估=中等，但選擇了最昂貴的動作
    → 附帶反饋重試：「您的威脅評估為中等。請考慮保險（$1,200/年）
      是否更符合您的風險評估。」

  LLM 提議（重試 1）：buy_insurance（$1,200/年）
    物理驗證器：  通過
    思考驗證器：  通過  （中等威脅 → 適度動作）
    個人驗證器：  通過  （收入 $35,000 > 保費 $1,200）
    社會驗證器：  警告 — 70% 的鄰居未採取行動（記錄）
    核准 → 由模擬引擎執行

  審計軌跡：year=3, agent=42, proposed=elevate_home, rejected,
               retry=1, final=buy_insurance, approved
```

---

## 架構

```text
┌─────────────────────────────────────────────────┐
│                治理仲裁器 (Governance Broker)      │
│                                                  │
│  1. 上下文組裝（記憶 + 狀態 + 社會）              │
│  2. LLM 推理（任意提供者）                        │
│  3. 輸出解析（JSON/enclosure 擷取）               │
│  4. 驗證（物理 → 思考 → 個人                      │
│           → 社會 → 語義）                         │
│  5. 核准或重試（附帶針對性反饋）                   │
│  6. 執行 + 審計                                   │
│                                                  │
│  若步驟 4 回傳 ERROR → 返回步驟 2                 │
│  若步驟 4 回傳 WARNING → 記錄並繼續               │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│                  執行環境                         │
│                                                  │
│  生命週期：pre_year → 代理人決策 →                │
│            post_step → post_year → 下一年         │
│                                                  │
│  領域配置：skill_registry.yaml                    │
│            agent_types.yaml                       │
│            lifecycle_hooks.py                     │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│                 支援子系統                         │
│                                                  │
│  記憶      加權檢索、整合                          │
│  上下文    分層提示詞（核心/歷史/近期）             │
│  社會      鄰里傳聞、新聞媒體、社群媒體            │
│  反思      定期 LLM 驅動的記憶整合                 │
└─────────────────────────────────────────────────┘
```

**關鍵入口檔案：**

```text
broker/core/skill_broker_engine.py     — 6 階段治理管線
broker/core/experiment.py              — ExperimentRunner + Builder API
broker/validators/governance/          — 6 類驗證器實作
broker/components/memory/              — 記憶引擎 ABC + 各實作
broker/components/context/             — 上下文組裝鏈
examples/quickstart/                   — 漸進式教學
```

### 組合式代理人設計

透過堆疊模組，建構不同認知複雜度的代理人，以進行受控實驗：

| 層級 | 新增組件 | 效果 |
|:---|:---|:---|
| **底座** | 執行引擎 | 可執行動作，無記憶或推理 |
| **+ Level 1** | 上下文 + 視窗記憶 | 對近期事件的有限感知 |
| **+ Level 2** | 加權記憶 | 情緒編碼、整合、衰減 |
| **+ Level 3** | 治理仲裁器 | 決策必須通過領域規則驗證 |

運行 Level 1（無治理）對比 Level 3（完整治理），以隔離驗證對代理人行為的影響。

---

## 參考實作

| 案例研究 | 代理人 | 期間 | 測試模型 | 研究區域 |
|:---|:---|:---|:---|:---|
| **洪水家戶** | 單代理人 | 13 年 | Gemma 3 (4B/12B/27B) | 帕塞伊克河流域，紐澤西州 |
| **洪水多代理人** | 402（200 屋主 + 200 租戶 + 政府 + 保險） | 13 年 | Gemma 3 4B | 帕塞伊克河流域，紐澤西州 |
| **灌溉** | 78 個 CRSS 代理人 | 42 年 | Gemma 3 4B, Ministral 3B, Gemma 3 12B | 科羅拉多河流域 |

洪水實驗使用來自水文模擬（2011-2023）的逐代理人洪水深度網格。灌溉實驗以 LLM 驅動的農民代理人重現 Hung & Yang (2021) 的科羅拉多河模擬系統設定。跨模型實驗在每個配置下以 3-5 個隨機種子比較不同 LLM 系列及規模的行為。

| 範例 | 說明 | 連結 |
|:---|:---|:---|
| **快速上手** | 治理迴路的漸進式教學 | [前往](examples/quickstart/) |
| **最小範本** | 新增領域的腳手架 | [前往](examples/minimal/) |
| **單代理人洪水** | 使用 PMT 的洪水適應 | [前往](examples/single_agent/) |
| **灌溉 ABM** | 稀缺條件下的水資源分配 | [前往](examples/irrigation_abm/) |
| **多代理人洪水** | 制度回饋（政府 + 保險 + 家戶） | [前往](examples/multi_agent/flood/) |

---

## 配置與擴展

所有領域特定值均從 YAML 載入。`broker/` 中零硬編碼領域邏輯。

| 您想變更的內容 | 僅 YAML | 需要 Python |
|:---|:---:|:---:|
| 新增/移除技能（動作） | 是 | 否 |
| 定義代理人類型與人設 | 是 | 否 |
| 新增/修改治理規則 | 是 | 否 |
| 調整記憶參數 | 是 | 否 |
| 變更 LLM 模型或提供者 | 是 | 否 |
| 新增領域驗證器 | 否 | 是 |
| 新增記憶引擎 | 否 | 是 |
| 新增 LLM 提供者 | 否 | 是 |

**新增領域**需提供三個檔案：
1. `skill_registry.yaml` — 可用動作及其前置條件
2. `agent_types.yaml` — 人設定義、構念標籤、治理規則
3. `lifecycle_hooks.py` — 繼承 `BaseLifecycleHooks` 處理環境轉換

### 程式化 API

```python
from broker.core.experiment import ExperimentBuilder
from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine

runner = (
    ExperimentBuilder()
    .with_model("gemma3:4b")
    .with_years(13)
    .with_agents(agents)
    .with_simulation(sim_engine)
    .with_skill_registry("config/skill_registry.yaml")
    .with_governance("strict", "config/agent_types.yaml")
    .with_memory_engine(HumanCentricMemoryEngine(ranking_mode="weighted"))
    .with_seed(42)
    .build()
)
runner.run()
```

詳見 [自定義指南](docs/guides/customization_guide.md)、[實驗設計指南](docs/guides/experiment_design_guide.md) 與 [領域包指南](docs/guides/domain_pack_guide.md)。

---

## 文件

**入門**：[快速上手指南](docs/guides/quickstart_guide.md) | [實驗設計](docs/guides/experiment_design_guide.md) | [領域包](docs/guides/domain_pack_guide.md) | [疑難排解](docs/guides/troubleshooting_guide.md)

**指南**：[代理人組裝](docs/guides/agent_assembly.md) | [自定義](docs/guides/customization_guide.md) | [多代理人設定](docs/guides/multi_agent_setup_guide.md) | [進階模式](docs/guides/advanced_patterns.md) | [YAML 參考](docs/references/yaml_configuration_reference.md)

**架構**：[系統總覽](docs/architecture/architecture.md) | [技能管線](docs/architecture/skill_architecture.md) | [治理核心](docs/modules/governance_core.md) | [記憶系統](docs/modules/memory_components.md)

**理論**：[理論基礎](docs/modules/00_theoretical_basis_overview.md) | [技能註冊表](docs/modules/skill_registry.md)

| 讀者類型 | 建議起點 |
|:---|:---|
| **研究者**（想試用） | [快速上手](docs/guides/quickstart_guide.md) → [範例](examples/README.md) → [實驗設計](docs/guides/experiment_design_guide.md) |
| **開發者**（擴展框架） | [架構](docs/architecture/architecture.md) → [自定義](docs/guides/customization_guide.md) → [領域包](docs/guides/domain_pack_guide.md) |

---

## 引用方式

```bibtex
@article{wagf2026,
  title={Water Agent Governance Framework: Governing LLM-Driven Agent-Based Models for Water Resources},
  author={Chiou, Wenyu and Yang, Y. C. Ethan},
  year={2026},
  note={Manuscript in preparation}
}
```

## References

1. Rogers, R. W. (1983). Cognitive and physiological processes in fear appeals and attitude change: A revised theory of protection motivation. *Social Psychophysiology*.
2. Grimm, V., et al. (2005). Pattern-oriented modeling of agent-based complex systems. *Science*, 310(5750), 987-991.
3. Park, J. S., et al. (2023). Generative Agents: Interactive Simulacra of Human Behavior. *ACM CHI*.
4. Hung, C.-L. J., & Yang, Y. C. E. (2021). Assessing adaptive irrigation impacts on water scarcity in nonstationary environments. *Water Resources Research*, 57(7).
5. Bubeck, P., Botzen, W. J. W., & Aerts, J. C. J. H. (2012). A review of risk perceptions and other factors that influence flood mitigation behavior. *Risk Analysis*, 32(9), 1481-1495.

---

## 授權

MIT
