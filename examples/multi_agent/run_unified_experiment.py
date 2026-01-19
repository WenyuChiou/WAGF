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
from typing import Dict, List, Any, Optional

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
from examples.multi_agent.environment.hazard import HazardModule, VulnerabilityModule

# Local imports from multi_agent directory
MULTI_AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(MULTI_AGENT_DIR))
from generate_agents import generate_agents_random, load_survey_agents, HouseholdProfile
from initial_memory import generate_all_memories, get_agent_memories_text
import json

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

def pmt_score_to_rating(score: float) -> str:
    """Convert PMT score (1-5) to descriptive rating."""
    if score >= 4.0:
        return "High"
    elif score >= 3.0:
        return "Moderate"
    elif score >= 2.0:
        return "Low"
    else:
        return "Very Low"


def wrap_household(profile: HouseholdProfile) -> BaseAgent:
    """Wrap HouseholdProfile as BaseAgent compatible with the framework."""
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
        "income_bracket": profile.income_bracket,
        "rcv_building": profile.rcv_building,
        "rcv_contents": profile.rcv_contents,
        "property_value": profile.rcv_building + profile.rcv_contents,
        "household_size": profile.household_size,
        "generations": profile.generations,
        # PMT constructs (from survey)
        "sc_score": profile.sc_score,
        "pa_score": profile.pa_score,
        "tp_score": profile.tp_score,
        "cp_score": profile.cp_score,
        "sp_score": profile.sp_score,
        # Spatial data
        "flood_zone": profile.flood_zone,
        "flood_depth": profile.flood_depth,
        "grid_x": profile.grid_x,
        "grid_y": profile.grid_y,
        # Flood experience
        "flood_experience": profile.flood_experience,
        "flood_frequency": profile.flood_frequency,
    }
    agent.dynamic_state = {
        "elevated": profile.elevated,
        "has_insurance": profile.has_insurance,
        "relocated": False,
        "cumulative_damage": 0.0,
        # Derived attributes for prompt
        "elevation_status_text": "Your house is elevated." if profile.elevated else "Your house is NOT elevated.",
        "insurance_status": "have" if profile.has_insurance else "do NOT have",
        # PMT ratings for prompt (descriptive)
        "tp_rating": pmt_score_to_rating(profile.tp_score),
        "cp_rating": pmt_score_to_rating(profile.cp_score),
        "sp_rating": pmt_score_to_rating(profile.sp_score),
        "sc_rating": pmt_score_to_rating(profile.sc_score),
        "pa_rating": pmt_score_to_rating(profile.pa_score),
        # Flood experience summary
        "flood_experience_summary": (
            f"Experienced {profile.flood_frequency} flood event(s)"
            if profile.flood_experience
            else "No direct flood experience"
        ),
    }

    # Ensure agent.id matches profile.agent_id
    agent.id = profile.agent_id

    return agent

# =============================================================================
# LIFECYCLE HOOKS
# =============================================================================

