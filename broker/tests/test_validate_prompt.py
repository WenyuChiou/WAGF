"""Tests for broker.tools.validate_prompt CLI (Phase 6C-v4 G3, 2026-05-10).

Verifies the static validator catches the 6 BLOCKERs surfaced by the
vaccination_demo PoC (see ``.ai/vaccination_poc_findings_2026-05-10.md``).
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from broker.tools.validate_prompt import (
    BROKER_FILLED_PLACEHOLDERS,
    extract_inline_json_keys,
    extract_placeholders,
    main,
    validate_agent_type,
)


# ---------------------------------------------------------------------------
# Pure-function tests
# ---------------------------------------------------------------------------

class TestExtractPlaceholders:
    def test_simple(self):
        assert extract_placeholders("{a} and {b}") == {"a", "b"}

    def test_ignores_double_brace(self):
        # Escaped literal braces — Python format() collapses {{ → { and }} → }.
        # The intermediate "key" is inside a {{...}} block and must not be
        # picked up as a placeholder.
        assert extract_placeholders("{{key}} and {{other}}") == set()

    def test_word_chars_only(self):
        # {1foo} → starts with digit, not a placeholder
        assert extract_placeholders("{1foo} {bar}") == {"bar"}


class TestExtractInlineJsonKeys:
    def test_top_level_keys(self):
        template = textwrap.dedent(
            """
            {{
              "a": "x",
              "b": "y"
            }}
            """
        )
        assert extract_inline_json_keys(template) == {"a", "b"}

    def test_skips_nested_keys(self):
        """The whole point of depth tracking — nested object keys ignored."""
        template = textwrap.dedent(
            """
            {{
              "decision": "1",
              "appraisal": {{"label": "H", "reason": "x"}}
            }}
            """
        )
        keys = extract_inline_json_keys(template)
        assert "decision" in keys
        assert "appraisal" in keys
        assert "label" not in keys
        assert "reason" not in keys

    def test_ignores_placeholder_substitutions(self):
        """Single-brace {name} placeholders don't pollute brace-depth."""
        template = textwrap.dedent(
            """
            {persona}
            {{
              "key": "value"
            }}
            """
        )
        assert extract_inline_json_keys(template) == {"key"}


# ---------------------------------------------------------------------------
# Validator tests via fixture YAML
# ---------------------------------------------------------------------------

@pytest.fixture
def good_config(tmp_path: Path) -> Path:
    """Write a minimal valid YAML + prompt to a temp dir."""
    yaml_path = tmp_path / "agent_types.yaml"
    prompt_path = tmp_path / "prompts" / "individual.txt"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text(textwrap.dedent("""
        {narrative_persona}
        Decide: {skills}
        {rating_scale}
        <<<DECISION_START>>>
        {{
          "reasoning": "...",
          "decision": "1"
        }}
        <<<DECISION_END>>>
    """).strip(), encoding="utf-8")
    yaml_path.write_text(textwrap.dedent("""
        shared:
          response_format:
            fields:
              - { key: "reasoning", type: "text", required: true }
        individual:
          agent_type: individual
          prompt_template_file: prompts/individual.txt
          actions:
            - id: get_vaccinated
              aliases: ["1", "get_vaccinated"]
            - id: refuse
              aliases: ["2", "refuse"]
          parsing:
            decision_keywords: ["decision"]
            default_skill: "refuse"
            strict_mode: true
    """).strip(), encoding="utf-8")
    return yaml_path


def test_validate_clean_config(good_config: Path):
    """A correct config yields no issues."""
    import yaml
    cfg = yaml.safe_load(good_config.read_text(encoding="utf-8"))
    issues = validate_agent_type(cfg, "individual", good_config)
    assert issues == []


def test_validate_missing_actions(good_config: Path, tmp_path: Path):
    """Removing the actions: block → ERROR."""
    import yaml
    cfg = yaml.safe_load(good_config.read_text(encoding="utf-8"))
    cfg["individual"].pop("actions")
    issues = validate_agent_type(cfg, "individual", good_config)
    errors = [i for i in issues if i.severity == "ERROR"]
    assert any("missing 'actions:' block" in i.message for i in errors), \
        f"expected actions ERROR, got: {[i.message for i in issues]}"


