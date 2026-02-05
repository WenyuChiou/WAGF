"""
Prompt Sensitivity & Positional Bias Tests (MAJOR M7, M8).

Two sensitivity tests for prompt engineering effects:

1. Option Reordering: Reverse the order of action options in the prompt.
   Tests whether LLM exhibits positional bias (e.g., preferring first option).

2. Framing Test: Remove the "CRITICAL RISK ASSESSMENT" section from the
   household prompt. Tests whether framing language inflates TP ratings.

For each test, compare decision/construct distributions using chi-squared
test of independence.

Usage:
    python paper3/analysis/prompt_sensitivity.py --model gemma3:4b --replicates 10
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import yaml

# Ensure project root and paper3 parent on path
def _find_project_root() -> Path:
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "broker").is_dir():
            return current
        current = current.parent
    return Path(__file__).resolve().parents[5]

_PROJECT_ROOT = _find_project_root()
_FLOOD_ROOT = Path(__file__).resolve().parents[2]  # examples/multi_agent/flood
for _p in [str(_PROJECT_ROOT), str(_FLOOD_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from broker.validators.calibration.directional_validator import (  # noqa: E402
    chi_squared_test,
)


# ---------------------------------------------------------------------------
# Modified prompt builders for sensitivity tests
# ---------------------------------------------------------------------------

# Standard option orderings (from run_cv.py)
OWNER_OPTIONS_STANDARD = """\
Choose ONE primary action:
1. buy_insurance — Purchase NFIP flood insurance
2. elevate_house — Elevate your home above Base Flood Elevation
3. buyout_program — Accept the Blue Acres government buyout (irreversible)
4. do_nothing — Take no protective action this year"""

# Reversed ordering: do_nothing first
OWNER_OPTIONS_REVERSED = """\
Choose ONE primary action:
1. do_nothing — Take no protective action this year
2. buyout_program — Accept the Blue Acres government buyout (irreversible)
3. elevate_house — Elevate your home above Base Flood Elevation
4. buy_insurance — Purchase NFIP flood insurance"""

RENTER_OPTIONS_STANDARD = """\
Choose ONE primary action:
1. buy_contents_insurance — Purchase contents-only flood insurance
2. relocate — Move to a different area
3. do_nothing — Take no protective action this year"""

RENTER_OPTIONS_REVERSED = """\
Choose ONE primary action:
1. do_nothing — Take no protective action this year
2. relocate — Move to a different area
3. buy_contents_insurance — Purchase contents-only flood insurance"""

# Reversed numeric → action maps (numbers match reversed ordering above)
OWNER_ACTION_MAP_REVERSED = {
    "1": "do_nothing",
    "2": "buyout_program",
    "3": "elevate_house",
    "4": "buy_insurance",
}
RENTER_ACTION_MAP_REVERSED = {
    "1": "do_nothing",
    "2": "relocate",
    "3": "buy_contents_insurance",
}

# The "CRITICAL RISK ASSESSMENT" framing section from household_owner.txt
RISK_ASSESSMENT_SECTION = """\

### CRITICAL RISK ASSESSMENT
It is crucial to accurately assess your flood risk based on your personal flood history, memories, and current situation. Consider how recent or distant your flood experiences are — threat perceptions naturally evolve with time and new experiences. Your decisions must reflect a realistic understanding of potential dangers and your vulnerability.
"""

# Neutral replacement
RISK_ASSESSMENT_NEUTRAL = """\

