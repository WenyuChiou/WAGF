# C&V 模組專家審查綜合報告

**日期**: 2026-02-14
**模組**: `compute_validation_metrics.py` (~1,297 行)
**審查團隊**: LLM 行為工程專家、行為/社會科學專家、水資源工程專家、資工系教授
**目標**: 通用性、可擴充性 (10K+ agents)、多理論支援、具體範例

---

## 1. 跨專家共識 — P0 必須立即修復

### 1.1 EBE 平均計算 bug
- **問題**: `(EBE_owner + EBE_renter) / 2` — Shannon entropy 不可加
- **範例**: Owners 全選 insurance (H=0), Renters 全選 do_nothing (H=0) → 平均=0，但合併分佈 H=1.0
- **修復**: 從合併的 action_counts 直接計算 `_compute_entropy(Counter(combined_actions))`

### 1.2 TP/CP 提取失敗 silent default to "M"
- **問題**: 提取失敗時默認 "M"（最寬鬆的 PMT cell），虛增 CACR
- **修復**: 使用 "UNKNOWN" sentinel，排除出 CACR 分母，另外追蹤 `extraction_failures` 數量

### 1.3 Agent type 推斷 circular
- **問題**: 用 proposed action (relocate → renter) 推斷 agent type，但 renter 若提 buy_insurance 就被當 owner
- **修復**: 使用 agent_id 數字範圍 (H0001-H0200=owner, H0201-H0400=renter)，fallback 才用 action

---

## 2. 架構重構建議 (P1)

### 2.1 模組化拆分 (CS 教授)
目前 1,297 行 monolith 混合 7 種職責。建議拆為 `broker/validators/validation/` package：

```
validation/
  __init__.py, api.py, engine.py
  theories/     → base.py, registry.py, pmt.py, tpb.py
  hallucinations/ → base.py, registry.py, flood.py
  benchmarks/   → computations.py, flood.py, irrigation.py
  metrics/      → l1_micro.py, l2_macro.py, l3_cognitive.py, entropy.py
  io/           → trace_reader.py, state_inference.py, field_extractors.py
  reporting/    → report_builder.py, cli.py
```

### 2.2 可插拔理論支援 (所有專家一致)

**BehavioralTheory protocol:**
```python
Protocol BehavioralTheory:
    name: str
    dimensions: List[ConstructDimension]
    def get_coherent_actions(construct_levels: Dict, agent_type: str) -> List[str]
    def extract_constructs(trace: Dict) -> Dict[str, str]
```

社科專家指出兩種 paradigm:
- **Paradigm A** (Construct-Action Mapping): PMT, TPB, HBM — lookup table
- **Paradigm B** (Frame-Conditional): Prospect Theory, Nudge Theory — 不是 lookup，是 tendency matching

### 2.3 Benchmark 外部化
- `BenchmarkComputation` protocol: 每個 benchmark 獨立 callable
- 替換目前 410 行 switch statement (`_compute_benchmark`)
- YAML 格式定義 benchmark name, range, weight, filter, compute function

---

## 3. LLM 特定驗證缺口 (LLM 專家)

| 缺口 | 優先級 | 說明 |
|------|--------|------|
| Sycophancy detection | P2 | LLM mirror prompt framing，不是真推理。加 Prompt-Response Independence 指標 |
| CACR temporal decomposition | P1 | CACR-by-year 偵測 instruction-following collapse (小 LLM 在後期退化) |
| Construct label circularity | P1 | LLM 自產 TP/CP 又用來驗自己 = self-consistency, NOT construct validity |
| Reasoning faithfulness | P3 | TP_LABEL=VH 但 reasoning 寫 "flood risk minimal" — label-reasoning disconnect |
| Cross-model comparability | P2 | CACR-normalized (vs random baseline), model card, variance metrics |
| Position bias | P3 | Skill list 順序影響選擇頻率，Spearman rho 診斷 |
| Degenerate output detection | P3 | 重複 n-gram、空 reasoning、truncated JSON |

---

## 4. 時空驗證缺口 (水資源 + 社科專家)

### 4.1 空間驗證

| 指標 | 說明 | 預期 |
|------|------|------|
| Adaptation Moran's I | 適應行為的空間自相關 | I > 0, p < 0.05 |
| Flood zone gradient slope | adaptation_rate ~ flood_depth_percentile | 正斜率 |
| Buyout spatial concentration | 收購集中於最高風險區 | Gini > 0.4 |

### 4.2 時間驗證

| 指標 | 說明 | 文獻基準 |
|------|------|----------|
| Post-flood spike ratio | 洪後 Y+1 適應率 / 洪前 Y-1 | 1.5-3.0x (Gallagher 2014) |
| Insurance survival half-life | 首購到失效的中位期間 | 2-4 yr (Michel-Kerjan 2012) |
| Adaptation S-curve R² | 累計適應 logistic 擬合 | R² > 0.85 |
| CACR-by-year slope | 偵測 LLM 時間退化 | 非負 |

