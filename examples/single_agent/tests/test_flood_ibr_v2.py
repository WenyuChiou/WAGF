"""Unit test for the flood IBR shared-family definition (flood_ibr_v2.py,
irrigation v3 spec item 37e).

A synthetic trace only -- no real run, no LLM, no Ollama. Exercises every
percent field (primary, first-proposal, executed, final-label; all 0-100,
never a bare 0-1 fraction -- irrigation's own ``_pct`` convention), the
relabel rate (over retried decisions, not n, read from the
appraisal_relabeled column; ``None`` when nothing retried), first-stated
labels that may fall back past attempt 0, the REJECTED_FALLBACK / ABORTED
edge cases, and the item-37e integrity checks (a non-ABORTED row with no
parsed attempt raises; status vs execution_path; attempt-column length vs
retry_count; initial_skill vs attempt 0; a header-only CSV raises).
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.flood_ibr_v2 import (  # noqa: E402
    compute_flood_ibr_v2, aggregate_over_seeds, parse_labels,
    parse_attempt_labels, first_stated_labels, parse_decision,
    FloodIbrV2, MetricsError,
)

_DEFAULT_SKILL = "do_nothing"
_EXECUTION_PATH_BY_STATUS = {
    "APPROVED": "approved",
    "REJECTED": "rejected_default",
    "REJECTED_FALLBACK": "fallback",
}
_REJECTED_STATUSES = {"REJECTED", "REJECTED_FALLBACK"}


def _row(initial_tp, initial_cp, final_tp, final_cp, final_skill,
         initial_skill=None, attempt_skills=None, attempt_labels=None,
         retry_count=0, status="APPROVED", execution_path=None,
         executed_skill=None, appraisal_relabeled=None,
         agent_id="H0001", year=1):
    """``initial_skill`` defaults to ``final_skill``, and ``attempt_skills``
    defaults to just ``final_skill`` (a decision that never retried: one
    attempt, parsed, approved) -- the common case. ``attempt_labels``
    defaults to one attempt matching ``initial_tp``/``initial_cp``.
    ``executed_skill`` defaults to flood's own engine behaviour under
    ``on_retry_exhausted: default`` (spec item 37b): the registry default
    on REJECTED/REJECTED_FALLBACK, else ``final_skill``.
    ``appraisal_relabeled`` defaults to whether the (initial_tp, initial_cp)
    pair differs from (final_tp, final_cp) -- the framework's own column,
    not recomputed by this module; pass it explicitly for a row whose
    first-STATED label differs from attempt 0's own literal one. Pass these
    explicitly to build a realistic multi-attempt, REJECTED_FALLBACK, or
    first-stated-on-a-later-attempt row (see
    ``broker/core/skill_broker_engine.py _build_approved_skill``: a
    REJECTED_FALLBACK row's ``final_skill`` IS the registry default, not
    the agent's last proposal -- that is read from ``attempt_skills``
    instead)."""
    if execution_path is None:
        execution_path = _EXECUTION_PATH_BY_STATUS.get(status, "approved")
    if executed_skill is None:
        executed_skill = _DEFAULT_SKILL if status in _REJECTED_STATUSES else final_skill
    if appraisal_relabeled is None:
        appraisal_relabeled = (initial_tp != final_tp) or (initial_cp != final_cp)
    resolved_attempt_skills = attempt_skills if attempt_skills is not None else final_skill
    # The literal last attempt's own labels -- blank when that attempt did
    # not parse (a trailing "" segment in attempt_skills), matching the real
    # engine (SkillBrokerEngine never writes final_labels off an attempt it
    # could not parse; parse_decision enforces this as an integrity check,
    # so the fixture must be realistic here too).
    last_attempt_parsed = resolved_attempt_skills.split("|")[-1] != ""
    final_labels = f"TP_LABEL={final_tp}|CP_LABEL={final_cp}" if last_attempt_parsed else ""
    return {
        "agent_id": agent_id, "year": year,
        "initial_skill": initial_skill if initial_skill is not None else final_skill,
        "initial_labels": f"TP_LABEL={initial_tp}|CP_LABEL={initial_cp}",
        "final_labels": final_labels,
        "attempt_skills": resolved_attempt_skills,
        "attempt_labels": (
            attempt_labels if attempt_labels is not None
            else f"TP_LABEL={initial_tp},CP_LABEL={initial_cp}"
        ),
        "executed_skill": executed_skill,
        "appraisal_relabeled": appraisal_relabeled,
        "retry_count": retry_count,
        "status": status,
        "execution_path": execution_path,
    }


def test_parse_labels():
    assert parse_labels("TP_LABEL=L|CP_LABEL=M") == {"TP_LABEL": "L", "CP_LABEL": "M"}
    assert parse_labels("TP_LABEL=|CP_LABEL=M") == {"TP_LABEL": "", "CP_LABEL": "M"}
    assert parse_labels("") == {}
    assert parse_labels(None) == {}
    assert parse_labels(float("nan")) == {}


def test_parse_attempt_labels():
    assert parse_attempt_labels("TP_LABEL=H,CP_LABEL=M") == [{"TP_LABEL": "H", "CP_LABEL": "M"}]
    assert parse_attempt_labels("TP_LABEL=H,CP_LABEL=M|TP_LABEL=M,CP_LABEL=M") == [
        {"TP_LABEL": "H", "CP_LABEL": "M"}, {"TP_LABEL": "M", "CP_LABEL": "M"},
    ]
    # an attempt that did not parse is an empty segment -> {}
    assert parse_attempt_labels("TP_LABEL=H,CP_LABEL=M|") == [
        {"TP_LABEL": "H", "CP_LABEL": "M"}, {},
    ]


def test_parse_attempt_labels_blank_or_nan_is_one_empty_segment_not_zero():
    """Mirrors irrigation's own loading, where ``_cell(...).split("|")``
    always yields >= 1 segment because the value is always a real string.
    A single parsed attempt that stated no labels at all must read as
    ``[{}]`` (one segment), never ``[]`` (zero segments) -- the latter used
    to make parse_decision see attempt_skills (1 segment) and attempt_labels
    (0 segments) disagree and raise a spurious length-mismatch error."""
    assert parse_attempt_labels("") == [{}]
    assert parse_attempt_labels(None) == [{}]
    assert parse_attempt_labels(float("nan")) == [{}]


def test_first_stated_labels_uses_initial_when_stated_there():
    stated = first_stated_labels("TP_LABEL=H|CP_LABEL=M", "TP_LABEL=H,CP_LABEL=M")
    assert stated == {"TP_LABEL": "H", "CP_LABEL": "M"}


def test_first_stated_labels_falls_back_to_a_later_attempt():
    """Attempt 0 left CP_LABEL blank; attempt 1 stated it. The construct is
    first stated at attempt 1, not never-stated -- the same rule irrigation's
    own _first_stated and the appraisal freeze use."""
    initial = "TP_LABEL=H|CP_LABEL="
    attempts = "TP_LABEL=H,CP_LABEL=|TP_LABEL=H,CP_LABEL=M"
    stated = first_stated_labels(initial, attempts)
    assert stated == {"TP_LABEL": "H", "CP_LABEL": "M"}


def test_first_stated_labels_never_overwrites_an_already_stated_value():
    """A construct stated at attempt 0 is frozen there even if a later
    attempt restates it differently -- first stated, not last stated."""
    initial = "TP_LABEL=H|CP_LABEL=M"
    attempts = "TP_LABEL=H,CP_LABEL=M|TP_LABEL=L,CP_LABEL=L"
    stated = first_stated_labels(initial, attempts)
    assert stated == {"TP_LABEL": "H", "CP_LABEL": "M"}


def test_first_stated_labels_stays_blank_when_nothing_ever_states_it():
    stated = first_stated_labels("TP_LABEL=|CP_LABEL=", "TP_LABEL=,CP_LABEL=|TP_LABEL=,CP_LABEL=")
    assert stated.get("TP_LABEL", "") == ""
    assert stated.get("CP_LABEL", "") == ""


# ---------------------------------------------------------------------------
# Decision / parse_decision: the step-back properties and the light
# integrity checks (item 37e; mirrors irrigation's own parse_decision).
# ---------------------------------------------------------------------------

def test_decision_last_parsed_proposal_steps_back_past_unparsed_tail():
    row = _row("L", "M", "L", "M", final_skill="do_nothing",
               initial_skill="elevate_house", attempt_skills="elevate_house|",
               attempt_labels="TP_LABEL=L,CP_LABEL=M|",
               retry_count=1,
               status="REJECTED_FALLBACK")
    d = parse_decision(row, "test")
    assert d.last_attempt_unparsed is True
    assert d.last_parsed_proposal == "elevate_house"
    assert d.final_proposal is None       # the literal last attempt never parsed


def test_decision_last_parsed_proposal_is_the_literal_last_when_it_parsed():
    row = _row("H", "M", "H", "M", "do_nothing")
    d = parse_decision(row, "test")
    assert d.last_attempt_unparsed is False
    assert d.last_parsed_proposal == d.final_proposal == "do_nothing"


def test_parse_decision_raises_on_status_execution_path_mismatch():
    row = _row("H", "M", "H", "M", "do_nothing")
    row["execution_path"] = "aborted"  # status is APPROVED, not ABORTED -- mismatch
    with pytest.raises(MetricsError, match="execution_path"):
        parse_decision(row, "test")


def test_parse_decision_raises_on_attempt_length_mismatch():
    """attempt_skills/attempt_labels both hold 2 attempts, but retry_count
    says 0 (expects exactly 1 attempt): item 37e's
    ``len(attempt_skills) == retry_count + 1`` check."""
    row = _row("H", "M", "H", "M", "do_nothing",
               attempt_skills="do_nothing|do_nothing",
               attempt_labels="TP_LABEL=H,CP_LABEL=M|TP_LABEL=H,CP_LABEL=M",
               retry_count=0)
    with pytest.raises(MetricsError, match="retry_count"):
        parse_decision(row, "test")


def test_parse_decision_raises_on_initial_skill_mismatch():
    row = _row("H", "M", "H", "M", "do_nothing", initial_skill="relocate")
    with pytest.raises(MetricsError, match="initial_skill"):
        parse_decision(row, "test")


def test_non_aborted_row_with_no_parsed_attempt_raises():
    """Item 37e: 'a non-aborted row with no parsed attempt raises' --
    mirrors irrigation's own parse_decision ('first attempt did not parse on
    a non-ABORTED row')."""
    rows = [_row("", "", "", "", final_skill="do_nothing",
                 initial_skill=float("nan"), attempt_skills="|",
                 attempt_labels="|", retry_count=1, status="REJECTED_FALLBACK")]
    with pytest.raises(MetricsError, match="first attempt did not parse"):
        compute_flood_ibr_v2(pd.DataFrame(rows))


