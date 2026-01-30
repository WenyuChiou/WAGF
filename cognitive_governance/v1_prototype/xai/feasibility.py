"""
Categorical Feasibility Scoring for XAI.

Provides domain-aware feasibility scoring for categorical transitions.
Instead of returning a fixed 0.5 score, this module ranks transitions
based on domain-specific transition matrices.

Example:
    >>> scorer = CategoricalFeasibilityScorer()
    >>> scorer.register_domain("education", EDUCATION_FEASIBILITY)
    >>> score = scorer.score("degree", "high_school", "bachelors", "education")
    0.4  # Harder transition
"""
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass, field


@dataclass
class TransitionInfo:
    """Information about a categorical transition."""
    from_value: str
    to_value: str
    feasibility: float
    rationale: Optional[str] = None


class CategoricalFeasibilityScorer:
    """
    Domain-aware feasibility scoring for categorical transitions.

    Registers domain-specific transition matrices that define how
    "feasible" it is to change from one category to another.

    Higher scores (close to 1.0) = easier transitions
    Lower scores (close to 0.0) = harder transitions
    """

    def __init__(self):
        self.matrices: Dict[str, Dict[Tuple[str, str], float]] = {}
        self.rationales: Dict[str, Dict[Tuple[str, str], str]] = {}
        self.default_score = 0.4  # Default when no matrix entry exists

    def register_domain(
        self,
        domain: str,
        transitions: Dict[Tuple[str, str], float],
        rationales: Optional[Dict[Tuple[str, str], str]] = None,
    ) -> None:
        """
        Register feasibility matrix for a domain.

        Args:
            domain: Domain name (e.g., "education", "finance")
            transitions: Dict mapping (from, to) tuples to feasibility scores
            rationales: Optional dict mapping (from, to) to explanations
        """
        self.matrices[domain] = transitions
        if rationales:
            self.rationales[domain] = rationales

    def score(
        self,
        param: str,
        from_value: str,
        to_value: str,
        domain: str = "generic",
    ) -> float:
        """
        Score the feasibility of a categorical transition.

        Args:
            param: Parameter name (for future param-specific scoring)
            from_value: Current category value
            to_value: Target category value
            domain: Domain for lookup

        Returns:
            Feasibility score between 0 and 1
        """
        if from_value == to_value:
            return 1.0  # No change needed

        matrix = self.matrices.get(domain, {})
        return matrix.get((from_value, to_value), self.default_score)

    def get_rationale(
        self,
        from_value: str,
        to_value: str,
        domain: str = "generic",
    ) -> Optional[str]:
        """Get explanation for a transition's feasibility."""
        rationales = self.rationales.get(domain, {})
        return rationales.get((from_value, to_value))

    def rank_options(
        self,
        param: str,
        from_value: str,
        valid_options: List[str],
        domain: str = "generic",
    ) -> List[TransitionInfo]:
        """
        Rank valid options by feasibility.

        Args:
            param: Parameter name
            from_value: Current category value
            valid_options: List of valid target values
            domain: Domain for lookup

        Returns:
            List of TransitionInfo sorted by feasibility (highest first)
        """
        transitions = []
        for to_value in valid_options:
            feasibility = self.score(param, from_value, to_value, domain)
            rationale = self.get_rationale(from_value, to_value, domain)
            transitions.append(TransitionInfo(
                from_value=from_value,
                to_value=to_value,
                feasibility=feasibility,
                rationale=rationale,
            ))

        return sorted(transitions, key=lambda t: t.feasibility, reverse=True)

    def get_easiest_transition(
        self,
        param: str,
        from_value: str,
        valid_options: List[str],
        domain: str = "generic",
    ) -> TransitionInfo:
        """Get the most feasible transition option."""
        ranked = self.rank_options(param, from_value, valid_options, domain)
        return ranked[0] if ranked else TransitionInfo(
            from_value=from_value,
            to_value=valid_options[0] if valid_options else "",
            feasibility=self.default_score,
        )


# =============================================================================
# Pre-built Domain Feasibility Matrices
# =============================================================================

# Education domain: degree progression
EDUCATION_FEASIBILITY: Dict[Tuple[str, str], float] = {
    # Natural progression (easier)
    ("none", "high_school"): 0.7,
    ("high_school", "associate"): 0.6,
    ("associate", "bachelors"): 0.5,
    ("bachelors", "masters"): 0.4,
    ("masters", "doctorate"): 0.3,

    # Skip levels (harder)
    ("high_school", "bachelors"): 0.4,
    ("high_school", "masters"): 0.2,
    ("associate", "masters"): 0.3,
    ("bachelors", "doctorate"): 0.25,

    # Reverse (very hard - credential loss)
    ("doctorate", "masters"): 0.1,
    ("masters", "bachelors"): 0.1,
    ("bachelors", "associate"): 0.1,
}

