# LLM-ABM 構念與驗證框架 (C&V Framework)

## 概述

本模組實作了 LLM 驅動之代理人基模型 (LLM-ABM) 的三級驗證協議，用於評估 LLM 代理人決策的**理論知情行為忠實度** (theory-informed behavioral fidelity)，而非預測精度。

設計理念參考 POM 框架 (Grimm et al. 2005)，延伸為 LLM-ABM 專用的量化驗證標準。目前以防洪適應（PMT 理論）為主要實作，但架構設計支援擴展至其他行為理論和應用領域。

---

## 三級驗證架構

```
L3 認知驗證（實驗前）
   │  ICC、eta²、方向敏感度
   │  → 確認 LLM 能區分不同人物誌
   ▼
L1 微觀驗證（逐決策）
   │  CACR、R_H、EBE
   │  → 確認每個決策符合行為理論
   ▼
L2 宏觀驗證（總體）
      EPI + 8 項經驗基準
      → 確認群體行為符合實證文獻
```

### L1 微觀指標 (Micro-level)

| 指標 | 全名 | 閾值 | 說明 |
|------|------|------|------|
| **CACR** | 構念-行動一致率 | ≥ 0.75 | 代理人的行為是否符合其構念映射（如 PMT 的 TP/CP → 行動） |
| **CACR_raw** | 原始一致率（治理前） | 參考值 | LLM 在治理介入前的推理品質 |
| **CACR_final** | 最終一致率（治理後） | 參考值 | 系統層級（含治理過濾）的一致率 |
| **R_H** | 幻覺率 | ≤ 0.10 | 物理上不可能的行為（如已搬遷仍做決策） |
| **EBE** | 有效行為熵 | 0.1 < ratio < 0.9 | 行為多樣性：既非全部相同，也非均勻隨機 |

**CACR 分解**是抵禦「受限隨機數生成器」批評的最強防線：若 CACR_raw 高，表示 LLM 在治理介入前就已具有合理推理能力。

**注意事項：**
- 構念提取失敗的 traces 標記為 `UNKNOWN`，**不計入** CACR 分母（避免虛增一致率）
- EBE 從 owner + renter **合併分佈**直接計算（Shannon entropy 不可加）

### L2 宏觀指標 (Macro-level)

| 指標 | 全名 | 說明 |
|------|------|------|
| **EPI** | 經驗合理性指數 | 加權基準值通過率（閾值 ≥ 0.60） |

**8 項經驗基準值（防洪領域）：**

| # | 基準 | 範圍 | 權重 | 文獻來源 |
|---|------|------|------|----------|
| B1 | SFHA 區保險率 | 0.30-0.60 | 1.0 | Choi et al. (2024), de Ruig et al. (2023) |
| B2 | 整體保險率 | 0.15-0.55 | 0.8 | Gallagher (2014) |
| B3 | 累計墊高率 | 0.10-0.35 | 1.0 | Brick Township post-Sandy FEMA HMGP |
| B4 | 累計收購/搬遷率 | 0.05-0.25 | 0.8 | Mach et al. (2019), NJ Blue Acres |
| B5 | 洪後不作為率 | 0.35-0.65 | 1.5 | Grothmann & Reusswig (2006), Bubeck et al. (2012) |
| B6 | MG 適應差距（複合） | 0.05-0.30 | 2.0 | Elliott & Howell (2020) |
| B7 | 租戶未保險率 | 0.15-0.40 | 1.0 | FEMA/NFIP 統計 |
| B8 | 保險失效率 | 0.15-0.30 | 1.0 | Michel-Kerjan et al. (2012) |

> **B6 說明**：MG 適應差距使用**複合指標** (composite metric)：任何保護行動 = 保險 OR 墊高 OR 收購 OR 搬遷。單獨使用保險率作為代理指標過於狹隘。

### L3 認知驗證 (Cognitive-level)

| 指標 | 閾值 | 說明 |
|------|------|------|
| ICC(2,1) | ≥ 0.60 | 組內相關係數：同一人物誌的重複回應一致性 |
| eta² | ≥ 0.25 | 效果量：不同人物誌間的區分度 |
| 方向敏感度 | ≥ 75% | 改變構念輸入後行為方向正確率 |

---

## 使用方法

### 前置需求

```bash
pip install pandas numpy
```

### 執行驗證