def test_single_parsed_attempt_with_no_labels_at_all_parses_cleanly():
    """A single parsed attempt whose attempt_labels cell is blank
    (nothing stated at all) must parse like an ordinary row with every
    label missing -- not raise a length-mismatch (fixed by
    parse_attempt_labels treating "" as one empty segment, not zero)."""
    row = _row("", "", "", "", "do_nothing",
               attempt_labels="", initial_skill="do_nothing")
    row["final_labels"] = ""  # the single attempt stated nothing at all
    r = compute_flood_ibr_v2(pd.DataFrame([row]))
    assert r.n == 1
    assert r.violations == 0
    assert r.first_tp_missing == 1
    assert r.first_cp_missing == 1


def test_blank_attempt_labels_via_real_csv_file_on_disk(tmp_path):
    """The real-file path: a genuinely blank CSV cell for
    attempt_labels (not an explicit NaN object built in Python) must still
    parse cleanly once read back with ``pd.read_csv`` -- this is the exact
    path a real household_governance_audit.csv run takes, not the
    in-memory DataFrame the other tests build directly."""
    blank_row = _row("", "", "", "", "do_nothing", attempt_labels="", initial_skill="do_nothing")
    blank_row["final_labels"] = ""  # the single attempt stated nothing at all
    rows = [
        blank_row,
        _row("H", "M", "H", "M", "do_nothing"),
    ]
    csv_path = tmp_path / "household_governance_audit.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    # The real CLI/analysis path: pd.read_csv with keep_default_na=False,
    # exactly like flood_ibr_v2._load_csv does, so a blank cell on disk
    # reads back as "" rather than NaN.
    df = pd.read_csv(csv_path, keep_default_na=False)
    r = compute_flood_ibr_v2(df)
    assert r.n == 2
    assert r.violations == 1  # only the second (H/M, do_nothing) row violates R1


