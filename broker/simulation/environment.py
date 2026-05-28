"""
Tiered Environment for Scientific World Modeling.

Distinguishes between:
1. Global State (e.g., Inflation, Sea Level)
2. Regional/Local State (e.g., Tract Paving Density, Market Sector Demand)
3. Institutional State (e.g., Government Budget)
4. Social State (e.g., Neighbor observations, network effects)

Serves as the single source of truth for "Non-Personal" state.
"""
from typing import Dict, Any, Iterator, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from broker.components.social.graph import SocialGraph
    from broker.components.social.post import Post
    from broker.domains.protocol import DomainPack

class TieredEnvironment:
    """
    Multi-layered environment state manager.

    Layers:
    - global_state: Simulation-wide variables (year, flood, policy)
    - local_states: Spatial/regional variables (tract-level)
    - institutions: Institutional agent states (FEMA, insurers)
    - social_states: Observable neighbor states (for social influence)
    - social_feeds: Phase 6T-E.B — author_id → ordered list of Posts.
      Empty by default; populated only when a DomainPack opts in via
      ``social_feeds_default_enabled`` or the YAML flag
      ``global_config.social_feeds.enable``. Paper-3 v21 dataset is
      byte-identical to v0.4.0 because no shipping experiment flips
      the flag yet.
    """

    def __init__(self, global_state: Optional[Dict[str, Any]] = None):
        # Layer 1: Global (Sim-wide)
        self.global_state: Dict[str, Any] = global_state or {}

        # Layer 2: Spatial/Local (Tracts, Neighborhoods)
        self.local_states: Dict[str, Dict[str, Any]] = {}

        # Layer 3: Institutional (Government, Companies)
        self.institutions: Dict[str, Dict[str, Any]] = {}

        # Layer 4: Social (Neighbor observations)
        self.social_states: Dict[str, Dict[str, Any]] = {}

        # Layer 5: Social-media feeds (Phase 6T-E.B). Empty dict =
        # the SocialMediaProvider walks an empty iterator and writes
        # ``context["social_media_feed"] = ""`` — byte-identical to
        # any earlier code that never built feeds.
        self.social_feeds: Dict[str, List["Post"]] = {}

        # Optional: Social Graph for neighbor lookups
        self._social_graph: Optional['SocialGraph'] = None

    # ===== Social-media feeds (Phase 6T-E.B) =====

    def add_post(self, post: "Post") -> None:
        """Append a Post to its author's feed.

        Caller responsibility: the post's ``author_id`` field is the
        feed key. No deduplication here — repeated posts with the
        same author / event_type / event_year are allowed (an author
        may legitimately re-post). Dedup is the SocialMediaProvider's
        job at render time.
        """
        self.social_feeds.setdefault(post.author_id, []).append(post)

    def iter_posts(
        self,
        since_year: Optional[int] = None,
        until_year: Optional[int] = None,
    ) -> Iterator["Post"]:
        """Iterate all posts across all authors, optionally filtered
        by event_year range (both endpoints inclusive). Used by the
        SocialMediaProvider's top-K sampling. Iteration order is
        author insertion order then per-author append order — stable
        across runs with deterministic event dispatch."""
        for posts in self.social_feeds.values():
            for p in posts:
                if since_year is not None and p.event_year < since_year:
                    continue
                if until_year is not None and p.event_year > until_year:
                    continue
                yield p

    def clear_social_feeds_year(self, current_year: int, pack: "DomainPack") -> None:
        """Drop posts whose event_type has ``EventPersistence.EPHEMERAL``
        in the pack's ``event_persistence_policy``. STICKY_* tiers
        survive across year boundaries (with age-decay weighting
        applied at render time, not here). Called from the multi-agent
        runner's year-boundary hook; safe to call on an empty feed
        dict (no-op).

        Phase 6T-E.B: keeps social_feeds bounded — without this,
        long-horizon experiments would accumulate every post
        forever, blowing memory + prompt context."""
        from broker.components.events.exceptions import EventPersistence

        if not self.social_feeds:
            return

        get_persistence = getattr(pack, "event_persistence_policy", None)
        for author_id in list(self.social_feeds):
            kept = []
            for p in self.social_feeds[author_id]:
                persistence = (
                    get_persistence(p.event_type)
                    if get_persistence is not None
                    else EventPersistence.EPHEMERAL
                )
                if persistence == EventPersistence.EPHEMERAL:
                    continue  # drop
                kept.append(p)
            if kept:
                self.social_feeds[author_id] = kept
            else:
                del self.social_feeds[author_id]

    # ===== Setters =====
    
    def set_global(self, key: str, value: Any):
        """Set a global variable."""
        self.global_state[key] = value

    def set_local(self, location_id: str, key: str, value: Any):
        """Set a variable for a specific location (tract)."""
        if location_id not in self.local_states:
            self.local_states[location_id] = {}
        self.local_states[location_id][key] = value

    def get_local(self, location_id: str, key: str, default: Any = None) -> Any:
        """Get a variable for a specific location (tract)."""
        return self.local_states.get(location_id, {}).get(key, default)

    def set_social(self, agent_id: str, key: str, value: Any):
        """Set an observable social state for an agent."""
        if agent_id not in self.social_states:
            self.social_states[agent_id] = {}
        self.social_states[agent_id][key] = value
    
    # ===== Social Graph Integration =====
    
    def set_social_graph(self, graph: 'SocialGraph'):
        """Attach a social graph for neighbor lookups."""
        self._social_graph = graph
    
    def get_neighbor_observations(self, agent_id: str, observable_keys: List[str] = None) -> Dict[str, Any]:
        """
        Get aggregated observations of an agent's neighbors for specific keys.
        
        Args:
            agent_id: Center agent
            observable_keys: List of boolean/numeric keys to aggregate. 
                            REQUIRED - no default to ensure domain-agnostic usage.
                            Example for flood domain: ["elevated", "has_insurance", "relocated"]
        """
        if observable_keys is None:
            # Phase 25 PR6: Removed hard-coded defaults for universality
            # Callers must explicitly specify keys for their domain
            return {"neighbor_count": 0, "warning": "observable_keys not specified"}
            
        if not self._social_graph:
            return {"neighbor_count": 0}
        
        neighbors = self._social_graph.get_neighbors(agent_id)
        if not neighbors:
            return {"neighbor_count": 0}
        
        # Aggregate observable states
        counts = {k: 0 for k in observable_keys}
        
        for nid in neighbors:
            nstate = self.social_states.get(nid, {})
            for k in observable_keys:
                if nstate.get(k, False):
                    counts[k] += 1
        
        n = len(neighbors)
        result = {"neighbor_count": n}
        for k, count in counts.items():
            result[f"{k}_count"] = count
            result[f"{k}_rate"] = count / n if n > 0 else 0.0
            
        return result

    # ===== Getters =====

    def get_observable(self, path: str, default: Any = None) -> Any:
        """
        Safe retrieval using dot-notation path.
        
        Examples:
        - "global.inflation"
        - "local.T001.paving_density"
        - "institutions.fema.budget"
        - "social.Agent_1.elevated"
        """
        parts = path.split('.')
        
        if not parts:
            return default

        scope = parts[0]
        
        try:
            if scope == "global":
                if len(parts) == 2:
                    return self.global_state.get(parts[1], default)
                    
            elif scope == "local":
                if len(parts) == 3:
                    loc_id, key = parts[1], parts[2]
                    return self.local_states.get(loc_id, {}).get(key, default)
                    
            elif scope == "institutions":
                 if len(parts) == 3:
                    inst_id, key = parts[1], parts[2]
                    return self.institutions.get(inst_id, {}).get(key, default)
            
            elif scope == "social":
                if len(parts) == 3:
                    agent_id, key = parts[1], parts[2]
                    return self.social_states.get(agent_id, {}).get(key, default)
                    
        except Exception:
            return default
            
        return default

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for audit/logging."""
        return {
            "global": self.global_state,
            "local": self.local_states,
            "institutions": self.institutions,
            "social": self.social_states
        }

