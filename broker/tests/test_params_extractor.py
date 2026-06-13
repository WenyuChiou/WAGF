"""Phase 6W-B2 — params-dict parse extractor + per-agent-type opt-in gate.

The parser already builds a full multi-field numeric dict (`_extracted_numerics`)
and historically discarded all but the collapsed `magnitude_pct`. B2 routes that
dict onto `SkillProposal.parameters` — but ONLY when the agent_type opts in via
`multi_param_action`. Frozen domains never opt in, so `parameters` stays {} ->
to_dict omits it -> byte-identical, EVEN for an agent_type that declares two
numeric fields (single_agent 'household' declares magnitude_pct +
secondary_magnitude_pct, so a count-based gate would be unsafe — the opt-in is not).

See .research/wagf_coupling_IMPLEMENTATION_PLAN_2026-06-12.md (B2, O1, risk R3).
"""
import copy
from pathlib import Path

import pytest

from broker.utils.agent_config import AgentTypeConfig
from broker.utils.model_adapter import UnifiedAdapter

CONFIG_PATH = str(Path("examples/single_agent/agent_types.yaml"))  # 'household': 2 numeric fields
_JSON = '{"decision": 1, "magnitude_pct": 20, "secondary_magnitude_pct": 10}'
_CTX = {"agent_id": "H0001", "agent_type": "household"}


# ---- the opt-in accessor (the new gate logic) ----

def _cfg(d):
    c = AgentTypeConfig()
    c._config = d
    return c


def test_get_multi_param_enabled_forms():
    assert _cfg({"r": {"multi_param_action": {"enabled": True}}}).get_multi_param_enabled("r") is True
    assert _cfg({"r": {"multi_param_action": True}}).get_multi_param_enabled("r") is True
    assert _cfg({"r": {"multi_param_action": {"enabled": False}}}).get_multi_param_enabled("r") is False
    assert _cfg({"r": {"multi_param_action": "garbage"}}).get_multi_param_enabled("r") is False
    assert _cfg({"r": {}}).get_multi_param_enabled("r") is False          # key absent
    assert _cfg({}).get_multi_param_enabled("missing") is False           # agent_type absent


def test_get_audit_param_columns_flag():
    # 6W-B6 audit-column flag (global_config.audit.param_columns), default OFF
    assert _cfg({"global_config": {"audit": {"param_columns": True}}}).get_audit_param_columns() is True
    assert _cfg({"global_config": {"audit": {"param_columns": False}}}).get_audit_param_columns() is False
    assert _cfg({"global_config": {"audit": {}}}).get_audit_param_columns() is False  # key absent
    assert _cfg({}).get_audit_param_columns() is False                                # block absent


# ---- the routing gate (byte-identity critical) ----

def test_off_keeps_parameters_empty_even_with_two_numeric_fields():
    """The frozen-domain guarantee: a 2-numeric-field agent_type that does NOT
    opt in yields parameters=={} -> to_dict omits -> byte-identical."""
    AgentTypeConfig.clear_cache()
    try:
        adapter = UnifiedAdapter(agent_type="household", config_path=CONFIG_PATH)
        proposal = adapter.parse_output(_JSON, _CTX)
        assert proposal is not None
        assert proposal.parameters == {}, "opt-in OFF must leave parameters empty"
        assert "parameters" not in proposal.to_dict()  # byte-identity: key absent
        # the legacy scalar still resolves exactly as before
        assert proposal.magnitude_pct == 20
    finally:
        AgentTypeConfig.clear_cache()


def test_on_routes_full_numeric_dict():
    AgentTypeConfig.clear_cache()
    try:
        adapter = UnifiedAdapter(agent_type="household", config_path=CONFIG_PATH)
        # detach this adapter's config from the shared cache, then flip the opt-in
        adapter.agent_config._config = copy.deepcopy(adapter.agent_config._config)
        adapter.agent_config._config["household"]["multi_param_action"] = True
        proposal = adapter.parse_output(_JSON, _CTX)
        assert proposal is not None
        assert proposal.parameters.get("magnitude_pct") == 20
        assert proposal.parameters.get("secondary_magnitude_pct") == 10
        # to_dict now emits the key (non-empty)
        assert proposal.to_dict().get("parameters") == proposal.parameters
        # backward path intact: the collapsed scalar is still set
        assert proposal.magnitude_pct == 20
    finally:
        AgentTypeConfig.clear_cache()


def test_on_json_fail_path_does_not_nameerror():
    """Regression: the JSON-parse-fail path must not NameError on _extracted_numerics
    (it is only assigned inside the JSON-success block at ~:335; the top-of-function
    init covers this path). Exercised with opt-in ON so the constructor gate evaluates."""
    AgentTypeConfig.clear_cache()
    try:
        adapter = UnifiedAdapter(agent_type="household", config_path=CONFIG_PATH)
        adapter.agent_config._config = copy.deepcopy(adapter.agent_config._config)
        adapter.agent_config._config["household"]["multi_param_action"] = True
        proposal = adapter.parse_output("I choose option 1", _CTX)  # plain text, not JSON
        # must not raise; no numerics extracted on the non-JSON path
        assert proposal is None or proposal.parameters == {}
    finally:
        AgentTypeConfig.clear_cache()
