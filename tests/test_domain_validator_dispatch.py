import inspect

from broker.validators import governance as governance_module


def test_governance_module_has_no_direct_example_imports():
    source = inspect.getsource(governance_module)
    assert "from examples." not in source


def test_water_domain_exposes_validator_builder():
    # Phase 6J-D (2026-05-22): the lazy ``_ensure_*_registered``
    # reverse-import fallback was removed, so this test must register
    # the example checks itself by importing the example packages —
    # otherwise ``build_domain_validators`` returns ``_empty_validators()``
    # and ``len(...) == 5`` passes vacuously (5 empty wrappers).
    import examples.governed_flood  # noqa: F401 — registers FloodDomainPack + checks
    import examples.irrigation_abm  # noqa: F401 — registers IrrigationDomainPack + checks
    from broker.domains.water.validator_bundles import build_domain_validators
    from broker.validators.governance.physical_validator import PhysicalValidator

    irrigation_validators = build_domain_validators("irrigation")
    flood_validators = build_domain_validators("flood")
    generic_validators = build_domain_validators(None)

    assert len(irrigation_validators) == 5
    assert len(flood_validators) == 5
    assert len(generic_validators) == 5

    # Guard against the vacuous-pass case: a populated domain's
    # PhysicalValidator must carry at least one builtin check; an
    # unconfigured (generic) one must not.
    flood_pv = next(v for v in flood_validators if isinstance(v, PhysicalValidator))
    irrigation_pv = next(v for v in irrigation_validators if isinstance(v, PhysicalValidator))
    generic_pv = next(v for v in generic_validators if isinstance(v, PhysicalValidator))
    assert flood_pv._builtin_checks, "flood physical checks must register on package import"
    assert irrigation_pv._builtin_checks, "irrigation physical checks must register on package import"
    assert not generic_pv._builtin_checks, "generic builder must carry no domain checks"


def test_validator_registry_returns_empty_for_unknown_domain():
    """Phase 6B-1: ValidatorRegistry should return [] (and warn) when
    asked for a domain it has not seen, rather than crashing."""
    from broker.components.governance.validator_registry import ValidatorRegistry

    result = ValidatorRegistry.get_checks("nonexistent_groundwater_domain", "physical")
    assert result == []


def test_validator_registry_round_trip():
    """Phase 6B-1: register a synthetic domain + slot, then read it back."""
    from broker.components.governance.validator_registry import ValidatorRegistry

    sentinel_check = lambda agent, ctx: True  # noqa: E731 -- test fixture
    ValidatorRegistry.register("test_domain_xyz", "physical", [sentinel_check])
    checks = ValidatorRegistry.get_checks("test_domain_xyz", "physical")
    assert len(checks) == 1
    assert checks[0] is sentinel_check
    # cleanup so other tests stay deterministic
    ValidatorRegistry._registry.pop("test_domain_xyz", None)


def test_validator_registry_rejects_invalid_slot():
    """Phase 6B-1: invalid slot name should raise ValueError, not silently misregister."""
    import pytest

    from broker.components.governance.validator_registry import ValidatorRegistry

    with pytest.raises(ValueError, match="slot must be one of"):
        ValidatorRegistry.register("foo", "not_a_slot", [])
