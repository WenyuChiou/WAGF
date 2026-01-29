"""
Tests for broker/core/agent_initializer.py

Tests cover:
1. CSV mode loading
2. Survey mode loading (with mock data)
3. Synthetic generation
4. Enricher application
5. Memory generation
6. Statistics calculation
"""

import pytest
import pandas as pd
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List

from broker.core.agent_initializer import (
    initialize_agents,
    AgentProfile,
    CSVLoader,
    SyntheticLoader,
    generate_initial_memories,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_csv_path(tmp_path) -> Path:
    """Create a sample CSV file for testing."""
    csv_content = """agent_id,family_size,income,tenure,is_mg,tp_score,cp_score,flood_zone,has_insurance
Agent_001,3,55000,Owner,False,3.5,3.2,MEDIUM,True
Agent_002,4,42000,Renter,True,4.2,2.1,HIGH,False
Agent_003,2,85000,Owner,False,2.8,3.8,LOW,True
Agent_004,5,32000,Renter,True,4.5,1.8,HIGH,False
Agent_005,1,120000,Owner,False,2.2,4.1,LOW,True
"""
    csv_path = tmp_path / "test_agents.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    return csv_path


@pytest.fixture
def minimal_csv_path(tmp_path) -> Path:
    """Create a minimal CSV with only agent_id."""
    csv_content = """agent_id
A1
A2
A3
"""
    csv_path = tmp_path / "minimal_agents.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    return csv_path


@pytest.fixture
def sample_enricher():
    """Create a mock position enricher."""
    @dataclass
    class MockPositionData:
        zone_name: str
        base_depth_m: float
        flood_probability: float

    class MockPositionEnricher:
        def assign_position(self, profile: Any) -> MockPositionData:
            # Assign based on MG status
            if profile.is_mg:
                return MockPositionData(
                    zone_name="HIGH",
                    base_depth_m=1.5,
                    flood_probability=0.3,
                )
            return MockPositionData(
                zone_name="MEDIUM",
                base_depth_m=0.5,
                flood_probability=0.1,
            )

    return MockPositionEnricher()


@pytest.fixture
def value_enricher():
    """Create a mock value enricher."""
    @dataclass
    class MockValueData:
        building_rcv_usd: float
        contents_rcv_usd: float

    class MockValueEnricher:
        def generate(
            self,
            income_bracket: str,
            is_owner: bool,
            is_mg: bool,
            family_size: int,
        ) -> MockValueData:
            base = 50000 * family_size
            if is_owner:
                building = base * 3
            else:
                building = 0
            contents = base * 0.5
            return MockValueData(
                building_rcv_usd=building,
                contents_rcv_usd=contents,
            )

    return MockValueEnricher()


# =============================================================================
# CSV MODE TESTS
# =============================================================================


class TestCSVMode:
    """Tests for CSV mode loading."""

    def test_csv_mode_loads_all_agents(self, sample_csv_path):
        """CSV mode should load all agents from file."""
        profiles, memories, stats = initialize_agents(
            mode="csv",
            path=sample_csv_path,
            config={},
        )

        assert len(profiles) == 5
        assert stats["total_agents"] == 5

    def test_csv_mode_parses_basic_fields(self, sample_csv_path):
        """CSV mode should correctly parse basic fields."""
        profiles, _, _ = initialize_agents(
            mode="csv",
            path=sample_csv_path,
            config={},
        )

        # Check first agent
        p1 = profiles[0]
        assert p1.agent_id == "Agent_001"
        assert p1.family_size == 3
        assert p1.income == 55000
        assert p1.tenure == "Owner"
        assert p1.is_mg is False
        assert p1.tp_score == 3.5
        assert p1.cp_score == 3.2
        assert p1.flood_zone == "MEDIUM"
        assert p1.has_insurance is True

        # Check MG agent
        p2 = profiles[1]
        assert p2.is_mg is True
        assert p2.tenure == "Renter"
        assert p2.flood_zone == "HIGH"

    def test_csv_mode_handles_minimal_csv(self, minimal_csv_path):
        """CSV mode should use defaults for missing columns."""
        profiles, _, _ = initialize_agents(
            mode="csv",
            path=minimal_csv_path,
            config={},
        )

        assert len(profiles) == 3
        # Should have defaults
        p = profiles[0]
        assert p.agent_id == "A1"
        assert p.family_size == 3  # default
        assert p.income == 55000  # default
        assert p.tp_score == 3.0  # default

    def test_csv_mode_calculates_stats(self, sample_csv_path):
        """CSV mode should calculate correct statistics."""
        _, _, stats = initialize_agents(
            mode="csv",
            path=sample_csv_path,
            config={},
        )

        assert stats["total_agents"] == 5
        assert stats["owner_count"] == 3
        assert stats["renter_count"] == 2
        assert stats["mg_count"] == 2
        assert stats["mg_ratio"] == pytest.approx(0.4)
        assert stats["owner_ratio"] == pytest.approx(0.6)

    def test_csv_mode_file_not_found(self, tmp_path):
        """CSV mode should raise error for missing file."""
        with pytest.raises(FileNotFoundError):
            initialize_agents(
                mode="csv",
                path=tmp_path / "nonexistent.csv",
                config={},
            )

    def test_csv_mode_requires_path(self):
        """CSV mode should raise error when path is None."""
        with pytest.raises(ValueError, match="CSV mode requires a path"):
            initialize_agents(
                mode="csv",
                path=None,
                config={},
            )


# =============================================================================
# SYNTHETIC MODE TESTS
# =============================================================================


class TestSyntheticMode:
    """Tests for synthetic agent generation."""

    def test_synthetic_mode_generates_correct_count(self):
        """Synthetic mode should generate the requested number of agents."""
        profiles, _, stats = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 50},
        )

        assert len(profiles) == 50
        assert stats["total_agents"] == 50

    def test_synthetic_mode_respects_mg_ratio(self):
        """Synthetic mode should approximately follow MG ratio."""
        profiles, _, stats = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 1000, "mg_ratio": 0.20},
            seed=42,
        )

        # Allow some variance due to randomness
        assert 0.15 < stats["mg_ratio"] < 0.25

    def test_synthetic_mode_respects_owner_ratio(self):
        """Synthetic mode should approximately follow owner ratio."""
        profiles, _, stats = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 1000, "owner_ratio": 0.70},
            seed=42,
        )

        # Allow some variance due to randomness
        assert 0.65 < stats["owner_ratio"] < 0.75

    def test_synthetic_mode_reproducible_with_seed(self):
        """Synthetic mode should be reproducible with same seed."""
        p1, _, _ = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 10},
            seed=123,
        )
        p2, _, _ = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 10},
            seed=123,
        )

        for a, b in zip(p1, p2):
            assert a.agent_id == b.agent_id
            assert a.is_mg == b.is_mg
            assert a.tp_score == b.tp_score
            assert a.income == b.income

    def test_synthetic_mode_different_seeds_different_results(self):
        """Different seeds should produce different results."""
        p1, _, _ = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 10},
            seed=111,
        )
        p2, _, _ = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 10},
            seed=222,
        )

        # At least some should be different
        differences = sum(
            1 for a, b in zip(p1, p2)
            if a.is_mg != b.is_mg or a.tp_score != b.tp_score
        )
        assert differences > 0

    def test_synthetic_mode_generates_valid_pmt_scores(self):
        """PMT scores should be in valid range [1.0, 5.0]."""
        profiles, _, _ = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 100},
            seed=42,
        )

        for p in profiles:
            assert 1.0 <= p.tp_score <= 5.0
            assert 1.0 <= p.cp_score <= 5.0
            assert 1.0 <= p.sp_score <= 5.0
            assert 1.0 <= p.sc_score <= 5.0
            assert 1.0 <= p.pa_score <= 5.0

    def test_synthetic_mode_mg_has_different_distribution(self):
        """MG and non-MG should have different PMT score distributions."""
        profiles, _, _ = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 500, "mg_ratio": 0.50},
            seed=42,
        )

        mg_profiles = [p for p in profiles if p.is_mg]
        nmg_profiles = [p for p in profiles if not p.is_mg]

        # MG should have higher TP (threat perception)
        mg_tp_mean = sum(p.tp_score for p in mg_profiles) / len(mg_profiles)
        nmg_tp_mean = sum(p.tp_score for p in nmg_profiles) / len(nmg_profiles)
        assert mg_tp_mean > nmg_tp_mean

        # MG should have lower CP (coping perception)
        mg_cp_mean = sum(p.cp_score for p in mg_profiles) / len(mg_profiles)
        nmg_cp_mean = sum(p.cp_score for p in nmg_profiles) / len(nmg_profiles)
        assert mg_cp_mean < nmg_cp_mean


