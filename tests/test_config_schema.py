import pytest
from pathlib import Path

from broker.config.schema import load_agent_config, MemoryConfig


def test_valid_config_loads_sa():
    config = load_agent_config(Path("examples/single_agent/agent_types.yaml"))
    assert config.global_config.memory.window_size == 5


def test_valid_config_loads_ma():
    config = load_agent_config(Path("examples/multi_agent/config/agents/agent_types.yaml"))
    assert config.global_config.memory.window_size == 5


def test_invalid_engine_type_raises():
    with pytest.raises(ValueError):
        MemoryConfig(engine_type="invalid")


def test_all_memory_engine_types():
    for engine in ["window", "importance", "humancentric", "hierarchical", "universal", "unified"]:
        config = MemoryConfig(engine_type=engine)
        assert config.engine_type == engine
