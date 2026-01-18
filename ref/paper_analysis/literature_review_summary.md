# 📄 文獻回顧綜述與論文寫作指南 (Literature Review & Writing Guide)

這份文件旨在協助論文寫作。我們分析了本專案引用的 7 篇核心文獻，並針對每一篇提供了「論文寫作建議」，告訴您在 **Methodology** 或 **Discussion** 章節該如何使用它們來證成 (Justify) 我們的架構設計。

---

## 1. 核心基礎 (Foundations)

### [1] Tversky, A., & Kahneman, D. (1973). Availability: A heuristic for judging frequency and probability.

- **核心概念**: **可用性捷思 (Availability Heuristic)**。人會高估容易想起的事件的發生機率。
- **專案應用**: **System-Push Retrieval**。
- **論文寫作建議 (Where to cite)**:
  - **Introduction**: 用來解釋為什麼傳統的 RAG (Agent 主動去搜) 是錯的。Agent 如果沒被「推播」洪水記憶，它就會因為「想不起來」而覺得很安全（低估風險）。
  - **Methodology**: 用來證成為什麼我們要強制把創傷記憶塞進 Prompt。

### [2] Rogers, R. W. (1983). Cognitive and physiological processes in fear appeals... (PMT)

- **核心概念**: **保護動機理論 (Protection Motivation Theory)**。行動 = 威脅評估 (Threat) + 應對評估 (Coping)。
- **專案應用**: **Cognitive Governance (Pillar 2)**。
- **論文寫作建議**:
  - **Methodology**: 解釋 `SafetyValve` 的邏輯。為什麼當 `Threat=High` 且 `Coping=Low` 時，Agent 會選擇「逃避」(Denial) 而不是「行動」？這不是 Bug，這是 PMT 預測的行為，需要外部干預 (Governance)。

---

## 2. 記憶架構 (Memory Architecture)

### [3] Park et al. (2023). Generative Agents: Interactive Simulacra of Human Behavior.

- **核心概念**: **Memory Stream**。記憶流、反思、規劃。提出了 `Importance Score` 的概念。
- **專案應用**: **MemoryEngine (Storage)**。
- **論文寫作建議**:
  - **Methodology**: 這是我們的「工程藍圖」。明確指出我們借鑑了它的架構，但把它的「社交評分」改成了「生存評分」(Survival Salience)。
  - **Note**: 這是目前 AI Agent 領域最權威的引用，一定要放在顯眼位置 (Section 2.4)。

### [4] Baddeley, A. D. (2000). The episodic buffer: a new component of working memory?

- **核心概念**: **Episodic Buffer**。工作記憶 (Working Memory) 需要一個緩衝區來整合長期記憶。
- **專案應用**: **ContextBuilder**。
- **論文寫作建議**:
  - **Methodology**: 用來解釋 `context_window` 的限制。我們的 `ContextBuilder` 就是在扮演這個 "Buffer" 的角色，從無限的硬碟 (LTM) 中挑選出最相關的片段放入有限的 Prompt (WM)。

### [5] Tulving, E., & Thomson, D. M. (1973). Encoding specificity and retrieval processes.

- **核心概念**: **編碼特定性原則**。提取情境必須與編碼情境匹配。
- **專案應用**: **Coupled Storage & Retrieval**。
- **論文寫作建議**:
  - **Methodology**: 用來回答 Reviewer 的問題：「為什麼不把記憶存取和檢索分開做？」因為心理學告訴我們，這兩者是強耦合的 (Coupled)。

---

## 3. 社會與距離 (Social & Distance)

### [6] Trope, Y., & Liberman, N. (2010). Construal-level theory of psychological distance.

- **核心概念**: **解釋水平理論 (CLT)**。距離越遠，思考越抽象；距離越近，思考越具體。
- **專案應用**: **Source Weights**。
- **論文寫作建議**:
  - **Methodology**: 解釋為什麼 `Personal Experience` (權重 1.0) 比 `News` (權重 0.5) 更重要。這是在模擬心理距離對決策的影響。

---

## 4. 寫作 Cheat Sheet (Copy-Paste Ready)

如果您正在寫論文，以下這段話可以直接拿去修改使用：

> "Our framework's memory architecture is grounded in cognitive science. We adopt the **Memory Stream** structure from **Park et al. (2023)** but refine the retrieval logic using **Protection Motivation Theory (Rogers, 1983)**. Specifically, we implement a **System-Push** mechanism to overcome the **Availability Heuristic bias (Tversky & Kahneman, 1973)**, ensuring that latent risks are actively surfaced to the agent. The coupling of storage and retrieval is informed by the **Encoding Specificity Principle (Tulving & Thomson, 1973)**, while the prioritization of personal over distal information operationalizes **Construal Level Theory (Trope & Liberman, 2010)**."

---
