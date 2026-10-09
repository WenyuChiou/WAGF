"""Irrigation v3 spec item 45: grounded year-end reflection and the memory,
option and dashboard wording that goes with it.

Spec: .research/design_specs/irrigation_v3_spec_2026-09-28.md item 45 (a)-(j);
the checks reuse the reflection error diagnosis's regular expressions
(irrigation_v3_reflection_error_diagnosis_2026-10-07.md section 4).

- (a) the reflection written at the end of a year sees that year's own
  outcome line, the exact line the next decision prompt shows;
- (b) one line per year, oldest first;
- (c) the program writes the key years (the year just ended and the listed
  year with the largest shortfall) and stores them before "Lesson: ";
- (e) semantic contradictions are measured as flags, with known false
  positives for pilot hand audit. Only enabled numbers, junk, overlong
  lessons and foreign figures retry once then drop; every attempt is logged
  and stored flags are counted per year in the manifest;
- (f) the Upper Basin memory line states the sub-basin natural-flow share;
- (g) a keep after a short year states the fall in the request;
- (h) the reflection prompt carries the allocation rules, in the decision
  prompt's words;
- (i) the floor note (the "received (AF)" column is pinned in test_v3_prompt).

Every test here fails on c7b10c05 (the module, options and wording did not
exist).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
import yaml

from broker.utils.llm_utils import LLMStats
from examples.irrigation_abm.irrigation_personas import (
    ALLOCATION_RULES,
    FLOOR_NO_DECREASE_NOTE,
    INCREASE_STEP_NOTE,
    build_action_outcome_feedback,
    build_option_notes,
    describe_gap_reason,
    reflection_rule_lines,
)
from examples.irrigation_abm.reflection_checks import (
    OutcomeLine,
    check_lesson,
    fact_line,
    key_years,
    line_year,
    parse_outcome_line,
)
from examples.irrigation_abm.tests.test_v3_prompt import CONFIG, ScriptedLLM, _run

UBS_PAST = describe_gap_reason({"gap_reason": "ub_subbasin_supply", "ub_subbasin_member_count": 11}, "past")
TIER_PAST = describe_gap_reason({
    "gap_reason": "lb_junior_tier_cut",
    "lb_junior_ceiling_af": 74_680.0,
    "lb_junior_entitlement_af": 100_000.0,
}, "past")

# The cbb74f73 pilot's line format (diagnosis section 3, C1: strict,
# AgAboveRandlette_NonIndian, written in 2027), verbatim apart from the reason.
PILOT_C1 = [
    ("Year 2020: You chose to maintain demand. You requested 182,869 acre-ft and received 162,401 acre-ft. "
     f"Shortfall: 20,468 acre-ft (11.2% unmet), {UBS_PAST}. That winter's precipitation in your sub-basin "
     "was below the previous winter's."),
    ("Year 2023: You chose to maintain demand. You requested 162,401 acre-ft and received 152,372 acre-ft. "
     f"Shortfall: 10,029 acre-ft (6.2% unmet), {UBS_PAST}. That winter's precipitation in your sub-basin "
     "was above the previous winter's."),
    ("Year 2024: You chose to maintain demand. You requested 152,372 acre-ft and received 152,372 acre-ft. "
     "Demand fully met. That winter's precipitation in your sub-basin was below the previous winter's."),
    ("Year 2025: You chose to maintain demand. You requested 152,372 acre-ft and received 152,372 acre-ft. "
     "Demand fully met. That winter's precipitation in your sub-basin was below the previous winter's."),
    ("Year 2026: You chose to increase demand (by 6%). You requested 161,870 acre-ft and received 161,870 "
     "acre-ft. Demand fully met. That winter's precipitation in your sub-basin was above the previous winter's."),
]
LB_MEAD = [  # diagnosis C3 (strict, CRIR CA, written in 2033)
    (f"Year {y}: You chose to maintain demand. You requested 1,853 acre-ft and received 1,853 acre-ft. "
     f"Demand fully met. On 1 January that year Lake Mead was {d} than a year earlier.")
    for y, d in ((2029, "higher"), (2030, "higher"), (2031, "higher"), (2032, "lower"))
]


def _lines(texts) -> List[OutcomeLine]:
    return [parse_outcome_line(t) for t in texts]


# ===========================================================================
# reading the agent's own lines
# ===========================================================================

def test_parse_reads_the_pilot_format():
    first, second, third, _, last = _lines(PILOT_C1)
    assert (first.year, first.direction, first.request, first.received) == (2020, "keep", 182_869, 162_401)
    assert first.short and first.unmet_pct == 11.2 and first.precip == "below" and first.mead is None
    assert not third.short and third.unmet_pct == 0.0
    assert last.direction == "increase" and last.precip == "above"
    assert parse_outcome_line("Consolidated Reflection (written in 2027): I learned.") is None
    assert line_year("Year 2031: x") == 2031 and line_year("I learned.") is None


def test_parse_reads_the_item_45_format():
    keep = build_action_outcome_feedback(
        {"skill_name": "maintain_demand"}, 2021, 23_766.0, 20_155.0, 0, basin="lower_basin",
        gap_reason=TIER_PAST, previous_request=28_295.0, previous_diversion=23_766.0)
    applied = build_action_outcome_feedback(
        {"skill_name": "maintain_demand", "was_fallback": True, "proposed_skill": "increase_demand",
         "blocking_rules": ["high_scarcity_no_increase"]}, 2022, 50_000.0, 50_000.0, 1,
        basin="upper_basin", rejection_line_style="neutral", flow_share=0.93)
    none = build_action_outcome_feedback(None, 2023, 1_000.0, 900.0, 0, basin="lower_basin",
                                         gap_reason=describe_gap_reason({"gap_reason": "lb_mead_availability"}, "past"),
                                         decision_read=False, previous_request=1_200.0, previous_diversion=1_000.0)
    for text, year, direction, short in ((keep, 2021, "keep", True), (applied, 2022, "keep", False),
                                         (none, 2023, "keep", True)):
        line = parse_outcome_line(text)
        assert (line.year, line.direction, line.short) == (year, direction, short), text


# ===========================================================================
# (c) key years and fact lines
# ===========================================================================

def test_key_years_are_the_last_year_and_the_largest_shortfall():
    lines = _lines(PILOT_C1)
    assert key_years(lines, 2026) == [2020, 2026]  # 11.2% unmet in 2020 is the largest
    assert key_years(lines[2:], 2026) == [2026]     # no shortfall listed
    assert key_years(lines, 2020) == [2020]         # the largest shortfall is the year just ended
    tie = _lines([PILOT_C1[0], PILOT_C1[0].replace("Year 2020", "Year 2022")])
    assert key_years(tie, 2022) == [2022]           # ties: the most recent
    with pytest.raises(ValueError, match="not among"):
        key_years(lines, 2030)


def test_fact_lines_state_direction_request_receipt_and_unmet_share():
    first, _, third, _, last = _lines(PILOT_C1)
    assert fact_line(first) == ("2020: you asked for 182,869 acre-ft and you received "
                                "162,401 acre-ft (11.2% unmet).")
    assert fact_line(last, previous_received=152_372) == (
        "2026: you asked for 161,870 acre-ft, an increase over the 152,372 acre-ft you received "
        "the year before, and you received 161,870 acre-ft (fully met).")
    dec = OutcomeLine(2030, "decrease", 900, 900, False, 0.0, None, "lower", "")
    assert fact_line(dec, previous_received=1_000) == (
        "2030: you asked for 900 acre-ft, a decrease from the 1,000 acre-ft you received the year before, "
        "and you received 900 acre-ft (fully met).")


def test_fact_line_compares_the_request_with_the_previous_receipt():
    previous = OutcomeLine(2020, "keep", 28_295, 23_766, True, 16.0, None, "lower", "")
    line = OutcomeLine(2021, "increase", 25_000, 25_000, False, 0.0, None, "lower", "")
    assert line.request < previous.request
    assert fact_line(line, previous_received=previous.received) == (
        "2021: you asked for 25,000 acre-ft, an increase over the 23,766 acre-ft you received "
        "the year before, and you received 25,000 acre-ft (fully met).")


# ===========================================================================
# (e) the irrigation checks (diagnosis section 4)
# ===========================================================================

@pytest.mark.parametrize("lesson,lines,codes", [
    # diagnosis S3 #14 (G): a "below means short" rule; 2024 is below and fully met
    ("I realized that maintaining demand consistently leads to unmet water needs when precipitation is "
     "below average, as demonstrated in 2020 and 2024.", PILOT_C1, ["precipitation_rule"]),
    # the same rule where no listed below year was fully met: no counterexample
    ("When precipitation is lower than the previous winter, my demand is not met.",
     [PILOT_C1[0], PILOT_C1[1]], []),
    # "despite" negates the rule (the diagnosis's NEGATE)
    ("Despite lower precipitation, my demand was not met in one year.", PILOT_C1, ["precipitation_rule"]),
    ("I learned that lower river flow, not lower precipitation, is what causes my shortfalls.", PILOT_C1, ["precipitation_rule"]),
    ("Lower precipitation alone did not cause a shortfall.", PILOT_C1, ["precipitation_rule"]),
    ("A dry winter does not always lead to a shortfall.", PILOT_C1, ["always_short"]),
    ("My demand was consistently met until the flow dropped.", PILOT_C1, ["always_full"]),
    ("My demand hasn't always been fully met.", PILOT_C1, ["always_full"]),
    ("My demand was never consistently fully met.", PILOT_C1, ["always_full"]),
    # higher precipitation goes with full delivery, but 2023 was above and short
    # (and, being unconditional, an "always met" claim a listed shortfall contradicts)
    ("Higher precipitation always meant my demand was fully met.", PILOT_C1,
     ["precipitation_rule", "always_full"]),
    # an unconditional "always met" with a listed shortfall
    ("My demand was consistently fully met.", PILOT_C1, ["always_full"]),
    # an unconditional "always short" when most listed years were fully met
    ("My demand consistently fell short.", PILOT_C1, ["always_short"]),
    # conditional persistence is not checked
    ("My demand was consistently met only when I kept my request.", PILOT_C1, []),
    # diagnosis S6 #15: Lake Mead "consistently rose", 2032 lower
    ("I noticed that Lake Mead levels consistently rose.", LB_MEAD, ["mead_direction"]),
    ("Lake Mead levels consistently declined.", LB_MEAD, ["mead_direction"]),
    # the offline replay's one Lake Mead false alarm: "water" alone is not the lake
    ("Consistently increasing my water demand requests kept my demand met.", LB_MEAD, []),
    # safety net: an amount of water, and a figure foreign to the record
    ("Asking for about 150,000 acre-ft kept me safe.", PILOT_C1, []),
    ("Asking for 99,999 acre-ft would have been safer.", PILOT_C1, ["foreign_figure"]),
    # a clean lesson
    ("I learned that keeping my request steady protects me when supply is short.", PILOT_C1, []),
])
def test_check_lesson(lesson, lines, codes):
    parsed = _lines(lines)
    assert [p.code for p in check_lesson(lesson, parsed, " ".join(lines))] == codes


@pytest.mark.parametrize(("lesson", "codes"), [
    ("Maintaining demand works when river flow and precipitation are favorable.", []),
    ("Maintaining demand works when river flow and precipitation are favorable, but my request was unmet.", []),
    ("Lower precipitation causes my shortfalls.", ["precipitation_rule"]),
    ("Lowest precipitation causes my shortfalls.", ["precipitation_rule"]),
    ("Lowered precipitation causes my shortfalls.", ["precipitation_rule"]),
    ("Lessened precipitation causes my shortfalls.", ["precipitation_rule"]),
    ("Lesser precipitation causes my shortfalls.", ["precipitation_rule"]),
    ("Poorer precipitation causes my shortfalls.", ["precipitation_rule"]),
    ("Scarcer precipitation causes my shortfalls.", ["precipitation_rule"]),
    ("Highest precipitation meant my demand was fully met.", ["precipitation_rule"]),
    ("Wettest precipitation meant my demand was fully met.", ["precipitation_rule"]),
    ("Stronger precipitation meant my demand was fully met.", ["precipitation_rule"]),
    ("Unfavorable precipitation always meant my demand was fully met.", ["always_full"]),
    ("Higher precipitation left my demand fully methodical.", []),
    ("Lower precipitation left me unmeticulous.", []),
    ("My demand was consistently unmeticulous.", []),
    ("My demand was consistently fully methodical.", []),
    ("My demand was alwaysmore fully met.", []),
    ("My demand was met every yearly cycle.", []),
    ("My demand was met every year.", ["always_full"]),
    ("My demand was consistently fully met particularlygood.", ["always_full"]),
    ("My demand was consistently fully met, particularly when flow was high.", []),
    ("My demand was always fully met, with the exception of one dry year.", []),
    ("My demand was always fully met, even without high river flow.", []),
    ("My demand was inconsistently fully met.", []),
    ("My demand was discontinued after being fully met.", []),
    ("Lower precipitation gave me a shortcut to planning.", []),
    ("Lake Mead levels consistently rosemary.", []),
    ("Lake Mead levels consistently rose.", ["mead_direction"]),
    ("Snowlake levels consistently rose.", []),
    ("I saw consistently rising lakefront demand.", []),
    ("I saw consistently rising lake levels.", ["mead_direction"]),
    ("I saw consistently declining reservoirs.", ["mead_direction"]),
    ("I saw consistently falling lakes.", ["mead_direction"]),
    ("Water levels consistently lowered.", ["mead_direction"]),
    ("Lake Mead levels rose every yearly cycle.", []),
    ("Lake Mead levels rose every year.", ["mead_direction"]),
    ("Lower precipitation left less than I requested.", ["precipitation_rule"]),
    ("My demand consistently reduced my deliveries.", ["always_short"]),
    ("My demand consistently reduced my allocations.", ["always_short"]),
    ("Lower precipitation caused reductions in my allocations.", ["precipitation_rule"]),
    ("My demand consistently met my requests.", ["always_full"]),
    ("My demand consistently met my demands.", ["always_full"]),
    ("My demand consistently met my needs.", ["always_full"]),
    ("I consistently received exactly my demand.", ["always_full"]),
    ("My demand consistently received full allocations.", ["always_full"]),
    ("I consistently received full demands.", ["always_full"]),
    ("I consistently received fully what I requested.", ["always_full"]),
])
def test_semantic_patterns_match_whole_words_and_preserve_intentional_stems(lesson, codes):
    texts = LB_MEAD if any(
        word in lesson.lower() for word in ("mead", "lake", "reservoir", "water levels")
    ) else PILOT_C1
    parsed = _lines(texts)
    assert [p.code for p in check_lesson(lesson, parsed, " ".join(texts))] == codes


@pytest.mark.parametrize("lesson", [
    "Lower precipitation means my demand is not fully met.",
    "Lower precipitation always causes a shortfall because no water is available.",
])
def test_outcome_negation_does_not_hide_a_false_precipitation_rule(lesson):
    problems = check_lesson(lesson, _lines(PILOT_C1), " ".join(PILOT_C1))
    assert "precipitation_rule" in [problem.code for problem in problems]


# ===========================================================================
# (f), (g) memory lines; (i) the floor note; (h) the allocation rules
# ===========================================================================

def test_upper_basin_memory_line_states_the_flow_share():
    ub = build_action_outcome_feedback({"skill_name": "maintain_demand"}, 2031, 100.0, 100.0, 0,
                                       basin="upper_basin", flow_share=0.736)
    assert ub.endswith("That winter's precipitation in your sub-basin was below the previous winter's. "
                       "The natural flow of the rivers your sub-basin draws on was 74% of its 1971-2018 "
                       "average that year.")
    # a synthetic agent without a sub-basin, and the Lower Basin: no flow sentence
    for line in (build_action_outcome_feedback(None, 2031, 100.0, 100.0, 0, basin="upper_basin",
                                               subbasin=False, flow_share=0.7),
                 build_action_outcome_feedback(None, 2031, 100.0, 100.0, 0, basin="lower_basin",
                                               flow_share=0.7)):
        assert "natural flow" not in line


def test_keep_after_a_short_year_states_the_fall_in_the_request():
    clause = ", so your request fell from 3,051 acre-ft to the 2,278 acre-ft you received the year before."
    common = dict(year=2023, request=2_278.0, diversion=1_572.0, preceding_factor=0, basin="lower_basin",
                  gap_reason=TIER_PAST, previous_request=3_051.0, previous_diversion=2_278.0)
    chose = build_action_outcome_feedback({"skill_name": "maintain_demand"}, **common)
    assert chose.startswith("Year 2023: You chose to maintain demand" + clause + " You requested 2,278")
    applied = build_action_outcome_feedback(
        {"skill_name": "maintain_demand", "was_fallback": True, "proposed_skill": "increase_demand",
         "blocking_rules": ["supply_gap_block_increase"]}, rejection_line_style="neutral", **common)
    assert applied.startswith("Year 2023: maintain demand was applied under the shortage-sharing rule" + clause)
    none = build_action_outcome_feedback(None, decision_read=False, **common)
    assert none.startswith("Year 2023: no valid decision was read" + clause + " You requested 2,278")
    # after a full year, or with no year before, the line reads as before
    full = dict(common, previous_request=2_278.0, previous_diversion=2_278.0)
    assert build_action_outcome_feedback({"skill_name": "maintain_demand"}, **full).startswith(
        "Year 2023: You chose to maintain demand. You requested")
    assert build_action_outcome_feedback(None, decision_read=False, **dict(common, previous_request=None)).startswith(
        "Year 2023: no valid decision was read; your request stayed at the amount you received the year before.")
    # an increase or a decrease never carries the clause, whatever its numbers
    inc = build_action_outcome_feedback({"skill_name": "increase_demand", "magnitude_pct": 8.0},
                                        **dict(common, request=2_460.0))
    assert inc.startswith("Year 2023: You chose to increase demand (by 8%). You requested 2,460")
    # a keep whose request is not last year's receipt would state something false
    with pytest.raises(ValueError, match="refusing"):
        build_action_outcome_feedback({"skill_name": "maintain_demand"}, **dict(common, request=2_500.0))


def test_floor_note_says_why_no_decrease_is_offered():
    nl = chr(10)
    note = FLOOR_NO_DECREASE_NOTE.format(floor=4_000.0, share=0.1)
    assert note == ("A decrease is not offered because your request is at or below the minimum-use floor of "
                    "4,000 acre-ft (10% of your water right).")
    assert build_option_notes(True, False, None, floor_af=4_000.0, floor_share=0.1) == nl + INCREASE_STEP_NOTE + nl + note
    assert build_option_notes(True, True, None, floor_af=4_000.0, floor_share=0.1) == nl + (
        "The exact size of an increase or a decrease is drawn at random around your typical step.")
    with pytest.raises(ValueError, match="floor_share"):
        build_option_notes(True, False, None, floor_af=4_000.0)


def test_reflection_rules_are_the_decision_prompt_words():
    """Item 45h: each allocation rule the reflection prompt carries is
    word for word in the decision prompt's dashboard warning that states it."""
    raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    messages = [" ".join(a["message"].split()) for a in raw["irrigation_farmer"]["feedback"]["assertions"]]
    for key, rules in ALLOCATION_RULES.items():
        for rule in rules:
            assert any(rule in m for m in messages), (key, rule)


