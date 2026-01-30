from datetime import datetime
from dataclasses import dataclass
import json
import csv
from pathlib import Path
from typing import Dict, Any, List, Optional
from broker.utils.logging import setup_logger

logger = setup_logger(__name__)


@dataclass
class AuditConfig:
    """Configuration for audit writing."""
    output_dir: str
    experiment_name: str = "simulation"
    log_level: str = "full"  # full, summary, errors_only
    clear_existing_traces: bool = True


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
        
        # Summary stats per agent type
        self.summary = {
            "experiment_name": config.experiment_name,
            "agent_types": {},
            "total_traces": 0,
            "validation_errors": 0,
            "validation_warnings": 0,
            "structural_faults_fixed": 0,  # Format issues fixed by retry
            "total_format_retries": 0      # Total format retry attempts
        }
        
        # Buffer for CSV export
        self._trace_buffer: Dict[str, List[Dict[str, Any]]] = {}
        
        # Buffer for JSONL writes (Performance Optimization)
        self._jsonl_buffer: Dict[str, List[str]] = {}
        self._jsonl_buffer_size = 1 # Flush immediately for visibility during long runs
    
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

            trace["validation_warnings_list"] = []
            seen_warnings = set()

            for r in validation_results:
                if not r.valid:
                    self.summary["validation_errors"] += 1
                    issue_key = (r.metadata.get("rule_id", "Unknown"), tuple(r.errors))
                    if issue_key not in seen_issues:
                        trace["validation_issues"].append({
                            "validator": getattr(r, 'validator_name', 'Unknown'),
                            "rule_id": r.metadata.get("rule_id", "Unknown"),
                            "errors": r.errors
                        })
                        seen_issues.add(issue_key)
                elif r.valid and hasattr(r, 'warnings') and r.warnings:
                    self.summary["validation_warnings"] += 1
                    warn_key = (r.metadata.get("rule_id", "Unknown"), tuple(r.warnings))
                    if warn_key not in seen_warnings:
                        trace["validation_warnings_list"].append({
                            "validator": getattr(r, 'validator_name', 'Unknown'),
                            "rule_id": r.metadata.get("rule_id", "Unknown"),
                            "warnings": r.warnings
                        })
                        seen_warnings.add(warn_key)
        else:
            trace["validated"] = True
            trace["validation_issues"] = []
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
        file_path = self._get_file_path(agent_type)
        json_line = json.dumps(trace, ensure_ascii=False, default=str) + '\n'
        
        if agent_type not in self._jsonl_buffer:
            self._jsonl_buffer[agent_type] = []
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
        for agent_type in list(self._jsonl_buffer.keys()):
            file_path = self._get_file_path(agent_type)
            self._flush_jsonl_buffer(agent_type, file_path)
        
        # Export summary JSON
        summary_path = self.output_dir / "audit_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(self.summary, f, indent=2, ensure_ascii=False)
        
        # Export CSVs
        for agent_type, traces in self._trace_buffer.items():
            self._export_csv(agent_type, traces)
            
        logger.info(f"[Audit] Finalized. Summary: {summary_path}")
        return self.summary
    
    def _flush_jsonl_buffer(self, agent_type: str, file_path: Path) -> None:
        """Flush buffered JSONL lines to disk."""
        if agent_type not in self._jsonl_buffer or not self._jsonl_buffer[agent_type]:
            return
        
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.writelines(self._jsonl_buffer[agent_type])
                self._jsonl_buffer[agent_type] = [] # Clear buffer
                break
            except (OSError, IOError) as e:
                if attempt == max_retries - 1:
                    logger.error(f" [AuditWriter:Error] Final failure flushing buffer to {file_path}: {e}")
                else:
                    time.sleep(1.0)

    def _export_csv(self, agent_type: str, traces: List[Dict[str, Any]]):
        """Export buffered traces to flat CSV with deep governance fields."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = self.output_dir / f"{agent_type}_governance_audit.csv"
        if not traces: return

        flat_rows = []
        for t in traces:
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
            row["llm_retries"] = t.get("llm_retries", 0)
            row["llm_success"] = t.get("llm_success", True)

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

            # 2.6. Fallback Indicator (Task-040 C.1)
            status = row["status"]
            row["fallback_activated"] = status in ("FALLBACK", "fallback", "MODIFIED")
            
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
                # Fallback: if reasoning is a string, check if it contains Appraisal logic
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

            # 5. Memory Audit (E1) - Memory retrieval details
            mem_audit = t.get("memory_audit", {})
            if mem_audit:
                row["mem_retrieved_count"] = mem_audit.get("retrieved_count", 0)
                row["mem_cognitive_system"] = mem_audit.get("cognitive_system", "")
                row["mem_surprise"] = mem_audit.get("surprise_value", 0.0)
                row["mem_retrieval_mode"] = mem_audit.get("retrieval_mode", "")
                # Extract top emotion/source from memories
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

            # 6. Social Audit (E2) - Social context details
            social_audit = t.get("social_audit", {})
            if social_audit:
                row["social_gossip_count"] = len(social_audit.get("gossip_received", []))
                visible = social_audit.get("visible_actions", {})
                row["social_elevated_neighbors"] = visible.get("elevated_neighbors", 0)
                row["social_relocated_neighbors"] = visible.get("relocated_neighbors", 0)
                row["social_neighbor_count"] = social_audit.get("neighbor_count", 0)
                row["social_network_density"] = social_audit.get("network_density", 0.0)
            else:
                row["social_gossip_count"] = 0
                row["social_elevated_neighbors"] = 0
                row["social_relocated_neighbors"] = 0
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

            # 9. Construct Tracking (Task-041 Phase 3) - Individual construct ratings
            # Extract from reasoning dict
            reasoning = skill_prop.get("reasoning", {}) if isinstance(skill_prop.get("reasoning"), dict) else {}
            # PMT constructs
            row["construct_TP_LABEL"] = reasoning.get("TP_LABEL", "")
            row["construct_CP_LABEL"] = reasoning.get("CP_LABEL", "")
            row["construct_SP_LABEL"] = reasoning.get("SP_LABEL", "")
            row["construct_PA_LABEL"] = reasoning.get("PA_LABEL", "")
            row["construct_SC_LABEL"] = reasoning.get("SC_LABEL", "")
            # Utility constructs
            row["construct_BUDGET_UTIL"] = reasoning.get("BUDGET_UTIL", "")
            row["construct_EQUITY_GAP"] = reasoning.get("EQUITY_GAP", "")
            # Financial constructs
            row["construct_RISK_APPETITE"] = reasoning.get("RISK_APPETITE", "")
            row["construct_SOLVENCY_IMPACT"] = reasoning.get("SOLVENCY_IMPACT", "")

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

            flat_rows.append(row)

        if not flat_rows: return

        # Ensure consistent column ordering for user
        priority_keys = [
            # Core identity
            "step_id", "year", "agent_id",
            # Skill decision
            "proposed_skill", "final_skill", "status", "fallback_activated",
            # Governance stats
            "retry_count", "format_retries", "validated", "failed_rules",
            # Parse quality
            "parse_layer", "parse_confidence", "construct_completeness",
            # Construct ratings (Task-041 Phase 3)
            "construct_TP_LABEL", "construct_CP_LABEL", "construct_SP_LABEL",
            "construct_PA_LABEL", "construct_SC_LABEL",
            "construct_BUDGET_UTIL", "construct_EQUITY_GAP",
            "construct_RISK_APPETITE", "construct_SOLVENCY_IMPACT",
            # Rule evaluation (Task-041 Phase 3)
            "rules_evaluated_count", "rules_triggered",
            # Memory audit (E1)
            "mem_retrieved_count", "mem_cognitive_system", "mem_surprise",
            # Social audit (E2)
            "social_gossip_count", "social_elevated_neighbors", "social_neighbor_count",
            # Cognitive audit (E3)
            "cog_system_mode", "cog_surprise_value", "cog_is_novel_state",
            # Rule breakdown (B.5)
            "rules_personal_hit", "rules_social_hit", "rules_thinking_hit", "rules_physical_hit"
        ]
        
        # Phase 12: Support custom priority keys from first trace if present
        if traces and "_audit_priority" in traces[0]:
            custom_priority = traces[0]["_audit_priority"]
            if isinstance(custom_priority, list):
                # Put custom ones after the absolute core (step, agent) but before others
                priority_keys = ["step_id", "agent_id"] + custom_priority + [k for k in priority_keys if k not in ["step_id", "agent_id"] + custom_priority]

        all_keys = set().union(*(d.keys() for d in flat_rows))
        # Sort keys to keep priority ones first
        fieldnames = priority_keys + [k for k in sorted(list(all_keys)) if k not in priority_keys]
        
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(flat_rows)


# Aliases
AuditWriter = GenericAuditWriter