def test_validate_missing_parsing_constructs():
    """response_format declares construct but parsing.constructs missing → ERROR."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        yaml_path = tmp_path / "agent_types.yaml"
        prompt = tmp_path / "p.txt"
        prompt.write_text("{narrative_persona}", encoding="utf-8")

        yaml_path.write_text(textwrap.dedent("""
            shared:
              response_format:
                fields:
                  - { key: "appraisal_a", type: "appraisal", required: true,
                      construct: "APPRAISAL_A_LABEL" }
            individual:
              agent_type: individual
              prompt_template_file: p.txt
              actions:
                - id: dummy
                  aliases: ["1"]
              parsing:
                default_skill: "dummy"
                strict_mode: true
                # constructs: ← deliberately missing
        """).strip(), encoding="utf-8")

        import yaml
        cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        issues = validate_agent_type(cfg, "individual", yaml_path)
        errors = [i for i in issues if i.severity == "ERROR"]
        assert any("APPRAISAL_A_LABEL" in i.message for i in errors), \
            f"expected parsing.constructs ERROR, got: {[i.message for i in issues]}"


def test_validate_inline_json_key_mismatch(tmp_path: Path):
    """Inline JSON key not in response_format.fields → ERROR (Finding 4)."""
    yaml_path = tmp_path / "agent_types.yaml"
    prompt = tmp_path / "p.txt"
    # Prompt uses 'susceptibility_appraisal' but YAML declares
    # 'susceptibility_assessment' (typo mismatch — the exact bug)
    prompt.write_text(textwrap.dedent("""
        <<<DECISION_START>>>
        {{
          "susceptibility_appraisal": "H",
          "decision": "1"
        }}
        <<<DECISION_END>>>
    """).strip(), encoding="utf-8")
    yaml_path.write_text(textwrap.dedent("""
        shared:
          response_format:
            fields:
              - { key: "susceptibility_assessment", type: "appraisal",
                  required: true }
        individual:
          agent_type: individual
          prompt_template_file: p.txt
          actions:
            - id: dummy
              aliases: ["1"]
          parsing:
            decision_keywords: ["decision"]
            default_skill: "dummy"
            strict_mode: true
    """).strip(), encoding="utf-8")

    import yaml
    cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    issues = validate_agent_type(cfg, "individual", yaml_path)
    errors = [i for i in issues if i.severity == "ERROR"]
    assert any("susceptibility_appraisal" in i.message for i in errors), \
        f"expected inline-JSON-key ERROR, got: {[i.message for i in issues]}"


def test_validate_unknown_placeholder_warns(tmp_path: Path):
    """Placeholder not in broker-filled set and not in YAML → WARN."""
    yaml_path = tmp_path / "agent_types.yaml"
    prompt = tmp_path / "p.txt"
    prompt.write_text("{narrative_persona} {mystery_thing}", encoding="utf-8")
    yaml_path.write_text(textwrap.dedent("""
        shared: {}
        individual:
          agent_type: individual
          prompt_template_file: p.txt
          actions:
            - id: dummy
              aliases: ["1"]
          parsing:
            default_skill: "dummy"
            strict_mode: true
    """).strip(), encoding="utf-8")

    import yaml
    cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    issues = validate_agent_type(cfg, "individual", yaml_path)
    warns = [i for i in issues if i.severity == "WARN"]
    assert any("mystery_thing" in i.message for i in warns), \
        f"expected unknown-placeholder WARN, got: {[i.message for i in issues]}"


def test_validate_parsing_actions_location(tmp_path: Path):
    """flood multi-agent puts actions inside parsing — also valid."""
    yaml_path = tmp_path / "agent_types.yaml"
    prompt = tmp_path / "p.txt"
    prompt.write_text("{narrative_persona}", encoding="utf-8")
    yaml_path.write_text(textwrap.dedent("""
        shared: {}
        individual:
          agent_type: individual
          prompt_template_file: p.txt
          parsing:
            default_skill: "a"
            strict_mode: true
            actions:
              - id: a
                aliases: ["1"]
              - id: b
                aliases: ["2"]
    """).strip(), encoding="utf-8")

    import yaml
    cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    issues = validate_agent_type(cfg, "individual", yaml_path)
    errors = [i for i in issues if i.severity == "ERROR"]
    # parsing.actions location should be accepted — no missing-actions error
    assert not any("missing 'actions:' block" in i.message for i in errors), \
        f"parsing.actions should be valid, got: {[i.message for i in errors]}"


# ---------------------------------------------------------------------------
# main() exit codes
# ---------------------------------------------------------------------------

def test_main_returns_zero_on_clean(good_config: Path, capsys):
    rc = main([str(good_config)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "OK:" in captured.out


def test_main_returns_one_on_error(good_config: Path, capsys):
    """Break the YAML and verify exit 1."""
    text = good_config.read_text(encoding="utf-8")
    # Drop the actions: block
    broken = text.replace("actions:", "actions_removed:")
    good_config.write_text(broken, encoding="utf-8")
    rc = main([str(good_config)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "missing 'actions:' block" in captured.out


def test_known_broker_placeholders_documented():
    """Sanity: BROKER_FILLED_PLACEHOLDERS contains the placeholders the
    docs / vaccination_demo prompt actually rely on. If a maintainer
    removes one, tests fail loudly."""
    expected = {"narrative_persona", "memory", "skills", "rating_scale",
                "response_format", "options_text"}
    assert expected.issubset(BROKER_FILLED_PLACEHOLDERS)
