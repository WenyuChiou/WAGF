# WAGF 構念與驗證模組 (C&V)

## 概述

本模組實作 LLM 驅動代理人模型 (LLM-ABM) 的三層驗證協定，評估**理論知情的行為保真度**（結構合理性），而非預測精確度。

設計源自 POM 框架（Grimm et al. 2005），擴展為 LLM-ABM 專用的量化驗證標準。目前以洪水調適（PMT 理論）為實作，但架構支援擴展至其他行為理論與領域。

---

## 三層驗證架構

```
L3 認知驗證（實驗前）
   │  ICC、eta²、方向敏感度
   │  → 確認 LLM 能區分不同人格
   ▼
L1 微觀驗證（逐決策）
   │  CACR、R_H、EBE
   │  → 確認每個決策符合行為理論
   ▼
L2 總體驗證（群體層級）
      EPI + 8 項經驗基準
      → 確認群體行為符合經驗文獻
```

### L1 微觀指標

| 指標 | 全名 | 門檻 | 說明 |
|------|------|------|------|
| **CACR** | 構念-行動一致率 | ≥ 0.75 | 代理人行動是否符合構念映射（例如 PMT TP/CP → 行動）？ |
| **CACR_raw** | 原始一致率（治理前） | 參考值 | 治理介入前的 LLM 推理品質 |
| **CACR_final** | 最終一致率（治理後） | 參考值 | 系統層級一致率（含治理過濾） |
| **R_H** | 幻覺率 | ≤ 0.10 | 物理上不可能的行動（例如已遷離的代理人仍在決策） |
| **EBE** | 有效行為熵 | 0.1 < 比值 < 0.9 | 行為多樣性：既非全同亦非均勻隨機 |

**CACR 分解**是對抗「受限隨機數產生器」批評的最強防線：若 CACR_raw 很高，表示 LLM 在治理介入前就能進行一致性推理。

**注意：**
- 提取失敗的軌跡標記為 `UNKNOWN`，從 CACR 分母中**排除**（避免虛增一致率）
- EBE 從**合併**的屋主+租戶行動分佈計算（Shannon 熵不可加）

### L2 總體指標

| 指標 | 全名 | 說明 |
|------|------|------|
| **EPI** | 經驗合理性指數 | 加權基準通過率（門檻 ≥ 0.60） |

**8 項經驗基準（洪水領域）：**

| # | 基準 | 範圍 | 權重 | 文獻來源 |
|---|------|------|------|----------|
| B1 | SFHA 保險投保率 | 0.30-0.60 | 1.0 | Choi et al. (2024), de Ruig et al. (2023) |
| B2 | 整體保險投保率 | 0.15-0.55 | 0.8 | Gallagher (2014) |
| B3 | 累計墊高率 | 0.10-0.35 | 1.0 | Brick Township 桑迪後 FEMA HMGP |
| B4 | 累計收購/遷移率 | 0.05-0.25 | 0.8 | Mach et al. (2019), NJ Blue Acres |
| B5 | 洪後不作為率 | 0.35-0.65 | 1.5 | Grothmann & Reusswig (2006), Bubeck et al. (2012) |
| B6 | MG 調適差距（複合） | 0.05-0.30 | 2.0 | Elliott & Howell (2020) |
| B7 | 租戶未投保率 | 0.15-0.40 | 1.0 | FEMA/NFIP 統計 |
| B8 | 保險失效率 | 0.15-0.30 | 1.0 | Michel-Kerjan et al. (2012) |

> **B6 注意**：MG 調適差距使用**複合指標**：任何保護行動 = 保險 OR 墊高 OR 收購 OR 遷移。僅用保險作為替代指標過於狹隘。

### L3 認知驗證

| 指標 | 門檻 | 說明 |
|------|------|------|
| ICC(2,1) | ≥ 0.60 | 類內相關：同一人格的回應一致性 |
| eta² | ≥ 0.25 | 效果量：不同人格間的可區分性 |
| 方向敏感度 | ≥ 75% | 構念輸入改變後的正確行為方向 |

---

## 使用方式

### 前置需求

```bash
pip install pandas numpy
```

### 快速開始（合成數據）

```bash
# 使用合成軌跡執行範例（不需要實驗數據）
python example_cv_usage.py
```

展示 L1 指標、L2 基準、完整管線 I/O，以及領域適配（灌溉）。

### 執行驗證

