"""``global_config.governance.intervention_framing: plain`` (2026-11-26).

The retry text an agent sees must carry no log label: "governance layer",
"flagged", the severity tag "[ERROR]", "BLOCKED", "violations", the section
titles, the Suggestion line, the "[!NOTE]" truncation tag, or the
parse-failure summary written for model builders ("LLM output ... delimiter").
Those stay in the logs and the audit, which read the validation results,
never the retry text.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from broker.core._retry_loop import RetryMixin
from broker.interfaces.skill_types import InterventionReport, SkillProposal, ValidationResult
from broker.utils.agent_config import AgentTypeConfig
from broker.utils.parsing.unified_adapter import (
    PLAIN_FORMAT_LINE,
    PLAIN_RETRY_CLOSER,
    PLAIN_RETRY_HEADER,
    PLAIN_WRAPPER_CLOSER,
    UnifiedAdapter,
)

REPO = Path(__file__).resolve().parents[2]

# Words that belong to the logs, never to the text the agent sees.
LOG_LABELS = (
    "governance", "Governance", "flagged", "[ERROR]", "ERROR", "WARNING",
    "BLOCKED", "blocked", "violation", "Suggestion", "Issues Detected",
    "Rules Triggered", "[!NOTE]", "LLM output", "delimiter",
)

REASON = (
    "Under the rule on severe-threat response, doing nothing is not available "
    "in this decision: at the start of this decision you judged the flood "
    "threat to be high and your coping appraisal was not very low or low."
)
ORIGINAL_PROMPT = "ORIGINAL PROMPT TEXT"


def _adapter() -> UnifiedAdapter:
    # format_intervention_prompt reads no instance state (same idiom as
    # test_retry_feedback_placebo.py), so __init__ is skipped.
    return UnifiedAdapter.__new__(UnifiedAdapter)


def _report(summary=REASON, skill="do nothing", suggestion="Under this rule, doing nothing is not available.",
            rule_id="extreme_threat_block", severity="ERROR"):
    return InterventionReport(
        rule_id=rule_id, blocked_skill=skill, violation_summary=summary,
        suggested_correction=suggestion, severity=severity,
    )


def _assert_no_log_labels(text: str):
    found = [w for w in LOG_LABELS if w in text]
    assert not found, f"log labels reached the agent: {found}\n---\n{text}"


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

def test_plain_rule_report_exact_text():
    text, shown = _adapter().format_intervention_prompt(
        ORIGINAL_PROMPT, [_report()], framing="plain")
    assert shown == 1
    assert text == (
        f"{PLAIN_RETRY_HEADER}\n\n"
        f"- You chose 'do nothing'. {REASON}\n\n"
        f"{PLAIN_RETRY_CLOSER}\n\n"
        f"{ORIGINAL_PROMPT}"
    )
    _assert_no_log_labels(text.replace(ORIGINAL_PROMPT, ""))


def test_plain_hides_suggestion_and_severity_even_when_present():
    text, _ = _adapter().format_intervention_prompt(
        ORIGINAL_PROMPT,
        [_report(suggestion="The shortage-sharing rule blocks increases this year.",
                 severity="WARNING")],
        framing="plain")
    assert "shortage-sharing rule blocks" not in text
    _assert_no_log_labels(text)


def test_plain_format_violation_is_one_plain_line():
    """The retry loop's synthetic report for an unreadable answer."""
    fmt = InterventionReport(
        rule_id="format_violation", blocked_skill="parsing",
        violation_summary="LLM output failed to match required delimiter or JSON structure.",
        suggested_correction="Ensure your response follows the specified format including all required fields within the delimiters.",
        severity="ERROR",
    )
    text, shown = _adapter().format_intervention_prompt(
        ORIGINAL_PROMPT, [fmt], framing="plain")
    assert shown == 1
    assert PLAIN_FORMAT_LINE in text
    assert "parsing" not in text
    _assert_no_log_labels(text)


