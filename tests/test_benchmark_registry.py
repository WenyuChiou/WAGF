"""Tests for BenchmarkRegistry — domain-agnostic empirical benchmark engine.

Validates:
    - Benchmark creation and validation
    - Registry registration and lookup
    - Comparison with tolerance-based range checking
    - Weighted EPI computation
    - Per-category EPI breakdown
    - Missing metric detection
    - YAML / dict loading
    - Deviation direction and magnitude
    - Edge cases (empty registry, all pass, all fail)
"""

import json
import pytest
from pathlib import Path

from broker.validators.calibration.benchmark_registry import (
    Benchmark,
    BenchmarkCategory,
    BenchmarkComparison,
    BenchmarkRegistry,
    BenchmarkReport,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_benchmarks():
    """Sample benchmarks for testing."""
    return [
        Benchmark(
            name="Insurance Uptake",
            metric="insurance_rate",
            rate_low=0.30,
            rate_high=0.50,
            source="Kousky (2017)",
            category=BenchmarkCategory.AGGREGATE,
            weight=1.0,
        ),
        Benchmark(
            name="Elevation Rate",
            metric="elevation_rate",
            rate_low=0.03,
            rate_high=0.12,
            source="Haer et al. (2017)",
            category=BenchmarkCategory.AGGREGATE,
            weight=1.0,
        ),
        Benchmark(
            name="Post-Flood Inaction",
            metric="do_nothing_rate_postflood",
            rate_low=0.35,
            rate_high=0.65,
            source="Grothmann & Reusswig (2006)",
            category=BenchmarkCategory.CONDITIONAL,
            weight=1.5,
        ),
        Benchmark(
            name="MG-NMG Gap",
            metric="mg_adaptation_gap",
            rate_low=0.10,
            rate_high=0.30,
            source="Choi et al. (2024)",
            category=BenchmarkCategory.DEMOGRAPHIC,
            weight=2.0,
        ),
    ]


@pytest.fixture
def registry(sample_benchmarks):
    """Registry with sample benchmarks."""
    return BenchmarkRegistry(benchmarks=sample_benchmarks)


# ---------------------------------------------------------------------------
# Benchmark dataclass
# ---------------------------------------------------------------------------

class TestBenchmark:
    def test_creation(self):
        bm = Benchmark(
            name="Test",
            metric="test_rate",
            rate_low=0.10,
            rate_high=0.40,
            source="Test (2024)",
        )
        assert bm.name == "Test"
        assert bm.metric == "test_rate"
        assert bm.midpoint == 0.25

    def test_invalid_range(self):
        with pytest.raises(ValueError, match="rate_low.*rate_high"):
            Benchmark(
                name="Bad",
                metric="bad",
                rate_low=0.50,
                rate_high=0.30,
                source="",
            )

    def test_negative_weight(self):
        with pytest.raises(ValueError, match="weight"):
            Benchmark(
                name="Bad",
                metric="bad",
                rate_low=0.10,
                rate_high=0.30,
                source="",
                weight=-1.0,
            )

    def test_equal_range(self):
        """rate_low == rate_high is valid (exact target)."""
        bm = Benchmark(
            name="Exact",
            metric="exact",
            rate_low=0.25,
            rate_high=0.25,
            source="",
        )
        assert bm.midpoint == 0.25

    def test_from_dict(self):
        d = {
            "name": "Test",
            "metric": "test_rate",
            "rate_low": 0.10,
            "rate_high": 0.40,
            "source": "Test (2024)",
            "category": "conditional",
            "weight": 2.0,
            "required": True,
        }
        bm = Benchmark.from_dict(d)
        assert bm.category == BenchmarkCategory.CONDITIONAL
        assert bm.weight == 2.0
        assert bm.required is True

    def test_from_dict_defaults(self):
        d = {
            "name": "Test",
            "metric": "test_rate",
            "rate_low": 0.10,
            "rate_high": 0.40,
        }
        bm = Benchmark.from_dict(d)
        assert bm.source == ""
        assert bm.category == BenchmarkCategory.AGGREGATE
        assert bm.weight == 1.0
        assert bm.required is False

    def test_to_dict(self):
        bm = Benchmark(
            name="Test",
            metric="test_rate",
            rate_low=0.10,
            rate_high=0.40,
            source="Test (2024)",
            category=BenchmarkCategory.TEMPORAL,
            weight=1.5,
        )
        d = bm.to_dict()
        assert d["category"] == "temporal"
        assert d["weight"] == 1.5

    def test_roundtrip(self):
        bm = Benchmark(
            name="RT",
            metric="rt_rate",
            rate_low=0.05,
            rate_high=0.20,
            source="RT (2025)",
            category=BenchmarkCategory.DISTRIBUTIONAL,
            weight=3.0,
            required=True,
        )
        bm2 = Benchmark.from_dict(bm.to_dict())
        assert bm2.name == bm.name
        assert bm2.metric == bm.metric
        assert bm2.rate_low == bm.rate_low
        assert bm2.rate_high == bm.rate_high
        assert bm2.category == bm.category
        assert bm2.weight == bm.weight
        assert bm2.required == bm.required


# ---------------------------------------------------------------------------
# Registry basics
# ---------------------------------------------------------------------------

class TestRegistryBasics:
    def test_empty_registry(self):
        reg = BenchmarkRegistry()
        assert len(reg) == 0
        assert reg.metrics == []

    def test_register_single(self):
        reg = BenchmarkRegistry()
        bm = Benchmark(
            name="Test", metric="test", rate_low=0.1, rate_high=0.5,
            source=""
        )
        reg.register(bm)
        assert len(reg) == 1
        assert "test" in reg
        assert reg.get("test") is bm

    def test_register_many(self, sample_benchmarks):
        reg = BenchmarkRegistry()
        reg.register_many(sample_benchmarks)
        assert len(reg) == 4
        assert "insurance_rate" in reg
        assert "elevation_rate" in reg

    def test_constructor_registration(self, sample_benchmarks):
        reg = BenchmarkRegistry(benchmarks=sample_benchmarks)
        assert len(reg) == 4

    def test_overwrite_warning(self, caplog):
        reg = BenchmarkRegistry()
        bm1 = Benchmark(
            name="First", metric="test", rate_low=0.1, rate_high=0.5,
            source=""
        )
        bm2 = Benchmark(
            name="Second", metric="test", rate_low=0.2, rate_high=0.6,
            source=""
        )
        reg.register(bm1)
        reg.register(bm2)
        assert len(reg) == 1
        assert reg.get("test").name == "Second"

    def test_get_nonexistent(self):
        reg = BenchmarkRegistry()
        assert reg.get("nonexistent") is None

    def test_benchmarks_property(self, sample_benchmarks):
        reg = BenchmarkRegistry(benchmarks=sample_benchmarks)
        assert len(reg.benchmarks) == 4


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

class TestComparison:
    def test_all_within_range(self, registry):
        observed = {
            "insurance_rate": 0.40,
            "elevation_rate": 0.07,
            "do_nothing_rate_postflood": 0.50,
            "mg_adaptation_gap": 0.20,
        }
        report = registry.compare(observed, tolerance=0.3)
        assert report.n_total == 4
        assert report.n_within_range == 4
        assert report.plausibility_score == pytest.approx(1.0)

    def test_all_out_of_range(self, registry):
        observed = {
            "insurance_rate": 0.01,    # too low
            "elevation_rate": 0.90,    # too high
            "do_nothing_rate_postflood": 0.01,  # too low
            "mg_adaptation_gap": 0.90,  # too high
        }
        report = registry.compare(observed, tolerance=0.3)
        assert report.n_within_range == 0
        assert report.plausibility_score == pytest.approx(0.0)

    def test_mixed_results(self, registry):
        observed = {
            "insurance_rate": 0.40,     # within range
            "elevation_rate": 0.90,     # too high
            "do_nothing_rate_postflood": 0.50,  # within range
            "mg_adaptation_gap": 0.90,  # too high
        }
        report = registry.compare(observed, tolerance=0.3)
        assert report.n_within_range == 2
        assert report.n_total == 4
        # Weighted: ins(1.0) + inaction(1.5) = 2.5 pass,
        #           elev(1.0) + gap(2.0) = 3.0 fail
        # EPI = 2.5 / 5.5
        assert report.plausibility_score == pytest.approx(2.5 / 5.5, abs=0.001)

    def test_tolerance_effect(self, registry):
        # Observed at the low boundary edge
        observed = {"insurance_rate": 0.20}
        # With 0.3 tolerance: low_bound = 0.30 * 0.70 = 0.21 → 0.20 fails
        report = registry.compare(observed, tolerance=0.3)
        assert report.comparisons[0].within_range is False
        # With 0.5 tolerance: low_bound = 0.30 * 0.50 = 0.15 → 0.20 passes
        report = registry.compare(observed, tolerance=0.5)
        assert report.comparisons[0].within_range is True

    def test_zero_tolerance(self, registry):
        observed = {"insurance_rate": 0.40}
        report = registry.compare(observed, tolerance=0.0)
        assert report.comparisons[0].within_range is True

        observed = {"insurance_rate": 0.29}
        report = registry.compare(observed, tolerance=0.0)
        assert report.comparisons[0].within_range is False

    def test_missing_metric_not_counted(self, registry):
        observed = {"insurance_rate": 0.40}  # only 1 of 4
        report = registry.compare(observed, tolerance=0.3)
        assert report.n_total == 1
        assert report.n_within_range == 1
        assert report.plausibility_score == pytest.approx(1.0)

    def test_missing_required_metric(self):
        reg = BenchmarkRegistry(benchmarks=[
            Benchmark(
                name="Required",
                metric="must_have",
                rate_low=0.10,
                rate_high=0.50,
                source="",
                required=True,
            ),
        ])
        observed = {}  # metric absent
        report = reg.compare(observed)
        assert "must_have" in report.missing_metrics
        assert report.n_total == 0

    def test_empty_observed(self, registry):
        report = registry.compare({})
        assert report.n_total == 0
        assert report.plausibility_score == 0.0

    def test_empty_registry(self):
        reg = BenchmarkRegistry()
        report = reg.compare({"foo": 0.5})
        assert report.n_total == 0


# ---------------------------------------------------------------------------
# Deviation direction and magnitude
# ---------------------------------------------------------------------------

class TestDeviation:
    def test_too_low(self, registry):
        observed = {"insurance_rate": 0.10}  # low_bound = 0.21
        report = registry.compare(observed, tolerance=0.3)
        comp = report.comparisons[0]
        assert comp.deviation_direction == "too_low"
        assert comp.deviation_magnitude == pytest.approx(0.21 - 0.10, abs=0.001)

    def test_too_high(self, registry):
        observed = {"insurance_rate": 0.90}  # high_bound = 0.65
        report = registry.compare(observed, tolerance=0.3)
        comp = report.comparisons[0]
        assert comp.deviation_direction == "too_high"
        assert comp.deviation_magnitude == pytest.approx(0.90 - 0.65, abs=0.001)

    def test_ok(self, registry):
        observed = {"insurance_rate": 0.40}
        report = registry.compare(observed, tolerance=0.3)
        comp = report.comparisons[0]
        assert comp.deviation_direction == "ok"
        assert comp.deviation_magnitude == 0.0

    def test_ratio_to_midpoint(self, registry):
        observed = {"insurance_rate": 0.40}
        report = registry.compare(observed, tolerance=0.3)
        comp = report.comparisons[0]
        # midpoint = 0.40, ratio = 0.40 / 0.40 = 1.0
        assert comp.ratio_to_midpoint == pytest.approx(1.0)

    def test_out_of_range_list(self, registry):
        observed = {
            "insurance_rate": 0.01,     # out
            "elevation_rate": 0.07,     # in
        }
        report = registry.compare(observed, tolerance=0.3)
        assert len(report.out_of_range) == 1
        assert report.out_of_range[0].metric == "insurance_rate"


# ---------------------------------------------------------------------------
# Category breakdown
# ---------------------------------------------------------------------------

class TestCategoryBreakdown:
    def test_by_category(self, registry):
        observed = {
            "insurance_rate": 0.40,     # aggregate, pass
            "elevation_rate": 0.90,     # aggregate, fail
            "do_nothing_rate_postflood": 0.50,  # conditional, pass
            "mg_adaptation_gap": 0.20,  # demographic, pass
        }
        report = registry.compare(observed, tolerance=0.3)
        # Aggregate: 1 pass (w=1.0), 1 fail (w=1.0) → 0.5
        assert report.by_category["aggregate"] == pytest.approx(0.5)
        # Conditional: 1 pass → 1.0
        assert report.by_category["conditional"] == pytest.approx(1.0)
        # Demographic: 1 pass → 1.0
        assert report.by_category["demographic"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Weighted EPI
# ---------------------------------------------------------------------------

class TestWeightedEPI:
    def test_equal_weights(self):
        reg = BenchmarkRegistry(benchmarks=[
            Benchmark(name="A", metric="a", rate_low=0.1, rate_high=0.5,
                      source="", weight=1.0),
            Benchmark(name="B", metric="b", rate_low=0.1, rate_high=0.5,
                      source="", weight=1.0),
        ])
        observed = {"a": 0.3, "b": 0.01}
        report = reg.compare(observed, tolerance=0.3)
        # 1 pass, 1 fail, equal weights → EPI = 0.5
        assert report.plausibility_score == pytest.approx(0.5)

    def test_unequal_weights(self):
        reg = BenchmarkRegistry(benchmarks=[
            Benchmark(name="A", metric="a", rate_low=0.1, rate_high=0.5,
                      source="", weight=3.0),
            Benchmark(name="B", metric="b", rate_low=0.1, rate_high=0.5,
                      source="", weight=1.0),
        ])
        # A passes (weight=3), B fails (weight=1) → EPI = 3/4 = 0.75
        observed = {"a": 0.3, "b": 0.01}
        report = reg.compare(observed, tolerance=0.3)
        assert report.plausibility_score == pytest.approx(0.75)

    def test_zero_weight_benchmark(self):
        reg = BenchmarkRegistry(benchmarks=[
            Benchmark(name="A", metric="a", rate_low=0.1, rate_high=0.5,
                      source="", weight=1.0),
            Benchmark(name="B", metric="b", rate_low=0.1, rate_high=0.5,
                      source="", weight=0.0),
        ])
        # B has weight 0 — doesn't affect EPI
        observed = {"a": 0.3, "b": 0.01}
        report = reg.compare(observed, tolerance=0.3)
        # Only A contributes: 1.0/1.0 = 1.0
        assert report.plausibility_score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# compute_epi convenience
# ---------------------------------------------------------------------------

class TestComputeEPI:
    def test_matches_compare(self, registry):
        observed = {
            "insurance_rate": 0.40,
            "elevation_rate": 0.07,
            "do_nothing_rate_postflood": 0.50,
            "mg_adaptation_gap": 0.20,
        }
        epi = registry.compute_epi(observed, tolerance=0.3)
        report = registry.compare(observed, tolerance=0.3)
        assert epi == pytest.approx(report.plausibility_score)


# ---------------------------------------------------------------------------
# YAML / Dict loading
# ---------------------------------------------------------------------------

class TestLoading:
    def test_load_from_dict_top_level(self):
        data = {
            "benchmarks": [
                {
                    "name": "Test A",
                    "metric": "rate_a",
                    "rate_low": 0.10,
                    "rate_high": 0.40,
                    "source": "Test (2024)",
                },
                {
                    "name": "Test B",
                    "metric": "rate_b",
                    "rate_low": 0.20,
                    "rate_high": 0.60,
                    "source": "Test (2024)",
                    "category": "demographic",
                },
            ]
        }
        reg = BenchmarkRegistry()
        reg.load_from_dict(data)
        assert len(reg) == 2
        assert reg.get("rate_a").name == "Test A"
        assert reg.get("rate_b").category == BenchmarkCategory.DEMOGRAPHIC

    def test_load_from_dict_nested(self):
        data = {
            "calibration": {
                "benchmarks": [
                    {
                        "name": "Nested",
                        "metric": "nested_rate",
                        "rate_low": 0.05,
                        "rate_high": 0.15,
                        "source": "",
                    },
                ]
            }
        }
        reg = BenchmarkRegistry()
        reg.load_from_dict(data)
        assert len(reg) == 1
        assert "nested_rate" in reg

    def test_load_from_dict_empty(self):
        reg = BenchmarkRegistry()
        reg.load_from_dict({"other_key": "value"})
        assert len(reg) == 0

    def test_load_from_yaml(self, tmp_path):
        yaml_content = """
benchmarks:
  - name: YAML Test
    metric: yaml_rate
    rate_low: 0.10
    rate_high: 0.30
    source: "YAML (2024)"
    category: temporal
    weight: 2.5
"""
        yaml_path = tmp_path / "test_benchmarks.yaml"
        yaml_path.write_text(yaml_content)

        reg = BenchmarkRegistry()
        reg.load_from_yaml(yaml_path)
        assert len(reg) == 1
        bm = reg.get("yaml_rate")
        assert bm.name == "YAML Test"
        assert bm.category == BenchmarkCategory.TEMPORAL
        assert bm.weight == 2.5

    def test_load_from_yaml_nested(self, tmp_path):
        yaml_content = """
calibration:
  decision_col: yearly_decision
  benchmarks:
    - name: Nested YAML
      metric: nested_yaml_rate
      rate_low: 0.05
      rate_high: 0.20
      source: ""
"""
        yaml_path = tmp_path / "nested.yaml"
        yaml_path.write_text(yaml_content)

        reg = BenchmarkRegistry()
        reg.load_from_yaml(yaml_path)
        assert len(reg) == 1
        assert "nested_yaml_rate" in reg


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_report_to_dict(self, registry):
        observed = {
            "insurance_rate": 0.40,
            "elevation_rate": 0.07,
        }
        report = registry.compare(observed, tolerance=0.3)
        d = report.to_dict()
        assert d["n_benchmarks_evaluated"] == 2
        assert d["n_within_range"] == 2
        assert "plausibility_score" in d
        assert "by_category" in d
        assert len(d["comparisons"]) == 2

    def test_report_save_json(self, registry, tmp_path):
        observed = {
            "insurance_rate": 0.40,
            "elevation_rate": 0.07,
        }
        report = registry.compare(observed, tolerance=0.3)
        json_path = tmp_path / "sub" / "report.json"
        report.save_json(json_path)

        assert json_path.exists()
        loaded = json.loads(json_path.read_text())
        assert loaded["n_benchmarks_evaluated"] == 2

    def test_comparison_to_dict(self, registry):
        observed = {"insurance_rate": 0.40}
        report = registry.compare(observed, tolerance=0.3)
        d = report.comparisons[0].to_dict()
        assert d["metric"] == "insurance_rate"
        assert d["deviation_direction"] == "ok"
        assert "expected_range" in d


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_zero_midpoint(self):
        """Benchmark with rate_low == rate_high == 0."""
        reg = BenchmarkRegistry(benchmarks=[
            Benchmark(
                name="Zero",
                metric="zero_rate",
                rate_low=0.0,
                rate_high=0.0,
                source="",
            ),
        ])
        report = reg.compare({"zero_rate": 0.0}, tolerance=0.3)
        assert report.comparisons[0].within_range is True
        assert report.comparisons[0].ratio_to_midpoint == 0.0

    def test_very_small_range(self):
        reg = BenchmarkRegistry(benchmarks=[
            Benchmark(
                name="Tiny",
                metric="tiny",
                rate_low=0.001,
                rate_high=0.002,
                source="",
            ),
        ])
        report = reg.compare({"tiny": 0.0015}, tolerance=0.3)
        assert report.comparisons[0].within_range is True

    def test_extra_observed_metrics_ignored(self, registry):
        observed = {
            "insurance_rate": 0.40,
            "unknown_metric": 0.99,
        }
        report = registry.compare(observed, tolerance=0.3)
        assert report.n_total == 1  # only insurance_rate matched
