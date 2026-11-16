"""Validate-time regression coverage for the generic framework escape hatch."""

class TestThinkingValidatorEscapeHatchValidateTime:
    """``ThinkingValidator(framework="")`` must execute ``validate()``
    cleanly when constructs and built-in checks are both empty.

    The escape-hatch path is the contract for any non-water domain
    that did not register a psychometric framework (per Phase 6Q-D).
    """

    def test_escape_hatch_validate_empty_state(self):
        from broker.validators.governance.thinking_validator import (
            ThinkingValidator,
            FRAMEWORK_ESCAPE_HATCH,
        )
        # builtin_checks=[] disables domain defaults so this stays a
        # pure base-class + YAML-rules-loop check (matches the
        # dispatcher's escape-hatch branch in build_domain_validators).
        validator = ThinkingValidator(
            framework=FRAMEWORK_ESCAPE_HATCH,
            builtin_checks=[],
        )
        # No constructs registered, no rules supplied, empty reasoning.
        results = validator.validate(
            skill_name="do_nothing",
            rules=[],
            context={"reasoning": {}, "state": {}},
        )
        assert isinstance(results, list)
        assert len(results) == 0
        # Sanity: the validator carries the escape-hatch sentinel.
        assert validator.framework == FRAMEWORK_ESCAPE_HATCH
        assert validator._constructs == {}

    def test_escape_hatch_validate_with_framework_agnostic_rule(self):
        from broker.governance.rule_types import GovernanceRule, RuleCondition
        from broker.validators.governance.thinking_validator import (
            ThinkingValidator,
            FRAMEWORK_ESCAPE_HATCH,
        )
        # A precondition-typed rule with no ``framework=`` field is
        # framework-agnostic per ``_validate_yaml_rules`` lines 354-357:
        # ``rule_framework = getattr(rule, 'framework', None)`` → None,
        # so the ``if rule_framework and rule_framework != framework``
        # skip never fires.
        rule = GovernanceRule(
            id="test_escape_hatch_precondition_rule",
            category="thinking",
            conditions=[
                RuleCondition(
                    type="precondition",
                    field="ready_state",
                    operator="==",
                    values=[True],
                )
            ],
            blocked_skills=["take_alternate_route"],
            level="ERROR",
            message="Cannot take alternate route when ready_state is True.",
        )
        validator = ThinkingValidator(
            framework=FRAMEWORK_ESCAPE_HATCH,
            builtin_checks=[],
        )
        results = validator.validate(
            skill_name="take_alternate_route",
            rules=[rule],
            context={"reasoning": {}, "state": {"ready_state": True}},
        )
        # Rule should trigger at least once — the same rule is
        # evaluated by both the base-class YAML path (``super().validate``
        # at thinking_validator.py:318) and the multi-condition path
        # (``_validate_yaml_rules`` at :322), so the precise count is an
        # internal evaluator detail. The point of this regression guard
        # is that validate-time does NOT crash on the escape-hatch path
        # when no constructs are registered, and that ERROR-level rule
        # metadata flows through correctly.
        assert isinstance(results, list)
        assert len(results) >= 1
        # Every triggered result must reference our rule and report
        # an ERROR-level block. The two evaluation paths
        # (``super().validate`` and ``_validate_yaml_rules``) populate
        # slightly different metadata key-sets — only the multi-condition
        # path injects ``framework`` — so we only assert keys both
        # paths agree on. The framework-leak guard belongs to the
        # multi-condition path; assert it on the subset of results that
        # carry it.
        for result in results:
            assert result.valid is False  # ERROR-level
            assert result.metadata["rule_id"] == "test_escape_hatch_precondition_rule"
        framework_tagged = [
            r for r in results if "framework" in r.metadata
        ]
        assert framework_tagged, (
            "at least one result must carry the framework key "
            "(emitted by _validate_yaml_rules)"
        )
        for result in framework_tagged:
            assert result.metadata["framework"] == FRAMEWORK_ESCAPE_HATCH
