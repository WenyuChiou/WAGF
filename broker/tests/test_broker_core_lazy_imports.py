"""Phase 6Q-H (2026-05-26) — direct coverage of broker.core PEP 562
lazy `__getattr__` for moved water-namespace classes.

The Phase 6Q-F-1 eager-import fix in `broker/core/__init__.py`
removed `PMTFramework` / `UtilityFramework` / `FinancialFramework`
from the package's top-level eager re-export and routed them
through a package-level `__getattr__` that imports them lazily from
their canonical `broker.domains.water.*` addresses.

Pre-6Q-H the subprocess genericity gate at
`test_genericity_runtime_gate.py::TestTrafficDomainSysModulesGate`
INDIRECTLY exercised this lazy path (by asserting that simply
importing `broker.core` doesn't pull water modules), but no test
directly verified that `from broker.core import PMTFramework`
returns the correct class — a future edit that broke the lazy
dispatch (e.g. a typo in `_LAZY_WATER_REEXPORTS`, or a wrong
import_module call) would not be caught by any existing test.

This file is the direct regression guard.
"""
from __future__ import annotations

import importlib
import sys

import pytest


# Water frameworks must be available — the test asserts the lazy
# dispatch resolves them correctly, but the underlying module must
# exist for that resolution to succeed. Importing the package
# triggers its own register() side effect, which is fine; the test
# isolates the lazy-attribute mechanic from the registration.
import broker.domains.water  # noqa: F401


# The canonical map post-Phase-6Q-F-1.
_EXPECTED_LAZY_MAP = {
    "PMTFramework": "broker.domains.water.pmt",
    "UtilityFramework": "broker.domains.water.utility",
    "FinancialFramework": "broker.domains.water.financial",
}


class TestBrokerCorePEP562LazyDispatch:
    """Pin the `broker/core/__init__.py::__getattr__` contract."""

    def test_lazy_map_is_canonical(self):
        """The module-level `_LAZY_WATER_REEXPORTS` dict literal in
        `broker/core/__init__.py` should match the expected mapping.
        If a name is added or moved, both this test and the real
        dispatch table need to update in lockstep."""
        from broker.core import _LAZY_WATER_REEXPORTS
        assert _LAZY_WATER_REEXPORTS == _EXPECTED_LAZY_MAP

    def test_lazy_names_are_NOT_in_module_dict_before_access(self):
        """Phase 6Q-F-1 contract: the moved water classes must NOT
        be eager-imported. Their names are absent from
        `broker.core.__dict__` until the first attribute access."""
        # Reload resets `broker.core.__dict__` populated by any prior
        # `from broker.core import <Name>` in this pytest session,
        # giving us a clean module-state baseline. PEP 562
        # `__getattr__` itself does not write back onto `__dict__`
        # on CPython 3.7+, so post-reload the moved names should
        # stay absent unless someone re-accesses them.
        import broker.core
        importlib.reload(broker.core)
        for name in _EXPECTED_LAZY_MAP:
            assert name not in broker.core.__dict__, (
                f"{name!r} eagerly cached on broker.core.__dict__ — "
                f"the Phase 6Q-F-1 lazy contract is broken."
            )

    @pytest.mark.parametrize("name,module_path", sorted(_EXPECTED_LAZY_MAP.items()))
    def test_lazy_attribute_resolves_to_canonical_class(self, name, module_path):
        """`from broker.core import <name>` must return the same
        class object as `from broker.domains.water.<module> import <name>`.
        Pins the dispatch correctness."""
        from_core = getattr(__import__("broker.core", fromlist=[name]), name)
        canonical_mod = importlib.import_module(module_path)
        from_canonical = getattr(canonical_mod, name)
        assert from_core is from_canonical, (
            f"broker.core.{name} ({from_core!r}) != "
            f"{module_path}.{name} ({from_canonical!r}) — lazy "
            f"dispatch returned the wrong class."
        )

    def test_unknown_attribute_raises_attributeerror(self):
        """The `__getattr__` must raise AttributeError (not return
        None or some default) for unrecognised names — Python's
        standard contract for module attribute access."""
        import broker.core
        with pytest.raises(AttributeError, match="no attribute"):
            broker.core.NotARealClass  # noqa
