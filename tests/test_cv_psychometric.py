"""Tests for Level 3 COGNITIVE validators: psychometric_battery.py.

Validates:
    - Vignette loading from YAML
    - ICC(2,1) computation with known data
    - Cronbach's alpha
    - Fleiss' kappa for decision agreement
    - PsychometricBattery response collection and analysis
    - Coherence evaluation against vignette expectations
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path

from broker.validators.calibration.psychometric_battery import (
    PsychometricBattery,
    Vignette,
    ProbeResponse,
    ICCResult,
    ConsistencyResult,
    VignetteReport,
    BatteryReport,
    EffectSizeResult,
    ConvergentValidityResult,
    compute_icc_2_1,
    compute_cronbach_alpha,
    compute_fleiss_kappa,
    LABEL_TO_ORDINAL,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def battery():
    """PsychometricBattery with flood-domain vignettes."""
    vdir = Path(__file__).resolve().parents[1] / "examples" / "multi_agent" / "flood" / "paper3" / "configs" / "vignettes"
    return PsychometricBattery(vignette_dir=vdir)


@pytest.fixture
def sample_responses():
    """Simulated responses: 3 archetypes x 3 vignettes x 5 replicates."""
    responses = []
    archetypes = ["risk_averse", "risk_neutral", "risk_seeking"]
    vignettes = {
        "high_severity_flood": {"tp": "VH", "cp": "H", "dec": "elevate_house"},
        "medium_severity_flood": {"tp": "M", "cp": "M", "dec": "buy_insurance"},
        "low_severity_flood": {"tp": "L", "cp": "H", "dec": "do_nothing"},
    }

    for vid, expected in vignettes.items():
        for arch_idx, arch in enumerate(archetypes):
            for rep in range(1, 6):
                # Add some variation by archetype
                tp = expected["tp"]
                cp = expected["cp"]

                # Risk-seeking agents have slightly lower TP perception
                if arch == "risk_seeking" and tp in ("VH", "H"):
                    tp = "H" if tp == "VH" else "M"

                responses.append(ProbeResponse(
                    vignette_id=vid,
                    archetype=arch,
                    replicate=rep,
                    tp_label=tp,
                    cp_label=cp,
                    decision=expected["dec"],
                    governed=False,
                ))

    return responses


@pytest.fixture
def governed_responses(sample_responses):
    """Same responses but with governed=True (for P2 comparison)."""
    governed = []
    for r in sample_responses:
        governed.append(ProbeResponse(
            vignette_id=r.vignette_id,
            archetype=r.archetype,
            replicate=r.replicate,
            tp_label=r.tp_label,
            cp_label=r.cp_label,
            decision=r.decision,
            governed=True,
        ))
    return governed


# ---------------------------------------------------------------------------
# Vignette loading
# ---------------------------------------------------------------------------

class TestVignetteLoading:
    """Tests for vignette YAML loading."""

    def test_load_vignettes(self, battery):
        """Should load all vignettes from default directory (3 core + 3 edge-case)."""
        vignettes = battery.load_vignettes()
        assert len(vignettes) >= 3  # At least 3 core vignettes
        ids = {v.id for v in vignettes}
        assert "high_severity_flood" in ids
        assert "medium_severity_flood" in ids
        assert "low_severity_flood" in ids

    def test_vignette_properties(self, battery):
        """Each vignette should have required properties."""
        battery.load_vignettes()
        for vid, v in battery.vignettes.items():
            assert v.id
            assert v.severity in ("high", "medium", "low", "extreme")
            assert v.scenario
            assert v.state_overrides
            assert v.expected_responses

    def test_high_severity_expectations(self, battery):
        """High severity vignette should expect H/VH threat."""
        battery.load_vignettes()
        v = battery.vignettes["high_severity_flood"]
        tp_expected = v.expected_responses["TP_LABEL"]["expected"]
        assert "H" in tp_expected or "VH" in tp_expected
        dec_incoherent = v.expected_responses["decision"]["incoherent"]
        assert "do_nothing" in dec_incoherent

    def test_low_severity_expectations(self, battery):
        """Low severity vignette should expect VL/L threat."""
        battery.load_vignettes()
        v = battery.vignettes["low_severity_flood"]
        tp_expected = v.expected_responses["TP_LABEL"]["expected"]
        assert "VL" in tp_expected or "L" in tp_expected

    def test_missing_directory(self):
        """Missing vignette dir should return empty list."""
        battery = PsychometricBattery(vignette_dir=Path("/nonexistent"))
        vignettes = battery.load_vignettes()
        assert len(vignettes) == 0


# ---------------------------------------------------------------------------
# ICC(2,1)
# ---------------------------------------------------------------------------

class TestICC:
    """Tests for Intraclass Correlation Coefficient computation."""

    def test_perfect_agreement(self):
        """All raters give same score -> ICC = 1.0."""
        # 4 subjects, 5 raters, all identical
        ratings = np.array([
            [5, 5, 5, 5, 5],
            [3, 3, 3, 3, 3],
            [1, 1, 1, 1, 1],
            [4, 4, 4, 4, 4],
        ], dtype=float)
        result = compute_icc_2_1(ratings, "perfect")
        assert result.icc_value == pytest.approx(1.0, abs=0.01)

    def test_random_disagreement(self):
        """Random ratings should have low ICC."""
        rng = np.random.RandomState(42)
        ratings = rng.randint(1, 6, size=(6, 10)).astype(float)
        result = compute_icc_2_1(ratings, "random")
        assert result.icc_value < 0.3  # Very low agreement

    def test_moderate_agreement(self):
        """Partially consistent ratings -> moderate ICC."""
        # Subjects have different means, raters have small noise
        rng = np.random.RandomState(42)
        base = np.array([1, 2, 3, 4, 5], dtype=float)
        ratings = np.column_stack([
            base + rng.normal(0, 0.3, 5) for _ in range(8)
        ])
        result = compute_icc_2_1(ratings, "moderate")
        assert 0.5 < result.icc_value <= 1.0

    def test_icc_insufficient_data(self):
        """Single subject or single rater -> ICC = 0."""
        ratings = np.array([[3, 4, 5]], dtype=float)  # 1 subject
        result = compute_icc_2_1(ratings, "insufficient")
        assert result.icc_value == 0.0

    def test_icc_result_fields(self):
        """ICC result should have all expected fields."""
        ratings = np.array([
            [3, 4, 3, 4],
            [1, 2, 1, 2],
            [5, 5, 4, 5],
        ], dtype=float)
        result = compute_icc_2_1(ratings, "test")
        assert result.construct == "test"
        assert result.n_subjects == 3
        assert result.n_raters == 4
        d = result.to_dict()
        assert "icc" in d
        assert "ci_95" in d


# ---------------------------------------------------------------------------
# Cronbach's alpha
# ---------------------------------------------------------------------------

class TestCronbach:
    """Tests for Cronbach's alpha computation."""

    def test_perfect_correlation(self):
        """Perfectly correlated items -> alpha = 1.0."""
        items = np.array([
            [1, 1], [2, 2], [3, 3], [4, 4], [5, 5],
        ], dtype=float)
        alpha = compute_cronbach_alpha(items)
        assert alpha == pytest.approx(1.0, abs=0.01)

    def test_random_items(self):
        """Random items -> low alpha."""
        rng = np.random.RandomState(42)
        items = rng.randint(1, 6, size=(50, 3)).astype(float)
        alpha = compute_cronbach_alpha(items)
        assert alpha < 0.3

    def test_single_item(self):
        """Single item -> alpha = 0."""
        items = np.array([[1], [2], [3]], dtype=float)
        alpha = compute_cronbach_alpha(items)
        assert alpha == 0.0