def test_plain_report_without_a_skill_name_shows_the_reason_alone():
    text, _ = _adapter().format_intervention_prompt(
        ORIGINAL_PROMPT, [_report(skill="unknown")], framing="plain")
    assert f"\n- {REASON}\n" in text
    assert "You chose" not in text


def test_plain_string_reports_get_the_same_plain_text():
    text, _ = _adapter().format_intervention_prompt(
        ORIGINAL_PROMPT, ["Response missing required fields: threat_appraisal",
                          "[Rule: some_rule] Your house is already elevated."],
        framing="plain")
    assert "\n- Your answer is missing these required fields: threat_appraisal.\n" in text
    assert "\n- Your house is already elevated.\n" in text
    _assert_no_log_labels(text)
    assert "[Rule:" not in text


def test_plain_truncation_note_has_no_tag():
    reports = [_report(summary=f"Reason {i}.") for i in range(5)]
    text, shown = _adapter().format_intervention_prompt(
        ORIGINAL_PROMPT, reports, framing="plain", max_reports=2)
    assert shown == 2
    assert "Reason 2." not in text
    assert "(Only the first 2 reasons are shown.)" in text
    _assert_no_log_labels(text)


def test_plain_feasible_line_comes_after_reports_and_before_closer():
    feasible = "Actions that pass every rule in this decision: 2 (decrease demand)."
    text, _ = _adapter().format_intervention_prompt(
        ORIGINAL_PROMPT, [_report()], framing="plain", feasible_line=feasible)
    assert text.index(REASON) < text.index(feasible) < text.index(PLAIN_RETRY_CLOSER)


def test_plain_wrapper_only_shows_header_and_closer():
    """retry_feedback_mode: placebo renders include_reports=False."""
    text, shown = _adapter().format_intervention_prompt(
        ORIGINAL_PROMPT, [_report()], framing="plain", include_reports=False)
    assert shown == 0
    assert text == f"{PLAIN_RETRY_HEADER}\n\n{PLAIN_WRAPPER_CLOSER}\n\n{ORIGINAL_PROMPT}"


def test_plain_honours_an_explicit_closer():
    """placebo_closer (irrigation sets one) is passed as ``closer``."""
    text, _ = _adapter().format_intervention_prompt(
        ORIGINAL_PROMPT, [_report()], framing="plain", include_reports=False,
        closer="Please reconsider your decision.")
    assert text == f"{PLAIN_RETRY_HEADER}\n\nPlease reconsider your decision.\n\n{ORIGINAL_PROMPT}"


def test_unknown_framing_still_raises():
    with pytest.raises(ValueError, match="plain"):
        _adapter().format_intervention_prompt(ORIGINAL_PROMPT, [_report()], framing="bogus")


# ---------------------------------------------------------------------------
# Retry loop end to end (real adapter, real RetryMixin)
# ---------------------------------------------------------------------------

class _NoopAuditor:
    def log_parse_error(self):
        pass


class _Host(RetryMixin):
    max_retries = 1
    max_reports = 3

    def __init__(self, plain_action_names=True):
        self.auditor = _NoopAuditor()
        self.model_adapter = _adapter()
        self._retry_feedback_mode = "full"
        self._plain_action_names = plain_action_names

    def _run_validators(self, proposal, context):
        return [ValidationResult(valid=True, validator_name="ok")]


def _rejected():
    return [ValidationResult(
        valid=False, validator_name="AgentValidator:thinking_error",
        errors=[REASON],
        metadata={"rules_hit": ["extreme_threat_block"],
                  "suggestion": "Under this rule, doing nothing is not available."},
    )]


def _run(host, skill_proposal):
    captured = {}

    def llm_invoke(retry_prompt):
        captured["prompt"] = retry_prompt
        return SkillProposal(skill_name="buy_insurance", agent_id="H01",
                             agent_type="household", reasoning={})

    host._governance_retry_loop(
        llm_invoke=llm_invoke, all_valid=False, skill_proposal=skill_proposal,
        validation_results=_rejected(), all_validation_history=list(_rejected()),
        validation_context={}, prompt=ORIGINAL_PROMPT, context={},
        agent_id="H01", agent_type="household", env_context={"current_year": 3},
        raw_output="raw", total_llm_stats={"llm_retries": 0, "llm_success": False},
    )
    return captured["prompt"]


