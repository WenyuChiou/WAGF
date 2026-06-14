"""Phase 6W deferred — cognitive-cache reconstruction must preserve multi-dim params.

Regression guard for the cache-hit `SkillProposal` reconstruction in
`broker/core/experiment_runner.py`. The legacy inline reconstruction copied only
four fields and silently DROPPED `SkillProposal.parameters` (the 6W multi-field
setpoint dict) on every cache hit — so a cached replay of a multi-dimensional
action lost its setpoints. `_rebuild_cached_proposal` threads `parameters` back.

The cognitive cache is opt-in (`enable_cognitive_cache=False` by default), so no
frozen/paper run reaches this path; these tests pin the reconstruction contract
directly on the extracted helper rather than spinning up a full runner.

See .research/wagf_coupling_IMPLEMENTATION_PLAN_2026-06-12.md (deferred A).
"""
from broker.core.experiment_runner import _rebuild_cached_proposal


def test_cache_reconstruction_threads_multidim_parameters():
    """A cached proposal carrying setpoints must rebuild WITH those setpoints."""
    cached = {
        "skill_name": "set_release_multi",
        "reasoning": {"threat": "high inflow"},
        "agent_type": "operator",
        "parameters": {"release_cms": 12.0, "hydropower_mw": 800.0},
    }
    proposal = _rebuild_cached_proposal(
        cached,
        skill_name=cached["skill_name"],
        agent_id="OP-1",
        reasoning=cached["reasoning"],
        agent_type="operator",
    )
    assert proposal.parameters == {"release_cms": 12.0, "hydropower_mw": 800.0}
    # round-trips back out (to_dict emits the key when non-empty)
    assert proposal.to_dict()["parameters"] == cached["parameters"]


def test_cache_reconstruction_frozen_domain_stays_byte_identical():
    """A frozen-domain cached entry has no `parameters` key -> rebuild yields {}
    -> to_dict OMITS the key -> byte-identical to the pre-6W reconstruction."""
    cached = {"skill_name": "do_nothing", "reasoning": {}}  # no parameters key
    proposal = _rebuild_cached_proposal(
        cached,
        skill_name=cached["skill_name"],
        agent_id="H-1",
        reasoning={},
        agent_type="household",
    )
    assert proposal.parameters == {}
    assert "parameters" not in proposal.to_dict()  # key-gated omission


def test_cache_reconstruction_honours_deliberate_overrides():
    """The validation-path reconstruction intentionally overrides skill_name
    (approved, not proposed) and agent_type (current agent) — the helper must NOT
    pull those from the cached dict, only `parameters`."""
    cached = {
        "skill_name": "proposed_skill",
        "reasoning": {"x": "y"},
        "agent_type": "cached_type",
        "parameters": {"q": 1.0},
    }
    proposal = _rebuild_cached_proposal(
        cached,
        skill_name="approved_skill",          # override (approved name)
        agent_id="A-9",
        reasoning=cached["reasoning"],
        agent_type="current_type",            # override (current agent)
    )
    assert proposal.skill_name == "approved_skill"
    assert proposal.agent_type == "current_type"
    assert proposal.parameters == {"q": 1.0}  # params still threaded from cache


def test_cache_reconstruction_none_cached_proposal_is_safe():
    """Defensive: a None cached_proposal (falsy skill_proposal) must not raise."""
    proposal = _rebuild_cached_proposal(
        None,
        skill_name="default_skill",
        agent_id="A-0",
        reasoning={},
        agent_type="default",
    )
    assert proposal.parameters == {}
    assert proposal.skill_name == "default_skill"
