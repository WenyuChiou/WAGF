"""Cross-check the ICLR draft against the frozen WAGF evidence boundary.

This check is deliberately conservative.  It does not execute simulations or
recompute a statistic.  It verifies that the source-of-truth evidence files
exist, that the manuscript includes the key reported quantities, and that the
scope-limiting language is present.
"""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "ICLR2027" / "submission"
TAE = ROOT / "SUBMISSION_2026" / "TAE"
MANUSCRIPT = PACKAGE / "paper" / "manuscript.tex"
NUMBERS = TAE / "NUMBERS.md"
DENOMINATOR_GAP = PACKAGE / "supplement" / "fig3_denominator_gap.csv"
GAP_INTERVALS = PACKAGE / "supplement" / "fig4_gap_intervals.csv"
PER_SEED = PACKAGE / "supplement" / "fig4_per_seed.csv"
REPORT = PACKAGE / "checks" / "evidence_boundary_report.json"
EXPECTED_MODELS = {
    "gemma3:4b",
    "gemma3:12b",
    "gemma4:e2b",
    "gemma4:e4b",
    "ministral3:8b",
}


def main() -> int:
    manuscript = MANUSCRIPT.read_text(encoding="utf-8")
    numbers = NUMBERS.read_text(encoding="utf-8")
    errors: list[str] = []
    warnings: list[str] = []

    required_sources = [
        TAE / "NUMBERS.md",
        TAE / "evidence" / "_data.py",
        TAE / "evidence" / "table1_cells.py",
        TAE / "evidence" / "fig1_rule_layers.py",
        TAE / "evidence" / "fig2_mechanism.py",
        TAE / "evidence" / "fig3_consequence.py",
        TAE / "evidence" / "e4_world_fixed_decomposition.py",
        TAE / "evidence" / "e6_antecedent_conjunction.py",
        DENOMINATOR_GAP,
        GAP_INTERVALS,
        PER_SEED,
    ]
    missing_sources = [str(path) for path in required_sources if not path.exists()]
    if missing_sources:
        errors.append(f"missing frozen evidence sources: {missing_sources}")

    key_values = [
        "+45.73",
        "+25.90",
        "+29.90",
        "+20.26",
        "+36.57",
        "-16.06",
        "+3.38",
        "+43.15",
        "25.46",
        "68.61",
        "-2.53",
        "+0.21",
        "+11.44",
        "+0.16",
        "-22.17",
        "+27.82",
        "+64.29",
        "+3.33",
        "+53.46",
        "24.3%",
        "106.57",
        "102.25",
    ]
    manuscript_search = manuscript.replace(r"\%", "%")
    denominator_gap_rows = []
    if DENOMINATOR_GAP.exists():
        with DENOMINATOR_GAP.open(newline="", encoding="utf-8") as handle:
            denominator_gap_rows = list(csv.DictReader(handle))

    gap_interval_rows = []
    if GAP_INTERVALS.exists():
        with GAP_INTERVALS.open(newline="", encoding="utf-8") as handle:
            gap_interval_rows = list(csv.DictReader(handle))
    denominator_models = [row.get("model", "") for row in denominator_gap_rows]
    interval_models = [row.get("model", "") for row in gap_interval_rows]
    exact_denominator_rows = (
        len(denominator_models) == len(set(denominator_models))
        and set(denominator_models) == EXPECTED_MODELS
    )
    exact_interval_rows = (
        len(interval_models) == len(set(interval_models))
        and set(interval_models) == EXPECTED_MODELS
    )
    if not exact_denominator_rows:
        errors.append("Figure 4 endpoint source must contain exactly one row for each expected model")
    if not exact_interval_rows:
        errors.append("Figure 4 gap intervals must contain exactly one row for each expected model")
    if exact_denominator_rows and exact_interval_rows:
        interval_by_model = {row["model"]: row for row in gap_interval_rows}
        negative = positive = uncertain = 0
        for endpoint in denominator_gap_rows:
            model = endpoint["model"]
            interval = interval_by_model[model]
            fields = [
                float(endpoint["cond_delta_pp"]),
                float(endpoint["all_delta_pp"]),
                float(endpoint["gap_pp"]),
                float(interval["gap_pp"]),
                float(interval["gap_ci_lo"]),
                float(interval["gap_ci_hi"]),
                float(interval["n_paired"]),
            ]
            if not all(math.isfinite(value) for value in fields):
                errors.append(f"Figure 4 contains a non-finite value for {model}")
                continue
            endpoint_gap = fields[0] - fields[1]
            if abs(endpoint_gap - fields[2]) > 0.011 or abs(fields[2] - fields[3]) > 0.011:
                errors.append(f"Figure 4 endpoint/gap mismatch for {model}")
            if not fields[4] <= fields[3] <= fields[5] or int(fields[6]) not in {3, 5}:
                errors.append(f"Figure 4 interval or paired count invalid for {model}")
            if fields[5] < 0:
                negative += 1
            elif fields[4] > 0:
                positive += 1
            else:
                uncertain += 1
        if (negative, positive, uncertain) != (3, 1, 1):
            errors.append(
                "Figure 4 sign summary changed; expected three negative, one positive, and one zero-crossing interval"
            )

    def gap_value_present(value: str) -> bool:
        """Accept a rounded display value only from the CSV's ``gap_pp`` field."""
        try:
            target = float(value)
        except ValueError:
            return False
        return any(
            abs(float(row["gap_pp"]) - target) < 0.005
            for row in denominator_gap_rows
            if row.get("gap_pp")
        )

    derived_gap_values = {"-16.06", "+3.38"}

    missing_in_numbers = [
        value
        for value in key_values
        if value not in numbers
        and not (value in derived_gap_values and gap_value_present(value))
    ]
    missing_in_manuscript = [value for value in key_values if value not in manuscript_search]
    if missing_in_numbers:
        errors.append(
            "key values absent from NUMBERS.md and the frozen denominator-gap CSV: "
            f"{missing_in_numbers}"
        )
    if missing_in_manuscript:
        errors.append(f"key values absent from manuscript: {missing_in_manuscript}")

    required_scope_assertions = {
        "descriptive causal boundary": (
            r"descriptive rather than causal",
            r"not a causal adjustment",
            r"not causal effect estimates",
            r"does not establish a causal explanation",
        ),
        "deception boundary": (
            r"does not claim deception",
            r"do not claim that agents deceive",
            r"no deception claim",
        ),
        "first-response boundary": (
            r"does not store the first response before a retry",
        ),
        "non-causal flood boundary": (
            r"do not use them to support causal claims",
            r"do not use these configurations to support causal claims",
        ),
        "reweighting boundary": (r"not a causal adjustment",),
        "scarcity-condition distinction": (
            r"broader than the two-condition rule",
        ),
        "conceptual-figure boundary": (r"not a data figure",),
        "public-weight scope": (r"publicly available weights",),
        "non-universal scope": (
            r"same magnitudes hold for every model or agent framework",
            r"rather than all LLM agents",
        ),
        "bitwise-reproduction boundary": (
            r"does not claim bitwise reproduction",
        ),
    }
    missing_scope = [
        name
        for name, assertions in required_scope_assertions.items()
        if not any(re.search(pattern, manuscript, flags=re.IGNORECASE)
                   for pattern in assertions)
    ]
    if missing_scope:
        errors.append(f"scope-limiting phrases absent: {missing_scope}")

    if not any(
        phrase in manuscript
        for phrase in ("full conjunction", "both conditions appear together")
    ):
        errors.append("manuscript does not define the two-condition rule")
    if "scarcity report" not in manuscript:
        errors.append("manuscript does not name the scarcity report")

    if "the rule's antecedent" in manuscript.lower():
        errors.append("manuscript may silently relabel the scarcity marginal as the rule antecedent")

    result = {
        "status": "PASS" if not errors else "FAIL",
        "scope": "frozen evidence presence and text alignment only",
        "required_source_count": len(required_sources),
        "key_value_count": len(key_values),
        "warnings": warnings,
        "errors": errors,
    }
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
