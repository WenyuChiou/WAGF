"""Flood reflection ON for the WRR26 rerun (flood design record PI decision
2026-10-07 item 7), with the irrigation mechanism of spec item 45:

- the year-end reflection sees the year's own flood outcome and the house's
  state at the end of it, plus remembered years from the prior reflection;
- the program writes the key years (the year just ended and the most recent
  damaged year) and the model writes only the lesson;
- semantic claims that a listed year contradicts (``check_flood_lesson``) are
  stored and reported as flags; only mechanical failures such as a number,
  junk, or overlength reply are retried and then dropped;
  counts and flags per year go to the run log and the manifest;
- the stored reflection is a high-importance memory shown after five recent
  event lines and up to two significant older event lines;
- with ``global_config.reflection.enabled`` false and the grounding keys off,
  nothing of this runs (no reflection engine under the window memory, the
  proxy passes every call through, as before).

Every test here fails on c7b10c05 (none of this existed).
"""
from __future__ import annotations

import json
import random
import re
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripted_mock_driver import REFLECTION_LESSON, reset_state, run_scripted_mock  # noqa: E402

from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine  # noqa: E402
from broker.components.memory.engines.window import WindowMemoryEngine  # noqa: E402
from examples.single_agent.flood_reflection import (  # noqa: E402
    FloodYear,
    check_flood_lesson,
    fact_line,
    key_years,
    year_line,
)

SA = Path(__file__).resolve().parents[1]

DRY = FloodYear(1, False, False, False, False, "Year 1: No flood occurred this year.")
HIT = FloodYear(3, True, True, False, True, "Year 3: Got flooded with $10,000 damage on my house.")
SPARED = FloodYear(4, True, False, True, True, "Year 4: A flood occurred, but my house was protected by its elevation.")


# ===========================================================================
# the year record, key years and facts
# ===========================================================================

def test_year_line_and_fact_line():
    assert year_line(HIT) == ("Year 3: Got flooded with $10,000 damage on my house. At the end of Year 3 my "
                              "house was not elevated and I had flood insurance.")
    assert fact_line(HIT) == ("Year 3: a flood damaged my house; at the end of the year my house was not "
                              "elevated and I had flood insurance.")
    assert fact_line(SPARED).startswith("Year 4: a flood occurred but did not damage my house; at the end of "
                                        "the year my house was elevated")
    assert fact_line(DRY) == ("Year 1: no flood occurred; at the end of the year my house was not elevated "
                              "and I did not have flood insurance.")


def test_key_years_are_the_last_year_and_the_latest_damage():
    assert key_years([DRY, HIT, SPARED], 4) == [3, 4]
    assert key_years([DRY, SPARED], 4) == [4]
    assert key_years([DRY, HIT], 3) == [3]
    with pytest.raises(ValueError, match="not among"):
        key_years([DRY], 2)


@pytest.mark.parametrize("lesson,years,codes", [
    ("I learned that my house has never been damaged, so waiting is safe.", [DRY, HIT], ["no_damage_claim"]),
    ("I learned that my house has never been damaged.", [DRY, SPARED], []),
    ("I have never experienced a flood, so I can relax.", [DRY, SPARED], ["no_flood_claim"]),
    ("I have never experienced a flood, so I can relax.", [DRY], []),
    ("I learned that a flood comes every year.", [DRY, HIT], ["every_year_flood_claim"]),
    ("Floods come every year, but I can't afford to elevate.", [DRY, HIT],
     ["every_year_flood_claim"]),
    ("Every flood has damaged my house.", [HIT, SPARED], ["always_damage_claim"]),
    ("Every flood damaged my house, but I didn't give up.", [HIT, SPARED],
     ["always_damage_claim"]),
    ("My house is elevated, so floods worry me less.", [DRY, HIT], ["elevation_state"]),
    ("My house is not elevated yet.", [DRY, SPARED], ["elevation_state"]),
    ("If my house were elevated, floods would worry me less.", [DRY, HIT], []),
    ("I do not have flood insurance.", [DRY, HIT], ["insurance_state"]),
    ("I have flood insurance, which helps.", [HIT, SPARED, FloodYear(5, False, False, True, False, "x")],
     ["insurance_state"]),
    ("I learned that protecting my home early matters more than reacting after a flood.", [DRY, HIT, SPARED], []),
])
def test_check_flood_lesson(lesson, years, codes):
    assert [p.code for p in check_flood_lesson(lesson, years)] == codes


