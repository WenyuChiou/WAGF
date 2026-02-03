"""
Persona Sensitivity Analysis (CRITICAL C6).

Tests whether LLM decisions are driven by persona content (demographics,
flood history, income) vs. LLM priors. Three swap experiments:

1. Income Swap: Give MG persona NMG income and vice versa.
2. Zone Swap: Place flood-experienced agent in Zone X (low risk).
3. History Swap: Give never-flooded agent a 3-flood history.

For each swap, re-run ICC probes and compare TP/CP/decision distributions
before and after using chi-squared test of independence.

Usage:
    python paper3/run_cv.py --mode persona_sensitivity --model gemma3:4b
    # or standalone:
    python paper3/analysis/persona_sensitivity.py --model gemma3:4b --replicates 10
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import yaml

# Ensure project root and paper3 parent on path
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOOD_ROOT = Path(__file__).resolve().parents[2]  # examples/multi_agent/flood
for _p in [str(_PROJECT_ROOT), str(_FLOOD_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# Swap definitions
# ---------------------------------------------------------------------------

SWAP_TESTS = {
    "income_swap": {
        "description": "Swap income between MG and NMG archetypes",
        "pairs": [
            {
                "base": "mg_owner_floodprone",
                "swap_field": ("persona", "income_range"),
                "swap_value": "$75,000 - $99,999",  # NMG income
                "label": "MG_owner_with_NMG_income",
            },
            {
                "base": "nmg_owner_floodprone",
                "swap_field": ("persona", "income_range"),
                "swap_value": "$25,000 - $44,999",  # MG income
                "label": "NMG_owner_with_MG_income",
            },
        ],
    },
    "zone_swap": {
        "description": "Place flood-experienced agent in safe zone",
        "pairs": [
            {
                "base": "mg_owner_floodprone",
                "swap_field": ("persona", "flood_zone"),
                "swap_value": "X (minimal risk)",
                "label": "MG_owner_in_zone_X",
            },
        ],
    },
    "history_swap": {
        "description": "Give never-flooded agent a 3-flood history",
        "pairs": [
            {
                "base": "nmg_renter_safe",
                "swap_fields": [
                    (("persona", "flood_count"), 3),
                    (("persona", "years_since_flood"), 1),
                    (("persona", "cumulative_damage"), 45000),
                    (
                        ("persona", "flood_experience_summary"),
                        "Experienced 3 major floods in the past 8 years",
                    ),
                ],
                "swap_memory": (
                    "I've been through three terrible floods. Each time the water "
                    "came higher. Last year was the worst — we lost everything in "
                    "the apartment. I'm scared it will happen again."
                ),
                "label": "NMG_renter_with_flood_history",
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# Swap logic
# ---------------------------------------------------------------------------

def apply_swap(
    archetype: Dict[str, Any],
    swap_def: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a modified copy of an archetype with swapped fields."""
    modified = copy.deepcopy(archetype)

    if "swap_field" in swap_def:
        # Single field swap
        section, key = swap_def["swap_field"]
        modified[section][key] = swap_def["swap_value"]
    elif "swap_fields" in swap_def:
        # Multi-field swap
        for (section, key), value in swap_def["swap_fields"]:
            modified[section][key] = value

    if "swap_memory" in swap_def:
        modified["memory_seed"] = swap_def["swap_memory"]

    return modified


# ---------------------------------------------------------------------------
# Chi-squared test
# ---------------------------------------------------------------------------

