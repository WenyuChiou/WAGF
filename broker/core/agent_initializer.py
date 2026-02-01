"""
Unified Agent Initializer for SA/MA experiments.

Provides a single entry point for initializing agents from various data sources:
- survey: Load from Excel/CSV with psychological scores
- csv: Simple CSV with basic attributes
- synthetic: Generate test agents programmatically

AgentProfile contains generic fields plus flood-domain fields for backward
compatibility.  New domains should use the ``extensions`` dict for
domain-specific data.  See ``examples/governed_flood/`` for flood-specific
usage and ``examples/irrigation_abm/`` for irrigation examples.

Usage:
    from broker.core.agent_initializer import initialize_agents

    # Survey mode (from questionnaire data)
    profiles, memories, stats = initialize_agents(
        mode="survey",
        path=Path("data/survey.xlsx"),
        config={"domain": "flood"},
        enrichers={"position": depth_sampler, "value": rcv_gen},
    )

    # CSV mode (simple profiles)
    profiles, memories, stats = initialize_agents(
        mode="csv",
        path=Path("data/agents.csv"),
        config={},
    )

    # Synthetic mode (for testing)
    profiles, memories, stats = initialize_agents(
        mode="synthetic",
        path=None,
        config={"n_agents": 100, "mg_ratio": 0.16},
    )
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Protocol, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# =============================================================================
# PROTOCOLS (for enricher dependency injection)
# =============================================================================


class Enricher(Protocol):
    """Base protocol for agent profile enrichment."""

    def enrich(self, profile: "AgentProfile") -> None:
        """Enrich a profile in-place with additional data."""
        ...


class PositionEnricher(Protocol):
    """Protocol for assigning spatial positions to agents."""

    def assign_position(self, profile: Any) -> Any:
        """Assign spatial position data to an agent profile."""
        ...


class ValueEnricher(Protocol):
    """Protocol for calculating agent asset values."""

    def generate(
        self, income_bracket: str, is_owner: bool, is_mg: bool, family_size: int
    ) -> Any:
        """Generate asset values for an agent."""
        ...


class MemoryEnricher(Protocol):
    """Protocol for generating initial memories from profile data."""

    def generate_all(self, profile_dict: Dict[str, Any]) -> List[Any]:
        """Generate all initial memory templates for a profile."""
        ...


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class AgentProfile:
    """
    Unified agent profile for SA/MA experiments.

    This is a consolidated profile structure that supports both simple CSV
    initialization and full survey-based PMT/psychological scores.

    Domain-specific fields (flood_zone, elevated, etc.) are kept for
    backward compatibility with existing experiments.  New domains should
    use the ``extensions`` dict instead.
    """

    # --- Identity ---
    agent_id: str
    record_id: str = ""  # Original survey/source ID

    # --- Demographics ---
    family_size: int = 3
    generations: str = "1"  # "moved_here", "1", "2", "3", "more_than_3"
    income_bracket: str = "50k_to_60k"
    income: float = 55000.0  # Estimated midpoint ($)
    housing_status: str = "mortgage"  # "mortgage", "rent", "own_free"
    house_type: str = "single_family"
    tenure: Literal["Owner", "Renter"] = "Owner"

    # --- Classification (MG/vulnerability status) ---
    is_mg: bool = False
    mg_score: int = 0
    mg_criteria: Dict[str, bool] = field(default_factory=dict)

    # --- Household Composition ---
    has_children: bool = False
    has_elderly: bool = False
    has_vehicle: bool = True
    housing_cost_burden: bool = False

    # --- Psychological Constructs (1-5 scale, framework-level) ---
    tp_score: float = 3.0  # Threat Perception
    cp_score: float = 3.0  # Coping Perception
    sp_score: float = 3.0  # Stakeholder Perception
    sc_score: float = 3.0  # Social Capital
    pa_score: float = 3.0  # Place Attachment

    # --- Domain-specific fields (flood, kept for backward compat) ---
    flood_experience: bool = False
    flood_frequency: int = 0
    sfha_awareness: bool = False
    flood_zone: str = "MEDIUM"  # HIGH, MEDIUM, LOW
    flood_depth: float = 0.0

    # --- Dynamic State (initial, flood-domain) ---
    elevated: bool = False
    has_insurance: bool = False
    relocated: bool = False
    cumulative_damage: float = 0.0

    # --- Spatial ---
    grid_x: int = 0
    grid_y: int = 0
    longitude: float = 0.0
    latitude: float = 0.0

    # --- Asset Values ---
    rcv_building: float = 0.0  # Replacement cost - building ($)
    rcv_contents: float = 0.0  # Replacement cost - contents ($)

    # --- Extensions (for domain-specific data — preferred for new domains) ---
    extensions: Dict[str, Any] = field(default_factory=dict)

    # --- Narrative metadata (flood-domain) ---
    recent_flood_text: str = ""
    insurance_type: str = ""
    post_flood_action: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def identity(self) -> str:
        """Return 'owner' or 'renter' for framework compatibility."""
        return "renter" if self.housing_status == "rent" else "owner"

    @property
    def is_owner(self) -> bool:
        return self.identity == "owner"

    @property
    def group_label(self) -> str:
        """Return MG group label."""
        return "MG" if self.is_mg else "NMG"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization or memory generation."""
        return asdict(self)


