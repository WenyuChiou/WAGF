"""Grounded reflection: the generic framework options of irrigation v3 spec
item 45 (a)-(e), shared with flood (design record PI decision 2026-10-07
item 7).

Every option is off by default, and a domain that sets none of them renders,
stores and logs exactly what it did before:

- ``AgentTypeConfig.get_reflection_grounding`` (``year_outcome``,
  ``year_lines``, ``program_facts``, ``lesson_no_numbers``): all False unless
  the YAML says true, YAML bools only, and no tracked config but irrigation
  and the single-agent flood config sets any of them;
- ``ReflectionEngine.generate_batch_reflection_prompt``'s new keywords
  (``year_lines``, ``fact_lines``, ``rule_lines``): at their defaults the
  prompt is the pre-item-45 prompt byte for byte (pinned against a copy of
  that code);
- ``add_year_outcome``, ``order_by_year``, ``compose_lesson_with_facts``,
  ``lesson_number_problems``, ``normalize_lesson_text``;
- ``run_checked_reflection`` (one retry with the reasons, then not stored;
  raw replies and semantic flags of every attempt go to a JSONL log),
  ``ReflectionCheckTally`` and ``record_reflection_checks`` (counts in the
  manifest);
- the feedback dashboard's optional column ``label`` (item 45i).
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
import yaml

from broker.components.analytics.feedback import AgentMetricsTracker, FeedbackDashboardProvider
from broker.components.cognitive.reflection import (
    GROUNDING_KEYS,
    LESSON_ONLY_INSTRUCTION,
    RECORD_HEADING,
    REFLECTION_RETRY_NOTE,
    CheckedReflection,
    LessonProblem,
    ReflectionCheckTally,
    ReflectionEngine,
    add_year_outcome,
    compose_lesson_with_facts,
    lesson_number_problems,
    normalize_lesson_text,
    order_by_year,
    record_reflection_checks,
    run_checked_reflection,
)
from broker.utils.agent_config import AgentTypeConfig

REPO = Path(__file__).resolve().parents[2]


def _cfg(raw: Dict[str, Any]) -> AgentTypeConfig:
    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = raw
    return cfg


# ---------------------------------------------------------------------------
# config keys
# ---------------------------------------------------------------------------

def test_grounding_getter_default_off_and_bool_only():
    assert _cfg({"global_config": {}}).get_reflection_grounding() == {k: False for k in GROUNDING_KEYS}
    on = _cfg({"global_config": {"reflection": {k: True for k in GROUNDING_KEYS}}})
    assert on.get_reflection_grounding() == {k: True for k in GROUNDING_KEYS}
    for key in GROUNDING_KEYS:
        with pytest.raises(ValueError, match=key):
            _cfg({"global_config": {"reflection": {key: "true"}}}).get_reflection_grounding()
    # get_reflection_config's dict is unchanged when the keys are absent
    plain = _cfg({"global_config": {}}).get_reflection_config()
    assert not set(GROUNDING_KEYS) & set(plain)


def test_only_irrigation_and_flood_opt_in():
    """Every other tracked domain config leaves the grounded mechanism off,
    so none of their reflection prompts or memories change."""
    opted = set()
    for path in sorted(REPO.glob("examples/**/*agent_types*.yaml")):
        if "results" in path.parts:
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if any(_cfg(raw).get_reflection_grounding().values()):
            opted.add(path.relative_to(REPO).as_posix())
    assert opted == {
        "examples/irrigation_abm/config/agent_types.yaml",
        "examples/single_agent/agent_types.yaml",
        "examples/single_agent/config_variants/nonudge/agent_types.yaml",
    }


# ---------------------------------------------------------------------------
# the prompt builder: defaults byte-identical, then each option
# ---------------------------------------------------------------------------

def _pre45_prompt(batch_data, current_year, reflection_questions=None, persona_instruction=None,
                  tick_label="Year"):
    """ReflectionEngine.generate_batch_reflection_prompt at c7b10c05 (before
    item 45), copied verbatim, as the byte-identity reference."""
    if not batch_data:
        return ""
    agents_noun = "agent" if len(batch_data) == 1 else "agents"
    lines = [f"### Background\nYou are a Reflection Assistant for {len(batch_data)} {agents_noun} in a simulation ({tick_label} {current_year})."]
    if persona_instruction:
        lines.append(f"Instructions: {persona_instruction}")
    else:
        lines.append("Instructions: Summarize each agent's memories into a 2-sentence 'Lesson Learned'.")
    if reflection_questions:
        lines.append("Focus your reflections on:")
        for q in reflection_questions:
            lines.append(f"  - {q}")
    lines.append("")
    lines.append("### Task Data to Process")
    for item in batch_data:
        agent_id = item.get("agent_id", "Unknown")
        memories = item.get("memories", [])
        mem_text = " ".join((str(m.get("content", "")) if isinstance(m, dict) else str(m))
                            for m in memories) if memories else "(No memories recorded)"
        lines.append(f"{agent_id} Memories: {mem_text}")
    lines.append("\n### Output Requirement")
    lines.append("Return ONLY the JSON object mapping Agent IDs to strings. No conversational filler.")
    return "\n".join(lines)


@pytest.mark.parametrize("batch,year,questions,persona,tick", [
    ([{"agent_id": "A", "memories": ["m1", "m2"]}], 2021, None, None, "Year"),
    ([{"agent_id": "A", "memories": [{"content": "x", "year": 3}, "y"]},
      {"agent_id": "B", "memories": []}], 3, ["q1", "q2"], "Speak plainly.", "Day"),
    ([{"agent_id": "A", "memories": []}], 1, [], "", "Year"),
])
def test_default_prompt_is_byte_identical_to_before_item_45(batch, year, questions, persona, tick):
    eng = ReflectionEngine()
    assert eng.generate_batch_reflection_prompt(batch, year, questions, persona, tick) == _pre45_prompt(
        batch, year, questions, persona, tick)


def test_year_lines_one_per_line_oldest_first():
    eng = ReflectionEngine()
    mems = [{"content": "Year 2033: worst.", "year": 2033}, {"content": "Year 2031: a.", "year": 2031},
            {"content": "Year 2034: b.", "year": 2034}, {"content": "Year 2031: tie kept second.", "year": 2031}]
    prompt = eng.generate_batch_reflection_prompt([{"agent_id": "A", "memories": mems}], 2034, year_lines=True)
    assert ("A Memories:\n- Year 2031: a.\n- Year 2031: tie kept second.\n- Year 2033: worst.\n"
            "- Year 2034: b.\n") in prompt
    with pytest.raises(ValueError, match="numeric 'year'"):
        eng.generate_batch_reflection_prompt([{"agent_id": "A", "memories": ["no year"]}], 1, year_lines=True)
    with pytest.raises(ValueError, match="numeric 'year'"):
        order_by_year([{"content": "x", "year": True}])
    # no memories: the shipped placeholder
    empty = eng.generate_batch_reflection_prompt([{"agent_id": "A", "memories": []}], 1, year_lines=True)
    assert "A Memories: (No memories recorded)" in empty


def test_fact_and_rule_lines():
    eng = ReflectionEngine()
    one = eng.generate_batch_reflection_prompt(
        [{"agent_id": "A", "memories": ["m"]}], 5,
        fact_lines=["Year 5: fact one.", "Year 3: fact two."], rule_lines=["Rule one."])
    assert "A Memories: m\nRules that apply to A:\n- Rule one.\n" in one
    assert ("\n\n" + RECORD_HEADING + "\nA Record:\n- Year 5: fact one.\n- Year 3: fact two.\n") in one
    assert one.endswith("No conversational filler.\n" + LESSON_ONLY_INSTRUCTION)
    # a mapping serves a batch; a list is refused for more than one agent
    two = eng.generate_batch_reflection_prompt(
        [{"agent_id": "A", "memories": ["m"]}, {"agent_id": "B", "memories": ["n"]}], 5,
        fact_lines={"B": ["fact b."]})
    assert "A Record:" not in two and "B Record:\n- fact b." in two
    with pytest.raises(ValueError, match="one-agent batch"):
        eng.generate_batch_reflection_prompt(
            [{"agent_id": "A", "memories": ["m"]}, {"agent_id": "B", "memories": ["n"]}], 5, fact_lines=["x"])
    # empty facts or rules: nothing added
    assert eng.generate_batch_reflection_prompt([{"agent_id": "A", "memories": ["m"]}], 5, fact_lines=[],
                                                rule_lines=[]) == _pre45_prompt(
        [{"agent_id": "A", "memories": ["m"]}], 5)


def test_add_year_outcome_contract():
    items = [{"content": "Year 1: a.", "year": 1}]
    assert add_year_outcome(items, None, required=False) == items
    with pytest.raises(ValueError, match="year_outcome"):
        add_year_outcome(items, None, required=True)
    new = {"content": "Year 2: b.", "year": 2}
    assert add_year_outcome(items, new, required=True) == items + [new]
    # the same line already in memory is not added twice
    assert add_year_outcome(items + [{"content": " Year 2: b. "}], new, required=True) == items + [{"content": " Year 2: b. "}]


def test_compose_and_normalize():
    assert compose_lesson_with_facts(None, "I learned.") == "I learned."
    assert compose_lesson_with_facts([" 2020: a. ", "", "2021: b."], "I learned.") == "2020: a. 2021: b. Lesson: I learned."
    assert normalize_lesson_text('  "I  learned\nthis.",  ') == "I learned this."
    assert normalize_lesson_text("\u201cQuoted.\u201d") == "Quoted."


@pytest.mark.parametrize("lesson,codes", [
    ("I learned to keep my request steady.", []),
    ("In 2031 I learned to keep my request steady.", ["year"]),
    ("A 17 percent cut taught me caution.", ["number"]),
    ("In 2031 a 17.5 percent cut of 1,000 acre-ft taught me.", ["year", "number"]),
    ("Year 3 taught me to buy insurance.", ["number"]),
    ("Two dry years taught me caution.", []),
    ("A request near 20155 was too high.", ["number"]),
])
def test_lesson_number_problems(lesson, codes):
    assert [p.code for p in lesson_number_problems(lesson)] == codes


# ---------------------------------------------------------------------------
# the checked call
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", [
    '{"AgentID": "TunnelDiversionBelowCrystalForAg_1971CompStudyAg": "I learned to watch demand."}',
    '{"AgentID": "Agent": "I learned to watch demand."}',
    '{"agent_id": "Bostwick", "lesson": "I learned to watch demand."}',
])
def test_single_agent_lenient_forms_recover_and_record(raw, tmp_path):
    log = tmp_path / "reflection_checks.jsonl"
    result = run_checked_reflection(
        ReflectionEngine(), prompt="PROMPT", agent_id="X", period=2031,
        llm_call=lambda _: raw, log_path=log, lesson_no_numbers=True)
    assert result.outcome == "stored" and result.lesson == "I learned to watch demand."
    assert json.loads(log.read_text())["parse"] == "lenient"
    tally = ReflectionCheckTally()
    tally.add(2031, result)
    assert tally.summary()["per_period"]["2031"]["recovered_lenient"] == 1
    assert tally.summary()["totals"]["recovered_lenient"] == 1
    assert "recovered lenient 1" in tally.log_line(2031)
    ids = (["AgentID", "TunnelDiversionBelowCrystalForAg_1971CompStudyAg"]
           if "TunnelDiversion" in raw else
           ["AgentID", "Agent"] if '"Agent"' in raw else
           ["Bostwick", "agent_id"])
    multi = ReflectionEngine().parse_batch_reflection_response(raw, ids, 2031)
    assert multi[ids[0]] is None or multi[ids[0]].summary != "I learned to watch demand."
    assert all(insight is None or insight.parse == "strict" for insight in multi.values())


@pytest.mark.parametrize("agent_id", ["X", "Bostwick", "Bostwick Park Water Conservancy"])
@pytest.mark.parametrize("allow_plain_text", [False, True])
def test_lenient_chained_form_rejects_lesson_as_middle(agent_id, allow_plain_text):
    raw = '{"lesson": "I learned to watch demand.": "Bostwick Park Water Conservancy"}'
    assert ReflectionEngine().parse_batch_reflection_response(
        raw, [agent_id], 2031, allow_plain_text=allow_plain_text) == {agent_id: None}


@pytest.mark.parametrize("raw", [
    '{"AgentID": "odd!": "I learned to watch demand carefully."}',
    '{"lesson": "I learned to keep demand steady": "Fort Mohave Ind Res AZ"}',
    '{"lesson": "I learned a lot.": "Fort Mohave Ind Res AZ"}',
])
def test_lenient_chained_form_requires_id_like_and_shorter_middle(raw):
    assert ReflectionEngine().parse_batch_reflection_response(raw, ["X"], 2031) == {"X": None}


def test_lenient_chained_form_rejects_long_non_id_middle():
    raw = '{"AgentID": "one two three four five six seven": "Short lesson"}'
    assert ReflectionEngine().parse_batch_reflection_response(
        raw, ["TargetAgent"], 2031) == {"TargetAgent": None}


@pytest.mark.parametrize("raw", [
    '{"lesson": ""}',
    '{"agent_id": "X", "lesson": "  "}',
])
def test_lenient_blank_lesson_stays_no_reply(raw):
    assert ReflectionEngine().parse_batch_reflection_response(raw, ["X"], 2031) == {"X": None}


def test_lenient_lesson_uses_stage1_repaired_object():
    raw = '{"agent_id": "X1", "lesson": "I learned to watch demand.",}'
    insight = ReflectionEngine().parse_batch_reflection_response(raw, ["X"], 2031)["X"]
    assert insight is not None
    assert insight.summary == "I learned to watch demand."
    assert insight.parse == "lenient"


@pytest.mark.parametrize("lesson,code", [
    ("In 2030 I learned to watch.", "year"),
    ("I learned to watch " + "demand " * 80, "too_long"),
    ("... ... ...", "empty"),  # three words, no letters: longer than the middle, still junk
])
def test_lenient_lesson_retains_blocking_checks(lesson, code, tmp_path):
    raw = '{"AgentID": "Agent": ' + json.dumps(lesson) + '}'
    replies = iter([raw, '{"X": "I learned to watch demand."}'])
    log = tmp_path / "reflection_checks.jsonl"
    result = run_checked_reflection(
        ReflectionEngine(), prompt="PROMPT", agent_id="X", period=2031,
        llm_call=lambda _: next(replies), log_path=log, lesson_no_numbers=True)
    assert result.outcome == "stored_after_retry"
    assert code in [p.code for p in result.first_problems]
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert rows[0]["parse"] == "lenient" and rows[1].get("parse", "strict") == "strict"
    tally = ReflectionCheckTally()
    tally.add(2031, result)
    assert tally.counts(2031)["recovered_lenient"] == 0  # stored lesson was strict


def test_lenient_parser_preserves_escapes_strict_precedence_and_no_reply():
    engine = ReflectionEngine()
    lesson = 'I learned to watch "demand" and my own needs.'
    raw = '{"AgentID": "Agent": ' + json.dumps(lesson) + '}'
    assert engine.parse_batch_reflection_response(raw, ["X"], 1)["X"].summary == lesson
    raw = json.dumps({"X": lesson, "lesson": "Other lesson stays unused."})
    insight = engine.parse_batch_reflection_response(raw, ["X"], 1)["X"]
    assert insight.summary == lesson and insight.parse == "strict"
    for raw in ('{"garbage": null}', '{"AgentID": "Agent": null}', '{"lesson": null}'):
        result = run_checked_reflection(
            engine, prompt="PROMPT", agent_id="X", period=1,
            llm_call=lambda _: raw, retries=0)
        assert result.outcome == "dropped"
        assert [p.code for p in result.first_problems] == ["no_reply"]


def test_lenient_invalid_escape_stays_no_reply():
    raw = r'{"AgentID":"Agent":"I learned to avoid \q replies."}'
    assert ReflectionEngine().parse_batch_reflection_response(
        raw, ["X"], 1, allow_plain_text=True) == {"X": None}


class _Model:
    """Answers in turn from ``replies``: a string is the lesson (wrapped as
    the one-key JSON the parser reads), None an unreadable reply, an
    exception a failed call. Every prompt is kept."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts: List[str] = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        if item is None:
            return "", object()
        return json.dumps({"A": item}), object()