# =============================================================================
# ENRICHER TESTS
# =============================================================================


class TestEnricherApplication:
    """Tests for enricher application."""

    def test_position_enricher_updates_profile(self, sample_enricher):
        """Position enricher should update flood zone and depth."""
        profiles, _, _ = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 10, "mg_ratio": 0.50},
            enrichers={"position": sample_enricher},
            seed=42,
        )

        mg_profiles = [p for p in profiles if p.is_mg]
        nmg_profiles = [p for p in profiles if not p.is_mg]

        # MG should be in HIGH zone
        for p in mg_profiles:
            assert p.flood_zone == "HIGH"
            assert p.flood_depth == 1.5

        # Non-MG should be in MEDIUM zone
        for p in nmg_profiles:
            assert p.flood_zone == "MEDIUM"
            assert p.flood_depth == 0.5

    def test_value_enricher_updates_rcv(self, value_enricher):
        """Value enricher should update RCV fields."""
        profiles, _, _ = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 10},
            enrichers={"value": value_enricher},
            seed=42,
        )

        for p in profiles:
            expected_base = 50000 * p.family_size
            if p.is_owner:
                assert p.rcv_building == expected_base * 3
            else:
                assert p.rcv_building == 0
            assert p.rcv_contents == expected_base * 0.5

    def test_multiple_enrichers(self, sample_enricher, value_enricher):
        """Multiple enrichers should all be applied."""
        profiles, _, _ = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 10},
            enrichers={
                "position": sample_enricher,
                "value": value_enricher,
            },
            seed=42,
        )

        for p in profiles:
            # Position enricher applied
            assert p.flood_zone in ["HIGH", "MEDIUM"]
            # Value enricher applied
            assert p.rcv_contents > 0

    def test_custom_enricher_with_enrich_method(self):
        """Custom enricher with enrich() method should work."""

        class CustomEnricher:
            def enrich(self, profile: AgentProfile) -> None:
                profile.extensions["custom"] = "enriched"

        profiles, _, _ = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 5},
            enrichers={"custom": CustomEnricher()},
            seed=42,
        )

        for p in profiles:
            assert p.extensions.get("custom") == "enriched"


