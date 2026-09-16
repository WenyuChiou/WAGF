"""P0-1c: the ADVISE disposition — behavioural contract.

The framework shipped two dispositions and neither could express "tell the model
about the rule, but do not block": a WARNING has NO channel to the model
(the retry loop opens only on `not all_valid`, and reports are built only from
`v.errors`, which is empty for a WARNING by construction). So the lab claim
"WARNING rules produce ~0% behaviour change" was architecturally forced rather
than measured, and could not be published.

These tests pin the third disposition that makes the question answerable, and in
particular the two properties the enforcement decomposition rests on:

  * EXACTLY ONE extra LLM call when an advisory fires — otherwise the advise arm
    is not sample-matched to the placebo arm and (C-B) silently reabsorbs the
    sampling term;
  * NEVER blocks — a persistent violator executes its own choice.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from broker.components.governance.registry import SkillRegistry
from broker.core._advise import (
    ADVISE_DENY, build_intervention_reports, demote, is_advisable,
    render_intervention_prompt,
)
from broker.core.skill_broker_engine import SkillBrokerEngine
from broker.interfaces.skill_types import (
    InterventionReport, SkillDefinition, SkillProposal, ValidationResult,
)
from broker.utils.agent_config import AgentTypeConfig
from broker.utils.model_adapter import UnifiedAdapter


# ---------------------------------------------------------------------------
# Config surface
# ---------------------------------------------------------------------------

def _cfg(global_config=None) -> AgentTypeConfig:
    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = {"global_config": global_config or {}}
    return cfg


def test_advise_absent_by_default():
    assert _cfg().get_governance_advise() is None
    assert _cfg({"governance": {}}).get_governance_advise() is None
    assert _cfg().get_governance_intervention_framing() == "legacy"
    assert _cfg().get_audit_advise_columns() is False


def test_advise_spec_parsed():
    spec = _cfg({"governance": {"advise": {"mode": "advise", "rule_ids": ["r1", "r2"]}}}
                ).get_governance_advise()
    assert spec["mode"] == "advise"
    assert spec["rule_ids"] == ["r1", "r2"]
    assert spec["placebo_text"]


@pytest.mark.parametrize("block,msg", [
    ({"advise": {"mode": "warn", "rule_ids": ["r1"]}}, "mode"),
    ({"advise": {"mode": "advise", "rule_ids": []}}, "rule_ids"),
    ({"advise": {"mode": "advise", "rule_ids": "r1"}}, "rule_ids"),
    ({"advise": {"mode": "advise", "rule_ids": ["affordability"]}}, "affordability"),
    ({"intervention_framing": "sneaky"}, "intervention_framing"),
])
def test_bad_arm_config_fails_loudly(block, msg):
    """A misspelled arm config must NOT silently produce a wrong-but-healthy run."""
    cfg = _cfg({"governance": block})
    with pytest.raises(ValueError, match=msg):
        if "intervention_framing" in block:
            cfg.get_governance_intervention_framing()
        else:
            cfg.get_governance_advise()


# ---------------------------------------------------------------------------
# Demotion predicate
# ---------------------------------------------------------------------------

def _blocking(rule_id, name="AgentValidator:thinking_error"):
    return ValidationResult(valid=False, validator_name=name, errors=["blocked"],
                            metadata={"rules_hit": [rule_id], "level": "ERROR"})


def test_demote_returns_same_object_when_off():
    """Object identity IS the flag-OFF byte-identity guarantee."""
    rs = [_blocking("r1")]
    assert demote(rs, frozenset()) is rs


def test_demote_never_mutates_input():
    """AgentValidator keeps long-lived references to these objects, and the engine
    is shared across a ThreadPoolExecutor — in-place edits would leak."""
    rs = [_blocking("r1")]
    demote(rs, frozenset({"r1"}))
    assert rs[0].valid is False and rs[0].errors == ["blocked"]
    assert "disposition" not in rs[0].metadata


def test_demote_moves_message_and_marks_disposition():
    out = demote([_blocking("r1")], frozenset({"r1"}))[0]
    assert out.valid is True
    assert out.errors == []
    assert out.warnings == ["blocked"]
    assert out.metadata["disposition"] == "ADVISE"
    assert out.metadata["advised_from_level"] == "ERROR"


def test_unlisted_rule_keeps_blocking():
    """Fails CLOSED — the allowlist cannot silently widen."""
    out = demote([_blocking("other")], frozenset({"r1"}))[0]
    assert out.valid is False


@pytest.mark.parametrize("rid", sorted(ADVISE_DENY))
def test_deny_set_never_demoted_even_if_listed(rid):
    """Hard feasibility gates must block regardless of config."""
    assert is_advisable(_blocking(rid), frozenset({rid})) is False


@pytest.mark.parametrize("name", ["AgentValidator:format", "AgentValidator:valid_decisions"])
def test_structural_validators_never_demoted(name):
    assert is_advisable(_blocking("r1", name=name), frozenset({"r1"})) is False


def test_result_without_rule_id_never_demoted():
    v = ValidationResult(valid=False, validator_name="x", errors=["e"], metadata={})
    assert is_advisable(v, frozenset({"r1"})) is False


# ---------------------------------------------------------------------------
# Prompt rendering — the arm-parity contract
# ---------------------------------------------------------------------------

def _report(summary, sug=None, sev="RULE"):
    return InterventionReport(rule_id="r1", blocked_skill="increase_large",
                              violation_summary=summary, suggested_correction=sug,
                              severity=sev, domain_context={})


def test_legacy_prompt_is_byte_identical_golden():
    """Pins the published arm-C prompt character for character."""
    a = UnifiedAdapter.__new__(UnifiedAdapter)
    got = a.format_retry_prompt("ORIGINAL PROMPT", [
        InterventionReport(rule_id="r1", blocked_skill="elevate_house",
                           violation_summary="Threat too low",
                           suggested_correction="try insurance", severity="ERROR",
                           domain_context={})
    ])
    assert got == (
        "Your previous response was flagged by the governance layer.\n\n"
        "**Issues Detected:**\n"
        "- [ERROR] Your proposed action 'elevate_house' was BLOCKED.\n"
        "  - Reason: Threat too low\n"
        "  - Suggestion: try insurance\n\n\n"
        "Please reconsider your decision. Ensure your new response addresses the violations above.\n\n"
        "ORIGINAL PROMPT"
    )


def test_advise_and_placebo_differ_on_exactly_the_reason_line():
    """(B - B') must isolate RULE CONTENT, so everything else must match."""
    a = UnifiedAdapter.__new__(UnifiedAdapter)
    advise, _ = a.format_intervention_prompt(
        "TASK", [_report("[Rule: r1] Increase blocked under high scarcity.", "reduce")],
        framing="neutral")
    placebo, _ = a.format_intervention_prompt(
        "TASK", [_report("A governance rule was triggered by this decision.", "reduce")],
        framing="neutral")
    al, pl = advise.split("\n"), placebo.split("\n")
    assert len(al) == len(pl)
    differing = [i for i, (x, y) in enumerate(zip(al, pl)) if x != y]
    assert differing, "the two arms must differ somewhere"
    assert all(al[i].lstrip().startswith("- Reason:") for i in differing)


def test_neutral_framing_never_says_blocked_and_hides_suggestion():
    """Advice must not claim the action was blocked — the agent can detect the lie,
    and the Suggestion line is absent from YAML rules but present on custom
    validators, so leaving it in makes report SHAPE covary with rule family."""
    a = UnifiedAdapter.__new__(UnifiedAdapter)
    out, _ = a.format_intervention_prompt("TASK", [_report("x", "do y")], framing="neutral")
    assert "BLOCKED" not in out
    assert "Suggestion" not in out
    assert "triggered a governance rule" in out


def test_wrapper_only_has_scaffolding_but_no_rule_content():
    a = UnifiedAdapter.__new__(UnifiedAdapter)
    out, shown = a.format_intervention_prompt(
        "TASK", [_report("secret rule text")], framing="neutral", include_reports=False)
    assert shown == 0
    assert "secret rule text" not in out
    assert "Rules Triggered" not in out
    assert out.endswith("TASK")


def test_legacy_adapter_without_new_method_still_works():
    """ModelAdapter is a user-extensible seam; requiring the new method would break
    every custom adapter that implements only format_retry_prompt."""
    class Legacy:
        def format_retry_prompt(self, prompt, errors, max_reports=None):
            return f"LEGACY::{prompt}::{len(errors)}"
    text, shown = render_intervention_prompt(Legacy(), "TASK", [_report("x")], framing="legacy")
    assert text.startswith("LEGACY::TASK::1")
    assert shown == 1


def test_legacy_adapter_rejects_neutral_framing_loudly():
    """Silently rendering the wrong text into an experiment arm would be worse."""
    class Legacy:
        def format_retry_prompt(self, prompt, errors, max_reports=None):
            return "x"
    with pytest.raises(ValueError, match="format_intervention_prompt"):
        render_intervention_prompt(Legacy(), "TASK", [_report("x")], framing="neutral")


def test_advisory_reports_built_only_from_advised_results():
    advised = demote([_blocking("r1")], frozenset({"r1"}))
    mixed = advised + [_blocking("r2")]
    proposal = SkillProposal(skill_name="increase_large", agent_id="A1", reasoning={})
    reports = build_intervention_reports(mixed, proposal, source="advisories", severity="RULE")
    assert [r.rule_id for r in reports] == ["r1"]
    assert reports[0].severity == "RULE"


# ---------------------------------------------------------------------------
# End-to-end: the two load-bearing behavioural guarantees
# ---------------------------------------------------------------------------

class _Ctx:
    def build(self, agent_id, env_context=None, **kwargs):
        return {"agent_id": agent_id, "state": {}}

    def format_prompt(self, context):
        return "PROMPT"


class _Writer:
    def __init__(self):
        self.traces = []

    def write_trace(self, agent_type, trace, history):
        self.traces.append(trace)


def _engine(*, mode, rule_ids, proposals, blocked_skills=("increase_large",),
            valid_skills=("increase_large", "decrease_small"), calls=None):
    """Engine whose validator blocks `blocked_skills` via rule 'r1'."""
    registry = SkillRegistry()
    for sid in valid_skills:
        registry.register(SkillDefinition(
            skill_id=sid, description=sid, eligible_agent_types=["*"],
            preconditions=[], institutional_constraints={},
            allowed_state_changes=[], implementation_mapping=sid,
        ))

    it = iter(proposals)
    last = {"p": None}

    def _parse(_raw, _ctx):
        try:
            last["p"] = next(it)
        except StopIteration:
            pass
        return last["p"]

    adapter = UnifiedAdapter.__new__(UnifiedAdapter)
    adapter.parse_output = _parse

    def _validate(proposal, _ctx, _reg=None):
        name = getattr(proposal, "skill_name", None)
        if name in blocked_skills:
            return ValidationResult(
                valid=False, validator_name="AgentValidator:thinking_error",
                errors=["Increase blocked under high scarcity."],
                metadata={"rules_hit": ["r1"], "level": "ERROR"})
        if name not in valid_skills:
            return ValidationResult(
                valid=False, validator_name="AgentValidator:valid_decisions",
                errors=[f"'{name}' is not a valid action."],
                metadata={"rules_hit": ["valid_actions"]})
        return ValidationResult(valid=True, validator_name="ok", errors=[], metadata={})

    validator = MagicMock()
    validator.validate.side_effect = _validate

    config = MagicMock()
    config.get_log_fields.return_value = []
    config.get_governance_retries.return_value = 3
    config.get_governance_max_reports.return_value = 20
    config.get_multi_skill_config.return_value = {}
    config.get_audit_initial_proposal_columns.return_value = True
    config.get_audit_executed_columns.return_value = True
    config.get_audit_advise_columns.return_value = True
    config.get_governance_advise.return_value = {
        "mode": mode, "rule_ids": list(rule_ids),
        "placebo_text": "A governance rule was triggered by this decision."}
    config.get_governance_intervention_framing.return_value = "neutral"

    eng = SkillBrokerEngine(
        skill_registry=registry, model_adapter=adapter, validators=[validator],
        simulation_engine=None, context_builder=_Ctx(), config=config,
    )
    writer = _Writer()
    eng.audit_writer = writer
    return eng, writer


def _P(name, **reasoning):
    return SkillProposal(skill_name=name, agent_id="A1",
                         reasoning=reasoning or {"WSA_LABEL": "H"}, parse_layer="mock")


def test_advise_issues_exactly_one_extra_call():
    """THE sample-matching guarantee. Attempt 0 + exactly one advisory = 2 calls."""
    calls = []
    eng, writer = _engine(mode="advise", rule_ids=["r1"],
                          proposals=[_P("increase_large"), _P("decrease_small")])
    eng.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                     llm_invoke=lambda p: calls.append(p) or "raw",
                     agent_type="farmer")
    t = writer.traces[0]
    assert len(calls) == 2, f"expected exactly 2 LLM calls, got {len(calls)}"
    assert t["advisory_fired"] is True
    assert t["advisory_llm_calls"] == 1
    assert t["llm_stats"]["llm_calls"] == 2
    assert t["retry_count"] == 0, "advice must not open the governance retry loop"
    assert t["advisory_skill_before"] == "increase_large"
    assert t["advisory_skill_after"] == "decrease_small"
    assert t["advisory_changed_action"] is True


