#!/usr/bin/env python3
"""
Example: How to use the C&V (Construct & Validation) Framework

This script demonstrates the three-level validation protocol using synthetic data,
showing how to:
  1. Compute L1 Micro metrics (CACR, R_H, EBE) from decision traces
  2. Compute L2 Macro metrics (EPI + 8 benchmarks) from traces + agent profiles
  3. Interpret results and adapt for other domains

Run:
    python example_cv_usage.py

No real experiment data is needed — synthetic traces are generated inline.
"""

import json
import math
import tempfile
from pathlib import Path
from collections import Counter
from typing import Dict, List

import numpy as np
import pandas as pd

# Import the C&V module (assumes running from paper3/analysis/)
from compute_validation_metrics import (
    compute_l1_metrics,
    compute_l2_metrics,
    compute_validation,
    L1Metrics,
    L2Metrics,
    PMT_OWNER_RULES,
    PMT_RENTER_RULES,
    EMPIRICAL_BENCHMARKS,
    _compute_entropy,
    _normalize_action,
)


# =============================================================================
# Example 1: L1 Micro Validation with Synthetic Traces
# =============================================================================

def example_l1_micro():
    """
    Compute L1 metrics (CACR, R_H, EBE) from hand-crafted traces.

    Each trace represents one agent decision in one year. The minimum fields are:
      - agent_id: unique agent identifier
      - year: simulation year
      - skill_proposal.skill_name: what the agent proposed
      - skill_proposal.reasoning.TP_LABEL: threat perception (VL/L/M/H/VH)
      - skill_proposal.reasoning.CP_LABEL: coping perception (VL/L/M/H/VH)
      - outcome: "APPROVED" or "REJECTED"
      - state_before: dict with physical state (elevated, bought_out, etc.)
    """
    print("=" * 60)
    print("Example 1: L1 Micro Validation")
    print("=" * 60)

    # --- Coherent traces (action matches PMT rules) ---
    # PMT_OWNER_RULES[(VH, VH)] includes: buy_insurance, elevate, buyout, retrofit
    coherent_traces = [
        {
            "agent_id": f"H{i:04d}",
            "year": 1,
            "outcome": "APPROVED",
            "skill_proposal": {
                "skill_name": "buy_insurance",
                "reasoning": {"TP_LABEL": "VH", "CP_LABEL": "VH"},
            },
            "approved_skill": {"skill_name": "buy_insurance"},
            "state_before": {"flood_zone": "HIGH", "elevated": False},
        }
        for i in range(1, 11)  # 10 coherent owner decisions
    ]

    # PMT_OWNER_RULES[(L, L)] includes: do_nothing, buy_insurance
    coherent_traces += [
        {
            "agent_id": f"H{i:04d}",
            "year": 1,
            "outcome": "APPROVED",
            "skill_proposal": {
                "skill_name": "do_nothing",
                "reasoning": {"TP_LABEL": "L", "CP_LABEL": "L"},
            },
            "approved_skill": {"skill_name": "do_nothing"},
            "state_before": {"flood_zone": "LOW", "elevated": False},
        }
        for i in range(11, 21)  # 10 coherent low-threat decisions
    ]

    # --- Incoherent trace (action violates PMT rules) ---
    # PMT_OWNER_RULES[(VL, VL)] = ["do_nothing"], but agent chose elevate
    incoherent_trace = {
        "agent_id": "H0021",
        "year": 1,
        "outcome": "APPROVED",
        "skill_proposal": {
            "skill_name": "elevate",
            "reasoning": {"TP_LABEL": "VL", "CP_LABEL": "VL"},
        },
        "approved_skill": {"skill_name": "elevate"},
        "state_before": {"flood_zone": "LOW", "elevated": False},
    }

    # --- Hallucination trace (physically impossible) ---
    # Already elevated but trying to elevate again
    hallucination_trace = {
        "agent_id": "H0022",
        "year": 2,
        "outcome": "APPROVED",
        "skill_proposal": {
            "skill_name": "elevate",
            "reasoning": {"TP_LABEL": "VH", "CP_LABEL": "VH"},
        },
        "approved_skill": {"skill_name": "elevate"},
        "state_before": {"flood_zone": "HIGH", "elevated": True},  # Already elevated!
    }

    # --- Trace with extraction failure ---
    # Missing TP/CP labels → defaults to UNKNOWN → excluded from CACR
    extraction_failure_trace = {
        "agent_id": "H0023",
        "year": 1,
        "outcome": "APPROVED",
        "skill_proposal": {
            "skill_name": "buy_insurance",
            "reasoning": {},  # No TP_LABEL or CP_LABEL
        },
        "approved_skill": {"skill_name": "buy_insurance"},
        "state_before": {"flood_zone": "HIGH", "elevated": False},
    }

    all_traces = coherent_traces + [incoherent_trace, hallucination_trace, extraction_failure_trace]

    # Compute L1 metrics
    l1 = compute_l1_metrics(all_traces, agent_type="owner")

    print(f"\nResults ({l1.total_decisions} decisions):")
    print(f"  CACR:      {l1.cacr:.4f}  (threshold >= 0.75)")
    print(f"  R_H:       {l1.r_h:.4f}  (threshold <= 0.10)")
    print(f"  EBE:       {l1.ebe:.4f}  (ratio={l1.ebe_ratio:.4f}, threshold 0.1 < ratio < 0.9)")
    print(f"  EBE_max:   {l1.ebe_max:.4f}  (log2({len(l1.action_distribution)}) actions)")
    print(f"  Actions:   {dict(l1.action_distribution)}")

    # Check pass/fail
    thresholds = l1.passes_thresholds()
    for metric, passed in thresholds.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {metric}: {status}")

    print(f"\nNote: 1 trace with UNKNOWN TP/CP was excluded from CACR denominator.")
    print(f"  CACR = {l1.coherent_decisions} coherent / "
          f"{l1.total_decisions - 1} eligible = {l1.cacr:.4f}")

    return l1


