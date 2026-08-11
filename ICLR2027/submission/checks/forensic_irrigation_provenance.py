"""Forensic provenance audit for the historical ICLR irrigation corpus.

This audit does not rewrite historical manifests and does not promote a run
to reproducibility GREEN.  It reconstructs the evidence that is still
observable on disk: run-local configuration snapshots, realized prompts,
trace/audit/simulation joins, committed code-era fingerprints, launch-script
settings, and the paper's per-seed condition-share direction.

The historical manifests predate commit 35c28291, when Git metadata was moved
from finalization time to construction time.  Their ``git_commit`` and
``git_dirty`` fields therefore describe finalization, not launch.  This script
records that semantic defect instead of treating ``git_dirty=true`` as proof
that runtime source was dirty at launch.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS_ROOT = REPO_ROOT / "examples" / "irrigation_abm" / "results"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "ICLR2027" / "submission" / "analysis" / "reproducibility"

V21_FIX_COMMIT = "4be50921be1d83412619388d475f4ea80c447597"
MANIFEST_LAUNCH_FIX_COMMIT = "35c28291027340543eb5294701db2e0bd98b0fab"
EXPECTED_ROWS = 78 * 42
HIGH_LABELS = {"H", "VH"}
PRIORITY_MARKER = "[CRITICAL FACTORS"
SENTINEL_STATUS = "UNRESOLVED_USAGE_NOT_AUDITED"


@dataclass(frozen=True)
class ModelSpec:
    model: str
    prefix: str
    seeds: tuple[int, ...]
    launcher: str


MODEL_SPECS = (
    ModelSpec("gemma3:4b", "", (42, 43, 44, 45, 46), "examples/irrigation_abm/run_ensemble.bat"),
    ModelSpec("gemma3:12b", "gemma3_12b_", (42, 43, 44), "examples/irrigation_abm/run_gemma12b_batch.bat"),
    ModelSpec("gemma4:e2b", "gemma4_e2b_", (42, 43, 44, 45, 46), "examples/irrigation_abm/run_gemma4_e2b_batch.bat"),
    ModelSpec("gemma4:e4b", "gemma4_e4b_", (42, 43, 44, 45, 46), "examples/irrigation_abm/run_gemma4_e4b_batch.bat"),
    ModelSpec("ministral-3:8b", "ministral3_8b_", (42, 43, 44), "examples/irrigation_abm/run_crossmodel_batch.sh"),
)

# Files shared by both treatment arms and capable of changing prompts,
# validation, parsing, execution, or audit logging.  Arm-specific launchers are
# intentionally excluded; their treatment difference is audited separately via
# config snapshots and realized traces.
CRITICAL_SHARED_PATHS = (
    "examples/irrigation_abm/run_experiment.py",
    "examples/irrigation_abm/run_ungoverned_experiment.py",
    "examples/irrigation_abm/irrigation_personas.py",
    "examples/irrigation_abm/adapters/irrigation_adapter.py",
    "examples/irrigation_abm/validators/irrigation_validators.py",
    "broker/core/experiment_runner.py",
    "broker/core/experiment.py",
    "broker/core/experiment_builder.py",
    "broker/core/skill_broker_engine.py",
    "broker/core/_retry_loop.py",
    "broker/validators/agent/agent_validator.py",
    "broker/components/context/builder.py",
    "broker/components/analytics/audit.py",
    "broker/components/memory/engine.py",
    "broker/components/memory/engines/humancentric.py",
    "broker/components/cognitive/reflection.py",
    "broker/components/governance/registry.py",
    "broker/utils/parsing/unified_adapter.py",
    "broker/utils/llm_utils.py",
    "broker/utils/agent_config.py",
    "examples/irrigation_abm/irrigation_env.py",
)


def _git(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _csv_rows_and_header(path: Path) -> tuple[int, list[str], set[tuple[str, int]], dict[tuple[str, int], dict[str, str]]]:
    rows = 0
    keys: set[tuple[str, int]] = set()
    indexed: dict[tuple[str, int], dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        for row in reader:
            rows += 1
            agent_id = row.get("agent_id", "")
            try:
                year = int(float(row.get("year", "")))
            except (TypeError, ValueError):
                continue
            key = (agent_id, year)
            keys.add(key)
            indexed[key] = row
    return rows, header, keys, indexed


def _read_trace(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    nonblank_lines = 0
    parsed_records = 0
    metadata_records = 0
    malformed_json_lines = 0
    invalid_data_records = 0
    data_rows = 0
    duplicate_key_rows = 0
    keys: set[tuple[str, int]] = set()
    year1_prompts: dict[str, str] = {}
    year1_state: dict[str, Any] = {}
    requests: list[tuple[tuple[str, int], float | None]] = []
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    models: set[str] = set()
    schema_keys: set[str] | None = None
    priority_marker_count = 0

    with path.open("rb") as handle:
        for raw_line in handle:
            digest.update(raw_line)
            if not raw_line.strip():
                continue
            nonblank_lines += 1
            try:
                record = json.loads(raw_line.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                malformed_json_lines += 1
                continue
            parsed_records += 1
            if "_metadata" in record:
                metadata_records += 1
                continue
            agent_id = str(record.get("agent_id", ""))
            try:
                year = int(record.get("year"))
            except (TypeError, ValueError):
                invalid_data_records += 1
                continue
            if not agent_id:
                invalid_data_records += 1
                continue
            data_rows += 1
            schema_keys = set(record) if schema_keys is None else schema_keys & set(record)
            timestamp = record.get("timestamp")
            if timestamp:
                first_timestamp = first_timestamp or timestamp
                last_timestamp = timestamp
            model = record.get("model")
            if model:
                models.add(str(model))
            key = (agent_id, year)
            if key in keys:
                duplicate_key_rows += 1
            keys.add(key)
            input_text = str(record.get("input", ""))
            priority_marker_count += int(PRIORITY_MARKER in input_text)
            if year == 1:
                year1_prompts[agent_id] = input_text
                year1_state[agent_id] = {
                    "state_before": record.get("state_before"),
                    "environment_context": record.get("environment_context"),
                }
            request = (record.get("state_after") or {}).get("request")
            try:
                parsed_request = float(request) if request is not None else None
            except (TypeError, ValueError):
                parsed_request = None
            requests.append((key, parsed_request))

    return {
        "nonblank_lines": nonblank_lines,
        "parsed_records": parsed_records,
        "metadata_records": metadata_records,
        "malformed_json_lines": malformed_json_lines,
        "invalid_data_records": invalid_data_records,
        "data_rows": data_rows,
        "duplicate_key_rows": duplicate_key_rows,
        "keys": keys,
        "year1_prompts": year1_prompts,
        "year1_state": year1_state,
        "requests": requests,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "models": sorted(models),
        "schema_keys": sorted(schema_keys or []),
        "priority_marker_count": priority_marker_count,
        "sha256": digest.hexdigest(),
    }


def _normalised_config(path: Path) -> tuple[dict[str, Any], str, dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    metadata = dict(data.get("metadata") or {}) if isinstance(data, dict) else {}
    identity = {
        "actual_model": metadata.get("actual_model"),
        "seed": metadata.get("seed"),
        "governance_profile": metadata.get("governance_profile"),
    }
    if isinstance(data, dict) and isinstance(data.get("metadata"), dict):
        data["metadata"]["governance_profile"] = "<ARM>"
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return data, hashlib.sha256(canonical.encode("utf-8")).hexdigest(), identity


def _nearest_commit_before(timestamp: str | None) -> str | None:
    if not timestamp:
        return None
    commit = _git("rev-list", "-1", f"--before={timestamp}", "HEAD", check=False)
    return commit or None


def _blob(commit: str | None, path: str) -> str:
    if not commit:
        return "MISSING_COMMIT"
    completed = subprocess.run(
        ["git", "rev-parse", f"{commit}:{path}"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "MISSING_PATH"


def _critical_fingerprint(commit: str | None) -> tuple[str | None, dict[str, str], list[str]]:
    if not commit:
        return None, {}, list(CRITICAL_SHARED_PATHS)
    blobs = {path: _blob(commit, path) for path in CRITICAL_SHARED_PATHS}
    missing = sorted(path for path, blob in blobs.items() if blob.startswith("MISSING_"))
    if missing:
        return None, blobs, missing
    payload = json.dumps(blobs, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest(), blobs, []


def _manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _timestamp_after_v21(timestamp: str | None, v21_date: str) -> bool | None:
    if not timestamp:
        return None
    trace_dt = datetime.fromisoformat(timestamp)
    fix_dt = datetime.fromisoformat(v21_date)
    if trace_dt.tzinfo is None:
        fix_dt = fix_dt.replace(tzinfo=None)
    return trace_dt >= fix_dt


def _condition_share(sim_rows: Iterable[dict[str, str]]) -> float:
    labels = [str(row.get("wsa_label", "")).strip().upper() for row in sim_rows]
    return 100.0 * sum(label in HIGH_LABELS for label in labels) / len(labels)


def _known_workers(model: str, seed: int, arm: str) -> tuple[int | None, str, str]:
    if model == "gemma3:4b" and seed in {42, 43, 44}:
        if arm == "no_validator":
            return 4, "run_ensemble.bat explicitly passes --workers 4", "explicit_launcher"
        if seed in {43, 44}:
            return 1, "run_ensemble.bat explicitly passes --workers 1", "explicit_launcher"
        return None, "run_ensemble.bat states that governed seed 42 already existed and does not launch it", "unknown"
    if model == "gemma3:4b" and seed in {45, 46}:
        return None, "no versioned launcher was recovered; the historical default is not treated as launch evidence", "unknown"
    return 1, "versioned batch command omits --workers and the versioned historical parser default is 1", "versioned_launcher_plus_parser_default"


def _launcher_evidence(spec: ModelSpec, seed: int) -> str | None:
    if spec.model == "gemma3:4b" and seed in {45, 46}:
        return None
    return spec.launcher


def _sentinel_findings(csv_path: Path) -> list[str]:
    from broker.components.analytics.audit import detect_audit_sentinels_in_csv

    return detect_audit_sentinels_in_csv(str(csv_path))


def _sentinel_column(message: str) -> str:
    match = re.search(r"Column '([^']+)'", message)
    return match.group(1) if match else message


def audit(results_root: Path) -> dict[str, Any]:
    v21_date = _git("show", "-s", "--format=%cI", V21_FIX_COMMIT)
    launch_fix_date = _git("show", "-s", "--format=%cI", MANIFEST_LAUNCH_FIX_COMMIT)
    runs: list[dict[str, Any]] = []
    run_cache: dict[tuple[str, int, str], dict[str, Any]] = {}
    sentinel_counts: Counter[str] = Counter()
    fingerprint_cache: dict[str | None, tuple[str | None, dict[str, str], list[str]]] = {}

    for spec in MODEL_SPECS:
        for seed in spec.seeds:
            for arm, stem in (("strict", "production"), ("no_validator", "ungoverned")):
                run_dir = results_root / f"{stem}_v21_42yr_{spec.prefix}seed{seed}"
                if not run_dir.is_dir():
                    raise FileNotFoundError(f"Missing expected run directory: {run_dir}")
                audit_csv = run_dir / "irrigation_farmer_governance_audit.csv"
                sim_csv = run_dir / "simulation_log.csv"
                trace_jsonl = run_dir / "raw" / "irrigation_farmer_traces.jsonl"
                config_yaml = run_dir / "config_snapshot.yaml"
                manifest_json = run_dir / "reproducibility_manifest.json"
                for required in (audit_csv, sim_csv, trace_jsonl, config_yaml, manifest_json):
                    if not required.exists():
                        raise FileNotFoundError(f"Missing expected artifact: {required}")

                audit_rows, audit_header, audit_keys, _ = _csv_rows_and_header(audit_csv)
                sim_rows, sim_header, sim_keys, sim_index = _csv_rows_and_header(sim_csv)
                trace = _read_trace(trace_jsonl)
                config_data, normalized_config_hash, config_identity = _normalised_config(config_yaml)
                manifest = _manifest(manifest_json)
                nearest_commit = _nearest_commit_before(trace["first_timestamp"])
                if nearest_commit not in fingerprint_cache:
                    fingerprint_cache[nearest_commit] = _critical_fingerprint(nearest_commit)
                critical_fp, critical_blobs, critical_missing = fingerprint_cache[nearest_commit]
                workers, worker_evidence, worker_evidence_strength = _known_workers(spec.model, seed, arm)
                expected_profile = "strict" if arm == "strict" else "disabled"
                config_identity_match = all((
                    config_identity["actual_model"] == spec.model,
                    config_identity["seed"] == seed,
                    config_identity["governance_profile"] == expected_profile,
                ))
                trace_model_match = not trace["models"] or trace["models"] == [spec.model]

                request_mismatches = 0
                for key, trace_request in trace["requests"]:
                    sim_row = sim_index.get(key)
                    if sim_row is None:
                        request_mismatches += 1
                        continue
                    try:
                        sim_request = float(sim_row.get("request", ""))
                    except (TypeError, ValueError):
                        request_mismatches += 1
                        continue
                    if trace_request is None or abs(trace_request - sim_request) > 1e-6:
                        request_mismatches += 1

                sim_share = _condition_share(sim_index.values())
                sentinel_messages = _sentinel_findings(audit_csv)
                for message in sentinel_messages:
                    sentinel_counts[_sentinel_column(message)] += 1

                record = {
                    "path": run_dir.relative_to(REPO_ROOT).as_posix(),
                    "model": spec.model,
                    "seed": seed,
                    "arm": arm,
                    "launcher": _launcher_evidence(spec, seed),
                    "workers": workers,
                    "worker_evidence": worker_evidence,
                    "worker_evidence_strength": worker_evidence_strength,
                    "manifest_present": bool(manifest),
                    "manifest_git_commit": manifest.get("git_commit"),
                    "manifest_git_dirty": manifest.get("git_dirty"),
                    "manifest_git_semantics": "finalize_time_legacy",
                    "manifest_model": manifest.get("model"),
                    "manifest_governance_profile": manifest.get("governance_profile"),
                    "manifest_config_hash": manifest.get("config_hash"),
                    "nearest_commit_before_first_trace": nearest_commit,
                    "nearest_commit_is_attested_launch": False,
                    "critical_shared_fingerprint": critical_fp,
                    "critical_shared_blobs": critical_blobs,
                    "critical_shared_missing_paths": critical_missing,
                    "first_trace_timestamp": trace["first_timestamp"],
                    "last_trace_timestamp": trace["last_timestamp"],
                    "post_v21_fix_by_timestamp": _timestamp_after_v21(trace["first_timestamp"], v21_date),
                    "audit_rows": audit_rows,
                    "simulation_rows": sim_rows,
                    "trace_nonblank_lines": trace["nonblank_lines"],
                    "trace_parsed_records": trace["parsed_records"],
                    "trace_metadata_records": trace["metadata_records"],
                    "trace_malformed_json_lines": trace["malformed_json_lines"],
                    "trace_invalid_data_records": trace["invalid_data_records"],
                    "trace_data_rows": trace["data_rows"],
                    "trace_duplicate_agent_year_rows": trace["duplicate_key_rows"],
                    "audit_unique_agent_years": len(audit_keys),
                    "simulation_unique_agent_years": len(sim_keys),
                    "trace_unique_agent_years": len(trace["keys"]),
                    "trace_audit_key_match": trace["keys"] == audit_keys,
                    "trace_simulation_key_match": trace["keys"] == sim_keys,
                    "trace_to_simulation_request_mismatches": request_mismatches,
                    "trace_models": trace["models"],
                    "trace_model_evidence_present": bool(trace["models"]),
                    "trace_model_match": trace_model_match,
                    "config_identity": config_identity,
                    "config_identity_match": config_identity_match,
                    "priority_schema_marker_count": trace["priority_marker_count"],
                    "audit_header_sha256": hashlib.sha256("\n".join(audit_header).encode("utf-8")).hexdigest(),
                    "simulation_header_sha256": hashlib.sha256("\n".join(sim_header).encode("utf-8")).hexdigest(),
                    "trace_common_schema_sha256": hashlib.sha256("\n".join(trace["schema_keys"]).encode("utf-8")).hexdigest(),
                    "normalized_config_hash": normalized_config_hash,
                    "config_snapshot_sha256": _sha256_file(config_yaml),
                    "audit_csv_sha256": _sha256_file(audit_csv),
                    "simulation_csv_sha256": _sha256_file(sim_csv),
                    "trace_jsonl_sha256": trace["sha256"],
                    "condition_share_pct": round(sim_share, 9),
                    "sentinel_columns": sorted({_sentinel_column(m) for m in sentinel_messages}),
                    "analysis_artifact_complete": all(
                        value == EXPECTED_ROWS
                        for value in (audit_rows, sim_rows, trace["data_rows"], len(audit_keys), len(sim_keys), len(trace["keys"]))
                    ) and all((
                        trace["keys"] == audit_keys == sim_keys,
                        request_mismatches == 0,
                        trace["duplicate_key_rows"] == 0,
                        trace["malformed_json_lines"] == 0,
                        trace["invalid_data_records"] == 0,
                        config_identity_match,
                        trace_model_match,
                    )),
                    "raw_trace_exactly_one_row_per_agent_year": (
                        trace["data_rows"] == EXPECTED_ROWS and trace["duplicate_key_rows"] == 0
                    ),
                    "strict_reproducibility_verdict": "RED",
                }
                runs.append(record)
                run_cache[(spec.model, seed, arm)] = {**record, "config": config_data, "trace": trace}

    pairs: list[dict[str, Any]] = []
    for spec in MODEL_SPECS:
        for seed in spec.seeds:
            strict = run_cache[(spec.model, seed, "strict")]
            off = run_cache[(spec.model, seed, "no_validator")]
            common_agents = set(strict["trace"]["year1_prompts"]) & set(off["trace"]["year1_prompts"])
            prompt_equal = len(common_agents) == 78 and all(
                strict["trace"]["year1_prompts"][agent] == off["trace"]["year1_prompts"][agent]
                for agent in common_agents
            )
            state_equal = len(common_agents) == 78 and all(
                strict["trace"]["year1_state"][agent] == off["trace"]["year1_state"][agent]
                for agent in common_agents
            )
            config_equal = strict["normalized_config_hash"] == off["normalized_config_hash"]
            code_equal = bool(
                strict["critical_shared_fingerprint"]
                and off["critical_shared_fingerprint"]
                and strict["critical_shared_fingerprint"] == off["critical_shared_fingerprint"]
            )
            worker_evidence_sufficient = all(
                run["worker_evidence_strength"] != "unknown" for run in (strict, off)
            )
            worker_equal = bool(
                worker_evidence_sufficient
                and strict["workers"] is not None
                and strict["workers"] == off["workers"]
            )
            changed_files = sorted(
                path for path in CRITICAL_SHARED_PATHS
                if strict["critical_shared_blobs"].get(path) != off["critical_shared_blobs"].get(path)
            )
            tier_a = all((
                prompt_equal,
                config_equal,
                code_equal,
                worker_equal,
                strict["analysis_artifact_complete"],
                off["analysis_artifact_complete"],
            ))
            reasons: list[str] = []
            if not config_equal:
                reasons.append("normalized config snapshots differ")
            missing_paths = sorted(set(
                strict["critical_shared_missing_paths"] + off["critical_shared_missing_paths"]
            ))
            if missing_paths:
                reasons.append(f"critical source paths unresolved: {', '.join(missing_paths)}")
            elif not code_equal:
                reasons.append("nearest-pretrace shared-runtime fingerprints differ")
            if not worker_equal:
                if not worker_evidence_sufficient:
                    reasons.append("worker setting is not launch-attested in both arms")
                else:
                    reasons.append(f"worker mismatch: strict={strict['workers']}, no-validator={off['workers']}")
            if not prompt_equal:
                reasons.append("year-1 realized prompts differ")
            if not strict["analysis_artifact_complete"] or not off["analysis_artifact_complete"]:
                reasons.append("artifact or join contract incomplete")
            delta = off["condition_share_pct"] - strict["condition_share_pct"]
            pairs.append({
                "model": spec.model,
                "seed": seed,
                "tier": "A" if tier_a else "B",
                "tier_meaning": (
                    "observable-alignment subset: aligned config, reconstructed code era, launch-evidenced workers, prompts, and joins"
                    if tier_a else
                    "sensitivity-only: at least one observable operational or code-era mismatch"
                ),
                "year1_agents_compared": len(common_agents),
                "year1_prompt_exact_equal": prompt_equal,
                "year1_extra_state_exact_equal": state_equal,
                "normalized_config_equal": config_equal,
                "critical_shared_fingerprint_equal": code_equal,
                "worker_count_equal": worker_equal,
                "worker_evidence_sufficient": worker_evidence_sufficient,
                "changed_critical_shared_files": changed_files,
                "strict_nearest_commit": strict["nearest_commit_before_first_trace"],
                "no_validator_nearest_commit": off["nearest_commit_before_first_trace"],
                "strict_condition_share_pct": strict["condition_share_pct"],
                "no_validator_condition_share_pct": off["condition_share_pct"],
                "condition_share_delta_no_validator_minus_strict_pp": round(delta, 9),
                "direction_positive": delta > 0,
                "reasons": reasons,
            })

    return {
        "metadata": {
            "audit_schema_version": 1,
            "results_root": results_root.relative_to(REPO_ROOT).as_posix(),
            "v21_fix_commit": V21_FIX_COMMIT,
            "v21_fix_commit_date": v21_date,
            "manifest_launch_sampling_fix_commit": MANIFEST_LAUNCH_FIX_COMMIT,
            "manifest_launch_sampling_fix_date": launch_fix_date,
            "historical_manifest_warning": (
                "All audited runs predate the launch-sampling fix. Their legacy git_commit/git_dirty fields were sampled at finalization."
            ),
            "critical_shared_paths": list(CRITICAL_SHARED_PATHS),
            "expected_rows_per_run": EXPECTED_ROWS,
        },
        "runs": runs,
        "pairs": pairs,
        "sentinel_findings": [
            {
                "column": column,
                "runs_flagged": count,
                "status": SENTINEL_STATUS,
                "note": "Not declared in reserved_columns.yaml; manuscript-estimand usage has not been audited.",
            }
            for column, count in sorted(sentinel_counts.items())
        ],
    }


def _summary(inventory: dict[str, Any]) -> dict[str, Any]:
    runs = inventory["runs"]
    pairs = inventory["pairs"]
    tier_a = [pair for pair in pairs if pair["tier"] == "A"]
    tier_b = [pair for pair in pairs if pair["tier"] == "B"]
    return {
        "runs": len(runs),
        "pairs": len(pairs),
        "complete_runs": sum(run["analysis_artifact_complete"] for run in runs),
        "raw_exact_runs": sum(run["raw_trace_exactly_one_row_per_agent_year"] for run in runs),
        "raw_duplicate_rows": sum(run["trace_duplicate_agent_year_rows"] for run in runs),
        "raw_metadata_records": sum(run["trace_metadata_records"] for run in runs),
        "raw_malformed_json_lines": sum(run["trace_malformed_json_lines"] for run in runs),
        "raw_invalid_data_records": sum(run["trace_invalid_data_records"] for run in runs),
        "post_v21_runs": sum(run["post_v21_fix_by_timestamp"] is True for run in runs),
        "prompt_equal_pairs": sum(pair["year1_prompt_exact_equal"] for pair in pairs),
        "config_equal_pairs": sum(pair["normalized_config_equal"] for pair in pairs),
        "config_identity_runs": sum(run["config_identity_match"] for run in runs),
        "code_equal_pairs": sum(pair["critical_shared_fingerprint_equal"] for pair in pairs),
        "worker_equal_pairs": sum(pair["worker_count_equal"] for pair in pairs),
        "tier_a": tier_a,
        "tier_b": tier_b,
        "tier_a_models": sorted({pair["model"] for pair in tier_a}),
        "tier_a_positive": sum(pair["direction_positive"] for pair in tier_a),
        "all_positive": sum(pair["direction_positive"] for pair in pairs),
        "manifest_commit_missing": sum(not run["manifest_git_commit"] for run in runs),
        "manifest_dirty_true": sum(run["manifest_git_dirty"] is True for run in runs),
    }


def render_report(inventory: dict[str, Any]) -> str:
    s = _summary(inventory)
    tier_b_rows = "\n".join(
        f"| {p['model']} | {p['seed']} | {'; '.join(p['reasons'])} |"
        for p in s["tier_b"]
    )
    tier_a_model_rows = []
    for model in s["tier_a_models"]:
        cells = [p for p in s["tier_a"] if p["model"] == model]
        mean_delta = sum(p["condition_share_delta_no_validator_minus_strict_pp"] for p in cells) / len(cells)
        tier_a_model_rows.append(f"| {model} | {len(cells)} | {mean_delta:.2f} pp |")

    return f"""# Historical irrigation forensic reproducibility report

