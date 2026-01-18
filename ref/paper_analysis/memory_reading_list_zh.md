# 📚 記憶與檢索系統：經典論文閱讀清單 (Classic Reading List)

這套「以人為本」的記憶架構並非憑空想像，而是融合了 **認知心理學** 與 **現代 AI Agent** 的研究成果。以下是我為您挑選的 5 篇最經典論文，並說明它們如何影響了我們的設計：

---

## 1. 為什麼要 "System-Push"？(主動推播的依據)

> **Paper**: _Availability: A heuristic for judging frequency and probability_
> **Author**: Tversky, A., & Kahneman, D. (1973)
> **領域**: 認知心理學 / 行為經濟學

- **核心觀念**: **可用性捷思 (Availability Heuristic)**。人類在評估風險時，不是去計算統計機率，而是看「腦中能多快想起這個畫面」。如果一件事情（如淹水）很容易被想起，我們就會覺得它發生機率很高。
- **對本系統的影響**:
  - 這就是為什麼我們設計 **System-Push**。我們強制把「淹水畫面」推到 Prompt 最前面，目的就是**人工製造「可用性」(Artificial Availability)**。
  - 如果不這麼做，LLM 就像一個健忘的人，覺得「想不起來 = 不會發生」，導致低估風險。

---

## 2. 為什麼遠處的新聞權重比較低？(來源權重的依據)

> **Paper**: _Construal-level theory of psychological distance_
> **Author**: Trope, Y., & Liberman, N. (2010)
> **領域**: 社會心理學

- **核心觀念**: **解釋水平理論 (CLT)**。心理距離越遠的事物（時間遠、空間遠、社會關係遠），我們會用越抽象的方式去思考它（Abstract）；距離越近，則越具體（Concrete）。具體的威脅更能引發行動。
- **對本系統的影響**:
  - 這是 `source_weights` 的理論基礎。
  - `Personal` (自己) = 零距離 = 權重 1.0 (最痛，最深刻)。
  - `News` (新聞) = 遠距離 = 權重 0.5 (感覺只是抽象的資訊，較難引發恐懼)。

---

## 3. 為什麼要分恐懼與效能？(屬性標籤的依據)

> **Paper**: _Cognitive and physiological processes in fear appeals and attitude change: A revised theory of protection motivation_
> **Author**: Rogers, R. W. (1983)
> **領域**: 健康心理學 / 風險溝通

- **核心觀念**: **保護動機理論 (PMT)**。恐懼 (Threat Appraisal) 必須搭配解決方案 (Coping Appraisal) 才會產生行動。光有恐懼會導致「防衛性逃避」(Denial)。
- **對本系統的影響**:
  - 這是 `ContextBuilder` 分類記憶的依據。我們不只存「淹水了」，還存「墊高很有用」。
  - 這也是 **Pillar 2 (Cognitive Intervention)** 規則庫的來源：如果 `Threat=High` 但 `Coping=Low`，Agent 會選擇不可見的逃避，我們必須加以干預。

---

## 4. 現代 LLM Agent 的記憶始祖

> **Paper**: _Generative Agents: Interactive Simulacra of Human Behavior_
> **Author**: Park, J. S., et al. (Stanford / Google) (2023)
> **領域**: 現代 AI Agent

- **核心觀念**: 提出了 **Retrieval (檢索)**、**Reflection (反思)**、**Planning (計畫)** 三大支柱。特別是 `Importance Score` 的概念：記憶不是平等的，有些記憶天生就比其他重要。
- **對本系統的影響**:
  - 我們借鑑了它的 **Score-based Retrieval** 機制。
  - 但我們做了改良：Park 的 Agent 是為了社交 (Social)，我們的 Agent 是為了生存 (Survival)。所以我們把權重從「社交頻率」改成了「PMT 威脅值」。

---

## 5. 工作記憶的極限

> **Paper**: _The episodic buffer: a new component of working memory?_
> **Author**: Baddeley, A. D. (2000)
> **領域**: 神經科學

