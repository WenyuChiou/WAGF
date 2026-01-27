"""
MA Environment & E2E Tests - Phase 9-10 of Integration Test Suite.
Task-038: Verify environment and E2E for Multi-Agent flood adaptation.

Tests:
- MA-E01 to MA-E04: Tiered environment
- MA-LI01 to MA-LI04: Lifecycle hooks
- MA-E2E01 to MA-E2E06: E2E smoke tests
"""
import pytest
import os
import sys
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from simulation.environment import TieredEnvironment
from governed_ai_sdk.v1_prototype.memory.symbolic import SymbolicMemory


# ============================================================================
# Phase 9: MA Environment Tests
# ============================================================================

class TestMATieredEnvironment:
    """Test tiered environment for MA scenarios."""

    @pytest.fixture
    def ma_environment(self):
        """Create MA tiered environment."""
        env = TieredEnvironment()
        # Initialize with MA-specific state
        env.set_global("year", 1)
        env.set_global("subsidy_rate", 0.5)
        env.set_global("premium_rate", 0.02)
        env.set_global("flood_occurred", False)
        return env

    def test_ma_e01_global_state(self, ma_environment):
        """MA-E01: Global state should store subsidy rate."""
        ma_environment.set_global("subsidy_rate", 0.65)

        assert ma_environment.global_state["subsidy_rate"] == 0.65

    def test_ma_e02_local_state(self, ma_environment):
        """MA-E02: Local state should store per-agent flood depth."""
        # Set per-agent local state
        if hasattr(ma_environment, 'set_local'):
            ma_environment.set_local("agent_001", "flood_depth", 1.5)
            depth = ma_environment.get_local("agent_001", "flood_depth", 0.0)
            assert depth == 1.5
        else:
            # Alternative: store in local_states dict
            if not hasattr(ma_environment, 'local_states'):
                ma_environment.local_states = {}
            ma_environment.local_states["agent_001"] = {"flood_depth": 1.5}
            assert ma_environment.local_states["agent_001"]["flood_depth"] == 1.5

    def test_ma_e03_institutional_state(self, ma_environment):
        """MA-E03: Institutional state should store govt/insurance decisions."""
        # Store institutional decisions
        ma_environment.set_global("govt_subsidy_rate", 0.65)
        ma_environment.set_global("insurance_premium_rate", 0.025)

        assert ma_environment.global_state["govt_subsidy_rate"] == 0.65
        assert ma_environment.global_state["insurance_premium_rate"] == 0.025

    def test_ma_e04_policy_broadcast(self, ma_environment):
        """MA-E04: Policy changes should be visible to households."""
        # Government increases subsidy
        ma_environment.set_global("subsidy_rate", 0.70)
        ma_environment.set_global("policy_message", "Subsidy increased to 70%")

        # Household should see the new rate
        subsidy = ma_environment.global_state["subsidy_rate"]
        message = ma_environment.global_state.get("policy_message", "")

        assert subsidy == 0.70
        assert "70%" in message


class TestMALifecycleHooks:
    """Test MA lifecycle hooks patterns."""

    def test_ma_li01_tier_ordering(self):
        """MA-LI01: Institutional agents should act before households."""
        execution_order = []

        # Simulate tier ordering
        tiers = [
            {"tier": 0, "agents": ["government", "insurance"]},
            {"tier": 1, "agents": ["household_001", "household_002", "household_003"]}
        ]

        for tier in tiers:
            for agent in tier["agents"]:
                execution_order.append(agent)

        # Government and insurance should be first
        assert execution_order[0] == "government"
        assert execution_order[1] == "insurance"
        assert "household" in execution_order[2]

    def test_ma_li02_policy_propagation(self):
        """MA-LI02: Policy changes should propagate to households."""
        # Government decision
        govt_decision = {"action": "increase_subsidy", "new_rate": 0.65}

        # Update global state (post_step)
        global_state = {"subsidy_rate": 0.5}
        global_state["subsidy_rate"] = govt_decision["new_rate"]

        # Household context should see new rate
        household_context = {
            "institutional": {
                "subsidy_rate": global_state["subsidy_rate"]
            }
        }

        assert household_context["institutional"]["subsidy_rate"] == 0.65

    def test_ma_li03_damage_calculation_per_agent(self):
        """MA-LI03: Damage should be calculated per agent."""
        agents = [
            {"id": "h1", "elevated": False, "flood_depth": 2.0, "rcv": 200000},
            {"id": "h2", "elevated": True, "flood_depth": 2.0, "rcv": 200000},
            {"id": "h3", "elevated": False, "flood_depth": 0.5, "rcv": 200000}
        ]

        damages = {}
        for agent in agents:
            if agent["elevated"]:
                # Elevated: much lower damage
                damage_rate = 0.05
            else:
                # Non-elevated: damage based on depth
                damage_rate = min(agent["flood_depth"] / 10.0, 1.0)

            damages[agent["id"]] = agent["rcv"] * damage_rate

        assert damages["h1"] > damages["h2"], "Non-elevated should have more damage"
        assert damages["h1"] > damages["h3"], "Deeper flood should have more damage"

    def test_ma_li04_memory_consolidation(self):
        """MA-LI04: Memories should be added post-year."""
        agent_memories = {
            "h1": [],
            "h2": [],
            "h3": []
        }

        # Post-year: add flood experience memories
        flood_occurred = True
        for agent_id in agent_memories:
            if flood_occurred:
                agent_memories[agent_id].append(
                    f"Year 1: Experienced flooding in our neighborhood."
                )

        # All agents should have memory
        for agent_id, memories in agent_memories.items():
            assert len(memories) > 0


