"""Appraisal freeze and the per-attempt / agent-state audit columns.

Generic framework options added for the irrigation v3 governance (WP3,
``irrigation_v3_spec_2026-09-28.md`` sections 3.5, 3.8, 3.9), all opt-in:

- ``global_config.governance.appraisal_freeze`` (default false): within one
  decision every validation pass reads each construct label as the agent
  FIRST STATED it (``broker/core/_appraisal_freeze.py``): the first parsed
  attempt's label, or, if that attempt omitted it, the first later
  statement. So a retry cannot pass a label-conditioned rule by rewriting
  its label; the feasible-set probe reads the same labels.
- ``global_config.governance.rule_id_prefix`` (default true): the
  ``[Rule: <id>] `` prefix of YAML identity/thinking rule messages.
- ``global_config.governance.hide_registry_backstop_reports`` (default
  false): the registry backstop results stay out of the retry text when an
  identity rule blocked the same attempt.
- ``global_config.audit.attempt_columns`` (default false):
  ``attempt_labels`` / ``attempt_failed_rules`` / ``appraisal_relabeled``.
- ``global_config.audit.state_columns`` (default none): ``state_<key>``.
- YAML thinking rules may carry a ``suggestion:``.

Every test here fails on the pre-change code (HEAD 5fe1ccf7): none of these
getters, columns or the freeze module exist there, and a relabelled retry
passes a label rule. The tests added for the WP3 review (first-stated
labels, the refusals, the ABORTED sentinel columns, the backstop filter,
the rule-id naming) also fail on the round-1 code.
"""
from __future__ import annotations

import textwrap
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from broker.components.analytics.audit import trace_to_csv_row
from broker.components.governance.registry import SkillRegistry
from broker.core._appraisal_freeze import (
    FROZEN_LABELS_CONTEXT_KEY,
    construct_label_dict,
    frozen_label_view,
)
from broker.interfaces.skill_types import SkillDefinition, SkillProposal, ValidationResult
from broker.utils.agent_config import AgentTypeConfig
from broker.utils.governance_auditor import GovernanceAuditor
from broker.utils.parsing.unified_adapter import UnifiedAdapter

SKILLS = ("grow", "keep", "shrink")
RULE_ID = "no_grow_when_x_high"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _registry() -> SkillRegistry:
    registry = SkillRegistry()
    for sid in SKILLS:
        registry.register(SkillDefinition(
            skill_id=sid, description=sid, eligible_agent_types=["*"],
            preconditions=[], institutional_constraints={},
            allowed_state_changes=[], implementation_mapping=sid,
        ))
    registry.set_default_skill("keep")
    return registry


class _Ctx:
    """Context builder stub: a fixed state and a fixed prompt."""

    def __init__(self, state: Dict[str, Any] = None):
        self.state = dict(state or {})

    def build(self, agent_id, env_context=None, **kwargs):
        return {"agent_id": agent_id, "state": dict(self.state)}

    def format_prompt(self, context):
        return "PROMPT"


class _LabelRule:
    """A generic label-conditioned rule, as any validator would read it:
    ``X_LABEL`` in {H, VH} blocks ``grow``. Records every label it saw."""

    def __init__(self):
        self.seen: List[Any] = []

    def __call__(self, proposal, context, registry=None):
        label = (proposal.reasoning or {}).get("X_LABEL")
        self.seen.append((proposal.skill_name, label))
        if proposal.skill_name == "grow" and label in ("H", "VH"):
            GovernanceAuditor().log_intervention(RULE_ID, success=False)
            return [ValidationResult(
                valid=False, validator_name="LabelRule",
                errors=["grow is blocked when X is high"],
                metadata={"rule_id": RULE_ID, "rules_hit": [RULE_ID]},
            )]
        return [ValidationResult(valid=True, validator_name="LabelRule")]


def _config(**flags) -> MagicMock:
    config = MagicMock()
    config.get_log_fields.return_value = []
    config.get_governance_retries.return_value = 3
    config.get_governance_max_reports.return_value = 3
    config.get_multi_skill_config.return_value = {}
    config.get_audit_initial_proposal_columns.return_value = True
    config.get_audit_executed_columns.return_value = False
    config.get_audit_advise_columns.return_value = False
    config.get_governance_advise.return_value = None
    config.get_governance_advise_mode.return_value = flags.get("advise_mode", "off")
    config.get_governance_intervention_framing.return_value = "legacy"
    config.get_governance_on_retry_exhausted.return_value = "default"
    config.get_governance_retry_feedback_mode.return_value = "full"
    config.get_governance_feasible_set_feedback.return_value = flags.get("feasible", False)
    config.get_governance_appraisal_freeze.return_value = flags.get("freeze", False)
    config.get_audit_attempt_columns.return_value = flags.get("attempt_columns", False)
    config.get_audit_state_columns.return_value = flags.get("state_columns", [])
    config.get_skill_map.return_value = {"1": "grow", "2": "keep", "3": "shrink"}
    return config


