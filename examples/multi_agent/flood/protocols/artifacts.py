"""
Flood-domain artifact subclasses for multi-agent structured communication.

These are the domain-specific implementations of AgentArtifact:
- PolicyArtifact: Government agent output (subsidy, budget, adoption targets)
- MarketArtifact: Insurance agent output (premium, loss ratio, solvency)
- HouseholdIntention: Household agent output (PMT-based skill choice)

Generic base: broker.interfaces.artifacts.AgentArtifact

Reference: Task-058A (Structured Artifact Protocols)
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


from broker.interfaces.artifacts import (
    AgentArtifact,
    register_artifact_routing,
    register_artifact_dispatch_rule,
)


# ---------------------------------------------------------------------------
# Government Agent
# ---------------------------------------------------------------------------

@dataclass
class PolicyArtifact(AgentArtifact):
    """Government agent structured output.

    Fields:
        subsidy_rate: Fraction of eligible households receiving subsidy (0.0-1.0)
        mg_priority: Whether to prioritize marginalized groups
        budget_remaining: Remaining budget for subsidies
        target_adoption_rate: Desired adoption rate for protective measures (0.0-1.0)
    """
    subsidy_rate: float = 0.0
    mg_priority: bool = False
    budget_remaining: float = 0.0
    target_adoption_rate: float = 0.0

    def artifact_type(self) -> str:
        return "PolicyArtifact"

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not (0.0 <= self.subsidy_rate <= 1.0):
            errors.append(f"subsidy_rate out of range: {self.subsidy_rate}")
        if self.budget_remaining < 0:
            errors.append(f"negative budget: {self.budget_remaining}")
        if not (0.0 <= self.target_adoption_rate <= 1.0):
            errors.append(f"target_adoption_rate out of range: {self.target_adoption_rate}")
        return errors


# ---------------------------------------------------------------------------
# Insurance Agent
# ---------------------------------------------------------------------------

@dataclass
class MarketArtifact(AgentArtifact):
    """Insurance agent structured output.

    Fields:
        premium_rate: Insurance premium rate (0.0-1.0)
        payout_ratio: Fraction of claims paid out
        solvency_ratio: Ratio of assets to liabilities
        loss_ratio: Claims paid / premiums collected
        risk_assessment: Free-text risk summary
    """
    premium_rate: float = 0.0
    payout_ratio: float = 0.0
    solvency_ratio: float = 1.0
    loss_ratio: float = 0.0
    risk_assessment: str = ""

    def artifact_type(self) -> str:
        return "MarketArtifact"

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not (0.0 <= self.premium_rate <= 1.0):
            errors.append(f"premium_rate out of range: {self.premium_rate}")
        if self.solvency_ratio < 0:
            errors.append(f"negative solvency: {self.solvency_ratio}")
        return errors


# ---------------------------------------------------------------------------
# Household Agent
# ---------------------------------------------------------------------------

@dataclass
class HouseholdIntention(AgentArtifact):
    """Household agent structured output (PMT-based).

    Fields:
        chosen_skill: Selected action (e.g. "buy_insurance", "relocate", "elevate_house")
        tp_level: Threat perception level (VL | L | M | H | VH)
        cp_level: Coping perception level (VL | L | M | H | VH)
        confidence: Decision confidence (0.0-1.0)
    """
    chosen_skill: str = ""
    tp_level: str = "M"
    cp_level: str = "M"
    confidence: float = 0.5

    _VALID_LEVELS = {"VL", "L", "M", "H", "VH"}

    def artifact_type(self) -> str:
        return "HouseholdIntention"

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.tp_level not in self._VALID_LEVELS:
            errors.append(f"invalid tp_level: {self.tp_level}")
        if self.cp_level not in self._VALID_LEVELS:
            errors.append(f"invalid cp_level: {self.cp_level}")
        if not (0.0 <= self.confidence <= 1.0):
            errors.append(f"confidence out of range: {self.confidence}")
        return errors


# Phase 6J-C (2026-05-22): artifact routing is domain-owned.
register_artifact_routing("PolicyArtifact", "POLICY_ANNOUNCEMENT", "government")
register_artifact_routing("MarketArtifact", "MARKET_UPDATE", "insurance")
register_artifact_routing("HouseholdIntention", "NEIGHBOR_WARNING", "household")

# Phase 6U-E-2 (2026-05-28): coordinator dispatch is also domain-owned.
# Pre-6U-E-2 the coordinator hardcoded these three names; now they're
# registered alongside the message-type routing above.
register_artifact_dispatch_rule("PolicyArtifact", bucket="policy", mode="single")
register_artifact_dispatch_rule("MarketArtifact", bucket="market", mode="single")
register_artifact_dispatch_rule(
    "HouseholdIntention", bucket="intentions", mode="append"
)
