"""
Memory V4 Integration Test - Phase 12 of Integration Test Suite.
Task-038: Verify HouseholdAgent._init_memory_v4() correctly uses SDK's SymbolicMemory.

Tests:
- MV4-01: Init symbolic memory
- MV4-02: Sensors configured
- MV4-03: Arousal threshold
- MV4-04: Memory in agent context
- MV4-05: Surprise across years
"""
import pytest
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cognitive_governance.v1_prototype.memory.symbolic import SymbolicMemory
from examples.multi_agent.ma_agents.household import HouseholdAgent


class TestMemoryV4Initialization:
    """Test V4 memory initialization via HouseholdAgent."""

    @pytest.fixture
    def household_agent(self):
        """Create a household agent."""
        return HouseholdAgent(
            agent_id="test_h1",
            mg=False,
            tenure="Owner",
            income=60000,
            property_value=250000
        )

    @pytest.fixture
    def symbolic_config(self):
        """Config for symbolic memory with flood sensors."""
        return {
            "engine": "symbolic",
            "sensors": [
                {
                    "path": "flood_depth_m",
                    "name": "FLOOD",
                    "bins": [
                        {"label": "SAFE", "max": 0.3},
                        {"label": "MINOR", "max": 1.0},
                        {"label": "MODERATE", "max": 2.0},
                        {"label": "SEVERE", "max": 99.0}
                    ]
                },
                {
                    "path": "panic_level",
                    "name": "PANIC",
                    "bins": [
                        {"label": "CALM", "max": 0.3},
                        {"label": "CONCERNED", "max": 0.6},
                        {"label": "PANICKED", "max": 1.0}
                    ]
                }
            ],
            "arousal_threshold": 0.5
        }

    def test_mv4_01_init_symbolic_memory(self, household_agent, symbolic_config):
        """MV4-01: _init_memory_v4 should return SymbolicMemory."""
        memory = household_agent._init_memory_v4(symbolic_config)

        assert memory is not None
        assert isinstance(memory, SymbolicMemory)

    def test_mv4_01_non_symbolic_returns_none(self, household_agent):
        """Non-symbolic engine should return None."""
        config = {"engine": "window"}  # Not symbolic

        memory = household_agent._init_memory_v4(config)

        assert memory is None

    def test_mv4_02_sensors_configured(self, household_agent, symbolic_config):
        """MV4-02: Sensors should quantize flood_depth correctly."""
        memory = household_agent._init_memory_v4(symbolic_config)

        # Test different flood depths
        test_cases = [
            ({"flood_depth_m": 0.1, "panic_level": 0.1}, "FLOOD:SAFE"),
            ({"flood_depth_m": 0.5, "panic_level": 0.1}, "FLOOD:MINOR"),
            ({"flood_depth_m": 1.5, "panic_level": 0.1}, "FLOOD:MODERATE"),
            ({"flood_depth_m": 3.0, "panic_level": 0.1}, "FLOOD:SEVERE"),
        ]

        for world_state, expected_flood_label in test_cases:
            sig, surprise = memory.observe(world_state)
            trace = memory.get_trace()

            assert trace is not None
            quantized = trace.get("quantized_sensors", {})
            flood_label = quantized.get("FLOOD", "")
            assert flood_label == expected_flood_label, \
                f"Expected {expected_flood_label} for depth {world_state['flood_depth_m']}, got {flood_label}"

            # Reset for next test
            memory.reset()

    def test_mv4_03_arousal_threshold(self, household_agent, symbolic_config):
        """MV4-03: System switching should use configured arousal threshold."""
        memory = household_agent._init_memory_v4(symbolic_config)

        assert memory.arousal_threshold == 0.5

        # First observation = 100% surprise = System 2
        sig, surprise = memory.observe({"flood_depth_m": 2.0, "panic_level": 0.5})
        system = memory.determine_system(surprise)

        assert surprise == 1.0
        assert system == "SYSTEM_2"

    def test_mv4_03_different_threshold(self, household_agent):
        """Different arousal threshold should affect switching."""
        config = {
            "engine": "symbolic",
            "sensors": [{"path": "val", "name": "V", "bins": [{"label": "L", "max": 0.5}, {"label": "H", "max": 99}]}],
            "arousal_threshold": 0.8  # Higher threshold
        }
        memory = household_agent._init_memory_v4(config)

        assert memory.arousal_threshold == 0.8


