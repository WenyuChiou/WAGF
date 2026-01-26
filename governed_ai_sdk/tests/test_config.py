"""
Tests for Task-034 Phase 11: Configuration System.

Tests configuration schema validation and loading.
"""

import pytest
import tempfile
import os
from pathlib import Path

from governed_ai_sdk.v1_prototype.config import (
    MemoryConfig,
    ReflectionConfig,
    SocialConfig,
    GovernanceConfig,
    LLMConfig,
    DomainPackConfig,
    OutputConfig,
    ExperimentConfig,
    UnifiedConfigLoader,
    load_config,
    create_default_config,
)


class TestMemoryConfig:
    """Tests for MemoryConfig dataclass."""

    def test_default_values(self):
        """MemoryConfig has sensible defaults."""
        config = MemoryConfig()
        assert config.engine == "universal"
        assert config.window_size == 10
        assert config.arousal_threshold == 2.0
        assert config.persistence is None

    def test_custom_values(self):
        """MemoryConfig accepts custom values."""
        config = MemoryConfig(
            engine="window",
            window_size=5,
            arousal_threshold=1.5,
        )
        assert config.engine == "window"
        assert config.window_size == 5

    def test_invalid_engine_raises(self):
        """MemoryConfig raises on invalid engine."""
        with pytest.raises(ValueError, match="engine must be one of"):
            MemoryConfig(engine="invalid_engine")

    def test_persistence_requires_path(self):
        """MemoryConfig raises if persistence set without path."""
        with pytest.raises(ValueError, match="persistence_path required"):
            MemoryConfig(persistence="json")

    def test_persistence_with_path(self):
        """MemoryConfig accepts persistence with path."""
        config = MemoryConfig(
            persistence="json",
            persistence_path="./memory_store"
        )
        assert config.persistence == "json"
        assert config.persistence_path == "./memory_store"


class TestReflectionConfig:
    """Tests for ReflectionConfig dataclass."""

    def test_default_values(self):
        """ReflectionConfig has sensible defaults."""
        config = ReflectionConfig()
        assert config.enabled is True
        assert config.interval == 1
        assert config.auto_promote is True
        assert config.promotion_threshold == 0.7

    def test_invalid_interval_raises(self):
        """ReflectionConfig raises on invalid interval."""
        with pytest.raises(ValueError, match="interval must be >= 1"):
            ReflectionConfig(interval=0)

    def test_threshold_clamping(self):
        """ReflectionConfig clamps promotion_threshold."""
        config = ReflectionConfig(promotion_threshold=1.5)
        assert config.promotion_threshold == 1.0


class TestLLMConfig:
    """Tests for LLMConfig dataclass."""

    def test_default_values(self):
        """LLMConfig has sensible defaults."""
        config = LLMConfig()
        assert config.provider == "ollama"
        assert config.model == "llama3.2:3b"
        assert config.temperature == 0.7

    def test_invalid_provider_raises(self):
        """LLMConfig raises on invalid provider."""
        with pytest.raises(ValueError, match="provider must be one of"):
            LLMConfig(provider="invalid_provider")

    def test_temperature_clamping(self):
        """LLMConfig clamps temperature to [0, 2]."""
        config = LLMConfig(temperature=3.0)
        assert config.temperature == 2.0


class TestOutputConfig:
    """Tests for OutputConfig dataclass."""

    def test_default_values(self):
        """OutputConfig has sensible defaults."""
        config = OutputConfig()
        assert config.output_dir == "results"
        assert config.log_level == "INFO"
        assert config.export_format == "json"

    def test_invalid_log_level_raises(self):
        """OutputConfig raises on invalid log_level."""
        with pytest.raises(ValueError, match="log_level must be one of"):
            OutputConfig(log_level="INVALID")

    def test_log_level_normalized(self):
        """OutputConfig normalizes log_level to uppercase."""
        config = OutputConfig(log_level="debug")
        assert config.log_level == "DEBUG"


class TestDomainPackConfig:
    """Tests for DomainPackConfig dataclass."""

    def test_basic_creation(self):
        """DomainPackConfig can be created."""
        config = DomainPackConfig(name="flood")
        assert config.name == "flood"
        assert config.sensors == []
        assert config.rules == []

    def test_with_all_fields(self):
        """DomainPackConfig accepts all fields."""
        config = DomainPackConfig(
            name="flood",
            sensors=["FLOOD_LEVEL", "RISK_PERCEPTION"],
            rules=["insurance_affordability"],
            observer="FloodObserver",
        )
        assert len(config.sensors) == 2
        assert config.observer == "FloodObserver"


