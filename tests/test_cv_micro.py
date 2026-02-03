"""Tests for Level 1 MICRO validators: CACR and EGS.

Validates:
    - MicroValidator.compute_cacr() with PMT framework
    - MicroValidator.compute_egs() keyword grounding
    - MicroValidator.compute_full_report() integration
    - Edge cases: empty DataFrame, missing columns, all-coherent traces
"""

import pytest
import pandas as pd
import numpy as np

from broker.validators.calibration.micro_validator import (
    MicroValidator,
    CACRResult,
    EGSResult,
    MicroReport,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def flood_df():
    """Standard flood simulation DataFrame (10 agents, 3 years)."""
    rows = []
    for year in range(1, 4):
        for agent_id in range(1, 11):
            # Agents 1-5: High threat, high coping -> should act
            # Agents 6-10: Low threat -> should do_nothing or buy_insurance
            if agent_id <= 5:
                ta = "H"
                ca = "H"
                # Coherent: protective action
                decision = "elevate_house" if year <= 2 else "buy_insurance"
            else:
                ta = "L"
                ca = "M"
                decision = "do_nothing"

            rows.append({
                "agent_id": f"h_{agent_id:03d}",
                "year": year,
                "threat_appraisal": ta,
                "coping_appraisal": ca,
                "ta_level": ta,
                "ca_level": ca,
                "yearly_decision": decision,
                "elevated": year > 1 and agent_id <= 3,
                "relocated": False,
                "reasoning": f"Given flood depth of 3 feet and income of $50000, "
                             f"I assess threat as {ta}. Based on prior experience "
                             f"with flooding, I decide to {decision}.",
            })

    return pd.DataFrame(rows)


@pytest.fixture
def incoherent_df():
    """DataFrame with deliberate incoherent decisions."""
    rows = []
    for year in range(1, 4):
        for agent_id in range(1, 6):
            rows.append({
                "agent_id": f"h_{agent_id:03d}",
                "year": year,
                "ta_level": "VH",  # Very high threat
                "ca_level": "H",   # High coping
                "yearly_decision": "do_nothing",  # INCOHERENT: VH threat + do_nothing
                "elevated": False,
                "relocated": False,
                "reasoning": "I have no idea what to do.",
            })

    return pd.DataFrame(rows)


@pytest.fixture
def validator():
    """Default PMT micro validator with flood-domain keywords for EGS."""
    return MicroValidator(
        framework="pmt",
        ta_col="threat_appraisal",
        ca_col="coping_appraisal",
        context_keywords=[
            "flood depth", "flood level", "water level", "inundation",
            "income", "savings", "mortgage", "property value",
            "elevation cost", "insurance premium", "deductible",
            "neighbor", "community", "FEMA", "NFIP",
            "previous flood", "flood experience", "prior experience",
            "year", "annual", "decade",
            "damage", "loss", "recovery",
        ],
    )


# ---------------------------------------------------------------------------
# CACR tests
# ---------------------------------------------------------------------------

class TestCACR:
    """Tests for Construct-Action Coherence Rate."""

    def test_all_coherent(self, validator, flood_df):
        """All decisions should be coherent in well-formed data."""
        report = validator.compute_cacr(flood_df, start_year=1)
        assert report.cacr == 1.0
        assert report.n_observations == 30  # 10 agents x 3 years

    def test_incoherent_detection(self, validator, incoherent_df):
        """All VH-threat + do_nothing decisions are incoherent."""
        report = validator.compute_cacr(incoherent_df, start_year=1)
        assert report.cacr == 0.0
        assert report.n_observations == 15
        assert len(report.cacr_results) == 15
        # Every result should have rule violations
        for r in report.cacr_results:
            assert not r.coherent
            assert len(r.rule_violations) > 0

    def test_cacr_by_year(self, validator, flood_df):
        """Per-year CACR should be 1.0 for all years."""
        report = validator.compute_cacr(flood_df, start_year=1)
        assert len(report.cacr_by_year) == 3
        for yr, cacr in report.cacr_by_year.items():
            assert cacr == 1.0

    def test_cacr_start_year_filter(self, validator, flood_df):
        """Start year filter should exclude early data."""
        report = validator.compute_cacr(flood_df, start_year=2)
        assert report.n_observations == 20  # 10 agents x 2 years

    def test_cacr_empty_df(self, validator):
        """Empty DataFrame should return 0 CACR gracefully."""
        empty_df = pd.DataFrame(columns=[
            "agent_id", "year", "ta_level", "ca_level",
            "yearly_decision", "threat_appraisal", "coping_appraisal",
        ])
        report = validator.compute_cacr(empty_df, start_year=1)
        assert report.cacr == 0.0
        assert report.n_observations == 0

    def test_cacr_mixed_coherence(self, validator):
        """Mix of coherent and incoherent decisions."""
        rows = [
            # Coherent: High TP + High CP -> elevate
            {"agent_id": "a1", "year": 1, "ta_level": "H", "ca_level": "H",
             "yearly_decision": "elevate_house", "threat_appraisal": "H",
             "coping_appraisal": "H"},
            # Incoherent: VH TP -> do_nothing
            {"agent_id": "a2", "year": 1, "ta_level": "VH", "ca_level": "H",
             "yearly_decision": "do_nothing", "threat_appraisal": "VH",
             "coping_appraisal": "H"},
            # Coherent: Low TP -> do_nothing
            {"agent_id": "a3", "year": 1, "ta_level": "L", "ca_level": "M",
             "yearly_decision": "do_nothing", "threat_appraisal": "L",
             "coping_appraisal": "M"},
            # Incoherent: Low TP -> relocate (extreme action)
            {"agent_id": "a4", "year": 1, "ta_level": "L", "ca_level": "H",
             "yearly_decision": "relocate", "threat_appraisal": "L",
             "coping_appraisal": "H"},
        ]
        df = pd.DataFrame(rows)
        report = validator.compute_cacr(df, start_year=1)
        assert report.cacr == 0.5  # 2/4 coherent
        assert report.n_observations == 4

    def test_cacr_by_agent_type(self, validator):
        """CACR decomposed by agent type (MA scenario)."""
        rows = [
            {"agent_id": "h1", "year": 1, "ta_level": "H", "ca_level": "H",
             "yearly_decision": "elevate_house", "agent_type": "household",
             "threat_appraisal": "H", "coping_appraisal": "H"},
            {"agent_id": "h2", "year": 1, "ta_level": "VH", "ca_level": "H",
             "yearly_decision": "do_nothing", "agent_type": "household",
             "threat_appraisal": "VH", "coping_appraisal": "H"},
            {"agent_id": "g1", "year": 1, "ta_level": "H", "ca_level": "H",
             "yearly_decision": "buy_insurance", "agent_type": "government",
             "threat_appraisal": "H", "coping_appraisal": "H"},
        ]
        df = pd.DataFrame(rows)
        report = validator.compute_cacr(
            df, start_year=1, agent_type_col="agent_type"
        )
        assert "household" in report.cacr_by_agent_type
        assert report.cacr_by_agent_type["household"] == 0.5  # 1/2


# ---------------------------------------------------------------------------
# EGS tests
# ---------------------------------------------------------------------------

class TestEGS:
    """Tests for Evidence Grounding Score."""

    def test_grounded_reasoning(self, validator, flood_df):
        """Reasoning with flood/income keywords should be grounded."""
        results = validator.compute_egs(flood_df, reasoning_col="reasoning")
        # All rows have "flood depth" and "income" in reasoning
        assert len(results) == 30
        for r in results:
            assert r.grounded
            assert r.evidence_count >= 2  # "flood depth" + "income"

    def test_ungrounded_reasoning(self, validator):
        """Reasoning without context references scores 0."""
        rows = [
            {"agent_id": "a1", "year": 1,
             "reasoning": "I just feel like doing nothing today."},
        ]
        df = pd.DataFrame(rows)
        results = validator.compute_egs(df, reasoning_col="reasoning")
        assert len(results) == 1
        assert not results[0].grounded
        assert results[0].evidence_count == 0

    def test_egs_missing_column(self, validator):
        """Missing reasoning column: rows processed but ungrounded."""
        df = pd.DataFrame({"agent_id": ["a1"], "year": [1]})
        results = validator.compute_egs(df, reasoning_col="reasoning")
        # Row is processed but reasoning is empty -> not grounded
        assert len(results) == 1
        assert not results[0].grounded
        assert results[0].evidence_count == 0

    def test_egs_summary(self, validator, flood_df):
        """Summary statistics computation."""
        results = validator.compute_egs(flood_df, reasoning_col="reasoning")
        summary = validator.compute_egs_summary(results)
        assert summary["n"] == 30
        assert summary["egs_grounded_rate"] == 1.0
        assert summary["egs_mean"] > 0
        assert len(summary["egs_by_year"]) == 3

    def test_egs_context_cross_reference(self, validator):
        """Cross-referencing context column values in reasoning."""
        rows = [
            {"agent_id": "a1", "year": 1,
             "flood_depth": "3.5",
             "reasoning": "The flood depth of 3.5 feet was significant."},
            {"agent_id": "a2", "year": 1,
             "flood_depth": "2.1",
             "reasoning": "Nothing happened."},
        ]
        df = pd.DataFrame(rows)
        results = validator.compute_egs(
            df, reasoning_col="reasoning",
            context_cols=["flood_depth"],
        )
        assert results[0].grounded  # "flood depth" keyword + "3.5" cross-ref
        assert results[0].evidence_count >= 2


# ---------------------------------------------------------------------------
# Full report tests
# ---------------------------------------------------------------------------

class TestFullReport:
    """Tests for compute_full_report()."""

    def test_full_report_structure(self, validator, flood_df):
        """Full report includes CACR and EGS."""
        report = validator.compute_full_report(
            flood_df, reasoning_col="reasoning", start_year=1
        )
        assert isinstance(report, MicroReport)
        assert report.cacr == 1.0
        assert report.egs > 0
        assert report.n_observations == 30
        assert len(report.egs_results) == 30

    def test_full_report_to_dict(self, validator, flood_df):
        """Report serialization."""
        report = validator.compute_full_report(
            flood_df, reasoning_col="reasoning", start_year=1
        )
        d = report.to_dict()
        assert "cacr" in d
        assert "egs" in d
        assert "tcs" in d
        assert "n_observations" in d
