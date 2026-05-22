"""Phase 6H Item 7: FinancialCostProvider's canonical home is the water
domain.

The flood-coupled generic copy in `broker/components/context/providers.py`
was deleted (it hardcoded `flood_zone` / NFIP / Passaic narratives); the
single canonical copy now lives in `broker/domains/water/providers.py`.
These tests guard the relocation — the provider must be importable from
the water domain and absent from generic broker code.
"""
from broker.components.context.providers import ContextProvider
from broker.domains.water.providers import FinancialCostProvider


def test_financial_cost_provider_importable_from_water():
    """The canonical FinancialCostProvider lives in the water domain."""
    provider = FinancialCostProvider()
    assert isinstance(provider, ContextProvider)


def test_financial_cost_provider_absent_from_generic_broker():
    """The flood-coupled copy must NOT be re-importable from generic
    broker code — that was the Item 7 de-flood."""
    import broker.components.context.providers as generic_providers

    assert not hasattr(generic_providers, "FinancialCostProvider")
    assert "FinancialCostProvider" not in getattr(
        generic_providers, "__all__", []
    )