class TestExperimentConfig:
    """Tests for ExperimentConfig dataclass."""

    def test_required_fields(self):
        """ExperimentConfig requires name, domain, agents, years."""
        config = ExperimentConfig(
            name="test_study",
            domain="flood",
            agents=100,
            years=10,
        )
        assert config.name == "test_study"
        assert config.domain == "flood"
        assert config.agents == 100
        assert config.years == 10

    def test_default_nested_configs(self):
        """ExperimentConfig creates default nested configs."""
        config = ExperimentConfig(
            name="test",
            domain="flood",
            agents=50,
            years=5,
        )
        assert isinstance(config.memory, MemoryConfig)
        assert isinstance(config.reflection, ReflectionConfig)
        assert isinstance(config.llm, LLMConfig)

    def test_invalid_agents_raises(self):
        """ExperimentConfig raises on invalid agents count."""
        with pytest.raises(ValueError, match="agents must be >= 1"):
            ExperimentConfig(name="test", domain="flood", agents=0, years=5)

    def test_invalid_years_raises(self):
        """ExperimentConfig raises on invalid years count."""
        with pytest.raises(ValueError, match="years must be >= 1"):
            ExperimentConfig(name="test", domain="flood", agents=50, years=0)

    def test_auto_configure_domain(self):
        """ExperimentConfig auto-configures domain-related settings."""
        config = ExperimentConfig(
            name="test",
            domain="flood",
            agents=50,
            years=5,
        )
        assert config.memory.scorer_domain == "flood"
        assert config.reflection.template_domain == "flood"
        assert config.social.observer_domain == "flood"

    def test_to_dict(self):
        """ExperimentConfig converts to dictionary."""
        config = ExperimentConfig(
            name="test",
            domain="flood",
            agents=100,
            years=10,
        )
        result = config.to_dict()

        assert result["name"] == "test"
        assert result["domain"] == "flood"
        assert "memory" in result
        assert "llm" in result

    def test_from_dict(self):
        """ExperimentConfig can be created from dictionary."""
        data = {
            "name": "restored_study",
            "domain": "finance",
            "agents": 75,
            "years": 8,
            "memory": {"engine": "window"},
            "llm": {"model": "gpt-4"},
        }
        config = ExperimentConfig.from_dict(data)

        assert config.name == "restored_study"
        assert config.domain == "finance"
        assert config.memory.engine == "window"
        assert config.llm.model == "gpt-4"


class TestUnifiedConfigLoader:
    """Tests for UnifiedConfigLoader."""

    def test_loader_creation(self):
        """UnifiedConfigLoader can be created."""
        loader = UnifiedConfigLoader()
        assert loader.base_path == Path.cwd()

    def test_loader_with_base_path(self):
        """UnifiedConfigLoader accepts base path."""
        loader = UnifiedConfigLoader(base_path="/tmp")
        assert loader.base_path == Path("/tmp")

    def test_create_from_dict(self):
        """UnifiedConfigLoader creates config from dict."""
        loader = UnifiedConfigLoader()
        data = {
            "name": "dict_config",
            "domain": "flood",
            "agents": 50,
            "years": 5,
        }
        config = loader.create_from_dict(data)

        assert config.name == "dict_config"
        assert config.domain == "flood"

    def test_env_interpolation(self):
        """UnifiedConfigLoader interpolates environment variables."""
        loader = UnifiedConfigLoader()

        # Set environment variable
        os.environ["TEST_MODEL"] = "llama3:8b"

        data = {
            "name": "env_test",
            "domain": "flood",
            "agents": 50,
            "years": 5,
            "llm": {"model": "${TEST_MODEL}"},
        }
        config = loader.create_from_dict(data)

        assert config.llm.model == "llama3:8b"

        # Cleanup
        del os.environ["TEST_MODEL"]

    def test_cache_clearing(self):
        """UnifiedConfigLoader can clear cache."""
        loader = UnifiedConfigLoader()
        loader._cache["test_key"] = {"data": "cached"}

        loader.clear_cache()

        assert "test_key" not in loader._cache


class TestCreateDefaultConfig:
    """Tests for create_default_config function."""

    def test_flood_default(self):
        """create_default_config creates flood config."""
        config = create_default_config("flood")

        assert config.domain == "flood"
        assert config.agents == 100
        assert config.years == 10

    def test_custom_agents_years(self):
        """create_default_config accepts custom agents and years."""
        config = create_default_config("finance", agents=50, years=5)

        assert config.domain == "finance"
        assert config.agents == 50
        assert config.years == 5

    def test_custom_seed(self):
        """create_default_config accepts custom seed."""
        config = create_default_config("health", seed=123)

        assert config.seed == 123


class TestYAMLLoading:
    """Tests for YAML file loading."""

    def test_load_experiment_from_yaml(self):
        """UnifiedConfigLoader loads experiment from YAML."""
        yaml_content = """
name: yaml_test
domain: flood
agents: 75
years: 8
memory:
  engine: universal
  window_size: 5
llm:
  model: llama3:8b
"""
        # Create temp file in a way that works on Windows
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "test_config.yaml"
            yaml_path.write_text(yaml_content)

            loader = UnifiedConfigLoader()
            config = loader.load_experiment(str(yaml_path))

            assert config.name == "yaml_test"
            assert config.domain == "flood"
            assert config.agents == 75
            assert config.memory.window_size == 5
            assert config.llm.model == "llama3:8b"

    def test_load_nonexistent_file_raises(self):
        """UnifiedConfigLoader raises for nonexistent file."""
        loader = UnifiedConfigLoader()

        with pytest.raises(FileNotFoundError):
            loader.load_experiment("nonexistent_config.yaml")


class TestConfigIntegration:
    """Integration tests for configuration system."""

    def test_full_config_workflow(self):
        """Full workflow: create, modify, serialize, restore."""
        # Create config
        original = ExperimentConfig(
            name="integration_test",
            domain="flood",
            agents=100,
            years=10,
            memory=MemoryConfig(engine="universal", window_size=8),
            llm=LLMConfig(model="llama3:8b", temperature=0.5),
        )

        # Serialize
        data = original.to_dict()

        # Restore (simplified)
        restored = ExperimentConfig(
            name=data["name"],
            domain=data["domain"],
            agents=data["agents"],
            years=data["years"],
        )

        assert restored.name == original.name
        assert restored.domain == original.domain

    def test_config_with_domain_pack(self):
        """ExperimentConfig works with DomainPackConfig."""
        domain_pack = DomainPackConfig(
            name="flood",
            sensors=["FLOOD_LEVEL", "RISK_PERCEPTION"],
            rules=["insurance_affordability"],
        )

        config = ExperimentConfig(
            name="pack_test",
            domain="flood",
            agents=50,
            years=5,
            domain_pack=domain_pack,
        )

        assert config.domain_pack is not None
        assert config.domain_pack.name == "flood"
        assert len(config.domain_pack.sensors) == 2
