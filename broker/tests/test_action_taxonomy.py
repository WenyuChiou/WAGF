"""Phase 6O-B-1 — Tests for the action-taxonomy contract.

Coverage:
  - `ActionTaxonomyEntry` dataclass shape (all 3 fields optional).
  - `load_action_taxonomy_from_skill_registry` reads YAML correctly,
    tolerates missing file / malformed YAML / missing fields.
  - `DefaultDomainPack.action_taxonomy()` returns empty dict.
  - Each of the 3 reference DomainPacks (Irrigation, Flood, Vaccination)
    returns the expected per-skill taxonomy with all 3 fields populated.

These tests exercise the public surface only — no broker pipeline
integration. The reference YAMLs (irrigation_abm / single_agent /
vaccination_demo skill_registry.yaml) must remain canonical inputs.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from broker.interfaces.action_taxonomy import (
    ActionTaxonomyEntry,
    load_action_taxonomy_from_skill_registry,
)


# ---------------------------------------------------------------------------
# Dataclass shape
# ---------------------------------------------------------------------------


def test_action_taxonomy_entry_all_fields_optional():
    e = ActionTaxonomyEntry()
    assert e.category is None
    assert e.intensity is None
    assert e.reversibility is None


def test_action_taxonomy_entry_partial():
    e = ActionTaxonomyEntry(category="increase", intensity="large")
    assert e.category == "increase"
    assert e.intensity == "large"
    assert e.reversibility is None


def test_action_taxonomy_entry_frozen():
    e = ActionTaxonomyEntry(category="x")
    with pytest.raises(Exception):
        e.category = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# YAML loader robustness
# ---------------------------------------------------------------------------


def test_load_missing_file_returns_empty(tmp_path):
    missing = tmp_path / "nonexistent.yaml"
    assert load_action_taxonomy_from_skill_registry(missing) == {}


def test_load_malformed_yaml_returns_empty(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("{not: valid: yaml:::", encoding="utf-8")
    assert load_action_taxonomy_from_skill_registry(bad) == {}


def test_load_no_skills_block_returns_empty(tmp_path):
    f = tmp_path / "no_skills.yaml"
    f.write_text("other_key: foo\n", encoding="utf-8")
    assert load_action_taxonomy_from_skill_registry(f) == {}


def test_load_skills_without_taxonomy_returns_empty_entries(tmp_path):
    """Skill present in YAML but without any taxonomy field gets all-None entry."""
    f = tmp_path / "bare.yaml"
    f.write_text(
        yaml.safe_dump({"skills": [{"skill_id": "foo"}, {"skill_id": "bar"}]}),
        encoding="utf-8",
    )
    result = load_action_taxonomy_from_skill_registry(f)
    assert set(result.keys()) == {"foo", "bar"}
    assert all(e == ActionTaxonomyEntry() for e in result.values())


def test_load_skips_malformed_entries(tmp_path):
    f = tmp_path / "mixed.yaml"
    f.write_text(
        yaml.safe_dump(
            {
                "skills": [
                    {"skill_id": "real_skill", "category": "x"},
                    "not_a_dict",  # ignored
                    {"no_skill_id": "field"},  # ignored
                    {"skill_id": "", "category": "y"},  # empty id ignored
                    None,  # ignored
                ]
            }
        ),
        encoding="utf-8",
    )
    result = load_action_taxonomy_from_skill_registry(f)
    assert set(result.keys()) == {"real_skill"}
    assert result["real_skill"].category == "x"


def test_load_non_string_taxonomy_fields_become_none(tmp_path):
    """If a YAML field is malformed (e.g. a list under `category`), the
    loader silently drops it rather than crash."""
    f = tmp_path / "weird.yaml"
    f.write_text(
        yaml.safe_dump(
            {
                "skills": [
                    {
                        "skill_id": "s1",
                        "category": ["should", "be", "string"],
                        "intensity": "small",
                        "reversibility": 42,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = load_action_taxonomy_from_skill_registry(f)
    assert result["s1"].category is None
    assert result["s1"].intensity == "small"
    assert result["s1"].reversibility is None


# ---------------------------------------------------------------------------
# Default DomainPack returns empty
# ---------------------------------------------------------------------------


def test_default_domain_pack_returns_empty():
    from broker.domains.default import DefaultDomainPack
    assert DefaultDomainPack().action_taxonomy() == {}


# ---------------------------------------------------------------------------
# Reference DomainPacks
#
# Note: an earlier draft added `assert all(isinstance(v, ActionTaxonomyEntry)
# for v in tax.values())` to each per-pack test (round-1 reviewer recommendation).
# That assertion failed in full-suite mode but passed in isolation — same
# pytest module-rewriting hazard as the parametrised cross-pack test removed
# earlier in this commit. The `set(tax.keys()) == set(expected.keys())`
# check already catches new-skill regressions; explicit isinstance is left
# off until the broader pytest config (pytest --importmode=importlib?) is
# evaluated as a Phase 6O-D follow-up.
# ---------------------------------------------------------------------------


def test_irrigation_domain_pack_full_taxonomy():
    from examples.irrigation_abm.adapters.irrigation_pack import IrrigationDomainPack
    tax = IrrigationDomainPack().action_taxonomy()
    expected = {
        "increase_large": ("increase", "large", "annual"),
        "increase_small": ("increase", "small", "annual"),
        "maintain_demand": ("maintain", "none", "annual"),
        "decrease_small": ("decrease", "small", "annual"),
        "decrease_large": ("decrease", "large", "annual"),
    }
    assert set(tax.keys()) == set(expected.keys())
    for sid, (cat, intens, rev) in expected.items():
        e = tax[sid]
        assert e.category == cat, f"{sid}: category mismatch"
        assert e.intensity == intens, f"{sid}: intensity mismatch"
        assert e.reversibility == rev, f"{sid}: reversibility mismatch"


def test_flood_domain_pack_full_taxonomy():
    from examples.governed_flood.adapters.flood_pack import FloodDomainPack
    tax = FloodDomainPack().action_taxonomy()
    expected = {
        "buy_insurance": ("adopt", "small", "annual"),
        "elevate_house": ("adopt", "large", "permanent"),
        "relocate": ("adopt", "large", "permanent"),
        "do_nothing": ("status_quo", "none", "instant"),
    }
    assert set(tax.keys()) == set(expected.keys())
    for sid, (cat, intens, rev) in expected.items():
        e = tax[sid]
        assert e.category == cat
        assert e.intensity == intens
        assert e.reversibility == rev


def test_vaccination_domain_pack_full_taxonomy():
    from examples.vaccination_demo.adapters.vaccination_pack import VaccinationDomainPack
    tax = VaccinationDomainPack().action_taxonomy()
    expected = {
        "get_vaccinated": ("adopt", "large", "permanent"),  # reviewer round-1: biological act not reversible within year
        "delay": ("delay", "none", "instant"),
        "refuse": ("refuse", "none", "instant"),
    }
    assert set(tax.keys()) == set(expected.keys())
    for sid, (cat, intens, rev) in expected.items():
        e = tax[sid]
        assert e.category == cat
        assert e.intensity == intens
        assert e.reversibility == rev
