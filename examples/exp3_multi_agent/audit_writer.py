"""
Audit Writer (Exp3) - Aligned with core broker pattern

Based on broker/audit_writer.py structure:
- JSONL format for traces
- write_trace() per decision
- finalize() for summary
- Separate files per agent type

Outputs:
- household_audit.jsonl: All household agent decisions
- institutional_audit.jsonl: Insurance + Government decisions
- audit_summary.json: Aggregate statistics
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from examples.exp3_multi_agent.parsers import HouseholdOutput, InsuranceOutput, GovernmentOutput


@dataclass
class AuditConfig:
    """Configuration for audit writing."""
    output_dir: str
    log_level: str = "full"  # full, summary, errors_only
    experiment_name: str = "exp3_multi_agent"


class AuditWriter:
    """
    Writes audit traces for multi-agent simulation.
    
    Aligned with core broker/audit_writer.py pattern:
    - JSONL format
    - write_trace() method
    - finalize() for summary
    """
    
    def __init__(self, config: AuditConfig):
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # File paths
        self.household_file = self.output_dir / "household_audit.jsonl"
        self.institutional_file = self.output_dir / "institutional_audit.jsonl"
        self.summary_file = self.output_dir / "audit_summary.json"
        
        # Summary statistics
        self.summary = {
            "experiment_name": config.experiment_name,
            "total_household_decisions": 0,
            "total_institutional_decisions": 0,
            "decisions_by_type": {
                "buy_insurance": 0,
                "elevate_house": 0,
                "relocate": 0,
                "do_nothing": 0
            },
            "validation_failures": 0,
            "constructs_distribution": {
                "TP": {"LOW": 0, "MODERATE": 0, "HIGH": 0},
                "CP": {"LOW": 0, "MODERATE": 0, "HIGH": 0},
                "SP": {"LOW": 0, "MODERATE": 0, "HIGH": 0},
                "SC": {"LOW": 0, "MODERATE": 0, "HIGH": 0},
                "PA": {"NONE": 0, "PARTIAL": 0, "FULL": 0}
            }
        }
    
    # =========================================================================
    # HOUSEHOLD AUDIT
    # =========================================================================
    
    def write_household_trace(
        self, 
        output: HouseholdOutput, 
        agent_state: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Write a single household decision trace.
        
        Args:
            output: Parsed LLM output (HouseholdOutput)
            agent_state: Current agent state
            context: Simulation context (subsidy_rate, premium_rate, etc.)
        """
        self.summary["total_household_decisions"] += 1
        
        # Update decision stats
        skill = output.decision_skill
        if skill in self.summary["decisions_by_type"]:
            self.summary["decisions_by_type"][skill] += 1
        
        # Update construct distribution
        self._update_construct_stats(output)
        
        # Track validation failures
        if not output.validated:
            self.summary["validation_failures"] += 1
        
        # Build trace
        trace = {
            "timestamp": datetime.now().isoformat(),
            "year": output.year,
            "agent_id": output.agent_id,
            "mg": output.mg,
            "tenure": output.tenure,
            "region_id": agent_state.get("region_id", "NJ"),
            # State snapshot
            "state": {
                "elevated": agent_state.get("elevated", False),
                "has_insurance": agent_state.get("has_insurance", False),
                "cumulative_damage": agent_state.get("cumulative_damage", 0),
                "income": agent_state.get("income", 0),
                "property_value": agent_state.get("property_value", 0)
            },
            # Constructs (LLM Output)
            "constructs": {
                "TP": {"level": output.tp_level, "explanation": output.tp_explanation},
                "CP": {"level": output.cp_level, "explanation": output.cp_explanation},
                "SP": {"level": output.sp_level, "explanation": output.sp_explanation},
                "SC": {"level": output.sc_level, "explanation": output.sc_explanation},
                "PA": {"level": output.pa_level, "explanation": output.pa_explanation}
            },
            # Decision
            "decision_number": output.decision_number,
            "decision_skill": output.decision_skill,
            "justification": output.justification,
            # Validation
            "validated": output.validated,
            "validation_errors": output.validation_errors,
            # Context
            "context": context or {}
        }
        
        # Should write?
        if self._should_write(trace):
            with open(self.household_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(trace, ensure_ascii=False) + '\n')
    
    def _update_construct_stats(self, output: HouseholdOutput) -> None:
        """Update construct distribution statistics."""
        dist = self.summary["constructs_distribution"]
        
        if output.tp_level in dist["TP"]:
            dist["TP"][output.tp_level] += 1
        if output.cp_level in dist["CP"]:
            dist["CP"][output.cp_level] += 1
        if output.sp_level in dist["SP"]:
            dist["SP"][output.sp_level] += 1
        if output.sc_level in dist["SC"]:
            dist["SC"][output.sc_level] += 1
        if output.pa_level in dist["PA"]:
            dist["PA"][output.pa_level] += 1
    
    # =========================================================================
    # INSTITUTIONAL AUDIT (Insurance + Government)
    # =========================================================================
    
    def write_insurance_trace(
        self, 
        output: InsuranceOutput, 
        agent_id: str = "InsuranceCo",
        state: Optional[Dict[str, Any]] = None
    ) -> None:
        """Write insurance agent decision trace."""
        self.summary["total_institutional_decisions"] += 1
        
        trace = {
            "timestamp": datetime.now().isoformat(),
            "year": output.year,
            "agent_type": "Insurance",
            "agent_id": agent_id,
            "analysis": output.analysis,
            "decision": output.decision,
            "adjustment_pct": output.adjustment_pct,
            "justification": output.justification,
            "validated": output.validated,
            "state": state or {}
        }
        
        with open(self.institutional_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(trace, ensure_ascii=False) + '\n')
    
    def write_government_trace(
        self, 
        output: GovernmentOutput, 
        agent_id: str = "Government",
        state: Optional[Dict[str, Any]] = None
    ) -> None:
        """Write government agent decision trace."""
        self.summary["total_institutional_decisions"] += 1
        
        trace = {
            "timestamp": datetime.now().isoformat(),
            "year": output.year,
            "agent_type": "Government",
            "agent_id": agent_id,
            "analysis": output.analysis,
            "decision": output.decision,
            "adjustment_pct": output.adjustment_pct,
            "priority": output.priority,
            "justification": output.justification,
            "validated": output.validated,
            "state": state or {}
        }
        
        with open(self.institutional_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(trace, ensure_ascii=False) + '\n')
    
    # =========================================================================
    # FILTERING & FINALIZATION
    # =========================================================================
    
    def _should_write(self, trace: Dict) -> bool:
        """Determine if trace should be written based on log level."""
        if self.config.log_level == "full":
            return True
        elif self.config.log_level == "summary":
            # Only write validation issues
            return not trace.get("validated", True)
        elif self.config.log_level == "errors_only":
            return len(trace.get("validation_errors", [])) > 0
        return True
    
    def finalize(self) -> Dict[str, Any]:
        """
        Finalize audit and write summary.
        
        Returns:
            Summary statistics dictionary
        """
        self.summary["finalized_at"] = datetime.now().isoformat()
        
        # Calculate rates
        total_hh = self.summary["total_household_decisions"]
        if total_hh > 0:
            self.summary["decision_rates"] = {
                k: f"{v/total_hh*100:.1f}%"
                for k, v in self.summary["decisions_by_type"].items()
            }
            self.summary["validation_failure_rate"] = \
                f"{self.summary['validation_failures']/total_hh*100:.1f}%"
        
        # Write summary
        with open(self.summary_file, 'w', encoding='utf-8') as f:
            json.dump(self.summary, f, indent=2, ensure_ascii=False)
        
        print(f"[Audit] Finalized. Summary written to {self.summary_file}")
        return self.summary
    
    def reset(self):
        """Reset audit files for new simulation run (backs up existing)."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for path in [self.household_file, self.institutional_file, self.summary_file]:
            if path.exists():
                backup = path.with_suffix(f".{timestamp}.backup")
                path.rename(backup)
