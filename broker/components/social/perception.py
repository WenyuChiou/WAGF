"""
Perception Filter Implementation - Agent-type specific context transformation.

This module implements perception filters that transform raw context data
into agent-appropriate representations. Different agent types see different
information:

- Household agents: See qualitative descriptors instead of exact numbers
- Government agents: See full numerical data with community summaries
- Insurance agents: See full numerical data focused on policyholders

Usage:
    registry = PerceptionFilterRegistry()
    filtered_context = registry.filter_context("household", raw_context, agent)

For MG (Marginalized Group) agents, community-wide observables are removed,
keeping only personal ("my_" prefixed) observables.
"""
from typing import Dict, Any, Optional, List
from broker.interfaces.perception import (
    PerceptionMode,
    DescriptorMapping,
    PerceptionConfig,
)


# Phase 6H Item 5: the flood-domain field-lists and depth descriptor that
# used to live at this module level moved to
# examples/governed_flood/adapters/flood_perception.py. HouseholdPerceptionFilter
# is now domain-neutral — it strips and verbalizes nothing unless a
# DomainPack supplies perception_field_policy() / perception_descriptors(),
# which PerceptionFilterRegistry injects at construction.


class HouseholdPerceptionFilter:
    """Perception filter for household agents.

    Transforms numerical context data into qualitative descriptions.
    Residents don't see exact numbers - they see qualitative descriptions.

    Converts:
    - depth_ft -> qualitative flood depth description
    - damage_amount/property_value ratio -> damage severity description
    - neighbor action counts -> qualitative neighbor descriptions

    Removes:
    - Exact dollar amounts
    - Exact percentages

    For MG (Marginalized Group) agents:
    - Removes community-wide observables
    - Keeps only "my_" prefixed personal observables
    """

    def __init__(
        self,
        config: Optional[PerceptionConfig] = None,
        dollar_fields: Optional[List[str]] = None,
        percentage_fields: Optional[List[str]] = None,
        community_observable_fields: Optional[List[str]] = None,
        neighbor_action_fields: Optional[List[str]] = None,
        descriptor_mappings: Optional[Dict[str, DescriptorMapping]] = None,
    ):
        """Initialize the household perception filter.

        All arguments are optional and default to empty / no-op — the
        filter is domain-neutral. The broker's PerceptionFilterRegistry
        populates them from the active DomainPack (Phase 6H Item 5):

        Args:
            config: Optional perception configuration. Defaults to qualitative mode.
            dollar_fields: Exact-dollar field names to strip. Default [].
            percentage_fields: Exact-percentage field names to strip. Default [].
            community_observable_fields: Fields removed for MG agents. Default [].
            neighbor_action_fields: Count fields verbalized to qualitative
                neighbour descriptions. Default [].
            descriptor_mappings: Numeric->qualitative DescriptorMappings keyed
                by role ("depth" / "damage" / "neighbor"). Absent role ->
                that verbalization step is skipped.
        """
        self.config = config or PerceptionConfig(mode=PerceptionMode.QUALITATIVE)
        descriptor_mappings = descriptor_mappings or {}
        # Numeric->qualitative descriptors keyed by role: "depth" / "damage"
        # / "neighbor". Absent role -> that verbalization step is skipped.
        self._depth_descriptor = descriptor_mappings.get("depth")
        self._damage_descriptor = descriptor_mappings.get("damage")
        self._neighbor_descriptor = descriptor_mappings.get("neighbor")
        # Field-lists default to empty -> strip/verbalize nothing. The
        # broker's PerceptionFilterRegistry fills these from the active
        # DomainPack; a domain that wants no filtering simply omits them.
        self._dollar_fields = list(dollar_fields) if dollar_fields else []
        self._percentage_fields = list(percentage_fields) if percentage_fields else []
        self._community_observable_fields = (
            list(community_observable_fields) if community_observable_fields else []
        )
        self._neighbor_action_fields = (
            list(neighbor_action_fields) if neighbor_action_fields else []
        )

    @property
    def agent_type(self) -> str:
        """Agent type this filter applies to."""
        return "household"

    def filter(self, context: Dict[str, Any], agent: Any = None) -> Dict[str, Any]:
        """Transform raw context for household agent perception.

        Args:
            context: Raw context with numerical data
            agent: Agent instance (for MG/tenure checks)

        Returns:
            Filtered context with qualitative descriptors
        """
        filtered = dict(context)

        # Verbalize depth — only when a DomainPack supplied a "depth"
        # descriptor (dormant for domains that did not).
        if "depth_ft" in filtered and self._depth_descriptor is not None:
            depth = filtered.get("depth_ft", 0.0)
            filtered["flood_depth_description"] = self._depth_descriptor.describe(depth)
            del filtered["depth_ft"]

        # Convert damage ratio to severity description (only if both
        # fields exist and a "damage" descriptor was supplied)
        if ("damage_amount" in filtered and "property_value" in filtered
                and self._damage_descriptor is not None):
            damage = filtered.get("damage_amount", 0.0)
            property_val = filtered.get("property_value", 0.0)
            if property_val > 0:
                damage_ratio = damage / property_val
                filtered["damage_severity"] = self._damage_descriptor.describe(damage_ratio)
            # If property_value is 0 or negative, skip damage_severity (undefined ratio)

        # Verbalize neighbour-action counts (when a "neighbor" descriptor
        # was supplied).
        if self._neighbor_descriptor is not None:
            for field in self._neighbor_action_fields:
                if field in filtered:
                    count = filtered.get(field, 0)
                    filtered[f"{field}_description"] = self._neighbor_descriptor.describe(count)
                    del filtered[field]

        # Remove exact dollar amounts (instance-configured)
        for field in self._dollar_fields:
            if field in filtered:
                del filtered[field]

        # Remove exact percentages (instance-configured)
        for field in self._percentage_fields:
            if field in filtered:
                del filtered[field]

        # For MG agents: remove community-wide observables
        if self._is_marginalized_group(agent):
            filtered = self._filter_for_mg(filtered)

        return filtered

    def _is_marginalized_group(self, agent: Any) -> bool:
        """Check if agent belongs to a marginalized group.

        Args:
            agent: Agent instance

        Returns:
            True if agent is MG, False otherwise
        """
        if agent is None:
            return False

        # Check various ways MG status might be indicated
        if isinstance(agent, dict):
            return agent.get("is_mg", False) or agent.get("marginalized_group", False)

        return getattr(agent, "is_mg", False) or getattr(agent, "marginalized_group", False)

    def _filter_for_mg(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Remove community-wide observables for MG agents.

        MG agents only see personal ("my_" prefixed) observables.
        Community-wide statistics are removed since MG agents have
        limited access to aggregate community information.

        Args:
            context: Current filtered context

        Returns:
            Context with community observables removed
        """
        filtered = {}
        for key, value in context.items():
            # Handle nested observables dict specially
            if key == "observables" and isinstance(value, dict):
                filtered_obs = {}
                for obs_key, obs_val in value.items():
                    # Keep personal observables (my_ prefix)
                    if obs_key.startswith("my_"):
                        filtered_obs[obs_key] = obs_val
                    # Remove community-wide observables
                    elif obs_key in self._community_observable_fields:
                        continue
                    # Keep other observables (e.g., type-specific)
                    else:
                        filtered_obs[obs_key] = obs_val
                filtered[key] = filtered_obs
            # Keep personal observables (my_ prefix)
            elif key.startswith("my_"):
                filtered[key] = value
            # Remove community-wide observables at top level
            elif key in self._community_observable_fields:
                continue
            # Remove description versions of community observables
            elif key.endswith("_description") and key.replace("_description", "") in self._neighbor_action_fields:
                continue
            # Keep other fields
            else:
                filtered[key] = value

        return filtered


class GovernmentPerceptionFilter:
    """Perception filter for government agents.

    Government sees full numerical data - no transformations applied.
    Adds summary metadata to aid policy decision-making.
    """

    def __init__(self, config: Optional[PerceptionConfig] = None):
        """Initialize the government perception filter.

        Args:
            config: Optional perception configuration. Defaults to quantitative mode.
        """
        self.config = config or PerceptionConfig(mode=PerceptionMode.QUANTITATIVE)

    @property
    def agent_type(self) -> str:
        """Agent type this filter applies to."""
        return "government"

    def filter(self, context: Dict[str, Any], agent: Any = None) -> Dict[str, Any]:
        """Keep all numerical data for government agent.

        Args:
            context: Raw context with numerical data
            agent: Agent instance (unused for government)

        Returns:
            Context with all numerical data preserved plus summary note
        """
        filtered = dict(context)

        # Add summary note indicating full data access
        filtered["_perception_note"] = "Full numerical data available for policy analysis"

        return filtered


class InsurancePerceptionFilter:
    """Perception filter for insurance agents.

    Insurance sees full numerical data focused on policyholder information.
    Preserves all data needed for actuarial analysis.
    """

    def __init__(self, config: Optional[PerceptionConfig] = None):
        """Initialize the insurance perception filter.

        Args:
            config: Optional perception configuration. Defaults to quantitative mode.
        """
        self.config = config or PerceptionConfig(mode=PerceptionMode.QUANTITATIVE)

    @property
    def agent_type(self) -> str:
        """Agent type this filter applies to."""
        return "insurance"

    def filter(self, context: Dict[str, Any], agent: Any = None) -> Dict[str, Any]:
        """Keep all numerical data for insurance agent.

        Args:
            context: Raw context with numerical data
            agent: Agent instance (unused for insurance)

        Returns:
            Context with all numerical data preserved for actuarial analysis
        """
        filtered = dict(context)

        # Add note indicating policyholder data focus
        filtered["_perception_note"] = "Policyholder data available for actuarial analysis"

        return filtered


def _household_filter_kwargs_from_domain_pack() -> Dict[str, Any]:
    """HouseholdPerceptionFilter kwargs from the first registered
    DomainPack — mirrors reflection.py's pack-scan. Empty dict when no
    pack is registered (then the filter is a domain-neutral no-op)."""
    try:
        from broker.domains.registry import DomainPackRegistry
    except ImportError:
        return {}
    # First pack with any non-empty perception config wins. Packs that
    # inherit DefaultDomainPack without overriding the perception hooks
    # return {} from both and are skipped, so the scan falls through to
    # the next pack. In production exactly one domain-specific pack is
    # registered per experiment, so ordering does not matter.
    for name in DomainPackRegistry.domains():
        pack = DomainPackRegistry.get(name)
        if pack is None:
            continue
        policy = pack.perception_field_policy() or {}
        descriptors = pack.perception_descriptors() or {}
        if not policy and not descriptors:
            continue
        return {
            "dollar_fields": policy.get("dollar_fields"),
            "percentage_fields": policy.get("percentage_fields"),
            "community_observable_fields": policy.get("community_observable_fields"),
            "neighbor_action_fields": policy.get("neighbor_action_fields"),
            "descriptor_mappings": descriptors or None,
        }
    return {}


class PerceptionFilterRegistry:
    """Registry for perception filters.

    Manages perception filters for different agent types and provides
    a unified interface for filtering context data.

    Default filters:
    - household: HouseholdPerceptionFilter
    - government: GovernmentPerceptionFilter
    - insurance: InsurancePerceptionFilter

    Unknown agent types default to household filter (qualitative perception).
    """

    def __init__(self, register_defaults: bool = True):
        """Initialize the perception filter registry.

        Args:
            register_defaults: If True, register default filters for
                household, government, and insurance agent types.
        """
        self._filters: Dict[str, Any] = {}
        self._default_filter: Optional[Any] = None

        if register_defaults:
            self._register_default_filters()

    def _register_default_filters(self) -> None:
        """Register the default perception filters.

        The household filter is configured from the active DomainPack's
        perception_field_policy() / perception_descriptors() (Phase 6H
        Item 5). With no registered pack it is a domain-neutral no-op
        filter — strips nothing, verbalizes nothing.
        """
        household_filter = HouseholdPerceptionFilter(
            **_household_filter_kwargs_from_domain_pack()
        )
        self.register("household", household_filter)
        self.register("government", GovernmentPerceptionFilter())
        self.register("insurance", InsurancePerceptionFilter())

        # Set household as default for unknown types
        self._default_filter = household_filter

    def register(self, agent_type: str, filter_instance: Any) -> None:
        """Register a filter for an agent type.

        Args:
            agent_type: The agent type identifier (e.g., 'household')
            filter_instance: A perception filter instance
        """
        self._filters[agent_type] = filter_instance

    def get(self, agent_type: str) -> Optional[Any]:
        """Get filter for agent type.

        Args:
            agent_type: The agent type identifier

        Returns:
            The registered filter, or None if not found
        """
        return self._filters.get(agent_type)

    def filter_context(
        self,
        agent_type: str,
        context: Dict[str, Any],
        agent: Any = None,
    ) -> Dict[str, Any]:
        """Apply appropriate filter based on agent type.

        Args:
            agent_type: The agent type identifier
            context: Raw context data to filter
            agent: Optional agent instance for MG/tenure checks

        Returns:
            Filtered context appropriate for the agent type.
            Unknown agent types receive household filter (qualitative).
        """
        filter_instance = self._filters.get(agent_type)

        if filter_instance is None:
            # Default to household filter for unknown types
            filter_instance = self._default_filter or HouseholdPerceptionFilter(
                **_household_filter_kwargs_from_domain_pack()
            )

        return filter_instance.filter(context, agent)

    @property
    def registered_types(self) -> List[str]:
        """List of registered agent types."""
        return list(self._filters.keys())


__all__ = [
    "HouseholdPerceptionFilter",
    "GovernmentPerceptionFilter",
    "InsurancePerceptionFilter",
    "PerceptionFilterRegistry",
]
