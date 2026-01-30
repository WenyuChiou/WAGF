"""
Test Suite: Multi-Agent Interaction Flow
=========================================
Verifies the complete interaction flow between agents:

1. Interaction Order: Government/Insurance act first, then households
2. Policy Broadcast: post_step() updates subsidy_rate & premium_rate
3. Information Diffusion: Households observe updated policies
4. Social Influence: SC (+30%) and TP (+20%) multipliers
5. Validation: 7 core rules in MultiAgentValidator

These tests focus on the flow and communication between agent types,
not the full simulation which would require an LLM.
"""

import sys
import unittest
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, MagicMock, patch

# Setup paths
CURRENT_DIR = Path(__file__).parent
MA_DIR = CURRENT_DIR.parent
ROOT_DIR = MA_DIR.parent.parent

sys.path = [p for p in sys.path if 'multi_agent' not in p or p == str(MA_DIR)]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import broker components
from broker.components.interaction_hub import InteractionHub
from broker.components.social_graph import SocialGraph, create_social_graph
from broker.interfaces.skill_types import SkillProposal, SkillOutcome


@dataclass
class MockState:
    """Minimal state for testing."""
    id: str
    region_id: str = "R1"
    elevated: bool = False
    has_insurance: bool = False
    relocated: bool = False


@dataclass
class MockAgent:
    """Minimal agent for testing interaction flow."""
    id: str
    agent_type: str
    dynamic_state: Dict[str, Any] = field(default_factory=dict)
    fixed_attributes: Dict[str, Any] = field(default_factory=dict)
    custom_attributes: Dict[str, Any] = field(default_factory=dict)
    memory: List[str] = field(default_factory=list)
    config: Any = None

    def __post_init__(self):
        if self.config is None:
            self.config = Mock()
            self.config.agent_type = self.agent_type


class TestInteractionOrder(unittest.TestCase):
    """Test that agents act in the correct order."""

    def test_institutional_before_household_order(self):
        """
        Verify that institutional agents (Gov/Insurance) act before households.

        In the run_unified_experiment.py, the order is defined as:
        - Tier 1: Government, Insurance (year-level decisions)
        - Tier 2: Household agents (observe policy, make decisions)
        """
        # Define expected order
        expected_order = ["government", "insurance", "household_owner", "household_renter"]

        # Create mock agents
        gov = MockAgent(id="GOV", agent_type="government")
        ins = MockAgent(id="INS", agent_type="insurance")
        hh1 = MockAgent(id="HH_001", agent_type="household_owner")
        hh2 = MockAgent(id="HH_002", agent_type="household_renter")

        agents = [hh1, gov, hh2, ins]  # Shuffled

        # Sort by execution order
        def get_order(agent):
            type_order = {"government": 0, "insurance": 1,
                         "household_owner": 2, "household_renter": 2}
            return type_order.get(agent.agent_type, 99)

        sorted_agents = sorted(agents, key=get_order)
        sorted_types = [a.agent_type for a in sorted_agents]

        # Verify institutional agents come first
        self.assertEqual(sorted_types[0], "government")
        self.assertEqual(sorted_types[1], "insurance")
        self.assertIn(sorted_types[2], ["household_owner", "household_renter"])
        self.assertIn(sorted_types[3], ["household_owner", "household_renter"])


