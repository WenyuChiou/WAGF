# WAGF — Water Agent Governance Framework

<div align="center">

**LLM 驅動代理人模型的治理層。** 起初為人類-水資源耦合系統而建；目前框架已可外掛新領域 — 參考包涵蓋水資源（洪水/灌溉）、疫苗接種、社群媒體三類。

每個 LLM 決策都會經過驗證管線——領域規則、行為理論檢查、附帶針對性反饋的重試——才能修改模擬狀態。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://github.com/WenyuChiou/WAGF/actions/workflows/test.yml/badge.svg)](https://github.com/WenyuChiou/WAGF/actions/workflows/test.yml)
[![Ollama](https://img.shields.io/badge/Ollama-Local_Inference-000000?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)

[**English**](README.md) | [**中文**](README_zh.md)

</div>

## WAGF 是什麼？

WAGF 是 LLM 驅動代理人模型的治理層。**治理仲裁器 (Governance Broker)** 在每個 LLM 決策執行前，依據物理約束、行為理論和財務可行性進行驗證。無效決策觸發附帶具體反饋的重試迴路——不只是重新提示。最終結果：可審計、可重現的代理人行為，而非原始 LLM 輸出。

本框架附帶五個參考實作，涵蓋四種行為理論：水資源（保護動機理論驅動的洪水適應、雙評估驅動的灌溉管理）、疫苗接種決策（健康信念模型，單代理人與多代理人）、社群媒體動態（耳語傳播）。領域層為可插拔式 — 新領域只需提供 YAML 配置 + 一個 `DomainPack` 子類，無需修改 `broker/`。

## WAGF 跟其他框架（如 LangChain、Mesa）有何不同？

WAGF 處於不同的技術層次。最接近的同類是規則式 ABM 平台（Mesa、NetLogo）；WAGF 把它們從「規則式代理人」延伸到「LLM 驅動代理人」，同時保留執行前驗證的嚴謹性。

| 框架類別 | 範例 | 主要功能 | WAGF 獨有的差異 |
|:---|:---|:---|:---|
| LLM 提供者 SDK | Anthropic SDK、OpenAI SDK | 包裝 API 呼叫 | 在任何提供者之上加入領域驗證器 + 審計管線 |
| RAG 框架 | LangChain、LlamaIndex | 用檢索內容增強 LLM 上下文 | 驗證 LLM 的「輸出」，而非僅輸入 |
| 代理人協調框架 | LangGraph、AutoGen、CrewAI | 多步驟 LLM 工具呼叫迴圈 | 強制治理閘道在任何狀態變更前介入；不只是工具分派 |
| 規則式 ABM | Mesa、NetLogo | 以手寫規則的代理人模擬 | 相同模擬嚴謹度，但代理人是 LLM 驅動，且每個決策都被行為理論約束 |
| **WAGF** ⭐ | （本專案）| **LLM 驅動代理人模型的治理層** | 驗證為一等公民、附反饋的重試、審計軌跡為科學產出 |

簡而言之：WAGF 不是 chatbot 框架，不是檢索工具，也不是 LLM SDK。它是研究級的鷹架，用於跑 LLM 代理人 ABM 實驗 — 每個決策必須通過領域物理、行為理論、制度約束驗證，且審計軌跡可重現到能直接附在論文 Supplementary Information。

## 核心特色

- **治理管線** — 任何動作到達模擬前的六步驟驗證：上下文 → LLM → 解析 → 驗證 → 核准/重試 → 執行
- **完整審計軌跡** — 每個決策、拒絕、重試及推理軌跡均以結構化 JSONL/CSV 記錄，供科學審查
- **領域包** — 新增領域只需 3 個檔案：`skill_registry.yaml` + `agent_types.yaml` + `lifecycle_hooks.py`
- **框架可參數化的行為理論** — `broker/` 內無硬編碼理論；參考包涵蓋保護動機理論（洪水）、雙評估（灌溉）、健康信念模型（疫苗）、社群動態（耳語）。新理論透過 YAML 宣告即可
- **研究就緒** — 消融模式（strict/relaxed/disabled）、6+ 個 LLM 系列的跨模型比較、多種子可重現性
- **AI 輔助工作流** — 內建 7 個 [Claude Code skills](docs/skills/wagf-skills.md)（`wagf-quickstart`、`wagf-domain-builder`、`wagf-coupling-designer`、`wagf-experiment-designer`、`llm-agent-audit-trace-analyzer`、`model-coupling-contract-checker`、`abm-reproducibility-checker`），新研究者從 `git clone` 到產出論文等級指標可不必先讀手冊

## 為什麼需要治理？

| 挑戰 | 會出什麼問題 | WAGF 解決方案 |
|:---|:---|:---|
| **幻覺** | LLM 捏造不存在的動作 | 嚴格技能註冊表：僅接受已註冊的動作 |
| **邏輯漂移** | 推理與選擇的動作矛盾 | 思考驗證器強制構念-行動一致性 |
| **上下文溢出** | 無法將完整歷史塞入提示詞 | 加權記憶檢索（依近期性 + 重要性 + 上下文取 top-k） |
| **不透明決策** | 無供科學審查的審計軌跡 | 結構化 JSONL 軌跡：輸入、推理、驗證、結果 |
| **不安全修改** | LLM 直接修改模擬狀態 | 仲裁器閘控執行：驗證通過的技能由引擎執行，非 LLM |

> **術語對照** — 程式碼裡稱為 `skill` 的概念，在 Nature Water
> 論文裡稱為 **action**（例如 `increase_demand`、`elevate_house`）。
> 兩者指同一件事：一個已註冊、經驗證的決策選項。`skill` 是早期
> 實作命名，貫穿整個原始碼樹（`SkillRegistry`、`skill_registry.yaml`）。

---

## 快速上手

### AI 輔助設定（首次使用者推薦）

在 [Claude Code](https://claude.ai/code) 開啟此 repo，輸入：

> 「I just cloned WAGF, help me set this up.」

`wagf-quickstart` skill 會帶你做環境檢查、2 分鐘 smoke test、並啟動第一個實驗（約 10 分鐘 + LLM 執行時間）。另外四個 skill 涵蓋完整研究流程：

| 需求 | Skill |
|------|-------|
| 規劃實驗 | `wagf-experiment-designer` |
| 建立新領域 | `wagf-domain-builder` |
| 設計外部模型耦合 | `wagf-coupling-designer` |
| 分析 audit traces | `llm-agent-audit-trace-analyzer` |
| 驗證外部模型耦合 | `model-coupling-contract-checker` |
| 投稿前 reproducibility 稽核 | `abm-reproducibility-checker` |

完整 skill 對照表見 [`docs/skills/wagf-skills.md`](docs/skills/wagf-skills.md)。所有 skill 都打包在 `.claude/skills/`，在 Claude Code 開啟此 repo 時會自動載入。

### 手動設定

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
broker/core/skill_broker_engine.py     — 六步驟治理管線
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

| 案例研究 | 行為理論 | 代理人 | 期間 | 領域 |
|:---|:---|:---|:---|:---|
| **洪水（單）** | PMT | 單代理人 | 13 年 | 帕塞伊克河流域，紐澤西州（水資源） |
| **洪水（多）** | PMT + 制度 | 402（200 屋主 + 200 租戶 + 政府 + 保險） | 13 年 | 帕塞伊克河流域，紐澤西州（水資源） |
| **灌溉** | 雙評估（WSA × ACA） | 78 個 CRSS 代理人 | 42 年 | 科羅拉多河流域（水資源） |
| **疫苗接種（單）** | 健康信念模型 (6 constructs) | 25 個文獻錨定代理人 | 5 年 | 公共衛生 Tier-2 showcase（3 seeds × 2 models） |
| **疫苗接種（多）** | HBM + 諮詢層級 | 1 衛生主管 + 2 社區組織 + N 個人 | 5 年 | 公共衛生概念驗證 |
| **耳語（社群媒體）** | 社群動態 | 1 版主 + K 影響者 + N 用戶 | 每日 | 社群媒體概念驗證 |

兩個洪水實驗使用來自水文模擬（2011-2023）的逐代理人洪水深度網格。灌溉實驗以 LLM 驅動的農民代理人重現 Hung & Yang (2021) 的科羅拉多河模擬系統設定。跨模型實驗在每個配置下以 3-5 個隨機種子比較不同 LLM 系列及規模的行為。後三個非水資源 demo（疫苗單／多、耳語）是較小的概念驗證參考包，用於演示非水資源插入路徑與多代理人耦合模式 — 不是研究級 ABM。

| 範例 | 說明 | 連結 |
|:---|:---|:---|
| **快速上手** | 治理迴路的漸進式教學 | [前往](examples/quickstart/) |
| **最小範本** | 新增領域的腳手架 | [前往](examples/minimal/) |
| **單代理人洪水** | 使用 PMT 的洪水適應 | [前往](examples/single_agent/) |
| **灌溉 ABM** | 稀缺條件下的水資源分配 | [前往](examples/irrigation_abm/) |
| **多代理人洪水** | 制度回饋（政府 + 保險 + 家戶） | [前往](examples/multi_agent/flood/) |
| **疫苗接種（單）** | 非水資源 Tier-2 showcase（HBM、25 agents、5 年 COVID-19 schedule、3 seeds × 2 models） | [前往](examples/vaccination_demo/) |
| **疫苗接種（多）** | 非水資源多代理人參考（3 種代理人類型、env-dict-whitelist 耦合） | [前往](examples/vaccination_ma_demo/) |
| **耳語（社群媒體）** | 每日節奏多代理人參考（版主 + 影響者 + 用戶） | [前往](examples/gossip_demo/) |

---

## 配置與擴展

所有領域特定值均從 YAML 載入。領域特定邏輯位於 `examples/<domain>/` 與 `broker/domains/<domain>/`；`broker/` 本體只保留框架邏輯。

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

*可選* — 若需自訂記憶分類、驗證器規則、漂移偵測器閾值或其他框架旋鈕，亦可繼承 `DomainPack` 並透過 `DomainPackRegistry.register(name, pack)` 註冊。預設 pack 為九個 hook（memory / drift / retrieval / perception / population-governance / policy-event-tiers / bridge-importance / event-handlers / agent-impact-handlers）提供 no-op stub，所以簡單領域可跳過此步驟。最小 DomainPack 範例參見 `examples/vaccination_demo/adapters/vaccination_pack.py`。

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
