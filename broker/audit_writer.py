"""
Generic Audit Writer

Agent-type agnostic audit logging.
Works with any agent type via Dict-based traces.
"""

from datetime import datetime
from dataclasses import dataclass
import json
import csv
from pathlib import Path
from typing import Dict, Any, List, Optional


@dataclass
class AuditConfig:
    """Configuration for audit writing."""
    output_dir: str
    experiment_name: str = "simulation"
    log_level: str = "full"  # full, summary, errors_only


class GenericAuditWriter:
    """
    Generic audit writer for any agent type.
    
    Uses Dict-based traces instead of typed dataclasses.
    Automatically creates per-agent-type files.
    
    Usage:
        writer = GenericAuditWriter(AuditConfig(output_dir="results"))
        writer.write_trace("agent_type_a", trace_dict)
        writer.write_trace("agent_type_b", trace_dict)
        writer.finalize()
    """
    
    def __init__(self, config: AuditConfig):
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
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
        """Get or create file path for agent type."""
        if agent_type not in self._files:
            self._files[agent_type] = self.output_dir / f"{agent_type}_audit.jsonl"
        return self._files[agent_type]
    
    def write_trace(
        self,
        agent_type: str,
        trace: Dict[str, Any],
        validation_results: Optional[List] = None
    ) -> None:
        """
        Write a generic trace for any agent type.
        
        Args:
            agent_type: Name of the agent category (e.g., "type_a", "type_b")
            trace: Dict with at least: agent_id, year, decision
            validation_results: Optional list of ValidationResult
        """
        # Ensure required fields
        trace.setdefault("timestamp", datetime.now().isoformat())
        trace.setdefault("agent_type", agent_type)
        
        # Add validation info
        if validation_results:
            trace["validated"] = len(validation_results) == 0
            trace["validation_issues"] = [
                {
                    "level": r.metadata.get("level").value if hasattr(r.metadata.get("level"), "value") else str(r.metadata.get("level")),
                    "tier": r.metadata.get("tier", "Unknown"),
                    "rule": r.metadata.get("rule", "Unknown"),
                    "message": r.metadata.get("message") or (r.errors[0] if r.errors else (r.warnings[0] if r.warnings else ""))
                }
                for r in validation_results
            ]
            # Count errors/warnings
            for r in validation_results:
                level = r.metadata.get("level")
                # Handle both enum and string cases
                level_str = level.value if hasattr(level, "value") else str(level)
                if level_str == "ERROR":
                    self.summary["validation_errors"] += 1
                else:
                    self.summary["validation_warnings"] += 1
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
        
        # Track decision distribution
        decision = trace.get("decision", trace.get("decision_skill", "unknown"))
        decisions = self.summary["agent_types"][agent_type]["decisions"]
        decisions[decision] = decisions.get(decision, 0) + 1
        
        # Should write?
        if self._should_write(trace):
            file_path = self._get_file_path(agent_type)
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(trace, ensure_ascii=False, default=str) + '\n')
            
            # Buffer for CSV
            if agent_type not in self._trace_buffer:
                self._trace_buffer[agent_type] = []
            self._trace_buffer[agent_type].append(trace)
    
    def write_construct_trace(
        self,
        agent_type: str,
        agent_id: str,
        year: int,
        constructs: Dict[str, Dict[str, str]],
        decision: str,
        state: Dict[str, Any],
        validation_results: Optional[List] = None
    ) -> None:
        """
        Convenience method for PMT-style construct logging.
        
        Args:
            constructs: Dict of {construct_name: {"level": "H", "explanation": "..."}}
        """
        trace = {
            "agent_id": agent_id,
            "year": year,
            "constructs": constructs,
            "decision": decision,
            "state": state
        }
        self.write_trace(agent_type, trace, validation_results)
    
    def _should_write(self, trace: Dict) -> bool:
        """Filter based on log level."""
        if self.config.log_level == "full":
            return True
        elif self.config.log_level == "summary":
            return not trace.get("validated", True)
        elif self.config.log_level == "errors_only":
            issues = trace.get("validation_issues", [])
            return any(i.get("level") == "ERROR" for i in issues)
        return True
    
    def finalize(self) -> Dict[str, Any]:
        """Write summary and return stats."""
        self.summary["finalized_at"] = datetime.now().isoformat()
        
        # Calculate rates
        total = self.summary["total_traces"]
        if total > 0:
            self.summary["error_rate"] = f"{self.summary['validation_errors']/total*100:.1f}%"
            self.summary["warning_rate"] = f"{self.summary['validation_warnings']/total*100:.1f}%"
        
        # Write summary
        summary_path = self.output_dir / "audit_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(self.summary, f, indent=2, ensure_ascii=False)
        
        # Export CSVs
        for agent_type, traces in self._trace_buffer.items():
            self._export_csv(agent_type, traces)
            
        print(f"[Audit] Finalized. Summary: {summary_path}")
        return self.summary

    def _export_csv(self, agent_type: str, traces: List[Dict[str, Any]]):
        """Export buffered traces to a flat CSV file."""
        csv_path = self.output_dir / f"{agent_type}_audit.csv"
        if not traces:
            return

        # Prepare flat rows
        flat_rows = []
        for t in traces:
            # Flatten core fields
            row = {
                "timestamp": t.get("timestamp"),
                "step_id": t.get("step_id"),
                "agent_id": t.get("agent_id"),
                "outcome": t.get("outcome"),
                "retry_count": t.get("retry_count"),
                "approved_skill": t.get("approved_skill", {}).get("skill_name"),
                "status": t.get("approved_skill", {}).get("status"),
                "validated": t.get("validated"),
                "issues": "|".join([f"[{i.get('tier', 'T2')}][{i.get('level', 'ERROR')}]: {i.get('message', '')}" for i in t.get("validation_issues", [])])
            }
            
            # Add all reasoning constructs dynamically (TP_LABEL, etc.)
            reasoning = t.get("skill_proposal", {}).get("reasoning", {})
            for k, v in reasoning.items():
                if k not in row:
                    row[k] = v
            
            # Add debug info at the end
            row["debug_prompt"] = t.get("input", "")[:1000] if t.get("input") else ""
            row["raw_output"] = t.get("skill_proposal", {}).get("raw_output", "")
            flat_rows.append(row)

        if not flat_rows:
            return

        # Use a fixed order for core fields if possible, then dynamic ones
        core_fields = ["timestamp", "step_id", "agent_id", "outcome", "retry_count", "approved_skill", "status", "validated", "issues"]
        all_keys = set()
        for r in flat_rows:
            all_keys.update(r.keys())
        
        # Sort keys: core first, then others, then debug info
        other_keys = sorted([k for k in all_keys if k not in core_fields and k not in ["debug_prompt", "raw_output"]])
        fieldnames = core_fields + other_keys + ["debug_prompt", "raw_output"]
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flat_rows)
        print(f"[Audit] Exported CSV: {csv_path}")

        # Enhanced: Export SEPARATE Error Log
        error_rows = [r for r in flat_rows if r.get("outcome") != "APPROVED" or r.get("validated") is False]
        if error_rows:
            err_csv_path = self.output_dir / f"{agent_type}_errors_audit.csv"
            with open(err_csv_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(error_rows)
            print(f"[Audit] Exported Error Log: {err_csv_path}")
    
    def reset(self):
        """Backup existing files and reset."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for path in self._files.values():
            if path.exists():
                backup = path.with_suffix(f".{timestamp}.backup")
                path.rename(backup)
        self._files.clear()
