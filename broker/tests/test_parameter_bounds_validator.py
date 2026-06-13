"""Phase 6W-B4 — generic ParameterBoundsValidator (AR-6 numeric-param governance).

Proves: per-field bounds via VarSpec.range_violation; missing-required blocks;
inert for skills with no specs; iterates the SPEC allowlist (non-setpoint keys like
magnitude_fallback are never checked); NEVER clips (blocks, leaves the proposed dict
untouched). See .research/wagf_coupling_IMPLEMENTATION_PLAN_2026-06-12.md (B4).
"""
from broker.coupling.contract import VarSpec
from broker.coupling.param_validator import make_parameter_bounds_validator


def _vs(name, unit, lo, hi):
    return VarSpec(name=name, dtype=float, unit=unit, lo=lo, hi=hi,
                   direction="agent_to_world", value_source="proposal")


SPECS = {"set_release": [_vs("release_cms", "cms", 0.0, 850.0),
                         _vs("hydropower_mw", "MW", 0.0, 2000.0)]}


def test_in_bounds_passes():
    v = make_parameter_bounds_validator(SPECS)
    ctx = {"proposed_parameters": {"release_cms": 100.0, "hydropower_mw": 500.0}}
    assert v("set_release", [], ctx) == []


def test_out_of_bounds_blocks_with_rule_id():
    v = make_parameter_bounds_validator(SPECS)
    ctx = {"proposed_parameters": {"release_cms": 900.0, "hydropower_mw": 500.0}}
    res = v("set_release", [], ctx)
    assert len(res) == 1 and res[0].valid is False
    assert res[0].metadata["rule_id"] == "param_bounds_release_cms"
    assert res[0].metadata["deterministic"] is True   # composes with EarlyExit
    assert "release_cms" in res[0].errors[0]           # field named in retry message
    assert "850" in res[0].errors[0]                   # bound named in retry message


def test_missing_required_blocks():
    v = make_parameter_bounds_validator(SPECS)
    res = v("set_release", [], {"proposed_parameters": {"release_cms": 100.0}})
    assert any(r.metadata["rule_id"] == "param_missing_hydropower_mw" for r in res)


def test_no_spec_skill_is_inert():
    v = make_parameter_bounds_validator(SPECS)
    assert v("do_nothing", [], {"proposed_parameters": {"x": 999}}) == []


def test_non_setpoint_key_ignored():
    """A non-setpoint key (the bool magnitude_fallback) in proposed_parameters is
    never range-checked — the validator iterates the spec allowlist, not the raw dict."""
    v = make_parameter_bounds_validator(SPECS)
    ctx = {"proposed_parameters": {"release_cms": 100.0, "hydropower_mw": 500.0,
                                   "magnitude_fallback": True}}
    assert v("set_release", [], ctx) == []


def test_never_clips_the_proposed_value():
    v = make_parameter_bounds_validator(SPECS)
    proposed = {"release_cms": 900.0, "hydropower_mw": 500.0}
    v("set_release", [], {"proposed_parameters": proposed})
    assert proposed["release_cms"] == 900.0   # blocked, NOT rewritten (EXECUTED-ONLY)


def test_no_proposed_parameters_blocks_all_required():
    v = make_parameter_bounds_validator(SPECS)
    res = v("set_release", [], {})   # frozen-shaped context: no proposed_parameters
    assert len(res) == 2
    assert all(r.metadata["rule_id"].startswith("param_missing_") for r in res)
