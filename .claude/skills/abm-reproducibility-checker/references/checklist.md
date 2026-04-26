# WAGF Reproducibility Checklist

A YES/NO question per artefact category. Use this as the canonical
checklist for any pre-submission sweep.

## A. Environment

- [ ] `pyproject.toml` or `requirements.txt` exists at repo root.
- [ ] Python version is pinned (e.g., `>=3.11,<3.15`).
- [ ] All third-party imports (numpy, pandas, scipy, langchain, ollama)
  resolve without warnings beyond the documented Pydantic-v1 + Python
  3.14 set.
- [ ] If Ollama is required, the README states the exact model tags
  (e.g., `ollama pull gemma3:4b gemma4:e2b`).

## B. Configuration

- [ ] `agent_types.yaml` for the relevant domain is committed and
  unchanged since the manifest's `git_commit`.
- [ ] `skill_registry.yaml` (if used) is committed.
- [ ] No flag in the bat / shell command differs from the documented
  Methods defaults without an inline comment justifying the deviation.
- [ ] No "secret" prompt flag (`--use-priority-schema`,
  `--persona-style`, etc.) is enabled in the bat unless documented.

## C. Manifests

- [ ] Every `<run_dir>` contains `reproducibility_manifest.json`.
- [ ] Each manifest includes: `model`, `seed`, `git_commit`,
  `temperature`, `top_p`, `num_ctx`, `num_predict`, `thinking_mode`,
  `governance_profile`, `agent_types_config`, `config_hash`,
  `timestamp`.
- [ ] No two manifests in the same logical batch have different
  `config_hash` unless intentional.
- [ ] `git_dirty` is `false` in every manifest. If `true`, the run
  cannot be reproduced and must be re-done or quarantined.

## D. Data provenance (the hard one)

- [ ] For each run, `git log --follow <relevant_code>` shows the most
  recent commit affecting agent behaviour. The data's first-trace
  timestamp must be AFTER that commit.
- [ ] Specifically for irrigation: `git log --follow examples/irrigation_abm/irrigation_env.py`
  must show v21 fix commit `4be5092` (2026-03-03 19:38) as ancestor of
  the data, OR the data must be archived as pre-fix.
- [ ] Specifically for flood Gemma-4: the bat that produced the run
  must NOT include `--use-priority-schema`. (This is the 2026-04-19
  confound.)

## E. Audit traces

- [ ] `household_governance_audit.csv` exists in every run dir.
- [ ] `simulation_log.csv` exists for completed runs (not in flight).
- [ ] `raw/*.jsonl` exists with non-zero size.
- [ ] `detect_audit_sentinels_in_csv()` flags only columns documented
  as RESERVED in `broker/INVARIANTS.md` Invariant 4. Any other
  constant column is a finding.

## F. Figures and tables

- [ ] Every numeric claim in Methods / Results / SI traces to a script
  in `examples/*/analysis/` or `paper/nature_water/scripts/`.
- [ ] Each script can be re-run and produces output within ±0.001 of
  the paper text value (spot-check at least one row per table).
- [ ] No paper claim references data from a `*_archive_*/` or
  `_archive_unused/` path.
- [ ] Forest plots, scatter plots, stacked-area plots all use the same
  IBR/EHE definitions as the corresponding tables.

## G. Tests

- [ ] `pytest broker/ tests/` exits 0.
- [ ] Any skipped test has a documented reason in the test file.
- [ ] No test was modified to silence a real failure (check git blame
  on test files near the manifest's `git_commit`).

## H. Idempotency

- [ ] Re-running any run script with the same seed and config produces
  byte-identical or numerically-identical output (within
  floating-point determinism for the chosen model).
- [ ] Restarting from a partially-completed dir picks up cleanly via
  the bat's `if exist simulation_log.csv` skip-check (or equivalent).

## Severity rubric

- **RED** — fails Section D (provenance), C (missing manifest), or G
  (failing tests). Submission must wait.
- **YELLOW** — fails Section A/B/E/F/H but data is salvageable with a
  documented patch.
- **GREEN** — all sections pass; safe to submit.
