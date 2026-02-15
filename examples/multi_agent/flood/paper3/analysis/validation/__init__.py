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
from validation.metrics.bootstrap import bootstrap_ci
from validation.metrics.null_model import (
    generate_null_traces,
    compute_null_epi_distribution,
    epi_significance_test,
)
from validation.reporting.report_builder import ValidationReport, _to_json_serializable
from validation.hallucinations.base import HallucinationChecker, NullHallucinationChecker
from validation.hallucinations.flood import FloodHallucinationChecker
from validation.grounding.base import GroundingStrategy
from validation.grounding.flood import FloodGroundingStrategy

__all__ = [
    "compute_validation",
    "load_traces",
    "compute_l1_metrics",
    "compute_l2_metrics",
    "compute_cacr_decomposition",
    "compute_cgr",
    "bootstrap_ci",
    "generate_null_traces",
    "compute_null_epi_distribution",
    "epi_significance_test",
    "L1Metrics",
    "L2Metrics",
    "CACRDecomposition",
    "ValidationReport",
    "_to_json_serializable",
    "HallucinationChecker",
    "NullHallucinationChecker",
    "FloodHallucinationChecker",
    "GroundingStrategy",
    "FloodGroundingStrategy",
]
