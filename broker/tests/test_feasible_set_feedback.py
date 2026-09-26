"""Feasible-set line on ERROR retries (``governance.feasible_set_feedback``),
appraisal-drift audit columns, and the neutral rejection memory line.

All three are default-off; the flag-off paths must render and record exactly
what they did before.
"""
from __future__ import annotations

from types import SimpleNamespace

from broker.components.analytics.audit import compute_csv_fieldnames, trace_to_csv_row
from broker.core._audit_helpers import AuditMixin, _label_drift
from broker.core._retry_loop import RetryMixin
from broker.interfaces.skill_types import SkillOutcome, SkillProposal, ValidationResult
from broker.utils.agent_config import AgentTypeConfig
from broker.utils.governance_auditor import GovernanceAuditor
from broker.utils.parsing.unified_adapter import UnifiedAdapter

SKILLS = ["grow_a", "grow_b", "keep", "shrink_a", "shrink_b"]
SKILL_MAP = {str(i + 1): s for i, s in enumerate(SKILLS)}
PROMPT = "ORIGINAL PROMPT"


class _Registry:
    def list_skills(self):
        return list(SKILLS)

    def exists(self, name):
        return name in SKILLS

    def check_eligibility(self, name, agent_type):
        return SimpleNamespace(valid=True)

    def get_default_skill(self):
        return "keep"


class _Auditor:
    def log_parse_error(self):
        pass


def _block_grow(proposal, context):
    """Blocks both grow_* skills with an ERROR; logs to the singleton auditor
    like the real config-rule validator does."""
    if proposal.skill_name.startswith("grow"):
        GovernanceAuditor().log_intervention("no_grow", success=False)
        return [ValidationResult(valid=False, validator_name="v", errors=["grow blocked"],
                                 metadata={"rule_id": "no_grow"})]
    return [ValidationResult(valid=True, validator_name="v")]


class _Host(RetryMixin):
    max_retries = 1
    max_reports = 3

    def __init__(self, feasible=True, validator=_block_grow, with_map=True):
        self.auditor = _Auditor()
        self.model_adapter = UnifiedAdapter.__new__(UnifiedAdapter)
        self._retry_feedback_mode = "full"
        self._intervention_framing = "legacy"
        self._feasible_set_feedback = feasible
        self._on_retry_exhausted = "default"
        self.skill_registry = _Registry()
        self.config = SimpleNamespace(
            get_skill_map=(lambda at, ctx: dict(SKILL_MAP)) if with_map else (lambda at, ctx: {})
        )
        self._validator = validator

    def _run_validators(self, proposal, context):
        return self._validator(proposal, context)


def _run(host, proposal_skill="grow_a", replies=None, feasible_by_attempt=None, errors=None):
    prompts = []
    replies = list(replies or ["keep"])

    def llm_invoke(p):
        prompts.append(p)
        return SkillProposal(skill_name=replies.pop(0), agent_id="A1", agent_type="t",
                             reasoning={"X_LABEL": "H"})

    proposal = SkillProposal(skill_name=proposal_skill, agent_id="A1", agent_type="t",
                             reasoning={"X_LABEL": "H"})
    if errors is not None:
        results = errors
    else:
        with GovernanceAuditor.muted():
            results = _block_grow(proposal, {})
    host._governance_retry_loop(
        all_valid=False, skill_proposal=proposal, validation_results=results,
        all_validation_history=list(results), validation_context={}, prompt=PROMPT,
        llm_invoke=llm_invoke, context={}, agent_id="A1", agent_type="t",
        env_context={}, raw_output="raw",
        total_llm_stats={"llm_retries": 0, "llm_success": False},
        feasible_by_attempt=feasible_by_attempt,
    )
    return prompts


def test_feasible_line_present_and_equals_probe_set():
    fba = []
    prompts = _run(_Host(), feasible_by_attempt=fba)
    line = ("Actions that pass every rule, given the assessment in your last response: "
            "3 (keep), 4 (shrink a), 5 (shrink b).")
    assert line in prompts[0]
    assert fba == [["keep", "shrink_a", "shrink_b"]]
    # after the reports, before the closer and the original prompt
    assert prompts[0].index("grow blocked") < prompts[0].index(line) < prompts[0].index(PROMPT)


def test_feasible_line_on_every_error_retry():
    host = _Host()
    host.max_retries = 3
    prompts = _run(host, replies=["grow_b", "grow_a", "keep"])
    assert len(prompts) == 3
    assert all("Actions that pass every rule" in p for p in prompts)


def test_feasible_line_survives_report_truncation():
    host = _Host()
    host.max_reports = 1
    errs = [ValidationResult(valid=False, validator_name="v", errors=[f"e{i}"],
                             metadata={"rule_id": f"r{i}"}) for i in range(4)]
    prompts = _run(host, errors=errs)
    assert "only the top 1 are shown" in prompts[0]
    assert "Actions that pass every rule" in prompts[0]


