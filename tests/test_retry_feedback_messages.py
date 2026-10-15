"""Load-time diagnostics must not change rule or retry behavior."""
import logging
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from broker.utils import agent_config
from broker.utils.agent_config import AgentTypeConfig
from broker.validators.agent.agent_validator import AgentValidator


FRAGMENT = "Blocking rule without a message"
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolated_warning_history(monkeypatch):
    # Production history survives clear_cache/force_reload for the whole process.
    monkeypatch.setattr(agent_config, "_warned_missing_rule_messages", set(), raising=False)


def _messages(caplog):
    return [r.getMessage() for r in caplog.records if FRAGMENT in r.getMessage()]


def _load(tmp_path, rules, *, layout="embedded", profile="strict", prefix=True,
          filename="agent_types.yaml"):
    data = {"global_config": {"governance": {"rule_id_prefix": prefix}}, "farmer": {}}
    if layout == "top":
        data["governance"] = {profile: {"farmer": rules}}
    elif layout == "direct":
        data["farmer"].update(rules)
    else:
        data["farmer"]["governance"] = {profile: rules}
    path = tmp_path / filename
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return AgentTypeConfig.load(str(path), force_reload=True)


@pytest.mark.parametrize("kind", ["thinking_rules", "identity_rules"])
@pytest.mark.parametrize("layout", ["top", "embedded", "direct"])
@pytest.mark.parametrize("message", [None, "", "   "])
def test_blank_blocking_message_warns_at_load(tmp_path, caplog, kind, layout, message):
    rule = {"id": "supply_block", "blocked_skills": ["increase", "hold"],
            "precondition": "supply_low", "level": "ERROR"}
    if message is not None:
        rule["message"] = message
    with caplog.at_level(logging.WARNING):
        cfg = _load(tmp_path, {kind: [rule]}, layout=layout)
    messages = _messages(caplog)
    assert len(messages) == 1
    warning = messages[0]
    assert "agent type='farmer'" in warning
    assert ("all profiles without their own block" if layout == "direct"
            else "profile='strict'") in warning
    assert "rule id='supply_block'" in warning
    assert kind in warning
    for skill in rule["blocked_skills"]:
        if kind == "identity_rules":
            assert f"[Rule: supply_block] Identity Block: {skill} restricted by supply_low" in warning
        else:
            assert f"[Rule: supply_block] Thinking Block: {skill} restricted by thinking rules" in warning
            assert f"[Rule: supply_block] Validation failed for skill: {skill}" in warning
    # Warning-only diagnostic: the YAML bytes/data, including whitespace, survive.
    raw = cfg._config["farmer"] if layout == "direct" else (
        cfg._config["governance"]["strict"]["farmer"] if layout == "top"
        else cfg._config["farmer"]["governance"]["strict"])
    assert raw[kind][0] == rule
    if message == "   ":
        assert "whitespace is rendered verbatim" in warning


@pytest.mark.parametrize("kind", ["thinking_rules", "identity_rules"])
@pytest.mark.parametrize("level,message", [("ERROR", "You cannot increase under low supply."),
                                          ("WARNING", ""), ("error", "")])
def test_nonblocking_or_explained_rule_does_not_warn(tmp_path, caplog, kind, level, message):
    # WARNING rules are diagnostic and never reach the model's retry prompt.
    with caplog.at_level(logging.WARNING):
        _load(tmp_path, {kind: [{"id": "supply_block", "blocked_skills": ["increase"],
                                "level": level, "message": message}]})
    assert _messages(caplog) == []


def test_warning_deduplicates_same_path_after_reloads_and_cache_clear(tmp_path, caplog):
    rules = {"thinking_rules": {"same_rule": {"blocked_skills": ["increase"]}}}
    with caplog.at_level(logging.WARNING):
        cfg = _load(tmp_path, rules)
        _load(tmp_path, rules)
        AgentTypeConfig.clear_cache()
        _load(tmp_path, rules)
    assert len(_messages(caplog)) == 1
    assert cfg._config["farmer"]["governance"]["strict"] == rules


def test_different_config_files_warn_independently(tmp_path, caplog):
    rules = {"thinking_rules": {"same_rule": {"blocked_skills": ["increase"]}}}
    with caplog.at_level(logging.WARNING):
        _load(tmp_path, rules)
        _load(tmp_path, rules, filename="another.yaml")
    assert len(_messages(caplog)) == 2
    paths = {key[0] for key in agent_config._warned_missing_rule_messages}
    assert paths == {str((tmp_path / name).resolve())
                     for name in ("agent_types.yaml", "another.yaml")}


