# Troubleshooting — common WAGF setup failures

Index of failure symptoms and the one-line fix. Add new entries as
they are observed.

## Phase 1 (env check)

| Symptom | Cause | Fix |
|---------|-------|-----|
| `python: command not found` | Python not installed or not on PATH | macOS: `brew install python@3.11`; Windows: `winget install Python.Python.3.11`; Linux: `sudo apt install python3.11` |
| `ModuleNotFoundError: No module named 'numpy'` | requirements.txt not installed | `pip install -r requirements.txt` |
| `ConnectionError: localhost:11434` | Ollama daemon not running | macOS/Linux: `ollama serve &`; Windows: open the Ollama app |
| `model 'gemma3:4b' not found` | model not pulled | `ollama pull gemma3:4b` (~2.4 GB) |
| `gpu memory exhausted` | model larger than VRAM | Pick smaller model (`gemma3:4b` instead of `gemma3:12b`) OR use CPU mode |

## Phase 2 (smoke test)

| Symptom | Cause | Fix |
|---------|-------|-----|
| The reservoir run exits with a stack trace at year 1 | broker code-state mismatch | `git status` (should be clean); `git pull` |
| No `Block and repair in this run:` block printed | the run crashed before the end, or `--years` was less than 3 | Inspect stdout for the first error; rerun with `--years 4` and a new `--output` directory |
| Empty `operator_governance_audit.csv` | Python crashed mid-run | Inspect the last record in `raw/operator_traces.jsonl`; rerun with a new `--output` directory |
| `retry_count` is 0 on every row | the dead-pool rule did not engage | Confirm the command used `--model mock` (the scripted operator makes the year 3 request that the rule blocks) |

## Phase 3 (first experiment via wagf-experiment-designer)

| Symptom | Cause | Fix |
|---------|-------|-----|
| "metric not in catalogue" error | user requested an undefined metric | Pick from `wagf-experiment-designer/references/metrics_catalog.md` |
| "model not in supported list" | user typed a model name without exact Ollama tag | Provide exact tag (e.g., `gemma3:4b` not `gemma`) and confirm via `ollama list` |
| Bat fails to launch on Windows | path with spaces or backslash escaping | Wrap paths in double quotes; use forward slashes in YAML |

## Phase 4 (analysis via llm-agent-audit-trace-analyzer)

| Symptom | Cause | Fix |
|---------|-------|-----|
| "no audit CSVs found" | analyser ran on the wrong directory | Pass the run-tree root, not a single bat output |
| "sentinel column flagged: mem_top_emotion='neutral'" | memory pipeline regression (should not happen post 2026-04-25) | Pull latest main; re-check `_memory_text` helper exists in `broker/components/cognitive/reflection.py` |
| IBR computation differs from manual count | wrong domain dispatch | Pass `--domain {flood,irrigation}` to `run_analyzer.py` |

## Generic / cross-cutting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `pytest broker/ tests/` fails after fresh clone | upstream regression | Run `git log --oneline -5 broker/` to confirm you're on a known-good commit; if HEAD is bleeding-edge, checkout the latest tag |
| Throughput much slower than expected | another LLM batch using the same Ollama daemon | Stop other batches OR set `OLLAMA_MAX_LOADED_MODELS=2` to keep both models hot in VRAM (only if total ≤ GPU VRAM) |
| Disk full during a run | results trees accumulate fast (~50 MB per long irrigation run) | Move old results to `_archive_*` dirs; rerun |

## When all else fails

1. Open `examples/reservoir_control/run_reservoir_ops.py` and read the
   scripted mock (`_operator_mock`) and the summary function.
2. Run with `--verbose` if the script supports it.
3. File an issue with: Python version, Ollama version, model tag,
   the first stack trace, the first 5 records of `raw/*.jsonl`.

This troubleshooting page is intentionally NOT exhaustive. The four
lifecycle skills handle deeper diagnostics in their own
`troubleshooting` sections.