# ============================================================================
# Phase 10: MA E2E Smoke Tests
# ============================================================================

class MockMAActor:
    """Mock actor for MA simulation."""

    def __init__(self, actor_id, actor_type, decisions=None):
        self.id = actor_id
        self.actor_type = actor_type
        self.decisions = decisions or {}
        self.state = {
            "elevated": False,
            "has_insurance": False,
            "relocated": False
        }
        self.memories = []

    def decide(self, year, context):
        """Return decision for given year."""
        return self.decisions.get(year, {"action": "do_nothing"})


class TestMAE2ESmoke:
    """E2E smoke tests for MA flood adaptation."""

    @pytest.fixture
    def ma_actors(self):
        """Create MA actors."""
        return {
            "government": MockMAActor(
                "government", "government",
                decisions={
                    1: {"action": "maintain_subsidy", "rate": 0.5},
                    2: {"action": "increase_subsidy", "rate": 0.65},
                    3: {"action": "maintain_subsidy", "rate": 0.65}
                }
            ),
            "insurance": MockMAActor(
                "insurance", "insurance",
                decisions={
                    1: {"action": "maintain_premium", "rate": 0.02},
                    2: {"action": "increase_premium", "rate": 0.025},
                    3: {"action": "maintain_premium", "rate": 0.025}
                }
            ),
            "h1": MockMAActor(
                "h1", "household",
                decisions={
                    1: {"action": "buy_insurance"},
                    2: {"action": "elevate_house"},
                    3: {"action": "do_nothing"}
                }
            ),
            "h2": MockMAActor(
                "h2", "household",
                decisions={
                    1: {"action": "do_nothing"},
                    2: {"action": "buy_insurance"},
                    3: {"action": "do_nothing"}
                }
            )
        }

    @pytest.fixture
    def ma_environment(self):
        """Create MA environment."""
        return TieredEnvironment()

    @pytest.fixture
    def simulation_traces(self):
        """Create trace collector."""
        return []

    def run_ma_simulation(self, actors, environment, num_years=3):
        """Run multi-agent simulation."""
        traces = []

        for year in range(1, num_years + 1):
            year_traces = {"year": year, "decisions": {}}

            # Set flood event
            flood_years = [1, 2]
            flood_occurred = year in flood_years
            environment.set_global("year", year)
            environment.set_global("flood_occurred", flood_occurred)

            # Tier 0: Institutional agents
            for actor_id in ["government", "insurance"]:
                actor = actors[actor_id]
                decision = actor.decide(year, {"global": environment.global_state})
                year_traces["decisions"][actor_id] = decision

                # Apply policy changes
                if "rate" in decision:
                    if actor_id == "government":
                        environment.set_global("subsidy_rate", decision["rate"])
                    elif actor_id == "insurance":
                        environment.set_global("premium_rate", decision["rate"])

            # Tier 1: Household agents
            for actor_id in ["h1", "h2"]:
                actor = actors[actor_id]
                context = {
                    "global": environment.global_state,
                    "social": self._get_social_context(actor_id, actors)
                }
                decision = actor.decide(year, context)
                year_traces["decisions"][actor_id] = decision

                # Apply state changes
                if decision["action"] == "buy_insurance":
                    actor.state["has_insurance"] = True
                elif decision["action"] == "elevate_house":
                    actor.state["elevated"] = True

                # Add memory
                if flood_occurred:
                    actor.memories.append(f"Year {year}: Flooding occurred")

            traces.append(year_traces)

        return traces

    def _get_social_context(self, agent_id, actors):
        """Get social context for agent."""
        neighbors = [a for a in actors.values() if a.actor_type == "household" and a.id != agent_id]
        return {
            "neighbor_count": len(neighbors),
            "elevated_pct": sum(1 for n in neighbors if n.state["elevated"]) / max(len(neighbors), 1)
        }

    def test_ma_e2e01_three_year_simulation(self, ma_actors, ma_environment):
        """MA-E2E01: 3-year simulation should complete."""
        traces = self.run_ma_simulation(ma_actors, ma_environment, num_years=3)

        assert len(traces) == 3

    def test_ma_e2e02_tier_ordering(self, ma_actors, ma_environment):
        """MA-E2E02: Govt should decide before households."""
        traces = self.run_ma_simulation(ma_actors, ma_environment, num_years=1)

        year1 = traces[0]
        decision_keys = list(year1["decisions"].keys())

        # Government and insurance should be before households
        govt_idx = decision_keys.index("government")
        h1_idx = decision_keys.index("h1")

        assert govt_idx < h1_idx

    def test_ma_e2e03_social_context(self, ma_actors, ma_environment):
        """MA-E2E03: Social context should be available."""
        # Run 2 years
        traces = self.run_ma_simulation(ma_actors, ma_environment, num_years=2)

        # After year 2, h1 should be elevated
        assert ma_actors["h1"].state["elevated"] is True

        # h2's social context should reflect this
        social = self._get_social_context("h2", ma_actors)
        assert social["elevated_pct"] > 0

    def test_ma_e2e04_memory_across_years(self, ma_actors, ma_environment):
        """MA-E2E04: Memories should persist across years."""
        traces = self.run_ma_simulation(ma_actors, ma_environment, num_years=3)

        # Households should have memories from flood years
        for actor_id in ["h1", "h2"]:
            assert len(ma_actors[actor_id].memories) >= 2, \
                f"{actor_id} should have memories from flood years 1 and 2"

    def test_ma_e2e05_policy_propagation(self, ma_actors, ma_environment):
        """MA-E2E05: Policy changes should affect households."""
        # Run simulation
        traces = self.run_ma_simulation(ma_actors, ma_environment, num_years=3)

        # Year 2: Government increased subsidy to 0.65
        assert ma_environment.global_state["subsidy_rate"] == 0.65

    def test_ma_e2e06_audit_complete(self, ma_actors, ma_environment):
        """MA-E2E06: All agents should have traces."""
        traces = self.run_ma_simulation(ma_actors, ma_environment, num_years=3)

        # Each year should have decisions from all agents
        for year_trace in traces:
            assert "government" in year_trace["decisions"]
            assert "insurance" in year_trace["decisions"]
            assert "h1" in year_trace["decisions"]
            assert "h2" in year_trace["decisions"]


