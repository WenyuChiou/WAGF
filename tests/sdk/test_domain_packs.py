"""
Tests for Phase 7 Domain Packs.

Verifies that all domain packs load correctly and contain expected components.
"""

import pytest
from cognitive_governance.domains import list_domains, get_domain_info, AVAILABLE_DOMAINS


class TestDomainModule:
    """Tests for the main domains module."""

    def test_list_domains(self):
        """list_domains returns all 4 domains."""
        domains = list_domains()
        assert len(domains) == 4
        assert "flood" in domains
        assert "finance" in domains
        assert "education" in domains
        assert "health" in domains

    def test_available_domains_constant(self):
        """AVAILABLE_DOMAINS constant is correct."""
        assert AVAILABLE_DOMAINS == ["flood", "finance", "education", "health"]

    def test_get_domain_info_flood(self):
        """get_domain_info returns flood info."""
        info = get_domain_info("flood")
        assert info["name"] == "Flood Risk Adaptation"
        assert "literature" in info

    def test_get_domain_info_unknown(self):
        """get_domain_info handles unknown domains."""
        info = get_domain_info("unknown_domain")
        assert info["name"] == "unknown_domain"


class TestFloodDomainPack:
    """Tests for the flood domain pack."""

    def test_import_sensors(self):
        """Can import flood sensors."""
        from cognitive_governance.domains.flood import FLOOD_SENSORS, FLOOD_SENSOR_CONFIGS

        assert len(FLOOD_SENSORS) == 8
        assert "FLOOD_LEVEL" in FLOOD_SENSORS
        assert "RISK_PERCEPTION" in FLOOD_SENSORS
        assert "ADAPTATION_STATUS" in FLOOD_SENSORS

        assert "FLOOD_LEVEL" in FLOOD_SENSOR_CONFIGS
        assert FLOOD_SENSOR_CONFIGS["FLOOD_LEVEL"].domain == "flood"

    def test_import_rules(self):
        """Can import flood rules."""
        from cognitive_governance.domains.flood import FLOOD_RULES, create_flood_policy

        assert len(FLOOD_RULES) == 8
        # Check rule structure
        rule_ids = [r.id for r in FLOOD_RULES]
        assert "insurance_affordability" in rule_ids
        assert "elevation_affordability" in rule_ids

    def test_create_flood_policy(self):
        """create_flood_policy returns valid policy dict."""
        from cognitive_governance.domains.flood import create_flood_policy

        policy = create_flood_policy()
        assert policy["domain"] == "flood"
        assert "rules" in policy
        assert len(policy["rules"]) > 0

    def test_create_flood_policy_selective(self):
        """create_flood_policy respects include flags."""
        from cognitive_governance.domains.flood import create_flood_policy

        policy = create_flood_policy(include_elevation=False, include_relocation=False)
        rule_ids = [r["id"] for r in policy["rules"]]
        assert "elevation_affordability" not in rule_ids
        assert "relocation_affordability" not in rule_ids

    def test_import_observers(self):
        """Can import flood observers."""
        from cognitive_governance.domains.flood import FloodObserver, FloodEnvironmentObserver

        obs = FloodObserver()
        assert obs.domain == "flood"

        env_obs = FloodEnvironmentObserver()
        assert env_obs.domain == "flood"

    def test_import_feasibility(self):
        """Can import flood feasibility matrix."""
        from cognitive_governance.domains.flood import FLOOD_FEASIBILITY, FLOOD_RATIONALES

        assert ("unprotected", "insured") in FLOOD_FEASIBILITY
        assert FLOOD_FEASIBILITY[("unprotected", "insured")] == 0.6


class TestFinanceDomainPack:
    """Tests for the finance domain pack."""

    def test_import_sensors(self):
        """Can import finance sensors."""
        from cognitive_governance.domains.finance import FINANCE_SENSORS, FINANCE_SENSOR_CONFIGS

        assert len(FINANCE_SENSORS) == 8
        assert "SAVINGS_RATIO" in FINANCE_SENSORS
        assert "DEBT_RATIO" in FINANCE_SENSORS
        assert "CREDIT_SCORE" in FINANCE_SENSORS

    def test_import_rules(self):
        """Can import finance rules."""
        from cognitive_governance.domains.finance import FINANCE_RULES, create_finance_policy

        assert len(FINANCE_RULES) == 8
        rule_ids = [r.id for r in FINANCE_RULES]
        assert "emergency_fund" in rule_ids
        assert "debt_ratio_limit" in rule_ids

    def test_create_finance_policy(self):
        """create_finance_policy returns valid policy dict."""
        from cognitive_governance.domains.finance import create_finance_policy

        policy = create_finance_policy()
        assert policy["domain"] == "finance"
        assert len(policy["rules"]) > 0

    def test_import_observers(self):
        """Can import finance observers."""
        from cognitive_governance.domains.finance import FinanceObserver, FinanceEnvironmentObserver

        obs = FinanceObserver()
        assert obs.domain == "finance"

        env_obs = FinanceEnvironmentObserver()
        assert env_obs.domain == "finance"

    def test_import_feasibility(self):
        """Can import finance feasibility matrix."""
        from cognitive_governance.domains.finance import FINANCE_FEASIBILITY

        assert ("critical", "low") in FINANCE_FEASIBILITY
        assert FINANCE_FEASIBILITY[("critical", "low")] == 0.5


