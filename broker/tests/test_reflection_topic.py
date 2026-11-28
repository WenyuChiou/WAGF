"""One-agent topic contract and neutral wording through both real domains."""
import json
from pathlib import Path

import pytest
import yaml

from broker.components.cognitive.reflection import (
    GROUNDING_KEYS, REFLECTION_RETRY_NOTE, ReflectionEngine, reflection_question,
    run_checked_reflection,
)
from broker.utils.agent_config import AgentTypeConfig
from examples.grounded_reflection import require_grounded_reflection
from examples.irrigation_abm.reflection_checks import OutcomeLine, check_lesson
from examples.single_agent.flood_reflection import FloodYear, check_flood_lesson

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = (
    ("examples/irrigation_abm/config/agent_types.yaml", "irrigation_farmer"),
    ("examples/irrigation_abm/config_variants/with_validator/agent_types.yaml", "irrigation_farmer"),
    ("examples/irrigation_abm/config_variants/without_validator/agent_types.yaml", "irrigation_farmer"),
    ("examples/single_agent/agent_types.yaml", "household"),
    ("examples/single_agent/agent_types_stress.yaml", "household"),
    ("examples/single_agent/config_variants/nonudge/agent_types.yaml", "household"),
)


def config_with(data):
    config = AgentTypeConfig()
    config._config = data
    return config


def test_topic_builds_exact_question_and_strips_surrounding_spaces():
    assert reflection_question("  floods and your home  ") == (
        "What do your recent years tell you about floods and your home?")


@pytest.mark.parametrize("topic", [None, 7, [], "", "  ", "water\nhome", "water\rhome", "water?", "water. "])
def test_invalid_topic_explains_the_contract(topic):
    with pytest.raises(ValueError, match="a short noun phrase naming what the agent faces") as exc:
        reflection_question(topic)
    assert "with no action verb or direction" in str(exc.value)
    assert "What do your recent years tell you about <topic>?" in str(exc.value)


@pytest.mark.parametrize("value", [None, "", "per-type topic", ["invalid topic"]])
def test_topic_scope_order_returns_raw_values_even_when_invalid(value):
    config = config_with({
        "person": {"reflection": {"topic": value}},
        "global_config": {"reflection": {"topic": "global topic"}},
        "shared": {"reflection": {"topic": "shared topic"}},
    })
    assert config.get_reflection_topic("person") == value
    del config._config["person"]["reflection"]["topic"]
    assert config.get_reflection_topic("person") == "global topic"
    del config._config["global_config"]["reflection"]["topic"]
    assert config.get_reflection_topic("person") == "shared topic"
    del config._config["shared"]["reflection"]["topic"]
    assert config.get_reflection_topic("person") is None


@pytest.mark.parametrize("path,agent_type", CONFIGS)
def test_shipped_configs_pass_runner_gate(path, agent_type):
    config = AgentTypeConfig.load(str(ROOT / path), force_reload=True)
    require_grounded_reflection(config, agent_type=agent_type)
    assert reflection_question(config.get_reflection_topic(agent_type)).endswith("?")


def test_runner_gate_checks_the_runners_own_agent_type_without_a_block():
    """A config whose only block is another type, with no global or shared
    topic, would leave the runner's own type without a topic."""
    data = {"global_config": {"reflection": dict.fromkeys(GROUNDING_KEYS, True)},
            "person": {"reflection": {"topic": "your circumstances"}}}
    require_grounded_reflection(config_with(data), agent_type="person")
    with pytest.raises(ValueError, match="reflection.topic must be a short noun phrase"):
        require_grounded_reflection(config_with(data), agent_type="household")


@pytest.mark.parametrize("scope", ["person", "global_config", "shared"])
@pytest.mark.parametrize("questions", [[], None, ["Old question?"]])
def test_runner_gate_rejects_retired_questions_in_every_scope(scope, questions):
    data = {"global_config": {"reflection": dict.fromkeys(GROUNDING_KEYS, True)},
            "person": {"reflection": {"topic": "your circumstances"}}}
    data.setdefault(scope, {}).setdefault("reflection", {})["questions"] = questions
    with pytest.raises(ValueError, match="reflection.questions.*2026-11-27.*v0.7.0"):
        require_grounded_reflection(config_with(data), agent_type="person")


@pytest.mark.parametrize("topic", [None, "", "topic?", "topic.", "one\ntwo"])
def test_runner_gate_requires_valid_topic(topic):
    reflection = dict.fromkeys(GROUNDING_KEYS, True)
    if topic is not None:
        reflection["topic"] = topic
    with pytest.raises(ValueError, match="reflection.topic must be a short noun phrase"):
        require_grounded_reflection(config_with({"global_config": {"reflection": reflection}}),
                                    agent_type="household")


