"""
Agent Initializer from Survey Data.

Integrates survey loading, MG classification, position assignment,
and RCV generation to create fully initialized agent profiles.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .survey_loader import SurveyLoader, SurveyRecord, INCOME_MIDPOINTS
from .mg_classifier import MGClassifier, MGClassificationResult

logger = logging.getLogger(__name__)


@dataclass
class AgentProfile:
    """Complete agent profile ready for simulation."""

    # Identity
    agent_id: str
    record_id: str  # Original survey record ID

    # Demographics
    family_size: int
    generations: str
    income_bracket: str
    income_midpoint: float
    housing_status: str  # "mortgage", "rent", "own_free"
    house_type: str

    # MG Classification
    is_mg: bool
    mg_score: int
    mg_criteria: Dict[str, bool]

    # Household Composition
    has_children: bool
    has_elderly: bool
    has_vulnerable_members: bool

    # Flood Experience
    flood_experience: bool
    financial_loss: bool

    # Raw survey data for flexible narrative use
    raw_data: Dict[str, Any] = field(default_factory=dict)
    narrative_fields: List[str] = field(default_factory=list)
    narrative_labels: Dict[str, str] = field(default_factory=dict)

    # Position & Exposure (to be filled by hazard module)
    flood_zone: str = "unknown"
    base_depth_m: float = 0.0
    flood_probability: float = 0.0

    # RCV (to be filled by RCV generator)
    building_rcv_usd: float = 0.0
    contents_rcv_usd: float = 0.0

    # Derived identity for framework
    @property
    def identity(self) -> str:
        """Return 'owner' or 'renter' for framework compatibility."""
        return "renter" if self.housing_status == "rent" else "owner"

    @property
    def is_owner(self) -> bool:
        return self.identity == "owner"

    @property
    def group_label(self) -> str:
        return "MG" if self.is_mg else "NMG"

    # Narrative generation
    def generate_narrative_persona(self) -> str:
        """Generate narrative persona text for LLM prompt."""
        if self.narrative_fields:
            parts = []
            for field_name in self.narrative_fields:
                value = getattr(self, field_name, None)
                if value is None:
                    value = self.raw_data.get(field_name)
                if value is None or value == "":
                    continue
                label = self.narrative_labels.get(field_name, field_name.replace("_", " ").capitalize())
                parts.append(f"{label}: {value}")
            if parts:
                return ". ".join(parts) + "."

        parts = []

        # Housing status
        if self.housing_status == "rent":
            parts.append("You are a renter")
        elif self.housing_status == "mortgage":
            parts.append("You are a homeowner with a mortgage")
        else:
            parts.append("You are a homeowner who owns your home outright")

        # Family composition
        if self.family_size == 1:
            parts.append("living alone")
        else:
            parts.append(f"with a family of {self.family_size}")

        # Vulnerable members
        if self.has_children and self.has_elderly:
            parts.append("including children and elderly family members")
        elif self.has_children:
            parts.append("including children")
        elif self.has_elderly:
            parts.append("including elderly family members")

        # Residency
        gen_text = {
            "moved_here": "You recently moved to this area",
            "1": "Your family has lived in this area for one generation",
            "2": "Your family has lived in this area for two generations",
            "3": "Your family has lived in this area for three generations",
            "more_than_3": "Your family has deep roots in this community, having lived here for multiple generations",
        }
        parts.append(gen_text.get(self.generations, ""))

        # MG status context
        if self.is_mg:
            if self.mg_criteria.get("housing_cost_burden"):
                parts.append("Housing costs are a significant burden for your household")

        return ". ".join(filter(None, parts)) + "."

    def generate_flood_experience_summary(self) -> str:
        """Generate flood experience summary for LLM prompt."""
        if not self.flood_experience:
            return "You have not personally experienced flooding in your current home."

        if self.financial_loss:
            return (
                "You have experienced flooding in the past and suffered financial losses. "
                "This experience has made you more aware of flood risks."
            )
        else:
            return (
                "You have experienced flooding in the past, though without major financial losses. "
                "You understand that floods can happen in this area."
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for CSV export or framework use."""
        return {
            "agent_id": self.agent_id,
            "record_id": self.record_id,
            "family_size": self.family_size,
            "generations": self.generations,
            "income_bracket": self.income_bracket,
            "income_midpoint": self.income_midpoint,
            "housing_status": self.housing_status,
            "house_type": self.house_type,
            "identity": self.identity,
            "is_mg": self.is_mg,
            "group": self.group_label,
            "mg_score": self.mg_score,
            "has_children": self.has_children,
            "has_elderly": self.has_elderly,
            "flood_experience": self.flood_experience,
            "financial_loss": self.financial_loss,
            "flood_zone": self.flood_zone,
            "base_depth_m": self.base_depth_m,
            "flood_probability": self.flood_probability,
            "building_rcv_usd": self.building_rcv_usd,
            "contents_rcv_usd": self.contents_rcv_usd,
            "rcv_kUSD": self.building_rcv_usd / 1000.0,
            "contents_kUSD": self.contents_rcv_usd / 1000.0,
            "narrative_persona": self.generate_narrative_persona(),
            "flood_experience_summary": self.generate_flood_experience_summary(),
        }