@pytest.mark.parametrize("ctx,key", [
    ({"basin": "lower_basin", "lb_junior_entitlement_af": 1_000.0, "ub_supply_mode": "subbasin"}, "lower_basin_junior"),
    ({"basin": "lower_basin", "lb_junior_entitlement_af": 0.0, "ub_supply_mode": "subbasin"}, "lower_basin"),
    ({"basin": "lower_basin", "lb_junior_entitlement_af": None, "ub_supply_mode": "subbasin"}, "lower_basin"),
    ({"basin": "upper_basin", "supply_group": "UT1", "ub_subbasin_member_count": 11,
      "ub_supply_mode": "subbasin"}, "subbasin"),
    ({"basin": "upper_basin", "supply_group": "UT2", "ub_subbasin_member_count": 1,
      "ub_supply_mode": "subbasin"}, "alone"),
    ({"basin": "upper_basin", "supply_group": None, "ub_supply_mode": "subbasin"}, "upper_basin"),
])
def test_reflection_rule_lines_pick_the_agents_rules(ctx, key):
    assert reflection_rule_lines(ctx) == list(ALLOCATION_RULES[key])


def test_junior_reflection_rules_are_tenseless_and_use_the_tier_ceiling():
    """Round-2 P1-1/P2-1: these rules appear in tier and Tier 0 years, so
    the tier rule is conditional and the physical-shortage rule preserves
    the full opportunity-cost clause for requests capped by the ceiling.
    """
    rules = reflection_rule_lines({
        "basin": "lower_basin",
        "lb_junior_entitlement_af": 1_000.0,
        "ub_supply_mode": "subbasin",
    })
    assert rules[0].startswith("In a year with a declared shortage tier")
    assert "this year" not in rules[0]
    assert "that year" in rules[0]
    assert "tier ceiling" in rules[0]
    assert "total limit" not in rules[0]
    assert "shared in proportion to requests capped by the tier ceiling" in rules[1]
    assert "would raise your share only by lowering the deliveries of other users" in rules[1]
    assert "would not add water to the Lower Basin" in rules[1]