class TestEducationDomainPack:
    """Tests for the education domain pack."""

    def test_import_sensors(self):
        """Can import education sensors."""
        from cognitive_governance.domains.education import EDUCATION_SENSORS, EDUCATION_SENSOR_CONFIGS

        assert len(EDUCATION_SENSORS) == 8
        assert "DEGREE_LEVEL" in EDUCATION_SENSORS
        assert "GPA" in EDUCATION_SENSORS
        assert "MOTIVATION" in EDUCATION_SENSORS

    def test_import_rules(self):
        """Can import education rules."""
        from cognitive_governance.domains.education import EDUCATION_RULES, create_education_policy

        assert len(EDUCATION_RULES) == 7
        rule_ids = [r.id for r in EDUCATION_RULES]
        assert "gpa_for_graduation" in rule_ids

    def test_create_education_policy(self):
        """create_education_policy returns valid policy dict."""
        from cognitive_governance.domains.education import create_education_policy

        policy = create_education_policy()
        assert policy["domain"] == "education"
        assert len(policy["rules"]) > 0

    def test_import_observers(self):
        """Can import education observers."""
        from cognitive_governance.domains.education import EducationObserver, EducationEnvironmentObserver

        obs = EducationObserver()
        assert obs.domain == "education"

        env_obs = EducationEnvironmentObserver()
        assert env_obs.domain == "education"

    def test_import_feasibility(self):
        """Can import education feasibility matrix."""
        from cognitive_governance.domains.education import EDUCATION_FEASIBILITY

        assert ("high_school", "associate") in EDUCATION_FEASIBILITY
        assert EDUCATION_FEASIBILITY[("high_school", "associate")] == 0.6


class TestHealthDomainPack:
    """Tests for the health domain pack."""

    def test_import_sensors(self):
        """Can import health sensors."""
        from cognitive_governance.domains.health import HEALTH_SENSORS, HEALTH_SENSOR_CONFIGS

        assert len(HEALTH_SENSORS) == 9
        assert "ACTIVITY_LEVEL" in HEALTH_SENSORS
        assert "DIET_QUALITY" in HEALTH_SENSORS
        assert "SMOKING_STATUS" in HEALTH_SENSORS
        assert "BMI" in HEALTH_SENSORS

    def test_import_rules(self):
        """Can import health rules."""
        from cognitive_governance.domains.health import HEALTH_RULES, create_health_policy

        assert len(HEALTH_RULES) == 7
        rule_ids = [r.id for r in HEALTH_RULES]
        assert "self_efficacy_for_change" in rule_ids

    def test_create_health_policy(self):
        """create_health_policy returns valid policy dict."""
        from cognitive_governance.domains.health import create_health_policy

        policy = create_health_policy()
        assert policy["domain"] == "health"
        assert len(policy["rules"]) > 0

    def test_import_observers(self):
        """Can import health observers."""
        from cognitive_governance.domains.health import HealthObserver, HealthEnvironmentObserver

        obs = HealthObserver()
        assert obs.domain == "health"

        env_obs = HealthEnvironmentObserver()
        assert env_obs.domain == "health"

    def test_import_feasibility(self):
        """Can import health feasibility matrix."""
        from cognitive_governance.domains.health import HEALTH_FEASIBILITY

        assert ("sedentary", "light_active") in HEALTH_FEASIBILITY
        assert HEALTH_FEASIBILITY[("sedentary", "light_active")] == 0.5