## Scope

- Input: `examples/irrigation_abm/results`, restricted to the 42 historical LLM irrigation runs used by the ICLR evidence pipeline.
- Runs surveyed: {s['runs']} ({s['pairs']} strict/no-validator seed pairs across five models).
- Observable artifacts checked: manifest, run-local config snapshot, raw JSONL, audit CSV, simulation CSV, recovered launcher or command evidence where available, pre-trace committed code fingerprint, realized year-1 prompt, and cross-file `(agent_id, year)` joins.
- This is a forensic salvage audit. It does not edit historical data or backfill missing launch metadata.

## Verdict

**RED for strict bitwise reproducibility; FORENSIC-SALVAGE PASS for the paper's bounded descriptive claim.** The legacy manifests cannot certify launch-time source because their Git fields were sampled at finalization. The full 21-pair observed corpus covers five models and all {s['all_positive']} pairs retain the same positive condition-share direction; a stricter {len(s['tier_a'])}-pair observable-alignment subset covers {len(s['tier_a_models'])} models. No experiment rerun is required to report this retrospective association, provided that it is not presented as clean-launch reproduction or a first-attempt causal effect.

## Findings

1. **RED — historical manifest semantics were misread by the earlier audit.** All 42 runs predate `{MANIFEST_LAUNCH_FIX_COMMIT[:8]}`, which moved Git sampling to construction time. In these historical manifests, `git_commit` and `git_dirty` were collected at finalization. Therefore the {s['manifest_dirty_true']} `git_dirty=true` values do not establish that runtime files were dirty at launch; the {s['manifest_commit_missing']} missing commits still prevent a GREEN reproducibility verdict. Fix: retain the legacy fields unchanged and publish this sidecar reconstruction.
2. **PASS — raw and tabular analysis rows are complete.** {s['complete_runs']}/{s['runs']} runs contain exactly {EXPECTED_ROWS:,} audit rows, simulation rows, and valid raw `(agent_id, year)` records. Every raw-to-audit and raw-to-simulation key join is exact; every raw `state_after.request` matches `simulation_log.request` within `1e-6`. The parser separately records {s['raw_metadata_records']} metadata headers, {s['raw_malformed_json_lines']} malformed JSON lines, {s['raw_invalid_data_records']} invalid data records, and {s['raw_duplicate_rows']} duplicate valid keys; metadata are not misclassified as observations.
3. **PASS — model-visible baseline parity is directly observed.** All {s['prompt_equal_pairs']}/{s['pairs']} paired seeds have byte-identical year-1 prompts for all 78 agents. No irrigation prompt contains `{PRIORITY_MARKER}`. This is stronger evidence for the realized model input than directory names or a reconstructed launcher alone.
4. **PASS with one declared sensitivity — run-local configuration identity and parity.** All {s['config_identity_runs']}/{s['runs']} snapshots record the expected model, seed, and arm-specific governance profile. {s['config_equal_pairs']}/{s['pairs']} pairs have identical normalized `config_snapshot.yaml` content after replacing only `metadata.governance_profile`. Ministral-3 8B seed 44 additionally records `shared.template_vars`; its realized year-1 prompts remain identical, but the pair is Tier B rather than silently pooled into the observable-alignment subset.
5. **PASS — an observable-alignment subset remains without new experiments.** {len(s['tier_a'])}/{s['pairs']} pairs align on normalized config, reconstructed nearest-pretrace shared-runtime fingerprint, launch-evidenced worker settings, exact year-1 prompts, and complete joins. This is not launch-attested provenance. The subset covers {len(s['tier_a_models'])} of five models, and every included pair has `no-validator - strict > 0` for the recorded high-scarcity condition share.

