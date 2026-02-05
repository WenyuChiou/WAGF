"""
Test Suite: Mini Social Network
================================
Simplified social network tests for quick validation.

Uses 5-10 agents with 2-3 neighbors each in simple topologies
(ring, star) for fast testing of:
1. Neighbor list symmetry
2. Gossip retrieval
3. Influence calculation

Target: All tests complete in <5 seconds.
"""

import sys
import unittest
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Set, List

# Setup paths
CURRENT_DIR = Path(__file__).parent
MA_DIR = CURRENT_DIR.parent
ROOT_DIR = MA_DIR.parent.parent

sys.path = [p for p in sys.path if 'multi_agent' not in p or p == str(MA_DIR)]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import the actual SocialNetwork from the MA environment
from examples.multi_agent.flood.environment.social_network import SocialNetwork, create_network_from_agents


@dataclass
class MockAgentState:
    """Minimal agent state for testing."""
    id: str
    region_id: str = "default"
    elevated: bool = False
    has_insurance: bool = False
    relocated: bool = False


@dataclass
class MockHouseholdAgent:
    """Minimal household agent for testing."""
    state: MockAgentState


class MiniSocialNetwork(SocialNetwork):
    """
    Simplified social network for fast testing.

    Features:
    - 2-3 neighbors max (instead of 5)
    - No region weighting
    - Simple ring or star topology options
    """

    def __init__(self, max_neighbors: int = 2):
        super().__init__()
        self.max_neighbors = max_neighbors
        self.same_region_weight = 0.0  # No region weighting

    def build_ring_topology(self, agents: List[MockHouseholdAgent]):
        """
        Build a simple ring topology where each agent connects
        to their immediate neighbors in a circular pattern.

        Agent 0 <-> Agent 1 <-> Agent 2 <-> ... <-> Agent N <-> Agent 0
        """
        n = len(agents)
        for i, agent in enumerate(agents):
            aid = agent.state.id
            neighbors = set()

            # Connect to previous and next agent (circular)
            prev_idx = (i - 1) % n
            next_idx = (i + 1) % n

            if prev_idx != i:
                neighbors.add(agents[prev_idx].state.id)
            if next_idx != i and next_idx != prev_idx:
                neighbors.add(agents[next_idx].state.id)

            self.connections[aid] = neighbors

    def build_star_topology(self, agents: List[MockHouseholdAgent]):
        """
        Build a star topology with first agent as hub.

        Hub (Agent 0) connects to all others.
        Peripheral agents only connect to hub.
        """
        if not agents:
            return

        hub = agents[0]
        hub_id = hub.state.id

        # Hub connects to all others
        self.connections[hub_id] = {a.state.id for a in agents[1:]}

        # Others connect only to hub
        for agent in agents[1:]:
            self.connections[agent.state.id] = {hub_id}


class TestMiniNetworkTopologies(unittest.TestCase):
    """Test basic network topologies."""

    def setUp(self):
        """Create a set of 5 mock agents."""
        self.agents = [
            MockHouseholdAgent(MockAgentState(id=f"HH_{i:03d}", region_id="R1"))
            for i in range(5)
        ]
        self.agents_dict = {a.state.id: a for a in self.agents}

    def test_ring_topology_creation(self):
        """Test that ring topology creates correct neighbors."""
        network = MiniSocialNetwork(max_neighbors=2)
        network.build_ring_topology(self.agents)

        # Each agent should have exactly 2 neighbors
        for agent in self.agents:
            neighbors = network.get_neighbors(agent.state.id)
            self.assertEqual(len(neighbors), 2,
                           f"Agent {agent.state.id} should have 2 neighbors")

    def test_ring_topology_symmetry(self):
        """Test that ring topology is symmetric (undirected)."""
        network = MiniSocialNetwork(max_neighbors=2)
        network.build_ring_topology(self.agents)

        for agent in self.agents:
            aid = agent.state.id
            neighbors = network.get_neighbors(aid)

            for neighbor_id in neighbors:
                neighbor_neighbors = network.get_neighbors(neighbor_id)
                self.assertIn(aid, neighbor_neighbors,
                            f"Symmetry broken: {aid} -> {neighbor_id} but not reverse")

    def test_star_topology_creation(self):
        """Test that star topology creates hub-spoke structure."""
        network = MiniSocialNetwork()
        network.build_star_topology(self.agents)

        hub_id = self.agents[0].state.id
        hub_neighbors = network.get_neighbors(hub_id)

        # Hub should connect to all others (4 neighbors)
        self.assertEqual(len(hub_neighbors), 4)

        # Peripheral agents should only connect to hub
        for agent in self.agents[1:]:
            neighbors = network.get_neighbors(agent.state.id)
            self.assertEqual(len(neighbors), 1)
            self.assertIn(hub_id, neighbors)

    def test_star_topology_hub_connectivity(self):
        """Test that all peripherals are reachable from hub."""
        network = MiniSocialNetwork()
        network.build_star_topology(self.agents)

        hub_id = self.agents[0].state.id
        peripheral_ids = {a.state.id for a in self.agents[1:]}
        hub_neighbors = network.get_neighbors(hub_id)

        self.assertEqual(hub_neighbors, peripheral_ids)


