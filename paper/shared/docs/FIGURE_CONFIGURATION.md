# WAGF WRR Paper - Figure Configuration

**Date**: 2026-02-04
**Decision**: Final figure allocation for submission

---

## Main Text Figures (4 figures)

### Figure 1: WAGF Architecture
- **File**: `paper/figures/sage_architecture.png` (OneDrive)
- **Status**: ✅ DONE
- **Location**: Section 2 (WAGF Architecture)
- **Purpose**: Illustrate Three-Pillar design (Governance + Memory + Context)
- **Note**: Convert to white background before submission

---

### Figure 2: Flood Case Study Results (3-panel)
- **File**: `examples/single_agent/analysis/paper_figures/flood_combined_3panel.png`
- **Status**: ✅ DONE
- **Location**: Section 4.3 (Flood Results)
- **Panels**:
  - (a) Decision adoption over time (elevate, insure, relocate, both, nothing)
  - (b) Normalized Shannon Entropy (H_norm) - Raw vs Corrected
  - (c) Hallucination Rate (R_H) by group
- **Purpose**: Show governance eliminates hallucination while preserving diversity

---

### Figure 3: Cross-Model EBE Scaling
- **File**: `examples/single_agent/analysis/paper_figures/ebe_scaling_cross_model.png`
- **Status**: 🔴 BLOCKED - Need all flood B/C experiments complete
- **Location**: Section 4.3 (Flood Results)
- **Purpose**: Demonstrate governance prevents mode collapse across 6 models
- **Remaining**: gemma3:27b C, ministral3:14b C

---

### Figure 4: Irrigation CRSS Comparison (UB/LB)
- **File**: `docs/papers/figures/crss_v11_ub_lb_comparison.png` ✅
- **Status**: ✅ DONE (v11 complete)
- **Location**: Section 5.2 (Irrigation Results)
- **Size**: 3570 × 2666 pixels (11.9" × 8.9" @ 300 DPI)
- **Panels**:
  - (a) **Upper Basin**: CRSS baseline vs WAGF request vs WAGF diversion
  - (b) **Lower Basin**: CRSS baseline vs WAGF request vs WAGF diversion
- **Caption** (outline.tex line 246):
  > Aggregate water demand trajectories for (a) Upper Basin and (b) Lower Basin, 2019–2060. Dark line: CRSS static baseline (USBR, 2012). Gray line: WAGF-governed agent requests (post-governance, pre-curtailment). Blue line: WAGF actual diversions (post-curtailment). Shaded area represents the "paper water" gap between static projections and curtailed allocations. 78 real CRSS districts, Gemma 3 4B, strict governance with human-centric memory.
- **Additional note**: Add one sentence about UB water rights including over-appropriation (historical phenomenon in Colorado River Basin)

---

## Supplementary Information Figures

**Rationale for Minimal SI**: This is a Technical Methods paper focused on framework demonstration, not exhaustive experimental documentation. SI reduced from 8 to 3 figures to emphasize core contributions.

### Figure S1: Governance Validation Pipeline
- **File**: `examples/single_agent/analysis/paper_figures/governance_pipeline.png`
- **Status**: ✅ DONE
- **Purpose**: Illustrate validator chain execution flow (Pillar 1: Governance)
- **Decision**: ✅ **KEEP** - Essential to understand governance mechanism

---

### Figure S2: Cumulative Relocation
- **File**: `examples/single_agent/analysis/paper_figures/cumulative_relocation.png`
- **Status**: ✅ DONE
- **Purpose**: Show memory-driven long-term behavioral shift (Pillar 2: Memory)
- **Decision**: ✅ **KEEP** - Demonstrates memory pillar effectiveness

---

### Figure S3: Lake Mead Elevation + Tier Dynamics (formerly S4)
- **File**: `docs/papers/figures/crss_v11_mead_elevation.png` ✅
- **Status**: ✅ DONE
- **Size**: 2969 × 1762 pixels (187 KB)
- **Purpose**: Validate hydrological realism (1004-1173 ft range, Tier 0-3 shortages)
- **Decision**: ✅ **KEEP** - Validates domain transferability and physical realism

---

### Removed Figures (rationale)


- ~~Figure S3: Economic Hallucination (v9 vs v11)~~ → Technical detail, can be discussed in text
- ~~Figure S5: Supply-Demand Dynamics~~ → Redundant with main Figure 4
- ~~Figure S6: Decision Composition Over Time~~ → Descriptive statistics, not framework demonstration
- ~~Figure S7: Drought Index vs Mead Scatter~~ → Domain-specific analysis
- ~~Figure S8: Agent Behavioral Heatmap~~ → Exceeds methods paper scope

---

## Table (Main Text)

### Table 1: Domain Mapping
- **Location**: Section 2.3 (Domain Instantiation)
- **Status**: ✅ Defined in outline.tex (lines 128-147)
- **Purpose**: Compare WAGF instantiation across flood and irrigation domains

---

## Page Unit Budget

| Component | Allocation | Status |
|-----------|------------|--------|
| Text (7 sections) | 8.8 PU | ✅ |
| Figure 1-4 | ~3.5 PU | Fig 3 blocked |
| Table 1 | ~0.3 PU | ✅ |
| SI Figures (8) | N/A | Mostly done |
| **Total Main Text** | **~12.6 PU** | Within 13 PU limit ✓ |

---

## Next Actions

1. ✅ **Confirmed**: Use `crss_v11_ub_lb_comparison.png` as Figure 4
2. ⏳ **Pending**: Add one sentence in Section 5.1 about UB water rights over-appropriation
3. 🔴 **Blocked**: Generate Figure 3 when all flood experiments complete
4. ⏳ **Pending**: Copy all SI figures to `paper/figures/SI/` directory
5. ⏳ **Pending**: Update `SAGE_WRR_SI.docx` with SI figure references

---

## Rationale for Figure 4 Choice

**Why `crss_v11_ub_lb_comparison.png`?**

1. **Fits paper scope**: This is a *Technical Methods* paper, not a hydrological study
2. **Demonstrates framework**: Shows WAGF governance in a second domain (transferability)
3. **Page efficient**: Single 2-panel figure vs multiple figures
4. **Clear message**: "Paper water gap" illustrates governance effectiveness
5. **Expert consensus**: Recommended as most appropriate for Methods paper

**What about the other 5 irrigation figures?**
- All moved to SI (Fig S4-S8) for interested readers
- Provides complete documentation without bloating main text
- Follows WRR Technical Reports format (concise main text + detailed SI)

---

**Last Updated**: 2026-02-04 09:30 PM
**Approved By**: User decision ("把最合理的結果放上去即可")

