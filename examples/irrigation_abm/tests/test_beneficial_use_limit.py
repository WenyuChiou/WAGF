"""Spec item 49: the shared beneficial-use constraint, without model calls."""
from types import SimpleNamespace

import pytest

from examples.irrigation_abm.irrigation_personas import IrrigationAgentProfile, build_option_texts
from examples.irrigation_abm.tests.test_v3_action_model import _one_agent_env
from examples.irrigation_abm.tests.test_v3_governance import (
    _config, _MenuHost, AGENT_TYPE, REGISTRY, CONFIG,
)
from broker.components.governance.registry import SkillRegistry
from broker.validators import AgentValidator


MESSAGE = "Increase not available: your request is already at about the most water your fields can use."


def limited_env(base=98_000., basin="upper_basin", margin=0., water_right=140_000.):
    env = _one_agent_env(base, base, water_right, basin, mu=1., sigma=0., step_bin_af=5_000.)
    p = IrrigationAgentProfile(agent_id="A", basin=basin, cluster="aggressive",
                              water_right=water_right, peak_obs_af=100_000.,
                              mu=1., sigma=0., step_bin_af=5_000.)
    env.configure_beneficial_use_limit([p], enabled=True, margin=margin, require_peak=True)
    env._reset_requests_to_base()
    return env, p


@pytest.mark.parametrize("basin", ["upper_basin", "lower_basin"])
@pytest.mark.parametrize("mode", ["strict", "disabled", "feasibility_only"])
@pytest.mark.parametrize("base,at", [(98_999., False), (99_000., True), (100_000., True)])
def test_beneficial_menu_and_block(monkeypatch, basin, mode, base, at):
    env, p = limited_env(base, basin)
    state = env.get_agent_state("A")
    assert state["at_beneficial_use_limit"] is at
    cfg = _config(monkeypatch, mode)
    rule = next(r for r in cfg.get_identity_rules(AGENT_TYPE) if r.id == "beneficial_use_limit")
    assert rule.message == MESSAGE
    registry = SkillRegistry()
    registry.register_from_yaml(str(REGISTRY))
    state["option_text_overrides"] = build_option_texts(p, base, p.water_right, 14_000.,
                                                       beneficial_use_limit_af=100_000.)
    ctx = {"agent_id": "A", "state": state}
    _MenuHost(cfg, registry)._inject_filtered_skills(ctx, AGENT_TYPE)
    offered = ctx["personal"]["dynamic_skill_map"].values()
    assert ("increase_demand" not in offered) is at
    # The real identity-rule evaluation also rejects an explicit off-menu skill.
    results = AgentValidator(config_path=str(CONFIG)).validate_identity(
        AGENT_TYPE, "A", "increase_demand", state)
    assert any(not r.valid and r.metadata.get("rule_id") == "beneficial_use_limit" for r in results) is at


@pytest.mark.parametrize("basin", ["upper_basin", "lower_basin"])
def test_beneficial_clamp_and_option_clause(basin):
    env, p = limited_env(basin=basin)
    result = env.execute_skill(SimpleNamespace(skill_name="increase_demand", agent_id="A", parameters={}))
    assert result.success
    assert env.get_agent_state("A")["request"] == 100_000.
    assert result.state_changes["magnitude_af"] == 2_000.
    assert result.state_changes["beneficial_use_clamp_cut_af"] == 3_000.
    assert result.action_context["magnitude_pct"] == pytest.approx(100 * 2_000 / 98_000)
    text = build_option_texts(p, 98_000., 140_000., 14_000., beneficial_use_limit_af=100_000.)["increase_demand"]
    assert text.startswith("Increase your request to about 100,000 acre-ft")
    assert "(it stops at 100,000 acre-ft, about the most water your fields can use)" in text
    env.update_agent_request("A", 130_000.)
    assert env.get_agent_state("A")["request"] == 100_000.


def test_beneficial_margin_widens_limit():
    env, _ = limited_env(base=100_000., margin=.1)
    assert not env.get_agent_state("A")["at_beneficial_use_limit"]
    env.update_agent_request("A", 130_000.)
    assert env.get_agent_state("A")["request"] == pytest.approx(110_000.)


