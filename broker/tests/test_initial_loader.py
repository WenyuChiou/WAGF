"""Unit tests for broker initial memory loader."""

import json
import shutil
import uuid
from pathlib import Path

import pytest

from broker.components.memory.content_types import MemoryContentType
from broker.components.memory.initial_loader import InitialLoadReport, load_initial_memories_from_json
from broker.components.memory.policy_filter import PolicyFilteredMemoryEngine
from broker.config.memory_policy import CLEAN_POLICY, LEGACY_POLICY


class MockEngine:
    def __init__(self):
        self.add_calls = []

    def add_memory(self, agent_id, content, metadata=None):
        self.add_calls.append({"agent_id": agent_id, "content": content, "metadata": metadata})


@pytest.fixture
def local_tmp_dir():
    path = Path("broker/tests/.tmp") / str(uuid.uuid4())
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def sample_memories_file(local_tmp_dir):
    data = {
        "H0001": [
            {"content": "I experienced flooding", "category": "flood_experience", "importance": 0.8},
            {"content": "I have NFIP insurance", "category": "insurance_history", "importance": 0.6},
            {"content": "I have deep emotional ties", "category": "place_attachment", "importance": 0.8},
            {"content": "I trust government programs", "category": "government_trust", "importance": 0.6},
        ],
        "H0002": [
            {"content": "I have not experienced flooding", "category": "flood_experience", "importance": 0.5},
            {"content": "This community is my home", "category": "place_attachment", "importance": 0.8},
        ],
        "H_NOT_IN_SIM": [
            {"content": "orphan", "category": "flood_experience", "importance": 0.5},
        ],
    }
    path = local_tmp_dir / "initial_memories.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


FLOOD_MAPPING = {
    "flood_experience": MemoryContentType.EXTERNAL_EVENT,
    "insurance_history": MemoryContentType.INITIAL_FACTUAL,
    "place_attachment": MemoryContentType.INITIAL_NARRATIVE,
    "government_trust": MemoryContentType.INITIAL_NARRATIVE,
}


class TestLoadAgainstRawEngine:
    def test_loads_all_memories_without_policy(self, sample_memories_file):
        inner = MockEngine()
        report = load_initial_memories_from_json(
            inner,
            sample_memories_file,
            agent_id_filter={"H0001", "H0002"},
            domain_mapping=FLOOD_MAPPING,
        )
        assert report.loaded_count == 6
        assert report.skipped_missing_agent == 1
        assert report.total_agents_loaded == 2
        assert len(inner.add_calls) == 6

    def test_all_writes_have_content_type_in_metadata(self, sample_memories_file):
        inner = MockEngine()
        load_initial_memories_from_json(
            inner,
            sample_memories_file,
            agent_id_filter={"H0001", "H0002"},
            domain_mapping=FLOOD_MAPPING,
        )
        for call in inner.add_calls:
            assert "content_type" in call["metadata"]

    def test_unknown_non_event_category_uses_default_content_type(self, local_tmp_dir):
        path = local_tmp_dir / "unknown.json"
        path.write_text(json.dumps({"H0001": [{"content": "x", "category": "unmapped"}]}), encoding="utf-8")
        inner = MockEngine()
        load_initial_memories_from_json(inner, path, default_content_type=MemoryContentType.INITIAL_FACTUAL)
        assert inner.add_calls[0]["metadata"]["content_type"] == MemoryContentType.INITIAL_FACTUAL.value

    def test_default_source_and_year_are_included(self, local_tmp_dir):
        path = local_tmp_dir / "default_fields.json"
        path.write_text(json.dumps({"H0001": [{"content": "x", "category": "flood_experience"}]}), encoding="utf-8")
        inner = MockEngine()
        load_initial_memories_from_json(inner, path)
        metadata = inner.add_calls[0]["metadata"]
        assert metadata["source"] == "survey"
        assert metadata["year"] == 0

    def test_classified_by_type_counts_every_submitted_memory(self, sample_memories_file):
        inner = MockEngine()
        report = load_initial_memories_from_json(
            inner,
            sample_memories_file,
            agent_id_filter={"H0001", "H0002"},
            domain_mapping=FLOOD_MAPPING,
        )
        assert report.classified_by_type["external_event"] == 2
        assert report.classified_by_type["initial_factual"] == 1
        assert report.classified_by_type["initial_narrative"] == 3


class TestLoadAgainstPolicyProxy:
    def test_clean_policy_drops_initial_narrative(self, sample_memories_file):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY, domain_mapping=FLOOD_MAPPING)
        report = load_initial_memories_from_json(
            proxy,
            sample_memories_file,
            agent_id_filter={"H0001", "H0002"},
            domain_mapping=FLOOD_MAPPING,
        )
        assert report.loaded_count == 3
        assert report.dropped_counts.get("initial_narrative") == 3
        assert len(inner.add_calls) == 3

    def test_legacy_policy_loads_everything(self, sample_memories_file):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, LEGACY_POLICY, domain_mapping=FLOOD_MAPPING)
        report = load_initial_memories_from_json(
            proxy,
            sample_memories_file,
            agent_id_filter={"H0001", "H0002"},
            domain_mapping=FLOOD_MAPPING,
        )
        assert report.loaded_count == 6
        assert report.dropped_counts == {}
        assert len(inner.add_calls) == 6

    def test_preexisting_drop_counts_are_delta_adjusted(self, sample_memories_file):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY, domain_mapping=FLOOD_MAPPING)
        proxy.add_memory("seed", "blocked", {"content_type": "initial_narrative"})
        report = load_initial_memories_from_json(
            proxy,
            sample_memories_file,
            agent_id_filter={"H0001", "H0002"},
            domain_mapping=FLOOD_MAPPING,
        )
        assert report.dropped_counts == {"initial_narrative": 3}

    def test_total_agents_loaded_counts_agents_even_with_drops(self, sample_memories_file):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY, domain_mapping=FLOOD_MAPPING)
        report = load_initial_memories_from_json(
            proxy,
            sample_memories_file,
            agent_id_filter={"H0001", "H0002"},
            domain_mapping=FLOOD_MAPPING,
        )
        assert report.total_agents_loaded == 2


class TestReport:
    def test_summary_human_readable(self, sample_memories_file):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY, domain_mapping=FLOOD_MAPPING)
        report = load_initial_memories_from_json(
            proxy,
            sample_memories_file,
            agent_id_filter={"H0001", "H0002"},
            domain_mapping=FLOOD_MAPPING,
        )
        summary = report.summary()
        assert "Loaded 3" in summary
        assert "dropped 3" in summary
        assert "initial_narrative" in summary

    def test_summary_mentions_skipped_agents(self):
        report = InitialLoadReport(loaded_count=1, skipped_missing_agent=2, total_agents_loaded=1)
        assert "[2 memories for agents not in filter]" in report.summary()

    def test_summary_without_drops_is_concise(self):
        report = InitialLoadReport(loaded_count=2, total_agents_loaded=1)
        summary = report.summary()
        assert "dropped" not in summary
        assert "Loaded 2 initial memories across 1 agents" in summary
