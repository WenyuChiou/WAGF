"""
Enrichment Protocols - Generic interfaces for agent profile enrichment.

These protocols allow domain-specific enrichment logic to be injected
into the generic agent initialization pipeline without hardcoding dependencies.

Design Pattern: Dependency Injection via Protocol (PEP 544)
- broker/modules/survey/ defines what enrichment interface it needs (Protocol)
- examples/multi_agent/ provides concrete implementations (DepthSampler, RCVGenerator)
- No import coupling: broker/ never imports from examples/

Usage:
    # Domain-specific implementation (e.g., flood simulation)
    from examples.multi_agent.flood.environment.depth_sampler import DepthSampler
    from examples.multi_agent.flood.environment.rcv_generator import RCVGenerator

    # Generic initialization with injected enrichers
    profiles, stats = initialize_agents_from_survey(
        survey_path,
        position_enricher=DepthSampler(seed=42),
        value_enricher=RCVGenerator(seed=42)
    )

    # Different domain (e.g., trading simulation)
    profiles, stats = initialize_agents_from_survey(
        survey_path,
        position_enricher=TradingLocationSampler(),
        value_enricher=PortfolioValueGenerator()
    )
"""
from typing import Protocol, NamedTuple, Any


class PositionData(NamedTuple):
    """
    Spatial position data for an agent.

    Attributes:
        zone_name: Identifier for the location/zone (e.g., "HIGH_RISK", "DOWNTOWN")
        base_depth_m: Baseline exposure metric in meters (domain-specific interpretation)
        flood_probability: Risk probability [0-1] (reusable for any risk metric)
    """
    zone_name: str
    base_depth_m: float
    flood_probability: float


class PositionEnricher(Protocol):
    """
    Protocol for assigning spatial positions to agents.

    Implementations must provide an assign_position method that takes
    an agent profile and returns PositionData.

    Example implementations:
        - DepthSampler: Assigns flood-prone locations based on survey responses
        - TradingLocationSampler: Assigns trading desk locations
        - OrganizationSampler: Assigns office locations in a building
    """

    def assign_position(self, profile: Any) -> PositionData:
        """
        Assign a spatial position to an agent profile.

        Args:
            profile: AgentProfile instance with attributes like
                     agent_id, income, family_size, etc. (survey-derived)

        Returns:
            PositionData with zone_name, base_depth_m, and flood_probability

        Implementation Note:
            Typically reads profile.fixed_attributes or profile metadata
            to determine appropriate location assignment.
        """
        ...


class ValueData(NamedTuple):
    """
    Asset value data for an agent.

    Attributes:
        building_rcv_usd: Replacement Cost Value for primary asset (USD)
        contents_rcv_usd: Replacement Cost Value for contents/inventory (USD)
    """
    building_rcv_usd: float
    contents_rcv_usd: float


class ValueEnricher(Protocol):
    """
    Protocol for calculating agent asset values.

    Implementations must provide a generate method that computes
    asset values based on agent characteristics.

    Example implementations:
        - RCVGenerator: Calculates building/contents value for homeowners
        - PortfolioValueGenerator: Calculates trading portfolio values
        - InventoryGenerator: Calculates business inventory values
    """

    def generate(
        self,
        income_bracket: str,
        is_owner: bool,
        is_mg: bool,
        family_size: int
    ) -> ValueData:
        """
        Generate asset values for an agent.

        Args:
            income_bracket: Income category (e.g., "$50k-$75k", "high", "low")
            is_owner: Whether agent owns vs rents (ownership status)
            is_mg: Whether agent is in marginalized/vulnerable group
            family_size: Number of household members or entity size

        Returns:
            ValueData with building_rcv_usd and contents_rcv_usd

        Implementation Note:
            Use domain-specific heuristics. For example:
            - Flood sim: Higher income → larger house → higher RCV
            - Trading sim: income_bracket maps to portfolio size
        """
        ...


# Future protocols can be added here as needed:
# - NetworkEnricher: For assigning social network positions
# - SkillEnricher: For assigning agent capabilities/skills
# - PreferenceEnricher: For assigning behavioral preferences
