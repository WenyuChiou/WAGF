# 🧠 認知架構詳解：檢索與記憶系統 (Retrieval & Memory)

在這個框架中，我們設計了一套 **"以人為本 (Human-Centric)"** 的記憶機制，這與一般 AI 應用中常見的 RAG (檢索增強生成) 有本質上的不同。

一般 RAG 是 **"Agent-Pull" (主動檢索)**：Agent 遇到問題 -> 去資料庫搜尋 -> 找到相關資料。
但在人類心理學中，我們通常不會"主動去資料庫搜"，而是"創傷或重要事件會自動浮現"。

因此，我們採用 **"System-Push" (被動推播)** 機制：**系統在 Agent 思考之前，就先預判"現在什麼最重要"，並直接塞進它的腦袋。**

---

## 1. 核心哲學：被動推播 (The System-Push Philosophy)

想像 Agent 是一個住戶。

- **錯誤的設計 (Standard RAG)**：Agent 問自己 "我以前淹過水嗎？" 然後去查詢歷史資料庫。
- **我們的設計 (System-Push)**：當 Agent 看到下雨 (Trigger) 時，系統自動把 **"2年前那場大水災"** 的記憶 **推 (Push)** 到它的眼前。Agent 不需要問，它被迫想起。

這更符合 **保護動機理論 (Protection Motivation Theory, PMT)**：恐懼往往來自於被迫喚起的創傷記憶。

---

## 2. 運作流程 (Step-by-Step Flow)

這個系統的運作可以拆解為四個步驟：**發生 -> 評分 -> 固化 -> 喚起**。

### 第一步：事件發生 (Event Logic)

每年結束時，`InteractionHub` (世界互動層) 會產生一系列事件。
例如：

- `FloodEvent`: 淹水深度 1.5m，造成 $50,000 損失。
- `SocialEvent`: 鄰居 Bob 決定把房子墊高。
- `NewsEvent`: 政府發布新的防洪補助。

這些原本只是冰冷的數據。

### 第二步：重要性評分 (Importance Scoring)

`MemoryEngine` 會立刻對這些事件進行**"心理評分"**。公式如下：

$$ \text{Importance} = (\text{Emotion} \times \text{Source}) $$

我們在 `agent_types.yaml` 定義了權重權威：

1.  **情感權重 (Emotion Weight)**：這件事有多"痛"或多"爽"？
    - **CRITICAL (1.0)**: 淹水受災、房屋被毀。(創傷)
    - **MAJOR (0.9)**: 做出了重大決定 (例如花錢墊高房屋)。
    - **ROUTINE (0.1)**: 下雨但沒淹水，或者無關緊要的新聞。

2.  **來源權重 (Source Weight)**：這件事是誰經歷的？
    - **PERSONAL (1.0)**: 親身經歷。(我淹水了)
    - **NEIGHBOR (0.7)**: 親眼看到。(我看見隔壁淹水)
    - **NEWS (0.5)**: 電視說的。(感覺比較遙遠)

**舉例**：

- **事件 A**：我自己淹水 (Critical + Personal) = $1.0 \times 1.0 = \mathbf{1.0}$ (極度重要)
- **事件 B**：新聞說別的地方淹水 (Critical + News) = $1.0 \times 0.5 = \mathbf{0.5}$ (普通)
- **事件 C**：今天沒下雨 (Routine + Personal) = $0.1 \times 1.0 = \mathbf{0.1}$ (垃圾資訊)

### 第三步：隨機固化 (Stochastic Consolidation)

人類不會記得每一件事。我們使用 **機率固化** 機制：

- **短期記憶 (Working Memory)**：所有事件都會保留在"今年"的腦袋裡。
- **長期記憶 (Long-Term Storage)**：
  - 分數越高，轉存到長期記憶的機率越高。
  - **分數 1.0 的創傷事件**：幾乎 100% 被寫入長期記憶。
  - **分數 0.1 的日常瑣事**：幾乎 100% 被遺忘 (Dropped)。

這解決了 **" Context Window Explosion"** 的問題：Agent 活了 100 年，卻只會記得那是幾次大災難，而不是 100 年的流水帳。

### 第四步：動態喚起 (Dynamic Retrieval)

到了明年 (Year T+1)，Agent 要做決定時，`ContextBuilder` 會去記憶庫抓資料。

這時候會加上 **時間衰減 (Time Decay)**：

$$ \text{Retrieval Score} = \text{Initial Importance} \times e^{-\lambda t} $$

- **創傷記憶 ($I=1.0$)**：衰減很慢。過了 10 年，它可能還有 0.6 的強度 -> **依然被喚起**。
- **普通記憶 ($I=0.5$)**：衰減稍快。過了 3 年就剩下 0.2 -> **可能被遺忘**。

**最終結果**：
Prompt 裡面會出現這樣的文字：

> "你記得 8 年前發生過一次毀滅性水災 (Year 2)，當時水深 1.5m，你損失慘重。"
> "你不記得去年的新聞細節，只覺得依稀有點印象。"

這就完美模擬了 **"金魚腦效應" (Goldfish Effect)** 的消除：普通的 Agent 過了 3 年就忘記教訓，但我們的 Agent 因為有創傷評分，到了第 10 年依然會因為 8 年前的災難而感到"害怕"。

---

## 3. 為什麼這對論文很重要？

這套機制是我們解決 **"LLM 不理性 (Irrationality)"** 的核心武器：

1.  **解決短視近利**：透過強制推播舊的創傷，讓 Agent 不會因為這兩年沒淹水就覺得"很安全" (Availability Heuristic)。
2.  **解決個體差異**：
    - 有些 Agent (敏感型) 的 `decay_rate` 設定很低 -> 記仇記很久。
    - 有些 Agent (樂天派) 的 `decay_rate` 設定很高 -> 好了傷疤忘了痛。
      這讓我們可以模擬出 **多樣化的社會行為** (Heterogeneity)。

## 總結

這不是一個冷冰冰的資料庫查詢系統，而是一個模擬**人類大腦皮層 (Hippocampus)** 運作的**認知過濾器 (Cognitive Filter)**。

它先幫 LLM 決定了"什麼值得被記住"，從而引導 LLM 做出更符合人性（包含恐懼與焦慮）的決策。