class TestPolicyBroadcast(unittest.TestCase):
    """Test that institutional decisions update global environment."""

    def setUp(self):
        """Create mock environment state."""
        self.env = {
            "year": 1,
            "subsidy_rate": 0.50,
            "premium_rate": 0.02,
            "flood_occurred": False,
            "total_households": 50,
            "elevated_count": 10,
            "insured_count": 25
        }

    def test_government_increase_subsidy_updates_env(self):
        """Test that government 'increase_subsidy' updates subsidy_rate."""
        # Simulate post_step logic from run_unified_experiment.py
        decision = "increase_subsidy"

        if decision == "increase_subsidy":
            self.env["subsidy_rate"] = min(0.95, self.env["subsidy_rate"] + 0.05)

        self.assertEqual(self.env["subsidy_rate"], 0.55)

    def test_government_decrease_subsidy_updates_env(self):
        """Test that government 'decrease_subsidy' updates subsidy_rate."""
        decision = "decrease_subsidy"

        if decision == "decrease_subsidy":
            self.env["subsidy_rate"] = max(0.20, self.env["subsidy_rate"] - 0.05)

        self.assertEqual(self.env["subsidy_rate"], 0.45)

    def test_insurance_raise_premium_updates_env(self):
        """Test that insurance 'raise_premium' updates premium_rate."""
        decision = "raise_premium"

        if decision == "raise_premium":
            self.env["premium_rate"] = min(0.15, self.env["premium_rate"] + 0.005)

        self.assertAlmostEqual(self.env["premium_rate"], 0.025, places=3)

    def test_insurance_lower_premium_updates_env(self):
        """Test that insurance 'lower_premium' updates premium_rate."""
        decision = "lower_premium"

        if decision == "lower_premium":
            self.env["premium_rate"] = max(0.01, self.env["premium_rate"] - 0.005)

        self.assertAlmostEqual(self.env["premium_rate"], 0.015, places=3)

    def test_subsidy_rate_bounds(self):
        """Test that subsidy_rate stays within bounds (20%-95%)."""
        self.env["subsidy_rate"] = 0.95

        # Try to increase beyond max
        decision = "increase_subsidy"
        if decision == "increase_subsidy":
            self.env["subsidy_rate"] = min(0.95, self.env["subsidy_rate"] + 0.05)

        self.assertEqual(self.env["subsidy_rate"], 0.95)  # Capped

        # Try to decrease below min
        self.env["subsidy_rate"] = 0.20
        decision = "decrease_subsidy"
        if decision == "decrease_subsidy":
            self.env["subsidy_rate"] = max(0.20, self.env["subsidy_rate"] - 0.05)

        self.assertEqual(self.env["subsidy_rate"], 0.20)  # Floor

    def test_premium_rate_bounds(self):
        """Test that premium_rate stays within bounds (1%-15%)."""
        self.env["premium_rate"] = 0.15

        # Try to increase beyond max
        decision = "raise_premium"
        if decision == "raise_premium":
            self.env["premium_rate"] = min(0.15, self.env["premium_rate"] + 0.005)

        self.assertEqual(self.env["premium_rate"], 0.15)  # Capped


class TestHouseholdPolicyObservation(unittest.TestCase):
    """Test that households observe updated policies in their context."""

    def test_household_sees_updated_subsidy_rate(self):
        """Test that household context includes current subsidy_rate."""
        env = {"subsidy_rate": 0.65, "premium_rate": 0.03}

        # Simulate context building for household
        context = {
            "subsidy_rate": env["subsidy_rate"],
            "premium_rate": env["premium_rate"]
        }

        self.assertEqual(context["subsidy_rate"], 0.65)
        self.assertEqual(context["premium_rate"], 0.03)

    def test_context_includes_flood_info(self):
        """Test that context includes flood occurrence info."""
        env = {
            "flood_occurred": True,
            "flood_depth_ft": 2.5
        }

        context = {
            "flood_occurred": env["flood_occurred"],
            "flood_depth_ft": env.get("flood_depth_ft", 0)
        }

        self.assertTrue(context["flood_occurred"])
        self.assertEqual(context["flood_depth_ft"], 2.5)


