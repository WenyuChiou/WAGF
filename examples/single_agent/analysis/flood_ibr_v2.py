"""Flood IBR, the SHARED IBR family (irrigation v3 spec item 37e, 2026-10
WRR26 rerun): irrigation's own ``examples/irrigation_abm/analysis/v3_metrics.py
(ibr_metrics, Decision, _first_stated, parse_decision)`` is the reference, and
this module mirrors it, construct for construct (TP_LABEL/CP_LABEL instead of
WSA; R1/R3/R4 instead of TR1/TR3) and name for name where irrigation itself
has a name to mirror.

Supersedes, for the WRR26-rerun corpus only, the final-attempt-label IBR of
``gemma4_nw_crossmodel_analysis.py (compute_ibr_components)`` (the EDT2/NW-era
definition, still canonical for the pre-rerun 83fa97e1 corpus; not modified
here).

THE SHARED DEFINITION (spec item 37e; ``.research/design_specs/
irrigation_v3_spec_2026-09-28.md``, as refined by items 37, 37a and 37d):

    n = every agent-year row, ABORTED included (never a violation). Raises
        (``MetricsError``) when n == 0 -- a mean of zero decisions is not a
        measurement, matching irrigation's own ``ibr_metrics``.
    first-stated labels = ``initial_labels`` (attempt 0) when a construct is
        stated there, else the first later attempt that states it
        (``first_stated_labels`` below; irrigation's own ``_first_stated``).
    PRIMARY (``ibr_pct``) = the LAST PARSED attempt's action (``Decision.
        last_parsed_proposal``; examples/irrigation_abm/analysis/v3_metrics.py,
        merged PR #71; item 37d: steps back past a literal last attempt that
        did not parse), judged against the first-stated labels, over n.
    first-proposal share (``ibr_first_proposal_pct``) = attempt 0's OWN
        action judged against the FIRST-STATED labels (NOT attempt 0's own
        literal label -- item 37e is explicit here, and it matches what
        irrigation's ``ibr_metrics`` already does: ``d.first_proposal == ...
        and d.first_wsa in ...``, where ``first_wsa`` is first-stated, not
        literal-attempt-0).
    executed share (``ibr_executed_pct``) = the ``executed_skill`` COLUMN,
        read directly (not re-derived from status + last action), judged
        against the first-stated labels.
    final-label share (``ibr_final_label_pct``) = the LITERAL last attempt's
        action (``final_proposal``; None when it did not parse) judged
        against ``final_labels`` (that SAME literal last attempt's own
        stated labels). An unparsed last attempt therefore contributes no
        violation, automatically -- no special-cased denominator is needed.
    relabel rate (``relabel_rate_pct``) = retried decisions (``retry_count >
        0``) whose ``appraisal_relabeled`` FRAMEWORK COLUMN is true, over
        retried decisions (NOT over n -- irrigation's own ``Decision.
        retried`` / ``relabel_rate_pct`` convention). Read DIRECTLY from the
        column the generic engine already writes
        (``broker/core/_appraisal_freeze.py (relabeled_after_first_statement)``,
        wired into the audit row by ``broker/core/_audit_helpers.py
        (_attempt_audit_columns)``), not recomputed by comparing two label
        dicts here -- irrigation counts WSA only (its one governed
        construct); flood counts TP and CP together (either relabelling
        sets the column True), because R1 depends on both and R3/R4 on TP.
        ``None`` when ``retried_decisions == 0`` (irrigation's own ``_pct``:
        a share of zero retries is not a measurement); ``aggregate_over_seeds``
        skips a ``None`` run rather than averaging it in as zero.
    last_attempt_unparsed_n = decisions whose literal last attempt had no
        skill (``Decision.last_attempt_unparsed``).
    ibr_stepback_violations_n = of those, the ones counted as a PRIMARY
        violation (every one of them was found ONLY by stepping back: a row
        whose literal last attempt is unparsed has no action for the
        final-label share to match either, so the step-back is the only way
        any of these could be a violation at all).
    first_tp_missing / first_cp_missing = decisions (ABORTED included, like
        irrigation's own ``first_wsa_missing``) whose first-stated TP_LABEL /
        CP_LABEL is blank -- a diagnostic on how much of the corpus had
        nothing to judge, not itself a share.
    aborted_count = rows with ``status`` in ``ABORTED_STATUSES``.
    Every percent field above is 0-100 (``_pct``, copied verbatim from
    irrigation: ``None if denominator == 0 else 100.0 * numerator /
    denominator``), never a bare 0-1 fraction.
    A non-ABORTED row with no parsed attempt at all RAISES (``MetricsError``)
    instead of degrading silently -- mirrors irrigation's own ``parse_decision``
    ("first attempt did not parse on a non-ABORTED row").

R1/R3/R4 (unchanged by item 37e, which is only about the shared arithmetic
above, not which rules are summed): R1 (redefined 2026-10-06, PI decision
item 10, PMT's non-protective response, Grothmann and Reusswig 2006 p.106):
threat H or VH AND coping NOT (VL or L), action do_nothing. R3: threat VL or
L AND action == relocate. R4: threat VL or L AND action == elevate_house. R5
(re-elevation) stays excluded, as before. A missing/blank label never
matches (no rule fires on absent information).

Inputs: the ``household_governance_audit.csv`` written by a run with
``global_config.audit.initial_proposal_columns: true``, ``attempt_columns:
true`` and ``corrected_status_columns: true`` (flood's ``agent_types.yaml``
turns all three on). Reads ``initial_skill``, ``initial_labels``,
``final_labels``, ``attempt_skills``, ``attempt_labels``, ``executed_skill``,
``appraisal_relabeled``, ``retry_count``, ``execution_path``, ``status`` --
columns these flags always produce, independent of governance arm (strict,
disabled, silent, no-nudge all carry them; ``disabled`` has no retries, so
``initial_skill`` == the last attempt's own skill and ``initial_labels`` ==
``final_labels`` on every disabled row, which collapses every share to the
same number -- the correct degenerate case, not a bug). A blank/NaN
``attempt_labels``/``initial_labels``/``final_labels`` cell (a single parsed
attempt that stated nothing at all) reads as "no labels", not a parse
failure -- ``_load_csv`` also reads with ``keep_default_na=False`` so pandas
never turns a genuinely-blank CSV cell into NaN in the first place.

CLI:
    python examples/single_agent/analysis/flood_ibr_v2.py \\
        --csv path/to/household_governance_audit.csv [path/to/another ...]

Unit test: examples/single_agent/tests/test_flood_ibr_v2.py (synthetic trace,
no real run needed).
"""
from __future__ import annotations

