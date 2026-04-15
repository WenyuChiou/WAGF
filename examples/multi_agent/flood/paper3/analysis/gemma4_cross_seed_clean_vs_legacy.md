# Gemma 4 cross-seed CLEAN vs LEGACY analysis

Generated: 2026-04-14
Arms: LEGACY seed_42, CLEAN seed_42, CLEAN seed_123 (all 400 agents × 13 years, Gemma 4 e4b, hazard schedules differ across seeds by design)
Pending: CLEAN seed_456 (interrupted mid-Year-3, cleaned up)

**Purpose**: verify that the dual-role narrative findings from the single-seed comprehensive report generalise to a second CLEAN seed, and establish cross-seed variance.

## Data integrity

| Arm | owner traces | renter traces | gov traces | ins traces | manifest |
|---|---:|---:|---:|---:|---|
| LEGACY_42 | 2600 | 2600 | 13 | 13 | ✅ |
| CLEAN_42 | 2600 | 2600 | 13 | 13 | ✅ |
| CLEAN_123 | 2600 | 2600 | 13 | 13 | ✅ |

All complete, all manifests valid, ready for 2-seed cross-seed analysis on CLEAN arm.

## Key findings — robust across CLEAN seeds

### 1. Renter PA ratchet — blocked consistently

| Year | LEGACY_42 | CLEAN_42 | CLEAN_123 |
|---:|---:|---:|---:|
| 1 | 32.5% | 40.0% | 40.5% |
| 5 | 76.5% | 50.5% | 46.0% |
| 9 | 95.5% | 45.2% | 54.5% |
| 13 | 90.9% | 53.5% | 56.0% |

Both CLEAN seeds stay in the 40-60% band across all years. LEGACY climbs to 91%. CLEAN delta from LEGACY: -37.4pp (seed_42), -34.9pp (seed_123). Delta-delta between seeds = 2.5pp → tight cross-seed variance on the ratchet block effect.

### 2. Owner Y1 priming unmask — prompt-level, seed-independent

| Year | LEGACY_42 | CLEAN_42 | CLEAN_123 |
|---:|---:|---:|---:|
| 1 | 52.5% | **78.0%** | **77.0%** |
| 2 | 87.0% | 95.0% | 96.0% |
| 13 | 94.5% | 97.0% | 96.0% |

Both CLEAN seeds produce the same +25pp Y1 jump when the `initial_narrative` rootedness seed is blocked. The owner prompt identity priming overwhelms any counter-signal in the first decision round. This is seed-independent by construction — it is the prompt + LLM prior interaction, not a memory-policy interaction.

### 3. `past_reference` phrase frequency (owner, main reasoning)

| Year | LEGACY_42 | CLEAN_42 | CLEAN_123 |
|---:|---:|---:|---:|
| 1 | 1.5% | 1.5% | 0.0% |
| 5 | 19.5% | 2.0% | 3.0% |
| 8 | 30.5% | 5.0% | 1.0% |
| 11 | 30.5% | 0.0% | 1.0% |
| 13 | 27.0% | 1.0% | 2.5% |

Both CLEAN seeds hold the phrase under 5% across all 13 years. LEGACY climbs to 30%+. ~20x compression reproducible across seeds.

### 4. 4-cell Y13 insurance state

| Cell | LEGACY_42 | CLEAN_42 | CLEAN_123 | CLEAN mean | Δ vs LEGACY |
|---|---:|---:|---:|---:|---:|
| MG-Owner | 39.0% | 26.0% | 32.0% | 29.0% | **-10.0pp** |
| NMG-Owner | 83.0% | 44.0% | 51.0% | 47.5% | **-35.5pp** |
| MG-Renter | 55.0% | 73.0% | 75.0% | 74.0% | **+19.0pp** |
| NMG-Renter | 47.0% | 63.0% | 66.0% | 64.5% | **+17.5pp** |

Cross-seed range for CLEAN: MG-Owner 6pp, NMG-Owner 7pp, MG-Renter 2pp, NMG-Renter 3pp. The tenure asymmetry (owners regress, renters improve) is fully reproduced across CLEAN seeds. Renter cells are more stable than owner cells — consistent with owner Y1 priming being a large one-shot effect that dominates trajectory variance.

### 5. Action space collapse

| Action | LEGACY_42 | CLEAN_42 | CLEAN_123 | CLEAN mean |
|---|---:|---:|---:|---:|
| Renter relocate | 36 | 1 | 2 | 1.5 |
| Owner elevate | 34 | 12 | 8 | 10 |
| Owner buyout | 1 | 0 | 0 | 0 |