# =============================================================================
# Example 2: L2 Macro Validation with Synthetic Experiment
# =============================================================================

def example_l2_macro():
    """
    Compute L2 metrics (EPI + 8 benchmarks) from a synthetic 400-agent experiment.

    This requires:
      1. Decision traces (JSONL format) spanning multiple years
      2. Agent profiles (CSV) with agent_id, tenure, flood_zone, mg columns
    """
    print("\n" + "=" * 60)
    print("Example 2: L2 Macro Validation")
    print("=" * 60)

    rng = np.random.default_rng(42)

    # --- Create synthetic agent profiles (400 agents, balanced design) ---
    agents = []
    for i in range(1, 401):
        if i <= 100:
            tenure, mg = "Owner", True
        elif i <= 200:
            tenure, mg = "Owner", False
        elif i <= 300:
            tenure, mg = "Renter", True
        else:
            tenure, mg = "Renter", False

        flood_zone = rng.choice(["HIGH", "MEDIUM", "LOW"],
                                p=[0.4, 0.3, 0.3] if mg else [0.25, 0.35, 0.4])
        agents.append({
            "agent_id": f"H{i:04d}",
            "tenure": tenure,
            "flood_zone": flood_zone,
            "mg": mg,
        })
    profiles = pd.DataFrame(agents)

    # --- Generate synthetic traces (13 years × 400 agents) ---
    traces = []
    # Track cumulative state per agent
    agent_state = {f"H{i:04d}": {"insured": False, "elevated": False,
                                   "bought_out": False, "relocated": False}
                   for i in range(1, 401)}

    for year in range(1, 14):
        for agent in agents:
            aid = agent["agent_id"]
            state = agent_state[aid]

            # Skip agents who already left
            if state["bought_out"] or state["relocated"]:
                continue

            is_owner = agent["tenure"] == "Owner"
            is_sfha = agent["flood_zone"] in ("HIGH", "MEDIUM")
            is_mg = agent["mg"]
            flooded = is_sfha and rng.random() < 0.15  # ~15% annual flood prob in SFHA

            # Simulate PMT-based decision with realistic probabilities
            if is_owner:
                tp = "VH" if flooded else ("H" if is_sfha else "L")
                cp = rng.choice(["VH", "H", "M", "L"],
                                p=[0.3, 0.3, 0.3, 0.1] if not is_mg else [0.1, 0.2, 0.4, 0.3])

                # Choose action based on PMT logic
                if tp in ("VH", "H") and cp in ("VH", "H"):
                    if not state["elevated"] and rng.random() < 0.08:
                        action = "elevate"
                    elif rng.random() < 0.05:
                        action = "buyout"
                    elif rng.random() < 0.5:
                        action = "buy_insurance"
                    else:
                        action = "do_nothing"
                elif tp in ("VH", "H") and cp in ("L", "VL"):
                    action = "do_nothing"  # fatalism
                else:
                    action = rng.choice(["buy_insurance", "do_nothing"],
                                        p=[0.4, 0.6] if is_sfha else [0.2, 0.8])
            else:
                # Renter
                tp = "H" if flooded else ("M" if is_sfha else "L")
                cp = rng.choice(["VH", "H", "M", "L"],
                                p=[0.2, 0.3, 0.3, 0.2] if not is_mg else [0.1, 0.1, 0.4, 0.4])

                if tp in ("VH", "H") and cp in ("VH", "H"):
                    action = rng.choice(["buy_insurance", "relocate"], p=[0.7, 0.3])
                elif rng.random() < 0.3:
                    action = "buy_insurance"
                else:
                    action = "do_nothing"

            # Update state
            if action == "elevate":
                state["elevated"] = True
            elif action == "buyout":
                state["bought_out"] = True
            elif action == "relocate":
                state["relocated"] = True
            elif action == "buy_insurance":
                # Insurance can lapse (20% annual lapse)
                state["insured"] = True
            elif action == "do_nothing" and state["insured"]:
                if rng.random() < 0.20:
                    state["insured"] = False  # lapse

            traces.append({
                "agent_id": aid,
                "year": year,
                "outcome": "APPROVED",
                "skill_proposal": {
                    "skill_name": action,
                    "reasoning": {"TP_LABEL": tp, "CP_LABEL": cp},
                },
                "approved_skill": {"skill_name": action},
                "state_before": {
                    "flood_zone": agent["flood_zone"],
                    "elevated": state["elevated"],
                    "bought_out": state["bought_out"],
                },
                "flooded_this_year": flooded,
            })

    print(f"Generated {len(traces)} traces ({len(agents)} agents × 13 years)")

    # Compute L2 metrics
    l2 = compute_l2_metrics(traces, profiles)

    print(f"\nEPI: {l2.epi:.4f}  (threshold >= 0.60)")
    print(f"Benchmarks in range: {l2.benchmarks_in_range}/{l2.total_benchmarks}")
    print(f"\nBenchmark Details:")
    for name, result in l2.benchmark_results.items():
        status = "PASS" if result["in_range"] else "FAIL"
        low, high = EMPIRICAL_BENCHMARKS[name]["range"]
        print(f"  {name:30s}: {result['value']:.4f}  [{low:.2f}, {high:.2f}]  {status}")

    overall = "PASS" if l2.passes_threshold() else "FAIL"
    print(f"\nOverall L2: {overall}")

    return l2


