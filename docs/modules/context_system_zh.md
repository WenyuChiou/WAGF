# 上下文與輸出系統 (Context & Output System)

**🌐 Language: [English](context_system.md) | [中文](context_system_zh.md)**

本文件說明 `FinalContextBuilder` 如何建構 Agent 的認知世界，以及如何強制執行嚴格的輸出格式（如 JSON scoring）。

---

## 1. 上下文建構 (Context Construction)

`ContextBuilder` 將原始數據轉換為 LLM 可理解的敘事結構，分為四個層次：

1.  **全局真理 (Global Truth)**：
    - 定義 Agent 的身分與基本規則（如：「你是一位居住在洪水易發區的屋主」）。
    - _來源_：`agent_initial_profiles.csv` 與 `run_flood.py` 中的 `narrative_persona`。

2.  **記憶檢索 (Retrieved Memory)**：
    - 從 10 年的歷史中檢索最相關的 3-5 個片段。
    - _機制_：使用 `HumanCentricMemoryEngine` 計算 $S_{retrieval}$ 分數。

3.  **當前感知 (Immediate Perception)**：
    - 當前年份的具體數值（水位、鄰居行動、政策變化）。
    - _來源_：`EnvironmentProvider` 與 `InteractionHub`。

### 📜 上下文範例 (Context Example)

以下是用於 `household` Agent 的實際上下文範本，包含了 **Shared Rules** 與 Policy 定義：

```text
[Role & Identity]
You are a homeowner in a coastal area (Flood Zone A).
Property Value: $200,000. Current Savings: $15,000.

[Policy & Shared Rules]
1. FLOOD_INSURANCE_ACT: Subsidy available if community participation > 50%.
2. ZONING_LAW_101: Elevation grants provided for houses < 0m elevation.
3. BUDGET_CONSTRAINT: You cannot spend more than your simulation savings.

[Prioritized Memory]
- Year 3: Flood depth 1.2m. "My basement was destroyed." (Importance: 0.9)
- Year 4: Neighbor Bob elevated his house. (Importance: 0.6)

[Current Situation - Year 5]
Flood Forecast: High Probability.
Neighbor Action: 3 neighbors bought insurance yesterday.
```

4.  **輸出指令 (Output Directives)**：
    - **最關鍵的部分**：強制 LLM 輸出特定格式。

---

## 2. 輸出強制與評分 (Output Enforcement & Scoring)

### 嚴格格式規則 (Strict Formatting Rule)

為了確保 Agent 的決策可以被程式化解析，`SystemPromptProvider` 會注入以下指令：

```text
### [STRICT FORMATTING RULE]
You MUST wrap your final decision JSON in <decision> and </decision> tags.
Example: <decision>{{"strategy": "elevate_house", "confidence": 0.8, "decision": 1}}</decision>
DO NOT include any commentary outside these tags.
```

### JSON 結構定義 (Constructs Definition)

用戶可以在 Prompt Template 中定義需要的 JSON 欄位（Constructs）。例如在 `household_template` 中：

- **Decision**: 具體行動代碼 (0=Wait, 1=Insure, etc.)
- **Confidence**: 決策信心分數 (0.0 - 1.0)
- **Reasoning**: 簡短的決策理由

### 決策解析 (Parsing Decision)

`UnifiedAdapter` (位於 `broker/utils/model_adapter.py`) 負責解析輸出：

1.  **提取**: 使用正則表達式尋找 `<decision>...</decision>` 標籤內的內容。
2.  **修復**: 若 JSON 格式錯誤（如缺少引號），`SmartRepairPreprocessor` 會嘗試自動修復。
3.  **驗證**: 檢查是否包含所有必要的欄位 (`strategy`, `confidence`)。

### 評分機制 (Scoring)

若您的應用需要對 Agent 的輸出進行評分（如：理由是否合邏輯），這通常在 **Governance Layer** 完成。

- **Validator**: 檢查輸出是否符合 `agent_types.yaml` 中的定義。
- **Auditor**: 記錄 `confidence` 分數並計算群體平均值 (如 `all_groups_stability.csv` 中的 AC Metric)。

---

## 3. 自定義上下文 (Customization)

若您需要修改上下文結構：

1.  **修改 Template**: 編輯 `broker/utils/prompts/household_template.txt`。
2.  **修改 Builder**: 繼承 `ContextBuilder` 並覆寫 `format_prompt` 方法。
