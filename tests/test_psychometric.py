"""
Tests for Psychometric Framework (Task-040: SA/MA Unified Architecture Part 14.5).

Tests the PsychologicalFramework implementations:
- PMTFramework: PMT construct validation and coherence
- UtilityFramework: Government decision validation
- FinancialFramework: Insurance decision validation
- Factory functions: get_framework, register_framework
"""
import pytest

from broker.core.psychometric import (
    ConstructDef,
    ValidationResult,
    PsychologicalFramework,
    PMTFramework,
    UtilityFramework,
    FinancialFramework,
    get_framework,
    register_framework,
    list_frameworks,
)


class TestConstructDef:
    """Test ConstructDef dataclass."""

    def test_create_basic_construct(self):
        """Test basic construct creation."""
        construct = ConstructDef(
            name="Threat Perception",
            values=["VL", "L", "M", "H", "VH"],
            required=True,
            description="Perceived threat level"
        )
        assert construct.name == "Threat Perception"
        assert len(construct.values) == 5
        assert construct.required is True

    def test_validate_value_valid(self):
        """Test validation with valid values."""
        construct = ConstructDef(
            name="Test",
            values=["A", "B", "C"]
        )
        assert construct.validate_value("A") is True
        assert construct.validate_value("B") is True
        assert construct.validate_value("C") is True

    def test_validate_value_case_insensitive(self):
        """Test validation is case insensitive."""
        construct = ConstructDef(
            name="Test",
            values=["HIGH", "LOW"]
        )
        assert construct.validate_value("high") is True
        assert construct.validate_value("HIGH") is True
        assert construct.validate_value("High") is True

    def test_validate_value_invalid(self):
        """Test validation with invalid value."""
        construct = ConstructDef(
            name="Test",
            values=["A", "B"]
        )
        assert construct.validate_value("C") is False
        assert construct.validate_value("invalid") is False

    def test_validate_value_no_constraint(self):
        """Test validation with no value constraints."""
        construct = ConstructDef(name="Test")
        assert construct.validate_value("anything") is True
        assert construct.validate_value(123) is True


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_create_valid_result(self):
        """Test creating a valid result."""
        result = ValidationResult(valid=True)
        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_create_invalid_result(self):
        """Test creating an invalid result with errors."""
        result = ValidationResult(
            valid=False,
            errors=["Error 1", "Error 2"],
            rule_violations=["rule1"]
        )
        assert result.valid is False
        assert len(result.errors) == 2
        assert "rule1" in result.rule_violations

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = ValidationResult(
            valid=True,
            warnings=["Warning 1"],
            metadata={"key": "value"}
        )
        data = result.to_dict()
        assert data["valid"] is True
        assert "Warning 1" in data["warnings"]
        assert data["metadata"]["key"] == "value"