def test_universal_patterns_are_reported_without_qualifier_skips():
    assert [p.code for p in check_flood_lesson(
        "Not every flood damaged my house, but one did.", [HIT, SPARED]
    )] == ["always_damage_claim"]
    assert [p.code for p in check_flood_lesson(
        "Every flood damaged my house because no protection worked.", [HIT, SPARED]
    )] == ["always_damage_claim"]
    assert [p.code for p in check_flood_lesson(
        "My house has never been damaged.", [DRY, HIT]
    )] == ["no_damage_claim"]


# ===========================================================================
# the reflection slot of the memory proxy
# ===========================================================================

class _Agent:
    def __init__(self, aid):
        self.id = aid


def _proxy(slot: bool):
    import examples.single_agent.run_flood as rf
    return rf.DecisionFilteredMemoryEngine(WindowMemoryEngine(window_size=5), reflection_slot=slot)


def test_reflection_slot_shows_the_reflection_after_the_five_event_lines():
    proxy = _proxy(True)
    for i in range(7):
        proxy.add_memory("A", f"Year {i}: event.", {"importance": 0.1})
    proxy.add_memory("A", "Consolidated Reflection (written in Year 6): x Lesson: y.", {"type": "reflection"})
    got = proxy.retrieve(_Agent("A"), top_k=5)
    assert got[:5] == [f"Year {i}: event." for i in range(2, 7)]
    assert got[5] == "Consolidated Reflection (written in Year 6): x Lesson: y."
    assert proxy.remove_by_type("A", "reflection") == 1
    assert proxy.retrieve(_Agent("A"), top_k=5) == [f"Year {i}: event." for i in range(2, 7)]
    proxy.add_memory("A", "Decided to: x", {})  # the runner's decision line is still dropped
    assert "Decided to: x" not in proxy.retrieve(_Agent("A"), top_k=5)


def test_slot_off_passes_every_call_through_as_before():
    proxy = _proxy(False)
    for i in range(6):
        proxy.add_memory("A", f"Year {i}: event.", {"importance": 0.1})
    proxy.add_memory("A", "Consolidated Reflection: z", {"type": "reflection"})
    # off: the reflection is an ordinary window item, as before item 7
    assert proxy.retrieve(_Agent("A"), top_k=5)[-1] == "Consolidated Reflection: z"
    with pytest.raises(NotImplementedError):
        proxy.remove_by_type("A", "reflection")


def test_enabled_must_be_a_yaml_bool():
    import examples.single_agent.run_flood as rf
    assert rf._reflection_enabled({}) is False
    assert rf._reflection_enabled({"reflection": {"enabled": True}}) is True
    with pytest.raises(ValueError, match="enabled"):
        rf._reflection_enabled({"reflection": {"enabled": "yes"}})


def _memory_5_2_1():
    import examples.single_agent.run_flood as rf

    inner = HumanCentricMemoryEngine(
        window_size=5,
        top_k_significant=2,
        consolidation_threshold=0.0,
        decay_rate=0.1,
        deterministic_consolidation=True,
        decay_ignore_emotion=True,
        decay_by_calendar_year=True,
        reflection_slot="separate",
        significant_tie_break="recent",
    )
    return rf.DecisionFilteredMemoryEngine(
        inner, reflection_slot=True, event_memory_5_2_1=True)


def _add_event(memory, year, line):
    import examples.single_agent.run_flood as rf

    memory.add_memory("A", line, rf._flood_event_memory_metadata(line, year))


def test_flood_memory_5_2_1_keeps_year_1_damage_visible_in_year_6():
    memory = _memory_5_2_1()
    lines = ["Year 1: Got flooded with $10,000 damage on my house."]
    for year, count in ((2, 3), (3, 4), (4, 5), (5, 3), (6, 4)):
        lines.append(f"Year {year}: No flood occurred this year.")
        lines.extend(
            f"Year {year}: I observe {i}% of my neighbors have elevated homes."
            for i in range(1, count)
        )
    for line in lines:
        _add_event(memory, int(re.search(r"Year (\d+)", line).group(1)), line)
    reflection = "Consolidated Reflection (written in Year 6): facts Lesson: lesson."
    memory.add_memory("A", reflection, {"type": "reflection"})

    got = [item["content"] for item in memory.retrieve(_Agent("A"), top_k=5)]

    assert len(got) == 8
    assert got[-1] == reflection
    assert got[2:7] == lines[-5:]
    assert lines[0] in got[:2]