# =============================================================================
# LOADERS
# =============================================================================


class CSVLoader:
    """Load agent profiles from simple CSV file."""

    # Default column mappings (can be overridden in config)
    DEFAULT_COLUMNS = {
        "agent_id": ["agent_id", "id", "AgentID"],
        "family_size": ["family_size", "household_size", "FamilySize"],
        "income": ["income", "Income", "annual_income"],
        "income_bracket": ["income_bracket", "IncomeBracket"],
        "tenure": ["tenure", "Tenure", "housing_status"],
        "is_mg": ["is_mg", "mg", "MG", "marginalized"],
        "tp_score": ["tp_score", "TP", "threat_perception"],
        "cp_score": ["cp_score", "CP", "coping_perception"],
        "sp_score": ["sp_score", "SP", "stakeholder_perception"],
        "sc_score": ["sc_score", "SC", "social_capital"],
        "pa_score": ["pa_score", "PA", "place_attachment"],
        "flood_experience": ["flood_experience", "has_flood_experience"],
        "flood_zone": ["flood_zone", "zone"],
        "has_insurance": ["has_insurance", "insurance"],
        "elevated": ["elevated", "is_elevated"],
    }

    def __init__(self, column_mappings: Optional[Dict[str, List[str]]] = None):
        self.column_mappings = column_mappings or self.DEFAULT_COLUMNS

    def _find_column(self, df: pd.DataFrame, field: str) -> Optional[str]:
        """Find actual column name in DataFrame for a field."""
        candidates = self.column_mappings.get(field, [field])
        for candidate in candidates:
            if candidate in df.columns:
                return candidate
        return None

    def load(self, path: Path, config: Dict[str, Any]) -> List[AgentProfile]:
        """Load profiles from CSV file."""
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")

        df = pd.read_csv(path)
        logger.info(f"Loading {len(df)} agents from CSV: {path}")

        profiles = []
        for idx, row in df.iterrows():
            profile = self._parse_row(idx, row, config)
            if profile:
                profiles.append(profile)

        logger.info(f"Loaded {len(profiles)} valid agent profiles")
        return profiles

    def _parse_row(
        self, idx: int, row: pd.Series, config: Dict[str, Any]
    ) -> Optional[AgentProfile]:
        """Parse a single CSV row into AgentProfile."""

        def get_val(field: str, default: Any = None) -> Any:
            col = self._find_column(row.index.tolist(), field)
            if col and col in row.index:
                val = row[col]
                if pd.isna(val):
                    return default
                return val
            return default

        agent_id = get_val("agent_id", f"Agent_{idx + 1:03d}")

        # Parse tenure/housing status
        tenure_raw = get_val("tenure", "Owner")
        tenure = "Owner" if str(tenure_raw).lower() in ["owner", "mortgage", "own_free"] else "Renter"
        housing_status = "rent" if tenure == "Renter" else "mortgage"

        return AgentProfile(
            agent_id=str(agent_id),
            record_id=f"CSV_{idx:04d}",
            family_size=int(get_val("family_size", 3)),
            income=float(get_val("income", 55000)),
            income_bracket=str(get_val("income_bracket", "50k_to_60k")),
            housing_status=housing_status,
            tenure=tenure,
            is_mg=bool(get_val("is_mg", False)),
            tp_score=float(get_val("tp_score", 3.0)),
            cp_score=float(get_val("cp_score", 3.0)),
            sp_score=float(get_val("sp_score", 3.0)),
            sc_score=float(get_val("sc_score", 3.0)),
            pa_score=float(get_val("pa_score", 3.0)),
            flood_experience=bool(get_val("flood_experience", False)),
            flood_zone=str(get_val("flood_zone", "MEDIUM")),
            has_insurance=bool(get_val("has_insurance", False)),
            elevated=bool(get_val("elevated", False)),
            raw_data=row.to_dict(),
        )

    def _find_column(
        self, columns: List[str], field: str
    ) -> Optional[str]:
        """Find column by field name using mapping."""
        candidates = self.column_mappings.get(field, [field])
        for candidate in candidates:
            if candidate in columns:
                return candidate
        return None


