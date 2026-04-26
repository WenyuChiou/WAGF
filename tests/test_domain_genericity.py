"""Domain-genericity smoke tests for the broker layer.

Verifies that broker components do not silently fall back to
flood-specific defaults when no domain config is supplied.

Phase 6A landing tests — see broker/INVARIANTS.md Invariant 6.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from broker.components.governance.registry import SkillRegistry
from broker.components.governance.retriever import SkillRetriever


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_registry_default_warns_without_yaml(caplog):
    """Empty registry returns the legacy 'do_nothing' fallback but
    emits a one-time warning telling the caller to declare default_skill
    in skill_registry.yaml."""
    reg = SkillRegistry()
    with caplog.at_level(logging.WARNING, logger="broker.components.governance.registry"):
        result = reg.get_default_skill()
    assert result == "do_nothing"  # backward-compat preserved
    assert any(
        "default_skill not declared" in rec.message for rec in caplog.records
    ), "Expected a warning about missing default_skill in YAML"

    # Warning fires only once per registry instance
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="broker.components.governance.registry"):
        reg.get_default_skill()
    assert not any(
        "default_skill not declared" in rec.message for rec in caplog.records
    ), "Warning should be one-time per registry instance"


def test_registry_default_from_irrigation_yaml():
    """Loading irrigation skill_registry.yaml gives 'maintain_demand'
    as default — proving the registry is not flood-flavoured."""
    yaml_path = REPO_ROOT / "examples" / "irrigation_abm" / "config" / "skill_registry.yaml"
    if not yaml_path.exists():
        pytest.skip(f"Irrigation YAML not present: {yaml_path}")
    reg = SkillRegistry()
    reg.register_from_yaml(str(yaml_path))
    assert reg.get_default_skill() == "maintain_demand"


def test_retriever_empty_global_skills_no_flood_default():
    """SkillRetriever without global_skills returns empty list (no
    automatic 'do_nothing' fallback) so domain-agnostic callers don't
    inherit a flood-specific magic value."""
    retriever = SkillRetriever()
    assert retriever.global_skills == []