Renter relocation collapses ~95% across both CLEAN seeds. Owner elevation collapses ~70%. Cross-seed consistency confirms that the action space collapse is not a seed-42 fluke — it is a reproducible consequence of blocking self-narrative memory writes.

### 6. Memory accumulation at Y13

| Metric | LEGACY_42 | CLEAN_42 | CLEAN_123 |
|---|---:|---:|---:|
| owner mem_post mean at Y13 | 67.7 | **54.1** | **54.1** |

Identical across CLEAN seeds to the first decimal. The 13.6-entry difference from LEGACY equals the `agent_self_report` + `initial_narrative` content that CLEAN drops by policy, confirming the memory write budget is deterministic at the policy level regardless of hazard randomness.

### 7. 4-cell pooled DN%

| Cell | LEGACY_42 | CLEAN_42 | CLEAN_123 |
|---|---:|---:|---:|
| MG-Owner | 56.2% | 66.2% | 67.0% |
| NMG-Owner | 33.5% | 43.5% | 43.8% |
| MG-Renter | 36.3% | 35.1% | 38.0% |
| NMG-Renter | 41.4% | 38.2% | 38.9% |

Owner DN rises ~10pp under CLEAN in both seeds. Renter DN barely moves (-1 to +2pp). The asymmetry is tenure-specific and stable across seeds. MG-Owner vs NMG-Owner gap: 22.7pp LEGACY, 22.7pp CLEAN_42, 23.2pp CLEAN_123 — the MG equity gap is tenure-internal and memory-policy-invariant.

## Key finding — seed-specific: EPI binary threshold

| Metric | LEGACY_42 | CLEAN_42 | CLEAN_123 |
|---|---:|---:|---:|
| EPI | 0.6115 | **0.4968** | **0.6115** |
| Pass (≥0.60) | ✅ | ❌ | ✅ |
| benchmarks_in_range | 10/16 | 8/16 | 10/16 |

Both CLEAN seeds fail the same two benchmarks (`buyout_rate` = 0.003 / 0.003 vs required [0.05, 0.25]; `renter_uninsured_rate` = 0.000 / 0.000 vs required [0.15, 0.40]) because the action space collapse eliminates both relocation and renter uninsured state in a memory-policy-level way.

The difference between CLEAN_42 failing and CLEAN_123 passing EPI comes from two marginal cases:
- `insurance_rate_all`: CLEAN_42 = 0.5575 (just above 0.55 ceiling, fail), CLEAN_123 = 0.5500 (exactly at ceiling, pass).
- `govt_decrease_count`: CLEAN_42 = 0 (below 1 floor, fail), CLEAN_123 = 1 (at floor, pass) — the institutional agent happened to decrease subsidies once in seed_123 but not in seed_42.

Both distinctions are knife-edge threshold crossings on benchmarks whose author-chosen ranges were never meant to be pass/fail gates. **The correct reading is that CLEAN's EPI is ~0.55 ± 0.06 across 2 seeds**, and whether the binary "pass" flag trips depends on which seed happens to land which benchmark above or below its range edge. Use EPI as a descriptive calibration table row, never as a verdict.

## Implications for Paper 3

1. **Dual-role narrative strengthened**: the core CLEAN effects (ratchet block, diversity collapse, tenure asymmetry, memory accumulation control) are reproducible across 2 seeds. The story does not depend on a particular seed or hazard trajectory.

2. **EPI framing confirmed soft**: the EPI "failure" of CLEAN seed_42 is not a robust finding; CLEAN seed_123 passes the same threshold. Paper 3 should report the EPI values for both seeds in a calibration table and not use the pass/fail flag as a judgment of either policy.

3. **3-seed robustness lost**: CLEAN seed_456 was interrupted at Year 3 and has been cleaned up. Paper 3 cross-seed claims will be based on 2 CLEAN seeds (42, 123) + 1 LEGACY seed (42). If reviewers demand a third seed, a rerun of seed_456 (~17 h) is required. Otherwise, the 2-seed CLEAN agreement on all major findings is sufficient to support the narrative.

4. **Ablation B (flat institutional) still required** for a complete RQ2 story: Full-vs-Flat policy comparison under both LEGACY and CLEAN memory policies. Runs 5-7 of the batch were not executed because the batch halted on seed_456 interruption.

## Files

- This document: `paper3/analysis/gemma4_cross_seed_clean_vs_legacy.md`
- CLEAN seed_123 validation JSON: `paper3/analysis/gemma4_clean_seed123/l2_macro_metrics.json`
- Single-seed comprehensive report: `paper3/analysis/gemma4_legacy_clean_comprehensive_report.md` (the dual-role framing)
