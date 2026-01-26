"""
Tests for Task-034 Phase 9: Memory Persistence System.

Tests JSON, SQLite, and InMemory persistence backends.
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from governed_ai_sdk.v1_prototype.memory.persistence import (
    MemoryPersistence,
    JSONMemoryPersistence,
    SQLiteMemoryPersistence,
    InMemoryPersistence,
    create_persistence,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path, ignore_errors=True)


class TestInMemoryPersistence:
    """Tests for InMemoryPersistence (test/mock backend)."""

    def test_save_and_load(self):
        """InMemoryPersistence can save and load memories."""
        persistence = InMemoryPersistence()
        memories = [
            {"content": "Memory 1", "importance": 0.8},
            {"content": "Memory 2", "importance": 0.5},
        ]

        persistence.save("agent_001", memories)
        loaded = persistence.load("agent_001")

        assert len(loaded) == 2
        assert loaded[0]["content"] == "Memory 1"
        assert loaded[1]["content"] == "Memory 2"

    def test_load_nonexistent_agent(self):
        """InMemoryPersistence returns empty list for nonexistent agent."""
        persistence = InMemoryPersistence()
        loaded = persistence.load("nonexistent")
        assert loaded == []

    def test_append(self):
        """InMemoryPersistence can append individual memories."""
        persistence = InMemoryPersistence()

        persistence.append("agent_001", {"content": "Memory 1"})
        persistence.append("agent_001", {"content": "Memory 2"})

        loaded = persistence.load("agent_001")
        assert len(loaded) == 2

    def test_clear(self):
        """InMemoryPersistence can clear agent memories."""
        persistence = InMemoryPersistence()
        persistence.save("agent_001", [{"content": "Memory 1"}])

        persistence.clear("agent_001")
        loaded = persistence.load("agent_001")

        assert loaded == []

    def test_exists(self):
        """InMemoryPersistence can check if agent has memories."""
        persistence = InMemoryPersistence()

        assert not persistence.exists("agent_001")

        persistence.save("agent_001", [{"content": "Memory 1"}])
        assert persistence.exists("agent_001")

    def test_list_agents(self):
        """InMemoryPersistence can list all agents."""
        persistence = InMemoryPersistence()

        persistence.save("agent_001", [{"content": "M1"}])
        persistence.save("agent_002", [{"content": "M2"}])

        agents = persistence.list_agents()
        assert "agent_001" in agents
        assert "agent_002" in agents

    def test_isolation(self):
        """InMemoryPersistence isolates memories by agent."""
        persistence = InMemoryPersistence()

        persistence.save("agent_001", [{"content": "Agent 1 memory"}])
        persistence.save("agent_002", [{"content": "Agent 2 memory"}])

        loaded_1 = persistence.load("agent_001")
        loaded_2 = persistence.load("agent_002")

        assert loaded_1[0]["content"] == "Agent 1 memory"
        assert loaded_2[0]["content"] == "Agent 2 memory"


class TestJSONMemoryPersistence:
    """Tests for JSONMemoryPersistence."""

    def test_creates_directory(self, temp_dir):
        """JSONMemoryPersistence creates storage directory."""
        path = Path(temp_dir) / "memory_store"
        persistence = JSONMemoryPersistence(str(path))
        assert path.exists()

    def test_save_and_load(self, temp_dir):
        """JSONMemoryPersistence can save and load memories."""
        persistence = JSONMemoryPersistence(temp_dir)
        memories = [
            {"content": "Memory 1", "importance": 0.8},
            {"content": "Memory 2", "importance": 0.5},
        ]

        persistence.save("agent_001", memories)
        loaded = persistence.load("agent_001")

        assert len(loaded) == 2
        assert loaded[0]["content"] == "Memory 1"

    def test_file_created(self, temp_dir):
        """JSONMemoryPersistence creates JSON file for agent."""
        persistence = JSONMemoryPersistence(temp_dir)
        persistence.save("agent_001", [{"content": "Test"}])

        expected_file = Path(temp_dir) / "agent_001_memory.json"
        assert expected_file.exists()

    def test_load_nonexistent_agent(self, temp_dir):
        """JSONMemoryPersistence returns empty list for nonexistent agent."""
        persistence = JSONMemoryPersistence(temp_dir)
        loaded = persistence.load("nonexistent")
        assert loaded == []

    def test_append(self, temp_dir):
        """JSONMemoryPersistence can append individual memories."""
        persistence = JSONMemoryPersistence(temp_dir)

        persistence.append("agent_001", {"content": "Memory 1"})
        persistence.append("agent_001", {"content": "Memory 2"})

        loaded = persistence.load("agent_001")
        assert len(loaded) == 2

    def test_list_agents(self, temp_dir):
        """JSONMemoryPersistence can list all agents."""
        persistence = JSONMemoryPersistence(temp_dir)

        persistence.save("agent_001", [{"content": "M1"}])
        persistence.save("agent_002", [{"content": "M2"}])

        agents = persistence.list_agents()
        assert "agent_001" in agents
        assert "agent_002" in agents

    def test_get_metadata(self, temp_dir):
        """JSONMemoryPersistence can retrieve metadata."""
        persistence = JSONMemoryPersistence(temp_dir)
        persistence.save("agent_001", [{"content": "M1"}, {"content": "M2"}])

        metadata = persistence.get_metadata("agent_001")

        assert metadata is not None
        assert metadata["agent_id"] == "agent_001"
        assert metadata["count"] == 2
        assert "saved_at" in metadata

    def test_sanitizes_agent_id(self, temp_dir):
        """JSONMemoryPersistence sanitizes agent IDs for filesystem."""
        persistence = JSONMemoryPersistence(temp_dir)
        # Agent ID with special characters
        persistence.save("agent/001\\test", [{"content": "Test"}])

        # Should create a safe filename
        loaded = persistence.load("agent/001\\test")
        assert len(loaded) == 1


class TestSQLiteMemoryPersistence:
    """Tests for SQLiteMemoryPersistence."""

    def test_creates_database(self, temp_dir):
        """SQLiteMemoryPersistence creates database file."""
        db_path = Path(temp_dir) / "memories.db"
        persistence = SQLiteMemoryPersistence(str(db_path))
        assert db_path.exists()
        persistence.close()

    def test_save_and_load(self, temp_dir):
        """SQLiteMemoryPersistence can save and load memories."""
        db_path = Path(temp_dir) / "memories.db"
        persistence = SQLiteMemoryPersistence(str(db_path))

        memories = [
            {"content": "Memory 1", "importance": 0.8},
            {"content": "Memory 2", "importance": 0.5},
        ]

        persistence.save("agent_001", memories)
        loaded = persistence.load("agent_001")

        assert len(loaded) == 2
        assert loaded[0]["content"] == "Memory 1"
        persistence.close()

    def test_load_nonexistent_agent(self, temp_dir):
        """SQLiteMemoryPersistence returns empty list for nonexistent agent."""
        db_path = Path(temp_dir) / "memories.db"
        persistence = SQLiteMemoryPersistence(str(db_path))

        loaded = persistence.load("nonexistent")
        assert loaded == []
        persistence.close()

    def test_append(self, temp_dir):
        """SQLiteMemoryPersistence can append individual memories."""
        db_path = Path(temp_dir) / "memories.db"
        persistence = SQLiteMemoryPersistence(str(db_path))

        persistence.append("agent_001", {"content": "Memory 1"})
        persistence.append("agent_001", {"content": "Memory 2"})

        loaded = persistence.load("agent_001")
        assert len(loaded) == 2
        persistence.close()

    def test_list_agents(self, temp_dir):
        """SQLiteMemoryPersistence can list all agents."""
        db_path = Path(temp_dir) / "memories.db"
        persistence = SQLiteMemoryPersistence(str(db_path))

        persistence.save("agent_001", [{"content": "M1"}])
        persistence.save("agent_002", [{"content": "M2"}])

        agents = persistence.list_agents()
        assert "agent_001" in agents
        assert "agent_002" in agents
        persistence.close()

    def test_get_count(self, temp_dir):
        """SQLiteMemoryPersistence can count memories."""
        db_path = Path(temp_dir) / "memories.db"
        persistence = SQLiteMemoryPersistence(str(db_path))

        persistence.save("agent_001", [
            {"content": "M1"},
            {"content": "M2"},
            {"content": "M3"},
        ])

        count = persistence.get_count("agent_001")
        assert count == 3
        persistence.close()

    def test_save_replaces_existing(self, temp_dir):
        """SQLiteMemoryPersistence save replaces existing memories."""
        db_path = Path(temp_dir) / "memories.db"
        persistence = SQLiteMemoryPersistence(str(db_path))

        persistence.save("agent_001", [{"content": "Old memory"}])
        persistence.save("agent_001", [{"content": "New memory"}])

        loaded = persistence.load("agent_001")
        assert len(loaded) == 1
        assert loaded[0]["content"] == "New memory"
        persistence.close()

    def test_preserves_importance(self, temp_dir):
        """SQLiteMemoryPersistence preserves importance scores."""
        db_path = Path(temp_dir) / "memories.db"
        persistence = SQLiteMemoryPersistence(str(db_path))

        persistence.save("agent_001", [
            {"content": "Important memory", "importance": 0.95}
        ])

        loaded = persistence.load("agent_001")
        assert loaded[0]["importance"] == 0.95
        persistence.close()


class TestCreatePersistence:
    """Tests for create_persistence factory function."""

    def test_create_json_persistence(self, temp_dir):
        """create_persistence creates JSONMemoryPersistence."""
        persistence = create_persistence("json", temp_dir)
        assert isinstance(persistence, JSONMemoryPersistence)

    def test_create_sqlite_persistence(self, temp_dir):
        """create_persistence creates SQLiteMemoryPersistence."""
        db_path = str(Path(temp_dir) / "test.db")
        persistence = create_persistence("sqlite", db_path)
        assert isinstance(persistence, SQLiteMemoryPersistence)
        persistence.close()

    def test_create_memory_persistence(self):
        """create_persistence creates InMemoryPersistence."""
        persistence = create_persistence("memory")
        assert isinstance(persistence, InMemoryPersistence)

    def test_create_inmemory_alias(self):
        """create_persistence accepts 'inmemory' alias."""
        persistence = create_persistence("inmemory")
        assert isinstance(persistence, InMemoryPersistence)

    def test_create_in_memory_alias(self):
        """create_persistence accepts 'in_memory' alias."""
        persistence = create_persistence("in_memory")
        assert isinstance(persistence, InMemoryPersistence)

    def test_json_requires_path(self):
        """create_persistence raises if JSON backend missing path."""
        with pytest.raises(ValueError, match="path required"):
            create_persistence("json")

    def test_sqlite_requires_path(self):
        """create_persistence raises if SQLite backend missing path."""
        with pytest.raises(ValueError, match="path required"):
            create_persistence("sqlite")

    def test_unknown_backend_raises(self):
        """create_persistence raises for unknown backend."""
        with pytest.raises(ValueError, match="Unknown persistence backend"):
            create_persistence("unknown_backend")

    def test_case_insensitive(self, temp_dir):
        """create_persistence is case insensitive."""
        persistence = create_persistence("JSON", temp_dir)
        assert isinstance(persistence, JSONMemoryPersistence)


class TestPersistenceInterface:
    """Tests for MemoryPersistence abstract interface."""

    def test_inmemory_implements_interface(self):
        """InMemoryPersistence implements MemoryPersistence interface."""
        persistence = InMemoryPersistence()
        assert isinstance(persistence, MemoryPersistence)
        assert hasattr(persistence, "save")
        assert hasattr(persistence, "load")
        assert hasattr(persistence, "append")
        assert hasattr(persistence, "clear")
        assert hasattr(persistence, "exists")

    def test_json_implements_interface(self, temp_dir):
        """JSONMemoryPersistence implements MemoryPersistence interface."""
        persistence = JSONMemoryPersistence(temp_dir)
        assert isinstance(persistence, MemoryPersistence)

    def test_sqlite_implements_interface(self, temp_dir):
        """SQLiteMemoryPersistence implements MemoryPersistence interface."""
        db_path = str(Path(temp_dir) / "test.db")
        persistence = SQLiteMemoryPersistence(db_path)
        assert isinstance(persistence, MemoryPersistence)
        persistence.close()