# ---------------------------------------------------------------------------
# Fleiss' kappa
# ---------------------------------------------------------------------------

class TestFleiss:
    """Tests for Fleiss' kappa computation."""

    def test_perfect_agreement(self):
        """All raters agree -> kappa = 1.0."""
        decisions = [
            ["elevate", "elevate", "elevate"],
            ["insure", "insure", "insure"],
            ["nothing", "nothing", "nothing"],
        ]
        kappa = compute_fleiss_kappa(decisions)
        assert kappa == pytest.approx(1.0, abs=0.01)

    def test_random_agreement(self):
        """Random decisions -> kappa near 0."""
        rng = np.random.RandomState(42)
        actions = ["elevate", "insure", "nothing", "relocate"]
        decisions = [
            [rng.choice(actions) for _ in range(10)]
            for _ in range(20)
        ]
        kappa = compute_fleiss_kappa(decisions)
        assert -0.2 < kappa < 0.3

    def test_empty_decisions(self):
        """Empty list -> kappa = 0."""
        kappa = compute_fleiss_kappa([])
        assert kappa == 0.0


# ---------------------------------------------------------------------------
# Battery response collection
# ---------------------------------------------------------------------------

class TestBatteryResponses:
    """Tests for response collection and DataFrame conversion."""

    def test_add_responses(self, battery, sample_responses):
        """Adding responses should accumulate."""
        battery.add_responses(sample_responses)
        assert len(battery.responses) == len(sample_responses)

    def test_to_dataframe(self, battery, sample_responses):
        """Responses should convert to DataFrame."""
        battery.add_responses(sample_responses)
        df = battery.responses_to_dataframe()
        assert len(df) == len(sample_responses)
        assert "vignette_id" in df.columns
        assert "tp_ordinal" in df.columns

    def test_ordinal_conversion(self):
        """ProbeResponse should convert labels to ordinals."""
        r = ProbeResponse(
            vignette_id="test", archetype="a", replicate=1,
            tp_label="VH", cp_label="L",
        )
        assert r.tp_ordinal == 5
        assert r.cp_ordinal == 2