def _contradiction(lesson):
    return [LessonProblem("rule", "it states a rule a listed year contradicts")] if "always" in lesson else []


@pytest.mark.parametrize("replies,outcome,calls,stored", [
    (["I learned to watch."], "stored", 1, "I learned to watch."),
    (["In 2031 I learned.", "I learned to watch."], "stored_after_retry", 2, "I learned to watch."),
    (["It always fails."], "stored", 1, "It always fails."),
    (["In 2031 I learned.", None], "dropped", 2, ""),
    (["   ", "   "], "dropped", 2, ""),
    ([None, None], "dropped", 2, ""),
    ([RuntimeError("model down"), RuntimeError("model down")], "dropped", 2, ""),
])
def test_run_checked_reflection_outcomes(tmp_path, replies, outcome, calls, stored):
    model = _Model(replies)
    log = tmp_path / "checks.jsonl"
    result = run_checked_reflection(ReflectionEngine(), prompt="PROMPT", agent_id="A", period=2031,
                                    llm_call=model, checker=_contradiction, lesson_no_numbers=True,
                                    log_path=log, year_created=13)
    assert (result.outcome, result.calls, result.lesson) == (outcome, calls, stored)
    assert (result.insight is not None) == bool(stored)
    if result.insight is not None:
        assert result.insight.year_created == 13
    if calls == 2:
        # the one retry: the original prompt, then the reasons
        assert model.prompts[1].startswith("PROMPT\n\n### Correction\nYour previous answer could not be stored because ")
        assert result.first_problems and all(p.message in model.prompts[1] for p in result.first_problems)
    # the raw reply of every reflection not stored at once is logged, one line per attempt
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [r["attempt"] for r in rows] == list(range(calls))
    assert all(r["outcome"] == outcome and r["agent_id"] == "A" and r["period"] == 2031 for r in rows)
    assert "raw_reply" in rows[0]