def test_retry_loop_plain_rule_block():
    proposal = SkillProposal(skill_name="do_nothing", agent_id="H01",
                             agent_type="household", reasoning={})
    prompt = _run(_Host(), proposal)
    assert prompt.startswith(PLAIN_RETRY_HEADER)
    assert f"- You chose 'do nothing'. {REASON}" in prompt
    _assert_no_log_labels(prompt)


def test_retry_loop_plain_unreadable_answer():
    prompt = _run(_Host(), None)
    assert PLAIN_FORMAT_LINE in prompt
    _assert_no_log_labels(prompt)




# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("retired", ["legacy", "neutral", "blocked", None])
def test_retry_setting_defaults_to_plain_and_rejects_retired_values(retired):
    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = {}
    assert cfg.get_governance_intervention_framing() == "plain"
    cfg._config = {"global_config": {"governance": {"intervention_framing": retired}}}
    with pytest.raises(ValueError, match=r"retired on 2026-11-27.*tag v0\.7\.0"):
        cfg.get_governance_intervention_framing()


@pytest.mark.parametrize("written", ["Plain", " plain ", "PLAIN"])
def test_retry_setting_ignores_case_and_spaces(written):
    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = {"global_config": {"governance": {"intervention_framing": written}}}
    assert cfg.get_governance_intervention_framing() == "plain"


@pytest.mark.parametrize("written", ["Executed", " executed "])
def test_memory_style_ignores_case_and_spaces(written):
    from broker.config.decision_wording import memory_line_style

    assert memory_line_style({"rejection_line_style": written}) == "executed"


def test_unknown_value_is_named_as_unsupported_not_only_retired():
    from broker.config.decision_wording import memory_line_style

    with pytest.raises(ValueError, match=r"'chatty' is not supported: the only value is 'executed'"):
        memory_line_style({"rejection_line_style": "chatty"})


NEW_RUN_CONFIGS = (
    "examples/single_agent/agent_types.yaml",
    "examples/single_agent/config_variants/nonudge/agent_types.yaml",
    "examples/irrigation_abm/config_variants/simple_executed/agent_types.yaml",
    "examples/irrigation_abm/config_variants/simple_nolimit_executed/agent_types.yaml",
)


@pytest.mark.parametrize("rel", NEW_RUN_CONFIGS)
def test_new_run_configs_use_plain_framing(rel):
    AgentTypeConfig.clear_cache()
    cfg = AgentTypeConfig.load(str(REPO / rel))
    assert cfg.get_governance_intervention_framing() == "plain"


@pytest.mark.parametrize("rel", NEW_RUN_CONFIGS)
def test_new_run_config_rule_messages_carry_no_log_label(rel):
    """A rule's message is the reason the agent reads on retry. Every
    ``message`` in the config (any YAML style, any profile) is rendered
    through the plain renderer and must come out with no log label."""
    import yaml

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "message" and isinstance(v, str):
                    yield v
                else:
                    yield from walk(v)
        elif isinstance(node, list):
            for v in node:
                yield from walk(v)

    messages = sorted(set(walk(yaml.safe_load((REPO / rel).read_text(encoding="utf-8")))))
    assert messages, rel
    # WARNING-level messages never reach the agent (they stay valid); this
    # one is the flood low_coping_block WARNING, kept out on purpose.
    shown = [m for m in messages if not m.startswith("Low coping appraisal: agent perceives")]
    reports = [_report(summary=m, skill="act") for m in shown]
    text, n = _adapter().format_intervention_prompt(
        ORIGINAL_PROMPT, reports, framing="plain", max_reports=len(reports))
    assert n == len(shown)
    _assert_no_log_labels(text)
    assert "[Rule:" not in text