```bash
# 計算 L1/L2 指標（實驗後）
python compute_validation_metrics.py \
    --traces ../results/main_400x13_seed42 \
    --profiles ../../data/agent_profiles_balanced.csv

# 輸出目錄（預設）
# paper3/results/validation/
#   ├── validation_report.json    # 完整報告
#   ├── l1_micro_metrics.json     # L1 細節（含 CACR 分解）
#   ├── l2_macro_metrics.json     # L2 細節（含補充指標）
#   └── benchmark_comparison.csv  # 基準比較表
```

### 輸入格式

**決策軌跡 (JSONL)**：每行一個 JSON 物件：
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

**代理人檔案 (CSV)**：
```csv
agent_id,tenure,flood_zone,mg
H0001,Owner,HIGH,True
H0002,Renter,LOW,False
```

---

## 適配其他領域

驗證邏輯可擴展至任何 LLM 代理人模擬。核心抽象為：

1. **行為理論** → 構念-行動映射（CACR 評估）
2. **經驗基準** → 文獻支持的合理性範圍（EPI 評估）
3. **不可能行為** → 領域特定的物理約束（R_H 評估）

### 步驟 1：定義行為理論構念

將 `PMT_OWNER_RULES` 替換為你的理論映射表。

**計畫行為理論 (TPB) 範例**（3D 構念）：
```python
TPB_RULES = {
    # (態度, 主觀規範, 知覺行為控制) → 允許行動
    ("positive", "supportive", "high"): ["adopt_technology", "invest"],
    ("positive", "supportive", "low"): ["seek_information"],
    ("negative", "unsupportive", "low"): ["do_nothing"],
    # ...
}
```

**水資源匱乏評估 (WSA/ACA) 範例**（灌溉領域）：
```python
IRRIGATION_RULES = {
    # (WSA, ACA) → 允許技能
    ("VH", "VH"): ["decrease_large", "decrease_small"],
    ("VH", "VL"): ["maintain_demand", "decrease_small"],  # 能力受限
    ("VL", "VH"): ["increase_large", "increase_small", "maintain_demand"],
    ("VL", "VL"): ["maintain_demand"],
    # ...
}
```

### 步驟 2：定義經驗基準

將 `EMPIRICAL_BENCHMARKS` 替換為你的領域基準。

**灌溉管理範例**：
```python
EMPIRICAL_BENCHMARKS = {
    "deficit_irrigation_rate": {
        "range": (0.20, 0.45),
        "weight": 1.0,
        "description": "採用虧缺灌溉的農戶比例",
    },
    "technology_adoption_rate": {
        "range": (0.05, 0.20),
        "weight": 1.0,
        "description": "採用滴灌的農戶比例",
    },
    "demand_reduction_drought": {
        "range": (0.10, 0.30),
        "weight": 1.5,
        "description": "乾旱期間的需水量削減幅度",
    },
}
```

### 步驟 3：定義幻覺規則

更新 `_is_hallucination()` 加入領域特定的不可能行為：

```python
def _is_hallucination(trace):
    action = trace["action"]
    state = trace["state_before"]
    # 破產農戶不能投資
    if state.get("bankrupt") and action == "invest":
        return True
    # 無灌溉設施 → 不能使用滴灌
    if not state.get("has_irrigation") and action == "drip_irrigation":
        return True
    # 達到水權上限 → 不能增加用水
    if state.get("at_allocation_cap") and action in ("increase_large", "increase_small"):
        return True
    return False
```

### 步驟 4：執行 L3 認知驗證

設計 15-20 個**極端人格**（原型），涵蓋人口統計-情境極端：

```yaml
# 原型範例
archetypes:
  - id: "wealthy_low_risk"
    income: 150000
    flood_zone: LOW
    flood_count: 0
    expected_tp: VL

  - id: "poor_high_risk_flooded"
    income: 25000
    flood_zone: HIGH
    flood_count: 5
    expected_tp: VH
```

每個人格探測多次（≥ 10 次重複），計算 ICC 與 eta²。

---

## 補充指標

### REJECTED 追蹤

治理攔截的提案作為**補充指標**輸出（不計入 EPI）：

- `rejection_rate_overall`：整體拒絕率
- `rejection_rate_mg` / `rejection_rate_nmg`：按邊緣化狀態分的拒絕率
- `rejection_gap_mg_minus_nmg`：拒絕率差距（環境正義指標）
- `constrained_non_adaptation_rate`：受限非調適率（想行動但被阻擋）