def test_retry_note_names_every_reason_and_retries_can_be_zero():
    model = _Model(["In 2031 it always fails."])
    result = run_checked_reflection(ReflectionEngine(), prompt="P", agent_id="A", period=1, llm_call=model,
                                    checker=_contradiction, lesson_no_numbers=True, retries=0)
    assert result.outcome == "dropped" and result.calls == 1
    assert [p.code for p in result.final_problems] == ["year"]
    note = REFLECTION_RETRY_NOTE.format(reasons="a; b")
    assert note.startswith("### Correction") and "a; b" in note
    with pytest.raises(ValueError):
        run_checked_reflection(ReflectionEngine(), prompt="P", agent_id="A", period=1, llm_call=model, retries=-1)


def test_numbers_pass_when_the_option_is_off():
    """lesson_no_numbers off and no checker: any parsed lesson is stored."""
    result = run_checked_reflection(ReflectionEngine(), prompt="P", agent_id="A", period=1,
                                    llm_call=_Model(["In 2031 I got 17 percent."]))
    assert result.outcome == "stored"


def test_json_value_instruction_keeps_json_wrapper():
    assert LESSON_ONLY_INSTRUCTION.startswith("In the JSON value, write only the lesson")


def test_single_agent_plain_text_is_checked_and_multi_agent_is_not_guessed():
    eng = ReflectionEngine()
    lesson = "I learned to watch the outcomes."
    assert eng.parse_batch_reflection_response(lesson, ["A"], 1) == {"A": None}
    assert eng.parse_batch_reflection_response(lesson, ["A"], 1, allow_plain_text=True)["A"].summary == lesson
    assert eng.parse_batch_reflection_response(lesson, ["A", "B"], 1, allow_plain_text=True) == {"A": None, "B": None}
    seen = []
    result = run_checked_reflection(eng, prompt="P", agent_id="A", period=1,
                                    llm_call=lambda _: lesson,
                                    checker=lambda text: seen.append(text) or [])
    assert result.outcome == "stored" and seen == [lesson]


