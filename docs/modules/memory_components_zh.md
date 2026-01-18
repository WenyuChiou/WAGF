# 組件說明：記憶、上下文與反思 (Components: Memory, Context & Reflection)

**🌐 Language: [English](memory_components.md) | [中文](memory_components_zh.md)**

本文檔詳細說明了代理人的認知架構設計，旨在利用心理學原理解決 LLM 的「金魚腦效應 (Goldfish Effect)」。

---

## 1. 核心概念與定義 (Core Concepts & Definitions)

在深入代碼之前，了解認知術語及其學術基礎至關重要。

- **以人為本的記憶 (Human-Centric Memory)**：一種優先處理「情感顯著性 (Emotional Salience)」（如創傷/重大事件）而非僅僅是時間新近度的檢索機制。它模擬了人類的可得性捷思。
  - _參考文獻_：**Park, J. S., et al.** (2023). Generative Agents: Interactive Simulacra of Human Behavior.
- **有界上下文 (Bounded Context)**：LLM 注意力的物理限制。我們無法餵入 10 年的日誌；我們必須建構一個適合 Token 窗口的「現實框架」。
- **反思 (Reflection)**：一種元認知過程，代理人回顧其歷史以形成高層次的「洞察 (Insights)」（例如：「我住在洪水區」）。
  - _參考文獻_：**Shinn, N., et al.** (2023). Reflexion: Language Agents with Verbal Reinforcement Learning.
- **保護動機 (PMT)**：驅動代理人決策的心理學理論，平衡「威脅感知」與「應對評估」。
  - _參考文獻_：**Rogers, R. W.** (1975). A Protection Motivation Theory.

---

## 2. 系統設計與架構 (System Design & Architecture)

### 🧠 記憶引擎：回憶的科學

`MemoryEngine` 是一個 **重構過程 (Reconstructive Process)**。它在 Prompt 變得有意義 _之前_ 作為過濾器運作。

**數學公式定義 (Mathematical Formulation)**

`HumanCentricMemoryEngine` 的檢索評分 $S$ 採用 **衰減加權乘積** 模型：

$$ S(m, t) = Imp(m) \cdot e^{-\lambda' \cdot \Delta t} $$

其中：

- $Imp(m) = W_{emotion} \times W_{source}$
- $\lambda'$ 是經情感修正後的衰減率：
  $$ \lambda' = \lambda*{base} \cdot (1 - 0.5 \cdot W*{emotion}) $$
  _(意義：情感越強烈的記憶，遺忘速度越慢)_

_注意：本系統不使用 $\alpha, \beta, \gamma$ 線性加權參數。_

### 👁️ 上下文建構器：認知透鏡

`ContextBuilder` 負責框架化現實以防止 **幻覺**。它為每個 Prompt 建構嚴格的 Schema：

1.  **全局真理**：「你是一位屋主。」(身分認同)
2.  **檢索記憶**：「你回想起第 2 年的洪水。」(來自記憶引擎)
3.  **當前狀態**：「目前水位：1.5m。」(感測器)
4.  **社交信號**：「鄰居購買了保險。」(同儕影響)

### 🪞 反思引擎：長期快取

在每個模擬年份結束時（「睡眠」階段）執行。

1.  **聚合 (Aggregate)**：讀取所有每日日誌。
2.  **合成 (Synthesize)**：LLM 生成 3 個高層次要點（洞察）。
3.  **固化 (Consolidate)**：洞察以 `Importance=10` 存入記憶，確保永久保存。

---

## 3. ⚙️ 配置與參數指南 (Configuration & Parameters)

針對 Llama 3 / Gemma 等模型的建議設定。

### 情感與來源權重 (Keywords & Weights)

用戶可通過 `agent_types.yaml` 自定義情感關鍵字與來源權重，這直接影響 $Imp(m)$ 的計算。

| 類別 (Category)     | 關鍵字範例                  | 權重 (Weight)       |
| :------------------ | :-------------------------- | :------------------ |
| **Direct Impact**   | `flood`, `damage`, `trauma` | **1.0** (最高/創傷) |
| **Personal Source** | `i`, `my`, `me`             | **1.0** (親身經歷)  |
| **Strategic**       | `decision`, `relocate`      | **0.8**             |
| **Neighbor**        | `neighbor`, `others`        | **0.8**             |
| **Routine**         | (default)                   | **0.1**             |

### 一般參數 (General Parameters)

| 參數                            | 類型    | 預設值 | 說明                      |
| :------------------------------ | :------ | :----- | :------------------------ |
| `window_size`                   | `int`   | `5`    | 「工作記憶」中的項目數。  |
| `decay_rate` ($\lambda_{base}$) | `float` | `0.1`  | 基礎遺忘率。              |
| `importance_boost`              | `float` | `0.9`  | **反思洞察** 的權重乘數。 |

---

## 4. 🔌 使用與連接器指南 (Usage & Connector Guide)

如何在您的實驗腳本 (`run.py`) 中實例化並連接組件。

```python
# 1. 初始化引擎
memory_engine = HumanCentricMemoryEngine(
    window_size=5,
    top_k_significant=2,
    consolidation_prob=0.7
)

# 2. 連結到上下文建構器
# ContextBuilder 會在 'build()' 步驟中自動觸發檢索
ctx_builder = FinalContextBuilder(
    memory_engine=memory_engine,
    agent_id=agent.id
)

# 3. 主迴圈整合
observation = ctx_builder.build(
    agent=agent,
    world_state=flood_depth
)
# 'observation' 現在包含注入的記憶 + 當前狀態
```

---

## 5. 📝 輸入/輸出範例 (Input / Output Examples)

Prompt 內部究竟發生了什麼？

**輸入：原始記憶庫**

```json
[
  { "year": 2, "text": "洪水摧毀房屋。創傷極高。", "importance": 1.0 },
  { "year": 8, "text": "晴天。", "importance": 0.1 }
]
```

**過程：第 10 年檢索**

- 第 8 年被遺忘 (衰減)。
- 第 2 年 **被檢索** (高重要性戰勝了衰減)。

**輸出：注入後的上下文**

```text
[Your History]
- Recurring Memory: "洪水摧毀房屋..." (第 2 年)
[Current Situation]
- "目前正在下大雨。"
```
