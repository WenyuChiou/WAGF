# Task-033 Phase 5: Research Reproducibility

**Assignee**: Codex
**Branch**: `task-033-phase5-research` (create from `task-033-phase1-types` after Phase 1 merges)
**Dependencies**: Phase 1 must be complete first

---

## Objective

Add research reproducibility features including session metadata, trace export for statistical analysis, and methods section generation.

---

## Deliverables

### 5.1 Research Session Metadata

**File**: `governed_ai_sdk/v1_prototype/research/__init__.py`

```python
"""Research reproducibility module."""
from .session import ResearchSession
from .export import export_traces_to_csv, export_to_stata, export_to_json

__all__ = [
    "ResearchSession",
    "export_traces_to_csv",
    "export_to_stata",
    "export_to_json",
]
```

**File**: `governed_ai_sdk/v1_prototype/research/session.py`

```python
"""Research session metadata for academic reproducibility."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional
import json


@dataclass
class ResearchSession:
    """
    Metadata for entire research session.

    Captures all parameters needed to reproduce the study.
    """
    study_id: str
    domain: str
    protocol_version: str
    execution_date: datetime = field(default_factory=datetime.now)
    seed: int = 42
    treatment_groups: Dict[str, int] = field(default_factory=dict)
    sensor_schemas: Dict[str, Any] = field(default_factory=dict)
    total_agents: int = 0
    framework_version: str = "0.1.0"

    # Optional metadata
    researcher: Optional[str] = None
    institution: Optional[str] = None
    irb_number: Optional[str] = None
    notes: Optional[str] = None

    def to_methods_section(self) -> str:
        """
        Export formatted text for academic Methods section.

        Returns:
            Markdown-formatted methods section
        """
        groups_str = ", ".join(f"{k}={v}" for k, v in self.treatment_groups.items())

        return f"""## Methods

### Simulation Framework
- **Framework**: GovernedAI SDK v{self.framework_version}
- **Domain**: {self.domain}
- **Protocol Version**: {self.protocol_version}

### Participants
- **Total Agents**: N={self.total_agents}
- **Treatment Groups**: {groups_str}

### Reproducibility
- **Study ID**: {self.study_id}
- **Random Seed**: {self.seed}
- **Execution Date**: {self.execution_date.strftime('%Y-%m-%d %H:%M:%S')}

### Sensor Configuration
{self._format_sensors()}
"""

    def _format_sensors(self) -> str:
        """Format sensor schemas as markdown table."""
        if not self.sensor_schemas:
            return "No sensors configured."

        lines = ["| Sensor | Variable | Data Type | Units |", "|--------|----------|-----------|-------|"]
        for name, schema in self.sensor_schemas.items():
            var = schema.get("variable_name", "N/A")
            dtype = schema.get("data_type", "N/A")
            units = schema.get("units", "N/A")
            lines.append(f"| {name} | {var} | {dtype} | {units} |")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Export as dictionary for JSON serialization."""
        return {
            "study_id": self.study_id,
            "domain": self.domain,
            "protocol_version": self.protocol_version,
            "execution_date": self.execution_date.isoformat(),
            "seed": self.seed,
            "treatment_groups": self.treatment_groups,
            "sensor_schemas": self.sensor_schemas,
            "total_agents": self.total_agents,
            "framework_version": self.framework_version,
            "researcher": self.researcher,
            "institution": self.institution,
            "irb_number": self.irb_number,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchSession":
        """Create from dictionary."""
        data = data.copy()
        if isinstance(data.get("execution_date"), str):
            data["execution_date"] = datetime.fromisoformat(data["execution_date"])
        return cls(**data)

    def save(self, path: str) -> None:
        """Save session metadata to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "ResearchSession":
        """Load session metadata from JSON file."""
        with open(path, "r") as f:
            return cls.from_dict(json.load(f))
```

### 5.2 Trace Export for Statistical Analysis

**File**: `governed_ai_sdk/v1_prototype/research/export.py`