def test_flood_significant_damage_uses_calendar_decay_and_newer_first_ties():
    memory = _memory_5_2_1()
    old_damage = "Year 1: Got flooded with $10,000 damage on my house."
    old_tie = "Year 2: I observe 10% of my neighbors have elevated homes."
    new_tie = "Year 2: I observe 20% of my neighbors have relocated."
    new_damage = "Year 3: Despite elevation, the flood was severe enough to cause damage."
    for year, line in ((1, old_damage), (2, old_tie), (2, new_tie), (3, new_damage)):
        _add_event(memory, year, line)
    for i in range(5):
        _add_event(memory, 6, f"Year 6: recent event {i}.")

    got = [item["content"] for item in memory.retrieve(_Agent("A"), top_k=5)]
    assert got[:2] == [new_damage, old_damage]

    tie_memory = _memory_5_2_1()
    for year, line in ((2, old_tie), (2, new_tie)):
        _add_event(tie_memory, year, line)
    for i in range(5):
        _add_event(tie_memory, 6, f"Year 6: recent event {i}.")
    tied = [item["content"] for item in tie_memory.retrieve(_Agent("A"), top_k=5)]
    assert tied[:2] == [new_tie, old_tie]


def test_significant_random_recall_adds_original_year_but_recent_wording_is_unchanged():
    memory = _memory_5_2_1()
    old_recall = "Suddenly recalled: 'Some residents reported delays when processing claims'."
    _add_event(memory, 2, old_recall)
    _add_event(memory, 1, "Year 1: Elevation grants are available.")
    recent_recall = "Suddenly recalled: 'A few households elevated before recent floods'."
    for i in range(4):
        _add_event(memory, 6, f"Year 6: recent event {i}.")
    _add_event(memory, 6, recent_recall)

    got = [item["content"] for item in memory.retrieve(_Agent("A"), top_k=5)]

    assert got[0] == f"Year 2: {old_recall}"
    assert got[-1] == recent_recall


def test_flood_memory_5_2_1_config_is_opt_in_and_requires_a_yaml_bool():
    import examples.single_agent.run_flood as rf

    assert rf._flood_memory_5_2_1_enabled({}) is False
    assert rf._flood_memory_5_2_1_enabled({"memory": {"event_memory_5_2_1": False}}) is False
    assert rf._flood_memory_5_2_1_enabled({"memory": {"event_memory_5_2_1": True}}) is True
    with pytest.raises(ValueError, match="event_memory_5_2_1"):
        rf._flood_memory_5_2_1_enabled({"memory": {"event_memory_5_2_1": "yes"}})


def test_flood_memory_provenance_reports_resolved_composed_engine_options(tmp_path):
    import examples.single_agent.run_flood as rf

    inner = HumanCentricMemoryEngine(
        window_size=5,
        top_k_significant=2,
        reflection_slot="separate",
    )
    memory = rf.DecisionFilteredMemoryEngine(
        inner,
        reflection_slot=True,
        event_memory_5_2_1=True,
    )

    expected = {
        "engine_type": "HumanCentricMemoryEngine",
        "window_size": 5,
        "top_k_significant": 2,
        "reflection_slot": "separate",
        "importance_by_event_type": {
            "own_damage": 1.0,
            "flood_without_own_damage": 0.8,
            "dry": 0.2,
            "grant": 0.2,
            "neighbour_observation": 0.2,
            "random_recall": 0.2,
        },
    }
    assert rf._resolved_flood_memory_options(memory) == expected

    manifest_path = tmp_path / "reproducibility_manifest.json"
    manifest_path.write_text('{"existing": true}', encoding="utf-8")
    rf._record_flood_memory_options_provenance(tmp_path, memory)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest == {"existing": True, "flood_memory_options": expected}


def test_flood_memory_provenance_does_not_claim_composed_options_when_opted_out():
    import examples.single_agent.run_flood as rf

    memory = rf.DecisionFilteredMemoryEngine(
        WindowMemoryEngine(window_size=3),
        reflection_slot=False,
        event_memory_5_2_1=False,
    )

    assert rf._resolved_flood_memory_options(memory) == {
        "engine_type": "WindowMemoryEngine",
        "window_size": 3,
        "top_k_significant": None,
        "reflection_slot": None,
        "importance_by_event_type": None,
    }


