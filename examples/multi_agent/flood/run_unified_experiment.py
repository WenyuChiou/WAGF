"""
Multi-Agent Unified Experiment Runner (v2.0)

Uses the core 'governed_broker_framework' to orchestrate:
- Institutional agents (Government, Insurance)
- Household agents (MG/NMG, Owner/Renter)
- Automated governance via config/ma_agent_types.yaml
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
from broker.components.context_providers import PerceptionAwareProvider
from broker.components.memory_engine import create_memory_engine
from broker.simulation.environment import TieredEnvironment
from cognitive_governance.agents import BaseAgent, AgentConfig, StateParam, Skill, PerceptionSource
from examples.multi_agent.flood.environment.hazard import HazardModule, VulnerabilityModule, YearMapping
from examples.multi_agent.flood.components.media_channels import MediaHub

# Local imports from multi_agent directory
MULTI_AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(MULTI_AGENT_DIR))
from generate_agents import generate_agents_random, load_survey_agents, HouseholdProfile
from initial_memory import generate_all_memories, get_agent_memories_text
from orchestration.agent_factories import create_government_agent, create_insurance_agent, wrap_household
from orchestration.lifecycle_hooks import MultiAgentHooks
import json


def _load_profiles_from_csv(csv_path: str) -> List[HouseholdProfile]:
    """Load HouseholdProfile objects from a CSV file (e.g. balanced agent output)."""
    from dataclasses import fields as dc_fields
    df = pd.read_csv(csv_path)
    profiles = []
    field_names = {f.name for f in dc_fields(HouseholdProfile)}
    for _, row in df.iterrows():
        kwargs = {}
        for col in df.columns:
            if col in field_names:
                val = row[col]
                # Handle pandas NaN → sensible defaults
                if pd.isna(val):
                    continue
                # Boolean columns saved as True/False strings
                field_type = next(f.type for f in dc_fields(HouseholdProfile) if f.name == col)
                if field_type == 'bool' or field_type is bool:
                    val = str(val).lower() in ('true', '1', 'yes')
                kwargs[col] = val
        profiles.append(HouseholdProfile(**kwargs))
    return profiles


def build_memory_engine(mem_cfg: Dict[str, Any], engine_type: str = "universal") -> MemoryEngine:
    """Create memory engine with optional SDK scorer."""
    scorer = None
    scorer_key = mem_cfg.get("scorer")
    if scorer_key:
        from cognitive_governance.v1_prototype.memory import get_memory_scorer
        scorer = get_memory_scorer(scorer_key)

    if engine_type == "humancentric":
        return HumanCentricMemoryEngine(
            window_size=mem_cfg.get("window_size", 3),
            top_k_significant=mem_cfg.get("top_k_significant", 2),
            consolidation_prob=mem_cfg.get("consolidation_probability", 0.7),
            decay_rate=mem_cfg.get("decay_rate", 0.1),
            scorer=scorer,
        )
    if engine_type == "hierarchical":
        from broker.components.memory_engine import HierarchicalMemoryEngine
        return HierarchicalMemoryEngine(
            window_size=mem_cfg.get("window_size", 5),
            semantic_top_k=mem_cfg.get("top_k_significant", 3),
            scorer=scorer,
        )
    if engine_type == "universal":
        return create_memory_engine(
            engine_type="universal",
            scorer=scorer,
            arousal_threshold=mem_cfg.get("arousal_threshold", 1.0),
        )
    return WindowMemoryEngine(
        window_size=mem_cfg.get("window_size", 3),
        scorer=scorer,
    )


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
    parser.add_argument("--mode", type=str, choices=["survey", "random", "balanced"], default="survey",
                        help="Agent initialization mode: survey (from questionnaire), random (synthetic), or balanced (4-cell from prepare_balanced_agents)")
    parser.add_argument("--agent-profiles", type=str, default=None,
                        help="Path to pre-generated agent profiles CSV (balanced mode)")
    parser.add_argument("--initial-memories-file", type=str, default=None,
                        help="Path to pre-generated initial memories JSON (balanced mode)")
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
    # Task-060 MA Enhancements
    parser.add_argument("--shuffle-skills", action="store_true",
                        help="Enable skill ordering randomization (Task-060B)")
    parser.add_argument("--enable-communication", action="store_true",
                        help="Enable MessagePool + GameMaster communication layer (Task-060D)")
    parser.add_argument("--enable-cross-validation", action="store_true",
                        help="Enable CrossAgentValidator echo chamber detection (Task-060E)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility")
    args = parser.parse_args()

    # Set random seed for reproducibility
    if args.seed is not None:
        random.seed(args.seed)
        print(f"[INFO] Random seed set to {args.seed}")
    
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
        "base_premium_rate": args.initial_premium,  # Immutable base for CRS calc
        "crs_discount": 0.0,  # CRS class discount (0-45%), Class 10 default
        "flood_occurred": False,
        "flood_depth_m": 0.0,
        "flood_depth_ft": 0.0,
        "year": 1,
        "govt_message": "The government is monitoring the situation.",
        "insurance_message": "Insurance rates are stable.",
        "loss_ratio": 0.0,  # Updated in post_year from claims/premiums
        # Generic crisis mechanism for TieredContextBuilder (Task-028)
        "crisis_event": False,
        "crisis_boosters": {},
        # Task-060B: Skill ordering randomization
        "_shuffle_skills": args.shuffle_skills,
    }
    tiered_env = TieredEnvironment(global_state=env_data)

    
    # 2. Setup agents (Gov + Ins + Households)
    gov = create_government_agent()
    ins = create_insurance_agent()

    # Load household profiles based on mode
    if args.mode == "survey":
        print("[INFO] Loading agents from survey data...")
        profiles = load_survey_agents()
    elif args.mode == "balanced":
        if not args.agent_profiles:
            # Default path: paper3/output/agent_profiles_balanced.csv
            default_profiles = MULTI_AGENT_DIR / "paper3" / "output" / "agent_profiles_balanced.csv"
            if default_profiles.exists():
                args.agent_profiles = str(default_profiles)
            else:
                print("[ERROR] Balanced mode requires --agent-profiles path or default file at paper3/output/agent_profiles_balanced.csv")
                print("[INFO] Run: python paper3/prepare_balanced_agents.py first")
                sys.exit(1)
        print(f"[INFO] Loading balanced agents from {args.agent_profiles}")
        profiles = _load_profiles_from_csv(args.agent_profiles)
        print(f"[INFO] Loaded {len(profiles)} balanced agent profiles")
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
    agent_cfg = AgentTypeConfig.load(MULTI_AGENT_DIR / "config" / "ma_agent_types.yaml")
    mem_cfg = agent_cfg.get_global_memory_config()
    if args.arousal_threshold is not None:
        mem_cfg["arousal_threshold"] = args.arousal_threshold
    if args.ema_alpha is not None:
        mem_cfg["ema_alpha"] = args.ema_alpha
    if args.stimulus_key is not None:
        mem_cfg["stimulus_key"] = args.stimulus_key

    memory_engine = build_memory_engine(mem_cfg, args.memory_engine)

    # 3a. Load initial memories (survey or balanced mode)
    initial_memories_path = None
    if args.mode == "balanced":
        if args.initial_memories_file:
            initial_memories_path = Path(args.initial_memories_file)
        else:
            # Default path for balanced mode
            default_mem = MULTI_AGENT_DIR / "paper3" / "output" / "initial_memories_balanced.json"
            if default_mem.exists():
                initial_memories_path = default_mem
    elif args.mode == "survey" and args.load_initial_memories:
        initial_memories_path = MULTI_AGENT_DIR / "data" / "initial_memories.json"

    if initial_memories_path and initial_memories_path.exists():
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
    elif initial_memories_path:
        print(f"[WARN] Initial memories file not found: {initial_memories_path}")
        if args.mode == "balanced":
            print("[INFO] Run: python paper3/prepare_balanced_agents.py first")
        else:
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
            seed=args.seed if args.seed is not None else 42
        )
        channels = []
        if args.enable_news_media:
            channels.append("news")
        if args.enable_social_media:
            channels.append("social_media")
        print(f"[INFO] Media channels enabled: {', '.join(channels)}")

    hub = InteractionHub(graph=graph, memory_engine=memory_engine, environment=tiered_env)

    # 3d. Communication Layer (Task-060D)
    message_pool = None
    game_master = None
    if args.enable_communication:
        from broker.components.message_pool import MessagePool
        from broker.components.coordinator import GameMaster, PassthroughStrategy
        message_pool = MessagePool(social_graph=graph)
        game_master = GameMaster(
            strategy=PassthroughStrategy(),
            message_pool=message_pool,
        )
        # Subscribe households to institutional announcements
        for aid, agent in all_agents.items():
            if getattr(agent, 'agent_type', '') in ["household_owner", "household_renter"]:
                message_pool.subscribe(aid, message_types=["policy_announcement", "market_update"])
        print("[INFO] Communication layer ENABLED: MessagePool + GameMaster")

    # 3e. Cross-Agent Validation (Task-060E)
    cross_validator = None
    if args.enable_cross_validation:
        from broker.validators.governance.cross_agent_validator import CrossAgentValidator
        cross_validator = CrossAgentValidator()
        if game_master:
            game_master.cross_validator = cross_validator
        print("[INFO] Cross-agent validation ENABLED (echo chamber + deadlock detection)")

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
        game_master=game_master,
        message_pool=message_pool,
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
                yaml_path=str(MULTI_AGENT_DIR / "config" / "ma_agent_types.yaml"),
                dynamic_whitelist=[
                    "govt_message",
                    "insurance_message",
                    "elevated_count",
                    "total_households",
                    "insured_count",
                    "loss_ratio",
                    "flood_depth_m",
                    "flood_depth_ft",
                    "mg_count",
                    "mg_ratio",
                    "mg_elevated_count",
                    "nmg_elevated_count",
                    "mg_insured_count",
                    "nmg_insured_count",
                ], # Phase 2 PR2: Allow institutional influence
                prompt_templates={}, # Loaded from YAML via with_governance
                enable_financial_constraints=args.enable_financial_constraints,
                extend_providers=[PerceptionAwareProvider()],  # LAST: perception filter
            )
        )
        .with_governance(
            profile="strict",
            config_path=str(MULTI_AGENT_DIR / "config" / "ma_agent_types.yaml")
        )
        .with_phase_order([
            ["government"],                           # Phase 1: NJDEP decides subsidy
            ["insurance"],                            # Phase 2: FEMA/NFIP decides premium
            ["household_owner", "household_renter"],  # Phase 3: Households decide adaptation
        ])
    )

    if args.enable_custom_affordability:
        builder.with_custom_validators([validate_affordability])
    
    # 6. Execute
    runner = builder.build()
    runner.run(runner.llm_invoke) # Use the selected llm_invoke


if __name__ == "__main__":
    run_unified_experiment()