class TestPMTFramework:
    """Test PMTFramework implementation."""

    @pytest.fixture
    def pmt(self):
        """Create PMT framework instance."""
        return PMTFramework()

    def test_name(self, pmt):
        """Test framework name."""
        assert "PMT" in pmt.name or "Protection" in pmt.name

    def test_get_constructs(self, pmt):
        """Test PMT construct definitions."""
        constructs = pmt.get_constructs()

        assert "TP_LABEL" in constructs
        assert "CP_LABEL" in constructs
        assert "SP_LABEL" in constructs

        tp = constructs["TP_LABEL"]
        assert tp.name == "Threat Perception"
        assert tp.values == ["VL", "L", "M", "H", "VH"]
        assert tp.required is True

        cp = constructs["CP_LABEL"]
        assert cp.required is True

        sp = constructs["SP_LABEL"]
        assert sp.required is False

    def test_get_construct_keys(self, pmt):
        """Test getting construct keys."""
        keys = pmt.get_construct_keys()
        assert "TP_LABEL" in keys
        assert "CP_LABEL" in keys

    def test_get_required_construct_keys(self, pmt):
        """Test getting required construct keys."""
        required = pmt.get_required_construct_keys()
        assert "TP_LABEL" in required
        assert "CP_LABEL" in required
        assert "SP_LABEL" not in required

    def test_validate_required_constructs_present(self, pmt):
        """Test validation with all required constructs present."""
        appraisals = {"TP_LABEL": "H", "CP_LABEL": "M"}
        result = pmt.validate_required_constructs(appraisals)
        assert result.valid is True

    def test_validate_required_constructs_missing(self, pmt):
        """Test validation with missing required constructs."""
        appraisals = {"TP_LABEL": "H"}  # Missing CP_LABEL
        result = pmt.validate_required_constructs(appraisals)
        assert result.valid is False
        assert "CP_LABEL" in str(result.errors)

    def test_validate_construct_values_valid(self, pmt):
        """Test validation with valid construct values."""
        appraisals = {"TP_LABEL": "H", "CP_LABEL": "VH"}
        result = pmt.validate_construct_values(appraisals)
        assert result.valid is True

    def test_validate_construct_values_invalid(self, pmt):
        """Test validation with invalid construct values."""
        appraisals = {"TP_LABEL": "INVALID", "CP_LABEL": "H"}
        result = pmt.validate_construct_values(appraisals)
        assert result.valid is False
        assert "INVALID" in str(result.errors)

    def test_validate_coherence_valid(self, pmt):
        """Test coherence validation with valid appraisals."""
        appraisals = {"TP_LABEL": "H", "CP_LABEL": "H"}
        result = pmt.validate_coherence(appraisals)
        assert result.valid is True

    def test_validate_coherence_with_warnings(self, pmt):
        """Test coherence validation generates warnings for high TP+CP."""
        appraisals = {"TP_LABEL": "VH", "CP_LABEL": "VH"}
        result = pmt.validate_coherence(appraisals)
        assert result.valid is True
        assert len(result.warnings) > 0

    def test_validate_action_coherence_high_tp_cp_do_nothing(self, pmt):
        """Test that High TP + High CP blocks do_nothing."""
        appraisals = {"TP_LABEL": "H", "CP_LABEL": "H"}
        result = pmt.validate_action_coherence(appraisals, "do_nothing")
        assert result.valid is False
        assert "high_tp_high_cp_should_act" in result.rule_violations

    def test_validate_action_coherence_vh_threat_do_nothing(self, pmt):
        """Test that VH TP blocks do_nothing."""
        appraisals = {"TP_LABEL": "VH", "CP_LABEL": "M"}
        result = pmt.validate_action_coherence(appraisals, "do_nothing")
        assert result.valid is False
        assert "extreme_threat_requires_action" in result.rule_violations

    def test_validate_action_coherence_low_tp_extreme_action(self, pmt):
        """Test that Low TP blocks extreme actions."""
        appraisals = {"TP_LABEL": "L", "CP_LABEL": "H"}
        result = pmt.validate_action_coherence(appraisals, "relocate")
        assert result.valid is False
        assert "low_tp_blocks_extreme_action" in result.rule_violations

    def test_validate_action_coherence_low_tp_elevate(self, pmt):
        """Test that Low TP blocks elevate_house."""
        appraisals = {"TP_LABEL": "VL", "CP_LABEL": "H"}
        result = pmt.validate_action_coherence(appraisals, "elevate_house")
        assert result.valid is False

    def test_validate_action_coherence_valid_action(self, pmt):
        """Test valid action with matching appraisals."""
        appraisals = {"TP_LABEL": "H", "CP_LABEL": "H"}
        result = pmt.validate_action_coherence(appraisals, "elevate_house")
        assert result.valid is True

    def test_validate_action_coherence_low_cp_warning(self, pmt):
        """Test that Very Low CP generates warning for complex actions."""
        appraisals = {"TP_LABEL": "H", "CP_LABEL": "VL"}
        result = pmt.validate_action_coherence(appraisals, "elevate_house")
        assert len(result.warnings) > 0

    def test_get_expected_behavior_high_threat_high_coping(self, pmt):
        """Test expected behavior for high threat + high coping."""
        appraisals = {"TP_LABEL": "H", "CP_LABEL": "H"}
        expected = pmt.get_expected_behavior(appraisals)
        assert "elevate_house" in expected
        assert "buy_insurance" in expected
        assert "do_nothing" not in expected

    def test_get_expected_behavior_low_threat(self, pmt):
        """Test expected behavior for low threat."""
        appraisals = {"TP_LABEL": "L", "CP_LABEL": "M"}
        expected = pmt.get_expected_behavior(appraisals)
        assert "do_nothing" in expected
        assert "elevate_house" not in expected

    def test_get_blocked_skills_high_tp_cp(self, pmt):
        """Test blocked skills for high TP + CP."""
        appraisals = {"TP_LABEL": "H", "CP_LABEL": "H"}
        blocked = pmt.get_blocked_skills(appraisals)
        assert "do_nothing" in blocked

    def test_get_blocked_skills_low_tp(self, pmt):
        """Test blocked skills for low TP."""
        appraisals = {"TP_LABEL": "L", "CP_LABEL": "H"}
        blocked = pmt.get_blocked_skills(appraisals)
        assert "relocate" in blocked
        assert "elevate_house" in blocked

    def test_normalize_label(self, pmt):
        """Test label normalization."""
        assert pmt._normalize_label("high") == "H"
        assert pmt._normalize_label("VERY HIGH") == "VH"
        assert pmt._normalize_label("very_low") == "VL"
        assert pmt._normalize_label("M") == "M"
        assert pmt._normalize_label(None) == "M"

    def test_compare_labels(self, pmt):
        """Test label comparison."""
        assert pmt.compare_labels("L", "H") == -1
        assert pmt.compare_labels("H", "L") == 1
        assert pmt.compare_labels("M", "M") == 0
        assert pmt.compare_labels("VL", "VH") == -1


