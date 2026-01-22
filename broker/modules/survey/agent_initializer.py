"""
Agent Initializer from Survey Data.

Integrates survey loading, MG classification, position assignment,
and RCV generation to create fully initialized agent profiles.

Design Pattern (v0.29+):
    Uses Protocol-based dependency injection for enrichers to avoid
    hardcoding domain-specific imports. Enrichers implementing
    PositionEnricher and ValueEnricher protocols can be passed in.

    See broker/interfaces/enrichment.py for protocol definitions.
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



def _create_flood_extension(flood_experience: bool, financial_loss: bool):
    """
    DEPRECATION BRIDGE: Create flood extension (MA-specific).

    TODO(v0.30): Move this to examples/multi_agent/survey/ after full migration.
    Currently kept here for backward compatibility with existing workflows.
    """
    from types import SimpleNamespace
    return SimpleNamespace(
        flood_experience=flood_experience,
        financial_loss=financial_loss,
        flood_zone="unknown",
        base_depth_m=0.0,
        flood_probability=0.0,
        building_rcv_usd=0.0,
        contents_rcv_usd=0.0,
    )


def _set_ext_value(ext, key: str, value):
    if isinstance(ext, dict):
        ext[key] = value
    else:
        setattr(ext, key, value)


def _get_ext_value(ext, key: str, default=None):
    if ext is None:
        return default
    if isinstance(ext, dict):
        return ext.get(key, default)
    return getattr(ext, key, default)


@dataclass

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

    @staticmethod
    def _ext_value(ext: Any, key: str, default: Any = None) -> Any:
        if ext is None:
            return default
        if isinstance(ext, dict):
            return ext.get(key, default)
        return getattr(ext, key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for CSV export or framework use."""
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
        self.seed = seed
        self.narrative_fields = narrative_fields or self.survey_loader.narrative_fields
        self.narrative_labels = narrative_labels or self.survey_loader.narrative_labels

    def _create_extensions(self, record) -> Dict[str, Any]:
        """
        Create extensions dict based on record type (generic or domain-specific).

        Auto-detects record type by checking for domain-specific fields.
        TODO(v0.30): Make this fully pluggable via extension registry.
        """
        extensions = {}

        # Check if record has flood-specific fields (FloodSurveyRecord)
        # DEPRECATION BRIDGE: This should be moved to MA-specific initialization
        if hasattr(record, "flood_experience") and hasattr(record, "financial_loss"):
            extensions["flood"] = _create_flood_extension(
                record.flood_experience,
                record.financial_loss
            )

        return extensions

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
        # Calculate statistics
        stats = {
            "total_agents": len(profiles),
            "owner_count": sum(1 for p in profiles if p.is_owner),
            "renter_count": sum(1 for p in profiles if not p.is_owner),
            "flood_experience_count": sum(1 for p in profiles if _get_ext_value(p.extensions.get("flood"), "flood_experience", False)),
            "validation_errors": len(self.survey_loader.validation_errors),
        }

        logger.info(
            f"Created {stats['total_agents']} agents: "
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
            # Flood experience data stored in profile.extensions["flood"]
            # which match the FloodExperienceRecord protocol
            position = depth_sampler.assign_position(profile)

            flood_ext = profile.extensions.get("flood") or _create_flood_extension(False, False)
            profile.extensions["flood"] = flood_ext
            _set_ext_value(flood_ext, "flood_zone", position.zone_name)
            _set_ext_value(flood_ext, "base_depth_m", position.base_depth_m)
            _set_ext_value(flood_ext, "flood_probability", position.flood_probability)

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

            flood_ext = profile.extensions.get("flood") or _create_flood_extension(False, False)
            profile.extensions["flood"] = flood_ext
            _set_ext_value(flood_ext, "building_rcv_usd", rcv.building_rcv_usd)
            _set_ext_value(flood_ext, "contents_rcv_usd", rcv.contents_rcv_usd)


def initialize_agents_from_survey(
    survey_path: Path,
    max_agents: Optional[int] = None,
    seed: int = 42,
    position_enricher: Optional[Any] = None,
    value_enricher: Optional[Any] = None,
    include_hazard: bool = None,  # DEPRECATED
    include_rcv: bool = None,  # DEPRECATED
    schema_path: Optional[Path] = None,
    narrative_fields: Optional[List[str]] = None,
    narrative_labels: Optional[Dict[str, str]] = None,
) -> Tuple[List[AgentProfile], Dict[str, Any]]:
    """
    Convenience function to initialize agents from survey with optional enrichment.

    Args:
        survey_path: Path to survey Excel file
        max_agents: Maximum number of agents
        seed: Random seed
        position_enricher: Optional enricher implementing PositionEnricher protocol
                          (e.g., DepthSampler for flood sim, LocationSampler for trading)
        value_enricher: Optional enricher implementing ValueEnricher protocol
                       (e.g., RCVGenerator for flood sim, PortfolioGenerator for trading)
        include_hazard: DEPRECATED - use position_enricher instead
        include_rcv: DEPRECATED - use value_enricher instead
        schema_path: Optional path to survey schema
        narrative_fields: Optional list of narrative field names
        narrative_labels: Optional mapping of field names to labels

    Returns:
        Tuple of (agent_profiles, statistics)

    Migration Guide:
        # Old API (deprecated)
        profiles, stats = initialize_agents_from_survey(
            survey_path, include_hazard=True, include_rcv=True
        )

        # New API (recommended)
        from examples.multi_agent.environment.depth_sampler import DepthSampler
        from examples.multi_agent.environment.rcv_generator import RCVGenerator
        profiles, stats = initialize_agents_from_survey(
            survey_path,
            position_enricher=DepthSampler(seed=42),
            value_enricher=RCVGenerator(seed=42)
        )
    """
    # Handle deprecated parameters
    import warnings
    if include_hazard is not None:
        warnings.warn(
            "include_hazard is deprecated and will be removed in v0.30. "
            "Pass position_enricher instead (e.g., DepthSampler(seed=42)).",
            DeprecationWarning,
            stacklevel=2
        )
        if include_hazard and position_enricher is None:
            # Fallback: Try to import for backward compatibility
            try:
                import sys
                from pathlib import Path as _Path
                _env_path = _Path(__file__).resolve().parents[3] / 'examples' / 'multi_agent' / 'environment'
                if str(_env_path) not in sys.path:
                    sys.path.insert(0, str(_env_path))
                from depth_sampler import DepthSampler
                position_enricher = DepthSampler(seed=seed)
                logger.warning("Using legacy include_hazard=True. Migrate to position_enricher parameter.")
            except ImportError as e:
                logger.warning(f'Hazard enrichment skipped: {e}')

    if include_rcv is not None:
        warnings.warn(
            "include_rcv is deprecated and will be removed in v0.30. "
            "Pass value_enricher instead (e.g., RCVGenerator(seed=42)).",
            DeprecationWarning,
            stacklevel=2
        )
        if include_rcv and value_enricher is None:
            # Fallback: Try to import for backward compatibility
            try:
                import sys
                from pathlib import Path as _Path
                _env_path = _Path(__file__).resolve().parents[3] / 'examples' / 'multi_agent' / 'environment'
                if str(_env_path) not in sys.path:
                    sys.path.insert(0, str(_env_path))
                from rcv_generator import RCVGenerator
                value_enricher = RCVGenerator(seed=seed)
                logger.warning("Using legacy include_rcv=True. Migrate to value_enricher parameter.")
            except ImportError as e:
                logger.warning(f'RCV enrichment skipped: {e}')

    # Initialize from survey
    survey_loader = SurveyLoader(schema_path=schema_path) if schema_path else SurveyLoader()
    initializer = AgentInitializer(
        survey_loader=survey_loader,
        seed=seed,
        narrative_fields=narrative_fields,
        narrative_labels=narrative_labels,
    )
    profiles, stats = initializer.load_from_survey(survey_path, max_agents)

    # Apply enrichers if provided (new protocol-based API)
    if position_enricher is not None:
        initializer.enrich_with_hazard(profiles, position_enricher)

    if value_enricher is not None:
        initializer.enrich_with_rcv(profiles, value_enricher)

    return profiles, stats
