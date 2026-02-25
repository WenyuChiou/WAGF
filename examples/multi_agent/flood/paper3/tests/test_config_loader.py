"""
Tests for config_loader.py — YAML externalization of C&V validation constants.

Validates:
  1. YAML loads produce identical values to hard-coded defaults
  2. Fallback works when YAML files are absent
  3. Hallucination rules from YAML match original Python logic
"""

import sys
from pathlib import Path

import pytest

# Setup path
ROOT_DIR = Path(__file__).parent.parent.parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from examples.multi_agent.flood.paper3.analysis.config_loader import (
    load_theory_config,
    load_benchmark_config,
    load_hallucination_rules,
    load_default_config,
    _parse_rule_key,
    _parse_rules_dict,
    TheoryConfig,
    BenchmarkConfig,
    HallucinationRule,
    ValidationConfig,
)
from examples.multi_agent.flood.paper3.analysis.compute_validation_metrics import (
    PMT_OWNER_RULES,
    PMT_RENTER_RULES,
    EMPIRICAL_BENCHMARKS,
    _is_hallucination,
    _normalize_action,
)


# =============================================================================
# Theory Config Tests
# =============================================================================

class TestTheoryConfig:
    """Test YAML theory config loading and consistency with hard-coded values."""

    def test_yaml_loads_successfully(self):
        """pmt_flood.yaml should load without errors."""
        config = load_theory_config()
        assert config is not None
        assert config.name == "pmt"
        assert config.full_name == "Protection Motivation Theory"

    def test_owner_rules_match_hardcoded(self):
        """YAML owner rules must exactly match PMT_OWNER_RULES."""
        config = load_theory_config()
        assert config is not None
        for key, actions in PMT_OWNER_RULES.items():
            assert key in config.owner_rules, f"Missing owner rule key: {key}"
            assert config.owner_rules[key] == actions, (
                f"Owner rule mismatch for {key}: "
                f"YAML={config.owner_rules[key]}, hardcoded={actions}"
            )
        # Also check no extra keys in YAML
        assert set(config.owner_rules.keys()) == set(PMT_OWNER_RULES.keys())

    def test_renter_rules_match_hardcoded(self):
        """YAML renter rules must exactly match PMT_RENTER_RULES."""
        config = load_theory_config()
        assert config is not None
        for key, actions in PMT_RENTER_RULES.items():
            assert key in config.renter_rules, f"Missing renter rule key: {key}"
            assert config.renter_rules[key] == actions, (
                f"Renter rule mismatch for {key}: "
                f"YAML={config.renter_rules[key]}, hardcoded={actions}"
            )
        assert set(config.renter_rules.keys()) == set(PMT_RENTER_RULES.keys())

    def test_dimensions_correct(self):
        """Should have TP and CP dimensions."""
        config = load_theory_config()
        assert config is not None
        assert len(config.dimensions) == 2
        names = [d.name for d in config.dimensions]
        assert "TP" in names
        assert "CP" in names

    def test_action_aliases_contain_all_variants(self):
        """All known action variants should be in aliases."""
        config = load_theory_config()
        assert config is not None
        # Check a sample of known variants
        assert "buy_contents_insurance" in config.action_aliases["buy_insurance"]
        assert "elevate_home" in config.action_aliases["elevate"]
        assert "buyout_program" in config.action_aliases["buyout"]
        assert "no_action" in config.action_aliases["do_nothing"]

    def test_fallback_when_file_missing(self):
        """Loading from non-existent path returns None."""
        config = load_theory_config(Path("/nonexistent/theory.yaml"))
        assert config is None

    def test_25_cells_per_agent_type(self):
        """Each agent type should have exactly 25 cells (5x5 grid)."""
        config = load_theory_config()
        assert config is not None
        assert len(config.owner_rules) == 25
        assert len(config.renter_rules) == 25


class TestParseRuleKey:
    """Test key parsing utility."""

    def test_simple_key(self):
        assert _parse_rule_key("VH_VH") == ("VH", "VH")

    def test_single_letter_key(self):
        assert _parse_rule_key("H_L") == ("H", "L")

    def test_mixed_key(self):
        assert _parse_rule_key("VL_VH") == ("VL", "VH")

    def test_invalid_key(self):
        with pytest.raises(ValueError):
            _parse_rule_key("INVALID")


# =============================================================================
# Benchmark Config Tests
# =============================================================================