@pytest.mark.parametrize("first", ["", RuntimeError("model down"), '{"decision": 1}'])
def test_no_reply_gets_one_checked_retry(tmp_path, first):
    replies = iter([first, "I learned to watch the outcomes."])
    prompts = []
    def call(prompt):
        prompts.append(prompt)
        raw = next(replies)
        if isinstance(raw, Exception):
            raise raw
        return raw
    log = tmp_path / "checks.jsonl"
    result = run_checked_reflection(ReflectionEngine(), prompt="P", agent_id="A", period=1,
                                    llm_call=call, lesson_no_numbers=True, log_path=log)
    assert result.outcome == "stored_after_retry" and result.calls == 2
    assert [p.code for p in result.first_problems] == ["no_reply"]
    assert "no readable answer" in prompts[1]
    assert len(log.read_text().splitlines()) == 2


def test_checker_exception_is_dropped_and_logged(tmp_path):
    def broken_checker(_):
        raise ValueError("invalid checker state")
    log = tmp_path / "checks.jsonl"
    result = run_checked_reflection(ReflectionEngine(), prompt="P", agent_id="A", period=1,
                                    llm_call=_Model(["I learned to watch."]),
                                    checker=broken_checker, log_path=log)
    assert result.outcome == "dropped" and result.calls == 1
    assert result.insight is None and result.lesson == ""
    assert [p.code for p in result.final_problems] == ["checker_error"]
    row = json.loads(log.read_text())
    assert row["problems"][0]["code"] == "checker_error"
    assert row["error"] == "ValueError: invalid checker state"
    tally = ReflectionCheckTally()
    tally.add(1, result)
    assert tally.counts(1)["dropped"] == 1
    assert tally.counts(1)["retried"] == 0
    assert tally.summary()["dropped_by_reason"] == {"checker_error": 1}


