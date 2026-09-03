"""
broker.calibration — Generic, domain-agnostic calibration & optimization.

Split out of ``broker/domains/water/calibration/`` in PR-7 (2026-09):
the three modules here (``benchmark_registry``, ``calibration_protocol``,
``directional_validator``) carry no water-domain content — no PMT
labels, no flood/irrigation constants, only caller-supplied definitions.
They moved here so a non-water WAGF domain can use them without
importing through ``broker.domains.water``.

What stayed under ``broker/domains/water/calibration/`` and why: every
other module there (``micro_validator``, ``distribution_matcher``,
``temporal_coherence``, ``psychometric_*``, ``validation_router``,
``cv_runner``, ``conservatism_diagnostic``) either imports water-domain
keyword lists directly (``micro_validator`` pulls ``TA_KEYWORDS`` /
``CA_KEYWORDS`` from ``broker.domains.water.posthoc_keywords``) or has
PMT-specific defaults baked in (hardcoded flood action names, the PMT
5-level ordinal scale as a fallback). Moving those would mean either
carrying the water coupling into a "generic" namespace or doing a
larger surgical split than this PR's scope — see
``docs/guides/calibration_guide.md``.

Backward compatibility: ``broker.domains.water.calibration.{benchmark_registry,
calibration_protocol, directional_validator}`` are now thin re-export
shims that emit ``DeprecationWarning`` on import. Update call sites to
import from here; the shims are not scheduled for removal yet.

New in this package:

* :mod:`broker.calibration.optimize` — the numeric parameter search
  that ``CalibrationProtocol``'s pilot loop never was (see that
  module's docstring for the audit finding).
* :mod:`broker.calibration.benchmark_diff` — lists where two benchmark
  tables disagree about the same metric names. It reconciles nothing;
  it makes the disagreements enumerable so they cannot go quiet.
"""

from __future__ import annotations

from broker.calibration.benchmark_registry import (
    Benchmark,
    BenchmarkCategory,
    BenchmarkComparison,
    BenchmarkRegistry,
    BenchmarkReport,
)
from broker.calibration.benchmark_diff import (
    BenchmarkDiff,
    BenchmarkDisagreement,
    BenchmarkSpec,
    diff_benchmark_tables,
    normalize_table,
)
from broker.calibration.directional_validator import (
    DirectionalValidator,
    DirectionalTest,
    DirectionalTestResult,
    DirectionalReport,
    SwapTest,
    chi_squared_test,
    mann_whitney_u,
)
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
)
from broker.calibration.optimize import (
    optimize_parameters,
    split_targets,
    flatten_dict,
    unflatten_dict,
    OptimizeResult,
    TargetSplit,
    ObjectiveFn,
)

__all__ = [
    # Benchmark registry
    "Benchmark",
    "BenchmarkCategory",
    "BenchmarkComparison",
    "BenchmarkRegistry",
    "BenchmarkReport",
    # Benchmark table comparison
    "BenchmarkDiff",
    "BenchmarkDisagreement",
    "BenchmarkSpec",
    "diff_benchmark_tables",
    "normalize_table",
    # Directional validator
    "DirectionalValidator",
    "DirectionalTest",
    "DirectionalTestResult",
    "DirectionalReport",
    "SwapTest",
    "chi_squared_test",
    "mann_whitney_u",
    # Calibration protocol
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
    # Optimizer
    "optimize_parameters",
    "split_targets",
    "flatten_dict",
    "unflatten_dict",
    "OptimizeResult",
    "TargetSplit",
    "ObjectiveFn",
]