@pytest.mark.parametrize("basin", ["upper_basin", "lower_basin"])
def test_beneficial_s1_stops_at_menu_target(basin):
    env, p = limited_env(basin=basin)
    env.config.ub_allocation_mode = "lees_ferry_pool"
    env.config.lb_priority_mode = "senior_all"
    env.keepfix_s1 = True
    env.advance_year()
    target, delivered = env.get_agent_state("A")["increase_expectation"]
    assert target == 100_000.
    text = build_option_texts(p, 98_000., 140_000., 14_000., beneficial_use_limit_af=100_000.)["increase_demand"]
    assert f"to about {target:,.0f} acre-ft" in text
    assert delivered["delivered"] <= target


@pytest.mark.parametrize("water_right,peak", [(490_000., 546_271.), (60_000., 63_558.)])
def test_water_right_binds_first(water_right, peak):
    env, p = limited_env(base=water_right, basin="lower_basin", water_right=water_right)
    p.peak_obs_af = peak
    env.configure_beneficial_use_limit([p], enabled=True, margin=0., require_peak=True)
    env._reset_requests_to_base()
    state = env.get_agent_state("A")
    assert state["at_allocation_cap"] and not state["at_beneficial_use_limit"]
    env.update_agent_request("A", water_right * 2)
    assert state["request"] == water_right
    text = build_option_texts(p, water_right-1, water_right, .1*water_right,
                              beneficial_use_limit_af=water_right)["increase_demand"]
    assert "your water right stops it" in text and "most water your fields" not in text


def test_beneficial_missing_peak_fails_real_startup():
    env, p = limited_env()
    p.peak_obs_af = None
    with pytest.raises(ValueError, match="peak_obs_af"):
        env.configure_beneficial_use_limit([p], enabled=True, margin=0., require_peak=True)


@pytest.mark.parametrize("margin", [-.1, 1.1, float("nan"), True])
def test_beneficial_invalid_margin(margin):
    with pytest.raises(ValueError, match="margin"):
        limited_env(margin=margin)


def test_beneficial_off_preserves_state():
    env, p = limited_env()
    env.configure_beneficial_use_limit([p], enabled=False, margin=0., require_peak=True)
    env._reset_requests_to_base()
    assert "beneficial_use_limit_af" not in env.get_agent_state("A")
    env.update_agent_request("A", 130_000.)
    assert env.get_agent_state("A")["request"] == 130_000.


@pytest.mark.parametrize("mode", ["strict", "disabled"])
@pytest.mark.parametrize("basin", ["upper_basin", "lower_basin"])
def test_beneficial_off_menu_retry_and_audit(monkeypatch, tmp_path, mode, basin):
    from broker.components.analytics.audit import AuditConfig, GenericAuditWriter, trace_to_csv_row
    from broker.core.skill_broker_engine import SkillBrokerEngine
    from broker.interfaces.skill_types import SkillProposal
    from broker.utils.parsing.unified_adapter import UnifiedAdapter
    from examples.irrigation_abm.tests.test_v3_governance import _AtCapContext
    cfg = _config(monkeypatch, mode)
    registry = SkillRegistry()
    registry.register_from_yaml(str(REGISTRY))
    ctx = _AtCapContext()
    ctx.state.update(at_allocation_cap=False, at_beneficial_use_limit=True, basin=basin)
    adapter = UnifiedAdapter.__new__(UnifiedAdapter)
    answers = iter(["increase_demand", "maintain_demand"])
    adapter.parse_output = lambda raw, context: SkillProposal(
        skill_name=next(answers), agent_id="A1", agent_type=AGENT_TYPE,
        reasoning={"WSA_LABEL": "M", "ACA_LABEL": "M", "WSA_REASON": "x", "ACA_REASON": "x"})
    engine = SkillBrokerEngine(skill_registry=registry, model_adapter=adapter,
                              validators=[AgentValidator(config_path=str(CONFIG))],
                              simulation_engine=None, context_builder=ctx, config=cfg)
    engine.audit_writer = GenericAuditWriter(AuditConfig(output_dir=str(tmp_path), experiment_name="item49"))
    prompts = []
    engine.process_step(agent_id="A1", step_id=1, run_id="r", seed=1,
                        llm_invoke=lambda p: prompts.append(p) or "raw", agent_type=AGENT_TYPE)
    assert MESSAGE in prompts[1]
    assert "your water right." not in prompts[1]
    row = trace_to_csv_row(engine.audit_writer._trace_buffer[AGENT_TYPE][-1])
    assert "beneficial_use_limit" in row["failed_rules"].split("|")
    assert "water_right_cap" not in row["failed_rules"].split("|")
    assert row["rules_world_grounded"] == "beneficial_use_limit"


