"""Unit tests for formatted/converted placeholder extraction in validate_prompt."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

from broker.tools.validate_prompt import extract_placeholders, main, validate_agent_type


class TestExtractFormatPlaceholders:
    def test_formatted_and_converted_placeholders(self) -> None:
        template = "Val: {typo:.2f} | Conv: {typo_conv!s} {repr_var!r} {ascii_var!a:>8}"
        assert extract_placeholders(template) == {"typo", "typo_conv", "repr_var", "ascii_var"}

    def test_attribute_and_subscript_root_names(self) -> None:
        template = "{agent.income:.1f} {items[0]} {nested[key].value!s}"
        assert extract_placeholders(template) == {"agent", "items", "nested"}

    def test_nested_format_spec_placeholders(self) -> None:
        template = "{value:{width}.{precision}f}"
        assert extract_placeholders(template) == {"value", "width", "precision"}

    def test_ignores_escaped_braces_and_positional_placeholders(self) -> None:
        template = "{{escaped:.2f}} {{escaped_conv!s}} {} {0} {1:.2f} {real_var:.2f}"
        assert extract_placeholders(template) == {"real_var"}

    def test_fallback_on_malformed_template(self) -> None:
        template = "Unclosed {broken and {typo:.2f} and {typo_s!s} and {{ignored}}"
        assert extract_placeholders(template) == {"typo", "typo_s"}


def _write_minimal_case(tmp_path: Path, extra_prompt: str) -> Path:
    yaml_path = tmp_path / "agent_types.yaml"
    prompt_path = tmp_path / "prompts" / "farmer.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(
        textwrap.dedent(
            f"""
            {{narrative_persona}}
            {{options_text}}
            {{rating_scale}}
            Known: {{declared_metric:.2f}}
            {extra_prompt}
            <<<DECISION_START>>>
            {{{{
              "threat": {{"label": "H", "reason": "x"}},
              "decision": 1
            }}}}
            <<<DECISION_END>>>
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    yaml_path.write_text(
        textwrap.dedent(
            """
            shared:
              template_vars:
                - declared_metric
              response_format:
                delimiter_start: "<<<DECISION_START>>>"
                delimiter_end: "<<<DECISION_END>>>"
                fields:
                  - {key: threat, type: appraisal, construct: THREAT_LABEL}
                  - {key: decision, type: choice}
            farmer:
              agent_type: farmer
              prompt_template_file: prompts/farmer.txt
              actions:
                - id: act_a
                  aliases: ["1"]
                - id: act_b
                  aliases: ["2"]
              parsing:
                constructs:
                  THREAT_LABEL: {keywords: [threat], levels: [L, M, H]}
                default_skill: act_a
                strict_mode: true
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return yaml_path


def test_validate_agent_type_catches_formatted_and_converted_typos(tmp_path: Path) -> None:
    yaml_path = _write_minimal_case(
        tmp_path, "Typos: {typo_fmt:.2f} {typo_conv!s} {{escaped_typo:.2f}}"
    )
    import yaml

    cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    issues = validate_agent_type(cfg, "farmer", yaml_path)
    msgs = [i.message for i in issues if "placeholders not in broker-filled" in i.message]
    assert len(msgs) == 1
    assert "'typo_fmt'" in msgs[0]
    assert "'typo_conv'" in msgs[0]
    assert "declared_metric" not in msgs[0]
    assert "escaped_typo" not in msgs[0]


def test_cli_catches_formatted_and_converted_typos(tmp_path: Path, capsys) -> None:
    yaml_path = _write_minimal_case(tmp_path, "Typos: {typo:.2f} {typo_s!s}")
    rc = main([str(yaml_path), "--agent-type", "farmer"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "'typo'" in out
    assert "'typo_s'" in out

    proc = subprocess.run(
        [sys.executable, "-m", "broker.tools.validate_prompt", str(yaml_path), "--agent-type", "farmer", "--strict"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "'typo'" in proc.stdout
    assert "'typo_s'" in proc.stdout
