# WAGF WRR Paper - Technical Reports/Methods

## Framework Positioning (WRR Technical Note)

### Naming Decision (Working Recommendation)

- **Recommended framework name**: **WAGF**
- **Expansion**: **Water Agent Governance Framework**
- **Positioning sentence**: WAGF is a domain-configurable governance framework for LLM-driven agent-based modeling in human-water systems.

### Why this positioning

- It presents the work as a **framework-level method**, not a single-case model.
- It keeps a clear **water-systems identity** for WRR readership.
- It frames the core contribution as **governance for bounded rationality**, not full rational-agent enforcement.

### Core argument to use in Introduction

Traditional water ABMs often encode behavior through theory-based assumptions of rational adaptation. LLM agents increase behavioral realism and heterogeneity, but retain hallucination risks (state-inconsistent proposals, parser-intent mismatch, and appraisal-action incoherence) that can bias interpretation if left unchecked. We therefore position WAGF as a governance layer between LLM agents and simulation engines, with the primary objective of behavioral rationalization under bounded rationality while preserving population-level behavioral diversity. In the module pipeline, `identity rules` and `physical rules` are enforced as first-pass constraints before softer thinking/coherence checks; together with skill-level action contracts, retry-with-feedback control, and audit logging, this improves decision coherence without collapsing adaptive heterogeneity. Physical feasibility diagnostics (`R_H`) are retained as a safety channel, but the main reported gain is reduced rationality deviation (`R_R`) with maintained effective diversity (`EHE`).

### Core argument to use in Discussion

The key methodological shift is from unconstrained generative behavior to auditable bounded rationality. In this framing, governance does not force optimality; it selectively suppresses coherence failures while retaining meaningful variation in agent behavior. This resolves a central adoption barrier for LLM-ABM in water systems: black-box outputs can be inspected through rule triggers, rejection reasons, retry outcomes, and intervention statistics. The framework is transferable across domains because physics, institutions, and behavioral theory slots are configuration-defined (skills, validators, prompts), while the governance runtime remains unchanged. Irrigation evidence is used primarily as transferability support, not as the main claim driver.

## Current Versions (2026-02-09)

| File | Description | Status |
|------|-------------|--------|
| `SAGE_WRR_Paper_v13.docx` | Main manuscript (irrigation section reframed as application showcase; de-emphasized comparative claims) | **LATEST** |
| `SAGE_WRR_Paper_v12.docx` | Previous manuscript snapshot | Previous |
| `SAGE_WRR_Paper_v11.docx` | Previous manuscript snapshot | Previous |
| `SAGE_WRR_Paper_v10.docx` | Previous manuscript (Section 5 irrigation: quantitative evidence + SI refs + cold-start + governance metrics) | Previous |
| `SAGE_WRR_Paper_v9.docx` | Previous manuscript (user edits on S7 diagnostics) | Previous |
| `SAGE_WRR_Paper_v8.docx` | Previous manuscript (revised narrative + table refresh) | Archived |
| `SAGE_WRR_Paper_v7.docx` | Previous main manuscript snapshot | Archived |
| `SAGE_WRR_SI_Tables_v6.docx` | Supporting Information (reorganized: S1-S9, 4 new sections) | **LATEST** |
| `SAGE_WRR_SI_Tables_v5.docx` | Previous SI tables (flood Tables S1-S2 to be merged into v6) | Previous |

**Editing Tool**: Microsoft Word

## Irrigation Evidence Status (v20 FINAL)

- **Production v20 COMPLETE**: 78 agents x 42yr, gemma3:4b, seed 42 (finalized 2026-02-08)
- Full dataset archived at `examples/irrigation_abm/results/production_v20_42yr/`:
  - `simulation_log.csv` (3,276 rows), `irrigation_farmer_governance_audit.csv`, `raw/irrigation_farmer_traces.jsonl`
- Smoke validation: **8/10 pass** (all CRITICAL checks pass)
- Key metrics: Mean=5.873 MAF (1.003x CRSS), CoV=9.2%, 88% within CRSS +/-10%
- Authoritative metrics: `examples/irrigation_abm/analysis/v20_metrics.json`
- Section 5 updated with final 42yr numbers (tracked changes in v6.docx)

---

## Figure & Table Configuration

### Main Paper (3 Figures + 1 Table = 4 PU)

WRR Technical Reports/Methods limit: **13 Publication Units (PU)** max

| Item | Content | File |
|------|---------|------|
| **Fig 1** | WAGF Framework (multi-panel: a. Architecture + b. Governance flow) | `figures/fig1_architecture.png` |
| **Fig 2** | Flood ABM cross-model consistency | `figures/fig2_flood_combined.png` |
| **Fig 3** | Irrigation ABM: demand vs CRSS + governance outcomes | `figures/fig3_irrigation.png` |
| **Table 1** | Main metrics (6 models x 3 groups): executed `R_R`, `R_H`, `EHE` with per-cell `n_runs` | Embedded in Word; source: `tables/Table1_executed_metrics_clean_v2.csv` |

