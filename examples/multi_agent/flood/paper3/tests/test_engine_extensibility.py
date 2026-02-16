"""Tests for engine.py extensibility (custom trace patterns, action_space_size)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

from validation.engine import load_traces, _FLOOD_TRACE_PATTERNS


def test_default_flood_patterns_constant():
    """_FLOOD_TRACE_PATTERNS is accessible and has owner/renter keys."""
    assert "owner" in _FLOOD_TRACE_PATTERNS
    assert "renter" in _FLOOD_TRACE_PATTERNS


def test_custom_trace_patterns(tmp_path):
    """Custom trace patterns load files correctly."""
    # Create custom trace files
    upstream_dir = tmp_path / "run1"
    upstream_dir.mkdir()
    traces_a = [
        {"agent_id": "A1", "year": 1, "approved_skill": {"skill_name": "maintain"}},
    ]
    traces_b = [
        {"agent_id": "A2", "year": 1, "approved_skill": {"skill_name": "decrease_large"}},
    ]
    with open(upstream_dir / "upstream_traces.jsonl", "w", encoding="utf-8") as f:
        for t in traces_a:
            f.write(json.dumps(t) + "\n")
    with open(upstream_dir / "downstream_traces.jsonl", "w", encoding="utf-8") as f:
        for t in traces_b:
            f.write(json.dumps(t) + "\n")

    custom_patterns = {
        "upstream": ["**/upstream_traces.jsonl"],
        "downstream": ["**/downstream_traces.jsonl"],
    }
    primary, secondary = load_traces(tmp_path, trace_patterns=custom_patterns)
    assert len(primary) == 1
    assert primary[0]["agent_id"] == "A1"
    assert len(secondary) == 1
    assert secondary[0]["agent_id"] == "A2"


def test_default_patterns_backward_compat(tmp_path):
    """Default None patterns use flood owner/renter patterns."""
    # Create a file matching the default pattern
    sub = tmp_path / "seed_1"
    sub.mkdir()
    with open(sub / "household_owner_traces.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"agent_id": "H1", "year": 1}) + "\n")
    with open(sub / "household_renter_traces.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"agent_id": "H2", "year": 1}) + "\n")

    owners, renters = load_traces(tmp_path)
    assert len(owners) == 1
    assert len(renters) == 1
    assert owners[0]["agent_id"] == "H1"
    assert renters[0]["agent_id"] == "H2"
