"""Red-team objection 3: the retry-feedback ablation (full vs placebo).

``global_config.governance.retry_feedback_mode`` (default ``full``) governs
ONLY the text of the BLOCKING governance retry loop
(``RetryMixin._governance_retry_loop``, ``broker/core/_retry_loop.py``). The
validator still decides WHEN a proposal is rejected — same rules, same
schedule, same ``on_retry_exhausted`` fallback.

DESIGN (review round 2, opus W1): ``placebo`` is the adapter's existing
WRAPPER-ONLY control — ``format_intervention_prompt(...,
include_reports=False)`` (``broker/utils/parsing/unified_adapter.py``
~1461-1467): header + closer + the original prompt, NO rules block at all.
That is the same "A''" mechanism ``governance.advise``'s own
``mode="wrapper"`` already uses for the advisory channel. It removes
rule-SPECIFIC content (identity, reason, suggestion) while KEEPING the
governance framing ("your previous response was flagged / triggered the
governance layer... please reconsider") — the contrast is "rule-specific
information" vs. "another attempt with the SAME framing", not vs. "another
attempt with no framing at all". A hand-written fixed sentence
(``RETRY_FEEDBACK_PLACEBO_TEXT``) is used ONLY as a fallback for a
third-party adapter that predates P0-1c and cannot render
``include_reports=False`` (every adapter shipped in this repo can).

NOT the same mechanism as ``governance.advise``'s own ``mode="placebo"``
(P0-1c, arm B', ``_advise_pass.py``): that one keeps the SAME report
count/shape and replaces each report's TEXT, for the separate, NON-BLOCKING
single advisory call issued for rules *demoted* from ERROR. This one renders
NO reports at all, for the actual BLOCKING retry loop. Same knob VALUE name
on purpose (opus W1 decision) — mechanically distinct; they gate different
code paths, different config keys, and never share state.

FALSIFICATION (recorded in PR description, not re-run automatically here):

* Round 1 — ``test_placebo_mode_...`` (the hand-written-sentence version)
  was run against the PRE-CHANGE ``broker/core/_retry_loop.py`` (git HEAD at
  branch creation, ``c3391a53`` on ``main``; this test file did not exist
  there, so the module was temporarily swapped back in, not stashed) and
  FAILED, because pre-change code has no ``_retry_feedback_mode`` concept at
  all. Restored immediately afterward.
* Round 2 — each new/changed test below was re-run against a temporarily
  reverted (commented-out) placebo branch in ``_retry_loop.py`` (the round-1
  hand-written-sentence version) and FAILED on the wrapper-text assertions
  (the round-1 code never called ``include_reports=False`` at all, so it
  never produced the adapter's real header/closer text); restored, and
  PASSES against the current module. Exact commands + counts in the PR
  description.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from broker.core._retry_loop import RetryMixin
from broker.interfaces.skill_types import InterventionReport, SkillProposal, ValidationResult
from broker.utils.parsing.unified_adapter import UnifiedAdapter

# The FALLBACK-ONLY sentence (see module docstring: used only when the
# adapter cannot render include_reports=False at all). Not imported from
# broker.core._retry_loop at module scope on purpose: a golden literal here
# means this file can still be COLLECTED (and every test that does not need
# the real export still runs) against a module that predates the export.
# The one test that needs the real export
# (`test_fallback_constant_matches_expected_text`) imports it locally.
EXPECTED_FALLBACK_PLACEBO_TEXT = (
    "Your previous decision was not accepted. Please reconsider and answer "
    "again in the required format."
)

# The real adapter's wrapper-only header/closer text, quoted verbatim from
# UnifiedAdapter.format_intervention_prompt (broker/utils/parsing/
# unified_adapter.py ~1441-1459) — pinned here so a change to that wording
# is caught by THIS file too, not only by the adapter's own golden-string
# tests.
LEGACY_HEADER = "Your previous response was flagged by the governance layer."
LEGACY_CLOSER = (
    "Please reconsider your decision. Ensure your new response "
    "addresses the violations above."
)
NEUTRAL_HEADER = "Your previous response triggered the governance layer."
NEUTRAL_CLOSER = "Please reconsider your decision in light of the information above."


class _NoopAuditor:
    def log_parse_error(self):
        pass


def _real_adapter() -> UnifiedAdapter:
    """A REAL ``UnifiedAdapter`` instance, not a hand-rolled stand-in.

    ``format_intervention_prompt`` (and ``format_retry_prompt``, its
    ``framing="legacy"`` delegate) reference no ``self.*`` state at all —
    confirmed empirically and by reading the method body — so
    ``UnifiedAdapter.__new__(UnifiedAdapter)`` (skipping ``__init__``
    entirely, the same idiom ``test_advise_disposition_p0_1c.py`` uses) is
    safe here. Every test that needs to see what the model ACTUALLY receives
    uses this, not a stand-in that could silently drift from production
    rendering. ``parse_output`` is never invoked in these tests: every
    ``llm_invoke`` in this file returns a ``SkillProposal`` directly, which
    ``_governance_retry_loop`` adopts without calling the adapter's parser.
    """
    return UnifiedAdapter.__new__(UnifiedAdapter)


class _LegacyAdapter:
    """Predates P0-1c: implements ONLY ``format_retry_prompt``, not
    ``format_intervention_prompt`` — exercises the FALLBACK branch in
    ``_governance_retry_loop`` (a third-party adapter that cannot render
    ``include_reports=False`` at all; ``render_intervention_prompt`` would
    raise ``ValueError`` for such an adapter rather than silently falling
    back to full content — see ``broker/core/_advise.py``).
    """

    def format_retry_prompt(self, prompt, errors, max_reports=None):
        lines = []
        for e in errors:
            if isinstance(e, InterventionReport):
                lines.append(e.to_prompt_string())
            else:
                lines.append(f"- {e}")
        return "Your previous response was flagged.\n\n" + "\n".join(lines) + f"\n\n{prompt}"

    def parse_output(self, raw_output, context):
        return raw_output if isinstance(raw_output, SkillProposal) else None


class _Host(RetryMixin):
    max_retries = 1
    max_reports = 3

    def __init__(self, retry_feedback_mode="full", adapter=None, framing="legacy"):
        self.auditor = _NoopAuditor()
        self.model_adapter = adapter if adapter is not None else _real_adapter()
        self._retry_feedback_mode = retry_feedback_mode
        self._intervention_framing = framing

    def _run_validators(self, proposal, context):
        return [ValidationResult(valid=True, validator_name="ok")]


RULE_ID = "low_coping_block_v9"
REASON_TEXT = "insufficient adaptive coping capacity for elevate_structure"
ORIGINAL_PROMPT = "ORIGINAL PROMPT TEXT — the agent's context block"


def _rejected_results():
    # Mirrors real validator shape (agent_validator.py:521):
    # `f"[Rule: {rule.id}] {rule.message}"` — the rule id is embedded in the
    # human-readable reason exactly as production error text does.
    return [
        ValidationResult(
            valid=False,
            validator_name="AgentValidator:thinking_error",
            errors=[f"[Rule: {RULE_ID}] Agent shows {REASON_TEXT}"],
            metadata={"rules_hit": [RULE_ID], "deterministic": False},
        )
    ]


def _retry_kwargs(*, skill_proposal="default", prompt=ORIGINAL_PROMPT):
    if skill_proposal == "default":
        skill_proposal = SkillProposal(
            skill_name="elevate_structure", agent_id="H01",
            agent_type="household", reasoning={},
        )
    return dict(
        all_valid=False,
        skill_proposal=skill_proposal,
        validation_results=_rejected_results(),
        all_validation_history=list(_rejected_results()),
        validation_context={},
        prompt=prompt,
        context={},
        agent_id="H01",
        agent_type="household",
        env_context={"current_year": 1},
        raw_output="raw",
        total_llm_stats={"llm_retries": 0, "llm_success": False},
    )


def _run_retry_loop(host, **kwargs):
    captured = {}

    def llm_invoke(retry_prompt):
        captured["prompt"] = retry_prompt
        return SkillProposal(
            skill_name="do_nothing", agent_id="H01", agent_type="household",
            reasoning={},
        )

    host._governance_retry_loop(llm_invoke=llm_invoke, **_retry_kwargs(**kwargs))
    return captured["prompt"]


# ---------------------------------------------------------------------------
# (a) Retry-prompt content: full vs placebo, real adapter
# ---------------------------------------------------------------------------

def test_full_mode_shows_rule_id_and_reason_in_retry_prompt():
    """Default behaviour, unchanged: the retry prompt names the rule."""
    prompt = _run_retry_loop(_Host(retry_feedback_mode="full"))
    assert RULE_ID in prompt
    assert REASON_TEXT in prompt
    assert ORIGINAL_PROMPT in prompt


def test_placebo_mode_renders_the_adapters_wrapper_only_control_legacy_framing():
    """The falsified assertion: neither the rule id, the reason, nor the
    blocked-skill name reaches the model — only the adapter's real
    wrapper-only header/closer (quoted verbatim from
    UnifiedAdapter.format_intervention_prompt) plus the original prompt."""
    prompt = _run_retry_loop(_Host(retry_feedback_mode="placebo", framing="legacy"))
    assert RULE_ID not in prompt
    assert REASON_TEXT not in prompt
    assert "elevate_structure" not in prompt  # the blocked_skill name
    assert LEGACY_HEADER in prompt
    assert LEGACY_CLOSER in prompt
    assert ORIGINAL_PROMPT in prompt
    # The round-1 hand-written fallback sentence must NOT appear: a
    # P0-1c-capable adapter (every adapter shipped in this repo) takes the
    # primary wrapper-only path, never the fallback.
    assert EXPECTED_FALLBACK_PLACEBO_TEXT not in prompt
    # Exact rendering, quoted, so a future wording change to either the
    # adapter or this test is forced to look at both:
    assert prompt == (
        f"{LEGACY_HEADER}\n\n{LEGACY_CLOSER}\n\n{ORIGINAL_PROMPT}"
    )


def test_placebo_mode_still_honours_intervention_framing_neutral():
    """S2: `_intervention_framing` STILL applies under placebo — the
    wrapper's header/closer text depends on it even with no rules block,
    because `include_reports=False` is evaluated inside the SAME
    `format_intervention_prompt` call that honours `framing`."""
    prompt = _run_retry_loop(_Host(retry_feedback_mode="placebo", framing="neutral"))
    assert RULE_ID not in prompt
    assert REASON_TEXT not in prompt
    assert NEUTRAL_HEADER in prompt
    assert NEUTRAL_CLOSER in prompt
    assert LEGACY_HEADER not in prompt  # confirms framing genuinely switched
    assert ORIGINAL_PROMPT in prompt


def test_placebo_mode_falls_back_to_fixed_sentence_for_a_legacy_adapter():
    """An adapter that predates P0-1c (only `format_retry_prompt`) cannot
    render `include_reports=False` — this is the ONE case where the
    hand-written RETRY_FEEDBACK_PLACEBO_TEXT constant is actually used."""
    prompt = _run_retry_loop(_Host(retry_feedback_mode="placebo", adapter=_LegacyAdapter()))
    assert RULE_ID not in prompt
    assert REASON_TEXT not in prompt
    assert EXPECTED_FALLBACK_PLACEBO_TEXT in prompt
    assert ORIGINAL_PROMPT in prompt


def test_fallback_constant_matches_expected_text():
    """Pins the real export against the golden literal above, so a future
    edit to the sentence cannot drift the two apart silently. Imported
    locally (not at module scope) so this is the ONLY test in the file that
    cannot even be collected against a module predating the export."""
    from broker.core._retry_loop import RETRY_FEEDBACK_PLACEBO_TEXT
    assert RETRY_FEEDBACK_PLACEBO_TEXT == EXPECTED_FALLBACK_PLACEBO_TEXT


def test_default_mode_is_full_when_attribute_absent():
    """A caller that never sets ``_retry_feedback_mode`` (every pre-existing
    test and production caller before this feature) gets full-content
    retries — the getattr default in ``_governance_retry_loop`` is
    ``"full"``."""
    class _BareHost(RetryMixin):
        max_retries = 1
        max_reports = 3

        def __init__(self):
            self.auditor = _NoopAuditor()
            self.model_adapter = _real_adapter()

        def _run_validators(self, proposal, context):
            return [ValidationResult(valid=True, validator_name="ok")]

    prompt = _run_retry_loop(_BareHost())
    assert RULE_ID in prompt


def test_unknown_retry_feedback_mode_value_raises_in_retry_loop():
    """W3: an unrecognised value on the resolved attribute is an ERROR, not
    a silent 'full'. A config/override bug here must never quietly send
    rule content to the model in a run an operator believed was placebo."""
    host = _Host(retry_feedback_mode="bogus")
    with pytest.raises(ValueError, match="bogus"):
        _run_retry_loop(host)


# ---------------------------------------------------------------------------
# (c) Cross-mode structural equality — the validator side is untouched
# ---------------------------------------------------------------------------

def test_placebo_mode_does_not_change_when_or_why_a_proposal_is_rejected():
    """Same rules, same schedule: the validator side of the loop (retry
    count, which proposal is adopted, all_valid) is byte-for-byte identical
    between full and placebo — only the outbound TEXT differs."""
    full_result = _Host(retry_feedback_mode="full")._governance_retry_loop(
        llm_invoke=lambda p: SkillProposal(
            skill_name="do_nothing", agent_id="H01", agent_type="household", reasoning={}),
        **_retry_kwargs())
    placebo_result = _Host(retry_feedback_mode="placebo")._governance_retry_loop(
        llm_invoke=lambda p: SkillProposal(
            skill_name="do_nothing", agent_id="H01", agent_type="household", reasoning={}),
        **_retry_kwargs())

    # (skill_proposal, raw_output, validation_results, all_validation_history,
    #  all_valid, retry_count)
    assert full_result[0].skill_name == placebo_result[0].skill_name
    assert full_result[4] == placebo_result[4]  # all_valid
    assert full_result[5] == placebo_result[5]  # retry_count


def test_cross_mode_all_validation_history_is_identical_per_attempt():
    """W5(c): compares the FULL `all_validation_history` list element-wise
    (`ValidationResult` is a `@dataclass`, so `==` compares field values,
    not identity) between full and placebo, attempt for attempt — not just
    the final outcome. Also confirms the loop genuinely retried in BOTH
    modes (not a no-op) and that the TEXT sent differs even though the
    STRUCTURE does not."""
    captured_prompts = {"full": [], "placebo": []}

    def make_invoke(key):
        def llm_invoke(retry_prompt):
            captured_prompts[key].append(retry_prompt)
            return SkillProposal(
                skill_name="do_nothing", agent_id="H01",
                agent_type="household", reasoning={})
        return llm_invoke

    full_result = _Host(retry_feedback_mode="full")._governance_retry_loop(
        llm_invoke=make_invoke("full"), **_retry_kwargs())
    placebo_result = _Host(retry_feedback_mode="placebo")._governance_retry_loop(
        llm_invoke=make_invoke("placebo"), **_retry_kwargs())

    full_history = full_result[3]
    placebo_history = placebo_result[3]
    assert len(full_history) == len(placebo_history) == 2  # seed + 1 retry attempt
    assert full_history == placebo_history

    assert len(captured_prompts["full"]) == len(captured_prompts["placebo"]) == 1
    assert captured_prompts["full"][0] != captured_prompts["placebo"][0]
    assert RULE_ID in captured_prompts["full"][0]
    assert RULE_ID not in captured_prompts["placebo"][0]


def test_placebo_mode_does_not_touch_audit_trail_validation_results():
    """The audit CSV's failed_rules / error_messages are derived from the
    ValidationResult objects the validators returned — never from the
    (possibly placebo'd) retry prompt text. Confirms the real rule id is
    still present in the returned validation_results even under placebo."""
    host = _Host(retry_feedback_mode="placebo")
    result = host._governance_retry_loop(
        llm_invoke=lambda p: SkillProposal(
            skill_name="do_nothing", agent_id="H01", agent_type="household", reasoning={}),
        **_retry_kwargs())
    _, _, _, all_validation_history, _, _ = result
    hit_ids = {
        rid
        for v in all_validation_history
        for rid in (v.metadata or {}).get("rules_hit", [])
    }
    assert RULE_ID in hit_ids


# ---------------------------------------------------------------------------
# (d) format_violation path (unparsable retry attempt) under placebo
# ---------------------------------------------------------------------------

def test_format_violation_path_under_placebo_has_no_parsing_language():
    """W5(d): when the retry attempt is UNPARSABLE (skill_proposal is
    None), `_governance_retry_loop` builds a synthetic `format_violation`
    InterventionReport naming the delimiter/JSON-structure problem. Under
    placebo this must be suppressed exactly like any other rule content —
    covered by the SAME wrapper-only render, not a special case."""
    prompt = _run_retry_loop(
        _Host(retry_feedback_mode="placebo"), skill_proposal=None)
    for forbidden in ("delimiter", "JSON structure", "required fields", "parsing"):
        assert forbidden not in prompt, f"{forbidden!r} leaked into the placebo retry prompt"
    assert LEGACY_HEADER in prompt
    assert ORIGINAL_PROMPT in prompt


def test_format_violation_path_under_full_mode_still_shows_parsing_guidance():
    """Contrast check: the SAME scenario under full mode DOES carry the
    parsing guidance — proves the placebo test above is discriminating,
    not vacuously true because nothing was ever rendered either way."""
    prompt = _run_retry_loop(
        _Host(retry_feedback_mode="full"), skill_proposal=None)
    assert "delimiter" in prompt
    assert "JSON structure" in prompt


# ---------------------------------------------------------------------------
# W5(a) — the engine reads the config getter into _retry_feedback_mode
# ---------------------------------------------------------------------------

class _EngineCtx:
    def build(self, agent_id, env_context=None, **kwargs):
        return {"agent_id": agent_id, "state": {}}

    def format_prompt(self, context):
        return "PROMPT"


def _engine_config(**overrides) -> MagicMock:
    """A MagicMock config exposing exactly the getters
    `SkillBrokerEngine.__init__` calls, all defaulted to inert values —
    the same idiom `test_advise_disposition_p0_1c.py` uses. Individual
    tests override what they need to check."""
    config = MagicMock()
    config.get_governance_retry_feedback_mode.return_value = "full"
    config.get_governance_advise.return_value = None
    config.get_governance_advise_mode.return_value = "off"
    config.get_governance_intervention_framing.return_value = "legacy"
    config.get_governance_on_retry_exhausted.return_value = "default"
    config.get_audit_advise_columns.return_value = False
    for key, value in overrides.items():
        getattr(config, key).return_value = value
    return config


def _build_engine(config) -> "SkillBrokerEngine":
    from broker.core.skill_broker_engine import SkillBrokerEngine
    from broker.components.governance.registry import SkillRegistry

    return SkillBrokerEngine(
        skill_registry=SkillRegistry(),
        model_adapter=MagicMock(),
        validators=[MagicMock()],
        simulation_engine=None,
        context_builder=_EngineCtx(),
        config=config,
    )


def test_w5a_engine_reads_the_getter_into_retry_feedback_mode():
    """The entry point this whole feature depends on: `__init__` must call
    `config.get_governance_retry_feedback_mode()` and store its resolved
    value on `self._retry_feedback_mode`. Falsified: fails if that wiring
    is removed (verified by temporarily commenting it out — see PR
    description)."""
    config = _engine_config(get_governance_retry_feedback_mode="placebo")
    eng = _build_engine(config)
    assert eng._retry_feedback_mode == "placebo"
    config.get_governance_retry_feedback_mode.assert_called_once()


def test_w5a_engine_coerces_an_unrecognised_getter_value_to_full():
    """Same MagicMock-safety idiom as `_advise_mode` / `_soft_advise_mode`
    / `_on_retry_exhausted`: a getter returning something outside the known
    set degrades to `"full"` at construction rather than raising — the
    config getter itself (`AgentTypeConfig.get_governance_retry_feedback_mode`)
    is what raises on a real bad YAML value; this is belt-and-braces for a
    non-`AgentTypeConfig` config object (tests, alternate embeddings)."""
    config = _engine_config(get_governance_retry_feedback_mode="not-a-real-mode")
    eng = _build_engine(config)
    assert eng._retry_feedback_mode == "full"


# ---------------------------------------------------------------------------
# W2 — warn when placebo AND an advisory channel is not off
# ---------------------------------------------------------------------------

def test_w2_warns_when_placebo_and_advise_channel_not_off(caplog):
    config = _engine_config(
        get_governance_retry_feedback_mode="placebo",
        get_governance_advise={"mode": "advise", "rule_ids": ["r1"]},
        get_governance_advise_mode="off",
    )
    with caplog.at_level(logging.WARNING, logger="broker"):
        eng = _build_engine(config)
    assert eng._retry_feedback_mode == "placebo"
    assert eng._advise_mode == "advise"
    assert any(
        "retry_feedback_mode=placebo" in rec.message and "_advise_mode" in rec.message
        for rec in caplog.records
    )


def test_w2_warns_when_placebo_and_soft_advise_channel_not_off(caplog):
    config = _engine_config(
        get_governance_retry_feedback_mode="placebo",
        get_governance_advise=None,
        get_governance_advise_mode="feedback",
    )
    with caplog.at_level(logging.WARNING, logger="broker"):
        eng = _build_engine(config)
    assert eng._soft_advise_mode == "feedback"
    assert any(
        "retry_feedback_mode=placebo" in rec.message and "_soft_advise_mode" in rec.message
        for rec in caplog.records
    )


def test_w2_no_warning_when_advise_channels_are_off():
    config = _engine_config(
        get_governance_retry_feedback_mode="placebo",
        get_governance_advise=None,
        get_governance_advise_mode="off",
    )
    logger = logging.getLogger("broker")
    records = []
    handler = logging.Handler()
    handler.emit = lambda record: records.append(record)
    logger.addHandler(handler)
    try:
        _build_engine(config)
    finally:
        logger.removeHandler(handler)
    assert not any(
        "retry_feedback_mode=placebo" in r.getMessage() and "_advise_mode" in r.getMessage()
        for r in records
    )


def test_w2_no_warning_when_full_even_if_advise_channel_is_on():
    """The warning is scoped to placebo specifically — full mode already
    carries rule content in its own prompt, so a co-active advisory channel
    is not the same failure mode."""
    config = _engine_config(
        get_governance_retry_feedback_mode="full",
        get_governance_advise={"mode": "advise", "rule_ids": ["r1"]},
        get_governance_advise_mode="off",
    )
    logger = logging.getLogger("broker")
    records = []
    handler = logging.Handler()
    handler.emit = lambda record: records.append(record)
    logger.addHandler(handler)
    try:
        _build_engine(config)
    finally:
        logger.removeHandler(handler)
    assert not any(
        "retry_feedback_mode=placebo" in r.getMessage()
        for r in records
    )


# ---------------------------------------------------------------------------
# (b) Reproducibility-manifest field test
# ---------------------------------------------------------------------------

def test_manifest_records_resolved_retry_feedback_mode(monkeypatch):
    """The manifest's `retry_feedback_mode` field reads the RESOLVED broker
    attribute (so a CLI override is reflected), next to `thinking_mode`."""
    from broker.core.experiment_runner import ExperimentRunner

    # No live Ollama dependency in a unit test.
    monkeypatch.setattr(
        "requests.post",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network disabled in test")),
    )

    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.config = SimpleNamespace(model="mock")
    runner.broker = SimpleNamespace(
        _retry_feedback_mode="placebo",
        model_adapter=SimpleNamespace(config_path=None),
    )

    metadata = runner._collect_reproducibility_metadata()
    assert metadata["retry_feedback_mode"] == "placebo"
    # Lives next to thinking_mode, as the task/PR asked.
    assert "thinking_mode" in metadata


def test_manifest_survives_a_runner_with_no_broker_attribute_at_all(monkeypatch):
    """Regression guard: a runner reaching this method before `self.broker`
    is even assigned (or a test double carrying only `.config`, as
    tests/test_llm_timeout_env_override.py's manifest test does) must not
    have the retry_feedback_mode line's AttributeError silently abort
    anything else — it now lives in its OWN try/except (S3, review round 2),
    so it cannot take thinking_mode / temperature / the timeout fields down
    with it even if it were ever to raise."""
    from broker.core.experiment_runner import ExperimentRunner

    monkeypatch.setattr(
        "requests.post",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network disabled in test")),
    )

    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.config = SimpleNamespace(model="mock")
    # Deliberately no `runner.broker` at all.

    metadata = runner._collect_reproducibility_metadata()
    assert metadata["retry_feedback_mode"] == "full"
    # The regression this guards against: these must still be populated.
    assert "thinking_mode" in metadata
    assert "temperature" in metadata


def test_manifest_defaults_retry_feedback_mode_to_full_when_broker_lacks_it(monkeypatch):
    """A broker built before this feature (or a test double) has no
    `_retry_feedback_mode` attribute at all; the manifest must not crash and
    must record the documented default, `"full"`."""
    from broker.core.experiment_runner import ExperimentRunner

    monkeypatch.setattr(
        "requests.post",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network disabled in test")),
    )

    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.config = SimpleNamespace(model="mock")
    runner.broker = SimpleNamespace(model_adapter=SimpleNamespace(config_path=None))

    metadata = runner._collect_reproducibility_metadata()
    assert metadata["retry_feedback_mode"] == "full"


# ---------------------------------------------------------------------------
# Config getter tests
# ---------------------------------------------------------------------------

def test_config_getter_defaults_to_full():
    from broker.utils.agent_config import AgentTypeConfig

    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = {}
    assert cfg.get_governance_retry_feedback_mode() == "full"


def test_config_getter_reads_placebo():
    from broker.utils.agent_config import AgentTypeConfig

    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = {"global_config": {"governance": {"retry_feedback_mode": "placebo"}}}
    assert cfg.get_governance_retry_feedback_mode() == "placebo"


def test_config_getter_rejects_unknown_value():
    from broker.utils.agent_config import AgentTypeConfig

    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = {"global_config": {"governance": {"retry_feedback_mode": "bogus"}}}
    with pytest.raises(ValueError):
        cfg.get_governance_retry_feedback_mode()


# ---------------------------------------------------------------------------
# W5(b) — the CLI / run_parity_benchmark override path, end to end
# ---------------------------------------------------------------------------

def test_w5b_run_parity_benchmark_cli_override_reaches_manifest_and_snapshot(tmp_path):
    """Calling `run_parity_benchmark` DIRECTLY (bypassing argparse and the
    `if __name__ == "__main__":` block entirely — exactly what a library
    caller, or this test, does) with `retry_feedback_mode="placebo"` must:

    1. apply the override to the live engine (proven indirectly: both
       artifacts below are written from the POST-override state);
    2. have it read back from the finished run's reproducibility manifest;
    3. have it read back from config_snapshot.yaml's injected metadata
       (silent-failure P1, review round 2) — the on-disk YAML's own
       `global_config.governance` block never had this key at all, so the
       snapshot would otherwise silently show the pre-override state.

    This call never runs the `if __name__ == "__main__":` block, so no
    module-global `args` exists at all in `examples.single_agent.run_flood`.
    Before the W3/W5 fix, TWO lines deep in `run_parity_benchmark` read the
    bare name `args` (`premium_rate = getattr(args, ...)` and the
    AutoTune `num_ctx_override=getattr(args, ...)` block) and raised
    `NameError` before ever reaching the retry_feedback_mode code far below
    them — `globals().get('args')` degrades to None instead, reproducing
    the exact CLI behaviour when `args` genuinely is a global.
    """
    import json

    import yaml

    import examples.single_agent.run_flood as run_flood_mod

    run_flood_mod.run_parity_benchmark(
        model="mock", years=1, agents_count=3, seed=42,
        custom_output=str(tmp_path), retry_feedback_mode="placebo",
    )

    manifest = json.loads(
        (tmp_path / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    assert manifest["retry_feedback_mode"] == "placebo"

    snapshot_path = tmp_path / "config_snapshot.yaml"
    assert snapshot_path.exists()
    snapshot = yaml.safe_load(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["metadata"]["retry_feedback_mode"] == "placebo"
    # Confirms this is genuinely an OVERRIDE, not a coincidence: the on-disk
    # governance block itself carries no such key (defaults full), so the
    # metadata value could only have come from the live engine attribute.
    assert "retry_feedback_mode" not in (
        snapshot.get("global_config", {}).get("governance", {}) or {})


def test_w5b_run_parity_benchmark_rejects_unknown_retry_feedback_mode(tmp_path):
    """W3: `run_parity_benchmark` is a public function a library caller can
    invoke with an arbitrary string, bypassing argparse's `choices=` guard
    entirely — validated here too, and BEFORE the run does any real work
    (the check sits right where the override is applied, after
    `builder.build()` but before `runner.run()`)."""
    import examples.single_agent.run_flood as run_flood_mod

    with pytest.raises(ValueError, match="bogus"):
        run_flood_mod.run_parity_benchmark(
            model="mock", years=1, agents_count=3, seed=42,
            custom_output=str(tmp_path), retry_feedback_mode="bogus",
        )


# ---------------------------------------------------------------------------
# Silent-failure P1 — replay prefers the manifest's retry_feedback_mode
# ---------------------------------------------------------------------------

def test_p1_replay_prefers_manifest_retry_feedback_mode_over_reloaded_config(tmp_path):
    """`build_replay_decider` must prefer the manifest's `retry_feedback_mode`
    over whatever the RELOADED config resolves to. The real scenario: a CLI
    override changes only the live engine attribute at run time, never the
    on-disk YAML — so a manifest saying "placebo" with a (correctly, for the
    on-disk YAML) reloaded "full" must still rebuild the engine as
    "placebo", or a replay of a placebo run would silently run full-content
    retries with nothing in the replay output saying so.
    """
    import json
    import sys
    import types

    from _pr5_run_fixture import FLOOD_CONFIG, write_run_dir

    run_dir = write_run_dir(tmp_path)
    manifest_path = run_dir / "reproducibility_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["retry_feedback_mode"] = "placebo"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    # Sanity: the reloaded config has no retry_feedback_mode key at all (the
    # real examples/single_agent/agent_types.yaml), so it resolves to the
    # documented default "full" — confirming this is a genuine mismatch,
    # not a coincidental agreement.
    from broker.utils.agent_config import AgentTypeConfig
    reloaded = AgentTypeConfig.load(str(FLOOD_CONFIG))
    assert reloaded.get_governance_retry_feedback_mode() == "full"

    name = "_p1_fake_validators_retry_feedback"
    module = types.ModuleType(name)
    module.build_custom_validators = lambda config: []
    sys.modules[name] = module
    try:
        from broker.experiments.replay import build_replay_decider
        decider = build_replay_decider(
            run_dir, model="mock", with_governance=True, validators_module=name,
        )
        assert decider.engine._retry_feedback_mode == "placebo"
    finally:
        sys.modules.pop(name, None)


def test_p1_replay_uses_reloaded_config_when_manifest_has_no_value(tmp_path):
    """Contrast check: a run directory whose manifest predates this feature
    (no `retry_feedback_mode` key at all) must fall back to the reloaded
    config's resolution — proves the preference test above is discriminating
    the two sources, not just always forcing "placebo"."""
    import sys
    import types

    from _pr5_run_fixture import write_run_dir

    run_dir = write_run_dir(tmp_path)
    # manifest written by write_run_dir carries no retry_feedback_mode key.

    name = "_p1_fake_validators_retry_feedback_fallback"
    module = types.ModuleType(name)
    module.build_custom_validators = lambda config: []
    sys.modules[name] = module
    try:
        from broker.experiments.replay import build_replay_decider
        decider = build_replay_decider(
            run_dir, model="mock", with_governance=True, validators_module=name,
        )
        assert decider.engine._retry_feedback_mode == "full"
    finally:
        sys.modules.pop(name, None)