def test_empty_feasible_set_wording():
    def block_all(proposal, context):
        return [ValidationResult(valid=False, validator_name="v", errors=["no"],
                                 metadata={"rule_id": "all"})]
    prompts = _run(_Host(validator=block_all))
    assert ("No action passes every rule given your last response; if this continues, "
            "the default action (keep) will be applied.") in prompts[0]


def test_names_without_skill_map():
    prompts = _run(_Host(with_map=False))
    assert "response: keep, shrink a, shrink b." in prompts[0]


def test_flag_off_prompt_is_unchanged():
    on = _run(_Host(feasible=True))[0]
    off = _run(_Host(feasible=False))[0]
    assert "Actions that pass every rule" not in off
    adapter = UnifiedAdapter.__new__(UnifiedAdapter)
    from broker.core._advise import build_intervention_reports
    proposal = SkillProposal(skill_name="grow_a", agent_id="A1", agent_type="t",
                             reasoning={"X_LABEL": "H"})
    with GovernanceAuditor.muted():
        blocked = _block_grow(proposal, {})
    reports = build_intervention_reports(blocked, proposal, source="errors")
    assert off == adapter.format_retry_prompt(PROMPT, reports, max_reports=3)
    assert on != off


def test_probes_do_not_count_as_rule_hits():
    aud = GovernanceAuditor()
    before = aud.rule_hits.get("no_grow", 0)
    fba = []
    _run(_Host(), feasible_by_attempt=fba)
    # the probe tried grow_a and grow_b (both blocked) without logging them;
    # the retry's own real validation of "keep" logs nothing either
    assert fba == [["keep", "shrink_a", "shrink_b"]]
    assert aud.rule_hits.get("no_grow", 0) == before
    # and the mute is scoped: outside it, a hit is counted again
    _block_grow(SkillProposal(skill_name="grow_a", agent_id="A1", agent_type="t", reasoning={}), {})
    assert aud.rule_hits.get("no_grow", 0) == before + 1


def test_config_getter_default_off():
    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = {"global_config": {}}
    assert cfg.get_governance_feasible_set_feedback() is False
    cfg._config = {"global_config": {"governance": {"feasible_set_feedback": True}}}
    assert cfg.get_governance_feasible_set_feedback() is True


# --------------------------------------------------------------------------
# Appraisal-drift and feasible_by_attempt audit columns
# --------------------------------------------------------------------------

def test_label_drift():
    assert _label_drift("A_LABEL=H|B_LABEL=H", "A_LABEL=M|B_LABEL=H") == "A_LABEL:H>M"
    assert _label_drift("A_LABEL=H|B_LABEL=H", "A_LABEL=M|B_LABEL=VH") == "A_LABEL:H>M|B_LABEL:H>VH"
    assert _label_drift("A_LABEL=H", "A_LABEL=H") == ""
    assert _label_drift("A_LABEL=H", "") == "A_LABEL:H>"


class _Writer:
    def __init__(self):
        self.traces = []

    def write_trace(self, agent_type, trace, history):
        self.traces.append(trace)


class _AuditHost(AuditMixin):
    def __init__(self, flag):
        self.audit_writer = _Writer()
        self.config = SimpleNamespace(get_log_fields=lambda at: [],
                                      get_audit_initial_proposal_columns=lambda: flag)


def _trace(flag, attempt_skills, final_reasoning, feasible_by_attempt=None):
    host = _AuditHost(flag)
    host._write_audit_trace(
        agent_type="t", context={}, run_id="r", step_id="Y1", timestamp="t",
        env_context={}, seed=1, agent_id="A1", all_valid=True, prompt="p",
        raw_output="o", context_hash="h", memory_pre=[], memory_post=[],
        skill_proposal=SkillProposal(skill_name="keep", agent_id="A1", agent_type="t",
                                     reasoning=final_reasoning),
        approved_skill=SimpleNamespace(skill_name="keep", approval_status="APPROVED",
                                       execution_mapping={}),
        execution_result=None, outcome=SkillOutcome.RETRY_SUCCESS, retry_count=1,
        format_retry_count=0, total_llm_stats={}, all_validation_history=[],
        initial_skill="grow_a", initial_labels="X_LABEL=H|Y_LABEL=H",
        attempt_skills=attempt_skills, feasible_by_attempt=feasible_by_attempt,
    )
    return host.audit_writer.traces[0]


def test_drift_columns_when_retried():
    t = _trace(True, ["grow_a", "keep"], {"X_LABEL": "M", "Y_LABEL": "H"})
    assert t["final_labels"] == "X_LABEL=M|Y_LABEL=H"
    assert t["appraisal_drift"] == "X_LABEL:H>M"
    assert t["appraisal_drifted"] is True
    row = trace_to_csv_row(dict(t, step_id="Y1", agent_id="A1"))
    for col in ("final_labels", "appraisal_drift", "appraisal_drifted"):
        assert col in compute_csv_fieldnames([row])


