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
from examples.multi_agent.environment.hazard import HazardModule, VulnerabilityModule, YearMapping
from broker.components.media_channels import MediaHub

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
        "survey_id": profile.survey_id,
        "mg": profile.mg,
        "mg_criteria_met": profile.mg_criteria_met,
        "tenure": profile.tenure,
        "income": profile.income,
        "income_bracket": profile.income_bracket,
        "rcv_building": profile.rcv_building,
        "rcv_contents": profile.rcv_contents,
        "property_value": profile.rcv_building + profile.rcv_contents,
        "household_size": profile.household_size,
        "generations": profile.generations,
        "zipcode": profile.zipcode,
        "has_vehicle": profile.has_vehicle,
        "has_children": profile.has_children,
        "has_elderly": profile.has_elderly,
        "housing_cost_burden": profile.housing_cost_burden,
        "sfha_awareness": profile.sfha_awareness,
        # Spatial data
        "flood_zone": profile.flood_zone,
        "flood_depth": profile.flood_depth,
        "grid_x": profile.grid_x,
        "grid_y": profile.grid_y,
        # Flood experience
        "flood_experience": profile.flood_experience,
        "flood_frequency": profile.flood_frequency,
        "recent_flood_text": profile.recent_flood_text,
        "insurance_type": profile.insurance_type,
        "post_flood_action": profile.post_flood_action,
    }
    agent.dynamic_state = {
        "elevated": profile.elevated,
        "has_insurance": profile.has_insurance,
        "relocated": False,
        "cumulative_damage": 0.0,
        # Derived attributes for prompt
        "elevation_status_text": "Your house is elevated." if profile.elevated else "Your house is NOT elevated.",
        "insurance_status": "have" if profile.has_insurance else "do NOT have",
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

def depth_to_qualitative_description(depth_ft: float) -> str:
    """Converts flood depth in feet to a qualitative description."""
    if depth_ft <= 0:
        return "no flooding"
    elif depth_ft < 0.5:
        return "minor flooding (ankle-deep)"
    elif depth_ft < 2.0:
        return "significant flooding (knee-deep)"
    elif depth_ft < 5.0:
        return "severe flooding (first-floor inundation)"
    else:
        return "catastrophic flooding"

class MultiAgentHooks:
    def __init__(
        self,
        environment: Dict,
        memory_engine: Optional[MemoryEngine] = None,
        hazard_module: Optional[HazardModule] = None,
        media_hub: Optional[MediaHub] = None,
        per_agent_depth: bool = False,
        year_mapping: Optional[YearMapping] = None,
    ):
        self.env = environment
        self.memory_engine = memory_engine
        self.hazard = hazard_module or HazardModule()
        self.vuln = VulnerabilityModule()
        self.media_hub = media_hub
        self.per_agent_depth = per_agent_depth
        self.year_mapping = year_mapping or YearMapping()
        self.agent_flood_depths: Dict[str, float] = {}  # Per-agent flood depths for current year
    
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
        if self.per_agent_depth:
            # Per-agent flood depth based on grid position
            households = [a for a in agents.values() if a.agent_type in ["household_owner", "household_renter"]]
            agent_positions = {}
            for agent in households:
                fixed = agent.fixed_attributes or {}
                grid_x = fixed.get("grid_x", 0)
                grid_y = fixed.get("grid_y", 0)
                agent_positions[agent.id] = (grid_x, grid_y)

            # Get per-agent flood events
            flood_events = self.hazard.get_flood_events_for_agents(
                sim_year=year,
                agent_positions=agent_positions,
                year_mapping=self.year_mapping
            )
            self.agent_flood_depths = {aid: ev.depth_m for aid, ev in flood_events.items()}

            # Community-level stats (max depth for reporting)
            max_depth_m = max(self.agent_flood_depths.values()) if self.agent_flood_depths else 0.0
            avg_depth_m = sum(self.agent_flood_depths.values()) / len(self.agent_flood_depths) if self.agent_flood_depths else 0.0
            flooded_count = sum(1 for d in self.agent_flood_depths.values() if d > 0)

            self.env["flood_occurred"] = max_depth_m > 0
            self.env["flood_depth_m"] = round(max_depth_m, 3)  # Max for community reporting
            self.env["flood_depth_ft"] = round(max_depth_m * 3.28084, 3)
            self.env["avg_flood_depth_m"] = round(avg_depth_m, 3)
            self.env["flooded_household_count"] = flooded_count

            if self.env["flood_occurred"]:
                print(f" [ENV] !!! FLOOD WARNING for Year {year} !!! max_depth={max_depth_m:.2f}m, avg={avg_depth_m:.2f}m, flooded={flooded_count}/{len(households)}")
            else:
                print(f" [ENV] Year {year}: No flood events.")
        else:
            # Community-wide single depth (legacy mode)
            event = self.hazard.get_flood_event(year=year)
            self.env["flood_occurred"] = event.depth_m > 0
            self.env["flood_depth_m"] = round(event.depth_m, 3)
            self.env["flood_depth_ft"] = round(event.depth_ft, 3)
            self.agent_flood_depths = {}  # Clear per-agent depths

            if self.env["flood_occurred"]:
                print(f" [ENV] !!! FLOOD WARNING for Year {year} !!! depth={event.depth_m:.2f}m")
            else:
                print(f" [ENV] Year {year}: No flood events.")

        # Broadcast flood event to media channels (Task-022)
        if self.media_hub and self.env["flood_occurred"]:
            self.media_hub.broadcast_event({
                "flood_occurred": True,
                "flood_depth_m": self.env["flood_depth_m"],
                "affected_households": self.env.get("flooded_household_count", "multiple"),
            }, year)

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

        community_depth_ft = self.env.get("flood_depth_ft", 0.0)
        if community_depth_ft <= 0 and not self.agent_flood_depths:
            return

        total_damage = 0
        flooded_agents = 0

        for agent in agents.values():
            if agent.agent_type not in ["household_owner", "household_renter"] or agent.dynamic_state.get("relocated"):
                continue

            # Use per-agent depth if available, otherwise community-wide depth
            if self.per_agent_depth and agent.id in self.agent_flood_depths:
                depth_m = self.agent_flood_depths[agent.id]
                depth_ft = depth_m * 3.28084
            else:
                depth_ft = community_depth_ft
                depth_m = depth_ft / 3.28084

            if depth_ft <= 0:
                continue  # This agent wasn't flooded

            flooded_agents += 1
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

            # Emotional memory with agent-specific depth description
            description = depth_to_qualitative_description(depth_ft)
            memory_engine.add_memory(
                agent.id,
                f"Year {year}: We experienced {description} which caused about ${damage:,.0f} in damages.",
                metadata={"emotion": "fear", "source": "personal", "importance": 0.8}
            )

        if self.per_agent_depth:
            print(f" [YEAR-END] Total Community Damage: ${total_damage:,.0f} ({flooded_agents} households flooded)")
        else:
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
                        choices=["window", "humancentric", "hierarchical", "universal"],
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
    parser.add_argument("--enable-financial-constraints", action="store_true",
                        help="Enable income-based affordability checks in the validator.")
    parser.add_argument("--mock-response-file", type=str, default=None,
                        help="Path to a JSON file containing a mock response for the LLM.")
    # PRB Integration & Spatial Enhancement (Task-022)
    parser.add_argument("--neighbor-mode", type=str, choices=["ring", "spatial"], default="ring",
                        help="Neighbor graph mode: ring (K-nearest) or spatial (grid-based)")
    parser.add_argument("--neighbor-radius", type=float, default=3.0,
                        help="Connection radius in grid cells for spatial mode (default: 3 = ~90m)")
    parser.add_argument("--per-agent-depth", action="store_true",
                        help="Enable per-agent flood depth based on grid position")
    parser.add_argument("--enable-news-media", action="store_true",
                        help="Enable news media channel (delayed, high reliability)")
    parser.add_argument("--enable-social-media", action="store_true",
                        help="Enable social media channel (immediate, variable reliability)")
    parser.add_argument("--news-delay", type=int, default=1,
                        help="News media delay in turns (default: 1)")
    parser.add_argument("--arousal-threshold", type=float, default=None,
                        help="Universal engine: prediction error threshold for System 2 activation")
    parser.add_argument("--ema-alpha", type=float, default=None,
                        help="Universal engine: EMA alpha for expectation tracking")
    parser.add_argument("--stimulus-key", type=str, default=None,
                        help="Universal engine: env field used for surprise computation")
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
    from broker.utils.agent_config import AgentTypeConfig
    agent_cfg = AgentTypeConfig.load(MULTI_AGENT_DIR / "ma_agent_types.yaml")
    mem_cfg = agent_cfg.get_global_memory_config()
    if args.arousal_threshold is not None:
        mem_cfg["arousal_threshold"] = args.arousal_threshold
    if args.ema_alpha is not None:
        mem_cfg["ema_alpha"] = args.ema_alpha
    if args.stimulus_key is not None:
        mem_cfg["stimulus_key"] = args.stimulus_key

    if args.memory_engine == "humancentric":
        memory_engine = HumanCentricMemoryEngine(
            window_size=mem_cfg.get("window_size", 3),
            top_k_significant=mem_cfg.get("top_k_significant", 2),
            consolidation_prob=mem_cfg.get("consolidation_probability", 0.7),
            decay_rate=mem_cfg.get("decay_rate", 0.1)
        )
    elif args.memory_engine == "hierarchical":
        from broker.components.memory_engine import HierarchicalMemoryEngine
        memory_engine = HierarchicalMemoryEngine(
            window_size=mem_cfg.get("window_size", 5),
            semantic_top_k=mem_cfg.get("top_k_significant", 3)
        )
    else:
        memory_engine = WindowMemoryEngine(window_size=mem_cfg.get("window_size", 3))

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
        if args.neighbor_mode == "spatial":
            # Build spatial graph using agent grid positions
            positions = {}
            for agent in households:
                fixed = agent.fixed_attributes or {}
                grid_x = fixed.get("grid_x", 0)
                grid_y = fixed.get("grid_y", 0)
                positions[agent.id] = (grid_x, grid_y)
            # Institutional agents don't participate in spatial gossip
            graph = create_social_graph(
                "spatial",
                [a.id for a in households],  # Only households in spatial graph
                positions=positions,
                radius=args.neighbor_radius,
                metric="euclidean",
                fallback_k=2
            )
            print(f"[INFO] Using spatial neighbor graph (radius={args.neighbor_radius} cells)")
        else:
            graph = create_social_graph("neighborhood", agent_ids, k=4)
            print("[INFO] Using ring neighbor graph (k=4)")
    else:
        graph = create_social_graph("custom", agent_ids, edge_builder=lambda ids: []) # Isolated
        print("[INFO] Gossip disabled - isolated agents")

    # 3c. Media Hub (Task-022)
    media_hub = None
    if args.enable_news_media or args.enable_social_media:
        media_hub = MediaHub(
            enable_news=args.enable_news_media,
            enable_social=args.enable_social_media,
            news_delay=args.news_delay,
            seed=42
        )
        channels = []
        if args.enable_news_media:
            channels.append("news")
        if args.enable_social_media:
            channels.append("social_media")
        print(f"[INFO] Media channels enabled: {', '.join(channels)}")

    hub = InteractionHub(graph=graph, memory_engine=memory_engine, environment=tiered_env)
    
    # 4. Hooks
    grid_years = None
    if args.grid_years:
        grid_years = [int(y.strip()) for y in args.grid_years.split(",") if y.strip()]

    # Default grid_dir to project PRB data if not specified and per_agent_depth enabled
    grid_dir = args.grid_dir
    if args.per_agent_depth and not grid_dir:
        default_prb_path = MULTI_AGENT_DIR / "input" / "PRB"
        if default_prb_path.exists():
            grid_dir = str(default_prb_path)
            print(f"[INFO] Using default PRB data: {grid_dir}")
        else:
            print(f"[WARN] Per-agent depth enabled but no PRB data found at {default_prb_path}")

    hazard_module = HazardModule(
        grid_dir=Path(grid_dir) if grid_dir else None,
        years=grid_years,
    )

    # Create year mapping for PRB data
    year_mapping = YearMapping(start_sim_year=1, start_prb_year=2011)

    ma_hooks = MultiAgentHooks(
        tiered_env.global_state,
        memory_engine=memory_engine,
        hazard_module=hazard_module,
        media_hub=media_hub,
        per_agent_depth=args.per_agent_depth,
        year_mapping=year_mapping,
    )

    if args.per_agent_depth:
        print(f"[INFO] Per-agent flood depth ENABLED (PRB year mapping: sim 1 -> PRB 2011)")

    
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
                media_hub=media_hub,
                yaml_path=str(MULTI_AGENT_DIR / "ma_agent_types.yaml"),
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
                prompt_templates={}, # Loaded from YAML via with_governance
                enable_financial_constraints=args.enable_financial_constraints
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
    runner.run(runner.llm_invoke) # Use the selected llm_invoke


if __name__ == "__main__":
    run_unified_experiment()
