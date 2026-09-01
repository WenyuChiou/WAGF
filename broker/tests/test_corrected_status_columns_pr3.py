"""PR-3: ``global_config.audit.corrected_status_columns`` (default OFF).

Five audit-plane defects share one root cause: the CSV reports the BLOCKED
proposal as if it were the outcome, and reports category/emotion placeholders
as if they were observations. Each is corrected only under this flag, because
each either adds a column, adds a row, or CHANGES the values of an existing
column — and every published corpus must still reproduce with the flag absent.

What is under test here:

1. flag-OFF byte identity — fieldnames and cell values, proven by writing the
   same traces through a config that PREDATES the getter (the pre-PR-3 world)
   and one that has it and returns False, then comparing with the project's
   own ``broker.tools.compare_audit_csv``;
2. ``executed_skill`` / ``execution_path`` truth on APPROVED, plain-REJECTED
   and parse-failure rows;
3. the ABORTED sentinel that conserves the agent x year row count;
4. ``get_rule_breakdown``'s tier/validator-name fallback;
5. ``fallback_activated`` derived from what EXECUTED;
6. ``mem_top_emotion`` / ``mem_top_source`` marked ``unobserved`` rather than
   wearing the ``neutral`` / ``personal`` costume of a real observation.
"""
from __future__ import annotations

import csv
from types import SimpleNamespace

import pytest

from broker.components.analytics.audit import (
    AuditConfig,
    GenericAuditWriter,
    audit_coverage,
    compute_csv_fieldnames,
    trace_to_csv_row,
)
from broker.core._audit_helpers import AuditMixin, UNOBSERVED
from broker.interfaces.skill_types import SkillOutcome, ValidationResult
from broker.tools.compare_audit_csv import compare
from broker.utils.agent_config import AgentTypeConfig
from broker.validators.governance import (
    get_rule_breakdown, get_uncategorised_rules, reset_uncategorised_rules,
)


# ---------------------------------------------------------------------------
# Config getter
# ---------------------------------------------------------------------------

def _cfg(global_config=None) -> AgentTypeConfig:
    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = {"global_config": global_config or {}}
    return cfg


def test_getter_default_off():
    assert _cfg().get_audit_corrected_status_columns() is False
    assert _cfg({"audit": {}}).get_audit_corrected_status_columns() is False


def test_getter_explicit_on():
    assert _cfg(
        {"audit": {"corrected_status_columns": True}}
    ).get_audit_corrected_status_columns() is True


def test_getter_non_dict_audit_block_is_off():
    """A malformed scalar block reads as OFF and never raises — a config typo
    must not silently change what the audit columns mean."""
    assert _cfg({"audit": "yes"}).get_audit_corrected_status_columns() is False


def test_getter_is_independent_of_the_other_audit_flags():
    on = _cfg({"audit": {"corrected_status_columns": True}})
    assert on.get_audit_corrected_status_columns() is True
    assert on.get_audit_executed_columns() is False
    assert on.get_audit_initial_proposal_columns() is False


# ---------------------------------------------------------------------------
# Test host — the AuditMixin with a swappable config
# ---------------------------------------------------------------------------

class _StubWriter:
    def __init__(self):
        self.traces = []

    def write_trace(self, agent_type, trace, history=None):
        self.traces.append((agent_type, trace))


class _Host(AuditMixin):
    """AuditMixin with a minimal config.

    ``flag=None`` omits the getter entirely, reproducing an engine wired with
    a config object that predates PR-3 — the pre-edit baseline.
    """

    def __init__(self, flag=None):
        self.audit_writer = _StubWriter()
        fields = {"get_log_fields": lambda agent_type: []}
        if flag is not None:
            fields["get_audit_corrected_status_columns"] = lambda: flag
        self.config = SimpleNamespace(**fields)


def _approved(name: str, status: str):
    return SimpleNamespace(
        skill_name=name, approval_status=status, execution_mapping={},
    )


def _write(host, *, approved, outcome, executed_skill, executed_via_fallback,
           execution_path, memory_pre=None, history=None):
    host._write_audit_trace(
        agent_type="household", context={}, run_id="r", step_id="Y1",
        timestamp="2026-09-01T00:00:00", env_context={"current_year": 1},
        seed=42, agent_id="A1", all_valid=(outcome is SkillOutcome.APPROVED),
        prompt="p", raw_output="o", context_hash="h",
        memory_pre=memory_pre or [], memory_post=[], skill_proposal=None,
        approved_skill=approved, execution_result=None, outcome=outcome,
        retry_count=2, format_retry_count=0, total_llm_stats={},
        all_validation_history=history or [],
        executed_skill=executed_skill,
        executed_via_fallback=executed_via_fallback,
        execution_path=execution_path,
    )
    traces = getattr(host.audit_writer, "traces", None)
    return traces[-1][1] if traces else None


_REJECTED_CASE = dict(
    approved=_approved("elevate", "REJECTED"),
    outcome=SkillOutcome.REJECTED,
    executed_skill="do_nothing",
    executed_via_fallback=True,
    execution_path="rejected_default",
)


# ---------------------------------------------------------------------------
# 1. Flag-OFF byte identity
# ---------------------------------------------------------------------------

def test_flag_off_adds_no_trace_keys():
    trace = _write(_Host(flag=False), **_REJECTED_CASE)
    for key in ("executed_skill", "executed_via_fallback", "execution_path"):
        assert key not in trace, f"{key} leaked into a flag-OFF trace"


def test_flag_off_row_has_no_execution_path_column():
    row = trace_to_csv_row(_write(_Host(flag=False), **_REJECTED_CASE))
    assert "execution_path" not in row
    assert "execution_path" not in compute_csv_fieldnames([row])


def _write_csv(tmp_path, name, host):
    """Drive the real audit writer with one trace of each interesting shape."""
    out = tmp_path / name
    writer = GenericAuditWriter(AuditConfig(output_dir=str(out),
                                            experiment_name="pr3"))
    host.audit_writer = writer
    _write(host, **_REJECTED_CASE, memory_pre=[{"content": "flooded once"}])
    _write(host, approved=_approved("elevate", "APPROVED"),
           outcome=SkillOutcome.APPROVED, executed_skill="elevate",
           executed_via_fallback=False, execution_path="approved",
           memory_pre=[{"content": "x", "emotion": "fear", "source": "news"}])
    writer.finalize()
    return out / "household_governance_audit.csv"


def test_flag_off_csv_identical_to_pre_pr3_config(tmp_path):
    """The load-bearing byte-identity proof.

    ``reference`` is written through a config object with NO
    ``get_audit_corrected_status_columns`` at all — exactly what the code did
    before this PR. ``candidate`` is written through a config that HAS the
    getter and returns False. The project's own comparison tool must call
    them identical: same header, same row count, same normalised cells.
    """
    reference = _write_csv(tmp_path, "ref", _Host(flag=None))
    candidate = _write_csv(tmp_path, "cand", _Host(flag=False))

    assert compare(reference, candidate) == 0

    with reference.open(newline="", encoding="utf-8-sig") as fh:
        ref_rows = list(csv.DictReader(fh))
    with candidate.open(newline="", encoding="utf-8-sig") as fh:
        cand_rows = list(csv.DictReader(fh))
    # compare() normalises timestamps; assert the untouched columns too.
    assert [r["fallback_activated"] for r in ref_rows] == \
           [r["fallback_activated"] for r in cand_rows] == ["False", "False"]
    assert [r["mem_top_source"] for r in ref_rows] == ["personal", "news"]


def test_flag_off_sidecar_has_no_flag_key(tmp_path):
    """The sidecar is an audit artifact too: flag-OFF must not gain a key."""
    import json

    csv_path = _write_csv(tmp_path, "off", _Host(flag=False))
    sidecar = json.loads(
        (csv_path.parent / "household_governance_audit.schema.json")
        .read_text(encoding="utf-8")
    )
    assert "corrected_status_columns" not in sidecar
    assert set(sidecar) == {
        "audit_schema_version", "git_commit_short", "row_count", "fieldnames",
    }


