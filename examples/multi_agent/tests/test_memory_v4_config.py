import yaml
from pathlib import Path


def test_symbolic_memory_config_exists():
    config_path = Path("examples/multi_agent/ma_agent_types.yaml")
    data = yaml.safe_load(config_path.read_text())
    memory_config = data.get("memory_config", {})
    household = memory_config.get("household_owner", {})
    assert household.get("engine") == "symbolic"
    assert household.get("sensors")
    assert household.get("scorer") == "flood"