import argparse
import re
import statistics
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

#: R1/R3/R4 construct label bins (R5 -- re-elevation -- excluded; see the
#: flood design record section 3.2 for why).
HIGH_THREAT = {"H", "VH"}
LOW_THREAT = {"VL", "L"}
LOW_COPING = {"VL", "L"}

#: Mirrors irrigation's own ABORTED_STATUSES (examples/irrigation_abm/analysis/
#: v3_metrics.py): no decision to judge, denominator-only.
ABORTED_STATUSES = {"ABORTED", "ABORTED_EXCEPTION"}

_LABEL_PAIR_RE = re.compile(r"([A-Za-z_]+)=([^|]*)")
TP_KEY = "TP_LABEL"
CP_KEY = "CP_LABEL"
_CONSTRUCT_KEYS = (TP_KEY, CP_KEY)

#: Required household_governance_audit.csv columns. initial_proposal_columns
#: gives initial_skill/initial_labels/attempt_skills/final_labels;
#: attempt_columns gives attempt_labels/appraisal_relabeled;
#: corrected_status_columns gives execution_path and executed_skill (and is
#: what makes an ABORTED row exist as a row at all -- requiring the column
#: here is the cheapest proof the flag was on). retry_count is a baseline
#: audit column, present regardless of any flag.
REQUIRED_COLUMNS = {
    "initial_skill", "initial_labels", "final_labels",
    "attempt_skills", "attempt_labels", "executed_skill",
    "appraisal_relabeled", "retry_count", "execution_path", "status",
}


class MetricsError(RuntimeError):
    """A missing/malformed cell or an inconsistent audit row -- raised, never
    papered over (mirrors irrigation's own ``v3_metrics.MetricsError``)."""


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value))