**PU Calculation**: 3 figures + 1 table = **4 PU**

### Supporting Information (v6 — Reorganized)

**Document**: `SAGE_WRR_SI_Tables_v6.docx`

| Section | Content | Source Markdown |
| ------- | ------- | -------------- |
| **Part A: Framework-Level** | | |
| S1 | Prompt templates and response format (flood + irrigation) | `SI/Section_S1_Prompt_Templates.md` |
| S2 | Governance retry mechanism and EarlyExit algorithm | `SI/Section_S2_Retry_EarlyExit.md` |
| **Part B: Flood Case Study** | | |
| S3 / Table S1 | Complete 18-row multi-model data (6 models x 3 groups) | Retained from v5.docx |
| S3 / Table S2 | `R_H` (strict feasibility safety diagnostic) by model size | Retained from v5.docx |
| S4 | Flood behavioral diagnostics (4 trace-backed cases) | `SI/Section_S7_Behavioral_Diagnostics_Examples.md` |
| S5 / Figure S1 | 6x3 Adaptation matrix | `flood/figures/SI_Figure_Adaptation_Matrix_6x3.png` |
| S5 / Figure S2 | Cumulative relocation (A=0%, B=32%, C=37%) | `flood/figures/fig_s2_relocation.png` |
| S5 / Figure S3 | Economic hallucination fix (v4 vs v6) | `flood/figures/fig_s3_econ_hallucination.png` |
| S5 / Figure S4 | Gemma3 3x3 adaptation matrix | `flood/figures/SI_Figure_Adaptation_Gemma3_3x3.png` |
| S5 / Figure S5 | Ministral3 3x3 adaptation matrix | `flood/figures/SI_Figure_Adaptation_Ministral3_3x3.png` |
| **Part C: Irrigation Case Study** | | |
| S6 / Table S3-S4 | Complete governance rule specification (12 validators + 3 thinking rules) | `SI/Section_S6_Governance_Rules.md` |
| S7 / Table S4-S5 | FQL-to-LLM persona cluster mapping + Gaussian magnitude params | `SI/Section_S7_FQL_Cluster_Mapping.md` |
| S8 | Mass balance and human-water coupling (with LaTeX equations) | `SI/Section_S8_Mass_Balance.md` |
| S9 / Table S6 | Irrigation governance summary (v20 42yr production) | `SI/Table_S3_Irrigation_Governance.md` |

**Numbering map (v5 → v6)**:

| v5 ID | v6 ID | Change |
| ----- | ----- | ------ |
| — | S1 | NEW: Prompt templates |
| — | S2 | NEW: Retry + EarlyExit |
| Table S1 | S3/Table S1 | Moved to Part B |
| Table S2 | S3/Table S2 | Moved to Part B |
| Section S7 | S4 | Renumbered |
| Figures S1-S5 | S5/Fig S1-S5 | Moved to Part B |
| — | S6 | NEW: Governance rules |
| — | S7 | NEW: FQL cluster mapping |
| Section S6 | S8 | Updated + renumbered |
| Table S3 | S9/Table S6 | Renumbered |

---

## WRR Technical Reports/Methods Limits

| Requirement | Limit |
|-------------|-------|
| **Total PU** | <= 13 (PU = words/500 + figures + tables) |
| **Word count** | <= 4,500 (with 4 display items; current: ~3,320 = 10.6 PU) |
| **Abstract** | <= 150 words |
| **Figures + Tables** | Current: 3 fig + 1 table = 4 PU |
| **References** | No strict limit for Technical Reports |

### Image Specifications

| Requirement | Specification |
|-------------|---------------|
| **Format** | TIFF, EPS, PDF (vector preferred); JPEG for photos |
| **Resolution** | Line art: 1000 dpi; Color: 300-600 dpi |
| **Size** | Single column: 8.5 cm; Double column: 17.5 cm |
| **Font size** | >= 6 pt after scaling |

### Word Document Settings

- **Font**: Times New Roman 12pt
- **Line spacing**: Double-spaced
- **Margins**: 2.5 cm all sides
- **Page numbers**: Centered at bottom
- **Line numbers**: REQUIRED

---

## Pre-Submission Checklist

- [ ] Line numbers enabled
- [ ] Double-spaced throughout
- [ ] All images >= 300 dpi
- [ ] Data Availability Statement included
- [ ] All SI items referenced in main text
- [ ] AI Tools Disclosure statement
- [ ] Key Points section (3 bullet points, 140 chars each)
- [ ] Abstract <= 150 words
- [ ] Word count <= 5,000

---

## Editing Workflow

1. Edit the current v6 file in Word
2. When complete, save as v7
3. Move old version to `archive/`
4. Update this README with new version info

---

## Directory Structure

