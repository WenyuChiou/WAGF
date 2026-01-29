"""
Tests for modular audit log enhancements (E1-E3, B.5).

Tests the new audit fields:
- Memory Audit (E1): retrieved_count, cognitive_system, surprise
- Social Audit (E2): gossip_count, elevated_neighbors, network_density
- Cognitive Audit (E3): system_mode, surprise_value, is_novel_state
- Rule Breakdown (B.5): personal/social/thinking/physical hit counts
- Structural Faults: format_retries tracking
"""
import pytest
import tempfile
import csv
from pathlib import Path

from broker.components.audit_writer import GenericAuditWriter, AuditConfig
from broker.utils.agent_config import GovernanceAuditor


@pytest.fixture
def audit_writer():
    """Create audit writer with temp directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = AuditConfig(
            output_dir=tmpdir,
            experiment_name="test_modular_audit",
            clear_existing_traces=True
        )
        writer = GenericAuditWriter(config)
        yield writer, tmpdir


class TestMemoryAudit:
    """E1: Memory Retrieval Audit tests."""

    def test_memory_audit_fields_exported(self, audit_writer):
        """Memory audit fields should appear in CSV."""
        writer, tmpdir = audit_writer

        trace = {
            "step_id": 1,
            "agent_id": "agent_001",
            "year": 2024,
            "memory_audit": {
                "retrieved_count": 3,
                "cognitive_system": "SYSTEM_2",
                "surprise_value": 0.72,
                "retrieval_mode": "weighted",
                "memories": [
                    {"content": "Flood in 2020", "emotion": "major", "source": "personal"},
                    {"content": "Insurance claim filed", "emotion": "major", "source": "personal"},
                    {"content": "Neighbor elevated", "emotion": "minor", "source": "neighbor"},
                ]
            },
            "approved_skill": {"skill_name": "elevate_house", "status": "APPROVED"}
        }

        writer.write_trace("household", trace)
        writer.finalize()

        csv_path = Path(tmpdir) / "household_governance_audit.csv"
        assert csv_path.exists()

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            row = next(reader)

            assert row["mem_retrieved_count"] == "3"
            assert row["mem_cognitive_system"] == "SYSTEM_2"
            assert float(row["mem_surprise"]) == pytest.approx(0.72)
            assert row["mem_retrieval_mode"] == "weighted"
            assert row["mem_top_emotion"] == "major"
            assert row["mem_top_source"] == "personal"

    def test_memory_audit_defaults(self, audit_writer):
        """Missing memory audit should use defaults."""
        writer, tmpdir = audit_writer

        trace = {
            "step_id": 1,
            "agent_id": "agent_002",
            "approved_skill": {"skill_name": "do_nothing", "status": "APPROVED"}
        }

        writer.write_trace("household", trace)
        writer.finalize()

        csv_path = Path(tmpdir) / "household_governance_audit.csv"
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            row = next(reader)

            assert row["mem_retrieved_count"] == "0"
            assert row["mem_cognitive_system"] == ""


class TestSocialAudit:
    """E2: Social Context Audit tests."""

    def test_social_audit_fields_exported(self, audit_writer):
        """Social audit fields should appear in CSV."""
        writer, tmpdir = audit_writer

        trace = {
            "step_id": 1,
            "agent_id": "agent_001",
            "social_audit": {
                "gossip_received": [
                    {"from_agent": "Agent_23", "content": "Heard about flood"},
                    {"from_agent": "Agent_45", "content": "Insurance claim"}
                ],
                "visible_actions": {
                    "elevated_neighbors": 3,
                    "relocated_neighbors": 1
                },
                "neighbor_count": 5,
                "network_density": 0.4
            },
            "approved_skill": {"skill_name": "buy_insurance", "status": "APPROVED"}
        }

        writer.write_trace("household", trace)
        writer.finalize()

        csv_path = Path(tmpdir) / "household_governance_audit.csv"
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            row = next(reader)

            assert row["social_gossip_count"] == "2"
            assert row["social_elevated_neighbors"] == "3"
            assert row["social_relocated_neighbors"] == "1"
            assert row["social_neighbor_count"] == "5"
            assert float(row["social_network_density"]) == pytest.approx(0.4)


class TestCognitiveAudit:
    """E3: Cognitive State Audit tests."""

    def test_cognitive_audit_fields_exported(self, audit_writer):
        """Cognitive audit fields should appear in CSV."""
        writer, tmpdir = audit_writer

        trace = {
            "step_id": 1,
            "agent_id": "agent_001",
            "cognitive_audit": {
                "system_mode": "SYSTEM_2",
                "surprise": 0.85,
                "margin_to_switch": 0.35,
                "is_novel_state": True
            },
            "approved_skill": {"skill_name": "relocate", "status": "APPROVED"}
        }

        writer.write_trace("household", trace)
        writer.finalize()

        csv_path = Path(tmpdir) / "household_governance_audit.csv"
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            row = next(reader)

            assert row["cog_system_mode"] == "SYSTEM_2"
            assert float(row["cog_surprise_value"]) == pytest.approx(0.85)
            assert row["cog_is_novel_state"] == "True"
            assert float(row["cog_margin_to_switch"]) == pytest.approx(0.35)


class TestRuleBreakdown:
    """B.5: Rule Breakdown tests."""

    def test_rule_breakdown_fields_exported(self, audit_writer):
        """Rule breakdown fields should appear in CSV."""
        writer, tmpdir = audit_writer

        trace = {
            "step_id": 1,
            "agent_id": "agent_001",
            "rule_breakdown": {
                "personal": 1,
                "social": 0,
                "thinking": 2,
                "physical": 1
            },
            "approved_skill": {"skill_name": "do_nothing", "status": "REJECTED"}
        }

        writer.write_trace("household", trace)
        writer.finalize()

        csv_path = Path(tmpdir) / "household_governance_audit.csv"
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            row = next(reader)

            assert row["rules_personal_hit"] == "1"
            assert row["rules_social_hit"] == "0"
            assert row["rules_thinking_hit"] == "2"
            assert row["rules_physical_hit"] == "1"


class TestStructuralFaultTracking:
    """Test structural fault (format/parsing issue) tracking."""

    def test_format_retries_exported_to_csv(self, audit_writer):
        """format_retries field should appear in CSV."""
        writer, tmpdir = audit_writer

        trace = {
            "step_id": 1,
            "agent_id": "agent_001",
            "year": 2024,
            "format_retries": 2,  # Had 2 format issues fixed
            "approved_skill": {"skill_name": "buy_insurance", "status": "APPROVED"}
        }

        writer.write_trace("household", trace)
        writer.finalize()

        csv_path = Path(tmpdir) / "household_governance_audit.csv"
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            row = next(reader)

            assert row["format_retries"] == "2"

    def test_format_retries_in_summary(self, audit_writer):
        """format_retries should be tracked in summary stats."""
        writer, tmpdir = audit_writer

        # Write trace with format retries
        trace1 = {
            "step_id": 1,
            "agent_id": "agent_001",
            "format_retries": 2,
            "approved_skill": {"skill_name": "buy_insurance", "status": "APPROVED"}
        }
        trace2 = {
            "step_id": 2,
            "agent_id": "agent_002",
            "format_retries": 1,
            "approved_skill": {"skill_name": "elevate_house", "status": "APPROVED"}
        }
        trace3 = {
            "step_id": 3,
            "agent_id": "agent_003",
            "format_retries": 0,  # No format issues
            "approved_skill": {"skill_name": "do_nothing", "status": "APPROVED"}
        }

        writer.write_trace("household", trace1)
        writer.write_trace("household", trace2)
        writer.write_trace("household", trace3)
        summary = writer.summary

        assert summary["total_format_retries"] == 3  # 2 + 1 + 0
        assert summary["structural_faults_fixed"] == 2  # 2 traces had format issues

    def test_format_retries_default_zero(self, audit_writer):
        """Missing format_retries should default to 0."""
        writer, tmpdir = audit_writer

        trace = {
            "step_id": 1,
            "agent_id": "agent_001",
            # No format_retries field
            "approved_skill": {"skill_name": "do_nothing", "status": "APPROVED"}
        }

        writer.write_trace("household", trace)
        writer.finalize()

        csv_path = Path(tmpdir) / "household_governance_audit.csv"
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            row = next(reader)

            assert row["format_retries"] == "0"


class TestColumnOrdering:
    """Test that priority columns appear first."""

    def test_priority_columns_order(self, audit_writer):
        """Priority columns should appear in correct order."""
        writer, tmpdir = audit_writer

        trace = {
            "step_id": 1,
            "agent_id": "agent_001",
            "year": 2024,
            "memory_audit": {"retrieved_count": 2, "cognitive_system": "SYSTEM_1"},
            "social_audit": {"gossip_received": [], "neighbor_count": 3},
            "cognitive_audit": {"system_mode": "SYSTEM_1", "surprise": 0.2},
            "rule_breakdown": {"personal": 0, "social": 0, "thinking": 0, "physical": 0},
            "approved_skill": {"skill_name": "do_nothing", "status": "APPROVED"}
        }

        writer.write_trace("household", trace)
        writer.finalize()

        csv_path = Path(tmpdir) / "household_governance_audit.csv"
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

            # Check core columns come first
            assert fieldnames[0] == "step_id"
            assert fieldnames[1] == "year"
            assert fieldnames[2] == "agent_id"

            # Check memory audit columns exist
            assert "mem_retrieved_count" in fieldnames
            assert "mem_cognitive_system" in fieldnames

            # Check social audit columns exist
            assert "social_gossip_count" in fieldnames
            assert "social_neighbor_count" in fieldnames

            # Check cognitive audit columns exist
            assert "cog_system_mode" in fieldnames
            assert "cog_surprise_value" in fieldnames

            # Check rule breakdown columns exist
            assert "rules_personal_hit" in fieldnames
            assert "rules_thinking_hit" in fieldnames

            # Check format_retries column exists
            assert "format_retries" in fieldnames


class TestGovernanceAuditorStructuralFaults:
    """Test GovernanceAuditor structural fault tracking methods."""

    @pytest.fixture
    def fresh_auditor(self):
        """Create a fresh auditor instance for each test."""
        # Reset singleton for testing
        GovernanceAuditor._instance = None
        auditor = GovernanceAuditor()
        yield auditor
        # Cleanup
        GovernanceAuditor._instance = None

    def test_log_format_retry(self, fresh_auditor):
        """log_format_retry increments format_retry_attempts."""
        auditor = fresh_auditor
        assert auditor.format_retry_attempts == 0

        auditor.log_format_retry()
        auditor.log_format_retry()

        assert auditor.format_retry_attempts == 2

    def test_log_structural_fault_resolved(self, fresh_auditor):
        """log_structural_fault_resolved tracks fixed faults."""
        auditor = fresh_auditor
        assert auditor.structural_faults_fixed == 0

        auditor.log_structural_fault_resolved(2)  # 2 retries before success
        auditor.log_structural_fault_resolved(1)  # 1 retry before success

        assert auditor.structural_faults_fixed == 3

    def test_log_structural_fault_terminal(self, fresh_auditor):
        """log_structural_fault_terminal tracks unfixed faults."""
        auditor = fresh_auditor
        assert auditor.structural_faults_terminal == 0

        auditor.log_structural_fault_terminal(2)  # Exhausted 2 retries

        assert auditor.structural_faults_terminal == 2

    def test_save_summary_includes_structural_faults(self, fresh_auditor):
        """save_summary includes structural fault stats."""
        auditor = fresh_auditor
        import json

        auditor.log_format_retry()
        auditor.log_format_retry()
        auditor.log_structural_fault_resolved(1)
        auditor.log_structural_fault_terminal(1)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            summary_path = Path(f.name)

        auditor.save_summary(summary_path)

        with open(summary_path, 'r') as f:
            summary = json.load(f)

        assert "structural_faults" in summary
        assert summary["structural_faults"]["format_retry_attempts"] == 2
        assert summary["structural_faults"]["faults_fixed"] == 1
        assert summary["structural_faults"]["faults_terminal"] == 1

        summary_path.unlink()  # Cleanup