def _engine(*, state=None, **flags):
    from broker.core.skill_broker_engine import SkillBrokerEngine

    rule = _LabelRule()
    adapter = UnifiedAdapter.__new__(UnifiedAdapter)
    eng = SkillBrokerEngine(
        skill_registry=_registry(), model_adapter=adapter, validators=[],
        simulation_engine=None, context_builder=_Ctx(state), config=_config(**flags),
        custom_validators=[rule],
    )
    return eng, rule, adapter


def _scripted(adapter, answers):
    """Every parse returns the next scripted (skill, X label) proposal; a
    label of None omits the X_LABEL key entirely."""
    queue = list(answers)

    def _parse(_raw, _ctx):
        skill, label = queue.pop(0)
        reasoning = {"X_REASON": "because"}
        if label is not None:
            reasoning["X_LABEL"] = label
        return SkillProposal(skill_name=skill, agent_id="A1", agent_type="operator",
                             reasoning=reasoning)

    adapter.parse_output = _parse


def _require_label(proposal, context, registry=None):
    """A format-like check (no rule id, like AgentValidator's required-field
    check): ERROR when the attempt carries no X_LABEL."""
    if "X_LABEL" not in (proposal.reasoning or {}):
        return [ValidationResult(valid=False, validator_name="format",
                                 errors=["Response missing required fields: x"])]
    return [ValidationResult(valid=True, validator_name="format")]


class _Writer:
    def __init__(self):
        self.traces = []

    def write_trace(self, agent_type, trace, history):
        self.traces.append(trace)


def _run(eng, adapter, answers, prompts=None):
    _scripted(adapter, answers)
    eng.audit_writer = _Writer()

    def _llm(p):
        if prompts is not None:
            prompts.append(p)
        return "raw"

    result = eng.process_step(agent_id="A1", step_id=1, run_id="r", seed=1,
                              llm_invoke=_llm, agent_type="operator")
    return result, eng.audit_writer.traces[-1]


# ---------------------------------------------------------------------------
# config getters
# ---------------------------------------------------------------------------

def _cfg(raw: Dict[str, Any]) -> AgentTypeConfig:
    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = raw
    return cfg


def test_governance_getters_defaults_and_bool_only():
    assert _cfg({"global_config": {}}).get_governance_appraisal_freeze() is False
    assert _cfg({"global_config": {}}).get_governance_rule_id_prefix() is True
    on = _cfg({"global_config": {"governance": {"appraisal_freeze": True, "rule_id_prefix": False}}})
    assert on.get_governance_appraisal_freeze() is True
    assert on.get_governance_rule_id_prefix() is False
    # A quoted "false" is truthy: refused, never read as a bool.
    with pytest.raises(ValueError, match="appraisal_freeze"):
        _cfg({"global_config": {"governance": {"appraisal_freeze": "false"}}}
             ).get_governance_appraisal_freeze()
    with pytest.raises(ValueError, match="rule_id_prefix"):
        _cfg({"global_config": {"governance": {"rule_id_prefix": 0}}}
             ).get_governance_rule_id_prefix()


def test_audit_getters_defaults_and_validation():
    assert _cfg({"global_config": {}}).get_audit_attempt_columns() is False
    assert _cfg({"global_config": {}}).get_audit_state_columns() == []
    raw = {"global_config": {"audit": {"attempt_columns": True, "state_columns": ["a", "b"]}}}
    assert _cfg(raw).get_audit_attempt_columns() is True
    assert _cfg(raw).get_audit_state_columns() == ["a", "b"]
    for bad in ("a", ["a", ""], ["a", 3], ["a", "a"]):
        with pytest.raises(ValueError, match="state_columns"):
            _cfg({"global_config": {"audit": {"state_columns": bad}}}).get_audit_state_columns()
    with pytest.raises(ValueError, match="attempt_columns"):
        _cfg({"global_config": {"audit": {"attempt_columns": "yes"}}}).get_audit_attempt_columns()


