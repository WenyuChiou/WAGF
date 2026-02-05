"""
Validation Metrics Computation for Paper 3

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
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import Counter
import math

# Setup paths
SCRIPT_DIR = Path(__file__).parent
FLOOD_DIR = SCRIPT_DIR.parent.parent
RESULTS_DIR = FLOOD_DIR / "paper3" / "results"
OUTPUT_DIR = RESULTS_DIR / "validation"

# Add project root
ROOT_DIR = FLOOD_DIR.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np
import pandas as pd


# =============================================================================
# PMT Coherence Rules
# =============================================================================

# Valid (TP, CP) → Action mappings per PMT theory
PMT_OWNER_RULES = {
    # High Threat + High Coping → Should act
    ("VH", "VH"): ["buy_insurance", "elevate", "buyout", "retrofit"],
    ("VH", "H"): ["buy_insurance", "elevate", "buyout", "retrofit"],
    ("H", "VH"): ["buy_insurance", "elevate", "buyout"],
    ("H", "H"): ["buy_insurance", "elevate", "buyout"],
    ("VH", "M"): ["buy_insurance", "elevate"],
    ("H", "M"): ["buy_insurance", "elevate"],

    # High Threat + Low Coping → Limited actions or fatalism
    ("VH", "L"): ["buy_insurance", "do_nothing"],  # Fatalism allowed
    ("VH", "VL"): ["do_nothing"],
    ("H", "L"): ["buy_insurance", "do_nothing"],
    ("H", "VL"): ["do_nothing"],

    # Moderate Threat
    ("M", "VH"): ["buy_insurance", "elevate", "buyout", "do_nothing"],
    ("M", "H"): ["buy_insurance", "elevate", "do_nothing"],
    ("M", "M"): ["buy_insurance", "do_nothing"],
    ("M", "L"): ["buy_insurance", "do_nothing"],
    ("M", "VL"): ["do_nothing"],

    # Low Threat → Inaction acceptable
    ("L", "VH"): ["buy_insurance", "do_nothing"],
    ("L", "H"): ["buy_insurance", "do_nothing"],
    ("L", "M"): ["do_nothing", "buy_insurance"],
    ("L", "L"): ["do_nothing"],
    ("L", "VL"): ["do_nothing"],
    ("VL", "VH"): ["do_nothing", "buy_insurance"],
    ("VL", "H"): ["do_nothing"],
    ("VL", "M"): ["do_nothing"],
    ("VL", "L"): ["do_nothing"],
    ("VL", "VL"): ["do_nothing"],
}

PMT_RENTER_RULES = {
    # Renters have fewer options (no elevate, different buyout = relocate)
    ("VH", "VH"): ["buy_insurance", "relocate"],
    ("VH", "H"): ["buy_insurance", "relocate"],
    ("H", "VH"): ["buy_insurance", "relocate"],
    ("H", "H"): ["buy_insurance", "relocate"],
    ("VH", "M"): ["buy_insurance"],
    ("H", "M"): ["buy_insurance"],
    ("VH", "L"): ["buy_insurance", "do_nothing"],
    ("VH", "VL"): ["do_nothing"],
    ("H", "L"): ["buy_insurance", "do_nothing"],
    ("H", "VL"): ["do_nothing"],
    ("M", "VH"): ["buy_insurance", "relocate", "do_nothing"],
    ("M", "H"): ["buy_insurance", "do_nothing"],
    ("M", "M"): ["buy_insurance", "do_nothing"],
    ("M", "L"): ["do_nothing", "buy_insurance"],
    ("M", "VL"): ["do_nothing"],
    ("L", "VH"): ["do_nothing", "buy_insurance"],
    ("L", "H"): ["do_nothing"],
    ("L", "M"): ["do_nothing"],
    ("L", "L"): ["do_nothing"],
    ("L", "VL"): ["do_nothing"],
    ("VL", "VH"): ["do_nothing"],
    ("VL", "H"): ["do_nothing"],
    ("VL", "M"): ["do_nothing"],
    ("VL", "L"): ["do_nothing"],
    ("VL", "VL"): ["do_nothing"],
}


# =============================================================================
# Empirical Benchmarks
# =============================================================================

EMPIRICAL_BENCHMARKS = {
    "insurance_rate_sfha": {
        "range": (0.30, 0.50),
        "weight": 1.0,
        "description": "Insurance uptake rate in SFHA zones",
    },
    "insurance_rate_all": {
        "range": (0.15, 0.40),
        "weight": 0.8,
        "description": "Overall insurance uptake rate",
    },
    "elevation_rate": {
        "range": (0.03, 0.12),
        "weight": 1.0,
        "description": "Cumulative elevation rate",
    },
    "buyout_rate": {
        "range": (0.02, 0.15),
        "weight": 0.8,
        "description": "Cumulative buyout/relocation rate",
    },
    "do_nothing_rate_postflood": {
        "range": (0.35, 0.65),
        "weight": 1.5,
        "description": "Inaction rate among recently flooded",
    },
    "mg_adaptation_gap": {
        "range": (0.10, 0.30),
        "weight": 2.0,
        "description": "Adaptation gap between MG and NMG",
    },
    "renter_uninsured_rate": {
        "range": (0.15, 0.40),
        "weight": 1.0,
        "description": "Uninsured rate among renters in flood zones",
    },
    "insurance_lapse_rate": {
        "range": (0.05, 0.15),
        "weight": 1.0,
        "description": "Annual insurance lapse rate",
    },
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class L1Metrics:
    """L1 Micro validation metrics."""
    cacr: float  # Construct-Action Coherence Rate
    r_h: float   # Hallucination Rate
    ebe: float   # Effective Behavioral Entropy
    total_decisions: int
    coherent_decisions: int
    hallucinations: int
    action_distribution: Dict[str, int]

    def passes_thresholds(self) -> Dict[str, bool]:
        return {
            "CACR": self.cacr >= 0.80,
            "R_H": self.r_h <= 0.10,
            "EBE": self.ebe > 0,
        }


@dataclass
class L2Metrics:
    """L2 Macro validation metrics."""
    epi: float  # Empirical Plausibility Index
    benchmark_results: Dict[str, Dict]
    benchmarks_in_range: int
    total_benchmarks: int

    def passes_threshold(self) -> bool:
        return self.epi >= 0.60


@dataclass
class ValidationReport:
    """Complete validation report."""
    l1: L1Metrics
    l2: L2Metrics
    traces_path: str
    seed: Optional[int]
    model: str
    pass_all: bool


# =============================================================================
# L1 Metric Computation
# =============================================================================

def compute_l1_metrics(traces: List[Dict], agent_type: str = "owner") -> L1Metrics:
    """
    Compute L1 micro-level validation metrics.

    Args:
        traces: List of decision trace dictionaries
        agent_type: "owner" or "renter"

    Returns:
        L1Metrics dataclass
    """
    rules = PMT_OWNER_RULES if agent_type == "owner" else PMT_RENTER_RULES

    total = len(traces)
    coherent = 0
    hallucinations = 0
    action_counts = Counter()

    for trace in traces:
        tp = trace.get("TP_LABEL", "M")
        cp = trace.get("CP_LABEL", "M")
        action = trace.get("approved_skill", trace.get("skill_proposal", "do_nothing"))

        # Normalize action name
        action = _normalize_action(action)
        action_counts[action] += 1

        # Check PMT coherence
        key = (tp, cp)
        if key in rules:
            if action in rules[key]:
                coherent += 1
        else:
            # Unknown combination - check if action is at least sensible
            if _is_sensible_action(tp, cp, action, agent_type):
                coherent += 1

        # Check for hallucinations
        if _is_hallucination(trace):
            hallucinations += 1

    # Compute CACR
    cacr = coherent / total if total > 0 else 0.0

    # Compute R_H
    r_h = hallucinations / total if total > 0 else 0.0

    # Compute EBE (Effective Behavioral Entropy)
    ebe = _compute_entropy(action_counts)

    return L1Metrics(
        cacr=round(cacr, 4),
        r_h=round(r_h, 4),
        ebe=round(ebe, 4),
        total_decisions=total,
        coherent_decisions=coherent,
        hallucinations=hallucinations,
        action_distribution=dict(action_counts),
    )


def _normalize_action(action: str) -> str:
    """Normalize action names to standard form."""
    action = action.lower().strip()

    # Map variations to standard names
    mappings = {
        "buy_insurance": ["buy_insurance", "purchase_insurance", "get_insurance", "insurance"],
        "elevate": ["elevate", "elevate_home", "home_elevation", "raise_home"],
        "buyout": ["buyout", "voluntary_buyout", "accept_buyout"],
        "relocate": ["relocate", "move", "relocation"],
        "retrofit": ["retrofit", "floodproof", "flood_retrofit"],
        "do_nothing": ["do_nothing", "no_action", "wait", "none"],
    }

    for standard, variants in mappings.items():
        if action in variants:
            return standard

    return action


def _is_sensible_action(tp: str, cp: str, action: str, agent_type: str) -> bool:
    """Check if action is sensible given TP/CP even if not in exact rule table."""
    tp_level = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}.get(tp, 3)
    cp_level = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}.get(cp, 3)

    # High threat should lead to some action
    if tp_level >= 4 and cp_level >= 3:
        return action != "do_nothing"

    # Low threat with inaction is sensible
    if tp_level <= 2:
        return True

    # Low coping limits complex actions
    if cp_level <= 2 and action in ["elevate", "buyout", "relocate"]:
        return False

    return True


def _is_hallucination(trace: Dict) -> bool:
    """Check if trace contains a hallucination (physically impossible action)."""
    action = trace.get("approved_skill", "")
    state_before = trace.get("state_before", {})

    # Already elevated and trying to elevate again
    if action == "elevate" and state_before.get("elevated", False):
        return True

    # Already bought out but still making decisions
    if state_before.get("bought_out", False) and action not in ["do_nothing"]:
        return True

    # Renter trying to elevate
    if "renter" in trace.get("agent_type", "") and action == "elevate":
        return True

    return False


def _compute_entropy(counts: Counter) -> float:
    """Compute Shannon entropy of action distribution."""
    total = sum(counts.values())
    if total == 0:
        return 0.0

    entropy = 0.0
    for count in counts.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)

    return entropy


# =============================================================================
# L2 Metric Computation
# =============================================================================

def compute_l2_metrics(
    traces: List[Dict],
    agent_profiles: pd.DataFrame,
) -> L2Metrics:
    """
    Compute L2 macro-level validation metrics.

    Args:
        traces: All decision traces
        agent_profiles: Agent profile DataFrame with mg, tenure, flood_zone

    Returns:
        L2Metrics dataclass
    """
    # Extract final states from last year of each agent
    final_states = _extract_final_states(traces)

    # Merge with agent profiles
    df = agent_profiles.copy()
    df["agent_id"] = df["agent_id"].astype(str)

    # Add final states
    for agent_id, state in final_states.items():
        mask = df["agent_id"] == agent_id
        if mask.any():
            for key, value in state.items():
                df.loc[mask, f"final_{key}"] = value

    # Compute each benchmark
    benchmark_results = {}
    in_range_count = 0
    total_weight = 0
    weighted_in_range = 0

    for name, config in EMPIRICAL_BENCHMARKS.items():
        value = _compute_benchmark(name, df, traces)
        low, high = config["range"]
        weight = config["weight"]

        is_in_range = low <= value <= high if value is not None else False

        benchmark_results[name] = {
            "value": round(value, 4) if value is not None else None,
            "range": config["range"],
            "in_range": is_in_range,
            "weight": weight,
            "description": config["description"],
        }

        if value is not None:
            total_weight += weight
            if is_in_range:
                in_range_count += 1
                weighted_in_range += weight

    # Compute EPI (weighted proportion in range)
    epi = weighted_in_range / total_weight if total_weight > 0 else 0.0

    return L2Metrics(
        epi=round(epi, 4),
        benchmark_results=benchmark_results,
        benchmarks_in_range=in_range_count,
        total_benchmarks=len(EMPIRICAL_BENCHMARKS),
    )


def _extract_final_states(traces: List[Dict]) -> Dict[str, Dict]:
    """Extract final state for each agent from traces."""
    final_states = {}

    for trace in traces:
        agent_id = trace.get("agent_id", "")
        year = trace.get("year", 0)

        if agent_id not in final_states or year > final_states[agent_id].get("_year", 0):
            state = trace.get("state_after", {})
            state["_year"] = year
            final_states[agent_id] = state

    return final_states


def _compute_benchmark(name: str, df: pd.DataFrame, traces: List[Dict]) -> Optional[float]:
    """Compute a specific benchmark value."""
    try:
        if name == "insurance_rate_sfha":
            # Insurance rate in high-risk zones
            high_risk = df[df["flood_zone"] == "HIGH"]
            if len(high_risk) == 0:
                return None
            insured = high_risk["final_insured"].sum() if "final_insured" in high_risk.columns else 0
            return insured / len(high_risk)

        elif name == "insurance_rate_all":
            # Overall insurance rate
            if "final_insured" not in df.columns:
                return None
            return df["final_insured"].mean()

        elif name == "elevation_rate":
            # Elevation rate (owners only)
            owners = df[df["tenure"] == "Owner"]
            if len(owners) == 0 or "final_elevated" not in owners.columns:
                return None
            return owners["final_elevated"].mean()

        elif name == "buyout_rate":
            # Buyout/relocation rate
            if "final_bought_out" not in df.columns and "final_relocated" not in df.columns:
                return None
            buyout = df.get("final_bought_out", pd.Series([0]*len(df))).fillna(0)
            reloc = df.get("final_relocated", pd.Series([0]*len(df))).fillna(0)
            return (buyout | reloc).mean()

        elif name == "do_nothing_rate_postflood":
            # Inaction rate among flooded agents
            flooded_traces = [t for t in traces if t.get("flooded_this_year", False)]
            if len(flooded_traces) == 0:
                return None
            inaction = sum(1 for t in flooded_traces if t.get("approved_skill") == "do_nothing")
            return inaction / len(flooded_traces)

        elif name == "mg_adaptation_gap":
            # Gap between MG and NMG adaptation rates
            if "final_insured" not in df.columns:
                return None
            mg = df[df["mg"] == True]
            nmg = df[df["mg"] == False]
            if len(mg) == 0 or len(nmg) == 0:
                return None
            mg_rate = mg["final_insured"].mean()
            nmg_rate = nmg["final_insured"].mean()
            return abs(nmg_rate - mg_rate)

        elif name == "renter_uninsured_rate":
            # Uninsured rate among renters in flood zones
            renters_flood = df[(df["tenure"] == "Renter") & (df["flood_zone"] == "HIGH")]
            if len(renters_flood) == 0 or "final_insured" not in renters_flood.columns:
                return None
            return 1.0 - renters_flood["final_insured"].mean()

        elif name == "insurance_lapse_rate":
            # Annual lapse rate (insured → uninsured transitions)
            lapses = 0
            insured_periods = 0
            for trace in traces:
                state_before = trace.get("state_before", {})
                state_after = trace.get("state_after", {})
                if state_before.get("insured", False):
                    insured_periods += 1
                    if not state_after.get("insured", True):
                        lapses += 1
            return lapses / insured_periods if insured_periods > 0 else None

        return None
    except Exception as e:
        print(f"Warning: Could not compute {name}: {e}")
        return None


# =============================================================================
# Main Functions
# =============================================================================

def load_traces(traces_dir: Path) -> Tuple[List[Dict], List[Dict]]:
    """Load owner and renter traces from directory."""
    owner_traces = []
    renter_traces = []

    # Find trace files
    for pattern in ["**/household_owner_traces.jsonl", "**/owner_traces.jsonl"]:
        for filepath in traces_dir.glob(pattern):
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        owner_traces.append(json.loads(line))

    for pattern in ["**/household_renter_traces.jsonl", "**/renter_traces.jsonl"]:
        for filepath in traces_dir.glob(pattern):
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        renter_traces.append(json.loads(line))

    return owner_traces, renter_traces


def compute_validation(
    traces_dir: Path,
    agent_profiles_path: Path,
    output_dir: Path,
) -> ValidationReport:
    """
    Compute full validation report.

    Args:
        traces_dir: Directory containing trace JSONL files
        agent_profiles_path: Path to agent_profiles_balanced.csv
        output_dir: Directory for output files

    Returns:
        ValidationReport dataclass
    """
    print(f"Loading traces from: {traces_dir}")
    owner_traces, renter_traces = load_traces(traces_dir)
    all_traces = owner_traces + renter_traces

    print(f"  Owner traces: {len(owner_traces)}")
    print(f"  Renter traces: {len(renter_traces)}")
    print(f"  Total: {len(all_traces)}")

    if len(all_traces) == 0:
        raise ValueError(f"No traces found in {traces_dir}")

    # Load agent profiles
    print(f"Loading agent profiles from: {agent_profiles_path}")
    agent_profiles = pd.read_csv(agent_profiles_path)
    print(f"  Agents: {len(agent_profiles)}")

    # Compute L1 metrics (separate for owners and renters)
    print("\nComputing L1 metrics...")
    l1_owner = compute_l1_metrics(owner_traces, "owner")
    l1_renter = compute_l1_metrics(renter_traces, "renter")

    # Combined L1
    l1_combined = L1Metrics(
        cacr=round((l1_owner.cacr * len(owner_traces) + l1_renter.cacr * len(renter_traces)) / len(all_traces), 4),
        r_h=round((l1_owner.r_h * len(owner_traces) + l1_renter.r_h * len(renter_traces)) / len(all_traces), 4),
        ebe=round((l1_owner.ebe + l1_renter.ebe) / 2, 4),
        total_decisions=len(all_traces),
        coherent_decisions=l1_owner.coherent_decisions + l1_renter.coherent_decisions,
        hallucinations=l1_owner.hallucinations + l1_renter.hallucinations,
        action_distribution={**l1_owner.action_distribution, **l1_renter.action_distribution},
    )

    print(f"  CACR: {l1_combined.cacr} (threshold ≥0.80)")
    print(f"  R_H: {l1_combined.r_h} (threshold ≤0.10)")
    print(f"  EBE: {l1_combined.ebe} (threshold >0)")

    # Compute L2 metrics
    print("\nComputing L2 metrics...")
    l2 = compute_l2_metrics(all_traces, agent_profiles)

    print(f"  EPI: {l2.epi} (threshold ≥0.60)")
    print(f"  Benchmarks in range: {l2.benchmarks_in_range}/{l2.total_benchmarks}")

    # Extract metadata
    seed = None
    model = "unknown"
    if "seed_" in str(traces_dir):
        try:
            seed = int(str(traces_dir).split("seed_")[1].split("/")[0].split("\\")[0])
        except:
            pass

    # Check overall pass
    l1_pass = all(l1_combined.passes_thresholds().values())
    l2_pass = l2.passes_threshold()

    report = ValidationReport(
        l1=l1_combined,
        l2=l2,
        traces_path=str(traces_dir),
        seed=seed,
        model=model,
        pass_all=l1_pass and l2_pass,
    )

    # Save outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON report
    report_path = output_dir / "validation_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump({
            "l1": asdict(l1_combined),
            "l2": asdict(l2),
            "traces_path": str(traces_dir),
            "seed": seed,
            "model": model,
            "pass_all": report.pass_all,
            "l1_pass": l1_pass,
            "l2_pass": l2_pass,
        }, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {report_path}")

    # Save L1 details
    l1_path = output_dir / "l1_micro_metrics.json"
    with open(l1_path, 'w', encoding='utf-8') as f:
        json.dump({
            "combined": asdict(l1_combined),
            "owner": asdict(l1_owner),
            "renter": asdict(l1_renter),
            "thresholds": {"CACR": ">=0.80", "R_H": "<=0.10", "EBE": ">0"},
            "pass": l1_combined.passes_thresholds(),
        }, f, indent=2, ensure_ascii=False)
    print(f"Saved: {l1_path}")

    # Save L2 details
    l2_path = output_dir / "l2_macro_metrics.json"
    with open(l2_path, 'w', encoding='utf-8') as f:
        json.dump({
            "epi": l2.epi,
            "benchmarks_in_range": l2.benchmarks_in_range,
            "total_benchmarks": l2.total_benchmarks,
            "benchmark_results": l2.benchmark_results,
            "pass": l2.passes_threshold(),
        }, f, indent=2, ensure_ascii=False)
    print(f"Saved: {l2_path}")

    # Save benchmark comparison CSV
    benchmark_df = pd.DataFrame([
        {
            "Benchmark": name,
            "Value": result["value"],
            "Range_Low": result["range"][0],
            "Range_High": result["range"][1],
            "In_Range": result["in_range"],
            "Weight": result["weight"],
        }
        for name, result in l2.benchmark_results.items()
    ])
    benchmark_path = output_dir / "benchmark_comparison.csv"
    benchmark_df.to_csv(benchmark_path, index=False)
    print(f"Saved: {benchmark_path}")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Compute L1/L2 validation metrics from experiment traces"
    )
    parser.add_argument(
        "--traces",
        type=str,
        required=True,
        help="Path to traces directory (e.g., paper3/results/paper3_primary/seed_42)",
    )
    parser.add_argument(
        "--profiles",
        type=str,
        default=None,
        help="Path to agent_profiles_balanced.csv (default: auto-detect)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory (default: paper3/results/validation)",
    )

    args = parser.parse_args()

    # Setup paths
    traces_dir = Path(args.traces)
    if not traces_dir.exists():
        print(f"Error: Traces directory not found: {traces_dir}")
        sys.exit(1)

    profiles_path = Path(args.profiles) if args.profiles else FLOOD_DIR / "data" / "agent_profiles_balanced.csv"
    if not profiles_path.exists():
        print(f"Error: Agent profiles not found: {profiles_path}")
        sys.exit(1)

    output_dir = Path(args.output) if args.output else OUTPUT_DIR

    print("=" * 60)
    print("Validation Metrics Computation")
    print("=" * 60)

    report = compute_validation(traces_dir, profiles_path, output_dir)

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"\nL1 Micro Metrics:")
    for metric, passed in report.l1.passes_thresholds().items():
        status = "PASS" if passed else "FAIL"
        print(f"  {metric}: {status}")

    print(f"\nL2 Macro Metrics:")
    print(f"  EPI: {'PASS' if report.l2.passes_threshold() else 'FAIL'}")

    print(f"\nOVERALL: {'PASS' if report.pass_all else 'FAIL'}")
    print(f"\nOutputs saved to: {output_dir}")


if __name__ == "__main__":
    main()
