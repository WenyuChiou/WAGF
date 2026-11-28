from pathlib import Path

import yaml
_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def test_skill_registry_preconditions_are_exactly_the_two_wp2_preconditions():
    """Pin the registry preconditions that backstop the identity rules."""
    with open(_CONFIG_DIR / "skill_registry.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    all_preconditions = set()
    for skill in data.get("skills", []):
        all_preconditions.update(skill.get("preconditions") or [])
    assert all_preconditions == {"not at_allocation_cap", "not at_beneficial_use_limit", "not below_minimum_utilisation"}
