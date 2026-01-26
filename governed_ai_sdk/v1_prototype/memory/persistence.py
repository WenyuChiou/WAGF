"""
Memory Persistence Layer.

Provides save/load functionality for agent memories across sessions.
Supports multiple storage backends:
- JSON: Simple file-based storage (one file per agent)
- SQLite: Database storage for larger experiments

Usage:
    >>> from governed_ai_sdk.v1_prototype.memory.persistence import JSONMemoryPersistence
    >>> persistence = JSONMemoryPersistence("./memory_store")
    >>> persistence.save("agent_001", memories)
    >>> loaded = persistence.load("agent_001")
"""

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class MemoryPersistence(ABC):
    """Abstract base for memory storage backends.

    All backends must implement save, load, and append operations.
    """

    @abstractmethod
    def save(self, agent_id: str, memories: List[Dict[str, Any]]) -> None:
        """Save all memories for an agent (overwrites existing).

        Args:
            agent_id: Unique agent identifier
            memories: List of memory dictionaries
        """
        pass

    @abstractmethod
    def load(self, agent_id: str) -> List[Dict[str, Any]]:
        """Load all memories for an agent.

        Args:
            agent_id: Unique agent identifier

        Returns:
            List of memory dictionaries (empty if none exist)
        """
        pass

    @abstractmethod
    def append(self, agent_id: str, memory: Dict[str, Any]) -> None:
        """Append a single memory to an agent's store.

        Args:
            agent_id: Unique agent identifier
            memory: Memory dictionary to append
        """
        pass

    def clear(self, agent_id: str) -> None:
        """Clear all memories for an agent.

        Args:
            agent_id: Unique agent identifier
        """
        self.save(agent_id, [])

    def exists(self, agent_id: str) -> bool:
        """Check if memories exist for an agent.

        Args:
            agent_id: Unique agent identifier

        Returns:
            True if memories exist
        """
        return len(self.load(agent_id)) > 0


class JSONMemoryPersistence(MemoryPersistence):
    """JSON file-based memory persistence.

    Creates one JSON file per agent in the specified directory.
    Simple and human-readable, suitable for small-medium experiments.

    File format: {agent_id}_memory.json
    """

    def __init__(self, base_path: str, indent: int = 2):
        """Initialize JSON persistence.

        Args:
            base_path: Directory path for storing memory files
            indent: JSON indentation level (default 2)
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.indent = indent
        self._lock = threading.Lock()

    def _agent_path(self, agent_id: str) -> Path:
        """Get file path for an agent's memories."""
        # Sanitize agent_id for filesystem
        safe_id = "".join(c if c.isalnum() or c in "_-" else "_" for c in agent_id)
        return self.base_path / f"{safe_id}_memory.json"

    def save(self, agent_id: str, memories: List[Dict[str, Any]]) -> None:
        """Save memories to JSON file."""
        with self._lock:
            path = self._agent_path(agent_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "agent_id": agent_id,
                        "saved_at": datetime.now().isoformat(),
                        "count": len(memories),
                        "memories": memories,
                    },
                    f,
                    indent=self.indent,
                    default=str,  # Handle non-serializable types
                )

    def load(self, agent_id: str) -> List[Dict[str, Any]]:
        """Load memories from JSON file."""
        path = self._agent_path(agent_id)
        if not path.exists():
            return []

        with self._lock:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("memories", [])
            except (json.JSONDecodeError, IOError):
                return []

    def append(self, agent_id: str, memory: Dict[str, Any]) -> None:
        """Append memory to JSON file."""
        memories = self.load(agent_id)
        memories.append(memory)
        self.save(agent_id, memories)

    def list_agents(self) -> List[str]:
        """List all agents with stored memories."""
        agents = []
        for path in self.base_path.glob("*_memory.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    agents.append(data.get("agent_id", path.stem.replace("_memory", "")))
            except (json.JSONDecodeError, IOError):
                continue
        return agents

    def get_metadata(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for an agent's memory store."""
        path = self._agent_path(agent_id)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "agent_id": data.get("agent_id"),
                    "saved_at": data.get("saved_at"),
                    "count": data.get("count", 0),
                }
        except (json.JSONDecodeError, IOError):
            return None


class SQLiteMemoryPersistence(MemoryPersistence):
    """SQLite database memory persistence.

    Stores all agents' memories in a single SQLite database.
    Suitable for larger experiments with many agents.

    Schema:
        memories(id, agent_id, content, created_at, metadata)
    """

    def __init__(self, db_path: str, table_name: str = "memories"):
        """Initialize SQLite persistence.

        Args:
            db_path: Path to SQLite database file
            table_name: Name of the memories table
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.table_name = table_name
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                content TEXT NOT NULL,
                importance REAL DEFAULT 0.5,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                UNIQUE(agent_id, content, created_at)
            )
        """)
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_agent_id
            ON {self.table_name}(agent_id)
        """)
        conn.commit()

    def save(self, agent_id: str, memories: List[Dict[str, Any]]) -> None:
        """Save memories (replaces existing)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Clear existing memories for this agent
        cursor.execute(
            f"DELETE FROM {self.table_name} WHERE agent_id = ?",
            (agent_id,)
        )

        # Insert new memories
        for memory in memories:
            cursor.execute(
                f"""
                INSERT INTO {self.table_name}
                (agent_id, content, importance, created_at, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    json.dumps(memory.get("content", memory)),
                    memory.get("importance", 0.5),
                    memory.get("created_at", datetime.now().isoformat()),
                    json.dumps({k: v for k, v in memory.items() if k not in ["content", "importance", "created_at"]}),
                ),
            )
        conn.commit()

    def load(self, agent_id: str) -> List[Dict[str, Any]]:
        """Load memories from database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"""
            SELECT content, importance, created_at, metadata
            FROM {self.table_name}
            WHERE agent_id = ?
            ORDER BY created_at ASC
            """,
            (agent_id,),
        )

        memories = []
        for row in cursor.fetchall():
            memory = {
                "content": json.loads(row["content"]) if row["content"].startswith(("{", "[", '"')) else row["content"],
                "importance": row["importance"],
                "created_at": row["created_at"],
            }
            if row["metadata"]:
                try:
                    metadata = json.loads(row["metadata"])
                    memory.update(metadata)
                except json.JSONDecodeError:
                    pass
            memories.append(memory)

        return memories

    def append(self, agent_id: str, memory: Dict[str, Any]) -> None:
        """Append a single memory."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"""
            INSERT OR IGNORE INTO {self.table_name}
            (agent_id, content, importance, created_at, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                json.dumps(memory.get("content", memory)),
                memory.get("importance", 0.5),
                memory.get("created_at", datetime.now().isoformat()),
                json.dumps({k: v for k, v in memory.items() if k not in ["content", "importance", "created_at"]}),
            ),
        )
        conn.commit()

    def list_agents(self) -> List[str]:
        """List all agents in the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT DISTINCT agent_id FROM {self.table_name}")
        return [row["agent_id"] for row in cursor.fetchall()]

    def get_count(self, agent_id: str) -> int:
        """Get memory count for an agent."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT COUNT(*) as count FROM {self.table_name} WHERE agent_id = ?",
            (agent_id,),
        )
        return cursor.fetchone()["count"]

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "connection"):
            self._local.connection.close()
            del self._local.connection


