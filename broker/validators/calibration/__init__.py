"""
Calibration & Validation (C&V) Framework for SAGE.

Three-level validation architecture:

    Level 1 — MICRO:  Individual agent reasoning validation
                       (CACR, EGS, TCS, Action Stability)
    Level 2 — MACRO:  Population-level calibration
                       (KS, Wasserstein, chi-sq, PEBA, MA-EBE)
    Level 3 — COGNITIVE: Psychological construct fidelity
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

Part of SAGE C&V Framework (feature/calibration-validation).
"""

from broker.validators.calibration.micro_validator import (
    MicroValidator,
    BRCResult,
    CACRResult,
    EGSResult,
    TCSResult,
    RHResult,
    EBEResult,
    MicroReport,
)
from broker.validators.calibration.distribution_matcher import (
    DistributionMatcher,
    DistributionTestResult,
    PEBAFeatures,
    MacroReport,
)
from broker.validators.calibration.temporal_coherence import (
    ActionStabilityValidator,
    TemporalCoherenceValidator,
    TransitionMatrix,
    TemporalReport,
    AgentTCSResult,
)
from broker.validators.calibration.validation_router import (
    FeatureProfile,
    ValidationPlan,
    ValidationRouter,
    ValidatorSpec,
    ValidatorType,
)
from broker.validators.calibration.benchmark_registry import (
    Benchmark,
    BenchmarkCategory,
    BenchmarkComparison,
    BenchmarkRegistry,
    BenchmarkReport,
)
from broker.validators.calibration.directional_validator import (
    DirectionalValidator,
    DirectionalTest,
    DirectionalTestResult,
    DirectionalReport,
    SwapTest,
    chi_squared_test,
    mann_whitney_u,
)
from broker.validators.calibration.calibration_protocol import (
    CalibrationProtocol,
    CalibrationConfig,
    CalibrationReport,
    CalibrationStage,
    StageVerdict,
    AdjustmentRecommendation,
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
]