def _startup_config():
    import yaml
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def _startup_registry():
    registry = SkillRegistry()
    registry.register_from_yaml(str(REGISTRY))
    return registry


@pytest.mark.parametrize("mode", ["strict", "disabled", "feasibility_only"])
def test_beneficial_startup_requires_selected_identity_rule(mode):
    from examples.irrigation_abm.run_experiment import _validate_beneficial_use_config
    cfg = _startup_config()
    rules = cfg[AGENT_TYPE]["governance"][mode]["identity_rules"]
    rules[:] = [rule for rule in rules if rule["id"] != "beneficial_use_limit"]
    with pytest.raises(ValueError, match=f"{mode}.*beneficial_use_limit"):
        _validate_beneficial_use_config(cfg, governance_mode=mode,
                                       skill_registry=_startup_registry(), model="mock")


def test_beneficial_startup_requires_registry_precondition():
    from examples.irrigation_abm.run_experiment import _validate_beneficial_use_config
    registry = _startup_registry()
    registry.get("increase_demand").preconditions.remove("not at_beneficial_use_limit")
    with pytest.raises(ValueError, match="increase_demand.*not at_beneficial_use_limit"):
        _validate_beneficial_use_config(_startup_config(), governance_mode="disabled",
                                       skill_registry=registry, model="mock")


@pytest.mark.parametrize("mode", ["strict", "disabled", "feasibility_only"])
def test_beneficial_startup_accepts_complete_wiring(mode):
    from examples.irrigation_abm.run_experiment import _validate_beneficial_use_config
    assert _validate_beneficial_use_config(
        _startup_config(), governance_mode=mode, skill_registry=_startup_registry(),
        model="mock")["enabled"] is True


@pytest.mark.parametrize("model", ["gemma3:4b", "gpt-4o"])
def test_beneficial_positive_margin_refuses_non_mock_model(model):
    from examples.irrigation_abm.run_experiment import _validate_beneficial_use_config
    cfg = _startup_config()
    cfg[AGENT_TYPE]["beneficial_use_limit"]["beneficial_use_margin"] = .1
    with pytest.raises(ValueError, match="mock/CPU sensitivity.*item 49"):
        _validate_beneficial_use_config(cfg, governance_mode="strict",
                                       skill_registry=_startup_registry(), model=model)


def test_beneficial_positive_margin_allows_mock_model():
    from examples.irrigation_abm.run_experiment import _validate_beneficial_use_config
    cfg = _startup_config()
    cfg[AGENT_TYPE]["beneficial_use_limit"]["beneficial_use_margin"] = .1
    assert _validate_beneficial_use_config(
        cfg, governance_mode="disabled", skill_registry=_startup_registry(),
        model="mock")["beneficial_use_margin"] == .1


def test_beneficial_disabled_setting_does_not_require_rule_or_precondition():
    from examples.irrigation_abm.run_experiment import _validate_beneficial_use_config
    cfg = _startup_config()
    cfg[AGENT_TYPE]["beneficial_use_limit"]["enabled"] = False
    cfg[AGENT_TYPE]["governance"]["disabled"]["identity_rules"] = []
    assert _validate_beneficial_use_config(
        cfg, governance_mode="disabled", skill_registry=SkillRegistry(), model="mock"
    )["enabled"] is False


