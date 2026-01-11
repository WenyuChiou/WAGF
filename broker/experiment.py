"""
Modular Experiment System - The "Puzzle" Architecture
Defined in PR 1.
"""
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, field
import random

from broker.skill_types import ApprovedSkill
from broker.skill_broker_engine import SkillBrokerEngine
from broker.context_builder import BaseAgentContextBuilder
from agents.base_agent import BaseAgent

@dataclass
class ExperimentConfig:
    """Configuration container for an experiment."""
    model: str
    num_years: int
    governance_profile: str = "default"
    output_dir: Path = Path("results")
    experiment_name: str = "modular_exp"
    seed: int = 42

class ExperimentRunner:
    """Engine that runs the simulation loop."""
    def __init__(self, 
                 broker: SkillBrokerEngine, 
                 sim_engine: Any, 
                 agents: Dict[str, BaseAgent], 
                 config: ExperimentConfig,
                 memory_window: int = 3,
                 hooks: Optional[Dict[str, Callable]] = None):
        self.broker = broker
        self.sim_engine = sim_engine
        self.agents = agents
        self.config = config
        self.step_counter = 0
        self.memory_window = memory_window
        self.hooks = hooks or {}

    def run(self, llm_invoke: Callable):
        """Standardized simulation loop."""
        run_id = f"exp_{random.randint(1000, 9999)}"
        print(f"Starting Experiment: {self.config.experiment_name} | Model: {self.config.model}")
        
        for year in range(1, self.config.num_years + 1):
            env = self.sim_engine.advance_year()
            print(f"--- Year {year} ---")
            
            # --- Lifecycle Hook: Pre-Year ---
            if "pre_year" in self.hooks:
                self.hooks["pre_year"](year, env, self.agents)
            
            active_agents = [a for a in self.agents.values() if not getattr(a, 'relocated', False)]
            
            for agent in active_agents:
                self.step_counter += 1
                result = self.broker.process_step(
                    agent_id=agent.id,
                    step_id=self.step_counter,
                    run_id=run_id,
                    seed=self.config.seed + self.step_counter,
                    llm_invoke=llm_invoke,
                )
                # Apply state changes
                if result.execution_result and result.execution_result.success:
                    self._apply_state_changes(agent, result)
                
                # --- Lifecycle Hook: Post-Step ---
                if "post_step" in self.hooks:
                    self.hooks["post_step"](agent, result)
                
                # Standard Memory Truncation
                if hasattr(agent, 'memory'):
                    agent.memory = agent.memory[-self.memory_window:]
            
            # --- Lifecycle Hook: Post-Year ---
            if "post_year" in self.hooks:
                self.hooks["post_year"](year, self.agents)
            
            self._finalize_year(year)

    def _apply_state_changes(self, agent: BaseAgent, result: Any):
        """Update agent attributes and memory from execution results."""
        # 1. Update State Flags
        changes = result.execution_result.state_changes
        for key, value in changes.items():
            setattr(agent, key, value)
        
        # 2. Update Memory (Action part)
        action_desc = result.approved_skill.skill_name.replace("_", " ").capitalize()
        agent.memory.append(f"Decided to: {action_desc}")

    def _finalize_year(self, year: int):
        # Notify audit writer to flush if needed
        if hasattr(self.broker.audit_writer, 'finalize'):
             # We don't finalize everything yet, maybe just per-year markers
             pass

class ExperimentBuilder:
    """Fluent API for assembling the experiment puzzle."""
    def __init__(self):
        self.model = "llama3.2:3b"
        self.num_years = 1
        self.profile = "default"
        self.agents = {}
        self.sim_engine = None
        self.skill_registry = None
        self.agent_types_path = None
        self.output_base = Path("results")
        self.ctx_builder = None
        self.memory_window = 3
        self.hooks = {}

    def with_model(self, model: str):
        self.model = model
        return self
    
    def with_context_builder(self, builder: Any):
        self.ctx_builder = builder
        return self

    def with_years(self, years: int):
        self.num_years = years
        return self

    def with_memory_window(self, window: int):
        self.memory_window = window
        return self

    def with_lifecycle_hooks(self, **hooks):
        """
        Register hooks: pre_year(year, env, agents), 
        post_step(agent, result), post_year(year, agents)
        """
        self.hooks.update(hooks)
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
        from broker.data_loader import load_agents_from_csv
        self.agents = load_agents_from_csv(path, mapping, agent_type)
        return self

    def with_simulation(self, sim_engine: Any):
        self.sim_engine = sim_engine
        return self
    
    def with_output(self, path: str):
        self.output_base = Path(path)
        return self

    def build(self) -> ExperimentRunner:
        # Complex assembly logic here
        from broker.skill_registry import SkillRegistry
        from broker.audit_writer import GenericAuditWriter, AuditConfig
        from validators import AgentValidator
        from broker.context_builder import create_context_builder
        
        # 1. Setup Skill Registry
        reg = self.skill_registry or SkillRegistry()
        
        # 2. Setup Context Builder
        ctx_builder = self.ctx_builder or create_context_builder(self.agents)
        
        # 3. Setup Audit
        audit_cfg = AuditConfig(
            output_dir=str(self.output_base / f"{self.model.replace(':','_')}_{self.profile}"),
            experiment_name=self.model
        )
        audit_writer = GenericAuditWriter(audit_cfg)
        
        # 4. Setup Validator & Adapter
        validator = AgentValidator(config_path=self.agent_types_path)
        from broker.model_adapter import UnifiedAdapter
        adapter = UnifiedAdapter(
            agent_type="household", 
            config_path=self.agent_types_path
        )
        
        # 5. Setup Broker
        broker = SkillBrokerEngine(
            skill_registry=reg,
            model_adapter=adapter,
            validators=[validator],
            simulation_engine=self.sim_engine,
            context_builder=ctx_builder,
            audit_writer=audit_writer
        )
        
        exp_config = ExperimentConfig(
            model=self.model,
            num_years=self.num_years,
            governance_profile=self.profile,
            output_dir=self.output_base
        )
        
        runner = ExperimentRunner(
            broker=broker, 
            sim_engine=self.sim_engine, 
            agents=self.agents, 
            config=exp_config,
            memory_window=self.memory_window,
            hooks=self.hooks
        )
        return runner
