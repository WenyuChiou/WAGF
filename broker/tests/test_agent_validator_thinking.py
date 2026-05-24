"""Phase 6N-E regression test — `AgentValidator.validate_thinking` fires
rules end-to-end on real YAML conditions.

Before this fix, vaccination_demo's 5 thinking_rules were silently
dead config: their conditions used the verbose
`RuleCondition`-flavoured shape `{ type: construct, field: X,
operator: "in", values: [...] }`, but
`AgentValidator._run_rule_set` at `agent_validator.py:418` read
`cond.get("construct")` ONLY — not `cond.get("field")`. So
`construct_name = None`, `get_label(None) → ""`,
`label_matches("", ["H","VH"]) → False`, rule never fired.

Origin: L3-1C (commit `64899b8`) copied the dict shape from
`broker/governance/rule_types.py::RuleCondition` instead of from
the working irrigation YAML. Phase 6N-C fixed `rules:` →
`thinking_rules:` at the top level but missed the nested condition
dict structure.

Phase 6N-E:
1. Defensive evaluator: `cond.get("construct") or cond.get("field")`.
2. Canonical YAML rewrite of vaccination_demo's 5 thinking_rules.

These tests pin both: (1) canonical shape works (would fire even on
pre-6N-E-1 code if the YAML used canonical); (2) legacy `field:`
shape is now tolerated (FAILS on pre-6N-E-1 code, PASSES post-fix).
"""
from __future__ import annotations

from pathlib import Path

import pytest

import examples.vaccination_demo  # noqa: F401 — register HBM framework
from broker.validators.agent import AgentValidator


VACCINATION_YAML = (
    Path(__file__).resolve().parents[2]
    / "examples" / "vaccination_demo" / "config" / "agent_types.yaml"
)


# ---------------------------------------------------------------------
# Smoke-#8 row 2 reasoning — BARRIERS=H + EFFICACY=H + delay
# Expected fire: high_barriers_high_self_efficacy_no_action_required (WARNING)
# ---------------------------------------------------------------------

_ROW_2_REASONING = {
    "SUSCEPTIBILITY_LABEL": "M",
    "SEVERITY_LABEL": "H",
    "BENEFITS_LABEL": "L",
    "BARRIERS_LABEL": "H",
    "SELF_EFFICACY_LABEL": "H",
    "CUES_TO_ACTION_LABEL": "L",
}


def test_canonical_construct_key_fires():
    """vaccination_demo's `{ construct: X, values: [...] }` shape
    fires under live AgentValidator end-to-end.

    Drives the row-2 case from smoke #8 (Phase 6N-D-5): with the
    canonical YAML shape, the WARNING rule should now fire with
    `valid=True` and the rule message in `warnings[]`.
    """
    validator = AgentValidator(config_path=str(VACCINATION_YAML))
    results = validator.validate_thinking(
        agent_type="individual",
        agent_id="Agent_005",
        decision="delay",
        state={},
        reasoning=_ROW_2_REASONING,
    )

    # Find the specific rule fire among results
    matched = [
        r for r in results
        if r.metadata.get("rule_id")
        == "high_barriers_high_self_efficacy_no_action_required"
    ]
    assert len(matched) == 1, (
        f"Expected exactly one fire of "
        f"`high_barriers_high_self_efficacy_no_action_required`; "
        f"got {len(matched)} matches across {len(results)} results."
    )

    r = matched[0]
    # WARNING level — must not block
    assert r.valid is True, (
        f"Phase 6N-D-1 contract: WARNING rule must set valid=True. "
        f"Got valid={r.valid}."
    )
    assert r.warnings, (
        f"WARNING rule must populate warnings[]. Got warnings={r.warnings}."
    )
    assert r.errors == [], (
        f"WARNING rule must NOT populate errors[]. Got errors={r.errors}."
    )


