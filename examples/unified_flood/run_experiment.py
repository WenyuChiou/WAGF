"""
Unified Flood Adaptation Experiment.

Demonstrates the SA/MA unified architecture (Task-040):
- UnifiedContextBuilder: Mode-based context building
- AgentInitializer: Survey/CSV/Synthetic initialization
- AgentTypeRegistry: Per-type configuration
- TypeValidator: Type-based skill validation
- PsychometricFramework: PMT/Utility/Financial frameworks

Usage:
    # SA mode (default)
    python run_experiment.py --mode single_agent --agents 10 --years 5

    # SA mode with social features
    python run_experiment.py --mode single_agent --enable-social --agents 10

    # MA mode with multiple agent types
    python run_experiment.py --mode multi_agent --enable-multi-type --agents 20

    # Different initialization modes
    python run_experiment.py --init-mode synthetic --agents 50
    python run_experiment.py --init-mode csv --csv-path agents.csv
"""
import sys
import yaml
import random
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Core broker components
from broker.core.experiment import ExperimentBuilder
from broker.components.social_graph import NeighborhoodGraph
from broker.components.interaction_hub import InteractionHub
from broker.components.skill_registry import SkillRegistry
from broker.utils.llm_utils import create_legacy_invoke as create_llm_invoke

# NEW: Unified architecture components (Task-040)
from broker.core.unified_context_builder import (
    UnifiedContextBuilder,
    TieredContextBuilder,
    create_unified_context_builder,
)
from broker.core.agent_initializer import (
    initialize_agents,
    AgentProfile,
)
from broker.config.agent_types import (
    AgentTypeRegistry,
    AgentTypeDefinition,
    PsychologicalFramework,
    get_default_registry,
)
from broker.core.psychometric import (
    get_framework,
    PMTFramework,
)
from broker.governance.type_validator import TypeValidator


def setup_registry_from_yaml(yaml_path: Path) -> AgentTypeRegistry:
    """
    Load agent type definitions from YAML.

    Supports the new unified schema with psychological frameworks.
    """
    registry = AgentTypeRegistry()

    if yaml_path.exists():
        registry.load_from_yaml(yaml_path)
        print(f"Loaded {len(registry)} agent types from {yaml_path.name}")
    else:
        # Use default registry
        registry = get_default_registry()
        print("Using default agent type registry")

    return registry


def create_simulation(agents: Dict[str, Any], flood_years: list):
    """Create simulation engine."""
    # Import from modular example for now
    try:
        from examples.single_agent_modular.components.simulation import ResearchSimulation
        return ResearchSimulation(agents, flood_years)
    except ImportError:
        # Fallback minimal simulation
        from broker.core.experiment import MinimalSimulation
        return MinimalSimulation(agents)