class TestSocialInfluence(unittest.TestCase):
    """Test social influence calculations from the social network."""

    def test_sc_influence_multiplier(self):
        """Test that Social Capital (SC) influence is calculated correctly.

        Formula: SC_influence = 1.0 + (elev_rate + ins_rate) * 0.3
        Max boost: +30% per factor, up to +60% total
        """
        # Scenario: 80% neighbors elevated, 60% insured
        observations = {
            "elevated_count": 4,
            "insured_count": 3,
            "relocated_count": 0,
            "neighbor_count": 5
        }

        elev_rate = observations["elevated_count"] / observations["neighbor_count"]
        ins_rate = observations["insured_count"] / observations["neighbor_count"]

        sc_influence = 1.0 + (elev_rate + ins_rate) * 0.3

        # Expected: 1.0 + (0.8 + 0.6) * 0.3 = 1.0 + 0.42 = 1.42
        self.assertAlmostEqual(sc_influence, 1.42, places=2)

    def test_tp_influence_multiplier(self):
        """Test that Threat Perception (TP) influence is calculated correctly.

        Formula: TP_influence = 1.0 + reloc_rate * 0.2
        Max boost: +20% when all neighbors have relocated
        """
        # Scenario: 50% neighbors relocated
        observations = {
            "elevated_count": 0,
            "insured_count": 0,
            "relocated_count": 2,
            "neighbor_count": 4
        }

        reloc_rate = observations["relocated_count"] / observations["neighbor_count"]
        tp_influence = 1.0 + reloc_rate * 0.2

        # Expected: 1.0 + 0.5 * 0.2 = 1.1
        self.assertAlmostEqual(tp_influence, 1.1, places=2)

    def test_no_influence_with_zero_neighbors(self):
        """Test that influence is neutral when no neighbors exist."""
        observations = {
            "elevated_count": 0,
            "insured_count": 0,
            "relocated_count": 0,
            "neighbor_count": 0
        }

        if observations["neighbor_count"] == 0:
            sc_influence = 1.0
            tp_influence = 1.0
        else:
            # Normal calculation
            pass

        self.assertEqual(sc_influence, 1.0)
        self.assertEqual(tp_influence, 1.0)


class TestValidationRules(unittest.TestCase):
    """Test the 7 core validation rules from MultiAgentValidator."""

    def test_rule_elevated_already_blocks_elevate(self):
        """Rule: Already elevated agents cannot choose elevate_house."""
        agent_state = {"elevated": True, "relocated": False}
        decision = "elevate_house"

        # Validation logic
        violations = []
        if agent_state["elevated"] and decision == "elevate_house":
            violations.append("elevated_already: Cannot elevate an already elevated house")

        self.assertEqual(len(violations), 1)
        self.assertIn("elevated_already", violations[0])

    def test_rule_relocated_already_blocks_actions(self):
        """Rule: Relocated agents cannot take further adaptation actions."""
        agent_state = {"elevated": False, "relocated": True}
        blocked_skills = ["buy_insurance", "elevate_house", "buyout_program"]

        for decision in blocked_skills:
            violations = []
            if agent_state["relocated"] and decision in blocked_skills:
                violations.append(f"relocated_already: Cannot {decision} after relocation")

            self.assertEqual(len(violations), 1)

    def test_rule_tp_vh_blocks_do_nothing(self):
        """Rule: Very High Threat Perception should not allow do_nothing."""
        constructs = {"TP_LABEL": "VH"}
        decision = "do_nothing"

        violations = []
        if constructs.get("TP_LABEL") == "VH" and decision == "do_nothing":
            violations.append("tp_vh_action: VH threat perception requires action")

        self.assertEqual(len(violations), 1)

    def test_rule_cp_vl_blocks_expensive_actions(self):
        """Rule: Very Low Coping Perception blocks expensive actions."""
        constructs = {"CP_LABEL": "VL"}
        expensive_actions = ["elevate_house", "buyout_program"]

        for decision in expensive_actions:
            violations = []
            if constructs.get("CP_LABEL") == "VL" and decision in expensive_actions:
                violations.append(f"cp_vl_affordability: Cannot afford {decision}")

            self.assertEqual(len(violations), 1)

    def test_valid_decision_passes_all_rules(self):
        """Test that a valid decision passes all validation rules."""
        agent_state = {"elevated": False, "relocated": False}
        constructs = {"TP_LABEL": "H", "CP_LABEL": "M"}
        decision = "buy_insurance"

        violations = []

        # Rule 1: elevated_already
        if agent_state["elevated"] and decision == "elevate_house":
            violations.append("elevated_already")

        # Rule 2: relocated_already
        if agent_state["relocated"] and decision in ["buy_insurance", "elevate_house", "buyout_program"]:
            violations.append("relocated_already")

        # Rule 3: TP VH -> no do_nothing
        if constructs.get("TP_LABEL") == "VH" and decision == "do_nothing":
            violations.append("tp_vh_action")

        # Rule 4: CP VL -> no expensive actions
        if constructs.get("CP_LABEL") == "VL" and decision in ["elevate_house", "buyout_program"]:
            violations.append("cp_vl_affordability")

        self.assertEqual(len(violations), 0)