def test_no_drift_without_retry():
    t = _trace(True, ["keep"], {"X_LABEL": "M", "Y_LABEL": "H"})
    assert t["appraisal_drift"] == "" and t["appraisal_drifted"] is False


def test_drift_and_feasible_columns_absent_when_flags_off():
    t = _trace(False, ["grow_a", "keep"], {"X_LABEL": "M"})
    for col in ("final_labels", "appraisal_drift", "appraisal_drifted", "feasible_by_attempt"):
        assert col not in t


def test_feasible_by_attempt_column():
    t = _trace(False, ["grow_a", "grow_b", "keep"], {"X_LABEL": "M"},
               feasible_by_attempt=[["keep", "shrink_a"], []])
    assert t["feasible_by_attempt"] == "keep,shrink_a|"
    row = trace_to_csv_row(dict(t, step_id="Y1", agent_id="A1"))
    assert row["feasible_by_attempt"] == "keep,shrink_a|"


# --------------------------------------------------------------------------
# Neutral rejection memory line (memory.rejection_line_style)
# --------------------------------------------------------------------------

def _apply(style):
    from broker.core.experiment_runner import ExperimentRunner

    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner._current_year = 3
    runner.config = SimpleNamespace(domain=None)
    stored = []
    runner.memory_engine = SimpleNamespace(
        add_memory_for_agent=lambda agent, content, meta: stored.append(content))
    agent = SimpleNamespace(id="A1", apply_delta=lambda d: None,
                            memory_config={} if style is None else {"rejection_line_style": style})
    result = SimpleNamespace(
        outcome=SkillOutcome.REJECTED,
        approved_skill=SimpleNamespace(skill_name="grow_a", parameters={}),
        executed_skill="keep", executed_via_fallback=True,
        execution_result=SimpleNamespace(success=True, state_changes={}, action_context={}),
        blocking_rule_ids=["no_grow"],
    )
    runner._apply_state_changes(agent, result)
    return stored[0], agent._last_action_context


def test_explicit_is_default_and_unchanged():
    line, ctx = _apply(None)
    assert line == "Year 3: Proposal to grow a was rejected; default action applied: Keep"
    assert "blocking_rules" not in ctx
    assert _apply("explicit")[0] == line


def test_neutral_names_rule_not_proposal():
    line, ctx = _apply("neutral")
    assert line == "Year 3: under rule no_grow, default action applied: Keep"
    assert "grow a" not in line and "rejected" not in line
    assert ctx["blocking_rules"] == ["no_grow"]


def test_unparsed_final_attempt_is_not_drift():
    host = _AuditHost(True)
    host._write_audit_trace(
        agent_type="t", context={}, run_id="r", step_id="Y1", timestamp="t",
        env_context={}, seed=1, agent_id="A1", all_valid=False, prompt="p",
        raw_output="o", context_hash="h", memory_pre=[], memory_post=[],
        skill_proposal=None,
        approved_skill=SimpleNamespace(skill_name="keep", approval_status="REJECTED",
                                       execution_mapping={}),
        execution_result=None, outcome=SkillOutcome.REJECTED, retry_count=1,
        format_retry_count=0, total_llm_stats={}, all_validation_history=[],
        initial_skill="grow_a", initial_labels="X_LABEL=H",
        attempt_skills=["grow_a", None],
    )
    t = host.audit_writer.traces[0]
    assert t["appraisal_drift"] == "" and t["appraisal_drifted"] is False


def test_keep_proposal_empty_set_wording():
    def block_all(proposal, context):
        return [ValidationResult(valid=False, validator_name="v", errors=["no"],
                                 metadata={"rule_id": "all"})]
    host = _Host(validator=block_all)
    host._on_retry_exhausted = "keep_proposal"
    prompts = _run(host)
    assert "No action passes every rule given your last response." in prompts[0]
    assert "default action" not in prompts[0].split("No action passes")[1].split("\n")[0]


def test_neutral_line_with_several_rules():
    from broker.core.experiment_runner import ExperimentRunner

    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner._current_year = 3
    runner.config = SimpleNamespace(domain=None)
    stored = []
    runner.memory_engine = SimpleNamespace(
        add_memory_for_agent=lambda agent, content, meta: stored.append(content))
    agent = SimpleNamespace(id="A1", apply_delta=lambda d: None,
                            memory_config={"rejection_line_style": "neutral"})
    result = SimpleNamespace(
        outcome=SkillOutcome.REJECTED,
        approved_skill=SimpleNamespace(skill_name="grow_a", parameters={}),
        executed_skill="keep", executed_via_fallback=True,
        execution_result=SimpleNamespace(success=True, state_changes={}, action_context={}),
        blocking_rule_ids=["r1", "r2"],
    )
    runner._apply_state_changes(agent, result)
    assert stored[0] == "Year 3: under rules (r1, r2), default action applied: Keep"
