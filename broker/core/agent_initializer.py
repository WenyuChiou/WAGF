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
from typing import Any, Callable, Dict, List, Literal, Optional, Protocol, Tuple, Union

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

    Phase 6C-v3 (2026-05-10): domain-specific hazard / insurance fields
    moved to the typed water-domain subclass
    :class:`broker.domains.water.agent_profile.FloodAgentProfile`.
    Base ``AgentProfile`` carries only domain-neutral demographic,
    psychometric, and spatial fields plus an ``extensions`` dict for
    domain-specific data.

    New domains should subclass this class (mirroring ``FloodAgentProfile``)
    or use ``extensions: Dict`` for sparse / per-agent data that doesn't
    warrant a typed field.
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

    # --- Psychological Constructs ---
    # Phase 6R-C (audit cluster A #3, 2026-05-26): the 5 PMT-framework
    # score fields (tp / cp / sp / sc / pa — Threat Perception, Coping
    # Perception, Stakeholder Perception, Social Capital, Place
    # Attachment) moved to
    # ``broker.domains.water.agent_profile.FloodAgentProfile``. Pre-fix
    # any non-water domain author calling initialize_agents() got back
    # profiles unconditionally carrying flood-framework score labels —
    # a domain leak in generic schema. New domains that need typed
    # psychometric fields subclass AgentProfile (mirroring
    # FloodAgentProfile) and add their own. Domain-sparse data
    # belongs in ``extensions: Dict`` instead.

    # --- Spatial (domain-neutral) ---
    grid_x: int = 0
    grid_y: int = 0
    longitude: float = 0.0
    latitude: float = 0.0

    # --- Extensions (for domain-specific sparse data — preferred for
    #     simple add-ons; subclass AgentProfile for typed structured fields) ---
    extensions: Dict[str, Any] = field(default_factory=dict)

    # --- Raw source data ---
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
    """Load agent profiles from simple CSV file.

    Phase 6C-v3 (2026-05-10): flood-specific column aliases moved to
    :class:`broker.domains.water.csv_loader.FloodCSVLoader`. Base
    DEFAULT_COLUMNS is now domain-neutral; subclass and extend for
    domain-specific columns.
    """

    # Default column mappings (domain-neutral). Domain subclasses extend
    # via class-level merge in their own ``DEFAULT_COLUMNS``.
    DEFAULT_COLUMNS = {
        "agent_id": ["agent_id", "id", "AgentID"],
        "family_size": ["family_size", "household_size", "FamilySize"],
        "income": ["income", "Income", "annual_income"],
        "income_bracket": ["income_bracket", "IncomeBracket"],
        "tenure": ["tenure", "Tenure", "housing_status"],
        "is_mg": ["is_mg", "mg", "MG", "marginalized"],
        # Phase 6R-C (2026-05-26): 5 PMT score column aliases moved to
        # ``FloodCSVLoader.DEFAULT_COLUMNS`` — they're flood-framework
        # vocabulary (TP / CP / SP / SC / PA) and shouldn't appear in
        # the generic alias map. A non-water CSV with no PMT columns
        # no longer collides with these defaults.
    }

    # Subclass hook: if non-empty, _parse_row will populate these
    # fields onto the profile from the CSV row. Domain CSVLoader
    # subclasses set this to their domain-specific field list.
    _DOMAIN_EXTRA_FIELDS: List[str] = []

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

    # Subclass hook: profile class to instantiate. FloodCSVLoader sets
    # this to FloodAgentProfile so flood-specific fields populate.
    _PROFILE_CLASS = AgentProfile

    def _parse_row(
        self, idx: int, row: pd.Series, config: Dict[str, Any]
    ) -> Optional[AgentProfile]:
        """Parse a single CSV row into a profile instance.

        Phase 6C-v3 (2026-05-10): base CSVLoader produces a domain-neutral
        :class:`AgentProfile`. Domain CSVLoader subclasses override
        ``_PROFILE_CLASS`` and ``_populate_domain_fields`` to add
        domain-specific column reads.
        """

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

        # Phase 6R-C (2026-05-26): the 5 PMT score kwargs
        # (tp_score / cp_score / sp_score / sc_score / pa_score)
        # previously constructed here directly moved to
        # ``FloodCSVLoader._populate_domain_fields`` — base loader
        # produces a domain-neutral profile, the flood subclass adds
        # the PMT columns from the CSV.
        profile = self._PROFILE_CLASS(
            agent_id=str(agent_id),
            record_id=f"CSV_{idx:04d}",
            family_size=int(get_val("family_size", 3)),
            income=float(get_val("income", 55000)),
            income_bracket=str(get_val("income_bracket", "50k_to_60k")),
            housing_status=housing_status,
            tenure=tenure,
            is_mg=bool(get_val("is_mg", False)),
            raw_data=row.to_dict(),
        )

        # Subclass hook: domain CSV loaders populate flood-specific
        # (or other domain) fields after the base profile is built.
        self._populate_domain_fields(profile, get_val)

        return profile

    def _populate_domain_fields(
        self, profile: AgentProfile, get_val: Callable
    ) -> None:
        """Hook for domain subclasses to add domain-specific field reads.

        Default implementation is a no-op; ``FloodCSVLoader`` and other
        domain subclasses override to read their fields from the CSV
        row via the supplied ``get_val`` lookup.
        """
        return None

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

    def __init__(self, domain: str):
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

    # Phase 6R-C (audit cluster A #4, 2026-05-26): the
    # ``PMT_PARAMS`` distribution dict moved to
    # ``broker.domains.water.loaders.FloodSyntheticLoader``. Pre-fix
    # any non-water domain author using SyntheticLoader silently got
    # agents whose psychometric scores were sampled from PMT-framework
    # (Threat / Coping / Stakeholder / Social / Place Attachment)
    # distributions — meaningless for non-PMT domains.

    # Subclass hook: agent_id prefix. Base uses domain-neutral "A";
    # water subclass uses "H" (household — preserved for paper-1b
    # byte-identity).
    _AGENT_ID_PREFIX = "A"

    def _build_agent_id(self, idx: int) -> str:
        """Subclass hook for agent_id formatting. Base uses 0-indexed
        ``A0000``, ``A0001``, ... — domain-neutral. FloodSyntheticLoader
        overrides to 1-indexed ``H0001``, ``H0002``, ... for paper-1b
        byte-identity."""
        return f"{self._AGENT_ID_PREFIX}{idx:04d}"

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

    # Subclass hook: profile class to instantiate. FloodSyntheticLoader
    # sets this to FloodAgentProfile so flood-specific synthetic fields
    # populate via _populate_domain_fields.
    _PROFILE_CLASS = AgentProfile

    # Domain-neutral spatial defaults. Flood/other domains override
    # via subclass to inject geographic priors (e.g., flood-zone
    # probabilities, geographic bounding box for synthetic coords).
    _SPATIAL_BBOX = {
        "x_min": 0, "x_max": 1000,
        "y_min": 0, "y_max": 1000,
        "lon_min": 0.0, "lon_max": 0.0,    # 0/0 → no geographic bias
        "lat_min": 0.0, "lat_max": 0.0,
    }

    def _generate_profile(
        self, idx: int, is_mg: bool, is_owner: bool, tract_id: str
    ) -> AgentProfile:
        """Generate a single synthetic profile.

        Phase 6C-v3 (2026-05-10): domain-specific synthesis (hazard-zone
        probability mix, regional coordinate range) moved to the
        water-domain ``FloodSyntheticLoader``.
        Base implementation produces a domain-neutral profile; subclass
        and override ``_populate_domain_fields`` for domain-specific
        synthetic state.
        """
        # Phase 6R-C (2026-05-26): PMT score sampling moved to the
        # subclass ``_pre_generate_rng`` hook below — runs BEFORE base
        # random calls so paper-1b byte-identity is preserved. The
        # original water-domain code path sampled PMT first; that order
        # advances the RNG state in a specific sequence which downstream
        # consumers (other random.choice / random.uniform calls in
        # this method, and any consumers of np.random / random after
        # the loader returns) depend on. Inverting the order would
        # break byte-identity.
        pre = self._pre_generate_rng(is_mg, is_owner)

        # Generate income
        if is_mg:
            income_idx = np.random.choice([0, 1, 2, 3, 4], p=[0.2, 0.25, 0.25, 0.2, 0.1])
        else:
            income_idx = np.random.choice([4, 5, 6, 7, 8], p=[0.1, 0.2, 0.25, 0.25, 0.2])
        income_bracket, income = self.INCOME_BRACKETS[income_idx]

        tenure = "Owner" if is_owner else "Renter"
        housing_status = "mortgage" if is_owner else "rent"

        bbox = self._SPATIAL_BBOX
        # Phase 6R-C (2026-05-26): agent_id prefix is now a subclass
        # hook (``_AGENT_ID_PREFIX``). Base uses domain-neutral "A";
        # FloodSyntheticLoader overrides to "H" + "+1" indexing to
        # preserve paper-1b byte-identity. PMT score kwargs removed —
        # flood subclass assigns them via _populate_domain_fields.
        profile = self._PROFILE_CLASS(
            agent_id=self._build_agent_id(idx),
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
            grid_x=random.randint(bbox["x_min"], bbox["x_max"]),
            grid_y=random.randint(bbox["y_min"], bbox["y_max"]),
            longitude=round(bbox["lon_min"] + random.uniform(0, bbox["lon_max"] - bbox["lon_min"]), 6),
            latitude=round(bbox["lat_min"] + random.uniform(0, bbox["lat_max"] - bbox["lat_min"]), 6),
        )

        # Subclass hook: domain synthetic loaders populate flood-specific
        # (or other domain) fields after the base profile is built.
        # ``pre`` carries any values pre-sampled by
        # ``_pre_generate_rng`` (e.g. PMT scores in
        # FloodSyntheticLoader).
        self._populate_domain_fields(profile, is_mg, is_owner, pre=pre)

        return profile

    def _pre_generate_rng(
        self, is_mg: bool, is_owner: bool,
    ) -> Optional[Dict[str, Any]]:
        """Phase 6R-C (2026-05-26): subclass hook for sampling RNG
        values BEFORE the base profile's own RNG calls.

        Returns a dict passed to ``_populate_domain_fields`` via the
        ``pre`` kwarg, or ``None`` if no pre-sampling is needed.
        Used by ``FloodSyntheticLoader`` to sample PMT scores in the
        original order required for paper-1b byte-identity (PMT scores
        were sampled BEFORE income/family/etc. in the pre-Phase-6R-C
        code path; preserving that RNG sequence is mandatory).

        **WARNING — asymmetric draws break reproducibility silently**:
        this hook MUST consume the same number of RNG draws regardless
        of ``is_mg`` / ``is_owner`` values (e.g. don't draw only when
        ``is_mg=True``). A conditional override that draws different
        counts per branch will desync np.random / random state from
        what the base method's subsequent calls assume, breaking
        seed-deterministic byte-identity with no error. If you need
        conditional behaviour, draw the same count and discard the
        unwanted samples.
        """
        return None

    def _populate_domain_fields(
        self, profile: AgentProfile, is_mg: bool, is_owner: bool,
        pre: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Hook for domain subclasses to populate domain-specific
        synthetic fields. Default no-op."""
        return None


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

    # Phase 6J-C (2026-05-22): loader selection must be explicit. A
    # missing domain silently selected a domain-specific loader before.
    try:
        domain_name = config["domain"]
    except KeyError as exc:
        raise KeyError(
            "initialize_agents requires config['domain'] so loader selection "
            "is explicit."
        ) from exc

    # Phase 6P-C (2026-05-25): registry-driven loader dispatch.
    # Replaces the `if domain_name == "flood":` hardcodes that
    # forced every CSV/synthetic mode call to traverse a
    # water-namespace import even when the domain was irrigation,
    # vaccination, or anything else. Each DomainPack now owns its
    # loader classes; default packs return None → generic loader.
    from broker.domains.registry import DomainPackRegistry
    _pack = DomainPackRegistry.get_or_default(domain_name)

    def _resolve_csv_loader_class():
        return _pack.csv_loader_class() or CSVLoader

    def _resolve_synthetic_loader_class():
        return _pack.synthetic_loader_class() or SyntheticLoader

    if mode == "survey":
        if path is None:
            raise ValueError("Survey mode requires a path to survey file")
        loader = SurveyLoader(domain=domain_name)
        profiles = loader.load(Path(path), config)
    elif mode == "csv":
        if path is None:
            raise ValueError("CSV mode requires a path to CSV file")
        loader_cls = _resolve_csv_loader_class()
        loader = loader_cls(column_mappings=config.get("column_mappings"))
        profiles = loader.load(Path(path), config)
    elif mode == "synthetic":
        loader_cls = _resolve_synthetic_loader_class()
        loader = loader_cls(seed=seed)
        profiles = loader.load(None, config)
    else:
        raise ValueError(f"Unknown mode: {mode}. Must be 'survey', 'csv', or 'synthetic'")

    # Step 2: Apply enrichers
    for key, enricher in enrichers.items():
        if key == "position" and hasattr(enricher, "assign_position"):
            logger.info(f"Applying position enricher: {type(enricher).__name__}")
            # The position object always lands in profile.extensions["position"];
            # any domain can read it from there. An enricher may additionally
            # declare `profile_field_map` ({position_attr: profile_attr}) to
            # copy position attributes onto typed fields of a profile
            # subclass — e.g. a water enricher maps the position's zone and
            # depth attributes onto the typed water-profile fields. Generic
            # broker code stays domain-token-free (Phase 6I-B de-flood;
            # previously a hardcoded water-field write block).
            field_map = getattr(enricher, "profile_field_map", {}) or {}
            for profile in profiles:
                position = enricher.assign_position(profile)
                profile.extensions["position"] = position
                for src_attr, dst_attr in field_map.items():
                    if hasattr(profile, dst_attr) and hasattr(position, src_attr):
                        setattr(profile, dst_attr, getattr(position, src_attr))
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