def test_shipped_flood_config_resolved_option_set_2026_10():
    """Renamed from test_shipped_flood_config_keeps_every_new_option_off,
    which had come to directly contradict its own body -- the WRR26 rerun
    (flood design record, PI decision 2026-10-06 item 5, items 8, 9 and 13)
    has turned ON appraisal_freeze, retry_prompt_columns,
    initial_proposal_columns, corrected_status_columns, attempt_columns and
    plain_action_names for flood -- that is most of the new option set, not
    "every new option off". This test now simply pins the FULL resolved
    set, named for what it actually checks. rule_id_prefix is OFF (no
    "[Rule: ...]" prefix, so retry text names neither a label nor an
    internal rule id); state_columns remains empty. hide_registry_backstop_reports
    is ON since 2026-10-15: flood R5 (elevation_block, the only identity rule)
    got a plain message, and the registry's repeat of the same check
    ("Precondition failed: 'not elevated' ...") is left out of that retry, as in
    irrigation.

    Also pins the sampling values (item 13, spec item 37e: flood sends
    gemma3:4b's own Modelfile defaults explicitly) THROUGH
    ``get_llm_params("household")`` -- the actual merged
    shared/global/per-type dict ``ExperimentRunner.get_llm_invoke`` reads
    from, not a raw re-read of the YAML's ``global_config.llm`` block,
    which would miss an agent-type override and so could pass even if the
    household type never actually saw these values."""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    cfg = AgentTypeConfig.load(str(repo / "examples" / "single_agent" / "agent_types.yaml"))
    assert cfg.get_governance_appraisal_freeze() is True
    assert cfg.get_governance_rule_id_prefix() is False
    assert cfg.get_governance_plain_action_names() is True
    assert cfg.get_governance_hide_registry_backstop_reports() is True
    assert cfg.get_audit_attempt_columns() is True
    assert cfg.get_audit_state_columns() == []
    assert cfg.get_audit_retry_prompt_columns() is True
    assert cfg.get_audit_initial_proposal_columns() is True
    assert cfg.get_audit_corrected_status_columns() is True
    llm_params = cfg.get_llm_params("household")
    assert llm_params["temperature"] == 1.0
    assert llm_params["top_p"] == 0.95
    assert llm_params["top_k"] == 64


def test_shipped_flood_elevation_block_states_its_reason(monkeypatch):
    """Flood R5 (2026-10-15): an elevated household that proposes elevating
    again is told why in plain words, not the internal fallback
    ("Identity Block: elevate_house restricted by elevated"). Every profile
    that carries the rule has the same message; under ``relaxed`` it is a
    WARNING and never reaches the agent."""
    from pathlib import Path
    from broker.validators import AgentValidator

    repo = Path(__file__).resolve().parents[2]
    path = str(repo / "examples" / "single_agent" / "agent_types.yaml")
    expected = ("Elevation blocked under the rule on a house already elevated: your house "
                "is already elevated, and elevating it again is not available under this rule.")
    for profile in ("strict", "relaxed"):
        AgentTypeConfig.clear_cache()
        monkeypatch.setenv("GOVERNANCE_PROFILE", profile)
        results = AgentValidator(config_path=path).validate_identity(
            "household", "A1", "elevate_house", {"elevated": True})
        errors = [e for r in results for e in r.errors]
        warnings = [w for r in results for w in r.warnings]
        if profile == "strict":
            assert errors == [expected] and warnings == []
        else:
            assert errors == [] and warnings == [expected]
        assert AgentValidator(config_path=path).validate_identity(
            "household", "A1", "elevate_house", {"elevated": False}) == []
    AgentTypeConfig.clear_cache()


# ---------------------------------------------------------------------------
# the freeze module
# ---------------------------------------------------------------------------

def test_frozen_label_view_replaces_labels_only():
    retry = SkillProposal(skill_name="grow", agent_id="A1", agent_type="t",
                          reasoning={"X_LABEL": "M", "Y_LABEL": "L", "X_REASON": "new"},
                          magnitude_pct=12.0)
    frozen = {"X_LABEL": "H"}
    view = frozen_label_view(retry, frozen)
    # a frozen label wins over the attempt's restatement; a label nobody has
    # frozen yet keeps the attempt's value; non-label fields are the attempt's
    assert view.reasoning == {"X_LABEL": "H", "Y_LABEL": "L", "X_REASON": "new"}
    assert view.skill_name == "grow" and view.magnitude_pct == 12.0
    # the model's own proposal is untouched (the audit trail records it)
    assert retry.reasoning["X_LABEL"] == "M"
    assert construct_label_dict(retry) == {"X_LABEL": "M", "Y_LABEL": "L"}
    # no reasoning dict and nothing frozen: the attempt is checked as given
    bare = SkillProposal(skill_name="keep", agent_id="A1", agent_type="t", reasoning=None)
    assert frozen_label_view(bare, {}) is bare