class MultiAgentHooks:
    def __init__(
        self,
        environment: Dict,
        memory_engine: Optional[MemoryEngine] = None,
        hazard_module: Optional[HazardModule] = None,
    ):
        self.env = environment
        self.memory_engine = memory_engine
        self.hazard = hazard_module or HazardModule()
        self.vuln = VulnerabilityModule()
    
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
        
        # Determine flood event using PRB grid (meters) as primary source
        event = self.hazard.get_flood_event(year=year)
        self.env["flood_occurred"] = event.depth_m > 0
        self.env["flood_depth_m"] = round(event.depth_m, 3)
        self.env["flood_depth_ft"] = round(event.depth_ft, 3)

        if self.env["flood_occurred"]:
            print(f" [ENV] !!! FLOOD WARNING for Year {year} !!! depth={event.depth_m:.2f}m")
        else:
            print(f" [ENV] Year {year}: No flood events.")

        # Calculate community statistics for Institutional perception
        households = [a for a in agents.values() if a.agent_type in ["household_owner", "household_renter"]]
        self.env["total_households"] = len(households)
        self.env["elevated_count"] = sum(1 for a in households if a.dynamic_state.get("elevated"))
        self.env["insured_count"] = sum(1 for a in households if a.dynamic_state.get("has_insurance"))
        # loss_ratio is calculated based on last year's damage if desired, or kept as a metric
        # For now, we'll keep it as a dynamic state of the insurance agent if it's already there

    def post_step(self, agent, result):
        """Update global vars if institutional agent acted."""
        if result.outcome.name != "SUCCESS":
            return
            
        decision = result.skill_proposal.skill_name
        
        # Mapping logic from Institutional choices to ENV values
        if agent.agent_type == "government":
            current = self.env["subsidy_rate"]
            if decision == "increase_subsidy":
                self.env["subsidy_rate"] = min(0.95, current + 0.05)
                self.env["govt_message"] = "The government has INCREASED the adaptation subsidy to support your safety."
            elif decision == "decrease_subsidy":
                self.env["subsidy_rate"] = max(0.20, current - 0.05)
                self.env["govt_message"] = "The government has DECREASED the subsidy due to budget constraints."
            else:
                self.env["govt_message"] = "The government is MAINTAINING the current subsidy rate."
            
        elif agent.agent_type == "insurance":
            current = self.env["premium_rate"]
            if decision == "raise_premium":
                self.env["premium_rate"] = min(0.15, current + 0.005)
                self.env["insurance_message"] = "Insurance premiums have been RAISED to ensure program solvency."
            elif decision == "lower_premium":
                self.env["premium_rate"] = max(0.01, current - 0.005)
                self.env["insurance_message"] = "Insurance premiums have been LOWERED due to favorable market conditions."
            else:
                self.env["insurance_message"] = "Insurance premiums remain UNCHANGED for now."

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
                agent.dynamic_state["pending_action"] = "buyout"
                agent.dynamic_state["action_completion_year"] = current_year + 2
                print(f" [LIFECYCLE] {agent.id} applied for buyout (finalizes Year {current_year + 2})")

            # Phase 3: Reasoning Gossip (SQ2) - Log reasoning to memory for others to hear
            if result.skill_proposal and result.skill_proposal.reasoning:
                reason = result.skill_proposal.reasoning.get("reasoning", "")
                if not reason:
                    # Generic fallback: search for any key with 'reason' in it
                    reason_key = next((k for k in result.skill_proposal.reasoning.keys() if "reason" in k.lower()), None)
                    reason = result.skill_proposal.reasoning.get(reason_key, "") if reason_key else ""
                
                if reason:
                    # MemoryEngine.add_memory is handled by ExperimentRunner, but we can add a specialized social trace
                    # For this experiment, we inject it into the memory engine via a hook or direct call if available
                    # Since ExperimentRunner will add the standard action memory, we add the qualitative 'social' memory here
                    mem_engine = getattr(self, 'memory_engine', None)
                    if mem_engine:
                        mem_engine.add_memory(
                            agent.id, 
                            f"I decided to {decision} because {reason}",
                            metadata={"source": "social", "type": "reasoning"}
                        )

    def post_year(self, year, agents, memory_engine):
        """Apply damage and consolidation."""
        if not self.env["flood_occurred"]:
            return

        depth_ft = self.env.get("flood_depth_ft", 0.0)
        if depth_ft <= 0:
            return
        total_damage = 0
        
        for agent in agents.values():
            if agent.agent_type not in ["household_owner", "household_renter"] or agent.dynamic_state.get("relocated"):
                continue
                
            rcv_building = agent.fixed_attributes["rcv_building"]
            rcv_contents = agent.fixed_attributes["rcv_contents"]
            damage_res = self.vuln.calculate_damage(
                depth_ft=depth_ft,
                rcv_building=rcv_building,
                rcv_contents=rcv_contents,
                is_elevated=agent.dynamic_state["elevated"],
            )
            damage = damage_res["total_damage"]
            
            agent.dynamic_state["cumulative_damage"] += damage
            total_damage += damage
            
            # Emotional memory
            memory_engine.add_memory(
                agent.id, 
                f"Year {year}: Flood depth {depth_ft:.1f}ft caused ${damage:,.0f} damage to my property.",
                metadata={"emotion": "fear", "source": "personal", "importance": 0.8}
            )
        
        print(f" [YEAR-END] Total Community Damage: ${total_damage:,.0f}")

# =============================================================================
# MAIN
# =============================================================================

