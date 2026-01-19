# 系統理論與架構詳解 (System Theory & Architecture Master Map)

![Cognitive Architecture Diagram](/c:/Users/wenyu/.gemini/antigravity/brain/9793af22-8e51-4316-9d6b-59ba45b8fe7a/cognitive_architecture_diagram_1768778927249.png)

這份文檔詳細解釋了框架中使用的每一個**專有名詞 (Term)**、其背後的**學術理論 (Theory)**、對應的**程式模組 (Module)**，以及整個系統是如何串聯運作的。

---

## 1. 名詞與理論詳解 (Detailed Dictionary)

### 1.1 可得性捷思 (Availability Heuristic)

- **定義**：心理學概念。人類判斷一件事發生的機率，不是看統計數據，而是看「多容易想起它」。如果有很深刻的創傷（如洪水），人就會高估災難再發的機率。
- **對應模組**：`broker/components/memory_engine.py`
- **實作方式**：
  - 我們使用 `Importance Score` (重要性分數) 來模擬這種「心理深刻度」。
  - 關鍵字 "Flood" 會觸發高分 (1.5)，導致這條記憶比 "Sunny Day" (0.1) 更難被遺忘。
  - **公式**：$S = I \times e^{-\lambda t}$ (時間越久忘越多，但創傷忘得慢)。

### 1.2 可配置的推論邏輯 (Configurable Reasoning Logic - e.g., PMT)

- **核心概念**：這是一個**可抽換的理論插槽 (Theory Slot)**。目前的設定是 PMT，但您可以隨意更換。
  - **例子**：若研究行為財務學，可換成 **展望理論 (Prospect Theory)**，要求代理人在決策時必須展現「損失規避 (Loss Aversion)」。
- **目前的實例 (PMT)**：保護動機理論 (Rogers, 1975)。人要採取防災決策，必須經過兩個認知評估 (威脅 vs 應對)。
- **對應模組**：`validators/agent_validator.py` + `agent_types.yaml`
- **實作方式**：
  - 我們在 `agent_types.yaml` 中定義 `thinking_rules`。
  - Validator 會檢查 LLM 的思考內容是否包含這兩個步驟。如果不包含，就判定為「不合規思考」並駁回。

### 1.3 有限理性 (Bounded Rationality)

- **定義**：經濟學概念 (Herbert Simon)。人不是完美的計算機，人的理性受限於資訊、時間和認知能力。
- **對應模組**：`broker/core/governance.py` (Governance Layer)
- **實作方式**：
  - 如果完全放任 LLM (Gemma/Llama)，它會產生幻覺或隨機行為 (完全不理性)。
  - 我們的 **Governance Layer** 就是那個「邊界 (Bound)」，它強迫代理人在一個合理的範圍內做決策，排除那些明顯錯誤的選項。

### 1.4 元認知與反思 (Metacognition & Reflexion)

- **定義**：認知科學概念。不僅僅是「思考」，而是「思考自己的思考」。
- **對應模組**：`broker/components/reflection_engine.py`
- **實作方式**：
  - 每天的行動是「反應 (Reaction)」。
  - 每年的總結是「反思 (Reflection)」。
  - 系統將一整年的日誌餵給 LLM，要求它：「找出你這一年學到的最大教訓。」產出的 **Insight (洞察)** 會成為永久記憶。

---

## 2. 模組對照表 (Mapping Table)

| 理論 (Theory)              | 程式模組 (Code)               | 檔案位置 (File)                        | 作用 (Function)                      |
| :------------------------- | :---------------------------- | :------------------------------------- | :----------------------------------- |
| **Availability Heuristic** | **HumanCentricMemoryEngine**  | `broker/components/memory_engine.py`   | 決定哪些記憶被檢索出來 (Retrieve)。  |
| **PMT**                    | **AgentValidator**            | `validators/agent_validator.py`        | 檢查思考邏輯是否合規 (Validate)。    |
| **Episodic Memory**        | **Path A (Raw Logs)**         | `experiment.py`                        | 紀錄客觀事實 (Record Facts)。        |
| **Semantic Memory**        | **Path B (ReflectionEngine)** | `reflection_engine.py`                 | 產生抽象智慧 (Generate Wisdom)。     |
| **Context Window**         | **ContextBuilder**            | `broker/components/context_builder.py` | 將記憶組合成 Prompt (Build Prompt)。 |

---

## 3. 系統運作流程 (How it Works Together)

這是一個代理人 (Agent) 在模擬環境中做出決策的**完整生命週期**，展示了所有模組如何協作：

### 步驟 1：感知 (Perception & Retrieval)

- **情況**：第 5 年，外面下大雨，水位 1.0ft。
- **Memory Engine (Availability Heuristic)**：
  - 系統掃描大腦，發現一條 3 年前的記憶：「第 2 年發大水，房子全毀 (Imp=1.5)」。
  - 雖然過了 3 年，但分數僅衰減至 1.1，依然很高。
  - **決定**：將這條「創傷記憶」強制注入 Prompt。

### 步驟 2：思考 (Reasoning with PMT)

- **Context Builder**：組合 Prompt：「你是 Agent 001，外面下雨，你記得以前淹過水。請決定行動。」
- **LLM (Gemma)**：開始思考。
  - _Draft 1_: "我覺得沒差，睡覺。" -> **Validator 攔截** (沒有評估威脅)。
  - _Retry_: "根據 PMT，外面下雨 + 我有創傷記憶 = **高威脅**。但我存款夠 = **高應對能力**。" -> **Validator 通過**。

### 步驟 3：行動 (Action)

- **LLM**：決定輸出 Action: `buy_insurance`。
- **Simulator**：執行扣款，更新狀態。

### 步驟 4：記憶固化 (Consolidation)

- **Path A**："Year 5: Bought Insurance due to fear." -> 存入 Raw Log。

### 步驟 5：反思 (Reflection - Night Phase)

- **一年結束**。
- **Reflection Engine (Reflexion)**：讀取日誌，LLM 總結：「我發現保險能讓我安心，即使要花錢。」
- **Path B**：這條「心得」被存入長期記憶，作為明年的決策依據。

---

## 4. 通用性與領域適配 (Universality & Domain Adaptation)

本框架是**可移植的中介軟體**，只要修改 YAML 設定檔即可適配不同領域。

### 4.1 跨領域對照表

| 認知層 (Layer)      | 水文學 (Current)      | 消費者行為 (Retail) | 行為財務學 (Finance)           |
| :------------------ | :-------------------- | :------------------ | :----------------------------- |
| **理論模型**        | **PMT** (保護動機)    | **TPB** (計畫行為)  | **Prospect Theory** (展望理論) |
| **關鍵字 (Memory)** | `["flood", "trauma"]` | `["scam", "waste"]` | `["crash", "loss"]`            |
| **思考規則**        | "評估威脅與應對"      | "評估CP值與口碑"    | "與參考點比較損益"             |
| **社會訊號**        | 鄰居是否墊高          | 網紅是否推薦        | 市場恐慌指數 (FOMO)            |

### 4.2 如何操作？

您只需要修改 `agent_types.yaml` 的 `emotion_keywords` 和 `thinking_rules` 即可。系統核心代碼 (**System Execution Layer**) 完全不需要更動。這一點證明了本研究貢獻在於「架構」而非單一案例。
