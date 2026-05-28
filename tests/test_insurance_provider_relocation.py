"""Phase 6U-C regression tests for InsuranceInfoProvider relocation.

Verifies the class lives at its new canonical location
(``broker.domains.water.insurance_provider``) and that the legacy
import path (``broker.components.context.providers``) still works
but emits a DeprecationWarning.
"""
import warnings

import pytest


def test_new_canonical_import_clean():
    """No DeprecationWarning on import from the canonical path."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        from broker.domains.water.insurance_provider import InsuranceInfoProvider

        assert InsuranceInfoProvider is not None


def test_legacy_import_path_warns():
    """Legacy `broker.components.context.providers` import path
    forwards to the canonical class via __getattr__ shim with
    DeprecationWarning."""
    # Cannot use `import broker.components.context.providers.InsuranceInfoProvider`
    # syntax directly; use getattr on the module to exercise __getattr__.
    import broker.components.context.providers as legacy_module

    with pytest.warns(
        DeprecationWarning,
        match=r"InsuranceInfoProvider moved to broker\.domains\.water",
    ):
        legacy_cls = legacy_module.InsuranceInfoProvider

    from broker.domains.water.insurance_provider import InsuranceInfoProvider

    assert legacy_cls is InsuranceInfoProvider


def test_unknown_attribute_still_raises_attribute_error():
    """The __getattr__ shim must NOT mask AttributeError for other
    missing names — only forward the InsuranceInfoProvider name."""
    import broker.components.context.providers as legacy_module

    with pytest.raises(AttributeError):
        _ = legacy_module.NonExistentProvider
