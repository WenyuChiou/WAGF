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


def test_reflection_and_placebo_closer_still_differentiate_flood_and_irrigation():
    """P3-10 (opus review round 3): renamed from
    test_flood_keeps_every_new_option_off_and_irrigation_turns_them_on,
    which had become inaccurate the moment the WRR26 rerun turned
    plain_action_names on for flood too (opus review P3-h, following
    irrigation's own WP4, spec 3.7, items 11 and 15 -- a retry report
    should name the blocked skill in plain words, not its internal id, in
    either domain) -- "flood keeps every new option off" was no longer
    true of the very option this test asserts first. Renamed for what it
    actually checks: reflection_keep_latest_only and placebo_closer remain
    the domains' own original differentiator (unrelated to the flood
    rerun); see test_appraisal_freeze.py::
    test_shipped_flood_config_resolved_option_set_2026_10 for flood's full
    resolved option set."""
    flood = AgentTypeConfig.load(str(FLOOD_CONFIG))
    assert flood.get_reflection_keep_latest_only() is False
    assert flood.get_governance_plain_action_names() is True
    assert flood.get_governance_placebo_closer() is None
    irr = AgentTypeConfig.load(str(IRRIGATION_CONFIG))
    assert irr.get_reflection_keep_latest_only() is True
    assert irr.get_governance_plain_action_names() is True
    assert irr.get_governance_placebo_closer() == "Please reconsider your decision."


# ---------------------------------------------------------------------------
# design-basis audit + fix proposals (2026-10-05): three generic, opt-in
# HumanCentricMemoryEngine options (deterministic_consolidation,
# decay_ignore_emotion, decay_by_calendar_year) -- all default False/off,
# so a caller that does not pass them (every existing domain) gets
# BYTE-IDENTICAL behaviour to before this change.
# ---------------------------------------------------------------------------

def test_deterministic_consolidation_off_is_byte_identical_to_shipped():
    """Off (default): the stochastic draw is unchanged from the SHIPPED
    (origin/main, commit 92e575ed) engine -- captured by exec'ing that
    commit's own humancentric.py source (git show origin/main:...) in a
    namespace with the real BaseAgent/MemoryEngine imports, then running
    this exact scenario against it (Opus review P3-1, 2026-10-06: a twin
    built from the NEW code only proves internal self-consistency, not
    that "off" actually reproduces what main shipped). importance=1.0
    with consolidation_prob=1.0 makes the OLD stochastic formula
    (rng.random() < 1.0) deterministic by construction, so this ground
    truth is not itself seed-fragile."""
    off = HumanCentricMemoryEngine(consolidation_prob=1.0, consolidation_threshold=0.6, seed=1)
    for i in range(20):
        off.add_memory("A", f"m{i}", {"importance": 1.0, "emotion": "major", "source": "personal"})
    assert [m["content"] for m in off.longterm["A"]] == [f"m{i}" for i in range(20)]


def test_deterministic_consolidation_on_consolidates_every_eligible_item():
    eng = HumanCentricMemoryEngine(
        consolidation_prob=0.01, consolidation_threshold=0.6, seed=1,
        deterministic_consolidation=True,
    )
    for i in range(10):
        eng.add_memory("A", f"m{i}", {"importance": 0.6, "emotion": "major", "source": "personal"})
    # consolidation_prob=0.01 would almost certainly consolidate ~0 of 10
    # under the stochastic draw; deterministic_consolidation=True ignores
    # it entirely and consolidates every one.
    assert len(eng.longterm["A"]) == 10
    below_threshold = HumanCentricMemoryEngine(
        consolidation_threshold=0.6, seed=1, deterministic_consolidation=True,
    )
    below_threshold.add_memory("A", "low", {"importance": 0.3, "emotion": "routine", "source": "abstract"})
    assert below_threshold.longterm["A"] == []  # still gated by the threshold


def test_decay_ignore_emotion_off_is_byte_identical_to_shipped():
    """Off (default): byte-identical to the SHIPPED (origin/main, commit
    92e575ed) engine on this exact scenario (Opus review P3-1, 2026-10-06;
    captured the same way as test_deterministic_consolidation_off_is_
    byte_identical_to_shipped above). importance=1.0 again makes
    consolidation deterministic by construction; the retrieved item's
    own timestamp (10, not 5) is the shipped engine's own arithmetic --
    _add_memory_internal's timestamp is working-length + longterm-length,
    and every item here consolidates into both stores, so it advances by
    2 per add, not 1."""
    off = HumanCentricMemoryEngine(consolidation_prob=1.0, consolidation_threshold=0.0, seed=1)
    off.add_memory("A", "crisis", {"importance": 1.0, "emotion": "critical", "source": "personal"})
    for i in range(5):
        off.add_memory("A", f"filler{i}", {"importance": 1.0, "emotion": "critical", "source": "personal"})
    result = off.retrieve(SimpleNamespace(id="A", memory=[]), window_size=0, top_k_significant=1)
    assert result == [{
        "content": "filler4", "emotion": "critical", "importance": 1.0,
        "source": "personal", "timestamp": 10, "final_score": 0.9512,
    }]


