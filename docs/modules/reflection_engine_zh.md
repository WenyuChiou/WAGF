---
title: Reflection Engine (反射引擎 - 系統 2 思維)
description: 定義用於長期記憶韌性的週期性認知整合模組 (框架的第二支柱)。
---

# Reflection Engine (反射引擎 / 系統 2 思維)

**Reflection Engine (反射引擎)** 負責執行框架的 **第二支柱 (Pillar 2)**：**週期性反思與整合 (Periodic Reflection & Synthesis)**。它的主要目標是對抗「金魚效應」(記憶碎片化)，透過將零散的情節記憶 (Episodic Memories) 綜合為連貫的高層次 **語義規則 (Semantic Rules)**。

此引擎的設計靈感來自人類睡眠時的記憶整合機制以及 _Generative Agents_ (Park et al., 2023) 研究。它允許 Agent 形成能夠跨越短期 Context Window 限制的長期策略。

---

## 1. 核心職責 (Core Responsibilities)

1.  **觸發反思 (Triggering)**：決定 Agent 何時應該停下來「思考」（例如：模擬年度結束或 Epoch 結束時）。
2.  **提示生成 (Prompt Construction)**：動態構建 Prompt，將近期的記憶輸入 LLM，要求其進行摘要與模式識別。
3.  **洞察解析 (Insight Parsing)**：將 LLM 的文字輸出轉換為結構化的 `ReflectionInsight` 物件。
4.  **記憶整合 (Integration)**：將這些洞察以人為提高的「重要性分數」注回 **Memory Engine**，確保它們不會隨時間衰退。
5.  **審計日誌 (Audit Logging)**：將所有反思記錄到 `reflection_log.jsonl`，用於生成 **認知熱圖 (Cognitive Heatmap)** 以實現可解釋性 AI (XAI)。

---

## 2. 架構與數據流 (Architecture)

```mermaid
graph TD
    A[年度結束觸發] -->|啟動| B[Reflection Engine]
    B -->|獲取近期回憶| C[Memory Engine]
    C -->|Top-k 重要事件| B
    B -->|綜合提示詞| D[LLM (System 2)]
    D -->|高層次洞察| E[洞察解析器]
    E -->|結構化規則| F[Memory Engine (長期記憶區)]
    E -->|JSON 報告| G[reflection_log.jsonl]

    style B fill:#f9f,stroke:#333
    style D fill:#bbf,stroke:#333
```

---

## 3. 配置參數 (Configuration)

引擎通常在 `Broker` 內部初始化，並透過主模擬配置進行設定：

```python
reflection_engine = ReflectionEngine(
    reflection_interval=1,         # 每年反思一次
    max_insights_per_reflection=2, # 每次循環提取最多 2 個洞察
    insight_importance_boost=0.9,  # 新洞察的重要性 (0.0-1.0)，防止衰退
    output_path="results/reflection_log.jsonl" # XAI 審計路徑
)
```

| 參數                  | 類型    | 描述                                                         | 默認值 |
| :-------------------- | :------ | :----------------------------------------------------------- | :----- |
| `reflection_interval` | `int`   | 反思的頻率 (以年或 Epoch 為單位)。                           | `1`    |
| `max_insights`        | `int`   | 每次反思產生的最大洞察數量。                                 | `2`    |
| `importance_boost`    | `float` | 硬編碼的重要性分數。高數值 (如 0.9) 確保該洞察能存活數十年。 | `0.9`  |
| `output_path`         | `str`   | 用於 XAI 可視化的日誌文件路徑。                              | `None` |

---

## 4. 提示策略 (Prompting Strategy)

預設的反思 Prompt 是 **領域無關 (Domain-Agnostic)** 的，依賴記憶本身的內容來提供上下文。

**模板範例 (Template):**

```text
You are reflecting on your experiences from the past {interval} year(s).

**Your Recent Memories:**
{bullet_list_of_memories}

**Task:** Summarize the key lessons you have learned from these experiences.
Focus on:
1. What patterns or trends have you noticed?
2. What actions proved beneficial or harmful?
3. How will this influence your future decisions?

Provide a concise summary (2-3 sentences) that captures the most important insight.
```

---

## 5. 與記憶引擎的整合

反思結果 (Reflections) 並不是存儲在單獨的資料庫中，而是 **存回同一個 Memory Store**，但具有特殊屬性：

1.  **高重要性 (High Importance)**：它們以 `0.9` 的分數進入系統 (相比之下，日常瑣事約為 `0.3`)。
2.  **語義性質 (Semantic Nature)**：它們代表 _規則_ (例如：「我應該購買保險」)，而非 _情節_ (例如：「昨天我看見洪水」)。
3.  **檢索優先級 (Retrieval Priority)**：當調用 `retrieve()` 時，這些高分項目會透過 HeapQ 優化自然地浮現到頂部 (Top-k)。

---

## 6. 審計與可視化 (XAI)

引擎會寫入 `reflection_log.jsonl`，每條記錄包含：

```json
{
  "summary": "我意識到單純依賴儲蓄是有風險的；保險提供了必要的安全網。",
  "source_memory_count": 5,
  "importance": 0.9,
  "year_created": 3,
  "domain_tags": [],
  "agent_id": "Agent_042",
  "timestamp": "2025-01-18T12:00:00"
}
```

此日誌用於生成 **認知熱圖 (Cognitive Heatmap)**，可視化 Agent 的思維如何從第 1 年的「反應式 (Reactive)」演變為第 5 年的「主動式 (Proactive)」。
