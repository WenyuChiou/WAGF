"""The one-agent year-end reflection prompt (single-agent flood and irrigation).

Layout decided by the owner on 2026-11-27: an identity sentence, the year, the
question, the agent's recent years, the program-written lines, the rules, the
configured instruction and a ``{"lesson": ...}`` answer. The old one-agent
layout ("Reflection Assistant" / "Task Data to Process") is retired.
"""
import json
import re

import pytest

from broker.components.cognitive.reflection import (
    LESSON_ONLY_INSTRUCTION,
    REFLECTION_RETRY_NOTE,
    ReflectionEngine,
    first_sentence,
    run_checked_reflection,
    LessonProblem,
    lesson_number_problems,
)

IDENTITY = "You are Agent_007, an agricultural water user holding a water right of 28,295 acre-ft/year."
BANNED = ("simulation", "Reflection Assistant", "agent", "Agent IDs", "Task Data", "###")


def _items():
    return [
        {"content": "Year 2019: you asked for less and got all of it.", "year": 2019},
        {"content": "Year 2018: you kept your request and received less.", "year": 2018},
    ]


def _prompt(**kw):
    args = dict(questions=["What does your record teach you?"],
                persona_instruction="Speak in the first person and base your lesson only on the years listed.",
                record_lines=["Year 2019: demand 100, received 90."],
                rule_lines=["A shortage is shared in proportion to requests."])
    args.update(kw)
    return ReflectionEngine().generate_reflection_prompt_one_agent(IDENTITY, _items(), 2019, **args)


def test_layout_is_exactly_the_decided_one():
    assert _prompt() == "\n".join([
        IDENTITY,
        "It is the end of 2019. Look back on your recent years and say what you learned.",
        "Question: What does your record teach you?",
        "",
        "Your recent years:",
        "- Year 2018: you kept your request and received less.",
        "- Year 2019: you asked for less and got all of it.",
        "",
        "What happened this year (kept with your lesson; do not repeat it):",
        "- Year 2019: demand 100, received 90.",
        "",
        "Rules that apply to you:",
        "- A shortage is shared in proportion to requests.",
        "",
        "Speak in the first person and base your lesson only on the years listed.",
        LESSON_ONLY_INSTRUCTION,
        "",
        'Answer with this JSON object only: {"lesson": "<your lesson>"}',
    ])


def test_banned_words_absent_apart_from_the_identity_sentence():
    body = _prompt().replace(IDENTITY, "", 1)
    for word in BANNED:
        assert word not in body, word
    assert "Agent_007" not in body
    assert "the record above" not in body


def test_optional_parts_are_left_out_and_several_questions_are_listed():
    p = _prompt(record_lines=None, rule_lines=None, questions=["Q one?", "Q two?"])
    assert "What happened this year" not in p
    assert "Rules that apply to you:" not in p
    assert "Questions:\n- Q one?\n- Q two?" in p
    assert LESSON_ONLY_INSTRUCTION not in p  # nothing is stored with the lesson


def test_no_memory_lines_means_no_reflection_is_asked():
    assert ReflectionEngine().generate_reflection_prompt_one_agent(IDENTITY, [], 2019) == ""


def test_empty_identity_raises():
    with pytest.raises(ValueError):
        ReflectionEngine().generate_reflection_prompt_one_agent("  ", _items(), 2019)
    with pytest.raises(ValueError):
        first_sentence("")


def test_first_sentence_stops_at_the_first_full_stop_followed_by_space():
    text = ("You are MohaveValleyIDD, an agricultural water user (an irrigation district, a tribal "
            "water user, or a group of water users) in the Lower Basin of the Colorado River, "
            "holding a water right of 28,295 acre-ft/year. The more water you receive, the more you can produce.")
    assert first_sentence(text).endswith("28,295 acre-ft/year.")
    assert first_sentence("You are a homeowner who owns your home outright. living alone.") == \
        "You are a homeowner who owns your home outright."


@pytest.mark.parametrize("reply", [
    '{"lesson": "I should watch my supply before changing my request."}',
    '```json\n{"lesson": "I should watch my supply before changing my request."}\n```',
    '{"lesson": "I should watch my supply before changing my request.", "note": "x"}',
    '{"Agent_007": "I should watch my supply before changing my request."}',
    '{"answer": "I should watch my supply before changing my request."}',
    'I should watch my supply before changing my request.',
])
def test_lesson_reply_and_tolerated_small_model_replies_parse(reply):
    out = ReflectionEngine().parse_batch_reflection_response(
        reply, ["Agent_007"], 2019, allow_plain_text=True)
    assert out["Agent_007"].summary == "I should watch my supply before changing my request."


def test_lesson_key_is_strict_not_lenient():
    out = ReflectionEngine().parse_batch_reflection_response(
        '{"lesson": "I should watch my supply early."}', ["A"], 1, allow_plain_text=True)
    assert out["A"].parse == "strict"


def test_retry_note_text_and_reason_messages_are_plain():
    assert REFLECTION_RETRY_NOTE == (
        "Your previous lesson cannot be used: {reasons}. "
        "Please answer again, taking the instructions above into account.")
    assert "###" not in REFLECTION_RETRY_NOTE
    seen = []
    prompts = []

    def llm(text):
        prompts.append(text)
        return json.dumps({"lesson": ["In 2031 I learned to wait 5 days.", "I learned to wait for clear signs."][len(prompts) - 1]})

    result = run_checked_reflection(
        ReflectionEngine(), prompt="BASE", agent_id="A", period=1, llm_call=llm,
        lesson_no_numbers=True,
        checker=lambda lesson: seen.append(lesson) or [])
    assert result.outcome == "stored_after_retry"
    assert prompts[1] == "BASE\n\nYour previous lesson cannot be used: it names a year (2031); it contains a number (5). " \
                         "Please answer again, taking the instructions above into account."
    # Every message that can reach {reasons} is plain words: no rule id, no log label.
    for p in lesson_number_problems("In 2031 I paid 5 dollars."):
        assert p.message.startswith("it ") and not re.search(r"[_\[\]#]", p.message)


def test_checker_error_is_not_retried_and_nothing_is_stored(tmp_path):
    calls = []

    def llm(text):
        calls.append(text)
        return json.dumps({"lesson": "I learned to wait for clear signs."})

    def boom(lesson):
        raise RuntimeError("scripted checker failure")

    log = tmp_path / "log.jsonl"
    result = run_checked_reflection(
        ReflectionEngine(), prompt="BASE", agent_id="A", period=1, llm_call=llm,
        checker=boom, log_path=log)
    assert len(calls) == 1
    assert result.outcome == "dropped" and result.insight is None
    assert [p.code for p in result.final_problems] == ["checker_error"]
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1 and rows[0]["problems"][0]["code"] == "checker_error"
    assert "Your previous lesson cannot be used" not in calls[0]