def test_advise_never_blocks_persistent_violator_executes():
    """THE negative control. The agent violates the advised rule on BOTH attempts
    and must still execute its own choice — never the registry default."""
    eng, writer = _engine(mode="advise", rule_ids=["r1"],
                          proposals=[_P("increase_large"), _P("increase_large")])
    res = eng.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                           llm_invoke=lambda p: "raw", agent_type="farmer")
    t = writer.traces[0]
    assert t["advisory_fired"] is True
    assert t["advisory_changed_action"] is False
    assert t["post_advice_rules"] == "r1", "the rule still fired, it just did not block"
    assert t["approved_skill"]["status"] == "APPROVED"
    assert t["executed_skill"] == "increase_large"
    assert t["executed_via_fallback"] is False
    assert res.retry_count == 0


def test_tier0_floor_still_blocks_under_advise():
    """Advice must not disable the structural floor: a hallucinated skill name
    proposed AFTER the advisory is still caught and cannot execute."""
    eng, writer = _engine(mode="advise", rule_ids=["r1"],
                          proposals=[_P("increase_large"), _P("teleport_house"),
                                     _P("teleport_house"), _P("teleport_house"),
                                     _P("teleport_house")])
    eng.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                     llm_invoke=lambda p: "raw", agent_type="farmer")
    t = writer.traces[0]
    assert t["advisory_fired"] is True
    assert t["retry_count"] > 0, "the governance loop must still run on the floor"
    assert t["approved_skill"]["status"].startswith("REJECTED")
    assert t["executed_skill"] != "teleport_house"


