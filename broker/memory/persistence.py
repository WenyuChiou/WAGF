"""
Memory Persistence - Checkpoint and Resume Functionality.

Provides serialization and deserialization of agent memory states for:
- Experiment reproducibility
- Cross-session learning (lifelong learning)
- Memory state snapshots

Reference:
- Task-050B: Memory Checkpoint/Resume
- MemGPT (2023): Archival memory persistence
- LangMem (LangChain, 2024): Long-term memory SDK

Example:
    >>> checkpoint = MemoryCheckpoint()
    >>> checkpoint.save("agent_1", store, Path("checkpoint.json"))
    >>> agent_id, memories, state = checkpoint.load(Path("checkpoint.json"))
"""

import json
import time
import hashlib
from dataclasses import asdict, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import logging

import numpy as np

from .unified_engine import UnifiedMemoryItem

logger = logging.getLogger(__name__)

# Checkpoint format version
CHECKPOINT_VERSION = "1.0"


class MemorySerializer:
    """
    Serializes and deserializes UnifiedMemoryItem objects.

    Handles numpy arrays and other non-JSON-serializable types.
    """

    @staticmethod
    def serialize_item(item: UnifiedMemoryItem) -> Dict[str, Any]:
        """
        Serialize a UnifiedMemoryItem to a JSON-compatible dict.

        Args:
            item: Memory item to serialize

        Returns:
            Dictionary representation
        """
        data = {
            "content": item.content,
            "timestamp": item.timestamp,
            "emotion": item.emotion,
            "source": item.source,
            "base_importance": item.base_importance,
            "surprise_score": item.surprise_score,
            "novelty_score": item.novelty_score,
            "agent_id": item.agent_id,
            "year": item.year,
            "tags": item.tags.copy() if item.tags else [],
            "metadata": item.metadata.copy() if item.metadata else {},
            "_current_importance": item._current_importance,
        }

        # Handle embedding (numpy array -> list)
        if item.embedding is not None:
            data["embedding"] = item.embedding.tolist()
        else:
            data["embedding"] = None

        return data

    @staticmethod
    def deserialize_item(data: Dict[str, Any]) -> UnifiedMemoryItem:
        """
        Deserialize a dict to UnifiedMemoryItem.

        Args:
            data: Dictionary from JSON

        Returns:
            UnifiedMemoryItem instance
        """
        # Handle embedding (list -> numpy array)
        embedding = None
        if data.get("embedding") is not None:
            embedding = np.array(data["embedding"], dtype=np.float32)

        item = UnifiedMemoryItem(
            content=data["content"],
            timestamp=data["timestamp"],
            emotion=data.get("emotion", "neutral"),
            source=data.get("source", "personal"),
            base_importance=data.get("base_importance", 0.5),
            surprise_score=data.get("surprise_score", 0.0),
            novelty_score=data.get("novelty_score", 0.0),
            agent_id=data.get("agent_id", ""),
            year=data.get("year", 0),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            embedding=embedding,
        )

        # Restore current importance if set
        if data.get("_current_importance") is not None:
            item._current_importance = data["_current_importance"]

        return item