def _required_columns():
    return ["initial_skill", "initial_labels", "final_labels",
            "attempt_skills", "attempt_labels", "executed_skill",
            "appraisal_relabeled", "retry_count", "execution_path", "status"]


def test_requires_columns():
    with pytest.raises(KeyError, match="attempt_columns"):
        compute_flood_ibr_v2(pd.DataFrame({"final_skill": ["do_nothing"]}))


def test_header_only_csv_raises():
    """A header-only CSV (every required column present, zero data
    rows) must raise, matching irrigation's own ``ibr_metrics`` -- a mean of
    zero decisions is not a measurement, never a silent all-zero result."""
    with pytest.raises(MetricsError, match="no decisions"):
        compute_flood_ibr_v2(pd.DataFrame(columns=_required_columns()))


def test_r1_violation_high_threat_adequate_coping_do_nothing():
    """R1 (redefined item 10): threat H/VH AND coping NOT VL/L, action
    do_nothing. Coping M (not low) -- this is PMT's non-protective-response
    case and must count."""
    rows = [_row("H", "M", "H", "M", "do_nothing")]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.violations == 1 and r.components == {"R1": 1, "R3": 0, "R4": 0}
    assert r.ibr_pct == 100.0


def test_r1_does_not_fire_when_coping_is_low():
    """The OLD R1 (threat alone) would have fired here; the redefined R1
    (item 10) must not, because coping VL/L takes the agent out of PMT's
    non-protective-response pattern (Grothmann and Reusswig 2006 p.106)."""
    rows = [_row("H", "L", "H", "L", "do_nothing")]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.violations == 0
    assert r.ibr_pct == 0.0


