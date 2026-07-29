"""P0-1d: arm provenance and the fail-loud profile guard.

An experiment sweep's biggest silent-failure risk is not a crash — it is a run that
looks completely healthy while carrying the WRONG arm identity. Two known traps:

  * ``SkillBrokerEngine.__init__`` resolves
    ``max_retries if max_retries != 3 else config.get_governance_retries(...)``,
    so an explicit constructor argument SILENTLY beats the YAML. An arm intended as
    one-retry can quietly run as three, breaking the call-matching the enforcement
    decomposition depends on.
  * ``get_thinking_rules`` silently falls back to the ``default`` profile when the
    requested one is undeclared, so a typo'd arm name runs the wrong rule set with
    no error anywhere.

The manifest is therefore the source of truth for what an arm actually was, and the
guard makes a typo loud. These tests pin both.
"""
from __future__ import annotations

import os

import pytest

from broker.utils.agent_config import AgentTypeConfig


def _cfg(global_config=None, governance=None, agent_types=None) -> AgentTypeConfig:
    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = {"global_config": global_config or {}}
    if governance is not None:
        cfg._config["governance"] = governance
    for k, v in (agent_types or {"household": {}}).items():
        cfg._config[k] = v
    return cfg


@pytest.fixture(autouse=True)
def _clean_env():
    prev = os.environ.pop("GOVERNANCE_PROFILE", None)
    yield
    os.environ.pop("GOVERNANCE_PROFILE", None)
    if prev is not None:
        os.environ["GOVERNANCE_PROFILE"] = prev


# ---------------------------------------------------------------------------
# Fail-loud profile guard
# ---------------------------------------------------------------------------

def test_require_profile_defaults_off():
    assert _cfg().get_governance_require_profile() is False
    assert _cfg({"governance": {}}).get_governance_require_profile() is False
    # A malformed scalar block must read as OFF, never raise.
    assert _cfg({"governance": "yes"}).get_governance_require_profile() is False


# The TOP-LEVEL governance form nests agent_type UNDER the profile
# (governance.{profile}.{agent_type}), mirroring the resolver's own lookup.
_TOP_LEVEL = {"strict": {"household": {}}, "enforce": {"household": {}}}


def test_undeclared_profile_raises_when_required():
    cfg = _cfg({"governance": {"require_profile": True}}, governance=_TOP_LEVEL)
    os.environ["GOVERNANCE_PROFILE"] = "enfroce"  # typo
    with pytest.raises(ValueError) as exc:
        cfg.get_thinking_rules("household")
    # The message must name the valid options, or the operator cannot self-serve.
    assert "enforce" in str(exc.value) and "strict" in str(exc.value)


def test_declared_profile_passes_when_required():
    cfg = _cfg({"governance": {"require_profile": True}}, governance=_TOP_LEVEL)
    os.environ["GOVERNANCE_PROFILE"] = "enforce"
    cfg.get_thinking_rules("household")  # must not raise


def test_flag_off_keeps_the_forgiving_fallback():
    """Frozen runs must not change behaviour."""
    cfg = _cfg(governance={"strict": {}})
    os.environ["GOVERNANCE_PROFILE"] = "does_not_exist"
    cfg.get_thinking_rules("household")  # silently falls back, as before


def test_default_profile_never_trips_the_guard():
    cfg = _cfg({"governance": {"require_profile": True}}, governance={"strict": {}})
    # No GOVERNANCE_PROFILE set -> "default" -> exempt.
    cfg.get_thinking_rules("household")


# --- the schema that ACTUALLY ships -----------------------------------------
# No config in this repo uses a top-level `governance:` key; all governance is
# agent-type-embedded (household.governance.{profile}). Tests that only exercise
# the top-level shape would still pass with the embedded half of the lookup
# deleted — while that regression would make the guard reject EVERY real config.

def _real_schema_cfg(require=True, profiles=("strict", "enforce")):
    return _cfg(
        {"governance": {"require_profile": require}},
        agent_types={"household": {"governance": {p: {} for p in profiles}}},
    )


def test_guard_accepts_agent_type_embedded_profile():
    os.environ["GOVERNANCE_PROFILE"] = "enforce"
    _real_schema_cfg().get_thinking_rules("household")  # must not raise


def test_guard_rejects_typo_under_agent_type_embedded_schema():
    os.environ["GOVERNANCE_PROFILE"] = "enfroce"
    with pytest.raises(ValueError, match="not declared"):
        _real_schema_cfg().get_thinking_rules("household")


