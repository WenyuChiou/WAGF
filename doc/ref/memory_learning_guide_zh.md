# 🎓 記憶與檢索系統：自我精進學習指南 (Self-Study Guide)

這份指南旨在協助您將 **「剛剛解決的 Bug (淺層記憶與隨機性)」** 與 **「學術理論」** 以及 **「我們的實驗設定」** 做深度連結。透過這個實際案例，您將能更深刻理解這些經典論文的核心價值，並學會如何在論文中論述您的系統設計。

---

## 🛑 案例分析：為什麼 Agent 1 會「失憶」？

**(Case Study: The Shallow Memory Bug)**

### 1. 現象回顧

在 Repo 版模擬中，Agent 1 經歷了第 3、4 年的洪水，但在第 9 年再次遭遇洪水時，卻選擇 "Do Nothing"。

- **工程視角**：因為 `MEMORY_WINDOW = 5`，舊記憶被推擠出去了 (FIFO)。
- **學術視角 (Paper #1)**：這是 **可用性捷思 (Availability Heuristic)** 的完美反例。

### 2. 理論連結：Tversky & Kahneman (1973)

> _"People assess the frequency of a class or the probability of an event by the ease with which instances or occurrences can be brought to mind."_

- **理論解釋**：人類判斷風險，不是看統計數據，而是看「腦中能想起多少畫面」。
- **Agent 的行為**：
  - 當第 3 年洪水還在 Window 裡 -> 畫面容易提取 (High Availability) -> 覺得風險高 -> 採取行動。
  - 當第 9 年洪水來襲，舊記憶已消失 -> 畫面無法提取 (Zero Availability) -> 覺得是偶發事件 -> 不採取行動。

### 3. 本實驗設定對應 (Experiment Mapping)

這個理論是如何具體反映在我們的程式碼中的？

| 理論概念 (Theory)                          | 程式變數/函式 (Code mapping)        | 檔案位置                                             | 說明                                                                                         |
| :----------------------------------------- | :---------------------------------- | :--------------------------------------------------- | :------------------------------------------------------------------------------------------- |
| **Availability Heuristic**<br>(可用性捷思) | `MEMORY_WINDOW = 5`                 | `run_baseline_original.py`<br>`run_tiered_memory.py` | 視窗大小限制了"可被提取"的事件數量。視窗越小，Availability Bias 越嚴重。                     |
| **Stochastic Recall**<br>(隨機回想)        | `RANDOM_MEMORY_RECALL_CHANCE = 0.2` | `run_tiered_memory.py`<br>(Line ~300)                | 模擬人類記憶的不穩定性。這個隨機變數即是造成 Desktop/Repo 差異的元兇 (Noise)。               |
| **Salience**<br>(顯著性)                   | `determine_flood_exposure()`        | `simulation/engine.py`<br>(Logic)                    | 我們只將 "Flooded" 事件寫入 `long_term_memory`，這對應了創傷記憶的高顯著性 (High Salience)。 |

---

## 🛠️ 架構解析：Tiered Memory 是什麼？

**(Architecture Analysis)**

### 1. 實作回顧

我們修改了 `run_tiered_memory.py`，將記憶拆分為：

- `long_term_memory` (永久保存重大事件)
- `memory` (短期視窗，保存最近 5 條)

### 2. 理論連結：Baddeley (2000) - Episodic Buffer

> _"The episodic buffer ... provides a temporary interface between the slave systems and long-term memory."_

- **理論解釋**：人類的工作記憶 (Working Memory) 很小，不能把一生都塞進去。我們需要一個「緩衝區 (Buffer)」來暫存從長期記憶中提取出來的關鍵片段，並與當下感知結合成一個完整故事。
- **對應設計**：

| 理論概念 (Theory)                   | 程式實作 (Code mapping)     | 說明                                                                                                                                |
| :---------------------------------- | :-------------------------- | :---------------------------------------------------------------------------------------------------------------------------------- |
| **Long-Term Memory**<br>(長期記憶)  | `agent["long_term_memory"]` | 一個 Python List，專門儲存 `Significant Past Events`。這是不會過期的硬碟資料庫。                                                    |
| **Working Memory**<br>(短期記憶)    | `agent["memory"]`           | 維持 FIFO 佇列，模擬只記得最近 5 年的瑣事 (Neighborhood stats)。                                                                    |
| **Episodic Buffer**<br>(情節緩衝區) | `prompt_template.format()`  | 在程式碼約 Line 310-330 的地方，我們將 LTM (`memory`) 和 STM (`recent_obs`) **合併** 到同一個 String 中，這就是 Buffer 的建構過程。 |

---

## 📝 論文寫作應用 (For Your Manuscript)

當您撰寫 Method 章節描述這個系統時，可以使用以下論述策略：

### 關鍵論述：

"Drawing on **Tversky and Kahneman’s (1973)** Availability Heuristic, we hypothesize that agents' risk perception is driven by the accessibility of past flood events. However, standard LLM context windows simulate a limited **Working Memory (Baddeley, 2000)**, leading to unrealistic 'catastrophic forgetting' of past traumas.

To address this, we implemented a **Tiered Memory Architecture** inspired by **Park et al. (2023)**. This system segregates **Long-Term Episodic Storage** (variable: `long_term_memory`) from **Transient Working Memory** (variable: `memory_window`), ensuring that trauma-induced risk usage remains 'available' for retrieval even after extended quiet periods."

---

## 📚 參考文獻 (Reference List)

以下提供您所需的完整 DOI 與引用格式，可直接複製到論文參考文獻中。

### 1. Availability Heuristic (可用性捷思)

這解釋了為什麼我們需要 System-Push 機制來對抗 "Out of sight, out of mind"。

- **Tversky, A., & Kahneman, D. (1973).** Availability: A heuristic for judging frequency and probability. _Cognitive Psychology_, 5(2), 207–232.
  - **DOI**: [10.1016/0010-0285(73)90033-9](<https://doi.org/10.1016/0010-0285(73)90033-9>)

### 2. Episodic Buffer (情節緩衝區)

這解釋了為什麼我們要設計 Context Window 的組裝邏輯。

- **Baddeley, A. D. (2000).** The episodic buffer: A new component of working memory? _Trends in Cognitive Sciences_, 4(11), 417–423.
  - **DOI**: [10.1016/S1364-6613(00)01538-2](<https://doi.org/10.1016/S1364-6613(00)01538-2>)

### 3. Generative Agents (生成式代理人)

這提供了我們 "Memory Stream" 與 "Retrieval" 的現代架構基礎。

- **Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023).** Generative Agents: Interactive Simulacra of Human Behavior. In _Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology (UIST '23)_ (pp. 1–22). New York, NY, USA: ACM.
  - **DOI**: [10.1145/3586183.3606763](https://doi.org/10.1145/3586183.3606763)

### 4. Protection Motivation Theory (保護動機理論)

這解釋了為什麼我們要把 Threat Appraisal (恐懼) 與 Coping Appraisal (效能) 分開來 Prompt。

- **Rogers, R. W. (1983).** Cognitive and physiological processes in fear appeals and attitude change: A revised theory of protection motivation. In J. T. Cacioppo & R. E. Petty (Eds.), _Social Psychophysiology: A Sourcebook_ (pp. 153–176). New York: Guilford Press.
  - **ISBN**: 978-0898626296