def chi_squared_test(
    dist_a: Dict[str, int],
    dist_b: Dict[str, int],
) -> Dict[str, Any]:
    """Chi-squared test of independence between two decision distributions.

    Returns dict with chi2 statistic, p-value, and effect size (Cramer's V).
    """
    try:
        from scipy import stats
    except ImportError:
        raise ImportError(
            "scipy is required for chi-squared tests. "
            "Install with: pip install scipy"
        ) from None

    # Union of all labels
    all_labels = sorted(set(dist_a.keys()) | set(dist_b.keys()))
    if len(all_labels) < 2:
        return {"chi2": 0.0, "p_value": 1.0, "cramers_v": 0.0, "df": 0}

    # Build contingency table
    observed = np.array(
        [[int(dist_a.get(lbl, 0)) for lbl in all_labels],
         [int(dist_b.get(lbl, 0)) for lbl in all_labels]],
        dtype=int,
    )

    # Remove columns with all zeros
    col_sums = observed.sum(axis=0)
    observed = observed[:, col_sums > 0]

    if observed.shape[1] < 2:
        return {"chi2": 0.0, "p_value": 1.0, "cramers_v": 0.0, "df": 0}

    chi2, p_val, df, expected = stats.chi2_contingency(observed)
    n = observed.sum()
    k = min(observed.shape) - 1
    cramers_v = np.sqrt(chi2 / (n * k)) if n * k > 0 else 0.0

    return {
        "chi2": float(chi2),
        "p_value": float(p_val),
        "cramers_v": float(cramers_v),
        "df": int(df),
    }