def test_leading_lesson_label_is_stripped_before_composing():
    result = run_checked_reflection(ReflectionEngine(), prompt="P", agent_id="A", period=1,
                                    llm_call=_Model(["Lesson: I learned to watch."]),
                                    normalize=lambda text: text.strip())
    assert result.lesson == "I learned to watch."
    assert compose_lesson_with_facts(["Year 1: an outcome."], result.lesson) == (
        "Year 1: an outcome. Lesson: I learned to watch.")


@pytest.mark.parametrize("preamble", [
    "My lesson: ", "The lesson: ", "Key lesson: ", "Lesson learned: ",
])
def test_short_leading_lesson_openers_are_stripped_before_composing(preamble):
    result = run_checked_reflection(
        ReflectionEngine(), prompt="P", agent_id="A", period=1,
        llm_call=_Model([preamble + '"I learned caution."']),
        lesson_no_numbers=True,
    )
    assert result.outcome == "stored" and result.calls == 1
    assert result.lesson == "I learned caution."
    assert compose_lesson_with_facts(["Period 1: an outcome."], result.lesson) == (
        "Period 1: an outcome. Lesson: I learned caution.")


def test_broker_grounding_comments_use_generic_examples():
    assert "shortage" not in ReflectionEngine.generate_batch_reflection_prompt.__doc__
    source = (REPO / "broker/components/analytics/feedback.py").read_text(encoding="utf-8")
    assert 'reads "received (AF)"' not in source


