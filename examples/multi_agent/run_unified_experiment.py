"""
Multi-Agent Unified Experiment Runner (v2.0)

Uses the core 'governed_broker_framework' to orchestrate:
- Institutional agents (Government, Insurance)
- Household agents (MG/NMG, Owner/Renter)
- Automated governance via ma_agent_types.yaml
- Environmental impacts via lifecycle hooks

Architecture:
1. Order: Gov/Insurer act first each year.
2. PostStepHook: Updates global subsidy/premium based on institutional decisions.
3. PostYearHook: Calculates damage and updates agent memories at year-end.
"""

import sys
import random
import argparse
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from broker import (
    ExperimentBuilder, 
    MemoryEngine, 
    WindowMemoryEngine, 
    HumanCentricMemoryEngine,
    TieredContextBuilder,
    InteractionHub,
    create_social_graph
)
from simulation.environment import TieredEnvironment
from agents.base_agent import BaseAgent, AgentConfig, StateParam, Skill, PerceptionSource

# Local imports from multi_agent directory
MULTI_AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(MULTI_AGENT_DIR))
from generate_agents import generate_agents

# =============================================================================
# INSTITUTIONAL AGENT FACTORIES
# =============================================================================

def create_government_agent() -> BaseAgent:
    config = AgentConfig(
        name="NJ_STATE",
        agent_type="government",
        state_params=[
            StateParam("subsidy_rate", (0.2, 0.95), 0.50, "Adaptation subsidy %"),
            StateParam("budget_remaining", (0, 1_000_000), 500_000, "Annual grant budget")
        ],
        objectives=[],
        constraints=[],
        skills=[
            Skill("increase_subsidy", "Raise subsidy rate", "subsidy_rate", "increase"),
            Skill("decrease_subsidy", "Lower subsidy rate", "subsidy_rate", "decrease"),
            Skill("maintain_subsidy", "Keep current rate", None, "none")
        ],
        perception=[
            PerceptionSource("environment", "env", ["year", "flood_occurred"])
        ],
        role_description="You represent the NJ State Government. Your goal is to support household adaptation while managing budget."
    )
    return BaseAgent(config)

def create_insurance_agent() -> BaseAgent:
    config = AgentConfig(
        name="FEMA_NFIP",
        agent_type="insurance",
        state_params=[
            StateParam("premium_rate", (0.01, 0.15), 0.02, "Flood insurance premium %"),
            StateParam("loss_ratio", (0, 2.0), 0.0, "Claims / Premiums ratio")
        ],
        objectives=[],
        constraints=[],
        skills=[
            Skill("raise_premium", "Increase premiums", "premium_rate", "increase"),
            Skill("lower_premium", "Decrease premiums", "premium_rate", "decrease"),
            Skill("maintain_premium", "Keep current rate", None, "none")
        ],
        perception=[
            PerceptionSource("environment", "env", ["year", "flood_occurred"])
        ],
        role_description="You represent FEMA/NFIP. Your goal is to maintain program solvency (RR 2.0)."
    )
    return BaseAgent(config)

# =============================================================================
# HOUSEHOLD AGENT WRAPPER
# =============================================================================

def wrap_household(profile) -> BaseAgent:
    # We map the profile to a BaseAgent compatible with the framework
    # Subdivide household into owner/renter for specialized prompts/skills
    ma_type = "household_owner" if profile.tenure == "Owner" else "household_renter"
    
    config = AgentConfig(
        name=profile.agent_id,
        agent_type=ma_type,
        state_params=[], 
        objectives=[],
        constraints=[],
        skills=[], # Loaded from YAML via SkillBrokerEngine
        perception=[
            PerceptionSource("environment", "env", ["year", "flood_occurred", "subsidy_rate", "premium_rate"])
        ]
    )
    agent = BaseAgent(config)
    
    # Store profile data in fixed/dynamic state
    agent.fixed_attributes = {
        "mg": profile.mg,
        "tenure": profile.tenure,
        "income": profile.income,
        "rcv_building": profile.rcv_building,
        "rcv_contents": profile.rcv_contents,
        "property_value": profile.rcv_building + profile.rcv_contents
    }
    agent.dynamic_state = {
        "elevated": profile.elevated,
        "has_insurance": profile.has_insurance,
        "relocated": False,
        "cumulative_damage": 0.0,
        # Derived attributes for prompt
        "elevation_status_text": "Your house is elevated." if profile.elevated else "Your house is NOT elevated.",
        "insurance_status": "have" if profile.has_insurance else "do NOT have"
    }
    
    # Ensure agent.id matches profile.agent_id
    agent.id = profile.agent_id
    
    return agent

