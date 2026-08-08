"""Cross-check the ICLR draft against the frozen WAGF evidence boundary.

This check is deliberately conservative.  It does not execute simulations or
recompute a statistic.  It verifies that the source-of-truth evidence files
exist, that the manuscript includes the key reported quantities, and that the
scope-limiting language is present.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "ICLR2027" / "submission"
TAE = ROOT / "SUBMISSION_2026" / "TAE"
MANUSCRIPT = PACKAGE / "paper" / "manuscript.tex"
NUMBERS = TAE / "NUMBERS.md"
DENOMINATOR_GAP = PACKAGE / "supplement" / "fig3_denominator_gap.csv"
REPORT = PACKAGE / "checks" / "evidence_boundary_report.json"


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