### 4.3 社會動態驗證

- Temporal contagion: 鄰居適應後，連接 agent 是否更快適應？
- Norm emergence: within-group entropy 隨時間變化
- Rejection cascade: MG 被拒 → 年 t+1 不作為 (compounding effect)

---

## 5. 可擴充性 — 10K+ Agents (CS 教授)

### 5.1 瓶頸分析

| 瓶頸 | 位置 | 影響 |
|------|------|------|
| `iterrows()` in CACR decomposition | L555-572 | 500K rows → 分鐘級 |
| 8次重複掃描 traces list | `_compute_benchmark` × 8 | 8 full scans |
| 全量載入 JSONL | `load_traces()` | ~4GB at 500K |

### 5.2 解決方案

- **Streaming TraceReader**: O(N_agents) memory, yield chunks
- **Single-pass extraction**: 預分組 (by flood_zone, tenure, mg)，1 scan 取代 8
- **Per-seed parallelism**: `ProcessPoolExecutor` 跨 seed 並行
- **orjson**: 替換 stdlib json，3-5x 加速

### 5.3 記憶體估算
- 目前 5,198 traces: ~10MB → OK
- 10K × 50yr = 500K traces: ~4GB (全量) → ~50MB (streaming)

---

## 6. 跨領域擴展 (水資源專家)

### 6.1 現有兩個領域的差距

| 面向 | 防洪 (已有) | 灌溉 (部分) | 缺少的抽象 |
|------|------------|-------------|-----------|
| 構念理論 | PMT (TP/CP) | WSA/ACA | ConstructCoherenceSpec |
| 經驗基準 | 8 benchmarks dict | 無標準化 | BenchmarkRegistry format |
| 幻覺規則 | hard-coded if/else | hard-coded | HallucinationSpec |
| Agent type | owner/renter | cluster-based | 通用分組 |

### 6.2 未來水資源領域

- **地下水管理**: DA/PF constructs, SGMA governance, 空間 externalities
- **都市用水**: Conservation motivation, price elasticity (-0.1 to -0.4)
- **乾旱回應**: Fallowing rates, water market, crop switching

---

## 7. Elevation rate = 0.57 問題 (水資源專家)

### 根本原因
1. **無容量約束**: 模擬中墊高是瞬時決策，現實中 NJ post-Sandy 每年僅 50-80 件
2. **Subsidy feedback loop**: 政府增補助 → 墊高變便宜 → 更多墊高 → 無 damping
3. **LLM anchoring bias**: 墊高選項有詳細成本效益資訊，小 LLM 傾向選「最負責任」的選項

### 建議修復
- 加 **per-year elevation cap** (5-8% of unelevated owners)
- 報告 **subsidy-conditioned elevation rate** 作為補充指標
- Prompt fix 已提交 (7f92e7e)，等重跑驗證

---

## 8. 實施路線圖

| Phase | 內容 | 工時 | 狀態 |
|-------|------|------|------|
| Phase 0 | 修 P0 bugs + golden regression test | 0.5 天 | ✅ 完成 |
| Phase 1 | 常數外部化 YAML (rules, benchmarks) | 1 天 | 🔲 |
| Phase 2 | 拆分子模組 (metrics/, io/, reporting/) | 2 天 | 🔲 |
| Phase 3 | BehavioralTheory protocol + TheoryRegistry | 2 天 | 🔲 |
| Phase 4 | BenchmarkComputation plugins | 2 天 | 🔲 |
| Phase 5 | Streaming TraceReader + ValidationRunner facade | 1.5 天 | 🔲 |
| **Total** | | **~9 天** | |

---

## 9. 各專家建議摘要

### LLM 專家 (15 項)
- P0: EBE bug, UNKNOWN default
- P1: CACR-by-year, 整合 PsychologicalFramework ABC, agent type fix
- P2: Sycophancy, streaming, benchmark YAML, cross-model report
- P3: Reasoning NLI, position bias, cacr_effective, degenerate output

### 社會科學專家 (8 項)
- High: Construct circularity, social dynamics validation (Moran's I)
- Medium: TheoryValidator protocol, EBE bounds grounding, SC/SP constructs unused
- Low: Reframe as "theory-informed behavioral fidelity", PMT rule acknowledgement

### 水資源專家 (8 項)
- High: Elevation capacity constraint, ConstructCoherenceSpec, temporal trajectory metrics
- Medium: Spatial autocorrelation, EPI confidence intervals, BenchmarkRegistry
- Low: Subsidy-conditioned benchmark, agent_type in audit CSV

### CS 教授 (完整架構)
- 7 sub-packages + 6 phase migration + 60+ test pyramid
- BehavioralTheory / HallucinationRule / BenchmarkComputation protocols
- Streaming + batch dual-mode TraceReader
- YAML declarative domain definition
- Golden regression test as safety net

---

*產生日期: 2026-02-14*