# One sample of every message the framework itself writes into a validation
# error (broker/validators/agent/agent_validator.py, broker/components/
# governance/registry.py). Each must reach the agent as plain words only.
FRAMEWORK_MESSAGES = (
    "[Rule: construct_missing] Construct 'TP_LABEL' has an invalid label, so rules "
    "conditioned on it did not fire. No middle value was assumed.",
    "[Rule: construct_missing] Construct 'TP_LABEL' was not reported, so rules "
    "conditioned on it did not fire. No middle value was assumed.",
    "Response missing required fields: threat_appraisal, coping_appraisal",
    "Missing 'decision' in response",
    "Invalid decision 'fly_away' for household",
    "Skill 'fly_away' not found in registry",
    "Skill 'fly_away' not found",
    "Agent type 'household' not eligible for skill 'elevate_house'",
    "Precondition failed: 'not elevated' (field is True)",
    "Required field 'magnitude_pct' missing for skill 'increase_demand'",
    "Field 'magnitude_pct': expected number, got str",
    "Field 'magnitude_pct': 120 > maximum 100",
    "Field 'tier': 'x' not in allowed values ['a', 'b']",
    "magnitude_pct 0.50 below min 1.00",
    "demand change 45.00% exceeds max 20%",
)
INTERNAL_TOKENS = ("TP_LABEL", "_LABEL", "construct", "registry", "Precondition", "Field '",
                   "expected number", "household", "magnitude_pct", "fly_away", "not elevated",
                   "skill", "maximum 100", "below min", "exceeds max")


@pytest.mark.parametrize("message", FRAMEWORK_MESSAGES)
def test_framework_messages_reach_the_agent_as_plain_words(message):
    for err in (_report(summary=message, skill="elevate house"), message):
        text, _ = _adapter().format_intervention_prompt(ORIGINAL_PROMPT, [err], framing="plain")
        retry_part = text.split(PLAIN_RETRY_CLOSER)[0]
        _assert_no_log_labels(retry_part)
        found = [t for t in INTERNAL_TOKENS if t in retry_part]
        assert not found, (found, retry_part)


def test_invalid_label_from_the_real_validator_reaches_the_agent_as_plain_words(monkeypatch):
    """Review finding (2026-11-26): an answer with a rating outside the
    allowed codes makes AgentValidator write a hard-coded
    "[Rule: construct_missing] ..." ERROR, which bypasses rule_id_prefix.
    Driven through the real flood config, report builder and renderer."""
    from broker.core._advise import build_intervention_reports
    from broker.validators import AgentValidator

    AgentTypeConfig.clear_cache()
    monkeypatch.setenv("GOVERNANCE_PROFILE", "strict")
    path = str(REPO / "examples" / "single_agent" / "agent_types.yaml")
    results = AgentValidator(config_path=path).validate_thinking(
        "household", "A1", "relocate", {}, {"TP_LABEL": "Unclear", "CP_LABEL": "M"})
    bad = [r for r in results if not r.valid]
    assert any("[Rule: construct_missing]" in e for r in bad for e in r.errors), results
    proposal = SkillProposal(skill_name="relocate", agent_id="A1",
                             agent_type="household", reasoning={})
    reports = build_intervention_reports(bad, proposal, source="errors")
    text, _ = _adapter().format_intervention_prompt(ORIGINAL_PROMPT, reports, framing="plain")
    assert ("- One of the ratings in your answer is not one of the allowed codes "
            "in the response format.") in text
    retry_part = text.split(PLAIN_RETRY_CLOSER)[0]
    _assert_no_log_labels(retry_part)
    assert "[Rule:" not in retry_part and "TP_LABEL" not in retry_part


@pytest.mark.parametrize("harness", ("harness_flood.py", "harness_multi_agent.py"))
def test_frozen_guard_mock_recognises_the_plain_retry_header(harness):
    """The guard's prompt-hash mock tells a retry from a first attempt by the
    header; without the plain header it would answer every plain retry as a
    first attempt and the guard would stop exercising the retry path."""
    text = (REPO / "reproduction" / "frozen_guard" / harness).read_text(encoding="utf-8")
    assert f'"{PLAIN_RETRY_HEADER}"' in text
