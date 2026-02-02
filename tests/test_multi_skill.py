"""
Tests for Multi-Skill Proposal support.

Validates:
- MultiSkillProposal dataclass
- SkillBrokerResult secondary fields
- SkillRegistry.check_composite_conflicts()
- ResponseFormatBuilder secondary_choice field type
- agent_config.get_multi_skill_config() toggle
"""
import pytest
from broker.interfaces.skill_types import (
    SkillProposal, MultiSkillProposal, SkillBrokerResult,
    ApprovedSkill, ExecutionResult, SkillOutcome, ValidationResult,
)
from broker.components.skill_registry import SkillRegistry


# ── MultiSkillProposal ──

def _make_proposal(name="buy_insurance", agent_id="a1", mag=None):
    return SkillProposal(
        skill_name=name, agent_id=agent_id,
        reasoning={"threat": "test"}, magnitude_pct=mag,
    )


def test_multi_skill_proposal_single():
    msp = MultiSkillProposal(primary=_make_proposal("buy_insurance"))
    assert not msp.is_composite
    assert msp.skill_names == ["buy_insurance"]
    d = msp.to_dict()
    assert "primary" in d
    assert "secondary" not in d


def test_multi_skill_proposal_composite():
    msp = MultiSkillProposal(
        primary=_make_proposal("buy_insurance"),
        secondary=_make_proposal("elevate_house"),
    )
    assert msp.is_composite
    assert msp.skill_names == ["buy_insurance", "elevate_house"]
    d = msp.to_dict()
    assert d["secondary"]["skill_name"] == "elevate_house"


# ── SkillBrokerResult secondary fields ──

def test_broker_result_backward_compat():
    """When multi_skill is off, secondary fields are None and to_dict is unchanged."""
    result = SkillBrokerResult(
        outcome=SkillOutcome.APPROVED,
        skill_proposal=_make_proposal(),
        approved_skill=ApprovedSkill(
            skill_name="buy_insurance", agent_id="a1", approval_status="APPROVED"
        ),
        execution_result=ExecutionResult(success=True),
    )
    d = result.to_dict()
    assert "secondary_proposal" not in d
    assert "secondary_approved" not in d
    assert "secondary_execution" not in d
    assert "composite_validation_errors" not in d


def test_broker_result_with_secondary():
    """When multi_skill is on, secondary fields appear in to_dict."""
    result = SkillBrokerResult(
        outcome=SkillOutcome.APPROVED,
        skill_proposal=_make_proposal("buy_insurance"),
        approved_skill=ApprovedSkill(
            skill_name="buy_insurance", agent_id="a1", approval_status="APPROVED"
        ),
        execution_result=ExecutionResult(success=True),
        secondary_proposal=_make_proposal("elevate_house"),
        secondary_approved=ApprovedSkill(
            skill_name="elevate_house", agent_id="a1", approval_status="APPROVED"
        ),
        secondary_execution=ExecutionResult(success=True, state_changes={"elevated": True}),
    )
    d = result.to_dict()
    assert d["secondary_proposal"]["skill_name"] == "elevate_house"
    assert d["secondary_approved"]["skill_name"] == "elevate_house"
    assert d["secondary_execution"]["state_changes"]["elevated"] is True


# ── SkillRegistry composite conflicts ──

def _build_registry_with_conflicts():
    from broker.interfaces.skill_types import SkillDefinition
    reg = SkillRegistry()
    for sid, conflicts in [
        ("buy_insurance", []),
        ("elevate_house", ["relocate"]),
        ("relocate", ["elevate_house", "buy_insurance"]),
        ("do_nothing", []),
    ]:
        reg.register(SkillDefinition(
            skill_id=sid, description=sid,
            eligible_agent_types=["*"], preconditions=[],
            institutional_constraints={}, allowed_state_changes=[],
            implementation_mapping=f"sim.{sid}",
            conflicts_with=conflicts,
        ))
    return reg


def test_composite_no_conflict():
    reg = _build_registry_with_conflicts()
    result = reg.check_composite_conflicts(["buy_insurance", "elevate_house"])
    assert result.valid


def test_composite_conflict_elevate_relocate():
    reg = _build_registry_with_conflicts()
    result = reg.check_composite_conflicts(["elevate_house", "relocate"])
    assert not result.valid
    assert "mutually exclusive" in result.errors[0]


def test_composite_conflict_relocate_insurance():
    reg = _build_registry_with_conflicts()
    result = reg.check_composite_conflicts(["relocate", "buy_insurance"])
    assert not result.valid


# ── ResponseFormatBuilder secondary_choice ──

def test_response_format_secondary_choice():
    from broker.components.response_format import ResponseFormatBuilder
    config = {
        "response_format": {
            "fields": [
                {"key": "decision", "type": "choice"},
                {"key": "secondary_decision", "type": "secondary_choice"},
            ]
        }
    }
    rfb = ResponseFormatBuilder(config)
    output = rfb.build(valid_choices_text="1, 2, 3, 4")
    assert "secondary_decision" in output
    assert "OPTIONAL" in output
    assert "or 0 for none" in output