def parse_labels(raw: object) -> Dict[str, str]:
    """``"TP_LABEL=L|CP_LABEL=M"`` -> ``{"TP_LABEL": "L", "CP_LABEL": "M"}``.

    ``""``/``NaN``/anything non-string -> ``{}``. A key with a blank value
    (``"TP_LABEL="``, the format for an attempt that did not state it) is
    kept, but reads as blank/missing to every check below -- consistent
    with the engine's own ``get_label`` returning ``""`` for a missing
    construct and no rule ever matching an empty label.
    """
    if not isinstance(raw, str) or not raw:
        return {}
    return {k: v for k, v in _LABEL_PAIR_RE.findall(raw)}


def parse_attempt_labels(attempt_labels_raw: object) -> List[Dict[str, str]]:
    """Each attempt's labels, in order, from the pipe-joined
    ``attempt_labels`` column (``global_config.audit.attempt_columns``):
    comma-joined ``KEY=VALUE`` pairs per attempt; ``""`` for an attempt
    that did not parse becomes ``{}``.

    ``None``/NaN (a blank CSV cell pandas coerced, or an explicit missing
    value) is treated exactly like ``""`` -- mirrors irrigation's own
    loading, where ``_cell(...).split("|")`` ALWAYS yields at least one
    segment because the value is always a real string (``csv.DictReader``
    never produces NaN). A single parsed attempt that stated no labels at
    all therefore returns ``[{}]`` (one empty-dict segment), never ``[]``:
    getting this wrong (returning ``[]``) made ``parse_decision`` see
    ``len(attempt_skills) == 1`` against ``len(attempt_labels) == 0`` and
    raise a spurious length-mismatch error on a perfectly ordinary row.
    """
    if isinstance(attempt_labels_raw, str):
        text = attempt_labels_raw
    elif _is_blank(attempt_labels_raw):
        text = ""
    else:
        return []
    out: List[Dict[str, str]] = []
    for segment in text.split("|"):
        if not segment:
            out.append({})
            continue
        pairs: Dict[str, str] = {}
        for part in segment.split(","):
            if "=" in part:
                key, value = part.split("=", 1)
                pairs[key] = value
        out.append(pairs)
    return out


def _stated(value: Optional[str]) -> bool:
    return value is not None and value.strip() != ""


def first_stated_labels(initial_labels_raw: object, attempt_labels_raw: object) -> Dict[str, str]:
    """The labels as FIRST STATED anywhere in the decision -- irrigation's
    own ``_first_stated`` helper and the appraisal freeze's
    ``freeze_first_stated_labels`` (``broker/core/_appraisal_freeze.py``)
    both use this same rule: ``initial_labels`` when a construct is stated
    there, else the first non-blank value for that construct in
    ``attempt_labels``, in attempt order. A construct the agent left BLANK
    on attempt 0 but stated on attempt 2 counts as first stated at attempt
    2, not as never stated."""
    initial = parse_labels(initial_labels_raw)
    result = dict(initial)
    missing = [k for k in _CONSTRUCT_KEYS if not _stated(initial.get(k))]
    if not missing:
        return result
    for attempt in parse_attempt_labels(attempt_labels_raw):
        for key in list(missing):
            candidate = attempt.get(key)
            if _stated(candidate):
                result[key] = candidate
                missing.remove(key)
        if not missing:
            break
    return result


def _label(labels: Mapping[str, str], key: str) -> str:
    return (labels.get(key) or "").strip().upper()


def _violates(threat: str, coping: str, action: object) -> Optional[str]:
    """Which rule (if any) this (threat, coping, action) combination
    violates. Returns the rule id, or ``None``. A blank/missing label never
    matches a bin, so a decision with no appraisal recorded never counts as
    a violation (consistent with the engine: ``get_label`` -> ``""`` ->
    ``label_matches`` -> False). ``action`` may be ``None`` (an unparsed
    attempt); it then matches nothing, by the same equality logic, with no
    special-casing needed -- this is how an unparsed literal last attempt
    contributes no violation to the final-label share without any denominator
    exclusion (item 37e)."""
    threat = (threat or "").strip().upper()
    coping = (coping or "").strip().upper()
    if action == "do_nothing" and threat in HIGH_THREAT and coping and coping not in LOW_COPING:
        return "R1"
    if action == "relocate" and threat in LOW_THREAT:
        return "R3"
    if action == "elevate_house" and threat in LOW_THREAT:
        return "R4"
    return None