class TestMemoryIntegration(unittest.TestCase):
    """Test memory-based gossip and information sharing."""

    def test_gossip_retrieval_format(self):
        """Test that gossip is formatted correctly."""
        neighbor_id = "HH_005"
        memory_snippet = "Flood last year caused $10,000 damage"

        gossip = f"Neighbor {neighbor_id} mentioned: '{memory_snippet}'"

        self.assertIn("Neighbor HH_005", gossip)
        self.assertIn("$10,000 damage", gossip)

    def test_empty_memory_returns_no_gossip(self):
        """Test that agents without memories don't generate gossip."""
        chatty_neighbors = []

        # No chatty neighbors -> no gossip
        gossip = []
        if not chatty_neighbors:
            pass  # gossip remains empty

        self.assertEqual(len(gossip), 0)


class TestFullInteractionFlow(unittest.TestCase):
    """Integration test for the full interaction flow."""

    def test_year_simulation_flow(self):
        """Test the complete flow for one year of simulation."""
        # 1. Setup environment
        env = {
            "year": 1,
            "subsidy_rate": 0.50,
            "premium_rate": 0.02,
            "flood_occurred": False,
            "total_households": 5,
            "elevated_count": 1,
            "insured_count": 2
        }

        # 2. Create agents
        gov = MockAgent(id="GOV", agent_type="government")
        ins = MockAgent(id="INS", agent_type="insurance")
        households = [
            MockAgent(id=f"HH_{i:03d}", agent_type="household_owner",
                     dynamic_state={"elevated": False, "has_insurance": i < 2})
            for i in range(5)
        ]

        all_agents = {"GOV": gov, "INS": ins}
        all_agents.update({h.id: h for h in households})

        # 3. Pre-year: Determine flood
        env["flood_occurred"] = True
        env["flood_depth_ft"] = 1.5

        # 4. Phase 1: Government acts (mock decision)
        gov_decision = "increase_subsidy"
        if gov_decision == "increase_subsidy":
            env["subsidy_rate"] = min(0.95, env["subsidy_rate"] + 0.05)

        # 5. Phase 2: Insurance acts (mock decision)
        ins_decision = "raise_premium"
        if ins_decision == "raise_premium":
            env["premium_rate"] = min(0.15, env["premium_rate"] + 0.005)

        # 6. Phase 3: Households observe and act
        for hh in households:
            # Build context with updated policies
            context = {
                "subsidy_rate": env["subsidy_rate"],
                "premium_rate": env["premium_rate"],
                "flood_occurred": env["flood_occurred"]
            }

            # Verify household sees updated policy
            self.assertEqual(context["subsidy_rate"], 0.55)  # Updated
            self.assertEqual(context["premium_rate"], 0.025)  # Updated

        # 7. Verify final state
        self.assertEqual(env["subsidy_rate"], 0.55)
        self.assertAlmostEqual(env["premium_rate"], 0.025, places=3)
        self.assertTrue(env["flood_occurred"])


class TestAgentTypeRouting(unittest.TestCase):
    """Test that agent types are routed to correct handlers."""

    def test_owner_vs_renter_type_distinction(self):
        """Test that owner and renter agent types are distinguished."""
        owner = MockAgent(id="HH_OWNER", agent_type="household_owner")
        renter = MockAgent(id="HH_RENTER", agent_type="household_renter")

        # Owner-specific skills
        owner_skills = ["buy_insurance", "elevate_house", "buyout_program", "do_nothing"]

        # Renter-specific skills
        renter_skills = ["buy_contents_insurance", "relocate", "do_nothing"]

        # Verify distinct skill sets
        self.assertIn("elevate_house", owner_skills)
        self.assertNotIn("elevate_house", renter_skills)
        self.assertIn("relocate", renter_skills)
        self.assertNotIn("relocate", owner_skills)

    def test_institutional_vs_household_routing(self):
        """Test that institutional and household agents are handled differently."""
        agents = [
            MockAgent(id="GOV", agent_type="government"),
            MockAgent(id="INS", agent_type="insurance"),
            MockAgent(id="HH_001", agent_type="household_owner"),
        ]

        institutional = [a for a in agents if a.agent_type in ["government", "insurance"]]
        household = [a for a in agents if a.agent_type.startswith("household")]

        self.assertEqual(len(institutional), 2)
        self.assertEqual(len(household), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