### SITUATION ASSESSMENT
Consider your flood history, current situation, and available options when making your decision.
"""

# Response format and criteria (shared constants)
RESPONSE_FORMAT_HINT = """\
Respond ONLY with valid JSON in this exact format:
{
  "TP_LABEL": "VL | L | M | H | VH",
  "CP_LABEL": "VL | L | M | H | VH",
  "decision": "your chosen action",
  "reasoning": "Brief explanation of your decision"
}"""

RATING_SCALE = "VL=Very Low, L=Low, M=Medium, H=High, VH=Very High"

CRITERIA_DEFS = """\
- TP (Threat Perception): How serious do you perceive the flood risk?
- CP (Coping Perception): How confident are you that you can take effective protective action?"""


def build_probe_prompt_variant(
    archetype: Dict[str, Any],
    vignette: Any,
    option_order: str = "standard",
    include_risk_framing: bool = True,
) -> str:
    """Build a probe prompt with configurable option order and framing.

    Parameters
    ----------
    archetype : dict
        Archetype definition from icc_archetypes.yaml.
    vignette : Vignette
        Vignette with .scenario attribute.
    option_order : str
        "standard" or "reversed" — controls action option ordering.
    include_risk_framing : bool
        If True, includes "CRITICAL RISK ASSESSMENT" section.
        If False, uses neutral framing.
    """
    persona = archetype["persona"]
    atype = archetype["agent_type"]
    memory = archetype.get("memory_seed", "No prior memories.")

    # Identity
    if atype == "household_owner":
        identity = "You are a homeowner in the Passaic River Basin, New Jersey."
        options = OWNER_OPTIONS_STANDARD if option_order == "standard" else OWNER_OPTIONS_REVERSED
    else:
        identity = "You are a renter in the Passaic River Basin, New Jersey."
        options = RENTER_OPTIONS_STANDARD if option_order == "standard" else RENTER_OPTIONS_REVERSED

    # Situation
    situation_lines = [f"- Income: {persona.get('income_range', 'Unknown')}"]
    situation_lines.append(f"- Household Size: {persona.get('household_size', 'Unknown')} people")
    if atype == "household_owner":
        situation_lines.append(f"- Property Value: ${persona.get('rcv_building', 0):,.0f}")
    situation_lines.append(f"- Flood Zone: {persona.get('flood_zone', 'Unknown')}")
    situation_lines.append(f"- Flood Experience: {persona.get('flood_experience_summary', 'None')}")
    situation_lines.append(f"- Insurance: You currently {persona.get('insurance_status', 'do not have')} flood insurance.")
    situation = "\n".join(situation_lines)

    # Risk framing section
    if include_risk_framing:
        risk_section = RISK_ASSESSMENT_SECTION
    else:
        risk_section = RISK_ASSESSMENT_NEUTRAL

    prompt = f"""{identity}

### YOUR SITUATION
{situation}

### SCENARIO (for this assessment)
{vignette.scenario}
{risk_section}
### RELEVANT MEMORIES
{memory}

### ADAPTATION OPTIONS
{options}

### EVALUATION CRITERIA
{CRITERIA_DEFS}

Rating Scale: {RATING_SCALE}

Based on the scenario, your situation, and your memories, evaluate the threat and your coping capacity, then choose an action.
{RESPONSE_FORMAT_HINT}"""

    return prompt


# chi_squared_test is imported from broker.validators.calibration.directional_validator


# ---------------------------------------------------------------------------
# Test runners
# ---------------------------------------------------------------------------

def _run_probes(
    invoke_fn,
    prompt: str,
    replicates: int,
    agent_type: str = "household_owner",
    action_map: Optional[Dict[str, str]] = None,
) -> List[Dict[str, str]]:
    """Run replicates of a single prompt and collect parsed responses."""
    from paper3.run_cv import parse_probe_response, map_decision_to_action

    responses = []
    for _ in range(replicates):
        raw, ok = invoke_fn(prompt)
        if ok and raw:
            parsed = parse_probe_response(raw)
            decision = map_decision_to_action(
                parsed.get("decision", "do_nothing"),
                agent_type=agent_type,
                action_map=action_map,
            )
            responses.append({
                "tp_label": parsed.get("TP_LABEL", parsed.get("tp_label", "M")).upper(),
                "cp_label": parsed.get("CP_LABEL", parsed.get("cp_label", "M")).upper(),
                "decision": decision,
            })
    return responses


def run_option_reordering_test(
    archetypes: Dict[str, Dict],
    vignettes: List,
    invoke_fn,
    replicates: int = 10,
    test_archetypes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Test 1: Option reordering — does position affect choice?

    Compares standard ordering (insurance first) vs reversed (do_nothing first).
    """
    if test_archetypes is None:
        # Use a subset of archetypes for cost efficiency
        test_archetypes = ["mg_owner_floodprone", "nmg_owner_floodprone", "vulnerable_newcomer"]

    results = {"pairs": [], "description": "Option reordering test (standard vs reversed)"}
    total_calls = 0

    for arch_name in test_archetypes:
        if arch_name not in archetypes:
            continue
        arch = archetypes[arch_name]

        for vig in vignettes:
            atype = arch.get("agent_type", "household_owner")
            standard_prompt = build_probe_prompt_variant(arch, vig, option_order="standard")
            reversed_prompt = build_probe_prompt_variant(arch, vig, option_order="reversed")

            # Use correct action map per ordering: standard uses default,
            # reversed uses the reversed map so "1" → different action
            reversed_map = (
                OWNER_ACTION_MAP_REVERSED if atype == "household_owner"
                else RENTER_ACTION_MAP_REVERSED
            )
            standard_responses = _run_probes(
                invoke_fn, standard_prompt, replicates,
                agent_type=atype, action_map=None,
            )
            reversed_responses = _run_probes(
                invoke_fn, reversed_prompt, replicates,
                agent_type=atype, action_map=reversed_map,
            )
            total_calls += replicates * 2

            if standard_responses and reversed_responses:
                comparisons = {}
                for field in ["tp_label", "cp_label", "decision"]:
                    dist_a = Counter(r[field] for r in standard_responses)
                    dist_b = Counter(r[field] for r in reversed_responses)
                    test_result = chi_squared_test(dict(dist_a), dict(dist_b))
                    comparisons[field] = {
                        "standard": dict(dist_a),
                        "reversed": dict(dist_b),
                        **test_result,
                        "significant": test_result["p_value"] < 0.05,
                    }

                results["pairs"].append({
                    "archetype": arch_name,
                    "vignette": vig.id,
                    "n_standard": len(standard_responses),
                    "n_reversed": len(reversed_responses),
                    "comparisons": comparisons,
                    "positional_bias_detected": comparisons["decision"].get("significant", False),
                })

    # Summary
    pairs_with_bias = sum(1 for p in results["pairs"] if p.get("positional_bias_detected"))
    results["summary"] = {
        "total_pairs": len(results["pairs"]),
        "pairs_with_positional_bias": pairs_with_bias,
        "bias_rate": pairs_with_bias / len(results["pairs"]) if results["pairs"] else 0.0,
        "total_llm_calls": total_calls,
        "conclusion": (
            "WARNING: Significant positional bias detected"
            if pairs_with_bias / max(len(results["pairs"]), 1) > 0.5
            else "OK: No systematic positional bias"
        ),
    }

    return results


