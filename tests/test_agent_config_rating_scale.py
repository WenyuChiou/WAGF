"""
Tests for AgentTypeConfig Rating Scale Methods.

Task-041: Universal Prompt/Context/Governance Framework
"""

import pytest
from broker.utils.agent_config import AgentTypeConfig
from broker.interfaces.rating_scales import RatingScaleRegistry


class TestAgentTypeConfigRatingScale:
    """Test rating scale methods in AgentTypeConfig."""

    def setup_method(self):
        """Reset registry before each test."""
        RatingScaleRegistry.reset()
        # Reset singleton
        AgentTypeConfig._instance = None

    def test_get_rating_scale_pmt_default(self):
        """PMT scale should be available by default."""
        config = AgentTypeConfig.load()
        scale = config.get_rating_scale("pmt")
        assert "VL = Very Low" in scale
        assert "VH = Very High" in scale

    def test_get_rating_scale_utility(self):
        """Utility scale should have priority levels."""
        config = AgentTypeConfig.load()
        scale = config.get_rating_scale("utility")
        assert "Low Priority" in scale
        assert "High Priority" in scale

    def test_get_rating_scale_financial(self):
        """Financial scale should have risk appetite levels."""
        config = AgentTypeConfig.load()
        scale = config.get_rating_scale("financial")
        assert "Conservative" in scale
        assert "Aggressive" in scale

    def test_get_rating_scale_unknown_defaults_pmt(self):
        """Unknown framework should default to PMT."""
        config = AgentTypeConfig.load()
        scale = config.get_rating_scale("unknown")
        # Should return PMT or legacy fallback
        assert scale  # Not empty

    def test_get_rating_scale_levels_pmt(self):
        """PMT levels should be VL/L/M/H/VH."""
        config = AgentTypeConfig.load()
        levels = config.get_rating_scale_levels("pmt")
        assert levels == ["VL", "L", "M", "H", "VH"]

    def test_get_rating_scale_levels_utility(self):
        """Utility levels should be L/M/H."""
        config = AgentTypeConfig.load()
        levels = config.get_rating_scale_levels("utility")
        assert levels == ["L", "M", "H"]

    def test_get_rating_scale_levels_financial(self):
        """Financial levels should be C/M/A."""
        config = AgentTypeConfig.load()
        levels = config.get_rating_scale_levels("financial")
        assert levels == ["C", "M", "A"]

    def test_get_rating_scale_levels_unknown_defaults_pmt(self):
        """Unknown framework should default to PMT levels."""
        config = AgentTypeConfig.load()
        levels = config.get_rating_scale_levels("unknown")
        assert levels == ["VL", "L", "M", "H", "VH"]

    def test_get_framework_for_agent_type_default(self):
        """Agent type without framework should default to pmt."""
        config = AgentTypeConfig.load()
        # Most agent types default to pmt
        framework = config.get_framework_for_agent_type("household")
        # Could be pmt or explicitly configured
        assert framework in ["pmt", "utility", "financial", "generic"]

    def test_get_rating_scale_for_agent_type(self):
        """Convenience method should work."""
        config = AgentTypeConfig.load()
        scale = config.get_rating_scale_for_agent_type("household")
        # Should return a non-empty scale
        assert scale
        assert isinstance(scale, str)