class TestUtilityFramework:
    """Test UtilityFramework implementation."""

    @pytest.fixture
    def utility(self):
        """Create Utility framework instance."""
        return UtilityFramework()

    def test_name(self, utility):
        """Test framework name."""
        assert "Utility" in utility.name

    def test_get_constructs(self, utility):
        """Test Utility construct definitions."""
        constructs = utility.get_constructs()

        assert "BUDGET_UTIL" in constructs
        assert "EQUITY_GAP" in constructs
        assert "ADOPTION_RATE" in constructs

        budget = constructs["BUDGET_UTIL"]
        assert budget.values == ["DEFICIT", "NEUTRAL", "SURPLUS"]
        assert budget.required is True

        equity = constructs["EQUITY_GAP"]
        assert equity.values == ["HIGH", "MEDIUM", "LOW"]

        adoption = constructs["ADOPTION_RATE"]
        assert adoption.required is False

    def test_validate_coherence_valid(self, utility):
        """Test coherence validation with valid appraisals."""
        appraisals = {
            "BUDGET_UTIL": "NEUTRAL",
            "EQUITY_GAP": "MEDIUM"
        }
        result = utility.validate_coherence(appraisals)
        assert result.valid is True

    def test_validate_coherence_warning(self, utility):
        """Test coherence validation generates warning for deficit + high gap."""
        appraisals = {
            "BUDGET_UTIL": "DEFICIT",
            "EQUITY_GAP": "HIGH"
        }
        result = utility.validate_coherence(appraisals)
        assert result.valid is True
        assert len(result.warnings) > 0

    def test_get_expected_behavior_high_equity_gap(self, utility):
        """Test expected behavior for high equity gap."""
        appraisals = {
            "BUDGET_UTIL": "NEUTRAL",
            "EQUITY_GAP": "HIGH"
        }
        expected = utility.get_expected_behavior(appraisals)
        assert "increase_subsidy" in expected or "targeted_assistance" in expected

    def test_get_expected_behavior_surplus(self, utility):
        """Test expected behavior for budget surplus."""
        appraisals = {
            "BUDGET_UTIL": "SURPLUS",
            "EQUITY_GAP": "LOW"
        }
        expected = utility.get_expected_behavior(appraisals)
        assert "increase_subsidy" in expected or "expand_program" in expected

    def test_get_expected_behavior_deficit(self, utility):
        """Test expected behavior for budget deficit."""
        appraisals = {
            "BUDGET_UTIL": "DEFICIT",
            "EQUITY_GAP": "LOW"
        }
        expected = utility.get_expected_behavior(appraisals)
        assert "reduce_subsidy" in expected or "cost_optimization" in expected


