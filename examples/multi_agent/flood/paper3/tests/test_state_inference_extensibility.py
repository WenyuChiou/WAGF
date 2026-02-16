"""Tests for state_inference extensibility (custom state rules)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

from validation.io.state_inference import (
    _extract_final_states_from_decisions,
    FLOOD_STATE_RULES,
)


def _make_trace(agent_id, year, action, outcome="APPROVED"):
    return {
        "agent_id": agent_id,
        "year": year,
        "approved_skill": {"skill_name": action},
        "outcome": outcome,
        "validated": True,
        "state_after": {},
    }


def test_default_flood_rules_unchanged():
    """Default flood state rules produce same results as before."""
    traces = [
        _make_trace("H001", 1, "buy_insurance"),
        _make_trace("H002", 1, "elevate"),
        _make_trace("H003", 1, "buyout"),
        _make_trace("H004", 1, "relocate"),
    ]
    states = _extract_final_states_from_decisions(traces)
    assert states["H001"]["has_insurance"] is True
    assert states["H002"]["elevated"] is True
    assert states["H003"]["bought_out"] is True
    assert states["H004"]["relocated"] is True


def test_custom_irrigation_rules():
    """Custom irrigation state rules work correctly."""
    irrigation_rules = [
        ("reduced_demand", "ever", "decrease_large"),
        ("increased_demand", "ever", "increase_large"),
        ("maintained", "last", "maintain"),
    ]
    traces = [
        _make_trace("A001", 1, "decrease_large"),
        _make_trace("A001", 2, "maintain"),
        _make_trace("A002", 1, "increase_large"),
        _make_trace("A002", 2, "increase_large"),
    ]
    states = _extract_final_states_from_decisions(traces, state_rules=irrigation_rules)

    # A001: ever decreased, last action=maintain
    assert states["A001"]["reduced_demand"] is True
    assert states["A001"]["maintained"] is True
    assert states["A001"]["increased_demand"] is False

    # A002: ever increased, last action=increase_large (not maintain)
    assert states["A002"]["increased_demand"] is True
    assert states["A002"]["maintained"] is False
    assert states["A002"]["reduced_demand"] is False


def test_empty_rules_produce_no_state_keys():
    """Empty state rules produce no domain-specific keys (only _year)."""
    traces = [_make_trace("H001", 1, "buy_insurance")]
    states = _extract_final_states_from_decisions(traces, state_rules=[])
    assert "_year" in states["H001"]
    assert "has_insurance" not in states["H001"]


def test_flood_state_rules_constant():
    """FLOOD_STATE_RULES is accessible and has expected entries."""
    assert len(FLOOD_STATE_RULES) == 4
    keys = [r[0] for r in FLOOD_STATE_RULES]
    assert "has_insurance" in keys
    assert "elevated" in keys
    assert "bought_out" in keys
    assert "relocated" in keys