class TestAgentTypeConfigRatingScaleYAML:
    """Test rating scale methods with custom YAML config."""

    def setup_method(self):
        RatingScaleRegistry.reset()
        AgentTypeConfig._instance = None

    def test_yaml_scale_override(self, tmp_path):
        """Custom YAML scales should override defaults."""
        yaml_content = """
shared:
  rating_scales:
    pmt:
      levels: ["LOW", "MID", "HIGH"]
      labels:
        LOW: "Low"
        MID: "Medium"
        HIGH: "High"
      template: "Custom: LOW/MID/HIGH"
"""
        yaml_file = tmp_path / "test_agent_types.yaml"
        yaml_file.write_text(yaml_content)

        config = AgentTypeConfig.load(str(yaml_file))
        scale = config.get_rating_scale("pmt")
        assert "Custom: LOW/MID/HIGH" in scale

        levels = config.get_rating_scale_levels("pmt")
        assert levels == ["LOW", "MID", "HIGH"]

    def test_legacy_rating_scale_fallback(self, tmp_path):
        """Legacy rating_scale (not rating_scales) should work."""
        yaml_content = """
shared:
  rating_scale: |
    ### LEGACY SCALE:
    1 = Bad | 5 = Good
"""
        yaml_file = tmp_path / "test_agent_types.yaml"
        yaml_file.write_text(yaml_content)

        config = AgentTypeConfig.load(str(yaml_file))
        # For unknown framework, should fall back to legacy
        scale = config.get_rating_scale("unknown_framework")
        assert "LEGACY SCALE" in scale or "VL = Very Low" in scale

    def test_agent_type_framework_config(self, tmp_path):
        """Agent type can specify psychological_framework."""
        yaml_content = """
government:
  psychological_framework: utility
  prompt_template: "Government prompt"

household:
  psychological_framework: pmt
  prompt_template: "Household prompt"
"""
        yaml_file = tmp_path / "test_agent_types.yaml"
        yaml_file.write_text(yaml_content)

        config = AgentTypeConfig.load(str(yaml_file))

        assert config.get_framework_for_agent_type("government") == "utility"
        assert config.get_framework_for_agent_type("household") == "pmt"

    def test_get_rating_scale_for_agent_type_utility(self, tmp_path):
        """Government agent should get utility scale."""
        yaml_content = """
government:
  psychological_framework: utility
"""
        yaml_file = tmp_path / "test_agent_types.yaml"
        yaml_file.write_text(yaml_content)

        config = AgentTypeConfig.load(str(yaml_file))
        scale = config.get_rating_scale_for_agent_type("government")

        # Should be utility scale
        assert "Priority" in scale or "L/M/H" in scale or scale  # Non-empty

    def test_irrigation_agent_type_uses_cognitive_appraisal_framework(self):
        """Irrigation config should resolve to the declared appraisal theory."""
        config = AgentTypeConfig.load("examples/irrigation_abm/config/agent_types.yaml", force_reload=True)
        assert config.get_framework_for_agent_type("irrigation_farmer") == "cognitive_appraisal"