def test_flood_memory_provenance_keeps_inner_slot_when_proxy_reflection_is_off():
    import examples.single_agent.run_flood as rf

    inner = HumanCentricMemoryEngine(
        window_size=5, top_k_significant=2, reflection_slot="separate",
    )
    memory = rf.DecisionFilteredMemoryEngine(
        inner, reflection_slot=False, event_memory_5_2_1=True,
    )
    assert rf._resolved_flood_memory_options(memory)["reflection_slot"] == inner.reflection_slot


def test_formatted_flood_prompt_preserves_recent_event_order_across_years():
    import examples.single_agent.run_flood as rf

    memory = _memory_5_2_1()
    events = ["Year 1: Got flooded with $10,000 damage on my house."]
    for year, count in ((2, 3), (3, 4), (4, 5), (5, 3), (6, 3)):
        outcome = (f"Year {year}: A flood occurred, but my house was protected by its elevation."
                   if year == 6 else f"Year {year}: No flood occurred this year.")
        events.append(outcome)
        events.extend(f"Year {year}: I observe {i}% of my neighbors have elevated homes."
                      for i in range(1, count))
    for line in events:
        _add_event(memory, int(re.search(r"Year (\d+)", line).group(1)), line)
    reflection = "Consolidated Reflection (written in Year 5): facts Lesson: keep watching."
    memory.add_memory("A", reflection, {"type": "reflection"})
    items = memory.retrieve(_Agent("A"), top_k=5)
    assert [item["content"] for item in items[2:7]] == events[-5:]

    builder = rf.FinalContextBuilder(
        agents={}, hub=SimpleNamespace(memory_engine=memory),
        prompt_templates={"household": "Your memory includes:\n{memory}"},
        yaml_path=str(SA / "agent_types.yaml"),
    )
    prompt = builder.format_prompt({"agent_type": "household", "personal": {"memory": items}})
    displayed = [line[2:] for line in prompt.splitlines() if line.startswith("- ")]
    assert displayed == [item["content"] for item in items]
    assert displayed[2:7] == events[-5:]
    assert displayed[-1] == reflection


def _reflection_harness(tmp_path, monkeypatch, records, *, store=False, memory=None):
    import examples.single_agent.run_flood as rf
    from broker.components.cognitive.reflection import CheckedReflection

    agent = SimpleNamespace(
        id="A", relocated=False, elevated=False, has_insurance=False,
        flood_history=[False] * max(records),
    )
    agent._flood_year_record = records
    if memory is None:
        memory = rf.DecisionFilteredMemoryEngine(
            WindowMemoryEngine(window_size=5), reflection_slot=True)

    captured = {"calls": []}

    class _ReflectionEngine:
        def generate_batch_reflection_prompt(self, candidates, year, **kwargs):
            captured["calls"].append({
                "year": year,
                "candidates": candidates,
                "facts": kwargs["fact_lines"],
            })
            return "prompt"

    config = SimpleNamespace(
        get_reflection_keep_latest_only=lambda: store,
    )
    runner = SimpleNamespace(
        broker=SimpleNamespace(
            config=config,
            context_builder=SimpleNamespace(memory_top_k=5),
        ),
        memory_engine=memory,
        get_llm_invoke=lambda _agent_type: (lambda _prompt: "unused"),
    )
    hook = rf.FinalParityHook(
        SimpleNamespace(agents={"A": agent}), runner,
        reflection_engine=_ReflectionEngine(), output_dir=tmp_path)
    result = (CheckedReflection(
        outcome="stored",
        insight=SimpleNamespace(importance=0.7),
        lesson="Protecting my home early matters.",
    ) if store else CheckedReflection(outcome="dropped"))
    monkeypatch.setattr(rf, "run_checked_reflection", lambda *args, **kwargs: result)
    return rf, hook, memory, agent, captured


def _add_realistic_year(memory, record, year, line_count):
    lines = [record[year]["event_line"]]
    lines.extend(
        f"Year {year}: household event line {i}."
        for i in range(2, line_count + 1)
    )
    for line in lines:
        memory.add_memory("A", line, {"importance": 0.1})


