from datetime import datetime
from dataclasses import dataclass
import json
import csv
import os
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Iterable, Tuple
from broker.utils.logging import setup_logger

logger = setup_logger(__name__)


AUDIT_SCHEMA_VERSION = "1"  # bump when the CSV priority-key set changes


def _git_commit_short() -> str:
    """Short git hash of the working tree, or 'unavailable'.

    Mirrors experiment_runner._collect_reproducibility_metadata git logic;
    duplicated (not imported) to keep audit.py free of a core->core import
    cycle.
    """
    try:
        import subprocess

        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
        return out[:12] or "unavailable"
    except Exception:
        return "unavailable"


def _framework_version() -> str:
    try:
        from broker import __version__

        return __version__
    except Exception:
        try:
            from importlib.metadata import version

            return version("broker")
        except Exception:
            return "unknown"


def audit_run_metadata() -> dict:
    """The version stamp embedded in audit_summary.json and JSONL metadata."""
    return {
        "framework_version": _framework_version(),
        "audit_schema_version": AUDIT_SCHEMA_VERSION,
        "git_commit_short": _git_commit_short(),
    }


# -----------------------------------------------------------------------------
# Framework invariant enforcement — see broker/INVARIANTS.md (Invariant 2).
#
# Columns listed here carry semantic signals from the memory / cognitive /
# social pipelines. If ANY of them shows a single constant value across an
# entire experiment, the most likely cause is a pipeline leak where the
# upstream dict was never populated and the audit wrote a default placeholder
# masquerading as real data (as happened on 2026-04-19 NW flood runs).
#
# The minimum row count threshold avoids false positives on tiny sanity runs.
# -----------------------------------------------------------------------------

# Columns whose constancy is suspicious (and the placeholder value they tend
# to silently degrade to). Empty-string / False / 0.0 constants below are the
# ones that should have triggered an alarm in the 2026-04-19 post-mortem.
_SUSPICIOUS_COLUMN_DEFAULTS: Dict[str, Tuple[Any, ...]] = {
    # Memory pipeline — see INVARIANTS.md Invariant 1 + 2
    "mem_top_emotion": ("neutral", ""),
    "mem_top_source": ("personal", ""),
    "mem_surprise": (0.0, 0),
    "mem_cognitive_system": ("",),
    # Cognitive module — dormant in V1, should fire WARNING until V2 lands
    "cog_is_novel_state": (False,),
    "cog_surprise_value": (0.0, 0),
    "cog_margin_to_switch": (0.0, 0),
    "cog_system_mode": ("",),
    # Social pipeline — quieter but same failure pattern is possible
    "social_gossip_count": (0,),
    "social_network_density": (0.0, 0),
}

_SENTINEL_MIN_ROWS = 50  # fewer than this → skip (tiny sanity runs)


def detect_audit_sentinels(
    rows: Iterable[Dict[str, Any]],
    columns: Optional[Dict[str, Tuple[Any, ...]]] = None,
    min_rows: int = _SENTINEL_MIN_ROWS,
) -> List[str]:
    """Scan audit rows for columns that appear to be silently masking absent data.

    Returns a list of human-readable warning strings, ONE per suspect column.
    Empty list means no suspects found. Safe to call on any list of audit
    dicts (from live run OR post-hoc CSV re-read).

    A column is flagged when:
        (a) we have at least ``min_rows`` observations, AND
        (b) every row has the same value, AND
        (c) that value matches a known placeholder default.

    This function intentionally does NOT raise — callers decide whether a
    warning is a hard-fail (CI test) or soft-warn (production finalize).
    """
    columns_map = columns or _SUSPICIOUS_COLUMN_DEFAULTS
    rows_list = list(rows)
    if len(rows_list) < min_rows:
        return []

    warnings: List[str] = []
    for column, placeholders in columns_map.items():
        values = {row.get(column) for row in rows_list if column in row}
        if not values:
            continue
        if len(values) == 1:
            only_value = next(iter(values))
            if only_value in placeholders:
                warnings.append(
                    f"[AuditInvariant] Column '{column}' is constant "
                    f"({only_value!r}) across {len(rows_list)} rows — likely "
                    f"pipeline leak (upstream never populated, audit wrote "
                    f"placeholder default). See broker/INVARIANTS.md Invariant 2."
                )
    return warnings


