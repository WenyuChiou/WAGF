"""
Tests for BehavioralTheory Protocol and Theory Registry (Phase 3).

Validates:
  1. PMTTheory satisfies BehavioralTheory Protocol
  2. PMTTheory produces identical results to module-level rules
  3. TheoryRegistry works correctly
  4. Example theories (TPB, Irrigation) satisfy the protocol
"""

import sys
from pathlib import Path

import pytest

# Setup path
ROOT_DIR = Path(__file__).parent.parent.parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

ANALYSIS_DIR = Path(__file__).parent.parent / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from validation.theories.base import BehavioralTheory
from validation.theories.pmt import (
    PMTTheory,
    PMT_OWNER_RULES,
    PMT_RENTER_RULES,
    _is_sensible_action,
)
from validation.theories.registry import TheoryRegistry, get_default_registry
from validation.theories.examples import TPBTheory, IrrigationWSATheory


# =============================================================================
# Protocol Compliance Tests
# =============================================================================

class TestBehavioralTheoryProtocol:
    """Test that implementations satisfy the BehavioralTheory Protocol."""

    def test_pmt_satisfies_protocol(self):
        pmt = PMTTheory()
        assert isinstance(pmt, BehavioralTheory)

    def test_tpb_satisfies_protocol(self):
        tpb = TPBTheory()
        assert isinstance(tpb, BehavioralTheory)

    def test_irrigation_satisfies_protocol(self):
        irr = IrrigationWSATheory()
        assert isinstance(irr, BehavioralTheory)


# =============================================================================
# PMTTheory Tests
# =============================================================================

class TestPMTTheory:
    """Test PMTTheory produces identical results to module-level rules."""

    def setup_method(self):
        self.pmt = PMTTheory()

    def test_name(self):
        assert self.pmt.name == "pmt"

    def test_dimensions(self):
        assert self.pmt.dimensions == ["TP", "CP"]

    def test_agent_types(self):
        assert self.pmt.agent_types == ["owner", "renter"]

    def test_owner_rules_match(self):
        """PMTTheory.get_coherent_actions must match PMT_OWNER_RULES exactly."""
        for (tp, cp), expected_actions in PMT_OWNER_RULES.items():
            result = self.pmt.get_coherent_actions({"TP": tp, "CP": cp}, "owner")
            assert result == expected_actions, (
                f"Mismatch for owner ({tp}, {cp}): got {result}, expected {expected_actions}"
            )

    def test_renter_rules_match(self):
        """PMTTheory.get_coherent_actions must match PMT_RENTER_RULES exactly."""
        for (tp, cp), expected_actions in PMT_RENTER_RULES.items():
            result = self.pmt.get_coherent_actions({"TP": tp, "CP": cp}, "renter")
            assert result == expected_actions, (
                f"Mismatch for renter ({tp}, {cp}): got {result}, expected {expected_actions}"
            )

    def test_extract_constructs_nested(self):
        trace = {
            "skill_proposal": {
                "reasoning": {"TP_LABEL": "VH", "CP_LABEL": "H"}
            }
        }
        result = self.pmt.extract_constructs(trace)
        assert result == {"TP": "VH", "CP": "H"}

    def test_extract_constructs_top_level(self):
        trace = {"TP_LABEL": "M", "CP_LABEL": "L"}
        result = self.pmt.extract_constructs(trace)
        assert result == {"TP": "M", "CP": "L"}

    def test_extract_constructs_missing(self):
        trace = {}
        result = self.pmt.extract_constructs(trace)
        assert result == {"TP": "UNKNOWN", "CP": "UNKNOWN"}

    def test_is_sensible_matches_free_function(self):
        """PMTTheory.is_sensible_action must match _is_sensible_action."""
        test_cases = [
            ({"TP": "VH", "CP": "VH"}, "buy_insurance", "owner"),
            ({"TP": "VH", "CP": "VH"}, "do_nothing", "owner"),
            ({"TP": "L", "CP": "L"}, "elevate", "owner"),
            ({"TP": "H", "CP": "VL"}, "buyout", "renter"),
        ]
        for levels, action, agent_type in test_cases:
            expected = _is_sensible_action(levels["TP"], levels["CP"], action, agent_type)
            result = self.pmt.is_sensible_action(levels, action, agent_type)
            assert result == expected, (
                f"Mismatch for ({levels}, {action}, {agent_type})"
            )

    def test_custom_rules(self):
        """PMTTheory accepts custom rules."""
        custom_rules = {("H", "H"): ["custom_action"]}
        pmt = PMTTheory(owner_rules=custom_rules)
        assert pmt.get_coherent_actions({"TP": "H", "CP": "H"}, "owner") == ["custom_action"]

    def test_unknown_combination_returns_empty(self):
        """Unknown construct combination returns empty list."""
        result = self.pmt.get_coherent_actions({"TP": "X", "CP": "Y"}, "owner")
        assert result == []