def _all_problem_messages():
    """Exercise every generic blocking code and every domain message branch."""
    problems = []
    for reply in ("", '{"answer": "123"}', json.dumps({"answer": "I watch " + "water " * 90}),
                  '{"answer": "In 2031 I waited 5 days."}'):
        result = run_checked_reflection(
            ReflectionEngine(), prompt="P", agent_id="A", period=1,
            llm_call=lambda _: reply, retries=0, lesson_no_numbers=True)
        problems.extend(result.first_problems)

    def broken_checker(_):
        raise RuntimeError("scripted failure")

    result = run_checked_reflection(
        ReflectionEngine(), prompt="P", agent_id="A", period=1,
        llm_call=lambda _: '{"answer": "I watch the river."}', checker=broken_checker)
    problems.extend(result.first_problems)
    assert {p.code for p in problems} == {"no_reply", "empty", "too_long", "year", "number", "checker_error"}

    lines = [OutcomeLine(2020, "keep", 100, 100, False, 0, "below", "higher", ""),
             OutcomeLine(2021, "keep", 100, 80, True, 20, "above", "lower", ""),
             OutcomeLine(2022, "keep", 100, 100, False, 0, "below", "higher", "")]
    irrigation = []
    for text in (
        "Lower precipitation means my demand is not met.",
        "Higher precipitation always meant my demand was fully met.",
        "Lake Mead levels consistently rose.", "Lake Mead levels consistently declined.",
        "My demand consistently fell short.", "My demand was consistently fully met.",
        "I received 99,999 acre-ft.",
    ):
        irrigation.extend(check_lesson(text, lines, "I received 100 acre-ft."))
    assert {p.code for p in irrigation} == {
        "precipitation_rule", "mead_direction", "always_short", "always_full", "foreign_figure"}
    assert len({p.message for p in irrigation}) == 7
    problems.extend(irrigation)

    dry = FloodYear(1, False, False, False, False, "dry")
    hit = FloodYear(2, True, True, False, False, "damage")
    spared = FloodYear(3, True, False, True, True, "spared")
    flood = []
    for text in (
        "I have never experienced a flood.", "My house has never been damaged.",
        "A flood comes every year.", "Every flood damaged my house.",
        "My house is elevated.", "My house is not elevated yet.",
        "I have flood insurance.", "I do not have flood insurance.",
    ):
        for years in ([dry, hit], [dry, hit, spared]):
            flood.extend(check_flood_lesson(text, years))
    assert {p.code for p in flood} == {
        "no_flood_claim", "no_damage_claim", "every_year_flood_claim", "always_damage_claim",
        "elevation_state", "insurance_state"}
    assert len({p.message for p in flood}) == 8
    return problems + flood


@pytest.mark.parametrize("path,agent_type", [CONFIGS[1], CONFIGS[3]])
def test_real_domain_prompt_and_all_retry_messages_are_neutral(path, agent_type):
    config = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    reflection = config["global_config"]["reflection"]
    prompt = ReflectionEngine().generate_reflection_prompt_one_agent(
        "You are a resident.", [{"content": "Year 1: supply was low.", "year": 1},
                               {"content": "Year 2: supply was higher.", "year": 2}], 2,
        topic=reflection["topic"], persona_instruction=reflection["persona_instruction"],
        record_lines=["Year 2: supply was higher."])
    assert [line for line in prompt.splitlines() if line.startswith("Question")] == [
        f"Question: What do your recent years tell you about {reflection['topic']}?"]
    retry = REFLECTION_RETRY_NOTE.format(reasons="; ".join(p.message for p in _all_problem_messages()))
    for word in ("lesson", "learn", "teach"):
        assert word not in (prompt + retry).lower()


@pytest.mark.parametrize("allow_plain_text", [False, True])
def test_answer_parser_reads_value_and_preserves_empty(allow_plain_text):
    engine = ReflectionEngine()
    for raw in ('{"answer": "I keep an eye on the river."}',
                '{"answer": "I keep an eye on the river.", "note": "x"}'):
        assert engine.parse_batch_reflection_response(
            raw, ["A"], 1, allow_plain_text=allow_plain_text)["A"].summary == "I keep an eye on the river."
    for raw in ('{"answer": ""}', '{"answer": "", "note": "x"}'):
        assert engine.parse_batch_reflection_response(
            raw, ["A"], 1, allow_plain_text=allow_plain_text) == {"A": None}
    if allow_plain_text:
        assert engine.parse_batch_reflection_response(
            '{"lesson": "I keep an eye on the river.", "note": "x"}',
            ["A"], 1, allow_plain_text=True) == {"A": None}
