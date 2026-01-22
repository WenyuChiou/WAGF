"""
Agent Initializer from Survey Data.

Generic survey-to-agent profile initialization.

Design Pattern (v0.29+):
    Uses Protocol-based dependency injection for enrichers to avoid
    hardcoding domain-specific imports. Enrichers implementing
    PositionEnricher and ValueEnricher protocols can be passed in.

    See broker/interfaces/enrichment.py for protocol definitions.

Domain-Specific Usage:
    For MA (flood simulation), use examples/multi_agent/survey/ma_initializer.py
    which adds MG classification and flood extensions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .survey_loader import SurveyLoader, INCOME_MIDPOINTS

# Protocol types imported for type hints (runtime_checkable not needed for usage)
# Concrete implementations provided by domain-specific code (e.g., examples/multi_agent/)

logger = logging.getLogger(__name__)



@dataclass
class AgentProfile:
    """
    Complete agent profile ready for simulation.

    Generic profile structure. Domain-specific data should be stored
    in the extensions dict (e.g., extensions["flood"] for MA simulation).
    """

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

    # Classification flags (domain-specific classifiers can populate these)
    # e.g., for MA flood sim: is_mg=True means "Marginalized Group"
    # for other domains: can represent any binary classification
    is_classified: bool = False
    classification_score: int = 0
    classification_criteria: Dict[str, bool] = field(default_factory=dict)

    # Legacy aliases for backward compatibility with MA code
    @property
    def is_mg(self) -> bool:
        """Backward compatibility alias for is_classified."""
        return self.is_classified

    @property
    def mg_score(self) -> int:
        """Backward compatibility alias for classification_score."""
        return self.classification_score

    @property
    def mg_criteria(self) -> Dict[str, bool]:
        """Backward compatibility alias for classification_criteria."""
        return self.classification_criteria

    # Household Composition
    has_children: bool = False
    has_elderly: bool = False
    has_vulnerable_members: bool = False

    # Raw survey data for flexible narrative use
    raw_data: Dict[str, Any] = field(default_factory=dict)
    narrative_fields: List[str] = field(default_factory=list)
    narrative_labels: Dict[str, str] = field(default_factory=dict)

    # Extensible domain-specific data
    extensions: Dict[str, Any] = field(default_factory=dict)

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
        """Return classification group label (default: 'A'/'B', override for domain-specific)."""
        return "A" if self.is_classified else "B"

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

        # Classification context (if applicable)
        if self.is_classified:
            if self.classification_criteria.get("housing_cost_burden"):
                parts.append("Housing costs are a significant burden for your household")

        return ". ".join(filter(None, parts)) + "."

    @staticmethod
    def _ext_value(ext: Any, key: str, default: Any = None) -> Any:
        if ext is None:
            return default
        if isinstance(ext, dict):
            return ext.get(key, default)
        return getattr(ext, key, default)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for CSV export or framework use.

        Returns generic profile data. Domain-specific extensions are
        included as nested dicts that callers can flatten if needed.
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

        # Include extensions as nested data (domain-specific code can flatten)
        if self.extensions:
            data["extensions"] = {}
            for ext_key, ext_val in self.extensions.items():
                if hasattr(ext_val, "__dict__"):
                    data["extensions"][ext_key] = vars(ext_val)
                elif isinstance(ext_val, dict):
                    data["extensions"][ext_key] = ext_val
                else:
                    data["extensions"][ext_key] = ext_val

        return data


class AgentInitializer:
    """
    Initialize agents from survey data.

    Generic initialization that creates AgentProfile instances from
    survey records. Domain-specific classification and enrichment
    should be handled by domain-specific wrappers.

    For MA flood simulation, use examples/multi_agent/survey/ma_initializer.py
    """

    def __init__(
        self,
        survey_loader: Optional[SurveyLoader] = None,
        seed: int = 42,
        narrative_fields: Optional[List[str]] = None,
        narrative_labels: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the agent initializer.

        Args:
            survey_loader: Custom survey loader (uses default if None)
            seed: Random seed for reproducibility
            narrative_fields: Fields to include in narrative generation
            narrative_labels: Labels for narrative fields
        """
        self.survey_loader = survey_loader or SurveyLoader()
        self.seed = seed
        self.narrative_fields = narrative_fields or self.survey_loader.narrative_fields
        self.narrative_labels = narrative_labels or self.survey_loader.narrative_labels

    def _create_extensions(self, record) -> Dict[str, Any]:
        """
        Create extensions dict for a record.

        Generic implementation returns empty dict.
        Domain-specific subclasses or wrappers can override to add
        domain-specific extensions.
        """
        return {}

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

        for i, record in enumerate(records):
            # Create profile
            profile = AgentProfile(
                agent_id=f"Agent_{i+1:03d}",
                record_id=record.record_id,
                family_size=record.family_size,
                generations=record.generations,
                income_bracket=record.income_bracket,
                income_midpoint=getattr(record, "income_midpoint", INCOME_MIDPOINTS.get(record.income_bracket, 50000)),
                housing_status=record.housing_status,
                house_type=record.house_type,
                is_mg=False,
                mg_score=0,
                mg_criteria={},
                has_children=record.has_children,
                has_elderly=record.elderly_over_65,
                has_vulnerable_members=record.has_vulnerable_members,
                extensions=self._create_extensions(record),
                raw_data=record.raw_data,
                narrative_fields=self.narrative_fields,
                narrative_labels=self.narrative_labels,
            )

            profiles.append(profile)

        # Calculate generic statistics
        stats = {
            "total_agents": len(profiles),
            "owner_count": sum(1 for p in profiles if p.is_owner),
            "renter_count": sum(1 for p in profiles if not p.is_owner),
            "validation_errors": len(self.survey_loader.validation_errors),
        }

        logger.info(
            f"Created {stats['total_agents']} agents: "
            f"{stats['owner_count']} owners, {stats['renter_count']} renters"
        )

        return profiles, stats

    def enrich_with_position(
        self,
        profiles: List[AgentProfile],
        position_enricher,
        extension_key: str = "position",
    ) -> None:
        """
        Enrich profiles with position data using a generic enricher.

        Args:
            profiles: List of AgentProfile to enrich
            position_enricher: Enricher implementing assign_position(profile) -> PositionData
            extension_key: Key to store position data in extensions (default: "position")
        """
        for profile in profiles:
            position = position_enricher.assign_position(profile)
            profile.extensions[extension_key] = position

    def enrich_with_values(
        self,
        profiles: List[AgentProfile],
        value_enricher,
        extension_key: str = "values",
    ) -> None:
        """
        Enrich profiles with value data using a generic enricher.

        Args:
            profiles: List of AgentProfile to enrich
            value_enricher: Enricher implementing generate(...) -> ValueData
            extension_key: Key to store value data in extensions (default: "values")
        """
        for profile in profiles:
            values = value_enricher.generate(
                income_bracket=profile.income_bracket,
                is_owner=profile.is_owner,
                is_mg=profile.is_mg,
                family_size=profile.family_size,
            )
            profile.extensions[extension_key] = values


