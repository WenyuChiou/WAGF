"""
Experiment Builder — fluent API for assembling experiments.

Extracted from experiment.py (Phase 2.1 split).
"""
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path

from broker.agents import BaseAgent
from ..components.memory.engine import MemoryEngine, WindowMemoryEngine
from ..utils.logging import logger
from .experiment_runner import ExperimentConfig, ExperimentRunner


class ExperimentBuilder:
    """Fluent API for assembling the experiment puzzle."""
    def __init__(self):
        self.model = "llama3.2:3b"
        self.num_years = 1
        self.num_steps = None # PR 2: Track if steps explicitly used
        self.semantic_thresholds = (0.3, 0.7) # PR 3: Default thresholds
        self.profile = "default"
        self.agents = {}
        self.sim_engine = None
        self.skill_registry = None
        self.agent_types_path = None
        self.output_base = Path("results")
        self.ctx_builder = None
        self.memory_engine = None
        self.verbose = False
        self.hooks = {}
        self.workers = 1  # PR: Multiprocessing Core - default to sequential
        self.seed = 42    # Default seed for reproducibility
        self.custom_validators = [] # New: custom validator functions
        self._auto_tune = False  # PR: Adaptive Performance Module
        self._exact_output = False # New: bypass model subfolder
        self._phase_order = None  # Agent type groups for phased execution

    def with_workers(self, workers: int = 4):
        """Set number of parallel workers for LLM calls. 1=sequential (default)."""
        self.workers = workers
        return self

    def with_auto_tune(self, enabled: bool = True):
        """
        Enable automatic performance tuning based on model size and available VRAM.

        When enabled, the builder will:
        1. Detect model parameter count from model tag
        2. Query available GPU VRAM
        3. Automatically set optimal workers, num_ctx, and num_predict

        Usage:
            builder = ExperimentBuilder()
                .with_model("qwen3:1.7b")
                .with_auto_tune()  # Auto-detect optimal settings
                .build()
        """
        self._auto_tune = enabled
        return self

    def with_seed(self, seed: Optional[int]):
        """Set custom random seed (None = system time)."""
        self.seed = seed
        return self

    def with_model(self, model: str):
        self.model = model
        return self

    def with_verbose(self, verbose: bool = True):
        self.verbose = verbose
        return self

    def with_custom_validators(self, validators: List[Callable]):
        """Register custom validator functions to be run by the broker."""
        self.custom_validators = validators
        return self

    def with_context_builder(self, builder: Any):
        self.ctx_builder = builder
        return self

    def with_years(self, years: int):
        self.num_years = years
        self.num_steps = None
        return self

    def with_steps(self, steps: int):
        """Generic alias for with_years."""
        self.num_years = steps
        self.num_steps = steps
        return self

    def with_memory_engine(self, engine: MemoryEngine):
        self.memory_engine = engine
        return self

    def with_semantic_thresholds(self, low: float, high: float):
        """PR 3: Configure L/M/H thresholds for prompt context."""
        self.semantic_thresholds = (low, high)
        return self

    def with_lifecycle_hooks(self, **hooks):
        """
        Register hooks: pre_year(year, env, agents),
        post_step(agent, result), post_year(year, agents)
        """
        self.hooks.update(hooks)
        return self

    def with_hooks(self, hooks: List[Callable]):
        """Register a list of pre_year hooks for simplicity.

        If multiple hooks are provided, they are composed into a single
        callable that invokes each in order.
        """
        if len(hooks) == 1:
            self.hooks["pre_year"] = hooks[0]
        elif len(hooks) > 1:
            def composed_hook(*args, **kwargs):
                for h in hooks:
                    h(*args, **kwargs)
            self.hooks["pre_year"] = composed_hook
        return self

    def with_hook(self, hook: Callable):
        """Register a single pre_year hook."""
        self.hooks["pre_year"] = hook
        return self

    def with_phase_order(self, phases: List[List[str]]):
        """Set explicit phase ordering for multi-agent execution.

        Each phase is a list of agent_type strings that execute together.
        Phases run sequentially; agents within a phase run per the worker config.
        Example: [["government"], ["insurance"], ["household_owner", "household_renter"]]
        """
        self._phase_order = phases
        return self

    def with_governance(self, profile: str, config_path: str):
        self.profile = profile
        self.agent_types_path = config_path
        return self

    def with_agents(self, agents: Dict[str, BaseAgent]):
        self.agents = agents
        return self

    def with_csv_agents(self, path: str, mapping: Dict[str, str], agent_type: str = None):
        """
        Load agents from a CSV file using column mapping.

        Args:
            path: Path to the CSV file
            mapping: Column name mapping (e.g., {"id": "agent_id", "income": "income_level"})
            agent_type: Agent type name from config (e.g., "household", "trader").
                        Required - must match a type defined in agent_types.yaml.
        """
        if agent_type is None:
            raise ValueError("agent_type is required. Specify the agent type from your config (e.g., 'household').")
        from broker import load_agents_from_csv
        self.agents = load_agents_from_csv(path, mapping, agent_type)
        return self

    def with_simulation(self, sim_engine: Any):
        self.sim_engine = sim_engine
        return self

    def with_skill_registry(self, registry: Any):
        self.skill_registry = registry
        return self

    def with_output(self, path: str):
        self.output_base = Path(path)
        self._exact_output = False
        return self

    def with_exact_output(self, path: str):
        """Set output path exactly without appending model/profile subfolders."""
        self.output_base = Path(path)
        self._exact_output = True
        return self

    def validate(self) -> list:
        """Validate builder configuration before building.

        Returns:
            List of validation error strings (empty if valid).
        """
        errors = []
        if not self.agents:
            errors.append(
                "No agents specified. Use .with_agents(dict) or .with_csv_agents(path, mapping, agent_type)."
            )
        if not self.skill_registry:
            errors.append(
                "No skill registry specified. Use .with_skill_registry('path/to/skills.yaml') "
                "or .with_skill_registry(SkillRegistry())."
            )
        if self.profile != "default" and not self.agent_types_path:
            errors.append(
                f"Governance profile '{self.profile}' requires agent_types.yaml. "
                f"Use .with_governance('{self.profile}', 'path/to/agent_types.yaml')."
            )
        if self.workers < 1:
            errors.append(f"Workers must be >= 1, got {self.workers}.")
        if self.num_years < 1 and (self.num_steps is None or self.num_steps < 1):
            errors.append("Simulation must run for at least 1 year/step.")
        return errors

    def build(self) -> ExperimentRunner:
        """Build the ExperimentRunner. Validates configuration first."""
        # Validate before building
        errors = self.validate()
        if errors:
            msg = "ExperimentBuilder validation failed:\n" + "\n".join(
                f"  - {err}" for err in errors
            )
            raise ValueError(msg)

        # Complex assembly logic here
        from broker import SkillRegistry
        from broker import GenericAuditWriter, AuditConfig
        from broker.validators.agent import AgentValidator
        from broker.components.context.builder import create_context_builder
        from broker.core.skill_broker_engine import SkillBrokerEngine
        import os

        # PR: Adaptive Performance Module - Auto-tune if enabled
        if getattr(self, '_auto_tune', False):
            try:
                from broker.utils.performance_tuner import get_optimal_config, apply_to_llm_config
                recommended = get_optimal_config(self.model)
                apply_to_llm_config(recommended)
                # Override workers with recommended value
                self.workers = recommended.workers
                logger.info(f"[AutoTune] Applied: workers={self.workers}, num_ctx={recommended.num_ctx}, num_predict={recommended.num_predict}")
            except Exception as e:
                logger.warning(f"[AutoTune] Failed to apply: {e}. Using defaults.")

        # Set environment variable for validator/config loader
        os.environ["GOVERNANCE_PROFILE"] = self.profile

        # 1. Setup Skill Registry
        reg = self.skill_registry
        if isinstance(reg, str):
            path = reg
            reg = SkillRegistry()
            reg.register_from_yaml(path)
        if not reg:
            reg = SkillRegistry()

        # 2. Setup Memory Engine (Default to Window if not provided)
        mem_engine = self.memory_engine or WindowMemoryEngine(window_size=3)
        # Seed initial memory from agent profiles (if provided)
        from broker.components.memory.engine import seed_memory_from_agents
        seed_memory_from_agents(mem_engine, self.agents)

        # Phase 28: If using HierarchicalMemoryEngine, ensure ContextBuilder supports it
        from broker.components.context.builder import TieredContextBuilder

        # 3. Setup Context Builder
        # Inject memory_engine and semantic_thresholds into ctx_builder if it supports it
        ctx_builder = self.ctx_builder or create_context_builder(
            self.agents,
            yaml_path=self.agent_types_path,
            semantic_thresholds=getattr(self, 'semantic_thresholds', (0.3, 0.7))
        )
        if hasattr(ctx_builder, 'memory_engine'):
            ctx_builder.memory_engine = mem_engine
            # Also update MemoryProvider instances in the provider pipeline
            from broker.components.context.providers import MemoryProvider as _MemProv
            for provider in getattr(ctx_builder, 'providers', []):
                if isinstance(provider, _MemProv) and provider.engine is None:
                    provider.engine = mem_engine

        if hasattr(ctx_builder, 'semantic_thresholds'):
            ctx_builder.semantic_thresholds = getattr(self, 'semantic_thresholds', (0.3, 0.7))

        # PR 2 Fix: Inject memory_engine into InteractionHub if present in ctx_builder
        if hasattr(ctx_builder, 'hub') and ctx_builder.hub:
            ctx_builder.hub.memory_engine = mem_engine

        # Re-alignment: Inject skill_registry into TieredContextBuilder
        from broker.components.context.builder import TieredContextBuilder
        if isinstance(ctx_builder, TieredContextBuilder):
            ctx_builder.skill_registry = reg

        # 4. Setup Output Directory
        # Resolve final model-specific sub-directory here so it's consistent across all components
        if self._exact_output:
            final_output_path = self.output_base
        else:
            model_subfolder = f"{self.model.replace(':','_').replace('-','_').replace('.','_')}_{self.profile}"
            final_output_path = self.output_base / model_subfolder

        final_output_path.mkdir(parents=True, exist_ok=True)

        audit_cfg = AuditConfig(
            output_dir=str(final_output_path),
            experiment_name=self.model
        )
        audit_writer = GenericAuditWriter(audit_cfg)

        # 5. Setup Validator & Adapter
        validator = AgentValidator(
            config_path=self.agent_types_path,
            enable_financial_constraints=getattr(ctx_builder, "enable_financial_constraints", False)
        )
        from broker.utils.model_adapter import get_adapter

        # PR 13.1: Inject registry skills into adapter for robust parsing via factory
        adapter = get_adapter(self.model, config_path=self.agent_types_path)
        adapter.agent_type = "default"
        adapter.config_path = self.agent_types_path

        # Resolve skills from registry for the adapter
        reg_skills = set(reg.skills.keys()) if hasattr(reg, 'skills') else None
        if reg_skills:
            adapter.valid_skills = reg_skills
            # Build alias map from YAML config (all agent types), then add registry skills
            full_aliases = {}
            for cfg_key in adapter.agent_config._config:
                if cfg_key not in ("global_config", "shared", "metadata"):
                    full_aliases.update(adapter.agent_config.get_action_alias_map(cfg_key))
            # Ensure canonical self-mappings from registry
            for s in reg_skills:
                full_aliases.setdefault(s.lower(), s)
            adapter.alias_map = full_aliases

        # Inject templates into ctx_builder if it supports it
        if hasattr(ctx_builder, 'prompt_templates') and self.agent_types_path:
            # Load template from config
            from broker.utils.agent_config import AgentTypeConfig
            try:
                config = AgentTypeConfig.load(self.agent_types_path)
                templates = {}
                for atype, cfg in config.items():
                    if "prompt_template" in cfg:
                        templates[atype] = cfg["prompt_template"]
                if templates:
                    ctx_builder.prompt_templates.update(templates)

                # Phase 12: Inject memory_config and other domain-specific parameters into agents
                for agent in self.agents.values():
                    atype = getattr(agent, 'agent_type', 'default')
                    agent.memory_config = config.get_memory_config(atype)
            except Exception as e:
                logger.warning(f"Could not load configurations from {self.agent_types_path}: {e}")

        # 6. Setup Broker
        from broker.utils.agent_config import AgentTypeConfig
        config = AgentTypeConfig.load(self.agent_types_path)

        broker = SkillBrokerEngine(
            skill_registry=reg,
            model_adapter=adapter,
            validators=[validator],
            simulation_engine=self.sim_engine,
            context_builder=ctx_builder,
            config=config,           # Added for generic logging
            audit_writer=audit_writer,
            log_prompt=self.verbose,
            custom_validators=self.custom_validators # Pass custom validators
        )

        # PR 11: Pass active project dir to adapter
        if hasattr(adapter, 'project_dir') and self.agent_types_path:
            adapter.project_dir = Path(self.agent_types_path).parent

        exp_config = ExperimentConfig(
            model=self.model,
            num_years=self.num_years,
            num_steps=self.num_steps,
            governance_profile=self.profile,
            output_dir=final_output_path,  # Use the same unified path
            seed=self.seed,
            verbose=self.verbose,
            workers=self.workers,  # PR: Multiprocessing Core
            phase_order=getattr(self, '_phase_order', None),
        )

        runner = ExperimentRunner(
            broker=broker,
            sim_engine=self.sim_engine,
            agents=self.agents,
            config=exp_config,
            memory_engine=mem_engine,
            hooks=self.hooks
        )
        return runner
