"""Tests for Temporal Consistency Score (TCS) validator.

Validates:
    - TemporalCoherenceValidator with PMT 5-level construct transitions
    - Impossible transition detection (jumps > max_jump)
    - Event-justified large transitions
    - Post-relocation frozen construct detection
    - Per-agent and per-construct TCS decomposition
"""

import pytest
import numpy as np
import pandas as pd

from broker.validators.calibration.temporal_coherence import (
    TemporalCoherenceValidator,
    TransitionMatrix,
    TemporalReport,
    AgentTCSResult,
    LABEL_ORDER,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def validator():
    """Default temporal coherence validator (max_jump=2)."""
    return TemporalCoherenceValidator(max_jump=2)


@pytest.fixture
def consistent_df():
    """DataFrame with only plausible transitions (step size <=2)."""
    rows = []
    # Agent 1: VL -> L -> M -> H -> VH (step=1 each)
    labels = ["VL", "L", "M", "H", "VH"]
    for i, yr in enumerate(range(1, 6)):
        rows.append({
            "agent_id": "a1",
            "year": yr,
            "ta_level": labels[i],
            "ca_level": "M",
            "relocated": False,
        })

    # Agent 2: stable at M
    for yr in range(1, 6):
        rows.append({
            "agent_id": "a2",
            "year": yr,
            "ta_level": "M",
            "ca_level": "M",
            "relocated": False,
        })

    return pd.DataFrame(rows)


@pytest.fixture
def impossible_df():
    """DataFrame with impossible transitions (jump > 2)."""
    rows = [
        # Agent 1: VL -> VH in one step (jump=4, impossible with max_jump=2)
        {"agent_id": "a1", "year": 1, "ta_level": "VL", "ca_level": "M",
         "relocated": False},
        {"agent_id": "a1", "year": 2, "ta_level": "VH", "ca_level": "M",
         "relocated": False},
        # Agent 2: VH -> VL in one step (also impossible)
        {"agent_id": "a2", "year": 1, "ta_level": "VH", "ca_level": "H",
         "relocated": False},
        {"agent_id": "a2", "year": 2, "ta_level": "VL", "ca_level": "H",
         "relocated": False},
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def relocated_df():
    """Agent that changes constructs after relocation (impossible)."""
    rows = [
        {"agent_id": "a1", "year": 1, "ta_level": "H", "ca_level": "H",
         "relocated": False},
        {"agent_id": "a1", "year": 2, "ta_level": "H", "ca_level": "H",
         "relocated": True},  # Relocated in year 2
        {"agent_id": "a1", "year": 3, "ta_level": "L", "ca_level": "L",
         "relocated": True},  # Changed constructs post-relocation!
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Core TCS tests
# ---------------------------------------------------------------------------

class TestTemporalCoherence:
    """Tests for TemporalCoherenceValidator."""

    def test_consistent_transitions(self, validator, consistent_df):
        """All step-1 transitions should be plausible."""
        report = validator.compute_tcs(consistent_df, start_year=1)
        assert report.overall_tcs == 1.0
        assert report.n_impossible == 0

    def test_impossible_transitions(self, validator, impossible_df):
        """VL->VH and VH->VL jumps should be flagged."""
        report = validator.compute_tcs(impossible_df, start_year=1)
        assert report.overall_tcs < 1.0
        assert report.n_impossible >= 2  # At least ta_level for both agents

    def test_tcs_by_construct(self, validator, impossible_df):
        """Per-construct TCS should be available."""
        report = validator.compute_tcs(impossible_df, start_year=1)
        assert "ta_level" in report.tcs_by_construct
        assert report.tcs_by_construct["ta_level"] < 1.0

    def test_per_agent_results(self, validator, impossible_df):
        """Per-agent TCS should identify problematic agents."""
        report = validator.compute_tcs(impossible_df, start_year=1)
        assert len(report.tcs_by_agent) == 2
        for agent_result in report.tcs_by_agent:
            assert agent_result.tcs < 1.0
            assert len(agent_result.impossible_transitions) > 0

    def test_post_relocation_change(self, validator, relocated_df):
        """Construct change after relocation should be flagged."""
        report = validator.compute_tcs(relocated_df, start_year=1)
        # Year 3: relocated=True in year 2, constructs changed in year 3
        assert report.n_impossible > 0

    def test_event_justifies_large_jump(self):
        """Event column should excuse large transitions."""
        validator = TemporalCoherenceValidator(
            max_jump=2, event_col="flood_occurred"
        )
        rows = [
            {"agent_id": "a1", "year": 1, "ta_level": "VL", "ca_level": "M",
             "relocated": False, "flood_occurred": False},
            {"agent_id": "a1", "year": 2, "ta_level": "VH", "ca_level": "M",
             "relocated": False, "flood_occurred": True},  # Flood justifies jump
        ]
        df = pd.DataFrame(rows)
        report = validator.compute_tcs(df, start_year=1)
        assert report.overall_tcs == 1.0  # Jump excused by flood event

    def test_empty_df(self, validator):
        """Empty DataFrame should return perfect TCS."""
        df = pd.DataFrame(columns=["agent_id", "year", "ta_level",
                                    "ca_level", "relocated"])
        report = validator.compute_tcs(df, start_year=1)
        assert report.overall_tcs == 1.0
        assert report.n_agents == 0

    def test_single_observation(self, validator):
        """Single observation = no transitions = perfect TCS."""
        df = pd.DataFrame([{
            "agent_id": "a1", "year": 1, "ta_level": "H",
            "ca_level": "M", "relocated": False,
        }])
        report = validator.compute_tcs(df, start_year=1)
        assert report.overall_tcs == 1.0


# ---------------------------------------------------------------------------
# Transition matrix tests
# ---------------------------------------------------------------------------

class TestTransitionMatrix:
    """Tests for transition matrix construction."""

    def test_matrix_shape(self, validator, consistent_df):
        """Matrix should be 5x5 for PMT 5-level scale."""
        report = validator.compute_tcs(consistent_df, start_year=1)
        for matrix in report.transition_matrices:
            assert matrix.counts.shape == (5, 5)
            assert matrix.impossible_mask.shape == (5, 5)

    def test_matrix_tcs_property(self, validator, consistent_df):
        """TransitionMatrix.tcs should match overall when all consistent."""
        report = validator.compute_tcs(consistent_df, start_year=1)
        for matrix in report.transition_matrices:
            assert matrix.tcs == 1.0

    def test_impossible_mask(self, validator):
        """Impossible mask should flag jumps > max_jump."""
        rows = [
            {"agent_id": "a1", "year": 1, "ta_level": "VL", "ca_level": "M",
             "relocated": False},
            {"agent_id": "a1", "year": 2, "ta_level": "VH", "ca_level": "M",
             "relocated": False},
        ]
        df = pd.DataFrame(rows)
        report = validator.compute_tcs(df, start_year=1)

        ta_matrix = next(
            m for m in report.transition_matrices if m.construct == "ta_level"
        )
        # VL=0, VH=4 -> jump=4 > max_jump=2 -> impossible
        assert ta_matrix.impossible_mask[0, 4]  # VL -> VH
        assert not ta_matrix.impossible_mask[0, 1]  # VL -> L (ok)
        assert not ta_matrix.impossible_mask[0, 2]  # VL -> M (ok, jump=2)

    def test_matrix_to_dict(self, validator, consistent_df):
        """TransitionMatrix serialization."""
        report = validator.compute_tcs(consistent_df, start_year=1)
        for matrix in report.transition_matrices:
            d = matrix.to_dict()
            assert "construct" in d
            assert "labels" in d
            assert "counts" in d
            assert "tcs" in d


# ---------------------------------------------------------------------------
# Report tests
# ---------------------------------------------------------------------------

class TestTemporalReport:
    """Tests for TemporalReport."""

    def test_report_to_dict(self, validator, consistent_df):
        """Report serialization."""
        report = validator.compute_tcs(consistent_df, start_year=1)
        d = report.to_dict()
        assert "overall_tcs" in d
        assert "tcs_by_construct" in d
        assert "n_agents" in d
        assert "transition_matrices" in d

    def test_report_agents_count(self, validator, consistent_df):
        """Report should count agents correctly."""
        report = validator.compute_tcs(consistent_df, start_year=1)
        assert report.n_agents == 2  # a1 and a2


# ---------------------------------------------------------------------------
# Custom configuration tests
# ---------------------------------------------------------------------------

class TestCustomConfig:
    """Tests for custom TCS configuration."""

    def test_strict_max_jump(self):
        """max_jump=1 should flag step-2 transitions."""
        validator = TemporalCoherenceValidator(max_jump=1)
        rows = [
            {"agent_id": "a1", "year": 1, "ta_level": "VL", "ca_level": "M",
             "relocated": False},
            {"agent_id": "a1", "year": 2, "ta_level": "M", "ca_level": "M",
             "relocated": False},  # Jump=2, impossible with max_jump=1
        ]
        df = pd.DataFrame(rows)
        report = validator.compute_tcs(df, start_year=1)
        assert report.n_impossible > 0

    def test_relaxed_max_jump(self):
        """max_jump=4 should allow VL->VH."""
        validator = TemporalCoherenceValidator(max_jump=4)
        rows = [
            {"agent_id": "a1", "year": 1, "ta_level": "VL", "ca_level": "M",
             "relocated": False},
            {"agent_id": "a1", "year": 2, "ta_level": "VH", "ca_level": "M",
             "relocated": False},
        ]
        df = pd.DataFrame(rows)
        report = validator.compute_tcs(df, start_year=1)
        assert report.overall_tcs == 1.0  # VL->VH is 4 steps, allowed

    def test_custom_construct_cols(self):
        """Validator with custom construct columns."""
        validator = TemporalCoherenceValidator(
            construct_cols=["wsa_level", "aca_level"]
        )
        rows = [
            {"agent_id": "a1", "year": 1, "wsa_level": "M",
             "aca_level": "H", "relocated": False},
            {"agent_id": "a1", "year": 2, "wsa_level": "H",
             "aca_level": "H", "relocated": False},
        ]
        df = pd.DataFrame(rows)
        report = validator.compute_tcs(df, start_year=1)
        assert "wsa_level" in report.tcs_by_construct
