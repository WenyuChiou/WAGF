"""
Tests for Phase 1 v2 type enhancements.

Tests:
- Enhanced PolicyRule with domain metadata
- SensorConfig for universal sensor schema
- ResearchTrace for academic reproducibility
"""
import pytest
from datetime import datetime
from cognitive_governance.v1_prototype.types import (
    PolicyRule,
    RuleOperator,
    RuleLevel,
    ParamType,
    Domain,
    SensorConfig,
    ResearchTrace,
    CounterFactualResult,
    CounterFactualStrategy,
)


class TestPolicyRuleV2:
    """Tests for enhanced PolicyRule with domain metadata."""

    def test_create_with_domain_metadata(self):
        """Can create rule with all v2 fields."""
        rule = PolicyRule(
            id="min_savings",
            param="savings",
            operator=">=",
            value=500,
            message="Insufficient savings",
            level="ERROR",
            domain="finance",
            param_type="numeric",
            param_unit="USD",
            severity_score=0.8,
            literature_ref="CFPB 2023",
            rationale="Emergency fund minimum"
        )
        assert rule.domain == "finance"
        assert rule.param_type == "numeric"
        assert rule.param_unit == "USD"
        assert rule.severity_score == 0.8
        assert rule.literature_ref == "CFPB 2023"

    def test_default_domain_values(self):
        """Default v2 fields have correct values."""
        rule = PolicyRule(
            id="test",
            param="x",
            operator=">=",
            value=10,
            message="test",
        )
        assert rule.domain == "generic"
        assert rule.param_type == "numeric"
        assert rule.param_unit is None
        assert rule.severity_score == 1.0
        assert rule.literature_ref is None

    def test_severity_score_validation(self):
        """severity_score must be 0-1."""
        with pytest.raises(ValueError, match="severity_score must be 0-1"):
            PolicyRule(
                id="test",
                param="x",
                operator=">=",
                value=10,
                message="test",
                severity_score=1.5
            )

    def test_severity_score_negative(self):
        """Negative severity_score is rejected."""
        with pytest.raises(ValueError, match="severity_score must be 0-1"):
            PolicyRule(
                id="test",
                param="x",
                operator=">=",
                value=10,
                message="test",
                severity_score=-0.1
            )

    def test_flood_domain_rule(self):
        """Create flood-specific rule with literature reference."""
        rule = PolicyRule(
            id="flood_insurance_requirement",
            param="has_insurance",
            operator="==",
            value=True,
            message="Flood insurance required in high-risk zone",
            level="WARNING",
            domain="flood",
            param_type="boolean",
            severity_score=0.7,
            literature_ref="FEMA NFIP Guidelines 2022",
            rationale="SFHA properties require flood insurance"
        )
        assert rule.domain == "flood"
        assert rule.param_type == "boolean"


class TestParamTypeEnum:
    """Tests for ParamType enum."""

    def test_all_param_types(self):
        """All expected param types exist."""
        assert ParamType.NUMERIC.value == "numeric"
        assert ParamType.CATEGORICAL.value == "categorical"
        assert ParamType.ORDINAL.value == "ordinal"
        assert ParamType.TEMPORAL.value == "temporal"
        assert ParamType.BOOLEAN.value == "boolean"


class TestDomainEnum:
    """Tests for Domain enum."""

    def test_all_domains(self):
        """All expected domains exist."""
        assert Domain.GENERIC.value == "generic"
        assert Domain.FLOOD.value == "flood"
        assert Domain.FINANCE.value == "finance"
        assert Domain.EDUCATION.value == "education"
        assert Domain.HEALTH.value == "health"
        assert Domain.ENVIRONMENTAL.value == "environmental"
        assert Domain.SOCIAL.value == "social"