# ---------------------------------------------------------------------------
# 2. executed_skill / execution_path truth
# ---------------------------------------------------------------------------

def test_flag_on_rejected_row_records_what_executed():
    """The defect this PR exists for: on a plain-REJECTED row ``final_skill``
    is the BLOCKED proposal while the registry default is what ran."""
    trace = _write(_Host(flag=True), **_REJECTED_CASE)
    assert trace["approved_skill"]["skill_name"] == "elevate"   # the lie
    assert trace["executed_skill"] == "do_nothing"              # the truth
    assert trace["execution_path"] == "rejected_default"

    row = trace_to_csv_row(trace)
    assert row["final_skill"] == "elevate"
    assert row["executed_skill"] == "do_nothing"
    assert row["execution_path"] == "rejected_default"
    assert "execution_path" in compute_csv_fieldnames([row])


def test_flag_on_approved_row_executed_equals_approved():
    trace = _write(
        _Host(flag=True), approved=_approved("elevate", "APPROVED"),
        outcome=SkillOutcome.APPROVED, executed_skill="elevate",
        executed_via_fallback=False, execution_path="approved",
    )
    assert trace["executed_skill"] == "elevate"
    assert trace["execution_path"] == "approved"
    assert trace["fallback_activated"] is False


def test_flag_on_parse_failure_row_is_labelled_fallback():
    trace = _write(
        _Host(flag=True), approved=_approved("do_nothing", "REJECTED_FALLBACK"),
        outcome=SkillOutcome.UNCERTAIN, executed_skill="do_nothing",
        executed_via_fallback=True, execution_path="fallback",
    )
    assert trace["execution_path"] == "fallback"
    assert trace["fallback_activated"] is True


def test_flag_on_implies_the_f3_executed_columns():
    """A run should not have to set two flags to get executed-stage truth."""
    trace = _write(_Host(flag=True), **_REJECTED_CASE)
    assert trace["executed_skill"] == "do_nothing"
    assert trace["executed_via_fallback"] is True


def test_sidecar_records_the_flag_when_on(tmp_path):
    import json

    _write_csv(tmp_path, "on", _Host(flag=True))
    sidecar = json.loads(
        (tmp_path / "on" / "household_governance_audit.schema.json").read_text(
            encoding="utf-8")
    )
    assert sidecar["corrected_status_columns"] is True
    assert "execution_path" in sidecar["fieldnames"]


# ---------------------------------------------------------------------------
# 3. fallback_activated derived from the EXECUTED skill
# ---------------------------------------------------------------------------

def test_fallback_activated_is_false_flag_off_on_a_row_where_fallback_ran():
    """Pins the documented pre-PR-3 behaviour so nobody 'fixes' it silently
    in a frozen corpus: the registry default ran, and the column says False."""
    trace = _write(_Host(flag=False), **_REJECTED_CASE)
    assert trace["fallback_activated"] is False


def test_fallback_activated_is_true_flag_on_when_the_default_ran():
    trace = _write(_Host(flag=True), **_REJECTED_CASE)
    assert trace["fallback_activated"] is True
    assert trace_to_csv_row(trace)["fallback_activated"] is True


def test_fallback_activated_stays_false_when_the_proposal_itself_ran():
    """``on_retry_exhausted: keep_proposal`` executes the agent's own blocked
    choice — nothing fell back, and the corrected column must not claim so."""
    trace = _write(
        _Host(flag=True), approved=_approved("elevate", "REJECTED"),
        outcome=SkillOutcome.REJECTED, executed_skill="elevate",
        executed_via_fallback=False, execution_path="rejected_proposal",
    )
    assert trace["fallback_activated"] is False
    assert trace["execution_path"] == "rejected_proposal"


# ---------------------------------------------------------------------------
# 4. get_rule_breakdown fallback
# ---------------------------------------------------------------------------

def _agent_validator_results():
    """The metadata shapes the PRODUCTION validator actually emits.

    Copied from ``broker/validators/agent/agent_validator.py``: identity and
    thinking rules set ``tier`` + a ``validator_name``, never ``category``.
    """
    return [
        ValidationResult(
            valid=False, validator_name="AgentValidator:thinking_error",
            errors=["[Rule: T1] blocked"],
            metadata={"tier": "Tier 2: Thinking", "rule": "thinking_error",
                      "rule_id": "T1", "rules_hit": ["T1"]},
        ),
        ValidationResult(
            valid=False, validator_name="AgentValidator:identity_error",
            errors=["[Rule: I1] blocked"],
            metadata={"tier": "Tier 1: Identity/Status",
                      "rule": "identity_error", "rule_id": "I1",
                      "rules_hit": ["I1"]},
        ),
        ValidationResult(
            valid=False, validator_name="AgentValidator:affordability",
            errors=["cannot afford"],
            metadata={"rules_hit": ["affordability"], "deterministic": True},
        ),
        ValidationResult(
            valid=False, validator_name="AgentValidator:format",
            errors=["Response missing required fields: x"],
            metadata={"rule": "format", "field": "json_structure"},
        ),
    ]


def test_rule_breakdown_default_is_structurally_zero():
    """Documents the defect: the production validator never sets
    ``metadata['category']``, so every bucket is zero however many fired."""
    breakdown = get_rule_breakdown(_agent_validator_results())
    assert breakdown == {"personal": 0, "social": 0, "thinking": 0,
                         "physical": 0, "semantic": 0}


def test_rule_breakdown_fallback_populates_from_tier_and_validator_name():
    breakdown = get_rule_breakdown(
        _agent_validator_results(), allow_metadata_fallback=True)
    assert breakdown["thinking"] == 1          # tier "Tier 2: Thinking"
    assert breakdown["personal"] == 1          # affordability only
    assert breakdown["social"] == 0
    assert breakdown["physical"] == 0
    # Two of the four results are deliberately UNCOUNTED. The format check is a
    # schema breach, and an identity rule is a precondition test ("has this
    # already happened") rather than a statement about who the agent is — the
    # PR-3 review call (P1c) is that a confident wrong bucket is worse than an
    # honest uncategorised count.
    assert sum(breakdown.values()) == 2


def test_identity_rules_are_uncategorised_not_personal():
    """P1c: the removed alias, pinned so it cannot come back by accident.

    An identity/precondition rule must reach NO bucket and must be reported by
    rule id in the uncategorised tally instead.
    """
    reset_uncategorised_rules()
    get_rule_breakdown(_agent_validator_results(), allow_metadata_fallback=True)
    uncat = get_uncategorised_rules()
    assert uncat["rules_uncategorised_total"] == 2
    assert "I1" in uncat["rules_uncategorised_ids"]      # the identity rule
    assert "format" in uncat["rules_uncategorised_ids"]  # the schema breach
    reset_uncategorised_rules()


def test_flag_off_breakdown_keeps_no_uncategorised_tally():
    """S3(i) / C1: the tally is kept ONLY on the inference path.

    With the fallback off, EVERY AgentValidator result is uncategorised by
    construction — that is the documented structural-zero defect, not a finding
    about this run. Tallying it there put a process-global counter on the
    byte-identity-locked path whose value was always 100% of the results, and
    made ``run_integrity.json`` carry a number that could not distinguish one
    flag-OFF run from another.
    """
    reset_uncategorised_rules()
    breakdown = get_rule_breakdown(_agent_validator_results())
    assert breakdown == {"personal": 0, "social": 0, "thinking": 0,
                         "physical": 0, "semantic": 0}
    uncat = get_uncategorised_rules()
    assert uncat["rules_uncategorised_total"] == 0
    assert uncat["rules_uncategorised_ids"] == []
    reset_uncategorised_rules()