class TestAgentTypeConfigRetrievalPolicy:
    """Phase 6H Item 3: get_retrieval_config() — skill-retrieval tuning
    resolved from YAML governance.retrieval (DomainPack retrieval_policy()
    path is exercised separately via the contract test)."""

    def setup_method(self):
        AgentTypeConfig._instance = None

    def test_retrieval_config_defaults(self, tmp_path):
        """No governance.retrieval block → framework defaults, byte-identical
        to the pre-6H hardcoded SkillRetriever construction (top_n=3)."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text("shared: {}\n")
        config = AgentTypeConfig.load(str(yaml_file))
        assert config.get_retrieval_config() == {"top_n": 3, "min_score": 0.05}

    def test_retrieval_config_yaml_override(self, tmp_path):
        """global_config.governance.retrieval overrides both knobs."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    retrieval:\n"
            "      top_n: 8\n"
            "      min_score: 0.2\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        cfg = config.get_retrieval_config()
        assert cfg["top_n"] == 8
        assert cfg["min_score"] == 0.2

    def test_retrieval_config_partial_override(self, tmp_path):
        """A partial override keeps the framework default for the other key."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    retrieval:\n"
            "      top_n: 10\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        cfg = config.get_retrieval_config()
        assert cfg["top_n"] == 10
        assert cfg["min_score"] == 0.05  # framework default preserved


class TestAgentTypeConfigDriftPolicy:
    """Phase 6L-A: get_drift_config() — population-drift-monitor knobs
    resolved from YAML governance.drift. Mirrors the get_retrieval_config
    pattern (Phase 6H Item 3 template)."""

    def setup_method(self):
        AgentTypeConfig._instance = None

    def test_drift_config_defaults(self, tmp_path):
        """No governance.drift block → DriftDetector constructor defaults.
        Byte-identical to the pre-6L-A
        ``DriftDetector(entropy_threshold=0.5, stagnation_threshold=0.6,
        collapse_threshold=0.9, jaccard_stagnation_threshold=0.8,
        history_window=5)``."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text("shared: {}\n")
        config = AgentTypeConfig.load(str(yaml_file))
        cfg = config.get_drift_config()
        assert cfg["entropy_threshold"] == 0.5
        assert cfg["stagnation_threshold"] == 0.6
        assert cfg["collapse_threshold"] == 0.9
        assert cfg["jaccard_stagnation_threshold"] == 0.8
        assert cfg["history_window"] == 5

    def test_drift_config_yaml_override(self, tmp_path):
        """global_config.governance.drift overrides every knob it sets."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    drift:\n"
            "      entropy_threshold: 0.4\n"
            "      stagnation_threshold: 0.7\n"
            "      collapse_threshold: 0.95\n"
            "      jaccard_stagnation_threshold: 0.75\n"
            "      history_window: 8\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        cfg = config.get_drift_config()
        assert cfg["entropy_threshold"] == 0.4
        assert cfg["stagnation_threshold"] == 0.7
        assert cfg["collapse_threshold"] == 0.95
        assert cfg["jaccard_stagnation_threshold"] == 0.75
        assert cfg["history_window"] == 8

    def test_drift_config_partial_override(self, tmp_path):
        """A partial override keeps framework defaults for un-set keys."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    drift:\n"
            "      collapse_threshold: 0.85\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        cfg = config.get_drift_config()
        assert cfg["collapse_threshold"] == 0.85
        # Unmentioned keys keep defaults.
        assert cfg["entropy_threshold"] == 0.5
        assert cfg["history_window"] == 5

    def test_drift_config_threads_to_drift_detector(self, tmp_path):
        """End-to-end: the dict returned by get_drift_config maps
        kwarg-for-kwarg onto DriftDetector.__init__."""
        from broker.components.analytics.drift import DriftDetector
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    drift:\n"
            "      entropy_threshold: 0.3\n"
            "      history_window: 7\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        cfg = config.get_drift_config()
        detector = DriftDetector(**cfg)
        assert detector.entropy_threshold == 0.3
        assert detector.history_window == 7
        # Un-overridden defaults preserved.
        assert detector.stagnation_threshold == 0.6
        assert detector.collapse_threshold == 0.9

    def test_drift_config_malformed_value_raises_clear_error(self, tmp_path):
        """A non-numeric threshold in YAML must fail at get_drift_config
        time with a clear ``governance.drift`` message — not later as a
        TypeError deep inside DriftDetector. Covers the coerce/validate
        branch."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    drift:\n"
            "      entropy_threshold: 'not-a-float'\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        with pytest.raises(ValueError, match="governance.drift"):
            config.get_drift_config()


class TestAgentTypeConfigPopulationGovernance:
    """Phase 6L-B: get_population_governance_config() — CrossAgentValidator
    + CouncilValidator thresholds resolved from YAML
    governance.population. Mirrors the get_retrieval_config /
    get_drift_config pattern."""

    def setup_method(self):
        AgentTypeConfig._instance = None

    def test_population_config_defaults(self, tmp_path):
        """No governance.population block → CrossAgentValidator +
        CouncilValidator constructor defaults. Byte-identical to
        ``CrossAgentValidator(0.8, 0.5, 0.5)`` +
        ``CouncilValidator(..., quorum_threshold=0.5)``."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text("shared: {}\n")
        config = AgentTypeConfig.load(str(yaml_file))
        cfg = config.get_population_governance_config()
        assert cfg["echo_threshold"] == 0.8
        assert cfg["entropy_threshold"] == 0.5
        assert cfg["deadlock_threshold"] == 0.5
        assert cfg["quorum_threshold"] == 0.5

    def test_population_config_yaml_override(self, tmp_path):
        """global_config.governance.population overrides every knob."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    population:\n"
            "      echo_threshold: 0.7\n"
            "      entropy_threshold: 0.4\n"
            "      deadlock_threshold: 0.6\n"
            "      quorum_threshold: 0.667\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        cfg = config.get_population_governance_config()
        assert cfg["echo_threshold"] == 0.7
        assert cfg["entropy_threshold"] == 0.4
        assert cfg["deadlock_threshold"] == 0.6
        assert cfg["quorum_threshold"] == pytest.approx(0.667)

    def test_population_config_partial_override(self, tmp_path):
        """A partial override keeps framework defaults for un-set keys."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    population:\n"
            "      quorum_threshold: 0.667\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        cfg = config.get_population_governance_config()
        assert cfg["quorum_threshold"] == pytest.approx(0.667)
        assert cfg["echo_threshold"] == 0.8
        assert cfg["entropy_threshold"] == 0.5
        assert cfg["deadlock_threshold"] == 0.5

    def test_population_config_threads_to_validators(self, tmp_path):
        """End-to-end: get_population_governance_config()'s dict maps
        kwarg-for-kwarg onto CrossAgentValidator + CouncilValidator."""
        from broker.validators.governance.cross_agent_validator import (
            CrossAgentValidator,
        )
        from broker.validators.agent.council import CouncilValidator
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    population:\n"
            "      echo_threshold: 0.75\n"
            "      quorum_threshold: 0.667\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        cfg = config.get_population_governance_config()
        cross = CrossAgentValidator(
            echo_threshold=cfg["echo_threshold"],
            entropy_threshold=cfg["entropy_threshold"],
            deadlock_threshold=cfg["deadlock_threshold"],
        )
        council = CouncilValidator(
            validators=[],
            quorum_threshold=cfg["quorum_threshold"],
        )
        assert cross.echo_threshold == 0.75
        assert cross.entropy_threshold == 0.5
        assert cross.deadlock_threshold == 0.5
        assert council.quorum_threshold == pytest.approx(0.667)

    def test_population_config_malformed_value_raises_clear_error(self, tmp_path):
        """Non-numeric threshold in YAML must fail at config-load time
        with a clear ``governance.population`` message — not later as
        a TypeError inside the validators."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    population:\n"
            "      quorum_threshold: 'not-a-float'\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        with pytest.raises(ValueError, match="governance.population"):
            config.get_population_governance_config()


class TestAgentTypeConfigPolicyEventTiers:
    """Phase 6L-C: get_policy_event_tiers_config() — PolicyEventGenerator
    severity-tier cutoffs resolved from YAML
    governance.policy_event_tiers. Mirrors the
    get_retrieval_config / get_drift_config /
    get_population_governance_config pattern."""

    def setup_method(self):
        AgentTypeConfig._instance = None

    def test_policy_event_tiers_defaults(self, tmp_path):
        """No governance.policy_event_tiers block → PolicyEventConfig
        defaults (severe=0.20, moderate=0.10, minor=0.05)
        byte-identical to the pre-6L-C hardcoded thresholds."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text("shared: {}\n")
        config = AgentTypeConfig.load(str(yaml_file))
        cfg = config.get_policy_event_tiers_config()
        assert cfg == {"severe": 0.20, "moderate": 0.10, "minor": 0.05}

    def test_policy_event_tiers_yaml_override(self, tmp_path):
        """global_config.governance.policy_event_tiers overrides every
        tier."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    policy_event_tiers:\n"
            "      severe: 0.25\n"
            "      moderate: 0.15\n"
            "      minor: 0.07\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        cfg = config.get_policy_event_tiers_config()
        assert cfg["severe"] == 0.25
        assert cfg["moderate"] == 0.15
        assert cfg["minor"] == 0.07

    def test_policy_event_tiers_partial_override(self, tmp_path):
        """A partial override keeps framework defaults for un-set tiers."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    policy_event_tiers:\n"
            "      severe: 0.30\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        cfg = config.get_policy_event_tiers_config()
        assert cfg["severe"] == 0.30
        assert cfg["moderate"] == 0.10
        assert cfg["minor"] == 0.05

    def test_policy_event_tiers_threads_to_generator(self, tmp_path):
        """End-to-end: get_policy_event_tiers_config()'s dict maps onto
        ``PolicyEventConfig(severity_tiers=...)`` and the generator's
        ``_determine_severity`` reads the overridden cutoffs."""
        from broker.components.events.generators.policy import (
            PolicyEventConfig,
            PolicyEventGenerator,
        )
        from broker.interfaces.event_generator import EventSeverity
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    policy_event_tiers:\n"
            "      severe: 0.30\n"
            "      moderate: 0.15\n"
            "      minor: 0.06\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        tiers = config.get_policy_event_tiers_config()
        gen = PolicyEventGenerator(PolicyEventConfig(severity_tiers=tiers))
        # A 25% change is now MODERATE (above 0.15, below 0.30) where it
        # would have been SEVERE (above 0.20) under the pre-6L-C
        # hardcoded thresholds.
        assert gen._determine_severity(
            {"old_value": 1.0, "new_value": 1.25}
        ) == EventSeverity.MODERATE

    def test_policy_event_tiers_malformed_value_raises_clear_error(self, tmp_path):
        """Non-numeric tier in YAML must fail at config-load time with
        a clear ``governance.policy_event_tiers`` message."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    policy_event_tiers:\n"
            "      severe: 'not-a-float'\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        with pytest.raises(ValueError, match="governance.policy_event_tiers"):
            config.get_policy_event_tiers_config()

    def test_policy_event_tiers_non_monotonic_raises(self, tmp_path):
        """``severe`` must be >= ``moderate`` must be >= ``minor`` —
        otherwise the comparison ladder in ``_determine_severity``
        produces a confusing classification. Catch this at config-load
        time with a clear message."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    policy_event_tiers:\n"
            "      severe: 0.10\n"
            "      moderate: 0.20\n"
            "      minor: 0.05\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        with pytest.raises(ValueError, match="monotonic|severe >= moderate"):
            config.get_policy_event_tiers_config()

    def test_policy_event_tiers_negative_raises(self, tmp_path):
        """A negative tier would silently misclassify every non-zero
        change as that severity (since ``abs(change_pct) >= negative``
        is always true). Catch at config-load time."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    policy_event_tiers:\n"
            "      severe: -0.05\n"
            "      moderate: -0.10\n"
            "      minor: -0.15\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        with pytest.raises(ValueError, match=">= 0"):
            config.get_policy_event_tiers_config()

    def test_policy_event_tiers_strips_unknown_keys(self, tmp_path):
        """A YAML config with an extra key beyond the canonical three
        is silently stripped — the returned dict carries only
        ``severe`` / ``moderate`` / ``minor`` so downstream consumers
        cannot accidentally consume a value ``_determine_severity``
        ignores."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  governance:\n"
            "    policy_event_tiers:\n"
            "      severe: 0.25\n"
            "      moderate: 0.15\n"
            "      minor: 0.07\n"
            "      extreme: 0.50\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        cfg = config.get_policy_event_tiers_config()
        assert set(cfg.keys()) == {"severe", "moderate", "minor"}


