"""Read-only ODD-LLM (Blocks A-E) protocol exporter CLI for any WAGF run directory.

Reads existing run artifacts under ``<run_dir>`` without mutating simulation
outputs, mutating validators, or instantiating a broker runtime, and produces:

- ``odd_llm.json`` — machine-readable Blocks A-E summary aligned with
  ODD (Grimm et al., 2020), ODD+D (Muller et al., 2013), and ODD-LLM
  (Downes et al., 2026, arXiv:2611.08932), plus an explicit
  ``unobserved_fields`` inventory (Invariant 2: missing inputs stay ``None``
  or absent, never fabricated placeholders).
- ``ODD_LLM.md`` — human-readable Supplementary Information Markdown report.

Usage::

    python -m broker.tools.export_odd_llm <run_dir>
    python -m broker.tools.export_odd_llm <run_dir> --hindcast-json results/hindcast_verification.json
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping
import hashlib
import json
import re
import string
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from broker.utils.agent_config import resolve_rule_grounding

SCHEMA_VERSION = "wagf.odd_llm.v1"
PROTOCOL_ALIGNMENT = [
    "ODD (Grimm et al., 2020)",
    "ODD+D (Muller et al., 2013)",
    "ODD-LLM Blocks A-E (Downes et al., 2026, arXiv:2611.08932)",
]

_BUILTIN_ROLES_IGNORED = frozenset({"global_config", "shared", "metadata", "default"})
_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else None
    except (OSError, ValueError):
        return None


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    parsed = json.loads(stripped)
                except ValueError:
                    continue
                if isinstance(parsed, dict) and "_metadata" not in parsed:
                    rows.append(parsed)
    except OSError:
        return []
    return rows


def _read_yaml(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else None
    except (OSError, yaml.YAMLError):
        return None


def _extract_placeholders(template: str) -> List[str]:
    names = set()
    try:
        for _lit, field_name, _fmt, _conv in string.Formatter().parse(template):
            if field_name:
                root = field_name.split(".", 1)[0].split("[", 1)[0]
                if root.isidentifier():
                    names.add(root)
    except ValueError:
        names.update(_PLACEHOLDER_RE.findall(template.replace("{{", "").replace("}}", "")))
    return sorted(names)


def _resolve_config_data(
    run_dir: Path,
    *,
    explicit_config: Optional[Path],
    manifest: Optional[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], Optional[Path]]:
    if explicit_config is not None:
        cfg = _read_yaml(explicit_config)
        return cfg, explicit_config

    candidates: List[Path] = [run_dir / "config_snapshot.yaml"]
    if isinstance(manifest, dict):
        for key in ("derived_from_config", "agent_types_config"):
            val = manifest.get(key)
            if isinstance(val, str) and val.strip() and val != "unknown":
                candidates.append(Path(val))
    for cand in candidates:
        cfg = _read_yaml(cand)
        if cfg is not None:
            return cfg, cand
    return None, None


def _collect_trace_statistics(run_dir: Path) -> Dict[str, Any]:
    raw_dir = run_dir / "raw"
    trace_paths = sorted(raw_dir.glob("*.jsonl")) if raw_dir.is_dir() else []
    parse_layers: Counter[str] = Counter()
    cognitive_modes: Counter[str] = Counter()
    surprise_values: List[float] = []
    appraisal_drift_count = 0
    appraisal_drift_seen = False
    appraisal_relabeled_count = 0
    appraisal_relabeled_seen = False
    trace_rows = 0
    rows_with_run_id = 0
    rows_with_step_id = 0
    rows_with_kg_triples = 0
    observed_roles: set[str] = set()

    for tp in trace_paths:
        for row in _read_jsonl(tp):
            trace_rows += 1
            if isinstance(row.get("run_id"), str) and row["run_id"].strip():
                rows_with_run_id += 1
            if row.get("_step_id") is not None or row.get("step_id") is not None:
                rows_with_step_id += 1
            if isinstance(row.get("agent_type"), str) and row["agent_type"].strip():
                observed_roles.add(row["agent_type"].strip())
            sp = row.get("skill_proposal")
            if isinstance(sp, dict) and isinstance(sp.get("parse_layer"), str):
                parse_layers[sp["parse_layer"]] += 1
            cog = row.get("cognitive_audit")
            if isinstance(cog, dict):
                mode = cog.get("system_mode") or cog.get("cognitive_mode") or cog.get("mode")
                if isinstance(mode, str) and mode.strip():
                    cognitive_modes[mode.strip()] += 1
                surp = cog.get("surprise")
                if isinstance(surp, (int, float)) and not isinstance(surp, bool):
                    surprise_values.append(float(surp))
            else:
                cog = {}

            drift_src = row if ("appraisal_drifted" in row or "appraisal_drift" in row) else cog
            if "appraisal_drifted" in drift_src or "appraisal_drift" in drift_src:
                val_drifted = drift_src.get("appraisal_drifted")
                val_drift = drift_src.get("appraisal_drift")
                if val_drifted != "unobserved" and val_drift != "unobserved":
                    appraisal_drift_seen = True
                    if val_drifted is True or (
                        isinstance(val_drift, str) and bool(val_drift.strip())
                    ):
                        appraisal_drift_count += 1

            rel_src = row if "appraisal_relabeled" in row else cog
            if "appraisal_relabeled" in rel_src and rel_src["appraisal_relabeled"] != "unobserved":
                appraisal_relabeled_seen = True
                if rel_src["appraisal_relabeled"] is True:
                    appraisal_relabeled_count += 1
            social = row.get("social_audit")
            if isinstance(social, dict) and social.get("kg_triples"):
                rows_with_kg_triples += 1

    return {
        "trace_files": [tp.name for tp in trace_paths],
        "trace_rows": trace_rows,
        "observed_roles": sorted(observed_roles),
        "parse_layer_distribution": dict(sorted(parse_layers.items())),
        "cognitive_modes": dict(sorted(cognitive_modes.items())),
        "mean_surprise": (
            round(sum(surprise_values) / len(surprise_values), 6) if surprise_values else None
        ),
        "appraisal_drift_count": appraisal_drift_count if appraisal_drift_seen else None,
        "appraisal_relabeled_count": (
            appraisal_relabeled_count if appraisal_relabeled_seen else None
        ),
        "rows_with_run_id": rows_with_run_id,
        "rows_with_step_id": rows_with_step_id,
        "rows_with_kg_triples": rows_with_kg_triples,
    }


def _collect_memory_and_reflection_stats(
    run_dir: Path,
    broker_run: Optional[Dict[str, Any]],
    integrity: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    mem_rows = _read_jsonl(run_dir / "memory_log.jsonl")
    refl_rows = _read_jsonl(run_dir / "reflection_log.jsonl")

    writes_by_origin: Optional[Dict[str, int]] = None
    if isinstance(broker_run, dict) and isinstance(broker_run.get("memory_writes_by_origin"), dict):
        writes_by_origin = {
            str(k): int(v) for k, v in broker_run["memory_writes_by_origin"].items()
        }
    elif isinstance(integrity, dict) and isinstance(integrity.get("governance_carryover"), dict):
        co_writes = integrity["governance_carryover"].get("memory_writes_by_origin")
        if isinstance(co_writes, dict):
            writes_by_origin = {str(k): int(v) for k, v in co_writes.items()}
    elif mem_rows:
        origin_counts: Counter[str] = Counter()
        for row in mem_rows:
            origin_counts[str(row.get("origin") or "unknown")] += 1
        writes_by_origin = dict(sorted(origin_counts.items()))

    hop_distribution: Counter[str] = Counter()
    mem_with_memory_id = 0
    mem_with_triple_id = 0
    mem_with_source_step_id = 0
    mem_with_run_id = 0
    for row in mem_rows:
        if row.get("memory_id") is not None:
            mem_with_memory_id += 1
        if row.get("triple_id") is not None:
            mem_with_triple_id += 1
        if row.get("source_step_id") is not None:
            mem_with_source_step_id += 1
        if row.get("run_id") is not None:
            mem_with_run_id += 1
        hop = row.get("hop")
        if hop is not None:
            hop_distribution[str(hop)] += 1

    refl_with_id = sum(1 for row in refl_rows if row.get("reflection_id") is not None)
    refl_with_retrieved = sum(
        1 for row in refl_rows if isinstance(row.get("retrieved_memory_ids"), list)
    )

    return {
        "memory_log_rows": len(mem_rows),
        "memory_writes_by_origin": writes_by_origin,
        "memory_rows_with_run_id": mem_with_run_id,
        "memory_rows_with_memory_id": mem_with_memory_id,
        "memory_rows_with_triple_id": mem_with_triple_id,
        "memory_rows_with_source_step_id": mem_with_source_step_id,
        "hop_distribution": dict(sorted(hop_distribution.items())),
        "reflection_log_rows": len(refl_rows),
        "reflection_rows_with_id": refl_with_id,
        "reflection_rows_with_retrieved_memory_ids": refl_with_retrieved,
    }


def _collect_role_rule_grounding(
    cfg: Optional[Dict[str, Any]],
    role: str,
    governance_profile: str,
) -> Optional[Dict[str, int]]:
    if not isinstance(cfg, dict):
        return None
    rcfg = cfg.get(role) if isinstance(cfg.get(role), dict) else {}
    role_gov = rcfg.get("governance") if isinstance(rcfg.get("governance"), dict) else {}
    profile_block = role_gov.get(governance_profile)
    if not isinstance(profile_block, dict):
        profile_block = role_gov.get("default")
    if not isinstance(profile_block, dict):
        top_gov = cfg.get("governance") if isinstance(cfg.get("governance"), dict) else {}
        top_prof = top_gov.get(governance_profile)
        if not isinstance(top_prof, dict):
            top_prof = top_gov.get("default")
        if isinstance(top_prof, dict) and isinstance(top_prof.get(role), dict):
            profile_block = top_prof[role]
    if not isinstance(profile_block, dict):
        return None

    counts: Counter[str] = Counter()
    for section in ("thinking_rules", "identity_rules"):
        raw_rules = profile_block.get(section)
        if isinstance(raw_rules, dict):
            rules_iter = [{"id": k, **v} if isinstance(v, dict) else {"id": k} for k, v in raw_rules.items()]
        elif isinstance(raw_rules, list):
            rules_iter = [r for r in raw_rules if isinstance(r, dict)]
        else:
            rules_iter = []
        for rule in rules_iter:
            counts[resolve_rule_grounding(rule)] += 1
    return dict(sorted(counts.items())) if counts else None


def _template_base_dirs(
    explicit_config: Optional[Path],
    manifest: Optional[Dict[str, Any]],
    resolved_cfg_path: Optional[Path],
) -> List[Path]:
    dirs: List[Path] = []
    seen: set[Path] = set()

    def _add_parent(candidate: Any) -> None:
        if isinstance(candidate, Path):
            p = candidate.parent
        elif isinstance(candidate, str) and candidate.strip() and candidate != "unknown":
            p = Path(candidate).parent
        else:
            return
        if p not in seen:
            seen.add(p)
            dirs.append(p)

    _add_parent(explicit_config)
    if isinstance(manifest, dict):
        _add_parent(manifest.get("derived_from_config"))
        _add_parent(manifest.get("agent_types_config"))
    _add_parent(resolved_cfg_path)
    return dirs


def _resolve_prompt_file_text(
    file_ref: str,
    base_dirs: List[Path],
) -> Tuple[Optional[str], Optional[str]]:
    raw_ref = Path(file_ref)
    candidates = [raw_ref] if raw_ref.is_absolute() else [base / raw_ref for base in base_dirs]
    for cand in candidates:
        if cand.is_file():
            try:
                raw_bytes = cand.read_bytes()
                return raw_bytes.decode("utf-8"), hashlib.sha256(raw_bytes).hexdigest()
            except (OSError, UnicodeError):
                continue
    return None, None


def _extract_role_specs(
    cfg: Optional[Dict[str, Any]],
    observed_roles: List[str],
    broker_run: Optional[Dict[str, Any]],
    governance_profile: str,
    unobserved: set[str],
    *,
    manifest: Optional[Dict[str, Any]] = None,
    explicit_config: Optional[Path] = None,
    resolved_cfg_path: Optional[Path] = None,
    default_model: Any = None,
) -> Tuple[List[str], Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    role_names: List[str] = []
    seen: set[str] = set()
    if isinstance(cfg, dict):
        for key, val in cfg.items():
            if key in _BUILTIN_ROLES_IGNORED or not isinstance(val, dict):
                continue
            if any(
                k in val
                for k in (
                    "prompt_template",
                    "prompt_template_file",
                    "actions",
                    "response_format",
                    "psychological_framework",
                    "description",
                    "agent_type",
                )
            ):
                role_names.append(str(key))
                seen.add(str(key))
    if isinstance(broker_run, dict) and isinstance(broker_run.get("population"), dict):
        for key in broker_run["population"]:
            if str(key) not in seen:
                role_names.append(str(key))
                seen.add(str(key))
    for role in observed_roles:
        if role not in seen:
            role_names.append(role)
            seen.add(role)

    shared = cfg.get("shared", {}) if isinstance(cfg, dict) and isinstance(cfg.get("shared"), dict) else {}
    global_cfg = (
        cfg.get("global_config", {})
        if isinstance(cfg, dict) and isinstance(cfg.get("global_config"), dict)
        else {}
    )
    default_rcfg = (
        cfg.get("default", {}) if isinstance(cfg, dict) and isinstance(cfg.get("default"), dict) else {}
    )
    shared_rf = shared.get("response_format") if isinstance(shared, dict) else None
    shared_llm = shared.get("llm") if isinstance(shared.get("llm"), dict) else {}
    global_llm = global_cfg.get("llm") if isinstance(global_cfg.get("llm"), dict) else {}
    default_llm = default_rcfg.get("llm_params") if isinstance(default_rcfg.get("llm_params"), dict) else {}

    base_dirs = _template_base_dirs(explicit_config, manifest, resolved_cfg_path)
    manifest_hashes = (
        manifest.get("prompt_template_sha256")
        if isinstance(manifest, dict) and isinstance(manifest.get("prompt_template_sha256"), dict)
        else {}
    )
    manifest_resolved = (
        manifest.get("llm_params_resolved")
        if isinstance(manifest, dict) and isinstance(manifest.get("llm_params_resolved"), dict)
        else {}
    )

    cognitive_roles: Dict[str, Dict[str, Any]] = {}
    prompt_roles: Dict[str, Dict[str, Any]] = {}

    for role in role_names:
        rcfg = cfg.get(role, {}) if isinstance(cfg, dict) and isinstance(cfg.get(role), dict) else {}
        psych_fw = rcfg.get("psychological_framework")
        if psych_fw is None:
            unobserved.add(f"block_b_cognitive_and_psychological_design.roles.{role}.psychological_framework")

        rf = rcfg.get("response_format") if isinstance(rcfg.get("response_format"), dict) else shared_rf
        fields_meta: List[Dict[str, Any]] = []
        constructs: Dict[str, Any] = {}
        if isinstance(rcfg.get("constructs"), dict):
            constructs.update(rcfg["constructs"])
        if isinstance(rf, dict) and isinstance(rf.get("fields"), list):
            for fld in rf["fields"]:
                if isinstance(fld, dict):
                    key = fld.get("key") or fld.get("name")
                    ftype = fld.get("type")
                    fields_meta.append({"key": key, "type": ftype})
                    if ftype == "appraisal" and key:
                        constructs.setdefault(str(key), {k: v for k, v in fld.items() if k != "key"})

        rule_grounding_counts = _collect_role_rule_grounding(cfg, role, governance_profile)
        cognitive_roles[role] = {
            "psychological_framework": psych_fw,
            "constructs": constructs or None,
            "rule_grounding_counts": rule_grounding_counts,
        }

        template_file = rcfg.get("prompt_template_file") or default_rcfg.get("prompt_template_file")
        template_inline = rcfg.get("prompt_template")
        if template_inline is None:
            template_inline = default_rcfg.get("prompt_template")

        resolved_text: Optional[str] = None
        fallback_sha: Optional[str] = None
        if isinstance(template_file, str) and template_file.strip():
            resolved_text, fallback_sha = _resolve_prompt_file_text(template_file.strip(), base_dirs)
        if resolved_text is None and isinstance(template_inline, str):
            resolved_text = template_inline
            fallback_sha = hashlib.sha256(template_inline.encode("utf-8")).hexdigest()

        manifest_sha = manifest_hashes.get(role)
        if manifest_sha is None and len(role_names) == 1:
            manifest_sha = manifest_hashes.get("default")
        prompt_sha256 = manifest_sha if isinstance(manifest_sha, str) and manifest_sha.strip() else fallback_sha
        placeholders = _extract_placeholders(resolved_text) if isinstance(resolved_text, str) else None
        if prompt_sha256 is None and placeholders is None:
            unobserved.add(f"block_c_llm_specification_and_prompt_contract.roles.{role}.prompt_template")

        actions_cfg = rcfg.get("actions") if isinstance(rcfg.get("actions"), list) else []
        action_ids = [
            a.get("id") for a in actions_cfg if isinstance(a, dict) and isinstance(a.get("id"), str)
        ]
        decider_cfg = rcfg.get("decider") if isinstance(rcfg.get("decider"), dict) else {}
        decider_type = decider_cfg.get("type") or ("llm" if rcfg else None)

        role_llm_params: Optional[Dict[str, Any]] = None
        llm_params_source: Optional[str] = None
        role_model: Any = default_model if decider_type == "llm" else None
        if isinstance(manifest_resolved.get(role), dict):
            role_llm_params = dict(manifest_resolved[role])
            llm_params_source = "manifest_resolved"
            role_model = role_llm_params.get("model") or role_model
        elif isinstance(cfg, dict):
            agent_llm = rcfg.get("llm_params") if isinstance(rcfg.get("llm_params"), dict) else {}
            if any((shared_llm, global_llm, default_llm, agent_llm)):
                merged: Dict[str, Any] = {}
                merged.update(shared_llm)
                merged.update(global_llm)
                merged.update(default_llm)
                merged.update(agent_llm)
                raw_override = merged.get("model")
                if isinstance(raw_override, str) and raw_override.strip().lower() in {
                    "",
                    "command-line-override",
                    "cli-override",
                }:
                    raw_override = None
                effective_role_model = raw_override or default_model
                if effective_role_model is not None:
                    merged["model"] = effective_role_model
                role_llm_params = merged
                llm_params_source = "config_fallback"
                role_model = effective_role_model if decider_type == "llm" else merged.get("model")

        prompt_roles[role] = {
            "model": role_model,
            "llm_params": role_llm_params,
            "llm_params_source": llm_params_source,
            "prompt_template_file": template_file.strip() if isinstance(template_file, str) and template_file.strip() else None,
            "prompt_sha256": prompt_sha256,
            "prompt_placeholders": placeholders,
            "response_format_fields": fields_meta or None,
            "action_ids": action_ids or None,
            "decider_type": decider_type,
        }

    return role_names, cognitive_roles, prompt_roles


def build_odd_llm_report(
    run_dir: Path,
    *,
    config_path: Optional[Path] = None,
    hindcast_metrics_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build structured Blocks A-E ODD-LLM dictionary from an existing run directory."""
    resolved_dir = Path(run_dir)
    if not resolved_dir.is_dir():
        raise FileNotFoundError(f"Run directory does not exist: {resolved_dir}")

    unobserved: set[str] = set()

    broker_run = _read_json(resolved_dir / "broker_run.json")
    manifest = _read_json(resolved_dir / "reproducibility_manifest.json")
    integrity = _read_json(resolved_dir / "run_integrity.json")
    audit_summary = _read_json(resolved_dir / "audit_summary.json")
    gov_summary = _read_json(resolved_dir / "governance_summary.json")
    coord_snap = _read_json(resolved_dir / "coordination_snapshot.json")

    if broker_run is None:
        unobserved.add("artifacts.broker_run.json")
    if manifest is None:
        unobserved.add("artifacts.reproducibility_manifest.json")
    if integrity is None:
        unobserved.add("artifacts.run_integrity.json")
    if coord_snap is None:
        unobserved.add("artifacts.coordination_snapshot.json")

    hindcast_path = (
        Path(hindcast_metrics_path)
        if hindcast_metrics_path is not None
        else resolved_dir / "hindcast_verification.json"
    )
    hindcast_data = _read_json(hindcast_path)
    if hindcast_metrics_path is not None and hindcast_data is None:
        raise ValueError(f"Could not parse hindcast JSON file: {hindcast_path}")
    if hindcast_data is None:
        unobserved.add("block_e_reproducibility_hindcast_and_integrity.hindcast_verification")

    if config_path is not None and not Path(config_path).is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    cfg, resolved_cfg_path = _resolve_config_data(
        resolved_dir, explicit_config=Path(config_path) if config_path else None, manifest=manifest
    )
    if cfg is None:
        unobserved.add("artifacts.agent_types_config")

    trace_stats = _collect_trace_statistics(resolved_dir)
    mem_stats = _collect_memory_and_reflection_stats(resolved_dir, broker_run, integrity)

    global_cfg = cfg.get("global_config", {}) if isinstance(cfg, dict) else {}
    if not isinstance(global_cfg, dict):
        global_cfg = {}

    model = (
        (broker_run or {}).get("model")
        or (manifest or {}).get("model")
        or (global_cfg.get("llm", {}) if isinstance(global_cfg.get("llm"), dict) else {}).get("model")
    )
    if model is None:
        unobserved.add("block_c_llm_specification_and_prompt_contract.model")

    governance_profile = (
        (broker_run or {}).get("governance")
        or (manifest or {}).get("governance_profile")
        or (integrity or {}).get("governance_mode")
        or "default"
    )
    explicit_cfg_path = Path(config_path) if config_path else None
    role_names, cognitive_roles, prompt_roles = _extract_role_specs(
        cfg,
        trace_stats["observed_roles"],
        broker_run,
        str(governance_profile),
        unobserved,
        manifest=manifest,
        explicit_config=explicit_cfg_path,
        resolved_cfg_path=resolved_cfg_path,
        default_model=model,
    )

    run_id: Optional[str] = None
    for src in (coord_snap, manifest, broker_run):
        if isinstance(src, dict) and isinstance(src.get("run_id"), str) and src["run_id"].strip():
            run_id = src["run_id"].strip()
            break
    if run_id is None:
        unobserved.add("run_id")

    years = (broker_run or {}).get("years") or (manifest or {}).get("num_years")
    if years is None:
        unobserved.add("block_a_overview_and_entities.years")

    agent_count = (broker_run or {}).get("agent_count")
    if agent_count is None and isinstance(integrity, dict):
        agent_count = integrity.get("audit_agents")
    if agent_count is None:
        unobserved.add("block_a_overview_and_entities.agent_count")

    # Block A: Overview, Entities, Scales & Heterogeneity Sources
    social_graph_summary = (
        coord_snap.get("social_graph") if isinstance(coord_snap, dict) else None
    )
    if social_graph_summary is None and isinstance(coord_snap, dict):
        social_block = coord_snap.get("social")
        if isinstance(social_block, dict) and "social_graph" in social_block:
            social_graph_summary = social_block.get("social_graph")
    if social_graph_summary is None:
        unobserved.add("block_a_overview_and_entities.spatial_and_social_graph")

    inactive_final = (integrity or {}).get("inactive_agents_final")
    inactive_count = (integrity or {}).get("inactive_agents_final_count")
    if inactive_count is None and isinstance(inactive_final, list):
        inactive_count = len(inactive_final)

    block_a: Dict[str, Any] = {
        "years": years,
        "agent_count": agent_count,
        "agent_roles": role_names,
        "population": (broker_run or {}).get("population"),
        "population_sources": (broker_run or {}).get("population_sources"),
        "phase_order": (broker_run or {}).get("phase_order"),
        "spatial_and_social_graph": social_graph_summary,
        "inactive_agents_final_count": inactive_count,
        "inactive_agents_final": inactive_final,
    }

    # Block B: Cognitive, Psychological & Memory Design
    mem_cfg = (
        (broker_run or {}).get("memory")
        or (global_cfg.get("memory") if isinstance(global_cfg.get("memory"), dict) else None)
    )
    refl_cfg = (
        (broker_run or {}).get("reflection")
        or (global_cfg.get("reflection") if isinstance(global_cfg.get("reflection"), dict) else None)
    )
    if not trace_stats["cognitive_modes"] and trace_stats["mean_surprise"] is None:
        unobserved.add("block_b_cognitive_and_psychological_design.dual_process_memory.observed_cognitive_modes")

    gov_cfg = global_cfg.get("governance") if isinstance(global_cfg.get("governance"), dict) else {}
    appraisal_freeze = gov_cfg.get("appraisal_freeze")
    if not isinstance(appraisal_freeze, bool):
        appraisal_freeze = None
        unobserved.add("block_b_cognitive_and_psychological_design.appraisal_freeze")

    block_b: Dict[str, Any] = {
        "appraisal_freeze": appraisal_freeze,
        "roles": cognitive_roles,
        "dual_process_memory": {
            "engine_type": (
                (mem_cfg or {}).get("engine_type")
                or (mem_cfg or {}).get("engine")
                or (integrity or {}).get("memory_engine_type")
                or (manifest or {}).get("memory_engine_class")
            ),
            "engine_class": (manifest or {}).get("memory_engine_class"),
            "memory_config": mem_cfg,
            "observed_cognitive_modes": trace_stats["cognitive_modes"] or None,
            "mean_surprise": trace_stats["mean_surprise"],
            "appraisal_drift_count": trace_stats["appraisal_drift_count"],
            "appraisal_relabeled_count": trace_stats["appraisal_relabeled_count"],
            "memory_writes_by_origin": mem_stats["memory_writes_by_origin"],
            "memory_log_rows": mem_stats["memory_log_rows"],
            "reflection_settings": refl_cfg,
            "reflection_log_rows": mem_stats["reflection_log_rows"],
        },
    }

    # Block C: LLM Specification & Prompt/Parsing Contract
    llm_cfg = global_cfg.get("llm") if isinstance(global_cfg.get("llm"), dict) else None
    manifest_llm_fields: Dict[str, Any] = {}
    if isinstance(manifest, dict):
        for k in (
            "temperature",
            "top_p",
            "num_ctx",
            "num_predict",
            "llm_timeout_seconds_effective",
            "llm_model_defaults",
        ):
            if k in manifest and manifest[k] is not None:
                manifest_llm_fields[k] = manifest[k]
    if manifest_llm_fields:
        llm_parameters: Optional[Dict[str, Any]] = {**(llm_cfg or {}), **manifest_llm_fields}
        llm_parameters_source: Optional[str] = "manifest"
    elif llm_cfg:
        llm_parameters = dict(llm_cfg)
        llm_parameters_source = "config_fallback"
    else:
        llm_parameters = None
        llm_parameters_source = None

    llm_parameters_by_role = {
        role: {"params": info["llm_params"], "source": info["llm_params_source"]}
        for role, info in prompt_roles.items()
        if info.get("llm_params") is not None
    } or None

    model_digest = (manifest or {}).get("model_digest") if isinstance(manifest, dict) else None
    if model_digest is None and isinstance(manifest, dict) and isinstance(manifest.get("model_metadata"), dict):
        model_digest = manifest["model_metadata"].get("model_digest")

    parse_layer_dist = (
        (integrity or {}).get("parse_layer_distribution")
        or trace_stats["parse_layer_distribution"]
        or None
    )
    block_c: Dict[str, Any] = {
        "model": model,
        "model_digest": model_digest,
        "thinking_mode": (broker_run or {}).get("thinking_mode") or (manifest or {}).get("thinking_mode"),
        "llm_parameters": llm_parameters,
        "llm_parameters_source": llm_parameters_source,
        "llm_parameters_by_role": llm_parameters_by_role,
        "llm_stats": (manifest or {}).get("llm_stats"),
        "roles": prompt_roles,
        "parse_layer_distribution": parse_layer_dist,
        "trace_rows_observed": trace_stats["trace_rows"],
    }

    # Block D: Governance, Coupling, Social Transmission & Causal Provenance
    gov_cfg = global_cfg.get("governance") if isinstance(global_cfg.get("governance"), dict) else {}
    carryover = (integrity or {}).get("governance_carryover")
    coupling_meta = (
        (manifest or {}).get("coupling")
        or (audit_summary or {}).get("coupling")
    )
    if coupling_meta is None:
        unobserved.add("block_d_governance_coupling_and_social_transmission.coupling")

    block_d: Dict[str, Any] = {
        "governance_profile": governance_profile,
        "max_retries": gov_cfg.get("max_retries"),
        "retry_feedback_mode": (
            (cfg.get("metadata", {}) if isinstance(cfg, dict) else {}).get("retry_feedback_mode")
            if isinstance(cfg, dict) and isinstance(cfg.get("metadata"), dict)
            else gov_cfg.get("retry_feedback_mode")
        ),
        "governance_summary": gov_summary,
        "audit_summary": audit_summary,
        "invariant_7_isolation": {
            "rejection_line_style": (broker_run or {}).get("rejection_line_style"),
            "governance_carryover_ok": (
                carryover.get("ok") if isinstance(carryover, dict) else None
            ),
            "governance_carryover": carryover,
        },
        "coupling": coupling_meta,
        "coordination_and_social_kg": {
            "coordination_snapshot": coord_snap,
            "causal_join_keys": {
                "trace_rows_with_run_id": trace_stats["rows_with_run_id"],
                "trace_rows_with_step_id": trace_stats["rows_with_step_id"],
                "trace_rows_with_kg_triples": trace_stats["rows_with_kg_triples"],
                "memory_rows_with_run_id": mem_stats["memory_rows_with_run_id"],
                "memory_rows_with_memory_id": mem_stats["memory_rows_with_memory_id"],
                "memory_rows_with_triple_id": mem_stats["memory_rows_with_triple_id"],
                "memory_rows_with_source_step_id": mem_stats["memory_rows_with_source_step_id"],
                "hop_distribution": mem_stats["hop_distribution"] or None,
                "reflection_rows_with_id": mem_stats["reflection_rows_with_id"],
                "reflection_rows_with_retrieved_memory_ids": mem_stats[
                    "reflection_rows_with_retrieved_memory_ids"
                ],
            },
        },
    }

    # Block E: Reproducibility, Hindcast Verification & Integrity
    run_env = (manifest or {}).get("run_environment") if isinstance(manifest, dict) else None
    git_commit = (manifest or {}).get("git_commit")
    if git_commit is None and isinstance(run_env, dict):
        wg = run_env.get("wagf_source_git")
        if isinstance(wg, dict):
            git_commit = wg.get("commit")
    if git_commit is None:
        unobserved.add("block_e_reproducibility_hindcast_and_integrity.git_commit")

    coverage_summary = None
    if isinstance(integrity, dict):
        cov_keys = (
            "audit_rows",
            "audit_aborted_rows",
            "audit_agents",
            "audit_years",
            "configured_grid_rows",
            "audit_rows_missing_vs_configured_grid",
        )
        cov = {k: integrity[k] for k in cov_keys if k in integrity}
        coverage_summary = cov or None

    exog_meta = None
    if isinstance(coord_snap, dict) and "exogenous_schedule" in coord_snap:
        exog_meta = coord_snap["exogenous_schedule"]
    elif isinstance(broker_run, dict) and "exogenous_schedule" in broker_run:
        exog_meta = broker_run["exogenous_schedule"]

    seed_val = next(
        (
            src["seed"]
            for src in (broker_run, manifest, integrity)
            if isinstance(src, dict) and src.get("seed") is not None
        ),
        None,
    )
    if seed_val is None:
        unobserved.add("block_e_reproducibility_hindcast_and_integrity.seed")

    block_e: Dict[str, Any] = {
        "seed": seed_val,
        "git_commit": git_commit,
        "git_dirty": (
            (run_env.get("wagf_source_git", {}) if isinstance(run_env, dict) else {}).get("dirty")
            if isinstance(run_env, dict) and isinstance(run_env.get("wagf_source_git"), dict)
            else None
        ),
        "python_version": run_env.get("python_version") if isinstance(run_env, dict) else None,
        "platform": run_env.get("platform") if isinstance(run_env, dict) else None,
        "config_source": str(resolved_cfg_path) if resolved_cfg_path is not None else None,
        "integrity_ok": (integrity or {}).get("integrity_ok"),
        "coverage_summary": coverage_summary,
        "leakage_scan": (integrity or {}).get("leakage_scan"),
        "exogenous_schedule": exog_meta,
        "hindcast_verification": hindcast_data,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "protocol_alignment": list(PROTOCOL_ALIGNMENT),
        "run_dir": str(resolved_dir),
        "run_id": run_id,
        "block_a_overview_and_entities": block_a,
        "block_b_cognitive_and_psychological_design": block_b,
        "block_c_llm_specification_and_prompt_contract": block_c,
        "block_d_governance_coupling_and_social_transmission": block_d,
        "block_e_reproducibility_hindcast_and_integrity": block_e,
        "unobserved_fields": sorted(unobserved),
    }