def test_reflection_rule_lines_refuse_to_guess():
    with pytest.raises(ValueError, match="ub_supply_mode"):
        reflection_rule_lines({"basin": "upper_basin", "supply_group": None,
                               "ub_supply_mode": "lees_ferry_pool"})
    with pytest.raises(ValueError, match="lb_junior_entitlement_af"):
        reflection_rule_lines({"basin": "lower_basin", "ub_supply_mode": "subbasin"})
    with pytest.raises(ValueError, match="member_count"):
        reflection_rule_lines({"basin": "upper_basin", "supply_group": "UT1",
                               "ub_supply_mode": "subbasin"})


# ===========================================================================
# end to end: a synthetic strict run with scripted reflections
# ===========================================================================

class _ReflectingLLM(ScriptedLLM):
    """Keeps every decision; reflection replies by agent: Agent_000 names a
    year at the first attempt and is clean on the retry; Agent_001 is clean;
    Agent_002 always quotes a number (dropped after the retry)."""

    CLEAN = "I learned to keep my request close to what I received."

    def __init__(self, script):
        super().__init__(script)
        self.reflection_calls: List[Dict[str, Any]] = []

    def __call__(self, prompt: str):
        if "You are a Reflection Assistant" not in prompt:
            return super().__call__(prompt)
        aid = re.search(r"^(.+?) Memories:", prompt, flags=re.M).group(1)
        year = int(re.search(r"\(Year (\d{4})\)", prompt).group(1))
        retry = "### Correction" in prompt
        with self._lock:
            self.reflection_calls.append({"agent": aid, "year": year, "retry": retry, "prompt": prompt})
        if aid == "Agent_000":
            lesson = self.CLEAN if retry else f"In {year} I learned to wait."
        elif aid == "Agent_002":
            lesson = "Asking for 5 percent more was too much."
        else:
            lesson = self.CLEAN
        return json.dumps({aid: lesson}), LLMStats(retries=0, success=True)


