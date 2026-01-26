"""
Configuration Schema Definitions.

Provides typed dataclasses for experiment configuration with validation.
Supports memory, reflection, domain pack, and LLM settings.

Usage:
    >>> from governed_ai_sdk.v1_prototype.config import ExperimentConfig, MemoryConfig
    >>> config = ExperimentConfig(
    ...     name="flood_study",
    ...     domain="flood",
    ...     agents=100,
    ...     years=10,
    ...     memory=MemoryConfig(engine="universal", persistence="json")
    ... )
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path


@dataclass
class MemoryConfig:
    """
    Memory engine configuration.

    Attributes:
        engine: Engine type (window, importance, humancentric, universal)
        window_size: Size of working memory window
        arousal_threshold: Threshold for System 2 activation
        ema_alpha: EMA smoothing factor for expectation tracking
        consolidation_threshold: Threshold for memory consolidation
        persistence: Persistence backend (json, sqlite, None)
        persistence_path: Path for persistence storage
        scorer_domain: Domain for memory scoring (flood, finance, etc.)
    """

    engine: str = "universal"
    window_size: int = 10
    arousal_threshold: float = 2.0
    ema_alpha: float = 0.3
    consolidation_threshold: float = 0.6
    persistence: Optional[str] = None
    persistence_path: Optional[str] = None
    scorer_domain: Optional[str] = None

    def __post_init__(self):
        valid_engines = ["window", "importance", "humancentric", "universal"]
        if self.engine not in valid_engines:
            raise ValueError(f"engine must be one of {valid_engines}, got {self.engine}")

        if self.persistence and self.persistence not in ["json", "sqlite", "memory"]:
            raise ValueError(f"persistence must be json, sqlite, or memory")

        if self.persistence in ["json", "sqlite"] and not self.persistence_path:
            raise ValueError(f"persistence_path required for {self.persistence} backend")


@dataclass
class ReflectionConfig:
    """
    Reflection system configuration.

    Attributes:
        enabled: Whether reflection is enabled
        interval: Reflect every N time periods
        auto_promote: Auto-promote insights to memory
        promotion_threshold: Minimum importance for promotion
        max_memories_per_reflection: Max memories to include in reflection
        template_domain: Domain for reflection template
    """

    enabled: bool = True
    interval: int = 1
    auto_promote: bool = True
    promotion_threshold: float = 0.7
    max_memories_per_reflection: int = 10
    template_domain: Optional[str] = None

    def __post_init__(self):
        if self.interval < 1:
            raise ValueError("interval must be >= 1")

        self.promotion_threshold = max(0.0, min(1.0, self.promotion_threshold))


@dataclass
class SocialConfig:
    """
    Social observation configuration.

    Attributes:
        enabled: Whether social observation is enabled
        observer_domain: Domain for social observer
        gossip_enabled: Whether gossip mechanism is enabled
        observation_radius: Number of neighbors to observe
    """

    enabled: bool = True
    observer_domain: Optional[str] = None
    gossip_enabled: bool = True
    observation_radius: int = 5


@dataclass
class GovernanceConfig:
    """
    Policy governance configuration.

    Attributes:
        enabled: Whether governance is enabled
        policy_path: Path to policy file
        xai_enabled: Whether XAI explanations are enabled
        feasibility_domain: Domain for feasibility scoring
    """

    enabled: bool = True
    policy_path: Optional[str] = None
    xai_enabled: bool = True
    feasibility_domain: Optional[str] = None


@dataclass
class LLMConfig:
    """
    LLM provider configuration.

    Attributes:
        provider: LLM provider (ollama, openai, anthropic)
        model: Model name/ID
        temperature: Sampling temperature
        max_tokens: Maximum response tokens
        base_url: API base URL (for ollama/custom)
        api_key_env: Environment variable for API key
    """

    provider: str = "ollama"
    model: str = "llama3.2:3b"
    temperature: float = 0.7
    max_tokens: int = 1024
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None

    def __post_init__(self):
        valid_providers = ["ollama", "openai", "anthropic", "custom"]
        if self.provider not in valid_providers:
            raise ValueError(f"provider must be one of {valid_providers}")

        self.temperature = max(0.0, min(2.0, self.temperature))


@dataclass
class DomainPackConfig:
    """
    Domain pack configuration.

    Attributes:
        name: Domain name (flood, finance, education, health)
        sensors: List of sensor names to enable
        rules: List of rule IDs to enable
        observer: Social observer class name
        environment_observer: Environment observer class name
        memory_scorer: Memory scorer class name
        reflection_template: Reflection template class name
    """

    name: str
    sensors: List[str] = field(default_factory=list)
    rules: List[str] = field(default_factory=list)
    observer: Optional[str] = None
    environment_observer: Optional[str] = None
    memory_scorer: Optional[str] = None
    reflection_template: Optional[str] = None

    def __post_init__(self):
        valid_domains = ["flood", "finance", "education", "health", "generic"]
        if self.name.lower() not in valid_domains:
            # Allow custom domains
            pass


@dataclass
class OutputConfig:
    """
    Output and logging configuration.

    Attributes:
        output_dir: Directory for results
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        save_traces: Whether to save cognitive traces
        save_memories: Whether to save memory snapshots
        export_format: Export format (json, csv, parquet)
    """

    output_dir: str = "results"
    log_level: str = "INFO"
    save_traces: bool = True
    save_memories: bool = True
    export_format: str = "json"

    def __post_init__(self):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if self.log_level.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        self.log_level = self.log_level.upper()

        valid_formats = ["json", "csv", "parquet"]
        if self.export_format not in valid_formats:
            raise ValueError(f"export_format must be one of {valid_formats}")


@dataclass
class ExperimentConfig:
    """
    Complete experiment configuration.

    Aggregates all component configurations for a full experiment setup.

    Attributes:
        name: Experiment name
        domain: Primary domain (flood, finance, education, health)
        agents: Number of agents
        years: Number of simulation years
        seed: Random seed for reproducibility
        memory: Memory engine configuration
        reflection: Reflection system configuration
        social: Social observation configuration
        governance: Policy governance configuration
        llm: LLM provider configuration
        domain_pack: Domain pack configuration
        output: Output configuration
    """

    name: str
    domain: str
    agents: int
    years: int
    seed: int = 42

    memory: MemoryConfig = field(default_factory=MemoryConfig)
    reflection: ReflectionConfig = field(default_factory=ReflectionConfig)
    social: SocialConfig = field(default_factory=SocialConfig)
    governance: GovernanceConfig = field(default_factory=GovernanceConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    domain_pack: Optional[DomainPackConfig] = None
    output: OutputConfig = field(default_factory=OutputConfig)

    def __post_init__(self):
        valid_domains = ["flood", "finance", "education", "health", "generic"]
        if self.domain.lower() not in valid_domains:
            # Allow but warn for custom domains
            pass

        if self.agents < 1:
            raise ValueError("agents must be >= 1")

        if self.years < 1:
            raise ValueError("years must be >= 1")

        # Auto-configure domain-related settings if not specified
        if self.memory.scorer_domain is None:
            self.memory.scorer_domain = self.domain

        if self.reflection.template_domain is None:
            self.reflection.template_domain = self.domain

        if self.social.observer_domain is None:
            self.social.observer_domain = self.domain

        if self.governance.feasibility_domain is None:
            self.governance.feasibility_domain = self.domain

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "name": self.name,
            "domain": self.domain,
            "agents": self.agents,
            "years": self.years,
            "seed": self.seed,
            "memory": {
                "engine": self.memory.engine,
                "window_size": self.memory.window_size,
                "arousal_threshold": self.memory.arousal_threshold,
                "persistence": self.memory.persistence,
            },
            "reflection": {
                "enabled": self.reflection.enabled,
                "interval": self.reflection.interval,
                "auto_promote": self.reflection.auto_promote,
            },
            "llm": {
                "provider": self.llm.provider,
                "model": self.llm.model,
            },
            "output": {
                "output_dir": self.output.output_dir,
                "log_level": self.output.log_level,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentConfig":
        """Create config from dictionary."""
        memory = MemoryConfig(**data.pop("memory", {}))
        reflection = ReflectionConfig(**data.pop("reflection", {}))
        social = SocialConfig(**data.pop("social", {}))
        governance = GovernanceConfig(**data.pop("governance", {}))
        llm = LLMConfig(**data.pop("llm", {}))
        output = OutputConfig(**data.pop("output", {}))

        domain_pack = None
        if "domain_pack" in data:
            domain_pack = DomainPackConfig(**data.pop("domain_pack"))

        return cls(
            **data,
            memory=memory,
            reflection=reflection,
            social=social,
            governance=governance,
            llm=llm,
            domain_pack=domain_pack,
            output=output,
        )