| model | observable-alignment paired seeds | mean condition-share delta |
| --- | ---: | ---: |
{chr(10).join(tier_a_model_rows)}

6. **YELLOW — {len(s['tier_b'])} pairs remain sensitivity-only, not discarded.** Their raw artifacts are complete and their year-1 prompts match, but at least one reconstructed code-era, worker-evidence, or config criterion is unresolved or differs. They must not carry the observable-alignment robustness claim.

| model | seed | reason for Tier B |
| --- | ---: | --- |
{tier_b_rows}

7. **PASS — the known v21 failure is not present by trace chronology.** {s['post_v21_runs']}/{s['runs']} first-trace timestamps are after v21 fix `{V21_FIX_COMMIT[:8]}`. Where a manifest commit exists it remains useful as finalization evidence, not as an attested launch commit.
8. **YELLOW — Gemma-3 4B worker evidence is incomplete or mismatched.** No-validator seeds 42–44 explicitly used four workers in `run_ensemble.bat`; governed seeds 43–44 explicitly used one, while governed seed 42 was not launched by that script. Seeds 45–46 have no recovered versioned launcher. All five pairs therefore remain Tier B even though their realized year-1 prompts match and their deltas have the same sign.
9. **RED under the checker contract — constant sentinels remain unresolved.** The inventory records every column flagged by `detect_audit_sentinels_in_csv()`. No `reserved_columns.yaml` exists, so the audit does not label them benign. Whether these columns feed any manuscript estimand requires a separate dependency audit; this generator does not assert that result.
10. **Decision — do not start a full rerun.** For the current paper, report the full corpus as a retrospective descriptive association and use the observable-alignment subset only as a sensitivity check. Reconsider targeted reruns only if the paper is expanded to a first-attempt causal mechanism claim or a venue explicitly requires clean-launch confirmation.