# =============================================================================
# LIFECYCLE HOOKS
# =============================================================================

class MultiAgentHooks:
    def __init__(self, environment: Dict):
        self.env = environment
        self.flood_probability = 0.3
    
    def pre_year(self, year, env, agents):
        """Randomly determine if flood occurs and resolve pending actions."""
        self.env["year"] = year
        
        # Phase 30: Resolve Pending Actions (Elevation / Buyout)
        for agent in agents.values():
            if agent.agent_type not in ["household_owner", "household_renter"]:
                continue
            pending = agent.dynamic_state.get("pending_action")
            completion_year = agent.dynamic_state.get("action_completion_year")
            
            if pending and completion_year and year >= completion_year:
                if pending == "elevation":
                    agent.dynamic_state["elevated"] = True
                    print(f" [LIFECYCLE] {agent.id} elevation COMPLETE.")
                elif pending == "buyout":
                    agent.dynamic_state["relocated"] = True
                    print(f" [LIFECYCLE] {agent.id} buyout FINALIZED (left community).")
                # Clear pending state
                agent.dynamic_state["pending_action"] = None
                agent.dynamic_state["action_completion_year"] = None
        
        # Determine if flood occurs
        self.env["flood_occurred"] = random.random() < self.flood_probability
        
        if self.env["flood_occurred"]:
            print(f" [ENV] !!! FLOOD WARNING for Year {year} !!!")
        else:
            print(f" [ENV] Year {year}: No flood events.")

    def post_step(self, agent, result):
        """Update global vars if institutional agent acted."""
        if result.outcome.name != "SUCCESS":
            return
            
        decision = result.skill_proposal.skill_name
        
        # Mapping logic from Institutional choices to ENV values
        if agent.agent_type == "government":
            # Simple linear adjustment for demo (can be replaced by LLM 'adj' parsing)
            current = self.env["subsidy_rate"]
            if decision == "increase_subsidy":
                self.env["subsidy_rate"] = min(0.95, current + 0.05)
            elif decision == "decrease_subsidy":
                self.env["subsidy_rate"] = max(0.20, current - 0.05)
            # print(f" [GOV] Subsidy rate updated to: {self.env['subsidy_rate']:.0%}")
            
        elif agent.agent_type == "insurance":
            current = self.env["premium_rate"]
            if decision == "raise_premium":
                self.env["premium_rate"] = min(0.15, current + 0.005)
            elif decision == "lower_premium":
                self.env["premium_rate"] = max(0.01, current - 0.005)
            # print(f" [INS] Premium rate updated to: {self.env['premium_rate']:.1%}")

        # Sync household state after their decisions (buy_insurance, etc)
        # Phase 30: Pending Actions for multi-year lifecycle
        elif agent.agent_type in ["household_owner", "household_renter"]:
            current_year = self.env.get("year", 1)
            
            if decision in ["buy_insurance", "buy_contents_insurance"]:
                agent.dynamic_state["has_insurance"] = True  # Effective immediately
            elif decision == "elevate_house":
                # Elevation takes 1 year to complete
                agent.dynamic_state["pending_action"] = "elevation"
                agent.dynamic_state["action_completion_year"] = current_year + 1
                print(f" [LIFECYCLE] {agent.id} started elevation (completes Year {current_year + 1})")
            elif decision in ["relocate", "buyout_program"]:
                # Buyout/Relocation takes 2 years to finalize
                agent.dynamic_state["pending_action"] = "buyout"
                agent.dynamic_state["action_completion_year"] = current_year + 2
                print(f" [LIFECYCLE] {agent.id} applied for buyout (finalizes Year {current_year + 2})")

    def post_year(self, year, agents, memory_engine):
        """Apply damage and consolidation."""
        if not self.env["flood_occurred"]:
            return

        damage_factor = random.uniform(0.05, 0.20)
        total_damage = 0
        
        for agent in agents.values():
            if agent.agent_type not in ["household_owner", "household_renter"] or agent.dynamic_state.get("relocated"):
                continue
                
            # Calculation
            rcv = agent.fixed_attributes["rcv_building"] + agent.fixed_attributes["rcv_contents"]
            damage = rcv * damage_factor
            
            if agent.dynamic_state["elevated"]:
                damage *= 0.3 # 70% reduction
            
            agent.dynamic_state["cumulative_damage"] += damage
            total_damage += damage
            
            # Emotional memory
            memory_engine.add_memory(
                agent.id, 
                f"Year {year}: Flood caused ${damage:,.0f} damage to my property.",
                metadata={"emotion": "fear", "source": "personal", "importance": 0.8}
            )
        
        print(f" [YEAR-END] Total Community Damage: ${total_damage:,.0f}")

