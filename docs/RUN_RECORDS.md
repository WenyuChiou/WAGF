# Run records

Every simulation run leaves the same records, so a reviewer can see what each model call was sent and
returned, and what code, data and machine produced the run. **These records are mandatory.** No setting,
flag or config key turns them off; `global_config.provenance` accepts only `input_files` and
`allow_dirty_tree`, and any other key in it is an error. They are written by `ExperimentRunner`
(`broker/core/experiment_runner.py`), so every runner built with `ExperimentBuilder` gets them.

## What a run writes

| File | Content |
|---|---|
| `llm_calls.jsonl` | One line per model call: `call_index`, `started_at_utc`, `agent_ids`, `agent_type`, `year`, `kind` (`decision`, `decision_retry`, `reflection`, `reflection_retry`, `other`), `attempt`, the full `prompt` and its `prompt_sha256`, the full `reply`, `options` (model, temperature, top_p, top_k, num_ctx, num_predict, think, seed), `prompt_eval_count`, `eval_count`, `done_reason`, `wall_seconds`, `error`. It never changes a prompt or a reply. |
| `reproducibility_manifest.json` | The manifest keys below. |
| `run_integrity.json` | Integrity checks, the call-log counts, and the same `provenance_*` / `submission_*` verdict as the manifest. |
| `config_snapshot.yaml` | The agent-types config with the run's command-line overrides. |

## Required manifest keys

The list lives in one place, `broker/utils/provenance_requirements.py`
(`REQUIRED_FILES`, `REQUIRED_MANIFEST_KEYS`, `REQUIRED_PRESENT_KEYS`, `REQUIRED_CALL_LOG_KEYS`).

- Times: `started_at_utc`, `finished_at_utc`, `wall_seconds` (and the older `timestamp`).
- Machine and software: `run_environment` (read at launch), `run_environment_at_finalize`,
  `run_environment_changed` (the keys that differ). Each holds the WAGF version and commit, dependency
  versions, OS, CPU, GPU (`nvidia-smi`, `None` when absent), `sys.executable` (the home folder written
  as `~`, so no user name), the Ollama server version,
  and `ollama_loaded_model` (Ollama's `/api/ps`: loaded `size`, `size_vram`, `context_length`, and
  `cpu_offload`, true when part of the model sits outside GPU memory). The launch reading can show the
  model as not loaded yet. `ollama_loaded_model_at_launch`, `ollama_loaded_model_at_finalize` and
  `ollama_cpu_offload` repeat the readings at the top level.
- Model calls: `llm_call_log` (counts: `calls_logged`, `calls_done_reason_length`,
  `calls_prompt_eval_count_ge_num_ctx`, `max_prompt_eval_count`, `write_failures`, `file_sha256`),
  `llm_sampling_seed_mode`, `llm_sampling_seeded`, `model_digest`, `model_digest_at_finalize`,
  `model_digest_changed`.
- `model_roles`: one entry per role that called a model (`decision`, `reflection`, `other`), each with
  the model, digest, quantization, endpoint (`mock`, a cloud provider name, or `ollama@host:port`, never a
  key), decoding options, `adaptation: "none (off the shelf)"`.
- `execution_order`: `workers`, how agents are ordered within a year (fixed registration order, never
  shuffled by the runner), `agent_ids_in_order` and its hash.
- `resolution_policy`: `max_governance_retries`, `max_format_attempts` (model calls one decision may use before an unparsed reply becomes an ABORTED row: 3, the first call plus two format retries), `retry_framing` (always `plain`),
  `on_retry_exhausted`, `default_skill`, and `counts` taken from the audit CSV at finalize: parse
  failures and retry exhaustion, as counts and rates.
- Paths and code: `agent_types_config_sha256`, `agent_types_config_repo_relative`,
  `launch_command_script_repo_relative`, `launch_command_repo_relative`. The two repo-relative keys must
  be present; they are `null` when the file lies outside the WAGF repo, which does not make the records
  incomplete but blocks `submission_ready`.
- Tree: `clean_tree_check`, `allow_dirty_tree`.
- Inputs: `input_files` (sha256, size and repo-relative path of every file the run reads; may be empty
  for a domain that reads none).

## Declaring input files