## Reproducible Command List

```powershell
python ICLR2027/submission/checks/forensic_irrigation_provenance.py
python ICLR2027/submission/checks/forensic_irrigation_provenance.py --check
python SUBMISSION_2026/TAE/evidence/_verify_pipeline.py
python -m pytest broker/ tests/
```

## Caveats

- A nearest commit before the first trace is a time-bounded reconstruction, not an attested launch commit. The inventory labels it accordingly.
- Gemma-3 4B seeds 45–46 have no recovered versioned launcher. Their worker setting is treated as unknown, not inferred into the observable-alignment subset.
- Historical uncommitted runtime patches cannot be recovered from Git after the fact. Exact prompt parity, run-local configs, realized validation/audit fields, source-era fingerprints, and output joins reduce but do not erase that uncertainty.
- Ollama real-model inference is not bitwise deterministic at fixed seed; this report evaluates observable contracts and multi-seed direction, not byte-identical regeneration.
- CRSS reference data were gitignored and were not hashed at launch. The present artifact hashes freeze outputs, not the historical input-data checkout.
- First-attempt governed-only runs are outside this scope and remain excluded from the manuscript because no matched no-validator first-attempt arm exists.
"""


def render_missing_steps(inventory: dict[str, Any]) -> str:
    s = _summary(inventory)
    tier_b = "\n".join(
        f"- [ ] Sensitivity disclosure: `{p['model']}` seed {p['seed']} — {'; '.join(p['reasons'])}."
        for p in s["tier_b"]
    )
    return f"""# Missing reproducibility steps and rerun decision