```
paper/
+-- PAPER_README.md              # This file
+-- SAGE_WRR_Paper_v8.docx       # Latest main manuscript
+-- SAGE_WRR_Paper_v7.docx       # Previous main manuscript snapshot
+-- SAGE_WRR_Paper_v5.docx       # Previous main manuscript baseline
+-- SAGE_WRR_SI_Tables_v5.docx   # Latest SI tables
+-- Table2_Update_v5.docx        # Table update document
+-- references.bib               # Bibliography
+-- package.json                 # Node.js deps for JS scripts
|
+-- figures/                     # Main submission figures ONLY
|   +-- fig1_architecture.png        # Fig 1: WAGF architecture (shared)
|   +-- fig2_flood_combined.pdf/png  # Fig 2: Flood cross-model (flood)
|
+-- flood/                       # All FLOOD domain files
|   +-- scripts/                     # Analysis & plotting scripts
|   |   +-- fig2_flood_combined.py       # Fig 2 generator
|   |   +-- fig3_ebe_scaling.py          # EBE cross-model scaling
|   |   +-- corrected_entropy_analysis.py # Entropy computation
|   |   +-- statistical_tests.py         # Bootstrap CIs, Mann-Whitney
|   |   +-- fig_s2_relocation.py         # SI Fig S2: relocation curves
|   |   +-- fig_s3_econ_hallucination.py # SI Fig S3: econ hallucination
|   |   +-- si_unified_entropy.py        # SI Table S1 generator
|   |   +-- generate_si_adaptation_matrix.py # SI adaptation matrices
|   +-- figures/                     # Flood output figures (incl. SI)
|   |   +-- fig3_ebe_scaling.pdf/png
|   |   +-- fig_s2_relocation.pdf/png
|   |   +-- fig_s3_econ_hallucination.pdf/png
|   |   +-- SI_Figure_Adaptation_*.png
|   +-- data/                        # Flood data CSVs
|   |   +-- corrected_entropy_gemma3_4b.csv
|   |   +-- flood_action_distribution.csv
|   |   +-- statistical_tests_results.csv
|   |   +-- si_table_s1_unified_entropy.csv
|   +-- verification/                # Metrics cross-verification
|   |   +-- verify_flood_metrics.py
|   |   +-- flood_metrics_verified.csv
|   |   +-- verification_report.md
|   +-- analysis/                    # Deep analysis scripts
|   |   +-- master_report.py
|   |   +-- rh_scripts/
|   +-- docs/                        # Flood-specific documentation
|       +-- flood_metrics_for_section4.md
|       +-- WRR_technical_notes_flood_v2.md
|
+-- irrigation/                  # All IRRIGATION domain files
|   +-- scripts/                     # Analysis & plotting scripts
|   |   +-- fig_wrr_irrigation.py        # WRR 2-panel figure (copy)
|   |   +-- irrigation_v2_analysis.py    # 6-panel analysis
|   |   +-- pilot_comparison.py          # Phase comparison (copy)
|   |   +-- README.md                    # Canonical source locations
|   +-- figures/                     # (pending production run output)
|   +-- data/
|   |   +-- README.md
|   +-- docs/
|       +-- section5_irrigation_draft.md
|       +-- FIGURE4_NOTES.md
|
+-- shared/                      # Cross-domain shared files
|   +-- scripts/
|   |   +-- fig1_architecture.py         # Fig 1 generator
|   |   +-- update_v5_phase2.py          # Word doc updater
|   |   +-- create_wrr_paper.js          # JS doc generators
|   |   +-- create_si_tables.js
|   |   +-- create_table2_update.js
|   +-- docs/
|       +-- FIGURE_CONFIGURATION.md
|       +-- v5_data_update.md
|
+-- experiments/                 # Experiment tracking (unchanged)
+-- archive/                     # Old versions (unchanged)
```

---

## Phase 2 Changes (2026-02-06)

- Filled all blank R_H/EBE/H_norm placeholders in Word doc (8 paragraphs)
- Fixed intervention rate: 11.0% → 16.1% (526/3276)
- Completed Discussion paragraph [65] ("Third, ..." / "Fourth, ...")
- Merged Table 1 + Table 2 into single Table 1 (R_H + H_norm + EBE + FF)
- Corrected Table 0 cross-model values (were wildly wrong)
- Renumbered figures: removed EBE scaling (old Fig 3), Fig 4 → Fig 3
- Created `verification/` folder with cross-verification scripts and reports
- Script: `scripts/update_v5_phase2.py` (33 changes applied)

---

## Expert Review Summary

Plan reviewed by WRR format expert (2026-02-05):

- Manuscript type: **Technical Reports/Methods (13 PU)**
- Current: ~3,320 words + 4 display items = **10.6 PU** (within limit)
- Abstract limit (150 words): **CORRECT**
- 3 fig + 1 table = 4 PU display: **CORRECT** (merged Fig 1+2 into multi-panel)
- Cleanup strategy: **APPROVED**

---

*Last updated: 2026-02-11*