def _reflect(hook, year):
    hook._grounded_reflection(
        year,
        {"batch_size": 1, "questions": []},
        {"year_outcome": True, "year_lines": True,
         "program_facts": True, "lesson_no_numbers": True},
    )


def _records(damaged_years=()):
    result = {}
    for year in range(1, 7):
        damaged = year in set(damaged_years)
        result[year] = {
            "flood": damaged,
            "damaged": damaged,
            "event_line": (
                f"Year {year}: Got flooded with $10,000 damage on my house."
                if damaged else f"Year {year}: No flood occurred this year."
            ),
            "elevated": False,
            "insured": False,
        }
    return result


def test_grounded_reflection_carries_year_4_damage_to_year_6_from_true_record(
        tmp_path, monkeypatch):
    records = _records({4})
    _rf, hook, memory, _agent, captured = _reflection_harness(
        tmp_path, monkeypatch, records)

    _add_realistic_year(memory, records, 4, 5)
    _reflect(hook, 4)
    memory.add_memory(
        "A",
        "Consolidated Reflection (written in Year 5): "
        "Year 4: no flood occurred; at the end of the year my house was elevated "
        "and I had flood insurance. Year 5: no flood occurred; at the end of the "
        "year my house was not elevated and I did not have flood insurance. "
        "Lesson: Protecting my home early matters.",
        {"type": "reflection"},
    )
    _add_realistic_year(memory, records, 5, 3)
    _add_realistic_year(memory, records, 6, 4)
    _reflect(hook, 6)

    call = captured["calls"][-1]
    assert [item["year"] for item in call["candidates"][0]["memories"]] == [4, 5, 6]
    carried_input = call["candidates"][0]["memories"][0]["content"]
    assert carried_input == fact_line(FloodYear(
        4, True, True, False, False, records[4]["event_line"]))
    assert call["facts"] == [fact_line(FloodYear(4, True, True, False, False,
                                                  records[4]["event_line"])),
                              fact_line(FloodYear(6, False, False, False, False,
                                                  records[6]["event_line"]))]


def test_grounded_reflection_reads_year_1_damage_from_significant_event_slot(
        tmp_path, monkeypatch):
    records = _records({1})
    memory = _memory_5_2_1()
    _rf, hook, _memory, _agent, captured = _reflection_harness(
        tmp_path, monkeypatch, records, memory=memory)

    for year, line_count in ((1, 3), (2, 4), (3, 5), (4, 3), (5, 4), (6, 5)):
        lines = [records[year]["event_line"]]
        lines.extend(
            f"Year {year}: I observe {i}% of my neighbors have elevated homes."
            for i in range(1, line_count)
        )
        for line in lines:
            _add_event(memory, year, line)

    _reflect(hook, 6)

    call = captured["calls"][-1]
    assert [item["year"] for item in call["candidates"][0]["memories"]] == [1, 6]
    assert call["candidates"][0]["memories"][0]["content"] == year_line(FloodYear(
        1, True, True, False, False, records[1]["event_line"]))
    assert call["facts"] == [
        fact_line(FloodYear(1, True, True, False, False, records[1]["event_line"])),
        fact_line(FloodYear(6, False, False, False, False, records[6]["event_line"])),
    ]


@pytest.mark.parametrize(("damaged_years", "expected_year_6_keys"), [
    ({4}, [4, 6]),
    ({4, 5}, [5, 6]),
    (set(), [6]),
])
def test_grounded_reflection_chains_stored_year_4_through_year_5_to_year_6(
        tmp_path, monkeypatch, damaged_years, expected_year_6_keys):
    records = _records(damaged_years)
    _rf, hook, memory, _agent, captured = _reflection_harness(
        tmp_path, monkeypatch, records, store=True)

    _add_realistic_year(memory, records, 4, 5)
    _reflect(hook, 4)
    assert list(memory._reflections) == ["A"]
    assert len(memory._reflections["A"]) == 1

    _add_realistic_year(memory, records, 5, 3)
    _reflect(hook, 5)
    year_5_input = captured["calls"][-1]["candidates"][0]["memories"]
    assert [item["year"] for item in year_5_input] == [4, 5]
    assert year_5_input[0]["content"] == fact_line(FloodYear(
        4, 4 in damaged_years, 4 in damaged_years, False, False,
        records[4]["event_line"]))
    assert year_5_input[1]["content"] == year_line(FloodYear(
        5, 5 in damaged_years, 5 in damaged_years, False, False,
        records[5]["event_line"]))
    assert len(memory._reflections["A"]) == 1

    _add_realistic_year(memory, records, 6, 4)
    _reflect(hook, 6)
    year_6_call = captured["calls"][-1]
    assert [int(line.split(":", 1)[0].split()[1])
            for line in year_6_call["facts"]] == expected_year_6_keys
    assert len(memory._reflections["A"]) == 1