# =============================================================================
# Audit rows: one decision each (mirrors irrigation's Attempt / Decision /
# parse_decision, examples/irrigation_abm/analysis/v3_metrics.py)
# =============================================================================

@dataclass(frozen=True)
class Attempt:
    """One parsed or unparsable attempt of a decision (``attempt_*``
    columns)."""

    skill: Optional[str]              # None: the attempt did not parse
    labels: Optional[Dict[str, str]]  # None: the attempt did not parse

    @property
    def parsed(self) -> bool:
        return self.skill is not None


@dataclass(frozen=True)
class Decision:
    """One audit row: the agent's decision for one year, all its attempts.

    Mirrors irrigation's own ``Decision`` (examples/irrigation_abm/analysis/
    v3_metrics.py): ``final_proposal`` / ``first_proposal`` /
    ``last_attempt_unparsed`` / ``last_parsed_proposal`` / ``retried`` are
    named and defined identically, substituting flood's own columns."""

    agent_id: str
    year: str
    status: str
    execution_path: str
    executed_skill: Optional[str]
    attempts: Tuple[Attempt, ...]      # empty for an ABORTED/ABORTED_EXCEPTION row
    retry_count: int
    first_labels: Dict[str, str]       # first-STATED TP_LABEL/CP_LABEL (may read past attempt 0)
    final_labels: Dict[str, str]       # the LITERAL last attempt's own stated labels
    relabeled: bool                    # the framework's own appraisal_relabeled column

    @property
    def aborted(self) -> bool:
        """No decision: ABORTED or ABORTED_EXCEPTION (``execution_path``
        aborted). In n, never a violation, no readable final proposal."""
        return self.execution_path == "aborted"

    @property
    def final_proposal(self) -> Optional[str]:
        """The skill of the LITERAL last attempt; None when it did not parse
        (or there are no attempts at all, i.e. an ABORTED row)."""
        return self.attempts[-1].skill if self.attempts else None

    @property
    def first_proposal(self) -> Optional[str]:
        return self.attempts[0].skill if self.attempts else None

    @property
    def last_attempt_unparsed(self) -> bool:
        """Item 37d: True when this decision has at least one attempt and
        the literal LAST one did not parse (flood's REJECTED_FALLBACK).
        False for an ABORTED/ABORTED_EXCEPTION row (no attempts at all -- a
        different, pre-existing category) and for a decision whose last
        attempt parsed."""
        return bool(self.attempts) and not self.attempts[-1].parsed

    @property
    def last_parsed_proposal(self) -> Optional[str]:
        """Item 37d: step back through ``attempts``, most recent first, to
        the latest one that parsed. None only when no attempt parsed at all
        -- which cannot happen on a non-ABORTED row (``parse_decision``
        raises first), so this is None only for an ABORTED row (attempts
        is empty)."""
        for attempt in reversed(self.attempts):
            if attempt.parsed:
                return attempt.skill
        return None

    @property
    def retried(self) -> bool:
        return self.retry_count > 0


def _cell(row: Mapping[str, Any], column: str, where: str) -> Any:
    if column not in row:
        raise MetricsError(f"{where}: column {column!r} is missing")
    return row[column]


def _str_cell(row: Mapping[str, Any], column: str, where: str) -> str:
    value = _cell(row, column, where)
    if _is_blank(value):
        raise MetricsError(f"{where}: column {column!r} has no value (blank/NaN cell)")
    return str(value)


def _opt_str(value: Any) -> Optional[str]:
    if _is_blank(value):
        return None
    text = str(value)
    return text if text.strip() != "" else None


def _retry_count(row: Mapping[str, Any], where: str) -> int:
    value = _cell(row, "retry_count", where)
    if _is_blank(value):
        raise MetricsError(f"{where}: retry_count is missing")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise MetricsError(f"{where}: retry_count={value!r} is not a number") from exc
    if number != int(number):
        raise MetricsError(f"{where}: retry_count={value!r} is not a whole number")
    return int(number)


