"""Generic framework options added for irrigation v3 WP4 (all opt-in).

Spec: .research/design_specs/irrigation_v3_spec_2026-09-28.md, 4.6 to 4.8
and PI item 8. Every option defaults to the shipped behaviour, so a domain
that does not set it (flood) renders and stores exactly what it did before:

- ``reflection.keep_latest_only`` with ``HumanCentricMemoryEngine.remove_by_type``
  and ``store_reflection_memory`` (keep only an agent's latest reflection);
- ``generate_batch_reflection_prompt`` says "1 agent" for a one-agent batch;
- ``feedback.show_trend`` and a tracked metric's ``display: false``;
- ``governance.plain_action_names`` and ``governance.placebo_closer``;
- the empty feasible-set line after an attempt that left out a required
  field names that cause instead of implying every action is ruled out.

Each test fails on the code before WP4 (the options, methods and wording
did not exist).
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from broker.components.analytics.feedback import AgentMetricsTracker, FeedbackDashboardProvider
from broker.components.cognitive.reflection import ReflectionEngine, store_reflection_memory
from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine
from broker.components.memory.engines.window import WindowMemoryEngine
from broker.core._advise import render_intervention_prompt
from broker.core._retry_loop import RETRY_FEEDBACK_PLACEBO_TEXT, RetryMixin
from broker.interfaces.skill_types import SkillProposal, ValidationResult
from broker.utils.agent_config import AgentTypeConfig
from broker.utils.parsing.unified_adapter import UnifiedAdapter

REPO = Path(__file__).resolve().parents[2]
FLOOD_CONFIG = REPO / "examples" / "single_agent" / "agent_types.yaml"
IRRIGATION_CONFIG = REPO / "examples" / "irrigation_abm" / "config" / "agent_types.yaml"


def _cfg(raw: Dict[str, Any]) -> AgentTypeConfig:
    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = raw
    return cfg


# ---------------------------------------------------------------------------
# keep only the latest reflection (PI item 8, spec 4.7)
# ---------------------------------------------------------------------------

def _engine() -> HumanCentricMemoryEngine:
    # importance 1.0 with consolidation_prob 1.0: every item is also copied to
    # long-term memory, so removal must reach both stores.
    return HumanCentricMemoryEngine(consolidation_prob=1.0, consolidation_threshold=0.0, seed=1)


def _meta(kind: str) -> Dict[str, Any]:
    return {"importance": 1.0, "emotion": "major", "source": "personal", "type": kind}


def test_remove_by_type_reaches_both_stores_and_keeps_the_timestamp_sequence():
    eng, twin = _engine(), _engine()
    for e in (eng, twin):
        e.add_memory("A", "outcome 1", _meta("outcome"))
        e.add_memory("A", "lesson 1", _meta("reflection"))
        e.add_memory("A", "outcome 2", _meta("outcome"))
    assert eng.remove_by_type("A", "reflection") == 2  # working and long-term copy
    assert [m["content"] for m in eng.working["A"]] == ["outcome 1", "outcome 2"]
    assert [m["content"] for m in eng.longterm["A"]] == ["outcome 1", "outcome 2"]
    assert eng.remove_by_type("A", "reflection") == 0
    assert eng.remove_by_type("nobody", "reflection") == 0
    # A memory added after the removal gets the timestamp it would have had
    # without it, so decay and recency of the remaining items are unchanged.
    eng.add_memory("A", "outcome 3", _meta("outcome"))
    twin.add_memory("A", "outcome 3", _meta("outcome"))
    assert eng.working["A"][-1]["timestamp"] == twin.working["A"][-1]["timestamp"]
    eng.clear("A")
    eng.add_memory("A", "fresh", _meta("outcome"))
    assert eng.working["A"][-1]["timestamp"] == 0


def test_timestamps_unchanged_when_nothing_is_removed():
    """The default path (flood): no removal, the exact shipped timestamps."""
    eng = _engine()
    for i in range(4):
        eng.add_memory("A", f"m{i}", _meta("outcome"))
    # each item is stored twice (working + long-term), as before WP4
    assert [m["timestamp"] for m in eng.working["A"]] == [0, 2, 4, 6]


def test_engine_without_remove_by_type_raises():
    with pytest.raises(NotImplementedError, match="remove_by_type"):
        WindowMemoryEngine(window_size=3).remove_by_type("A", "reflection")


def test_store_reflection_memory_keep_latest_on_and_off():
    on, off = _engine(), _engine()
    for i in range(3):
        store_reflection_memory(on, "A", f"lesson {i}", _meta("reflection"), keep_latest_only=True)
        store_reflection_memory(off, "A", f"lesson {i}", _meta("reflection"))
    assert [m["content"] for m in on.working["A"]] == ["lesson 2"]
    assert [m["content"] for m in on.longterm["A"]] == ["lesson 2"]
    assert [m["content"] for m in off.working["A"]] == ["lesson 0", "lesson 1", "lesson 2"]
    with pytest.raises(ValueError, match="type"):
        store_reflection_memory(on, "A", "x", {"importance": 0.5}, keep_latest_only=True)


def test_keep_latest_only_getter_default_off_and_bool_only():
    assert _cfg({"global_config": {}}).get_reflection_keep_latest_only() is False
    on = _cfg({"global_config": {"reflection": {"keep_latest_only": True}}})
    assert on.get_reflection_keep_latest_only() is True
    with pytest.raises(ValueError, match="keep_latest_only"):
        _cfg({"global_config": {"reflection": {"keep_latest_only": "true"}}}
             ).get_reflection_keep_latest_only()
    # get_reflection_config's returned dict is unchanged when the key is absent
    assert "keep_latest_only" not in _cfg({"global_config": {}}).get_reflection_config()


def test_reflection_prompt_singular_for_one_agent():
    eng = ReflectionEngine()
    one = eng.generate_batch_reflection_prompt([{"agent_id": "A", "memories": ["m"]}], 2021)
    two = eng.generate_batch_reflection_prompt(
        [{"agent_id": "A", "memories": ["m"]}, {"agent_id": "B", "memories": ["m"]}], 3)
    assert "You are a Reflection Assistant for 1 agent in a simulation (Year 2021)." in one
    assert "You are a Reflection Assistant for 2 agents in a simulation (Year 3)." in two


# ---------------------------------------------------------------------------
# feedback dashboard: show_trend and display (spec 4.6)
# ---------------------------------------------------------------------------

def _dashboard(config: Dict[str, Any]) -> str:
    names = [m["name"] for m in config["tracked_metrics"]]
    tracker = AgentMetricsTracker(names, window=5)
    for year, supply in ((2019, 100.0), (2020, 80.0), (2021, 60.0)):
        tracker.record("A", year, {"request": 100.0, "supply": supply, "flag": 1.0})
    ctx: Dict[str, Any] = {}
    FeedbackDashboardProvider(tracker, config).provide("A", {}, ctx, env_context={})
    return ctx["feedback_dashboard"]


_METRICS = [
    {"name": "request", "source": "r", "unit": "AF", "format": ",.0f"},
    {"name": "supply", "source": "s", "unit": "AF", "format": ",.0f"},
]


def test_dashboard_defaults_render_as_shipped():
    text = _dashboard({"tracked_metrics": _METRICS + [{"name": "flag", "source": "f"}]})
    assert "TREND: request STABLE, supply FALLING, flag STABLE" in text
    assert "flag ()" in text


def test_dashboard_show_trend_false_and_hidden_metric():
    config = {"show_trend": False, "tracked_metrics": _METRICS + [
        {"name": "flag", "source": "f", "display": False}],
        "assertions": [{"when": "flag >= 1", "message": "flag seen"}]}
    text = _dashboard(config)
    assert "TREND" not in text
    assert "flag" not in text.split("WARNING")[0]  # no column, no trend part
    assert "Year | request (AF) | supply (AF)" in text
    assert "2021 |" in text
    assert "WARNING: flag seen" in text  # still usable in an assertion
    with pytest.raises(ValueError, match="show_trend"):
        FeedbackDashboardProvider(AgentMetricsTracker([], 5),
                                  {"show_trend": "no", "tracked_metrics": []})
    with pytest.raises(ValueError, match="display"):
        FeedbackDashboardProvider(AgentMetricsTracker([], 5), {"tracked_metrics": [
            {"name": "x", "source": "x", "display": "false"}]})


# ---------------------------------------------------------------------------
# retry text: plain action names, placebo closer, missing-field line (4.8)
# ---------------------------------------------------------------------------

SKILLS = ["grow_more", "keep_same", "cut_back"]


class _Registry:
    def list_skills(self):
        return list(SKILLS)

    def exists(self, name):
        return name in SKILLS

    def check_eligibility(self, name, agent_type):
        return SimpleNamespace(valid=True)

    def get_default_skill(self):
        return "keep_same"


class _Auditor:
    def log_parse_error(self):
        pass


def _block_grow(proposal, context):
    if proposal.skill_name == "grow_more":
        return [ValidationResult(valid=False, validator_name="v", errors=["grow blocked"],
                                 metadata={"rule_id": "no_grow"})]
    return [ValidationResult(valid=True, validator_name="v")]


def _missing_field(proposal, context):
    return [ValidationResult(valid=False, validator_name="AgentValidator:format",
                             errors=["Response missing required fields: x_assessment"],
                             metadata={"rule": "format"})]


class _Host(RetryMixin):
    max_retries = 1
    max_reports = 3

    def __init__(self, validator=_block_grow, mode="full", plain=None, closer=None):
        self.auditor = _Auditor()
        self.model_adapter = UnifiedAdapter.__new__(UnifiedAdapter)
        self._retry_feedback_mode = mode
        self._intervention_framing = "legacy"
        self._feasible_set_feedback = True
        self._on_retry_exhausted = "default"
        self.skill_registry = _Registry()
        self.config = SimpleNamespace(get_skill_map=lambda at, ctx: {
            str(i + 1): s for i, s in enumerate(SKILLS)})
        self._validator = validator
        if plain is not None:
            self._plain_action_names = plain
        if closer is not None:
            self._placebo_closer = closer

    def _run_validators(self, proposal, context):
        return self._validator(proposal, context)


def _first_retry_prompt(host, skill="grow_more"):
    prompts = []

    def llm_invoke(p):
        prompts.append(p)
        return SkillProposal(skill_name="keep_same", agent_id="A1", agent_type="t",
                             reasoning={"X_LABEL": "M"})

    proposal = SkillProposal(skill_name=skill, agent_id="A1", agent_type="t",
                             reasoning={"X_LABEL": "M"})
    results = host._validator(proposal, {})
    host._governance_retry_loop(
        all_valid=False, skill_proposal=proposal, validation_results=results,
        all_validation_history=list(results), validation_context={}, prompt="ORIGINAL",
        llm_invoke=llm_invoke, context={}, agent_id="A1", agent_type="t",
        env_context={}, raw_output="raw",
        total_llm_stats={"llm_retries": 0, "llm_success": False},
    )
    return prompts[0]


def test_plain_action_names_off_by_default_on_when_set():
    off = _first_retry_prompt(_Host())
    on = _first_retry_prompt(_Host(plain=True))
    assert "Your proposed action 'grow_more' was BLOCKED." in off
    assert "Your proposed action 'grow more' was BLOCKED." in on
    assert "grow_more" not in on
    assert on.replace("'grow more'", "'grow_more'") == off  # nothing else differs


def test_placebo_closer_replaces_the_closer_only_in_placebo():
    default = _first_retry_prompt(_Host(mode="placebo"))
    custom = _first_retry_prompt(_Host(mode="placebo", closer="Please reconsider your decision."))
    assert default == (
        "Your previous response was flagged by the governance layer.\n\n"
        "Please reconsider your decision. Ensure your new response addresses the "
        "violations above.\n\nORIGINAL")
    assert custom == (
        "Your previous response was flagged by the governance layer.\n\n"
        "Please reconsider your decision.\n\nORIGINAL")
    # full mode keeps the shipped closer whatever placebo_closer says
    full = _first_retry_prompt(_Host(closer="Please reconsider your decision."))
    assert "Ensure your new response addresses the violations above." in full
    # an adapter without format_intervention_prompt cannot render a closer
    legacy = SimpleNamespace(format_retry_prompt=lambda *a, **k: "x")
    with pytest.raises(ValueError, match="closer"):
        render_intervention_prompt(legacy, "P", [], closer="c")


def test_legacy_adapter_placebo_refuses_a_configured_closer():
    """Review LOW 10: an adapter without format_intervention_prompt cannot
    render a closer. With placebo_closer configured, a placebo retry raises
    instead of silently sending the fixed placebo sentence without it; with
    the option unset it sends that sentence as before."""
    legacy = SimpleNamespace(format_retry_prompt=lambda *a, **k: "x")
    host = _Host(mode="placebo", closer="Please reconsider your decision.")
    host.model_adapter = legacy
    with pytest.raises(ValueError, match="placebo_closer"):
        _first_retry_prompt(host)
    plain = _Host(mode="placebo")
    plain.model_adapter = legacy
    assert _first_retry_prompt(plain) == RETRY_FEEDBACK_PLACEBO_TEXT + "\n\nORIGINAL"


def test_missing_field_feasible_line_names_the_cause():
    text = _first_retry_prompt(_Host(validator=_missing_field), skill="keep_same")
    assert ("No action passes every rule this step, because your response did not "
            "include every required field; if this continues, the default action "
            "(keep same) will be applied.") in text
    # any other empty set keeps the shipped wording
    def block_all(proposal, context):
        return [ValidationResult(valid=False, validator_name="v", errors=["no"],
                                 metadata={"rule_id": "all"})]
    other = _first_retry_prompt(_Host(validator=block_all))
    assert ("No action passes every rule this step; if this continues, the default "
            "action (keep same) will be applied.") in other


def test_retry_text_getters_default_off_and_validated():
    blank = _cfg({"global_config": {}})
    assert blank.get_governance_plain_action_names() is False
    assert blank.get_governance_placebo_closer() is None
    raw = {"global_config": {"governance": {"plain_action_names": True, "placebo_closer": "Go."}}}
    assert _cfg(raw).get_governance_plain_action_names() is True
    assert _cfg(raw).get_governance_placebo_closer() == "Go."
    with pytest.raises(ValueError, match="plain_action_names"):
        _cfg({"global_config": {"governance": {"plain_action_names": "yes"}}}
             ).get_governance_plain_action_names()
    for bad in ("", "   ", 3):
        with pytest.raises(ValueError, match="placebo_closer"):
            _cfg({"global_config": {"governance": {"placebo_closer": bad}}}
                 ).get_governance_placebo_closer()


def test_flood_keeps_every_new_option_off_and_irrigation_turns_them_on():
    flood = AgentTypeConfig.load(str(FLOOD_CONFIG))
    assert flood.get_reflection_keep_latest_only() is False
    assert flood.get_governance_plain_action_names() is False
    assert flood.get_governance_placebo_closer() is None
    irr = AgentTypeConfig.load(str(IRRIGATION_CONFIG))
    assert irr.get_reflection_keep_latest_only() is True
    assert irr.get_governance_plain_action_names() is True
    assert irr.get_governance_placebo_closer() == "Please reconsider your decision."
