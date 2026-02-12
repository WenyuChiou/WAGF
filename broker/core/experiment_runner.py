"""
Experiment Runner — simulation loop engine.

Extracted from experiment.py (Phase 2.1 split).
"""
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, field
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from broker.agents import BaseAgent
from ..interfaces.skill_types import ApprovedSkill, SkillOutcome, SkillBrokerResult, ExecutionResult, SkillProposal
from ..interfaces.lifecycle_protocols import PreYearHook, PostStepHook, PostYearHook
from .skill_broker_engine import SkillBrokerEngine
from ..components.context.builder import BaseAgentContextBuilder
from ..components.memory.engine import MemoryEngine, WindowMemoryEngine, HierarchicalMemoryEngine
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

        # Validate hook signatures (warning only, non-breaking)
        _hook_protocols = {
            "pre_year": PreYearHook, "pre_step": PreYearHook,
            "post_step": PostStepHook,
            "post_year": PostYearHook, "post_step_end": PostYearHook,
        }
        for name, hook_fn in self.hooks.items():
            expected = _hook_protocols.get(name)
            if expected and not isinstance(hook_fn, expected):
                logger.warning(
                    f"[Lifecycle:Diagnostic] Hook '{name}' does not match "
                    f"{expected.__name__} protocol signature. "
                    f"See broker.interfaces.lifecycle_protocols for expected signatures."
                )

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
        """Create or return cached llm_invoke for a specific agent type.

        Supports per-type model names via ``llm_params.model`` in YAML:

        .. code-block:: yaml

            government:
              llm_params:
                model: llama3.3:70b   # overrides CLI --model for this type

        If ``model`` is not specified in ``llm_params``, the CLI/builder model
        (``self.config.model``) is used as fallback.
        """
        if agent_type not in self._llm_cache:
            from broker.utils.llm_utils import create_llm_invoke
            # Get parameters from config if available
            overrides = {}
            if hasattr(self.broker, 'config') and self.broker.config:
                overrides = self.broker.config.get_llm_params(agent_type)

            # Per-type model name: llm_params.model overrides CLI model.
            # Keep backward compatibility with legacy placeholder values.
            model_override = overrides.pop("model", None)
            if isinstance(model_override, str) and model_override.strip().lower() in {
                "",
                "command-line-override",
                "cli-override",
            }:
                model_override = None
            model_name = model_override or self.config.model

            self._llm_cache[agent_type] = create_llm_invoke(
                model_name,
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
                    # Wrap context the same way process_step() does for custom validators
                    cache_validation_context = {
                        "agent_state": context,
                        "agent_type": getattr(agent, 'agent_type', 'default'),
                        "env_state": env,
                        **context.get("state", {}),
                        **env
                    }
                    val_results = self.broker._run_validators(cached_proposal_obj, cache_validation_context)
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
                    # Wrap context the same way process_step() does for custom validators
                    cache_validation_context = {
                        "agent_state": context,
                        "agent_type": getattr(agent, 'agent_type', 'default'),
                        "env_state": env,
                        **context.get("state", {}),
                        **env
                    }
                    val_results = self.broker._run_validators(cached_proposal_obj, cache_validation_context)
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
