"""
Utility Theory framework for government agents.

Government agents evaluate policies based on:
- Budget Utility: Fiscal impact (deficit, neutral, surplus)
- Equity Gap: Socioeconomic equity assessment
- Adoption Rate: Policy adoption among constituents
"""

from typing import Dict, List

from broker.core.psychometric import (
    PsychologicalFramework,
    ConstructDef,
    ValidationResult,
)


class UtilityFramework(PsychologicalFramework):
    """Utility Theory framework for government agents."""

    @property
    def name(self) -> str:
        return "Utility Theory"

    def get_constructs(self) -> Dict[str, ConstructDef]:
        """Return Utility Theory constructs for government agents."""
        return {
            "BUDGET_UTIL": ConstructDef(
                name="Budget Utility",
                values=["DEFICIT", "NEUTRAL", "SURPLUS"],
                required=True,
                description="Current budget impact assessment"
            ),
            "EQUITY_GAP": ConstructDef(
                name="Equity Gap",
                values=["HIGH", "MEDIUM", "LOW"],
                required=True,
                description="Socioeconomic equity assessment"
            ),
            "ADOPTION_RATE": ConstructDef(
                name="Adoption Rate",
                values=["LOW", "MEDIUM", "HIGH"],
                required=False,
                description="Current policy adoption rate"
            ),
        }

    def validate_coherence(self, appraisals: Dict[str, str]) -> ValidationResult:
        """Validate Utility Theory coherence."""
        errors = []
        warnings = []

        required_check = self.validate_required_constructs(appraisals)
        if not required_check.valid:
            return required_check

        value_check = self.validate_construct_values(appraisals)
        if not value_check.valid:
            return value_check

        budget = appraisals.get("BUDGET_UTIL", "NEUTRAL").upper()
        equity = appraisals.get("EQUITY_GAP", "MEDIUM").upper()

        if budget == "DEFICIT" and equity == "HIGH":
            warnings.append("Budget deficit with high equity gap may require careful prioritization")

        return ValidationResult(
            valid=True,
            errors=errors,
            warnings=warnings,
            metadata={
                "budget_util": budget,
                "equity_gap": equity,
                "adoption_rate": appraisals.get("ADOPTION_RATE", ""),
            }
        )

    def get_expected_behavior(self, appraisals: Dict[str, str]) -> List[str]:
        """Return expected government actions given utility appraisals."""
        budget = appraisals.get("BUDGET_UTIL", "NEUTRAL").upper()
        equity = appraisals.get("EQUITY_GAP", "MEDIUM").upper()

        if equity == "HIGH":
            return ["increase_subsidy", "targeted_assistance", "outreach_program"]
        elif budget == "SURPLUS":
            return ["increase_subsidy", "infrastructure_improvement", "expand_program"]
        elif budget == "DEFICIT":
            return ["reduce_subsidy", "cost_optimization", "maintain_current"]
        else:
            return ["maintain_current", "incremental_improvement"]