def test_unparsable_advisory_keeps_attempt_zero_and_does_not_reask():
    """A second call here would silently unbalance arm B against arm B'."""
    calls = []
    eng, writer = _engine(mode="advise", rule_ids=["r1"],
                          proposals=[_P("increase_large"), None])
    eng.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                     llm_invoke=lambda p: calls.append(p) or "raw",
                     agent_type="farmer")
    t = writer.traces[0]
    assert len(calls) == 2, "must not re-ask after an unparsable advisory"
    assert t["advisory_parse_failed"] is True
    assert t["advisory_skill_after"] == "increase_large"


def test_placebo_mode_strips_rule_content_from_the_prompt():
    seen = []
    eng, _ = _engine(mode="placebo", rule_ids=["r1"],
                     proposals=[_P("increase_large"), _P("decrease_small")])
    eng.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                     llm_invoke=lambda p: seen.append(p) or "raw", agent_type="farmer")
    assert len(seen) == 2
    advisory_prompt = seen[1]
    assert "high scarcity" not in advisory_prompt
    assert "A governance rule was triggered by this decision." in advisory_prompt


def test_resample_mode_sends_the_original_prompt_unchanged():
    seen = []
    eng, _ = _engine(mode="resample", rule_ids=["r1"],
                     proposals=[_P("increase_large"), _P("decrease_small")])
    eng.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                     llm_invoke=lambda p: seen.append(p) or "raw", agent_type="farmer")
    assert len(seen) == 2
    assert seen[1] == seen[0], "arm A' must add no text at all"


