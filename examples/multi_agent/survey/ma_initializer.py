"""
MA-Specific Agent Initializer.

Wrapper around the generic broker/modules/survey components that adds:
- MG (Marginalized Group) classification
- Flood experience extensions
- MA-specific statistics

Usage:
    from examples.multi_agent.survey.ma_initializer import initialize_ma_agents_from_survey

    profiles, stats = initialize_ma_agents_from_survey(
        survey_path,
        position_enricher=DepthSampler(seed=42),
        value_enricher=RCVGenerator(seed=42)
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from broker.modules.survey.agent_initializer import AgentProfile
from broker.modules.survey.survey_loader import INCOME_MIDPOINTS

from .flood_survey_loader import FloodSurveyLoader, FloodSurveyRecord
from .mg_classifier import MGClassifier, MGClassificationResult

logger = logging.getLogger(__name__)


@dataclass
class MAAgentProfile(AgentProfile):
    """
    MA-specific agent profile with MG classification and flood extensions.

    Extends the generic AgentProfile with MA-specific fields while maintaining
    backward compatibility with existing MA code.
    """

    # Override classification fields to be MA-specific
    is_classified: bool = False
    classification_score: int = 0
    classification_criteria: Dict[str, bool] = field(default_factory=dict)

    @property
    def is_mg(self) -> bool:
        """MA-specific: True if agent is classified as Marginalized Group."""
        return self.is_classified

    @is_mg.setter
    def is_mg(self, value: bool):
        """Set MG status."""
        self.is_classified = value

    @property
    def mg_score(self) -> int:
        """MA-specific: MG classification score (0-3 criteria met)."""
        return self.classification_score

    @mg_score.setter
    def mg_score(self, value: int):
        """Set MG score."""
        self.classification_score = value

    @property
    def mg_criteria(self) -> Dict[str, bool]:
        """MA-specific: Which MG criteria were met."""
        return self.classification_criteria

    @mg_criteria.setter
    def mg_criteria(self, value: Dict[str, bool]):
        """Set MG criteria."""
        self.classification_criteria = value

    @property
    def group_label(self) -> str:
        """Return 'MG' or 'NMG' for MA classification."""
        return "MG" if self.is_mg else "NMG"

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary with MA-specific flattened flood fields.

        This maintains backward compatibility with existing MA analysis code.
        """
        data = {
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
            "narrative_persona": self.generate_narrative_persona(),
        }

        # Flatten flood extension for MA compatibility
        flood = self.extensions.get("flood")
        if flood is not None:
            data.update({
                "flood_experience": self._ext_value(flood, "flood_experience", False),
                "financial_loss": self._ext_value(flood, "financial_loss", False),
                "flood_zone": self._ext_value(flood, "flood_zone", "unknown"),
                "base_depth_m": self._ext_value(flood, "base_depth_m", 0.0),
                "flood_probability": self._ext_value(flood, "flood_probability", 0.0),
                "building_rcv_usd": self._ext_value(flood, "building_rcv_usd", 0.0),
                "contents_rcv_usd": self._ext_value(flood, "contents_rcv_usd", 0.0),
            })
            data["rcv_kUSD"] = data["building_rcv_usd"] / 1000.0
            data["contents_kUSD"] = data["contents_rcv_usd"] / 1000.0

        return data


def _create_flood_extension(
    flood_experience: bool = False,
    financial_loss: bool = False,
) -> SimpleNamespace:
    """Create a flood extension with default values."""
    return SimpleNamespace(
        flood_experience=flood_experience,
        financial_loss=financial_loss,
        flood_zone="unknown",
        base_depth_m=0.0,
        flood_probability=0.0,
        building_rcv_usd=0.0,
        contents_rcv_usd=0.0,
    )


