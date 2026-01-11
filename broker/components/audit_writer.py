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
        """Write a generic trace for any agent type."""
        # Ensure required fields
        trace.setdefault("timestamp", datetime.now().isoformat())
        trace.setdefault("agent_type", agent_type)
        
        # Add basic validation info if provided
        if validation_results:
            trace["validated"] = all(r.valid for r in validation_results)
            trace["validation_issues"] = []
            for r in validation_results:
                if not r.valid:
                    self.summary["validation_errors"] += 1
                    trace["validation_issues"].append({
                        "validator": getattr(r, 'validator_name', 'Unknown'),
                        "errors": r.errors
                    })
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
        
        # Write JSONL
        file_path = self._get_file_path(agent_type)
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(trace, ensure_ascii=False, default=str) + '\n')
        
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
            
        print(f"[Audit] Finalized. Summary: {summary_path}")
        return self.summary

    def _export_csv(self, agent_type: str, traces: List[Dict[str, Any]]):
        """Export buffered traces to flat CSV."""
        csv_path = self.output_dir / f"{agent_type}_audit.csv"
        if not traces: return

        # Flatten rows (simplified)
        flat_rows = []
        for t in traces:
            row = {
                "timestamp": t.get("timestamp"),
                "agent_id": t.get("agent_id"),
                "decision": t.get("decision", t.get("approved_skill", {}).get("skill_name")),
                "validated": t.get("validated")
            }
            # Flatten reasoning if present
            if "skill_proposal" in t and "reasoning" in t["skill_proposal"]:
                row.update(t["skill_proposal"]["reasoning"])
            flat_rows.append(row)

        if not flat_rows: return

        keys = flat_rows[0].keys()
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(flat_rows)


# Aliases
AuditWriter = GenericAuditWriter