class SurveyLoader:
    """Load agent profiles from survey data (Excel/CSV with PMT scores)."""

    def __init__(self, domain: str = "flood"):
        self.domain = domain

    def load(self, path: Path, config: Dict[str, Any]) -> List[AgentProfile]:
        """Load profiles from survey file."""
        # Try to use the existing broker survey loader
        try:
            from broker.modules.survey.agent_initializer import (
                AgentInitializer as ExistingInitializer,
            )
            from broker.modules.survey.survey_loader import SurveyLoader as ExistingSurveyLoader

            existing_loader = ExistingSurveyLoader()
            existing_initializer = ExistingInitializer(survey_loader=existing_loader)
            existing_profiles, _ = existing_initializer.load_from_survey(
                path, max_agents=config.get("max_agents")
            )

            # Convert to our unified AgentProfile format
            profiles = []
            for ep in existing_profiles:
                profile = AgentProfile(
                    agent_id=ep.agent_id,
                    record_id=ep.record_id,
                    family_size=ep.family_size,
                    generations=ep.generations,
                    income_bracket=ep.income_bracket,
                    income=ep.income_midpoint,
                    housing_status=ep.housing_status,
                    tenure="Owner" if ep.is_owner else "Renter",
                    is_mg=ep.is_mg,
                    mg_score=ep.mg_score,
                    mg_criteria=ep.mg_criteria,
                    has_children=ep.has_children,
                    has_elderly=ep.has_elderly,
                    raw_data=ep.raw_data,
                    extensions=ep.extensions,
                )
                profiles.append(profile)

            return profiles
        except ImportError:
            # Fall back to direct loading if survey module not available
            return self._load_direct(path, config)

    def _load_direct(self, path: Path, config: Dict[str, Any]) -> List[AgentProfile]:
        """Direct loading from Excel/CSV when survey module unavailable."""
        if not path.exists():
            raise FileNotFoundError(f"Survey file not found: {path}")

        # Determine file type and load
        if path.suffix.lower() in [".xlsx", ".xls"]:
            df = pd.read_excel(path, header=1)
        else:
            df = pd.read_csv(path)

        logger.info(f"Loading {len(df)} records from survey: {path}")

        profiles = []
        for idx, row in df.iterrows():
            profile = AgentProfile(
                agent_id=f"Agent_{idx + 1:03d}",
                record_id=f"Survey_{idx:04d}",
                family_size=int(row.get("family_size", 3)) if not pd.isna(row.get("family_size")) else 3,
                income=float(row.get("income", 55000)) if not pd.isna(row.get("income")) else 55000,
                raw_data=row.to_dict(),
            )
            profiles.append(profile)

        return profiles


