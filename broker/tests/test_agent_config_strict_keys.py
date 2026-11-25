"""Load-time range checks and strict keys for ``AgentTypeConfig.load``."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from broker.utils import agent_config as ac
from broker.utils.agent_config import AgentTypeConfig, UnknownConfigKeysError

ROOT = Path(__file__).resolve().parents[2]


def _agent_type_yamls():
    found = set()
    for top in ("examples", "broker"):
        for path in (ROOT / top).rglob("*.yaml"):
            if any(part in {"results", "__pycache__", "node_modules"} for part in path.parts):
                continue
            if "agent_types" in path.name:
                found.add(path)
                continue
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, dict) and "global_config" in data:
                found.add(path)
    return sorted(found)


@pytest.fixture(autouse=True)
def _fresh_cache():
    AgentTypeConfig.clear_cache()
    ac._warned_unknown_config_keys.clear()
    yield
    AgentTypeConfig.clear_cache()


@pytest.fixture
def warnings_seen(monkeypatch):
    seen = []
    monkeypatch.setattr(ac.logger, "warning", lambda message, *args: seen.append(message % args))
    return seen


def _write(tmp_path, data, name="agent_types.yaml"):
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


# --- the walk: nothing that ships may be refused -----------------------------

def test_the_walk_finds_the_known_paper_yamls():
    names = {p.relative_to(ROOT).as_posix() for p in _agent_type_yamls()}
    assert "examples/irrigation_abm/config/agent_types.yaml" in names
    assert "examples/governed_flood/config/agent_types.yaml" in names
    assert "examples/multi_agent/flood/config/ma_agent_types.yaml" in names
    assert "examples/single_agent/agent_types.yaml" in names


@pytest.mark.parametrize("path", _agent_type_yamls(), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_every_example_agent_types_yaml_still_loads(path):
    """No example or paper YAML may be refused by a load-time range check."""
    AgentTypeConfig.load(str(path), force_reload=True)


@pytest.mark.parametrize("path", _agent_type_yamls(), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_example_has_an_unknown_key_inside_a_covered_section(path):
    """Strict mode may report top-level keys, but never a key inside memory,
    reflection, governance.* or llm_safeguard: those sections list every key an
    example uses."""
    try:
        AgentTypeConfig.load(str(path), force_reload=True, strict_keys=True)
    except UnknownConfigKeysError as exc:
        inside = [key for key in exc.keys
                  if any(f".{section}." in f".{key}" for section in
                         ("memory", "reflection", "governance", "llm_safeguard"))
                  and key.count(".") >= 2]
        assert inside == [], inside


# --- range checks for the continuous keys that were unchecked ----------------

BAD = 1.5


def _memory(key):
    return {"memory": {key: BAD}}


CASES = [
    ("memory.W_relevance", _memory("W_relevance")),
    ("memory.W_interference", _memory("W_interference")),
    ("memory.interference_cap", _memory("interference_cap")),
    ("memory.ema_alpha", _memory("ema_alpha")),
    ("memory.retrieval_weights.recency", {"memory": {"retrieval_weights": {"recency": BAD}}}),
    ("reflection.triggers.institutional_threshold",
     {"reflection": {"triggers": {"institutional_threshold": BAD}}}),
    *[(f"governance.drift.{key}", {"governance": {"drift": {key: BAD}}}) for key in (
        "entropy_threshold", "stagnation_threshold", "collapse_threshold", "jaccard_stagnation_threshold")],
    *[(f"governance.population.{key}", {"governance": {"population": {key: BAD}}}) for key in (
        "echo_threshold", "entropy_threshold", "deadlock_threshold", "quorum_threshold")],
    *[(f"governance.memory.resolution_importance_policy.{key}",
       {"governance": {"memory": {"resolution_importance_policy": {key: BAD}}}}) for key in ("approved", "denied")],
]


@pytest.mark.parametrize("name, block", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("scope", ["global_config", "shared"])
def test_out_of_range_fraction_is_refused_in_global_config_and_shared(tmp_path, name, block, scope):
    path = _write(tmp_path, {scope: block})
    with pytest.raises(ValueError, match=name.split(".")[-1]):
        AgentTypeConfig.load(path, force_reload=True)


@pytest.mark.parametrize("name, block", [c for c in CASES if c[0].startswith(("memory.", "reflection."))],
                         ids=lambda v: v if isinstance(v, str) else "")
def test_out_of_range_memory_and_reflection_fraction_is_refused_in_an_agent_block(tmp_path, name, block):
    path = _write(tmp_path, {"household": {"agent_type": "household", **block}})
    with pytest.raises(ValueError, match=name.split(".")[-1]):
        AgentTypeConfig.load(path, force_reload=True)


@pytest.mark.parametrize("value", [0, 1, 0.5])
def test_values_on_the_unit_interval_load(tmp_path, value):
    block = {"memory": {"ema_alpha": value, "W_relevance": value},
             "governance": {"drift": {"entropy_threshold": value}, "population": {"quorum_threshold": value}}}
    AgentTypeConfig.load(_write(tmp_path, {"global_config": block}), force_reload=True)


def test_arousal_threshold_stays_unbounded(tmp_path):
    AgentTypeConfig.load(_write(tmp_path, {"global_config": {"memory": {"arousal_threshold": 99.0}}}),
                         force_reload=True)


# --- strict keys ------------------------------------------------------------------

def _mixed(decay_rate=0.1):
    return {
        "global_config": {
            "mystery_flag": True,                                              # level (b)
            "memory": {"decay_rate": decay_rate, "window_size": 3, "memory_typo": 1},   # level (c)
            "reflection": {"interval": 1, "triggers": {"crisis": True, "trigger_typo": 1}},
            "governance": {"max_retries": 3, "retrieval": {"top_n": 3, "retrieval_typo": 1}},
            "llm_safeguard": {"enabled": False, "safeguard_typo": 1},
            "water_system": {"anything": 1},                                   # "<domain>_system" is exempt
        },
        "household": {
            "agent_type": "household", "description": "x",
            "agent_typo": 1,                                                   # level (a)
            "memory": {"window_size": 5, "agent_memory_typo": 2},
        },
    }


EXPECTED_UNKNOWN = [
    "household.agent_typo",
    "global_config.mystery_flag",
    "global_config.memory.memory_typo",
    "global_config.reflection.triggers.trigger_typo",
    "global_config.governance.retrieval.retrieval_typo",
    "global_config.llm_safeguard.safeguard_typo",
    "household.memory.agent_memory_typo",
]


def test_mixed_config_strict_off_loads_warns_for_each_unknown_key_and_still_refuses_a_bad_value(
        tmp_path, warnings_seen):
    good = _write(tmp_path, _mixed(), "good.yaml")
    config = AgentTypeConfig.load(good, force_reload=True)
    assert config.get_global_memory_config()["window_size"] == 3
    for key in EXPECTED_UNKNOWN:
        assert any(f"'{key}'" in line for line in warnings_seen), (key, warnings_seen)
    assert len([line for line in warnings_seen if "Unknown key" in line]) == len(EXPECTED_UNKNOWN)

    bad = _write(tmp_path, _mixed(decay_rate=1.5), "bad.yaml")
    with pytest.raises(ValueError, match="decay_rate must be a real number in \\[0, 1\\]"):
        AgentTypeConfig.load(bad, force_reload=True)


def test_mixed_config_strict_on_raises_once_and_lists_every_unknown_key(tmp_path):
    path = _write(tmp_path, _mixed())
    with pytest.raises(UnknownConfigKeysError) as raised:
        AgentTypeConfig.load(path, force_reload=True, strict_keys=True)
    assert raised.value.keys == EXPECTED_UNKNOWN
    for key in EXPECTED_UNKNOWN:
        assert key in str(raised.value)
    assert isinstance(raised.value, ValueError)


def test_strict_on_with_a_clean_config_loads(tmp_path):
    data = _mixed()
    data["global_config"] = {k: v for k, v in data["global_config"].items() if k != "mystery_flag"}
    for section in ("memory", "reflection", "governance", "llm_safeguard"):
        block = data["global_config"][section]
        for key in [k for k in block if k.endswith("_typo")]:
            del block[key]
    data["global_config"]["reflection"]["triggers"].pop("trigger_typo", None)
    data["global_config"]["governance"]["retrieval"].pop("retrieval_typo", None)
    del data["household"]["agent_typo"]
    del data["household"]["memory"]["agent_memory_typo"]
    AgentTypeConfig.load(_write(tmp_path, data), force_reload=True, strict_keys=True)


def test_a_cached_non_strict_instance_is_checked_again_when_strict_is_requested(tmp_path):
    path = _write(tmp_path, _mixed())
    AgentTypeConfig.load(path)                      # non-strict: cached
    with pytest.raises(UnknownConfigKeysError):
        AgentTypeConfig.load(path, strict_keys=True)   # no force_reload: must still refuse
    assert AgentTypeConfig.load(path) is not None   # a plain load still works


def test_warnings_are_given_once_per_file_and_key(tmp_path, warnings_seen):
    path = _write(tmp_path, _mixed())
    AgentTypeConfig.load(path, force_reload=True)
    first = len(warnings_seen)
    AgentTypeConfig.load(path, force_reload=True)
    assert len(warnings_seen) == first


def test_global_config_check_uses_the_validators_known_keys(tmp_path):
    from broker.tools.validate_prompt import KNOWN_GLOBAL_CONFIG_KEYS

    block = {key: {} for key in KNOWN_GLOBAL_CONFIG_KEYS}
    block["foo_system"] = {}
    AgentTypeConfig.load(_write(tmp_path, {"global_config": block}), force_reload=True, strict_keys=True)


def test_global_and_section_checks_wait_while_llm_utils_is_still_importing(
    tmp_path, monkeypatch, warnings_seen,
):
    """llm_utils loads a config while it imports; checks (b) and (c) skip then, (a) does not."""
    import sys
    import types

    half_imported = types.ModuleType("broker.utils.llm_utils")  # no LLM_CONFIG yet
    monkeypatch.setitem(sys.modules, "broker.utils.llm_utils", half_imported)
    path = _write(tmp_path, {
        "global_config": {"not_a_global_key": 1, "memory": {"window_sise": 3}},
        "household": {"prompt_template": "x", "not_an_agent_key": 1},
    })
    AgentTypeConfig.load(path, force_reload=True)
    seen = " ".join(warnings_seen)
    assert "not_an_agent_key" in seen
    assert "not_a_global_key" not in seen
    assert "window_sise" not in seen