class TestMiniNetworkObservation(unittest.TestCase):
    """Test neighbor observation functionality."""

    def setUp(self):
        """Create 5 agents with varied states."""
        self.agents = [
            MockHouseholdAgent(MockAgentState(
                id=f"HH_{i:03d}",
                region_id="R1",
                elevated=(i % 2 == 0),  # 0, 2, 4 elevated
                has_insurance=(i < 3),   # 0, 1, 2 insured
                relocated=(i == 4)       # Only 4 relocated
            ))
            for i in range(5)
        ]
        self.agents_dict = {a.state.id: a for a in self.agents}

    def test_observe_neighbors_counts(self):
        """Test that observation returns correct counts."""
        network = MiniSocialNetwork(max_neighbors=2)
        network.build_ring_topology(self.agents)

        # Agent 0's neighbors are 1 and 4
        observations = network.observe_neighbors("HH_000", self.agents_dict)

        self.assertIn("elevated_count", observations)
        self.assertIn("insured_count", observations)
        self.assertIn("relocated_count", observations)
        self.assertIn("neighbor_count", observations)

        self.assertEqual(observations["neighbor_count"], 2)

    def test_observe_specific_neighbor_states(self):
        """Test observation with known neighbor states."""
        network = MiniSocialNetwork()
        network.build_star_topology(self.agents)

        # Hub (HH_000) sees all peripherals: 1,2,3,4
        # Elevated: 2, 4 (2 agents)
        # Insured: 1, 2 (2 agents)
        # Relocated: 4 (1 agent)

        obs = network.observe_neighbors("HH_000", self.agents_dict)

        self.assertEqual(obs["elevated_count"], 2)
        self.assertEqual(obs["insured_count"], 2)
        self.assertEqual(obs["relocated_count"], 1)
        self.assertEqual(obs["neighbor_count"], 4)


class TestMiniNetworkInfluence(unittest.TestCase):
    """Test social influence calculations."""

    def test_influence_with_no_neighbors(self):
        """Test influence calculation with empty network."""
        network = MiniSocialNetwork()

        observations = {
            "elevated_count": 0,
            "insured_count": 0,
            "relocated_count": 0,
            "neighbor_count": 0
        }

        influence = network.calculate_social_influence(observations)

        # With no neighbors, influence should be neutral (1.0)
        self.assertEqual(influence["tp_influence"], 1.0)
        self.assertEqual(influence["sc_influence"], 1.0)

    def test_influence_with_adapted_neighbors(self):
        """Test that adapted neighbors increase SC influence."""
        network = MiniSocialNetwork()

        # All neighbors are adapted
        observations = {
            "elevated_count": 4,
            "insured_count": 4,
            "relocated_count": 0,
            "neighbor_count": 4
        }

        influence = network.calculate_social_influence(observations)

        # SC should be boosted (100% elevated + 100% insured = +60%)
        # Formula: 1.0 + (elev_rate + ins_rate) * 0.3 = 1.0 + 2.0 * 0.3 = 1.6
        self.assertGreater(influence["sc_influence"], 1.0)
        self.assertAlmostEqual(influence["sc_influence"], 1.6, places=2)

    def test_influence_with_relocated_neighbors(self):
        """Test that relocated neighbors increase TP influence."""
        network = MiniSocialNetwork()

        # All neighbors have relocated
        observations = {
            "elevated_count": 0,
            "insured_count": 0,
            "relocated_count": 4,
            "neighbor_count": 4
        }

        influence = network.calculate_social_influence(observations)

        # TP should be boosted (100% relocated = +20%)
        # Formula: 1.0 + reloc_rate * 0.2 = 1.0 + 1.0 * 0.2 = 1.2
        self.assertGreater(influence["tp_influence"], 1.0)
        self.assertAlmostEqual(influence["tp_influence"], 1.2, places=2)

    def test_influence_mixed_neighbors(self):
        """Test influence with mixed neighbor states."""
        network = MiniSocialNetwork()

        # 50% elevated, 25% insured, 25% relocated
        observations = {
            "elevated_count": 2,
            "insured_count": 1,
            "relocated_count": 1,
            "neighbor_count": 4
        }

        influence = network.calculate_social_influence(observations)

        # SC: 1.0 + (0.5 + 0.25) * 0.3 = 1.225
        # TP: 1.0 + 0.25 * 0.2 = 1.05
        self.assertAlmostEqual(influence["sc_influence"], 1.225, places=2)
        self.assertAlmostEqual(influence["tp_influence"], 1.05, places=2)

    def test_adaptation_exposure_metric(self):
        """Test that adaptation_exposure is calculated correctly."""
        network = MiniSocialNetwork()

        observations = {
            "elevated_count": 3,
            "insured_count": 2,
            "relocated_count": 0,
            "neighbor_count": 5
        }

        influence = network.calculate_social_influence(observations)

        # adaptation_exposure = elev_rate + ins_rate = 0.6 + 0.4 = 1.0
        expected_exposure = (3/5) + (2/5)
        self.assertAlmostEqual(influence["adaptation_exposure"], expected_exposure, places=2)


