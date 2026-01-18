# JOH Cognitive Architecture Guide (JOH 認知架構學習指南)

本指南旨在解釋 **Governed Broker Framework** 核心的兩大認知機制：**技能註冊 (Skill Registry)** 與 **層次化記憶 (Hierarchical Memory)**。這兩個模組共同構成了 Agent 的 "System 2" (邏輯腦)，確保其行為既具備適應性 (Adaptive)，又符合物理現實 (Realistic)。

---

## 🏗️ Part 1: Skill Registry (技藝之書)

這就像是 Agent 的「合法動作手冊」。Agent 不能隨意創造動作，只能從這本手冊中選擇。這解決了 "Structure Hallucination" (結構性幻覺)。

### 1.1 核心概念 (Core Concepts)

- **Skill (技能)**: 一個具體的、有物理後果的動作。例如 `elevate_house` (墊高房屋)。
- **Validator (驗證器)**: 綁定在技能上的「法律條文」。如果 Agent 想要執行某技能，必須先通過驗證。
- **Instruction (指令)**: 告訴 LLM 這個技能是做什麼的，以及什麼時候該用。

### 1.2 設定檔結構 (`skill_registry.yaml`)

```yaml
agent_types:
  default_homeowner:
    skills:
      - name: "do_nothing"
        description: "Maintain current state."
        # validators: []  <-- 沒有驗證器，隨時可做

      - name: "buy_insurance"
        description: "Purchase flood insurance policy."
        validators:
          - "budget_constraint" # 錢夠嗎？
          - "cooldown_check" # 冷卻時間過了嗎？ (模擬保單期限)

      - name: "elevate_house"
        description: "Elevate the property to reduce flood risk."
        validators:
          - "budget_constraint" # 錢夠嗎？
          - "elevation_block" # 房子已經墊高過了嗎？ (One-time action)
          - "no_action_under_high_threat" # 防止癱瘓 (Paralysis check)
```

### 1.3 學習重點 (Key Takeaways)

1.  **分離控制 (Decoupling)**: 技能 logic (Python) 與技能 definition (YAML) 分離。你想增加新技能，只需改 YAML 和提供對應的 Python 函數。
2.  **自我修正 (Self-Correction)**: 當 Validator 拒絕 (Reject) 時，Broker 會將錯誤訊息 (e.g., "Insufficient Funds") 扔回給 LLM，強迫其重試。這就是 "System 2" 的運作方式。

---

## 🧠 Part 2: Hierarchical Memory (層次化記憶)

這就像是 Agent 的「創傷回憶錄」。解決了 "Goldfish Effect" (金魚效應，即 Agent 過兩年就忘記曾經發生的災難)。

### 2.1 核心概念 (Core Concepts)

這次我們放棄了標準的 RAG (Vector Search)，改用 **Human-Centric Heuristics (人性化啟發式)**。

- **Episodic Buffer (情節緩衝區)**: 模擬人類的工作記憶，只能容納最近 5 年的事情。
- **Semantic Consolidation (語義固化)**: 當某件事太重要 (e.g., 房子淹水)，它會被「燒錄」進長期記憶，即使過了 10 年也不會忘。
- **Retrieval Logic (檢索邏輯)**: 不是用 Embedding 相似度，而是用 **"Emotional Taxonomy" (情緒分類學)**。

### 2.2 情緒分類與權重 (Emotional Taxonomy)

我們定義了四種記憶來源，並賦予不同的權重 (Salience Score)：

| Source (來源)             | Weight (權重)  | 心理學意義 (Psychological Meaning)                           |
| :------------------------ | :------------- | :----------------------------------------------------------- |
| **Experience (親身經歷)** | **1.0 (最高)** | "Availability Heuristic" - 親身體驗最難忘 (e.g., 自家淹水)。 |
| **Neighbor (鄰居觀察)**   | 0.8            | "Social Proof" - 看到鄰居淹水，感同身受。                    |
| **Community (社區八卦)**  | 0.5            | "Distal Information" - 聽說社區有災情。                      |
| **News (新聞報導)**       | 0.3 (最低)     | "Abstract Info" - 電視上的災難，感覺很遙遠。                 |

### 2.3 檢索邏輯 (The Algorithm)

當 Agent 需要做決策時，記憶引擎會執行以下步驟：

1.  **Filter (過濾)**: 只看過去 $N$ 年 (Window Size) 的事件。
2.  **Score (評分)**: 計算每條記憶的 $Score = Weight \times Decay$。
    - $Decay$: 時間越久，記憶越淡 (Ebbinghaus Forgetting Curve)。
3.  **Inject (注入)**: 將 Score 最高的 Top-K 事件插入 Prompt。
4.  **Trauma Recall (創傷回溯)**: **[關鍵創新]** 如果某條舊記憶 (比如 8 年前的大水) 的 Score 即使經過 Decay 仍然很高 (因為初始 Weight=1.0)，它會被強制拉回 Prompt。

> **這就是為什麼我們的 Agent 能夠在第 10 年仍然記得第 2 年的水災，而 Baseline 模型早就忘光了。**

---

## 📚 Part 3: Learning Resources (延伸閱讀)

如果你想更深入了解這些機制背後的理論：

1.  **Skill Registry -> CoALA Architecture**
    - _Sumers et al. (2023). Cognitive Architectures for Language Agents._
    - 這篇論文定義了 Action Space 應該如何被結構化。

2.  **Hierarchical Memory -> Generative Agents**
    - _Park et al. (2023). Generative Agents: Interactive Simulacra of Human Behavior._
    - 史丹佛小鎮論文，我們借用了它的 Memory Stream 概念，但簡化了檢索邏輯以適應科學模擬。

3.  **Governance -> Protection Motivation Theory**
    - _Rogers (1975)_.
    - 這是所有 Validator 的理論基礎 (Threat Appraisal vs. Coping Appraisal)。

---

**使用建議**: 將此文檔存檔，未來若要增加新 Agent (e.g., 政府官員)，請參考 Part 1 修改 YAML；若要調整記憶衰退速度，請參考 Part 2 調整 Python 參數。
