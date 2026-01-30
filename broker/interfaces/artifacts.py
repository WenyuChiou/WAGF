from dataclasses import dataclass, field
from typing import Any, Dict, List, Union


@dataclass
class PolicyArtifact:
    """Government agent structured output."""
    agent_id: str
    year: int
    subsidy_rate: float           # 0.0-1.0
    mg_priority: bool
    budget_remaining: float
    target_adoption_rate: float
    rationale: str

    def validate(self) -> List[str]:
        """Return list of validation errors (empty = valid)."""
        errors = []
        if not (0.0 <= self.subsidy_rate <= 1.0):
            errors.append(f"subsidy_rate out of range: {self.subsidy_rate}")
        if self.budget_remaining < 0:
            errors.append(f"negative budget: {self.budget_remaining}")
        if not (0.0 <= self.target_adoption_rate <= 1.0):
            errors.append(f"target_adoption_rate out of range: {self.target_adoption_rate}")
        return errors

    def to_message_payload(self) -> Dict[str, Any]:
        return {
            "artifact_type": "PolicyArtifact",
            "agent_id": self.agent_id,
            "year": self.year,
            "subsidy_rate": self.subsidy_rate,
            "mg_priority": self.mg_priority,
            "budget_remaining": self.budget_remaining,
            "target_adoption_rate": self.target_adoption_rate,
            "rationale": self.rationale,
        }


@dataclass
class MarketArtifact:
    """Insurance agent structured output."""
    agent_id: str
    year: int
    premium_rate: float           # 0.0-1.0
    payout_ratio: float
    solvency_ratio: float
    loss_ratio: float
    risk_assessment: str

    def validate(self) -> List[str]:
        errors = []
        if not (0.0 <= self.premium_rate <= 1.0):
            errors.append(f"premium_rate out of range: {self.premium_rate}")
        if self.solvency_ratio < 0:
            errors.append(f"negative solvency: {self.solvency_ratio}")
        return errors

    def to_message_payload(self) -> Dict[str, Any]:
        return {
            "artifact_type": "MarketArtifact",
            "agent_id": self.agent_id,
            "year": self.year,
            "premium_rate": self.premium_rate,
            "payout_ratio": self.payout_ratio,
            "solvency_ratio": self.solvency_ratio,
            "loss_ratio": self.loss_ratio,
            "risk_assessment": self.risk_assessment,
        }


@dataclass
class HouseholdIntention:
    """Household agent structured output (PMT-based)."""
    agent_id: str
    year: int
    chosen_skill: str
    tp_level: str                 # VL | L | M | H | VH
    cp_level: str                 # VL | L | M | H | VH
    confidence: float             # 0.0-1.0
    rationale: str

    def validate(self) -> List[str]:
        errors = []
        valid_levels = {"VL", "L", "M", "H", "VH"}
        if self.tp_level not in valid_levels:
            errors.append(f"invalid tp_level: {self.tp_level}")
        if self.cp_level not in valid_levels:
            errors.append(f"invalid cp_level: {self.cp_level}")
        if not (0.0 <= self.confidence <= 1.0):
            errors.append(f"confidence out of range: {self.confidence}")
        return errors

    def to_message_payload(self) -> Dict[str, Any]:
        return {
            "artifact_type": "HouseholdIntention",
            "agent_id": self.agent_id,
            "year": self.year,
            "chosen_skill": self.chosen_skill,
            "tp_level": self.tp_level,
            "cp_level": self.cp_level,
            "confidence": self.confidence,
            "rationale": self.rationale,
        }


@dataclass
class ArtifactEnvelope:
    """Wrapper that converts any artifact into an AgentMessage."""
    artifact: Union[PolicyArtifact, MarketArtifact, HouseholdIntention]
    source_agent: str
    target_scope: str = "global"  # "global" | "regional" | "direct"
    timestamp: int = 0

    def to_agent_message(self):
        """Convert to AgentMessage for MessagePool integration."""
        from broker.interfaces.coordination import AgentMessage, MessageType
        type_map = {
            "PolicyArtifact": MessageType.POLICY_ANNOUNCEMENT,
            "MarketArtifact": MessageType.MARKET_UPDATE,
            "HouseholdIntention": MessageType.NEIGHBOR_WARNING,
        }
        sender_type_map = {
            "PolicyArtifact": "government",
            "MarketArtifact": "insurance",
            "HouseholdIntention": "household",
        }
        payload = self.artifact.to_message_payload()
        artifact_type = payload.get("artifact_type", "unknown")
        rationale = getattr(self.artifact, "rationale", None)
        if rationale is None:
            rationale = getattr(self.artifact, "risk_assessment", "")
        msg = AgentMessage(
            sender_id=self.source_agent,
            sender_type=sender_type_map.get(artifact_type, "unknown"),
            message_type=type_map.get(artifact_type, MessageType.POLICY_ANNOUNCEMENT),
            content=f"[{artifact_type}] {rationale}",
            data=payload,
            timestamp=self.timestamp,
        )
        # Backwards-compat attribute for tests/legacy usage.
        setattr(msg, "sender", self.source_agent)
        setattr(msg, "step", self.timestamp)
        return msg