class TestOriginalSocialNetworkWithMiniData(unittest.TestCase):
    """Test the original SocialNetwork class with mini dataset."""

    def setUp(self):
        """Create a small set of agents across 2 regions."""
        self.agents = []

        # Region 1: 3 agents
        for i in range(3):
            self.agents.append(MockHouseholdAgent(
                MockAgentState(id=f"R1_HH_{i}", region_id="Region1")
            ))

        # Region 2: 3 agents
        for i in range(3):
            self.agents.append(MockHouseholdAgent(
                MockAgentState(id=f"R2_HH_{i}", region_id="Region2")
            ))

        self.agents_dict = {a.state.id: a for a in self.agents}

    def test_original_network_builds(self):
        """Test that original network builds successfully with small data."""
        network = create_network_from_agents(self.agents, seed=42)

        # All agents should have connections
        for agent in self.agents:
            neighbors = network.get_neighbors(agent.state.id)
            self.assertIsInstance(neighbors, set)
            self.assertGreater(len(neighbors), 0,
                             f"Agent {agent.state.id} should have neighbors")

    def test_original_network_region_bias(self):
        """Test that original network has region bias (70% same region)."""
        network = SocialNetwork(max_neighbors=3, same_region_weight=0.7)
        network.build_network(self.agents, seed=42)

        # Check that agents tend to have more same-region neighbors
        same_region_counts = []
        for agent in self.agents:
            aid = agent.state.id
            region = agent.state.region_id
            neighbors = network.get_neighbors(aid)

            same_region_neighbors = sum(
                1 for nid in neighbors
                if self.agents_dict[nid].state.region_id == region
            )
            same_region_counts.append(same_region_neighbors / len(neighbors) if neighbors else 0)

        # Average same-region ratio should be > 0.5 (biased toward same region)
        avg_same_region = sum(same_region_counts) / len(same_region_counts)
        self.assertGreater(avg_same_region, 0.5,
                          f"Expected region bias, got {avg_same_region:.2%} same-region neighbors")


class TestPerformance(unittest.TestCase):
    """Test that operations complete quickly."""

    def test_mini_network_performance(self):
        """Test that mini network operations are fast (<1s)."""
        import time

        # Create 10 agents
        agents = [
            MockHouseholdAgent(MockAgentState(id=f"HH_{i:03d}"))
            for i in range(10)
        ]
        agents_dict = {a.state.id: a for a in agents}

        start = time.time()

        # Build network
        network = MiniSocialNetwork(max_neighbors=3)
        network.build_ring_topology(agents)

        # Observe all neighbors
        for agent in agents:
            obs = network.observe_neighbors(agent.state.id, agents_dict)
            _ = network.calculate_social_influence(obs)

        elapsed = time.time() - start

        self.assertLess(elapsed, 1.0, f"Mini network ops took {elapsed:.3f}s (should be <1s)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
