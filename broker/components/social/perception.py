"""
Perception Filter Implementation - Agent-type specific context transformation.

This module implements perception filters that transform raw context data
into agent-appropriate representations. Different agent types see different
information:

- Lay agents (e.g. households): qualitative descriptors instead of
  exact numbers (QualitativePerceptionFilter).
- Expert / institutional agents: full numerical data
  (PassThroughPerceptionFilter).

Which agent type gets which filter is declared per domain by
DomainPack.passthrough_agent_types() — no agent-type names are
hardcoded in this module (Phase 6H Item 5c).

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
# examples/governed_flood/adapters/flood_perception.py. QualitativePerceptionFilter
# is now domain-neutral — it strips and verbalizes nothing unless a
# DomainPack supplies perception_field_policy() / perception_descriptors(),
# which PerceptionFilterRegistry injects at construction.


class QualitativePerceptionFilter:
    """Perception filter for qualitative agent views.

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
        """Initialize the qualitative perception filter.

        All arguments are optional and default to empty / no-op — the
        filter is domain-neutral. The broker's PerceptionFilterRegistry
        populates them from the active DomainPack (Phase 6H Item 5):

        Args:
            config: Optional perception configuration. Defaults to qualitative mode.
            dollar_fields: Exact-dollar field names to strip. Default [].
            percentage_fields: Exact-percentage field names to strip. Default [].
            community_observable_fields: Fields removed for MG agents. Default [].
            neighbor_action_fields: Names of neighbour-count fields — used
                ONLY to prune their `_description` outputs for MG agents.
                Verbalization itself is driven by descriptor_mappings;
                keep this list consistent with the neighbour entries there.
            descriptor_mappings: Numeric->qualitative DescriptorMappings keyed
                by INPUT context field (e.g. {"depth_ft": <mapping>}).
                Absent field -> that verbalization step is skipped.
        """
        self.config = config or PerceptionConfig(mode=PerceptionMode.QUALITATIVE)
        # Verbalization rules keyed by INPUT context field (Phase 6H
        # Item 5b): {field: DescriptorMapping}. filter() applies each as
        # a pure lookup -- it never computes a derived quantity itself.
        self._descriptor_mappings = (
            dict(descriptor_mappings) if descriptor_mappings else {}
        )
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

        # Verbalize: numeric -> qualitative. One DescriptorMapping per
        # INPUT context field (Phase 6H Item 5b). The filter only looks
        # up -- never computes. Derived quantities (changes, deltas)
        # arrive as fields the domain environment already produced; a
        # same-context ratio is supported via `denominator_field`.
        for in_field, mapping in self._descriptor_mappings.items():
            if in_field not in filtered:
                continue
            value = filtered[in_field]
            if mapping.denominator_field:
                denom = filtered.get(mapping.denominator_field)
                if denom is None or denom <= 0:
                    # denominator missing / zero / negative -> the ratio
                    # is undefined or nonsensical; skip (this matches the
                    # prior flood semantics of `property_value > 0`).
                    continue
                value = value / denom
            filtered[mapping.field_name] = mapping.describe(value)
            if mapping.field_name != in_field:
                del filtered[in_field]

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


class PassThroughPerceptionFilter:
    """Perception filter for expert / institutional agents (Phase 6H Item 5c).

    Preserves all numerical data — institutions and instruments perceive
    precise figures, unlike lay agents who perceive qualitatively (see
    :class:`QualitativePerceptionFilter`). Whether a given agent type
    verbalizes or passes raw numbers through is a per-agent-type modelling
    choice a DomainPack declares via ``passthrough_agent_types()``.

    Replaces the former flood-named GovernmentPerceptionFilter /
    InsurancePerceptionFilter — both were pure pass-through plus a note.
    """

    def __init__(
        self,
        config: Optional[PerceptionConfig] = None,
        agent_type: str = "default",
    ):
        """Initialize the pass-through perception filter.

        Args:
            config: Optional perception configuration. Defaults to quantitative mode.
            agent_type: Agent type this filter is registered for.
        """
        self.config = config or PerceptionConfig(mode=PerceptionMode.QUANTITATIVE)
        self._agent_type = agent_type

    @property
    def agent_type(self) -> str:
        """Agent type this filter applies to."""
        return self._agent_type

    def filter(self, context: Dict[str, Any], agent: Any = None) -> Dict[str, Any]:
        """Keep all numerical data — expert agents see precise figures."""
        filtered = dict(context)
        filtered["_perception_note"] = "Full numerical data available."
        return filtered


