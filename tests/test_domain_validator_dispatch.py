import inspect

from broker.validators import governance as governance_module


def test_governance_module_has_no_direct_example_imports():
    source = inspect.getsource(governance_module)
    assert "from examples." not in source


def test_water_domain_exposes_validator_builder():
    from broker.domains.water.validator_bundles import build_domain_validators

    irrigation_validators = build_domain_validators("irrigation")
    flood_validators = build_domain_validators("flood")
    generic_validators = build_domain_validators(None)

    assert len(irrigation_validators) == 5
    assert len(flood_validators) == 5
    assert len(generic_validators) == 5