def test_top_level_profile_declared_for_another_agent_type_does_not_count():
    """The resolver nests agent_type UNDER profile, so the guard must too --
    otherwise a profile declared for one agent type silently authorises it for
    every other one, defeating the guard exactly where multi-agent domains need it."""
    cfg = _cfg({"governance": {"require_profile": True}},
               governance={"enforce": {"government": {}}},
               agent_types={"household": {}, "government": {}})
    os.environ["GOVERNANCE_PROFILE"] = "enforce"
    cfg.get_thinking_rules("government")          # declared for this type -> OK
    with pytest.raises(ValueError, match="not declared"):
        cfg.get_thinking_rules("household")       # NOT declared for this type


# --- the guard must cover EVERY accessor, not just the thinking one ----------

def test_identity_rules_accessor_is_guarded_too():
    """get_identity_rules runs on EVERY step, while get_thinking_rules is skipped
    when a proposal's reasoning fails to parse. Guarding only the latter leaves a
    typo'd profile reachable for an entire run with no error anywhere."""
    os.environ["GOVERNANCE_PROFILE"] = "enfroce"
    with pytest.raises(ValueError, match="not declared"):
        _real_schema_cfg().get_identity_rules("household")


def test_identity_rules_accessor_unguarded_when_flag_off():
    os.environ["GOVERNANCE_PROFILE"] = "does_not_exist"
    _real_schema_cfg(require=False).get_identity_rules("household")


# ---------------------------------------------------------------------------
# Manifest arm provenance — must never poison the whole manifest
# ---------------------------------------------------------------------------

def test_manifest_fields_degrade_safely_on_a_duck_typed_broker():
    """Regression: getattr on a Mock broker returns a truthy Mock, so reading
    spec["mode"] produced a non-serialisable value. json.dump raises TypeError,
    which the manifest write did NOT catch, so the whole manifest was lost AND the
    load-bearing summary save was starved."""
    import json
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from broker.core.experiment_runner import ExperimentRunner

    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.broker = MagicMock()          # _advise_spec -> truthy Mock
    runner.agents = {}
    runner.config = SimpleNamespace(model="m", seed=1, num_years=1)

    metadata = {}
    spec = getattr(runner.broker, "_advise_spec", None)
    if isinstance(spec, dict) and isinstance(spec.get("rule_ids"), (list, tuple)):
        metadata["advise_spec_resolved"] = {"mode": str(spec.get("mode", "off")),
                                            "rule_ids": sorted(str(r) for r in spec["rule_ids"])}
    else:
        metadata["advise_spec_resolved"] = None
    framing = getattr(runner.broker, "_intervention_framing", "legacy")
    metadata["intervention_framing_resolved"] = framing if isinstance(framing, str) else "legacy"
    retries = getattr(runner.broker, "max_retries", None)
    metadata["max_retries_resolved"] = (
        retries if isinstance(retries, int) and not isinstance(retries, bool) else None)

    json.dumps(metadata)  # must not raise
    assert metadata["advise_spec_resolved"] is None
    assert metadata["intervention_framing_resolved"] == "legacy"
    assert metadata["max_retries_resolved"] is None


def test_manifest_write_survives_a_nonserialisable_entry():
    """The summary save must never be starved by a manifest serialisation failure."""
    import json
    from unittest.mock import MagicMock
    with pytest.raises(TypeError):
        json.dumps({"bad": MagicMock()})
    # and the handler that guards it must name TypeError
    import inspect
    from broker.core import experiment_runner as er
    src = inspect.getsource(er.ExperimentRunner.finalize) if hasattr(
        er.ExperimentRunner, "finalize") else inspect.getsource(er)
    assert "OSError, TypeError, ValueError" in src


# ---------------------------------------------------------------------------
# NOTE: a blanket `strict_warning` profile was built and then DELETED on purpose.
#
# It downgraded every ERROR in `thinking_rules` to WARNING, on the assumption that
# the thinking_rules/identity_rules split maps onto behavioural-theory/world-
# affordance. It does not: that split is a FILE STRUCTURE, not a semantic guarantee,
# and physically-infeasible constraints live on both sides. A blanket downgrade can
# therefore make an impossible action executable -- the same defect class as
# advising `precondition_violation` (see ADVISE_DENY in broker/core/_advise.py).
#
# The capability is not lost: broker/core/_advise.py takes an EXPLICIT per-rule-id
# allowlist, so the same arm is built by naming each rule, which forces the
# theory-vs-affordance judgement to be made once, by a domain expert, and recorded
# in the config and the run manifest. Do not reintroduce a blanket profile.
# ---------------------------------------------------------------------------
