"""Tests for the opt-in registry-PHYSICAL dispatch in the simple ExperimentBuilder
path (Phase 6V follow-up).

Root cause fixed: SkillBrokerEngine._run_validators never dispatched
ValidatorRegistry-registered PHYSICAL checks (the registry physical path was dead
in all production runs; domains hand-wired via custom_validators). The engine now
dispatches a domain's PHYSICAL checks when domain_physical_dispatch is set, which
the builder threads from global_config.governance.dispatch_domain_physical.

These lock: (1) the dispatch fires the check when ON; (2) it is a strict no-op
when OFF (byte-safety for frozen domains); (3) the accessor is opt-in (cat ON,
frozen domains None); (4) the GOVERNANCE_DOMAIN env var does NOT activate dispatch.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import examples.cat_model  # noqa: F401 — registers cat_model PHYSICAL checks
from broker.components.governance.registry import SkillRegistry
from broker.core.skill_broker_engine import SkillBrokerEngine
from broker.interfaces.skill_types import SkillProposal
from broker.utils.agent_config import AgentTypeConfig

REPO = Path(__file__).resolve().parents[2]
_CFG = REPO / "examples"

_INSOLVENT = {
    "agent_type": "insurer",
    "env_state": {
        "policy_in_force_before_event": True,
        "agent_ground_up_loss": 100_000.0,
        "policy_deductible": 5_000.0,
        "policy_limit": 50_000.0,
        "pool_budget_remaining": 1_000.0,  # owed 45k >> pool -> pool_insolvent
    },
}


def _engine(dispatch):
    cfg = MagicMock()
    cfg.get_log_fields.return_value = []
    cfg.get_base_type.side_effect = lambda a: a
    return SkillBrokerEngine(
        skill_registry=SkillRegistry(),  # empty -> output_schema/precondition blocks skip
        model_adapter=MagicMock(),
        validators=[],
        simulation_engine=MagicMock(),
        context_builder=MagicMock(),
        config=cfg,
        domain_physical_dispatch=dispatch,
    )


def _proposal():
    return SkillProposal(
        skill_name="approve_payout", agent_id="INS", reasoning={},
        agent_type="insurer", parse_layer="test",
    )


def test_dispatch_on_fires_registry_physical_check():
    """With dispatch ON, the registered cat_model physical check runs and blocks
    an over-pool approve_payout — via the production registry path, no bridge."""
    results = _engine("cat_model")._run_validators(_proposal(), dict(_INSOLVENT))
    assert any(not r.valid and r.metadata.get("rule_id") == "pool_insolvent" for r in results), \
        [getattr(r, "metadata", r) for r in results]


def test_dispatch_off_is_strict_noop():
    """With dispatch OFF (None), NO physical check fires even though cat_model
    checks are registered — the byte-safety guarantee for frozen domains."""
    results = _engine(None)._run_validators(_proposal(), dict(_INSOLVENT))
    assert all(r.valid for r in results), \
        f"dispatch OFF must not fire any check; got {[getattr(r,'metadata',r) for r in results if not r.valid]}"


def test_accessor_opt_in_cat_on_frozen_off():
    cat = AgentTypeConfig.load(str(_CFG / "cat_model" / "config" / "agent_types.yaml"))
    assert cat.get_governance_physical_dispatch() == "cat_model"
    ma = AgentTypeConfig.load(str(_CFG / "multi_agent" / "flood" / "config" / "ma_agent_types.yaml"))
    assert ma.get_governance_physical_dispatch() is None  # frozen -> no dispatch (byte-safe)


def test_governance_domain_env_var_does_not_activate_dispatch(monkeypatch):
    """A stray GOVERNANCE_DOMAIN env var must NOT silently activate physical
    dispatch — dispatch is config-declared (the flag) only."""
    monkeypatch.setenv("GOVERNANCE_DOMAIN", "irrigation")
    ma = AgentTypeConfig.load(str(_CFG / "multi_agent" / "flood" / "config" / "ma_agent_types.yaml"))
    assert ma.get_governance_physical_dispatch() is None


def test_flag_true_but_no_domain_raises(tmp_path):
    """The flag alone is insufficient — and since 2026-06-09 (review P1-11) an
    explicitly-set dispatch_domain_physical WITHOUT a declared domain RAISES
    instead of silently returning None (a requested feature must never
    silently no-op). Frozen configs lack the flag entirely, so they still
    take the quiet None path."""
    import yaml as _yaml

    p = tmp_path / "at.yaml"
    p.write_text(
        _yaml.safe_dump({
            "global_config": {"governance": {"dispatch_domain_physical": True}},  # no domain
            "shared": {},
            "some_agent": {"parsing": {}},
        }),
        encoding="utf-8",
    )
    cfg = AgentTypeConfig.load(str(p))
    with pytest.raises(ValueError, match="dispatch_domain_physical"):
        cfg.get_governance_physical_dispatch()