class TestSensorConfig:
    """Tests for SensorConfig dataclass."""

    def test_create_numeric_sensor(self):
        """Can create numeric sensor with bins."""
        sensor = SensorConfig(
            domain="flood",
            variable_name="savings_ratio",
            sensor_name="SAVINGS",
            path="agent.finances.savings_to_income",
            data_type="numeric",
            units="%",
            quantization_type="threshold_bins",
            bins=[
                {"label": "CRITICAL", "max": 0.1},
                {"label": "LOW", "max": 0.3},
                {"label": "ADEQUATE", "max": 0.6},
                {"label": "STRONG", "max": 1.0}
            ],
            bin_rationale="US CFPB emergency fund guidelines"
        )
        assert sensor.domain == "flood"
        assert sensor.variable_name == "savings_ratio"
        assert len(sensor.bins) == 4

    def test_quantize_numeric(self):
        """Quantize numeric value to symbolic label."""
        sensor = SensorConfig(
            domain="flood",
            variable_name="savings",
            sensor_name="SAVINGS",
            path="agent.savings",
            data_type="numeric",
            bins=[
                {"label": "LOW", "max": 0.3},
                {"label": "MEDIUM", "max": 0.6},
                {"label": "HIGH", "max": 1.0}
            ]
        )
        assert sensor.quantize(0.1) == "LOW"
        assert sensor.quantize(0.3) == "LOW"  # At boundary
        assert sensor.quantize(0.5) == "MEDIUM"
        assert sensor.quantize(0.9) == "HIGH"

    def test_quantize_categorical(self):
        """Quantize categorical value."""
        sensor = SensorConfig(
            domain="flood",
            variable_name="flood_zone",
            sensor_name="FLOOD_ZONE",
            path="agent.zone",
            data_type="categorical",
            quantization_type="none",
            categories=["A", "AE", "X", "V"]
        )
        assert sensor.quantize("AE") == "AE"
        assert sensor.quantize("Z") == "UNKNOWN"

    def test_quantize_with_scale_factor(self):
        """Scale factor is applied before quantization."""
        sensor = SensorConfig(
            domain="finance",
            variable_name="income",
            sensor_name="INCOME",
            path="agent.income",
            data_type="numeric",
            units="USD",
            scale_factor=0.001,  # Convert to thousands
            bins=[
                {"label": "LOW", "max": 30},  # <30K
                {"label": "MEDIUM", "max": 75},  # 30-75K
                {"label": "HIGH", "max": 150}  # 75-150K
            ]
        )
        assert sensor.quantize(25000) == "LOW"
        assert sensor.quantize(50000) == "MEDIUM"
        assert sensor.quantize(100000) == "HIGH"

    def test_no_quantization(self):
        """No quantization returns string value."""
        sensor = SensorConfig(
            domain="generic",
            variable_name="raw_value",
            sensor_name="RAW",
            path="agent.value",
            quantization_type="none"
        )
        assert sensor.quantize(42) == "42"
        assert sensor.quantize("test") == "test"


class TestResearchTrace:
    """Tests for ResearchTrace dataclass."""

    def test_create_research_trace(self):
        """Can create research trace with all fields."""
        trace = ResearchTrace(
            trace_id="T001",
            valid=True,
            decision="allow",
            domain="flood",
            research_phase="main_study",
            treatment_group="control",
            effect_size=0.45,
            confidence_interval=(0.2, 0.7),
            baseline_surprise=2.3
        )
        assert trace.trace_id == "T001"
        assert trace.domain == "flood"
        assert trace.treatment_group == "control"
        assert trace.effect_size == 0.45

    def test_to_research_dict(self):
        """Export to flat dict for statistical analysis."""
        trace = ResearchTrace(
            trace_id="T002",
            valid=False,
            decision="block",
            blocked_by="min_savings",
            domain="finance",
            research_phase="pilot",
            treatment_group="treatment_A",
            effect_size=0.8,
            confidence_interval=(0.5, 1.1),
        )
        d = trace.to_research_dict()

        assert d["trace_id"] == "T002"
        assert d["valid"] is False
        assert d["decision"] == "block"
        assert d["blocked_by"] == "min_savings"
        assert d["domain"] == "finance"
        assert d["treatment_group"] == "treatment_A"
        assert d["effect_size"] == 0.8
        assert d["ci_lower"] == 0.5
        assert d["ci_upper"] == 1.1

    def test_to_research_dict_with_counterfactual(self):
        """Export includes counterfactual metadata."""
        cf = CounterFactualResult(
            passed=False,
            delta_state={"savings": 200},
            explanation="Need +$200 savings",
            feasibility_score=0.6,
            strategy_used=CounterFactualStrategy.NUMERIC
        )
        trace = ResearchTrace(
            trace_id="T003",
            valid=False,
            decision="block",
            counterfactual=cf
        )
        d = trace.to_research_dict()

        assert d["cf_feasibility"] == 0.6
        assert d["cf_strategy"] == "numeric_delta"

    def test_timestamp_default(self):
        """Timestamp defaults to now."""
        trace = ResearchTrace(trace_id="T004")
        assert isinstance(trace.timestamp, datetime)
        # Should be recent (within last minute)
        delta = datetime.now() - trace.timestamp
        assert delta.total_seconds() < 60


class TestBackwardsCompatibility:
    """Ensure v1 code still works with v2 types."""

    def test_v1_policy_rule_still_works(self):
        """v1-style PolicyRule creation still works."""
        rule = PolicyRule(
            id="test",
            param="x",
            operator=">=",
            value=10,
            message="x must be >= 10",
            level="ERROR"
        )
        assert rule.id == "test"
        assert rule.domain == "generic"  # Default

    def test_all_operators_still_valid(self):
        """All v1 operators still work."""
        for op in RuleOperator:
            rule = PolicyRule(
                id="test",
                param="x",
                operator=op.value,
                value=10,
                message="test"
            )
            assert rule.operator == op.value