A domain lists the files it reads with `runner.declare_input_files({"name": path, ...})` after `build()`,
or with `global_config.provenance.input_files` (a name-to-path map, relative to the WAGF repo root). The
runner hashes them at launch. A missing file is recorded as `present: false`.

## Clean tree

A non-mock run on a WAGF tree with uncommitted changes refuses to start. `--allow-dirty-tree` (paper
runners), `ExperimentBuilder.with_allow_dirty_tree()` or `global_config.provenance.allow_dirty_tree`
overrides it; the override is recorded and blocks `submission_ready`. `python -m broker.run` keeps its
own `--strict-provenance` check and the runner does not repeat it.

## Failing loudly

- A run that cannot open `llm_calls.jsonl` does not start.
- A line that cannot be written stops the run at the end of that step (`RunRecordsError`).
- A manifest that cannot be written raises `RunRecordsError` after the rest of finalize has run. A run
  that is already stopping on another error keeps that error; the records failure is logged and shows
  in `provenance_complete`.
- One process runs one experiment at a time: the call log and the seed switch are process-wide, so
  two `ExperimentRunner.run` calls running at the same time in one process would share them.
  `workers` > 1 inside one run is fine (each worker thread carries its own call context).
- At finalize the runner checks every required file and key and writes `provenance_complete` and
  `provenance_missing` to the manifest and `run_integrity.json`. A block whose builder failed (stored as
  `{"error": ...}`), an environment reading that failed or was not taken at the right time, and a
  declared input file with no sha256 (missing or unreadable) all count as missing. The paper runners and `python -m
  broker.run` read both files back and exit with code 3 when the records are incomplete
  (`enforce_complete`). A function that a test or another program calls gets the verdict in the files
  and does not exit.

## `submission_ready`

The manifest and `run_integrity.json` carry `submission_ready` and `submission_blockers`, and the run
prints them at its end. It is false when: the model is a mock; the tree was dirty or the run used
`--allow-dirty-tree`; provenance is incomplete; the run did not finish normally; any call ended with
`done_reason` `length` or a prompt reached `num_ctx`; the agent-types config or the launch script lies
outside the WAGF repo; part of the model ran on the CPU; the WAGF commit,
the Ollama version or the model digest changed between launch and finalize; an Ollama model's digest
is unavailable; neither reading has the Ollama server version; or the finalize reading of Ollama's
loaded model failed, did not find the model loaded (a short `keep_alive` unloads it), or could not
tell the GPU / CPU split. These Ollama readings decide `submission_ready` only: a failed reading does
not make the records incomplete. The launch reading is not checked, since the model is often not
loaded before the first call.

## Limits

- A resumed run (`--resume-from`) replays its journal without calling the model, so the replayed calls
  are not in this process's `llm_calls.jsonl` counts; they are in the source run's log.
- A model call made with no call context is logged with kind `other` and no agent or year, and under
  `sampling_seed: per_call` all such calls would get the same seed. Every call site in the framework
  and the example runners sets the context (`call_context`); a new domain that calls the model itself
  should do the same.

## Which entry points use the recorder

All of them go through `ExperimentRunner` and call `enforce_complete`: `examples/single_agent/run_flood.py`,
`examples/irrigation_abm/run_experiment.py`, `examples/multi_agent/flood/run_unified_experiment.py`,
`python -m broker.run`, `examples/governed_flood/run_experiment.py`, `examples/cat_model/run_cat.py` and
`run_cat_ma.py`, `examples/quickstart/01_barebone.py` and `02_governance.py`,
`examples/reservoir_control_multidim/run_reservoir_multidim.py`, and
`examples/coupling_examples/archetype_c_subprocess/run_archetype_c.py`. A test fails when a script that
builds an experiment is not on that list. Not simulation runs, so not covered: the offline replay and
ablation tools (`broker/experiments/ablation.py`, `replay.py`, `broker/tools/ablate_factor.py`) and the
prompt-calibration script `examples/multi_agent/flood/paper3/analysis/pa_prompt_calibration_test.py`,
which call a model on stored prompts and produce no simulation. `examples/irrigation_abm/run_fql_baseline.py`
calls no model and writes its own manifest; it is not routed through the recorder.
