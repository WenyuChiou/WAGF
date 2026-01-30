"""Tests for drift detection and role enforcement (Task-058C)."""
import math

from broker.components.drift_detector import DriftDetector, DriftAlert
from broker.components.role_permissions import RoleEnforcer, FLOOD_ROLES


def test_compute_shannon_entropy_values():
    # All same -> entropy 0
    uniform = {"elevate_house": 10}
    assert DriftDetector.compute_shannon_entropy(uniform) == 0.0

    # Diverse -> entropy > 0
    diverse = {"a": 5, "b": 5}
    assert DriftDetector.compute_shannon_entropy(diverse) > 0.0
    assert math.isclose(DriftDetector.compute_shannon_entropy(diverse), 1.0, rel_tol=1e-6)


def test_population_drift_detects_echo_chamber():
    detector = DriftDetector(entropy_threshold=0.5)
    decisions = {f"H_{i:03d}": "elevate_house" for i in range(9)}
    decisions["H_010"] = "do_nothing"
    detector.record_population_snapshot(year=5, decisions=decisions)

    report = detector.detect_population_drift()
    assert report is not None
    assert report.dominant_action == "elevate_house"
    assert report.dominant_pct >= 0.8
    assert any("entropy" in alert.lower() for alert in report.alerts)
    assert any("dominant" in alert.lower() for alert in report.alerts)


def test_jaccard_similarity_and_individual_drift():
    detector = DriftDetector(window_size=5, jaccard_threshold=0.7)
    for _ in range(5):
        detector.record_agent_decision("H_001", "elevate_house")

    score = detector.compute_jaccard_similarity("H_001")
    assert score > 0.7

    report = detector.detect_individual_drift("H_001")
    assert report is not None
    assert report.stagnant is True
    assert report.decision_variety == 1


def test_get_alerts_population_and_individual():
    detector = DriftDetector(window_size=5, entropy_threshold=0.5, jaccard_threshold=0.7)
    decisions = {f"H_{i:03d}": "elevate_house" for i in range(10)}
    agent_types = {aid: "household" for aid in decisions}
    detector.record_population_snapshot(year=3, decisions=decisions, agent_types=agent_types)
    for _ in range(5):
        detector.record_agent_decision("H_001", "elevate_house")

    alerts = detector.get_alerts(year=3)
    assert any(a.category == "population" for a in alerts)
    assert any(a.category == "individual" for a in alerts)
    assert any(a.category == "type" for a in alerts)


def test_no_data_returns_no_alerts():
    detector = DriftDetector()
    assert detector.detect_population_drift() is None
    assert detector.get_alerts(year=1) == []


def test_role_enforcer_permissions():
    enforcer = RoleEnforcer()

    allowed = enforcer.check_skill_permission("government", "increase_subsidy")
    denied = enforcer.check_skill_permission("government", "buy_insurance")
    assert allowed.allowed is True
    assert denied.allowed is False

    allowed_access = enforcer.check_state_access("insurance", "community")
    denied_access = enforcer.check_state_access("insurance", "spatial")
    assert allowed_access.allowed is True
    assert denied_access.allowed is False

    allowed_mut = enforcer.check_state_mutation("insurance", "premium_rate")
    denied_mut = enforcer.check_state_mutation("insurance", "budget")
    assert allowed_mut.allowed is True
    assert denied_mut.allowed is False