```bash
# 計算 L1/L2 指標（實驗後）
python compute_validation_metrics.py \
    --traces ../results/main_400x13_seed42 \
    --profiles ../../data/agent_profiles_balanced.csv

# 輸出目錄（預設）
# paper3/results/validation/
#   ├── validation_report.json    # 完整報告
#   ├── l1_micro_metrics.json     # L1 詳細（含 CACR 分解）
#   ├── l2_macro_metrics.json     # L2 詳細（含補充指標）
#   └── benchmark_comparison.csv  # 基準值對照表
```

### 輸入格式

**決策追蹤檔 (JSONL)**：每行一個 JSON 物件，包含：
```json
{
  "agent_id": "H0001",
  "year": 3,
  "outcome": "APPROVED",
  "skill_proposal": {
    "skill_name": "buy_insurance",
    "reasoning": {"TP_LABEL": "H", "CP_LABEL": "M"}
  },
  "approved_skill": {"skill_name": "buy_insurance"},
  "state_before": {"flood_zone": "HIGH", "elevated": false},
  "state_after": {"flood_zone": "HIGH"},
  "flooded_this_year": true
}
```

**代理人設定檔 (CSV)**：
```csv
agent_id,tenure,flood_zone,mg
H0001,Owner,HIGH,True
H0002,Renter,LOW,False
```

---

## 適用其他領域

本框架的驗證邏輯可延伸至任何使用 LLM 代理的模擬場景。核心抽象為：

1. **行為理論** → 構念-行動映射（CACR 評估）
2. **經驗基準** → 文獻支持的合理範圍（EPI 評估）
3. **不可能行為** → 領域特定的物理約束（R_H 評估）

### 步驟 1：定義行為理論構念

替換 `PMT_OWNER_RULES` 為你的理論對照表。

**計畫行為理論 (TPB) 範例**（3 維構念）：
```python
TPB_RULES = {
    # (Attitude, SubjectiveNorm, PBC) → 允許的行為
    ("positive", "supportive", "high"): ["adopt_technology", "invest"],
    ("positive", "supportive", "low"): ["seek_information"],
    ("negative", "unsupportive", "low"): ["do_nothing"],
    # ...
}
```

**水資源稀缺評估 (WSA/ACA) 範例**（灌溉領域）：
```python
IRRIGATION_RULES = {
    # (WSA, ACA) → 允許的技能
    ("VH", "VH"): ["decrease_large", "decrease_small"],
    ("VH", "VL"): ["maintain_demand", "decrease_small"],  # 容量受限
    ("VL", "VH"): ["increase_large", "increase_small", "maintain_demand"],
    ("VL", "VL"): ["maintain_demand"],
    # ...
}
```

### 步驟 2：定義經驗基準值

替換 `EMPIRICAL_BENCHMARKS` 為你的領域基準。

**灌溉管理範例**：
```python
EMPIRICAL_BENCHMARKS = {
    "deficit_irrigation_rate": {
        "range": (0.20, 0.45),
        "weight": 1.0,
        "description": "採用缺水灌溉的農民比例",
    },
    "technology_adoption_rate": {
        "range": (0.05, 0.20),
        "weight": 1.0,
        "description": "採用滴灌技術的農民比例",
    },
    "demand_reduction_drought": {
        "range": (0.10, 0.30),
        "weight": 1.5,
        "description": "乾旱期間需求減少比例",
    },
}
```

### 步驟 3：定義幻覺規則

更新 `_is_hallucination()` 函數，加入領域特定的不可能行為：

```python
def _is_hallucination(trace):
    action = trace["action"]
    state = trace["state_before"]
    # 已破產的農民不能投資
    if state.get("bankrupt") and action == "invest":
        return True
    # 沒有灌溉設施不能用滴灌
    if not state.get("has_irrigation") and action == "drip_irrigation":
        return True
    # 水權上限時不能增加
    if state.get("at_allocation_cap") and action in ("increase_large", "increase_small"):
        return True
    return False
```

### 步驟 4：執行 L3 認知驗證

設計 15-20 個**極端人物誌**（archetype），涵蓋人口統計與情境的極端組合：

```yaml
# 極端人物誌範例
archetypes:
  - id: "wealthy_low_risk"
    income: 150000
    flood_zone: LOW
    flood_count: 0
    expected_tp: VL  # 預期低威脅感知

  - id: "poor_high_risk_flooded"
    income: 25000
    flood_zone: HIGH
    flood_count: 5
    expected_tp: VH  # 預期高威脅感知
```

