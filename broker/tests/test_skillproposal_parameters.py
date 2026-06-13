"""Phase 6W-B1 — SkillProposal.parameters field byte-identity + round-trip invariant.

Guards the multi-dimensional-action proposal field added in B1. The load-bearing
properties:
  * default {} (single-scalar legacy behaviour),
  * to_dict() omits the key when empty so frozen-domain JSONL/CSV stay byte-identical,
  * the undocumented invariant the frozen parametric SQ1 path relies on:
    SkillProposal(**proposal.to_dict()) must round-trip (every to_dict key is a
    constructor field). This test pins it so a future to_dict-only key can't silently
    TypeError on the frozen parametric_decider.py:_proposal_from_dict path.
See .research/wagf_coupling_IMPLEMENTATION_PLAN_2026-06-12.md (B1, risk R2).
"""
import inspect

from broker.interfaces.skill_types import SkillProposal

# The exact frozen pre-6W-B key set + order (skill_types.py:48-59). Locks ordering.
_LEGACY_KEYS = [
    "skill_name", "agent_id", "agent_type", "reasoning", "confidence",
    "raw_output", "parsing_warnings", "parse_layer", "parse_confidence",
    "construct_completeness", "magnitude_pct", "magnitude_fallback",
]


def _base(**over):
    kw = dict(skill_name="action_a", agent_id="H0001", reasoning={"threat": "M"})
    kw.update(over)
    return SkillProposal(**kw)


def test_default_empty():
    assert _base().parameters == {}


def test_no_shared_mutable_default():
    a, b = _base(), _base()
    a.parameters["x"] = 1.0
    assert b.parameters == {}, "field(default_factory=dict) must not share one dict"


def test_to_dict_omits_empty_parameters_and_preserves_order():
    d = _base().to_dict()
    assert "parameters" not in d, "empty parameters must NOT appear in to_dict (byte-identity)"
    assert list(d.keys()) == _LEGACY_KEYS, "frozen 12-key order must be unchanged"


def test_to_dict_emits_nonempty_parameters_last():
    d = _base(parameters={"release_cms": 12.0, "hydropower_mw": 800.0}).to_dict()
    assert d["parameters"] == {"release_cms": 12.0, "hydropower_mw": 800.0}
    assert list(d.keys()) == _LEGACY_KEYS + ["parameters"], "parameters must append last"


def test_roundtrip_invariant_empty_and_nonempty():
    """SkillProposal(**to_dict()) must succeed — the frozen parametric path depends on it."""
    ctor_params = set(inspect.signature(SkillProposal).parameters)
    for params in ({}, {"release_cms": 5.0}):
        p = _base(parameters=params)
        d = p.to_dict()
        # every emitted key is a real constructor field (the splat invariant)
        assert set(d).issubset(ctor_params), (
            f"to_dict emitted non-constructor key(s): {set(d) - ctor_params}"
        )
        rebuilt = SkillProposal(**d)  # must not raise
        assert rebuilt.parameters == params
        assert rebuilt.skill_name == p.skill_name


def test_legacy_magnitude_path_untouched():
    p = _base(magnitude_pct=50.0, magnitude_fallback=True)
    d = p.to_dict()
    assert d["magnitude_pct"] == 50.0 and d["magnitude_fallback"] is True
    assert "parameters" not in d  # magnitude alone does not populate parameters (B1)