def test_r3_relocate_low_threat():
    rows = [_row("VL", "M", "VL", "M", "relocate")]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.components == {"R1": 0, "R3": 1, "R4": 0}


def test_r4_elevate_low_threat():
    rows = [_row("L", "H", "L", "H", "elevate_house")]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.components == {"R1": 0, "R3": 0, "R4": 1}


def test_compliant_rows_never_counted():
    rows = [
        _row("M", "M", "M", "M", "do_nothing"),
        _row("H", "H", "H", "H", "elevate_house"),
        _row("VH", "M", "VH", "M", "buy_insurance"),
    ]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.violations == 0 and r.ibr_pct == 0.0


def test_missing_label_never_counts_as_violation():
    """A blank/absent appraisal must never be read as a middle value that
    happens to clear the rule -- it must simply not match any bin, exactly
    like the live engine's get_label() -> "" -> label_matches() -> False."""
    rows = [_row("", "", "", "", "do_nothing")]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.violations == 0
    assert r.first_tp_missing == 1 and r.first_cp_missing == 1


def test_first_tp_cp_missing_counts_aborted_rows_too():
    """Like irrigation's own first_wsa_missing: an ABORTED row has no
    first-stated labels at all, so it counts toward both missing tallies,
    same as irrigation counts an aborted d.first_wsa (None) into
    first_wsa_missing."""
    rows = [_aborted_row("ABORTED"), _row("H", "M", "H", "M", "do_nothing")]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.first_tp_missing == 1  # only the aborted row is missing TP
    assert r.first_cp_missing == 1  # only the aborted row is missing CP


def test_primary_uses_first_stated_label_not_just_attempt_zero():
    """Attempt 0 left TP_LABEL blank; attempt 1 (a retry) stated H, then
    the agent's last parsed attempt still proposes do_nothing with adequate
    coping stated throughout -- the PRIMARY must read H as first-stated and
    count the R1 violation, even though initial_labels alone is blank."""
    rows = [_row("", "M", "H", "M", "do_nothing",
                 attempt_labels="TP_LABEL=,CP_LABEL=M|TP_LABEL=H,CP_LABEL=M",
                 attempt_skills="do_nothing|do_nothing", retry_count=1)]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.violations == 1
    assert r.components == {"R1": 1, "R3": 0, "R4": 0}


