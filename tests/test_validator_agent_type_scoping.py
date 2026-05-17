from __future__ import annotations

from broker.core.skill_broker_engine import SkillBrokerEngine
from broker.interfaces.skill_types import ValidationResult
from broker.interfaces.skill_types import SkillProposal
from broker.validators.governance.base_validator import BaseValidator, scoped_to


class TriggerValidator(BaseValidator):
    @property
    def category(self) -> str:
        return "thinking"


def _blocking_result(rule_id: str = "builtin_rule") -> ValidationResult:
    return ValidationResult(
        valid=False,
        errors=["blocked by scoped builtin test"],
        validator_name="X",
        metadata={"rule_id": rule_id},
    )


def test_scoped_builtin_runs_only_for_matching_agent_type():
    calls = []

    @scoped_to("household_owner")
    def owner_check(skill_name, rules, context):
        calls.append(context["agent_type"])
        return [_blocking_result()]

    validator = TriggerValidator(builtin_checks=[owner_check])

    owner_results = validator.validate(
        "do_nothing",
        [],
        {"agent_type": "household_owner", "reasoning": {}},
    )
    renter_results = validator.validate(
        "do_nothing",
        [],
        {"agent_type": "household_renter", "reasoning": {}},
    )

    assert len(owner_results) == 1
    assert owner_results[0].valid is False
    assert renter_results == []
    assert calls == ["household_owner"]


def test_scoped_builtin_for_renter_skips_household_owner_context():
    calls = []

    @scoped_to("household_renter")
    def renter_check(skill_name, rules, context):
        calls.append(context["agent_type"])
        return [_blocking_result()]

    validator = TriggerValidator(builtin_checks=[renter_check])

    results = validator.validate(
        "do_nothing",
        [],
        {"agent_type": "household_owner", "reasoning": {}},
    )

    assert results == []
    assert calls == []


def test_unscoped_builtin_runs_for_all_agent_types():
    calls = []

    def unscoped_check(skill_name, rules, context):
        calls.append(context["agent_type"])
        return [_blocking_result(context["agent_type"])]

    validator = TriggerValidator(builtin_checks=[unscoped_check])

    owner_results = validator.validate(
        "do_nothing",
        [],
        {"agent_type": "household_owner", "reasoning": {}},
    )
    renter_results = validator.validate(
        "do_nothing",
        [],
        {"agent_type": "household_renter", "reasoning": {}},
    )

    assert len(owner_results) == 1
    assert len(renter_results) == 1
    assert calls == ["household_owner", "household_renter"]


def test_scoped_builtin_runs_when_base_type_matches():
    calls = []

    @scoped_to("household")
    def household_check(skill_name, rules, context):
        calls.append((context["agent_type"], context["base_type"]))
        return [_blocking_result()]

    validator = TriggerValidator(builtin_checks=[household_check])

    results = validator.validate(
        "do_nothing",
        [],
        {
            "agent_type": "household_owner",
            "base_type": "household",
            "reasoning": {},
        },
    )

    assert len(results) == 1
    assert results[0].valid is False
    assert calls == [("household_owner", "household")]


def test_scoped_builtin_that_runs_still_uses_shadow_transform():
    @scoped_to("X")
    def scoped_shadow_check(skill_name, rules, context):
        return [_blocking_result("shadowed_builtin")]

    validator = TriggerValidator(
        builtin_checks=[scoped_shadow_check],
        mode="shadow",
    )

    results = validator.validate("do_nothing", [], {"agent_type": "X"})

    assert len(results) == 1
    result = results[0]
    assert result.valid is True
    assert result.errors == []
    assert "blocked by scoped builtin test" in result.warnings
    assert result.metadata["shadow_blocked"] == ["shadowed_builtin"]
    assert result.metadata["would_block_level"] == "ERROR"


def test_scoped_builtin_runs_when_context_lacks_agent_and_base_type():
    calls = []

    @scoped_to("household_owner")
    def owner_check(skill_name, rules, context):
        calls.append(dict(context))
        return [_blocking_result()]

    validator = TriggerValidator(builtin_checks=[owner_check])

    results = validator.validate("do_nothing", [], {"reasoning": {}})

    assert len(results) == 1
    assert results[0].valid is False
    assert calls == [{"reasoning": {}}]


def test_run_validators_adds_scope_context_without_mutating_caller_context():
    class CaptureValidator:
        def __init__(self):
            self.contexts = []

        def validate(self, proposal, context, registry):
            self.contexts.append(context)
            return []

    class Config:
        def get_governance_retries(self, default):
            return default

        def get_governance_max_reports(self):
            return 3

        def get_base_type(self, agent_type):
            return "household"

    capture = CaptureValidator()
    engine = SkillBrokerEngine(
        skill_registry=None,
        model_adapter=None,
        validators=[capture],
        simulation_engine=None,
        context_builder=None,
        config=Config(),
        skill_retriever=object(),
    )
    proposal = SkillProposal(
        skill_name="do_nothing",
        agent_id="agent_1",
        reasoning={},
        agent_type="household_owner",
    )
    context = {"agent_state": {"state": {}}}

    engine._run_validators(proposal, context)

    assert context == {"agent_state": {"state": {}}}
    assert capture.contexts[0]["agent_type"] == "household_owner"
    assert capture.contexts[0]["base_type"] == "household"


def test_run_validators_resolves_base_type_for_scoped_builtin_without_mutating_caller_context():
    calls = []

    @scoped_to("household")
    def household_check(skill_name, rules, context):
        calls.append((skill_name, context["agent_type"], context["base_type"]))
        return [_blocking_result()]

    class EngineTriggerValidator(TriggerValidator):
        def validate(self, proposal, context, registry):
            return super().validate(proposal.skill_name, [], context)

    class Config:
        def get_governance_retries(self, default):
            return default

        def get_governance_max_reports(self):
            return 3

        def get_base_type(self, agent_type):
            return "household"

    engine = SkillBrokerEngine(
        skill_registry=None,
        model_adapter=None,
        validators=[EngineTriggerValidator(builtin_checks=[household_check])],
        simulation_engine=None,
        context_builder=None,
        config=Config(),
        skill_retriever=object(),
    )
    proposal = SkillProposal(
        skill_name="do_nothing",
        agent_id="agent_1",
        reasoning={},
        agent_type="household_owner",
    )
    context = {"agent_state": {"state": {}}}

    results = engine._run_validators(proposal, context)

    assert context == {"agent_state": {"state": {}}}
    assert len(results) == 1
    assert results[0].valid is False
    assert calls == [("do_nothing", "household_owner", "household")]
