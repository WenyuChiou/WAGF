# Governed Broker Framework

<div align="center">

**LLM 驅動水社會代理人模型的治理中間件**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/Ollama-Local_Inference-000000?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)

[**English**](README.md) | [**中文**](README_zh.md)

</div>

## 核心使命

> _「將 LLM 從故事講述者轉變為水社會代理人模型中的理性行動者。」_

**Governed Broker Framework** 旨在解決大型語言模型 (LLM) 代理人的根本性 **邏輯-行動差距 (Logic-Action Gap)**：LLM 雖然能生成流暢的自然語言推理，但在長跨度模擬中會出現隨機不穩定、幻覺與記憶沖蝕等問題——這些問題嚴重損害了 LLM 驅動之代理人模型 (ABMs) 的科學有效性。

本框架提供了一個架構級的 **治理層 (Governance Layer)**，負責實時驗證代理人的推理過程是否符合物理約束與行為理論（例如保護動機理論, PMT）。它專為**洪水風險適應研究**及其他水社會建模情境而設計，強調可重現性、可審計性及長跨度一致性。

**目標領域**：非穩態洪水風險、家戶適應行為、社區韌性、水資源政策評估。

---

## 快速上手

### 1. 安裝

```bash
pip install -r requirements.txt
```

### 2. 執行治理洪水模擬