# =============================================================================
# MEMORY GENERATION TESTS
# =============================================================================


class TestMemoryGeneration:
    """Tests for initial memory generation."""

    def test_memories_generated_for_all_agents(self):
        """Each agent should have initial memories."""
        profiles, memories, _ = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 10},
            seed=42,
        )

        assert len(memories) == len(profiles)
        for p in profiles:
            assert p.agent_id in memories
            assert len(memories[p.agent_id]) > 0

    def test_memory_content_reflects_flood_experience(self):
        """Memory content should reflect flood experience."""
        # Generate profiles with controlled attributes
        profiles, memories, _ = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 100},
            seed=42,
        )

        # Check agents with flood experience
        flood_exp_agents = [p for p in profiles if p.flood_experience]
        if flood_exp_agents:
            p = flood_exp_agents[0]
            agent_memories = memories[p.agent_id]
            # Should have flood-related memory
            has_flood_memory = any(
                "flood" in str(m).lower() for m in agent_memories
            )
            assert has_flood_memory

    def test_custom_memory_enricher(self):
        """Custom memory enricher should override default generation."""

        class CustomMemoryEnricher:
            def generate_all(self, profile_dict: Dict[str, Any]) -> List[Dict]:
                return [{"content": "Custom memory", "category": "test"}]

        profiles, memories, _ = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 5},
            enrichers={"memory": CustomMemoryEnricher()},
            seed=42,
        )

        for p in profiles:
            agent_memories = memories[p.agent_id]
            assert len(agent_memories) == 1
            assert agent_memories[0]["content"] == "Custom memory"


# =============================================================================
# AGENT PROFILE TESTS
# =============================================================================


