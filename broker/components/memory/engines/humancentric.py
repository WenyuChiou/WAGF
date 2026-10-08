from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
import copy
import heapq
import logging

from broker.agents import BaseAgent
from ..engine import MemoryEngine

if TYPE_CHECKING:
    from broker.memory.strategies.base import SurpriseStrategy

logger = logging.getLogger(__name__)

class HumanCentricMemoryEngine(MemoryEngine):
    """
    Human-Centered Memory Engine with:
    1. Emotional encoding (fear, relief, regret, trust shifts)
    2. Source differentiation (personal > neighbor > community)
    3. Stochastic consolidation (probabilistic long-term storage)
    4. Time-weighted decay (exponential with emotion modifier)
    5. Contextual Resonance (retrieval-time query-memory relevance)
    6. Interference-Based Forgetting (newer similar memories suppress older ones)

    All parameters use 0-1 scale for consistency.

    References:
    - Park et al. (2023) Generative Agents: recency x importance x relevance
    - Chapter 8: Memory consolidation and forgetting strategies
    - Tulving (1972): Episodic vs Semantic memory distinction
    - Anderson & Neely (1996): Retroactive interference theory
    """

    # Stopwords for keyword extraction in contextual resonance
    _STOPWORDS = frozenset({
        "the", "a", "an", "is", "was", "are", "were", "been", "be",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "can", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "and", "but",
        "or", "not", "so", "if", "when", "that", "which", "this",
        "i", "me", "my", "we", "our", "you", "your", "he", "she",
        "it", "its", "they", "them", "their",
    })
    
    def __init__(
        self,
        window_size: int = 3,
        top_k_significant: int = 2,
        consolidation_prob: float = 0.7,      # P(consolidate) for high-importance items
        consolidation_threshold: float = 0.6, # Min importance to consider consolidation
        decay_rate: float = 0.1,               # λ in e^(-λt) decay
        emotional_weights: Optional[Dict[str, float]] = None,
        source_weights: Optional[Dict[str, float]] = None,
        # v2 Weighted Scoring Params
        W_recency: float = 0.3,
        W_importance: float = 0.5,
        W_context: float = 0.2,
        # v2-next: Contextual Resonance & Interference weights (0 = disabled)
        W_relevance: float = 0.0,
        W_interference: float = 0.0,
        # Mode switch: "legacy" (v1 compatible) or "weighted" (v2)
        ranking_mode: str = "legacy",
        seed: Optional[int] = None,
        forgetting_threshold: float = 0.2,    # Default threshold for forgetting
        # v2-next: Memory capacity limits (0 = unlimited for backward compat)
        max_working: int = 0,
        max_longterm: int = 0,
        interference_cap: float = 0.8,
        # P1: Optional SurpriseStrategy plugin (replaces v3/v4 wrappers)
        surprise_strategy: Optional["SurpriseStrategy"] = None,
        arousal_threshold: float = 0.5,
        # Wave 3 (3-4): domain-supplied emotion lexicon {emotion: [keywords]}.
        # None -> the generic default bank below (byte-identical to pre-3-4).
        emotion_keywords: Optional[Dict[str, List[str]]] = None,
        # Reserved retrieval slots (weighted mode only): {memory type: count}
        # or a list of types (one slot each). None -> strict no-op.
        reserve_types: Optional[Any] = None,
        # Design-basis audit + fix proposals, 2026-10-05: three generic,
        # opt-in framework options for a "memory randomness, seed and
        # documentation" finding raised against one consuming domain's
        # case study. Every one defaults to False/off, so a caller that
        # does not pass these (every existing domain) gets BYTE-IDENTICAL
        # behaviour to before this change.
        #
        # deterministic_consolidation: when True, an item with importance
        # >= consolidation_threshold ALWAYS enters long-term memory (no
        # random draw; self.rng.random() is not even called for this
        # item, so the rng stream another caller might also read from
        # this engine is unaffected). When False (default), the
        # pre-existing stochastic draw (consolidation_prob * importance)
        # is unchanged.
        deterministic_consolidation: bool = False,
        # decay_ignore_emotion: when True, _apply_decay's emotion modifier
        # (high-emotion memories decay slower) is disabled -- every
        # memory decays at the bare decay_rate, regardless of its
        # classified emotion. When False (default), the pre-existing
        # emotion-weighted modifier is unchanged.
        decay_ignore_emotion: bool = False,
        # decay_by_calendar_year: when True, _apply_decay's "age" is the
        # difference between the CALLER-SUPPLIED "year" metadata of each
        # memory (echoed through final_metadata into the stored item,
        # see _add_memory_internal) and the latest such year across that
        # agent's own working+long-term store, instead of the difference
        # between stored-item COUNTS (today's "timestamp"). The audit
        # found the item-count age over-decays by roughly 2x whenever a
        # domain stores more than one item per simulated year (e.g. one
        # outcome line plus one reflection per year).
        # Requires every working/long-term memory of an agent being
        # decayed to carry a numeric "year" in its metadata; raises
        # ValueError rather than silently falling back to the item-count
        # age if one is missing. When False (default), the pre-existing
        # item-count age is unchanged.
        decay_by_calendar_year: bool = False,
        # Opt-in composed decision memory: latest reflection appended after
        # event slots, excluded from both recent and significant selection.
        # None preserves the existing retrieval and payload bytes.
        reflection_slot: Optional[str] = None,
        # Equal decayed importance keeps earlier items by default. Domains
        # may opt into newer timestamps first without changing the score.
        significant_tie_break: str = "earlier",
    ):
        """
        Args:
            window_size: Number of recent memories always included
            top_k_significant: Number of historical events
            ranking_mode: "legacy" (v1) or "weighted" (v2)
            max_working: Working memory capacity (0 = unlimited)
            max_longterm: Long-term memory capacity (0 = unlimited)
            W_relevance: Weight for query-memory relevance (0 = disabled)
            W_interference: Weight for interference penalty (0 = disabled)
            reserve_types: Weighted mode only. Reserves retrieval slots for
                memory types, as ``{type: count}`` or a list of types (one
                slot each); a memory's type is its ``type`` metadata key.
                When the score-ranked top-k holds fewer than ``count`` items
                of a reserved type and unselected items of that type exist,
                the lowest-scoring selected item that is not of a reserved
                type is replaced by the best-scoring unselected item of that
                type; the result stays sorted by score and a swapped-in item
                carries ``"reserved": True``. Counts are integers (slots),
                not weights. Applies to EVERY weighted ``retrieve`` call of
                this engine (prompt retrieval and any other top-k read), one
                reserved slot per type per call. ``None`` (default) leaves
                retrieval unchanged.
        """
        import random
        # Kept as well as consumed. The seed governs which memories this engine promotes
        # to the long-term store, so it is a behavioural parameter -- but it reached no
        # artifact any run produced, which made `--memory-seed` unrecoverable from a
        # finished corpus. ExperimentRunner reads this back into the manifest.
        self.seed = seed
        self.rng = random.Random(seed)

        self.window_size = window_size
        self.top_k_significant = top_k_significant
        self.consolidation_prob = consolidation_prob
        self.consolidation_threshold = consolidation_threshold
        self.decay_rate = decay_rate
        self.ranking_mode = ranking_mode
        self.forgetting_threshold = forgetting_threshold
        self.reserve_types = self._normalise_reserve_types(reserve_types)
        if reflection_slot not in (None, "separate"):
            raise ValueError(f"reflection_slot must be None or 'separate', got {reflection_slot!r}")
        if significant_tie_break not in ("earlier", "recent"):
            raise ValueError(f"significant_tie_break must be 'earlier' or 'recent', got {significant_tie_break!r}")
        self.reflection_slot = reflection_slot
        self.significant_tie_break = significant_tie_break
        # Item 36b: see the three parameters' docstrings above. Opus
        # review P3-2 (2026-10-06): type-checked here, not left to raise
        # downstream on a string like "true" or "false" read straight
        # from YAML (a plain dict .get() does no coercion) -- the SAME
        # discipline AgentTypeConfig's own boolean getters and
        # WaterSystemConfig.hold_requests_fixed already apply.
        for _name, _value in (
            ("deterministic_consolidation", deterministic_consolidation),
            ("decay_ignore_emotion", decay_ignore_emotion),
            ("decay_by_calendar_year", decay_by_calendar_year),
        ):
            if not isinstance(_value, bool):
                raise ValueError(f"{_name} must be a bool, got {_value!r}")
        self.deterministic_consolidation = deterministic_consolidation
        self.decay_ignore_emotion = decay_ignore_emotion
        self.decay_by_calendar_year = decay_by_calendar_year

        # Memory capacity limits (0 = unlimited)
        self._max_working = max_working
        self._max_longterm = max_longterm
        self._interference_cap = interference_cap

        # P1: Optional surprise plugin (replaces v3/v4 wrappers)
        self._surprise_strategy = surprise_strategy
        self._arousal_threshold = arousal_threshold

        # Retrieval weights
        self.W_recency = W_recency
        self.W_importance = W_importance
        self.W_context = W_context
        self.W_relevance = W_relevance
        self.W_interference = W_interference

        # Working memory (short-term)
        self.working: Dict[str, List[Dict[str, Any]]] = {}
        # Long-term memory (consolidated)
        self.longterm: Dict[str, List[Dict[str, Any]]] = {}
        # Stored items remove_by_type has taken out, per agent. A new
        # memory's timestamp is the count of stored items plus this, so the
        # sequence continues as if nothing had been removed (decay reads
        # ages from timestamps). Empty unless remove_by_type runs, so every
        # other run keeps its exact timestamps.
        self._removed_count: Dict[str, int] = {}

        # Emotional encoding weights (Generic)
        self.emotional_weights = emotional_weights or {
            "critical": 1.0,     # Negative impact, failure, damage
            "major": 0.9,        # Significant event or choice
            "positive": 0.8,     # Success, reward, protection
            "shift": 0.7,        # Trust or behavioral changes
            "observation": 0.4,  # Neutral social observation
            "routine": 0.1       # No notable event
        }
        
        # Source differentiation (personal experience weighted higher)
        self.source_weights = source_weights or {
            "personal": 1.0,     # Direct experience
            "neighbor": 0.7,     # Proximate observation
            "community": 0.5,    # Group statistics
            "abstract": 0.3      # General information
        }
        
        # Emotion keywords for classification — domain-supplied via the ctor
        # (DomainPack.emotional_keywords through the factory, Wave 3 / 3-4)
        # or the generic default bank.
        self.emotion_keywords = emotion_keywords if emotion_keywords is not None else {
            "critical": ["failure", "damage", "destroyed", "loss", "error", "emergency"],
            "major": ["should have", "could have", "important", "decision"],
            "positive": ["success", "improved", "protected", "approved", "gain"],
            "shift": ["trust", "reliable", "doubt", "skeptic", "change"]
        }
    
    def _classify_emotion(self, content: str, agent: Optional[BaseAgent] = None) -> str:
        """Classify content emotion using keyword matching."""
        content_lower = content.lower()
        
        emotion_keywords = self.emotion_keywords
        if agent and hasattr(agent, 'memory_config'):
            emotion_keywords = agent.memory_config.get("emotion_keywords", self.emotion_keywords)
            
        for emotion, keywords in emotion_keywords.items():
            for kw in keywords:
                if kw in content_lower:
                    return emotion
        return "routine"
    
    def _classify_source(self, content: str, agent: Optional[BaseAgent] = None) -> str:
        """Classify content source type."""
        content_lower = content.lower()
        
        # Default patterns logic (Fixing the logic error)
        personal_patterns = ["i ", "my ", "me ", "i've"]
        neighbor_patterns = ["neighbor", "friend"]
        community_patterns = ["%", "community", "region", "area"]
        
        if agent and hasattr(agent, 'memory_config'):
            source_cfg = agent.memory_config.get("source_patterns", {})
            personal_patterns = source_cfg.get("personal", personal_patterns)
            neighbor_patterns = source_cfg.get("neighbor", neighbor_patterns)
            community_patterns = source_cfg.get("community", community_patterns)

        if any(w in content_lower for w in personal_patterns):
            return "personal"
        elif any(w in content_lower for w in neighbor_patterns):
            return "neighbor"
        elif any(w in content_lower for w in community_patterns):
            return "community"
        return "abstract"
    
    def _compute_importance(self, content: str, metadata: Optional[Dict] = None, agent: Optional[BaseAgent] = None) -> float:
        """Compute memory importance score [0-1] based on emotion and source."""
        # Allow direct override via metadata
        if metadata and "importance" in metadata:
            return float(metadata["importance"])
            
        emotion = metadata.get("emotion") if metadata else None
        source = metadata.get("source") if metadata else None
        
        if emotion is None: emotion = self._classify_emotion(content, agent)
        if source is None: source = self._classify_source(content, agent)
        
        emotional_weights = self.emotional_weights
        source_weights = self.source_weights
        
        if agent and hasattr(agent, 'memory_config'):
            emotional_weights = agent.memory_config.get("emotional_weights", self.emotional_weights)
            source_weights = agent.memory_config.get("source_weights", self.source_weights)

        emotion_w = emotional_weights.get(emotion, 0.1)
        source_w = source_weights.get(source, 0.3)
        
        # Combined importance = emotion × source (both 0-1)
        return emotion_w * source_w
    
    def add_memory(self, agent_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Standard add_memory (Compatibility)."""
        # We don't have agent object here, so we use default classification
        self._add_memory_internal(agent_id, content, metadata=metadata)

    def add_memory_for_agent(self, agent: BaseAgent, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Added for Phase 12: Context-aware memory scoring."""
        self._add_memory_internal(agent.id, content, metadata=metadata, agent=agent)

    def _add_memory_internal(self, agent_id: str, content: str, metadata: Optional[Dict[str, Any]] = None, agent: Optional[BaseAgent] = None):
        """Internal worker for adding memory with scoring."""
        if agent_id not in self.working:
            self.working[agent_id] = []
        if agent_id not in self.longterm:
            self.longterm[agent_id] = []

        # Revised logic for importance, emotion, source.
        # Initialize importance, emotion, and source. Prioritize metadata if available.
        importance = 0.5
        emotion = "routine"
        source = "abstract"

        if metadata:
            importance = float(metadata.get("importance", importance))
            emotion = metadata.get("emotion", self._classify_emotion(content, agent))
            source = metadata.get("source", self._classify_source(content, agent))
        else:
            emotion = self._classify_emotion(content, agent)
            source = self._classify_source(content, agent)
            importance = self._compute_importance(content, {"emotion": emotion, "source": source}, agent)

        final_metadata = metadata.copy() if metadata else {}
        final_metadata["importance"] = importance
        final_metadata["emotion"] = emotion
        final_metadata["source"] = source

        memory_item = {
            "content": content,
            "importance": importance,
            "emotion": emotion,
            "source": source,
            "timestamp": (len(self.working[agent_id]) + len(self.longterm[agent_id])
                          + self._removed_count.get(agent_id, 0)),
            "consolidated": False,
            **final_metadata
        }

        self.working[agent_id].append(memory_item)

        # Stochastic consolidation: high importance items have chance to go
        # to long-term. Item 36b: deterministic_consolidation (opt-in,
        # default off) replaces the random draw with "always consolidate"
        # for every item at or above the threshold -- no rng.random() call
        # at all in that branch, so this option changes nothing about the
        # rng stream any other caller on this engine instance reads.
        if importance >= self.consolidation_threshold:  # Configurable threshold
            if self.deterministic_consolidation:
                should_consolidate = True
            else:
                consolidate_p = self.consolidation_prob * importance
                should_consolidate = self.rng.random() < consolidate_p
            if should_consolidate:
                memory_item["consolidated"] = True
                # Deep copy to fully isolate working and longterm stores
                self.longterm[agent_id].append(copy.deepcopy(memory_item))

        # Enforce capacity limits if configured
        self._enforce_capacity(agent_id)
    
    def _apply_decay(
        self, memories: List[Dict], current_time: int,
        current_year: Optional[int] = None,
    ) -> List[Dict]:
        """Apply emotional time decay (Legacy Logic).

        Item 36b (opt-in, both default off, byte-identical when off):
        - ``decay_ignore_emotion``: the emotion modifier below becomes
          1.0 for every memory (bare ``decay_rate``), instead of varying
          by the memory's classified emotion.
        - ``decay_by_calendar_year``: ``age`` is ``current_year -
          m["year"]`` instead of ``current_time - m["timestamp"]``. The
          caller must then also pass ``current_year`` (the retrieval
          call's own "now", computed the same way as ``current_time`` but
          over each memory's "year" metadata); every memory in
          ``memories`` must carry a numeric "year" -- a missing one
          raises rather than silently falling back to the item-count age,
          since that would quietly re-introduce the ~2x over-decay this
          option exists to remove.
        """
        import math
        decayed = []
        for m in memories:
            if self.decay_by_calendar_year:
                if current_year is None or m.get("year") is None:
                    raise ValueError(
                        "HumanCentricMemoryEngine._apply_decay: "
                        "decay_by_calendar_year is True but this memory "
                        f"has no numeric 'year' metadata (content={m.get('content')!r}) "
                        "or the caller passed no current_year; refusing to "
                        "silently fall back to the item-count age."
                    )
                age = current_year - m["year"]
            else:
                age = current_time - m["timestamp"]
            # Emotion-modified decay: high emotion memories decay slower,
            # unless decay_ignore_emotion disables the modifier (item 36b).
            if self.decay_ignore_emotion:
                emotion_modifier = 1.0
            else:
                emotion_modifier = 1.0 - (0.5 * self.emotional_weights.get(m.get("emotion"), 0.1))
            effective_decay = self.decay_rate * emotion_modifier
            decay_factor = math.exp(-effective_decay * age)
            m["decayed_importance"] = m["importance"] * decay_factor
            if m["decayed_importance"] > 0.05:  # Threshold for forgetting
                decayed.append(m)
        return decayed

    def _current_year_for_decay(self, working: List[Dict], longterm: List[Dict]) -> Optional[int]:
        """Item 36b: the "now" year for ``decay_by_calendar_year``, the max
        "year" metadata across an agent's working + long-term store --
        the same combined-store convention ``current_time`` already uses
        for the item-count age. Returns None (decay then uses the
        item-count age) when the option is off; raises if it is on and
        any memory in either list lacks a numeric "year".
        """
        if not self.decay_by_calendar_year:
            return None
        combined = working + longterm
        if not combined:
            return None
        years = [m.get("year") for m in combined]
        if any(y is None for y in years):
            missing = [m.get("content") for m in combined if m.get("year") is None]
            raise ValueError(
                "HumanCentricMemoryEngine: decay_by_calendar_year is True but "
                f"{len(missing)} memor{'y' if len(missing) == 1 else 'ies'} have no "
                f"numeric 'year' metadata (e.g. content={missing[0]!r}); every "
                "add_memory_for_agent call must pass metadata['year'] when this "
                "option is on."
            )
        return max(years)

    # ── P2 Innovation: Contextual Resonance ──────────────────────────

    def _contextual_resonance(self, query: str, memory_content: str) -> float:
        """Compute keyword-overlap relevance between query and memory.

        Uses the overlap coefficient: |A ∩ B| / min(|A|, |B|).
        This is robust to asymmetric lengths (short query vs long memory).

        Inspired by Park et al. (2023) *relevance* dimension and
        Tulving's encoding-specificity principle.

        Args:
            query: Retrieval query or context string
            memory_content: The memory's content text

        Returns:
            Relevance score [0-1], 1.0 = perfect keyword overlap.
            Returns 0.0 when query is empty or no keywords match.
        """
        if not query or not memory_content:
            return 0.0

        query_tokens = set(query.lower().split()) - self._STOPWORDS
        memory_tokens = set(memory_content.lower().split()) - self._STOPWORDS

        if not query_tokens or not memory_tokens:
            return 0.0

        overlap = len(query_tokens & memory_tokens)
        denominator = min(len(query_tokens), len(memory_tokens))
        return overlap / denominator if denominator > 0 else 0.0

    # ── P2 Innovation: Interference-Based Forgetting ───────────────

    def _interference_penalty(
        self, memory: Dict, newer_memories: List[Dict]
    ) -> float:
        """Compute retroactive interference from newer similar memories.

        When a newer memory covers similar content, it partially
        suppresses retrieval of the older memory — modelling the
        well-established retroactive-interference effect.

        Reference: Anderson & Neely (1996), Wixted (2004).

        Args:
            memory: The memory being scored
            newer_memories: Memories with timestamp > this memory's timestamp

        Returns:
            Penalty in [0, 1]. 0 = no interference, 1 = fully suppressed.
        """
        if not newer_memories:
            return 0.0

        content = memory.get("content", "")
        max_sim = 0.0
        for newer in newer_memories:
            sim = self._contextual_resonance(content, newer.get("content", ""))
            if sim > max_sim:
                max_sim = sim
        # Scale: high similarity → high interference, capped to preserve
        # partial retrieval of older memories (dual-process memory models).
        # NOTE: O(n²) per retrieval — acceptable for 20-100 memories.
        # TODO: cache tokenization if scaling beyond 500 memories.
        return min(max_sim * self._interference_cap, self._interference_cap)

    def _enforce_capacity(self, agent_id: str) -> None:
        """Enforce working and long-term memory capacity limits.

        Working memory overflow: consolidated items are removed first (they
        are safely duplicated in long-term).  If still over capacity, the
        oldest non-consolidated items are dropped.

        Long-term memory overflow: lowest-importance items are evicted.

        When both limits are 0 (the default), this method is a no-op,
        preserving full backward compatibility.
        """
        # --- Working memory cap ---
        if self._max_working > 0:
            working = self.working.get(agent_id, [])
            if len(working) > self._max_working:
                # Phase 1: prefer removing consolidated items (safe in longterm)
                consolidated = [m for m in working if m.get("consolidated")]
                non_consolidated = [m for m in working if not m.get("consolidated")]

                if len(non_consolidated) <= self._max_working:
                    keep = self._max_working - len(non_consolidated)
                    to_keep = (
                        consolidated[-keep:] + non_consolidated if keep > 0
                        else non_consolidated
                    )
                    # Restore temporal order after splitting by consolidation status
                    to_keep.sort(key=lambda m: m.get("timestamp", 0))
                    self.working[agent_id] = to_keep
                else:
                    # Even non-consolidated exceeds cap; keep most recent
                    self.working[agent_id] = non_consolidated[-self._max_working:]

        # --- Long-term memory cap ---
        if self._max_longterm > 0:
            lt = self.longterm.get(agent_id, [])
            if len(lt) > self._max_longterm:
                # Evict lowest-importance items (sorted copy to preserve temporal order)
                sorted_lt = sorted(lt, key=lambda m: m.get("importance", 0))
                overflow = len(sorted_lt) - self._max_longterm
                self.longterm[agent_id] = sorted_lt[overflow:]
    
    @staticmethod
    def _normalise_reserve_types(reserve_types: Optional[Any]) -> Optional[Dict[str, int]]:
        """``None``/empty -> None; a list of types -> one slot each; a dict
        -> {type: int(count)} with non-positive counts dropped."""
        if not reserve_types:
            return None
        if isinstance(reserve_types, str):
            reserve_types = [reserve_types]
        if isinstance(reserve_types, dict):
            out = {str(k): int(v) for k, v in reserve_types.items() if int(v) > 0}
        else:
            out = {}
            for t in reserve_types:
                out[str(t)] = out.get(str(t), 0) + 1
        return out or None

    def _apply_reserved_slots(self, scored: List, selected: List) -> "tuple[List, set]":
        """Swap reserved-type items into ``selected`` (see ``reserve_types``
        in ``__init__``). Returns (selection sorted by score, ids of the
        memories that were swapped in)."""
        selected = list(selected)
        chosen = {id(m) for m, _ in selected}
        swapped: set = set()
        for mtype, count in self.reserve_types.items():
            have = sum(1 for m, _ in selected if m.get("type") == mtype)
            need = count - have
            if need <= 0:
                continue
            candidates = sorted(
                (x for x in scored if x[0].get("type") == mtype and id(x[0]) not in chosen),
                key=lambda x: x[1], reverse=True,
            )
            for cand in candidates[:need]:
                victims = [x for x in selected if x[0].get("type") not in self.reserve_types]
                if not victims:
                    break
                victim = min(victims, key=lambda x: x[1])
                selected.remove(victim)
                chosen.discard(id(victim[0]))
                selected.append(cand)
                chosen.add(id(cand[0]))
                swapped.add(id(cand[0]))
        selected.sort(key=lambda x: x[1], reverse=True)
        return selected, swapped

    @staticmethod
    def _memory_payload(memory: Dict[str, Any], final_score: Optional[float] = None) -> Dict[str, Any]:
        payload = {
            "content": memory.get("content", ""),
            "emotion": memory.get("emotion", "routine"),
            "importance": memory.get("importance", 0.1),
            "source": memory.get("source", "abstract"),
            "timestamp": memory.get("timestamp", 0),
        }
        if final_score is not None:
            payload["final_score"] = final_score
        return payload

    def retrieve(self, agent: BaseAgent, query: Optional[str] = None, top_k: int = 5, contextual_boosters: Optional[Dict[str, float]] = None, window_size: Optional[int] = None, top_k_significant: Optional[int] = None, **kwargs) -> List[Dict[str, Any]]:
        """Retrieve memories using dual mode: Legacy (v1) or Weighted (v2).

        Legacy mode is the composed retrieval: the ``window_size`` most recent
        working memories are always included, plus the ``top_k_significant``
        long-term memories with the highest decayed importance that are not
        already in the window. Long-term items whose decayed importance is at
        or below 0.05 are dropped (``_apply_decay``); ties in decayed
        importance keep the earlier item first (stable ordering over the
        timestamp-ordered store). ``top_k`` is ignored in this mode.
        ``window_size`` / ``top_k_significant`` override the constructor
        values for this call when given (None = constructor value).
        With ``reflection_slot='separate'``, reflections never consume event
        slots and only the latest stored reflection is appended. A call-local
        ``reflection_slot=None`` restores the original selection for readers
        that require it. ``significant_tie_break='recent'`` chooses newer
        timestamps for equal decayed importance; both options default off.
        """
        
        if agent.id not in self.working:
            initial_mem = getattr(agent, 'memory', [])
            self.working[agent.id] = []
            self.longterm[agent.id] = []
            if isinstance(initial_mem, list):
                for m in initial_mem:
                    # Ensure metadata is correctly extracted and passed.
                    if isinstance(m, dict) and "content" in m:
                        content_to_add = m["content"]
                        metadata_to_add = m.get("metadata", {})
                        self.add_memory_for_agent(agent, content_to_add, metadata_to_add)
                    else:
                        # Handle cases where 'm' is just a string (no metadata).
                        self.add_memory_for_agent(agent, m)
        
        working = self.working.get(agent.id, [])
        longterm = self.longterm.get(agent.id, [])
        
        if not working and not longterm:
            return []
        
        max_timestamp = -1
        if working:
            max_timestamp = max(max_timestamp, max(m["timestamp"] for m in working))
        if longterm:
            max_timestamp = max(max_timestamp, max(m["timestamp"] for m in longterm))
        current_time = max_timestamp + 1
        # Item 36b: None (decay then uses the item-count age) unless
        # decay_by_calendar_year is on.
        current_year = self._current_year_for_decay(working, longterm)

        reflection_slot = kwargs.get("reflection_slot", self.reflection_slot)
        if reflection_slot not in (None, "separate"):
            raise ValueError(f"reflection_slot must be None or 'separate', got {reflection_slot!r}")
        separate_reflection = reflection_slot == "separate"
        latest_reflection = None
        if separate_reflection:
            reflections = [m for m in working + longterm if m.get("type") == "reflection"]
            latest_reflection = max(reflections, key=lambda m: m["timestamp"], default=None)
            working = [m for m in working if m.get("type") != "reflection"]
            longterm = [m for m in longterm if m.get("type") != "reflection"]

        def payload(memory, score=None):
            item = self._memory_payload(memory, score)
            if separate_reflection:
                item.update({key: memory[key] for key in ("type", "year") if key in memory})
            return item

        def finish(items):
            if latest_reflection is not None:
                items.append(payload(latest_reflection))
            return items

        # --- MODE 1: LEGACY (v1 Parity for Groups A/B) ---
        if self.ranking_mode == "legacy":
             _window = self.window_size if window_size is None else int(window_size)
             _n_sig = self.top_k_significant if top_k_significant is None else int(top_k_significant)
             recent = working[-_window:] if _window > 0 else []
             recent_texts = [m["content"] for m in recent]

             decayed_longterm = self._apply_decay(longterm, current_time, current_year)
             
             # Contextual Boosters are IGNORED in legacy mode
             # Use generic significance key
             if self.significant_tie_break == "recent":
                 significance_key = lambda m: (m.get("decayed_importance", 0), m["timestamp"])
             else:
                 significance_key = lambda m: m.get("decayed_importance", 0)
             # Opt-in composition scans the whole pool so duplicate content
             # cannot leave a slot empty while a distinct eligible item exists.
             candidate_count = (len(decayed_longterm) if separate_reflection
                                else _n_sig + len(recent_texts) + 2)
             top_significant = heapq.nlargest(candidate_count, decayed_longterm, key=significance_key)
             if separate_reflection and _n_sig <= 0:
                 top_significant = []
             
             # Content-level dedup (2026-09-26): two stored long-term items
             # can carry visually-identical text that differs only in
             # incidental leading/trailing whitespace, which an exact ==
             # comparison lets through as two distinct significant slots
             # (the same text shown twice in the composed block). Compare
             # on a stripped copy; the stored/returned content itself is
             # never modified. Ordering (by decayed importance, ties
             # earlier-first) and the 0.05 decay floor in ``_apply_decay``
             # are both unchanged; a duplicate candidate is simply skipped
             # in favour of the next-ranked one, same as an already-in-
             # recent-window candidate was skipped before this change.
             recent_texts_normalized = {t.strip() for t in recent_texts}
             significant = []
             seen_significant = set()
             for m in top_significant:
                 content_normalized = m["content"].strip()
                 if (content_normalized not in recent_texts_normalized
                         and content_normalized not in seen_significant):
                     significant.append(payload(m, round(float(m.get("decayed_importance", m.get("importance", 0.0))), 4)))
                     seen_significant.add(content_normalized)
                 if len(significant) >= _n_sig:
                     break

             recent_payload = [payload(m) for m in recent]
             return finish(significant + recent_payload)

        # --- MODE 2: WEIGHTED (v2 Model for Stress Test) ---
        else:
            # Correctly combine and deduplicate memories while preserving metadata.
            all_memories_map = {}
            for mem in self._apply_decay(longterm, current_time, current_year):
                all_memories_map[mem["content"]] = mem
            for mem in working:
                all_memories_map[mem["content"]] = mem
            all_memories = list(all_memories_map.values())

            scored_memories = []
            for mem in all_memories:
                age = current_time - mem["timestamp"]
                recency_score = 1.0 - (age / max(current_time, 1))
                importance_score = mem.get("importance", mem.get("decayed_importance", 0.1))

                contextual_boost = 0.0
                if contextual_boosters:
                    for tag_key_val, boost_val in contextual_boosters.items():
                        if ":" in tag_key_val:
                            tag_cat, tag_val = tag_key_val.split(":", 1)
                            if mem.get(tag_cat) == tag_val:
                                contextual_boost = boost_val
                                break

                # P2: Contextual Resonance — query-memory keyword relevance
                relevance_score = 0.0
                if self.W_relevance > 0 and query:
                    relevance_score = self._contextual_resonance(query, mem["content"])

                # P2: Interference — newer similar memories suppress older ones
                interference = 0.0
                if self.W_interference > 0:
                    mem_ts = mem.get("timestamp", 0)
                    newer = [m for m in all_memories if m.get("timestamp", 0) > mem_ts]
                    interference = self._interference_penalty(mem, newer)

                final_score = (
                    (recency_score * self.W_recency)
                    + (importance_score * self.W_importance)
                    + (contextual_boost * self.W_context)
                    + (relevance_score * self.W_relevance)
                    - (interference * self.W_interference)
                )

                logger.debug(f"Memory: '{mem['content']}'")
                logger.debug(f"  Timestamp: {mem['timestamp']}, Current Time: {current_time}")
                logger.debug(f"  Emotion: {mem.get('emotion')}, Source: {mem.get('source')}")
                logger.debug(
                    f"  Scores - Recency: {recency_score:.2f}, Importance: {importance_score:.2f}, "
                    f"Contextual Boost: {contextual_boost:.2f}, "
                    f"Relevance: {relevance_score:.2f}, Interference: {interference:.2f}"
                )
                logger.debug(f"  Final Score: {final_score:.2f}")

                scored_memories.append((mem, final_score))
            
            top_k_memories = heapq.nlargest(top_k, scored_memories, key=lambda x: x[1])
            if not self.reserve_types or top_k <= 0:
                return finish([payload(mem, round(float(score), 4)) for mem, score in top_k_memories])
            top_k_memories, swapped = self._apply_reserved_slots(scored_memories, top_k_memories)
            out = []
            for mem, score in top_k_memories:
                item = payload(mem, round(float(score), 4))
                if id(mem) in swapped:
                    item["reserved"] = True
                out.append(item)
            return finish(out)

    def retrieve_stratified(
        self,
        agent_id: str,
        allocation: Optional[Dict[str, int]] = None,
        total_k: int = 10,
        contextual_boosters: Optional[Dict[str, float]] = None,
    ) -> List[str]:
        """Retrieve memories with source-stratified diversity guarantee.

        Instead of pure top-k by score, allocates retrieval slots by source category.
        This ensures reflection prompts see a mix of personal experiences,
        neighbor observations, community events, and past reflections.

        Args:
            agent_id: Agent to retrieve for
            allocation: Dict mapping source -> max slots.
                        Default: {"personal": 4, "neighbor": 2, "community": 2, "reflection": 1, "abstract": 1}
            total_k: Total memories to return (cap)
            contextual_boosters: Same as retrieve() -- optional score boosters

        Returns:
            List of memory content strings, stratified by source
        """
        if allocation is None:
            allocation = {
                "personal": 4,
                "neighbor": 2,
                "community": 2,
                "reflection": 1,
                "abstract": 1,
            }

        working = self.working.get(agent_id, [])
        longterm = self.longterm.get(agent_id, [])

        if not working and not longterm:
            return []

        # Combine all memories (same dedup logic as retrieve weighted mode)
        max_timestamp = -1
        if working:
            max_timestamp = max(max_timestamp, max(m["timestamp"] for m in working))
        if longterm:
            max_timestamp = max(max_timestamp, max(m["timestamp"] for m in longterm))
        current_time = max_timestamp + 1
        current_year = self._current_year_for_decay(working, longterm)

        all_memories_map = {}
        for mem in self._apply_decay(longterm, current_time, current_year):
            all_memories_map[mem["content"]] = mem
        for mem in working:
            all_memories_map[mem["content"]] = mem
        all_memories = list(all_memories_map.values())

        # Score all memories (same scoring as weighted mode)
        scored = []
        for mem in all_memories:
            age = current_time - mem["timestamp"]
            recency_score = 1.0 - (age / max(current_time, 1))
            importance_score = mem.get("importance", mem.get("decayed_importance", 0.1))

            contextual_boost = 0.0
            if contextual_boosters:
                for tag_key_val, boost_val in contextual_boosters.items():
                    if ":" in tag_key_val:
                        tag_cat, tag_val = tag_key_val.split(":", 1)
                        if mem.get(tag_cat) == tag_val:
                            contextual_boost = boost_val
                            break

            # P2: Contextual Resonance disabled — stratified retrieval
            # prioritizes source diversity over query relevance.
            relevance_score = 0.0

            # P2: Interference — newer similar memories suppress older ones
            interference = 0.0
            if self.W_interference > 0:
                mem_ts = mem.get("timestamp", 0)
                newer = [m for m in all_memories if m.get("timestamp", 0) > mem_ts]
                interference = self._interference_penalty(mem, newer)

            final_score = (
                (recency_score * self.W_recency)
                + (importance_score * self.W_importance)
                + (contextual_boost * self.W_context)
                + (relevance_score * self.W_relevance)
                - (interference * self.W_interference)
            )

            scored.append((mem, final_score))

        # Group by source
        import heapq
        source_groups: Dict[str, List] = {}
        for mem, score in scored:
            src = mem.get("source", "abstract")
            # Map reflection-sourced memories
            if mem.get("type") == "reflection" or "Consolidated Reflection" in mem.get("content", ""):
                src = "reflection"
            if src not in source_groups:
                source_groups[src] = []
            source_groups[src].append((mem["content"], score))

        # Sort each group by score descending
        for src in source_groups:
            source_groups[src].sort(key=lambda x: -x[1])

        # Allocate slots per source
        result = []
        remaining_slots = total_k

        for src, max_slots in allocation.items():
            available = source_groups.get(src, [])
            take = min(max_slots, len(available), remaining_slots)
            for content, score in available[:take]:
                result.append(content)
                remaining_slots -= 1
            if remaining_slots <= 0:
                break

        # Fill remaining slots with highest-scoring memories from any source
        if remaining_slots > 0:
            all_sorted = sorted(scored, key=lambda x: -x[1])
            for mem, score in all_sorted:
                if mem["content"] not in result and remaining_slots > 0:
                    result.append(mem["content"])
                    remaining_slots -= 1

        return result

    def forget(self, agent_id: str, strategy: str = "importance", threshold: Optional[float] = None) -> int:
        """Forget memories using specified strategy.

        Strategies:
        - 'importance': Remove memories below threshold
        - 'time': Remove oldest memories beyond capacity
        - 'emotion': Remove low-emotion memories

        Returns: Number of memories forgotten
        """
        # Use instance default if threshold not provided
        if threshold is None:
            threshold = self.forgetting_threshold

        if agent_id not in self.working:
            return 0

        original_count = len(self.working[agent_id]) + len(self.longterm.get(agent_id, []))
        
        if strategy == "importance":
            self.working[agent_id] = [m for m in self.working[agent_id] if m.get("importance", 0) >= threshold]
            self.longterm[agent_id] = [m for m in self.longterm.get(agent_id, []) if m.get("importance", 0) >= threshold]
        elif strategy == "time":
            # Keep only recent 50 in working, recent 20 high-importance in longterm
            self.working[agent_id] = self.working[agent_id][-50:]
            self.longterm[agent_id] = sorted(self.longterm.get(agent_id, []), 
                                              key=lambda x: x.get("importance", 0), reverse=True)[:20]
        
        new_count = len(self.working[agent_id]) + len(self.longterm.get(agent_id, []))
        return original_count - new_count
    
    def remove_by_type(self, agent_id: str, memory_type: str) -> int:
        """Remove every memory of ``agent_id`` whose ``type`` metadata is
        ``memory_type``, from working and long-term memory alike.

        Returns the number of stored items removed (an item consolidated
        into long-term memory is stored twice and counts twice). Memories
        added later keep the timestamps they would have had without the
        removal (``_removed_count``), so decay and recency of the items
        that remain are unchanged.
        """
        removed = 0
        for store in (self.working, self.longterm):
            items = store.get(agent_id)
            if not items:
                continue
            kept = [m for m in items if m.get("type") != memory_type]
            removed += len(items) - len(kept)
            store[agent_id] = kept
        if removed:
            self._removed_count[agent_id] = self._removed_count.get(agent_id, 0) + removed
        return removed

    def clear(self, agent_id: str):
        """Clear all memories for agent."""
        self.working[agent_id] = []
        self.longterm[agent_id] = []
        self._removed_count.pop(agent_id, None)

    # ── P1: Optional Surprise Plugin Interface ─────────────────────

    def observe(self, observation: Dict[str, Any]) -> float:
        """Feed an observation to the attached surprise strategy.

        This replaces the heavyweight v3/v4 wrapper pattern.  When no
        surprise strategy is configured, returns 0.0 (no surprise).

        The observation structure depends on the attached strategy:
        - EMASurpriseStrategy: ``{<stimulus_key>: 2.5}`` (key set at construction time)
        - SymbolicSurpriseStrategy: multi-key numeric dict
        - DecisionConsistencySurprise: ``{"action": "increase_demand"}``

        Args:
            observation: Strategy-specific observation dict.

        Returns:
            Surprise value [0-1]. 0.0 if no plugin attached.
        """
        if self._surprise_strategy is None:
            return 0.0
        return self._surprise_strategy.update(observation)

    def get_cognitive_system(self) -> str:
        """Determine cognitive system based on current arousal.

        System 1 (routine): low surprise → fast, heuristic retrieval
        System 2 (deliberate): high surprise → careful, weighted retrieval

        Returns:
            "SYSTEM_1" or "SYSTEM_2". Always "SYSTEM_1" if no plugin.
        """
        if self._surprise_strategy is None:
            return "SYSTEM_1"
        arousal = self._surprise_strategy.get_arousal()
        return "SYSTEM_2" if arousal > self._arousal_threshold else "SYSTEM_1"

    def reset_surprise(self) -> None:
        """Reset surprise strategy state for a new simulation episode.

        Clears internal tracking (expectations, frequency maps, etc.)
        without affecting stored memories.  No-op if no plugin attached.
        """
        if self._surprise_strategy is not None:
            self._surprise_strategy.reset()

    def get_surprise_trace(self) -> Optional[Dict[str, Any]]:
        """Get trace data from the surprise plugin for XAI.

        Returns:
            Strategy-specific trace dict, or None if no plugin.
        """
        if self._surprise_strategy is None:
            return None
        return self._surprise_strategy.get_trace()