class TestSensorConfigStructure:
    """Tests for SensorConfig structure across domains."""

    def test_sensor_has_required_fields(self):
        """All sensors have required fields."""
        from cognitive_governance.domains.flood import FLOOD_SENSOR_CONFIGS
        from cognitive_governance.domains.finance import FINANCE_SENSOR_CONFIGS

        for name, config in FLOOD_SENSOR_CONFIGS.items():
            assert config.domain == "flood"
            assert config.variable_name is not None
            assert config.sensor_name is not None
            assert config.data_type in ["numeric", "categorical"]

        for name, config in FINANCE_SENSOR_CONFIGS.items():
            assert config.domain == "finance"

    def test_numeric_sensors_have_bins(self):
        """Numeric sensors have quantization bins."""
        from cognitive_governance.domains.flood import FLOOD_SENSOR_CONFIGS

        flood_level = FLOOD_SENSOR_CONFIGS["FLOOD_LEVEL"]
        assert flood_level.data_type == "numeric"
        assert flood_level.bins is not None
        assert len(flood_level.bins) > 0

    def test_categorical_sensors_have_categories(self):
        """Categorical sensors have categories."""
        from cognitive_governance.domains.flood import FLOOD_SENSOR_CONFIGS

        adaptation = FLOOD_SENSOR_CONFIGS["ADAPTATION_STATUS"]
        assert adaptation.data_type == "categorical"
        assert adaptation.categories is not None
        assert "unprotected" in adaptation.categories


class TestRuleStructure:
    """Tests for PolicyRule structure across domains."""

    def test_rule_has_required_fields(self):
        """All rules have required fields."""
        from cognitive_governance.domains.flood import FLOOD_RULES
        from cognitive_governance.domains.finance import FINANCE_RULES

        for rule in FLOOD_RULES:
            assert rule.id is not None
            assert rule.param is not None
            assert rule.operator is not None
            assert rule.message is not None
            assert rule.level in ["ERROR", "WARNING"]
            assert rule.domain == "flood"

        for rule in FINANCE_RULES:
            assert rule.domain == "finance"

    def test_rule_has_literature_ref(self):
        """Rules have literature references for traceability."""
        from cognitive_governance.domains.flood import FLOOD_RULES

        for rule in FLOOD_RULES:
            assert rule.literature_ref is not None, f"Rule {rule.id} missing literature_ref"

    def test_rule_has_rationale(self):
        """Rules have rationale for explainability."""
        from cognitive_governance.domains.flood import FLOOD_RULES

        for rule in FLOOD_RULES:
            assert rule.rationale is not None, f"Rule {rule.id} missing rationale"


class TestObserverUtilities:
    """Tests for domain observer utility functions."""

    def test_flood_create_observers(self):
        """create_flood_observers returns both observers."""
        from cognitive_governance.domains.flood.observer import create_flood_observers

        observers = create_flood_observers()
        assert "social" in observers
        assert "environment" in observers
        assert observers["social"].domain == "flood"
        assert observers["environment"].domain == "flood"

    def test_flood_observable_attributes(self):
        """get_observable_flood_attributes returns list."""
        from cognitive_governance.domains.flood.observer import get_observable_flood_attributes

        attrs = get_observable_flood_attributes()
        assert "elevated" in attrs
        assert "has_flood_insurance" in attrs

    def test_flood_events(self):
        """get_flood_events returns list."""
        from cognitive_governance.domains.flood.observer import get_flood_events

        events = get_flood_events()
        assert "flood_active" in events
        assert "evacuation_order" in events


class TestCrossDomainConsistency:
    """Tests for consistency across domain packs."""

    def test_all_domains_have_same_structure(self):
        """All domain packs export the same types of components."""
        from cognitive_governance.domains import flood, finance, education, health

        for domain_module in [flood, finance, education, health]:
            # Check sensors exist
            assert hasattr(domain_module, f"{domain_module.__name__.split('.')[-1].upper()}_SENSORS") or \
                   any(attr.endswith("_SENSORS") for attr in dir(domain_module))

            # Check rules exist
            assert hasattr(domain_module, f"{domain_module.__name__.split('.')[-1].upper()}_RULES") or \
                   any(attr.endswith("_RULES") for attr in dir(domain_module))

    def test_all_observers_have_domain_property(self):
        """All observers have a domain property."""
        from cognitive_governance.v1_prototype.social import (
            FloodObserver, FinanceObserver, EducationObserver, HealthObserver
        )
        from cognitive_governance.v1_prototype.observation import (
            FloodEnvironmentObserver, FinanceEnvironmentObserver,
            EducationEnvironmentObserver, HealthEnvironmentObserver
        )

        social_observers = [FloodObserver(), FinanceObserver(), EducationObserver(), HealthObserver()]
        env_observers = [
            FloodEnvironmentObserver(), FinanceEnvironmentObserver(),
            EducationEnvironmentObserver(), HealthEnvironmentObserver()
        ]

        expected_domains = ["flood", "finance", "education", "health"]

        for obs, domain in zip(social_observers, expected_domains):
            assert obs.domain == domain

        for obs, domain in zip(env_observers, expected_domains):
            assert obs.domain == domain
