"""Phase 6H Item 8: the post-hoc validators are domain-parameterised.

`ThinkingRulePostHoc` transition rules and `unified_rh`'s physical
hallucination detection take their state columns / irreversible-state
mappings from the caller — no hardcoded flood defaults. These two
modules previously had zero unit tests.
"""
import pandas as pd

from broker.validators.posthoc.thinking_rule_posthoc import ThinkingRulePostHoc
from broker.validators.posthoc.unified_rh import (
    _compute_physical_hallucinations,
    compute_hallucination_rate,
)


def _df():
    """Two agent-years; `elevated` flips False->True in year 2."""
    return pd.DataFrame([
        {"agent_id": "a", "year": 1, "relocated": False, "elevated": False,
         "ta_level": "L", "ca_level": "M", "yearly_decision": "do_nothing"},
        {"agent_id": "a", "year": 2, "relocated": False, "elevated": True,
         "ta_level": "L", "ca_level": "M", "yearly_decision": "elevate_house"},
    ])


class TestThinkingRuleTransitionColumns:
    """V1/V2 are now one transition rule per domain-declared column."""

    def test_transition_rule_per_declared_column(self):
        tp = ThinkingRulePostHoc(transition_columns=["relocated", "elevated"])
        by_id = {r.rule_id: r.count for r in tp.apply(_df(), group="B")}
        # `elevated` False->True under low threat -> 1 hallucination
        assert by_id["V_transition_elevated_threat_low"] == 1
        assert by_id["V_transition_relocated_threat_low"] == 0

    def test_no_columns_means_no_transition_rules(self):
        """Default (no transition_columns) -> only V3, no transition rules."""
        ids = {r.rule_id for r in ThinkingRulePostHoc().apply(_df(), group="B")}
        assert not any(i.startswith("V_transition_") for i in ids)
        assert "V3_extreme_threat_block" in ids

    def test_non_flood_domain_column(self):
        """A non-flood domain verbalizes its own irreversible state."""
        df = pd.DataFrame([
            {"agent_id": "x", "year": 1, "exited_market": False,
             "ta_level": "L", "ca_level": "M", "yearly_decision": "hold"},
            {"agent_id": "x", "year": 2, "exited_market": True,
             "ta_level": "VL", "ca_level": "M", "yearly_decision": "sell"},
        ])
        tp = ThinkingRulePostHoc(transition_columns=["exited_market"])
        by_id = {r.rule_id: r.count for r in tp.apply(df, group="B")}
        assert by_id["V_transition_exited_market_threat_low"] == 1

    def test_missing_column_is_skipped(self):
        """A declared column absent from the df is silently skipped."""
        tp = ThinkingRulePostHoc(transition_columns=["not_a_column"])
        ids = {r.rule_id for r in tp.apply(_df(), group="B")}
        assert not any(i.startswith("V_transition_") for i in ids)


class TestPhysicalHallucinationDefault:
    """`_compute_physical_hallucinations` default is domain-neutral."""

    def test_empty_default_no_physical(self):
        # irreversible_states=None -> {} -> nothing detected
        assert _compute_physical_hallucinations(_df()).sum() == 0

    def test_caller_supplied_mapping_detects(self):
        df = pd.DataFrame([
            {"agent_id": "a", "year": 1, "elevated": True,
             "yearly_decision": "elevate_house"},
            {"agent_id": "a", "year": 2, "elevated": True,
             "yearly_decision": "elevate_house"},
        ])
        # year 2: already elevated + action matches "elevat" -> hallucination
        mask = _compute_physical_hallucinations(
            df, irreversible_states={"elevated": "elevat"})
        assert mask.sum() == 1


class TestComputeHallucinationRateGeneric:
    """compute_hallucination_rate end-to-end on a non-flood domain —
    no exit_state_col, no irreversible_states (the new generic path)."""

    def test_no_exit_col_all_years_active(self):
        df = pd.DataFrame([
            {"agent_id": "a", "year": 1, "yearly_decision": "hold"},
            {"agent_id": "a", "year": 2, "yearly_decision": "hold"},
            {"agent_id": "a", "year": 3, "yearly_decision": "hold"},
        ])
        # exit_state_col=None (default) -> no exit filtering; start_year=2
        out = compute_hallucination_rate(df, group="B", start_year=2)
        assert out["n_active"] == 2          # years 2, 3
        assert out["n_physical"] == 0        # irreversible_states default {}
        assert out["n_thinking"] == 0        # no transition cols, no extreme TP
        assert out["rh"] == 0.0
