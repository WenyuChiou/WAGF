"""Cross-check the ICLR draft against the frozen WAGF evidence boundary.

This check is deliberately conservative.  It does not execute simulations or
recompute a statistic.  It verifies that the source-of-truth evidence files
exist, that the manuscript includes the key reported quantities, and that the
scope-limiting language is present.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "ICLR2027" / "submission"
TAE = ROOT / "SUBMISSION_2026" / "TAE"
MANUSCRIPT = PACKAGE / "paper" / "manuscript.tex"
NUMBERS = TAE / "NUMBERS.md"
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
    ]
    missing_sources = [str(path) for path in required_sources if not path.exists()]
    if missing_sources:
        errors.append(f"missing frozen evidence sources: {missing_sources}")

    key_values = [
        "+45.73",
        "+23.02",
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
    missing_in_numbers = [value for value in key_values if value not in numbers]
    missing_in_manuscript = [value for value in key_values if value not in manuscript_search]
    if missing_in_numbers:
        errors.append(f"key values absent from NUMBERS.md: {missing_in_numbers}")
    if missing_in_manuscript:
        errors.append(f"key values absent from manuscript: {missing_in_manuscript}")

    required_scope_phrases = [
        "descriptive rather than causal",
        "does not claim deception",
        "does not store the first response",
        "identification control",
        "not a causal adjustment",
        "marginal proxy",
        "not a data figure",
    ]
    missing_scope = [phrase for phrase in required_scope_phrases if phrase not in manuscript]
    if missing_scope:
        errors.append(f"scope-limiting phrases absent: {missing_scope}")

    if "full conjunction" not in manuscript:
        errors.append("manuscript does not define the full conjunction")
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
