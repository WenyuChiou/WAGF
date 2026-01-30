"""
Generic cross-agent validation for multi-agent coordination.

Provides domain-agnostic checks:
- echo_chamber_check: Detects homogeneous decision-making (Shannon entropy)
- deadlock_check: Detects high rejection rates in action resolutions

Domain-specific checks (e.g. perverse incentive, budget coherence) are
injected via the ``domain_rules`` constructor parameter. Each rule is
a callable: (artifacts: Dict, prev_artifacts: Optional[Dict]) -> Optional[CrossValidationResult]

Reference: Task-058B (Cross-Agent Validation & Arbitration)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional
import math

from broker.interfaces.artifacts import AgentArtifact
from broker.interfaces.coordination import ActionResolution


# ---------------------------------------------------------------------------
# Cross-agent validation result types
# ---------------------------------------------------------------------------

class ValidationLevel(Enum):
    """Severity level for cross-agent validation results."""
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class CrossValidationResult:
    """Result from a cross-agent validation check.

    Distinct from ``broker.interfaces.skill_types.ValidationResult`` which
    is for single-agent skill validation. This type represents pattern
    detection across multiple agents.
    """
    is_valid: bool
    level: ValidationLevel
    rule_id: str
    message: str

# Type alias for pluggable domain rules
DomainRule = Callable[[Dict, Optional[Dict]], Optional[CrossValidationResult]]


class CrossAgentValidator:
    """Validates inter-agent consistency and detects pathological patterns.

    Generic checks (echo_chamber, deadlock) work with any AgentArtifact subclass.
    Domain-specific checks are injected via ``domain_rules``.

    Args:
        echo_threshold: Fraction above which a single skill is flagged (default 0.8)
        entropy_threshold: Shannon entropy (bits) below which diversity is flagged (default 0.5)
        deadlock_threshold: Rejection rate above which deadlock is flagged (default 0.5)
        domain_rules: List of callables for domain-specific checks
    """

    def __init__(
        self,
        echo_threshold: float = 0.8,
        entropy_threshold: float = 0.5,
        deadlock_threshold: float = 0.5,
        domain_rules: Optional[List[DomainRule]] = None,
    ):
        self.echo_threshold = echo_threshold
        self.entropy_threshold = entropy_threshold
        self.deadlock_threshold = deadlock_threshold
        self.domain_rules: List[DomainRule] = domain_rules or []
        self.history: List[Dict] = []

    # ------------------------------------------------------------------
    # Generic checks
    # ------------------------------------------------------------------

    def echo_chamber_check(
        self, intentions: List[AgentArtifact],
        skill_accessor: str = "chosen_skill",
    ) -> CrossValidationResult:
        """Check if > echo_threshold of agents chose the same action.

        Also computes Shannon entropy and flags if < entropy_threshold.

        Args:
            intentions: List of individual-agent artifacts
            skill_accessor: Attribute name to read the chosen skill from each artifact
        """
        if not intentions:
            return CrossValidationResult(
                is_valid=True, level=ValidationLevel.INFO,
                rule_id="ECHO_CHAMBER",
                message="Echo chamber check skipped: No intentions provided.",
            )

        skill_counts: Dict[str, int] = {}
        for intention in intentions:
            skill = getattr(intention, skill_accessor, None)
            if skill is not None:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1

        total = len(intentions)
        if total == 0:
            return CrossValidationResult(
                is_valid=True, level=ValidationLevel.INFO,
                rule_id="ECHO_CHAMBER", message="Echo chamber check: no valid intentions.",
            )

        # Find dominant skill
        max_count = 0
        dominant_skill = None
        for skill, count in skill_counts.items():
            if count > max_count:
                max_count = count
                dominant_skill = skill

        if dominant_skill and (max_count / total) > self.echo_threshold:
            return CrossValidationResult(
                is_valid=False, level=ValidationLevel.WARNING,
                rule_id="ECHO_CHAMBER_DETECTED",
                message=f"Echo chamber: {max_count / total:.0%} chose '{dominant_skill}'.",
            )

        # Shannon entropy (bits)
        entropy = 0.0
        for count in skill_counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        if entropy < self.entropy_threshold:
            return CrossValidationResult(
                is_valid=False, level=ValidationLevel.WARNING,
                rule_id="LOW_DECISION_ENTROPY",
                message=f"Decision entropy {entropy:.2f} bits below threshold "
                        f"({self.entropy_threshold:.2f} bits).",
            )

        return CrossValidationResult(
            is_valid=True, level=ValidationLevel.INFO,
            rule_id="ECHO_CHAMBER", message="Echo chamber check passed.",
        )

    def deadlock_check(
        self, resolutions: List[ActionResolution],
    ) -> CrossValidationResult:
        """Check if > deadlock_threshold of proposals were rejected."""
        if not resolutions:
            return CrossValidationResult(
                is_valid=True, level=ValidationLevel.INFO,
                rule_id="DEADLOCK",
                message="Deadlock check skipped: No resolutions provided.",
            )

        rejected = sum(1 for r in resolutions if not r.approved)
        rate = rejected / len(resolutions)

        if rate > self.deadlock_threshold:
            return CrossValidationResult(
                is_valid=False, level=ValidationLevel.WARNING,
                rule_id="DEADLOCK_RISK",
                message=f"Deadlock risk: {rate:.0%} proposals rejected "
                        f"(threshold {self.deadlock_threshold:.0%}).",
            )

        return CrossValidationResult(
            is_valid=True, level=ValidationLevel.INFO,
            rule_id="DEADLOCK", message="Deadlock check passed.",
        )

    # ------------------------------------------------------------------
    # Domain rule execution
    # ------------------------------------------------------------------

    def run_domain_checks(
        self,
        artifacts: Dict,
        prev_artifacts: Optional[Dict] = None,
    ) -> List[CrossValidationResult]:
        """Execute all registered domain-specific rules.

        Each rule receives (artifacts, prev_artifacts) and returns
        an Optional[ValidationResult]. Non-valid results are collected.
        """
        results: List[CrossValidationResult] = []
        for rule in self.domain_rules:
            result = rule(artifacts, prev_artifacts)
            if result is not None and not result.is_valid:
                results.append(result)
        return results

    # ------------------------------------------------------------------
    # Aggregate validation
    # ------------------------------------------------------------------

    def validate_round(
        self,
        artifacts: Dict,
        resolutions: Optional[List[ActionResolution]] = None,
        prev_artifacts: Optional[Dict] = None,
        intentions_key: str = "intentions",
        skill_accessor: str = "chosen_skill",
    ) -> List[CrossValidationResult]:
        """Run all generic + domain checks and return non-valid results.

        Args:
            artifacts: Dict of current-round artifacts keyed by role/type
            resolutions: List of ActionResolution from GameMaster
            prev_artifacts: Dict of previous-round artifacts (for trend checks)
            intentions_key: Key in artifacts dict containing individual agent intentions
            skill_accessor: Attribute name on intention artifacts for the chosen skill
        """
        results: List[CrossValidationResult] = []

        # 1. Echo chamber check
        intentions = artifacts.get(intentions_key, [])
        if intentions:
            ec = self.echo_chamber_check(intentions, skill_accessor=skill_accessor)
            if not ec.is_valid:
                results.append(ec)

        # 2. Deadlock check
        if resolutions:
            dl = self.deadlock_check(resolutions)
            if not dl.is_valid:
                results.append(dl)

        # 3. Domain-specific checks
        results.extend(self.run_domain_checks(artifacts, prev_artifacts))

        # Store in history
        self.history.append({
            "results": [
                {"rule_id": r.rule_id, "level": r.level.value, "message": r.message}
                for r in results
            ],
        })

        return results
