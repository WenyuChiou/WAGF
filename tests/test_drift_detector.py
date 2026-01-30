"""Tests for DriftDetector (Task-058C).

Tests population-level entropy, individual Jaccard stagnation, and alerts.
"""
import pytest
from broker.components.drift_detector import (
    DriftDetector,
    DriftReport,
    AgentDriftReport,
    DriftAlert,
)


@pytest.fixture
def detector():
    return DriftDetector(
        entropy_threshold=0.5,
        stagnation_threshold=0.6,
        collapse_threshold=0.9,
        history_window=5,
        jaccard_stagnation_threshold=0.8,
    )


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

class TestRecording:
    def test_record_single_decision(self, detector):
        detector.record_decision("A1", "buy_insurance")
        assert "A1" in detector._agent_history
        assert detector._agent_history["A1"] == ["buy_insurance"]

    def test_record_decisions_batch(self, detector):
        detector.record_decisions({"A1": "buy", "A2": "sell", "A3": "hold"})
        assert len(detector._agent_history) == 3

    def test_history_trimming(self, detector):
        for i in range(25):
            detector.record_decision("A1", f"action_{i}")
        assert len(detector._agent_history["A1"]) <= detector.history_window * 2


# ---------------------------------------------------------------------------
# Snapshot computation
# ---------------------------------------------------------------------------

class TestSnapshot:
    def test_empty_snapshot(self, detector):
        report = detector.compute_snapshot(step=1)
        assert report.decision_entropy == 0.0
        assert report.dominant_action == ""
        assert report.stagnation_rate == 0.0

    def test_single_action_zero_entropy(self, detector):
        for i in range(10):
            detector.record_decision(f"A{i}", "buy_insurance")
        report = detector.compute_snapshot(step=1)
        assert report.decision_entropy == 0.0
        assert report.dominant_action == "buy_insurance"
        assert report.dominant_action_pct == 1.0

    def test_diverse_actions_high_entropy(self, detector):
        actions = ["buy", "sell", "hold", "wait", "invest", "hedge", "trade", "swap"]
        for i, action in enumerate(actions):
            detector.record_decision(f"A{i}", action)
        report = detector.compute_snapshot(step=1)
        assert report.decision_entropy > 2.0  # log2(8) = 3.0
        assert report.dominant_action_pct == 1.0 / 8.0

    def test_dominant_action_pct(self, detector):
        for i in range(8):
            detector.record_decision(f"A{i}", "buy")
        for i in range(2):
            detector.record_decision(f"B{i}", "sell")
        report = detector.compute_snapshot(step=1)
        assert report.dominant_action == "buy"
        assert abs(report.dominant_action_pct - 0.8) < 0.01

    def test_include_agents(self, detector):
        for step in range(4):
            detector.record_decision("A1", "buy")
            detector.record_decision("A2", f"action_{step}")
        report = detector.compute_snapshot(step=4, include_agents=True)
        assert len(report.agent_reports) == 2

    def test_reports_accumulate(self, detector):
        detector.record_decision("A1", "buy")
        detector.compute_snapshot(step=1)
        detector.compute_snapshot(step=2)
        assert len(detector.reports) == 2


# ---------------------------------------------------------------------------
# Stagnation (Jaccard)
# ---------------------------------------------------------------------------

class TestStagnation:
    def test_fully_stagnant_agents(self, detector):
        # Same decision repeatedly -> stagnant
        for step in range(6):
            for i in range(10):
                detector.record_decision(f"A{i}", "buy_insurance")
        report = detector.compute_snapshot(step=6)
        # All agents always choose "buy_insurance" -> Jaccard = 1.0 -> stagnant
        assert report.stagnation_rate > 0.5

    def test_varying_agents_not_stagnant(self, detector):
        actions = ["buy", "sell", "hold", "wait", "invest"]
        for step in range(6):
            for i in range(10):
                detector.record_decision(f"A{i}", actions[(i + step) % len(actions)])
        report = detector.compute_snapshot(step=6)
        # Varying decisions -> low Jaccard -> not stagnant
        assert report.stagnation_rate < 0.5


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class TestAlerts:
    def test_low_entropy_alert(self, detector):
        report = DriftReport(
            step=1, decision_entropy=0.3,
            dominant_action="buy", dominant_action_pct=0.7,
            stagnation_rate=0.2,
        )
        alerts = detector.check_alerts(report)
        assert any(a.alert_type == "LOW_ENTROPY" for a in alerts)

    def test_high_stagnation_alert(self, detector):
        report = DriftReport(
            step=1, decision_entropy=2.0,
            dominant_action="buy", dominant_action_pct=0.5,
            stagnation_rate=0.8,
        )
        alerts = detector.check_alerts(report)
        assert any(a.alert_type == "HIGH_STAGNATION" for a in alerts)

    def test_mode_collapse_alert(self, detector):
        report = DriftReport(
            step=1, decision_entropy=0.1,
            dominant_action="buy", dominant_action_pct=0.95,
            stagnation_rate=0.3,
        )
        alerts = detector.check_alerts(report)
        assert any(a.alert_type == "MODE_COLLAPSE" for a in alerts)

    def test_no_alerts_when_healthy(self, detector):
        report = DriftReport(
            step=1, decision_entropy=2.5,
            dominant_action="buy", dominant_action_pct=0.3,
            stagnation_rate=0.1,
        )
        alerts = detector.check_alerts(report)
        assert alerts == []


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_clears_state(self, detector):
        detector.record_decision("A1", "buy")
        detector.compute_snapshot(step=1)
        detector.reset()
        assert len(detector._agent_history) == 0
        assert len(detector.reports) == 0