def test_first_proposal_share_now_uses_first_stated_labels_item_37e():
    """Item 37e overrides the earlier definition outright: first_proposal_share
    judges attempt 0's OWN action against the FIRST-STATED labels (which may
    read past attempt 0), not attempt 0's own literal label -- matching
    irrigation's own ``ibr_first_proposal_*`` (judged against ``first_wsa``,
    which is itself first-stated). Same row as the primary's own
    first-stated test above: attempt 0's action (do_nothing) is judged
    against the first-stated H (from attempt 1) + the coping M stated
    already at attempt 0 -> an R1 violation, even though attempt 0's own
    TP_LABEL cell was blank."""
    rows = [_row("", "M", "H", "M", "do_nothing",
                 attempt_labels="TP_LABEL=,CP_LABEL=M|TP_LABEL=H,CP_LABEL=M",
                 attempt_skills="do_nothing|do_nothing", retry_count=1)]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.first_proposal_violations == 1


def test_relabel_hides_violation_from_primary_but_shows_in_final_label_share():
    """First attempt: threat H, coping M, agent proposes do_nothing (R1
    violation). Suppose the agent LOWERS its stated threat to M on the
    final attempt while STILL proposing do_nothing (the appraisal freeze,
    which the real engine enforces at validation time, does not change what
    the model itself writes into its own final reasoning -- see
    broker/core/_appraisal_freeze.py). The PRIMARY (frozen first-stated
    label) must still count this as a violation; the final-label share
    (judged on the literal last attempt's OWN final label) must NOT, since M
    is not H/VH -- that gap IS the whole point of reporting both."""
    rows = [_row("H", "M", "M", "M", "do_nothing", initial_skill="do_nothing",
                 attempt_skills="do_nothing|do_nothing",
                 attempt_labels="TP_LABEL=H,CP_LABEL=M|TP_LABEL=M,CP_LABEL=M",
                 retry_count=1)]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.violations == 1                # primary: judged on first-stated H -> R1 fires
    assert r.final_label_violations == 0     # literal last attempt judged on its own final M -> no rule
    assert r.relabeled_decisions == 1 and r.relabel_rate_pct == 100.0  # 1 relabelled / 1 retried


def test_relabel_rate_is_a_share_of_retried_decisions_not_all_rows():
    """3 rows, only 1 retried and relabelled; relabel_rate_pct must be
    50.0 (1/2 of the RETRIED share), not 1/3 of all rows. Irrigation's own
    convention (Decision.retried / relabel_rate_pct). Reads the
    appraisal_relabeled column directly (auto-computed by _row() from
    initial vs final labels, just like the real engine would write it)."""
    rows = [
        _row("H", "M", "M", "M", "do_nothing",  # retried AND relabelled
             attempt_skills="do_nothing|do_nothing",
             attempt_labels="TP_LABEL=H,CP_LABEL=M|TP_LABEL=M,CP_LABEL=M",
             retry_count=1),
        _row("M", "M", "M", "M", "do_nothing"),  # never retried, trivially not relabelled
        _row("L", "M", "L", "M", "buy_insurance",  # retried but NOT relabelled (same label both times)
             initial_skill="elevate_house",
             attempt_skills="elevate_house|buy_insurance",
             attempt_labels="TP_LABEL=L,CP_LABEL=M|TP_LABEL=L,CP_LABEL=M",
             retry_count=1),
    ]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.retried_decisions == 2
    assert r.relabeled_decisions == 1
    assert r.relabel_rate_pct == pytest.approx(50.0)


def test_relabel_rate_is_none_not_zero_when_nothing_retried():
    """Irrigation's own ``_pct`` returns None (not 0.0) for a
    zero-denominator share -- a decision set where nothing ever retried has
    no relabel rate to report, not a rate of 0%."""
    rows = [_row("M", "M", "M", "M", "do_nothing")]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.retried_decisions == 0
    assert r.relabel_rate_pct is None


# ---------------------------------------------------------------------------
# REJECTED (plain, not _FALLBACK): a REAL, PARSEABLE proposal exhausts
# retries. The literal last attempt parsed -- this is the status the live
# engine actually writes for this scenario. Flood's on_retry_exhausted is
# `default` (spec item 37b), so the registry default still executes.
# ---------------------------------------------------------------------------

