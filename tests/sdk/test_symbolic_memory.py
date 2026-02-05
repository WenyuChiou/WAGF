"""
Tests for Phase 3: Symbolic Memory Layer.

Verifies SymbolicMemory wrapper for v4 Symbolic Context integration.
"""

import pytest
from cognitive_governance.v1_prototype.memory.symbolic import (
    Sensor,
    SymbolicMemory,
    SymbolicContextMonitor,
)


class TestSymbolicMemory:
    """Test SymbolicMemory wrapper class."""

    def test_init_with_dict_sensors(self):
        """Initialize with dict sensor configs."""
        sensors = [
            {
                "path": "flood_depth",
                "name": "FLOOD",
                "bins": [
                    {"label": "SAFE", "max": 0.5},
                    {"label": "DANGER", "max": 99.0}
                ]
            }
        ]
        memory = SymbolicMemory(sensors, arousal_threshold=0.5)
        assert memory.arousal_threshold == 0.5

    def test_init_with_sensor_objects(self):
        """Initialize with Sensor objects directly."""
        sensors = [
            Sensor(
                path="flood",
                name="FLOOD",
                bins=[{"label": "LO", "max": 1.0}, {"label": "HI", "max": 99.0}]
            )
        ]
        memory = SymbolicMemory(sensors)
        assert memory.total_events == 0

    def test_novelty_first_logic(self):
        """First occurrence = 100% surprise (Novelty-First)."""
        sensors = [
            {"path": "flood", "name": "FLOOD", "bins": [
                {"label": "SAFE", "max": 0.5},
                {"label": "DANGER", "max": 99.0}
            ]}
        ]
        memory = SymbolicMemory(sensors)

        # First observation: NOVEL -> 100% surprise
        sig1, surprise1 = memory.observe({"flood": 2.0})
        assert surprise1 == 1.0, "First occurrence MUST be 100% surprise"

        # Second same observation: seen before -> lower surprise
        sig2, surprise2 = memory.observe({"flood": 2.0})
        assert surprise2 < 1.0, "Repeated observation should reduce surprise"
        assert sig1 == sig2, "Same world state should produce same signature"

    def test_novel_different_state(self):
        """New state signature should trigger 100% surprise again."""
        sensors = [
            {"path": "flood", "name": "FLOOD", "bins": [
                {"label": "SAFE", "max": 0.5},
                {"label": "DANGER", "max": 99.0}
            ]}
        ]
        memory = SymbolicMemory(sensors)

        # First state
        sig1, _ = memory.observe({"flood": 2.0})  # DANGER

        # Different state (new bin)
        sig2, surprise2 = memory.observe({"flood": 0.3})  # SAFE
        assert surprise2 == 1.0, "New signature MUST be 100% surprise"
        assert sig1 != sig2, "Different bins should produce different signatures"

    def test_get_trace(self):
        """Get last observation trace."""
        sensors = [
            {"path": "flood", "name": "FLOOD", "bins": [
                {"label": "LO", "max": 1.0},
                {"label": "HI", "max": 99.0}
            ]}
        ]
        memory = SymbolicMemory(sensors)
        memory.observe({"flood": 5.0})

        trace = memory.get_trace()
        assert trace is not None
        assert "signature" in trace
        assert "is_novel" in trace
        assert trace["is_novel"] is True

    def test_get_trace_history(self):
        """Get full trace history."""
        sensors = [
            {"path": "x", "name": "X", "bins": [
                {"label": "A", "max": 5.0},
                {"label": "B", "max": 99.0}
            ]}
        ]
        memory = SymbolicMemory(sensors)

        memory.observe({"x": 1.0})
        memory.observe({"x": 10.0})
        memory.observe({"x": 2.0})

        history = memory.get_trace_history()
        assert len(history) == 3

    def test_explain(self):
        """Human-readable explanation."""
        sensors = [
            {"path": "flood", "name": "FLOOD", "bins": [
                {"label": "SAFE", "max": 0.5},
                {"label": "DANGER", "max": 99.0}
            ]}
        ]
        memory = SymbolicMemory(sensors)
        memory.observe({"flood": 2.0})

        explanation = memory.explain()
        assert "FLOOD" in explanation or "Signature" in explanation

    def test_determine_system(self):
        """Determine cognitive system based on surprise."""
        sensors = [
            {"path": "x", "name": "X", "bins": [{"label": "A", "max": 99.0}]}
        ]
        memory = SymbolicMemory(sensors, arousal_threshold=0.5)

        # High surprise -> System 2
        assert memory.determine_system(0.8) == "SYSTEM_2"

        # Low surprise -> System 1
        assert memory.determine_system(0.3) == "SYSTEM_1"

    def test_frequency_map_property(self):
        """Access internal frequency map."""
        sensors = [
            {"path": "x", "name": "X", "bins": [
                {"label": "A", "max": 5.0},
                {"label": "B", "max": 99.0}
            ]}
        ]
        memory = SymbolicMemory(sensors)

        memory.observe({"x": 1.0})  # A
        memory.observe({"x": 1.0})  # A again
        memory.observe({"x": 10.0})  # B

        freq_map = memory.frequency_map
        assert len(freq_map) == 2
        assert memory.total_events == 3

    def test_reset(self):
        """Reset memory state."""
        sensors = [
            {"path": "x", "name": "X", "bins": [{"label": "A", "max": 99.0}]}
        ]
        memory = SymbolicMemory(sensors)

        memory.observe({"x": 1.0})
        memory.observe({"x": 2.0})
        assert memory.total_events == 2

        memory.reset()
        assert memory.total_events == 0
        assert len(memory.frequency_map) == 0

    def test_invalid_sensor_type_raises(self):
        """Invalid sensor type should raise TypeError."""
        with pytest.raises(TypeError):
            SymbolicMemory(["not_a_dict_or_sensor"])


class TestMultiSensorMemory:
    """Test SymbolicMemory with multiple sensors."""

    def test_multi_sensor_signature(self):
        """Multiple sensors produce combined signature."""
        sensors = [
            {"path": "flood", "name": "FLOOD", "bins": [
                {"label": "SAFE", "max": 0.5},
                {"label": "DANGER", "max": 99.0}
            ]},
            {"path": "panic", "name": "PANIC", "bins": [
                {"label": "CALM", "max": 0.3},
                {"label": "HIGH", "max": 1.0}
            ]}
        ]
        memory = SymbolicMemory(sensors)

        sig1, _ = memory.observe({"flood": 0.3, "panic": 0.1})  # SAFE, CALM
        sig2, _ = memory.observe({"flood": 0.3, "panic": 0.5})  # SAFE, HIGH

        assert sig1 != sig2, "Different sensor combinations should have different signatures"

    def test_multi_sensor_same_state(self):
        """Same multi-sensor state produces same signature."""
        sensors = [
            {"path": "flood", "name": "FLOOD", "bins": [
                {"label": "LO", "max": 1.0},
                {"label": "HI", "max": 99.0}
            ]},
            {"path": "subsidy", "name": "SUBSIDY", "bins": [
                {"label": "LO", "max": 0.5},
                {"label": "HI", "max": 1.0}
            ]}
        ]
        memory = SymbolicMemory(sensors)

        sig1, _ = memory.observe({"flood": 0.5, "subsidy": 0.3})
        sig2, _ = memory.observe({"flood": 0.5, "subsidy": 0.3})

        assert sig1 == sig2