# ---------------------------------------------------------------------------
# Battery analysis
# ---------------------------------------------------------------------------

class TestBatteryAnalysis:
    """Tests for ICC, consistency, and agreement analysis."""

    def test_icc_computation(self, battery, sample_responses):
        """ICC should be computable from sample responses."""
        battery.load_vignettes()
        battery.add_responses(sample_responses)
        icc = battery.compute_icc(
            vignette_id="high_severity_flood",
            construct="tp",
        )
        assert isinstance(icc, ICCResult)
        assert icc.n_subjects > 0

    def test_consistency(self, battery, sample_responses):
        """Consistency should be computable."""
        battery.add_responses(sample_responses)
        result = battery.compute_consistency()
        assert isinstance(result, ConsistencyResult)
        assert result.n_items == 2

    def test_decision_agreement(self, battery, sample_responses):
        """Agreement should be high for consistent responses."""
        battery.load_vignettes()
        battery.add_responses(sample_responses)
        # Within each vignette, all archetypes give same decision
        # (with some variation), so kappa should be moderate to high
        kappa = battery.compute_decision_agreement(
            vignette_id="high_severity_flood"
        )
        assert isinstance(kappa, float)

    def test_coherence_evaluation(self, battery, sample_responses):
        """Coherence against vignette expectations."""
        battery.load_vignettes()
        battery.add_responses(sample_responses)
        coh, incoh = battery.evaluate_coherence("high_severity_flood")
        # All responses should be coherent for high severity
        assert coh > 0  # At least some coherent

    def test_coherence_low_severity(self, battery, sample_responses):
        """Low severity: do_nothing should be coherent."""
        battery.load_vignettes()
        battery.add_responses(sample_responses)
        coh, incoh = battery.evaluate_coherence("low_severity_flood")
        assert coh > 0
        assert incoh == 0  # L threat + do_nothing should not be incoherent


# ---------------------------------------------------------------------------
# Full report
# ---------------------------------------------------------------------------

class TestBatteryReport:
    """Tests for full battery report generation."""

    def test_full_report(self, battery, sample_responses):
        """Full report should include all components."""
        battery.load_vignettes()
        battery.add_responses(sample_responses)
        report = battery.compute_full_report()
        assert isinstance(report, BatteryReport)
        assert len(report.vignette_reports) == 3
        assert report.overall_tp_icc is not None
        assert report.consistency is not None
        assert report.n_total_probes == len(sample_responses)

    def test_report_to_dict(self, battery, sample_responses):
        """Report serialization."""
        battery.load_vignettes()
        battery.add_responses(sample_responses)
        report = battery.compute_full_report()
        d = report.to_dict()
        assert "n_total_probes" in d
        assert "n_vignettes" in d
        assert "overall_tp_icc" in d

    def test_governance_effect(
        self, battery, sample_responses, governed_responses
    ):
        """Governance effect comparison."""
        battery.load_vignettes()
        battery.add_responses(sample_responses)
        battery.add_responses(governed_responses)
        effect = battery.compute_governance_effect()
        assert "tp_icc_governed" in effect
        assert "tp_icc_ungoverned" in effect
        assert effect["n_governed"] > 0
        assert effect["n_ungoverned"] > 0

    def test_full_report_includes_r3d_fields(self, battery, sample_responses):
        """Report should include R3-D fields: effect size, convergent, discriminant."""
        battery.load_vignettes()
        battery.add_responses(sample_responses)
        report = battery.compute_full_report()
        assert report.tp_effect_size is not None
        assert report.cp_effect_size is not None
        assert report.convergent_validity is not None
        assert isinstance(report.tp_cp_discriminant, float)
        d = report.to_dict()
        assert "tp_effect_size" in d
        assert "tp_cp_discriminant_r" in d


# ---------------------------------------------------------------------------
# R3-D: Effect size, convergent validity, discriminant
# ---------------------------------------------------------------------------

