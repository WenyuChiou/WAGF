"""Third retry-feedback arm: ``global_config.governance.retry_feedback_mode: silent``.

See ``broker/tests/test_retry_feedback_placebo.py`` for the full design
history of the ``full``/``placebo`` pair (red-team objection 3). ``silent``
is a strictly MORE content-free control than ``placebo``: ``placebo`` still
keeps the adapter's wrapper framing ("your previous response was
flagged/triggered the governance layer... please reconsider"); ``silent``
removes that too. Under ``silent`` the governance retry loop
(``RetryMixin._governance_retry_loop``, ``broker/core/_retry_loop.py``)
re-sends the ORIGINAL prompt byte-for-byte on every retry attempt -- no
header, no closer, no rules block, no "attempt N" text, nothing -- so the
only thing that can differ between attempts is the LLM's own sampling.
Validators, retry count, ``on_retry_exhausted``, and the audit trail
(``retry_count`` / ``failed_rules`` / initial-proposal columns) are all
unchanged from ``full``/``placebo``.

FALSIFICATION: test (a) below
(``test_silent_retry_prompt_equals_initial_prompt_across_three_retries``) was
run against a temporarily stashed diff of this feature (``git stash push --
broker/core/_retry_loop.py broker/core/skill_broker_engine.py
broker/utils/agent_config.py broker/experiments/replay.py
examples/single_agent/run_flood.py broker/tools/validate_prompt.py``,
reproducing the ``origin/main`` state exactly) and FAILED with
``ValueError: _retry_feedback_mode='silent' is not 'full' or 'placebo'`` --
pre-change code has no ``silent`` concept at all. Restored immediately
afterward (``git stash pop``). Exact commands + output in the PR
description.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from broker.components.governance.registry import SkillRegistry
from broker.interfaces.skill_types import SkillDefinition, SkillProposal, ValidationResult
from broker.utils.parsing.unified_adapter import UnifiedAdapter

from test_retry_feedback_placebo import (
    LEGACY_HEADER,
    LEGACY_CLOSER,
    ORIGINAL_PROMPT,
    REASON_TEXT,
    RULE_ID,
    _Host,
    _rejected_results,
    _retry_kwargs,
    _run_retry_loop,
)


# ---------------------------------------------------------------------------
# (a) silent retry prompt == initial prompt, byte equality, across 3 retries
# ---------------------------------------------------------------------------

def test_silent_retry_prompt_equals_initial_prompt_across_three_retries():
    """THE falsified assertion. `max_retries=3` and a validator that ALWAYS
    rejects (non-deterministic, so EarlyExit never fires) forces the loop
    through every attempt -- a mutation that only survived attempt 1 would be
    caught here."""
    class _AlwaysRejectHost(_Host):
        max_retries = 3
        # The exhaustion-diagnostics branch reads `self.skill_registry` to
        # name the fallout skill; `_Host` (test_retry_feedback_placebo.py)
        # never needed one because its own `_run_validators` always
        # succeeds and the loop never exhausts.
        skill_registry = SimpleNamespace(
            get_default_skill=lambda: "do_nothing",
            exists=lambda skill_name: True,
        )

        def _run_validators(self, proposal, context):
            return _rejected_results()

    host = _AlwaysRejectHost(retry_feedback_mode="silent")
    captured = []

    def llm_invoke(retry_prompt):
        captured.append(retry_prompt)
        return SkillProposal(
            skill_name="elevate_structure", agent_id="H01",
            agent_type="household", reasoning={},
        )

    result = host._governance_retry_loop(llm_invoke=llm_invoke, **_retry_kwargs())
    retry_count = result[5]

    assert retry_count == 3, "EarlyExit fired; test is not exercising 3 full retries"
    assert len(captured) == 3
    for i, prompt in enumerate(captured, start=1):
        assert prompt == ORIGINAL_PROMPT, f"attempt {i} retry prompt != initial prompt"


def test_silent_mode_never_calls_the_adapters_render_methods():
    """Belt-and-braces: `silent` must not even reach `format_intervention_prompt`
    / `format_retry_prompt` -- an adapter whose render methods raise must not
    break a silent run, because `_governance_retry_loop` never calls them."""
    class _ExplodingAdapter:
        def format_intervention_prompt(self, *a, **k):
            raise AssertionError("silent mode must not call format_intervention_prompt")

        def format_retry_prompt(self, *a, **k):
            raise AssertionError("silent mode must not call format_retry_prompt")

        def parse_output(self, raw_output, context):
            return raw_output if isinstance(raw_output, SkillProposal) else None

    prompt = _run_retry_loop(_Host(retry_feedback_mode="silent", adapter=_ExplodingAdapter()))
    assert prompt == ORIGINAL_PROMPT


def test_silent_mode_suppresses_the_format_violation_synthetic_report_too():
    """Same discipline as placebo's own
    `test_format_violation_path_under_placebo_has_no_parsing_language`: an
    UNPARSABLE retry attempt builds a synthetic `format_violation` report,
    and `silent` must suppress it exactly like any other rule content --
    trivially true here since `silent` never renders reports at all, but
    pinned so a future refactor that special-cases the format-violation path
    cannot silently reintroduce it."""
    prompt = _run_retry_loop(_Host(retry_feedback_mode="silent"), skill_proposal=None)
    assert prompt == ORIGINAL_PROMPT
    for forbidden in ("delimiter", "JSON structure", "required fields", "parsing", RULE_ID, REASON_TEXT):
        assert forbidden not in prompt


# ---------------------------------------------------------------------------
# (b) full and placebo prompts unchanged vs today (regression against the
#     placebo test's own fixtures / golden text)
# ---------------------------------------------------------------------------

def test_full_mode_prompt_unchanged_by_the_silent_addition():
    """Adding the `silent` branch to `_governance_retry_loop` must not alter
    `full`'s rendering at all."""
    prompt = _run_retry_loop(_Host(retry_feedback_mode="full"))
    assert RULE_ID in prompt
    assert REASON_TEXT in prompt
    assert ORIGINAL_PROMPT in prompt