class MemoryCheckpoint:
    """
    Save and restore agent memory states.

    Provides checkpoint/resume functionality for:
    - Single agent memory snapshots
    - Multi-agent experiment state
    - Belief state persistence
    - Surprise strategy state

    Args:
        compress: Use gzip compression for large checkpoints
        include_embeddings: Include embedding vectors (larger files)

    Example:
        >>> checkpoint = MemoryCheckpoint()
        >>> checkpoint.save_agent(
        ...     agent_id="Agent_42",
        ...     memories=memory_list,
        ...     path=Path("agent_42_year5.json"),
        ...     metadata={"year": 5, "experiment": "flood_sim"}
        ... )
        >>> agent_id, memories, state = checkpoint.load(Path("agent_42_year5.json"))
    """

    def __init__(
        self,
        compress: bool = False,
        include_embeddings: bool = True,
    ):
        self.compress = compress
        self.include_embeddings = include_embeddings
        self._serializer = MemorySerializer()

    def save_agent(
        self,
        agent_id: str,
        memories: List[UnifiedMemoryItem],
        path: Union[str, Path],
        metadata: Optional[Dict[str, Any]] = None,
        belief_state: Optional[Dict[str, float]] = None,
        surprise_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Save a single agent's memory state to file.

        Args:
            agent_id: Agent identifier
            memories: List of memory items to save
            path: Output file path
            metadata: Optional experiment metadata
            belief_state: Optional belief values (trust, risk perception)
            surprise_state: Optional surprise strategy state
        """
        path = Path(path)

        # Serialize memories
        serialized_memories = []
        for mem in memories:
            mem_data = self._serializer.serialize_item(mem)
            if not self.include_embeddings:
                mem_data["embedding"] = None
            serialized_memories.append(mem_data)

        # Build checkpoint structure
        checkpoint = {
            "version": CHECKPOINT_VERSION,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "agent_id": agent_id,
            "metadata": metadata or {},
            "memory_count": len(serialized_memories),
            "memories": serialized_memories,
            "belief_state": belief_state or {},
            "surprise_state": surprise_state or {},
            "checksum": self._compute_checksum(serialized_memories),
        }

        # Write to file
        if self.compress:
            import gzip
            with gzip.open(str(path) + ".gz", "wt", encoding="utf-8") as f:
                json.dump(checkpoint, f, indent=2)
            logger.info(f"Saved compressed checkpoint: {path}.gz ({len(memories)} memories)")
        else:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(checkpoint, f, indent=2)
            logger.info(f"Saved checkpoint: {path} ({len(memories)} memories)")

    def load(
        self,
        path: Union[str, Path],
        verify_checksum: bool = True,
    ) -> Tuple[str, List[UnifiedMemoryItem], Dict[str, Any]]:
        """
        Load agent memory state from checkpoint file.

        Args:
            path: Checkpoint file path
            verify_checksum: Verify data integrity

        Returns:
            Tuple of (agent_id, memories, state_dict)
            state_dict contains: metadata, belief_state, surprise_state

        Raises:
            FileNotFoundError: If checkpoint doesn't exist
            ValueError: If checksum verification fails
        """
        path = Path(path)

        # Handle compressed files
        if path.suffix == ".gz" or not path.exists() and Path(str(path) + ".gz").exists():
            import gzip
            actual_path = path if path.suffix == ".gz" else Path(str(path) + ".gz")
            with gzip.open(actual_path, "rt", encoding="utf-8") as f:
                checkpoint = json.load(f)
        else:
            with open(path, "r", encoding="utf-8") as f:
                checkpoint = json.load(f)

        # Version check
        version = checkpoint.get("version", "0.0")
        if version != CHECKPOINT_VERSION:
            logger.warning(
                f"Checkpoint version mismatch: {version} != {CHECKPOINT_VERSION}"
            )

        # Verify checksum
        if verify_checksum:
            stored_checksum = checkpoint.get("checksum")
            computed_checksum = self._compute_checksum(checkpoint["memories"])
            if stored_checksum and stored_checksum != computed_checksum:
                raise ValueError(
                    f"Checkpoint checksum mismatch: file may be corrupted"
                )

        # Deserialize memories
        memories = [
            self._serializer.deserialize_item(mem_data)
            for mem_data in checkpoint["memories"]
        ]

        # Build state dict
        state = {
            "metadata": checkpoint.get("metadata", {}),
            "belief_state": checkpoint.get("belief_state", {}),
            "surprise_state": checkpoint.get("surprise_state", {}),
            "created_at": checkpoint.get("created_at"),
            "version": checkpoint.get("version"),
        }

        agent_id = checkpoint["agent_id"]
        logger.info(f"Loaded checkpoint: {path} ({len(memories)} memories)")

        return agent_id, memories, state

    def save_experiment(
        self,
        agents: Dict[str, List[UnifiedMemoryItem]],
        path: Union[str, Path],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Save entire experiment state (all agents).

        Args:
            agents: Dict mapping agent_id -> memories
            path: Output file path
            metadata: Experiment metadata
        """
        path = Path(path)

        experiment = {
            "version": CHECKPOINT_VERSION,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "type": "experiment",
            "metadata": metadata or {},
            "agent_count": len(agents),
            "agents": {},
        }

        for agent_id, memories in agents.items():
            experiment["agents"][agent_id] = {
                "memory_count": len(memories),
                "memories": [
                    self._serializer.serialize_item(mem)
                    for mem in memories
                ],
            }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(experiment, f, indent=2)

        logger.info(
            f"Saved experiment checkpoint: {path} "
            f"({len(agents)} agents, "
            f"{sum(len(m) for m in agents.values())} total memories)"
        )

    def load_experiment(
        self,
        path: Union[str, Path],
    ) -> Tuple[Dict[str, List[UnifiedMemoryItem]], Dict[str, Any]]:
        """
        Load experiment state (all agents).

        Args:
            path: Checkpoint file path

        Returns:
            Tuple of (agents_dict, metadata)
        """
        path = Path(path)

        with open(path, "r", encoding="utf-8") as f:
            experiment = json.load(f)

        agents = {}
        for agent_id, agent_data in experiment["agents"].items():
            agents[agent_id] = [
                self._serializer.deserialize_item(mem_data)
                for mem_data in agent_data["memories"]
            ]

        metadata = experiment.get("metadata", {})
        logger.info(
            f"Loaded experiment: {path} ({len(agents)} agents)"
        )

        return agents, metadata

    def merge(
        self,
        old_memories: List[UnifiedMemoryItem],
        new_memories: List[UnifiedMemoryItem],
        strategy: str = "importance",
        max_memories: Optional[int] = None,
    ) -> List[UnifiedMemoryItem]:
        """
        Merge memories from different sessions.

        Strategies:
        - "importance": Keep highest importance memories
        - "recency": Keep most recent memories
        - "dedupe": Remove duplicates, keep all unique

        Args:
            old_memories: Memories from previous session
            new_memories: Memories from current session
            strategy: Merge strategy
            max_memories: Optional limit on total memories

        Returns:
            Merged memory list
        """
        # Combine all memories
        all_memories = old_memories + new_memories

        # Deduplicate by content hash
        seen = {}
        unique = []
        for mem in all_memories:
            content_hash = hashlib.md5(mem.content.encode()).hexdigest()
            if content_hash not in seen:
                seen[content_hash] = mem
                unique.append(mem)
            else:
                # Keep higher importance version
                existing = seen[content_hash]
                if mem.importance > existing.importance:
                    unique.remove(existing)
                    unique.append(mem)
                    seen[content_hash] = mem

        # Apply strategy
        if strategy == "importance":
            unique.sort(key=lambda m: m.importance, reverse=True)
        elif strategy == "recency":
            unique.sort(key=lambda m: m.timestamp, reverse=True)
        # "dedupe" just keeps unique memories without sorting

        # Apply limit
        if max_memories and len(unique) > max_memories:
            unique = unique[:max_memories]

        logger.info(
            f"Merged memories: {len(old_memories)} old + {len(new_memories)} new "
            f"-> {len(unique)} merged (strategy={strategy})"
        )

        return unique

    def _compute_checksum(self, memories: List[Dict]) -> str:
        """Compute checksum for memory list."""
        # Hash the serialized content
        content = json.dumps(
            [m.get("content", "") for m in memories],
            sort_keys=True
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# Convenience functions for quick use
def save_checkpoint(
    agent_id: str,
    memories: List[UnifiedMemoryItem],
    path: Union[str, Path],
    **kwargs
) -> None:
    """Quick function to save a checkpoint."""
    checkpoint = MemoryCheckpoint()
    checkpoint.save_agent(agent_id, memories, path, **kwargs)


def load_checkpoint(
    path: Union[str, Path]
) -> Tuple[str, List[UnifiedMemoryItem], Dict[str, Any]]:
    """Quick function to load a checkpoint."""
    checkpoint = MemoryCheckpoint()
    return checkpoint.load(path)