def test_advise_off_is_a_total_no_op():
    """Flag-OFF: no advisory, no extra call, and no advisory keys in the trace."""
    calls = []
    eng, writer = _engine(mode="off", rule_ids=[],
                          proposals=[_P("increase_large"), _P("decrease_small"),
                                     _P("decrease_small"), _P("decrease_small")])
    eng.config.get_audit_advise_columns.return_value = False
    eng._count_llm_calls = False
    eng.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                     llm_invoke=lambda p: calls.append(p) or "raw", agent_type="farmer")
    t = writer.traces[0]
    assert "advise_mode" not in t
    assert "advisory_fired" not in t
    assert "llm_calls" not in t["llm_stats"]


# ---------------------------------------------------------------------------
# Review regressions (2026-07-29). Each pins a confirmed defect.
# ---------------------------------------------------------------------------

def test_mode_off_with_populated_rule_ids_does_not_demote():
    """CRITICAL regression. Authoring the control arm by flipping only `mode`
    while leaving rule_ids populated used to demote the rules anyway: they stopped
    blocking AND the advisory pass never fired, so the model was told nothing --
    reintroducing the exact 'WARNING has no channel' defect inside the arm that
    is supposed to be the no-op control."""
    spec = _cfg({"governance": {"advise": {"mode": "off", "rule_ids": ["r1"]}}}
                ).get_governance_advise()
    assert spec["mode"] == "off"
    assert spec["rule_ids"] == [], "mode=off must force an empty allowlist"

    eng, writer = _engine(mode="off", rule_ids=["r1"],
                          proposals=[_P("increase_large")] * 6)
    calls = []
    eng.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                     llm_invoke=lambda p: calls.append(p) or "raw", agent_type="farmer")
    t = writer.traces[0]
    assert t["advisory_fired"] is False
    # The rule must STILL BLOCK: retries happen and the proposal is not approved.
    assert t["retry_count"] > 0, "mode=off must leave the rule blocking"
    assert t["approved_skill"]["status"].startswith("REJECTED")
    assert t["executed_skill"] != "increase_large"