def run_framing_test(
    archetypes: Dict[str, Dict],
    vignettes: List,
    invoke_fn,
    replicates: int = 10,
    test_archetypes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Test 2: Framing — does 'CRITICAL RISK ASSESSMENT' inflate TP?

    Compares prompts with risk framing vs neutral framing.
    """
    if test_archetypes is None:
        test_archetypes = ["mg_owner_floodprone", "nmg_renter_safe", "resilient_veteran"]

    results = {"pairs": [], "description": "Framing test (risk emphasis vs neutral)"}
    total_calls = 0

    for arch_name in test_archetypes:
        if arch_name not in archetypes:
            continue
        arch = archetypes[arch_name]

        for vig in vignettes:
            atype = arch.get("agent_type", "household_owner")
            framed_prompt = build_probe_prompt_variant(arch, vig, include_risk_framing=True)
            neutral_prompt = build_probe_prompt_variant(arch, vig, include_risk_framing=False)

            framed_responses = _run_probes(
                invoke_fn, framed_prompt, replicates, agent_type=atype,
            )
            neutral_responses = _run_probes(
                invoke_fn, neutral_prompt, replicates, agent_type=atype,
            )
            total_calls += replicates * 2

            if framed_responses and neutral_responses:
                comparisons = {}
                for field in ["tp_label", "cp_label", "decision"]:
                    dist_a = Counter(r[field] for r in framed_responses)
                    dist_b = Counter(r[field] for r in neutral_responses)
                    test_result = chi_squared_test(dict(dist_a), dict(dist_b))
                    comparisons[field] = {
                        "framed": dict(dist_a),
                        "neutral": dict(dist_b),
                        **test_result,
                        "significant": test_result["p_value"] < 0.05,
                    }

                # Check if framing inflates TP specifically
                tp_inflation = False
                if comparisons["tp_label"].get("significant"):
                    # Check if framed TP is skewed higher (proper weighted mean)
                    framed_tp = comparisons["tp_label"]["framed"]
                    neutral_tp = comparisons["tp_label"]["neutral"]
                    tp_order = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}
                    # Expand to individual observations for correct mean
                    framed_vals = [tp_order.get(k, 3) for k, v in framed_tp.items() for _ in range(v)]
                    neutral_vals = [tp_order.get(k, 3) for k, v in neutral_tp.items() for _ in range(v)]
                    framed_mean = np.mean(framed_vals) if framed_vals else 3.0
                    neutral_mean = np.mean(neutral_vals) if neutral_vals else 3.0
                    tp_inflation = framed_mean > neutral_mean + 0.1  # threshold for noise

                results["pairs"].append({
                    "archetype": arch_name,
                    "vignette": vig.id,
                    "n_framed": len(framed_responses),
                    "n_neutral": len(neutral_responses),
                    "comparisons": comparisons,
                    "tp_inflation_detected": tp_inflation,
                    "framing_effect_on_decision": comparisons["decision"].get("significant", False),
                })

    # Summary
    tp_inflated = sum(1 for p in results["pairs"] if p.get("tp_inflation_detected"))
    decision_affected = sum(1 for p in results["pairs"] if p.get("framing_effect_on_decision"))
    results["summary"] = {
        "total_pairs": len(results["pairs"]),
        "pairs_with_tp_inflation": tp_inflated,
        "pairs_with_decision_change": decision_affected,
        "total_llm_calls": total_calls,
        "conclusion": (
            "WARNING: Risk framing significantly inflates TP — consider neutral prompt"
            if tp_inflated / max(len(results["pairs"]), 1) > 0.5
            else "OK: Framing effect within acceptable range"
        ),
    }

    return results


# ---------------------------------------------------------------------------
# Master runner
# ---------------------------------------------------------------------------

def run_prompt_sensitivity(
    archetypes_path: str | Path,
    model: str = "gemma3:4b",
    replicates: int = 10,
    output_dir: str | Path = "paper3/results/cv",
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """Run all prompt sensitivity tests.

    Parameters
    ----------
    archetypes_path : Path
        Path to icc_archetypes.yaml.
    model : str
        Ollama model name.
    replicates : int
        Replicates per condition.
    output_dir : Path
        Where to save results.
    temperature : float
        LLM sampling temperature.

    Returns
    -------
    dict
        Combined results from all tests.
    """
    from paper3.run_cv import create_probe_invoke
    from broker.validators.calibration.psychometric_battery import PsychometricBattery

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load archetypes
    with open(archetypes_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    archetypes = config.get("archetypes", {})

    # Load vignettes — use only high severity for cost savings
    vignette_dir = _PROJECT_ROOT / "examples" / "multi_agent" / "flood" / "paper3" / "configs" / "vignettes"
    battery = PsychometricBattery(vignette_dir=vignette_dir)
    vignettes = battery.load_vignettes()
    high_vig = [v for v in vignettes if "high" in v.id.lower()]
    test_vignettes = high_vig if high_vig else vignettes[:1]

    invoke = create_probe_invoke(model, temperature=temperature)

    # Test 1: Option reordering
    print("\n" + "=" * 60)
    print("TEST 1: Option Reordering (Positional Bias)")
    print("=" * 60)
    reorder_results = run_option_reordering_test(
        archetypes, test_vignettes, invoke, replicates=replicates,
    )
    print(f"\n  {reorder_results['summary']['conclusion']}")

    # Test 2: Framing
    print("\n" + "=" * 60)
    print("TEST 2: Risk Framing Effect")
    print("=" * 60)
    framing_results = run_framing_test(
        archetypes, test_vignettes, invoke, replicates=replicates,
    )
    print(f"\n  {framing_results['summary']['conclusion']}")

    # Combined report
    total_calls = (
        reorder_results["summary"]["total_llm_calls"]
        + framing_results["summary"]["total_llm_calls"]
    )
    report = {
        "option_reordering": reorder_results,
        "framing_effect": framing_results,
        "total_llm_calls": total_calls,
    }

    report_path = output_dir / "prompt_sensitivity_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved: {report_path}")
    print(f"Total LLM calls: {total_calls}")

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Prompt Sensitivity Tests")
    parser.add_argument("--model", default="gemma3:4b")
    parser.add_argument("--replicates", type=int, default=10)
    parser.add_argument("--output-dir", default="paper3/results/cv")
    parser.add_argument(
        "--archetypes",
        default=str(Path(__file__).parent.parent / "configs" / "icc_archetypes.yaml"),
    )
    args = parser.parse_args()

    run_prompt_sensitivity(
        archetypes_path=args.archetypes,
        model=args.model,
        replicates=args.replicates,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