@pytest.mark.parametrize("kind", ["thinking_rules", "identity_rules"])
@pytest.mark.parametrize("skills,expected", [
    ("increase_demand", "increase_demand"), (5, "<skill>"), (None, "<skill>"),
    ({"odd": "shape"}, "<skill>"), ([5], "<skill>"),
])
def test_odd_blocked_skills_never_prevent_loading(tmp_path, caplog, kind, skills, expected):
    rule = {"id": "odd_skills", "blocked_skills": skills}
    with caplog.at_level(logging.WARNING):
        cfg = _load(tmp_path, {kind: [rule]})
    assert cfg._config["farmer"]["governance"]["strict"][kind] == [rule]
    assert len(_messages(caplog)) == 1
    warning = _messages(caplog)[0]
    assert f"{expected} restricted by" in warning
    if isinstance(skills, str):
        assert "'i restricted by" not in warning


@pytest.mark.parametrize("container", [
    {"thinking_rules": ["not a rule"]},
    {"identity_rules": ["not a rule"]},
    ["not a profile"],
])
def test_unexpected_rule_or_profile_shape_keeps_loaded_data(tmp_path, caplog, container):
    with caplog.at_level(logging.DEBUG, logger="broker.utils.agent_config"):
        cfg = _load(tmp_path, container)
    assert cfg._config["farmer"]["governance"]["strict"] == container
    assert _messages(caplog) == []
    assert any(record.levelno == logging.DEBUG and "diagnostic" in record.getMessage().lower()
               for record in caplog.records)


def test_unexpected_scan_failure_is_debug_only(tmp_path, caplog, monkeypatch):
    def broken_scan(*args):
        raise RuntimeError("unexpected diagnostic shape")
    monkeypatch.setattr(AgentTypeConfig, "_iter_rule_message_blocks", broken_scan)
    with caplog.at_level(logging.DEBUG, logger="broker.utils.agent_config"):
        cfg = _load(tmp_path, {"thinking_rules": []})
    assert cfg._config["farmer"]
    assert _messages(caplog) == []
    assert any(record.levelno == logging.DEBUG and record.exc_info
               for record in caplog.records)


def _load_data(tmp_path, data):
    path = tmp_path / "selection.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return AgentTypeConfig.load(str(path), force_reload=True)


def test_only_rules_selected_by_getters_warn(tmp_path, caplog):
    def block(rule_id):
        return [{"id": rule_id, "blocked_skills": ["increase"]}]
    data = {"farmer": {
        "thinking_rules": block("legacy_thinking_shadowed"),
        "coherence_rules": block("legacy_alias_shadowed"),
        "identity_rules": block("legacy_identity"),
        "governance": {
            "default": {"thinking_rules": block("default_thinking")},
            "strict": {"thinking_rules": block("embedded_shadowed"),
                       "coherence_rules": block("profile_alias_ignored")},
            "empty": {"thinking_rules": [], "identity_rules": []},
        }},
        "governance": {"strict": {"farmer": {"thinking_rules": block("top_thinking")}},
                       "other": {"farmer": {}}}}
    with caplog.at_level(logging.WARNING):
        _load_data(tmp_path, data)
    messages = _messages(caplog)
    assert len(messages) == 3
    for rule_id in ("default_thinking", "legacy_identity", "top_thinking"):
        assert any(f"rule id='{rule_id}'" in msg for msg in messages)
    identity = next(msg for msg in messages if "rule id='legacy_identity'" in msg)
    assert "all profiles without their own block" in identity
    assert "strict" in identity and "other" in identity
    assert "empty" not in identity


@pytest.mark.parametrize("kind", ["thinking_rules", "identity_rules"])
def test_empty_top_level_rules_use_embedded_rules(tmp_path, caplog, kind):
    data = {"farmer": {"governance": {"strict": {kind: [{"id": "embedded"}]}}},
            "governance": {"strict": {"farmer": {kind: []}}}}
    with caplog.at_level(logging.WARNING):
        _load_data(tmp_path, data)
    assert len(_messages(caplog)) == 1
    assert "rule id='embedded'" in _messages(caplog)[0]


