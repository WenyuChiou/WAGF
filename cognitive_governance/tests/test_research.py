"""Tests for research reproducibility features."""
import pytest
import tempfile
import os
from datetime import datetime
from cognitive_governance.v1_prototype.research.session import ResearchSession
from cognitive_governance.v1_prototype.research.export import (
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
