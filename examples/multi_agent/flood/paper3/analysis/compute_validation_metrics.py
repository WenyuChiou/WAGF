"""
Validation Metrics Computation for Paper 3

Backward-compatibility wrapper. All logic has been moved to the validation/ package.

Computes L1 Micro and L2 Macro validation metrics from experiment traces.

L1 Micro Metrics (per-decision):
- CACR: Construct-Action Coherence Rate (TP/CP labels match action per PMT)
- R_H: Hallucination Rate (physically impossible actions)
- EBE: Effective Behavioral Entropy (decision diversity)

L2 Macro Metrics (aggregate):
- EPI: Empirical Plausibility Index (benchmarks within range)
- 8 empirical benchmarks comparison

Usage:
    python compute_validation_metrics.py --traces paper3/results/paper3_primary/seed_42
    python compute_validation_metrics.py --traces paper3/results/paper3_primary --all-seeds
"""

import sys
from pathlib import Path

# Setup paths (needed by CLI and external scripts)
SCRIPT_DIR = Path(__file__).parent
FLOOD_DIR = SCRIPT_DIR.parent.parent
RESULTS_DIR = FLOOD_DIR / "paper3" / "results"
OUTPUT_DIR = RESULTS_DIR / "validation"

# Add project root to sys.path
ROOT_DIR = FLOOD_DIR.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Add analysis dir for validation package resolution
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# =============================================================================
# Re-export everything from validation/ package for backward compatibility
# =============================================================================

# Core pipeline
from validation.engine import compute_validation, load_traces

# L1 metrics
from validation.metrics.l1_micro import (
    compute_l1_metrics,
    compute_cacr_decomposition,
    CACRDecomposition,
    L1Metrics,
)

# L2 metrics
from validation.metrics.l2_macro import compute_l2_metrics, L2Metrics

# Reporting
from validation.reporting.report_builder import ValidationReport, _to_json_serializable
from validation.reporting.cli import main

# PMT theory rules
from validation.theories.pmt import (
    PMT_OWNER_RULES,
    PMT_RENTER_RULES,
    _is_sensible_action,
)

# Benchmarks
from validation.benchmarks.flood import EMPIRICAL_BENCHMARKS, _compute_benchmark

# IO utilities
from validation.io.trace_reader import (
    _extract_tp_label,
    _extract_cp_label,
    _extract_action,
    _normalize_action,
)
from validation.io.state_inference import (
    _extract_final_states,
    _extract_final_states_from_decisions,
)

# CGR
from validation.metrics.cgr import compute_cgr

# Bootstrap CIs
from validation.metrics.bootstrap import bootstrap_ci

# Null model
from validation.metrics.null_model import (
    generate_null_traces,
    compute_null_epi_distribution,
    epi_significance_test,
)

# Entropy
from validation.metrics.entropy import _compute_entropy

# Hallucinations
from validation.hallucinations.flood import _is_hallucination


if __name__ == "__main__":
    main()
