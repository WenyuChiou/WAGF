"""Regression tests for legacy thinking-rule conditions and normalization."""
from __future__ import annotations

from pathlib import Path

import pytest

import broker.domains.water  # noqa: F401 — register PMT framework
from broker.validators.agent import AgentValidator


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
  psychological_framework: pmt
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