def _perception_filter_kwargs_from_domain_pack() -> Dict[str, Any]:
    """QualitativePerceptionFilter kwargs from the first registered
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


def _passthrough_agent_types_from_domain_pack() -> set:
    """Agent types declared pass-through (raw numbers) by any registered
    DomainPack. Empty set when none — every agent type then verbalizes.
    Verbalize is the safe default: verbalizing a precise perceiver only
    loses precision, whereas passing raw numbers to a lay perceiver
    manufactures a super-perceiver artifact (see Phase 6H Item 5c)."""
    try:
        from broker.domains.registry import DomainPackRegistry
    except ImportError:
        return set()
    result: set = set()
    for name in DomainPackRegistry.domains():
        pack = DomainPackRegistry.get(name)
        if pack is None:
            continue
        result |= set(pack.passthrough_agent_types() or set())
    return result


class PerceptionFilterRegistry:
    """Registry for perception filters.

    Manages perception filters for different agent types and provides
    a unified interface for filtering context data.

    Filters are built from the active DomainPack:
    - verbalizing (QualitativePerceptionFilter) — the default for every
      agent type, and for unknown types;
    - pass-through (PassThroughPerceptionFilter) — for the agent types a
      DomainPack lists in ``passthrough_agent_types()``.
    """

    def __init__(self, register_defaults: bool = True):
        """Initialize the perception filter registry.

        Args:
            register_defaults: If True, build filters from the active
                DomainPack — the verbalizing household filter plus a
                pass-through filter for each agent type the DomainPack
                lists in passthrough_agent_types().
        """
        self._filters: Dict[str, Any] = {}
        self._default_filter: Optional[Any] = None

        if register_defaults:
            self._register_default_filters()

    def _register_default_filters(self) -> None:
        """Register perception filters from the active DomainPack.

        The verbalizing household filter (configured from the DomainPack's
        perception_descriptors() / perception_field_policy()) is the
        default — every agent type verbalizes unless the DomainPack lists
        it in ``passthrough_agent_types()``, in which case it gets a
        PassThroughPerceptionFilter (raw numbers). No agent-type names
        are hardcoded here (Phase 6H Item 5c).
        """
        verbalizing = QualitativePerceptionFilter(
            **_perception_filter_kwargs_from_domain_pack()
        )
        self.register("household", verbalizing)
        for agent_type in _passthrough_agent_types_from_domain_pack():
            self.register(
                agent_type, PassThroughPerceptionFilter(agent_type=agent_type)
            )
        # Verbalizing filter is the default for any unlisted agent type.
        self._default_filter = verbalizing

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
            filter_instance = self._default_filter or QualitativePerceptionFilter(
                **_perception_filter_kwargs_from_domain_pack()
            )

        return filter_instance.filter(context, agent)

    @property
    def registered_types(self) -> List[str]:
        """List of registered agent types."""
        return list(self._filters.keys())


__all__ = [
    "QualitativePerceptionFilter",
    "HouseholdPerceptionFilter",  # deprecated alias
    "PassThroughPerceptionFilter",
    "PerceptionFilterRegistry",
]


def __getattr__(name):
    if name == "HouseholdPerceptionFilter":
        import warnings

        warnings.warn(
            "HouseholdPerceptionFilter is deprecated; use QualitativePerceptionFilter",
            DeprecationWarning,
            stacklevel=2,
        )
        return QualitativePerceptionFilter
    raise AttributeError(name)