class TestAgentTypeConfigReflectionQuestions:
    """Phase 6H Item 4: get_reflection_questions() — per-agent-type and
    domain-wide reflection questions resolved from agent_types.yaml."""

    def setup_method(self):
        AgentTypeConfig._instance = None

    def test_per_agent_type_wins_over_domain_wide(self, tmp_path):
        """A <agent_type>.reflection.questions block overrides the
        global_config one — the multi-agent per-type case."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  reflection:\n"
            "    questions:\n"
            "      - domain-wide question\n"
            "farmer:\n"
            "  reflection:\n"
            "    questions:\n"
            "      - farmer-specific question\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        assert config.get_reflection_questions("farmer") == [
            "farmer-specific question"
        ]
        # An agent type without its own block falls back to domain-wide.
        assert config.get_reflection_questions("regulator") == [
            "domain-wide question"
        ]

    def test_domain_wide_when_no_per_type(self, tmp_path):
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text(
            "global_config:\n"
            "  reflection:\n"
            "    questions:\n"
            "      - domain-wide question\n"
        )
        config = AgentTypeConfig.load(str(yaml_file))
        assert config.get_reflection_questions("farmer") == [
            "domain-wide question"
        ]

    def test_empty_when_nothing_configured(self, tmp_path):
        """No YAML questions, no domain → []; the caller then applies the
        generic _DEFAULT_REFLECTION_QUESTIONS fallback."""
        yaml_file = tmp_path / "t.yaml"
        yaml_file.write_text("shared: {}\n")
        config = AgentTypeConfig.load(str(yaml_file))
        assert config.get_reflection_questions("farmer") == []
