"""
SA Flood Adaptation Experiment - Modular Version.

Entry point that wires together pluggable components.
To modify any component, edit the corresponding file in components/ or agents/.
"""
import sys
import yaml
import random
import argparse
import pandas as pd
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from broker.core.experiment import ExperimentBuilder
from broker.components.social_graph import NeighborhoodGraph
from broker.components.interaction_hub import InteractionHub
from broker.components.skill_registry import SkillRegistry
from broker.components.observable_state import (
    ObservableStateManager,
    create_flood_observables,
)
from broker.components.context_providers import (
    ObservableStateProvider,
    EnvironmentEventProvider,
)
from broker.components.event_manager import EnvironmentEventManager
from broker.components.event_generators.flood import FloodEventGenerator, FloodConfig
from broker.utils.llm_utils import create_legacy_invoke as create_llm_invoke
from broker.utils.agent_config import GovernanceAuditor

# Add local path for modular components
sys.path.insert(0, str(Path(__file__).parent))

# Local modular components (use full path to avoid conflict with top-level agents/)
from examples.single_agent_modular.components.simulation import ResearchSimulation
from examples.single_agent_modular.components.memory_factory import create_memory_engine
from examples.single_agent_modular.components.context_builder import FloodContextBuilder
from examples.single_agent_modular.components.hooks import FloodHooks
from examples.single_agent_modular.agents.loader import load_agents_from_csv, load_agents_from_survey
from examples.single_agent_modular.analysis.plotting import plot_adaptation_results


def main():
    parser = argparse.ArgumentParser(description="SA Flood Experiment (Modular)")
    parser.add_argument("--model", type=str, default="llama3.2:3b")
    parser.add_argument("--years", type=int, default=10)
    parser.add_argument("--agents", type=int, default=100)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--memory-engine", type=str, default="window",
                        choices=["window", "importance", "humancentric", "hierarchical", "universal", "unified"])
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--governance-mode", type=str, default="strict",
                        choices=["strict", "relaxed", "disabled"])
    parser.add_argument("--survey-mode", action="store_true")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--memory-ranking-mode", type=str, default="legacy",
                        choices=["legacy", "weighted"])
    args = parser.parse_args()

    # Seed
    seed = args.seed or random.randint(0, 1000000)
    random.seed(seed)
    print(f"--- SA Flood Experiment (Modular) ---")
    print(f"Model: {args.model}, Years: {args.years}, Agents: {args.agents}, Seed: {seed}")

    # Paths
    base_path = Path(__file__).parent
    config_path = base_path / "agent_types.yaml"

    # Load config
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Load agents (PLUGGABLE: edit agents/loader.py)
    if args.survey_mode:
        survey_path = base_path.parent / "multi_agent" / "input" / "initial_household data.xlsx"
        agents = load_agents_from_survey(survey_path, max_agents=args.agents, seed=seed)
    else:
        agents = load_agents_from_csv(base_path / "agent_initial_profiles.csv")

    print(f"Loaded {len(agents)} agents")

    # Load flood years
    flood_years = sorted(pd.read_csv(base_path / "flood_years.csv")['Flood_Years'].tolist())
    print(f"Flood years: {flood_years}")

    # Create components (PLUGGABLE: edit respective files)
    sim = ResearchSimulation(agents, flood_years)

    memory_engine = create_memory_engine(  # Edit components/memory_factory.py
        engine_type=args.memory_engine,
        config=config,
        window_size=args.window_size,
        ranking_mode=args.memory_ranking_mode
    )

    registry = SkillRegistry()
    registry.register_from_yaml(str(base_path / "skill_registry.yaml"))

    graph = NeighborhoodGraph(list(agents.keys()), k=4)
    hub = InteractionHub(graph)
    hub.memory_engine = memory_engine

    # Setup observable state manager for cross-agent observation
    obs_manager = ObservableStateManager()
    obs_manager.register_many(create_flood_observables())
    obs_manager.set_neighbor_graph(graph)

    # Setup environment event manager for flood events
    event_manager = EnvironmentEventManager()
    flood_generator = FloodEventGenerator(FloodConfig(
        mode="fixed",
        fixed_years=flood_years,
    ))
    event_manager.register("flood", flood_generator)

    ctx_builder = FloodContextBuilder(  # Edit components/context_builder.py
        agents=agents,
        hub=hub,
        sim=sim,
        skill_registry=registry,
        prompt_templates={"household": config.get('household', {}).get('prompt_template', '')},
        yaml_path=str(config_path),
        memory_top_k=args.window_size
    )

    # Add providers for cross-agent observation and environment events
    if hasattr(ctx_builder, 'providers'):
        ctx_builder.providers.append(ObservableStateProvider(obs_manager))
        ctx_builder.providers.append(EnvironmentEventProvider(event_manager))

    # Output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        model_folder = f"{args.model.replace(':','_')}_{args.governance_mode}"
        output_dir = base_path / "results" / model_folder
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output: {output_dir}")

    # Build experiment
    builder = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.years)
        .with_agents(agents)
        .with_simulation(sim)
        .with_context_builder(ctx_builder)
        .with_skill_registry(registry)
        .with_memory_engine(memory_engine)
        .with_governance(args.governance_mode, config_path)
        .with_exact_output(str(output_dir))
        .with_seed(seed)
    )

    runner = builder.build()

    # Inject hooks (PLUGGABLE: edit components/hooks.py)
    hooks = FloodHooks(sim, runner, output_dir=output_dir, obs_manager=obs_manager, event_manager=event_manager)
    runner.hooks = {
        "pre_year": hooks.pre_year,
        "post_step": hooks.post_step,
        "post_year": hooks.post_year
    }

    # Run
    print(f"\n=== Starting {args.years}-Year Simulation ===\n")
    runner.run(llm_invoke=create_llm_invoke(args.model, verbose=args.verbose))

    # Finalize
    if runner.broker and hasattr(runner.broker, 'audit_writer') and runner.broker.audit_writer:
        runner.broker.audit_writer.finalize()

    # Save logs
    csv_path = output_dir / "simulation_log.csv"
    pd.DataFrame(hooks.logs).to_csv(csv_path, index=False)
    print(f"\nSaved logs to {csv_path}")

    # Plot (PLUGGABLE: edit analysis/plotting.py)
    plot_adaptation_results(csv_path, output_dir)

    # Summary
    GovernanceAuditor().print_summary()
    print(f"\n--- Complete! Results in {output_dir} ---")


if __name__ == "__main__":
    main()