啟動一個 10 人的洪水適應示範，含治理與以人為本的記憶系統（需要 [Ollama](https://ollama.com/)）：

```bash
python examples/governed_flood/run_experiment.py --model gemma3:4b --years 3 --agents 10
```

### 3. 執行完整基準測試（JOH 論文）

複製三組消融研究（100 代理人，10 年）：

```bash
python examples/single_agent/run_flood.py --model gemma3:4b --years 10 --agents 100 \
    --memory-engine humancentric --governance-mode strict --use-priority-schema
```

### 4. 探索更多

| 範例 | 複雜度 | 說明 | 連結 |
| :--- | :--- | :--- | :--- |
| **Governed Flood** | 入門 | 獨立的 Group C 示範，含完整治理 | [前往](examples/governed_flood/) |
| **Single Agent** | 中階 | JOH 基準測試：Groups A/B/C 消融研究 | [前往](examples/single_agent/) |
| **Multi-Agent** | 進階 | 社會動態、保險市場、政府政策 | [前往](examples/multi_agent/) |
| **Finance** | 延伸 | 跨領域示範（投資組合決策） | [前往](examples/finance/) |

---

## 模組導覽大廳（文件中心）

本框架分為五個概念章節，每章皆有雙語文件：

- **第 0 章 — 理論基礎**: [總覽](docs/modules/00_theoretical_basis_overview_zh.md) | [English](docs/modules/00_theoretical_basis_overview.md)
- **第 1 章 — 記憶與反思**: [記憶與驚奇引擎](docs/modules/memory_components_zh.md) | [反思引擎](docs/modules/reflection_engine_zh.md)
- **第 2 章 — 核心治理**: [治理邏輯與驗證器](docs/modules/governance_core_zh.md)
- **第 3 章 — 感知與上下文**: [上下文構建器](docs/modules/context_system_zh.md) | [模擬引擎](docs/modules/simulation_engine_zh.md)
- **第 4 章 — 技能註冊表**: [動作本體論](docs/modules/skill_registry_zh.md)
- **基準測試**: [範例與基準](examples/README_zh.md)

---

## 文檔與指南

### 整合指南 (`docs/guides/`)

- **[實驗設計指南](docs/guides/experiment_design_guide.md)**：建構新實驗的食譜。
- **[代理人組裝指南](docs/guides/agent_assembly_zh.md)**：如何堆疊「認知積木」（Level 1-3）。
- **[自定義指南](docs/guides/customization_guide.md)**：新增技能、驗證器與審計欄位。

### 架構規格 (`docs/architecture/`)

- **[高階架構圖](docs/architecture/architecture.md)**：系統圖表與資料流。
- **[技能架構詳解](docs/architecture/skill_architecture.md)**：動作/技能本體論的深度解析。
- **[MAS 五層映射](docs/architecture/mas-five-layers.md)**：多代理人系統架構（AgentTorch 對齊）。

### 多代理人生態系統 (`docs/multi_agent_specs/`)

- **[政府代理人](docs/multi_agent_specs/government_agent_spec.md)**：補貼、收購與政策邏輯。
- **[保險市場](docs/multi_agent_specs/insurance_agent_spec.md)**：保費計算與風險模型。
- **[機構行為](docs/multi_agent_specs/institutional_agent_behavior_spec.md)**：互動協議規範。

---

## 核心問題陳述

![核心挑戰與解決方案](docs/challenges_solutions_v3.png)

LLM 驅動的 ABM 面臨五個反覆出現的問題，本框架逐一解決：

| 挑戰 | 問題描述 | 框架解決方案 | 組件 |
| :--- | :--- | :--- | :--- |
| **幻覺** | LLM 產生無效動作（例如「造牆」） | **嚴格註冊表**：僅接受已註冊的 `skill_id` | `SkillRegistry` |
| **上下文限制** | 無法將完整歷史塞入提示詞 | **顯著性記憶**：僅檢索 Top-k 相關的過去事件 | `MemoryEngine` |
| **不一致性** | 決策與推理矛盾（邏輯漂移） | **思考驗證器**：檢查 TP/CP 與 Choice 之間的邏輯連貫性 | `SkillBrokerEngine` |
| **不透明決策** | 「為什麼代理人 X 做了 Y？」行為佚失 | **結構化軌跡**：完整記錄輸入、推理、驗證與結果 | `AuditWriter` |
| **不安全變更** | LLM 輸出破壞模擬狀態 | **沙盒執行**：獲准技能由引擎執行，而非 LLM 直接修改 | `SimulationEngine` |

---

## 統一架構 (v3.3)

本框架採用分層中間件方法，將單代理人的孤立推理與多代理人社會模擬進行了統一。

![Unified Architecture v3.3](docs/architecture.png)

### 組合式智能（「蓋積木」架構）

本框架採用 **堆疊積木 (Stacking Blocks)** 設計。您可以像玩樂高一樣，將不同的認知模組疊加在基礎執行引擎上，打造出不同複雜度的代理人：

| 堆疊層級 | 認知積木 | 功能 | 效果 |
| :--- | :--- | :--- | :--- |
| **底座** | **執行引擎** | _身體_ | 能夠執行物理動作，但沒有記憶或理性。 |
| **+ Level 1** | **感知透鏡** | _眼睛_ | 加入有界感知（視窗記憶）。防止 LLM 因歷史過長而當機。 |
| **+ Level 2** | **記憶引擎** | _海馬迴_ | 加入**通用認知架構 (v3)**。包含驚喜驅動的系統 1/2 切換與創傷優先檢索。 |
| **+ Level 3** | **技能仲裁** | _超我_ | 加入**治理機制**。強制執行 "Thinking Rules"，確保行為符合信念（理性驗證）。 |

> **為什麼這對研究很重要**：此設計支持受控消融研究。運行 Level 1 Agent（Group A — 基準組）對比 Level 3 Agent（Group C — 完整組），精確區分出_哪一個_認知組件解決了特定的行為偏差。

**[學習如何組裝自定義代理人](docs/guides/agent_assembly_zh.md)**

### 框架演進

![框架演進](docs/framework_evolution.png)

記憶與治理架構經歷了三個演進階段：

- **v1 (舊版)**：[可得性捷思] — 單一視窗記憶模式（Group A/B 基準）。
- **v2 (加權)**：[情境依賴記憶] — 模組化 `SkillBrokerEngine` 與**加權優先級檢索** ($S = W_{rec}R + W_{imp}I + W_{ctx}C$)。
- **v3 (最新)**：[雙系統理論與主動推理] — **通用認知架構（驚喜引擎）**。
  - **動態切換**：根據預測誤差 ($PE$) 自動在系統一（習慣）與系統二（理性）之間切換。
  - **狀態-心智耦聯**：環境現實 ($R$) 與心理預期 ($E$) 直接驅動認知喚起程度。
  - **可解釋審計**：提供完整的邏輯軌跡，解釋「代理人為何想起這件事/選擇此行動」。

**[深度解析：記憶優先級與檢索數學](docs/modules/memory_components_zh.md)**

### 提供者層與適配器

| 組件 | 檔案 | 說明 |
| :--- | :--- | :--- |
| **UnifiedAdapter** | `model_adapter.py` | 智能解析：處理特定模型的怪癖（例如 DeepSeek `<think>` 標籤、Llama JSON 格式） |
| **LLM Utils** | `llm_utils.py` | 集中式 LLM 調用，具備穩健錯誤處理與詳細程度控制 |
| **OllamaProvider** | `ollama.py` | 預設的本地推理提供者 |

### 驗證器層

治理規則分為 2x2 矩陣：

| 維度 | **嚴格（阻止並重試）** | **啟發式（警告並記錄）** |
| :--- | :--- | :--- |
| **物理 / 身份規則** | _不可能的動作_（例：已加高房屋卻再次加高） | _可疑狀態_（例：富裕代理人卻選擇什麼都不做） |
| **心理 / 思考規則** | _邏輯謬誤_（例：高威脅 + 低成本 → 什麼都不做） | _行為異常_（例：極度焦慮卻延遲行動） |

**實作方式**：身份規則檢查當前狀態（來自 `StateManager`）。思考規則檢查 LLM 推理的內部一致性（來自 `SkillProposal`）。

---

## 進階記憶與技能檢索 (v3.2)

為了處理長期模擬（10 年以上），v3.2 引入了**分層記憶系統**與**動態技能檢索 (RAG)**，確保代理人在不超過 LLM 上下文限制的情況下保持決策一致性。

### 分層記憶

記憶不再是簡單的滑動窗口，而是分為三個功能層級：

- **CORE（語義記憶）**：固定的代理人屬性（收入、人格特質、治理配置文件）。
- **HISTORIC（情節摘要）**：長期壓縮的重大事件歷史（例如：特定洪水影響）。
- **RECENT（情節記憶）**：高解析度的最近幾年記錄。

### 上下文感知技能檢索 (RAG)

對於擁有多種備選動作的模擬，框架使用 **SkillRetriever** 僅將最相關的動作注入 Prompt：

- **自適應精度**：根據當前情境過濾無關技能（例如：當威脅程度高時，優先檢索搬遷相關技能），降低 LLM 認知負荷。
- **基準測試相容**：使用 `WindowMemoryEngine` 時，系統自動禁用 RAG，以便與舊版基準（v1.0/v3.1）進行公平對比。

---

## 認知架構與設計哲學

**Context Builder** 不僅是一個資料管道；它是一個經過精心設計的**「認知透鏡」**，用於建構現實以減輕 LLM 的幻覺與認知偏誤。

### 1. 結構性偏誤緩解

我們透過 Prompt 工程來對抗已知的 LLM 限制：

- **Scale Anchoring（「浮動 M」問題）**：3B-4B 模型在長文本中容易失去符號與定義的連結。
  - **設計**：使用**行內語意錨定**（例如 `TP=M(Medium)` 而非僅 `TP=M`）來強制即時理解。
- **Option Primacy Bias**：LLM 在統計上傾向選擇列表中的第一個選項。
  - **設計**：`Context Builder` 實作**動態選項洗牌**，確保 "Do Nothing" 或 "Buy Insurance" 不會因位置而獲得不公平優勢。
- **「金魚腦效應」（Recency Bias）**：資訊過載時，模型會忘記早期指令。
  - **設計**：使用**分層上下文階層** (`Personal State -> Local Observation -> Global Memory`)，將生存關鍵數據放在最接近決策區塊的位置。

### 2. 邏輯-行動驗證器與可解釋反饋循環

- **挑戰**：「邏輯-行動差距」。小型 LLM 經常輸出「威脅非常高 (VH)」的推理，但卻因語法困惑或獎勵偏誤而選擇「不採取行動」。
- **解決方案**：**SkillBrokerEngine** 實作**遞歸反饋循環**：
  1. **偵測**：驗證器掃描解析後的結果。若 `TP=VH` 但 `Action=Do Nothing`，則產生 `InterventionReport`。
  2. **注入**：框架提取具體違規原因，注入**重試提示詞**。
  3. **指令**：告知 LLM：_「您之前的回應因邏輯不一致被拒絕。原因如下：[違規描述]。請重新考慮。」_
  4. **軌跡**：治理引擎與 LLM 之間的完整交互記錄在 `AuditWriter` 中。

---

## 記憶架構

![Human-Centric Memory System](docs/human_centric_memory_diagram.png)

**Human-Centric Memory Engine** (v3.3) 解決了「金魚腦效應」，根據**情感顯著性**而非僅時間新近度來優先處理記憶。它包含一個**反思引擎**，能將年度經歷整合為長期洞察。

### 核心功能

1. **優先級驅動檢索**：Context Builder 根據檢索分數 $S = (W_{rec} \cdot S_{rec}) + (W_{imp} \cdot S_{imp}) + (W_{ctx} \cdot S_{ctx})$ 動態注入記憶。確保即便時間久遠的創傷或與現狀匹配的事實能被 LLM 看見。
2. **反思迴圈**：年度事件整合為通用「洞察」（初始權重 $I=10.0$ 以抵抗衰減）。
3. **有界上下文**：將數千條日誌精煉為節省 Token 的提示詞，優先保障準確性。

### 分層記憶路線圖（v4 目標）

| 層級 | 組件 | 功能（理論） |
| :--- | :--- | :--- |
| **1** | **工作記憶** | **感覺緩衝器**。即時上下文（最近 5 年）。 |
| **2** | **情節摘要** | **海馬迴**。長期儲存「重大」事件（Phase 1/2 邏輯）。 |
| **3** | **語義洞察** | **新皮質**。從反思中萃取的抽象「規則」（例如「保險很重要」）。 |

**[閱讀完整的記憶與反思規格說明](docs/modules/memory_components_zh.md)**

---

## 狀態管理

### 狀態所有權（多代理人）

| 狀態類型 | 範例 | 範圍 | 讀取 | 寫入 |
| :--- | :--- | :--- | :--- | :--- |
| **Individual** | `memory`, `elevated`, `has_insurance` | 代理人私有 | 僅自己 | 僅自己 |
| **Social** | `neighbor_actions`, `last_decisions` | 可觀察鄰居 | 鄰居 | 系統 |
| **Shared** | `flood_occurred`, `year` | 所有代理人 | 全部 | 系統 |
| **Institutional** | `subsidy_rate`, `policy_mode` | 所有代理人 | 全部 | 僅政府 |

> **重點**：`memory` 是 **Individual** — 每個代理人有自己的記憶，不共享。

---

## 驗證管線

| 階段 | 驗證器 | 檢查 |
| :--- | :--- | :--- |
| 1 | Admissibility | 技能存在？代理人有資格使用此技能？ |
| 2 | Feasibility | 前置條件滿足？（例如，尚未加高） |
| 3 | Constraints | 一次性或年度限制？ |
| 4 | Effect Safety | 狀態變更有效？ |
| 5 | PMT Consistency | 推理與決策一致？ |
| 6 | Uncertainty | 回應有信心？ |

---

## 領域中立配置 (v3.3)

所有領域專屬邏輯集中於 `agent_types.yaml`。框架本身對模擬領域無關：

```yaml
# agent_types.yaml - 解析與記憶配置
parsing:
  decision_keywords: ["decision", "choice", "action"]
  synonyms:
    tp: ["severity", "vulnerability", "threat", "risk"]
    cp: ["efficacy", "self_efficacy", "coping", "ability"]

memory_config:
  emotional_weights:
    critical: 1.0   # 洪水損害、創傷
    major: 0.9      # 重大生活決策
    positive: 0.8   # 成功的適應
    routine: 0.1    # 日常噪音

  source_weights:
    personal: 1.0   # 直接經歷「我看到...」
    neighbor: 0.7   # 「我的鄰居做了...」
    community: 0.5  # 「新聞說...」

  # 上下文優先級權重
  priority_schema:
    flood_depth: 1.0     # 最高：物理現實
    savings: 0.8         # 財務現實
    risk_tolerance: 0.5  # 心理因素
```

---

## 實驗驗證與基準測試

本框架透過 **JOH 基準測試**（Journal of Hydrology）進行驗證，為三組消融研究，用以隔離每個認知組件的貢獻：

| 組別 | 記憶引擎 | 治理 | 目的 |
| :--- | :--- | :--- | :--- |
| **A（基準）** | 無 | 停用 | 原始 LLM 輸出 — 無記憶、無驗證 |
| **B（治理）** | Window | 嚴格 | 治理效果隔離 — 無記憶但理性 |
| **C（完整認知）** | HumanCentric + Priority | 嚴格 | 完整系統，含情感顯著性與創傷回憶 |

### 單代理人 vs. 多代理人比較

| 維度 | 單代理人 | 多代理人 |
| :--- | :--- | :--- |
| 狀態 | 僅 Individual | Individual + Social + Shared + Institutional |
| 代理人類型 | 1（家戶） | N（家戶、政府、保險公司） |
| 可觀察 | 僅自己 | 自己 + 鄰居 + 社區統計 |
| 上下文 | 直接 | Context Builder + Social Module |
| 使用案例 | 基礎 ABM | 具社會動態的政策模擬 |

### 已驗證模型 (v3.3)

| 模型族 | 變體 | 使用案例 |
| :--- | :--- | :--- |
| **Google Gemma** | 3-4B, 3-12B, 3-27B | 主要基準測試模型（JOH 論文） |
| **Meta Llama** | 3.2-3B-Instruct | 輕量邊緣代理人 |
| **DeepSeek** | R1-Distill-Llama-8B | 高推理（CoT）任務 |

**[完整實驗細節](examples/single_agent/)**

---

## 實務挑戰與經驗教訓

### 1. 解析崩潰（語法 vs. 語意）

**挑戰**：小型語言模型（3B-4B 參數）在 Prompt 密集時頻繁出現「語法崩潰」。可能輸出無效 JSON、巢狀物件而非扁平鍵值、或未加引號的字串。

**洞察**：我們從嚴格 JSON 解析轉向**多層防禦式解析**策略：封閉標記提取 -> JSON 修復（補齊引號/逗號）-> 關鍵字正規表達式 -> 最後手段數字提取。

### 2. 治理死區

**挑戰**：當治理規則形成狹窄的「行動漏斗」（例如：TP=H 阻止「什麼都不做」，CP=L 阻止「加高」和「搬遷」），代理人可能只剩一個有效動作，失去有意義的選擇。

**洞察**：我們區分 **ERROR** 規則（阻止動作並觸發重試）與 **WARNING** 規則（允許動作通過但在審計軌跡中記錄觀察）。這在保持科學可觀測性的同時維護了代理人自主性。

---

## 參考文獻 (APA)

本架構植基於並貢獻於以下文獻：

### 行為理論
1. **Rogers, R. W.** (1983). Cognitive and physiological processes in fear appeals and attitude change: A revised theory of protection motivation. _Social Psychophysiology_.
2. **Trope, Y., & Liberman, N.** (2010). Construal-level theory of psychological distance. _Psychological Review_, 117(2), 440.
3. **Tversky, A., & Kahneman, D.** (1973). Availability: A heuristic for judging frequency and probability. _Cognitive Psychology_, 5(2), 207-232.
4. **Ebbinghaus, H.** (1885). _Memory: A Contribution to Experimental Psychology_. (遺忘曲線基礎).

### 洪水風險與適應
5. **Siegrist, M., & Gutscher, H.** (2008). Natural hazards and motivation for self-protection: Memory matters. _Risk Analysis_, 28(3), 771-778.
6. **Bubeck, P., Botzen, W. J. W., & Aerts, J. C. J. H.** (2012). A review of risk perceptions and other factors that influence flood mitigation behavior. _Risk Analysis_, 32(9), 1481-1495.
7. **Hung, C.-L. J., & Yang, Y. C. E.** (2021). Assessing adaptive irrigation impacts on water scarcity in nonstationary environments. _Water Resources Research_, 57(7), e2020WR028946.

### LLM 代理人與架構
8. **Park, J. S., ... & Bernstein, M. S.** (2023). Generative Agents: Interactive Simulacra of Human Behavior. _ACM CHI_.

---

## 授權

MIT
