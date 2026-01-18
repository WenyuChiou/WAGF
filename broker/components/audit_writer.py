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
            "validation_warnings": 0
        }
        
        # Buffer for CSV export
        self._trace_buffer: Dict[str, List[Dict[str, Any]]] = {}
    
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
        else:
            trace["validated"] = True
            trace["validation_issues"] = []

        
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
        
        # Write JSONL with retry for cloud drive flakiness (Errno 22 / Locks)
        file_path = self._get_file_path(agent_type)
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(trace, ensure_ascii=False, default=str) + '\n')
                break # Success
            except (OSError, IOError) as e:
                if attempt == max_retries - 1:
                    logger.error(f" [AuditWriter:Error] Final failure writing trace to {file_path}: {e}")
                else:
                    time.sleep(1.0) # Wait for sync/lock to clear
        
        # Buffer for CSV
        if agent_type not in self._trace_buffer:
            self._trace_buffer[agent_type] = []
        self._trace_buffer[agent_type].append(trace)
    
    def finalize(self) -> Dict[str, Any]:
        """Write summary and export CSVs."""
        self.summary["finalized_at"] = datetime.now().isoformat()
        
        # Export summary JSON
        summary_path = self.output_dir / "audit_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(self.summary, f, indent=2, ensure_ascii=False)
        
        # Export CSVs
        for agent_type, traces in self._trace_buffer.items():
            self._export_csv(agent_type, traces)
            
        logger.info(f"[Audit] Finalized. Summary: {summary_path}")
        return self.summary

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
            
            # 2. Skill Logic (Proposed vs Approved)
            skill_prop = t.get("skill_proposal") or {}
            appr_skill = t.get("approved_skill") or {}
            row["proposed_skill"] = skill_prop.get("skill_name")
            row["final_skill"] = appr_skill.get("skill_name")
            row["parsing_warnings"] = "|".join(skill_prop.get("parsing_warnings", []) or [])
            row["raw_output"] = skill_prop.get("raw_output", t.get("raw_output", ""))
            
            # 3. Reasoning (TP/CP Appraisal + Audits)
            reasoning = skill_prop.get("reasoning", {})
            if isinstance(reasoning, dict):
                for k, v in reasoning.items():
                    if k == "demographic_audit" and isinstance(v, dict):
                        # Flatten Demographic Audit (Phase 21)
                        row["demo_score"] = v.get("score", 0.0)
                        row["demo_anchors"] = "|".join(v.get("cited_anchors", []))
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

            flat_rows.append(row)

        if not flat_rows: return

        # Ensure consistent column ordering for user
        priority_keys = ["step_id", "year", "agent_id", "proposed_skill", "final_skill", "status", "retry_count", "validated", "failed_rules"]
        
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
