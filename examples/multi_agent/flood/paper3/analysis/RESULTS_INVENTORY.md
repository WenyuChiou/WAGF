# Paper 3 完整盤點 (2026-03-20)

## 1. 實驗數據狀態

| 實驗 | Seeds | Traces (per seed) | 狀態 |
|------|-------|------------------|------|
| Full hybrid_v2 | 42, 123, 456 | 2600 owner + 2600 renter = 5,200 | ✅ ALL COMPLETE |
| Ablation A (replay) | 42 | 5,200 | ✅ manipulation check only |
| Ablation B (flat baseline) | 42, 123, 456 | 5,200 each | ✅ ALL COMPLETE |
| Traditional ABM baseline | single run | ~52K HH, 13yr | ✅ yearly action rates |
| Traditional ABM MC | 50 runs | timeseries CSV | ✅ (cumulative only) |
| **L3 ICC probing** | N/A | 2,700 probes | ✅ pre-experiment |
| **L3 persona sensitivity** | N/A | 80 calls | ✅ |
| **L3 prompt sensitivity** | N/A | 120 calls | ✅ |

**是否需要補跑？** 不需要。3 seeds cross-seed CV < 5%，所有定性發現一致。

---

## 2. Validation 狀態

### L1 Micro (per-decision coherence) — seed_42 ONLY

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| CACR | 0.853 | ≥ 0.80 | ✅ PASS |
| R_H | 0.000 | ≤ 0.10 | ✅ PASS |
| EBE | 1.438 (ratio=0.62) | > 0 | ✅ PASS |

⚠️ **TODO**: L1 metrics 只計算了 seed_42。需要跑 seed_123 和 seed_456 的 L1，並報告 cross-seed mean ± SD。

### L2 Macro (empirical benchmarks) — seed_42 ONLY, EPI=0.809

| Benchmark | Value | Range | Status | Cross-seed stability |
|-----------|-------|-------|--------|---------------------|
| B1: insurance_rate_sfha | 0.461 | 0.30-0.60 | ✅ PASS | stable (~0.33) |
| B2: insurance_rate_all | 0.338 | 0.15-0.55 | ✅ PASS | stable |
| B3: elevation_rate | 0.280 | 0.10-0.35 | ✅ PASS | stable (0.135-0.137) |
| B4: buyout_rate | 0.228 | 0.05-0.25 | ✅ PASS | ⚠️ 0.025-0.032 per-year |
| B5: dn_postflood | 0.471 | 0.35-0.65 | ✅ PASS | stable (0.38-0.41) |
| B6: mg_adaptation_gap | 0.050 | 0.05-0.30 | ✅ PASS (邊界) | need check |
| B7: renter_uninsured_rate | 0.578 | 0.15-0.40 | ❌ FAIL | 0.655-0.670 |
| B8: insurance_lapse_rate | 0.557 | 0.15-0.30 | ❌ FAIL | 0.230-0.250 |
| B9-B16 (institutional) | various | various | 13/16 PASS | seed_42 only |

⚠️ **TODO**:
- 跑 seed_123、seed_456 的完整 L2 (compute_validation_metrics.py)
- 計算 cross-seed EPI mean ± SD
- **B7 renter_uninsured (0.66 vs 0.15-0.40)**: 持續 FAIL，所有 seeds 一致 → 系統性偏差，非隨機
- **B8 lapse_rate**: 用 audit trace 算的是 0.23-0.25 (PASS)，但 validation_report 顯示 0.557 (FAIL) → 計算方法可能不一致，需要檢查

### L3 Cognitive (pre-experiment) — COMPLETE

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| ICC(2,1) TP | 0.964 | ≥ 0.60 | ✅ PASS |
| ICC(2,1) CP | 0.947 | ≥ 0.60 | ✅ PASS |
| eta² TP | 0.330 | ≥ 0.25 | ✅ PASS |
| eta² CP | 0.544 | ≥ 0.25 | ✅ PASS |
| Persona sensitivity | 75% | ≥ 75% | ✅ PASS (邊界) |
| Positional bias | 1/3 | - | ⚠️ flagged OK |
| Framing effect | 1/3 | - | ⚠️ flagged OK |

**L3 不需要補做。** Pre-experiment validation，與 seeds 無關。

---

## 3. RQ 結果摘要

### RQ1: Traditional ABM vs LLM-ABM (3 seeds)

| Metric | MAD | Classification | Cross-seed CV |
|--------|-----|---------------|---------------|
| Owner EH | 1.1pp | CONVERGE | < 1% |
| Owner BP | 1.0pp | CONVERGE | < 2% |
| Renter FI | 5.1pp (r=+0.83***) | MODERATE | < 3% |
| Owner FI | 12.9pp (r=-0.58*) | DIVERGE | < 3% |
| Renter RL | 21.9pp | DIVERGE | < 5% |
| Renter DN | 24.0pp | DIVERGE | < 5% |

**狀態**: ✅ 分析完成，結果穩定。Section 4.1 尚未寫。

### RQ2: Institutional Endogenization (3 seeds pooled, N=7,800)

| 比較 | chi² | p | V | Status |
|------|------|---|---|--------|
| Owner overall | 10.66 | 0.014 | 0.026 | Significant, negligible |
| Renter overall | 11.84 | 0.003 | 0.028 | Significant, negligible |
| MG owner | 4.41 | 0.220 | 0.024 | NOT significant |
| NMG owner | 7.48 | 0.058 | 0.031 | Approaching |
| Affordability blocking | +40 MG rejections | — | — | Equity channel |