def test_executed_violation_share_drops_on_rejected_parseable_proposal():
    """Retries exhausted on a PARSEABLE blocked proposal (elevate_house,
    R4-violating on initial threat L): status is plain REJECTED (not
    REJECTED_FALLBACK -- see broker/core/skill_broker_engine.py
    _build_approved_skill: is_generic_fallback is False when skill_proposal
    parsed). The registry default (do_nothing) executes instead (read
    directly from the executed_skill column); the PRIMARY still counts the
    proposal-based violation, the executed-violation share must NOT, because
    do_nothing under threat L violates no rule."""
    rows = [_row("L", "M", "L", "M", "elevate_house", status="REJECTED")]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.violations == 1                 # proposal-based primary: R4 fires
    assert r.executed_violations == 0         # do_nothing executed instead: no rule fires
    assert r.last_attempt_unparsed_n == 0     # the literal last attempt DID parse (plain REJECTED)


def test_executed_violation_share_counts_when_default_itself_violates():
    """If the registry default (do_nothing) executes under a HIGH threat +
    adequate coping first attempt, that itself is an R1 violation that DID
    reach the simulated world."""
    rows = [_row("H", "M", "H", "M", "relocate", status="REJECTED")]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    # proposal was relocate under threat H -> no R3 (R3 needs LOW threat); not a
    # proposal-based violation, but the EXECUTED do_nothing under H/adequate
    # coping is an R1 violation that reached the world.
    assert r.violations == 0
    assert r.executed_violations == 1


def test_r1_executed_can_exceed_primary_r1():
    """Corrected note: an earlier definition of this module claimed the
    executed share can never EXCEED the primary's R1 contribution. It can:
    here the agent's last PARSED proposal is elevate_house (not R1-shaped:
    R1 needs do_nothing), so the primary has no R1 violation at all, but the
    last attempt never parsed, so the registry default (do_nothing)
    executes -- and under the first-stated threat H + adequate coping M,
    that default itself is a fresh R1 violation the primary's own judged
    action never had."""
    rows = [_row("H", "M", "H", "M", final_skill="do_nothing",
                 initial_skill="elevate_house", attempt_skills="elevate_house|",
                 attempt_labels="TP_LABEL=H,CP_LABEL=M|",
                 retry_count=1,
                 status="REJECTED_FALLBACK")]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.violations == 0                 # last parsed proposal: elevate_house, not R1-shaped
    assert r.components == {"R1": 0, "R3": 0, "R4": 0}
    assert r.executed_violations == 1         # do_nothing executed (fallback) IS an R1 violation
    assert r.executed_violations > r.violations


# ---------------------------------------------------------------------------
# REJECTED_FALLBACK (realistic): the LAST attempt never parsed, so
# final_skill IS the registry default, not a proposal. attempt_skills
# carries the real history; Decision.last_parsed_proposal must recover the
# agent's last PARSED proposal from it, not trust final_skill.
# ---------------------------------------------------------------------------

def test_rejected_fallback_primary_reads_attempt_skills_not_final_skill():
    """Attempt 0 proposed elevate_house (threat L -> R4-violating); attempt
    1 (a governance retry) never parsed, so the engine's own
    is_generic_fallback branch fires: final_skill becomes the registry
    default ("do_nothing"), status is REJECTED_FALLBACK, and attempt_skills
    records "elevate_house|" (the trailing empty segment is the unparsed
    retry). Trusting final_skill directly would read this as a compliant
    do_nothing proposal (0 violations); stepping back through attempt_skills
    recovers the real last PARSED proposal (elevate_house) and correctly
    counts the primary violation -- found ONLY by stepping back
    (ibr_stepback_violations_n)."""
    rows = [_row("L", "M", "L", "M", final_skill="do_nothing",
                 initial_skill="elevate_house", attempt_skills="elevate_house|",
                 attempt_labels="TP_LABEL=L,CP_LABEL=M|",
                 retry_count=1,
                 status="REJECTED_FALLBACK")]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.last_attempt_unparsed_n == 1
    assert r.violations == 1             # R4, from the real last-parsed proposal
    assert r.components == {"R1": 0, "R3": 0, "R4": 1}
    assert r.ibr_stepback_violations_n == 1  # the literal final_skill (do_nothing) alone finds nothing


