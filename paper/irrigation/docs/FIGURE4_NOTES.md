# Figure 4: Irrigation CRSS Comparison - Expert Review Notes

**Date**: 2026-02-04
**Expert Review Score**: 8.0/10
**Status**: ✅ Approved for paper with modifications applied

---

## 專家評估總結

### 評分
- **水文合理性**: 7.5/10
- **Methods Paper 適用性**: 8.5/10
- **綜合評價**: **8.0/10 - 建議使用**

### 關鍵結論
✅ **UB 需求低於 CRSS baseline 是科學合理的**
- 初始條件：2018 年實際使用量（3.0 MAF）
- 物理約束：Powell min release (7.0 MAF) + infrastructure cap (5.0 MAF)
- Governance 效果：P3 supply-gap + P4 Tier 2+ enforcement

---

## 已實施的修改

### 1. ✅ 加入初始條件標註（Panel a）
**位置**: Year 2019 起點
**內容**: "Initial: 2018 actual usage (3.0 MAF, 28% of 10.5 MAF rights)"
**效果**: 橙色框 + 箭頭，清楚說明低基線原因

### 2. ✅ 保留 Paper Water Gap 標註
**位置**: Year 2040 中段
**內容**: "Paper water vs wet water gap (~1.8×)"
**效果**: 凸顯需求與實際配水的差距

---

## 待更新：Caption 補充（Critical）

**現有 outline.tex caption (line 246)**:
> Aggregate water demand trajectories for (a) Upper Basin and (b) Lower Basin, 2019–2060. Dark line: CRSS static baseline (USBR, 2012). Gray line: WAGF-governed agent requests (post-governance, pre-curtailment). Blue line: WAGF actual diversions (post-curtailment). Shaded area represents the "paper water" gap between static projections and curtailed allocations. 78 real CRSS districts, Gemma 3 4B, strict governance with human-centric memory.

**專家建議加入** (需更新到 outline.tex 或 Word):

在現有 caption 後加上：

> **(a) Upper Basin:** Agents start from 2018 actual usage (3.0 MAF, 28% of paper rights) rather than CRSS projected demand. Strict governance (supply-gap validators + Powell constraint) limits aggregate growth to 4.9 MAF by 2060 (47% utilization), well below paper rights (10.5 MAF). The "paper water vs wet water gap" (~1.8×) reflects infrastructure-limited physical capacity (5.0 MAF ceiling) and over-appropriated legal rights.
>
> **(b) Lower Basin:** Agents start near saturation (2.8 MAF, 65% of rights). WAGF Request remains stable at ~2.3 MAF/yr (55% utilization), slightly below CRSS baseline, driven by forward-looking conservative cluster's voluntary curtailment under persistent Tier 2 shortages.

---

## 專家建議（未實施項目）

### Optional: Panel (c) Compact Allocation 參考線
**如果有第三個 panel**，加入水平虛線：
```python
ax.axhline(7.5, color="#999999", ls="--", lw=1.0, alpha=0.7,
           label="Compact Allocation (7.5 MAF)", zorder=1)
```

**目前狀態**: 只有 2 個 panels (a/b)，未實施此項

---

## 對審稿人的預期質疑與回應

### Q1: "為何 UB 需求這麼低？"
**A**: 模型從 2018 年實際使用量（3.0 MAF）啟動，非紙面水權（10.5 MAF）。UB 歷史上從未超過 4.0 MAF，受基礎設施和 Powell 最小放水量約束。

### Q2: "WAGF 比 CRSS 低，是否保守？"
**A**: CRSS baseline 是靜態預測。WAGF agents 透過 reflection 學習「supply-gap 模式」，主動削減需求以避免 curtailment penalty。這是 rational adaptation，非保守。

### Q3: "為何 LB 需求幾乎不變？"
**A**: LB 初始已接近飽和（65%），在 Tier 2 shortage 下，forward-looking conservative cluster 主動維持穩定需求。這是 defensive strategy。

---

## 文件位置

**圖片**:
- PNG: `paper/figures/fig4_crss_comparison.png`
- PDF: `paper/figures/fig4_crss_comparison.pdf`

**生成腳本**:
- `examples/single_agent/analysis/paper_figures/fig4_crss_comparison.py`

**數據來源**:
- `examples/irrigation_abm/results/production_4b_42yr_v11/simulation_log.csv`

---

## 核心訊息（給審稿人）

> "WAGF 並非預測未來需求絕對值，而是展示 LLM agents 在嚴格 governance 下如何從真實歷史基線適應性調整。與 CRSS 靜態預測的差異，正凸顯框架捕捉 adaptive behavior 的能力。"

---

**最後更新**: 2026-02-04 10:00 PM
**下一步**: 更新 outline.tex 或 SAGE_WRR_Paper.docx 的 Figure 4 caption