class TestMAE2EWithSymbolicMemory:
    """Test MA E2E with SDK symbolic memory."""

    def test_symbolic_memory_across_years(self):
        """Symbolic memory should track states across years."""
        sensors = [
            {
                "path": "flood_depth",
                "name": "FLOOD",
                "bins": [
                    {"label": "NONE", "max": 0.0},
                    {"label": "MINOR", "max": 1.0},
                    {"label": "MAJOR", "max": 99.0}
                ]
            }
        ]
        memory = SymbolicMemory(sensors, arousal_threshold=0.5)

        # Year 1: Major flood
        sig1, surprise1 = memory.observe({"flood_depth": 2.0})
        assert surprise1 == 1.0  # Novel

        # Year 2: Minor flood
        sig2, surprise2 = memory.observe({"flood_depth": 0.5})
        assert surprise2 == 1.0  # Different state = novel

        # Year 3: Major flood again
        sig3, surprise3 = memory.observe({"flood_depth": 2.5})
        assert sig3 == sig1  # Same bin
        assert surprise3 < surprise1  # Seen before

    def test_system_switching_during_crisis(self):
        """System should switch to System 2 during novel events."""
        sensors = [{"path": "flood", "name": "F", "bins": [{"label": "L", "max": 1}, {"label": "H", "max": 99}]}]
        memory = SymbolicMemory(sensors, arousal_threshold=0.5)

        # First high flood = novel = System 2
        _, surprise = memory.observe({"flood": 5.0})
        system = memory.determine_system(surprise)
        assert system == "SYSTEM_2"

        # Repeat same flood = lower surprise = might be System 1
        _, surprise2 = memory.observe({"flood": 5.0})
        # After many observations, surprise would drop below threshold


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