def initialize_agents_from_survey(
    survey_path: Path,
    max_agents: Optional[int] = None,
    seed: int = 42,
    position_enricher: Optional[Any] = None,
    value_enricher: Optional[Any] = None,
    schema_path: Optional[Path] = None,
    narrative_fields: Optional[List[str]] = None,
    narrative_labels: Optional[Dict[str, str]] = None,
) -> Tuple[List[AgentProfile], Dict[str, Any]]:
    """
    Convenience function to initialize agents from survey with optional enrichment.

    Generic initialization that creates AgentProfile instances.
    For domain-specific initialization (e.g., MA flood simulation with MG
    classification), use the domain-specific wrapper instead.

    Args:
        survey_path: Path to survey Excel file
        max_agents: Maximum number of agents
        seed: Random seed
        position_enricher: Optional enricher implementing PositionEnricher protocol
        value_enricher: Optional enricher implementing ValueEnricher protocol
        schema_path: Optional path to survey schema
        narrative_fields: Optional list of narrative field names
        narrative_labels: Optional mapping of field names to labels

    Returns:
        Tuple of (agent_profiles, statistics)

    Example:
        # Generic initialization
        profiles, stats = initialize_agents_from_survey(survey_path)

        # With custom enrichers
        profiles, stats = initialize_agents_from_survey(
            survey_path,
            position_enricher=MyPositionEnricher(),
            value_enricher=MyValueEnricher()
        )

    For MA flood simulation:
        Use examples/multi_agent/survey/ma_initializer.py instead
    """
    # Initialize from survey
    survey_loader = SurveyLoader(schema_path=schema_path) if schema_path else SurveyLoader()
    initializer = AgentInitializer(
        survey_loader=survey_loader,
        seed=seed,
        narrative_fields=narrative_fields,
        narrative_labels=narrative_labels,
    )
    profiles, stats = initializer.load_from_survey(survey_path, max_agents)

    # Apply enrichers if provided (protocol-based API)
    if position_enricher is not None:
        initializer.enrich_with_position(profiles, position_enricher)

    if value_enricher is not None:
        initializer.enrich_with_values(profiles, value_enricher)

    return profiles, stats
