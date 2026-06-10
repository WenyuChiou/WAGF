"""Regression tests for the unified behavioural-framework registration facade."""
from __future__ import annotations

import pytest

from broker.core.psychometric import (
    ConstructDef,
    PsychologicalFramework,
    ValidationResult,
    get_framework,
)


@pytest.fixture
def restore_framework_registries():
    """Keep facade tests from leaking transient framework registrations."""
    from broker.core import psychometric
    from broker.validators.governance import thinking_validator

    saved_frameworks = dict(psychometric._FRAMEWORKS)  # registry has no public iterator.
    saved_label_orders = dict(thinking_validator.FRAMEWORK_LABEL_ORDERS)
    saved_constructs = dict(thinking_validator.FRAMEWORK_CONSTRUCTS)
    saved_label_mappings = dict(thinking_validator._LABEL_MAPPINGS)
    saved_checks = dict(thinking_validator._THINKING_CHECKS_BY_FRAMEWORK)
    try:
        yield
    finally:
        psychometric._FRAMEWORKS.clear()
        psychometric._FRAMEWORKS.update(saved_frameworks)
        thinking_validator.FRAMEWORK_LABEL_ORDERS.clear()
        thinking_validator.FRAMEWORK_LABEL_ORDERS.update(saved_label_orders)
        thinking_validator.FRAMEWORK_CONSTRUCTS.clear()
        thinking_validator.FRAMEWORK_CONSTRUCTS.update(saved_constructs)
        thinking_validator._LABEL_MAPPINGS.clear()
        thinking_validator._LABEL_MAPPINGS.update(saved_label_mappings)
        thinking_validator._THINKING_CHECKS_BY_FRAMEWORK.clear()
        thinking_validator._THINKING_CHECKS_BY_FRAMEWORK.update(saved_checks)


class TinyFramework(PsychologicalFramework):
    @property
    def name(self) -> str:
        return "Tiny"

    def get_constructs(self):
        return {
            "PRIMARY_LABEL": ConstructDef(
                name="Primary", values=["L", "M", "H"]
            )
        }

    def validate_coherence(self, appraisals):
        return ValidationResult(valid=True)

    def get_expected_behavior(self, appraisals):
        return ["act"]


def test_facade_allows_deliberate_metadata_only_registration(
    restore_framework_registries,
):
    from broker.validators.governance.frameworks import register_behavioral_framework
    from broker.validators.governance.thinking_validator import ThinkingValidator

    name = "test_metadata_only"
    register_behavioral_framework(
        name,
        constructs={
            "primary": "PRIMARY_LABEL",
            "secondary": "PRIMARY_LABEL",
            "all": ["PRIMARY_LABEL"],
        },
        label_order={"L": 0, "M": 1, "H": 2},
    )

    assert ThinkingValidator(framework=name) is not None
    with pytest.raises(ValueError, match="Unknown framework"):
        get_framework(name)


def test_facade_registers_psychometric_class_when_supplied(
    restore_framework_registries,
):
    from broker.validators.governance.frameworks import register_behavioral_framework

    register_behavioral_framework(
        "test_tiny_class",
        constructs={
            "primary": "PRIMARY_LABEL",
            "secondary": "PRIMARY_LABEL",
            "all": ["PRIMARY_LABEL"],
        },
        label_order={"L": 0, "M": 1, "H": 2},
        framework_class=TinyFramework,
    )

    instance = get_framework("test_tiny_class")
    assert isinstance(instance, TinyFramework)


def test_psychometric_class_registry_never_lacks_metadata(
    restore_framework_registries,
):
    import broker.validators.governance  # noqa: F401
    from broker.core import psychometric
    from broker.validators.governance.thinking_validator import FRAMEWORK_LABEL_ORDERS

    # _FRAMEWORKS is the only current registry surface for behavioural classes.
    missing = [
        name for name in psychometric._FRAMEWORKS
        if name not in FRAMEWORK_LABEL_ORDERS
    ]
    assert missing == []