class AgentInitializer:
    """
    Initialize agents from survey data with full context.

    Integrates:
    - Survey data loading
    - MG classification
    - Position assignment (via hazard module)
    - RCV generation (via RCV generator)
    """

    def __init__(
        self,
        survey_loader: Optional[SurveyLoader] = None,
        mg_classifier: Optional[MGClassifier] = None,
        seed: int = 42,
        narrative_fields: Optional[List[str]] = None,
        narrative_labels: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the agent initializer.

        Args:
            survey_loader: Custom survey loader (uses default if None)
            mg_classifier: Custom MG classifier (uses default if None)
            seed: Random seed for reproducibility
        """
        self.survey_loader = survey_loader or SurveyLoader()
        self.mg_classifier = mg_classifier or MGClassifier()
        self.seed = seed
        self.narrative_fields = narrative_fields or self.survey_loader.narrative_fields
        self.narrative_labels = narrative_labels or self.survey_loader.narrative_labels

    def load_from_survey(
        self,
        survey_path: Path,
        max_agents: Optional[int] = None,
    ) -> Tuple[List[AgentProfile], Dict[str, Any]]:
        """
        Load and initialize agents from survey file.

        Args:
            survey_path: Path to survey Excel file
            max_agents: Maximum number of agents to create

        Returns:
            Tuple of (agent_profiles, statistics)
        """
        logger.info(f"Loading agents from survey: {survey_path}")

        # Load survey records
        records = self.survey_loader.load(
            survey_path,
            max_records=max_agents,
        )

        # Classify and create profiles
        profiles = []
        mg_count = 0

        for i, record in enumerate(records):
            # MG classification
            mg_result = self.mg_classifier.classify(record)

            # Create profile
            profile = AgentProfile(
                agent_id=f"Agent_{i+1:03d}",
                record_id=record.record_id,
                family_size=record.family_size,
                generations=record.generations,
                income_bracket=record.income_bracket,
                income_midpoint=INCOME_MIDPOINTS.get(record.income_bracket, 50000),
                housing_status=record.housing_status,
                house_type=record.house_type,
                is_mg=mg_result.is_mg,
                mg_score=mg_result.score,
                mg_criteria=mg_result.criteria,
                has_children=record.has_children,
                has_elderly=record.elderly_over_65,
                has_vulnerable_members=record.has_vulnerable_members,
                flood_experience=record.flood_experience,
                financial_loss=record.financial_loss,
                raw_data=record.raw_data,
                narrative_fields=self.narrative_fields,
                narrative_labels=self.narrative_labels,
            )

            profiles.append(profile)
            if mg_result.is_mg:
                mg_count += 1

        # Calculate statistics
        stats = {
            "total_agents": len(profiles),
            "mg_count": mg_count,
            "nmg_count": len(profiles) - mg_count,
            "mg_ratio": mg_count / len(profiles) if profiles else 0,
            "owner_count": sum(1 for p in profiles if p.is_owner),
            "renter_count": sum(1 for p in profiles if not p.is_owner),
            "flood_experience_count": sum(1 for p in profiles if p.flood_experience),
            "validation_errors": len(self.survey_loader.validation_errors),
        }

        logger.info(
            f"Created {stats['total_agents']} agents: "
            f"{stats['mg_count']} MG ({stats['mg_ratio']:.1%}), "
            f"{stats['owner_count']} owners, {stats['renter_count']} renters"
        )

        return profiles, stats

    def enrich_with_hazard(
        self,
        profiles: List[AgentProfile],
        depth_sampler,  # DepthSampler instance
    ) -> None:
        """
        Enrich profiles with flood zone and position data.

        Args:
            profiles: List of AgentProfile to enrich
            depth_sampler: DepthSampler instance for position assignment
        """
        for profile in profiles:
            # AgentProfile already has flood_experience and financial_loss attributes
            # which match the FloodExperienceRecord protocol
            position = depth_sampler.assign_position(profile)

            profile.flood_zone = position.zone_name
            profile.base_depth_m = position.base_depth_m
            profile.flood_probability = position.flood_probability

    def enrich_with_rcv(
        self,
        profiles: List[AgentProfile],
        rcv_generator,  # RCVGenerator instance
    ) -> None:
        """
        Enrich profiles with RCV data.

        Args:
            profiles: List of AgentProfile to enrich
            rcv_generator: RCVGenerator instance
        """
        for profile in profiles:
            rcv = rcv_generator.generate(
                income_bracket=profile.income_bracket,
                is_owner=profile.is_owner,
                is_mg=profile.is_mg,
                family_size=profile.family_size,
            )

            profile.building_rcv_usd = rcv.building_rcv_usd
            profile.contents_rcv_usd = rcv.contents_rcv_usd


def initialize_agents_from_survey(
    survey_path: Path,
    max_agents: Optional[int] = None,
    seed: int = 42,
    include_hazard: bool = True,
    include_rcv: bool = True,
    schema_path: Optional[Path] = None,
    narrative_fields: Optional[List[str]] = None,
    narrative_labels: Optional[Dict[str, str]] = None,
) -> Tuple[List[AgentProfile], Dict[str, Any]]:
    """
    Convenience function to initialize agents from survey with full enrichment.

    Args:
        survey_path: Path to survey Excel file
        max_agents: Maximum number of agents
        seed: Random seed
        include_hazard: Whether to add hazard/position data
        include_rcv: Whether to generate RCV values

    Returns:
        Tuple of (agent_profiles, statistics)
    """
    survey_loader = SurveyLoader(schema_path=schema_path) if schema_path else SurveyLoader()
    initializer = AgentInitializer(
        survey_loader=survey_loader,
        seed=seed,
        narrative_fields=narrative_fields,
        narrative_labels=narrative_labels,
    )
    profiles, stats = initializer.load_from_survey(survey_path, max_agents)

    if include_hazard:
        # Import from sibling hazard package (handle both package and script modes)
        try:
            from broker.modules.hazard.depth_sampler import DepthSampler
        except ImportError:
            from ...modules.hazard.depth_sampler import DepthSampler

        sampler = DepthSampler(seed=seed)
        initializer.enrich_with_hazard(profiles, sampler)

    if include_rcv:
        try:
            from broker.modules.hazard.rcv_generator import RCVGenerator
        except ImportError:
            from ...modules.hazard.rcv_generator import RCVGenerator

        gen = RCVGenerator(seed=seed)
        initializer.enrich_with_rcv(profiles, gen)

    return profiles, stats
