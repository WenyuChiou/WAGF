"""Flood reflection grounding: the household's own year record, the key years
the program writes, and the report-only semantic flags measured on a lesson.

Flood design record (``.research/design_specs/flood_design_record_2026-09-29.md``),
PI decision 2026-10-07 item 7: reflection is ON for the WRR26 rerun, with the
same checks and storage as irrigation. Flood's current 5 + 2 + 1 design also
reads its previous reflection's program facts (design record item 8), preserving
key years beyond the recent and significant event slots.
The reflection written at the end of a year sees that year's own outcome; its
input lists one line per year, oldest first; the program writes the key years
(flood years, damage, the household's own state) and the model writes only
the lesson. A year or number, junk, or an overlength reply is retried once and
then not stored; a dropped reflection keeps the previous stored one. Semantic
patterns that contradict the listed years are
report-only flags: the lesson is still stored. The stored reflection is a
high-importance memory shown after five recent and up to two significant older
event lines (``run_flood.DecisionFilteredMemoryEngine``). Its program-written
facts may name years also present in those significant lines. This WAGF
addition is listed in the runbook's difference table.

Key years (a stated assumption, the flood form of irrigation's
``reflection_checks.key_years``): among years remembered through either an
exact flood-event line in the retrieved decision window or the previous stored
reflection's program facts, the year just ended, plus the most recent year in
which the house was damaged when that is another year. Prior-only input uses a
regenerated ``fact_line``; window and current input uses ``year_line``. Both
come from the household's true year record, never model text. Recency
(Hertwig et al., 2004, Psychological Science 15(8): 534-539; Weber, 2006,
Climatic Change 77: 103-120) and loss salience (Baumeister et al., 2001,
Review of General Psychology 5(4): 323-370); every WRR26 flood damage is the
same $10,000, so the most recent damaged year is the largest loss's tie-break.

The word-pattern flags have known false positives. They are measurements, not
storage gates, and must be hand-audited on the new pilot.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence

from broker.components.cognitive.reflection import LessonProblem


@dataclass(frozen=True)
class FloodYear:
    """One year of a household's own record, as the household saw it."""
    year: int
    flood: bool        # a flood occurred that year
    damaged: bool      # the flood damaged the house
    elevated: bool     # at the end of that year
    insured: bool      # at the end of that year
    event_line: str    # the flood-outcome memory line the household read that year


def year_line(fy: FloodYear) -> str:
    """The reflection input line of one year: the flood-outcome memory line
    the household read, then its own state at the end of that year."""
    return (f"{fy.event_line} At the end of Year {fy.year} my house was "
            f"{'elevated' if fy.elevated else 'not elevated'} and I "
            f"{'had' if fy.insured else 'did not have'} flood insurance.")


def key_years(years: Sequence[FloodYear], latest_year: int) -> List[int]:
    """The years the program writes into a stored reflection: ``latest_year``
    and the most recent damaged remembered year when that is another year.
    ``years`` may come from retrieved event lines or a prior reflection's
    program facts. Oldest first."""
    listed = {fy.year for fy in years}
    if latest_year not in listed:
        raise ValueError(f"key_years: the year just ended ({latest_year}) is not among {sorted(listed)}.")
    picked = {latest_year}
    damaged = [fy.year for fy in years if fy.damaged]
    if damaged:
        picked.add(max(damaged))
    return sorted(picked)


def fact_line(fy: FloodYear) -> str:
    """One program-written fact: the flood outcome and the household's own
    state at the end of that year."""
    if fy.flood and fy.damaged:
        event = "a flood damaged my house"
    elif fy.flood:
        event = "a flood occurred but did not damage my house"
    else:
        event = "no flood occurred"
    return (f"Year {fy.year}: {event}; at the end of the year my house was "
            f"{'elevated' if fy.elevated else 'not elevated'} and I "
            f"{'had' if fy.insured else 'did not have'} flood insurance.")


# --- checks ---------------------------------------------------------------
# Claims about the household's whole listed record, contradicted by one listed
# year. Conditional or hypothetical sentences ("if", "would", ...) are skipped
# for the state claims, which are about the present.

_NO_FLOOD = re.compile(
    r"\bno floods? (?:has|have|had) (?:ever )?(?:occurred|happened|hit|come)\b"
    r"|\bthere (?:has|have) (?:never )?been no flood(?:s|ed|ing|waters?)?\b"
    r"|\b(?:have|has|had)? ?never (?:experienced|faced|seen|had|lived through) (?:a |any )?flood(?:s|ed|ing|waters?)?\b", re.I)
_NO_DAMAGE = re.compile(
    r"\b(?:has|have|had)? ?never (?:been )?(?:flooded|damaged)\b"
    r"|\bnever (?:suffered|had|experienced|sustained|taken) (?:any )?(?:flood )?damages?\b"
    r"|\b(?:has|have) not (?:yet )?been (?:flooded|damaged)\b"
    r"|\bI (?:have )?had no (?:flood )?damages?\b", re.I)