def test_decay_ignore_emotion_on_removes_the_emotion_modifier():
    """A "critical" item (emotion modifier 0.5) and a "routine" item
    (modifier 0.955) decay at visibly different rates when off; at the
    SAME bare decay_rate when decay_ignore_emotion is on."""
    def decayed_importance(ignore_emotion: bool, emotion: str, age: int) -> float:
        eng = HumanCentricMemoryEngine(decay_rate=0.1, decay_ignore_emotion=ignore_emotion)
        mem = {"importance": 0.9, "emotion": emotion, "timestamp": 0}
        return eng._apply_decay([mem], current_time=age)[0]["decayed_importance"]

    off_critical = decayed_importance(False, "critical", 10)
    off_routine = decayed_importance(False, "routine", 10)
    assert off_critical != pytest.approx(off_routine)

    on_critical = decayed_importance(True, "critical", 10)
    on_routine = decayed_importance(True, "routine", 10)
    assert on_critical == pytest.approx(on_routine)


def test_decay_by_calendar_year_off_is_byte_identical_to_shipped():
    """Off (default): "year" metadata is stored but IGNORED by decay --
    age is still the item-count difference, matching the SHIPPED
    (origin/main, commit 92e575ed) engine's own computed value on this
    exact scenario (Opus review P3-1, 2026-10-06), not a formula
    re-derived from the new code's own decay_rate/emotional_weights."""
    eng = HumanCentricMemoryEngine(consolidation_prob=1.0, consolidation_threshold=0.0, seed=1)
    eng.add_memory("A", "old", {"importance": 1.0, "emotion": "major", "source": "personal", "year": 2019})
    for i in range(3):
        eng.add_memory("A", f"filler{i}", {"importance": 0.1, "emotion": "routine", "source": "abstract", "year": 2020 + i})
    decayed = eng._apply_decay(eng.longterm["A"], current_time=4)
    old = next(m for m in decayed if m["content"] == "old")
    assert old["timestamp"] == 0
    # item-count age = 4 - 0 = 4, NOT a year-based age (2019 is stored,
    # unused, by this off path).
    assert old["decayed_importance"] == pytest.approx(0.8025187979624785)


def test_decay_by_calendar_year_on_uses_year_metadata_not_item_count():
    """On: two items added back-to-back (item-count age 1 apart) but
    tagged 10 calendar years apart decay as if 10 years had passed, not 1
    stored item."""
    eng = HumanCentricMemoryEngine(
        consolidation_prob=1.0, consolidation_threshold=0.0, seed=1,
        decay_by_calendar_year=True,
    )
    eng.add_memory("A", "old", {"importance": 0.9, "emotion": "major", "source": "personal", "year": 2010})
    eng.add_memory("A", "new", {"importance": 0.9, "emotion": "major", "source": "personal", "year": 2020})
    decayed = eng._apply_decay(eng.longterm["A"], current_time=2, current_year=2020)
    old = next(m for m in decayed if m["content"] == "old")
    import math
    expected = 0.9 * math.exp(-eng.decay_rate * (1.0 - 0.5 * eng.emotional_weights["major"]) * 10)
    assert old["decayed_importance"] == pytest.approx(expected)


def test_decay_by_calendar_year_on_requires_year_metadata():
    eng = HumanCentricMemoryEngine(
        consolidation_prob=1.0, consolidation_threshold=0.0, seed=1,
        decay_by_calendar_year=True,
    )
    eng.add_memory("A", "no year", {"importance": 0.9, "emotion": "major", "source": "personal"})
    with pytest.raises(ValueError, match="year"):
        eng._apply_decay(eng.longterm["A"], current_time=1, current_year=2020)
    # retrieve() itself refuses the same way, through _current_year_for_decay.
    with pytest.raises(ValueError, match="year"):
        eng.retrieve(SimpleNamespace(id="A", memory=[]))


@pytest.mark.parametrize("name", [
    "deterministic_consolidation", "decay_ignore_emotion", "decay_by_calendar_year",
])
@pytest.mark.parametrize("bad", ["true", "false", "True", "", 1, 0, None])
def test_memory_option_rejects_non_bool(name, bad):
    """Opus review P3-2 (2026-10-06): bool only, raised here rather than
    left to fail downstream on a string read straight from YAML -- "1"/
    "0" (Python ints, truthy/falsy but not bool) are refused too, same
    as WaterSystemConfig.hold_requests_fixed's own check."""
    with pytest.raises(ValueError, match=name):
        HumanCentricMemoryEngine(**{name: bad})


def test_memory_options_flood_off_irrigation_on():
    flood = AgentTypeConfig.load(str(FLOOD_CONFIG))
    flood_memory = flood._config.get("global_config", {}).get("memory", {})
    for key in ("deterministic_consolidation", "decay_ignore_emotion", "decay_by_calendar_year"):
        assert flood_memory.get(key, False) is False

    irr = AgentTypeConfig.load(str(IRRIGATION_CONFIG))
    irr_memory = irr._config.get("global_config", {}).get("memory", {})
    for key in ("deterministic_consolidation", "decay_ignore_emotion", "decay_by_calendar_year"):
        assert irr_memory.get(key) is True