def _bool_cell(row: Mapping[str, Any], column: str, where: str) -> bool:
    value = _cell(row, column, where)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text == "True":
            return True
        if text == "False":
            return False
    raise MetricsError(f"{where}: {column}={value!r} is not True or False")


def parse_decision(row: Mapping[str, Any], where: str) -> Decision:
    """Builds one :class:`Decision` from one audit row, with the same light
    integrity checks irrigation's own ``parse_decision`` runs (status vs
    execution_path; ``len(attempt_skills) == retry_count + 1``;
    ``initial_skill == attempt 0``), plus the item-37e requirement that a
    non-ABORTED row with no parsed attempt at all raises rather than
    degrading silently.

    ``attempt_labels`` is read with ``_cell`` (column-presence only), not
    ``_str_cell``: a blank/NaN cell there is a real, valid "this attempt
    stated nothing" row, not a missing-column error -- ``parse_attempt_labels``
    treats it exactly like ``""``."""
    status = _str_cell(row, "status", where).strip().upper()
    path = _str_cell(row, "execution_path", where).strip()
    aborted = status in ABORTED_STATUSES
    if aborted != (path == "aborted"):
        raise MetricsError(f"{where}: status {status!r} with execution_path {path!r}")

    retry_count = _retry_count(row, where)
    executed = _opt_str(row.get("executed_skill"))

    if aborted:
        attempts: Tuple[Attempt, ...] = ()
        first_labels: Dict[str, str] = {}
        final_labels: Dict[str, str] = {}
        relabeled = False
    else:
        skills = _str_cell(row, "attempt_skills", where).split("|")
        label_segments = parse_attempt_labels(_cell(row, "attempt_labels", where))
        if len(skills) != len(label_segments):
            raise MetricsError(
                f"{where}: attempt_skills has {len(skills)} segments, attempt_labels "
                f"has {len(label_segments)}"
            )
        if len(skills) != retry_count + 1:
            raise MetricsError(
                f"{where}: attempt_skills holds {len(skills)} attempts, "
                f"retry_count is {retry_count}"
            )
        attempts = tuple(
            Attempt(seg or None, labels if seg else None)
            for seg, labels in zip(skills, label_segments)
        )
        if not attempts[0].parsed:
            raise MetricsError(
                f"{where}: first attempt did not parse on a non-ABORTED row (item 37e: "
                "a non-aborted row with no parsed attempt raises)"
            )
        initial_skill = _opt_str(row.get("initial_skill"))
        if initial_skill != attempts[0].skill:
            raise MetricsError(
                f"{where}: initial_skill {initial_skill!r} is not attempt 0's skill "
                f"{attempts[0].skill!r}"
            )
        if executed is None:
            raise MetricsError(f"{where}: a non-ABORTED decision executed nothing")
        final_labels = parse_labels(row.get("final_labels"))
        if attempts[-1].parsed and final_labels != (attempts[-1].labels or {}):
            raise MetricsError(
                f"{where}: final_labels {final_labels} differ from the last attempt "
                f"{attempts[-1].labels}"
            )
        if not attempts[-1].parsed and final_labels:
            raise MetricsError(f"{where}: final_labels set although the last attempt did not parse")
        first_labels = first_stated_labels(row.get("initial_labels"), row.get("attempt_labels"))
        relabeled = _bool_cell(row, "appraisal_relabeled", where)

    return Decision(
        agent_id=str(row.get("agent_id", "")),
        year=str(row.get("year", "")),
        status=status,
        execution_path=path,
        executed_skill=executed,
        attempts=attempts,
        retry_count=retry_count,
        first_labels=first_labels,
        final_labels=final_labels,
        relabeled=relabeled,
    )


def load_decisions(df: pd.DataFrame) -> List[Decision]:
    out: List[Decision] = []
    for n, row in df.iterrows():
        out.append(parse_decision(row, f"row {n}"))
    return out


# =============================================================================
# The shared IBR family (spec item 37e; irrigation's own ibr_metrics)
# =============================================================================

