# Recipe: irrigation paper runs

The recorded `config_dir` folders exist at tag `paper-irrigation-runs` and were removed from the working tree on 2026-11-27.

Scope: the 15 gemma3:4b irrigation runs (3 sets of simulations x seeds 42-46, 42 years, 78 agents) and the FQL reference. Machine-readable twin: [`irrigation.yaml`](irrigation.yaml). `tests/test_repro_kit.py` checks the YAML file against the history-rewrite tables and, when the run folders are present, against the stored `launch_command.txt` of every run; this page says the same in prose and is kept in step with the YAML by hand.

Every irrigation run folder stores its launch command, so the flags below are the flags as launched, with the machine-specific parts (interpreter, working folder, absolute paths) replaced by repo-relative ones. All 15 runs record `git_dirty: false` at launch and at finalize.

## Commits and tags

The history was rewritten on 2026-11-21; every commit id changed. The run folders still name the old ids. Look an old id up in [`../history_rewrite/commit-map.txt`](../history_rewrite/commit-map.txt).

| Role | Old id (in the run folders) | New id | Tag |
|---|---|---|---|
| Irrigation runs (15) | `6d06739e` (`6d06739e0160aacca0babe2b1ee1c2190a8ea653`) | `25897813` (`258978134d67515c517677ce7b5f79d57aeeee00`) | `paper-irrigation-runs` |
| FQL reference, 10 seeds | `6027deaa` | `28b34862` | `paper-irrigation-fql` |

## Environment

| | |
|---|---|
| Python | 3.14.0 (manifest `python_version`, all 15 runs) |
| numpy | not recorded in the LLM-run manifests. The FQL reference manifests record 2.4.2. |
| Model | `gemma3:4b`, digest `c30276f7dffec93a536d283e15088990454b8d21cf180a3d6eea4959e4147291`, 4.3B, Q4_K_M |
| Ollama server | 0.40.4 for `disabled` and `strict` (10 runs); 0.40.6 for `disabled_withlimit` (5 runs) (`ollama_version.txt`) |
| Digest in manifest | 11 of 15. `disabled_withlimit` seeds 43-46 have none; their `ollama_version.txt` shows the same short id `c30276f7dffe`. |

## Sets of simulations, configs and run folders

| Set (`set` key) | Main text | `--governance-mode` | `--config-dir` | Beneficial-use limit (manifest) |
|---|---|---|---|---|
| `disabled` | without rules | `disabled` | `examples/irrigation_abm/config_variants/simple_nolimit` | `enabled: false` |
| `disabled_withlimit` | SI: with the use limit only | `disabled` | `examples/irrigation_abm/config_variants/simple` | `enabled: true` |
| `strict` | with rules | `strict` | `examples/irrigation_abm/config_variants/simple` | `enabled: true` |

Folders: `examples/irrigation_abm/results/v3_simple/v3_simple_<set>_42yr_gemma3_4b_6d06739e_seed<seed>`.

How this map was confirmed: each run's `launch_command.txt` names the `--config-dir` and `--governance-mode`; its manifest records `governance_profile` and the `beneficial_use_limit.enabled` switch, matching the table in all three sets (seed 42 read). The `disabled` runs read a derived copy, `resolved_agent_types.yaml` (kept in the run folder); the manifest names the tracked `agent_types.yaml` in that arm's recorded `config_dir` as its source.

## Flags, as launched

```bash
python examples/irrigation_abm/run_experiment.py \
  --real --model gemma3:4b --years 42 \
  --seed <S> --memory-seed <S> \
  --paper-water-margin 0.4 --cluster-method hy2021 \
  --governance-mode <mode of the set> \
  --config-dir <config dir of the set> \
  --output <folder of the set> \
  --llm-journal --workers 4
```

`<S>` is each of 42, 43, 44, 45, 46; `--memory-seed` equals `--seed` in all 15 runs. The launch commands were run from a separate working copy of the repository (its commit, as the manifest records it, is the run commit with a clean tree); the paths in them are that machine's.

## Config and data hashes

| File (at `paper-irrigation-runs`) | Hash (sha256, first 12 hex) | Where the manifest records it |
|---|---|---|
| `config_variants/simple/agent_types.yaml` | `da90d4c52909` | `config_hash` (`disabled_withlimit`, `strict`) |
| `config_variants/simple_nolimit/agent_types.yaml` | `5ee12b76dd71` | `derived_from_config_sha256` (`disabled`) |
| `resolved_agent_types.yaml` of a `disabled` run (untracked) | `f7075f293dad` | `config_hash` (`disabled`) |

The six data files the manifest hashes (`hydrology_v3.csv`, `mead_capacity_usbr2009_1ft.csv`, `lb_priority_split_v3.csv`, `ub_subbasin_supply_v3.csv`, `ub_subbasin_envelope_v3.csv`, `ub_subbasin_variant_means_v3.csv`) are tracked, and their hashes match at the run tag. These manifests carry no prompt hash. `check_manifests.py` prints all of this per run; the irrigation config files here have LF endings and matched in the LF form.

## FQL reference

`examples/irrigation_abm/run_fql_baseline.py --real --years 42 --seed <42..51> --paper-water-margin 0.4 --cluster-method hy2021 --no-governance --fql-init calibrated`, no LLM; folders `examples/irrigation_abm/results/v3_corpus/v3_fql_reference_6027deaa_seed<seed>`. The folder's `LAUNCH_COMMAND.txt` holds only timings, so these flags come from each manifest. `--fql-init-dir` points into the CRSS data (`Initial_Files/All-1109`).

## Rerun and replot: does it need CRSS?

- **A rerun needs CRSS.** A rerun needs the CRSS data (`ref/CRSS_DB`; see `DATA.md`); the listed run artifacts do not include it. `--real` loads the 78 agents from `ref/CRSS_DB/CRSS_DB` and `ref/RL-ABM-CRSS`. The FQL reference rerun needs it too.
- **A replot or recount from the run folders** reads the run folders. Some analysis scripts in `examples/irrigation_abm/analysis/` (`compute_v20_metrics.py`, `fig_wrr_irrigation.py`, `hindcast_v3.py`, `v3_metrics.py`) also read files under `ref/CRSS_DB`; which scripts the paper's figures use, and whether they need it, is settled where the figure scripts move (a later part of the plan).
- LLM sampling is not seeded (`llm_sampling_seeded: false`), so a rerun gives the same statistics over seeds, not the same rows.
- Check the folders you hold: `python reproduction/check_manifests.py --root <checkout that holds them>`.