class MAAgentInitializer:
    """
    MA-specific agent initializer.

    Integrates:
    - Flood survey loading (FloodSurveyLoader)
    - MG classification (MGClassifier)
    - Flood extension management
    """

    def __init__(
        self,
        survey_loader: Optional[FloodSurveyLoader] = None,
        mg_classifier: Optional[MGClassifier] = None,
        seed: int = 42,
        narrative_fields: Optional[List[str]] = None,
        narrative_labels: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize MA agent initializer.

        Args:
            survey_loader: Custom flood survey loader (uses default if None)
            mg_classifier: Custom MG classifier (uses default if None)
            seed: Random seed for reproducibility
            narrative_fields: Fields to include in narrative generation
            narrative_labels: Labels for narrative fields
        """
        self.survey_loader = survey_loader or FloodSurveyLoader()
        self.mg_classifier = mg_classifier or MGClassifier()
        self.seed = seed
        self.narrative_fields = narrative_fields or self.survey_loader.narrative_fields
        self.narrative_labels = narrative_labels or self.survey_loader.narrative_labels

    def load_from_survey(
        self,
        survey_path: Path,
        max_agents: Optional[int] = None,
    ) -> Tuple[List[MAAgentProfile], Dict[str, Any]]:
        """
        Load and initialize MA agents from survey file.

        Args:
            survey_path: Path to survey Excel file
            max_agents: Maximum number of agents to create

        Returns:
            Tuple of (agent_profiles, statistics)
        """
        logger.info(f"Loading MA agents from survey: {survey_path}")

        # Load flood survey records
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

            # Create MA-specific profile
            profile = MAAgentProfile(
                agent_id=f"H{i+1:04d}",
                record_id=record.record_id,
                family_size=record.family_size,
                generations=record.generations,
                income_bracket=record.income_bracket,
                income_midpoint=INCOME_MIDPOINTS.get(record.income_bracket, 50000),
                housing_status=record.housing_status,
                house_type=record.house_type,
                is_classified=mg_result.is_mg,
                classification_score=mg_result.score,
                classification_criteria=mg_result.criteria,
                has_children=record.has_children,
                has_elderly=record.elderly_over_65,
                has_vulnerable_members=record.has_vulnerable_members,
                raw_data=record.raw_data,
                narrative_fields=self.narrative_fields,
                narrative_labels=self.narrative_labels,
            )

            # Add flood extension
            profile.extensions["flood"] = _create_flood_extension(
                flood_experience=record.flood_experience,
                financial_loss=record.financial_loss,
            )

            profiles.append(profile)
            if mg_result.is_mg:
                mg_count += 1

        # Calculate MA-specific statistics
        stats = {
            "total_agents": len(profiles),
            "mg_count": mg_count,
            "nmg_count": len(profiles) - mg_count,
            "mg_ratio": mg_count / len(profiles) if profiles else 0,
            "owner_count": sum(1 for p in profiles if p.is_owner),
            "renter_count": sum(1 for p in profiles if not p.is_owner),
            "flood_experience_count": sum(
                1 for p in profiles
                if p.extensions.get("flood") and p.extensions["flood"].flood_experience
            ),
            "validation_errors": len(self.survey_loader.validation_errors),
        }

        logger.info(
            f"Created {stats['total_agents']} MA agents: "
            f"{stats['mg_count']} MG, {stats['nmg_count']} NMG, "
            f"{stats['owner_count']} owners, {stats['renter_count']} renters"
        )

        return profiles, stats

    def enrich_with_hazard(
        self,
        profiles: List[MAAgentProfile],
        depth_sampler,
    ) -> None:
        """
        Enrich profiles with flood zone and position data.

        Args:
            profiles: List of MAAgentProfile to enrich
            depth_sampler: DepthSampler instance for position assignment
        """
        for profile in profiles:
            position = depth_sampler.assign_position(profile)

            flood_ext = profile.extensions.get("flood")
            if flood_ext is None:
                flood_ext = _create_flood_extension()
                profile.extensions["flood"] = flood_ext

            flood_ext.flood_zone = position.zone_name
            flood_ext.base_depth_m = position.base_depth_m
            flood_ext.flood_probability = position.flood_probability

    def enrich_with_rcv(
        self,
        profiles: List[MAAgentProfile],
        rcv_generator,
    ) -> None:
        """
        Enrich profiles with RCV (Replacement Cost Value) data.

        Args:
            profiles: List of MAAgentProfile to enrich
            rcv_generator: RCVGenerator instance
        """
        for profile in profiles:
            rcv = rcv_generator.generate(
                income_bracket=profile.income_bracket,
                is_owner=profile.is_owner,
                is_mg=profile.is_mg,
                family_size=profile.family_size,
            )

            flood_ext = profile.extensions.get("flood")
            if flood_ext is None:
                flood_ext = _create_flood_extension()
                profile.extensions["flood"] = flood_ext

            flood_ext.building_rcv_usd = rcv.building_rcv_usd
            flood_ext.contents_rcv_usd = rcv.contents_rcv_usd


def initialize_ma_agents_from_survey(
    survey_path: Path,
    max_agents: Optional[int] = None,
    seed: int = 42,
    position_enricher: Optional[Any] = None,
    value_enricher: Optional[Any] = None,
    schema_path: Optional[Path] = None,
    narrative_fields: Optional[List[str]] = None,
    narrative_labels: Optional[Dict[str, str]] = None,
) -> Tuple[List[MAAgentProfile], Dict[str, Any]]:
    """
    Initialize MA agents from survey with MG classification and flood extensions.

    This is the MA-specific entry point that should be used instead of the
    generic broker.modules.survey.initialize_agents_from_survey for MA simulations.

    Args:
        survey_path: Path to survey Excel file
        max_agents: Maximum number of agents
        seed: Random seed
        position_enricher: Optional DepthSampler for flood zone assignment
        value_enricher: Optional RCVGenerator for property values
        schema_path: Optional path to survey schema
        narrative_fields: Optional list of narrative field names
        narrative_labels: Optional mapping of field names to labels

    Returns:
        Tuple of (agent_profiles, statistics)

    Example:
        from examples.multi_agent.survey.ma_initializer import initialize_ma_agents_from_survey
        from examples.multi_agent.environment.depth_sampler import DepthSampler
        from examples.multi_agent.environment.rcv_generator import RCVGenerator

        profiles, stats = initialize_ma_agents_from_survey(
            survey_path,
            position_enricher=DepthSampler(seed=42),
            value_enricher=RCVGenerator(seed=42)
        )
    """
    # Initialize flood survey loader
    survey_loader = FloodSurveyLoader(schema_path=schema_path) if schema_path else FloodSurveyLoader()

    # Initialize MA agent initializer
    initializer = MAAgentInitializer(
        survey_loader=survey_loader,
        seed=seed,
        narrative_fields=narrative_fields,
        narrative_labels=narrative_labels,
    )

    # Load and classify agents
    profiles, stats = initializer.load_from_survey(survey_path, max_agents)

    # Apply enrichers if provided
    if position_enricher is not None:
        initializer.enrich_with_hazard(profiles, position_enricher)

    if value_enricher is not None:
        initializer.enrich_with_rcv(profiles, value_enricher)

    return profiles, stats
