"""Deprecated re-export shim — moved to :mod:`broker.calibration.directional_validator`.

``DirectionalValidator`` is a callback-based sensitivity-testing engine
with no water-domain content, so PR-7 (2026-09) moved this module to
the generic ``broker.calibration`` package. This shim keeps every
existing ``from broker.domains.water.calibration.directional_validator
import ...`` working — including ``chi_squared_test``, which is the
only symbol from this module with a live production call site
(``examples/multi_agent/flood/paper3/analysis/persona_sensitivity.py``
and ``prompt_sensitivity.py``) — while warning so call sites can update
at their own pace.

The callback type aliases (``PromptBuilderFn`` / ``ParseFn`` /
``InvokeFn``) are re-exported too — they were importable from the old
path, so dropping them would break a type annotation that used to
resolve. ``broker/tests/test_calibration_pr7.py::TestShims`` compares
the two namespaces so a name cannot go missing unnoticed.

Update imports to ``broker.calibration.directional_validator``.
"""

from __future__ import annotations

import warnings

from broker.calibration.directional_validator import (
    DirectionalValidator,
    DirectionalTest,
    DirectionalTestResult,
    DirectionalReport,
    SwapTest,
    chi_squared_test,
    mann_whitney_u,
    # Callback type aliases — importable from the old path too.
    PromptBuilderFn,
    ParseFn,
    InvokeFn,
)

warnings.warn(
    "broker.domains.water.calibration.directional_validator is "
    "deprecated and will be removed in a future release; import from "
    "broker.calibration.directional_validator instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "DirectionalValidator",
    "DirectionalTest",
    "DirectionalTestResult",
    "DirectionalReport",
    "SwapTest",
    "chi_squared_test",
    "mann_whitney_u",
    "PromptBuilderFn",
    "ParseFn",
    "InvokeFn",
]
