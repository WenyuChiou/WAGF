"""Phase 6W-B3 — per-skill param_specs() SkillPack hook + loader.

Mirrors test_action_taxonomy. Proves: the opt-in loader reads a domain's OWN
skill_registry.yaml param_specs block into coupling VarSpecs (one bounds
vocabulary — AR-6); the default pack + the FROZEN paper-3 registry yield {} (no
byte-identity / skill-iteration perturbation); a malformed numeric spec fails
LOUD at load. See .research/wagf_coupling_IMPLEMENTATION_PLAN_2026-06-12.md (B3).
"""
from pathlib import Path

import pytest

from broker.domains.default import DefaultDomainPack
from broker.interfaces.param_spec import load_param_specs_from_skill_registry

_VALID = """
skills:
  - skill_id: set_release
    param_specs:
      - { name: release_cms, unit: cms, lo: 0.0, hi: 850.0 }
      - { name: hydropower_mw, unit: MW, lo: 0.0, hi: 2000.0 }
  - skill_id: do_nothing
"""


def test_default_pack_param_specs_empty():
    assert DefaultDomainPack().param_specs() == {}


def test_loader_absent_file_returns_empty(tmp_path):
    assert load_param_specs_from_skill_registry(tmp_path / "nope.yaml") == {}


def test_loader_no_param_specs_block(tmp_path):
    p = tmp_path / "sr.yaml"
    p.write_text("skills:\n  - skill_id: a\n", encoding="utf-8")
    assert load_param_specs_from_skill_registry(p) == {}


def test_loader_builds_varspecs(tmp_path):
    p = tmp_path / "sr.yaml"
    p.write_text(_VALID, encoding="utf-8")
    specs = load_param_specs_from_skill_registry(p)
    assert set(specs) == {"set_release"}  # do_nothing declares none -> omitted
    vs_list = specs["set_release"]
    assert [v.name for v in vs_list] == ["release_cms", "hydropower_mw"]
    vs = vs_list[0]
    assert vs.unit == "cms" and vs.lo == 0.0 and vs.hi == 850.0
    assert vs.direction == "agent_to_world" and vs.value_source == "proposal"
    # range_violation is the bounds check B4 will reuse (AR-6)
    assert vs.range_violation(900.0) is not None  # above hi
    assert vs.range_violation(100.0) is None


def test_loader_malformed_numeric_empty_unit_fails_loud(tmp_path):
    bad = "skills:\n  - skill_id: x\n    param_specs:\n      - { name: r, lo: 0, hi: 1 }\n"
    p = tmp_path / "bad.yaml"
    p.write_text(bad, encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty unit"):
        load_param_specs_from_skill_registry(p)


def test_loader_malformed_lo_gt_hi_fails_loud(tmp_path):
    bad = "skills:\n  - skill_id: x\n    param_specs:\n      - { name: r, unit: cms, lo: 9, hi: 1 }\n"
    p = tmp_path / "bad.yaml"
    p.write_text(bad, encoding="utf-8")
    with pytest.raises(ValueError, match=r"lo .* > hi"):
        load_param_specs_from_skill_registry(p)


def test_frozen_paper3_registry_has_no_param_specs():
    """The frozen MA-flood skill_registry.yaml (md5 58a0da94) declares no
    param_specs -> loader returns {} -> no perturbation of the frozen skill set."""
    fr = Path(__file__).resolve().parents[2] / "examples/multi_agent/flood/config/skill_registry.yaml"
    if not fr.is_file():
        pytest.skip("frozen registry not present in this checkout")
    assert load_param_specs_from_skill_registry(fr) == {}