def test_labels_freeze_the_first_time_they_are_stated():
    """WP3 review round 1 (HIGH 1): the frozen set grows by first
    statements only -- setdefault, and a blank value is not a statement."""
    from broker.core._appraisal_freeze import (
        freeze_first_stated_labels, stated_construct_labels,
    )

    def attempt(**labels):
        return SkillProposal(skill_name="keep", agent_id="A1", agent_type="t",
                             reasoning={"X_REASON": "r", **labels})

    frozen = stated_construct_labels(attempt(Y_LABEL="L", X_LABEL=""))
    assert frozen == {"Y_LABEL": "L"}          # blank X is not stated
    freeze_first_stated_labels(frozen, attempt(X_LABEL="H", Y_LABEL="VH"))
    assert frozen == {"Y_LABEL": "L", "X_LABEL": "H"}   # X first stated now; Y kept
    freeze_first_stated_labels(frozen, attempt(X_LABEL="M"))
    assert frozen == {"Y_LABEL": "L", "X_LABEL": "H"}   # a restatement never replaces


def test_label_keys_follow_the_parser_test():
    """WP3 review round 1 (LOW 7): a construct label is a key CONTAINING
    "_LABEL" (the parser's own test), not only one ending in it."""
    from broker.core._appraisal_freeze import is_construct_label_key

    assert is_construct_label_key("X_LABEL_V2") and is_construct_label_key("X_LABEL")
    assert not is_construct_label_key("x_label") and not is_construct_label_key(3)
    proposal = SkillProposal(skill_name="keep", agent_id="A1", agent_type="t",
                             reasoning={"X_LABEL_V2": "H", "X_REASON": "r"})
    assert construct_label_dict(proposal) == {"X_LABEL_V2": "H"}


# ---------------------------------------------------------------------------
# freeze in the engine
# ---------------------------------------------------------------------------

def test_freeze_off_relabel_passes_the_rule():
    """Default behaviour, unchanged: the retry's own relabelled appraisal is
    read, so rewriting H to M lets the same blocked skill through."""
    eng, rule, adapter = _engine()
    assert eng._appraisal_freeze is False
    result, _ = _run(eng, adapter, [("grow", "H"), ("grow", "M")])
    assert result.approved_skill.skill_name == "grow"
    assert result.retry_count == 1
    assert rule.seen == [("grow", "H"), ("grow", "M")]


def test_freeze_on_relabel_cannot_pass_the_rule():
    """First attempt H + grow is blocked; the retry relabels to M and asks
    for grow again -- still blocked, because the rule reads the frozen H;
    only a different skill passes. The relabel itself is logged."""
    eng, rule, adapter = _engine(freeze=True, attempt_columns=True)
    assert eng._appraisal_freeze is True
    result, trace = _run(eng, adapter, [("grow", "H"), ("grow", "M"), ("keep", "M")])
    assert result.approved_skill.skill_name == "keep"
    assert result.retry_count == 2
    # every validation pass read the FIRST attempt's label
    assert [label for _, label in rule.seen] == ["H", "H", "H"]
    row = trace_to_csv_row(trace)
    assert row["initial_labels"] == "X_LABEL=H"
    assert row["final_labels"] == "X_LABEL=M"
    assert row["appraisal_drift"] == "X_LABEL:H>M"
    assert row["attempt_skills"] == "grow|grow|keep"
    assert row["attempt_labels"] == "X_LABEL=H|X_LABEL=M|X_LABEL=M"
    assert row["attempt_failed_rules"] == f"{RULE_ID}|{RULE_ID}|"
    assert row["appraisal_relabeled"] is True


def test_freeze_recovers_a_label_the_first_parsed_attempt_omitted():
    """WP3 review round 1 (HIGH 1, the reviewer's scenario in generic form):
    the first parsed attempt carries no X_LABEL, the retry states it. The
    label is frozen at its first statement, so the retry passes -- exactly
    as with the freeze off. Pre-fix the view stripped the retry's label and
    the required-field check failed on every retry."""
    from broker.interfaces.skill_types import SkillOutcome

    eng, _, adapter = _engine(freeze=True, attempt_columns=True)
    eng.custom_validators.insert(0, _require_label)
    result, trace = _run(eng, adapter, [("keep", None)] + [("keep", "M")] * 3)
    assert result.outcome is SkillOutcome.RETRY_SUCCESS
    assert result.approved_skill.skill_name == "keep" and result.retry_count == 1
    row = trace_to_csv_row(trace)
    assert row["attempt_labels"] == "|X_LABEL=M"
    assert row["attempt_failed_rules"] == "Unknown|"
    assert row["appraisal_relabeled"] is False  # a first statement is not a relabel


def test_freeze_reads_the_first_stated_label_after_an_omission():
    """The first statement of X (H, on the first retry) is the one every
    later pass reads: a relabel to M cannot pass, only a different skill
    does. Pre-fix the stated label was stripped, so the rule never saw H."""
    from broker.interfaces.skill_types import SkillOutcome

    eng, rule, adapter = _engine(freeze=True)
    eng.custom_validators.insert(0, _require_label)
    result, _ = _run(eng, adapter, [("grow", None), ("grow", "H"), ("grow", "M"), ("keep", "M")])
    assert result.outcome is SkillOutcome.RETRY_SUCCESS
    assert result.approved_skill.skill_name == "keep" and result.retry_count == 3
    assert [label for _, label in rule.seen] == [None, "H", "H", "H"]