- **核心觀念**: 人類的工作記憶 (Working Memory) 非常有限，需要一個「情節緩衝區」來整合來自長期記憶的資訊。
- **對本系統的影響**:
  - 這解釋了為什麼我們需要 `Window Size` 限制 (例如只看過去 5 年)，以及為什麼需要 `ContextBuilder` 來扮演這個「緩衝區」的角色，把長期記憶和當下感知整合在一起再給 LLM。

---

### 建議閱讀順序

如果您時間有限，建議先看 **1. Tversky & Kahneman (1973)** 和 **4. Generative Agents (2023)**。這兩篇分別代表了「心理學基礎」和「系統實作基礎」。

此外，如果您想了解「為什麼要把記憶和檢索合在一起」，請閱讀：

**6. Tulving & Thomson (1973)**: _Encoding Specificity Principle_. 這是認知科學的鐵律：你無法提取一個你沒有「針對性編碼」的記憶。這就是為什麼我們的 _ContextBuilder_ (Retrieval) 必須深深地與 _MemoryEngine_ (Storage) 綁定在一起的原因。

---

## 📚 正式參考文獻 (References with DOI)

以下是標準 Citation 格式，方便您查找：

1.  **Tversky & Kahneman (1973)**. Availability: A heuristic for judging frequency and probability. _Cognitive Psychology_.
    - DOI: [10.1016/0010-0285(73)90033-9](<https://doi.org/10.1016/0010-0285(73)90033-9>)
2.  **Trope & Liberman (2010)**. Construal-level theory of psychological distance. _Psychological Review_.
    - DOI: [10.1037/a0018963](https://doi.org/10.1037/a0018963)
3.  **Park et al. (2023)**. Generative Agents: Interactive Simulacra of Human Behavior. _ACM UIST_.
    - DOI: [10.1145/3586183.3606763](https://doi.org/10.1145/3586183.3606763)
4.  **Rogers (1983)**. Cognitive and physiological processes in fear appeals and attitude change. _Guilford Press_.
    - ISBN: 978-0898626296
5.  **Grothmann & Reusswig (2006)**. People at risk of flooding: Why some residents take precautionary action while others do not. _Natural Hazards_.
    - DOI: [10.1007/s11069-005-8608-0](https://doi.org/10.1007/s11069-005-8608-0)
6.  **Tulving & Thomson (1973)**. Encoding specificity and retrieval processes in episodic memory. _Psychological review_.
    - DOI: [10.1037/h0020071](https://doi.org/10.1037/h0020071)
7.  **Anderson (1983)**. The architecture of cognition. _Harvard University Press_.

---

## 6. 這個系統中的「記憶分類」 (Taxonomy)

您提到的 Working / Short / Long Term Memory，在這個專案中是這樣對應的：

| 認知名詞 (Cognitive Term)        | 系統實作 (Implementation) | 說明                                                                                                                                                                   |
| :------------------------------- | :------------------------ | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Working Memory** (工作記憶)    | **LLM Context Window**    | 這是 **Prompt 當下能塞進去的文字量**。就像 Baddeley 說的 "Episodic Buffer"，我們用 `ContextBuilder` 來挑選最重要的東西放進這裡。容量極限取決於 LLM (e.g., 8k tokens)。 |
| **Short-Term Memory** (短期記憶) | **Transient Variables**   | 這是 **Code 中的變數** (如 `current_flood_depth`)。這些變數只在 `Year T` 存在，如果不重要的話，跑完這一年就會被清空 (Garbage Collection)。                             |
| **Long-Term Memory** (長期記憶)  | **JSON Disk Storage**     | 這是 **`memory_stream` 檔案**。所有經過 `Importance Score > 0.6` 篩選的記憶，都會被序列化 (Serialize) 到硬碟。這裡可以存 100 年的資料，透過 retrieval 機制隨時喚起。   |