def _pct(numerator: float, denominator: float) -> Optional[float]:
    """Copied verbatim from irrigation's own
    ``examples/irrigation_abm/analysis/v3_metrics.py (_pct)``: ``None``
    (not 0.0) when the denominator is zero -- a share of nothing is not a
    measurement, and 0.0 would be indistinguishable from a real zero rate."""
    return None if denominator == 0 else 100.0 * numerator / denominator


def ibr_metrics(decisions: Sequence[Decision]) -> Dict[str, Any]:
    """Item 37e's shared IBR family, for flood's R1/R3/R4 (irrigation's own
    ``ibr_metrics`` computes the same family for TR1/TR3 -- see the module
    docstring for the full definition of every field returned here). Raises
    ``MetricsError`` when ``decisions`` is empty, matching irrigation's own
    ``ibr_metrics`` exactly."""
    n = len(decisions)
    if n == 0:
        raise MetricsError("ibr_metrics: no decisions")
    components = {"R1": 0, "R3": 0, "R4": 0}
    violations = 0
    first_proposal_violations = 0
    executed_violations = 0
    final_label_violations = 0
    retried_decisions = relabeled_decisions = 0
    aborted_count = 0
    last_attempt_unparsed_n = 0
    ibr_stepback_violations_n = 0
    first_tp_missing = first_cp_missing = 0

    for d in decisions:
        # Diagnostic counts (like irrigation's own first_wsa_missing):
        # computed for EVERY decision, ABORTED included (an aborted row's
        # first_labels is {}, so both are missing there too, same as
        # irrigation's first_wsa for an aborted d.first_wsa is None).
        if not _stated(d.first_labels.get(TP_KEY)):
            first_tp_missing += 1
        if not _stated(d.first_labels.get(CP_KEY)):
            first_cp_missing += 1

        if d.aborted:
            # No decision to judge (irrigation's own convention): in n,
            # never a violation on any share -- every property below is
            # None/empty for this row by construction (attempts == ()), so
            # skipping explicitly is a clarity choice, not a behaviour one.
            aborted_count += 1
            continue

        tp = _label(d.first_labels, TP_KEY)
        cp = _label(d.first_labels, CP_KEY)

        stepped_back = d.last_attempt_unparsed
        if stepped_back:
            last_attempt_unparsed_n += 1

        # PRIMARY: the last PARSED attempt's action (item 37d), judged on
        # the first-STATED labels (item 37e).
        judged = d.last_parsed_proposal
        rule = _violates(tp, cp, judged)
        if rule:
            violations += 1
            components[rule] += 1
            if stepped_back:
                # Every violation found on a stepped-back row was found
                # ONLY by stepping back: the literal last attempt's own
                # action is None here, which _violates() never matches.
                ibr_stepback_violations_n += 1

        # First-proposal share (item 37e): attempt 0's OWN action, judged
        # against the FIRST-STATED labels -- not attempt 0's own literal
        # label (an earlier definition of this module used the literal
        # reading; item 37e overrides it).
        if _violates(tp, cp, d.first_proposal):
            first_proposal_violations += 1

        # Executed share (item 37e): the executed_skill COLUMN, read
        # directly, judged against the first-STATED labels.
        if _violates(tp, cp, d.executed_skill):
            executed_violations += 1

        # Final-label share (item 37e): the LITERAL last attempt's action,
        # judged against that SAME attempt's own final labels. None
        # (unparsed) matches nothing, so an unparsed last attempt
        # contributes no violation -- no special denominator exclusion
        # needed.
        ftp = _label(d.final_labels, TP_KEY)
        fcp = _label(d.final_labels, CP_KEY)
        if _violates(ftp, fcp, d.final_proposal):
            final_label_violations += 1

        if d.retried:
            retried_decisions += 1
            relabeled_decisions += d.relabeled

    return {
        "decisions": n,
        "ibr_count": violations, "ibr_r1_count": components["R1"],
        "ibr_r3_count": components["R3"], "ibr_r4_count": components["R4"],
        "ibr_pct": _pct(violations, n),
        "first_proposal_count": first_proposal_violations,
        "ibr_first_proposal_pct": _pct(first_proposal_violations, n),
        "executed_count": executed_violations,
        "ibr_executed_pct": _pct(executed_violations, n),
        "final_label_count": final_label_violations,
        "ibr_final_label_pct": _pct(final_label_violations, n),
        "retried_decisions": retried_decisions, "relabeled_decisions": relabeled_decisions,
        "relabel_rate_pct": _pct(relabeled_decisions, retried_decisions),
        "aborted_count": aborted_count,
        "last_attempt_unparsed_n": last_attempt_unparsed_n,
        "ibr_stepback_violations_n": ibr_stepback_violations_n,
        "first_tp_missing": first_tp_missing, "first_cp_missing": first_cp_missing,
        "components": components,
    }