def test_engine_construction_clears_a_previous_runs_tally():
    """C1(b): the tally is a module global, so a second run in one interpreter
    would otherwise report the FIRST run's rule ids as well as its own."""
    reset_uncategorised_rules()
    get_rule_breakdown(_agent_validator_results(), allow_metadata_fallback=True)
    assert get_uncategorised_rules()["rules_uncategorised_total"] == 2

    _engine(True)                                   # constructing an engine
    assert get_uncategorised_rules()["rules_uncategorised_total"] == 0
    assert get_uncategorised_rules()["rules_uncategorised_ids"] == []


def test_uncategorised_tally_survives_concurrent_recording():
    """C1(c): audit rows are built under ThreadPoolExecutor when workers > 1,
    and a bare ``+=`` on a module global loses updates — an UNDERCOUNT in the
    one field that exists to say the buckets are lying."""
    import threading as _threading

    reset_uncategorised_rules()
    results = _agent_validator_results()

    def _worker():
        for _ in range(200):
            get_rule_breakdown(results, allow_metadata_fallback=True)

    threads = [_threading.Thread(target=_worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # 4 threads x 200 calls x 2 uncategorised results each.
    assert get_uncategorised_rules()["rules_uncategorised_total"] == 1600
    reset_uncategorised_rules()


def test_rule_breakdown_explicit_category_still_wins():
    """Validators that DO set category keep their exact prior behaviour, so
    turning the fallback on can never re-label a correctly-tagged result."""
    results = [
        ValidationResult(
            valid=False, validator_name="AgentValidator:thinking_error",
            errors=["x"],
            # 'thinking' in the validator name, but the producer says physical
            metadata={"category": "physical", "tier": "Tier 2: Thinking"},
        ),
    ]
    assert get_rule_breakdown(results)["physical"] == 1
    assert get_rule_breakdown(
        results, allow_metadata_fallback=True)["physical"] == 1
    assert get_rule_breakdown(
        results, allow_metadata_fallback=True)["thinking"] == 0


def test_rule_breakdown_reaches_the_trace_only_under_the_flag():
    history = [_agent_validator_results()]
    off = _write(_Host(flag=False), **_REJECTED_CASE, history=history)
    on = _write(_Host(flag=True), **_REJECTED_CASE, history=history)
    assert off["rule_breakdown"]["thinking"] == 0
    assert on["rule_breakdown"]["thinking"] == 1
    assert trace_to_csv_row(on)["rules_thinking_hit"] == 1
    assert trace_to_csv_row(on)["rules_personal_hit"] == 1


# ---------------------------------------------------------------------------
# 5. mem_top_emotion / mem_top_source are not faked
# ---------------------------------------------------------------------------

_MEM_WITHOUT_KEYS = [{"content": "the river rose in 2019"}]
_MEM_WITH_KEYS = [{"content": "x", "emotion": "fear", "source": "news"}]


def test_absent_memory_emotion_is_marked_unobserved_under_the_flag():
    trace = _write(_Host(flag=True), **_REJECTED_CASE,
                   memory_pre=_MEM_WITHOUT_KEYS)
    row = trace_to_csv_row(trace)
    assert row["mem_top_emotion"] == UNOBSERVED
    assert row["mem_top_source"] == UNOBSERVED


def test_absent_memory_emotion_keeps_the_literals_with_the_flag_off():
    """Pins the pre-PR-3 behaviour that makes the released corpora what they
    are: an absent key is indistinguishable from a unanimous observation."""
    row = trace_to_csv_row(
        _write(_Host(flag=False), **_REJECTED_CASE,
               memory_pre=_MEM_WITHOUT_KEYS))
    assert row["mem_top_emotion"] == "neutral"
    assert row["mem_top_source"] == "personal"


@pytest.mark.parametrize("flag", [False, True])
def test_observed_memory_values_are_never_overwritten(flag):
    """The flag changes only the missing-key default. A run whose memory
    records carry real values reads identically under both settings."""
    row = trace_to_csv_row(
        _write(_Host(flag=flag), **_REJECTED_CASE, memory_pre=_MEM_WITH_KEYS))
    assert row["mem_top_emotion"] == "fear"
    assert row["mem_top_source"] == "news"


# ---------------------------------------------------------------------------
# 6. ABORTED sentinel + row-count conservation
# ---------------------------------------------------------------------------

def test_aborted_sentinel_row_shape(tmp_path):
    # Driven through the REAL writer: it is what turns the passed
    # ValidationResult into validation_issues, which is what makes the row
    # say why the step aborted rather than merely that it did.
    host = _Host(flag=True)
    host.audit_writer = GenericAuditWriter(
        AuditConfig(output_dir=str(tmp_path / "abort"), experiment_name="pr3"))
    host._write_aborted_sentinel_trace(
        agent_type="household", run_id="r", step_id=7,
        timestamp="2026-09-01T00:00:00", env_context={"current_year": 3},
        seed=42, agent_id="A9", raw_output="not json at all",
        format_retry_count=3,
    )
    trace = host.audit_writer._trace_buffer["household"][-1]
    row = trace_to_csv_row(trace)
    assert row["status"] == "ABORTED"
    assert row["executed_skill"] == ""
    assert row["execution_path"] == "aborted"
    assert row["final_skill"] == ""
    assert row["agent_id"] == "A9"
    assert row["year"] == 3
    assert row["format_retries"] == 3
    assert row["fallback_activated"] is False
    # The row must also say WHY, and must not claim the step validated.
    assert row["validated"] is False
    assert row["failed_rules"] == "parse_failure_terminal"
    assert "Parse error after retries" in row["error_messages"]


def test_aborted_sentinel_introduces_no_new_columns():
    """The sentinel must fit the existing schema: a row that adds columns
    would change the CSV header for every other row in the run."""
    normal = trace_to_csv_row(_write(_Host(flag=True), **_REJECTED_CASE))
    host = _Host(flag=True)
    host._write_aborted_sentinel_trace(
        agent_type="household", run_id="r", step_id=7, timestamp="t",
        env_context={"current_year": 3}, seed=42, agent_id="A9",
        raw_output="junk", format_retry_count=0,
    )
    sentinel = trace_to_csv_row(host.audit_writer.traces[-1][1])
    assert set(sentinel) - set(normal) == set()


def test_aborted_sentinel_never_raises_on_a_broken_writer():
    """A parse failure must not become a crashed run because the audit
    writer failed — the sentinel is a best-effort record, not a gate."""
    host = _Host(flag=True)

    class _Boom:
        def write_trace(self, *a, **k):
            raise OSError("disk full")

    host.audit_writer = _Boom()
    host._write_aborted_sentinel_trace(
        agent_type="household", run_id="r", step_id=1, timestamp="t",
        env_context={}, seed=42, agent_id="A1", raw_output="x",
        format_retry_count=0,
    )  # must return normally


def test_audit_coverage_counts_sentinels_in_the_row_total(tmp_path):
    out = tmp_path / "run"
    writer = GenericAuditWriter(AuditConfig(output_dir=str(out),
                                            experiment_name="pr3"))
    host = _Host(flag=True)
    host.audit_writer = writer
    for year in (1, 2):
        for agent in ("A1", "A2"):
            host._write_audit_trace(
                agent_type="household", context={}, run_id="r",
                step_id=f"{agent}-{year}", timestamp="t",
                env_context={"current_year": year}, seed=42, agent_id=agent,
                all_valid=False, prompt="p", raw_output="o", context_hash="h",
                memory_pre=[], memory_post=[], skill_proposal=None,
                approved_skill=_approved("elevate", "REJECTED"),
                execution_result=None, outcome=SkillOutcome.REJECTED,
                retry_count=0, format_retry_count=0, total_llm_stats={},
                all_validation_history=[], executed_skill="do_nothing",
                executed_via_fallback=True, execution_path="rejected_default",
            )
    # A3's year-1 step never parsed: without a sentinel it would vanish.
    host._write_aborted_sentinel_trace(
        agent_type="household", run_id="r", step_id="A3-1", timestamp="t",
        env_context={"current_year": 1}, seed=42, agent_id="A3",
        raw_output="junk", format_retry_count=3,
    )
    writer.finalize()

    coverage = audit_coverage(out)
    assert coverage["audit_rows"] == 5
    assert coverage["audit_aborted_rows"] == 1
    assert coverage["audit_agents"] == 3
    assert coverage["audit_years"] == 2
    assert coverage["audit_grid_rows"] == 6
    assert coverage["audit_rows_missing_vs_grid"] == 1
    # No expectation given -> the configured pair is "not measured", not zero.
    assert coverage["configured_grid_rows"] is None
    assert coverage["audit_rows_missing_vs_configured_grid"] is None
    assert audit_coverage(
        out, expected_rows=5)["audit_rows_missing_vs_configured_grid"] == 0
    assert audit_coverage(
        out, expected_rows=6)["audit_rows_missing_vs_configured_grid"] == 1
    # W1: the old `row_count_conserved` boolean is gone — it restated the line
    # above while dropping its "a shortfall is a number to explain" caveat.
    assert "row_count_conserved" not in coverage


def test_audit_coverage_reports_parse_layer_shares(tmp_path):
    out = tmp_path / "layers"
    out.mkdir()
    header = ["agent_id", "year", "status", "parse_layer"]
    rows = [
        ["A1", "1", "APPROVED", "enclosure+json"],
        ["A2", "1", "APPROVED", "enclosure+digit"],
        ["A3", "1", "REJECTED_FALLBACK", "default"],
        ["A4", "1", "APPROVED", "digit"],
    ]
    with (out / "household_governance_audit.csv").open(
            "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)

    coverage = audit_coverage(out)
    assert coverage["parse_layer_digit_share"] == 0.5
    assert coverage["parse_layer_default_share"] == 0.25
    assert coverage["parse_layer_distribution"] == {
        "default": 1, "digit": 1, "enclosure+digit": 1, "enclosure+json": 1,
    }


def test_audit_coverage_on_a_dir_without_a_csv_is_empty(tmp_path):
    assert audit_coverage(tmp_path) == {}


# ---------------------------------------------------------------------------
# 7. Engine wiring — the sentinel actually fires on the ABORTED early return
# ---------------------------------------------------------------------------

class _Sim:
    def __init__(self):
        self.executed = []

    def execute_skill(self, approved_skill):
        from broker.interfaces.skill_types import ExecutionResult

        self.executed.append(approved_skill.skill_name)
        return ExecutionResult(success=True, state_changes={})


class _Ctx:
    def build(self, agent_id, env_context=None, **kwargs):
        return {"agent_id": agent_id, "state": {}}

    def format_prompt(self, context):
        return "PROMPT"


def _engine(flag, *, proposal=None, blocking=False):
    """A real ``SkillBrokerEngine`` over stub parts.

    ``proposal=None`` makes the parser return nothing, so ``process_step``
    takes the ABORTED early return that sits BEFORE the single
    ``_write_audit_trace`` call site — the mechanism by which an unparsable
    step used to leave no row anywhere. ``blocking=True`` makes every
    validation fail, so a real proposal exhausts its retries and the registry
    default executes in its place.
    """
    from unittest.mock import MagicMock

    from broker.components.governance.registry import SkillRegistry
    from broker.core.skill_broker_engine import SkillBrokerEngine
    from broker.interfaces.skill_types import SkillDefinition, SkillProposal
    from broker.utils.model_adapter import UnifiedAdapter

    registry = SkillRegistry()
    for sid in ("elevate", "do_nothing"):
        registry.register(SkillDefinition(
            skill_id=sid, description=sid, eligible_agent_types=["*"],
            preconditions=[], institutional_constraints={},
            allowed_state_changes=[], implementation_mapping=sid,
        ))
    registry.set_default_skill("do_nothing")

    adapter = UnifiedAdapter.__new__(UnifiedAdapter)
    adapter.parse_output = lambda *_a, **_k: (
        SkillProposal(skill_name=proposal, agent_id="A1",
                      reasoning={"TP_LABEL": "H"}, parse_layer="json")
        if proposal else None
    )

    validators = []
    if blocking:
        validator = MagicMock()
        validator.validate.side_effect = lambda *_a, **_k: ValidationResult(
            valid=False, validator_name="AgentValidator:thinking_error",
            errors=["blocked"],
            metadata={"rules_hit": ["r1"], "tier": "Tier 2: Thinking",
                      "level": "ERROR"},
        )
        validators.append(validator)

    config = MagicMock()
    config.get_log_fields.return_value = []
    config.get_governance_retries.return_value = 1
    config.get_governance_max_reports.return_value = 1
    config.get_multi_skill_config.return_value = {}
    config.get_parsing_config.return_value = {}
    config.get_governance_on_retry_exhausted.return_value = "default"
    # A REAL bool, not a Mock: bool(MagicMock()) is True, and a flag this
    # consequential must never switch on because a test used a Mock config.
    config.get_audit_corrected_status_columns.return_value = flag

    sim = _Sim()
    engine = SkillBrokerEngine(
        skill_registry=registry, model_adapter=adapter, validators=validators,
        simulation_engine=sim, context_builder=_Ctx(), config=config,
    )
    engine.audit_writer = _StubWriter()
    return engine, sim


def _step(engine):
    return engine.process_step(
        agent_id="A1", step_id=1, run_id="r", seed=42,
        llm_invoke=lambda p: "raw", agent_type="household",
        env_context={"current_year": 1},
    )


def test_engine_flag_off_aborted_step_writes_no_row():
    """Pins the defect: with the flag off an unparsable step leaves NO row,
    so the arm with more parse failures silently runs a smaller denominator."""
    engine, sim = _engine(False)
    assert _step(engine).outcome is SkillOutcome.ABORTED
    assert engine.audit_writer.traces == []
    assert sim.executed == []


def test_engine_flag_on_aborted_step_writes_a_sentinel_row():
    engine, _ = _engine(True)
    assert _step(engine).outcome is SkillOutcome.ABORTED
    assert len(engine.audit_writer.traces) == 1
    row = trace_to_csv_row(engine.audit_writer.traces[0][1])
    assert row["status"] == "ABORTED"
    assert row["execution_path"] == "aborted"
    assert row["executed_skill"] == ""
    assert row["agent_id"] == "A1"
    assert row["year"] == 1


def test_engine_mock_config_does_not_enable_the_flag():
    """A MagicMock config returns a truthy Mock from every getter. The flag
    must read as OFF anyway — otherwise every mock-config test in the suite
    would silently run corrected semantics."""
    from unittest.mock import MagicMock

    from broker.core._audit_helpers import _corrected_status_flag

    assert _corrected_status_flag(MagicMock()) is False
    assert _corrected_status_flag(SimpleNamespace()) is False


def test_engine_resolves_execution_path_for_a_rejected_step():
    """End-to-end: a proposal blocked to exhaustion runs the registry default,
    and the row says ``rejected_default`` rather than leaving the reader to
    infer it from ``status`` plus the domain's on_retry_exhausted policy."""
    engine, sim = _engine(True, proposal="elevate", blocking=True)
    _step(engine)

    assert sim.executed == ["do_nothing"]
    row = trace_to_csv_row(engine.audit_writer.traces[0][1])
    assert row["final_skill"] == "elevate"          # the blocked proposal
    assert row["executed_skill"] == "do_nothing"    # what actually ran
    assert row["execution_path"] == "rejected_default"
    assert row["fallback_activated"] is True
    assert row["rules_thinking_hit"] >= 1           # tier fallback populated


# ---------------------------------------------------------------------------
# 8. PR-3 REVIEW FIXES
#
# Each test below pins one reviewer finding. The theme they share: a number
# that looked like a measurement and was not — a coverage grid derived from the
# rows it was meant to check, a sentinel row asserting a successful zero-token
# call, a flag that failed closed without saying so.
# ---------------------------------------------------------------------------

def _write_grid_csv(out, name, agents, years, status="APPROVED"):
    """Write a bare audit CSV with one row per agent-year actually present."""
    out.mkdir(parents=True, exist_ok=True)
    # No ``decision_source`` column: the live writer never emits one (P1a-2),
    # and a fixture that invents columns is how a dead code path stays green.
    header = ["agent_id", "year", "status", "parse_layer"]
    path = out / f"{name}_governance_audit.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for agent in range(agents):
            for year in range(1, years + 1):
                writer.writerow([f"A{agent:04d}", str(year), status, "json"])
    return path


# --- P0: the observed grid cannot see a run that stopped early --------------

def test_truncated_run_reports_the_missing_rows_against_the_configured_grid(tmp_path):
    """The P0 defect, at the size it actually bites.

    100 agents were configured for 13 years; the run died after year 9. Every
    number the CSV can produce on its own looks healthy — 900 rows filling a
    100 x 9 grid exactly — because the grid is DERIVED from the rows being
    checked. Only the configured expectation shows the 400 missing rows.
    """
    out = tmp_path / "truncated"
    _write_grid_csv(out, "household", agents=100, years=9)

    naive = audit_coverage(out)
    assert naive["audit_rows"] == 900
    assert naive["audit_years"] == 9
    assert naive["audit_rows_missing_vs_grid"] == 0        # the blind spot
    assert naive["audit_rows_missing_vs_configured_grid"] is None
    assert naive["configured_grid_rows"] is None

    informed = audit_coverage(
        out, expected_rows=1300, expected_agents=100, expected_years=13)
    assert informed["configured_grid_rows"] == 1300
    assert informed["audit_rows_missing_vs_configured_grid"] == 400


def test_configured_grid_shortfall_is_reported_not_explained_away(tmp_path):
    """A flood household that relocates legitimately stops producing rows.

    The count still surfaces it. Nothing subtracts exits on the domain's
    behalf: doing so would also hide the truncation case above, and the two are
    indistinguishable from inside this function.
    """
    out = tmp_path / "exits"
    _write_grid_csv(out, "household", agents=10, years=5)
    coverage = audit_coverage(
        out, expected_rows=60, expected_agents=12, expected_years=5)
    assert coverage["audit_rows_missing_vs_configured_grid"] == 10
    assert coverage["configured_grid_rows"] == 60


def test_runner_threads_the_configured_expectation():
    """``ExperimentRunner`` must supply the expectation per agent TYPE — the
    only place the number exists, since coverage cannot see the config."""
    from broker.core.experiment_runner import ExperimentRunner

    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.agents = {
        "H1": SimpleNamespace(agent_type="household"),
        "H2": SimpleNamespace(agent_type="household"),
        "F1": SimpleNamespace(agent_type="farmer"),
    }
    assert runner._configured_grid_expectation(13) == {
        "expected_agents": {"household": 2, "farmer": 1},
        "expected_rows": {"household": 26, "farmer": 13},
        "expected_years": 13,
    }
    # An unavailable expectation must leave coverage saying "not measured",
    # never abort a finished run.
    runner.agents = {}
    assert runner._configured_grid_expectation(13) == {}
    # Including a runner so partially built it has no `agents` attribute at
    # all — which is what a finalize-path test drives, and what a crash before
    # agent construction leaves behind.
    del runner.agents
    assert runner._configured_grid_expectation(13) == {}


# --- S2: ONE expectation helper, shared by both run paths -------------------

def test_both_run_paths_use_the_same_expectation_helper():
    """S2: ``run_flood`` had its own inline copy of this arithmetic. Two copies
    of a number that must agree is how they stop agreeing."""
    import inspect

    from broker.core.experiment_runner import ExperimentRunner
    from broker.core.run_integrity import configured_grid_expectation
    import examples.single_agent.run_flood as run_flood

    agents = {
        "H1": SimpleNamespace(agent_type="household"),
        "H2": SimpleNamespace(agent_type="household"),
        "F1": SimpleNamespace(agent_type="farmer"),
    }
    expected = {
        "expected_agents": {"household": 2, "farmer": 1},
        "expected_rows": {"household": 26, "farmer": 13},
        "expected_years": 13,
    }
    assert configured_grid_expectation(agents, 13) == expected

    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.agents = agents
    assert runner._configured_grid_expectation(13) == expected

    # run_flood must CALL the helper, not re-derive the number inline.
    source = inspect.getsource(run_flood.run_parity_benchmark)
    assert "configured_grid_expectation(agents, years)" in source


def test_expectation_helper_never_raises_on_a_finished_run():
    """It runs after the experiment is over, while writing a side artifact.
    An exception there would take a COMPLETED run down over a log file."""
    from broker.core.run_integrity import configured_grid_expectation

    class _Explodes:
        def values(self):
            raise RuntimeError("agent registry closed")

    assert configured_grid_expectation(_Explodes(), 13) == {}
    assert configured_grid_expectation(None, 13) == {}
    assert configured_grid_expectation({"A": SimpleNamespace()}, 0) == {}
    # An agent with no agent_type is counted under "default", not dropped.
    assert configured_grid_expectation(
        [SimpleNamespace(), SimpleNamespace()], 4)["expected_agents"] == {
            "default": 2}


# --- S3(ii): legitimate agent exits report a shortfall and NOTHING else -----

def test_legitimate_exits_report_only_the_configured_shortfall(tmp_path):
    """A flood household that relocates stops producing rows. The shortfall
    must be visible AND must be the only thing that fires: no coverage error,
    no unreadable-file list, no pooled-grid flag, no uncategorised tally — a
    second alarm on a healthy run is how the real one gets ignored.
    """
    out = tmp_path / "exits_only"
    # 12 households configured for 5 years; 2 relocated after year 5 was
    # planned, so only 10 of them produced rows.
    _write_grid_csv(out, "household", agents=10, years=5)

    coverage = audit_coverage(
        out, expected_agents={"household": 12},
        expected_rows={"household": 60}, expected_years=5)

    assert coverage["audit_rows"] == 50
    assert coverage["configured_grid_rows"] == 60
    assert coverage["audit_rows_missing_vs_configured_grid"] == 10
    # Everything else stays quiet.
    assert coverage["audit_aborted_rows"] == 0
    assert coverage["audit_rows_missing_vs_grid"] == 0
    assert "audit_coverage_errors" not in coverage
    assert "audit_expectation_unmatched_keys" not in coverage
    assert "audit_grid_pooled_across_agent_types" not in coverage

    reset_uncategorised_rules()
    from broker.core.run_integrity import record_run_integrity

    audit = record_run_integrity(
        out, expected_agents={"household": 12},
        expected_rows={"household": 60}, expected_years=5,
        corrected_status_columns=False, verbose=False)
    assert audit["audit_rows_missing_vs_configured_grid"] == 10
    assert audit["integrity_ok"] is True
    assert audit["rules_uncategorised_total"] == 0
    assert "audit_coverage_error" not in audit


# --- P2-1: an expectation key that names no CSV must be reported ------------

def test_unmatched_expectation_key_is_named_not_silently_dropped(tmp_path):
    """``_as_per_file_expectation`` returns None for a key matching no stem,
    and None also means "no expectation supplied" — so a misspelled agent type
    read as "not measured" with nothing saying the caller HAD measured it."""
    out = tmp_path / "typo"
    _write_grid_csv(out, "household", agents=3, years=4)

    coverage = audit_coverage(
        out, expected_agents={"households": 3},          # note the plural
        expected_rows={"households": 12}, expected_years=4)

    assert coverage["audit_expectation_unmatched_keys"] == ["households"]
    # And the affected per-file numbers still read "not measured", not zero.
    assert coverage["audit_coverage_by_file"]["household"][
        "configured_grid_rows"] is None


def test_matched_expectation_keys_report_nothing_unmatched(tmp_path):
    out = tmp_path / "matched"
    _write_grid_csv(out, "household", agents=3, years=4)
    coverage = audit_coverage(
        out, expected_agents={"household": 3},
        expected_rows={"household": 12}, expected_years=4)
    assert "audit_expectation_unmatched_keys" not in coverage


# --- P2b: per-CSV coverage, because pooling invents a grid ------------------

def test_coverage_is_computed_per_csv_not_pooled(tmp_path):
    """Two agent types pooled into one grid multiply one type's agents by the
    other type's years, producing an expectation no run could ever meet."""
    out = tmp_path / "two_types"
    _write_grid_csv(out, "household", agents=4, years=3)
    _write_grid_csv(out, "farmer", agents=2, years=5)

    coverage = audit_coverage(
        out,
        expected_agents={"household": 4, "farmer": 2},
        expected_rows={"household": 12, "farmer": 10},
        expected_years=5,
    )
    assert sorted(coverage["audit_csv_files"]) == ["farmer", "household"]
    by_file = coverage["audit_coverage_by_file"]
    assert by_file["household"]["audit_rows"] == 12
    assert by_file["farmer"]["audit_rows"] == 10
    # Each file is judged against ITS OWN expectation.
    assert by_file["farmer"]["expected_rows"] == 10
    assert by_file["household"]["expected_rows"] == 12
    # household ran 3 of the configured 5 years: 4 x 5 - 12 = 8 missing.
    assert by_file["household"]["audit_rows_missing_vs_configured_grid"] == 8
    assert by_file["farmer"]["audit_rows_missing_vs_configured_grid"] == 0
    # The pooled 6 agents x 5 observed years = 30 grid is flagged as pooled so
    # nobody reads it as an expectation.
    assert coverage["audit_grid_pooled_across_agent_types"] is True


def test_unreadable_csv_is_named_not_silently_dropped(tmp_path):
    """W3: a skipped file used to leave a plausible smaller number and no trace
    of why. A zero from an I/O failure must not look like a measured zero."""
    out = tmp_path / "broken"
    _write_grid_csv(out, "household", agents=2, years=2)
    (out / "farmer_governance_audit.csv").write_bytes(b"\xff\xfe\x00bad\x00")

    coverage = audit_coverage(out)
    assert coverage["audit_rows"] == 4
    assert coverage.get("audit_coverage_errors")
    assert "farmer_governance_audit.csv" in coverage["audit_coverage_errors"][0]


def test_coverage_error_is_recorded_in_run_integrity(tmp_path, monkeypatch):
    """The same principle one layer up: run_integrity.json must be able to say
    'coverage failed' rather than carry an empty block that reads as fine."""
    import broker.components.analytics.audit as audit_mod
    from broker.core.run_integrity import record_run_integrity

    def _boom(*_a, **_k):
        raise RuntimeError("coverage exploded")

    monkeypatch.setattr(audit_mod, "audit_coverage", _boom)
    result = record_run_integrity(tmp_path, verbose=False)
    assert "coverage exploded" in result["audit_coverage_error"]


# --- P2a: the parse-layer "default" share was an exact-match lookup ---------

def test_default_parse_layer_share_matches_layer_name_variants(tmp_path):
    out = tmp_path / "layers2"
    out.mkdir()
    with (out / "household_governance_audit.csv").open(
            "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["agent_id", "year", "status", "parse_layer"])
        writer.writerow(["A1", "1", "APPROVED", "json"])
        writer.writerow(["A2", "1", "APPROVED", "layer4_default"])
        writer.writerow(["A3", "1", "APPROVED", "default_fallback"])
        writer.writerow(["A4", "1", "APPROVED", "default"])
    # 3 of 4 rows reached a default layer; the exact-match lookup saw 1.
    assert audit_coverage(out)["parse_layer_default_share"] == 0.75


# --- P1a: the F1 exception sentinel -----------------------------------------

def test_aborted_rows_are_counted_from_status_and_say_so(tmp_path):
    """P1a-2: ``decision_source`` is a JSONL-only key.

    ``trace_to_csv_row`` never emits a column for it, so the branch that used
    to count on it was dead on every real corpus and only ever fired for a
    hand-written CSV. The count reads ``status`` alone now, and the block
    records WHICH column it read — because on a flag-OFF corpus the F1
    exception sentinel's status cell says ``UNKNOWN`` and is genuinely not
    countable from the CSV.
    """
    out = tmp_path / "f1"
    out.mkdir()
    with (out / "household_governance_audit.csv").open(
            "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["agent_id", "year", "status", "parse_layer"])
        writer.writerow(["A1", "1", "APPROVED", "json"])
        writer.writerow(["A2", "1", "UNKNOWN", ""])          # flag-OFF F1 row
        writer.writerow(["A3", "1", "ABORTED", ""])
        writer.writerow(["A4", "1", "ABORTED_EXCEPTION", ""])  # flag-ON F1 row
    coverage = audit_coverage(out)
    assert coverage["audit_aborted_rows"] == 2
    assert coverage["audit_aborted_rows_source"] == "csv_status_column"


def test_decision_source_is_not_a_csv_column():
    """The fact behind P1a-2, pinned so the dead branch cannot be reinstated:
    no trace produces a ``decision_source`` cell, however the trace was built."""
    ordinary = trace_to_csv_row(_write(_Host(flag=True), **_REJECTED_CASE))
    assert "decision_source" not in ordinary

    host = _Host(flag=True)
    host._write_aborted_sentinel_trace(
        agent_type="household", run_id="r", step_id=1, timestamp="t",
        env_context={"current_year": 1}, seed=42, agent_id="A1",
        raw_output="junk", format_retry_count=0,
    )
    sentinel_trace = host.audit_writer.traces[-1][1]
    assert sentinel_trace["decision_source"] == "parse_failure"   # in the JSONL
    assert "decision_source" not in trace_to_csv_row(sentinel_trace)  # not CSV


def test_f1_sentinel_status_cell_is_truthful_only_under_the_flag():
    """Flag OFF the cell must stay ``UNKNOWN`` — a frozen corpus rerun cannot
    gain a changed cell, however wrong that cell is. Flag ON it says what
    happened."""
    from broker.core.experiment_runner import ExperimentRunner

    def _run(flag):
        runner = ExperimentRunner.__new__(ExperimentRunner)
        writer = _StubWriter()
        runner.broker = SimpleNamespace(
            audit_writer=writer, _corrected_status_columns=flag)
        runner.config = SimpleNamespace(seed=42)
        runner.step_counter = 3
        runner._write_aborted_trace(
            SimpleNamespace(id="A1", agent_type="household"),
            "run", {"current_year": 2}, RuntimeError("timeout"),
        )
        return trace_to_csv_row(writer.traces[-1][1])

    off = _run(False)
    assert off["status"] == "UNKNOWN"          # the documented flag-OFF state
    on = _run(True)
    assert on["status"] == "ABORTED_EXCEPTION"
    assert on["execution_path"] == "aborted"
    assert on["final_skill"] == ""


# --- P1b: the sentinel row must not fabricate the call it records -----------

def test_sentinel_row_carries_the_real_llm_and_memory_measurements():
    host = _Host(flag=True)
    host._write_aborted_sentinel_trace(
        agent_type="household", run_id="r", step_id=1, timestamp="t",
        env_context={"current_year": 1}, seed=42, agent_id="A1",
        raw_output="junk", format_retry_count=2,
        llm_stats={"llm_retries": 1, "llm_success": True,
                   "prompt_tokens": 812, "response_tokens": 40,
                   "num_ctx": 8192, "context_utilization": 0.0991},
        memory_pre=[{"content": "a"}, {"content": "b"}],
        prompt="THE PROMPT",
    )
    trace = host.audit_writer.traces[-1][1]
    row = trace_to_csv_row(trace)
    assert row["prompt_tokens"] == 812
    assert row["context_utilization"] == 0.0991
    assert row["llm_retries"] == 1
    assert row["mem_retrieved_count"] == 2
    assert row["mem_retrieval_mode"] == "aborted"
    assert trace["input"] == "THE PROMPT"


def test_sentinel_marks_unmeasured_fields_empty_never_zero():
    """Without real stats the row must say "" — not 0 tokens and not a
    successful call. A fabricated zero is a number somebody can average; an
    empty cell is not."""
    host = _Host(flag=True)
    host._write_aborted_sentinel_trace(
        agent_type="household", run_id="r", step_id=1, timestamp="t",
        env_context={"current_year": 1}, seed=42, agent_id="A1",
        raw_output="junk", format_retry_count=0,
    )
    row = trace_to_csv_row(host.audit_writer.traces[-1][1])
    for column in ("prompt_tokens", "response_tokens", "num_ctx",
                   "context_utilization", "llm_success"):
        assert row[column] == "", f"{column} fabricated a value"
    assert row["mem_surprise"] == ""
    assert row["mem_retrieved_count"] == 0      # measured: nothing retrieved


def test_sentinel_introduces_no_column_beyond_the_corrected_set():
    """P1b must not widen the schema — the sentinel is extra ROWS, not extra
    columns."""
    host = _Host(flag=True)
    ordinary = trace_to_csv_row(_write(host, **_REJECTED_CASE))
    host._write_aborted_sentinel_trace(
        agent_type="household", run_id="r", step_id=1, timestamp="t",
        env_context={"current_year": 1}, seed=42, agent_id="A1",
        raw_output="junk", format_retry_count=0,
        llm_stats={"llm_success": True}, memory_pre=[{"content": "a"}],
        prompt="p",
    )
    sentinel = trace_to_csv_row(host.audit_writer.traces[-1][1])
    assert set(sentinel) - set(ordinary) == set()


def test_sentinel_write_failures_are_counted_not_only_logged():
    """P2d: a failed sentinel write is a missing row — the same denominator
    hole the sentinel exists to close — and used to live only in the log."""
    host = _Host(flag=True)

    class _Boom:
        def write_trace(self, *a, **k):
            raise OSError("disk full")

    host.audit_writer = _Boom()
    for _ in range(3):
        host._write_aborted_sentinel_trace(
            agent_type="household", run_id="r", step_id=1, timestamp="t",
            env_context={}, seed=42, agent_id="A1", raw_output="x",
            format_retry_count=0,
        )
    assert host._audit_sentinel_write_failures == 3


def test_run_integrity_surfaces_sentinel_write_failures(tmp_path):
    from broker.core.run_integrity import record_run_integrity

    audit = record_run_integrity(
        tmp_path, sentinel_write_failures=2, corrected_status_columns=True,
        verbose=False)
    assert audit["audit_sentinel_write_failures"] == 2
    assert audit["audit_corrected_status_columns_resolved"] is True


# --- P1c: uncategorised rules reach run_integrity.json ----------------------

def test_uncategorised_rules_reach_run_integrity(tmp_path):
    from broker.core.run_integrity import record_run_integrity

    reset_uncategorised_rules()
    get_rule_breakdown(_agent_validator_results(), allow_metadata_fallback=True)
    audit = record_run_integrity(tmp_path, verbose=False)
    assert audit["rules_uncategorised_total"] == 2
    assert "I1" in audit["rules_uncategorised_ids"]
    reset_uncategorised_rules()


# --- P1d: the corrected column set is schema "3" ----------------------------

def test_sidecar_stamps_schema_3_when_the_columns_are_corrected(tmp_path):
    import json

    from broker.components.analytics.audit import (
        AUDIT_SCHEMA_VERSION, AUDIT_SCHEMA_VERSION_CORRECTED,
    )

    off = _write_csv(tmp_path, "v_off", _Host(flag=False))
    on = _write_csv(tmp_path, "v_on", _Host(flag=True))

    def _sidecar(csv_path):
        return json.loads(
            (csv_path.parent / "household_governance_audit.schema.json")
            .read_text(encoding="utf-8"))

    assert _sidecar(off)["audit_schema_version"] == AUDIT_SCHEMA_VERSION == "2"
    assert _sidecar(on)["audit_schema_version"] == \
        AUDIT_SCHEMA_VERSION_CORRECTED == "3"
    assert _sidecar(on)["corrected_status_columns"] is True


def test_framework_provenance_agrees_with_the_sidecar(tmp_path):
    """Provenance and sidecar use the SAME fieldname detection, so they cannot
    report different schema versions for one file."""
    from broker.core.run_integrity import record_run_integrity

    csv_path = _write_csv(tmp_path, "prov", _Host(flag=True))
    audit = record_run_integrity(csv_path.parent, verbose=False)
    assert audit["framework_provenance"]["audit_schema_version"] == "3"
    assert audit["audit_corrected_status_columns"] is True


def test_flag_off_run_integrity_keeps_schema_2(tmp_path):
    from broker.core.run_integrity import record_run_integrity

    csv_path = _write_csv(tmp_path, "prov_off", _Host(flag=False))
    audit = record_run_integrity(
        csv_path.parent, corrected_status_columns=False, verbose=False)
    assert audit["framework_provenance"]["audit_schema_version"] == "2"
    assert audit["audit_corrected_status_columns"] is False
    assert audit["audit_corrected_status_columns_resolved"] is False


# --- P1d-2: all four version stamps must agree (or be the documented one) ---

def test_summary_is_restamped_when_the_corrected_columns_were_written(tmp_path):
    """S3(iii). ``audit_run_metadata()`` runs at writer construction, before
    any column set exists, so it can only stamp the base "2" — which on a
    corrected run told an analyst reading audit_summary.json to apply the wrong
    contract while the sidecar beside it said "3"."""
    import json

    on = _write_csv(tmp_path, "stamp_on", _Host(flag=True))
    off = _write_csv(tmp_path, "stamp_off", _Host(flag=False))

    def _summary(csv_path):
        return json.loads(
            (csv_path.parent / "audit_summary.json").read_text(encoding="utf-8"))

    assert _summary(on)["audit_schema_version"] == "3"
    # Flag OFF must be untouched: audit_summary.json is a published artifact.
    assert _summary(off)["audit_schema_version"] == "2"


def test_the_three_csv_side_stamps_agree_and_the_jsonl_one_is_documented(tmp_path):
    """The sidecar, the summary and run_integrity all resolve from the same
    signal, so they cannot disagree. The JSONL ``_metadata`` stamp is the
    documented exception: it is written on the FIRST trace, before the column
    set exists, so it stays the base constant."""
    import json

    from broker.core.run_integrity import record_run_integrity

    csv_path = _write_csv(tmp_path, "stamps", _Host(flag=True))
    out = csv_path.parent

    sidecar = json.loads(
        (out / "household_governance_audit.schema.json").read_text(
            encoding="utf-8"))
    summary = json.loads(
        (out / "audit_summary.json").read_text(encoding="utf-8"))
    integrity = record_run_integrity(
        out, corrected_status_columns=True, verbose=False)

    assert sidecar["audit_schema_version"] == "3"
    assert summary["audit_schema_version"] == "3"
    assert integrity["framework_provenance"]["audit_schema_version"] == "3"

    jsonl_meta = json.loads(
        (out / "raw" / "household_traces.jsonl").read_text(
            encoding="utf-8").splitlines()[0])
    assert jsonl_meta["_metadata"]["audit_schema_version"] == "2"


def test_readiness_reads_the_restamped_summary_when_integrity_is_absent(tmp_path):
    """readiness_report falls back to audit_summary.json for provenance. With
    the restamp it now gets "3" there instead of reporting the wrong contract
    from the artifact whose job is to state which contract applies."""
    from broker.tools.readiness_report import _compute_metrics

    csv_path = _write_csv(tmp_path, "readiness_stamp", _Host(flag=True))
    metrics = _compute_metrics(csv_path.parent)
    assert metrics.framework_provenance["audit_schema_version"] == "3"


# --- P2-2: ONE flag resolution per run --------------------------------------

def test_engine_row_write_uses_the_cached_flag_not_a_per_row_reread():
    """Two independent resolutions meant a config whose getter changed mid-run
    could write some rows under one contract and some under the other, in ONE
    CSV, with nothing recording the split."""
    engine, _ = _engine(True, proposal="elevate")
    _step(engine)
    assert "execution_path" in engine.audit_writer.traces[0][1]

    # The config now says OFF, but the engine resolved ON at construction: the
    # rows must stay on one contract for the life of the run.
    engine.config.get_audit_corrected_status_columns.return_value = False
    _step(engine)
    assert "execution_path" in engine.audit_writer.traces[1][1]
    assert engine._corrected_status_columns is True


def test_a_host_without_the_cached_attribute_still_reads_the_config():
    """The per-row helper stays as the fallback for a host that mixes in
    AuditMixin without being a SkillBrokerEngine (every test host here)."""
    assert not hasattr(_Host(flag=True), "_corrected_status_columns")
    assert "execution_path" in _write(_Host(flag=True), **_REJECTED_CASE)
    assert "execution_path" not in _write(_Host(flag=False), **_REJECTED_CASE)


# --- P2-4: standalone mode did not execute anything -------------------------

def test_standalone_mode_is_labelled_approved_no_engine():
    """The branch reports success=True and names an executed skill although no
    simulation engine exists to run it. Labelling that ``approved`` made those
    rows indistinguishable from a row where an engine really did execute the
    action — in the column whose whole purpose is to say what happened."""
    engine, _ = _engine(True, proposal="elevate")
    engine.simulation_engine = None
    _step(engine)

    row = trace_to_csv_row(engine.audit_writer.traces[0][1])
    assert row["execution_path"] == "approved_no_engine"
    # executed_skill stays the approved skill: it IS the action the run
    # attributes to the agent, and executed-only analysis depends on it.
    assert row["executed_skill"] == "elevate"
    assert row["final_skill"] == "elevate"
    assert row["fallback_activated"] is False


def test_engine_backed_approval_keeps_the_plain_approved_label():
    engine, sim = _engine(True, proposal="elevate")
    _step(engine)
    assert sim.executed == ["elevate"]
    assert trace_to_csv_row(
        engine.audit_writer.traces[0][1])["execution_path"] == "approved"


# --- P1e: the flag must never fail closed in silence ------------------------

def test_flag_getter_that_raises_warns_and_reads_off(caplog):
    import logging

    from broker.core._audit_helpers import _FLAG_WARNED, _corrected_status_flag

    class _Raiser:
        def get_audit_corrected_status_columns(self):
            raise ValueError("malformed audit block")

    _FLAG_WARNED.clear()
    with caplog.at_level(logging.WARNING):
        assert _corrected_status_flag(_Raiser()) is False
    assert any("corrected_status_columns is being read OFF" in r.getMessage()
               for r in caplog.records)
    _FLAG_WARNED.clear()


def test_flag_getter_returning_a_non_bool_warns_and_reads_off(caplog):
    import logging

    from broker.core._audit_helpers import _FLAG_WARNED, _corrected_status_flag

    class _Stringy:
        def get_audit_corrected_status_columns(self):
            return "true"          # a YAML string, not a bool

    _FLAG_WARNED.clear()
    with caplog.at_level(logging.WARNING):
        assert _corrected_status_flag(_Stringy()) is False
    assert any("rather than a bool" in r.getMessage() for r in caplog.records)
    _FLAG_WARNED.clear()


def test_flag_warning_is_emitted_once_per_process():
    """Per row it would fire thousands of times a run and train the operator to
    filter it — which re-buries the failure it exists to surface."""
    from broker.core._audit_helpers import _FLAG_WARNED, _corrected_status_flag

    class _Stringy:
        def get_audit_corrected_status_columns(self):
            return "true"

    _FLAG_WARNED.clear()
    for _ in range(5):
        _corrected_status_flag(_Stringy())
    assert len(_FLAG_WARNED) == 1
    _FLAG_WARNED.clear()


def test_validate_prompt_flags_a_typod_audit_key():
    """The flag fails closed, so a typo produces UNCORRECTED columns and no
    artifact says the flag was ever requested. This check is the only net."""
    from broker.tools.validate_prompt import (
        KNOWN_AUDIT_KEYS, check_global_config_keys,
    )

    assert "corrected_status_columns" in KNOWN_AUDIT_KEYS
    issues = check_global_config_keys(
        {"global_config": {"audit": {"corected_status_columns": True}}})
    assert any("corected_status_columns" in i.message for i in issues)
    assert not check_global_config_keys(
        {"global_config": {"audit": {"corrected_status_columns": True}}})


# --- S2 / S4: execution_path "unknown" and "not_executed" -------------------

def test_execution_path_absent_reads_unknown_not_blank():
    """A blank cell reads as "does not apply"; the truth is that the caller
    never said which branch ran, and those rows must be filterable by name."""
    trace = _write(_Host(flag=True), approved=_approved("elevate", "APPROVED"),
                   outcome=SkillOutcome.APPROVED, executed_skill="elevate",
                   executed_via_fallback=False, execution_path=None)
    assert trace["execution_path"] == "unknown"
    assert trace_to_csv_row(trace)["execution_path"] == "unknown"


def test_engine_reports_not_executed_when_the_default_is_missing():
    """A blocked proposal whose registry default cannot be found executes
    NOTHING. The row must say so rather than inherit the previous branch's
    label."""
    engine, sim = _engine(True, proposal="elevate", blocking=True)
    engine.skill_registry.exists = lambda _sid: False
    _step(engine)

    assert sim.executed == []
    row = trace_to_csv_row(engine.audit_writer.traces[0][1])
    assert row["execution_path"] == "not_executed"
    assert row["executed_skill"] in ("", None)
    assert row["fallback_activated"] is False


# --- S4: the sidecar fieldnames LIST, order included ------------------------

def test_flag_off_sidecar_fieldnames_match_in_order(tmp_path):
    """Set equality would pass on a reordered header, and column ORDER is part
    of what byte identity means for a CSV."""
    import json

    ref = _write_csv(tmp_path, "order_ref", _Host(flag=None))
    cand = _write_csv(tmp_path, "order_cand", _Host(flag=False))

    def _fieldnames(csv_path):
        return json.loads(
            (csv_path.parent / "household_governance_audit.schema.json")
            .read_text(encoding="utf-8"))["fieldnames"]

    ref_fields, cand_fields = _fieldnames(ref), _fieldnames(cand)
    assert isinstance(ref_fields, list)
    assert ref_fields == cand_fields            # order, not just membership
    # And the header row on disk agrees with the sidecar it describes.
    with ref.open(newline="", encoding="utf-8-sig") as fh:
        assert next(csv.reader(fh)) == ref_fields


# --- P2c: a partial coverage block must trigger a recompute -----------------

def test_readiness_recomputes_coverage_from_a_partial_integrity_block(tmp_path):
    """One coverage key made the old truth test pass, so a partially-written
    run_integrity.json was accepted whole and the report showed a block with
    holes and no sign anything was missing."""
    import json

    from broker.tools.readiness_report import _compute_metrics

    results = tmp_path / "partial"
    _write_grid_csv(results, "household", agents=3, years=4)
    (results / "run_integrity.json").write_text(
        json.dumps({"governance_mode": "strict", "audit_rows": 999}),
        encoding="utf-8",
    )

    coverage = _compute_metrics(results).audit_coverage
    assert coverage["audit_rows"] == 999          # what the run recorded wins
    assert coverage["audit_agents"] == 3          # the gaps are filled in
    assert coverage["audit_years"] == 4
    assert "parse_layer_distribution" in coverage
