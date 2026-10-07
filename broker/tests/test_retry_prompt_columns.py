"""``global_config.audit.retry_prompt_columns`` (default off; P2-b, opus
review of the flood WRR26 rerun): the exact text sent on each governance
retry, recorded into the raw JSONL trace's ``retry_prompts`` key.

Generic framework feature (no domain words): lives in
``broker/core/_retry_loop.py`` (``RetryMixin._governance_retry_loop``'s
``attempt_prompts`` parameter), ``broker/core/skill_broker_engine.py``
(flag resolution + wiring), ``broker/core/_audit_helpers.py``
(``AuditMixin._write_audit_trace``'s ``attempt_prompts`` parameter and the
``retry_prompt_extra`` dict), and ``broker/utils/agent_config.py``
(``AgentTypeConfig.get_audit_retry_prompt_columns``).

Reuses the ``_Host``/``_retry_kwargs``/``_rejected_results`` harness from
``test_retry_feedback_placebo.py`` and the silent-mode import from
``test_retry_feedback_silent.py`` rather than re-deriving them, so this file
tests the SAME retry loop those files already exercise, with one more
parameter wired through.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from broker.interfaces.skill_types import SkillProposal, ValidationResult

from test_retry_feedback_placebo import (
    LEGACY_HEADER,
    ORIGINAL_PROMPT,
    RULE_ID,
    _Host,
    _rejected_results,
    _retry_kwargs,
)


# ---------------------------------------------------------------------------
# Config getter: default False, non-bool raises (mirrors every sibling
# opt-in getter's own test, e.g. test_appraisal_freeze.py's
# test_audit_getters_defaults_and_validation).
# ---------------------------------------------------------------------------

def _cfg(d):
    from broker.utils.agent_config import AgentTypeConfig
    c = AgentTypeConfig.__new__(AgentTypeConfig)
    c._config = d
    return c


def test_getter_defaults_false():
    assert _cfg({"global_config": {}}).get_audit_retry_prompt_columns() is False
    assert _cfg({}).get_audit_retry_prompt_columns() is False
    assert _cfg({"global_config": {"audit": {}}}).get_audit_retry_prompt_columns() is False


def test_getter_reads_true():
    cfg = _cfg({"global_config": {"audit": {"retry_prompt_columns": True}}})
    assert cfg.get_audit_retry_prompt_columns() is True


def test_getter_rejects_non_bool():
    with pytest.raises(ValueError, match="retry_prompt_columns"):
        _cfg({"global_config": {"audit": {"retry_prompt_columns": "yes"}}}
             ).get_audit_retry_prompt_columns()
    with pytest.raises(ValueError, match="retry_prompt_columns"):
        _cfg({"global_config": {"audit": {"retry_prompt_columns": 1}}}
             ).get_audit_retry_prompt_columns()


# ---------------------------------------------------------------------------
# _governance_retry_loop: off -> untouched; on -> len == retry_count, [] with
# no retry.
# ---------------------------------------------------------------------------

def _fixed_invoke(skill_name="do_nothing"):
    def llm_invoke(prompt):
        return SkillProposal(skill_name=skill_name, agent_id="H01",
                              agent_type="household", reasoning={})
    return llm_invoke


def test_off_leaves_attempt_prompts_none_and_nothing_is_appended():
    host = _Host(retry_feedback_mode="full")
    result = host._governance_retry_loop(
        llm_invoke=_fixed_invoke(), attempt_prompts=None, **_retry_kwargs())
    # The parameter defaults to None and the loop never assigns it back --
    # nothing to assert on the return value itself; the real assertion is
    # that passing None raises nothing (no "NoneType has no append" crash).
    assert result[5] == 1  # retry_count: the loop still ran as normal


def test_on_records_one_entry_per_retry_attempt():
    """max_retries=1 on _Host (test_retry_feedback_placebo.py): exactly one
    retry attempt happens before the loop returns (the fixed validator
    always rejects, so all_valid stays False and retry_count reaches 1)."""
    host = _Host(retry_feedback_mode="full")
    attempt_prompts = []
    result = host._governance_retry_loop(
        llm_invoke=_fixed_invoke(), attempt_prompts=attempt_prompts, **_retry_kwargs())
    retry_count = result[5]
    assert retry_count == 1
    assert len(attempt_prompts) == retry_count == 1
    assert ORIGINAL_PROMPT in attempt_prompts[0]
    assert RULE_ID in attempt_prompts[0]  # full mode: real rule content


def test_on_records_three_entries_across_three_retries():
    class _AlwaysRejectHost(_Host):
        max_retries = 3
        # The exhaustion-diagnostics branch reads self.skill_registry to name
        # the fallout skill when every retry is exhausted (same idiom as
        # test_retry_feedback_silent.py's own _AlwaysRejectHost).
        skill_registry = SimpleNamespace(
            get_default_skill=lambda: "do_nothing",
            exists=lambda skill_name: True,
        )

        def _run_validators(self, proposal, context):
            return _rejected_results()

    host = _AlwaysRejectHost(retry_feedback_mode="full")
    attempt_prompts = []
    result = host._governance_retry_loop(
        llm_invoke=_fixed_invoke(), attempt_prompts=attempt_prompts, **_retry_kwargs())
    retry_count = result[5]
    assert retry_count == 3
    assert len(attempt_prompts) == 3 == retry_count


def test_on_is_empty_list_when_the_initial_attempt_already_passes():
    """all_valid=True from the start: the while loop body never executes,
    so a pre-allocated attempt_prompts list stays exactly as given -- []."""
    host = _Host(retry_feedback_mode="full")
    attempt_prompts = []
    kwargs = _retry_kwargs()
    kwargs["all_valid"] = True
    kwargs["validation_results"] = [ValidationResult(valid=True, validator_name="ok")]
    host._governance_retry_loop(
        llm_invoke=_fixed_invoke(), attempt_prompts=attempt_prompts, **kwargs)
    assert attempt_prompts == []


# ---------------------------------------------------------------------------
# full, placebo and silent each record what was ACTUALLY sent (not a
# reconstruction) -- the whole point of the feature.
# ---------------------------------------------------------------------------

def test_full_mode_records_the_real_header_rule_and_original_prompt():
    host = _Host(retry_feedback_mode="full")
    attempt_prompts = []
    host._governance_retry_loop(
        llm_invoke=_fixed_invoke(), attempt_prompts=attempt_prompts, **_retry_kwargs())
    assert len(attempt_prompts) == 1
    assert LEGACY_HEADER in attempt_prompts[0]
    assert RULE_ID in attempt_prompts[0]
    assert ORIGINAL_PROMPT in attempt_prompts[0]


def test_placebo_mode_records_the_wrapper_only_text_no_rule_content():
    host = _Host(retry_feedback_mode="placebo")
    attempt_prompts = []
    host._governance_retry_loop(
        llm_invoke=_fixed_invoke(), attempt_prompts=attempt_prompts, **_retry_kwargs())
    assert len(attempt_prompts) == 1
    assert LEGACY_HEADER in attempt_prompts[0]
    assert RULE_ID not in attempt_prompts[0]
    assert ORIGINAL_PROMPT in attempt_prompts[0]


def test_silent_mode_records_the_original_prompt_byte_for_byte():
    """The real falsifying case: silent mode's recorded text must be
    IDENTICAL to the original prompt, not merely similar -- this is the
    exact property test_retry_feedback_silent.py's own test (a) checks for
    the prompt SENT; here we check the prompt RECORDED is the same string."""
    host = _Host(retry_feedback_mode="silent")
    attempt_prompts = []
    host._governance_retry_loop(
        llm_invoke=_fixed_invoke(), attempt_prompts=attempt_prompts, **_retry_kwargs())
    assert len(attempt_prompts) == 1
    assert attempt_prompts[0] == ORIGINAL_PROMPT


def test_silent_mode_records_the_same_text_on_every_retry_attempt():
    class _AlwaysRejectHost(_Host):
        max_retries = 3
        skill_registry = SimpleNamespace(
            get_default_skill=lambda: "do_nothing",
            exists=lambda skill_name: True,
        )

        def _run_validators(self, proposal, context):
            return _rejected_results()

    host = _AlwaysRejectHost(retry_feedback_mode="silent")
    attempt_prompts = []
    host._governance_retry_loop(
        llm_invoke=_fixed_invoke(), attempt_prompts=attempt_prompts, **_retry_kwargs())
    assert len(attempt_prompts) == 3
    assert all(p == ORIGINAL_PROMPT for p in attempt_prompts)


# ---------------------------------------------------------------------------
# trace_to_csv_row never emits retry_prompts as a CSV column.
# ---------------------------------------------------------------------------

def test_trace_to_csv_row_never_emits_retry_prompts():
    from broker.components.analytics.audit import trace_to_csv_row

    trace = {
        "run_id": "r1", "step_id": "s1", "agent_id": "H01", "year": 1,
        "input": ORIGINAL_PROMPT, "raw_output": "{}",
        "retry_prompts": [f"{LEGACY_HEADER}\n\n{ORIGINAL_PROMPT}"],
        "skill_proposal": None, "approved_skill": None,
        "execution_result": None, "outcome": "APPROVED",
        "retry_count": 1, "format_retries": 0,
        "llm_stats": {}, "memory_audit": {}, "social_audit": {},
        "rule_breakdown": {},
    }
    row = trace_to_csv_row(trace)
    assert "retry_prompts" not in row


# ---------------------------------------------------------------------------
# Engine wiring: __init__ resolves the flag; process_step seeds the list
# correctly (empty when on, None when off).
# ---------------------------------------------------------------------------

def _engine_config(**overrides) -> MagicMock:
    config = MagicMock()
    config.get_governance_retry_feedback_mode.return_value = "full"
    config.get_governance_advise.return_value = None
    config.get_governance_advise_mode.return_value = "off"
    config.get_governance_intervention_framing.return_value = "legacy"
    config.get_governance_on_retry_exhausted.return_value = "default"
    config.get_audit_advise_columns.return_value = False
    config.get_audit_attempt_columns.return_value = False
    config.get_audit_retry_prompt_columns.return_value = False
    config.get_governance_appraisal_freeze.return_value = False
    config.get_governance_rule_id_prefix.return_value = True
    config.get_governance_hide_registry_backstop_reports.return_value = False
    config.get_audit_state_columns.return_value = []
    for key, value in overrides.items():
        getattr(config, key).return_value = value
    return config


def _build_engine(config):
    from broker.core.skill_broker_engine import SkillBrokerEngine
    from broker.components.governance.registry import SkillRegistry

    class _EngineCtx:
        def build(self, agent_id, env_context=None, **kwargs):
            return {"agent_id": agent_id, "state": {}}

        def format_prompt(self, context):
            return "PROMPT"

    return SkillBrokerEngine(
        skill_registry=SkillRegistry(),
        model_adapter=MagicMock(),
        validators=[MagicMock()],
        simulation_engine=None,
        context_builder=_EngineCtx(),
        config=config,
    )


def test_engine_reads_the_getter_into_retry_prompt_columns_flag():
    config = _engine_config(get_audit_retry_prompt_columns=True)
    eng = _build_engine(config)
    assert eng._retry_prompt_columns is True
    config.get_audit_retry_prompt_columns.assert_called_once()


def test_engine_defaults_flag_false_when_getter_absent():
    """Simulates a config object with no ``get_audit_retry_prompt_columns``
    attribute at all (e.g. a non-AgentTypeConfig embedding that predates
    this feature): ``skill_broker_engine.py`` reads it via
    ``getattr(self.config, "get_audit_retry_prompt_columns", None)``, so
    setting the attribute to plain ``None`` (not a callable) reproduces
    "attribute absent" without restricting every OTHER getter the engine's
    own __init__ needs (a MagicMock(spec=[]) would have blocked those too)."""
    config = _engine_config()
    config.get_audit_retry_prompt_columns = None
    eng = _build_engine(config)
    assert eng._retry_prompt_columns is False