# =============================================================================
# Example 3: Full Pipeline (traces dir → validation report JSON)
# =============================================================================

def example_full_pipeline():
    """
    Demonstrate the end-to-end pipeline: write traces to files, run compute_validation(),
    and get a full ValidationReport.

    This mirrors the actual production usage:
        python compute_validation_metrics.py --traces <dir> --profiles <csv>
    """
    print("\n" + "=" * 60)
    print("Example 3: Full Pipeline (File I/O)")
    print("=" * 60)

    rng = np.random.default_rng(99)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        traces_dir = tmpdir / "seed_42" / "gemma3_4b" / "raw"
        traces_dir.mkdir(parents=True)

        # --- Write agent profiles CSV ---
        profiles_path = tmpdir / "agent_profiles_balanced.csv"
        agents = []
        for i in range(1, 51):
            tenure = "Owner" if i <= 25 else "Renter"
            mg = i % 3 == 0
            fz = rng.choice(["HIGH", "MEDIUM", "LOW"])
            agents.append({"agent_id": f"H{i:04d}", "tenure": tenure,
                           "flood_zone": fz, "mg": mg})
        pd.DataFrame(agents).to_csv(profiles_path, index=False)

        # --- Write owner traces JSONL ---
        owner_traces = []
        for year in range(1, 4):
            for i in range(1, 26):
                tp = rng.choice(["VH", "H", "M", "L"])
                cp = rng.choice(["VH", "H", "M", "L"])
                action = rng.choice(["buy_insurance", "elevate", "do_nothing"],
                                    p=[0.4, 0.1, 0.5])
                owner_traces.append({
                    "agent_id": f"H{i:04d}", "year": year,
                    "outcome": "APPROVED",
                    "skill_proposal": {"skill_name": action,
                                       "reasoning": {"TP_LABEL": tp, "CP_LABEL": cp}},
                    "approved_skill": {"skill_name": action},
                    "state_before": {"flood_zone": agents[i-1]["flood_zone"],
                                     "elevated": False},
                    "flooded_this_year": rng.random() < 0.2,
                })

        with open(traces_dir / "household_owner_traces.jsonl", 'w', encoding='utf-8') as f:
            for t in owner_traces:
                f.write(json.dumps(t) + "\n")

        # --- Write renter traces JSONL ---
        renter_traces = []
        for year in range(1, 4):
            for i in range(26, 51):
                tp = rng.choice(["H", "M", "L"])
                cp = rng.choice(["H", "M", "L"])
                action = rng.choice(["buy_insurance", "do_nothing", "relocate"],
                                    p=[0.3, 0.6, 0.1])
                renter_traces.append({
                    "agent_id": f"H{i:04d}", "year": year,
                    "outcome": "APPROVED",
                    "skill_proposal": {"skill_name": action,
                                       "reasoning": {"TP_LABEL": tp, "CP_LABEL": cp}},
                    "approved_skill": {"skill_name": action},
                    "state_before": {"flood_zone": agents[i-1]["flood_zone"],
                                     "elevated": False},
                    "flooded_this_year": rng.random() < 0.2,
                })

        with open(traces_dir / "household_renter_traces.jsonl", 'w', encoding='utf-8') as f:
            for t in renter_traces:
                f.write(json.dumps(t) + "\n")

        # --- Run full validation pipeline ---
        output_dir = tmpdir / "validation"
        output_dir.mkdir()

        report = compute_validation(
            traces_dir=tmpdir / "seed_42",
            agent_profiles_path=profiles_path,
            output_dir=output_dir,
        )

        print(f"\nValidation Report:")
        print(f"  L1 CACR:     {report.l1.cacr:.4f}")
        print(f"  L1 R_H:      {report.l1.r_h:.4f}")
        print(f"  L1 EBE:      {report.l1.ebe:.4f} (ratio={report.l1.ebe_ratio:.4f})")
        print(f"  L2 EPI:      {report.l2.epi:.4f}")
        print(f"  Overall:     {'PASS' if report.pass_all else 'FAIL'}")

        # Show output files
        print(f"\nOutput files written to: {output_dir}")
        for f in sorted(output_dir.glob("*")):
            print(f"  {f.name}")

    return report


