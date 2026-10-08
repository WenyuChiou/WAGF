"""Irrigation reflection grounding: parse the agent's own outcome lines, pick
the key years the program writes, and measure semantic lesson flags.

Spec: ``.research/design_specs/irrigation_v3_spec_2026-09-28.md`` item 45
(c) and (e); the report-only semantic checks are the ones the reflection error
diagnosis measured on the cbb74f73 pilot
(``.research/design_specs/irrigation_v3_reflection_error_diagnosis_2026-10-07.md``
section 4, scripts ``analyze.py`` and ``analyze3.py``). Those precision
measurements apply to the old prompt. Flags have known false positives,
including negated claims, and must be hand-audited in the new pilot; they
never trigger a retry or drop. The measurement patterns are:

- a "when precipitation is below/above ..." outcome rule with a
  counterexample among the listed years (precision 37/37);
- an unconditional "always fully met" claim with a listed shortfall, or an
  "always short" claim when at least half the listed years were fully met
  (about 22/24);
- "Lake Mead consistently rose/declined" with a listed year in the other
  direction (8/12);
The foreign-figure check (``_foreign_figures``, kept from spec 4.7) still
blocks storage. The framework enforces numbers only when enabled, junk and
the 500-character cap separately.

Key years (item 45c, refined by the 2026-10-07 literature scan, ADD NOW A2):
the year just ended, plus the listed year with the largest shortfall when it
is a different year (ties: the most recent). A stated assumption: a lesson is
anchored on the most recent and the most severe outcome, following recency
(Hertwig et al., 2004, Psychological Science 15(8): 534-539; Weber, 2006,
Climatic Change 77: 103-120) and loss salience (Baumeister et al., 2001,
Review of General Psychology 5(4): 323-370). Under the irrigation importance
bands (``adapters/irrigation_adapter.py (IrrigationAdapter.outcome_importance)``)
the largest shortfall is also the listed line of highest importance.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from broker.components.cognitive.reflection import LessonProblem

# ---------------------------------------------------------------------------
# figures (moved here from run_experiment.py; re-exported there unchanged)
# ---------------------------------------------------------------------------

# A figure a reflection summary can quote (spec 4.7, review HIGH 1): a number
# with thousands separators ("20,155"), a plain number, optionally followed by
# a unit: "%" or "percent" (a share), "million" (million acre-ft), or an
# acre-ft unit ("acre-ft", "acre-feet", "AF"). Not preceded by a letter,
# digit, point or comma, so "UT2" or the tail of a longer number never match.
_FIGURE = re.compile(
    r"(?<![\w.,])(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<unit>\s*(?:%|percent\b|million\b|acre[- ]?f(?:ee|oo)?t\b|af\b))?",
    re.IGNORECASE,
)

# A summary figure within this relative distance of a figure of the same kind
# in the agent's own memory text counts as that figure, rounded (review HIGH 1:
# "about 20,000 acre-ft" for a memory line's 20,155 is the agent's own figure).
_FIGURE_TOLERANCE = 0.05


def _figures(text: str) -> Tuple[List[Tuple[str, float]], List[Tuple[str, float]]]:
    """(volumes, percentages) quoted in ``text``, each as (as written, value).

    A volume is a number with thousands separators, a plain number of four or
    more digits that is not a calendar year (1900 to 2100), or any number
    followed by an acre-ft unit or "million" (scaled to acre-ft). A percentage
    is a number followed by "%" or "percent". Any other bare number (a count,
    a tier, a day of the month, a year) is not a figure."""
    volumes: List[Tuple[str, float]] = []
    percents: List[Tuple[str, float]] = []
    for m in _FIGURE.finditer(text):
        num = m.group("num")
        unit = (m.group("unit") or "").strip().lower()
        value = float(num.replace(",", ""))
        written = m.group(0).strip()
        if unit in ("%", "percent"):
            percents.append((written, value))
        elif unit == "million":
            volumes.append((written, value * 1e6))
        elif unit:
            volumes.append((written, value))
        elif "," in num:
            volumes.append((written, value))
        elif "." not in num and len(num) >= 4 and not (len(num) == 4 and 1900 <= value <= 2100):
            volumes.append((written, value))
    return volumes, percents


def _near(value: float, pool: List[float]) -> bool:
    return any(abs(value - ref) <= _FIGURE_TOLERANCE * abs(ref) for ref in pool)


def _foreign_figures(summary: str, own_text: str) -> List[str]:
    """Figures in ``summary`` that match no figure of the same kind in
    ``own_text`` (the agent's own memory lines the reflection was written
    from), within ``_FIGURE_TOLERANCE``. A reflection that quotes one is not
    stored (spec 4.7; L3 M8: 201 prompts showed an acre-ft figure that
    belonged to another agent).

    Review HIGH 1 (2026-09-30): rounding is tolerated ("about 20,000
    acre-ft" matches a memory line's 20,155), and figures written without
    separators ("14420 acre-ft") and percentages are checked too. A
    percentage also matches the complement of a memory percentage (a
    delivered share is 100 minus the unmet share the memory line states), and
    0 and 100 percent always match (a full delivery or none, nobody's own
    figure)."""
    own_volumes, own_percents = _figures(own_text)
    volume_pool = [v for _, v in own_volumes]
    percent_pool = [p for _, p in own_percents] + [100.0 - p for _, p in own_percents] + [0.0, 100.0]
    volumes, percents = _figures(summary)
    return ([w for w, v in volumes if not _near(v, volume_pool)]
            + [w for w, p in percents if not _near(p, percent_pool)])


# ---------------------------------------------------------------------------
# the agent's own outcome lines
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OutcomeLine:
    """One memory line of ``irrigation_personas.build_action_outcome_feedback``,
    as the model read it (every number as printed)."""
    year: int
    direction: str          # "increase" | "decrease" | "keep"
    request: int
    received: int
    short: bool
    unmet_pct: float        # 0.0 when fully met
    precip: Optional[str]   # "above" | "below" (Upper Basin), else None
    mead: Optional[str]     # "higher" | "lower" (Lower Basin), else None
    text: str


_LINE_YEAR = re.compile(r"^Year (\d{4}):")
_REQ_REC = re.compile(r"You requested ([\d,]+) acre-ft and received ([\d,]+) acre-ft\.")
_SHORT = re.compile(r"Shortfall: [\d,]+ acre-ft \(([\d.]+)% unmet\)")
_PRECIP = re.compile(r"precipitation in (?:your sub-basin|the Upper Basin) was (above|below) the previous winter's")
_MEAD = re.compile(r"Lake Mead was (higher|lower) than a year earlier")
_CHOSE = re.compile(r"^Year \d{4}: You chose to (increase|maintain|decrease) demand")


def line_year(text: str) -> Optional[int]:
    """The calendar year a memory line names ("Year 2033: ..."), or None."""
    m = _LINE_YEAR.match(text or "")
    return int(m.group(1)) if m else None


def parse_outcome_line(text: str) -> Optional[OutcomeLine]:
    """An outcome line as printed, or None when ``text`` is not one (no year
    or no "You requested ... and received ..." sentence). Reads the pre-45
    lines (the cbb74f73 pilot) and the item-45 lines (keep-change clause,
    flow share) alike."""
    year = line_year(text)
    rr = _REQ_REC.search(text or "")
    if year is None or rr is None:
        return None
    chose = _CHOSE.match(text)
    if chose:
        direction = {"maintain": "keep"}.get(chose.group(1), chose.group(1))
    else:
        # An overruled year ("maintain demand was applied under ...") or a
        # year with no decision read: the request stayed at the base.
        direction = "keep"
    short = _SHORT.search(text)
    precip = _PRECIP.search(text)
    mead = _MEAD.search(text)
    return OutcomeLine(
        year=year, direction=direction,
        request=int(rr.group(1).replace(",", "")), received=int(rr.group(2).replace(",", "")),
        short=short is not None, unmet_pct=float(short.group(1)) if short else 0.0,
        precip=precip.group(1) if precip else None, mead=mead.group(1) if mead else None,
        text=text,
    )


def key_years(lines: Sequence[OutcomeLine], latest_year: int) -> List[int]:
    """The years the program writes into a stored reflection (item 45c):
    ``latest_year`` (the year just ended) and the listed year with the
    largest unmet share when that is another year (ties: the most recent).
    Oldest first. ``latest_year`` must be listed."""
    years = {line.year for line in lines}
    if latest_year not in years:
        raise ValueError(f"key_years: the year just ended ({latest_year}) is not among the listed years {sorted(years)}.")
    picked = {latest_year}
    shorts = [line for line in lines if line.short]
    if shorts:
        worst = max(shorts, key=lambda line: (line.unmet_pct, line.year))
        picked.add(worst.year)
    return sorted(picked)


def fact_line(line: OutcomeLine, previous_received: Optional[int] = None) -> str:
    """One program-written fact (item 45c; literature scan A2): the year,
    the request, its actual change from the preceding receipt when that
    receipt is among the input lines, the amount received and the unmet
    share. The comparison uses amounts rather than the action label because
    an increase action can still ask for less than the prior request."""
    action = f"you asked for {line.request:,} acre-ft"
    if previous_received is not None and line.request > previous_received:
        action += (f", an increase over the {previous_received:,} acre-ft you received "
                   "the year before,")
    elif previous_received is not None and line.request < previous_received:
        action += (f", a decrease from the {previous_received:,} acre-ft you received "
                   "the year before,")
    elif previous_received is not None:
        action += (f", the same as the {previous_received:,} acre-ft you received "
                   "the year before,")
    outcome = "fully met" if not line.short else f"{line.unmet_pct:.1f}% unmet"
    return f"{line.year}: {action} and you received {line.received:,} acre-ft ({outcome})."


# ---------------------------------------------------------------------------
# the checks (diagnosis section 4; regular expressions copied verbatim)
# ---------------------------------------------------------------------------

# analyze.py: the precipitation-rule check
_RULE_SHORT_CUE = re.compile(r"shortfall|unmet|short of|fell short|falls? short|fail\w* to (?:meet|secure|fulfil|fully)|not (?:fully )?met|insufficient (?:water|deliver|supply)|deficit|less than (?:I|my|what I) request|curtail|cut |reduced deliver|reductions? in (?:my )?(?:deliver|supply|allocation)", re.I)
_RULE_FULL_CUE = re.compile(r"fully met|full(?:y)? (?:fulfil\w*|deliver\w*|satisf\w*)|full fulfil\w*|full demand|demand (?:was |being )?(?:fully )?met|request(?:s)? (?:was |were )?(?:fully |successfully )?met|successfully met|met my (?:request|demand|need)|fulfil(?:l)?(?:ed|ment) (?:of )?my|received (?:the )?(?:full|exact|same)|met in full|always met|consistently met|full supply", re.I)
_LOWP = re.compile(r"(?:below|low|lower|decreas\w*|reduced|less|drier|dry|declin\w*|poor|lack of|limited|scarce|unfavorable)[\w\s-]{0,25}precipitation|precipitation[\w\s'-]{0,30}?(?:was |is |were )?(?:below|decreas\w*|declin\w*|lower|low\b|dropp\w*|fell|less)", re.I)
_HIGHP = re.compile(r"(?:above|high|higher|increas\w*|more|wetter|wet|abundant|ample|favorable|good|strong)[\w\s-]{0,25}precipitation|precipitation[\w\s'-]{0,30}?(?:was |is |were )?(?:above|increas\w*|higher|high\b|exceed\w*|rose|rising)", re.I)
# analyze3.py: the persistent-outcome and Lake Mead checks
_SHORT_CUE = re.compile(r"shortfall|unmet|short of|fell short|falls? short|fail\w* to (?:meet|secure|fulfil|fully)|not (?:fully )?met|insufficient (?:water|deliver|supply)|deficit|less than (?:I|my|what I) request|curtail|reduced my (?:allocation|deliver|water)|cut my|reduc\w* my (?:junior|water|allocation)", re.I)
_FULL_CUE = re.compile(r"fully met|full(?:y)? (?:fulfil\w*|deliver\w*|satisf\w*)|full fulfil\w*|full demand|full water|demand (?:was |being )?(?:fully )?met|request(?:s)? (?:was |were )?(?:fully |successfully )?met|successfully met|met my (?:request|demand|need)|fulfil(?:l)?(?:ed|ment) (?:of )?my|received (?:the )?(?:full|exact|same)|met in full|always met|consistently met|full supply|full allocation", re.I)
_PERSIST = re.compile(r"consistent\w*|persistent\w*|always|every year|each year|year after year|repeated\w*|continu\w*|invariabl\w*", re.I)
_COND = re.compile(r"\bwhen\b|\bif\b|\bduring\b|particularly|especially|whenever|\bonly\b|despite|even (?:when|though|with)|unless|\bexcept|\bin years\b", re.I)
_MEAD_TIGHT = re.compile(
    r"(?:Mead|lake|reservoir|water)(?:'s)?\s+(?:water\s+)?levels?\s+(?:\w+\s+){0,2}(?:consistently|steadily|always|continuously|continually|repeatedly)\s+(?:\w+\s+){0,1}(?P<d1>rose|rising|risen|increas\w*|higher|climb\w*|declin\w*|fell|falling|drop\w*|lower|decreas\w*)"
    # One change from analyze3.py (2026-10-07 hand check of the offline
    # replay): "water" alone counted as the lake, so "consistently
    # increasing my water demand" read as Lake Mead rising; it must now be
    # "water level(s)".
    r"|(?:consistently|steadily|continuously|continually)\s+(?P<d2>rising|increasing|declining|decreasing|falling|dropping|higher|lower)\s+(?:\w+\s+){0,2}(?:Lake\s+)?(?:Mead|lake|reservoir|water\s+levels?)"
    r"|(?:Mead|lake|reservoir)(?:'s)?\s+(?:water\s+)?levels?\s+(?P<d3>rose|increased|declined|fell|dropped|decreased)\s+(?:\w+\s+){0,2}(?:consistently|steadily|each year|every year|year after year|in each)", re.I)


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def check_lesson(lesson: str, lines: Sequence[OutcomeLine], own_text: str) -> List[LessonProblem]:
    """Report-only semantic flags and blocking foreign figures, judged
    against ``lines`` (the agent's listed outcome lines, the reflection's
    input) and ``own_text`` (their text, for the foreign-figure check).
    Semantic flags are measured, not enforced; known false positives are
    hand-audited in the pilot. Numbers are the framework's optional check."""
    problems: List[LessonProblem] = []
    below_full = any(l.precip == "below" and not l.short for l in lines)
    above_short = any(l.precip == "above" and l.short for l in lines)
    for s in _sentences(lesson):
        if _LOWP.search(s) and _RULE_SHORT_CUE.search(s) and below_full:
            problems.append(LessonProblem(
                "precipitation_rule",
                "it says that lower precipitation goes with a shortfall, but a listed year "
                "with lower precipitation than the previous winter was fully met"))
        if _HIGHP.search(s) and _RULE_FULL_CUE.search(s) and above_short:
            problems.append(LessonProblem(
                "precipitation_rule",
                "it says that higher precipitation goes with full delivery, but a listed year "
                "with higher precipitation than the previous winter had a shortfall"))

    shorts = [l.short for l in lines]
    mead_dirs = [l.mead for l in lines if l.mead]
    for s in _sentences(lesson):
        m = _MEAD_TIGHT.search(s)
        if m and mead_dirs:
            d = (m.group("d1") or m.group("d2") or m.group("d3")).lower()
            up = bool(re.match(r"ros|ris|incr|high|climb", d))
            if (up and "lower" in mead_dirs) or ((not up) and "higher" in mead_dirs):
                problems.append(LessonProblem(
                    "mead_direction",
                    f"it says Lake Mead {'rose' if up else 'fell'} every year, but a listed year "
                    f"shows it {'lower' if up else 'higher'} than a year earlier"))
        if _PERSIST.search(s) and not _COND.search(s):
            sh = bool(_SHORT_CUE.search(s))
            fu = bool(_FULL_CUE.search(s))
            if sh and not fu and shorts and sum(1 for x in shorts if not x) * 2 >= len(shorts):
                problems.append(LessonProblem(
                    "always_short",
                    "it says your demand was short every year, but at least half of the "
                    "listed years were fully met"))
            if fu and not sh and any(shorts):
                problems.append(LessonProblem(
                    "always_full",
                    "it says your demand was always met, but a listed year had a shortfall"))

    foreign = _foreign_figures(lesson, own_text)
    if foreign:
        problems.append(LessonProblem(
            "foreign_figure", f"it quotes a figure that is not in your record ({', '.join(foreign)})"))
    # one problem per code, in order
    seen = set()
    out = []
    for p in problems:
        if p.code not in seen:
            seen.add(p.code)
            out.append(p)
    return out