def run_unified_experiment():
    parser = argparse.ArgumentParser(description="Multi-Agent Unified Experiment")
    parser.add_argument("--model", type=str, default="gpt-oss:latest", help="LLM model")
    parser.add_argument("--agents", type=int, default=10, help="Number of household agents (random mode only)")
    parser.add_argument("--years", type=int, default=10, help="Simulation years")
    parser.add_argument("--output", type=str, default="examples/multi_agent/results_unified")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose LLM output")
    parser.add_argument("--memory-engine", type=str, default="humancentric",
                        choices=["window", "humancentric", "hierarchical"],
                        help="Memory engine type")
    parser.add_argument("--gossip", action="store_true", help="Enable neighbor gossip (SQ2)")
    parser.add_argument("--initial-subsidy", type=float, default=0.50, help="Initial gov subsidy rate (SQ3)")
    parser.add_argument("--initial-premium", type=float, default=0.02, help="Initial insurance premium rate (SQ3)")
    parser.add_argument("--grid-dir", type=str, default=None, help="Path to PRB ASCII grid directory")
    parser.add_argument("--grid-years", type=str, default=None, help="Comma-separated PRB years to load (e.g. 2011,2012,2023)")
    parser.add_argument("--mode", type=str, choices=["survey", "random"], default="survey",
                        help="Agent initialization mode: survey (from questionnaire) or random (synthetic)")
    parser.add_argument("--load-initial-memories", action="store_true", default=True,
                        help="Load initial memories from initial_memories.json (survey mode)")
    parser.add_argument("--enable-custom-affordability", action="store_true",
                        help="Enable custom income-based affordability checks from experiment script.")
    parser.add_argument("--mock-response-file", type=str, default=None,
                        help="Path to a JSON file containing a mock response for the LLM.")
    args = parser.parse_args()
    
    # =============================================================================
    # CUSTOM VALIDATOR FUNCTIONS (Application-Specific)
    # =============================================================================

    from broker.interfaces.skill_types import ValidationResult, SkillProposal, ValidationLevel
    from typing import Tuple

    def validate_affordability(
        proposal: SkillProposal, 
        context: Dict[str, Any], 
        skill_registry: Any # Not used here, but part of standard signature
    ) -> List[ValidationResult]:
        """
        Application-specific financial affordability check for household agents.
        Returns a list of ValidationResult objects.
        """
        results = []

        if proposal.agent_type not in ["household_owner", "household_renter"]:
            return results # Only applies to household agents

        agent_data_from_builder = context.get('agent_state', {})
        fixed = agent_data_from_builder.get('personal', {}).get('fixed_attributes', {})
        env = context.get('env_state', {})

        income = fixed.get('income', 50000)
        subsidy_rate = env.get('subsidy_rate', 0.5)
        premium_rate = env.get('premium_rate', 0.02)
        property_value = fixed.get('property_value', 300000)
        
        decision = proposal.skill_name

        if decision == "elevate_house":
            cost = 150_000 * (1 - subsidy_rate)
            if cost > income * 3.0:
                results.append(ValidationResult(
                    valid=False,
                    validator_name="CustomAffordabilityValidator",
                    errors=[f"AFFORDABILITY: Cannot afford elevation (${cost:,.0f} > 3x income ${income*3:,.0f})"],
                    metadata={
                        "level": ValidationLevel.ERROR,
                        "rule": "affordability",
                        "field": "decision",
                        "constraint": "financial_affordability"
                    }
                ))

        if decision in ["buy_insurance", "buy_contents_insurance"]:
            premium = premium_rate * property_value
            if premium > income * 0.05:
                results.append(ValidationResult(
                    valid=False,
                    validator_name="CustomAffordabilityValidator",
                    errors=[f"AFFORDABILITY: Premium ${premium:,.0f} exceeds 5% of income ${income*0.05:,.0f})"],
                    metadata={
                        "level": ValidationLevel.ERROR,
                        "rule": "affordability",
                        "field": "decision",
                        "constraint": "financial_affordability"
                    }
                ))

        return results

    # 1. Init environment
    env_data = {
        "subsidy_rate": args.initial_subsidy,
        "premium_rate": args.initial_premium,
        "flood_occurred": False,
        "flood_depth_m": 0.0,
        "flood_depth_ft": 0.0,
        "year": 1,
        "govt_message": "The government is monitoring the situation.",
        "insurance_message": "Insurance rates are stable."
    }
    tiered_env = TieredEnvironment(global_state=env_data)

    
    # 2. Setup agents (Gov + Ins + Households)
    gov = create_government_agent()
    ins = create_insurance_agent()

    # Load household profiles based on mode
    if args.mode == "survey":
        print("[INFO] Loading agents from survey data...")
        profiles = load_survey_agents()
    else:
        print(f"[INFO] Generating {args.agents} random agents...")
        profiles = generate_agents_random(n_agents=args.agents)

    households = [wrap_household(p) for p in profiles]

    # Order: Institutional agents first
    all_agents = {a.id: a for a in [gov, ins] + households}

    # Calculate MG statistics for government prompt
    mg_count = sum(1 for p in profiles if p.mg)
    env_data["mg_count"] = mg_count
    env_data["mg_ratio"] = mg_count / len(profiles) if profiles else 0
    
    # 3. Memory Engine
    if args.memory_engine == "humancentric":
        memory_engine = HumanCentricMemoryEngine(window_size=3)
    elif args.memory_engine == "hierarchical":
        from broker.components.memory_engine import HierarchicalMemoryEngine
        memory_engine = HierarchicalMemoryEngine(window_size=5, semantic_top_k=3)
    else:
        memory_engine = WindowMemoryEngine(window_size=3)

    # 3a. Load initial memories (survey mode)
    if args.mode == "survey" and args.load_initial_memories:
        initial_memories_path = MULTI_AGENT_DIR / "data" / "initial_memories.json"
        if initial_memories_path.exists():
            print(f"[INFO] Loading initial memories from {initial_memories_path}")
            with open(initial_memories_path, 'r', encoding='utf-8') as f:
                initial_memories = json.load(f)
            # Inject initial memories into memory engine
            for agent_id, memories in initial_memories.items():
                if agent_id in all_agents:
                    for mem in memories:
                        memory_engine.add_memory(
                            agent_id,
                            mem["content"],
                            metadata={
                                "category": mem.get("category", "general"),
                                "importance": mem.get("importance", 0.5),
                                "source": mem.get("source", "survey"),
                                "year": 0  # Initial memories are pre-simulation
                            }
                        )
            print(f"[INFO] Loaded initial memories for {len(initial_memories)} agents")
        else:
            print(f"[WARN] Initial memories file not found: {initial_memories_path}")
            print("[INFO] Run initial_memory.py to generate initial memories")

    # 3b. Social & Interaction Hub
    agent_ids = list(all_agents.keys())
    if args.gossip:
        graph = create_social_graph("neighborhood", agent_ids, k=4)
    else:
        graph = create_social_graph("custom", agent_ids, edge_builder=lambda ids: []) # Isolated
        
    hub = InteractionHub(graph=graph, memory_engine=memory_engine, environment=tiered_env)
    
    # 4. Hooks
    grid_years = None
    if args.grid_years:
        grid_years = [int(y.strip()) for y in args.grid_years.split(",") if y.strip()]
    hazard_module = HazardModule(
        grid_dir=Path(args.grid_dir) if args.grid_dir else None,
        years=grid_years,
    )
    ma_hooks = MultiAgentHooks(
        tiered_env.global_state,
        memory_engine=memory_engine,
        hazard_module=hazard_module,
    )

    
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
                dynamic_whitelist=[
                    "govt_message",
                    "insurance_message",
                    "elevated_count",
                    "total_households",
                    "insured_count",
                    "loss_ratio",
                    "flood_depth_m",
                    "flood_depth_ft",
                ], # Phase 2 PR2: Allow institutional influence
                prompt_templates={} # Loaded from YAML via with_governance
            )
        )
        .with_governance(
            profile="strict", 
            config_path=str(MULTI_AGENT_DIR / "ma_agent_types.yaml")
        )
    )

    if args.enable_custom_affordability:
        builder.with_custom_validators([validate_affordability])
    
    # 6. Execute
    runner = builder.build()
    
    # Custom llm_invoke for mock model with response file
    if args.model == "mock" and args.mock_response_file:
        from broker.utils.llm_utils import create_llm_invoke
        from broker.interfaces.skill_types import SkillProposal
        from dataclasses import dataclass

        @dataclass
        class MockLLMStats:
            retries: int = 0
            success: bool = True

        mock_responses = []
        with open(args.mock_response_file, 'r') as f:
            for line in f:
                mock_responses.append(json.loads(line))

        def mock_llm_invoke(prompt: str):
            import re
            match = re.search(r"id: (\S+)", prompt)
            agent_id = match.group(1) if match else "unknown"

            # Find matching mock response
            for resp in mock_responses:
                if resp.get("agent_id") == agent_id:
                    # Determine agent type from response or default
                    agent_type = "default"
                    if "NJ_STATE" in agent_id:
                        agent_type = "government"
                    elif "FEMA_NFIP" in agent_id:
                        agent_type = "insurance"
                    elif "H" in agent_id:
                        # Simple check for household agent
                        agent_type = "household_owner"


                    return (SkillProposal(
                        skill_name=resp.get("skill_name"),
                        agent_id=resp.get("agent_id"),
                        reasoning=resp.get("reasoning"),
                        agent_type=agent_type
                    ), MockLLMStats())
            
            # Default response if no match
            return (SkillProposal(skill_name="do_nothing", agent_id=agent_id, reasoning={"reasoning": "default"}, agent_type="default"), MockLLMStats())

        llm_invoke_func = mock_llm_invoke
    else:
        llm_invoke_func = runner.llm_invoke
        
    runner.run(llm_invoke_func) # Use the selected llm_invoke


if __name__ == "__main__":
    run_unified_experiment()