# =============================================================================
# Example 4: Adapting for a New Domain (Irrigation)
# =============================================================================

def example_domain_adaptation():
    """
    Show how to adapt the C&V framework for a different domain.

    This example uses irrigation water management with WSA/ACA constructs
    instead of PMT's TP/CP. It demonstrates the three components you need
    to define for any new domain:
      1. Construct-action coherence rules (like PMT_OWNER_RULES)
      2. Empirical benchmarks (like EMPIRICAL_BENCHMARKS)
      3. Hallucination rules (like _is_hallucination)
    """
    print("\n" + "=" * 60)
    print("Example 4: Domain Adaptation (Irrigation)")
    print("=" * 60)

    # --- Step 1: Define construct-action rules ---
    # WSA = Water Scarcity Awareness, ACA = Adaptive Capacity Assessment
    IRRIGATION_RULES = {
        ("VH", "VH"): ["decrease_large", "decrease_small"],
        ("VH", "H"):  ["decrease_large", "decrease_small"],
        ("VH", "M"):  ["decrease_small", "maintain_demand"],
        ("VH", "L"):  ["maintain_demand", "decrease_small"],
        ("VH", "VL"): ["maintain_demand"],
        ("H", "VH"):  ["decrease_small", "decrease_large"],
        ("H", "H"):   ["decrease_small", "maintain_demand"],
        ("H", "M"):   ["decrease_small", "maintain_demand"],
        ("H", "L"):   ["maintain_demand"],
        ("H", "VL"):  ["maintain_demand"],
        ("M", "VH"):  ["maintain_demand", "increase_small", "decrease_small"],
        ("M", "H"):   ["maintain_demand", "increase_small"],
        ("M", "M"):   ["maintain_demand"],
        ("M", "L"):   ["maintain_demand"],
        ("M", "VL"):  ["maintain_demand"],
        ("L", "VH"):  ["increase_small", "increase_large", "maintain_demand"],
        ("L", "H"):   ["increase_small", "maintain_demand"],
        ("L", "M"):   ["maintain_demand", "increase_small"],
        ("L", "L"):   ["maintain_demand"],
        ("L", "VL"):  ["maintain_demand"],
        ("VL", "VH"): ["increase_large", "increase_small"],
        ("VL", "H"):  ["increase_large", "increase_small"],
        ("VL", "M"):  ["increase_small", "maintain_demand"],
        ("VL", "L"):  ["maintain_demand"],
        ("VL", "VL"): ["maintain_demand"],
    }

    # --- Step 2: Define empirical benchmarks ---
    IRRIGATION_BENCHMARKS = {
        "deficit_irrigation_rate": {
            "range": (0.20, 0.45),
            "weight": 1.0,
            "description": "Fraction of farmers adopting deficit irrigation",
        },
        "technology_adoption_rate": {
            "range": (0.05, 0.20),
            "weight": 1.0,
            "description": "Fraction adopting drip/sprinkler irrigation",
        },
        "demand_reduction_drought": {
            "range": (0.10, 0.30),
            "weight": 1.5,
            "description": "Aggregate demand reduction during drought years",
        },
    }

    # --- Step 3: Define hallucination rules ---
    def is_irrigation_hallucination(trace):
        action = trace.get("action", "maintain_demand")
        state = trace.get("state_before", {})
        # Bankrupt farmer cannot invest
        if state.get("bankrupt") and action in ("increase_large", "decrease_large"):
            return True
        # At allocation cap → cannot increase
        if state.get("at_allocation_cap") and action in ("increase_large", "increase_small"):
            return True
        return False

    # --- Compute CACR manually ---
    rng = np.random.default_rng(42)
    traces = []
    for i in range(200):
        wsa = rng.choice(["VH", "H", "M", "L", "VL"])
        aca = rng.choice(["VH", "H", "M", "L", "VL"])
        allowed = IRRIGATION_RULES.get((wsa, aca), ["maintain_demand"])
        # 85% of the time, choose a coherent action
        if rng.random() < 0.85:
            action = rng.choice(allowed)
        else:
            action = rng.choice(["increase_large", "decrease_large", "maintain_demand"])
        traces.append({"wsa": wsa, "aca": aca, "action": action,
                        "state_before": {}})

    # Manual CACR computation
    coherent = sum(1 for t in traces
                   if t["action"] in IRRIGATION_RULES.get((t["wsa"], t["aca"]), []))
    cacr = coherent / len(traces)

    # Manual EBE computation
    action_counts = Counter(t["action"] for t in traces)
    ebe = _compute_entropy(action_counts)
    k = len(action_counts)
    ebe_max = math.log2(k) if k > 1 else 0.0
    ebe_ratio = ebe / ebe_max if ebe_max > 0 else 0.0

    # Hallucination rate
    n_halluc = sum(1 for t in traces if is_irrigation_hallucination(t))
    r_h = n_halluc / len(traces)

    print(f"\nIrrigation C&V Results ({len(traces)} decisions):")
    print(f"  CACR:      {cacr:.4f}  (threshold >= 0.75)")
    print(f"  R_H:       {r_h:.4f}  (threshold <= 0.10)")
    print(f"  EBE:       {ebe:.4f}  (ratio={ebe_ratio:.4f})")
    print(f"  Actions:   {dict(action_counts)}")
    print(f"\nTo use in production, replace PMT_OWNER_RULES with IRRIGATION_RULES")
    print(f"in compute_validation_metrics.py and update EMPIRICAL_BENCHMARKS.")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print("C&V Framework Usage Examples")
    print("Demonstrates the three-level validation protocol for LLM-ABMs\n")

    # Run all examples
    l1 = example_l1_micro()
    l2 = example_l2_macro()
    report = example_full_pipeline()
    example_domain_adaptation()

    print("\n" + "=" * 60)
    print("All examples complete.")
    print("=" * 60)
    print("\nFor production usage:")
    print("  python compute_validation_metrics.py \\")
    print("    --traces ../results/main_400x13_seed42 \\")
    print("    --profiles ../../data/agent_profiles_balanced.csv")