def test_canonical_susceptibility_vl_fires_warning():
    """A second canonical-shape rule fires: SUSCEPTIBILITY=VL + skill=get_vaccinated
    triggers `low_susceptibility_no_get_vaccinated` (WARNING)."""
    validator = AgentValidator(config_path=str(VACCINATION_YAML))
    reasoning = {**_ROW_2_REASONING, "SUSCEPTIBILITY_LABEL": "VL"}
    results = validator.validate_thinking(
        agent_type="individual",
        agent_id="Agent_TEST",
        decision="get_vaccinated",
        state={},
        reasoning=reasoning,
    )
    matched = [
        r for r in results
        if r.metadata.get("rule_id") == "low_susceptibility_no_get_vaccinated"
    ]
    assert len(matched) == 1
    assert matched[0].valid is True  # WARNING
    assert matched[0].warnings


def test_legacy_field_key_also_fires(tmp_path: Path):
    """Phase 6N-E defensive evaluator: legacy `field:` key shape is
    tolerated as a fallback when `construct:` is absent. Pins
    backwards-compatibility so any YAML still using the L3-1C-style
    verbose shape doesn't go silently dead in the future.

    This test FAILS on pre-Phase-6N-E-1 code (no fallback) and
    PASSES post-fix.
    """
    # Synthetic minimal YAML using the legacy `field:` key.
    legacy_yaml = tmp_path / "agent_types_legacy.yaml"
    legacy_yaml.write_text(
        """
global_config: {}
shared:
  normalization_map: {VL: VL, L: L, M: M, H: H, VH: VH}
test_agent:
  agent_type: test_agent
  psychological_framework: hbm
  prompt_template_file: ""
  inherit_shared: true
  actions:
    - { id: do_a, aliases: [do_a, "1"], description: "do A" }
    - { id: do_b, aliases: [do_b, "2"], description: "do B" }
  constructs:
    primary: [TEST_LABEL]
    all: [TEST_LABEL]
  thinking_rules:
    - id: legacy_field_shape_rule
      level: WARNING
      blocked_skills: [do_a]
      conditions:
        # NOTE: uses legacy `field:` shape (NOT canonical `construct:`).
        # The Phase 6N-E-1 defensive evaluator fallback makes this work.
        - { type: construct, field: TEST_LABEL, operator: "in", values: ["H", "VH"] }
      message: "Legacy field-shape rule fired"
""".lstrip(),
        encoding="utf-8",
    )

    validator = AgentValidator(config_path=str(legacy_yaml))
    results = validator.validate_thinking(
        agent_type="test_agent",
        agent_id="Agent_LEGACY",
        decision="do_a",
        state={},
        reasoning={"TEST_LABEL": "H"},
    )
    matched = [
        r for r in results
        if r.metadata.get("rule_id") == "legacy_field_shape_rule"
    ]
    assert len(matched) == 1, (
        f"Phase 6N-E-1 fallback regression: legacy `field:` shape did "
        f"NOT fire. Defensive `cond.get('construct') or cond.get('field')` "
        f"is required. Got {len(matched)} fires across {len(results)} results."
    )
    assert matched[0].valid is True
    assert matched[0].warnings == ["[Rule: legacy_field_shape_rule] Legacy field-shape rule fired"]


def test_rule_set_uses_validator_config_normalization_map(tmp_path: Path):
    """Thinking rules must use the validator's config path, not global defaults."""
    yaml_path = tmp_path / "agent_types_custom_norm.yaml"
    yaml_path.write_text(
        """
global_config: {}
shared:
  normalization_map: {EXTREME: VH}
test_agent:
  agent_type: test_agent
  actions:
    - { id: act, aliases: [act, "1"], description: "act" }
    - { id: wait, aliases: [wait, "2"], description: "wait" }
  thinking_rules:
    - id: custom_norm_rule
      level: ERROR
      blocked_skills: [act]
      conditions:
        - { construct: TEST_LABEL, operator: "in", values: ["VH"] }
      message: "Custom normalization fired"
""".lstrip(),
        encoding="utf-8",
    )

    validator = AgentValidator(config_path=str(yaml_path))
    results = validator.validate_thinking(
        agent_type="test_agent",
        agent_id="Agent_CUSTOM",
        decision="act",
        state={},
        reasoning={"TEST_LABEL": "extreme"},
    )
    matched = [
        r for r in results
        if r.metadata.get("rule_id") == "custom_norm_rule"
    ]
    assert len(matched) == 1
    assert matched[0].valid is False
    assert matched[0].errors == ["[Rule: custom_norm_rule] Custom normalization fired"]