@pytest.fixture(scope="module")
def reflecting_run(tmp_path_factory):
    llm = _ReflectingLLM(lambda agent, year, attempt: ("M", "M", "Keep"))
    with pytest.MonkeyPatch.context() as mp:
        out = _run(mp, tmp_path_factory.mktemp("item45") / "run", llm,
                   "--agents", "3", "--years", "3", "--seed", "7")
    return SimpleNamespace(llm=llm, out=out)


def _memory_lines(prompt: str) -> List[str]:
    block = prompt[prompt.index("Your memory includes:"):prompt.index("First, assess")]
    return [line[2:] for line in block.splitlines() if line.startswith("- ")]


def test_year_end_reflection_sees_the_years_own_outcome_line(reflecting_run):
    """(a) and (b): the reflection written at the end of Y lists Y's line
    last, the same text the Y+1 decision prompt shows; lines in year order."""
    llm = reflecting_run.llm
    firsts = [c for c in llm.reflection_calls if not c["retry"]]
    assert {(c["agent"], c["year"]) for c in firsts} == {(f"Agent_00{i}", y) for i in range(3) for y in (2019, 2020, 2021)}
    for c in firsts:
        listed = re.findall(r"^- (Year \d{4}: .*)$", c["prompt"], flags=re.M)
        years = [line_year(line) for line in listed]
        assert years == sorted(years) and years[-1] == c["year"], (c["agent"], c["year"], years)
        nxt = llm.decisions.get((c["agent"], c["year"] + 1, 0))
        if nxt is not None:
            assert listed[-1] in _memory_lines(nxt)


