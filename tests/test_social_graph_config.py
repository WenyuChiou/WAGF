"""
Tests for Social Graph Configuration by Agent Type (Task-043).

Tests the SocialGraphSpec, AGENT_SOCIAL_SPECS, get_social_spec,
and configure_social_graph_for_agent functions.
"""
import pytest
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from broker.components.social.config import (
    SocialGraphSpec,
    AGENT_SOCIAL_SPECS,
    DEFAULT_SOCIAL_SPEC,
    get_social_spec,
    configure_social_graph_for_agent,
    get_spec_for_type_key,
    list_all_type_keys,
    _normalize_tenure,
)


# ==============================================================================
# Test Fixtures and Helpers
# ==============================================================================

@dataclass
class MockAgent:
    """Mock agent for testing."""
    id: str
    agent_type: str = "household"
    is_mg: bool = False
    tenure: str = "owner"
    has_insurance: bool = False

    def get_state(self, key: str, default: Any = None) -> Any:
        if key == "has_insurance":
            return self.has_insurance
        return default


class MockSpatialGraph:
    """Mock spatial graph for testing."""

    def __init__(self, positions: Dict[str, Tuple[int, int]], default_radius: float = 2.0):
        self.positions = positions
        self.default_radius = default_radius
        self.agent_ids = list(positions.keys())

    def get_neighbors(self, agent_id: str) -> List[str]:
        """Get neighbors using default radius."""
        return self.get_neighbors_within_radius(agent_id, self.default_radius)

    def get_neighbors_within_radius(self, agent_id: str, radius: float) -> List[str]:
        """Get neighbors within a given radius."""
        if agent_id not in self.positions:
            return []

        pos = self.positions[agent_id]
        neighbors = []

        for other_id, other_pos in self.positions.items():
            if other_id == agent_id:
                continue

            # Calculate euclidean distance
            dx = pos[0] - other_pos[0]
            dy = pos[1] - other_pos[1]
            dist = (dx**2 + dy**2) ** 0.5

            if dist <= radius:
                neighbors.append(other_id)

        return neighbors


class MockGlobalGraph:
    """Mock global graph for testing."""

    def __init__(self, agent_ids: List[str]):
        self.agent_ids = agent_ids

    def get_neighbors(self, agent_id: str) -> List[str]:
        return [a for a in self.agent_ids if a != agent_id]


# ==============================================================================
# Test SocialGraphSpec
# ==============================================================================