```python
"""Export traces for statistical analysis (R, Python, Stata)."""
from typing import List, Dict, Any, Optional
from pathlib import Path
import json


def _trace_to_research_dict(trace: Any) -> Dict[str, Any]:
    """
    Convert a GovernanceTrace or ResearchTrace to flat dict for export.

    Handles nested structures by flattening with underscores.
    """
    result = {
        "trace_id": getattr(trace, "trace_id", None),
        "timestamp": str(getattr(trace, "timestamp", "")),
        "valid": getattr(trace, "valid", None),
        "decision": getattr(trace, "decision", None),
        "blocked_by": getattr(trace, "blocked_by", None),
    }

    # Add research-specific fields if present
    if hasattr(trace, "domain"):
        result["domain"] = trace.domain
    if hasattr(trace, "research_phase"):
        result["research_phase"] = trace.research_phase
    if hasattr(trace, "treatment_group"):
        result["treatment_group"] = trace.treatment_group
    if hasattr(trace, "effect_size"):
        result["effect_size"] = trace.effect_size
    if hasattr(trace, "baseline_surprise"):
        result["baseline_surprise"] = trace.baseline_surprise

    # Flatten delta_state if present
    delta_state = getattr(trace, "delta_state", None)
    if delta_state and isinstance(delta_state, dict):
        for k, v in delta_state.items():
            result[f"delta_{k}"] = v

    # Flatten counterfactual results if present
    cf = getattr(trace, "counterfactual", None)
    if cf:
        result["cf_feasibility"] = getattr(cf, "feasibility_score", None)
        result["cf_strategy"] = str(getattr(cf, "strategy_used", ""))

    return result


def export_traces_to_csv(
    traces: List[Any],
    path: str,
    include_headers: bool = True
) -> None:
    """
    Export traces for R/Python statistical analysis.

    Args:
        traces: List of GovernanceTrace or ResearchTrace objects
        path: Output CSV file path
        include_headers: Whether to include column headers
    """
    if not traces:
        return

    # Convert all traces to dicts
    rows = [_trace_to_research_dict(t) for t in traces]

    # Get all unique keys across all rows
    all_keys = set()
    for row in rows:
        all_keys.update(row.keys())
    all_keys = sorted(all_keys)

    # Write CSV
    with open(path, "w", newline="", encoding="utf-8") as f:
        if include_headers:
            f.write(",".join(all_keys) + "\n")

        for row in rows:
            values = []
            for key in all_keys:
                val = row.get(key, "")
                if val is None:
                    val = ""
                elif isinstance(val, bool):
                    val = "1" if val else "0"
                elif isinstance(val, (int, float)):
                    val = str(val)
                else:
                    # Escape quotes and wrap in quotes if contains comma
                    val = str(val).replace('"', '""')
                    if "," in val or '"' in val or "\n" in val:
                        val = f'"{val}"'
                values.append(val)
            f.write(",".join(values) + "\n")


def export_to_stata(
    traces: List[Any],
    path: str
) -> None:
    """
    Export for Stata analysis (.dta format).

    Requires pandas with pyreadstat installed.
    Falls back to CSV if not available.

    Args:
        traces: List of trace objects
        path: Output .dta file path
    """
    try:
        import pandas as pd
        rows = [_trace_to_research_dict(t) for t in traces]
        df = pd.DataFrame(rows)
        df.to_stata(path, write_index=False)
    except ImportError:
        # Fallback to CSV
        csv_path = path.replace(".dta", ".csv")
        export_traces_to_csv(traces, csv_path)
        raise ImportError(
            f"pandas with pyreadstat required for Stata export. "
            f"Saved as CSV instead: {csv_path}"
        )


def export_to_json(
    traces: List[Any],
    path: str,
    indent: int = 2
) -> None:
    """
    Export traces as JSON (preserves full structure).

    Args:
        traces: List of trace objects
        path: Output JSON file path
        indent: JSON indentation level
    """
    rows = [_trace_to_research_dict(t) for t in traces]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=indent, default=str)


def export_summary_stats(
    traces: List[Any],
    path: str
) -> Dict[str, Any]:
    """
    Generate and export summary statistics.

    Args:
        traces: List of trace objects
        path: Output JSON file path

    Returns:
        Summary statistics dictionary
    """
    if not traces:
        return {}

    rows = [_trace_to_research_dict(t) for t in traces]

    # Calculate statistics
    total = len(rows)
    valid_count = sum(1 for r in rows if r.get("valid"))
    blocked_count = total - valid_count

    # Group by treatment if present
    by_treatment = {}
    for row in rows:
        group = row.get("treatment_group", "unknown")
        if group not in by_treatment:
            by_treatment[group] = {"total": 0, "valid": 0, "blocked": 0}
        by_treatment[group]["total"] += 1
        if row.get("valid"):
            by_treatment[group]["valid"] += 1
        else:
            by_treatment[group]["blocked"] += 1

    stats = {
        "total_traces": total,
        "valid_count": valid_count,
        "blocked_count": blocked_count,
        "valid_rate": valid_count / total if total > 0 else 0,
        "by_treatment_group": by_treatment,
    }

    with open(path, "w") as f:
        json.dump(stats, f, indent=2)

    return stats
```

---

## Tests

**File**: `governed_ai_sdk/tests/test_research.py`