def _fmt(val: Any) -> str:
    if val is None:
        return "unobserved"
    if isinstance(val, (dict, list)):
        return f"`{json.dumps(val, ensure_ascii=False, sort_keys=True, default=str)}`"
    return f"`{val}`"


def render_odd_llm_markdown(report: Mapping[str, Any]) -> str:
    """Render a Blocks A-E ODD-LLM dictionary as structured Markdown."""
    a = report.get("block_a_overview_and_entities", {})
    b = report.get("block_b_cognitive_and_psychological_design", {})
    c = report.get("block_c_llm_specification_and_prompt_contract", {})
    d = report.get("block_d_governance_coupling_and_social_transmission", {})
    e = report.get("block_e_reproducibility_hindcast_and_integrity", {})

    lines: List[str] = [
        "# ODD-LLM Protocol Report (Blocks A-E)",
        "",
        f"- Schema: {_fmt(report.get('schema_version'))}",
        f"- Run Directory: {_fmt(report.get('run_dir'))}",
        f"- Run ID: {_fmt(report.get('run_id'))}",
        f"- Alignment: {', '.join(report.get('protocol_alignment', ()))}",
        "",
        "## Block A — Overview, Entities & Heterogeneity",
        "",
        f"- Years: {_fmt(a.get('years'))}",
        f"- Agent Count: {_fmt(a.get('agent_count'))}",
        f"- Agent Roles: {_fmt(a.get('agent_roles'))}",
        f"- Population: {_fmt(a.get('population'))}",
        f"- Population Sources (SHA-256): {_fmt(a.get('population_sources'))}",
        f"- Phase Order: {_fmt(a.get('phase_order'))}",
        f"- Inactive Agents Final: {_fmt(a.get('inactive_agents_final'))} (count={_fmt(a.get('inactive_agents_final_count'))})",
        f"- Spatial & Social Graph: {_fmt(a.get('spatial_and_social_graph'))}",
        "",
        "## Block B — Cognitive, Psychological & Memory Design",
        "",
        f"- Appraisal Freeze (`global_config.governance.appraisal_freeze`): {_fmt(b.get('appraisal_freeze'))}",
        "",
        "| Role | Psychological Framework | Constructs | Rule Grounding |",
        "|---|---|---|---|",
    ]
    for role, info in (b.get("roles") or {}).items():
        lines.append(
            f"| `{role}` | {_fmt(info.get('psychological_framework'))} | "
            f"{_fmt(info.get('constructs'))} | {_fmt(info.get('rule_grounding_counts'))} |"
        )
    if not (b.get("roles") or {}):
        lines.append("| (none) | unobserved | unobserved | unobserved |")

    dp = b.get("dual_process_memory") or {}
    lines.extend([
        "",
        f"- Memory Engine: {_fmt(dp.get('engine_type'))}",
        f"- Memory Config: {_fmt(dp.get('memory_config'))}",
        f"- Observed Cognitive Modes (System 1 / 2): {_fmt(dp.get('observed_cognitive_modes'))}",
        f"- Mean Surprise: {_fmt(dp.get('mean_surprise'))}",
        f"- Appraisal Drift / Relabeled: drift={_fmt(dp.get('appraisal_drift_count'))}, relabeled={_fmt(dp.get('appraisal_relabeled_count'))}",
        f"- Memory Writes by Origin: {_fmt(dp.get('memory_writes_by_origin'))} (rows={_fmt(dp.get('memory_log_rows'))})",
        f"- Reflection Settings: {_fmt(dp.get('reflection_settings'))} (entries={_fmt(dp.get('reflection_log_rows'))})",
        "",
        "## Block C — LLM Specification, Prompts & Parsing",
        "",
        f"- Model: {_fmt(c.get('model'))} (digest={_fmt(c.get('model_digest'))})",
        f"- Thinking Mode: {_fmt(c.get('thinking_mode'))}",
        f"- LLM Parameters ({_fmt(c.get('llm_parameters_source'))}): {_fmt(c.get('llm_parameters'))}",
        f"- Parse Layer Distribution: {_fmt(c.get('parse_layer_distribution'))}",
        "",
        "| Role | Decider | Model | LLM Params | Prompt SHA-256 | Placeholders | Actions |",
        "|---|---|---|---|---|---|---|",
    ])
    for role, info in (c.get("roles") or {}).items():
        sha_short = (
            info["prompt_sha256"][:12] + "..."
            if isinstance(info.get("prompt_sha256"), str)
            else "unobserved"
        )
        lines.append(
            f"| `{role}` | {_fmt(info.get('decider_type'))} | {_fmt(info.get('model'))} | "
            f"{_fmt(info.get('llm_params'))} | `{sha_short}` | "
            f"{_fmt(info.get('prompt_placeholders'))} | {_fmt(info.get('action_ids'))} |"
        )
    if not (c.get("roles") or {}):
        lines.append("| (none) | unobserved | unobserved | unobserved | unobserved | unobserved | unobserved |")

    inv7 = d.get("invariant_7_isolation") or {}
    causal = (d.get("coordination_and_social_kg") or {}).get("causal_join_keys") or {}
    lines.extend([
        "",
        "## Block D — Governance, Coupling & Social Transmission",
        "",
        f"- Governance Profile: {_fmt(d.get('governance_profile'))}",
        f"- Max Retries / Feedback Mode: max_retries={_fmt(d.get('max_retries'))}, mode={_fmt(d.get('retry_feedback_mode'))}",
        f"- Governance Summary: {_fmt(d.get('governance_summary'))}",
        f"- Invariant 7 Carryover OK: {_fmt(inv7.get('governance_carryover_ok'))} (styles={_fmt(inv7.get('rejection_line_style'))})",
        f"- Coupling Contract: {_fmt(d.get('coupling'))}",
        f"- Causal Join Keys: {_fmt(causal)}",
        "",
        "## Block E — Reproducibility, Hindcast Verification & Integrity",
        "",
        f"- Seed: {_fmt(e.get('seed'))}",
        f"- Git Commit / Dirty: commit={_fmt(e.get('git_commit'))}, dirty={_fmt(e.get('git_dirty'))}",
        f"- Runtime Environment: Python={_fmt(e.get('python_version'))}, Platform={_fmt(e.get('platform'))}",
        f"- Config Source: {_fmt(e.get('config_source'))}",
        f"- Integrity OK: {_fmt(e.get('integrity_ok'))}",
        f"- Coverage Summary: {_fmt(e.get('coverage_summary'))}",
        f"- Leakage Scan: {_fmt(e.get('leakage_scan'))}",
        f"- Exogenous Schedule: {_fmt(e.get('exogenous_schedule'))}",
        f"- Hindcast Verification: {_fmt(e.get('hindcast_verification'))}",
        "",
        "## Unobserved Fields (Invariant 2)",
        "",
    ])
    for item in report.get("unobserved_fields") or []:
        lines.append(f"- `{item}`")
    if not report.get("unobserved_fields"):
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def write_odd_llm_bundle(
    run_dir: Path,
    *,
    config_path: Optional[Path] = None,
    hindcast_metrics_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    json_name: str = "odd_llm.json",
    md_name: str = "ODD_LLM.md",
) -> Tuple[Path, Path, Dict[str, Any]]:
    """Build Blocks A-E ODD-LLM report and write JSON and Markdown outputs."""
    report = build_odd_llm_report(
        run_dir,
        config_path=config_path,
        hindcast_metrics_path=hindcast_metrics_path,
    )
    target_dir = Path(output_dir) if output_dir is not None else Path(run_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    json_path = target_dir / json_name
    md_path = target_dir / md_name
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_odd_llm_markdown(report), encoding="utf-8")
    return json_path, md_path, report


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m broker.tools.export_odd_llm",
        description="Export Blocks A-E ODD-LLM documentation (odd_llm.json + ODD_LLM.md) from a WAGF run directory.",
    )
    parser.add_argument("run_dir", help="Completed or partial WAGF output directory")
    parser.add_argument("--config", help="Optional explicit agent_types.yaml path")
    parser.add_argument("--hindcast-json", help="Optional hindcast verification metrics JSON file")
    parser.add_argument("--output-dir", help="Optional destination directory (defaults to run_dir)")
    parser.add_argument("--json-name", default="odd_llm.json", help="Output JSON filename")
    parser.add_argument("--md-name", default="ODD_LLM.md", help="Output Markdown filename")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        json_path, md_path, report = write_odd_llm_bundle(
            Path(args.run_dir),
            config_path=Path(args.config) if args.config else None,
            hindcast_metrics_path=Path(args.hindcast_json) if args.hindcast_json else None,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            json_name=args.json_name,
            md_name=args.md_name,
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"export_odd_llm: {exc}", file=sys.stderr)
        return 2
    print(f"export_odd_llm: wrote {json_path} and {md_path} ({len(report['unobserved_fields'])} unobserved field(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
