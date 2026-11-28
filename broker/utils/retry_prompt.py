"""Agent-visible wording for retry and advisory feedback."""

import re
from typing import Any, List, Optional

from broker.utils.logging import logger


# Retry / advisory text under ``framing="plain"`` (see
# UnifiedAdapter.format_intervention_prompt). The agent sees only these
# sentences and the rules' own reasons; no log label ("governance layer",
# "flagged", "[ERROR]", "BLOCKED", "violations", "Suggestion") reaches it.
PLAIN_RETRY_HEADER = "Your previous answer cannot be used in this decision."
PLAIN_RETRY_CLOSER = "Please answer again, taking the information above into account."
PLAIN_FORMAT_LINE = (
    "- Your answer could not be read: it did not follow the required "
    "response format."
)
# Closer of the wrapper-only retry (retry_feedback_mode: placebo), which shows
# no reason, so it cannot point at "the information above".
PLAIN_WRAPPER_CLOSER = "Please answer again."


def format_plain_intervention_prompt(
    original_prompt: str,
    errors: List[Any],
    *,
    max_reports: Optional[int] = None,
    header: Optional[str] = None,
    closer: Optional[str] = None,
    include_reports: bool = True,
    feasible_line: Optional[str] = None,
) -> "tuple[str, int]":
    """Render the reviewed retry wording and count the reports shown."""
    from broker.interfaces.skill_types import InterventionReport

    header = header if header is not None else PLAIN_RETRY_HEADER

    if not include_reports:
        closer = closer if closer is not None else PLAIN_WRAPPER_CLOSER
        return f"{header}\n\n{closer}\n\n{original_prompt}", 0

    closer = closer if closer is not None else PLAIN_RETRY_CLOSER

    if max_reports and len(errors) > max_reports:
        logger.warning(f" [Adapter] Truncating retry reports from {len(errors)} to {max_reports} to save context.")
        errors = errors[:max_reports]
        truncated = True
    else:
        truncated = False

    lines = []
    for e in errors:
        if isinstance(e, InterventionReport):
            lines.append(plain_report_line(e))
        else:
            lines.append(f"- {_plain_text(str(e))[0]}")

    if truncated:
        lines.append(f"\n(Only the first {max_reports} reasons are shown.)")

    if feasible_line:
        lines.append(f"\n{feasible_line}")

    body = "\n".join(lines)
    return f"{header}\n\n{body}\n\n{closer}\n\n{original_prompt}", len(errors)


# Messages the framework itself writes (not a rule author). They name
# internal ids, field names or types. Each is shown
# as the plain sentence next to it; the original stays in the audit. The bool
# says whether the line still names the agent's own choice (the action itself
# is unavailable) or not (the form of the answer is the problem).
_PLAIN_FRAMEWORK_MESSAGES = (
    (re.compile(r"^\[Rule: construct_missing\] Construct '.*' has an invalid label"),
     "One of the ratings in your answer is not one of the allowed codes in the "
     "response format.", False),
    (re.compile(r"^\[Rule: construct_missing\] Construct '.*' was not reported"),
     "Your answer left out a rating that the response format asks for.", False),
    (re.compile(r"^Response missing required fields: (?P<fields>.+?)\.?$"),
     "Your answer is missing these required fields: {fields}.", False),
    (re.compile(r"^Missing '(?P<field>[^']+)' in response$"),
     "Your answer is missing the field '{field}'.", False),
    (re.compile(r"^Invalid decision '.*' for "),
     "Your choice is not one of the listed options.", False),
    (re.compile(r"^Skill '.*' not found( in registry)?$"),
     "Your choice is not one of the listed options.", False),
    (re.compile(r"^Agent type '.*' not eligible for skill '.*'$"),
     "This action is not available to you.", True),
    (re.compile(r"^Precondition failed: "),
     "This action is not available to you in your current situation.", True),
    (re.compile(r"^Required field '.*' missing for skill '.*'$"),
     "Your answer is missing a value that this action needs.", False),
    (re.compile(r"^Field '.*': expected (number|string|integer), got "),
     "A value in your answer is not in the form this action needs.", False),
    (re.compile(r"^Field '.*': .* [<>] (minimum|maximum) "),
     "A value in your answer is outside the allowed range.", False),
    (re.compile(r"^Field '.*': '.*' not in allowed values "),
     "A value in your answer is not one of the allowed values.", False),
    (re.compile(r"^\S+ -?[\d.]+ (below min|above max) -?[\d.]+$"),
     "The amount you asked for is outside the allowed range.", False),
    (re.compile(r"^\S+ change -?[\d.]+% exceeds max -?[\d.]+%$"),
     "The change you asked for is larger than allowed.", False),
)
_RULE_TAG = re.compile(r"^\[Rule: [^\]]*\]\s*")


def _plain_text(summary) -> "tuple[str, bool]":
    """``(text, names_choice)`` for one reason.

    A framework-written message becomes its plain sentence; any other text
    (a rule author's own message) is kept word for word, less a leading
    ``[Rule: <id>]`` tag if one is there.
    """
    summary = str(summary or "").strip()
    for pattern, plain, names_choice in _PLAIN_FRAMEWORK_MESSAGES:
        m = pattern.match(summary)
        if m:
            return plain.format(**m.groupdict()), names_choice
    return _RULE_TAG.sub("", summary), True


def plain_report_line(report) -> str:
    """One report as the agent sees it.

    An unreadable answer (the retry loop's ``format_violation`` report) gets
    :data:`PLAIN_FORMAT_LINE`. A framework-written message becomes a plain
    sentence (:data:`_PLAIN_FRAMEWORK_MESSAGES`); a rule's own message is kept
    word for word. When the action itself is what is unavailable, the line
    starts by naming the agent's choice. No severity tag, verb or Suggestion.
    """
    if report.rule_id == "format_violation":
        return PLAIN_FORMAT_LINE
    text, names_choice = _plain_text(report.violation_summary)
    skill = str(report.blocked_skill or "").strip()
    if names_choice and skill and skill not in ("unknown", "parsing"):
        return f"- You chose '{skill}'. {text}"
    return f"- {text}"
