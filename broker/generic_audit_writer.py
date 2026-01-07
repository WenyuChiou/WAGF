"""
Generic Audit Writer

Agent-type agnostic audit logging.
Works with any agent type via Dict-based traces.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass


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
        writer.write_trace("household", trace_dict)
        writer.write_trace("insurance", trace_dict)
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
            agent_type: e.g., "household", "insurance", "government"
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
                {"level": r.level.value, "rule": r.rule, "message": r.message}
                for r in validation_results
            ]
            # Count errors/warnings
            for r in validation_results:
                if r.level.value == "ERROR":
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
        
        print(f"[Audit] Finalized. Summary: {summary_path}")
        return self.summary
    
    def reset(self):
        """Backup existing files and reset."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for path in self._files.values():
            if path.exists():
                backup = path.with_suffix(f".{timestamp}.backup")
                path.rename(backup)
        self._files.clear()