def test_grounded_reflection_new_damage_replaces_carried_year(tmp_path, monkeypatch):
    records = _records({4, 5})
    _rf, hook, memory, _agent, captured = _reflection_harness(
        tmp_path, monkeypatch, records)
    memory.add_memory(
        "A", "Consolidated Reflection (written in Year 5): "
        f"{fact_line(FloodYear(4, True, True, False, False, records[4]['event_line']))} "
        f"{fact_line(FloodYear(5, True, True, False, False, records[5]['event_line']))} "
        "Lesson: Protecting my home early matters.", {"type": "reflection"})
    _add_realistic_year(memory, records, 6, 5)
    _reflect(hook, 6)

    assert [line.split(":", 1)[0] for line in captured["calls"][-1]["facts"]] == [
        "Year 5", "Year 6"]


def test_grounded_reflection_without_damage_names_only_current_year(tmp_path, monkeypatch):
    records = _records()
    _rf, hook, memory, _agent, captured = _reflection_harness(
        tmp_path, monkeypatch, records)
    memory.add_memory(
        "A", "Consolidated Reflection (written in Year 5): "
        f"{fact_line(FloodYear(5, False, False, False, False, records[5]['event_line']))} "
        "Lesson: Protecting my home early matters.", {"type": "reflection"})
    _add_realistic_year(memory, records, 6, 3)
    _reflect(hook, 6)

    assert captured["calls"][-1]["facts"] == [
        fact_line(FloodYear(6, False, False, False, False, records[6]["event_line"]))]


@pytest.mark.parametrize("reason", ["empty", "no_reply", "checker_error"])
def test_dropped_reflection_keeps_year_4_damage_for_year_6(
        tmp_path, monkeypatch, reason):
    from broker.components.cognitive.reflection import CheckedReflection, LessonProblem

    records = _records({4})
    rf, hook, memory, _agent, captured = _reflection_harness(
        tmp_path, monkeypatch, records, store=True)
    results = iter([
        CheckedReflection(
            outcome="stored", insight=SimpleNamespace(importance=0.7),
            lesson="Protecting my home early matters.",
        ),
        CheckedReflection(
            outcome="dropped",
            final_problems=[LessonProblem(reason, f"{reason} test drop")],
            error="checker failed" if reason == "checker_error" else "",
        ),
        CheckedReflection(
            outcome="stored", insight=SimpleNamespace(importance=0.7),
            lesson="Protecting my home early matters.",
        ),
    ])
    monkeypatch.setattr(rf, "run_checked_reflection", lambda *args, **kwargs: next(results))

    _add_realistic_year(memory, records, 4, 5)
    _reflect(hook, 4)
    year_4_reflection = memory._reflections["A"][0]
    _add_realistic_year(memory, records, 5, 3)
    _reflect(hook, 5)
    assert memory._reflections["A"] == [year_4_reflection]
    _add_realistic_year(memory, records, 6, 4)
    _reflect(hook, 6)

    assert [line.split(":", 1)[0] for line in captured["calls"][-1]["facts"]] == [
        "Year 4", "Year 6"]


def test_previous_fact_years_are_ignored_when_program_facts_are_off(tmp_path, monkeypatch):
    records = _records({4})
    rf, hook, memory, _agent, captured = _reflection_harness(
        tmp_path, monkeypatch, records)
    memory.add_memory(
        "A", "Consolidated Reflection (written in Year 5): "
        f"{fact_line(FloodYear(4, True, True, False, False, records[4]['event_line']))} "
        "Lesson: Protecting my home early matters.", {"type": "reflection"})
    _add_realistic_year(memory, records, 6, 4)
    monkeypatch.setattr(
        rf, "_remembered_reflection_years",
        lambda _lines: pytest.fail("previous facts must not be parsed when program_facts is off"),
    )

    hook._grounded_reflection(
        6,
        {"batch_size": 1, "questions": []},
        {"year_outcome": True, "year_lines": True,
         "program_facts": False, "lesson_no_numbers": True},
    )

    call = captured["calls"][-1]
    assert [item["year"] for item in call["candidates"][0]["memories"]] == [6]
    assert call["facts"] is None