def detect_audit_sentinels_in_csv(csv_path: str, min_rows: int = _SENTINEL_MIN_ROWS) -> List[str]:
    """Convenience wrapper: read a *.csv and run detect_audit_sentinels on its rows.

    Usage: post-hoc triage of an experiment CSV to see if it matches the
    2026-04-19 failure pattern. Requires pandas if available, falls back to
    csv.DictReader.
    """
    try:
        import pandas as pd  # type: ignore

        df = pd.read_csv(csv_path, encoding="utf-8-sig")
        rows = df.to_dict(orient="records")
    except Exception:
        with open(csv_path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
    return detect_audit_sentinels(rows, min_rows=min_rows)


@dataclass
class AuditConfig:
    """Configuration for audit writing."""
    output_dir: str
    experiment_name: str = "simulation"
    log_level: str = "full"  # full, summary, errors_only
    clear_existing_traces: bool = True


_CONSTRUCT_SUFFIXES = ("_LABEL", "_UTIL", "_GAP", "_IMPACT", "_APPETITE")


def _sanitize_text(val: Any) -> Any:
    """Sanitize text for CSV compatibility (strip newlines)."""
    if not isinstance(val, str):
        return val
    return val.replace('\n', ' ').replace('\r', ' ').strip()


def trace_to_csv_row(t: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a single audit trace dict to a flat CSV row dict.

    Extracted as a module-level function (Phase 6G, 2026-05-15) so the
    `broker.tools.recover_csv_from_jsonl` CLI can reuse the exact same
    row schema as the live audit writer's `_export_csv` method. Single
    source of truth for trace → row mapping.
    """
    # 1. Base identity and timing
    row = {
        "step_id": t.get("step_id"),
        "year": t.get("year"),
        "timestamp": t.get("timestamp"),
        "agent_id": t.get("agent_id"),
        "status": (t.get("approved_skill") or {}).get("status", "UNKNOWN"),
        "retry_count": t.get("retry_count", 0),
        "validated": t.get("validated", True),
    }

    # 1.5. LLM-level retry info (for empty response tracking)
    llm_stats = t.get("llm_stats") or {}
    row["llm_retries"] = llm_stats.get("llm_retries", t.get("llm_retries", 0))
    row["llm_success"] = llm_stats.get("llm_success", t.get("llm_success", True))

    # 1.5b. R5-C: Token monitoring
    row["prompt_tokens"] = llm_stats.get("prompt_tokens", 0)
    row["response_tokens"] = llm_stats.get("response_tokens", 0)
    row["num_ctx"] = llm_stats.get("num_ctx", 0)
    row["context_utilization"] = llm_stats.get("context_utilization", 0.0)

    # 1.6. Structural fault tracking (format/parsing issues fixed by retry)
    row["format_retries"] = t.get("format_retries", 0)

    # 2. Skill Logic (Proposed vs Approved)
    skill_prop = t.get("skill_proposal") or {}
    appr_skill = t.get("approved_skill") or {}
    row["proposed_skill"] = skill_prop.get("skill_name")
    row["final_skill"] = appr_skill.get("skill_name")
    row["parsing_warnings"] = "|".join(skill_prop.get("parsing_warnings", []) or [])
    row["raw_output"] = skill_prop.get("raw_output", t.get("raw_output", ""))

    # 2.5. Parse Quality Metrics (Task-040 C4)
    row["parse_layer"] = skill_prop.get("parse_layer", "")
    row["parse_confidence"] = skill_prop.get("parse_confidence", 0.0)
    row["construct_completeness"] = skill_prop.get("construct_completeness", 0.0)

    # 2.6. Fallback Indicator (Task-040 C.1 + Phase 6G 2026-05-15 fix).
    # Source of truth for fallback is the trace's top-level `fallback_activated`
    # field (set by retry_loop on REJECTED_FALLBACK termination); we only fall
    # back to status-string inference when the field is absent (older traces).
    if "fallback_activated" in t:
        row["fallback_activated"] = bool(t["fallback_activated"])
    else:
        status_value = row["status"]
        row["fallback_activated"] = status_value in (
            "FALLBACK", "fallback", "MODIFIED", "REJECTED_FALLBACK"
        )

    # 3. Reasoning (TP/CP Appraisal + Audits)
    reasoning = skill_prop.get("reasoning", {})
    if isinstance(reasoning, dict):
        for k, v in reasoning.items():
            if k == "demographic_audit" and isinstance(v, dict):
                # Flatten Demographic Audit (Phase 21)
                row["demo_score"] = v.get("score", 0.0)
                row["demo_anchors"] = "|".join(v.get("cited_anchors", []))
            elif k.lower() == "appraisal":
                 # PROMOTE Appraisal to top level for CSV visibility
                 row["appraisal"] = v
            else:
                row[f"reason_{k.lower()}"] = v
    else:
        row["reason_text"] = str(reasoning)

    # 4. Validation Details (Which rule triggered)
    issues = t.get("validation_issues", [])
    if issues:
        row["failed_rules"] = "|".join([str(i.get('rule_id', 'Unknown')) for i in issues])
        row["error_messages"] = "|".join(["; ".join(i.get('errors', [])) for i in issues])
    else:
        row["failed_rules"] = ""
        row["error_messages"] = ""

    # 4b. Warning Details (Non-blocking governance observations)
    warnings_list = t.get("validation_warnings_list", [])
    if warnings_list:
        row["warning_rules"] = "|".join([str(w.get('rule_id', 'Unknown')) for w in warnings_list])
        row["warning_messages"] = "|".join(["; ".join(w.get('warnings', [])) for w in warnings_list])
    else:
        row["warning_rules"] = ""
        row["warning_messages"] = ""

    # 4c. Shadow-blocked rules (W5: would-block under active mode,
    # recorded non-blocking under shadow mode)
    shadow_list = t.get("shadow_blocked", [])
    if shadow_list:
        row["shadow_blocked"] = "|".join([str(s.get('rule_id', 'Unknown')) for s in shadow_list])
    else:
        row["shadow_blocked"] = ""

    # 5. Memory Audit (E1) - Memory retrieval details
    mem_audit = t.get("memory_audit", {})
    if mem_audit:
        row["mem_retrieved_count"] = mem_audit.get("retrieved_count", 0)
        row["mem_cognitive_system"] = mem_audit.get("cognitive_system", "")
        row["mem_surprise"] = mem_audit.get("surprise_value", 0.0)
        row["mem_retrieval_mode"] = mem_audit.get("retrieval_mode", "")
        memories = mem_audit.get("memories", [])
        if memories:
            emotions = [m.get("emotion", "neutral") for m in memories if isinstance(m, dict)]
            sources = [m.get("source", "personal") for m in memories if isinstance(m, dict)]
            row["mem_top_emotion"] = max(set(emotions), key=emotions.count) if emotions else ""
            row["mem_top_source"] = max(set(sources), key=sources.count) if sources else ""
        else:
            row["mem_top_emotion"] = ""
            row["mem_top_source"] = ""
    else:
        row["mem_retrieved_count"] = 0
        row["mem_cognitive_system"] = ""
        row["mem_surprise"] = 0.0
        row["mem_retrieval_mode"] = ""
        row["mem_top_emotion"] = ""
        row["mem_top_source"] = ""

    # 6. Social Audit (E2) - Social context details.
    # Phase 6N-A (2026-05-23): `visible_actions` is a dict whose keys come
    # from the domain's social context provider — each domain supplies
    # whatever ``<skill>_neighbors`` count it wants to surface. Iterate
    # the dict instead of hardcoding skill names so the audit writer
    # stays domain-neutral. Downstream column names are still
    # ``social_<key>``; existing per-domain CSVs reproduce byte-identical
    # because each domain still emits the same dict keys it did before.
    # Broker-owned column names (must NOT be reused as visible_actions
    # dict keys by domains): ``gossip_count`` / ``neighbor_count`` /
    # ``network_density``. The loop runs AFTER the broker-owned writes
    # so a domain that accidentally collides on these key names cannot
    # silently overwrite them.
    social_audit = t.get("social_audit", {})
    if social_audit:
        row["social_gossip_count"] = len(social_audit.get("gossip_received", []))
        row["social_neighbor_count"] = social_audit.get("neighbor_count", 0)
        row["social_network_density"] = social_audit.get("network_density", 0.0)
        visible = social_audit.get("visible_actions", {})
        for vkey, vval in visible.items():
            row[f"social_{vkey}"] = vval
    else:
        row["social_gossip_count"] = 0
        row["social_neighbor_count"] = 0
        row["social_network_density"] = 0.0

    # 7. Cognitive Audit (E3) - Cognitive state details
    cog_audit = t.get("cognitive_audit", {})
    if cog_audit:
        row["cog_system_mode"] = cog_audit.get("system_mode", "")
        row["cog_surprise_value"] = cog_audit.get("surprise", 0.0)
        row["cog_is_novel_state"] = cog_audit.get("is_novel_state", False)
        row["cog_margin_to_switch"] = cog_audit.get("margin_to_switch", 0.0)
    else:
        row["cog_system_mode"] = ""
        row["cog_surprise_value"] = 0.0
        row["cog_is_novel_state"] = False
        row["cog_margin_to_switch"] = 0.0

    # 8. Rule Breakdown (B.5) - Rules hit by category
    rule_breakdown = t.get("rule_breakdown", {})
    row["rules_personal_hit"] = rule_breakdown.get("personal", 0)
    row["rules_social_hit"] = rule_breakdown.get("social", 0)
    row["rules_thinking_hit"] = rule_breakdown.get("thinking", 0)
    row["rules_physical_hit"] = rule_breakdown.get("physical", 0)
    row["rules_semantic_hit"] = rule_breakdown.get("semantic", 0)

    # 8b. Hallucination type from validation issues
    hall_types = [i.get("hallucination_type") for i in issues if i.get("hallucination_type")]
    row["hallucination_types"] = "|".join(hall_types) if hall_types else ""

    # 9. Construct Tracking — dynamic extraction from reasoning dict.
    reasoning_dict = skill_prop.get("reasoning", {}) if isinstance(skill_prop.get("reasoning"), dict) else {}
    for key, val in reasoning_dict.items():
        if any(key.endswith(suffix) for suffix in _CONSTRUCT_SUFFIXES):
            row[f"construct_{key}"] = val

    # 10. Rule Evaluation Details (Task-041 Phase 3)
    rules_evaluated = t.get("rules_evaluated", [])
    triggered_rules = t.get("triggered_rules", [])
    row["rules_evaluated_count"] = len(rules_evaluated) if rules_evaluated else 0
    row["rules_triggered"] = "|".join(triggered_rules) if triggered_rules else ""

    # Condition match details (first 3 for CSV)
    condition_results = t.get("condition_results", [])
    for i in range(3):
        if i < len(condition_results):
            cond_result = condition_results[i]
            row[f"condition_{i}_rule"] = cond_result.get("rule_id", "")
            row[f"condition_{i}_matched"] = cond_result.get("matched", False)
        else:
            row[f"condition_{i}_rule"] = ""
            row[f"condition_{i}_matched"] = ""

    return {k: _sanitize_text(v) for k, v in row.items()}


def compute_csv_fieldnames(rows: List[Dict[str, Any]],
                           audit_priority: Optional[List[str]] = None) -> List[str]:
    """Compute priority-ordered fieldname list given a batch of row dicts.

    Mirrors the column ordering logic in GenericAuditWriter._export_csv so
    crash-recovered CSVs match live-written CSVs column-for-column.
    """
    if not rows:
        return []
    all_keys_set: set = set().union(*(d.keys() for d in rows))
    construct_cols = sorted(
        k for k in all_keys_set
        if k.startswith("construct_") and k != "construct_completeness"
    )

    priority_keys = [
        "step_id", "year", "agent_id",
        "proposed_skill", "final_skill", "status", "fallback_activated",
        "retry_count", "format_retries", "validated", "failed_rules", "shadow_blocked",
        "parse_layer", "parse_confidence", "construct_completeness",
        *construct_cols,
        "rules_evaluated_count", "rules_triggered",
        "mem_retrieved_count", "mem_cognitive_system", "mem_surprise",
        "social_gossip_count", "social_neighbor_count",
        "cog_system_mode", "cog_surprise_value", "cog_is_novel_state",
        "rules_personal_hit", "rules_social_hit", "rules_thinking_hit",
        "rules_physical_hit", "rules_semantic_hit", "hallucination_types",
    ]
    if audit_priority and isinstance(audit_priority, list):
        priority_keys = ["step_id", "agent_id"] + audit_priority + [
            k for k in priority_keys
            if k not in ["step_id", "agent_id"] + audit_priority
        ]
    return priority_keys + [k for k in sorted(list(all_keys_set)) if k not in priority_keys]


class GenericAuditWriter:
    """
    Generic audit writer for any agent type.
    
    Uses Dict-based traces instead of typed dataclasses.
    Automatically creates per-agent-type files.
    """
    
    def __init__(self, config: AuditConfig):
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if config.clear_existing_traces:
            raw_dir = self.output_dir / "raw"
            if raw_dir.exists():
                for trace_file in raw_dir.glob("*_traces.jsonl"):
                    try:
                        trace_file.unlink()
                    except OSError as e:
                        logger.warning(f"[Audit] Could not clear trace file {trace_file}: {e}")
        
        # Track file handles per agent type
        self._files: Dict[str, Path] = {}
        self._run_metadata = audit_run_metadata()
        
        # Summary stats per agent type
        self.summary = {
            "experiment_name": config.experiment_name,
            **self._run_metadata,
            "agent_types": {},
            "total_traces": 0,
            "validation_errors": 0,
            "validation_warnings": 0,
            "structural_faults_fixed": 0,  # Format issues fixed by retry
            "total_format_retries": 0,     # Total format retry attempts
            "validator_health": {},
            # F2 fix (post-Phase-6T silent-failure audit, 2026-05-27):
            # count of JSONL events lost to terminal flush failure
            # (max retries exhausted). Pre-fix the buffer was NOT
            # cleared on final failure, causing the events to be
            # re-appended on the next flush → duplicate JSONL lines
            # that inflate IBR + decision counts. Fix: discard buffer
            # on final failure (data loss is detectable;
            # data duplication is not) + emit this counter so
            # downstream consumers can detect partial runs.
            "jsonl_events_lost": 0,
        }
        
        # Buffer for CSV export
        self._trace_buffer: Dict[str, List[Dict[str, Any]]] = {}
        
        # Buffer for JSONL writes (Performance Optimization)
        self._jsonl_buffer: Dict[str, List[str]] = {}
        self._jsonl_buffer_size = 1  # Flush every trace for real-time observability
        self._write_lock = threading.Lock()  # Thread safety for workers > 1

        # Track which aggregate dict keys have been observed across all traces
        # so we can emit a one-time WARNING at first-trace time if any are
        # absent (they would otherwise silently degrade to hardcoded defaults
        # — see INVARIANTS.md Invariant 2 and the 2026-04-19 NW flood
        # post-mortem).
        self._expected_aggregates: Dict[str, str] = {
            "memory_audit":    "mem_* columns (retrieved_count, top_emotion, etc.)",
            "social_audit":    "social_* columns (gossip, neighbor_count, etc.)",
            "cognitive_audit": "cog_* columns (surprise, novel_state, etc.)",
            "rule_breakdown":  "rules_* columns (personal_hit, social_hit, etc.)",
        }
        self._startup_warned: bool = False

    def _get_file_path(self, agent_type: str) -> Path:
        """Get or create file path for agent type (JSONL traces in raw/ subdir)."""
        if agent_type not in self._files:
            raw_dir = self.output_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            self._files[agent_type] = raw_dir / f"{agent_type}_traces.jsonl"
        return self._files[agent_type]
    
    def write_trace(
        self,
        agent_type: str,
        trace: Dict[str, Any],
        validation_results: Optional[List] = None
    ) -> None:
        """Write a generic trace for any agent type."""
        # Framework invariant check — on first trace, warn once if any
        # expected aggregate dict key is absent (would cause silent
        # degradation to hardcoded column defaults). See INVARIANTS.md §2.
        if not self._startup_warned:
            absent = [
                f"'{key}' (would populate: {cols})"
                for key, cols in self._expected_aggregates.items()
                if key not in trace
            ]
            if absent:
                logger.warning(
                    f"[AuditInvariant] First trace for '{agent_type}' is "
                    f"missing upstream aggregate dict(s): {absent}. CSV "
                    f"columns derived from these keys will carry hardcoded "
                    f"default placeholders. See broker/INVARIANTS.md §2 "
                    f"and _RESERVED_DICT_KEYS in framework invariant tests."
                )
            self._startup_warned = True

        # Ensure required fields
        trace.setdefault("timestamp", datetime.now().isoformat())
        trace.setdefault("agent_type", agent_type)
        
        # Add basic validation info if provided
        if validation_results:
            # Respect existing 'validated' flag if already set by broker (e.g. final attempt status)
            if "validated" not in trace:
                trace["validated"] = all(r.valid for r in validation_results)
            
            trace["validation_issues"] = []
            seen_issues = set()

            trace["shadow_blocked"] = []
            seen_shadow = set()

            trace["validation_warnings_list"] = []
            seen_warnings = set()

            for r in validation_results:
                metadata = getattr(r, "metadata", None) or {}
                rid = metadata.get("rule_id")
                if (
                    not rid
                    and r.valid
                    and not getattr(r, "warnings", None)
                    and not metadata.get("shadow_blocked")
                ):
                    continue
                rid = rid or "Unknown"
                vh = self.summary["validator_health"].setdefault(rid, {
                    "rule_id": rid, "seen_count": 0, "fire_count": 0,
                    "warn_count": 0, "error_path_count": 0,
                })
                vh["seen_count"] += 1
                if not r.valid:
                    vh["fire_count"] += 1
                elif getattr(r, "warnings", None):
                    vh["warn_count"] += 1
                if metadata.get("error_path"):
                    vh["error_path_count"] += 1
                _at = agent_type if agent_type else trace.get("agent_type", "Unknown")
                _vbt = self.__dict__.setdefault("_validator_health_by_type", {})
                vht = _vbt.setdefault(_at, {}).setdefault(rid, {
                    "agent_type": _at, "rule_id": rid, "seen_count": 0,
                    "fire_count": 0, "warn_count": 0, "error_path_count": 0,
                })
                vht["seen_count"] += 1
                if not r.valid:
                    vht["fire_count"] += 1
                elif getattr(r, "warnings", None):
                    vht["warn_count"] += 1
                if metadata.get("error_path"):
                    vht["error_path_count"] += 1

                if metadata.get("shadow_blocked"):
                    for rid in metadata["shadow_blocked"]:
                        if rid not in seen_shadow:
                            trace["shadow_blocked"].append({
                                "rule_id": rid,
                                "validator": getattr(r, 'validator_name', 'Unknown'),
                                "would_block_level": metadata.get("would_block_level", "ERROR"),
                            })
                            seen_shadow.add(rid)

                if not r.valid:
                    self.summary["validation_errors"] += 1
                    issue_key = (rid, tuple(r.errors))
                    if issue_key not in seen_issues:
                        issue = {
                            "validator": getattr(r, 'validator_name', 'Unknown'),
                            "rule_id": rid,
                            "errors": r.errors
                        }
                        if metadata.get("hallucination_type"):
                            issue["hallucination_type"] = metadata["hallucination_type"]
                        trace["validation_issues"].append(issue)
                        seen_issues.add(issue_key)
                elif r.valid and hasattr(r, 'warnings') and r.warnings:
                    self.summary["validation_warnings"] += 1
                    warn_key = (rid, tuple(r.warnings))
                    if warn_key not in seen_warnings:
                        trace["validation_warnings_list"].append({
                            "validator": getattr(r, 'validator_name', 'Unknown'),
                            "rule_id": rid,
                            "warnings": r.warnings
                        })
                        seen_warnings.add(warn_key)
        else:
            trace["validated"] = True
            trace["validation_issues"] = []
            trace["shadow_blocked"] = []
            trace["validation_warnings_list"] = []

        
        # Update summary
        self.summary["total_traces"] += 1
        if agent_type not in self.summary["agent_types"]:
            self.summary["agent_types"][agent_type] = {
                "total": 0,
                "decisions": {}
            }
        self.summary["agent_types"][agent_type]["total"] += 1
        
        # Track decision
        decision = trace.get("decision", trace.get("approved_skill", {}).get("skill_name", "unknown"))
        decisions = self.summary["agent_types"][agent_type]["decisions"]
        decisions[decision] = decisions.get(decision, 0) + 1

        # Track structural faults (format retries)
        format_retries = trace.get("format_retries", 0)
        if format_retries > 0:
            self.summary["total_format_retries"] += format_retries
            self.summary["structural_faults_fixed"] += 1  # Count traces with faults fixed

        # Buffered JSONL write (Optimized: flush every N traces)
        # Truncate raw_output in JSONL to reduce file size; CSV retains full version
        file_path = self._get_file_path(agent_type)
        jsonl_trace = trace
        raw = trace.get('raw_output')
        if isinstance(raw, str) and len(raw) > 500:
            jsonl_trace = {**trace, 'raw_output': raw[:500] + '...[truncated]'}
        json_line = json.dumps(jsonl_trace, ensure_ascii=False, default=str) + '\n'
        
        with self._write_lock:
            if agent_type not in self._jsonl_buffer:
                self._jsonl_buffer[agent_type] = []
                metadata_record = {
                    "_metadata": dict(self._run_metadata),
                    "agent_type": agent_type,
                }
                metadata_line = json.dumps(
                    metadata_record, ensure_ascii=False, default=str
                ) + '\n'
                self._jsonl_buffer[agent_type].append(metadata_line)
            self._jsonl_buffer[agent_type].append(json_line)

            # Flush buffer when threshold reached
            if len(self._jsonl_buffer[agent_type]) >= self._jsonl_buffer_size:
                self._flush_jsonl_buffer(agent_type, file_path)

            # Buffer for CSV
            if agent_type not in self._trace_buffer:
                self._trace_buffer[agent_type] = []
            self._trace_buffer[agent_type].append(trace)
    
    def finalize(self) -> Dict[str, Any]:
        """Write summary and export CSVs."""
        self.summary["finalized_at"] = datetime.now().isoformat()
        
        # Flush remaining JSONL buffers before closing
        with self._write_lock:
            for agent_type in list(self._jsonl_buffer.keys()):
                file_path = self._get_file_path(agent_type)
                self._flush_jsonl_buffer(agent_type, file_path)
        
        # Export summary JSON
        summary_path = self.output_dir / "audit_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(self.summary, f, indent=2, ensure_ascii=False)

        vh = self.summary.get("validator_health", {})
        if vh:
            import csv as _csv
            vh_path = self.output_dir / "validator_health.csv"
            cols = ["rule_id", "seen_count", "fire_count", "warn_count",
                    "error_path_count", "fire_rate"]
            with open(vh_path, "w", newline="", encoding="utf-8-sig") as f:
                w = _csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
                w.writeheader()
                for rid in sorted(vh):
                    row = dict(vh[rid])
                    seen = row.get("seen_count", 0) or 0
                    row["fire_rate"] = round(row.get("fire_count", 0) / seen, 4) if seen else 0.0
                    w.writerow(row)
            logger.info(f"[Audit] Validator health: {vh_path}")
        vht_all = getattr(self, "_validator_health_by_type", {})
        if vht_all:
            import csv as _csv2
            _recs = [rec for _inner in vht_all.values() for rec in _inner.values()]
            _rule_fire = {}
            for _rec in _recs:
                _agg = _rule_fire.setdefault(_rec["rule_id"], {"seen": 0, "fire": 0})
                _agg["seen"] += _rec.get("seen_count", 0)
                _agg["fire"] += _rec.get("fire_count", 0)
            vht_path = self.output_dir / "validator_health_by_agent_type.csv"
            cols2 = ["agent_type", "rule_id", "seen_count", "fire_count",
                     "warn_count", "error_path_count", "fire_rate", "dead_for_all"]
            with open(vht_path, "w", newline="", encoding="utf-8-sig") as f:
                w2 = _csv2.DictWriter(f, fieldnames=cols2, extrasaction="ignore")
                w2.writeheader()
                for rec in sorted(_recs, key=lambda r: (str(r.get("agent_type")), str(r.get("rule_id")))):
                    rec = dict(rec)
                    seen = rec.get("seen_count", 0) or 0
                    rec["fire_rate"] = round(rec.get("fire_count", 0) / seen, 4) if seen else 0.0
                    g = _rule_fire.get(rec["rule_id"], {"seen": 0, "fire": 0})
                    rec["dead_for_all"] = bool(g["seen"] > 0 and g["fire"] == 0)
                    w2.writerow(rec)
            logger.info(f"[Audit] Validator health (per-agent-type): {vht_path}")
            for _rid, g in sorted(_rule_fire.items()):
                if g["seen"] > 0 and g["fire"] == 0:
                    logger.warning(
                        f"[Audit] DEAD VALIDATOR: rule '{_rid}' never fired "
                        f"across {g['seen']} decisions (possible inert/misconfigured rule)"
                    )
                elif g["fire"] > 0:
                    _inactive = sorted(
                        str(r.get("agent_type")) for r in _recs
                        if r.get("rule_id") == _rid and r.get("seen_count", 0) > 0
                        and r.get("fire_count", 0) == 0
                    )
                    if _inactive:
                        logger.info(
                            f"[Audit] rule '{_rid}' inactive for agent-type(s) "
                            f"{_inactive} (active elsewhere - likely scope-expected)"
                        )
        
        # Export CSVs
        for agent_type, traces in self._trace_buffer.items():
            self._export_csv(agent_type, traces)

        # Framework invariant check — see broker/INVARIANTS.md Invariant 2.
        # Warn (not raise) if any semantic signal column is silently constant,
        # which is the 2026-04-19 NW flood failure pattern.
        for agent_type, traces in self._trace_buffer.items():
            warnings_found = detect_audit_sentinels(traces)
            for warning in warnings_found:
                logger.warning(f"[Audit:{agent_type}] {warning}")

        logger.info(f"[Audit] Finalized. Summary: {summary_path}")
        return self.summary
    
    def _flush_jsonl_buffer(self, agent_type: str, file_path: Path) -> None:
        """Flush buffered JSONL lines to disk + fsync.

        Phase 6G crash-resistance fix (2026-05-15): explicit os.fsync after
        each flush so a process crash mid-year cannot lose recent traces in
        the OS page cache. Per-call cost is ~1 ms on SSDs, negligible
        against LLM inference time. Combined with the JSONL-to-CSV recovery
        CLI (`broker.tools.recover_csv_from_jsonl`), this closes the
        2026-05-13/14 14-hour-data-loss failure mode.
        """
        if agent_type not in self._jsonl_buffer or not self._jsonl_buffer[agent_type]:
            return

        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.writelines(self._jsonl_buffer[agent_type])
                    f.flush()
                    os.fsync(f.fileno())
                self._jsonl_buffer[agent_type] = [] # Clear buffer
                break
            except (OSError, IOError) as e:
                if attempt == max_retries - 1:
                    # F2 fix (post-Phase-6T audit, 2026-05-27): pre-fix
                    # path logged the error but did NOT clear the
                    # buffer. The next flush re-appended the same
                    # lines, producing duplicate JSONL rows that
                    # inflate per-agent decision counts (IBR climbs
                    # spuriously) + corrupt
                    # broker.tools.recover_csv_from_jsonl output.
                    # Trade-off: discarding buffer = data loss
                    # (detectable via the lost-event counter below);
                    # keeping = data duplication (undetectable, looks
                    # like real activity). Pick loss — same v0.88.15
                    # lesson family as F1 / F3 in this patch:
                    # detectable data loss > undetectable corruption.
                    lost = len(self._jsonl_buffer[agent_type])
                    logger.error(
                        f" [AuditWriter:Error] Final failure flushing "
                        f"{lost} events to {file_path}: {e}. Discarding "
                        f"buffer to prevent next-flush duplication. "
                        f"Run summary will record jsonl_events_lost += "
                        f"{lost} for downstream detection.",
                        exc_info=True,
                    )
                    self._jsonl_buffer[agent_type] = []
                    self.summary["jsonl_events_lost"] = (
                        self.summary.get("jsonl_events_lost", 0) + lost
                    )
                else:
                    time.sleep(1.0)

    @staticmethod
    def sanitize_text(val: Any) -> Any:
        """Sanitize text for CSV compatibility (remove newlines and problematic characters)."""
        if not isinstance(val, str):
            return val
        # Replace newlines with spaces and escaped commas/quotes if needed
        # Standard CSV writers handle commas/quotes with quoting, but newlines often break row parsing in simple viewers
        return val.replace('\n', ' ').replace('\r', ' ').strip()

    def _export_csv(self, agent_type: str, traces: List[Dict[str, Any]]):
        """Export buffered traces to flat CSV with deep governance fields."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = self.output_dir / f"{agent_type}_governance_audit.csv"
        if not traces: return

        flat_rows = [trace_to_csv_row(t) for t in traces]

        if not flat_rows: return

        # Single source of truth for column ordering — shared with
        # broker.tools.recover_csv_from_jsonl so crash-recovered CSVs are
        # column-identical to live-finalized CSVs.
        audit_priority = None
        if traces and "_audit_priority" in traces[0]:
            cand = traces[0]["_audit_priority"]
            if isinstance(cand, list):
                audit_priority = cand
        fieldnames = compute_csv_fieldnames(flat_rows, audit_priority=audit_priority)

        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore', quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(flat_rows)


# Aliases
AuditWriter = GenericAuditWriter