EDUCATION_RATIONALES: Dict[Tuple[str, str], str] = {
    ("high_school", "associate"): "2-year community college program",
    ("associate", "bachelors"): "Transfer to 4-year university",
    ("bachelors", "masters"): "Graduate school admission required",
    ("masters", "doctorate"): "PhD program (4-7 years)",
}

# Finance domain: savings level transitions
FINANCE_FEASIBILITY: Dict[Tuple[str, str], float] = {
    # Improvement (natural with effort)
    ("critical", "low"): 0.5,
    ("low", "moderate"): 0.5,
    ("moderate", "adequate"): 0.4,
    ("adequate", "strong"): 0.3,

    # Big jumps (harder)
    ("critical", "moderate"): 0.3,
    ("critical", "adequate"): 0.2,
    ("low", "strong"): 0.2,

    # Decline (easier but undesirable)
    ("strong", "adequate"): 0.7,
    ("adequate", "moderate"): 0.7,
    ("moderate", "low"): 0.8,
    ("low", "critical"): 0.9,
}

FINANCE_RATIONALES: Dict[Tuple[str, str], str] = {
    ("critical", "low"): "Build emergency fund (3-6 months effort)",
    ("low", "moderate"): "Consistent saving habit required",
    ("moderate", "adequate"): "Increase savings rate, reduce expenses",
    ("adequate", "strong"): "Investment growth + high savings rate",
}

# Flood domain: adaptation status
FLOOD_FEASIBILITY: Dict[Tuple[str, str], float] = {
    # Protective actions
    ("unprotected", "insured"): 0.6,
    ("unprotected", "elevated"): 0.3,
    ("insured", "elevated"): 0.35,
    ("unprotected", "relocated"): 0.2,

    # Combined protection
    ("insured", "insured_elevated"): 0.35,
    ("elevated", "insured_elevated"): 0.55,

    # Full protection
    ("insured_elevated", "fully_adapted"): 0.4,

    # Reverse (losing protection)
    ("insured", "unprotected"): 0.8,  # Easy to lose
    ("elevated", "unprotected"): 0.1,  # Can't un-elevate
}

FLOOD_RATIONALES: Dict[Tuple[str, str], str] = {
    ("unprotected", "insured"): "Purchase flood insurance policy",
    ("unprotected", "elevated"): "Major construction project ($50K-200K)",
    ("insured", "elevated"): "Add elevation to existing insurance",
    ("unprotected", "relocated"): "Sell property and move (major life change)",
}

# Health domain: behavior change
HEALTH_FEASIBILITY: Dict[Tuple[str, str], float] = {
    # Exercise habits
    ("sedentary", "light_active"): 0.5,
    ("light_active", "moderately_active"): 0.4,
    ("moderately_active", "very_active"): 0.3,
    ("sedentary", "very_active"): 0.1,

    # Diet changes
    ("unhealthy_diet", "mixed_diet"): 0.5,
    ("mixed_diet", "healthy_diet"): 0.4,
    ("unhealthy_diet", "healthy_diet"): 0.2,

    # Smoking cessation
    ("smoker", "trying_to_quit"): 0.4,
    ("trying_to_quit", "non_smoker"): 0.3,
    ("smoker", "non_smoker"): 0.15,
}

HEALTH_RATIONALES: Dict[Tuple[str, str], str] = {
    ("sedentary", "light_active"): "Start with 30 min walks 3x/week",
    ("smoker", "non_smoker"): "Average 6-8 quit attempts needed",
    ("unhealthy_diet", "healthy_diet"): "Gradual transition recommended",
}


def create_default_scorer() -> CategoricalFeasibilityScorer:
    """Create a scorer with all pre-built domain matrices."""
    scorer = CategoricalFeasibilityScorer()

    scorer.register_domain("education", EDUCATION_FEASIBILITY, EDUCATION_RATIONALES)
    scorer.register_domain("finance", FINANCE_FEASIBILITY, FINANCE_RATIONALES)
    scorer.register_domain("flood", FLOOD_FEASIBILITY, FLOOD_RATIONALES)
    scorer.register_domain("health", HEALTH_FEASIBILITY, HEALTH_RATIONALES)

    return scorer


__all__ = [
    "CategoricalFeasibilityScorer",
    "TransitionInfo",
    "create_default_scorer",
    # Domain matrices
    "EDUCATION_FEASIBILITY",
    "FINANCE_FEASIBILITY",
    "FLOOD_FEASIBILITY",
    "HEALTH_FEASIBILITY",
]