def test_placebo_mode_golden_text_unchanged_by_the_silent_addition():
    """Regression: pins the EXACT placebo golden text (same assertion as
    test_retry_feedback_placebo.py's own pin). The new
    `if _retry_feedback_mode == "silent":` branch sits strictly BEFORE the
    placebo branches in `_retry_loop.py` and must never intercept them."""
    prompt = _run_retry_loop(_Host(retry_feedback_mode="placebo", framing="legacy"))
    assert prompt == f"{LEGACY_HEADER}\n\n{LEGACY_CLOSER}\n\n{ORIGINAL_PROMPT}"


# ---------------------------------------------------------------------------
# (c) manifest records retry_feedback_mode: silent
# ---------------------------------------------------------------------------

def test_manifest_records_resolved_retry_feedback_mode_silent(monkeypatch):
    from broker.core.experiment_runner import ExperimentRunner

    monkeypatch.setattr(
        "requests.post",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network disabled in test")),
    )

    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.config = SimpleNamespace(model="mock")
    runner.broker = SimpleNamespace(
        _retry_feedback_mode="silent",
        model_adapter=SimpleNamespace(config_path=None),
    )

    metadata = runner._collect_reproducibility_metadata()
    assert metadata["retry_feedback_mode"] == "silent"
    assert "thinking_mode" in metadata