class InMemoryPersistence(MemoryPersistence):
    """In-memory persistence for testing.

    Stores memories in a dictionary. Not persistent across sessions.
    """

    def __init__(self):
        """Initialize in-memory storage."""
        self._store: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def save(self, agent_id: str, memories: List[Dict[str, Any]]) -> None:
        """Save memories in memory."""
        with self._lock:
            self._store[agent_id] = memories.copy()

    def load(self, agent_id: str) -> List[Dict[str, Any]]:
        """Load memories from memory."""
        with self._lock:
            return self._store.get(agent_id, []).copy()

    def append(self, agent_id: str, memory: Dict[str, Any]) -> None:
        """Append memory in memory."""
        with self._lock:
            if agent_id not in self._store:
                self._store[agent_id] = []
            self._store[agent_id].append(memory)

    def list_agents(self) -> List[str]:
        """List all agents."""
        return list(self._store.keys())


# =============================================================================
# Factory Function
# =============================================================================

def create_persistence(
    backend: str,
    path: Optional[str] = None,
    **kwargs
) -> MemoryPersistence:
    """Create a memory persistence backend.

    Args:
        backend: Backend type ("json", "sqlite", "memory")
        path: Storage path (required for json and sqlite)
        **kwargs: Additional backend-specific arguments

    Returns:
        MemoryPersistence instance

    Example:
        >>> persistence = create_persistence("json", "./memory_store")
        >>> persistence = create_persistence("sqlite", "./memories.db")
        >>> persistence = create_persistence("memory")  # For testing
    """
    backend = backend.lower()

    if backend == "json":
        if not path:
            raise ValueError("path required for JSON persistence")
        return JSONMemoryPersistence(path, **kwargs)

    elif backend == "sqlite":
        if not path:
            raise ValueError("path required for SQLite persistence")
        return SQLiteMemoryPersistence(path, **kwargs)

    elif backend in ("memory", "inmemory", "in_memory"):
        return InMemoryPersistence()

    else:
        raise ValueError(f"Unknown persistence backend: {backend}")