class TestAgentProfile:
    """Tests for AgentProfile dataclass."""

    def test_profile_to_dict(self):
        """to_dict() should include all fields."""
        profile = AgentProfile(
            agent_id="Test_001",
            family_size=4,
            income=75000,
            is_mg=True,
            tp_score=4.2,
        )

        d = profile.to_dict()
        assert d["agent_id"] == "Test_001"
        assert d["family_size"] == 4
        assert d["income"] == 75000
        assert d["is_mg"] is True
        assert d["tp_score"] == 4.2

    def test_profile_identity_property(self):
        """identity property should reflect housing_status."""
        owner = AgentProfile(agent_id="O1", housing_status="mortgage")
        renter = AgentProfile(agent_id="R1", housing_status="rent")

        assert owner.identity == "owner"
        assert owner.is_owner is True
        assert renter.identity == "renter"
        assert renter.is_owner is False

    def test_profile_group_label(self):
        """group_label should reflect MG status."""
        mg = AgentProfile(agent_id="M1", is_mg=True)
        nmg = AgentProfile(agent_id="N1", is_mg=False)

        assert mg.group_label == "MG"
        assert nmg.group_label == "NMG"


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_mode_raises_error(self):
        """Invalid mode should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown mode"):
            initialize_agents(
                mode="invalid_mode",
                path=None,
                config={},
            )

    def test_survey_mode_requires_path(self):
        """Survey mode should raise error when path is None."""
        with pytest.raises(ValueError, match="Survey mode requires a path"):
            initialize_agents(
                mode="survey",
                path=None,
                config={},
            )


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_full_workflow_csv(self, sample_csv_path, sample_enricher, value_enricher):
        """Full workflow with CSV loading and enrichers."""
        profiles, memories, stats = initialize_agents(
            mode="csv",
            path=sample_csv_path,
            config={},
            enrichers={
                "position": sample_enricher,
                "value": value_enricher,
            },
            seed=42,
        )

        # Verify profiles
        assert len(profiles) == 5

        # Verify enrichment
        for p in profiles:
            assert p.rcv_contents > 0

        # Verify memories
        assert len(memories) == 5

        # Verify stats
        assert stats["mode"] == "csv"
        assert stats["seed"] == 42

    def test_full_workflow_synthetic(self, sample_enricher, value_enricher):
        """Full workflow with synthetic generation and enrichers."""
        profiles, memories, stats = initialize_agents(
            mode="synthetic",
            path=None,
            config={"n_agents": 100, "mg_ratio": 0.25, "owner_ratio": 0.60},
            enrichers={
                "position": sample_enricher,
                "value": value_enricher,
            },
            seed=42,
        )

        # Verify profiles
        assert len(profiles) == 100

        # Verify stats are reasonable (wider tolerance for 100 samples)
        assert stats["mode"] == "synthetic"
        assert 0.15 <= stats["mg_ratio"] <= 0.35
        assert 0.45 <= stats["owner_ratio"] <= 0.80

        # Verify all agents have memories
        assert len(memories) == 100
        for p in profiles:
            assert p.agent_id in memories


# =============================================================================
# STANDALONE LOADER TESTS
# =============================================================================


class TestCSVLoader:
    """Tests for CSVLoader class directly."""

    def test_loader_finds_columns_by_alias(self, tmp_path):
        """Loader should find columns by alternative names."""
        csv_content = """id,FamilySize,Income
A1,3,50000
"""
        csv_path = tmp_path / "alias_test.csv"
        csv_path.write_text(csv_content, encoding="utf-8")

        loader = CSVLoader()
        profiles = loader.load(csv_path, {})

        assert len(profiles) == 1
        # Should find 'id' for agent_id, 'FamilySize' for family_size
        p = profiles[0]
        assert p.agent_id == "A1"


class TestSyntheticLoader:
    """Tests for SyntheticLoader class directly."""

    def test_loader_defaults(self):
        """Loader should use default values."""
        loader = SyntheticLoader(seed=42)
        profiles = loader.load(None, {"n_agents": 5})

        assert len(profiles) == 5
        for p in profiles:
            # Should have valid agent ID format
            assert p.agent_id.startswith("H")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
