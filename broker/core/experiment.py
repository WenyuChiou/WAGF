"""
Modular Experiment System - The "Puzzle" Architecture
Defined in PR 1.
"""
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, field
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from cognitive_governance.agents import BaseAgent
from ..interfaces.skill_types import ApprovedSkill, SkillOutcome, SkillBrokerResult, ExecutionResult, SkillProposal
from .skill_broker_engine import SkillBrokerEngine
from ..components.context_builder import BaseAgentContextBuilder
from ..components.memory_engine import MemoryEngine, WindowMemoryEngine, HierarchicalMemoryEngine
from ..utils.agent_config import GovernanceAuditor
from ..utils.logging import logger
from .efficiency import CognitiveCache

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
    phase_order: Optional[List[List[str]]] = None  # Agent type groups for phased execution

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
        
        # [Efficiency Hub] Cognitive Caching for decision reuse
        persistence_path = config.output_dir / "cognitive_cache.json"
        self.efficiency = CognitiveCache(persistence_path=persistence_path)

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
        logger.info(f"Starting Experiment: {self.config.experiment_name} | Model: {self.config.model}")
        
        # 0. Fool-proof Schema Validation
        # ... (keep existing validation code)
        if hasattr(self.broker, 'model_adapter') and getattr(self.broker.model_adapter, 'agent_config', None):
            config = self.broker.model_adapter.agent_config
            types = set(a.agent_type for a in self.agents.values() if hasattr(a, 'agent_type'))
            logger.debug(f"[Governance:Diagnostic] Initializing with Profile: {self.config.governance_profile}")
            for atype in types:
                issues = config.validate_schema(atype)
                for issue in issues:
                    logger.warning(f"[Governance:Diagnostic] {issue}")
        
        # Determine total iterations (backward compatible)
        iterations = self.config.num_steps or self.config.num_years
        
        for step in range(1, iterations + 1):
            self._current_year = step # internal tracker
            # Environment update (Attempt advance_step first, fallback to advance_year)
            if hasattr(self.sim_engine, 'advance_step'):
                env = self.sim_engine.advance_step()
            else:
                env = self.sim_engine.advance_year() if self.sim_engine else {}
            
            # Ensure current_year is in env (Standardized)
            if env is None: env = {}
            if "current_year" not in env:
                env["current_year"] = step
            
            # Print status using generic term if steps used, otherwise year
            term = "Step" if self.config.num_steps else "Year"
            logger.info(f"--- {term} {step} ---")
            
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

            # Partition agents into phases (if phase_order configured)
            if self.config.phase_order:
                agent_phases = self._partition_by_phase(active_agents)
            else:
                agent_phases = [active_agents]  # Single phase (backward compatible)

            # Execute each phase sequentially, agents within phase sequential or parallel
            for phase_agents in agent_phases:
                if not phase_agents:
                    continue
                if self.config.workers > 1:
                    results = self._run_agents_parallel(phase_agents, run_id, llm_invoke, env)
                else:
                    results = self._run_agents_sequential(phase_agents, run_id, llm_invoke, env)

                # Apply results and trigger post-step hooks
                for agent, result in results:
                    if result.outcome in (SkillOutcome.REJECTED, SkillOutcome.UNCERTAIN):
                        # REJECTED: no state change, no memory — only audit trace
                        if "post_step" in self.hooks:
                            self.hooks["post_step"](agent, result)
                        continue
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
        
        # Phase 32: Create Reproducibility Manifest
        import shutil
        import json
        manifest = {
            "model": self.config.model,
            "seed": self.config.seed,
            "num_years": iterations,
            "governance_profile": self.config.governance_profile,
            "agent_types_config": str(self.broker.model_adapter.config_path) if hasattr(self.broker.model_adapter, 'config_path') else "unknown"
        }
        
        # Copy configuration for future audit (with CLI overrides applied)
        if hasattr(self.broker.model_adapter, 'config_path') and self.broker.model_adapter.config_path:
            config_src = Path(self.broker.model_adapter.config_path)
            if config_src.exists():
                try:
                    import yaml
                    with open(config_src, 'r', encoding='utf-8') as f:
                        config_data = yaml.safe_load(f)
                    
                    # Inject CLI overrides so snapshot reflects actual run
                    if 'global_config' not in config_data:
                        config_data['global_config'] = {}
                    if 'llm' not in config_data['global_config']:
                        config_data['global_config']['llm'] = {}
                    
                    # Override model with actual CLI value
                    config_data['global_config']['llm']['model'] = self.config.model
                    
                    # Add metadata about this specific run
                    config_data['metadata'] = config_data.get('metadata', {})
                    config_data['metadata']['actual_model'] = self.config.model
                    config_data['metadata']['seed'] = self.config.seed
                    config_data['metadata']['governance_profile'] = self.config.governance_profile
                    
                    with open(self.config.output_dir / "config_snapshot.yaml", 'w', encoding='utf-8') as f:
                        yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
                except Exception as e:
                    # Fallback to simple copy if YAML processing fails
                    shutil.copy(config_src, self.config.output_dir / "config_snapshot.yaml")
        
        with open(self.config.output_dir / "reproducibility_manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)
            
        self.broker.auditor.save_summary(summary_path)

    def _apply_state_changes(self, agent: BaseAgent, result: Any):
        """Update agent attributes and memory from execution results.

        Also stores action context on agent._last_action_context for
        deferred feedback by domain pre_year hooks.
        """
        # 1. Update State Flags using canonical method
        if result.execution_result and result.execution_result.state_changes:
            agent.apply_delta(result.execution_result.state_changes)

        # 2. Store action context for deferred feedback by domain pre_year hooks
        action_ctx = {
            "skill_name": result.approved_skill.skill_name,
            "year": getattr(self, '_current_year', 0),
        }
        params = result.approved_skill.parameters or {}
        if params.get("magnitude_pct") is not None:
            action_ctx["magnitude_pct"] = params["magnitude_pct"]
            action_ctx["magnitude_fallback"] = params.get("magnitude_fallback", False)
        if result.execution_result and result.execution_result.action_context:
            action_ctx.update(result.execution_result.action_context)
        agent._last_action_context = action_ctx

        # 3. Legacy immediate memory (kept for backward compat; filtered by
        #    DecisionFilteredMemoryEngine in baseline parity experiments)
        action_desc = result.approved_skill.skill_name.replace("_", " ").capitalize()
        timestamp_prefix = f"Year {self._current_year}: " if hasattr(self, '_current_year') else ""
        memory_content = f"{timestamp_prefix}Decided to: {action_desc}"

        if hasattr(self.memory_engine, 'add_memory_for_agent'):
            self.memory_engine.add_memory_for_agent(agent, memory_content)
        else:
            self.memory_engine.add_memory(agent.id, memory_content)

    def _partition_by_phase(self, agents: List) -> List[List]:
        """Partition agents into ordered phases based on config.phase_order.

        Each entry in phase_order is a list of agent_type strings.
        Agents whose type matches a phase are grouped together.
        Any agents not matching any phase are appended at the end.
        """
        phase_order = self.config.phase_order or []
        phases: List[List] = [[] for _ in phase_order]
        unmatched = []

        type_to_phase = {}
        for idx, type_group in enumerate(phase_order):
            for atype in type_group:
                type_to_phase[atype] = idx

        for agent in agents:
            atype = getattr(agent, 'agent_type', 'default')
            if atype in type_to_phase:
                phases[type_to_phase[atype]].append(agent)
            else:
                unmatched.append(agent)

        if unmatched:
            phases.append(unmatched)
        return phases

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
            
            # [Efficiency Hub] Cognitive Cache Check
            ctx_builder = self.broker.context_builder
            # Build context early to compute hash
            context = ctx_builder.build(agent.id, env_context=env)
            context_hash = self.efficiency.compute_hash(context)
            
            cached_data = self.efficiency.get(context_hash)
            if cached_data:
                logger.info(f"[Efficiency] Cache HIT for {agent.id} (Hash={context_hash[:8]}). Bypassing LLM.")
                # Reconstruct result from cache
                
                # Restore reasoning metadata to ensure AuditWriter can find appraisals
                cached_proposal = cached_data.get("skill_proposal") or {}
                proposal = SkillProposal(
                    skill_name=cached_proposal.get("skill_name", "do_nothing"),
                    agent_id=agent.id,
                    reasoning=cached_proposal.get("reasoning", {}),
                    agent_type=cached_proposal.get("agent_type", "default")
                )
                
                # Basic reconstruction (Logic here should match SkillBrokerResult structure)
                result = SkillBrokerResult(
                    outcome=SkillOutcome(cached_data.get("outcome", "APPROVED")),
                    skill_proposal=proposal, # Restore proposal for audit
                    approved_skill=ApprovedSkill(
                        skill_name=cached_data.get("approved_skill", {}).get("skill_name", "do_nothing"),
                        agent_id=agent.id,
                        approval_status="APPROVED",
                        execution_mapping=cached_data.get("approved_skill", {}).get("mapping", "sim.noop")
                    ),
                    execution_result=ExecutionResult(
                        success=True,
                        state_changes=cached_data.get("execution_result", {}).get("state_changes", {})
                    ),
                    validation_errors=[],
                    retry_count=0
                )
                if hasattr(self.broker, "_run_validators"):
                    cached_proposal_obj = SkillProposal(
                        skill_name=cached_data.get("approved_skill", {}).get("skill_name", "do_nothing"),
                        agent_id=agent.id,
                        reasoning=cached_data.get("skill_proposal", {}).get("reasoning", {}),
                        agent_type=getattr(agent, 'agent_type', 'default')
                    )
                    val_results = self.broker._run_validators(cached_proposal_obj, context)
                    if not all(v.valid for v in val_results):
                        logger.warning(f"[Efficiency] Cache HIT for {agent.id} INVALIDATED by governance. Re-running.")
                        self.efficiency.invalidate(context_hash)
                    else:
                        results.append((agent, result))
                        continue
                else:
                    results.append((agent, result))
                    continue
            
            result = self.broker.process_step(
                agent_id=agent.id,
                step_id=self.step_counter,
                run_id=run_id,
                seed=self.config.seed + self.step_counter,
                llm_invoke=self.get_llm_invoke(getattr(agent, 'agent_type', 'default')),
                agent_type=getattr(agent, 'agent_type', 'default'),
                env_context=env
            )
            
            # Store validated result in cache
            if result.outcome in [SkillOutcome.APPROVED, SkillOutcome.RETRY_SUCCESS]:
                # We store the raw_output or structured decision
                self.efficiency.put(context_hash, result.to_dict())
            
            results.append((agent, result))
        return results

    def _run_agents_parallel(self, agents: List, run_id: str, llm_invoke: Callable, env: Dict) -> List:
        """Execute agent steps in parallel using ThreadPoolExecutor."""
        results = []
        
        def process_agent(agent, step_id):
            # [Efficiency Hub] Cognitive Cache Check
            ctx_builder = self.broker.context_builder
            context = ctx_builder.build(agent.id, env_context=env)
            context_hash = self.efficiency.compute_hash(context)
            
            cached_data = self.efficiency.get(context_hash)
            if cached_data:
                logger.info(f"[Efficiency:Parallel] Cache HIT for {agent.id} (Hash={context_hash[:8]}). Bypassing LLM.")
                
                cached_proposal = cached_data.get("skill_proposal") or {}
                proposal = SkillProposal(
                    skill_name=cached_proposal.get("skill_name", "do_nothing"),
                    agent_id=agent.id,
                    reasoning=cached_proposal.get("reasoning", {}),
                    agent_type=cached_proposal.get("agent_type", "default")
                )
                
                result = SkillBrokerResult(
                    outcome=SkillOutcome(cached_data.get("outcome", "APPROVED")),
                    skill_proposal=proposal,
                    approved_skill=ApprovedSkill(
                        skill_name=cached_data.get("approved_skill", {}).get("skill_name", "do_nothing"),
                        agent_id=agent.id,
                        approval_status="APPROVED",
                        execution_mapping=cached_data.get("approved_skill", {}).get("mapping", "sim.noop")
                    ),
                    execution_result=ExecutionResult(
                        success=True,
                        state_changes=cached_data.get("execution_result", {}).get("state_changes", {})
                    ),
                    validation_errors=[],
                    retry_count=0
                )
                if hasattr(self.broker, "_run_validators"):
                    cached_proposal_obj = SkillProposal(
                        skill_name=cached_data.get("approved_skill", {}).get("skill_name", "do_nothing"),
                        agent_id=agent.id,
                        reasoning=cached_data.get("skill_proposal", {}).get("reasoning", {}),
                        agent_type=getattr(agent, 'agent_type', 'default')
                    )
                    val_results = self.broker._run_validators(cached_proposal_obj, context)
                    if not all(v.valid for v in val_results):
                        logger.warning(f"[Efficiency:Parallel] Cache HIT for {agent.id} INVALIDATED by governance. Re-running.")
                        self.efficiency.invalidate(context_hash)
                    else:
                        return agent, result
                else:
                    return agent, result
            
            result = self.broker.process_step(
                agent_id=agent.id,
                step_id=step_id,
                run_id=run_id,
                seed=self.config.seed + step_id,
                llm_invoke=self.get_llm_invoke(getattr(agent, 'agent_type', 'default')),
                agent_type=getattr(agent, 'agent_type', 'default'),
                env_context=env
            )
            
            if result.outcome in [SkillOutcome.APPROVED, SkillOutcome.RETRY_SUCCESS]:
                self.efficiency.put(context_hash, result.to_dict())
                
            return agent, result
        
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
                    logger.error(f"[Parallel] Agent {futures[future].id} failed: {e}")
        
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

    def build(self) -> ExperimentRunner:
        # Complex assembly logic here
        from broker import SkillRegistry
        from broker import GenericAuditWriter, AuditConfig
        from broker.validators.agent import AgentValidator
        from broker.components.context_builder import create_context_builder
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
        from broker.components.memory_engine import seed_memory_from_agents
        seed_memory_from_agents(mem_engine, self.agents)
        
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
            # Also update MemoryProvider instances in the provider pipeline
            from broker.components.context_providers import MemoryProvider as _MemProv
            for provider in getattr(ctx_builder, 'providers', []):
                if isinstance(provider, _MemProv) and provider.engine is None:
                    provider.engine = mem_engine

        if hasattr(ctx_builder, 'semantic_thresholds'):
            ctx_builder.semantic_thresholds = getattr(self, 'semantic_thresholds', (0.3, 0.7))
        
        # PR 2 Fix: Inject memory_engine into InteractionHub if present in ctx_builder
        if hasattr(ctx_builder, 'hub') and ctx_builder.hub:
            ctx_builder.hub.memory_engine = mem_engine
        
        # Re-alignment: Inject skill_registry into TieredContextBuilder
        from broker.components.context_builder import TieredContextBuilder
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