class SyntheticLoader:
    """Generate synthetic agent profiles for testing."""

    # PMT score distributions by MG status
    PMT_PARAMS = {
        "mg": {
            "tp": (3.5, 0.8),  # Higher threat perception
            "cp": (2.5, 0.7),  # Lower coping perception
            "sp": (2.3, 0.6),  # Lower stakeholder perception
            "sc": (3.8, 0.6),  # Higher social capital (within community)
            "pa": (3.5, 0.7),  # Moderate place attachment
        },
        "nmg": {
            "tp": (2.8, 0.7),
            "cp": (3.2, 0.6),
            "sp": (3.0, 0.5),
            "sc": (3.2, 0.6),
            "pa": (3.0, 0.7),
        },
    }

    INCOME_BRACKETS = [
        ("less_than_25k", 12500),
        ("25k_to_30k", 27500),
        ("30k_to_35k", 32500),
        ("35k_to_40k", 37500),
        ("40k_to_45k", 42500),
        ("45k_to_50k", 47500),
        ("50k_to_60k", 55000),
        ("60k_to_75k", 67500),
        ("75k_or_more", 100000),
    ]

    def __init__(self, seed: int = 42):
        self.seed = seed

    def load(self, path: Optional[Path], config: Dict[str, Any]) -> List[AgentProfile]:
        """Generate synthetic profiles."""
        random.seed(self.seed)
        np.random.seed(self.seed)

        n_agents = config.get("n_agents", 100)
        mg_ratio = config.get("mg_ratio", 0.16)
        owner_ratio = config.get("owner_ratio", 0.65)
        tract_id = config.get("tract_id", "T001")

        logger.info(
            f"Generating {n_agents} synthetic agents "
            f"(MG ratio: {mg_ratio:.0%}, Owner ratio: {owner_ratio:.0%})"
        )

        profiles = []
        for i in range(n_agents):
            is_mg = random.random() < mg_ratio
            is_owner = random.random() < owner_ratio
            profile = self._generate_profile(i, is_mg, is_owner, tract_id)
            profiles.append(profile)

        return profiles

    def _generate_profile(
        self, idx: int, is_mg: bool, is_owner: bool, tract_id: str
    ) -> AgentProfile:
        """Generate a single synthetic profile."""
        params = self.PMT_PARAMS["mg" if is_mg else "nmg"]

        # Generate PMT scores
        tp = np.clip(np.random.normal(*params["tp"]), 1.0, 5.0)
        cp = np.clip(np.random.normal(*params["cp"]), 1.0, 5.0)
        sp = np.clip(np.random.normal(*params["sp"]), 1.0, 5.0)
        sc = np.clip(np.random.normal(*params["sc"]), 1.0, 5.0)
        pa = np.clip(np.random.normal(*params["pa"]), 1.0, 5.0)

        # Generate income
        if is_mg:
            income_idx = np.random.choice([0, 1, 2, 3, 4], p=[0.2, 0.25, 0.25, 0.2, 0.1])
        else:
            income_idx = np.random.choice([4, 5, 6, 7, 8], p=[0.1, 0.2, 0.25, 0.25, 0.2])
        income_bracket, income = self.INCOME_BRACKETS[income_idx]

        # Generate flood zone
        if is_mg:
            flood_zone = np.random.choice(
                ["HIGH", "MEDIUM", "LOW"], p=[0.4, 0.4, 0.2]
            )
        else:
            flood_zone = np.random.choice(
                ["HIGH", "MEDIUM", "LOW"], p=[0.2, 0.4, 0.4]
            )

        tenure = "Owner" if is_owner else "Renter"
        housing_status = "mortgage" if is_owner else "rent"

        return AgentProfile(
            agent_id=f"H{idx + 1:04d}",
            record_id=f"SYN_{idx:04d}",
            family_size=np.random.choice([1, 2, 3, 4, 5], p=[0.15, 0.25, 0.30, 0.20, 0.10]),
            generations=str(np.random.choice([1, 2, 3], p=[0.5, 0.3, 0.2])),
            income_bracket=income_bracket,
            income=float(income),
            housing_status=housing_status,
            tenure=tenure,
            is_mg=is_mg,
            has_children=random.random() < 0.35,
            has_elderly=random.random() < 0.20,
            has_vehicle=not (is_mg and random.random() < 0.25),
            housing_cost_burden=is_mg and random.random() < 0.45,
            tp_score=round(tp, 2),
            cp_score=round(cp, 2),
            sp_score=round(sp, 2),
            sc_score=round(sc, 2),
            pa_score=round(pa, 2),
            flood_experience=random.random() < 0.25,
            flood_frequency=np.random.choice([0, 1, 2, 3]) if random.random() < 0.25 else 0,
            sfha_awareness=random.random() < 0.6,
            flood_zone=flood_zone,
            flood_depth=round(random.uniform(0.1, 2.0), 3),
            has_insurance=random.random() < 0.15,
            grid_x=random.randint(0, 456),
            grid_y=random.randint(0, 410),
            longitude=round(-74.3 + random.uniform(0, 0.1), 6),
            latitude=round(40.9 + random.uniform(0, 0.1), 6),
        )