def test_appraisal_relabeled_counts_changes_after_the_first_statement():
    """WP3 review round 1 (HIGH 1), audit side: a relabel is a stated value
    other than the one the label was FIRST STATED with, the value the freeze
    holds. The round-1 column compared every retry with the first attempt,
    so a label stated for the first time after an omission, or a retry that
    left a label out, read as a relabel."""
    from broker.core._audit_helpers import _attempt_audit_columns

    def relabeled(*attempts):
        return _attempt_audit_columns(
            list(attempts), [[] for _ in attempts])["appraisal_relabeled"]

    assert relabeled({"X_LABEL": "H"}, {"X_LABEL": "M"}) is True
    assert relabeled({"X_LABEL": "H"}, {"X_LABEL": "H"}) is False
    # first statement after an omission: not a relabel
    assert relabeled({"Y_LABEL": "M"}, {"X_LABEL": "M", "Y_LABEL": "M"}) is False
    # a change after the first statement: a relabel
    assert relabeled({"Y_LABEL": "M"}, {"X_LABEL": "H", "Y_LABEL": "M"},
                     {"X_LABEL": "M", "Y_LABEL": "M"}) is True
    assert relabeled({}, {"X_LABEL": "H"}, {"X_LABEL": "M"}) is True
    # leaving a label out (missing, blank, unparsed attempt): not a relabel
    assert relabeled({"X_LABEL": "H"}, {"Y_LABEL": "M"}, None,
                     {"X_LABEL": "", "Y_LABEL": "M"}) is False


def test_attempt_failed_rules_name_ids_exactly_as_failed_rules():
    """WP3 review round 1 (LOW 7): the audit writer's failed_rules names a
    result by its rule_id, else "Unknown" -- never by rules_hit -- and so
    does attempt_failed_rules."""
    from broker.core._retry_loop import RetryMixin

    results = [
        ValidationResult(valid=False, validator_name="v", errors=["e"],
                         metadata={"rules_hit": ["only_hit"]}),
        ValidationResult(valid=False, validator_name="v", errors=["e"],
                         metadata={"rule_id": "named", "rules_hit": ["named"]}),
        ValidationResult(valid=True, validator_name="v", metadata={"rule_id": "passed"}),
    ]
    assert RetryMixin._failed_rule_ids(results) == ["Unknown", "named"]


def test_freeze_refused_with_multi_skill():
    from broker.core.skill_broker_engine import SkillBrokerEngine

    config = _config(freeze=True)
    config.items.return_value = [("operator", {"multi_skill": {"enabled": True}})]
    config.get_thinking_rules.return_value = []
    config.get_multi_skill_config.return_value = {"enabled": True, "max_skills": 2}
    with pytest.raises(ValueError, match="multi_skill"):
        SkillBrokerEngine(
            skill_registry=_registry(), model_adapter=UnifiedAdapter.__new__(UnifiedAdapter),
            validators=[], simulation_engine=None, context_builder=_Ctx(), config=config)
    config.get_multi_skill_config.return_value = {}
    SkillBrokerEngine(  # the same config without multi-skill is accepted
        skill_registry=_registry(), model_adapter=UnifiedAdapter.__new__(UnifiedAdapter),
        validators=[], simulation_engine=None, context_builder=_Ctx(), config=config)


def test_freeze_refused_without_a_checkable_config():
    """WP3 review round 1 (LOW 6): no callable items() means the thinking
    rules cannot be checked -- refused, never passed unchecked."""
    from broker.core.skill_broker_engine import SkillBrokerEngine

    config = _config(freeze=True)
    config.items = None
    with pytest.raises(ValueError, match="items"):
        SkillBrokerEngine(
            skill_registry=_registry(), model_adapter=UnifiedAdapter.__new__(UnifiedAdapter),
            validators=[], simulation_engine=None, context_builder=_Ctx(), config=config)


def test_freeze_refused_with_the_runner_cognitive_cache(tmp_path):
    """A cache hit re-validates a proposal from an earlier decision, outside
    the freeze: refused at runner construction, where the cache is set."""
    from broker.core.experiment_runner import ExperimentConfig, ExperimentRunner

    cached = ExperimentConfig(output_dir=tmp_path, enable_cognitive_cache=True)
    frozen_engine, _, _ = _engine(freeze=True)
    with pytest.raises(ValueError, match="enable_cognitive_cache"):
        ExperimentRunner(broker=frozen_engine, sim_engine=None, agents={}, config=cached)
    ExperimentRunner(broker=_engine()[0], sim_engine=None, agents={}, config=cached)
    ExperimentRunner(broker=frozen_engine, sim_engine=None, agents={},
                     config=ExperimentConfig(output_dir=tmp_path))