def test_all_profiles_and_legacy_coherence_alias_are_checked(tmp_path, caplog):
    path = tmp_path / "agent_types.yaml"
    data = {"farmer": {"governance": {
        "strict": {"thinking_rules": [{"id": "first", "blocked_skills": ["increase"]}]},
        "unused": {"identity_rules": {"second": {"precondition": "limited", "blocked_skills": ["hold"]}}}}},
        "other": {"coherence_rules": {"third": {"blocked_skills": ["act"]}}}}
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        AgentTypeConfig.load(str(path), force_reload=True)
    assert len(_messages(caplog)) == 3
    assert any("profile='unused'" in msg and "rule id='second'" in msg for msg in _messages(caplog))
    assert any("agent type='other'" in msg and "rule id='third'" in msg for msg in _messages(caplog))


@pytest.mark.parametrize("kind", ["thinking_rules", "identity_rules"])
def test_warning_matches_actual_agent_validator_fallback(tmp_path, caplog, kind):
    rule = {"id": "supply_block", "construct": "WSA_LABEL", "when_above": ["H"],
            "blocked_skills": ["increase"], "precondition": "supply_low"}
    with caplog.at_level(logging.WARNING):
        cfg = _load(tmp_path, {kind: [rule]}, layout="direct", prefix=False)
    validator = AgentValidator.__new__(AgentValidator)
    validator.config = cfg
    validator.auditor = Mock()
    validator.rule_id_prefix = False
    if kind == "identity_rules":
        results = validator.validate_identity("farmer", "f1", "increase", {"supply_low": True})
    else:
        results = validator.validate_thinking("farmer", "f1", "increase", {}, {"WSA_LABEL": "H"})
    assert len(results) == 1
    assert results[0].errors[0] in _messages(caplog)[0]
    assert not results[0].errors[0].startswith("[Rule:")


WATER_CONFIGS = [ROOT / "examples/single_agent/agent_types.yaml", *sorted(
    (ROOT / "examples/irrigation_abm").rglob("agent_types.yaml"))]
# Empty since PR #92 (fix/flood-r5-plain-feedback) gave the flood identity rule
# elevation_block its message: every blocking rule in both water examples
# states its reason.
FLOOD_ALLOWED: set = set()


@pytest.mark.parametrize("path", WATER_CONFIGS, ids=lambda p: str(p.relative_to(ROOT)))
def test_water_example_configs_have_messages(path, caplog):
    with caplog.at_level(logging.WARNING):
        AgentTypeConfig.load(str(path), force_reload=True)
    actual = set(agent_config._warned_missing_rule_messages)
    expected = FLOOD_ALLOWED if path == ROOT / "examples/single_agent/agent_types.yaml" else set()
    assert actual == expected
    assert len(_messages(caplog)) == len(expected)


def test_water_matrix_includes_every_shipped_runner_config():
    # --config-dir reads agent_types.yaml from a complete isolated config tree.
    irrigation = [p for p in WATER_CONFIGS if "irrigation_abm" in p.parts]
    assert irrigation
    assert ROOT / "examples/irrigation_abm/config_variants/simple/agent_types.yaml" in irrigation
    assert ROOT / "examples/irrigation_abm/config_variants/simple_nolimit/agent_types.yaml" in irrigation


@pytest.mark.parametrize("path", WATER_CONFIGS, ids=lambda p: str(p.relative_to(ROOT)))
def test_scanned_rules_match_getters_for_every_water_profile(path, monkeypatch):
    cfg = AgentTypeConfig.load(str(path), force_reload=True)
    selected = {}
    resolver = cfg._get_rule_definitions

    def record(agent_type, profile, kind):
        rules = resolver(agent_type, profile, kind)
        selected[agent_type, profile, kind] = rules
        return rules

    monkeypatch.setattr(cfg, "_get_rule_definitions", record)
    blocks = list(cfg._iter_rule_message_blocks())
    # Freeze scanner observations before the accessors use the same resolver.
    selected = dict(selected)
    assert selected

    def raw_ids(rules):
        if isinstance(rules, dict):
            rules = [{"id": key, **value} for key, value in rules.items()]
        return {rule.get("id", rule.get("construct", "unknown")) for rule in rules}

    expected = set()
    for (agent_type, profile, kind), raw in list(selected.items()):
        monkeypatch.setenv("GOVERNANCE_PROFILE", profile)
        getter = cfg.get_thinking_rules if kind == "thinking_rules" else cfg.get_identity_rules
        actual = {rule.id for rule in getter(agent_type)}
        assert actual == raw_ids(raw), (agent_type, profile, kind)
        expected.update((agent_type, kind, rule_id) for rule_id in actual)
    scanned = {(agent_type, kind, rule_id)
               for agent_type, _, kind, raw in blocks for rule_id in raw_ids(raw)}
    assert scanned == expected