def test_rejected_fallback_executed_share_is_the_default_regardless():
    """Same row as above: the EXECUTED action is still the registry default
    (do_nothing, read directly from the executed_skill column) -- that part
    of the engine's behaviour is unaffected by this fix -- and do_nothing
    under threat L violates no rule."""
    rows = [_row("L", "M", "L", "M", final_skill="do_nothing",
                 initial_skill="elevate_house", attempt_skills="elevate_house|",
                 attempt_labels="TP_LABEL=L,CP_LABEL=M|",
                 retry_count=1,
                 status="REJECTED_FALLBACK")]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.executed_violations == 0


def test_final_label_share_counts_unparsed_last_attempt_as_no_violation_not_excluded():
    """Item 37e: the final-label share no longer excludes a REJECTED_FALLBACK
    row from its own denominator -- it divides by n like every other share.
    The row still contributes zero to the numerator: its literal last
    attempt's action is None (unparsed), which _violates() never matches --
    that falls straight out of the definition, no special-casing needed."""
    rows = [
        _row("L", "M", "L", "M", final_skill="do_nothing",
             initial_skill="elevate_house", attempt_skills="elevate_house|",
             attempt_labels="TP_LABEL=L,CP_LABEL=M|",
             retry_count=1,
             status="REJECTED_FALLBACK"),
        _row("M", "M", "M", "M", "do_nothing"),  # ordinary compliant row
    ]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.n == 2
    assert r.final_label_violations == 0
    assert r.ibr_final_label_pct == 0.0


# ---------------------------------------------------------------------------
# ABORTED rows: treated exactly as irrigation's v3_metrics.py (ibr_metrics)
# treats them -- in n, never a violation, tallied separately. Needs
# execution_path (corrected_status_columns) -- without it this row would
# not exist in a real corpus at all; the synthetic fixture still names the
# column so compute_flood_ibr_v2's required-column check passes.
# ---------------------------------------------------------------------------

def _aborted_row(status="ABORTED"):
    """SkillBrokerEngine._write_aborted_sentinel_trace never writes
    initial_skill/initial_labels/attempt_skills/attempt_labels at all; a CSV
    row therefore has them blank (NaN after pd.read_csv). It DOES write
    executed_skill="" and (attempt_columns on) appraisal_relabeled=
    "unobserved" -- neither is ever read by parse_decision for an ABORTED
    row, but they are set here to match the real sentinel row exactly."""
    return {
        "agent_id": "H0001", "year": 1,
        "initial_skill": float("nan"),
        "initial_labels": float("nan"),
        "final_labels": float("nan"),
        "attempt_skills": float("nan"),
        "attempt_labels": float("nan"),
        "executed_skill": "",
        "appraisal_relabeled": "unobserved",
        "retry_count": 0,
        "status": status,
        "execution_path": "aborted",
    }


def test_aborted_row_counted_in_denominator_never_as_violation():
    rows = [
        _row("H", "M", "H", "M", "do_nothing"),  # a real R1 violation
        _aborted_row("ABORTED"),
    ]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.n == 2
    assert r.aborted_count == 1
    assert r.violations == 1             # only the real row
    assert r.ibr_pct == pytest.approx(50.0)   # 1 violation / 2 total decisions
    assert r.first_proposal_violations == 1
    assert r.executed_violations == 1
    assert r.final_label_violations == 1


def test_aborted_exception_status_also_counted():
    rows = [_aborted_row("ABORTED_EXCEPTION")]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.n == 1
    assert r.aborted_count == 1
    assert r.violations == 0
    assert r.ibr_pct == 0.0


def test_denominator_is_every_row_pooled():
    rows = [
        _row("H", "M", "H", "M", "do_nothing"),          # R1 violation
        _row("M", "M", "M", "M", "do_nothing"),           # compliant
        _row("VL", "M", "VL", "M", "relocate"),           # R3 violation
    ]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.n == 3
    assert r.violations == 2
    assert r.ibr_pct == pytest.approx(200 / 3)