# =============================================================================
# MAIN
# =============================================================================

def run_unified_experiment():
    parser = argparse.ArgumentParser(description="Multi-Agent Unified Experiment")
    parser.add_argument("--model", type=str, default="gpt-oss:latest", help="LLM model")
    parser.add_argument("--agents", type=int, default=10, help="Number of household agents")
    parser.add_argument("--years", type=int, default=10, help="Simulation years")
    parser.add_argument("--output", type=str, default="examples/multi_agent/results_unified")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose LLM output")
    parser.add_argument("--memory-engine", type=str, default="humancentric", 
                        choices=["window", "humancentric", "hierarchical"], 
                        help="Memory engine type")
    parser.add_argument("--gossip", action="store_true", help="Enable neighbor gossip (SQ2)")
    parser.add_argument("--initial-subsidy", type=float, default=0.50, help="Initial gov subsidy rate (SQ3)")
    parser.add_argument("--initial-premium", type=float, default=0.02, help="Initial insurance premium rate (SQ3)")
    args = parser.parse_args()

    # 1. Init environment
    env_data = {
        "subsidy_rate": args.initial_subsidy,
        "premium_rate": args.initial_premium,
        "flood_occurred": False,
        "year": 1
    }
    tiered_env = TieredEnvironment(global_state=env_data)

    
    # 2. Setup agents (Gov + Ins + Households)
    gov = create_government_agent()
    ins = create_insurance_agent()
    
    profiles = generate_agents(n_agents=args.agents)
    households = [wrap_household(p) for p in profiles]
    
    # Order: Institutional agents first
    all_agents = {a.id: a for a in [gov, ins] + households}
    
    # 3. Memory Engine
    if args.memory_engine == "humancentric":
        memory_engine = HumanCentricMemoryEngine(window_size=3)
    elif args.memory_engine == "hierarchical":
        from broker.components.memory_engine import HierarchicalMemoryEngine
        memory_engine = HierarchicalMemoryEngine(window_size=5, semantic_top_k=3)
    else:
        memory_engine = WindowMemoryEngine(window_size=3)
    
    # 3b. Social & Interaction Hub
    agent_ids = list(all_agents.keys())
    if args.gossip:
        graph = create_social_graph("neighborhood", agent_ids, k=4)
    else:
        graph = create_social_graph("custom", agent_ids, edge_builder=lambda ids: []) # Isolated
        
    hub = InteractionHub(graph=graph, memory_engine=memory_engine, environment=tiered_env)
    
    # 4. Hooks
    ma_hooks = MultiAgentHooks(tiered_env.global_state)

    
    # 5. Build Experiment
    builder = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.years)
        .with_output(args.output)
        .with_verbose(args.verbose)
        .with_agents(all_agents)
        .with_memory_engine(memory_engine)
        .with_lifecycle_hooks(
            pre_year=ma_hooks.pre_year,
            post_step=ma_hooks.post_step,
            post_year=lambda year, agents: ma_hooks.post_year(year, agents, memory_engine)
        )
        .with_context_builder(
            TieredContextBuilder(
                agents=all_agents,
                hub=hub,
                memory_engine=memory_engine,
                prompt_templates={} # Loaded from YAML via with_governance
            )
        )
        .with_governance(
            profile="strict", 
            config_path=str(MULTI_AGENT_DIR / "ma_agent_types.yaml")
        )
    )
    
    # 6. Execute
    runner = builder.build()
    runner.run(runner.llm_invoke) # Standard framework invocation

if __name__ == "__main__":
    run_unified_experiment()
