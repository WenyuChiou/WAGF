"""The records every WAGF run must leave, and the checks that say whether it did.

One list, here, of the files and manifest keys a run must have written. ``ExperimentRunner``
calls :func:`missing_items` and :func:`submission_blockers` at finalize and writes the answers
to ``reproducibility_manifest.json`` and ``run_integrity.json`` as ``provenance_complete`` /
``provenance_missing`` and ``submission_ready`` / ``submission_blockers``. Entry points call
:func:`enforce_complete` after the run and exit non-zero when the records are incomplete.

There is no switch that turns these records off. A record that cannot be written stops the run
(:class:`RunRecordsError`); it never finishes looking successful without its records.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from broker.utils.llm_journal import JournalWriteError
from broker.utils.llm_utils import is_cloud_provider_model, is_mock_model

# Files that must exist in the output folder when the run ends.
REQUIRED_FILES = (
    "llm_calls.jsonl",
    "reproducibility_manifest.json",
    "run_integrity.json",
    "config_snapshot.yaml",
)

# Manifest keys that must be present and filled (not None, not an empty string).
REQUIRED_MANIFEST_KEYS = (
    "model",
    "started_at_utc",
    "finished_at_utc",
    "wall_seconds",
    "run_environment",
    "run_environment_at_finalize",
    "llm_call_log",
    "model_roles",
    "execution_order",
    "resolution_policy",
    "agent_types_config_sha256",
    "clean_tree_check",
    "ollama_loaded_model_at_launch",
    "ollama_loaded_model_at_finalize",
    "llm_sampling_seed_mode",
)

# Keys that must be present; the value is None when the file lies outside the WAGF repo
# (a blocker for submission, see submission_blockers).
REQUIRED_NULLABLE_KEYS = (
    "agent_types_config_repo_relative",
    "launch_command_script_repo_relative",
)

# Keys that must be present and not None, but may be empty (an empty list or dict is an answer).
REQUIRED_PRESENT_KEYS = (
    "run_environment_changed",
    "allow_dirty_tree",
    "input_files",
)

# Blocks the runner builds at finalize; a builder that raised leaves {"error": <type>}.
BUILT_BLOCK_KEYS = ("model_roles", "execution_order", "resolution_policy")

# Counts the call-log block must carry (truncation evidence).
REQUIRED_CALL_LOG_KEYS = (
    "calls_logged",
    "calls_done_reason_length",
    "calls_prompt_eval_count_ge_num_ctx",
    "max_prompt_eval_count",
    "write_failures",
)

# Fields written to both files at finalize.
RESULT_KEYS = ("provenance_complete", "provenance_missing", "submission_ready",
               "submission_blockers")


class RunRecordsError(JournalWriteError):
    """A run record could not be written. Stops the run (same path as a journal write error)."""


def _empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def missing_items(manifest: Dict[str, Any], output_dir: Any,
                  skip_files: tuple = ()) -> List[str]:
    """Required files and manifest keys that are absent or empty. Never raises."""
    missing: List[str] = []
    try:
        out = Path(output_dir)
        for name in REQUIRED_FILES:
            if name in skip_files:
                continue
            path = out / name
            if not path.is_file():
                missing.append(f"file:{name}")
        for key in REQUIRED_MANIFEST_KEYS:
            if _empty(manifest.get(key)):
                missing.append(f"manifest:{key}")
        for key in REQUIRED_PRESENT_KEYS:
            if manifest.get(key) is None:
                missing.append(f"manifest:{key}")
        for key in REQUIRED_NULLABLE_KEYS:
            if key not in manifest:
                missing.append(f"manifest:{key}")
        env = manifest.get("run_environment")
        if isinstance(env, dict) and env.get("captured_at") != "launch":
            missing.append("manifest:run_environment.captured_at (not a launch reading)")
        env_final = manifest.get("run_environment_at_finalize")
        if isinstance(env_final, dict) and env_final.get("captured_at") != "finalize":
            missing.append("manifest:run_environment_at_finalize.captured_at (not a finalize reading)")
        for key, reading in (("run_environment", env), ("run_environment_at_finalize", env_final)):
            errors = reading.get("errors") if isinstance(reading, dict) else None
            if isinstance(errors, dict) and "_collection" in errors:
                missing.append(f"manifest:{key} (reading failed: {errors['_collection']})")
        # A block whose builder raised is stored as {"error": ...}: present, but not a record.
        for key in BUILT_BLOCK_KEYS:
            value = manifest.get(key)
            if isinstance(value, dict) and "error" in value:
                missing.append(f"manifest:{key} (could not be built: {value['error']})")
        # A declared input file that was missing or unreadable at launch has no digest.
        inputs = manifest.get("input_files")
        if isinstance(inputs, dict):
            for name, entry in sorted(inputs.items()):
                if not isinstance(entry, dict) or _empty(entry.get("sha256")):
                    missing.append(f"manifest:input_files.{name} (file missing or unreadable)")
        elif inputs is not None:
            missing.append("manifest:input_files (not a mapping)")
        block = manifest.get("llm_call_log")
        if isinstance(block, dict):
            for key in REQUIRED_CALL_LOG_KEYS:
                if key == "max_prompt_eval_count":
                    if key not in block:
                        missing.append(f"manifest:llm_call_log.{key}")
                elif block.get(key) is None:
                    missing.append(f"manifest:llm_call_log.{key}")
            if isinstance(block.get("write_failures"), int) and block["write_failures"] > 0:
                missing.append("manifest:llm_call_log.write_failures > 0 (lines were lost)")
            if isinstance(block.get("calls_logged"), int) and block["calls_logged"] > 0 \
                    and _empty(block.get("file_sha256")):
                missing.append("manifest:llm_call_log.file_sha256")
        elif block is not None:
            missing.append("manifest:llm_call_log (not a block)")
    except Exception as exc:  # noqa: BLE001 - a check that cannot run must not pass
        missing.append(f"check_failed:{type(exc).__name__}")
    return missing


def _changed_prefix(changed: Any, prefix: str) -> bool:
    return isinstance(changed, list) and any(str(k).startswith(prefix) for k in changed)


def submission_blockers(manifest: Dict[str, Any]) -> List[str]:
    """Reasons this run must not go into a submission. Empty list means ready. Never raises."""
    blockers: List[str] = []
    try:
        model = manifest.get("model")
        if not isinstance(model, str) or is_mock_model(model):
            blockers.append("mock model")
        tree = manifest.get("clean_tree_check") or {}
        env_launch = manifest.get("run_environment") or {}
        env_final = manifest.get("run_environment_at_finalize") or {}
        dirty = tree.get("dirty") is True or any(
            isinstance(e.get("wagf_source_git"), dict) and e["wagf_source_git"].get("dirty") is True
            for e in (env_launch, env_final) if isinstance(e, dict))
        if manifest.get("allow_dirty_tree") is True:
            blockers.append("dirty tree (run started with --allow-dirty-tree)")
        elif dirty:
            blockers.append("dirty tree")
        if manifest.get("provenance_complete") is not True:
            blockers.append("provenance incomplete")
        if manifest.get("agent_types_config_repo_relative") is None:
            blockers.append("agent-types config is outside the WAGF repo")
        if manifest.get("launch_command_script_repo_relative") is None:
            blockers.append("launch script is outside the WAGF repo")
        status = manifest.get("run_status")
        if status:
            blockers.append(f"run did not finish normally ({status})")
        block = manifest.get("llm_call_log") or {}
        if isinstance(block, dict):
            if (block.get("calls_done_reason_length") or 0) > 0:
                blockers.append(
                    f"{block['calls_done_reason_length']} call(s) truncated (done_reason length)")
            if (block.get("calls_prompt_eval_count_ge_num_ctx") or 0) > 0:
                blockers.append(
                    f"{block['calls_prompt_eval_count_ge_num_ctx']} prompt(s) reached num_ctx")
        loaded = [manifest.get("ollama_loaded_model_at_launch"),
                  manifest.get("ollama_loaded_model_at_finalize")]
        if manifest.get("ollama_cpu_offload") is True or any(
                isinstance(m, dict) and m.get("cpu_offload") is True for m in loaded):
            blockers.append("part of the model ran on the CPU (cpu_offload)")
        changed = manifest.get("run_environment_changed")
        if _changed_prefix(changed, "wagf_source_git.commit"):
            blockers.append("WAGF commit changed during the run")
        if _changed_prefix(changed, "ollama_server_version.version"):
            blockers.append("Ollama version changed during the run")
        if manifest.get("model_digest_changed") is True:
            blockers.append("model digest changed during the run")
        if isinstance(model, str) and not is_mock_model(model) and not is_cloud_provider_model(model):
            if _empty(manifest.get("model_digest")) or _empty(manifest.get("model_digest_at_finalize")):
                blockers.append("model digest unavailable")
            # The Ollama readings behind the GPU / CPU and server-version facts (ODD+LLM C).
            versions = [((e or {}).get("ollama_server_version") or {}).get("version")
                        for e in (env_launch, env_final) if isinstance(e, dict)]
            if not any(isinstance(v, str) and v.strip() for v in versions):
                blockers.append("Ollama server version unavailable")
            final_loaded = manifest.get("ollama_loaded_model_at_finalize")
            if not isinstance(final_loaded, dict) or final_loaded.get("error") \
                    or final_loaded.get("loaded") is None:
                blockers.append("Ollama loaded-model reading failed at finalize "
                                "(GPU / CPU split unknown)")
            elif final_loaded.get("loaded") is False:
                blockers.append("model not loaded at finalize (GPU / CPU split unknown; "
                                "check Ollama keep_alive)")
            elif final_loaded.get("cpu_offload") is None:
                blockers.append("GPU / CPU split unknown at finalize")
    except Exception as exc:  # noqa: BLE001
        blockers.append(f"check_failed:{type(exc).__name__}")
    return blockers


def seal(manifest: Dict[str, Any], output_dir: Any) -> Dict[str, Any]:
    """Compute the four result fields, put them in ``manifest`` and return them.

    The manifest file itself is not on disk yet, so it is not checked here; the entry point's
    :func:`enforce_complete` checks it afterwards.
    """
    missing = missing_items(manifest, output_dir, skip_files=("reproducibility_manifest.json",))
    manifest["provenance_complete"] = not missing
    manifest["provenance_missing"] = missing
    blockers = submission_blockers(manifest)
    manifest["submission_blockers"] = blockers
    manifest["submission_ready"] = not blockers
    return {k: manifest[k] for k in RESULT_KEYS}


def summary_line(fields: Dict[str, Any]) -> str:
    text = (f"[Records] provenance_complete={fields.get('provenance_complete')} "
            f"submission_ready={fields.get('submission_ready')}")
    if fields.get("provenance_missing"):
        text += " | missing: " + "; ".join(fields["provenance_missing"])
    if fields.get("submission_blockers"):
        text += " | blockers: " + "; ".join(fields["submission_blockers"])
    return text


def amend_run_integrity(output_dir: Any, fields: Dict[str, Any]) -> None:
    """Add the result fields to ``run_integrity.json``. Raises RunRecordsError on failure."""
    path = Path(output_dir) / "run_integrity.json"
    if not path.is_file():
        return  # reported as file:run_integrity.json in provenance_missing
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("run_integrity.json is not an object")
        data.update(fields)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    except (OSError, ValueError) as exc:
        raise RunRecordsError(f"could not update {path}: {type(exc).__name__}: {exc}") from exc


def enforce_complete(output_dir: Any, exit_code: int = 3, entry: bool = True) -> Dict[str, Any]:
    """Read the finished run's files; exit non-zero unless the records are complete.

    Checks the manifest and ``run_integrity.json`` on disk, not the in-memory state, so a
    file that never reached the disk is caught. Returns the manifest's result fields.
    ``entry`` is True when the caller is the process's own entry point (a script run as
    ``__main__``); a function that a test or another program calls passes False and gets the
    verdict in the files instead of an exit.
    """
    problems: List[str] = []
    fields: Dict[str, Any] = {}
    out = Path(output_dir)
    for name in ("reproducibility_manifest.json", "run_integrity.json"):
        try:
            data = json.loads((out / name).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problems.append(f"file:{name} unreadable ({type(exc).__name__})")
            continue
        if not isinstance(data, dict) or "provenance_complete" not in data:
            problems.append(f"{name} has no provenance_complete")
            continue
        if name == "reproducibility_manifest.json":
            fields = {k: data.get(k) for k in RESULT_KEYS}
        if data.get("provenance_complete") is not True:
            problems.extend(f"{name}: {m}" for m in (data.get("provenance_missing") or ["incomplete"]))
    if not problems:
        # Re-check the files now that the manifest exists.
        manifest = json.loads((out / "reproducibility_manifest.json").read_text(encoding="utf-8"))
        problems.extend(missing_items(manifest, out))
    if problems and entry:
        import sys
        print(f"[Records] run records are incomplete, exiting {exit_code}: " + "; ".join(problems),
              file=sys.stderr, flush=True)
        raise SystemExit(exit_code)
    return fields