def test_semantic_flags_are_stored_logged_and_counted_without_retry(tmp_path):
    log = tmp_path / "checks.jsonl"
    result = run_checked_reflection(
        ReflectionEngine(), prompt="P", agent_id="A", period=1,
        llm_call=_Model(["It always fails."]), checker=_contradiction, log_path=log)
    assert (result.outcome, result.calls, result.lesson) == ("stored", 1, "It always fails.")
    assert [p.code for p in result.flags] == ["rule"]
    row = json.loads(log.read_text())
    assert row["problems"] == [] and row["flags"][0]["code"] == "rule"
    tally = ReflectionCheckTally()
    tally.add(1, result)
    assert tally.summary()["flagged_by_reason"] == {"rule": 1}
    assert tally.summary()["per_period"]["1"]["flagged_by_reason"] == {"rule": 1}
    assert tally.summary()["dropped_by_reason"] == {}
    assert tally.counts(1)["retried"] == 0


@pytest.mark.parametrize("bad", ["{", "increase", "123 !!!", "I learned", " "])
def test_junk_lesson_retries_once_then_drops(bad):
    result = run_checked_reflection(ReflectionEngine(), prompt="P", agent_id="A", period=1,
                                    llm_call=_Model([bad, bad]))
    assert result.outcome == "dropped" and result.calls == 2
    assert [p.code for p in result.final_problems] == ["empty"]
    assert result.lesson == "" and result.insight is None


def test_overlong_lesson_retries_without_truncation(tmp_path):
    long = "I learned " + "caution " * 70 + "carefully."
    log = tmp_path / "checks.jsonl"
    result = run_checked_reflection(ReflectionEngine(), prompt="P", agent_id="A", period=1,
                                    llm_call=_Model([long, "I learned caution."]), log_path=log)
    assert result.outcome == "stored_after_retry" and result.calls == 2
    assert [p.code for p in result.first_problems] == ["too_long"]
    assert json.loads(log.read_text().splitlines()[0])["lesson"] == long
    assert result.lesson == "I learned caution."


@pytest.mark.parametrize("preamble", ["Lesson: ", "Here is your lesson: ", "Sure! ",
                                     "Sure! Here is the lesson: Lesson: ",
                                     "My reflection for 2031: Lesson: "])
def test_preambles_are_removed_before_mechanical_checks(preamble):
    result = run_checked_reflection(ReflectionEngine(), prompt="P", agent_id="A", period=1,
                                    llm_call=_Model([preamble + "I learned caution."]),
                                    lesson_no_numbers=True)
    assert result.outcome == "stored" and result.lesson == "I learned caution."


