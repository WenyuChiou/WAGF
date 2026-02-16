"""
C&V Validation Package — Modular validation framework for LLM-ABMs.

Public API:
    compute_validation()    — Full pipeline: traces dir → ValidationReport
    compute_l1_metrics()    — L1 micro metrics (CACR, R_H, EBE)
    compute_l2_metrics()    — L2 macro metrics (EPI + benchmarks)
    compute_cacr_decomposition() — CACR raw/final from audit CSVs
    load_traces()           — Load owner/renter traces from directory

Data classes:
    L1Metrics, L2Metrics, ValidationReport, CACRDecomposition
"""

from validation.engine import compute_validation, load_traces
from validation.metrics.l1_micro import (
    compute_l1_metrics,
    compute_cacr_decomposition,
    CACRDecomposition,
    L1Metrics,
)
from validation.metrics.l2_macro import compute_l2_metrics, L2Metrics
from validation.metrics.cgr import compute_cgr
from validation.metrics.bootstrap import bootstrap_ci, clustered_bootstrap_ci
from validation.metrics.null_model import (
    generate_null_traces,
    generate_frequency_matched_null_traces,
    compute_null_epi_distribution,
    compute_frequency_matched_null_distribution,
    epi_significance_test,
)
from validation.metrics.l2_macro import epi_weight_sensitivity
from validation.metrics.l0_audit import run_l0_audit, L0AuditReport
from validation.metrics.l4_meta import (
    wasserstein_categorical,
    cross_run_stability,
    empirical_distance,
    compute_l4_meta,
    L4MetaReport,
)
from validation.metrics.sycophancy import (
    build_probes,
    evaluate_sycophancy,
    SycophancyProbe,
    SycophancyReport,
)
from validation.reporting.report_builder import ValidationReport, _to_json_serializable
from validation.hallucinations.base import HallucinationChecker, NullHallucinationChecker
from validation.hallucinations.flood import FloodHallucinationChecker
from validation.grounding.base import GroundingStrategy
from validation.grounding.flood import FloodGroundingStrategy

__all__ = [
    # Engine
    "compute_validation",
    "load_traces",
    # L0
    "run_l0_audit",
    "L0AuditReport",
    # L1
    "compute_l1_metrics",
    "compute_cacr_decomposition",
    "compute_cgr",
    "L1Metrics",
    "CACRDecomposition",
    # L2
    "compute_l2_metrics",
    "epi_weight_sensitivity",
    "L2Metrics",
    # L4
    "wasserstein_categorical",
    "cross_run_stability",
    "empirical_distance",
    "compute_l4_meta",
    "L4MetaReport",
    # Bootstrap
    "bootstrap_ci",
    "clustered_bootstrap_ci",
    # Null model
    "generate_null_traces",
    "generate_frequency_matched_null_traces",
    "compute_null_epi_distribution",
    "compute_frequency_matched_null_distribution",
    "epi_significance_test",
    # Sycophancy
    "build_probes",
    "evaluate_sycophancy",
    "SycophancyProbe",
    "SycophancyReport",
    # Reporting
    "ValidationReport",
    "_to_json_serializable",
    # Protocols
    "HallucinationChecker",
    "NullHallucinationChecker",
    "FloodHallucinationChecker",
    "GroundingStrategy",
    "FloodGroundingStrategy",
]
