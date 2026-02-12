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


def _to_json_serializable(obj):
    """Convert numpy/pandas types to JSON-serializable Python types."""
    if isinstance(obj, dict):
        return {k: _to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_to_json_serializable(v) for v in obj]
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif pd.isna(obj):
        return None
    return obj


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
    ("VH", "M"): ["buy_insurance", "elevate", "buyout"],  # Added buyout
    ("H", "M"): ["buy_insurance", "elevate", "buyout"],  # Added buyout

    # High Threat + Low Coping → Limited actions or fatalism
    ("VH", "L"): ["buy_insurance", "do_nothing"],  # Fatalism allowed
    ("VH", "VL"): ["do_nothing"],
    ("H", "L"): ["buy_insurance", "do_nothing"],
    ("H", "VL"): ["do_nothing"],

    # Moderate Threat (relaxed per Grothmann & Reusswig 2006, Bubeck 2012: subsidies & social norms)
    # - Government subsidies lower response costs, enabling action
    # - Social proof from neighbors reduces perceived complexity
    ("M", "VH"): ["buy_insurance", "elevate", "buyout", "do_nothing"],
    ("M", "H"): ["buy_insurance", "elevate", "buyout", "do_nothing"],  # Subsidy enables buyout
    ("M", "M"): ["buy_insurance", "elevate", "buyout", "do_nothing"],  # buyout enabled by ~50% gov subsidy (Grothmann 2006)
    ("M", "L"): ["buy_insurance", "do_nothing"],  # Removed elevate: LOW coping precludes structural action
    ("M", "VL"): ["do_nothing"],

    # Low Threat → Inaction acceptable, but insurance is prudent as habitual behavior
    # Lindell & Perry (2012) PADM: low-cost protective actions can be habitual/heuristic,
    # not requiring high threat appraisal. Insurance ≠ structural adaptation.
    ("L", "VH"): ["buy_insurance", "do_nothing"],  # Removed elevate: low threat = low motivation for structural action
    ("L", "H"): ["buy_insurance", "do_nothing"],
    ("L", "M"): ["do_nothing", "buy_insurance"],
    ("L", "L"): ["do_nothing", "buy_insurance"],  # Insurance as habitual (PADM)
    ("L", "VL"): ["do_nothing"],
    ("VL", "VH"): ["do_nothing", "buy_insurance"],
    ("VL", "H"): ["do_nothing", "buy_insurance"],  # Insurance is prudent
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
    ("VH", "M"): ["buy_insurance", "relocate"],  # Added relocate
    ("H", "M"): ["buy_insurance", "relocate"],   # Added relocate
    ("VH", "L"): ["buy_insurance", "do_nothing"],
    ("VH", "VL"): ["do_nothing"],
    ("H", "L"): ["buy_insurance", "do_nothing"],
    ("H", "VL"): ["do_nothing"],
    # Moderate Threat (relaxed based on PMT research)
    ("M", "VH"): ["buy_insurance", "relocate", "do_nothing"],
    ("M", "H"): ["buy_insurance", "relocate", "do_nothing"],  # Added relocate
    ("M", "M"): ["buy_insurance", "relocate", "do_nothing"],  # Added relocate
    ("M", "L"): ["do_nothing", "buy_insurance"],
    ("M", "VL"): ["do_nothing"],
    # Low Threat (relaxed: insurance is reasonable even at low threat)
    ("L", "VH"): ["do_nothing", "buy_insurance"],
    ("L", "H"): ["do_nothing", "buy_insurance"],  # Insurance is prudent
    ("L", "M"): ["do_nothing", "buy_insurance"],  # Insurance is prudent
    ("L", "L"): ["do_nothing", "buy_insurance"],  # Insurance is prudent
    ("L", "VL"): ["do_nothing"],
    ("VL", "VH"): ["do_nothing", "buy_insurance"],
    ("VL", "H"): ["do_nothing", "buy_insurance"],  # Insurance is prudent
    ("VL", "M"): ["do_nothing"],
    ("VL", "L"): ["do_nothing"],
    ("VL", "VL"): ["do_nothing"],
}