def test_normalize_exception_is_dropped_as_checker_error(tmp_path):
    def broken(_):
        raise ValueError("normalization failed")
    log = tmp_path / "checks.jsonl"
    result = run_checked_reflection(ReflectionEngine(), prompt="P", agent_id="A", period=1,
                                    llm_call=_Model(["I learned caution."]), normalize=broken,
                                    log_path=log)
    assert result.outcome == "dropped" and result.calls == 1
    assert [p.code for p in result.final_problems] == ["checker_error"]
    assert json.loads(log.read_text())["error"] == "ValueError: normalization failed"


def test_foreign_figure_still_blocks_when_semantic_flags_are_report_only():
    result = run_checked_reflection(
        ReflectionEngine(), prompt="P", agent_id="A", period=1,
        llm_call=_Model(["I recalled a foreign amount.", "I learned caution."]),
        checker=lambda text: [LessonProblem("foreign_figure", "foreign amount")]
        if "foreign" in text else [])
    assert result.outcome == "stored_after_retry" and result.calls == 2
    assert [p.code for p in result.first_problems] == ["foreign_figure"]


@pytest.mark.parametrize("enabled", [True, False, None])
def test_window_reflection_integrity_uses_resolved_flag(tmp_path, enabled):
    from broker.core.run_integrity import record_run_integrity
    audit = record_run_integrity(tmp_path, memory_engine_type="window",
                                 reflection_enabled=enabled, verbose=False)
    assert audit["reflection_expected"] is bool(enabled)
    assert audit["integrity_ok"] is not bool(enabled)
    (tmp_path / "reflection_log.jsonl").write_text('{"summary":"lesson"}\n', encoding="utf-8")
    assert record_run_integrity(tmp_path, memory_engine_type="window",
                                reflection_enabled=enabled, verbose=False)["integrity_ok"] is True


def test_tally_and_manifest(tmp_path, capsys):
    tally = ReflectionCheckTally()
    p = [LessonProblem("year", "y")]
    for outcome, problems in (("stored", []), ("stored_after_retry", p), ("dropped", p + p)):
        tally.add(2031, CheckedReflection(outcome=outcome, first_problems=problems))
    tally.add(2032, CheckedReflection(outcome="stored"))
    c = tally.counts(2031)
    assert (c["stored_total"], c["retried"], c["dropped"]) == (2, 2, 1)
    assert "empty" not in c and "no_reply" not in c
    assert tally.log_line(2031) == ("stored 2 (1 after one retry), retried 2, dropped 1, recovered lenient 0, "
                                    "flagged by reason {}")
    summary = tally.summary()
    assert summary["per_period"]["2031"]["first_attempt_problems"] == {"year": 2}
    assert summary["totals"]["stored_total"] == 3
    with pytest.raises(ValueError):
        tally.add(1, CheckedReflection(outcome="lost"))

    manifest = tmp_path / "reproducibility_manifest.json"
    manifest.write_text(json.dumps({"seed": 42}), encoding="utf-8")
    record_reflection_checks(tmp_path, tally, {"lesson_no_numbers": True})
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["seed"] == 42  # additive
    assert data["reflection_checks"]["settings"] == {"lesson_no_numbers": True}
    assert data["reflection_checks"]["per_period"]["2032"]["stored"] == 1
    record_reflection_checks(tmp_path / "missing", tally, {})  # never raises
    assert "no reproducibility_manifest.json" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# feedback dashboard column label (item 45i)
# ---------------------------------------------------------------------------

def _table(metrics):
    tracker = AgentMetricsTracker([m["name"] for m in metrics], window=5)
    tracker.record("A", 2019, {"request": 100.0, "supply": 80.0})
    ctx: Dict[str, Any] = {}
    FeedbackDashboardProvider(tracker, {"show_trend": False, "tracked_metrics": metrics,
                                        "assertions": [{"when": "supply / request < 0.999",
                                                        "message": "got {supply_fmt}"}]}
                              ).provide("A", {}, ctx, env_context={})
    return ctx["feedback_dashboard"]