@pytest.mark.parametrize("rid", ["precondition_violation", "output_schema_violation"])
def test_registry_wide_floor_ids_are_undemotable(rid):
    """CRITICAL regression. These ids are stamped on EVERY skill's precondition /
    schema failure registry-wide, so advising one switches the floor off for the
    whole registry -- e.g. an already-elevated house could elevate again and
    execute a physically impossible mutation."""
    assert rid in ADVISE_DENY
    with pytest.raises(ValueError, match=rid):
        _cfg({"governance": {"advise": {"mode": "advise", "rule_ids": [rid]}}}
             ).get_governance_advise()
    assert is_advisable(_blocking(rid), frozenset({rid})) is False


def test_advisory_call_failure_keeps_attempt_zero_without_a_second_call():
    """WARNING regression. A transient failure must not become a second call --
    that would silently unmatch the advise arm from the placebo arm."""
    calls = []

    def _boom(prompt):
        calls.append(prompt)
        if len(calls) > 1:
            raise RuntimeError("provider hiccup")
        return "raw"

    eng, writer = _engine(mode="advise", rule_ids=["r1"],
                          proposals=[_P("increase_large"), _P("decrease_small")])
    eng.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                     llm_invoke=_boom, agent_type="farmer")
    t = writer.traces[0]
    assert len(calls) == 2, "must not retry the advisory call"
    assert t["advisory_parse_failed"] is True
    assert t["advisory_skill_after"] == "increase_large"


def test_advisory_stats_are_accounted_and_surface_failure():
    """WARNING regression. The advisory prompt is the LONGEST in the decision, so
    excluding it under-reported peak pressure on exactly the decisions where
    advice fired; and a failed advisory call was masked by attempt 0's success
    flag.

    2026-09-15 rewrite of the ASSERTIONS, not of the property. The per-call
    columns stopped being a running sum/max (a sum of prompt tokens over three
    attempts is not a prompt anyone sent, and it made `context_utilization`
    disagree with `prompt_tokens / num_ctx`), so the budget claim this test
    protects moved to `prompt_tokens_total` and the peak claim to
    `context_utilization_peak`. Both still fail if the advisory call is
    dropped from the accounting, which is what the test is for."""
    stats0 = SimpleNamespace(retries=0, success=True, prompt_tokens=100,
                             response_tokens=10, num_ctx=8192, context_utilization=0.10)
    stats1 = SimpleNamespace(retries=0, success=False, prompt_tokens=400,
                             response_tokens=20, num_ctx=8192, context_utilization=0.55)
    seq = iter([stats0, stats1])

    eng, writer = _engine(mode="advise", rule_ids=["r1"],
                          proposals=[_P("increase_large"), _P("decrease_small")])
    eng.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                     llm_invoke=lambda p: ("raw", next(seq)), agent_type="farmer")
    ls = writer.traces[0]["llm_stats"]
    assert ls["prompt_tokens_total"] == 500, "token totals must accumulate"
    assert ls["response_tokens_total"] == 30
    assert ls["llm_calls_total"] == 2, "the advisory call is a call"
    assert ls["prompt_tokens"] == 400, "per-call columns describe ONE call"
    assert ls["context_utilization"] == 0.55
    assert ls["context_utilization_peak"] == 0.55, "the peak must survive"
    assert ls["llm_success"] is False, "a failed advisory call must not be masked"


def test_attempt_skills_still_indexes_every_attempt():
    """P0-1a's invariant widens: 1 (attempt 0) + advisory calls + retries."""
    eng, writer = _engine(mode="advise", rule_ids=["r1"],
                          proposals=[_P("increase_large"), _P("decrease_small")])
    eng.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                     llm_invoke=lambda p: "raw", agent_type="farmer")
    t = writer.traces[0]
    attempts = t["attempt_skills"].split("|")
    assert attempts == ["increase_large", "decrease_small"]
    assert len(attempts) == 1 + t["advisory_llm_calls"] + t["retry_count"]