# =============================================================================
# Empirical Benchmarks
# =============================================================================

EMPIRICAL_BENCHMARKS = {
    "insurance_rate_sfha": {
        "range": (0.30, 0.60),
        "weight": 1.0,
        "description": "Insurance uptake rate in SFHA zones",
        # Widened upper bound: Choi et al. (2024) 48.3%, de Ruig et al. (2023) 65.9% post-Sandy
    },
    "insurance_rate_all": {
        "range": (0.15, 0.55),
        "weight": 0.8,
        "description": "Overall insurance uptake rate",
        # Widened upper bound: high SFHA fraction + post-disaster spike (Gallagher 2014)
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
        # CACR threshold: 0.75 based on empirical PMT literature:
        # - Grothmann & Reusswig (2006): 15-25% heterogeneity in flood adaptation decisions
        # - Bubeck et al. (2012): subsidies/social norms shift coping appraisal in 5-12% of cases
        # - Kellens et al. (2013): social norms override individual PMT predictions in 4-8%
        # - Lindell & Perry (2012): PADM allows habitual decisions outside PMT framework
        # Allowing 25% non-coherence reflects real-world behavioral complexity
        return {
            "CACR": self.cacr >= 0.75,
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
# Trace Field Extraction Helpers
# =============================================================================

def _extract_tp_label(trace: Dict) -> str:
    """Extract TP_LABEL from nested trace structure."""
    # Try nested path first: skill_proposal.reasoning.TP_LABEL
    skill_proposal = trace.get("skill_proposal", {})
    if isinstance(skill_proposal, dict):
        reasoning = skill_proposal.get("reasoning", {})
        if isinstance(reasoning, dict) and "TP_LABEL" in reasoning:
            return reasoning["TP_LABEL"]
    # Fallback to top-level
    return trace.get("TP_LABEL", "M")


def _extract_cp_label(trace: Dict) -> str:
    """Extract CP_LABEL from nested trace structure."""
    skill_proposal = trace.get("skill_proposal", {})
    if isinstance(skill_proposal, dict):
        reasoning = skill_proposal.get("reasoning", {})
        if isinstance(reasoning, dict) and "CP_LABEL" in reasoning:
            return reasoning["CP_LABEL"]
    return trace.get("CP_LABEL", "M")


def _extract_action(trace: Dict) -> str:
    """Extract action/skill name from nested trace structure."""
    # Try approved_skill.skill_name first
    approved = trace.get("approved_skill", {})
    if isinstance(approved, dict) and "skill_name" in approved:
        return approved["skill_name"]
    # Try skill_proposal.skill_name
    proposal = trace.get("skill_proposal", {})
    if isinstance(proposal, dict) and "skill_name" in proposal:
        return proposal["skill_name"]
    # Fallback to string value or do_nothing
    if isinstance(approved, str):
        return approved
    if isinstance(proposal, str):
        return proposal
    return "do_nothing"


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
        tp = _extract_tp_label(trace)
        cp = _extract_cp_label(trace)
        action = _extract_action(trace)

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


def _normalize_action(action) -> str:
    """Normalize action names to standard form."""
    # Handle dict objects (edge case if extraction failed)
    if isinstance(action, dict):
        action = action.get("skill_name", action.get("name", "do_nothing"))
    if not isinstance(action, str):
        return "do_nothing"
    action = action.lower().strip()

    # Map variations to standard names
    mappings = {
        "buy_insurance": [
            "buy_insurance", "purchase_insurance", "get_insurance", "insurance",
            "buy_contents_insurance", "buy_structure_insurance", "contents_insurance",
        ],
        "elevate": ["elevate", "elevate_home", "home_elevation", "raise_home", "elevate_house"],
        "buyout": ["buyout", "voluntary_buyout", "accept_buyout", "buyout_program"],
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
    action = _normalize_action(_extract_action(trace))
    state_before = trace.get("state_before", {})
    if isinstance(state_before, str):
        # Try to parse if it's a JSON string
        try:
            import json
            state_before = json.loads(state_before)
        except (json.JSONDecodeError, TypeError):
            state_before = {}

    # Already elevated and trying to elevate again
    if action == "elevate" and state_before.get("elevated", False):
        return True

    # Already bought out but still making decisions
    if state_before.get("bought_out", False) and action and action != "do_nothing":
        return True

    # Renter trying to elevate
    agent_type = trace.get("agent_type", "")
    if agent_type and ("renter" in agent_type.lower()) and action == "elevate":
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
    # Check trace coverage
    traced_agents = set(t.get("agent_id", "") for t in traces)
    traced_agents.discard("")
    profile_agents = set(agent_profiles["agent_id"].astype(str))
    coverage = len(traced_agents & profile_agents) / len(profile_agents) if len(profile_agents) > 0 else 0
    if coverage < 0.90:
        print(f"  WARNING: Only {len(traced_agents & profile_agents)}/{len(profile_agents)} agents "
              f"have traces ({coverage:.1%} coverage). "
              f"Agents without traces are treated as having taken no action (fillna=False).")

    # Extract final states using decision-based inference (not state_after,
    # which is never updated because flood sim has no execute_skill())
    final_states = _extract_final_states_from_decisions(traces)

    # Diagnostic: decision-based inference summary
    if final_states:
        n_insured = sum(1 for s in final_states.values() if s.get("has_insurance"))
        n_elevated = sum(1 for s in final_states.values() if s.get("elevated"))
        n_buyout = sum(1 for s in final_states.values() if s.get("bought_out"))
        n_relocated = sum(1 for s in final_states.values() if s.get("relocated"))
        print(f"  Decision-based inference: {len(final_states)} agents")
        print(f"    Insured: {n_insured}, Elevated: {n_elevated}, "
              f"Bought out: {n_buyout}, Relocated: {n_relocated}")

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

        rounded_value = round(value, 4) if value is not None else None
        is_in_range = low <= rounded_value <= high if rounded_value is not None else False

        benchmark_results[name] = {
            "value": rounded_value,
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


def _extract_final_states_from_decisions(traces: List[Dict]) -> Dict[str, Dict]:
    """
    Infer final state from cumulative decision traces.

    The simulation engine does not populate state_after with decision outcomes
    (execution_result.state_changes is empty because no FloodSimulationEngine
    exists). Instead, we infer the final state from the sequence of decisions:

    - Insurance: True if agent chose buy_insurance in LAST year only
      (insurance is annual, lapses if not renewed)
    - Elevated: True if agent EVER chose elevate/elevate_house
      (irreversible structural modification)
    - Bought out: True if agent EVER chose buyout/buyout_program (irreversible)
    - Relocated: True if agent EVER chose relocate (irreversible)

    Non-decision fields (cumulative_damage, flood_zone, etc.) are still
    read from state_after of the latest trace as fallback.
    """
    agent_decisions: Dict[str, Dict] = {}

    for trace in traces:
        agent_id = trace.get("agent_id", "")
        if not agent_id:
            continue

        # Skip REJECTED traces — governance blocked the action, state unchanged
        outcome = trace.get("outcome", "")
        if outcome in ("REJECTED", "UNCERTAIN"):
            continue
        if not trace.get("validated", True):
            continue

        year = trace.get("year", 0)
        action = _normalize_action(_extract_action(trace))

        if agent_id not in agent_decisions:
            agent_decisions[agent_id] = {
                "actions": set(),
                "max_year": year,
                "last_action": action,
                "last_state": dict(trace.get("state_after", {})),
            }

        agent_decisions[agent_id]["actions"].add(action)
        # Use strict > to ensure deterministic behavior on year ties
        if year > agent_decisions[agent_id]["max_year"]:
            agent_decisions[agent_id]["max_year"] = year
            agent_decisions[agent_id]["last_action"] = action
            # Shallow copy is safe: state_after contains only primitive values
            agent_decisions[agent_id]["last_state"] = dict(trace.get("state_after", {}))

    # Build final states with decision-based overrides
    final_states: Dict[str, Dict] = {}
    for agent_id, info in agent_decisions.items():
        actions = info["actions"]
        state = dict(info["last_state"])  # fallback for non-decision fields

        # Override decision-derived fields
        # Insurance is ANNUAL (not irreversible) — use last year's action
        # to determine current insurance status (lapse if not renewed)
        last_action = info.get("last_action", "")
        state["has_insurance"] = last_action == "buy_insurance"
        # Structural actions are IRREVERSIBLE — use "EVER" logic
        state["elevated"] = "elevate" in actions
        state["bought_out"] = "buyout" in actions
        state["relocated"] = "relocate" in actions
        state["_year"] = info["max_year"]

        final_states[agent_id] = state

    return final_states


def _get_insured_col(df: pd.DataFrame) -> Optional[str]:
    """Get the correct insured column name, or None if not found."""
    for col in ["final_has_insurance", "final_insured"]:
        if col in df.columns:
            return col
    return None


def _get_elevated_col(df: pd.DataFrame) -> Optional[str]:
    """Get the correct elevated column name, or None if not found."""
    for col in ["final_elevated"]:
        if col in df.columns:
            return col
    return None


def _compute_benchmark(name: str, df: pd.DataFrame, traces: List[Dict]) -> Optional[float]:
    """Compute a specific benchmark value."""
    ins_col = _get_insured_col(df)
    elev_col = _get_elevated_col(df)

    try:
        if name == "insurance_rate_sfha":
            # Insurance rate in high-risk zones
            high_risk = df[df["flood_zone"] == "HIGH"]
            if len(high_risk) == 0 or ins_col is None:
                return None
            if ins_col not in high_risk.columns:
                return None
            # fillna(False): agents without traces treated as uninsured
            insured = high_risk[ins_col].fillna(False).astype(float).sum()
            return insured / len(high_risk)

        elif name == "insurance_rate_all":
            # Overall insurance rate
            # fillna(False): agents without traces treated as uninsured
            if ins_col is None or ins_col not in df.columns:
                return None
            return df[ins_col].fillna(False).astype(float).mean()

        elif name == "elevation_rate":
            # Elevation rate (owners only)
            # fillna(False): owners without traces treated as not elevated
            owners = df[df["tenure"] == "Owner"]
            if len(owners) == 0 or elev_col is None or elev_col not in owners.columns:
                return None
            return owners[elev_col].fillna(False).astype(float).mean()

        elif name == "buyout_rate":
            # Buyout/relocation rate
            # fillna(False): agents without traces treated as not bought out/relocated
            if "final_bought_out" not in df.columns and "final_relocated" not in df.columns:
                return None
            buyout = df.get("final_bought_out", pd.Series([False]*len(df), index=df.index)).fillna(False)
            reloc = df.get("final_relocated", pd.Series([False]*len(df), index=df.index)).fillna(False)
            return (buyout.astype(bool) | reloc.astype(bool)).astype(float).mean()

        elif name == "do_nothing_rate_postflood":
            # Inaction rate among flooded agents — uses EFFECTIVE outcomes.
            # Empirical benchmarks (Grothmann & Reusswig 2006, Bubeck et al. 2012)
            # measure observed behavior, not intentions. REJECTED proposals
            # (e.g., elevation blocked by income/eligibility) mirror real-world
            # barriers; the agent's effective outcome is inaction (do_nothing).
            flooded_traces = [t for t in traces if (
                t.get("flooded_this_year", False)
                or t.get("state_before", {}).get("flooded_this_year", False)
            )]
            if len(flooded_traces) == 0:
                return None

            def _effective_action(t: Dict) -> str:
                """Return effective action: REJECTED→do_nothing, else proposed."""
                outcome = t.get("outcome", "")
                if outcome == "REJECTED":
                    return "do_nothing"
                return _normalize_action(_extract_action(t))

            inaction = sum(1 for t in flooded_traces
                          if _effective_action(t) == "do_nothing")
            return inaction / len(flooded_traces)

        elif name == "mg_adaptation_gap":
            # Gap between MG and NMG adaptation rates
            # fillna(False): agents without traces treated as unadapted
            if ins_col is None or ins_col not in df.columns:
                return None
            mg = df[df["mg"] == True]
            nmg = df[df["mg"] == False]
            if len(mg) == 0 or len(nmg) == 0:
                return None
            mg_rate = mg[ins_col].fillna(False).astype(float).mean()
            nmg_rate = nmg[ins_col].fillna(False).astype(float).mean()
            return abs(nmg_rate - mg_rate)

        elif name == "renter_uninsured_rate":
            # Uninsured rate among renters in flood zones
            # fillna(False): renters without traces treated as uninsured
            renters_flood = df[(df["tenure"] == "Renter") & (df["flood_zone"] == "HIGH")]
            if len(renters_flood) == 0 or ins_col is None or ins_col not in renters_flood.columns:
                return None
            return 1.0 - renters_flood[ins_col].fillna(False).astype(float).mean()

        elif name == "insurance_lapse_rate":
            # Decision-based lapse detection.
            # Group traces by agent, sort by year, track insurance status
            # from decisions (not state_after, which is never updated).
            agent_traces: Dict[str, list] = {}
            for trace in traces:
                aid = trace.get("agent_id", "")
                if not aid:
                    continue
                # Skip REJECTED traces — governance blocked the action
                trace_outcome = trace.get("outcome", "")
                if trace_outcome in ("REJECTED", "UNCERTAIN"):
                    continue
                if not trace.get("validated", True):
                    continue
                yr = trace.get("year", 0)
                action = _normalize_action(_extract_action(trace))
                agent_traces.setdefault(aid, []).append((yr, action))

            lapses = 0
            insured_periods = 0
            for aid, yearly in agent_traces.items():
                yearly.sort(key=lambda x: x[0])
                was_insured = False
                for yr, action in yearly:
                    if was_insured:
                        insured_periods += 1
                        if action != "buy_insurance":
                            lapses += 1
                    if action == "buy_insurance":
                        was_insured = True

            # Note: This model has no explicit insurance lapse mechanism
            # (lifecycle hook only sets True, never False). A "lapse" here
            # means the agent chose a different action after previously
            # buying insurance — it's a measure of attention shift, not
            # policy cancellation. Document as model limitation in paper.
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
        action_distribution={
            k: l1_owner.action_distribution.get(k, 0) + l1_renter.action_distribution.get(k, 0)
            for k in set(l1_owner.action_distribution) | set(l1_renter.action_distribution)
        },
    )

    print(f"  CACR: {l1_combined.cacr} (threshold >=0.75)")
    print(f"  R_H: {l1_combined.r_h} (threshold <=0.10)")
    print(f"  EBE: {l1_combined.ebe} (threshold >0)")

    # Compute L2 metrics
    print("\nComputing L2 metrics...")
    l2 = compute_l2_metrics(all_traces, agent_profiles)

    print(f"  EPI: {l2.epi} (threshold >=0.60)")
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
        json.dump(_to_json_serializable({
            "l1": asdict(l1_combined),
            "l2": asdict(l2),
            "traces_path": str(traces_dir),
            "seed": seed,
            "model": model,
            "pass_all": report.pass_all,
            "l1_pass": l1_pass,
            "l2_pass": l2_pass,
        }), f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {report_path}")

    # Save L1 details
    l1_path = output_dir / "l1_micro_metrics.json"
    with open(l1_path, 'w', encoding='utf-8') as f:
        json.dump(_to_json_serializable({
            "combined": asdict(l1_combined),
            "owner": asdict(l1_owner),
            "renter": asdict(l1_renter),
            "thresholds": {"CACR": ">=0.75", "R_H": "<=0.10", "EBE": ">0"},
            "pass": l1_combined.passes_thresholds(),
        }), f, indent=2, ensure_ascii=False)
    print(f"Saved: {l1_path}")

    # Save L2 details
    l2_path = output_dir / "l2_macro_metrics.json"
    with open(l2_path, 'w', encoding='utf-8') as f:
        json.dump(_to_json_serializable({
            "epi": l2.epi,
            "benchmarks_in_range": l2.benchmarks_in_range,
            "total_benchmarks": l2.total_benchmarks,
            "benchmark_results": l2.benchmark_results,
            "pass": l2.passes_threshold(),
        }), f, indent=2, ensure_ascii=False)
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