def test_first_proposal_share_uses_the_first_attempts_own_action():
    """First attempt proposed elevate_house under threat L (an R4
    violation); on retry the agent switched to buy_insurance, which is what
    both the last proposal and the executed action now are (labels never
    change between attempts here, so first-stated == attempt 0's own
    literal label -- this row is unaffected by the item 37e first-proposal
    redefinition). The PRIMARY and the executed-violation share must NOT
    fire (the final/executed action is compliant); the first-proposal share
    must fire, because it asks "what did the agent's own first, ungoverned
    instinct violate.\""""
    rows = [_row("L", "M", "L", "M", "buy_insurance", initial_skill="elevate_house",
                 attempt_skills="elevate_house|buy_insurance",
                 attempt_labels="TP_LABEL=L,CP_LABEL=M|TP_LABEL=L,CP_LABEL=M",
                 retry_count=1)]
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.violations == 0
    assert r.executed_violations == 0
    assert r.first_proposal_violations == 1
    assert r.ibr_first_proposal_pct == 100.0


def test_first_proposal_share_equals_primary_when_no_retry_happened():
    """A decision with no retry: initial_skill == final_skill, and the
    first-proposal share and the primary read the same thing (both the
    first attempt's own action, both judged on the first-stated label)."""
    rows = [_row("H", "M", "H", "M", "do_nothing")]  # initial_skill defaults to final_skill
    r = compute_flood_ibr_v2(pd.DataFrame(rows))
    assert r.violations == r.first_proposal_violations == 1
    assert r.ibr_pct == r.ibr_first_proposal_pct == 100.0


def _result(**overrides):
    base = dict(
        n=10, violations=1, ibr_pct=10.0,
        first_proposal_violations=1, ibr_first_proposal_pct=10.0,
        executed_violations=0, ibr_executed_pct=0.0,
        final_label_violations=0, ibr_final_label_pct=0.0,
        relabeled_decisions=0, retried_decisions=5, relabel_rate_pct=0.0,
        components={"R1": 1, "R3": 0, "R4": 0},
        aborted_count=0, last_attempt_unparsed_n=0, ibr_stepback_violations_n=0,
        first_tp_missing=0, first_cp_missing=0,
    )
    base.update(overrides)
    return FloodIbrV2(**base)


def test_aggregate_over_seeds_mean_and_range():
    a = _result()
    b = _result(violations=3, ibr_pct=30.0, first_proposal_violations=2, ibr_first_proposal_pct=20.0,
                executed_violations=1, ibr_executed_pct=10.0,
                final_label_violations=1, ibr_final_label_pct=10.0,
                relabeled_decisions=1, relabel_rate_pct=10.0,
                components={"R1": 2, "R3": 1, "R4": 0})
    agg = aggregate_over_seeds([a, b])
    assert agg["ibr_pct"]["mean"] == pytest.approx(20.0)
    assert agg["ibr_pct"]["min"] == pytest.approx(10.0)
    assert agg["ibr_pct"]["max"] == pytest.approx(30.0)
    assert agg["ibr_pct"]["n_seeds"] == 2
    assert agg["ibr_first_proposal_pct"]["mean"] == pytest.approx(15.0)
    assert agg["ibr_final_label_pct"]["mean"] == pytest.approx(5.0)


def test_aggregate_over_seeds_skips_none_relabel_rate():
    """A run that retried nothing has relabel_rate_pct=None; averaging
    it in as 0.0 would understate the real rate among runs that DID retry.
    aggregate_over_seeds must skip it, not treat it as zero."""
    a = _result(relabel_rate_pct=None, retried_decisions=0)
    b = _result(relabel_rate_pct=40.0, retried_decisions=5, relabeled_decisions=2)
    agg = aggregate_over_seeds([a, b])
    assert agg["relabel_rate_pct"]["mean"] == pytest.approx(40.0)
    assert agg["relabel_rate_pct"]["n_seeds"] == 1


def test_aggregate_over_seeds_all_none_relabel_rate_reports_none_not_crash():
    a = _result(relabel_rate_pct=None, retried_decisions=0)
    b = _result(relabel_rate_pct=None, retried_decisions=0)
    agg = aggregate_over_seeds([a, b])
    assert agg["relabel_rate_pct"] == {"mean": None, "min": None, "max": None, "n_seeds": 0}


def test_aggregate_over_seeds_rejects_empty():
    with pytest.raises(ValueError):
        aggregate_over_seeds([])