def test_relocated_household_is_skipped_by_grounded_reflection(tmp_path, monkeypatch):
    records = _records({4})
    _rf, hook, memory, agent, captured = _reflection_harness(
        tmp_path, monkeypatch, records)
    agent.relocated = True
    _add_realistic_year(memory, records, 4, 5)

    _reflect(hook, 4)

    assert captured["calls"] == []


def test_reflection_on_window_four_fails_before_llm(tmp_path, monkeypatch):
    import examples.single_agent.run_flood as rf

    llm_calls = []
    monkeypatch.setattr(rf, "create_llm_invoke", lambda *args, **kwargs: llm_calls.append(1))
    with pytest.raises(ValueError, match="at least 5"):
        rf.run_parity_benchmark(
            model="mock", years=1, agents_count=1, custom_output=str(tmp_path / "out"),
            memory_engine_type="window", window_size=4,
        )
    assert llm_calls == []


def test_reflection_off_allows_window_three():
    import examples.single_agent.run_flood as rf

    rf._validate_flood_window_size("window", 3, False)


def test_goldfish_mock_runs_with_reflection_off(tmp_path):
    import examples.single_agent.run_flood as rf

    reset_state()
    out = tmp_path / "goldfish"
    rf.run_parity_benchmark(
        model="mock", years=1, agents_count=2, custom_output=str(out),
        memory_engine_type="window", window_size=5, workers=1, seed=42,
        stress_test="goldfish", config_root=str(_variant_without_reflection(tmp_path)),
    )
    assert (out / "reproducibility_manifest.json").exists()


# ===========================================================================
# end to end with the scripted mock (no Ollama)
# ===========================================================================

def _traces(out: Path):
    with (out / "raw" / "household_traces.jsonl").open(encoding="utf-8") as f:
        return [json.loads(line) for line in f.readlines()[1:]]


def _memory_items(prompt: str):
    block = prompt[prompt.index("Your memory includes:\n") + len("Your memory includes:\n"):
                   prompt.index("\n\nYou currently")]
    return [line[2:] for line in block.splitlines()]


@pytest.fixture(scope="module")
def reflecting_run(tmp_path_factory):
    random.seed(42)  # run_flood seeds random only in its CLI main
    reset_state()
    out = tmp_path_factory.mktemp("flood_item7") / "run"
    run_scripted_mock(governance_mode="strict", output=str(out), agents=12, years=6, seed=42)
    return out


def test_reflection_is_last_in_the_at_most_five_plus_two_plus_one_prompt(reflecting_run):
    rows = [json.loads(line) for line in
            (reflecting_run / "reflection_checks.jsonl").read_text(encoding="utf-8").splitlines()]
    stored_lessons = {(row["agent_id"], row["period"]): row["lesson"] for row in rows
                      if row["outcome"] in {"stored", "stored_after_retry"} and not row["problems"]}
    seen = 0
    for rec in _traces(reflecting_run):
        items = _memory_items(rec["input"])
        reflections = [i for i, m in enumerate(items) if m.startswith("Consolidated Reflection")]
        if rec["year"] == 1:
            assert reflections == []
            continue
        if not reflections:
            continue  # this household's last reflection was not stored
        seen += 1
        assert reflections == [len(items) - 1], items
        assert 5 <= len(items) - 1 <= 7, items
        line = items[-1]
        assert line.startswith(f"Consolidated Reflection (written in Year {rec['year'] - 1}): Year ")
        assert line.endswith(" Lesson: " + stored_lessons[(rec["agent_id"], rec["year"] - 1)])
    assert seen > 0