def test_aborted_sentinel_fills_state_and_attempt_columns():
    """WP3 review round 1 (LOW 5): an ABORTED row (nothing ever parsed)
    carries the state columns from the decision's state, and the per-attempt
    columns as "unobserved" -- not blank."""
    from broker.interfaces.skill_types import SkillOutcome

    eng, _, adapter = _engine(state={"alpha": 1.5}, attempt_columns=True,
                              state_columns=["alpha", "missing"])
    eng._corrected_status_columns = True  # sentinel rows exist only under this flag
    adapter.parse_output = lambda raw, ctx: None
    eng.audit_writer = _Writer()
    result = eng.process_step(agent_id="A1", step_id=1, run_id="r", seed=1,
                              llm_invoke=lambda p: "garbage", agent_type="operator")
    assert result.outcome is SkillOutcome.ABORTED
    row = trace_to_csv_row(eng.audit_writer.traces[-1])
    assert row["status"] == "ABORTED"
    assert row["state_alpha"] == 1.5 and row["state_missing"] == "unobserved"
    for key in ("attempt_labels", "attempt_failed_rules", "appraisal_relabeled"):
        assert row[key] == "unobserved", key


def test_hide_registry_backstop_reports_is_opt_in_and_narrow():
    """WP3 review round 1 (MEDIUM 2), generic: off by default; when on, the
    registry backstop results are left out of the retry reports ONLY when an
    identity rule blocked the same attempt."""
    from broker.interfaces.skill_types import IDENTITY_TIER

    identity = ValidationResult(
        valid=False, validator_name="AgentValidator:identity_error", errors=["at limit"],
        metadata={"tier": IDENTITY_TIER, "rule_id": "at_limit", "rules_hit": ["at_limit"]})
    precond = ValidationResult(
        valid=False, validator_name="registry", errors=["Precondition failed: 'not at_limit'"],
        metadata={"rule_id": "precondition_violation", "rules_hit": ["precondition_violation"]})
    schema = ValidationResult(
        valid=False, validator_name="registry", errors=["Required field 'decision' missing"],
        metadata={"rule_id": "output_schema_violation", "rules_hit": ["output_schema_violation"]})
    other = ValidationResult(valid=False, validator_name="v", errors=["x"], metadata={"rule_id": "other"})
    assert _cfg({"global_config": {}}).get_governance_hide_registry_backstop_reports() is False
    eng, _, _ = _engine()
    assert eng._hide_registry_backstop_reports is False
    everything = [identity, precond, schema, other]
    assert eng._retry_report_results(everything) == everything
    eng._hide_registry_backstop_reports = True
    assert eng._retry_report_results(everything) == [identity, other]
    assert eng._retry_report_results([precond, schema, other]) == [precond, schema, other]


def test_identity_tier_has_one_definition_for_the_validator_and_the_filter(
        tmp_path, monkeypatch):
    """The backstop filter recognises an identity block by the tier
    ``AgentValidator.validate_identity`` stamps. Both import ONE definition
    (``skill_types.IDENTITY_TIER``), so the writer and the reader cannot drift
    apart, and a real identity block is recognised by the filter."""
    from broker.core import _retry_loop
    from broker.interfaces import skill_types
    from broker.validators import AgentValidator
    from broker.validators.agent import agent_validator

    assert _retry_loop.IDENTITY_TIER is skill_types.IDENTITY_TIER
    assert agent_validator.IDENTITY_TIER is skill_types.IDENTITY_TIER
    monkeypatch.setenv("GOVERNANCE_PROFILE", "default")
    path = _yaml(tmp_path, _RULES_YAML.format(
        freeze="false", prefix="false", rule_id="r_x", construct="X_LABEL"))
    identity = AgentValidator(config_path=path).validate_identity(
        "operator", "A1", "grow", {"at_limit": True})
    assert [r.metadata["tier"] for r in identity] == [skill_types.IDENTITY_TIER]
    precond = ValidationResult(valid=False, validator_name="registry", errors=["p"],
                               metadata={"rule_id": "precondition_violation"})
    eng, _, _ = _engine()
    eng._hide_registry_backstop_reports = True
    assert eng._retry_report_results(identity + [precond]) == identity
    AgentTypeConfig.clear_cache()


def test_freeze_on_without_relabel_changes_nothing():
    eng, rule, adapter = _engine(freeze=True)
    result, _ = _run(eng, adapter, [("grow", "M")])
    assert result.approved_skill.skill_name == "grow"
    assert result.retry_count == 0