class TestMemoryV4InContext:
    """Test memory integration in agent context."""

    @pytest.fixture
    def memory_with_observations(self):
        """Create memory with some observations."""
        sensors = [
            {
                "path": "flood_depth_m",
                "name": "FLOOD",
                "bins": [
                    {"label": "SAFE", "max": 0.3},
                    {"label": "DANGER", "max": 99.0}
                ]
            }
        ]
        memory = SymbolicMemory(sensors, arousal_threshold=0.5)
        return memory

    def test_mv4_04_trace_in_context(self, memory_with_observations):
        """MV4-04: Trace should be available after observe()."""
        memory = memory_with_observations

        # Observe
        sig, surprise = memory.observe({"flood_depth_m": 1.5})

        # Get trace
        trace = memory.get_trace()

        assert trace is not None
        assert "quantized_sensors" in trace
        assert "signature" in trace
        assert "surprise" in trace
        assert "is_novel" in trace

        # Context integration pattern
        agent_context = {
            "memory": {
                "symbolic_trace": trace,
                "current_signature": sig,
                "surprise_level": surprise,
                "system": memory.determine_system(surprise)
            }
        }

        assert agent_context["memory"]["surprise_level"] == 1.0
        assert agent_context["memory"]["system"] == "SYSTEM_2"


class TestMemoryV4AcrossYears:
    """Test surprise detection across multiple years."""

    @pytest.fixture
    def flood_memory(self):
        """Create memory for flood tracking."""
        sensors = [
            {
                "path": "flood_depth_m",
                "name": "FLOOD",
                "bins": [
                    {"label": "NONE", "max": 0.0},
                    {"label": "MINOR", "max": 1.0},
                    {"label": "MAJOR", "max": 99.0}
                ]
            }
        ]
        return SymbolicMemory(sensors, arousal_threshold=0.5)

    def test_mv4_05_surprise_across_years(self, flood_memory):
        """MV4-05: Repeated states should have lower surprise."""
        memory = flood_memory

        # Year 1: First major flood - novel
        sig1, surprise1 = memory.observe({"flood_depth_m": 2.0})
        assert surprise1 == 1.0, "First observation should be 100% surprise"

        # Year 2: Another major flood - same bin, lower surprise
        sig2, surprise2 = memory.observe({"flood_depth_m": 2.5})
        assert sig2 == sig1, "Same bin should produce same signature"
        assert surprise2 < surprise1, "Repeated state should have lower surprise"

        # Year 3: Minor flood - different state, higher surprise
        sig3, surprise3 = memory.observe({"flood_depth_m": 0.5})
        assert sig3 != sig1, "Different bin should produce different signature"
        assert surprise3 == 1.0, "Novel state should be 100% surprise"

        # Year 4: Major flood again - now familiar
        sig4, surprise4 = memory.observe({"flood_depth_m": 3.0})
        assert sig4 == sig1
        assert surprise4 < surprise1, "State seen twice before should be less surprising"

    def test_multi_year_system_switching(self, flood_memory):
        """System should switch based on surprise across years."""
        memory = flood_memory
        systems = []

        # Simulate 5 years with same flood pattern
        for year in range(1, 6):
            _, surprise = memory.observe({"flood_depth_m": 2.0})
            system = memory.determine_system(surprise)
            systems.append(system)

        # First year: System 2 (novel)
        assert systems[0] == "SYSTEM_2"

        # Later years: May switch to System 1 as pattern becomes familiar
        # (depends on threshold and frequency calculation)

    def test_frequency_map_growth(self, flood_memory):
        """Frequency map should track all observed signatures."""
        memory = flood_memory

        # Observe different states
        memory.observe({"flood_depth_m": 0.0})   # NONE
        memory.observe({"flood_depth_m": 0.5})   # MINOR
        memory.observe({"flood_depth_m": 2.0})   # MAJOR
        memory.observe({"flood_depth_m": 2.0})   # MAJOR again

        # Should have 3 unique signatures
        assert len(memory.frequency_map) == 3

        # Total events should be 4
        assert memory.total_events == 4

    def test_trace_history(self, flood_memory):
        """Trace history should capture all observations."""
        memory = flood_memory

        # Make 3 observations
        memory.observe({"flood_depth_m": 0.0})
        memory.observe({"flood_depth_m": 1.5})
        memory.observe({"flood_depth_m": 3.0})

        # Get history
        history = memory.get_trace_history()

        assert len(history) == 3
        assert all("signature" in trace for trace in history)
        assert all("surprise" in trace for trace in history)


class TestMemoryV4ExplainAbility:
    """Test XAI/explainability features."""

    def test_explain_output(self):
        """explain() should return human-readable string."""
        sensors = [{"path": "flood", "name": "F", "bins": [{"label": "L", "max": 1}, {"label": "H", "max": 99}]}]
        memory = SymbolicMemory(sensors, arousal_threshold=0.5)

        memory.observe({"flood": 5.0})

        explanation = memory.explain()

        assert isinstance(explanation, str)
        assert len(explanation) > 0
        # Should contain some expected content
        assert "Signature" in explanation or "signature" in explanation.lower()


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
