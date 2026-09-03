"""Deprecated re-export shim — moved to :mod:`broker.calibration.calibration_protocol`.

``CalibrationProtocol`` orchestrates the generic ``BenchmarkRegistry``
and ``DirectionalValidator`` via caller-supplied callbacks and carries
no water-domain content, so PR-7 (2026-09) moved this module to the
generic ``broker.calibration`` package. This shim keeps every existing
``from broker.domains.water.calibration.calibration_protocol import
...`` working while warning so call sites can update at their own
pace.

As of this PR, ``CalibrationProtocol`` has zero production call sites
(only tests and a docstring usage example in
``examples/multi_agent/flood/paper3/analysis/calibration_hooks.py``
reference it) — see ``docs/guides/calibration_guide.md``. It is also
not an optimizer: see the moved module's docstring for the audit
finding and :mod:`broker.calibration.optimize` for the actual search.

A re-export shim has to carry *everything* the old module made
importable, not just its headline classes — ``from
broker.domains.water.calibration.calibration_protocol import
BenchmarkRegistry`` worked before the move, so it still has to work
now. That includes the callback type aliases (``SimulateFn`` /
``ComputeMetricsFn`` / ``InvokeLLMFn``) and the names this module
itself imports from the sibling calibration modules.
``broker/tests/test_calibration_pr7.py::TestShims`` compares the two
namespaces so a name cannot be dropped unnoticed.

Update imports to ``broker.calibration.calibration_protocol``.
"""

from __future__ import annotations

import warnings

from broker.calibration.calibration_protocol import (
    CalibrationProtocol,
    CalibrationConfig,
    CalibrationReport,
    CalibrationStage,
    StageVerdict,
    AdjustmentRecommendation,
    FullConfig,
    PilotConfig,
    PilotIterationResult,
    SensitivityConfig,
    StageReport,
    # Callback type aliases — importable from the old path too.
    SimulateFn,
    ComputeMetricsFn,
    InvokeLLMFn,
    # Names the moved module re-exposes from its siblings; they were
    # reachable through this module's namespace before the move.
    Benchmark,
    BenchmarkRegistry,
    BenchmarkReport,
    DirectionalValidator,
    DirectionalReport,
    DirectionalTest,
    SwapTest,
)

warnings.warn(
    "broker.domains.water.calibration.calibration_protocol is "
    "deprecated and will be removed in a future release; import from "
    "broker.calibration.calibration_protocol instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "CalibrationProtocol",
    "CalibrationConfig",
    "CalibrationReport",
    "CalibrationStage",
    "StageVerdict",
    "AdjustmentRecommendation",
    "FullConfig",
    "PilotConfig",
    "PilotIterationResult",
    "SensitivityConfig",
    "StageReport",
    "SimulateFn",
    "ComputeMetricsFn",
    "InvokeLLMFn",
    "Benchmark",
    "BenchmarkRegistry",
    "BenchmarkReport",
    "DirectionalValidator",
    "DirectionalReport",
    "DirectionalTest",
    "SwapTest",
]
