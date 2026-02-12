"""
Financial Risk Theory framework for insurance agents.

Insurance agents evaluate decisions based on:
- Loss Ratio: Claims vs premiums (high, medium, low)
- Solvency: Financial stability (at_risk, stable, strong)
- Market Share: Competitive position
"""

from typing import Dict, List

from broker.core.psychometric import (
    PsychologicalFramework,
    ConstructDef,
    ValidationResult,
)


class FinancialFramework(PsychologicalFramework):
    """Financial Risk Theory framework for insurance agents."""

    @property
    def name(self) -> str:
        return "Financial Risk Theory"

    def get_constructs(self) -> Dict[str, ConstructDef]:
        """Return Financial constructs for insurance agents."""
        return {
            "LOSS_RATIO": ConstructDef(
                name="Loss Ratio",
                values=["HIGH", "MEDIUM", "LOW"],
                required=True,
                description="Claims to premiums ratio assessment"
            ),
            "SOLVENCY": ConstructDef(
                name="Solvency",
                values=["AT_RISK", "STABLE", "STRONG"],
                required=True,
                description="Financial stability status"
            ),
            "MARKET_SHARE": ConstructDef(
                name="Market Share",
                values=["DECLINING", "STABLE", "GROWING"],
                required=False,
                description="Competitive market position"
            ),
        }

    def validate_coherence(self, appraisals: Dict[str, str]) -> ValidationResult:
        """Validate Financial Theory coherence."""
        errors = []
        warnings = []

        required_check = self.validate_required_constructs(appraisals)
        if not required_check.valid:
            return required_check

        value_check = self.validate_construct_values(appraisals)
        if not value_check.valid:
            return value_check

        loss = appraisals.get("LOSS_RATIO", "MEDIUM").upper()
        solvency = appraisals.get("SOLVENCY", "STABLE").upper()

        if loss == "HIGH" and solvency == "STRONG":
            warnings.append("High loss ratio with strong solvency may indicate pricing inefficiency")

        if solvency == "AT_RISK":
            warnings.append("At-risk solvency requires conservative decision-making")

        return ValidationResult(
            valid=True,
            errors=errors,
            warnings=warnings,
            metadata={
                "loss_ratio": loss,
                "solvency": solvency,
                "market_share": appraisals.get("MARKET_SHARE", ""),
            }
        )

    def get_expected_behavior(self, appraisals: Dict[str, str]) -> List[str]:
        """Return expected insurance actions given financial appraisals."""
        loss = appraisals.get("LOSS_RATIO", "MEDIUM").upper()
        solvency = appraisals.get("SOLVENCY", "STABLE").upper()

        if solvency == "AT_RISK":
            return ["raise_premium", "limit_coverage", "reduce_exposure"]
        elif loss == "HIGH":
            return ["raise_premium", "adjust_coverage", "increase_deductible"]
        elif solvency == "STRONG" and loss == "LOW":
            return ["expand_coverage", "competitive_pricing", "new_product"]
        else:
            return ["maintain_pricing", "standard_renewal"]
