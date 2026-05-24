"""Phase 6N-B regression tests.

Two bugs surfaced during the L3-1B vaccination_demo upgrade:

1. ``BaseAgentContextBuilder.format_prompt`` did not inject the YAML-
   defined ``{response_format}`` schema into prompts. Only
   ``TieredContextBuilder`` (used when an InteractionHub is wired) did.
   So single-agent / no-Hub domains fell through to ``SafeFormatter``'s
   ``[N/A]`` placeholder and the LLM had no JSON schema example. Caught
   when the vaccination_demo L3-1B smoke #1/#2 hit 0-1/10 APPROVED.

2. The construct-LABEL regex extractor at
   ``broker/utils/parsing/unified_adapter.py`` matched case-insensitively
   (``re.IGNORECASE``) but preserved the LLM's original case in
   ``match.group(1)``. A chatty model emitting ``"m"`` instead of
   ``"M"`` produced mixed-case labels in the audit CSV like
   ``['M', 'm']``, breaking downstream ``in ['H', 'VH']`` rule checks.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


# =============================================================================
# Bug 1 — BaseAgentContextBuilder injects response_format
# =============================================================================


def test_base_context_builder_injects_response_format(tmp_path: Path):
    """A single-agent demo that uses the default ``create_context_builder``
    (no Hub → plain ``BaseAgentContextBuilder``) must still get the
    ``<<<DECISION_START>>>`` JSON schema injected when its YAML defines
    ``response_format``. Without this fix the prompt's
    ``{response_format}`` placeholder rendered as ``[N/A]``.
    """
    # Minimal agent_types.yaml mirroring the vaccination_demo schema shape
    # (shared.response_format.fields with the canonical broker keys).
    yaml_text = """
global_config: {}
shared:
  response_format:
    delimiter_start: "<<<DECISION_START>>>"
    delimiter_end: "<<<DECISION_END>>>"
    fields:
      - { key: "reasoning", type: "text", required: true }
      - { key: "decision", type: "choice", required: true }
test_agent:
  agent_type: test_agent
  inherit_shared: true
"""
    yaml_path = tmp_path / "agent_types.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    from broker.components.context.tiered import BaseAgentContextBuilder

    builder = BaseAgentContextBuilder(
        agents={},
        environment={},
        prompt_templates={"test_agent": "{response_format}"},
        memory_engine=None,
        max_prompt_tokens=8192,
    )
    builder.yaml_path = str(yaml_path)

    context = {
        "agent_id": "Agent_001",
        "agent_name": "Agent_001",
        "agent_type": "test_agent",
        "state": {},
        "perception": {},
        "objectives": {},
        "memory": [],
        "available_skills": ["a", "b", "c"],
    }
    prompt = builder.format_prompt(context)

    assert "<<<DECISION_START>>>" in prompt, (
        f"BaseAgentContextBuilder did not inject response_format. "
        f"Prompt was: {prompt!r}"
    )
    assert "<<<DECISION_END>>>" in prompt
    assert "[N/A]" not in prompt, (
        f"Prompt still contains [N/A] placeholder — response_format "
        f"injection regressed. Prompt: {prompt!r}"
    )


# =============================================================================
# Bug 2 — LABEL regex captures uppercase
# =============================================================================


def test_label_capture_normalized_to_uppercase():
    """The construct LABEL extractor must normalize the captured value
    to uppercase. The regex itself matches case-insensitively, but
    without this fix ``match.group(1)`` returned whatever case the LLM
    emitted, breaking governance rules that compare against a canonical
    uppercase alphabet (VL/L/M/H/VH).
    """
    # Mirror the in-tree fix at unified_adapter.py:~463 inline so this
    # test exercises the exact normalization decision (capture + upper)
    # without depending on the full adapter pipeline.
    regex = r"(?i)\b(VL|L|M|H|VH)\b"
    for raw, expected in [
        ("m", "M"),
        ("M", "M"),
        ("vh", "VH"),
        ("VH", "VH"),
        ("Vl", "VL"),
        ("h", "H"),
    ]:
        match = re.search(regex, raw, re.IGNORECASE)
        assert match is not None, f"regex failed to match {raw!r}"
        captured = match.group(1).upper()
        assert captured == expected, (
            f"captured {captured!r} != expected {expected!r} for input {raw!r}"
        )


def test_label_capture_no_lowercase_leak_documented():
    """Sanity assertion: the fix site in
    ``broker/utils/parsing/unified_adapter.py`` calls ``.upper()`` on
    the matched LABEL capture. A grep-based contract test (no live LLM
    needed) — guards against a future refactor silently dropping the
    normalization that the L3-1B smoke #5 verified end-to-end with a
    real model.

    Phase 6N-B reviewer W3: comment lines are stripped before the
    substring assertion so a future maintainer who deletes the active
    ``.upper()`` call while leaving the explanatory comment in place
    will NOT silently pass this test.
    """
    src = (
        Path(__file__).resolve().parents[1]
        / "utils" / "parsing" / "unified_adapter.py"
    ).read_text(encoding="utf-8")
    non_comment_lines = [
        line for line in src.splitlines() if not line.strip().startswith("#")
    ]
    non_comment = "\n".join(non_comment_lines)
    assert "match.group(1).upper()" in non_comment, (
        "broker/utils/parsing/unified_adapter.py no longer uppercases the "
        "LABEL capture (Phase 6N-B regression). The case-normalization is "
        "load-bearing: governance rules compare labels against ['H', 'VH'] "
        "etc. and a lowercase 'h' would silently miss."
    )