這些指標將「方法論尷尬」轉化為環境正義發現：治理約束不成比例地影響邊緣化群體。

### 構念提取品質

- `extraction_failures`：TP/CP 標籤提取失敗的軌跡數
- 失敗軌跡從 CACR 中排除（避免默認偏誤）

---

## 混合治理校準 (v9b)

LLM-ABM 的核心挑戰是校準行為率以符合經驗數據。小型 LLM（4B 參數）展現兩種失敗模式：

1. **純提示校準失敗**：LLM 忽略提示中的基準率校準文本（v7: EPI=0.1099）
2. **純硬阻擋過度約束**：總是阻擋的驗證器移除了 LLM 的自主性（v8: EPI=0.4725，但 mg_adaptation_gap=0.005）

**混合方案**結合明確案例的硬治理阻擋與中間案例的描述性規範提示引導，在經驗上站得住腳的情況下保留 LLM 決策自主性。

### 設計原則

每個行為約束在**三層梯度**上運作：

```
    硬阻擋                提示引導                完全允許
    (驗證器 ERROR)        (描述性規範)            (無干預)
    ─────────────────── ─────────────────────── ───────────────────
    無自主性              LLM 權衡取捨            完全自主
    確定性結果            機率性影響              無影響
```

### MG 保險取得障礙

邊緣化家庭面臨有文獻記載的 NFIP 投保結構性障礙：信任赤字、語言取得、官僚複雜度（Atreya et al., 2015; FEMA, 2018）。

| 洪水經驗 | 當前淹水 | 機制 | 理由 |
|----------|----------|------|------|
| 從未 (`flood_count == 0`) | 否 | **硬阻擋** | 無個人動機克服結構性障礙 |
| 從未 (`flood_count == 0`) | 是 | 允許 | 立即淹水創造迫切需求 |
| 一次 (`flood_count == 1`) | 否 | **提示引導** | 一次經驗可能不足以克服障礙；LLM 自行權衡 |
| 一次 (`flood_count == 1`) | 是 | 允許 | 再次淹水強化迫切性 |
| 多次 (`flood_count >= 2`) | 任何 | 允許 | 反覆暴露克服障礙 |

**提示文本**（顯示給 `flood_count == 1`、當前未淹水的 MG 代理人）：
> 「作為低收入家庭，您面臨 NFIP 投保的額外障礙：不熟悉的申請流程、有限的語言資源，以及對政府計畫的不信任。許多類似情況的家庭等到反覆淹水後才投保。在您的情況下，只有約 15-25% 的家庭持有洪水保險。」

### 保險續保疲勞

NFIP 保單為年度制。沒有強化性洪水事件，保戶會失效（Michel-Kerjan et al., 2012：中位數保有期 2-4 年）。HIGH 區（SFHA）代理人因持續可見風險而豁免。

| 距上次洪水年數 | 洪水區 | 機制 | 理由 |
|----------------|--------|------|------|
| 0（剛淹水） | 任何 | 允許 | 立即顯著性 |
| 1-2 | 非 HIGH | **提示引導** | 記憶消退；LLM 自行決定 |
| 3+ | 非 HIGH | **硬阻擋** | 幾乎確定失效（Michel-Kerjan 2012） |
| 任何 | HIGH (SFHA) | 允許 | SFHA = 持續可見風險 |

**提示文本**（顯示給 `years_since_flood` 1-2 的非 HIGH 區代理人）：
> 「距離您上次洪水已過 N 年。研究顯示，大多數 NFIP 保戶在沒有強化性洪水事件的情況下，會在 2-4 年內讓保單失效。許多與您情況類似的鄰居已經退保。」

### 實作

| 組件 | 檔案 | 角色 |
|------|------|------|
| 硬阻擋驗證器 | `run_unified_experiment.py` | `validate_insurance_access_barriers()` |
| 提示文本生成 | `broker/components/context/providers.py` | `InstitutionalProvider.provide()` |
| 模板轉發 | `broker/components/context/tiered.py` | `mg_barrier_text`, `renewal_fatigue_text` |
| 提示模板 | `config/prompts/household_{owner,renter}.txt` | `{mg_barrier_text}`, `{renewal_fatigue_text}` |

### 校準版本歷程

