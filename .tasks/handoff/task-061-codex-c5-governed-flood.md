# Task-061-C5: governed_flood/README.md Update

> **Branch**: `feat/memory-embedding-retrieval`
> **Priority**: MEDIUM
> **Depends on**: None (standalone)

## Objective

Update `examples/governed_flood/README.md` to include governance rule documentation, output interpretation guide, and create a Chinese version.

## Current State

- `examples/governed_flood/README.md`: 65 lines, concise Group C demo documentation
- `examples/governed_flood/README_zh.md`: Does NOT exist (needs creation)

## Changes Required

### 1. Add Governance Rules Section

Add a section explaining the strict governance profile used in this demo. Copy the structure from `examples/single_agent/README.md` "Governance Rules (v22)" section (already added by Task-061):

- `extreme_threat_block` (ERROR): TP in {H, VH} blocks do_nothing
- `low_coping_block` (WARNING): CP in {VL, L} observes elevate/relocate
- `relocation_threat_low` (ERROR): TP in {VL, L} blocks relocate
- `elevation_threat_low` (ERROR): TP in {VL, L} blocks elevate
- `elevation_block` (ERROR): Already-elevated agent cannot re-elevate

### 2. Add Output Interpretation Guide

Explain the output files:

| File | Description |
|------|-------------|
| `governance_summary.json` | `total_interventions` = ERROR blocks, `warnings.total_warnings` = WARNING observations, `retry_success` = agent corrected on retry |
| `household_governance_audit.csv` | Per-agent audit trail. Key columns: `failed_rules`, `warning_rules`, `warning_messages` |
| `audit_summary.json` | Parse quality: `validation_errors` (structural parse failures), `validation_warnings` (governance warnings) |
| `config_snapshot.yaml` | Full experiment config for reproducibility |

### 3. Update Default Model

Change recommended model from `gemma3:1b` to `gemma3:4b` (1b is not recommended for governance experiments — its parsing is unreliable).

### 4. Create Chinese Version

Create `examples/governed_flood/README_zh.md` with identical structure translated to Traditional Chinese. Follow the pattern established in `examples/README_zh.md` (already created by Task-061).

## Reference Files

- `examples/single_agent/README.md` (lines 147-250): Governance rules section to reference
- `examples/governed_flood/README.md`: Current file to update
- `examples/README.md` + `examples/README_zh.md`: Pattern for bilingual structure

## Verification

1. English and Chinese versions have identical section structure
2. All governance rules match `agent_types.yaml` strict profile
3. Output file descriptions are accurate
4. Default model is `gemma3:4b`
