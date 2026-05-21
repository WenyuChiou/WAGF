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
    COVERAGE_THRESHOLD,
    check_skill_rule_coverage,
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


# ---------------------------------------------------------------------------
# Phase 6G flaw 5: skill->rule coverage (Requisite Variety)
# ---------------------------------------------------------------------------

class TestSkillRuleCoverage:
    """Closes harness-engineering flaw 5 — Requisite Variety check.

    Per the audit (2026-05-14): a DomainPack with N skills but rules
    constraining only M < N skills lets agents converge on the unconstrained
    subset while governance silently looks effective on the constrained
    subset.
    """

    @staticmethod
    def _cfg(**governance):
        """Build a minimal agent_type config with the given governance block."""
        return {
            "agent_x": {
                "actions": [
                    {"id": "skill_a"},
                    {"id": "skill_b"},
                    {"id": "skill_c"},
                    {"id": "skill_d"},
                ],
                "governance": governance,
            }
        }

    def test_full_coverage_no_warning(self):
        """All 4 skills constrained by at least one rule → 100% → no WARN."""
        cfg = self._cfg(strict={
            "thinking_rules": [
                {"id": "r1", "blocked_skills": ["skill_a", "skill_b"]},
                {"id": "r2", "blocked_skills": ["skill_c", "skill_d"]},
            ],
        })
        issues = check_skill_rule_coverage(cfg, "agent_x")
        assert issues == [], f"expected no issues, got: {[i.format() for i in issues]}"

    def test_seventy_five_percent_below_threshold_warns(self):
        """3 of 4 skills covered = 75% < 80% threshold → WARN.

        Documents the threshold contract: the check fires for any coverage
        strictly below COVERAGE_THRESHOLD (0.80).
        """
        cfg = self._cfg(strict={
            "thinking_rules": [
                {"id": "r1", "blocked_skills": ["skill_a", "skill_b", "skill_c"]},
            ],
        })
        assert COVERAGE_THRESHOLD == 0.80
        issues = check_skill_rule_coverage(cfg, "agent_x")
        warns = [i for i in issues if i.severity == "WARN"]
        assert any("coverage 75%" in i.message for i in warns), \
            f"expected 75% coverage warn, got: {[i.message for i in issues]}"

    def test_partial_coverage_warns_with_uncovered_list(self):
        """50% coverage warns and names the uncovered skills."""
        cfg = self._cfg(strict={
            "thinking_rules": [
                {"id": "r1", "blocked_skills": ["skill_a", "skill_b"]},
            ],
        })
        issues = check_skill_rule_coverage(cfg, "agent_x")
        warns = [i for i in issues if i.severity == "WARN"]
        assert len(warns) == 1
        msg = warns[0].message
        assert "coverage 50%" in msg
        assert "skill_c" in msg and "skill_d" in msg
        assert "Requisite Variety" in msg
        assert warns[0].location == "yaml: agent_x.governance.strict"

    def test_disabled_profile_skipped(self):
        """Profile with empty rules (ablation baseline) is intentionally exempt."""
        cfg = self._cfg(disabled={
            "thinking_rules": [],
            "identity_rules": [],
        })
        issues = check_skill_rule_coverage(cfg, "agent_x")
        assert issues == [], f"disabled profile should not warn: {[i.format() for i in issues]}"

    def test_ghost_skill_warns(self):
        """Rule references a skill id not in actions → ghost-skill WARN."""
        cfg = self._cfg(strict={
            "thinking_rules": [
                {"id": "r1", "blocked_skills": ["skill_a", "skill_b", "nonexistent"]},
                {"id": "r2", "blocked_skills": ["skill_c", "skill_d"]},
            ],
        })
        issues = check_skill_rule_coverage(cfg, "agent_x")
        # Coverage is 100% (all 4 real skills covered) so only ghost warn fires
        warns = [i for i in issues if i.severity == "WARN"]
        ghost_warns = [w for w in warns if "nonexistent" in w.message]
        assert len(ghost_warns) == 1
        assert "typo" in ghost_warns[0].message.lower() or "stale" in ghost_warns[0].message.lower()

    def test_identity_rules_also_count(self):
        """identity_rules + thinking_rules both contribute to coverage."""
        cfg = self._cfg(strict={
            "thinking_rules": [
                {"id": "r1", "blocked_skills": ["skill_a", "skill_b"]},
            ],
            "identity_rules": [
                {"id": "i1", "blocked_skills": ["skill_c", "skill_d"]},
            ],
        })
        issues = check_skill_rule_coverage(cfg, "agent_x")
        assert issues == [], "identity_rules should contribute to coverage"

    def test_multiple_profiles_evaluated_independently(self):
        """A two-profile config warns only on the under-covered profile."""
        cfg = self._cfg(
            strict={
                "thinking_rules": [
                    {"id": "r1", "blocked_skills": ["skill_a", "skill_b",
                                                     "skill_c", "skill_d"]},
                ],
            },
            relaxed={
                "thinking_rules": [
                    {"id": "r2", "blocked_skills": ["skill_a"]},
                ],
            },
        )
        issues = check_skill_rule_coverage(cfg, "agent_x")
        warns = [i for i in issues if i.severity == "WARN"]
        strict_warns = [w for w in warns if "strict" in w.location]
        relaxed_warns = [w for w in warns if "relaxed" in w.location]
        assert strict_warns == [], f"strict (100%) should not warn: {strict_warns}"
        assert len(relaxed_warns) == 1
        assert "coverage 25%" in relaxed_warns[0].message

    def test_no_governance_block_skipped(self):
        """An agent_type with no governance block returns no issues."""
        cfg = {"agent_x": {"actions": [{"id": "skill_a"}]}}
        assert check_skill_rule_coverage(cfg, "agent_x") == []

    def test_parsing_actions_location_supported(self):
        """Skills declared under parsing.actions are also checked."""
        cfg = {
            "agent_x": {
                "parsing": {
                    "actions": [
                        {"id": "skill_a"},
                        {"id": "skill_b"},
                    ],
                },
                "governance": {
                    "strict": {
                        "thinking_rules": [
                            {"id": "r1", "blocked_skills": ["skill_a"]},
                        ],
                    },
                },
            }
        }
        issues = check_skill_rule_coverage(cfg, "agent_x")
        warns = [i for i in issues if i.severity == "WARN"]
        assert any("coverage 50%" in w.message for w in warns)