@dataclass
class FloodIbrV2:
    """One run's (or one pooled set of rows') item-37e numbers.

    Every ``_pct`` field is a PERCENT (0-100), never a bare 0-1 fraction,
    copied via irrigation's own ``_pct`` (``None`` when its denominator is
    zero). ``relabel_rate_pct`` is ``None`` when ``retried_decisions == 0``.
    """
    n: int
    violations: int
    ibr_pct: Optional[float]                   # PRIMARY: last PARSED attempt, first-STATED labels
    first_proposal_violations: int
    ibr_first_proposal_pct: Optional[float]    # first attempt's action, first-STATED labels (item 37e)
    executed_violations: int
    ibr_executed_pct: Optional[float]          # executed_skill column, first-STATED labels
    final_label_violations: int
    ibr_final_label_pct: Optional[float]       # literal last attempt, its OWN final labels; unparsed = no violation
    relabeled_decisions: int
    retried_decisions: int                     # rows with retry_count > 0
    relabel_rate_pct: Optional[float]          # relabeled_decisions / retried_decisions (NOT / n); None if retried_decisions == 0
    components: Dict[str, int]                 # {"R1": n, "R3": n, "R4": n} for the PRIMARY definition
    aborted_count: int                         # status in ABORTED_STATUSES: in n, never a violation
    last_attempt_unparsed_n: int               # literal last attempt had no skill (item 37d)
    ibr_stepback_violations_n: int             # of those, the ones counted as a PRIMARY violation
    first_tp_missing: int                      # decisions (ABORTED included) with no first-stated TP_LABEL
    first_cp_missing: int                      # decisions (ABORTED included) with no first-stated CP_LABEL


def compute_flood_ibr_v2(df: pd.DataFrame) -> FloodIbrV2:
    """The item-37e numbers for one run's (or one pooled multi-run) audit
    rows. ``df`` must carry every column in ``REQUIRED_COLUMNS``
    (``household_governance_audit.csv`` with ``audit.initial_proposal_columns``,
    ``attempt_columns`` and ``corrected_status_columns`` all ``true``).
    Raises ``KeyError`` if a required column is absent -- never silently
    substitutes a default (that column's absence means the run did not turn
    the flag on, which is a configuration error to fix, not a zero to paper
    over). Raises ``MetricsError`` on a malformed or inconsistent row (see
    ``parse_decision``), or when ``df`` has zero data rows (a header-only
    CSV): matching irrigation's own ``ibr_metrics``, a mean of zero
    decisions is not a measurement, not a silent zero."""
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise KeyError(
            f"flood_ibr_v2 needs columns {sorted(REQUIRED_COLUMNS)}; missing "
            f"{sorted(missing)}. Was the run started with "
            "global_config.audit.initial_proposal_columns, attempt_columns "
            "and corrected_status_columns all set to true?"
        )

    decisions = load_decisions(df)
    m = ibr_metrics(decisions)  # raises MetricsError when decisions is empty
    return FloodIbrV2(
        n=m["decisions"],
        violations=m["ibr_count"], ibr_pct=m["ibr_pct"],
        first_proposal_violations=m["first_proposal_count"],
        ibr_first_proposal_pct=m["ibr_first_proposal_pct"],
        executed_violations=m["executed_count"],
        ibr_executed_pct=m["ibr_executed_pct"],
        final_label_violations=m["final_label_count"],
        ibr_final_label_pct=m["ibr_final_label_pct"],
        relabeled_decisions=m["relabeled_decisions"],
        retried_decisions=m["retried_decisions"],
        relabel_rate_pct=m["relabel_rate_pct"],
        components=m["components"],
        aborted_count=m["aborted_count"],
        last_attempt_unparsed_n=m["last_attempt_unparsed_n"],
        ibr_stepback_violations_n=m["ibr_stepback_violations_n"],
        first_tp_missing=m["first_tp_missing"], first_cp_missing=m["first_cp_missing"],
    )