def test_run_validators_passes_the_same_proposal_without_the_key():
    """Freeze off never builds a view: the validators get the very object."""
    eng, _, _ = _engine()
    seen = []
    eng.custom_validators = [lambda p, c, r=None: seen.append(p) or []]
    proposal = SkillProposal(skill_name="grow", agent_id="A1", agent_type="t",
                             reasoning={"X_LABEL": "M"})
    eng._run_validators(proposal, {"agent_type": "t"})
    assert seen[0] is proposal
    eng._run_validators(proposal, {"agent_type": "t", FROZEN_LABELS_CONTEXT_KEY: {"X_LABEL": "H"}})
    assert seen[1] is not proposal and seen[1].reasoning["X_LABEL"] == "H"


def test_feasible_probe_uses_frozen_labels():
    """The feasible-action line lists the actions that pass every rule, and
    under the freeze every rule reads the first attempt's label: an attempt
    relabelled to M must not see grow listed as feasible."""
    eng, _, _ = _engine(freeze=True, feasible=True)
    relabelled = SkillProposal(skill_name="grow", agent_id="A1", agent_type="operator",
                               reasoning={"X_LABEL": "M"})
    context = {"agent_type": "operator"}
    frozen_context = {**context, FROZEN_LABELS_CONTEXT_KEY: {"X_LABEL": "H"}}
    assert eng._probe_feasible_skills(relabelled, context, "operator", {}) == list(SKILLS)
    assert eng._probe_feasible_skills(relabelled, frozen_context, "operator", {}) == ["keep", "shrink"]


def test_feasible_line_in_the_retry_prompt_uses_frozen_labels():
    eng, _, adapter = _engine(freeze=True, feasible=True)
    prompts: List[str] = []
    _run(eng, adapter, [("grow", "H"), ("grow", "M"), ("keep", "M")], prompts=prompts)
    # prompts[0] is the first attempt; prompts[2] answers the relabelled attempt
    assert "Actions that pass every rule this step: 2 (keep), 3 (shrink)." in prompts[2]


def test_attempt_columns_off_adds_no_key():
    eng, _, adapter = _engine(freeze=True)
    _, trace = _run(eng, adapter, [("grow", "H"), ("keep", "H")])
    row = trace_to_csv_row(trace)
    for key in ("attempt_labels", "attempt_failed_rules", "appraisal_relabeled"):
        assert key not in trace and key not in row


def test_attempt_columns_name_an_unnamed_failure_like_failed_rules():
    """An ERROR without a rule id is 'Unknown' per attempt, exactly as the
    failed_rules column names it -- never an empty (passing-looking) slot."""
    eng, _, adapter = _engine(attempt_columns=True)
    eng.custom_validators = [lambda p, c, r=None: [
        ValidationResult(valid=p.skill_name != "grow", validator_name="anon",
                         errors=[] if p.skill_name != "grow" else ["no"])]]
    _, trace = _run(eng, adapter, [("grow", "M"), ("keep", "M")])
    assert trace_to_csv_row(trace)["attempt_failed_rules"] == "Unknown|"


def test_attempt_columns_refused_with_an_advisory_channel():
    from broker.core.skill_broker_engine import SkillBrokerEngine

    with pytest.raises(ValueError, match="attempt_columns"):
        SkillBrokerEngine(
            skill_registry=_registry(), model_adapter=UnifiedAdapter.__new__(UnifiedAdapter),
            validators=[], simulation_engine=None, context_builder=_Ctx(),
            config=_config(attempt_columns=True, advise_mode="record"),
        )


def test_state_columns():
    eng, _, adapter = _engine(state={"alpha": 1.5, "beta": "x"},
                              state_columns=["alpha", "missing"])
    _, trace = _run(eng, adapter, [("keep", "M")])
    row = trace_to_csv_row(trace)
    assert row["state_alpha"] == 1.5
    assert row["state_missing"] == "unobserved"
    assert "state_beta" not in row
    # off: no trace key, no column
    eng2, _, adapter2 = _engine(state={"alpha": 1.5})
    _, trace2 = _run(eng2, adapter2, [("keep", "M")])
    assert "audit_state" not in trace2
    assert not [k for k in trace_to_csv_row(trace2) if k.startswith("state_")]


# ---------------------------------------------------------------------------
# YAML-driven: freeze coverage guard, rule_id_prefix, suggestion
# ---------------------------------------------------------------------------

def _yaml(tmp_path, body: str) -> str:
    path = tmp_path / "agent_types.yaml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    AgentTypeConfig.clear_cache()
    return str(path)