# =============================================================================
# MEMORY GENERATION
# =============================================================================


def generate_initial_memories(
    profiles: List[AgentProfile],
    memory_enricher: Optional[MemoryEnricher] = None,
) -> Dict[str, List[Any]]:
    """
    Generate initial memories for all profiles.

    Uses MemoryTemplateProvider from broker/components/prompt_templates/memory_templates.py
    if no custom enricher is provided.
    """
    # Try to import the existing MemoryTemplateProvider
    try:
        from broker.components.prompt_templates.memory_templates import (
            MemoryTemplateProvider,
        )
        provider = MemoryTemplateProvider
    except ImportError:
        provider = None

    initial_memories: Dict[str, List[Any]] = {}

    for profile in profiles:
        profile_dict = profile.to_dict()

        if memory_enricher is not None:
            memories = memory_enricher.generate_all(profile_dict)
        elif provider is not None:
            memories = provider.generate_all(profile_dict)
        else:
            # Fallback: generate minimal memories
            memories = _generate_fallback_memories(profile)

        initial_memories[profile.agent_id] = memories

    return initial_memories


def _generate_fallback_memories(profile: AgentProfile) -> List[Dict[str, Any]]:
    """Generate minimal fallback memories when no provider is available.

    Returns a single generic memory based on available profile data.
    Domain-specific memory generation should be handled by a MemoryEnricher.
    """
    memories = [{
        "content": f"I am a {profile.tenure.lower()} in my community.",
        "category": "identity",
        "emotion": "neutral",
        "source": "personal",
    }]
    return memories


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def initialize_agents(
    mode: Literal["survey", "csv", "synthetic"],
    path: Optional[Path],
    config: Dict[str, Any],
    enrichers: Optional[Dict[str, Any]] = None,
    seed: int = 42,
) -> Tuple[List[AgentProfile], Dict[str, List[Any]], Dict[str, Any]]:
    """
    Unified agent initialization function.

    This is the main entry point for initializing agents from any source.

    Args:
        mode:
            - "survey": Load from Excel/CSV with PMT scores
            - "csv": Simple CSV with basic attributes
            - "synthetic": Generate test agents
        path:
            Path to data file (None for synthetic mode)
        config:
            Configuration dict with mode-specific options
            - survey mode: {"domain": "flood", "max_agents": 100}
            - csv mode: {"column_mappings": {...}}
            - synthetic mode: {"n_agents": 100, "mg_ratio": 0.16, "owner_ratio": 0.65}
        enrichers:
            Optional dict of enrichers to apply:
            - "position": PositionEnricher (spatial positions)
            - "value": ValueEnricher (property values)
            - "memory": MemoryEnricher (initial memories)
            - Or any Enricher with .enrich(profile) method
        seed:
            Random seed for reproducibility

    Returns:
        Tuple of (profiles, initial_memories, stats):
            - profiles: List[AgentProfile] - loaded/generated agents
            - initial_memories: Dict[str, List[MemoryTemplate]] - per-agent memories
            - stats: Dict[str, Any] - statistics about the load

    Example:
        # Survey mode with enrichers
        profiles, memories, stats = initialize_agents(
            mode="survey",
            path=Path("data/survey.xlsx"),
            config={"domain": "flood"},
            enrichers={
                "position": DepthSampler(seed=42),
                "value": RCVGenerator(seed=42),
            },
        )

        # CSV mode
        profiles, memories, stats = initialize_agents(
            mode="csv",
            path=Path("data/agents.csv"),
            config={},
        )

        # Synthetic mode for testing
        profiles, memories, stats = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 50, "mg_ratio": 0.20},
            seed=123,
        )
    """
    random.seed(seed)
    np.random.seed(seed)

    enrichers = enrichers or {}

    # Step 1: Load profiles based on mode
    logger.info(f"Initializing agents (mode={mode}, seed={seed})")

    if mode == "survey":
        if path is None:
            raise ValueError("Survey mode requires a path to survey file")
        loader = SurveyLoader(domain=config.get("domain", "flood"))
        profiles = loader.load(Path(path), config)
    elif mode == "csv":
        if path is None:
            raise ValueError("CSV mode requires a path to CSV file")
        loader = CSVLoader(column_mappings=config.get("column_mappings"))
        profiles = loader.load(Path(path), config)
    elif mode == "synthetic":
        loader = SyntheticLoader(seed=seed)
        profiles = loader.load(None, config)
    else:
        raise ValueError(f"Unknown mode: {mode}. Must be 'survey', 'csv', or 'synthetic'")

    # Step 2: Apply enrichers
    for key, enricher in enrichers.items():
        if key == "position" and hasattr(enricher, "assign_position"):
            logger.info(f"Applying position enricher: {type(enricher).__name__}")
            for profile in profiles:
                position = enricher.assign_position(profile)
                profile.extensions["position"] = position
                # Populate flood-domain fields for backward compat
                if hasattr(position, "zone_name"):
                    profile.flood_zone = position.zone_name
                if hasattr(position, "base_depth_m"):
                    profile.flood_depth = position.base_depth_m
        elif key == "value" and hasattr(enricher, "generate"):
            logger.info(f"Applying value enricher: {type(enricher).__name__}")
            for profile in profiles:
                values = enricher.generate(
                    income_bracket=profile.income_bracket,
                    is_owner=profile.is_owner,
                    is_mg=profile.is_mg,
                    family_size=profile.family_size,
                )
                profile.extensions["values"] = values
                if hasattr(values, "building_rcv_usd"):
                    profile.rcv_building = values.building_rcv_usd
                if hasattr(values, "contents_rcv_usd"):
                    profile.rcv_contents = values.contents_rcv_usd
        elif hasattr(enricher, "enrich"):
            logger.info(f"Applying enricher '{key}': {type(enricher).__name__}")
            for profile in profiles:
                enricher.enrich(profile)

    # Step 3: Generate initial memories
    memory_enricher = enrichers.get("memory")
    initial_memories = generate_initial_memories(profiles, memory_enricher)

    # Step 4: Calculate statistics
    stats = _calculate_stats(profiles)
    stats["mode"] = mode
    stats["seed"] = seed

    logger.info(
        f"Initialized {stats['total_agents']} agents: "
        f"{stats['owner_count']} owners, {stats['renter_count']} renters, "
        f"{stats['mg_count']} MG"
    )

    return profiles, initial_memories, stats