每個人物誌重複詢問 LLM 多次（建議 ≥ 10 次），計算 ICC 和 eta²。

---

## 補充指標

### REJECTED 追蹤

治理系統攔截的提案會作為**補充指標**輸出（不計入 EPI），包括：

- `rejection_rate_overall`：整體被拒率
- `rejection_rate_mg` / `rejection_rate_nmg`：弱勢/非弱勢群體被拒率
- `rejection_gap_mg_minus_nmg`：被拒率差距（環境正義指標）
- `constrained_non_adaptation_rate`：受限非適應率（想行動但被阻擋）

這些指標將「方法論上的尷尬」轉化為環境正義發現：治理約束不成比例地影響弱勢群體。

### 構念提取品質

- `extraction_failures`：TP/CP 標籤提取失敗的 trace 數量
- 提取失敗的 traces 不計入 CACR（避免 silent default bias）

---

## 已知限制與未來方向

### 目前限制

1. **構念標籤循環性**：CACR 檢查 LLM 自己產生的 TP/CP 標籤是否與行動一致 = 自我一致性 (self-consistency)，而非構念效度 (construct validity)。未來需要「構念接地」驗證。
2. **無空間驗證**：目前所有指標為非空間的。水資源應用需要 Moran's I（空間自相關）、洪水區梯度分析。
3. **無時間軌跡驗證**：EPI 壓縮多年動態為單一數字。應補充洪後適應峰值比、保險存活半衰期、適應 S 曲線擬合。
4. **單理論支援**：目前僅 hard-code PMT。未來將透過 `BehavioralTheory` protocol 支援 TPB、HBM、PADM、前景理論等。
5. **記憶體限制**：500K+ traces 需要串流處理。目前為全量載入。

### 架構演進計畫

| 階段 | 內容 | 狀態 |
|------|------|------|
| Phase 0 | 修復 P0 bugs (EBE 平均、UNKNOWN sentinel) | ✅ 完成 |
| Phase 1 | 常數外部化為 YAML (規則、基準) | 🔲 規劃中 |
| Phase 2 | 拆分為子模組 (metrics/, io/, reporting/) | 🔲 規劃中 |
| Phase 3 | BehavioralTheory protocol + TheoryRegistry | 🔲 規劃中 |
| Phase 4 | BenchmarkComputation 可插拔 plugins | 🔲 規劃中 |
| Phase 5 | 串流 TraceReader + ValidationRunner facade | 🔲 規劃中 |

---

## 關鍵設計決策

1. **構念合理性，非預測精度**：LLM-ABM 不是統計預測模型，驗證目標是結構合理性
2. **校準 vs 驗證分離**：明確標註哪些基準是開發時迭代的（校準目標）、哪些是保留的（驗證目標）
3. **治理 ≈ 制度約束**：REJECTED 提案類比於現實中的制度障礙（資格、負擔能力）
4. **4B 模型作為範圍條件**：小型 LLM 代表「模型能力下界」，結果保守但可信
5. **基率忽視 ≈ 有限理性**：LLM 忽略校準文本可解讀為有限理性（特徵，非缺陷）
6. **UNKNOWN sentinel**：構念提取失敗不默認為 "M"，而是排除出 CACR，確保指標誠實

---

## 文獻參考

- Grimm, V. et al. (2005). Pattern-oriented modeling of agent-based complex systems. *Science*.
- Grothmann, T. & Reusswig, F. (2006). People at risk of flooding. *Natural Hazards*.
- Bubeck, P. et al. (2012). A review of risk perceptions and coping. *Risk Analysis*.
- Michel-Kerjan, E. et al. (2012). Policy tenure under the NFIP. *Risk Analysis*.
- Mach, K.J. et al. (2019). Managed retreat through voluntary buyouts. *Science Advances*.
- Elliott, J.R. & Howell, J. (2020). Beyond disasters. *Social Problems*.
- Choi, J. et al. (2024). National Flood Insurance Program participation.
- Lindell, M.K. & Perry, R.W. (2012). The Protective Action Decision Model. *Risk Analysis*.
- Ajzen, I. (1991). The Theory of Planned Behavior. *Organizational Behavior and Human Decision Processes*.

---

*最後更新：2026-02-14*
