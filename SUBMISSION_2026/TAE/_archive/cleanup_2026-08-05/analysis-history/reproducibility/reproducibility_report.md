# Reproducibility Report — 2026-08-04 13:16

## Scope

- Runs surveyed: 3
- Manifests present: 3 / 3

## Verdict

**RED**

## Findings

### 1. SUBMISSION_2026\TAE\runs\smoke_gemma3_4b_a2y1  (RED)
  - **RED**: git_dirty=true; cannot reproduce

### 2. SUBMISSION_2026\TAE\runs\smoke_gemma4_12b_a2y1  (RED)
  - **RED**: git_dirty=true; cannot reproduce

### 3. SUBMISSION_2026\TAE\runs\smoke_gemma4_12b_a4y2  (RED)
  - **RED**: git_dirty=true; cannot reproduce

## Reproducible Command List

```bash
python .claude/skills/abm-reproducibility-checker/scripts/repro_audit.py \
    <results_root>
```

## Caveats

- Does not run pytest unless invoked with `--run-tests` (skipped here).
- Does not verify Ollama model digests against current local models.
- Sentinel-column scan delegated to `detect_audit_sentinels_in_csv()` (run separately).
- Does not check figure-script outputs match committed PNG/PDFs.