def test_feedback_label_renames_only_the_column():
    base = [{"name": "request", "source": "r", "unit": "AF", "format": ",.0f"},
            {"name": "supply", "source": "s", "unit": "AF", "format": ",.0f"}]
    assert "Year | request (AF) | supply (AF)" in _table(base)  # default: the name, as shipped
    labelled = [base[0], {**base[1], "label": "received"}]
    text = _table(labelled)
    assert "Year | request (AF) | received (AF)" in text
    assert "WARNING: got 80" in text  # assertions still read the metric's name
    with pytest.raises(ValueError, match="label"):
        FeedbackDashboardProvider(AgentMetricsTracker([], 5), {"tracked_metrics": [
            {"name": "x", "source": "x", "label": ""}]})


@pytest.mark.parametrize("separator", [" ", "\n"])
def test_checked_keyed_plain_reply_preserves_late_number_after_contraction(separator):
    bad = "Agent_000: I learned to be cautious because I can't" + separator + "ignore 2031."
    replies = iter([bad, "I learned to be cautious."])
    result = run_checked_reflection(ReflectionEngine(), prompt="P", agent_id="Agent_000", period=1,
                                    llm_call=lambda _: next(replies), lesson_no_numbers=True)
    assert result.outcome == "stored_after_retry" and result.calls == 2
    assert [p.code for p in result.first_problems] == ["year"]
    assert result.lesson == "I learned to be cautious."


def test_checked_keyed_plain_reply_preserves_full_length_after_contraction(tmp_path):
    bad = "Agent_000: I learned to be cautious because I can't " + "ignore risk " * 60
    replies = iter([bad, "I learned to be cautious."])
    log = tmp_path / "checks.jsonl"
    result = run_checked_reflection(ReflectionEngine(), prompt="P", agent_id="Agent_000", period=1,
                                    llm_call=lambda _: next(replies), log_path=log)
    assert result.outcome == "stored_after_retry" and result.calls == 2
    assert [p.code for p in result.first_problems] == ["too_long"]
    assert len(json.loads(log.read_text().splitlines()[0])["lesson"]) > 500


def test_surely_is_not_stripped_as_a_sure_preamble():
    lesson = "Surely I should watch the outcomes."
    result = run_checked_reflection(ReflectionEngine(), prompt="P", agent_id="A", period=1,
                                    llm_call=_Model([lesson]))
    assert result.lesson == lesson


@pytest.mark.parametrize("lesson", [
    "I learned an important lesson: keep my choices cautious.",
    "One lesson: cut early.",
    "My experience taught a lesson: keep watching the outcomes.",
    "Here is what my experience has taught me: stay cautious.",
    "My reflection on everything I experienced through the last season: Lesson: stay cautious.",
    "My lesson from the whole season: stay cautious.",
    "Lesson learned from a difficult experience: stay cautious.",
])
def test_lesson_colon_in_substantive_text_is_preserved(lesson):
    result = run_checked_reflection(
        ReflectionEngine(), prompt="P", agent_id="A", period=1,
        llm_call=_Model([lesson]))
    assert result.outcome == "stored" and result.calls == 1
    assert result.lesson == lesson


@pytest.mark.parametrize("preamble", ["Lesson: ", "lesson: ", "Here is your lesson: ", "Sure! Lesson: "])
def test_quotes_exposed_by_preamble_are_normalized_before_checking(preamble):
    seen = []
    result = run_checked_reflection(
        ReflectionEngine(), prompt="P", agent_id="A", period=1,
        llm_call=_Model([preamble + '\"I learned caution.\"']),
        checker=lambda lesson: seen.append(lesson) or [])
    assert result.lesson == "I learned caution."
    assert seen == ["I learned caution."]


def test_manifest_outcomes_omit_junk_and_no_reply_reason_keys(tmp_path):
    tally = ReflectionCheckTally()
    for raw in ("{", ""):
        result = run_checked_reflection(
            ReflectionEngine(), prompt="P", agent_id="A", period=1,
            llm_call=lambda _: raw)
        tally.add(1, result)
    manifest = tmp_path / "reproducibility_manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    record_reflection_checks(tmp_path, tally, {})
    summary = json.loads(manifest.read_text())["reflection_checks"]
    assert summary["dropped_by_reason"] == {"empty": 1, "no_reply": 1}
    assert summary["totals"]["dropped"] == 2
    assert summary["per_period"]["1"]["retried"] == 2
    assert not {"empty", "no_reply"}.intersection(summary["totals"])
    assert not {"empty", "no_reply"}.intersection(summary["per_period"]["1"])