_RULES_YAML = """
    global_config:
      governance:
        appraisal_freeze: {freeze}
        rule_id_prefix: {prefix}
    operator:
      governance:
        default:
          thinking_rules:
            - id: {rule_id}
              conditions: [{{ construct: {construct}, values: ["H", "VH"] }}]
              blocked_skills: ["grow"]
              level: ERROR
              message: "Grow is not available while X is high."
              suggestion: "Choose keep or shrink."
          identity_rules:
            - id: at_limit
              precondition: at_limit
              blocked_skills: ["grow"]
              level: ERROR
              message: "Grow is not available at the limit."
"""


def _yaml_engine(path):
    from broker.core.skill_broker_engine import SkillBrokerEngine
    from broker.validators import AgentValidator

    config = AgentTypeConfig.load(path)
    return SkillBrokerEngine(
        skill_registry=_registry(), model_adapter=UnifiedAdapter.__new__(UnifiedAdapter),
        validators=[AgentValidator(config_path=path)], simulation_engine=None,
        context_builder=_Ctx(), config=config,
    )


def test_freeze_refuses_a_rule_on_a_construct_it_does_not_cover(tmp_path, monkeypatch):
    monkeypatch.setenv("GOVERNANCE_PROFILE", "default")
    path = _yaml(tmp_path, _RULES_YAML.format(
        freeze="true", prefix="true", rule_id="r_risk", construct="RISK"))
    with pytest.raises(ValueError, match="r_risk"):
        _yaml_engine(path)
    ok = _yaml(tmp_path, _RULES_YAML.format(
        freeze="true", prefix="true", rule_id="r_x", construct="X_LABEL"))
    assert _yaml_engine(ok)._appraisal_freeze is True
    AgentTypeConfig.clear_cache()


@pytest.mark.parametrize("prefix,expected_start", [("true", "[Rule: r_x] "), ("false", "Grow is")])
def test_rule_id_prefix_and_suggestion(tmp_path, monkeypatch, prefix, expected_start):
    from broker.core._advise import build_intervention_reports
    from broker.validators import AgentValidator

    monkeypatch.setenv("GOVERNANCE_PROFILE", "default")
    path = _yaml(tmp_path, _RULES_YAML.format(
        freeze="false", prefix=prefix, rule_id="r_x", construct="X_LABEL"))
    validator = AgentValidator(config_path=path)
    thinking = validator.validate_thinking("operator", "A1", "grow", {}, {"X_LABEL": "H"})
    identity = validator.validate_identity("operator", "A1", "grow", {"at_limit": True})
    assert thinking[0].errors[0].startswith(expected_start)
    assert identity[0].errors[0].startswith(
        "[Rule: at_limit] " if prefix == "true" else "Grow is not available at the limit.")
    # the YAML suggestion reaches the retry report's Suggestion line
    proposal = SkillProposal(skill_name="grow", agent_id="A1", agent_type="operator",
                             reasoning={"X_LABEL": "H"})
    reports = build_intervention_reports(thinking, proposal, source="errors")
    assert reports[0].suggested_correction == "Choose keep or shrink."
    assert "  - Suggestion: Choose keep or shrink." in reports[0].to_prompt_string()
    AgentTypeConfig.clear_cache()


def test_flood_messages_drop_the_rule_prefix(monkeypatch):
    """2026-10 WRR26 rerun (coordinator decision on open point 2, following
    irrigation's own WP3.5): flood now sets ``rule_id_prefix: false``, so a
    triggered rule's message carries NO "[Rule: <id>] " prefix -- a retry
    prompt names neither a label value nor an internal rule id.

    Also (item 9, neutral retry text): ``relocation_threat_low`` carries a
    ``suggestion`` (irrigation-style neutral wording, no label code) whose
    text itself names no rule id either.
    """
    from pathlib import Path

    from broker.validators import AgentValidator

    monkeypatch.setenv("GOVERNANCE_PROFILE", "strict")
    repo = Path(__file__).resolve().parents[2]
    validator = AgentValidator(config_path=str(repo / "examples" / "single_agent" / "agent_types.yaml"))
    assert validator.rule_id_prefix is False
    results = validator.validate_thinking(
        "household", "H1", "relocate", {}, {"TP_LABEL": "VL", "CP_LABEL": "H"})
    blocked = [r for r in results if not r.valid]
    assert blocked and all(not r.errors[0].startswith("[Rule: ") for r in blocked)
    assert blocked and all("[Rule:" not in r.errors[0] for r in blocked)
    for r in blocked:
        suggestion = r.metadata.get("suggestion", "")
        assert suggestion and "[Rule:" not in suggestion
        for code in ("VL", "L", "M", "H", "VH"):
            assert f" {code} " not in f" {suggestion} "
    AgentTypeConfig.clear_cache()
