"""The generated parameter table: coverage, defaults, ranges and the committed document."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from broker.components.memory.factory import FRACTION_PARAMETERS, GOVERNANCE_FRACTION_KEYS
from broker.config import parameter_table as pt

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "references" / "parameter_table.md"


def test_the_table_has_no_problems():
    assert pt.problems() == []


def test_a_new_accepted_key_without_a_row_is_reported(monkeypatch):
    real = pt.accepted_keys()
    monkeypatch.setattr(pt, "accepted_keys", lambda: {**real, "global_config.memory.brand_new_rate": ["test"]})
    assert pt.missing_rows() == ["global_config.memory.brand_new_rate"]
    assert "accepted key has no row: global_config.memory.brand_new_rate" in pt.problems()


def test_every_row_path_is_unique_and_in_a_known_group():
    paths = [row.path for row in pt.rows()]
    assert len(paths) == len(set(paths))
    assert {row.group for row in pt.rows()} <= set(pt.GROUPS)
    assert all(row.consumers for row in pt.rows())


def test_a_consumer_with_no_default_is_reported(monkeypatch):
    first = pt.rows()[0]
    broken = replace(first.consumers[0], default=lambda: pt.MISSING)
    patched = (replace(first, consumers=(broken,) + first.consumers[1:]),) + pt.rows()[1:]
    monkeypatch.setattr(pt, "rows", lambda: patched)
    assert pt.rows_without_default() == [(first.path, broken.label)]
    assert any(line.startswith("no default found") for line in pt.problems())


def test_fraction_defaults_are_in_the_unit_interval():
    seen = 0
    for row in pt.rows():
        if row.group != "fraction":
            continue
        for consumer in row.consumers:
            value = consumer.default()
            assert isinstance(value, (int, float)) and not isinstance(value, bool), (row.path, consumer.label)
            assert 0 <= value <= 1, (row.path, consumer.label, value)
            seen += 1
    assert seen > 40


def test_count_defaults_are_integers_or_none():
    for row in pt.rows():
        if row.group != "count":
            continue
        for consumer in row.consumers:
            value = consumer.default()
            assert value is None or (isinstance(value, int) and not isinstance(value, bool)), (
                row.path, consumer.label, value)


def test_keys_with_two_defaults_list_both():
    by_path = {row.path: row for row in pt.rows()}
    window = {c.label: c.default() for c in by_path["global_config.memory.window_size"].consumers}
    assert window["HumanCentricMemoryEngine"] == 3
    assert window["registry humancentric factory"] == 5
    assert window["broker.run"] == 3
    boost = {c.label: c.default() for c in by_path["global_config.reflection.importance_boost"].consumers}
    assert boost["get_reflection_config"] == 0.9 and boost["ReflectionTriggerConfig"] == 0.85
    arousal = {c.label: c.default() for c in by_path["global_config.memory.arousal_threshold"].consumers}
    assert arousal == {"UniversalCognitiveEngine": 2.0, "HumanCentricMemoryEngine": 0.5}
    top_n = {c.label: c.default() for c in by_path["global_config.governance.retrieval.top_n"].consumers}
    assert top_n == {"get_retrieval_config": 3, "SkillRetriever": 5}
    predict = {c.label: c.default() for c in by_path["global_config.llm.num_predict"].consumers}
    assert sorted(predict.values()) == [-1, 2048]


def test_the_named_exceptions_are_the_only_ones():
    exceptions = {row.path for row in pt.rows() if row.group == "exception"}
    assert exceptions == {
        "global_config.memory.arousal_threshold",
        "global_config.governance.retrieval.min_score",
        "global_config.llm.temperature",
        "global_config.llm.top_p",
        "global_config.llm.top_k",
    }


def test_every_fraction_name_has_a_section_and_every_governance_fraction_is_checked():
    assert set(pt._FRACTION_HOME) == set(FRACTION_PARAMETERS)
    checked = {
        f"global_config.governance.{'.'.join(path)}.{key}"
        for path, keys in GOVERNANCE_FRACTION_KEYS.items() for key in keys
    }
    governance_fractions = {
        row.path for row in pt.rows()
        if row.group == "fraction" and row.path.startswith("global_config.governance.")
    }
    assert governance_fractions == checked


def test_every_non_numeric_key_appears_in_the_file_that_reads_it():
    for section, keys in pt._NONNUMERIC.items():
        for key, where in keys.items():
            relative = where.split(" (")[0]
            text = (ROOT / relative).read_text(encoding="utf-8")
            assert key in text, f"{section}.{key} is not mentioned in {relative}"


def test_every_accepted_key_is_accepted_in_a_section():
    sections = pt.accepted_section_keys()
    assert set(sections) == set(pt._SECTIONS)
    assert {"decay_rate", "consolidation_prob", "ema_alpha", "retrieval_top_k"} <= sections["memory"]
    assert {"institutional_threshold", "crisis", "periodic_interval"} <= sections["reflection"]
    assert sections["reflection.triggers"] == {
        "crisis", "periodic_interval", "decision_types", "institutional_threshold"}
    assert "enabled" in sections["llm_safeguard"] and "abort_window" in sections["llm_safeguard"]


def test_render_is_deterministic_and_equals_the_committed_document():
    assert pt.render_markdown() == pt.render_markdown()
    committed = DOC.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert pt.render_markdown() == committed, (
        "docs/references/parameter_table.md is out of date: run "
        "python -m broker.config.parameter_table --write docs/references/parameter_table.md")


def test_the_document_says_it_is_generated():
    head = pt.render_markdown().splitlines()[:6]
    assert any("Do not edit by hand" in line for line in head)
    assert any("python -m broker.config.parameter_table --write docs/references/parameter_table.md" in line
               for line in head)


def test_check_command_exits_1_on_a_stale_file(tmp_path, capsys):
    good = tmp_path / "table.md"
    assert pt.main(["--write", str(good)]) == 0
    assert pt.main(["--check", str(good)]) == 0
    good.write_text(good.read_text(encoding="utf-8") + "\nhand edit\n", encoding="utf-8")
    assert pt.main(["--check", str(good)]) == 1
    assert pt.main(["--check", str(tmp_path / "missing.md")]) == 1
    capsys.readouterr()


def test_multi_skill_max_skills_row_matches_the_accessor():
    from broker.utils.agent_config import AgentTypeConfig

    row = next(r for r in pt.rows() if r.path == "<agent_type>.multi_skill.max_skills")
    assert row.group == "count"
    config = AgentTypeConfig()
    config._config = {"a": {"multi_skill": {"enabled": True}}}
    assert [c.default() for c in row.consumers] == [config.get_multi_skill_config("a")["max_skills"]] == [2]
    config._config = {"a": {"multi_skill": {"enabled": True, "max_skills": 9}}}
    assert config.get_multi_skill_config("a")["max_skills"] == 2  # the cap the row's range states
    assert "<agent_type>.multi_skill.max_skills" in pt.accepted_keys()


def test_the_document_has_the_action_number_note():
    text = pt.render_markdown()
    assert "## The agent's action number" in text
    assert "min: 0" in text and "max: 1" in text and "multi_skill" in text