def test_w5b_run_parity_benchmark_cli_override_silent_reaches_manifest_and_snapshot(tmp_path):
    """End-to-end mirror of test_retry_feedback_placebo.py's own
    `test_w5b_run_parity_benchmark_cli_override_reaches_manifest_and_snapshot`,
    for `silent`: a mock (`--model mock`) run through the real CLI entry
    point (called directly, bypassing argparse) must apply the override to
    the live engine and have it read back from BOTH the reproducibility
    manifest and config_snapshot.yaml's injected metadata."""
    import json

    import yaml

    import examples.single_agent.run_flood as run_flood_mod

    run_flood_mod.run_parity_benchmark(
        model="mock", years=1, agents_count=3, seed=42,
        custom_output=str(tmp_path), retry_feedback_mode="silent",
    )

    manifest = json.loads(
        (tmp_path / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    assert manifest["retry_feedback_mode"] == "silent"

    snapshot_path = tmp_path / "config_snapshot.yaml"
    assert snapshot_path.exists()
    snapshot = yaml.safe_load(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["metadata"]["retry_feedback_mode"] == "silent"
    assert "retry_feedback_mode" not in (
        snapshot.get("global_config", {}).get("governance", {}) or {})


# ---------------------------------------------------------------------------
# (d) audit row on a silent run still has retry_count and failed_rules
# ---------------------------------------------------------------------------

class _Ctx:
    def build(self, agent_id, env_context=None, **kwargs):
        return {"agent_id": agent_id, "state": {}}

    def format_prompt(self, context):
        return "PROMPT"


def _silent_engine(*, max_retries=2):
    """A full `SkillBrokerEngine` wired for `retry_feedback_mode="silent"`
    whose single validator ALWAYS rejects `elevate_structure` -- forces the
    governance retry loop to exhaustion so `retry_count` and `failed_rules`
    are both non-trivial in the resulting audit row."""
    registry = SkillRegistry()
    for sid in ("do_nothing", "elevate_structure"):
        registry.register(SkillDefinition(
            skill_id=sid, description=sid, eligible_agent_types=["*"],
            preconditions=[], institutional_constraints={},
            allowed_state_changes=[], implementation_mapping=sid,
        ))
    registry.set_default_skill("do_nothing")

    proposals = iter([
        SkillProposal(skill_name="elevate_structure", agent_id="H01",
                      agent_type="household", reasoning={})
        for _ in range(max_retries + 3)
    ])

    def _parse(_raw, _ctx):
        return next(proposals)

    adapter = UnifiedAdapter.__new__(UnifiedAdapter)
    adapter.parse_output = _parse

    def _validate(proposal, _ctx, _reg=None):
        return ValidationResult(
            valid=False, validator_name="AgentValidator:thinking_error",
            errors=[f"[Rule: {RULE_ID}] {REASON_TEXT}"],
            # `rule_id` (singular) is what the REAL `GenericAuditWriter`
            # reads to build `validation_issues` -> `failed_rules`
            # (`broker/components/analytics/audit.py` ~line 1168);
            # `rules_hit` (list) is the separate convention
            # `_extract_blocking_rule_ids`/EarlyExit reads. A custom
            # validator authors both, matching the documented split in
            # `_retry_loop.py`'s module docstring.
            metadata={"rule_id": RULE_ID, "rules_hit": [RULE_ID], "deterministic": False},
        )

    validator = MagicMock()
    validator.validate.side_effect = _validate

    config = MagicMock()
    config.get_log_fields.return_value = []
    config.get_governance_retries.return_value = max_retries
    config.get_governance_max_reports.return_value = 3
    config.get_multi_skill_config.return_value = {}
    config.get_audit_initial_proposal_columns.return_value = False
    config.get_audit_executed_columns.return_value = False
    config.get_audit_advise_columns.return_value = False
    config.get_governance_advise.return_value = None
    config.get_governance_advise_mode.return_value = "off"
    config.get_governance_intervention_framing.return_value = "legacy"
    config.get_governance_on_retry_exhausted.return_value = "default"
    config.get_governance_retry_feedback_mode.return_value = "silent"

    from broker.core.skill_broker_engine import SkillBrokerEngine

    eng = SkillBrokerEngine(
        skill_registry=registry, model_adapter=adapter, validators=[validator],
        simulation_engine=None, context_builder=_Ctx(), config=config,
    )
    assert eng._retry_feedback_mode == "silent"
    return eng


def test_silent_mode_audit_row_still_has_retry_count_and_failed_rules(tmp_path):
    """Retry-feedback mode governs the retry PROMPT text only; the audit
    plane must be completely unaffected under `silent`, exactly as documented
    for `full`/`placebo` (`broker/core/_audit_helpers.py` populates
    `retry_count` from the loop's own counter and `failed_rules` from the
    real `ValidationResult` objects -- never from the retry prompt text).
    Driven through the REAL `GenericAuditWriter` (not a stub): it is what
    turns the passed `ValidationResult` list into the `validation_issues`
    key `trace_to_csv_row` reads for `failed_rules`."""
    from broker.components.analytics.audit import AuditConfig, GenericAuditWriter, trace_to_csv_row

    eng = _silent_engine(max_retries=2)
    eng.audit_writer = GenericAuditWriter(
        AuditConfig(output_dir=str(tmp_path), experiment_name="silent-audit-row"))

    # Also captures every prompt sent through the REAL engine's llm_invoke
    # (not just the isolated _Host harness test (a) above uses), so this
    # test proves byte-identity end to end AND that the audit plane is
    # unaffected, in one real `process_step` call.
    captured_prompts = []

    def _llm_invoke(p):
        captured_prompts.append(p)
        return "raw"

    eng.process_step(agent_id="H01", step_id=1, run_id="r", seed=42,
                     llm_invoke=_llm_invoke, agent_type="household")

    assert len(captured_prompts) >= 3, "expected the initial attempt + 2 governance retries"
    assert all(p == "PROMPT" for p in captured_prompts), (
        "every call through the real engine (initial attempt AND both "
        "retries) must receive _Ctx.format_prompt's literal, unmutated "
        f"output; got {captured_prompts!r}"
    )

    trace = eng.audit_writer._trace_buffer["household"][-1]
    row = trace_to_csv_row(trace)

    assert row["retry_count"] == 2
    assert row["failed_rules"] != ""
    assert RULE_ID in row["failed_rules"]


# ---------------------------------------------------------------------------
# (e) invalid mode string still rejected (config getter, retry loop, CLI)
# ---------------------------------------------------------------------------

def test_config_getter_reads_silent():
    from broker.utils.agent_config import AgentTypeConfig

    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = {"global_config": {"governance": {"retry_feedback_mode": "silent"}}}
    assert cfg.get_governance_retry_feedback_mode() == "silent"


def test_config_getter_still_rejects_unknown_value_after_adding_silent():
    from broker.utils.agent_config import AgentTypeConfig

    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = {"global_config": {"governance": {"retry_feedback_mode": "quiet"}}}
    with pytest.raises(ValueError, match="quiet"):
        cfg.get_governance_retry_feedback_mode()


def test_retry_loop_still_rejects_unknown_value_after_adding_silent():
    """Adding `silent` must not widen the retry loop's own check into
    accepting an arbitrary string."""
    host = _Host(retry_feedback_mode="quiet")
    with pytest.raises(ValueError, match="quiet"):
        _run_retry_loop(host)


def test_engine_coerces_an_unrecognised_getter_value_to_full_not_silent():
    """Same MagicMock-safety idiom as the placebo file's own
    `test_w5a_engine_coerces_an_unrecognised_getter_value_to_full`: a getter
    returning something outside the known three-value set degrades to
    `"full"`, never silently to `"silent"`."""
    from test_retry_feedback_placebo import _build_engine, _engine_config

    config = _engine_config(get_governance_retry_feedback_mode="not-a-real-mode")
    eng = _build_engine(config)
    assert eng._retry_feedback_mode == "full"


def test_engine_accepts_silent_from_the_config_getter():
    from test_retry_feedback_placebo import _build_engine, _engine_config

    config = _engine_config(get_governance_retry_feedback_mode="silent")
    eng = _build_engine(config)
    assert eng._retry_feedback_mode == "silent"


# ---------------------------------------------------------------------------
# W2 warning (skill_broker_engine.py) now also fires for silent, not just
# placebo -- confirms the %s/%r/%r/%r reformat lines up with its arguments
# and that "silent" (not the literal word "placebo") shows up in the message.
# ---------------------------------------------------------------------------

def test_w2_warns_when_silent_and_advise_channel_not_off(caplog):
    import logging

    from test_retry_feedback_placebo import _build_engine, _engine_config

    config = _engine_config(
        get_governance_retry_feedback_mode="silent",
        get_governance_advise={"mode": "advise", "rule_ids": ["r1"]},
        get_governance_advise_mode="off",
    )
    with caplog.at_level(logging.WARNING, logger="broker"):
        eng = _build_engine(config)
    assert eng._retry_feedback_mode == "silent"
    assert eng._advise_mode == "advise"
    assert any(
        "retry_feedback_mode=silent" in rec.message
        and "_advise_mode" in rec.message
        and "'silent' corpus" in rec.message
        for rec in caplog.records
    )
    # Never the placebo wording, or the message would be silently wrong for
    # a reader grepping logs for which mode was actually running.
    assert not any("retry_feedback_mode=placebo" in rec.message for rec in caplog.records)


def test_w2_no_warning_for_silent_when_advise_channels_are_off(caplog):
    """Uses `caplog.at_level` (not a bare manually-attached handler) so the
    logger's effective level is pinned for the duration of the build --
    otherwise an ambient level above INFO/WARNING could make this test pass
    vacuously (nothing captured at all) without checking anything. The
    positive assertion on the unconditional startup line is exactly that
    belt-and-braces check: if it ever failed, the level pin failed, not the
    W2 logic."""
    import logging

    from test_retry_feedback_placebo import _build_engine, _engine_config

    config = _engine_config(
        get_governance_retry_feedback_mode="silent",
        get_governance_advise=None,
        get_governance_advise_mode="off",
    )
    with caplog.at_level(logging.INFO, logger="broker"):
        _build_engine(config)

    # Positive control: the engine ALWAYS logs an unconditional INFO startup
    # line ("[Governance] retry_feedback_mode=silent") regardless of the
    # advise channels. If this fails, the level pin above is broken and the
    # negative assertion below would be meaningless.
    assert any(
        rec.message == "[Governance] retry_feedback_mode=silent"
        for rec in caplog.records
    )
    # Only the W2 CONFLICT warning (which also names `_advise_mode`) must be
    # absent when both advisory channels are off.
    assert not any(
        "retry_feedback_mode=silent" in rec.message and "_advise_mode" in rec.message
        for rec in caplog.records
    )


def test_cli_still_rejects_unknown_value_after_adding_silent(tmp_path):
    """W3 parity: `run_parity_benchmark` validates before argparse's
    `choices=` guard could ever help a direct library caller."""
    import examples.single_agent.run_flood as run_flood_mod

    with pytest.raises(ValueError, match="quiet"):
        run_flood_mod.run_parity_benchmark(
            model="mock", years=1, agents_count=3, seed=42,
            custom_output=str(tmp_path), retry_feedback_mode="quiet",
        )


def test_cli_accepts_silent():
    """The argparse `choices=` tuple is the CLI surface for this flag (there
    is no `main()` function to introspect -- argparse setup lives in the
    `if __name__ == "__main__":` block), so pin it directly against the
    module source."""
    import inspect

    import examples.single_agent.run_flood as run_flood_mod

    src = inspect.getsource(run_flood_mod)
    assert 'choices=["full", "placebo", "silent"]' in src
