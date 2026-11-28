"""Tests for legacy module bug fixes and v0.7.0 deprecations."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import yaml

from broker.agents.loader import load_agent_configs, load_agents
from broker.components.memory.seeding import seed_memory_from_agents


def test_seed_memory_from_agents_supports_strings_and_dict_metadata():
    calls = []

    class DummyEngine:
        def add_memory_for_agent(self, agent, content, metadata=None):
            calls.append((agent.id, content, metadata))

    agents = {
        "a1": SimpleNamespace(
            id="a1",
            memory=[
                "Year 0: plain profile line",
                {"content": "Year 0: seeded event", "metadata": {"origin": "seed", "importance": 0.8}},
                {"content": "Year 0: inline meta", "origin": "seed", "source": "survey"},
            ],
        )
    }
    engine = DummyEngine()
    seed_memory_from_agents(engine, agents)

    assert calls == [
        ("a1", "Year 0: plain profile line", None),
        ("a1", "Year 0: seeded event", {"origin": "seed", "importance": 0.8}),
        ("a1", "Year 0: inline meta", {"origin": "seed", "source": "survey"}),
    ]


def test_agents_loader_emits_deprecation_warnings(tmp_path):
    cfg_path = tmp_path / "inst.yaml"
    cfg_path.write_text(
        yaml.safe_dump({
            "agents": [
                {
                    "name": "reg_1",
                    "type": "regulator",
                    "skills": [{"id": "hold", "description": "Hold"}],
                }
            ]
        }),
        encoding="utf-8",
    )

    with pytest.warns(DeprecationWarning, match="load_agent_configs is deprecated"):
        configs = load_agent_configs(str(cfg_path))
    assert len(configs) == 1 and configs[0].name == "reg_1"

    with pytest.warns(DeprecationWarning, match="load_agents is deprecated"):
        agents = load_agents(str(cfg_path))
    assert "reg_1" in agents