def test_beneficial_context_keys_are_reported_as_uncovered():
    from examples.irrigation_abm.irrigation_coupling import (
        IRRIGATION_CONTEXT_FIELD_SOURCES, IRRIGATION_CONTEXT_UNCOVERED_KEYS,
    )
    for key in ("beneficial_use_limit_af", "at_beneficial_use_limit"):
        assert key in IRRIGATION_CONTEXT_UNCOVERED_KEYS
        assert key not in IRRIGATION_CONTEXT_FIELD_SOURCES


@pytest.mark.parametrize("defect", ["identity_rule", "precondition", "positive_margin", "top_override"])
def test_beneficial_main_refuses_bad_config_before_server_query(monkeypatch, tmp_path, defect):
    import shutil
    import yaml
    from examples.irrigation_abm import run_experiment
    config_dir = tmp_path / "config"
    shutil.copytree(CONFIG.parent, config_dir)
    cfg = _startup_config()
    model = "mock"
    if defect == "identity_rule":
        rules = cfg[AGENT_TYPE]["governance"]["disabled"]["identity_rules"]
        rules[:] = [r for r in rules if r["id"] != "beneficial_use_limit"]
    elif defect == "precondition":
        registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        registry["skills"][0]["preconditions"].remove("not at_beneficial_use_limit")
        (config_dir / "skill_registry.yaml").write_text(yaml.safe_dump(registry), encoding="utf-8")
    elif defect == "positive_margin":
        cfg[AGENT_TYPE]["beneficial_use_limit"]["beneficial_use_margin"] = .1
        model = "gemma3:4b"
    else:
        cfg["governance"] = {"disabled": {AGENT_TYPE: {"identity_rules": [
            r for r in cfg[AGENT_TYPE]["governance"]["disabled"]["identity_rules"]
            if r["id"] != "beneficial_use_limit"]}}}
    (config_dir / "agent_types.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    def forbidden_query(_model):
        pytest.fail("Invalid item-49 config reached a server query")
    monkeypatch.setattr(run_experiment, "_read_ollama_server_version", forbidden_query)
    monkeypatch.setattr("sys.argv", ["run_experiment.py", "--model", model, "--years", "1",
                                    "--governance-mode", "disabled", "--config-dir", str(config_dir),
                                    "--output", str(tmp_path / "out")])
    with pytest.raises(ValueError, match="beneficial_use"):
        run_experiment.main()
    assert not (tmp_path / "out" / "simulation_log.csv").exists()


@pytest.mark.parametrize("mapping", [False, True], ids=["list", "mapping"])
def test_beneficial_startup_uses_effective_top_level_override(mapping):
    from examples.irrigation_abm.run_experiment import _validate_beneficial_use_config
    cfg = _startup_config()
    rules = cfg[AGENT_TYPE]["governance"]["disabled"]["identity_rules"]
    override = [r for r in rules if r["id"] != "beneficial_use_limit"]
    if mapping:
        override = {r["id"]: {k: v for k, v in r.items() if k != "id"} for r in override}
    cfg["governance"] = {"disabled": {AGENT_TYPE: {"identity_rules": override}}}
    with pytest.raises(ValueError, match="disabled.*beneficial_use_limit"):
        _validate_beneficial_use_config(cfg, governance_mode="disabled",
                                       skill_registry=_startup_registry(), model="mock")


@pytest.mark.parametrize("layout", ["top_override", "embedded", "agent_fallback"])
def test_beneficial_startup_accepts_effective_identity_rule_mapping(layout):
    from examples.irrigation_abm.run_experiment import _validate_beneficial_use_config
    cfg = _startup_config()
    profile = cfg[AGENT_TYPE]["governance"]["disabled"]
    mapping = {r["id"]: {k: v for k, v in r.items() if k != "id"}
               for r in profile["identity_rules"]}
    if layout == "top_override":
        cfg["governance"] = {"disabled": {AGENT_TYPE: {"identity_rules": mapping}}}
        profile["identity_rules"] = []
    elif layout == "embedded":
        profile["identity_rules"] = mapping
    else:
        del profile["identity_rules"]
        cfg[AGENT_TYPE]["identity_rules"] = mapping
    assert _validate_beneficial_use_config(
        cfg, governance_mode="disabled", skill_registry=_startup_registry(), model="mock"
    )["enabled"] is True