```python
"""Tests for research reproducibility features."""
import pytest
import tempfile
import os
from datetime import datetime
from governed_ai_sdk.v1_prototype.research.session import ResearchSession
from governed_ai_sdk.v1_prototype.research.export import (
    export_traces_to_csv,
    export_to_json,
    export_summary_stats,
)


class MockTrace:
    """Mock trace object for testing."""
    def __init__(self, valid=True, treatment_group="control", **kwargs):
        self.trace_id = kwargs.get("trace_id", "t1")
        self.timestamp = kwargs.get("timestamp", datetime.now())
        self.valid = valid
        self.decision = kwargs.get("decision", "allow")
        self.blocked_by = kwargs.get("blocked_by")
        self.treatment_group = treatment_group
        self.domain = kwargs.get("domain", "flood")
        self.research_phase = kwargs.get("research_phase", "main_study")


class TestResearchSession:
    """Tests for ResearchSession."""

    def test_create_session(self):
        """Can create research session."""
        session = ResearchSession(
            study_id="FLOOD-2024-001",
            domain="flood",
            protocol_version="1.0",
            seed=42,
            treatment_groups={"control": 50, "treatment": 50},
            total_agents=100,
        )
        assert session.study_id == "FLOOD-2024-001"
        assert session.total_agents == 100

    def test_to_methods_section(self):
        """Methods section generation works."""
        session = ResearchSession(
            study_id="TEST-001",
            domain="flood",
            protocol_version="1.0",
            treatment_groups={"control": 10, "treatment": 10},
            total_agents=20,
        )
        methods = session.to_methods_section()
        assert "## Methods" in methods
        assert "flood" in methods
        assert "N=20" in methods

    def test_save_load(self):
        """Can save and load session."""
        session = ResearchSession(
            study_id="TEST-002",
            domain="finance",
            protocol_version="2.0",
            seed=123,
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            session.save(path)
            loaded = ResearchSession.load(path)
            assert loaded.study_id == "TEST-002"
            assert loaded.seed == 123
        finally:
            os.unlink(path)

    def test_to_dict_roundtrip(self):
        """Dict conversion is reversible."""
        session = ResearchSession(
            study_id="TEST-003",
            domain="health",
            protocol_version="1.0",
        )
        data = session.to_dict()
        restored = ResearchSession.from_dict(data)
        assert restored.study_id == session.study_id
        assert restored.domain == session.domain


class TestExport:
    """Tests for export functions."""

    def test_export_csv(self):
        """Can export traces to CSV."""
        traces = [
            MockTrace(valid=True, treatment_group="control"),
            MockTrace(valid=False, treatment_group="treatment", blocked_by="r1"),
        ]

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name

        try:
            export_traces_to_csv(traces, path)
            with open(path) as f:
                content = f.read()
            assert "valid" in content
            assert "treatment_group" in content
        finally:
            os.unlink(path)

    def test_export_json(self):
        """Can export traces to JSON."""
        traces = [
            MockTrace(valid=True),
            MockTrace(valid=False),
        ]

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            export_to_json(traces, path)
            import json
            with open(path) as f:
                data = json.load(f)
            assert len(data) == 2
        finally:
            os.unlink(path)

    def test_summary_stats(self):
        """Summary statistics are calculated correctly."""
        traces = [
            MockTrace(valid=True, treatment_group="control"),
            MockTrace(valid=True, treatment_group="control"),
            MockTrace(valid=False, treatment_group="treatment"),
        ]

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            stats = export_summary_stats(traces, path)
            assert stats["total_traces"] == 3
            assert stats["valid_count"] == 2
            assert stats["blocked_count"] == 1
            assert stats["by_treatment_group"]["control"]["valid"] == 2
        finally:
            os.unlink(path)
```

---

## Verification

```bash
# Create branch
git checkout task-033-phase1-types
git pull
git checkout -b task-033-phase5-research

# Run tests
python -m pytest governed_ai_sdk/tests/test_research.py -v

# Verify methods section generation
python -c "
from governed_ai_sdk.v1_prototype.research import ResearchSession

session = ResearchSession(
    study_id='FLOOD-2024-001',
    domain='flood',
    protocol_version='1.0',
    seed=42,
    treatment_groups={'control': 500, 'governed': 500},
    total_agents=1000,
    researcher='Dr. Example',
    institution='Example University'
)
print(session.to_methods_section())
"
```

---

## Report Format

After completion, add to `.tasks/handoff/current-session.md`:

```
---
REPORT
agent: Codex
task_id: task-033-phase5
scope: governed_ai_sdk/v1_prototype/research
status: done
changes:
- governed_ai_sdk/v1_prototype/research/__init__.py (created)
- governed_ai_sdk/v1_prototype/research/session.py (created)
- governed_ai_sdk/v1_prototype/research/export.py (created)
tests: pytest governed_ai_sdk/tests/test_research.py -v (X passed)
artifacts: none
issues: <any issues encountered>
next: merge into task-033-phase1-types
---
```
