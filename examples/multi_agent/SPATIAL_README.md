# Spatial Integration Strategy / 空間整合策略

## Why: The Spatial Mismatch / 為什麼需要空間投影？

In this simulation, we face a common challenge in spatial modeling:

- **Agent Data**: Real survey data from ~1,000 households across 69 NJ ZIP codes (e.g., Weehawken, Bayonne).
- **Hazard Data**: High-resolution (1m/30m) flood depth grids from the **Pompton River Basin (PRB)**.

The agents' real properties are physically outside the PRB flood grid. If we mapped them by exact coordinates, we would have 0 agents in the flood zone, making the simulation meaningless.

在本模擬中，我們面臨空間建模中常見的挑戰：

- **Agent 數據**：來自新澤西州 69 個郵遞區號（如 Weehawken, Bayonne）的約 1,000 戶真實調查數據。
- **災害數據**：來自 **Pompton River Basin (PRB)** 的高解析度（1m/30m）洪水深度網格。

這群 Agent 的現實住處在物理上位於 PRB 網格之外。如果我們按精確座標對齊，將沒有任何 Agent 會被淹到，導致模擬失去意義。

---

## How: Synthetic Spatial Projection / 核心方案：虛擬空間投影

To bridge this gap, we implement a **"Identity-Preserving Projection"**:
我們對此實施了 **「保留身份特徵的投影」** 策略：

1. **Retain Reality (Demographics)**: We use the **real income, education, and property values** from the survey agents.
   **保留現實 (人口統計)**：我們完整使用調查中 Agent 的**真實收入、教育程度和房產價值**。

2. **Project Experience (Spatial Assignment)**:

   - Agents who reported **real-world flood experience** in the survey are "projected" into **High-Hazard zones** within the PRB grid.
   - Agents who never experienced floods are assigned to **Safe zones**.
     **投影經驗 (空間分配)**：
   - 在現實調查中回報過**有淹水經驗**的 Agent，會被「投影」到 PRB 網格中的**高風險區域**。
   - 從未經歷過洪水的 Agent 則被分配到**安全區域**。

3. **Convert & Calculate (Hazard Impact)**:
   - Grid data is in **Meters** (per project README).
   - We convert Meters to **Feet** (1m = 3.28ft) before applying **FEMA Standard Depth-Damage curves** via `hazard.py`.
     **轉換與計算 (災害影響)**：
   - 網格數據單位為 **公尺** (Meters)。
   - 在透過 `hazard.py` 套用 **FEMA 標準深度-損害曲線** 之前，我們會將公尺轉換為 **英呎** (1m = 3.28ft)。

---

## Results / 預期效果

This approach ensures that **decision-makers with high risk perception (real history)** are exposed to **high physical hazard (real grid depth)**, creating a logically consistent environment for testing adaptation behaviors (Insurance, Elevation, Relocation).

這種方法確保了**具有高風險感知（真實歷史）**的決策者，能接觸到**高強度的物理災害（真實網格水深）**，進而為測試適應行為（保險、加高、搬遷）創造了一個邏輯自洽的環境。

## CLI Notes
- Use --grid-dir to point at the PRB ASCII grid folder (meters).
- Optionally set --grid-years (comma-separated) to constrain loaded years.