**狀態**: ✅ 分析完成。Section 4.3 已更新 pooled 結果。

### RQ3: PMT Construct Dynamics (3 seeds, preliminary)

| Finding | Value | Cross-seed CV |
|---------|-------|---------------|
| TP accumulation (Y1→Y13) | 3.06 → 3.37 (+0.31) | 1.8% |
| CP ceiling | ~2.79 (M) all years | 1.3% |
| TP-CP gap MG (Y13) | 0.66 | ~4% |
| TP-CP gap NMG (Y13) | 0.50 | ~4% |
| TP shock (flooded) | 83% H+VH | stable |
| TP decay rate (4yr) | 11.2% (vs Trad 30-50%) | N/A |
| do_nothing rise | 46% → 67% (Y1→Y10) | 3.2% |

**狀態**: 數據分析完成，尚未寫正式腳本和 Section 4.4。

---

## 4. Paper Draft 狀態

| Section | Status | Notes |
|---------|--------|-------|
| 1. Introduction | ⚠️ 需要大幅修改 | 舊版基於 paper3_primary，需更新 RQ framing |
| 2. Study Area | ✅ 基本完成 | PRB 描述 |
| 3. Methods | ⚠️ 部分完成 | 需更新：RQ 定義、ablation 設計、Traditional ABM 比較方法 |
| 4.1 Validation | ✅ 基本完成 | 需更新 cross-seed metrics |
| 4.2 RQ1 | ❌ 未寫 | 有數據，需寫 section |
| 4.3 RQ2 | ✅ 已更新 pooled 結果 | 教授已 review 過單 seed 版 |
| 4.4 RQ3 | ❌ 需要替換 | 舊版是 gossip/social → 新版是 PMT dynamics |
| 4.5 Cross-seed | ❌ 需重寫 | 舊腳本用 seeds 42/43/44 → 需改為 42/123/456 |
| 5. Discussion | ❌ 未寫 | |
| 6. Conclusion | ❌ 未寫 | |

---

## 5. 需要與教授討論的問題

### 5.1 B7 renter_uninsured 持續 FAIL (0.66 vs 0.15-0.40)

**問題**: 所有 seeds 的 renter uninsured rate 都在 65-67%，遠超目標 15-40%。
**原因**: Renter 的 contents insurance 需求本身較低（平均 RCV_contents 只有 $15-40K），且 prompt 設計中 renter 的 default action 是 do_nothing。
**選項**:
- (a) 調整 benchmark range（引用 renter 保險文獻的更寬範圍）
- (b) 在 Discussion 中承認為 known limitation
- (c) 不處理（EPI 已 ≥ 0.80，且 B7 weight=1.0）

### 5.2 RQ2 效應量 negligible (V=0.026)

**問題**: chi² 顯著但 V < 0.03 → 審稿人可能說「既然效應量 negligible，為什麼要 endogenize？」
**建議 framing**:
- Aggregate 效應小是因為制度參數差異窄 (50% vs 65%)
- 真正的效應在 equity channel (+40 MG rejections, +33%)
- 結論：fixed params 在 aggregate 合理，但會 miss equity consequences

### 5.3 RQ3 是否合適？

**問題**: PMT constructs 是 LLM self-report，不是 validated measures。
**辯護**: 我們不 claim 這是真實心理，而是 LLM 的動態 re-evaluation 產生了與 static-parameter ABM 不同的 emergent patterns，且這些 patterns 與災害適應文獻一致（TP accumulation, adaptation fatigue）。
**需要教授確認**: 這個 framing 是否能通過 WRR review。

### 5.4 Cross-seed robustness script 過時

**問題**: 現有 `cross_seed_robustness.py` 使用 seeds 42/43/44（舊 paper3_primary 數據）。
**TODO**: 改為 seeds 42/123/456，更新所有 RQ 分析，重新生成 Figure 5。

### 5.5 Section 4.2 (RQ1) 尚未寫

RQ1 是三個 RQ 中最重要的（framework-level comparison），但 paper section 尚未起草。需要與教授確認 RQ1 的 framing 和深度。

### 5.6 L1 validation 需要 multi-seed

目前 CACR, R_H, EBE 只計算了 seed_42。WRR 審稿人可能要求跨 seed 的 validation metrics。需要跑 `compute_validation_metrics.py` for seed_123 and seed_456。

---

## 6. 行動項目（優先順序）

| # | Task | Effort | Blocking? |
|---|------|--------|-----------|
| 1 | Run L1/L2 validation for seed_123, seed_456 | 30 min | YES — paper needs cross-seed validation |
| 2 | Update cross_seed_robustness.py (42/43/44 → 42/123/456) | 1 hr | YES — Section 4.5 |
| 3 | Write RQ3 analysis script | 1 hr | YES — Section 4.4 |
| 4 | Write Section 4.2 (RQ1) | 2 hr | YES — main contribution |
| 5 | Rewrite Section 4.4 (RQ3: PMT dynamics) | 2 hr | YES |
| 6 | Rewrite Section 4.5 (cross-seed) | 1 hr | YES |
| 7 | Resolve B7 renter_uninsured FAIL | 30 min | Should discuss with professor |
| 8 | Run seed_789 (if professor requests) | ~12 hr | NO — only if requested |