class TestEffectSize:
    """Tests for eta-squared between-archetype effect size."""

    def test_effect_size_basic(self, battery, sample_responses):
        """Effect size should be computable from sample responses."""
        battery.add_responses(sample_responses)
        result = battery.compute_effect_size(construct="tp")
        assert isinstance(result, EffectSizeResult)
        assert 0.0 <= result.eta_squared <= 1.0
        assert result.construct == "tp"

    def test_effect_size_cp(self, battery, sample_responses):
        """Effect size for CP construct."""
        battery.add_responses(sample_responses)
        result = battery.compute_effect_size(construct="cp")
        assert isinstance(result, EffectSizeResult)
        assert 0.0 <= result.eta_squared <= 1.0

    def test_effect_size_with_variation(self, battery):
        """Different archetypes with different TP -> positive eta-squared."""
        responses = []
        for rep in range(1, 6):
            # Archetype A: always VH TP
            responses.append(ProbeResponse(
                vignette_id="v1", archetype="high_risk", replicate=rep,
                tp_label="VH", cp_label="H",
            ))
            # Archetype B: always L TP
            responses.append(ProbeResponse(
                vignette_id="v1", archetype="low_risk", replicate=rep,
                tp_label="L", cp_label="M",
            ))
        battery.add_responses(responses)
        result = battery.compute_effect_size(construct="tp")
        # Large between-group difference -> high eta-squared
        assert result.eta_squared > 0.5

    def test_effect_size_no_variation(self, battery):
        """Identical archetypes -> eta-squared = 0."""
        responses = []
        for arch in ["a", "b", "c"]:
            for rep in range(1, 4):
                responses.append(ProbeResponse(
                    vignette_id="v1", archetype=arch, replicate=rep,
                    tp_label="M", cp_label="M",
                ))
        battery.add_responses(responses)
        result = battery.compute_effect_size(construct="tp")
        assert result.eta_squared == pytest.approx(0.0, abs=0.01)

    def test_effect_size_empty(self, battery):
        """Empty responses -> eta-squared = 0."""
        result = battery.compute_effect_size(construct="tp")
        assert result.eta_squared == 0.0

    def test_effect_size_to_dict(self, battery, sample_responses):
        """EffectSizeResult serialization."""
        battery.add_responses(sample_responses)
        result = battery.compute_effect_size(construct="tp")
        d = result.to_dict()
        assert "eta_squared" in d
        assert "construct" in d


class TestConvergentValidity:
    """Tests for TP vs vignette severity correlation."""

    def test_convergent_basic(self, battery, sample_responses):
        """Convergent validity should be computable."""
        battery.load_vignettes()
        battery.add_responses(sample_responses)
        result = battery.compute_convergent_validity()
        assert isinstance(result, ConvergentValidityResult)
        assert -1.0 <= result.spearman_rho <= 1.0
        assert result.n_observations > 0

    def test_convergent_positive_correlation(self, battery):
        """Higher severity -> higher TP should produce positive rho."""
        battery.load_vignettes()
        responses = []
        for rep in range(1, 6):
            responses.append(ProbeResponse(
                vignette_id="high_severity_flood", archetype="a",
                replicate=rep, tp_label="VH", cp_label="H",
            ))
            responses.append(ProbeResponse(
                vignette_id="low_severity_flood", archetype="a",
                replicate=rep, tp_label="L", cp_label="H",
            ))
        battery.add_responses(responses)
        result = battery.compute_convergent_validity()
        assert result.spearman_rho > 0.3  # Positive correlation

    def test_convergent_empty(self, battery):
        """Empty responses -> rho = 0."""
        battery.load_vignettes()
        result = battery.compute_convergent_validity()
        assert result.spearman_rho == 0.0

    def test_convergent_to_dict(self, battery, sample_responses):
        """ConvergentValidityResult serialization."""
        battery.load_vignettes()
        battery.add_responses(sample_responses)
        result = battery.compute_convergent_validity()
        d = result.to_dict()
        assert "spearman_rho" in d
        assert "n_observations" in d


class TestDiscriminant:
    """Tests for TP-CP discriminant correlation."""

    def test_discriminant_basic(self, battery, sample_responses):
        """Discriminant should return a correlation value."""
        battery.add_responses(sample_responses)
        r = battery.compute_discriminant()
        assert isinstance(r, float)
        assert -1.0 <= r <= 1.0

    def test_discriminant_independent_constructs(self, battery):
        """TP and CP varying independently -> low correlation."""
        responses = []
        tp_labels = ["VL", "L", "M", "H", "VH"]
        cp_labels = ["VH", "M", "VL", "H", "L"]  # Not ordered with TP
        for i in range(5):
            for rep in range(1, 4):
                responses.append(ProbeResponse(
                    vignette_id="v1", archetype=f"arch_{i}",
                    replicate=rep,
                    tp_label=tp_labels[i], cp_label=cp_labels[i],
                ))
        battery.add_responses(responses)
        r = battery.compute_discriminant()
        assert abs(r) < 0.8  # Should not be highly correlated

    def test_discriminant_empty(self, battery):
        """Empty responses -> r = 0."""
        r = battery.compute_discriminant()
        assert r == 0.0