def main():
    parser = argparse.ArgumentParser(
        description="Unified Flood Experiment (Task-040 Architecture)"
    )

    # Mode configuration
    parser.add_argument("--mode", type=str, default="single_agent",
                        choices=["single_agent", "multi_agent"],
                        help="Experiment mode")
    parser.add_argument("--enable-social", action="store_true",
                        help="Enable social features (gossip, neighbor influence)")
    parser.add_argument("--enable-multi-type", action="store_true",
                        help="Enable multi-agent-type support")

    # Initialization
    parser.add_argument("--init-mode", type=str, default="synthetic",
                        choices=["synthetic", "csv", "survey"],
                        help="Agent initialization mode")
    parser.add_argument("--csv-path", type=str, default=None,
                        help="Path to CSV file (for csv init mode)")
    parser.add_argument("--survey-path", type=str, default=None,
                        help="Path to survey Excel file (for survey init mode)")

    # Experiment parameters
    parser.add_argument("--model", type=str, default="llama3.2:3b")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--agents", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default=None)

    # Memory and governance
    parser.add_argument("--memory-engine", type=str, default="unified",
                        choices=["window", "humancentric", "unified"])
    parser.add_argument("--governance-mode", type=str, default="strict",
                        choices=["strict", "relaxed", "disabled"])

    # Debug
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="Initialize components but don't run experiment")

    args = parser.parse_args()

    # Seed
    random.seed(args.seed)

    print("=" * 60)
    print("  Unified Flood Experiment (Task-040 Architecture)")
    print("=" * 60)
    print(f"Mode: {args.mode}")
    print(f"Social: {'enabled' if args.enable_social else 'disabled'}")
    print(f"Multi-type: {'enabled' if args.enable_multi_type else 'disabled'}")
    print(f"Init mode: {args.init_mode}")
    print(f"Agents: {args.agents}, Years: {args.years}, Seed: {args.seed}")
    print("=" * 60)

    # Paths
    base_path = Path(__file__).parent
    config_path = base_path / "agent_types.yaml"

    # ==========================================
    # Step 1: Load Agent Type Registry (NEW)
    # ==========================================
    print("\n[1] Loading Agent Type Registry...")
    registry = setup_registry_from_yaml(config_path)

    for type_id in registry.list_types():
        defn = registry.get(type_id)
        print(f"  - {type_id}: {defn.psychological_framework.value} framework, "
              f"{len(defn.eligible_skills)} skills")

    # ==========================================
    # Step 2: Initialize Agents (NEW)
    # ==========================================
    print(f"\n[2] Initializing agents ({args.init_mode} mode)...")

    init_config = {
        "num_agents": args.agents,
        "mg_ratio": 0.3,  # 30% minority group
        "owner_ratio": 0.7,  # 70% owners
    }

    path = None
    if args.init_mode == "csv" and args.csv_path:
        path = Path(args.csv_path)
    elif args.init_mode == "survey" and args.survey_path:
        path = Path(args.survey_path)

    profiles, initial_memories, stats = initialize_agents(
        mode=args.init_mode,
        path=path,
        config=init_config,
        seed=args.seed,
    )

    print(f"  Loaded {len(profiles)} agent profiles")
    print(f"  Stats: {stats}")

    # Convert profiles to agent dict
    agents = {p.agent_id: p.to_dict() for p in profiles}

    # ==========================================
    # Step 3: Setup Psychometric Framework (NEW)
    # ==========================================
    print("\n[3] Setting up Psychometric Framework...")

    # Get framework for household agents
    household_type = registry.get("household") or registry.get("household_owner")
    if household_type:
        framework_name = household_type.psychological_framework.value
        framework = get_framework(framework_name)
        print(f"  Framework: {framework.name}")
        print(f"  Constructs: {framework.get_construct_keys()}")
    else:
        framework = PMTFramework()
        print(f"  Using default PMT framework")

    # ==========================================
    # Step 4: Create Components
    # ==========================================
    print("\n[4] Creating experiment components...")

    # Flood years (sample)
    flood_years = [2, 4, 7]  # Years with flood events
    print(f"  Flood years: {flood_years}")

    # Simulation
    sim = create_simulation(agents, flood_years)

    # Skill registry
    skill_registry = SkillRegistry()
    skill_yaml = base_path / "skill_registry.yaml"
    if skill_yaml.exists():
        skill_registry.register_from_yaml(str(skill_yaml))
    else:
        # Use modular example's skill registry
        modular_skill_yaml = base_path.parent / "single_agent_modular" / "skill_registry.yaml"
        if modular_skill_yaml.exists():
            skill_registry.register_from_yaml(str(modular_skill_yaml))
    print(f"  Registered {len(skill_registry.skills)} skills")

    # Social graph and hub (optional)
    hub = None
    if args.enable_social:
        graph = NeighborhoodGraph(list(agents.keys()), k=4)
        hub = InteractionHub(graph)
        print(f"  Social graph: {len(agents)} nodes, k=4 neighbors")

    # ==========================================
    # Step 5: Create Unified Context Builder (NEW)
    # ==========================================
    print("\n[5] Creating Unified Context Builder...")

    # Load config for templates
    config = {}
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}

    context_builder = create_unified_context_builder(
        agents=agents,
        mode=args.mode,
        enable_social=args.enable_social,
        enable_multi_type=args.enable_multi_type,
        hub=hub,
        agent_type_registry=registry if args.enable_multi_type else None,
        skill_registry=skill_registry if args.enable_multi_type else None,
        prompt_templates={"household": config.get('household', {}).get('prompt_template', '')},
    )

    print(f"  Mode: {args.mode}")
    print(f"  Providers: {len(context_builder.providers)}")

    # ==========================================
    # Step 6: Setup Type Validator (NEW)
    # ==========================================
    print("\n[6] Setting up Type Validator...")

    type_validator = TypeValidator(registry=registry)
    print(f"  Validator ready with {len(registry)} agent types")

    # Demo validation
    demo_context = {
        "state": {"elevated": False, "tenure": "Owner"},
        "reasoning": {"TP_LABEL": "H", "CP_LABEL": "M"},
    }
    demo_results = type_validator.validate("elevate_house", "household", demo_context)
    print(f"  Demo validation (elevate_house, household): "
          f"{'PASS' if not demo_results else f'FAIL ({len(demo_results)} issues)'}")

    # ==========================================
    # Step 7: Output Setup
    # ==========================================
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = base_path / "results" / f"{args.mode}_{args.init_mode}"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[7] Output directory: {output_dir}")

    # ==========================================
    # Dry Run Check
    # ==========================================
    if args.dry_run:
        print("\n" + "=" * 60)
        print("  DRY RUN COMPLETE - Components initialized successfully")
        print("=" * 60)

        # Show sample context
        sample_agent = list(agents.keys())[0]
        sample_context = context_builder.build_context(sample_agent, year=1)
        print(f"\nSample context for {sample_agent}:")
        for key in ['agent_id', 'agent_type', 'attributes']:
            if key in sample_context:
                print(f"  {key}: {sample_context[key]}")

        return

    # ==========================================
    # Step 8: Build and Run Experiment
    # ==========================================
    print(f"\n[8] Building experiment...")

    # Memory engine
    from examples.single_agent_modular.components.memory_factory import create_memory_engine
    memory_engine = create_memory_engine(
        engine_type=args.memory_engine,
        config=config,
    )

    # Attach memory to hub if social enabled
    if hub:
        hub.memory_engine = memory_engine

    # Build experiment
    builder = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.years)
        .with_agents(agents)
        .with_simulation(sim)
        .with_context_builder(context_builder)
        .with_skill_registry(skill_registry)
        .with_memory_engine(memory_engine)
        .with_governance(args.governance_mode, config_path)
        .with_exact_output(str(output_dir))
        .with_seed(args.seed)
    )

    runner = builder.build()

    # Run
    print(f"\n{'=' * 60}")
    print(f"  Starting {args.years}-Year Simulation")
    print(f"{'=' * 60}\n")

    llm_invoke = create_llm_invoke(args.model, verbose=args.verbose)
    runner.run(llm_invoke=llm_invoke)

    # Finalize
    if runner.broker and hasattr(runner.broker, 'audit_writer') and runner.broker.audit_writer:
        runner.broker.audit_writer.finalize()

    print(f"\n{'=' * 60}")
    print(f"  Experiment Complete")
    print(f"  Results: {output_dir}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
