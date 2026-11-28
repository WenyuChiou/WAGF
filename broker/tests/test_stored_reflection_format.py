"""Stored reflection compatibility and shipped one-agent configuration contracts."""
from pathlib import Path

import pytest
import yaml

from broker.components.cognitive.reflection import (
    LEGACY_STORED_REFLECTION_LABEL,
    STORED_REFLECTION_LABEL,
    ReflectionEngine,
    compose_lesson_with_facts,
    split_stored_reflection,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = [
    "examples/single_agent/agent_types.yaml",
    "examples/single_agent/config_variants/nonudge/agent_types.yaml",
    "examples/irrigation_abm/config/agent_types.yaml",
    "examples/irrigation_abm/config_variants/with_validator/agent_types.yaml",
    "examples/irrigation_abm/config_variants/without_validator/agent_types.yaml",
]


def test_composed_reflection_uses_neutral_label_and_preserves_answer():
    facts, answer = "Year 1: an outcome.", "I should keep watching."
    stored = compose_lesson_with_facts([facts], answer)
    assert stored == f"{facts} Looking back: {answer}"
    assert STORED_REFLECTION_LABEL == "Looking back:"
    assert LEGACY_STORED_REFLECTION_LABEL == "Lesson:"
    assert split_stored_reflection(stored) == (facts, answer)
    assert compose_lesson_with_facts([], answer) == answer


@pytest.mark.parametrize("label", ["Lesson:", "Looking back:"])
def test_split_accepts_both_labels_and_preserves_later_labels(label):
    answer = "I should keep watching. Lesson: stay cautious. Looking back: I agree."
    assert split_stored_reflection(f"Year 1: an outcome. {label} {answer}") == (
        "Year 1: an outcome.", answer)


@pytest.mark.parametrize("answer", ["I should keep watching.", ""])
def test_unlabelled_text_is_an_answer_alone(answer):
    assert split_stored_reflection(answer) == ("", answer)


@pytest.mark.parametrize("config_path", CONFIGS)
@pytest.mark.parametrize("record_lines", [None, ["Year 1: an outcome."]])
def test_shipped_config_has_one_first_person_instruction_and_no_unused_keys(config_path, record_lines):
    reflection = yaml.safe_load((ROOT / config_path).read_text(encoding="utf-8"))["global_config"]["reflection"]
    assert "first person" not in reflection["persona_instruction"]
    assert reflection["persona_instruction"].startswith("Base your answer only on the years listed above.")
    assert "method" not in reflection
    if "single_agent" in config_path:
        assert "triggers" not in reflection
    prompt = ReflectionEngine().generate_reflection_prompt_one_agent(
        "You are a water user.", [{"content": "Year 1: an outcome.", "year": 1}], 1,
        topic=reflection["topic"], persona_instruction=reflection["persona_instruction"],
        record_lines=record_lines, year_lines=True)
    assert prompt.count("first person") == 1


@pytest.mark.parametrize("label", ["Lesson:", "Looking back:"])
def test_flood_recovers_fact_years_for_both_labels(label):
    from examples.single_agent.run_flood import _remembered_reflection_years

    line = ("Consolidated Reflection (written in Year 4): Year 2: an outcome. "
            f"Year 4: another outcome. {label} I recall Year 9: an imagined event.")
    ungrounded = "Consolidated Reflection (written in Year 4): I should keep watching."
    assert _remembered_reflection_years([line, ungrounded]) == [2, 4]


def test_nonudge_variant_matches_base_except_the_authorized_prompt_line():
    base = ROOT / "examples/single_agent"
    variant = base / "config_variants/nonudge"
    for path in variant.rglob("*"):
        if not path.is_file() or path.name == "NOTES.md":
            continue
        relative = path.relative_to(variant)
        original = (base / relative).read_text(encoding="utf-8")
        copied = path.read_text(encoding="utf-8")
        if relative.as_posix() == "config/prompts/household.txt":
            original = "\n".join(line for line in original.splitlines()
                                 if not line.startswith("Note: If no flood occurred"))
            copied = "\n".join(copied.splitlines())
        assert copied == original, str(relative)