_FLOOD_VERB = r"(?:comes?|came|occurs?|occurred|hit(?:s|ting)?|happens?|happened|strikes?|struck)"
_EVERY_YEAR_FLOOD = re.compile(
    r"\bflood(?:s|ed|ing)? (?:" + _FLOOD_VERB + r" )?(?:every|each) (?:single )?year\b"
    r"|\b(?:every|each) (?:single )?year[\w\s,'-]{0,20}\bflood(?:s|ed|ing|waters?)?\b"
    r"|\bfloods? (?:always|constantly) " + _FLOOD_VERB + r"\b", re.I)
_ALWAYS_DAMAGE = re.compile(
    r"\b(?:every|each) flood (?:has )?(?:damaged|hit(?:s|ting)?|hurt(?:s|ing)?|harmed)\b"
    r"|\b(?:always|every time) (?:been )?damaged\b"
    r"|\bfloods? (?:always|each time|every time) (?:damaged|damages?|hit(?:s|ting)?|hurt(?:s|ing)?)\b", re.I)
_HYPOTHETICAL = re.compile(r"\b(?:if|would|could|should|might|may|unless|consider\w*|plan\w*|want\w*|need\w*)\b", re.I)
_ELEVATED_CLAIM = re.compile(
    r"\bmy (?:house|home) is (?:already |now |still )?elevated\b"
    r"|\bI (?:have )?(?:already )?elevated my (?:house|home)\b"
    r"|\bsince I elevated\b", re.I)
_NOT_ELEVATED_CLAIM = re.compile(
    r"\bmy (?:house|home) is (?:still )?not (?:yet )?elevated\b"
    r"|\bI (?:have )?(?:still )?not (?:yet )?elevated\b"
    r"|\bI have(?:n't| not) (?:yet )?elevated\b", re.I)
_INSURED_CLAIM = re.compile(
    r"\bI (?:currently |now |still )?(?:have|hold|carry) (?:a )?(?:flood )?insurance\b"
    r"|\bI am (?:currently |now |still )?insured\b", re.I)
_UNINSURED_CLAIM = re.compile(
    r"\bI (?:do not|don't|no longer) (?:have|hold|carry) (?:any )?(?:flood )?insurance\b"
    r"|\bI am (?:not|un)insured\b", re.I)


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]


def check_flood_lesson(lesson: str, years: Sequence[FloodYear]) -> List[LessonProblem]:
    """Report-only semantic flags for ``lesson``, judged against ``years``.

    ``years`` are the household's listed years in the reflection input; the
    last is the year just ended, whose state is the present. These pattern
    matches do not block storage because they have known false positives. The
    framework separately enforces the mechanical reflection checks."""
    problems: List[LessonProblem] = []
    if not years:
        return problems
    any_flood = any(fy.flood for fy in years)
    any_dry = any(not fy.flood for fy in years)
    any_damage = any(fy.damaged for fy in years)
    spared_flood = any(fy.flood and not fy.damaged for fy in years)
    now = max(years, key=lambda fy: fy.year)
    for s in _sentences(lesson):
        if _NO_FLOOD.search(s) and any_flood:
            problems.append(LessonProblem(
                "no_flood_claim", "it says no flood has occurred, but a listed year had a flood"))
        if _NO_DAMAGE.search(s) and any_damage:
            problems.append(LessonProblem(
                "no_damage_claim", "it says your house was never damaged, but a listed year had flood damage"))
        if _EVERY_YEAR_FLOOD.search(s) and any_dry:
            problems.append(LessonProblem(
                "every_year_flood_claim", "it says a flood came every year, but a listed year had no flood"))
        if _ALWAYS_DAMAGE.search(s) and spared_flood:
            problems.append(LessonProblem(
                "always_damage_claim",
                "it says every flood damaged your house, but in a listed flood year your house was not damaged"))
        if _HYPOTHETICAL.search(s):
            continue
        if _ELEVATED_CLAIM.search(s) and not now.elevated:
            problems.append(LessonProblem(
                "elevation_state", "it says your house is elevated, but at the end of this year it is not"))
        if _NOT_ELEVATED_CLAIM.search(s) and now.elevated:
            problems.append(LessonProblem(
                "elevation_state", "it says your house is not elevated, but at the end of this year it is"))
        if _INSURED_CLAIM.search(s) and not now.insured:
            problems.append(LessonProblem(
                "insurance_state", "it says you have flood insurance, but at the end of this year you do not"))
        if _UNINSURED_CLAIM.search(s) and now.insured:
            problems.append(LessonProblem(
                "insurance_state", "it says you have no flood insurance, but at the end of this year you do"))
    seen = set()
    out = []
    for p in problems:
        if p.code not in seen:
            seen.add(p.code)
            out.append(p)
    return out
