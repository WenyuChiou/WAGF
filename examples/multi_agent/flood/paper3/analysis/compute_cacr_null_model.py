#!/usr/bin/env python3
"""
Compute CACR Null Model for Flood Domain
=========================================

Calculates the expected Construct-Action Coherence Rate (CACR) under
uniform random action selection, given the PMT matrix structure.

For each (TP, CP) cell in the 5×5 PMT matrix:
    P(coherent | random) = (# coherent actions) / (# total actions)

Null CACR = weighted average across all cells.

Usage:
    python compute_cacr_null_model.py
"""

import sys
from pathlib import Path

# Add validation package to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

import numpy as np
from validation.theories.pmt import PMT_OWNER_RULES, PMT_RENTER_RULES


def compute_null_cacr(rules_dict, n_total_actions, agent_type="owner"):
    """Compute null CACR for a single agent type."""
    tp_levels = ["VL", "L", "M", "H", "VH"]
    cp_levels = ["VL", "L", "M", "H", "VH"]

    coherence_rates = []
    cell_details = []

    for tp in tp_levels:
        for cp in cp_levels:
            coherent_actions = rules_dict.get((tp, cp), [])
            n_coherent = len(coherent_actions)
            p_coherent = n_coherent / n_total_actions
            coherence_rates.append(p_coherent)

            cell_details.append({
                "TP": tp,
                "CP": cp,
                "n_coherent": n_coherent,
                "n_total": n_total_actions,
                "p_coherent": p_coherent,
                "actions": coherent_actions,
            })

    null_mean = np.mean(coherence_rates)
    null_std = np.std(coherence_rates)
    null_min = np.min(coherence_rates)
    null_max = np.max(coherence_rates)

    return {
        "agent_type": agent_type,
        "n_cells": len(coherence_rates),
        "null_cacr_mean": null_mean,
        "null_cacr_std": null_std,
        "null_cacr_min": null_min,
        "null_cacr_max": null_max,
        "cell_details": cell_details,
    }


def main():
    print("=" * 80)
    print("FLOOD CACR NULL MODEL COMPUTATION")
    print("=" * 80)

    # Owner actions
    owner_actions = ["do_nothing", "buy_insurance", "elevate", "buyout", "retrofit"]
    owner_result = compute_null_cacr(PMT_OWNER_RULES, len(owner_actions), "owner")

    # Renter actions
    renter_actions = ["do_nothing", "buy_insurance", "relocate"]
    renter_result = compute_null_cacr(PMT_RENTER_RULES, len(renter_actions), "renter")

    print(f"\n1. OWNER NULL MODEL")
    print(f"   Total action pool: {len(owner_actions)} actions")
    print(f"   PMT cells: {owner_result['n_cells']} (5 TP × 5 CP)")
    print(f"   Null CACR (uniform random selection):")
    print(f"     Mean:  {owner_result['null_cacr_mean']:.1%}")
    print(f"     SD:    {owner_result['null_cacr_std']:.1%}")
    print(f"     Range: [{owner_result['null_cacr_min']:.1%}, {owner_result['null_cacr_max']:.1%}]")

    print(f"\n2. RENTER NULL MODEL")
    print(f"   Total action pool: {len(renter_actions)} actions")
    print(f"   PMT cells: {renter_result['n_cells']} (5 TP × 5 CP)")
    print(f"   Null CACR (uniform random selection):")
    print(f"     Mean:  {renter_result['null_cacr_mean']:.1%}")
    print(f"     SD:    {renter_result['null_cacr_std']:.1%}")
    print(f"     Range: [{renter_result['null_cacr_min']:.1%}, {renter_result['null_cacr_max']:.1%}]")

    # Combined null model (weighted by agent type frequency)
    # NOTE: Replace with actual proportions from experiment if needed
    # For now, assume 70% owners, 30% renters (typical US flood-prone areas)
    p_owner = 0.70
    p_renter = 0.30

    combined_null = (
        p_owner * owner_result['null_cacr_mean'] +
        p_renter * renter_result['null_cacr_mean']
    )

    print(f"\n3. COMBINED NULL MODEL (weighted)")
    print(f"   Assumed proportions: {p_owner:.0%} owners, {p_renter:.0%} renters")
    print(f"   Weighted null CACR: {combined_null:.1%}")

    # Cell-by-cell breakdown for supplement
    print(f"\n4. CELL-LEVEL BREAKDOWN (Owner PMT Matrix)")
    print(f"   {'TP':>3s}  {'CP':>3s}  {'#Coherent':>10s}  {'#Total':>7s}  {'P(coherent)':>12s}  Actions")
    print(f"   {'-'*3}  {'-'*3}  {'-'*10}  {'-'*7}  {'-'*12}  {'-'*40}")

    for cell in owner_result['cell_details']:
        actions_str = ', '.join(cell['actions']) if cell['actions'] else "NONE"
        if len(actions_str) > 40:
            actions_str = actions_str[:37] + "..."
        print(f"   {cell['TP']:>3s}  {cell['CP']:>3s}  {cell['n_coherent']:>10d}  "
              f"{cell['n_total']:>7d}  {cell['p_coherent']:>12.1%}  {actions_str}")

    print(f"\n5. INTERPRETATION")
    print(f"   • Random owner agent: {owner_result['null_cacr_mean']:.1%} coherent by chance")
    print(f"   • Random renter agent: {renter_result['null_cacr_mean']:.1%} coherent by chance")
    print(f"   • Combined null baseline: {combined_null:.1%}")
    print(f"\n   USAGE IN PAPER:")
    print(f"   'Under uniform random action selection, the expected CACR is")
    print(f"   {combined_null:.1%} (owners: {owner_result['null_cacr_mean']:.1%}, "
          f"renters: {renter_result['null_cacr_mean']:.1%}).")
    print(f"   Observed CACR values significantly above this baseline indicate")
    print(f"   construct-driven decision-making; values near this baseline suggest")
    print(f"   governance restores coherence without prescriptive bias.'")

    print("\n" + "=" * 80)
    print("EXPORT: Save results for validation pipeline")
    print("=" * 80)

    import json
    output = {
        "owner": {
            "null_cacr_mean": round(owner_result['null_cacr_mean'], 4),
            "null_cacr_std": round(owner_result['null_cacr_std'], 4),
            "null_cacr_min": round(owner_result['null_cacr_min'], 4),
            "null_cacr_max": round(owner_result['null_cacr_max'], 4),
            "n_cells": owner_result['n_cells'],
            "action_pool_size": len(owner_actions),
        },
        "renter": {
            "null_cacr_mean": round(renter_result['null_cacr_mean'], 4),
            "null_cacr_std": round(renter_result['null_cacr_std'], 4),
            "null_cacr_min": round(renter_result['null_cacr_min'], 4),
            "null_cacr_max": round(renter_result['null_cacr_max'], 4),
            "n_cells": renter_result['n_cells'],
            "action_pool_size": len(renter_actions),
        },
        "combined": {
            "null_cacr_weighted": round(combined_null, 4),
            "weights": {"owner": p_owner, "renter": p_renter},
        },
    }

    output_path = SCRIPT_DIR / "cacr_null_model.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\n   Saved to: {output_path}")


if __name__ == "__main__":
    main()