class TestFinancialFramework:
    """Test FinancialFramework implementation."""

    @pytest.fixture
    def financial(self):
        """Create Financial framework instance."""
        return FinancialFramework()

    def test_name(self, financial):
        """Test framework name."""
        assert "Financial" in financial.name

    def test_get_constructs(self, financial):
        """Test Financial construct definitions."""
        constructs = financial.get_constructs()

        assert "LOSS_RATIO" in constructs
        assert "SOLVENCY" in constructs
        assert "MARKET_SHARE" in constructs

        loss = constructs["LOSS_RATIO"]
        assert loss.values == ["HIGH", "MEDIUM", "LOW"]
        assert loss.required is True

        solvency = constructs["SOLVENCY"]
        assert "AT_RISK" in solvency.values
        assert "STABLE" in solvency.values
        assert "STRONG" in solvency.values

        market = constructs["MARKET_SHARE"]
        assert market.required is False

    def test_validate_coherence_valid(self, financial):
        """Test coherence validation with valid appraisals."""
        appraisals = {
            "LOSS_RATIO": "MEDIUM",
            "SOLVENCY": "STABLE"
        }
        result = financial.validate_coherence(appraisals)
        assert result.valid is True

    def test_validate_coherence_high_loss_strong_solvency(self, financial):
        """Test coherence generates warning for high loss + strong solvency."""
        appraisals = {
            "LOSS_RATIO": "HIGH",
            "SOLVENCY": "STRONG"
        }
        result = financial.validate_coherence(appraisals)
        assert result.valid is True
        assert len(result.warnings) > 0

    def test_validate_coherence_at_risk_solvency(self, financial):
        """Test coherence generates warning for at-risk solvency."""
        appraisals = {
            "LOSS_RATIO": "MEDIUM",
            "SOLVENCY": "AT_RISK"
        }
        result = financial.validate_coherence(appraisals)
        assert result.valid is True
        assert any("conservative" in w.lower() for w in result.warnings)

    def test_get_expected_behavior_at_risk(self, financial):
        """Test expected behavior for at-risk solvency."""
        appraisals = {
            "LOSS_RATIO": "MEDIUM",
            "SOLVENCY": "AT_RISK"
        }
        expected = financial.get_expected_behavior(appraisals)
        assert "raise_premium" in expected or "limit_coverage" in expected

    def test_get_expected_behavior_high_loss(self, financial):
        """Test expected behavior for high loss ratio."""
        appraisals = {
            "LOSS_RATIO": "HIGH",
            "SOLVENCY": "STABLE"
        }
        expected = financial.get_expected_behavior(appraisals)
        assert "raise_premium" in expected or "adjust_coverage" in expected

    def test_get_expected_behavior_strong_position(self, financial):
        """Test expected behavior for strong position."""
        appraisals = {
            "LOSS_RATIO": "LOW",
            "SOLVENCY": "STRONG"
        }
        expected = financial.get_expected_behavior(appraisals)
        assert "expand_coverage" in expected or "competitive_pricing" in expected


class TestFrameworkFactory:
    """Test framework factory functions."""

    def test_get_framework_pmt(self):
        """Test getting PMT framework."""
        framework = get_framework("pmt")
        assert isinstance(framework, PMTFramework)

    def test_get_framework_utility(self):
        """Test getting Utility framework."""
        framework = get_framework("utility")
        assert isinstance(framework, UtilityFramework)

    def test_get_framework_financial(self):
        """Test getting Financial framework."""
        framework = get_framework("financial")
        assert isinstance(framework, FinancialFramework)

    def test_get_framework_case_insensitive(self):
        """Test framework lookup is case insensitive."""
        pmt1 = get_framework("PMT")
        pmt2 = get_framework("pmt")
        pmt3 = get_framework("Pmt")
        assert all(isinstance(f, PMTFramework) for f in [pmt1, pmt2, pmt3])

    def test_get_framework_unknown_raises(self):
        """Test that unknown framework raises ValueError."""
        with pytest.raises(ValueError, match="Unknown framework"):
            get_framework("unknown")

    def test_list_frameworks(self):
        """Test listing available frameworks."""
        frameworks = list_frameworks()
        assert "pmt" in frameworks
        assert "utility" in frameworks
        assert "financial" in frameworks

    def test_register_framework(self):
        """Test registering a custom framework."""
        class CustomFramework(PsychologicalFramework):
            @property
            def name(self):
                return "Custom"

            def get_constructs(self):
                return {}

            def validate_coherence(self, appraisals):
                return ValidationResult(valid=True)

            def get_expected_behavior(self, appraisals):
                return []

        register_framework("custom", CustomFramework)
        framework = get_framework("custom")
        assert framework.name == "Custom"

    def test_register_framework_invalid_type(self):
        """Test that registering non-framework raises TypeError."""
        class NotAFramework:
            pass

        with pytest.raises(TypeError):
            register_framework("invalid", NotAFramework)


class TestIntegrationWithAgentTypeRegistry:
    """Test integration with AgentTypeRegistry."""

    def test_framework_from_registry(self):
        """Test getting framework via registry integration."""
        from broker.config.agent_types import (
            get_default_registry,
            PsychologicalFramework as PFEnum,
        )

        registry = get_default_registry()
        defn = registry.get("household")

        # Get the framework enum value
        assert defn.psychological_framework == PFEnum.PMT

        # Use factory to get framework instance
        framework = get_framework(defn.psychological_framework.value)
        assert isinstance(framework, PMTFramework)

    def test_constructs_alignment(self):
        """Test that PMT constructs align between framework and registry defaults."""
        from broker.config.agent_types import DEFAULT_PMT_CONSTRUCTS

        pmt = PMTFramework()
        framework_constructs = pmt.get_constructs()

        # Verify key constructs match
        assert "TP_LABEL" in framework_constructs
        assert "CP_LABEL" in framework_constructs
        assert framework_constructs["TP_LABEL"].values == DEFAULT_PMT_CONSTRUCTS["TP_LABEL"].values