def aggregate_over_seeds(results: Sequence[FloodIbrV2]) -> Dict[str, Dict[str, Optional[float]]]:
    """Mean and range of each percent field over a list of per-seed
    :class:`FloodIbrV2` results (item 37: "then mean and range over
    seeds"). Returns ``{"ibr_pct": {"mean":.., "min":.., "max":..,
    "n_seeds":..}, ...}``. Raises ``ValueError`` on an empty list -- a mean
    of zero runs is not a measurement.

    A run whose field is ``None`` (only possible for ``relabel_rate_pct``,
    when that run retried nothing) is SKIPPED, not averaged in as zero --
    matching irrigation's own convention that a share of zero retries is not
    a measurement. ``n_seeds`` reports how many runs actually contributed;
    if every run is ``None``, the field's own ``mean``/``min``/``max`` are
    ``None`` too (never a crash on an empty ``fmean``/``min``/``max``)."""
    results = list(results)
    if not results:
        raise ValueError("aggregate_over_seeds needs at least one run")

    out: Dict[str, Dict[str, Optional[float]]] = {}
    for field in ("ibr_pct", "ibr_first_proposal_pct", "ibr_executed_pct",
                  "ibr_final_label_pct", "relabel_rate_pct"):
        values = [v for v in (getattr(r, field) for r in results) if v is not None]
        if not values:
            out[field] = {"mean": None, "min": None, "max": None, "n_seeds": 0}
            continue
        out[field] = {
            "mean": statistics.fmean(values),
            "min": min(values),
            "max": max(values),
            "n_seeds": len(values),
        }
    return out


def _load_csv(path: str) -> pd.DataFrame:
    # keep_default_na=False: a genuinely blank CSV cell (e.g. a
    # single parsed attempt that stated no labels) must read as "", never
    # pandas' NaN -- parse_decision tolerates both, but reading this way
    # means the common real-corpus case never needs that tolerance at all.
    return pd.read_csv(path, keep_default_na=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Flood IBR (irrigation v3 spec item 37e): compute and print the "
                    "shared-family IBR numbers for one or more household_governance_audit.csv runs."
    )
    parser.add_argument("--csv", nargs="+", required=True,
                         help="one or more household_governance_audit.csv paths (one per seed)")
    args = parser.parse_args()

    per_seed = [compute_flood_ibr_v2(_load_csv(p)) for p in args.csv]
    for path, result in zip(args.csv, per_seed):
        print(f"{path}: n={result.n} ibr_pct={result.ibr_pct:.2f} "
              f"ibr_first_proposal_pct={result.ibr_first_proposal_pct:.2f} "
              f"ibr_executed_pct={result.ibr_executed_pct:.2f} "
              f"ibr_final_label_pct={result.ibr_final_label_pct:.2f} "
              f"relabel_rate_pct={result.relabel_rate_pct} (retried={result.retried_decisions}) "
              f"components={result.components} "
              f"aborted={result.aborted_count} "
              f"last_attempt_unparsed={result.last_attempt_unparsed_n} "
              f"(stepback_violations={result.ibr_stepback_violations_n}) "
              f"first_tp_missing={result.first_tp_missing} first_cp_missing={result.first_cp_missing}")
    if len(per_seed) > 1:
        agg = aggregate_over_seeds(per_seed)
        print("--- aggregate over seeds ---")
        for field, stats in agg.items():
            if stats["mean"] is None:
                print(f"{field}: no seed contributed a value (n_seeds=0)")
                continue
            print(f"{field}: mean={stats['mean']:.2f} min={stats['min']:.2f} "
                  f"max={stats['max']:.2f} (n_seeds={stats['n_seeds']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