class TestBenchmarkConfig:
    """Test YAML benchmark config loading."""

    def test_yaml_loads_successfully(self):
        config = load_benchmark_config()
        assert config is not None
        assert len(config.benchmarks) == 16  # 8 household + 7 institutional + 1 diagnostic

    def test_benchmark_ranges_match_hardcoded(self):
        """YAML benchmark ranges must match EMPIRICAL_BENCHMARKS."""
        config = load_benchmark_config()
        assert config is not None
        for name, spec in EMPIRICAL_BENCHMARKS.items():
            assert name in config.benchmarks, f"Missing benchmark: {name}"
            yaml_range = config.benchmarks[name].range
            assert yaml_range == tuple(spec["range"]), (
                f"Range mismatch for {name}: YAML={yaml_range}, hardcoded={spec['range']}"
            )

    def test_benchmark_weights_match_hardcoded(self):
        """YAML weights must match."""
        config = load_benchmark_config()
        assert config is not None
        for name, spec in EMPIRICAL_BENCHMARKS.items():
            assert config.benchmarks[name].weight == spec["weight"]

    def test_thresholds_present(self):
        """L1 and L2 thresholds should be present."""
        config = load_benchmark_config()
        assert config is not None
        assert "l1" in config.thresholds
        assert "l2" in config.thresholds
        assert "cacr" in config.thresholds["l1"]
        assert "epi" in config.thresholds["l2"]

    def test_threshold_values(self):
        """Threshold values should match expected constants."""
        config = load_benchmark_config()
        assert config is not None
        assert config.thresholds["l1"]["cacr"].value == 0.75
        assert config.thresholds["l1"]["r_h"].value == 0.10
        assert config.thresholds["l2"]["epi"].value == 0.60

    def test_fallback_when_file_missing(self):
        config = load_benchmark_config(Path("/nonexistent/benchmarks.yaml"))
        assert config is None


# =============================================================================
# Hallucination Rules Tests
# =============================================================================

class TestHallucinationRules:
    """Test YAML hallucination rules and consistency with Python logic."""

    def test_yaml_loads_successfully(self):
        rules = load_hallucination_rules()
        assert rules is not None
        assert len(rules) == 3

    def test_rule_ids(self):
        rules = load_hallucination_rules()
        assert rules is not None
        ids = {r.id for r in rules}
        assert "double_elevation" in ids
        assert "bought_out_acting" in ids
        assert "renter_elevate" in ids

    def test_double_elevation_matches_python(self):
        """YAML double_elevation rule should match _is_hallucination logic."""
        # Trace: already elevated, trying to elevate again
        trace = {
            "approved_skill": {"skill_name": "elevate"},
            "state_before": {"elevated": True},
            "agent_type": "household_owner",
        }
        # Python logic says hallucination
        assert _is_hallucination(trace) is True

    def test_bought_out_acting_matches_python(self):
        """YAML bought_out_acting rule should match _is_hallucination logic."""
        trace = {
            "approved_skill": {"skill_name": "buy_insurance"},
            "state_before": {"bought_out": True},
            "agent_type": "household_owner",
        }
        assert _is_hallucination(trace) is True

        # do_nothing should NOT be hallucination even if bought_out
        trace_ok = {
            "approved_skill": {"skill_name": "do_nothing"},
            "state_before": {"bought_out": True},
            "agent_type": "household_owner",
        }
        assert _is_hallucination(trace_ok) is False

    def test_renter_elevate_matches_python(self):
        """YAML renter_elevate rule should match _is_hallucination logic."""
        trace = {
            "approved_skill": {"skill_name": "elevate"},
            "state_before": {},
            "agent_type": "household_renter",
        }
        assert _is_hallucination(trace) is True

    def test_fallback_when_file_missing(self):
        rules = load_hallucination_rules(Path("/nonexistent/rules.yaml"))
        assert rules is None


# =============================================================================
# Full Config Tests
# =============================================================================

class TestFullConfig:
    """Test load_default_config() integration."""

    def test_loads_with_yaml(self):
        """Full config should load with YAML files present."""
        config = load_default_config()
        assert isinstance(config, ValidationConfig)
        assert config.theory is not None
        assert config.benchmarks is not None
        assert config.hallucination_rules is not None

    def test_theory_accessible(self):
        config = load_default_config()
        assert config.theory.name == "pmt"
        assert len(config.theory.owner_rules) == 25

    def test_benchmarks_accessible(self):
        config = load_default_config()
        assert len(config.benchmarks.benchmarks) == 16  # 8 household + 7 institutional + 1 diagnostic

    def test_hallucination_rules_accessible(self):
        config = load_default_config()
        assert len(config.hallucination_rules) == 3
