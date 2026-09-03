"""Deprecated re-export shim — moved to :mod:`broker.calibration.benchmark_registry`.

``BenchmarkRegistry`` and friends carry no water-domain content (all
benchmark definitions come from the caller), so PR-7 (2026-09) moved
this module to the generic ``broker.calibration`` package. This shim
keeps every existing ``from broker.domains.water.calibration.benchmark_registry
import ...`` working — it re-exports the exact same objects, so
``isinstance`` checks and identity comparisons are unaffected — while
warning so call sites can update at their own pace.

Update imports to ``broker.calibration.benchmark_registry``.
"""

from __future__ import annotations

import warnings

from broker.calibration.benchmark_registry import (
    Benchmark,
    BenchmarkCategory,
    BenchmarkComparison,
    BenchmarkRegistry,
    BenchmarkReport,
)

warnings.warn(
    "broker.domains.water.calibration.benchmark_registry is deprecated "
    "and will be removed in a future release; import from "
    "broker.calibration.benchmark_registry instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "Benchmark",
    "BenchmarkCategory",
    "BenchmarkComparison",
    "BenchmarkRegistry",
    "BenchmarkReport",
]