def test_reflection_prompt_carries_record_rules_and_the_lesson_only_line(reflecting_run):
    c = next(c for c in reflecting_run.llm.reflection_calls if c["agent"] == "Agent_001" and c["year"] == 2021)
    p = c["prompt"]
    assert "Rules that apply to Agent_001:" in p
    assert "### Record (written by the simulation and stored with your lesson; do not restate it)" in p
    assert "Agent_001 Record:\n- 2021: " in p
    assert p.endswith("Do not write any year, amount, percentage or other number; the record above is "
                      "stored with your lesson.")
    assert "average" in p and "Lesson Learned" not in p  # item 45d: "never call ... above or below average"


def test_lessons_are_checked_retried_once_and_counted(reflecting_run):
    llm, out = reflecting_run.llm, reflecting_run.out
    retries = [c for c in llm.reflection_calls if c["retry"]]
    assert {c["agent"] for c in retries} == {"Agent_000", "Agent_002"}
    assert all("Your previous answer could not be stored because it names a year" in c["prompt"]
               for c in retries if c["agent"] == "Agent_000")
    # the stored line: program facts, then the lesson; Agent_002 stores none
    for agent, stored in (("Agent_000", True), ("Agent_001", True), ("Agent_002", False)):
        lines = [l for l in _memory_lines(llm.decisions[(agent, 2021, 0)]) if l.startswith("Consolidated")]
        if not stored:
            assert lines == []
            continue
        assert len(lines) == 1
        head, lesson = lines[0].split(" Lesson: ")
        assert head.startswith("Consolidated Reflection (written in 2020): 2020: ")
        assert lesson == _ReflectingLLM.CLEAN
    manifest = json.loads((out / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    checks = manifest["reflection_checks"]
    assert manifest["run_integrity"]["reflection_expected"] is True
    assert checks["settings"]["program_facts"] is True and checks["settings"]["retries"] == 1
    for year in ("2019", "2020", "2021"):
        c = checks["per_period"][year]
        assert (c["stored"], c["stored_after_retry"], c["dropped"]) == (1, 1, 1), (year, c)
        # Agent_000's year; Agent_002's number, a share not in its record
        assert c["first_attempt_problems"] == {"foreign_figure": 1, "number": 1, "year": 1}
    rows = [json.loads(l) for l in (out / "reflection_checks.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {(r["agent_id"], r["outcome"]) for r in rows} == {("Agent_000", "stored_after_retry"),
                                                              ("Agent_001", "stored"),
                                                              ("Agent_002", "dropped")}
    assert all("raw_reply" in r for r in rows)


@pytest.mark.parametrize("drop_reason", ["mechanical", "no_reply", "checker_error"])
def test_dropped_reflection_keeps_previous_reflection_in_next_decision_prompt(
        tmp_path, monkeypatch, drop_reason):
    class CarryForwardLLM(_ReflectingLLM):
        def __call__(self, prompt: str):
            if "You are a Reflection Assistant" not in prompt:
                return super().__call__(prompt)
            year = int(re.search(r"\(Year (\d{4})\)", prompt).group(1))
            if year != 2020:
                return super().__call__(prompt)
            with self._lock:
                self.reflection_calls.append({
                    "agent": "Agent_000", "year": year,
                    "retry": "### Correction" in prompt, "prompt": prompt,
                })
            if drop_reason == "no_reply":
                return None
            lesson = "Trigger checker failure." if drop_reason == "checker_error" else "Asking for 5 percent more."
            return json.dumps({"Agent_000": lesson}), LLMStats(retries=0, success=True)

    if drop_reason == "checker_error":
        original_check = check_lesson

        def fail_selected_lesson(lesson, lines, own_text):
            if lesson == "Trigger checker failure.":
                raise RuntimeError("scripted checker failure")
            return original_check(lesson, lines, own_text)

        monkeypatch.setattr("examples.irrigation_abm.run_experiment.check_lesson", fail_selected_lesson)

    llm = CarryForwardLLM(lambda agent, year, attempt: ("M", "M", "Keep"))
    out = _run(monkeypatch, tmp_path / drop_reason, llm,
               "--agents", "1", "--years", "3", "--seed", "7")

    lines = _memory_lines(llm.decisions[("Agent_000", 2021, 0)])
    carried = [line for line in lines if line.startswith("Consolidated Reflection")]
    assert len(carried) == 1
    assert carried[0].startswith("Consolidated Reflection (written in 2019): ")
    assert carried[0].endswith(f" Lesson: {_ReflectingLLM.CLEAN}")

    from examples.irrigation_abm.analysis import v3_metrics as vm
    gate = vm.gate_p6([vm.load_run(out, keep_prompts=True)])
    details = next(iter(gate["details"].values()))
    assert gate["passed"] is True, gate
    assert details["carried_after_drop"] == 1
    assert details["reflections_not_from_previous_year"] == 0


@pytest.mark.parametrize("lesson,code", [
    ("Lower precipitation causes my shortfalls, but I can plan ahead for it.", "precipitation_rule"),
    ("Lower precipitation, which I can't predict, causes my shortfalls.", "precipitation_rule"),
    ("Lower precipitation never fails to cause a shortfall.", "precipitation_rule"),
    ("My demand was always fully met, but I should keep my request modest.", "always_full"),
    ("maintaining demand consistently resulted in full fulfillment of my requests, regardless of fluctuating precipitation", "always_full"),
])
def test_adversarial_semantic_claims_are_flagged_and_stored(tmp_path, lesson, code):
    from broker.components.cognitive.reflection import ReflectionEngine, run_checked_reflection
    result = run_checked_reflection(
        ReflectionEngine(), prompt="P", agent_id="A", period=2026,
        llm_call=lambda _: json.dumps({"A": lesson}), lesson_no_numbers=True,
        checker=lambda text: check_lesson(text, _lines(PILOT_C1), " ".join(PILOT_C1)),
        log_path=tmp_path / "checks.jsonl")
    assert result.outcome == "stored" and result.calls == 1
    assert code in [p.code for p in result.flags]
    row = json.loads((tmp_path / "checks.jsonl").read_text())
    assert code in [p["code"] for p in row["flags"]]


@pytest.mark.parametrize("enabled", [True, False])
def test_grounded_startup_requires_subbasin_before_profile_setup(tmp_path, monkeypatch, enabled):
    import shutil
    import sys
    from examples.irrigation_abm import run_experiment as runner
    cfg = tmp_path / "config"
    shutil.copytree(CONFIG.parent, cfg)
    raw = yaml.safe_load((cfg / "agent_types.yaml").read_text(encoding="utf-8"))
    if not enabled:
        for key in ("year_outcome", "year_lines", "program_facts", "lesson_no_numbers"):
            raw["global_config"]["reflection"][key] = False
    (cfg / "agent_types.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    original = runner.WaterSystemConfig
    monkeypatch.setattr(runner, "WaterSystemConfig", lambda **kwargs:
                        original(**kwargs, ub_supply_mode="lees_ferry_pool"))
    def stop_profiles(*args):
        raise RuntimeError("profile setup reached")
    monkeypatch.setattr(runner, "_create_synthetic_profiles", stop_profiles)
    monkeypatch.setattr(sys, "argv", ["run_experiment.py", "--model", "mock", "--seed", "42",
                        "--output", str(tmp_path / "out"), "--config-dir", str(cfg)])
    if enabled:
        with pytest.raises(SystemExit, match="Grounded reflection requires ub_supply_mode"):
            runner.main()
    else:
        with pytest.raises(RuntimeError, match="profile setup reached"):
            runner.main()