class TestSocialGraphSpec:
    """Tests for SocialGraphSpec dataclass."""

    def test_create_spatial_spec(self):
        """Test creating a spatial graph spec."""
        spec = SocialGraphSpec(graph_type="spatial", radius=2)
        assert spec.graph_type == "spatial"
        assert spec.radius == 2
        assert spec.filter_fn is None
        assert spec.max_connections == 0

    def test_create_global_spec(self):
        """Test creating a global graph spec."""
        spec = SocialGraphSpec(graph_type="global")
        assert spec.graph_type == "global"
        assert spec.radius == 2  # Default

    def test_create_filtered_global_spec(self):
        """Test creating a filtered global spec."""
        spec = SocialGraphSpec(
            graph_type="filtered_global",
            filter_fn="has_insurance"
        )
        assert spec.graph_type == "filtered_global"
        assert spec.filter_fn == "has_insurance"

    def test_create_with_max_connections(self):
        """Test creating spec with max connections limit."""
        spec = SocialGraphSpec(
            graph_type="spatial",
            radius=3,
            max_connections=5
        )
        assert spec.max_connections == 5

    def test_invalid_graph_type_raises(self):
        """Test that invalid graph type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid graph_type"):
            SocialGraphSpec(graph_type="invalid_type")

    def test_valid_graph_types(self):
        """Test all valid graph types can be created."""
        for gtype in ["spatial", "global", "filtered_global", "random"]:
            spec = SocialGraphSpec(graph_type=gtype)
            assert spec.graph_type == gtype


# ==============================================================================
# Test AGENT_SOCIAL_SPECS Dictionary
# ==============================================================================

class TestAgentSocialSpecs:
    """Tests for AGENT_SOCIAL_SPECS pre-defined specs."""

    def test_nmg_owner_has_radius_2(self):
        """Test that NMG owners have spatial radius of 2."""
        spec = AGENT_SOCIAL_SPECS["household_nmg_owner"]
        assert spec.graph_type == "spatial"
        assert spec.radius == 2

    def test_nmg_renter_has_radius_2(self):
        """Test that NMG renters have spatial radius of 2."""
        spec = AGENT_SOCIAL_SPECS["household_nmg_renter"]
        assert spec.graph_type == "spatial"
        assert spec.radius == 2

    def test_mg_owner_has_radius_1(self):
        """Test that MG owners have smaller spatial radius of 1."""
        spec = AGENT_SOCIAL_SPECS["household_mg_owner"]
        assert spec.graph_type == "spatial"
        assert spec.radius == 1

    def test_mg_renter_has_radius_1(self):
        """Test that MG renters have smaller spatial radius of 1."""
        spec = AGENT_SOCIAL_SPECS["household_mg_renter"]
        assert spec.graph_type == "spatial"
        assert spec.radius == 1

    def test_government_has_global_view(self):
        """Test that government agents have global view."""
        spec = AGENT_SOCIAL_SPECS["government"]
        assert spec.graph_type == "global"

    def test_insurance_has_filtered_global(self):
        """Test that insurance agents have filtered global view."""
        spec = AGENT_SOCIAL_SPECS["insurance"]
        assert spec.graph_type == "filtered_global"
        assert spec.filter_fn == "has_insurance"

    def test_all_specs_are_valid(self):
        """Test all pre-defined specs are valid SocialGraphSpec instances."""
        for key, spec in AGENT_SOCIAL_SPECS.items():
            assert isinstance(spec, SocialGraphSpec), f"Invalid spec for {key}"
            assert spec.graph_type in {"spatial", "global", "filtered_global", "random"}


# ==============================================================================
# Test get_social_spec Function
# ==============================================================================

class TestGetSocialSpec:
    """Tests for get_social_spec function."""

    def test_nmg_owner_gets_radius_2(self):
        """NMG owners have larger network (radius=2)."""
        agent = MockAgent(id="H1", agent_type="household", is_mg=False, tenure="owner")
        spec = get_social_spec(agent)

        assert spec.graph_type == "spatial"
        assert spec.radius == 2

    def test_mg_owner_gets_radius_1(self):
        """MG owners have smaller network (radius=1)."""
        agent = MockAgent(id="H2", agent_type="household", is_mg=True, tenure="owner")
        spec = get_social_spec(agent)

        assert spec.graph_type == "spatial"
        assert spec.radius == 1

    def test_nmg_renter_gets_radius_2(self):
        """NMG renters have larger network (radius=2)."""
        agent = MockAgent(id="H3", agent_type="household", is_mg=False, tenure="renter")
        spec = get_social_spec(agent)

        assert spec.graph_type == "spatial"
        assert spec.radius == 2

    def test_mg_renter_gets_radius_1(self):
        """MG renters have smaller network (radius=1)."""
        agent = MockAgent(id="H4", agent_type="household", is_mg=True, tenure="renter")
        spec = get_social_spec(agent)

        assert spec.graph_type == "spatial"
        assert spec.radius == 1

    def test_government_gets_global(self):
        """Government sees all agents (global)."""
        agent = MockAgent(id="G1", agent_type="government")
        spec = get_social_spec(agent)

        assert spec.graph_type == "global"

    def test_insurance_gets_filtered_global(self):
        """Insurance sees only policyholders (filtered_global)."""
        agent = MockAgent(id="I1", agent_type="insurance")
        spec = get_social_spec(agent)

        assert spec.graph_type == "filtered_global"
        assert spec.filter_fn == "has_insurance"

    def test_spec_composition_from_attributes(self):
        """Test correct key building from agent attributes."""
        # Test various attribute combinations
        test_cases = [
            # (is_mg, tenure, expected_radius)
            (False, "owner", 2),   # NMG owner -> radius 2
            (False, "renter", 2),  # NMG renter -> radius 2
            (True, "owner", 1),    # MG owner -> radius 1
            (True, "renter", 1),   # MG renter -> radius 1
        ]

        for is_mg, tenure, expected_radius in test_cases:
            agent = MockAgent(
                id=f"H_{is_mg}_{tenure}",
                agent_type="household",
                is_mg=is_mg,
                tenure=tenure
            )
            spec = get_social_spec(agent)

            assert spec.radius == expected_radius, (
                f"Expected radius {expected_radius} for is_mg={is_mg}, tenure={tenure}, "
                f"got {spec.radius}"
            )

    def test_dict_agent(self):
        """Test with agent as dictionary."""
        agent_dict = {
            "id": "H1",
            "agent_type": "household",
            "is_mg": False,
            "tenure": "owner",
        }
        spec = get_social_spec(agent_dict)

        assert spec.graph_type == "spatial"
        assert spec.radius == 2

    def test_dict_agent_mg(self):
        """Test dict agent with MG status."""
        agent_dict = {
            "id": "H2",
            "agent_type": "household",
            "is_mg": True,
            "tenure": "renter",
        }
        spec = get_social_spec(agent_dict)

        assert spec.graph_type == "spatial"
        assert spec.radius == 1

    def test_dict_agent_government(self):
        """Test dict agent for government."""
        agent_dict = {"id": "G1", "agent_type": "government"}
        spec = get_social_spec(agent_dict)

        assert spec.graph_type == "global"

    def test_unknown_agent_type_uses_default(self):
        """Test that unknown agent type uses default spec."""
        agent = MockAgent(id="X1", agent_type="unknown_type")
        spec = get_social_spec(agent)

        assert spec == DEFAULT_SOCIAL_SPEC
        assert spec.graph_type == "spatial"
        assert spec.radius == 2

    def test_missing_attributes_use_defaults(self):
        """Test agent with missing attributes uses defaults."""
        # Minimal object with no attributes
        class MinimalAgent:
            pass

        agent = MinimalAgent()
        spec = get_social_spec(agent)

        # Should default to household_nmg_owner
        assert spec.graph_type == "spatial"
        assert spec.radius == 2


# ==============================================================================
# Test configure_social_graph_for_agent Function
# ==============================================================================

class TestConfigureSocialGraphForAgent:
    """Tests for configure_social_graph_for_agent function."""

    def test_spatial_graph_returns_neighbors_within_radius(self):
        """Test spatial graph returns neighbors within spec radius."""
        # Create a spatial graph with positions
        positions = {
            "H1": (0, 0),   # Target agent
            "H2": (1, 0),   # Distance 1 - within radius 2
            "H3": (1, 1),   # Distance ~1.4 - within radius 2
            "H4": (3, 0),   # Distance 3 - outside radius 2
            "H5": (10, 10), # Distance ~14 - outside radius 2
        }
        graph = MockSpatialGraph(positions)

        agent = MockAgent(id="H1", is_mg=False, tenure="owner")
        all_agents = {
            "H1": agent,
            "H2": MockAgent(id="H2"),
            "H3": MockAgent(id="H3"),
            "H4": MockAgent(id="H4"),
            "H5": MockAgent(id="H5"),
        }

        neighbors = configure_social_graph_for_agent(graph, agent, all_agents)

        assert "H2" in neighbors
        assert "H3" in neighbors
        assert "H4" not in neighbors
        assert "H5" not in neighbors

    def test_spatial_graph_mg_smaller_radius(self):
        """Test MG agents have smaller radius."""
        positions = {
            "H1": (0, 0),   # Target MG agent
            "H2": (1, 0),   # Distance 1 - within radius 1
            "H3": (1, 1),   # Distance ~1.4 - outside radius 1
            "H4": (2, 0),   # Distance 2 - outside radius 1
        }
        graph = MockSpatialGraph(positions)

        # MG agent should only see H2 (within radius 1)
        agent = MockAgent(id="H1", is_mg=True, tenure="owner")
        all_agents = {aid: MockAgent(id=aid) for aid in positions.keys()}

        neighbors = configure_social_graph_for_agent(graph, agent, all_agents)

        assert "H2" in neighbors
        assert "H3" not in neighbors
        assert "H4" not in neighbors

    def test_global_graph_returns_all_others(self):
        """Test global graph returns all other agents."""
        agent_ids = ["G1", "H1", "H2", "H3", "I1"]
        graph = MockGlobalGraph(agent_ids)

        government = MockAgent(id="G1", agent_type="government")
        all_agents = {aid: MockAgent(id=aid) for aid in agent_ids}

        neighbors = configure_social_graph_for_agent(graph, government, all_agents)

        # Government should see all other agents
        assert set(neighbors) == {"H1", "H2", "H3", "I1"}
        assert "G1" not in neighbors

    def test_insurance_sees_only_policyholders(self):
        """Insurance filtered view - only sees agents with has_insurance=True."""
        agent_ids = ["I1", "H1", "H2", "H3", "H4"]
        graph = MockGlobalGraph(agent_ids)

        insurance = MockAgent(id="I1", agent_type="insurance")

        # H1 and H3 have insurance, H2 and H4 do not
        all_agents = {
            "I1": insurance,
            "H1": MockAgent(id="H1", has_insurance=True),
            "H2": MockAgent(id="H2", has_insurance=False),
            "H3": MockAgent(id="H3", has_insurance=True),
            "H4": MockAgent(id="H4", has_insurance=False),
        }

        neighbors = configure_social_graph_for_agent(graph, insurance, all_agents)

        assert "H1" in neighbors
        assert "H3" in neighbors
        assert "H2" not in neighbors
        assert "H4" not in neighbors
        assert "I1" not in neighbors

    def test_filtered_global_with_dict_agents(self):
        """Test filtered global works with dict agents."""
        graph = MockGlobalGraph(["I1", "H1", "H2"])

        insurance = {"id": "I1", "agent_type": "insurance"}
        all_agents = {
            "I1": insurance,
            "H1": {"id": "H1", "has_insurance": True},
            "H2": {"id": "H2", "has_insurance": False},
        }

        neighbors = configure_social_graph_for_agent(graph, insurance, all_agents)

        assert neighbors == ["H1"]

    def test_filtered_global_with_dynamic_state(self):
        """Test filtered global works with dynamic_state nested attribute."""
        graph = MockGlobalGraph(["I1", "H1", "H2"])

        insurance = {"id": "I1", "agent_type": "insurance"}
        all_agents = {
            "I1": insurance,
            "H1": {"id": "H1", "dynamic_state": {"has_insurance": True}},
            "H2": {"id": "H2", "dynamic_state": {"has_insurance": False}},
        }

        neighbors = configure_social_graph_for_agent(graph, insurance, all_agents)

        assert neighbors == ["H1"]

    def test_list_of_agents(self):
        """Test with list of agents instead of dict."""
        positions = {"H1": (0, 0), "H2": (1, 0), "H3": (10, 10)}
        graph = MockSpatialGraph(positions)

        agent = MockAgent(id="H1", is_mg=False, tenure="owner")
        all_agents = [
            MockAgent(id="H1"),
            MockAgent(id="H2"),
            MockAgent(id="H3"),
        ]

        neighbors = configure_social_graph_for_agent(graph, agent, all_agents)

        assert "H2" in neighbors
        assert "H3" not in neighbors


# ==============================================================================
# Test Utility Functions
# ==============================================================================

class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_get_spec_for_type_key(self):
        """Test getting spec by type key directly."""
        spec = get_spec_for_type_key("household_nmg_owner")
        assert spec is not None
        assert spec.radius == 2

        spec = get_spec_for_type_key("government")
        assert spec is not None
        assert spec.graph_type == "global"

    def test_get_spec_for_type_key_nonexistent(self):
        """Test getting spec for nonexistent key returns None."""
        spec = get_spec_for_type_key("nonexistent_key")
        assert spec is None

    def test_list_all_type_keys(self):
        """Test listing all defined type keys."""
        keys = list_all_type_keys()

        assert "household_nmg_owner" in keys
        assert "household_nmg_renter" in keys
        assert "household_mg_owner" in keys
        assert "household_mg_renter" in keys
        assert "government" in keys
        assert "insurance" in keys

    def test_normalize_tenure_owner(self):
        """Test tenure normalization for owner."""
        assert _normalize_tenure("owner") == "owner"
        assert _normalize_tenure("Owner") == "owner"
        assert _normalize_tenure("OWN") == "owner"
        assert _normalize_tenure("o") == "owner"

    def test_normalize_tenure_renter(self):
        """Test tenure normalization for renter."""
        assert _normalize_tenure("renter") == "renter"
        assert _normalize_tenure("Renter") == "renter"
        assert _normalize_tenure("RENT") == "renter"
        assert _normalize_tenure("r") == "renter"

    def test_normalize_tenure_defaults_to_owner(self):
        """Test unknown tenure defaults to owner."""
        assert _normalize_tenure(None) == "owner"
        assert _normalize_tenure("unknown") == "owner"


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_flow_nmg_spatial(self):
        """Test full flow for NMG household with spatial graph."""
        # Setup
        positions = {
            "H1": (0, 0),
            "H2": (1, 0),
            "H3": (2, 0),
            "H4": (5, 0),
        }
        graph = MockSpatialGraph(positions)

        agent = MockAgent(id="H1", is_mg=False, tenure="owner")
        all_agents = {aid: MockAgent(id=aid) for aid in positions.keys()}

        # Get spec and configure graph
        spec = get_social_spec(agent)
        neighbors = configure_social_graph_for_agent(graph, agent, all_agents)

        # Verify
        assert spec.graph_type == "spatial"
        assert spec.radius == 2
        assert "H2" in neighbors
        assert "H3" in neighbors
        assert "H4" not in neighbors

    def test_full_flow_mg_spatial(self):
        """Test full flow for MG household with smaller network."""
        positions = {
            "H1": (0, 0),
            "H2": (1, 0),
            "H3": (2, 0),
        }
        graph = MockSpatialGraph(positions)

        agent = MockAgent(id="H1", is_mg=True, tenure="owner")
        all_agents = {aid: MockAgent(id=aid) for aid in positions.keys()}

        spec = get_social_spec(agent)
        neighbors = configure_social_graph_for_agent(graph, agent, all_agents)

        assert spec.radius == 1
        assert "H2" in neighbors
        assert "H3" not in neighbors  # Distance 2, outside radius 1

    def test_full_flow_government_global(self):
        """Test full flow for government with global view."""
        agent_ids = ["G1", "H1", "H2", "H3", "I1"]
        graph = MockGlobalGraph(agent_ids)

        government = MockAgent(id="G1", agent_type="government")
        all_agents = {aid: MockAgent(id=aid) for aid in agent_ids}

        spec = get_social_spec(government)
        neighbors = configure_social_graph_for_agent(graph, government, all_agents)

        assert spec.graph_type == "global"
        assert len(neighbors) == 4  # All except self

    def test_full_flow_insurance_filtered(self):
        """Test full flow for insurance with filtered view."""
        agent_ids = ["I1", "H1", "H2", "H3"]
        graph = MockGlobalGraph(agent_ids)

        insurance = MockAgent(id="I1", agent_type="insurance")
        all_agents = {
            "I1": insurance,
            "H1": MockAgent(id="H1", has_insurance=True),
            "H2": MockAgent(id="H2", has_insurance=False),
            "H3": MockAgent(id="H3", has_insurance=True),
        }

        spec = get_social_spec(insurance)
        neighbors = configure_social_graph_for_agent(graph, insurance, all_agents)

        assert spec.graph_type == "filtered_global"
        assert spec.filter_fn == "has_insurance"
        assert set(neighbors) == {"H1", "H3"}