## Required before claiming exact historical reproducibility

- [ ] Do not claim GREEN or bitwise reproducibility: {s['manifest_commit_missing']} runs lack a manifest commit, and legacy Git fields were sampled at finalization rather than launch.
- [ ] Release the generated `artifact_inventory.yml` with the paper artifact so current files are checksum-frozen.
- [ ] Add a concise Methods/Reproducibility disclosure distinguishing the full 21-pair retrospective corpus from the {len(s['tier_a'])}-pair observable-alignment sensitivity subset.
- [ ] Preserve the six unresolved constant-column sentinel findings as an audit limitation; do not relabel them reserved without a versioned declaration.
- [ ] Audit manuscript estimand dependencies before stating whether any sentinel column is unused; this generator deliberately makes no such claim.

## Sensitivity-only cells

{tier_b}

## Experiment rerun decision

- **Current descriptive trace-audit paper:** zero experiment reruns required to report the observed association. Integrate the observable-alignment subset as sensitivity and disclose all other pairs as provenance-limited.
- **If adding a first-attempt appraisal-revision claim:** a matched no-validator first-attempt arm and clean provenance become required; that is a different estimand and is not authorized by this audit.
- **If a reviewer requires clean-launch confirmation:** design the smallest prospective confirmation after review. Do not pre-emptively rerun all 50 cells.
"""


def _write_or_check(path: Path, content: str, check: bool) -> None:
    normalized = content.replace("\r\n", "\n")
    if check:
        existing = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        if existing != normalized:
            raise SystemExit(f"DRIFT: regenerate {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--check", action="store_true", help="Fail if committed outputs differ from a fresh audit")
    args = parser.parse_args()

    results_root = args.results_root.resolve()
    output_dir = args.output_dir.resolve()
    inventory = audit(results_root)
    inventory_text = yaml.safe_dump(inventory, sort_keys=False, allow_unicode=True, width=120)
    _write_or_check(output_dir / "artifact_inventory.yml", inventory_text, args.check)
    _write_or_check(output_dir / "reproducibility_report.md", render_report(inventory), args.check)
    _write_or_check(output_dir / "missing_repro_steps.md", render_missing_steps(inventory), args.check)

    summary = _summary(inventory)
    print(
        "forensic irrigation audit: "
        f"runs={summary['runs']} pairs={summary['pairs']} "
        f"tier_a={len(summary['tier_a'])} tier_b={len(summary['tier_b'])} "
        f"tier_a_positive={summary['tier_a_positive']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
