"""
Modular Experiment System - The "Puzzle" Architecture
Defined in PR 1.
"""
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, field
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.base_agent import BaseAgent
from ..interfaces.skill_types import ApprovedSkill
from .skill_broker_engine import SkillBrokerEngine
from ..components.context_builder import BaseAgentContextBuilder
from ..components.memory_engine import MemoryEngine, WindowMemoryEngine, HierarchicalMemoryEngine
from ..utils.agent_config import GovernanceAuditor

@dataclass
class ExperimentConfig:
    """Configuration container for an experiment."""
    model: str = "gpt-4"
    num_years: int = 1
    num_steps: Optional[int] = None  # Generic alias for num_years
    semantic_thresholds: tuple = (0.3, 0.7) # PR 3: Configurable heuristics
    governance_profile: str = "default"
    output_dir: Path = Path("results")
    experiment_name: str = "modular_exp"
    seed: int = 42
    verbose: bool = False
    workers: int = 1  # Number of parallel workers for LLM calls (1=sequential)

class ExperimentRunner:
    """Engine that runs the simulation loop."""
    def __init__(self, 
                 broker: SkillBrokerEngine, 
                 sim_engine: Any, 
                 agents: Dict[str, BaseAgent], 
                 config: ExperimentConfig,
                 memory_engine: Optional[MemoryEngine] = None,
                 hooks: Optional[Dict[str, Callable]] = None):
        self.broker = broker
        self.sim_engine = sim_engine
        self.agents = agents
        self.config = config
        self.step_counter = 0
        self.memory_engine = memory_engine or WindowMemoryEngine(window_size=3)
        self.hooks = hooks or {}
        
        # Sync verbosity
        self.broker.log_prompt = self.config.verbose
        
        # Cache for llm_invoke functions per agent type
        self._llm_cache = {}

    @property
    def llm_invoke(self) -> Callable:
        """Legacy default llm_invoke."""
        return self.get_llm_invoke("default")

    def get_llm_invoke(self, agent_type: str) -> Callable:
        """Create or return cached llm_invoke for a specific agent type."""
        if agent_type not in self._llm_cache:
            from broker.utils.llm_utils import create_llm_invoke
            # Get parameters from config if available
            overrides = {}
            if hasattr(self.broker, 'config') and self.broker.config:
                overrides = self.broker.config.get_llm_params(agent_type)
            
            self._llm_cache[agent_type] = create_llm_invoke(
                self.config.model, 
                verbose=self.config.verbose,
                overrides=overrides
            )
        return self._llm_cache[agent_type]

    @property
    def current_step(self) -> int:
        """Alias for the simulation loop cycle."""
        # This returns the current year/cycle index
        return getattr(self, '_current_year', 0)

    def run(self, llm_invoke: Optional[Callable] = None):
        """Standardized simulation loop."""
        llm_invoke = llm_invoke or self.llm_invoke
        run_id = f"exp_{random.randint(1000, 9999)}"
        print(f"Starting Experiment: {self.config.experiment_name} | Model: {self.config.model}")
        
        # 0. Fool-proof Schema Validation
        # ... (keep existing validation code)
        if hasattr(self.broker, 'model_adapter') and getattr(self.broker.model_adapter, 'agent_config', None):
            config = self.broker.model_adapter.agent_config
            types = set(a.agent_type for a in self.agents.values() if hasattr(a, 'agent_type'))
            print(f"[Governance:Diagnostic] Initializing with Profile: {self.config.governance_profile}")
            for atype in types:
                issues = config.validate_schema(atype)
                for issue in issues:
                    print(f"[Governance:Diagnostic] {issue}")
        
        # Determine total iterations (backward compatible)
        iterations = self.config.num_steps or self.config.num_years
        
        for step in range(1, iterations + 1):
            self._current_year = step # internal tracker
            # Environment update (Attempt advance_step first, fallback to advance_year)
            if hasattr(self.sim_engine, 'advance_step'):
                env = self.sim_engine.advance_step()
            else:
                env = self.sim_engine.advance_year() if self.sim_engine else {}
            
            # Print status using generic term if steps used, otherwise year
            term = "Step" if self.config.num_steps else "Year"
            print(f"--- {term} {step} ---")
            
            # --- Lifecycle Hook: Pre-Step / Pre-Year ---
            # Dual trigger for generic compatibility
            if "pre_step" in self.hooks:
                self.hooks["pre_step"](step, env, self.agents)
            if "pre_year" in self.hooks:
                self.hooks["pre_year"](step, env, self.agents)
            
            # Filter only active agents (Generic approach)
            active_agents = [
                a for a in self.agents.values() 
                if getattr(a, 'is_active', True)
            ]
            
            # Parallel vs Sequential Execution (PR: Multiprocessing Core)
            if self.config.workers > 1:
                results = self._run_agents_parallel(active_agents, run_id, llm_invoke, env)
            else:
                results = self._run_agents_sequential(active_agents, run_id, llm_invoke, env)
            
            # Apply results and trigger post-step hooks
            for agent, result in results:
                if result.execution_result and result.execution_result.success:
                    self._apply_state_changes(agent, result)
                if "post_step" in self.hooks:
                    self.hooks["post_step"](agent, result)
            
            # --- Lifecycle Hook: Post-Step-End / Post-Year ---
            # Dual trigger for generic compatibility
            if "post_step_end" in self.hooks:
                self.hooks["post_step_end"](step, self.agents)
            if "post_year" in self.hooks:
                self.hooks["post_year"](step, self.agents)
            
            self._finalize_step(step)
        
        # 4. Finalize Experiment
        if hasattr(self.broker.audit_writer, 'finalize'):
            self.broker.audit_writer.finalize()
            
        summary_path = self.config.output_dir / "governance_summary.json"
        self.broker.auditor.save_summary(summary_path)

    def _apply_state_changes(self, agent: BaseAgent, result: Any):
        """Update agent attributes and memory from execution results."""
        # 1. Update State Flags
        changes = result.execution_result.state_changes
        for key, value in changes.items():
            setattr(agent, key, value)
        
        # 2. Update Memory via Engine
        action_desc = result.approved_skill.skill_name.replace("_", " ").capitalize()
        
        # Enhance memory description with outcome/context if available
        # Example: "Year 5: Decided to Buy Flood Insurance (Success)"
        timestamp_prefix = f"Year {self._current_year}: " if hasattr(self, '_current_year') else ""
        memory_content = f"{timestamp_prefix}Decided to: {action_desc}"
        
        if result.execution_result and result.execution_result.metadata:
            meta = result.execution_result.metadata
            if "payout" in meta:
                memory_content += f" (Received payout: {meta['payout']:.2f})"
            elif "damage" in meta and meta["damage"] > 0:
                memory_content += f" (Suffered damage: {meta['damage']:.2f})"
        
        if hasattr(self.memory_engine, 'add_memory_for_agent'):
            self.memory_engine.add_memory_for_agent(agent, memory_content)
        else:
            self.memory_engine.add_memory(agent.id, memory_content)

    def _finalize_step(self, step: int):
        """Unified finalization logic per cycle."""
        # Notify audit writer to flush if needed
        if hasattr(self.broker.audit_writer, 'finalize'):
             # Future: per-step flushing could be added here
             pass

    def _finalize_year(self, year: int):
        """Legacy alias for _finalize_step."""
        self._finalize_step(year)

    def _run_agents_sequential(self, agents: List, run_id: str, llm_invoke: Callable, env: Dict) -> List:
        """Execute agent steps sequentially. Default mode."""
        results = []
        for agent in agents:
            self.step_counter += 1
            result = self.broker.process_step(
                agent_id=agent.id,
                step_id=self.step_counter,
                run_id=run_id,
                seed=self.config.seed + self.step_counter,
                llm_invoke=self.get_llm_invoke(getattr(agent, 'agent_type', 'default')),
                agent_type=getattr(agent, 'agent_type', 'default'),
                env_context=env
            )
            results.append((agent, result))
        return results

    def _run_agents_parallel(self, agents: List, run_id: str, llm_invoke: Callable, env: Dict) -> List:
        """Execute agent steps in parallel using ThreadPoolExecutor."""
        results = []
        
        def process_agent(agent, step_id):
            return agent, self.broker.process_step(
                agent_id=agent.id,
                step_id=step_id,
                run_id=run_id,
                seed=self.config.seed + step_id,
                llm_invoke=self.get_llm_invoke(getattr(agent, 'agent_type', 'default')),
                agent_type=getattr(agent, 'agent_type', 'default'),
                env_context=env
            )
        
        with ThreadPoolExecutor(max_workers=self.config.workers) as executor:
            futures = {}
            for agent in agents:
                self.step_counter += 1
                futures[executor.submit(process_agent, agent, self.step_counter)] = agent
            
            for future in as_completed(futures):
                try:
                    agent, result = future.result()
                    results.append((agent, result))
                except Exception as e:
                    print(f"[Parallel] Agent {futures[future].id} failed: {e}")
        
        return results

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

    def with_workers(self, workers: int = 4):
        """Set number of parallel workers for LLM calls. 1=sequential (default)."""
        self.workers = workers
        return self

    def with_model(self, model: str):
        self.model = model
        return self
    
    def with_verbose(self, verbose: bool = True):
        self.verbose = verbose
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
        """Register a list of pre_year hooks for simplicity."""
        for hook in hooks:
            # For now, default to pre_year if just a list
            self.hooks["pre_year"] = hook 
        return self

    def with_hook(self, hook: Callable):
        """Register a single pre_year hook."""
        self.hooks["pre_year"] = hook
        return self

    def with_governance(self, profile: str, config_path: str):
        self.profile = profile
        self.agent_types_path = config_path
        return self

    def with_agents(self, agents: Dict[str, BaseAgent]):
        self.agents = agents
        return self

    def with_csv_agents(self, path: str, mapping: Dict[str, str], agent_type: str = "household"):
        """Load agents from a CSV file using column mapping."""
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
        return self

    def build(self) -> ExperimentRunner:
        # Complex assembly logic here
        from broker import SkillRegistry
        from broker import GenericAuditWriter, AuditConfig
        from validators import AgentValidator
        from broker.components.context_builder import create_context_builder
        import os

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
        
        # Phase 28: If using HierarchicalMemoryEngine, ensure ContextBuilder supports it
        from ..components.context_builder import TieredContextBuilder
        
        # 3. Setup Context Builder
        # Inject memory_engine and semantic_thresholds into ctx_builder if it supports it
        ctx_builder = self.ctx_builder or create_context_builder(
            self.agents, 
            yaml_path=self.agent_types_path,
            semantic_thresholds=getattr(self, 'semantic_thresholds', (0.3, 0.7))
        )
        if hasattr(ctx_builder, 'memory_engine'):
            ctx_builder.memory_engine = mem_engine
        
        if hasattr(ctx_builder, 'semantic_thresholds'):
            ctx_builder.semantic_thresholds = getattr(self, 'semantic_thresholds', (0.3, 0.7))
        
        # PR 2 Fix: Inject memory_engine into InteractionHub if present in ctx_builder
        if hasattr(ctx_builder, 'hub') and ctx_builder.hub:
            ctx_builder.hub.memory_engine = mem_engine
        
        # Re-alignment: Inject skill_registry into TieredContextBuilder
        from broker.components.context_builder import TieredContextBuilder
        if isinstance(ctx_builder, TieredContextBuilder):
            ctx_builder.skill_registry = reg
        
        # 4. Setup Audit
        audit_cfg = AuditConfig(
            output_dir=str(self.output_base / f"{self.model.replace(':','_').replace('-','_').replace('.','_')}_{self.profile}"),
            experiment_name=self.model
        )
        audit_writer = GenericAuditWriter(audit_cfg)
        
        # 5. Setup Validator & Adapter
        validator = AgentValidator(config_path=self.agent_types_path)
        from broker.utils.model_adapter import get_adapter
        
        # PR 13.1: Inject registry skills into adapter for robust parsing via factory
        adapter = get_adapter(self.model)
        adapter.agent_type = "default"
        adapter.config_path = self.agent_types_path
        
        # Resolve skills from registry for the adapter
        reg_skills = set(reg.skills.keys()) if hasattr(reg, 'skills') else None
        if reg_skills:
            adapter.valid_skills = reg_skills
            # Re-initialize alias map with new valid skills
            adapter.alias_map = {s.lower(): s for s in reg_skills}
        
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
                print(f" Warning: Could not load configurations from {self.agent_types_path}: {e}")
        
        # 6. Setup Broker
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
            log_prompt=self.verbose
        )
        
        # PR 11: Pass active project dir to adapter
        if hasattr(adapter, 'project_dir') and self.agent_types_path:
            adapter.project_dir = Path(self.agent_types_path).parent

        exp_config = ExperimentConfig(
            model=self.model,
            num_years=self.num_years,
            num_steps=self.num_steps,
            governance_profile=self.profile,
            output_dir=self.output_base,
            verbose=self.verbose,
            workers=self.workers  # PR: Multiprocessing Core
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
