# Recipe: flood paper runs

Scope: the 15 gemma3:4b flood runs (3 sets of simulations x seeds 42-46) and the reference household model. Machine-readable twin: [`flood.yaml`](flood.yaml). `tests/test_repro_kit.py` checks the YAML file against the history-rewrite tables and, when the run folders are present, against them; this page says the same in prose and is kept in step with the YAML by hand.

**Read this first.** The flood run folders store no launch command. The flags below were read back from each run's `reproducibility_manifest.json` and `config_snapshot.yaml`, or are the runner's defaults (marked). All 15 runs record `git_dirty: true` at launch and at finalize, and no list of the changed files. The tag marks the commit they started from; it is not an exact copy of the code that ran.

## Commits and tags

The history was rewritten on 2026-11-21; every commit id changed. The run folders still name the old ids. Look an old id up in [`../history_rewrite/commit-map.txt`](../history_rewrite/commit-map.txt).

| Role | Old id (in the run folders) | New id | Tag |
|---|---|---|---|
| Flood runs (15) | `9c4ba160` (`9c4ba160996428117dfe72d0a54053cc1d550ff7`) | `98b54298` (`98b542986bd409786b8662710dbed4bf45500a77`) | `paper-flood-runs` |
| Reference household model, 5 seeds | `186abb29` | `24d62cb9` | `paper-flood-rulebased` |

## Environment

| | |
|---|---|
| Python | 3.14.0 (manifest `python_version`, all 15 runs) |
| numpy | not recorded in these manifests |
| Model | `gemma3:4b`, digest `c30276f7dffec93a536d283e15088990454b8d21cf180a3d6eea4959e4147291`, 4.3B, Q4_K_M |
| Ollama server | 0.40.4 (`ollama_version.txt`, all 15 runs) |
| Digest in manifest | 14 of 15. `silent` seed 45 has none; its `ollama_version.txt` shows the same short id `c30276f7dffe`. |

## Sets of simulations and run folders

| Set (`set` key) | Main text | Flags that differ | Folder |
|---|---|---|---|
| `disabled` | without rules | `--governance-mode disabled` | `examples/single_agent/results/JOH_disabled_defaults_gemma3_4b_9c4ba160/Run_<seed>` |
| `strict` | with rules | `--governance-mode strict` | `examples/single_agent/results/JOH_strict_defaults_gemma3_4b_9c4ba160/Run_<seed>` |
| `silent` | SI: with rules, no reasons | `--governance-mode strict --retry-feedback-mode silent` | `examples/single_agent/results/JOH_silent_defaults_gemma3_4b_9c4ba160/Run_<seed>` |

All three read the same file, `examples/single_agent/agent_types.yaml` (prompt: `config/prompts/household.txt`). The sets differ only in the flags above; for seed 42, the `config_snapshot.yaml` of the `disabled` and `strict` runs differ in `metadata.governance_profile` alone, and `strict` and `silent` in `metadata.retry_feedback_mode` alone.

## Flags

```bash
python examples/single_agent/run_flood.py \
  --model gemma3:4b --years 10 --agents 100 \
  <flags of the set> \
  --seed <42..46> --workers 4 \
  --num-ctx 8192 --num-predict 4096 --thinking-mode disabled \
  --output <folder of the set>
```

Where each flag was confirmed: `--model`, `--years`, `--num-ctx`, `--num-predict`, `--thinking-mode`, `--workers` and `--seed` are manifest fields; `--governance-mode` is `governance_profile`; `--retry-feedback-mode` is `retry_feedback_mode` (also in `config_snapshot.yaml`); `--agents 100` is `run_integrity.audit_agents` and the runner default.

Not recorded in the run folders:

- `--memory-seed`: the manifest field is `null`. The runner default is 42 and the 2026-10 runbook command (`examples/single_agent/docs/flood_wrr_rerun_runbook.md`) passes 42.
- `--workers`: that runbook passes 1; the manifests record 4. The list above uses the manifest value.
- `--output` paths, and `--flood-mode` (runner default `fixed`).
- `--survey-mode`: off by default, so the runner reads the agent profiles from `examples/single_agent/agent_initial_profiles.csv`. The manifest does not record the flag.

## Config hashes

The manifest's `config_hash` is the first 12 hex characters of the sha256 of `agent_types.yaml` as it was checked out on the Windows machine, with CRLF line endings: `926ff4a10ee8`. The tracked file has LF endings (`bdb8afce44dc`); turning its LF into CRLF gives the manifest value. `check_manifests.py` tries both forms and prints which one matched (`crlf` for all 15 flood runs). These manifests carry no prompt hash.

## Reference household model

`examples/single_agent/run_flood_rulebased.py --seed <42..46> --output <folder>`, no LLM; folders `examples/single_agent/results/rulebased_5seed_186abb29/Run_<seed>`. The run folders store no launch command; the manifest records the commit `186abb29...` and the seed.

## Rerun and replot

- A rerun needs Ollama with the model at the digest above, Python 3.14 and this repository at `paper-flood-runs`. Flood needs no CRSS data. Because the runs started from a dirty tree, a rerun from the tag is a rerun of the recorded commit, not of the exact files that ran. LLM sampling is not seeded (`llm_sampling_seeded: false`), so a rerun gives the same statistics over seeds, not the same rows.
- A replot or recount, given the listed run artifacts (the run folders), needs only those folders and the analysis scripts; no CRSS data.
- Check the folders you hold: `python reproduction/check_manifests.py --root <checkout that holds them>`.