# =============================================================================
# TheoryRegistry Tests
# =============================================================================

class TestTheoryRegistry:
    """Test TheoryRegistry operations."""

    def test_register_and_get(self):
        registry = TheoryRegistry()
        pmt = PMTTheory()
        registry.register(pmt)
        assert registry.get("pmt") is pmt

    def test_get_nonexistent(self):
        registry = TheoryRegistry()
        assert registry.get("nonexistent") is None

    def test_first_registered_is_default(self):
        registry = TheoryRegistry()
        pmt = PMTTheory()
        registry.register(pmt)
        assert registry.default is pmt

    def test_set_default(self):
        registry = TheoryRegistry()
        pmt = PMTTheory()
        tpb = TPBTheory()
        registry.register(pmt)
        registry.register(tpb)
        assert registry.default is pmt

        registry.set_default("tpb")
        assert registry.default is tpb

    def test_set_default_invalid(self):
        registry = TheoryRegistry()
        with pytest.raises(ValueError):
            registry.set_default("nonexistent")

    def test_names(self):
        registry = TheoryRegistry()
        registry.register(PMTTheory())
        registry.register(TPBTheory())
        assert set(registry.names) == {"pmt", "tpb"}

    def test_default_registry_has_pmt(self):
        registry = get_default_registry()
        assert registry.get("pmt") is not None
        assert registry.default.name == "pmt"


# =============================================================================
# Example Theory Tests
# =============================================================================

class TestTPBTheory:
    """Test TPBTheory example."""

    def test_name(self):
        assert TPBTheory().name == "tpb"

    def test_dimensions(self):
        assert TPBTheory().dimensions == ["attitude", "norm", "pbc"]

    def test_high_all_returns_actions(self):
        tpb = TPBTheory()
        actions = tpb.get_coherent_actions(
            {"attitude": "VH", "norm": "VH", "pbc": "VH"}, "individual"
        )
        assert "adopt" in actions

    def test_low_pbc_limits_actions(self):
        tpb = TPBTheory()
        actions = tpb.get_coherent_actions(
            {"attitude": "VH", "norm": "VH", "pbc": "VL"}, "individual"
        )
        assert "do_nothing" in actions


class TestIrrigationWSATheory:
    """Test IrrigationWSATheory example."""

    def test_name(self):
        assert IrrigationWSATheory().name == "irrigation_wsa"

    def test_dimensions(self):
        assert IrrigationWSATheory().dimensions == ["WSA", "ACA"]

    def test_25_cells(self):
        assert len(IrrigationWSATheory.RULES) == 25

    def test_high_scarcity_high_capacity(self):
        irr = IrrigationWSATheory()
        actions = irr.get_coherent_actions({"WSA": "VH", "ACA": "VH"}, "farmer")
        assert "decrease_large" in actions

    def test_low_scarcity_high_capacity(self):
        irr = IrrigationWSATheory()
        actions = irr.get_coherent_actions({"WSA": "VL", "ACA": "VH"}, "farmer")
        assert "increase_large" in actions