def _calculate_stats(profiles: List[AgentProfile]) -> Dict[str, Any]:
    """Calculate statistics about the loaded profiles.

    Returns generic demographic stats.  Domain-specific stats (flood zone
    distribution, PMT averages, etc.) should be computed by calling code.
    """
    if not profiles:
        return {
            "total_agents": 0,
            "owner_count": 0,
            "renter_count": 0,
            "mg_count": 0,
            "mg_ratio": 0.0,
            "owner_ratio": 0.0,
        }

    owner_count = sum(1 for p in profiles if p.is_owner)
    mg_count = sum(1 for p in profiles if p.is_mg)
    total = len(profiles)

    return {
        "total_agents": total,
        "owner_count": owner_count,
        "renter_count": total - owner_count,
        "mg_count": mg_count,
        "mg_ratio": mg_count / total if total > 0 else 0.0,
        "owner_ratio": owner_count / total if total > 0 else 0.0,
        "avg_income": np.mean([p.income for p in profiles]),
    }


# =============================================================================
# CONVENIENCE EXPORTS
# =============================================================================


__all__ = [
    "initialize_agents",
    "AgentProfile",
    "CSVLoader",
    "SurveyLoader",
    "SyntheticLoader",
    "Enricher",
    "PositionEnricher",
    "ValueEnricher",
    "MemoryEnricher",
    "generate_initial_memories",
]