def test_counts_in_the_manifest_and_the_check_log(reflecting_run):
    manifest = json.loads((reflecting_run / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    assert manifest["flood_memory_options"] == {
        "engine_type": "HumanCentricMemoryEngine",
        "window_size": 5,
        "top_k_significant": 2,
        "reflection_slot": "separate",
        "importance_by_event_type": {
            "own_damage": 1.0,
            "flood_without_own_damage": 0.8,
            "dry": 0.2,
            "grant": 0.2,
            "neighbour_observation": 0.2,
            "random_recall": 0.2,
        },
    }
    checks = manifest["reflection_checks"]
    assert checks["settings"]["year_outcome"] is True and checks["settings"]["retries"] == 1
    totals = checks["totals"]
    assert totals["stored_after_retry"] > 0 and totals["dropped"] == 0 and totals["stored"] > 0
    assert set(checks["per_period"]) == {"1", "2", "3", "4", "5", "6"}
    assert sum(checks["flagged_by_reason"].values()) > 0
    assert any(period["flagged_by_reason"] for period in checks["per_period"].values())
    rows = [json.loads(l) for l in (reflecting_run / "reflection_checks.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {r["outcome"] for r in rows} == {"stored", "stored_after_retry"}
    assert len(rows) == totals["stored_total"] + totals["retried"]
    assert any(
        any(flag["code"] in {"every_year_flood_claim", "no_damage_claim"}
            for flag in r["flags"])
        for r in rows
    )


def test_reflecting_run_integrity_expects_reflection(reflecting_run):
    integrity = json.loads((reflecting_run / "run_integrity.json").read_text(encoding="utf-8"))
    assert integrity["reflection_expected"] is True
    assert integrity["effective_memory_engine_type"] == "humancentric"


def test_scripted_year_5_reflection_carries_year_3_or_4_damage(reflecting_run):
    year_6_reflections = []
    for rec in _traces(reflecting_run):
        if rec["year"] != 6:
            continue
        year_6_reflections.extend(
            item for item in _memory_items(rec["input"])
            if item.startswith("Consolidated Reflection (written in Year 5):")
        )

    assert any(
        re.search(r"Year [34]: a flood damaged my house;", reflection.split(" Lesson: ", 1)[0])
        for reflection in year_6_reflections
    ), year_6_reflections


def _variant_without_reflection(tmp_path: Path) -> Path:
    """An isolated --config-root: the base flood config with the whole
    item-7 reflection block reverted to the c7b10c05 one."""
    root = tmp_path / "noreflect"
    root.mkdir()
    for name in ("agent_initial_profiles.csv", "flood_years.csv", "skill_registry.yaml"):
        shutil.copy(SA / name, root / name)
    (root / "config" / "prompts").mkdir(parents=True)
    shutil.copy(SA / "config" / "prompts" / "household.txt", root / "config" / "prompts" / "household.txt")
    raw = (SA / "agent_types.yaml").read_text(encoding="utf-8")
    start = raw.index("  reflection:\n")
    end = raw.index("    triggers:\n", start)
    old_block = ("  reflection:\n"
                 "    interval: 1               # Reflect every N years\n"
                 "    batch_size: 10            # Reduced from 25 to avoid LLM output truncation\n"
                 "    importance_boost: 0.9     # Boost emotional weight for reflected memories\n"
                 "    questions:\n"
                 "      - \"What risks feel most urgent to your family right now?\"\n"
                 "      - \"Have your neighbors' choices influenced your thinking?\"\n"
                 "      - \"What trade-offs have you faced between cost and safety?\"\n")
    (root / "agent_types.yaml").write_text(raw[:start] + old_block + raw[end:], encoding="utf-8")
    cfg = yaml.safe_load((root / "agent_types.yaml").read_text(encoding="utf-8"))
    assert "enabled" not in cfg["global_config"]["reflection"]
    cfg["global_config"]["memory"].pop("event_memory_5_2_1", None)
    (root / "agent_types.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return root


def test_reflection_off_leaves_the_window_memory_as_before(tmp_path):
    reset_state()
    out = tmp_path / "off"
    run_scripted_mock(governance_mode="strict", output=str(out), agents=5, years=3, seed=42,
                      config_root=str(_variant_without_reflection(tmp_path)))
    for rec in _traces(out):
        assert "Consolidated Reflection" not in rec["input"]
        assert len(_memory_items(rec["input"])) <= 5
    assert not (out / "reflection_log.jsonl").exists() or not (out / "reflection_log.jsonl").read_text().strip()
    manifest = json.loads((out / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    assert "reflection_checks" not in manifest
    assert manifest["flood_memory_options"] == {
        "engine_type": "WindowMemoryEngine",
        "window_size": 5,
        "top_k_significant": None,
        "reflection_slot": None,
        "importance_by_event_type": None,
    }
