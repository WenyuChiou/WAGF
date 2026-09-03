"""
Calibration & Validation (C&V) Framework for WAGF.

Three-level validation architecture:

    Level 1 — MICRO:  Individual agent reasoning validation
                       (CACR, EGS, TCS, Action Stability)
    Level 2 — MACRO:  Population-level calibration
                       (KS, Wasserstein, chi-sq, PEBA, MA-EBE)
    Level 3 — COGNITIVE: Psychological construct consistency
                       (psychometric battery, ICC, social amplification)

Validation routing:
    The :class:`ValidationRouter` auto-detects available features from
    ``agent_types.yaml`` config and/or simulation DataFrames, then
    selects appropriate validators via a decision-tree.

References:
    Grimm et al. (2005) Pattern-oriented modelling — multi-level validation
    Thiele et al. (2014) PEBA — distributional feature matching
    Windrum et al. (2007) Empirical validation survey
    Huang et al. (2025) LLM psychometric testing (Nature MI)

Part of WAGF C&V Framework (feature/calibration-validation).
"""

from broker.domains.water.calibration.micro_validator import (
    MicroValidator,
    BRCResult,
    CACRResult,
    EGSResult,
    TCSResult,
    RHResult,
    EBEResult,
    MicroReport,
)
from broker.domains.water.calibration.distribution_matcher import (
    DistributionMatcher,
    DistributionTestResult,
    PEBAFeatures,
    MacroReport,
)
from broker.domains.water.calibration.temporal_coherence import (
    ActionStabilityValidator,
    TemporalCoherenceValidator,
    TransitionMatrix,
    TemporalReport,
    AgentTCSResult,
)
from broker.domains.water.calibration.validation_router import (
    FeatureProfile,
    ValidationPlan,
    ValidationRouter,
    ValidatorSpec,
    ValidatorType,
)
# PR-7 (2026-09): benchmark_registry / directional_validator /
# calibration_protocol moved to broker.calibration (generic,
# water-token-free). Importing directly from the new location here
# means `import broker.domains.water.calibration` (this package) does
# NOT itself trigger the submodules' DeprecationWarning — only an
# explicit `from broker.domains.water.calibration.benchmark_registry
# import ...` (the old submodule path, now a shim) does. Same objects
# either way; this is purely where the names are resolved from.
from broker.calibration.benchmark_registry import (
    Benchmark,
    BenchmarkCategory,
    BenchmarkComparison,
    BenchmarkRegistry,
    BenchmarkReport,
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

__all__ = [
    # Level 1 — MICRO
    "MicroValidator",
    "BRCResult",
    "CACRResult",
    "EGSResult",
    "TCSResult",
    "RHResult",
    "EBEResult",
    "MicroReport",
    # Level 2 — MACRO
    "DistributionMatcher",
    "DistributionTestResult",
    "PEBAFeatures",
    "MacroReport",
    # TCS + Action Stability
    "ActionStabilityValidator",
    "TemporalCoherenceValidator",
    "TransitionMatrix",
    "TemporalReport",
    "AgentTCSResult",
    # Validation Router
    "FeatureProfile",
    "ValidationPlan",
    "ValidationRouter",
    "ValidatorSpec",
    "ValidatorType",
    # Calibration Protocol
    "Benchmark",
    "BenchmarkCategory",
    "BenchmarkComparison",
    "BenchmarkRegistry",
    "BenchmarkReport",
    "DirectionalValidator",
    "DirectionalTest",
    "DirectionalTestResult",
    "DirectionalReport",
    "SwapTest",
    "chi_squared_test",
    "mann_whitney_u",
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
]