def compare_distributions(
    responses_base: List[Dict],
    responses_swap: List[Dict],
) -> Dict[str, Any]:
    """Compare TP, CP, and decision distributions between base and swap."""
    results = {}

    for field in ["tp_label", "cp_label", "decision"]:
        dist_a = Counter(r[field] for r in responses_base)
        dist_b = Counter(r[field] for r in responses_swap)

        chi2_result = chi_squared_test(dict(dist_a), dict(dist_b))
        results[field] = {
            "base_distribution": dict(dist_a),
            "swap_distribution": dict(dist_b),
            **chi2_result,
            "significant": chi2_result["p_value"] < 0.05,
        }

    return results


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_persona_sensitivity(
    archetypes_path: str | Path,
    model: str = "gemma3:4b",
    replicates: int = 10,
    output_dir: str | Path = "paper3/results/cv",
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """Run all persona swap experiments.

    Parameters
    ----------
    archetypes_path : Path
        Path to icc_archetypes.yaml.
    model : str
        Ollama model name.
    replicates : int
        Number of replicates per condition.
    output_dir : Path
        Where to save results.
    temperature : float
        LLM sampling temperature.

    Returns
    -------
    dict
        Results for each swap test.
    """
    # Late imports to avoid circular dependencies
    from paper3.run_cv import (
        build_probe_prompt,
        create_probe_invoke,
        parse_probe_response,
    )
    from broker.validators.calibration.psychometric_battery import (
        PsychometricBattery,
        Vignette,
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load archetypes
    with open(archetypes_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    archetypes = config.get("archetypes", {})

    # Load vignettes (use high_severity only for sensitivity — reduces cost)
    vignette_dir = _PROJECT_ROOT / "examples" / "multi_agent" / "flood" / "paper3" / "configs" / "vignettes"
    battery = PsychometricBattery(vignette_dir=vignette_dir)
    vignettes = battery.load_vignettes()
    # Use only high severity vignette for swap tests (cost savings)
    high_vig = [v for v in vignettes if "high" in v.id.lower()]
    if high_vig:
        test_vignettes = high_vig
    else:
        test_vignettes = vignettes[:1]  # fallback to first vignette

    invoke = create_probe_invoke(model, temperature=temperature)

    all_results: Dict[str, Any] = {}
    total_calls = 0

    for test_name, test_def in SWAP_TESTS.items():
        print(f"\n=== Swap Test: {test_name} ===")
        print(f"  {test_def['description']}")

        test_results = {"description": test_def["description"], "pairs": []}

        for pair_def in test_def["pairs"]:
            base_key = pair_def["base"]
            label = pair_def["label"]

            if base_key not in archetypes:
                print(f"  SKIP: archetype '{base_key}' not found in config")
                continue

            base_arch = archetypes[base_key]
            swap_arch = apply_swap(base_arch, pair_def)

            print(f"  Pair: {base_key} -> {label}")

            # Collect responses for base and swap
            base_responses = []
            swap_responses = []

            for vig in test_vignettes:
                base_prompt = build_probe_prompt(base_arch, vig)
                swap_prompt = build_probe_prompt(swap_arch, vig)

                for rep in range(replicates):
                    # Base
                    raw_b, ok_b = invoke(base_prompt)
                    total_calls += 1
                    if ok_b and raw_b:
                        parsed = parse_probe_response(raw_b)
                        base_responses.append({
                            "tp_label": parsed.get("TP_LABEL", parsed.get("tp_label", "M")).upper(),
                            "cp_label": parsed.get("CP_LABEL", parsed.get("cp_label", "M")).upper(),
                            "decision": parsed.get("decision", "do_nothing").lower().strip(),
                        })

                    # Swap
                    raw_s, ok_s = invoke(swap_prompt)
                    total_calls += 1
                    if ok_s and raw_s:
                        parsed = parse_probe_response(raw_s)
                        swap_responses.append({
                            "tp_label": parsed.get("TP_LABEL", parsed.get("tp_label", "M")).upper(),
                            "cp_label": parsed.get("CP_LABEL", parsed.get("cp_label", "M")).upper(),
                            "decision": parsed.get("decision", "do_nothing").lower().strip(),
                        })

            # Compare distributions
            if base_responses and swap_responses:
                comparison = compare_distributions(base_responses, swap_responses)
                pair_result = {
                    "base_archetype": base_key,
                    "swap_label": label,
                    "n_base": len(base_responses),
                    "n_swap": len(swap_responses),
                    "comparisons": comparison,
                }

                # Summary: is persona driving behavior?
                sig_count = sum(
                    1 for v in comparison.values() if v.get("significant", False)
                )
                pair_result["persona_sensitive"] = sig_count >= 2
                pair_result["significant_fields"] = [
                    k for k, v in comparison.items() if v.get("significant", False)
                ]

                print(f"    Significant changes in: {pair_result['significant_fields']}")
                print(f"    Persona sensitive: {pair_result['persona_sensitive']}")

                test_results["pairs"].append(pair_result)
            else:
                print(f"    WARNING: Insufficient responses (base={len(base_responses)}, swap={len(swap_responses)})")

        all_results[test_name] = test_results

    # Overall assessment
    all_pairs = [p for t in all_results.values() for p in t.get("pairs", [])]
    sensitive_count = sum(1 for p in all_pairs if p.get("persona_sensitive", False))
    total_pairs = len(all_pairs)

    summary = {
        "total_pairs_tested": total_pairs,
        "persona_sensitive_pairs": sensitive_count,
        "persona_sensitivity_rate": sensitive_count / total_pairs if total_pairs > 0 else 0.0,
        "conclusion": (
            "PASS: Persona content drives LLM behavior"
            if sensitive_count >= total_pairs * 0.7
            else "INCONCLUSIVE: Mixed evidence for persona sensitivity"
            if sensitive_count >= total_pairs * 0.4
            else "FAIL: LLM behavior not sufficiently persona-driven"
        ),
        "total_llm_calls": total_calls,
    }

    report = {"swap_tests": all_results, "summary": summary}

    # Save
    report_path = output_dir / "persona_sensitivity_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved: {report_path}")
    print(f"Summary: {summary['conclusion']}")
    print(f"Total LLM calls: {total_calls}")

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Persona Sensitivity Analysis")
    parser.add_argument("--model", default="gemma3:4b")
    parser.add_argument("--replicates", type=int, default=10)
    parser.add_argument("--output-dir", default="paper3/results/cv")
    parser.add_argument(
        "--archetypes",
        default=str(Path(__file__).parent.parent / "configs" / "icc_archetypes.yaml"),
    )
    args = parser.parse_args()

    run_persona_sensitivity(
        archetypes_path=args.archetypes,
        model=args.model,
        replicates=args.replicates,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