| 版本 | EPI | 通過 | 關鍵改動 |
|------|-----|------|----------|
| v7 | 0.1099 | 1/8 | 純提示（保險主導） |
| v8 | 0.4725 | 4/8 | 硬阻擋：失效 + MG 障礙 + 續保疲勞 |
| v9b | 待定 | 待定 | 混合：中間案例使用提示引導 |

---

## 已知限制與未來方向

### 現有限制

1. **構念標籤循環性**：CACR 檢查 LLM 生成的 TP/CP 標籤是否與行動一致 = 自我一致性，而非構念效度。緩解：CGR（構念奠基率）提供客觀比較。
2. **無空間驗證**：所有指標均無空間性。水資源應用需要 Moran's I（空間自相關）、洪水區梯度分析。
3. **無時序軌跡驗證**：EPI 將多年動態壓縮為單一數字。未來：洪後調適尖峰比、保險存活半衰期、調適 S 曲線擬合。
4. **行為理論可擴展性**：現支援 `BehavioralTheory` 協定（PMT 已實作；TPB、HBM、PADM 模板見 EXTENDING.md），但僅 PMT 已通過經驗驗證。
5. **記憶體限制**：500K+ 軌跡需要串流處理。目前全部載入記憶體。

### 架構演進計畫

| 階段 | 內容 | 狀態 |
|------|------|------|
| Phase 0 | 修復 P0 錯誤（EBE 平均、UNKNOWN 哨兵） | 完成 |
| Phase 1 | 拆分為子套件（metrics/、io/、reporting/、theories/、benchmarks/） | 完成 |
| Phase 2 | 4 個協定介面（BehavioralTheory、HallucinationChecker、GroundingStrategy、BenchmarkRegistry） | 完成 |
| Phase 3 | P0/P1 修復（CGR、Null Model、Bootstrap CI、Benchmark 同步） | 完成 |
| Phase 4 | 跨領域泛化（6 個可配置擴展點、EXTENDING.md） | 完成 |
| Phase 5 | 串流 TraceReader + 進階後設驗證（L4 Wasserstein、阿諛測試） | 完成 |

---

## 關鍵設計決策

1. **結構合理性，非預測精確度**：LLM-ABM 不是統計預測模型；驗證目標為行為保真度
2. **校準 vs. 驗證分離**：明確標記開發中迭代的基準（校準目標）vs. 保留的基準（驗證目標）
3. **治理 = 制度約束**：REJECTED 提案類比真實世界的制度障礙（資格、可負擔性）。這在方法論上站得住腳，不是權宜之計。
4. **混合治理校準**：明確案例用硬阻擋，中間案例用描述性規範提示。在維持經驗合理性的同時保留 LLM 自主性。詳見上方「混合治理校準」段落。
5. **4B 模型作為範圍條件**：小型 LLM 代表「模型能力下限」；結果保守但可信
6. **基準率忽略 = 有限理性**：LLM 忽略校準文本平行於人類有限理性（特性，非缺陷）
7. **UNKNOWN 哨兵**：構念提取失敗默認為 "UNKNOWN"（非 "M"），從 CACR 排除以確保指標誠實
8. **描述性規範優於福利威脅**：提示文本使用「許多類似家庭做 X」的框架，而非「你很脆弱」的框架。福利威脅語言觸發小型 LLM 的 RLHF 道德傷害反射，導致過度矯正。

---

## 參考文獻

- Ajzen, I. (1991). The Theory of Planned Behavior. *Organizational Behavior and Human Decision Processes*.
- Atreya, A. et al. (2015). What drives households to buy flood insurance? *Ecological Economics*.
- Bubeck, P. et al. (2012). A review of risk perceptions and coping. *Risk Analysis*.
- Choi, J. et al. (2024). National Flood Insurance Program participation.
- Elliott, J.R. & Howell, J. (2020). Beyond disasters. *Social Problems*.
- FEMA (2018). An Affordability Framework for the National Flood Insurance Program.
- Grimm, V. et al. (2005). Pattern-oriented modeling of agent-based complex systems. *Science*.
- Grothmann, T. & Reusswig, F. (2006). People at risk of flooding. *Natural Hazards*.
- Lindell, M.K. & Perry, R.W. (2012). The Protective Action Decision Model. *Risk Analysis*.
- Mach, K.J. et al. (2019). Managed retreat through voluntary buyouts. *Science Advances*.
- Michel-Kerjan, E. et al. (2012). Policy tenure under the NFIP. *Risk Analysis*.

---

*最後更新：2026-02-16*
