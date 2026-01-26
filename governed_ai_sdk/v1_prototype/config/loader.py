"""
Unified Configuration Loader.

Provides a single loader for all configuration types with:
- YAML file loading
- Environment variable interpolation
- Caching
- Domain pack configuration

Usage:
    >>> from governed_ai_sdk.v1_prototype.config import UnifiedConfigLoader
    >>> loader = UnifiedConfigLoader()
    >>> config = loader.load_experiment("config/flood_study.yaml")
    >>> print(config.domain, config.agents)
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union
import logging

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from .schema import (
    ExperimentConfig,
    MemoryConfig,
    ReflectionConfig,
    SocialConfig,
    GovernanceConfig,
    LLMConfig,
    DomainPackConfig,
    OutputConfig,
)

logger = logging.getLogger(__name__)


class UnifiedConfigLoader:
    """
    Single loader for all configuration types.

    Features:
    - YAML file loading with caching
    - Environment variable interpolation (${VAR})
    - Domain pack configuration loading
    - Fallback to Python module defaults

    Attributes:
        base_path: Base path for relative file references
        cache: Dictionary cache for loaded configurations
    """

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize the loader.

        Args:
            base_path: Base path for relative file references
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self._cache: Dict[str, Any] = {}

    def load_experiment(self, path: Union[str, Path]) -> ExperimentConfig:
        """
        Load experiment configuration from YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            ExperimentConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        data = self._load_yaml(path)
        data = self._interpolate_env(data)

        # Build nested configs
        memory_data = data.pop("memory", {})
        reflection_data = data.pop("reflection", {})
        social_data = data.pop("social", {})
        governance_data = data.pop("governance", {})
        llm_data = data.pop("llm", {})
        output_data = data.pop("output", {})
        domain_pack_data = data.pop("domain_pack", None)

        # Create nested config objects
        memory = MemoryConfig(**memory_data)
        reflection = ReflectionConfig(**reflection_data)
        social = SocialConfig(**social_data)
        governance = GovernanceConfig(**governance_data)
        llm = LLMConfig(**llm_data)
        output = OutputConfig(**output_data)

        domain_pack = None
        if domain_pack_data:
            domain_pack = DomainPackConfig(**domain_pack_data)

        return ExperimentConfig(
            **data,
            memory=memory,
            reflection=reflection,
            social=social,
            governance=governance,
            llm=llm,
            domain_pack=domain_pack,
            output=output,
        )

    def load_domain_pack(self, domain: str) -> DomainPackConfig:
        """
        Load domain pack configuration.

        Tries to load from YAML first, then falls back to Python module defaults.

        Args:
            domain: Domain name (flood, finance, education, health)

        Returns:
            DomainPackConfig instance
        """
        # Try YAML config first
        yaml_path = self.base_path / f"config/domains/{domain}.yaml"
        if yaml_path.exists():
            data = self._load_yaml(yaml_path)
            data = self._interpolate_env(data)
            return DomainPackConfig(**data)

        # Fallback to Python module defaults
        try:
            from governed_ai_sdk.domains import get_domain_info
            info = get_domain_info(domain)
            return DomainPackConfig(
                name=domain,
                sensors=info.get("sensors", []),
                rules=info.get("rules", []),
            )
        except ImportError:
            # Return minimal config
            return DomainPackConfig(name=domain)

    def load_memory_config(self, path: Union[str, Path]) -> MemoryConfig:
        """
        Load standalone memory configuration.

        Args:
            path: Path to YAML file

        Returns:
            MemoryConfig instance
        """
        data = self._load_yaml(path)
        data = self._interpolate_env(data)
        return MemoryConfig(**data)

    def load_llm_config(self, path: Union[str, Path]) -> LLMConfig:
        """
        Load standalone LLM configuration.

        Args:
            path: Path to YAML file

        Returns:
            LLMConfig instance
        """
        data = self._load_yaml(path)
        data = self._interpolate_env(data)
        return LLMConfig(**data)

    def _load_yaml(self, path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load YAML file with caching.

        Args:
            path: Path to YAML file

        Returns:
            Dictionary with parsed YAML contents
        """
        if not YAML_AVAILABLE:
            raise ImportError("PyYAML is required for YAML configuration loading")

        path = Path(path)
        if not path.is_absolute():
            path = self.base_path / path

        cache_key = str(path.absolute())

        if cache_key in self._cache:
            return self._cache[cache_key].copy()

        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        self._cache[cache_key] = data
        return data.copy()

    def _interpolate_env(self, data: Any) -> Any:
        """
        Replace ${VAR} with environment variable values.

        Args:
            data: Data structure to process

        Returns:
            Data with environment variables interpolated
        """
        if isinstance(data, str):
            pattern = r'\$\{(\w+)\}'
            matches = re.findall(pattern, data)
            for var in matches:
                value = os.environ.get(var, "")
                data = data.replace(f"${{{var}}}", value)
            return data
        elif isinstance(data, dict):
            return {k: self._interpolate_env(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._interpolate_env(item) for item in data]
        return data

    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        self._cache.clear()

    def create_from_dict(self, data: Dict[str, Any]) -> ExperimentConfig:
        """
        Create ExperimentConfig from dictionary without file loading.

        Useful for programmatic configuration.

        Args:
            data: Configuration dictionary

        Returns:
            ExperimentConfig instance
        """
        data = self._interpolate_env(data)
        return ExperimentConfig.from_dict(data)


def load_config(path: Union[str, Path]) -> ExperimentConfig:
    """
    Convenience function to load experiment config.

    Args:
        path: Path to YAML configuration file

    Returns:
        ExperimentConfig instance

    Example:
        >>> config = load_config("config/flood_study.yaml")
        >>> print(config.domain, config.agents)
    """
    loader = UnifiedConfigLoader()
    return loader.load_experiment(path)


def create_default_config(
    domain: str,
    agents: int = 100,
    years: int = 10,
    **kwargs
) -> ExperimentConfig:
    """
    Create a default ExperimentConfig for a domain.

    Args:
        domain: Domain name (flood, finance, education, health)
        agents: Number of agents
        years: Number of simulation years
        **kwargs: Additional config overrides

    Returns:
        ExperimentConfig instance

    Example:
        >>> config = create_default_config("flood", agents=50, years=5)
    """
    return ExperimentConfig(
        name=f"{domain}_study",
        domain=domain,
        agents=agents,
        years=years,
        **kwargs
    )
