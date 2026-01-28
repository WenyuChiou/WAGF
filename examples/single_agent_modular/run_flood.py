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
from typing import Dict, Any, List, Optional, Tuple
import json

# Ensure project root is in sys.path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from broker.agents import BaseAgent, AgentConfig
from broker.components.skill_registry import SkillRegistry
from broker.components.simulation import ResearchSimulation as BaseSimulation # Renamed to avoid conflict
from broker.components.memory_engine import MemoryEngine, create_memory_engine
from broker.components.context_builder import TieredContextBuilder
from broker.components.interaction_hub import InteractionHub
from broker.components.social_graph import NeighborhoodGraph
from broker.components.audit_writer import AuditWriter
from broker.utils.llm_utils import create_legacy_invoke as create_llm_invoke
from broker.utils.agent_config import GovernanceAuditor

# Local modular components
from components.simulation import ResearchSimulation # Use the new simulation class
from components.memory_factory import create_memory_engine # Use the factory
from components.context_builder import FloodContextBuilder
from components.hooks import FloodHooks
from agents.loader import load_agents_from_csv, load_agents_from_survey
from analysis.plotting import plot_adaptation_results

# Mocking necessary SDK components for standalone execution if not available
try:
    from governed_ai_sdk.v1_prototype.memory import MemoryScorer, MemoryScore, MemoryPersistence
    from governed_ai_sdk.agents import BaseAgent, AgentConfig # Use SDK BaseAgent if available
except ImportError:
    print("WARNING: governed_ai_sdk not found. Using mock objects for MemoryScorer, MemoryScore, MemoryPersistence, BaseAgent, AgentConfig.")
    # Mock necessary SDK components if not available
    class MockSDKObject: pass
    MemoryScorer = MockSDKObject
    MemoryScore = MockSDKObject
    MemoryPersistence = MockSDKObject
    # Use broker's BaseAgent if SDK's is not available, ensure it's compatible
    if 'BaseAgent' not in locals():
        from broker.agents import BaseAgent # Fallback to broker's definition
    if 'AgentConfig' not in locals():
        from broker.agents import AgentConfig # Fallback to broker's definition

# Mocking Persistence for create_memory_engine factory example in docs
try:
    from governed_ai_sdk.v1_prototype.memory import create_persistence
except ImportError:
    def create_persistence(type, path):
        print(f"Mocking create_persistence for type={type}, path={path}")
        return None # Return None if SDK not available


def main():
    parser = argparse.ArgumentParser(description="SA Flood Experiment (Modular)")
    parser.add_argument("--model", type=str, default="llama3.2:3b")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--agents", type=int, default=100)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--memory-engine", type=str, default="universal",
                        choices=["window", "importance", "humancentric", "hierarchical", "universal"])
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--governance-mode", type=str, default="strict",
                        choices=["strict", "relaxed", "disabled"])
    parser.add_argument("--survey-mode", action="store_true")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    # Seed
    seed = args.seed or random.randint(0, 1000000)
    random.seed(seed)
    print(f"Using random seed: {seed}")

    # Paths
    base_path = Path(__file__).parent
    config_path = base_path / "agent_types.yaml"

    # Load config
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"ERROR: Config file not found at {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"ERROR: Failed to parse YAML config file: {e}")
        sys.exit(1)

    # Load agents (PLUGGABLE: edit agents/loader.py)
    if args.survey_mode:
        # Assuming survey data is located in a standard place relative to the experiment script
        survey_path = base_path / "input" / "initial_household data.xlsx"
        if not survey_path.exists():
            print(f"WARNING: Survey file not found at {survey_path}. Falling back to CSV loading.")
            survey_mode = False
        else:
            agents = load_agents_from_survey(survey_path, max_agents=args.agents, seed=seed)
            if not agents: # Handle case where survey loading returns empty
                print(f"ERROR: Failed to load agents from survey.")
                sys.exit(1)
    else:
        agents_csv_path = base_path / "agent_initial_profiles.csv"
        if not agents_csv_path.exists():
            print(f"ERROR: Agent profiles CSV not found at {agents_csv_path}. Please provide a valid path or use --survey-mode.")
            sys.exit(1)
        agents = load_agents_from_csv(agents_csv_path)
        if not agents: # Handle case where CSV loading returns empty
            print(f"ERROR: Failed to load agents from CSV.")
            sys.exit(1)
    
    # Load flood years
    flood_years_path = base_path / "flood_years.csv"
    if not flood_years_path.exists():
        print(f"WARNING: Flood years CSV not found at {flood_years_path}. Using default empty list.")
        flood_years = []
    else:
        try:
            flood_years_df = pd.read_csv(flood_years_path)
            flood_years = sorted(flood_years_df['Flood_Years'].tolist()) if 'Flood_Years' in flood_years_df.columns else []
        except Exception as e:
            print(f"ERROR: Could not read flood years from {flood_years_path}: {e}")
            flood_years = []

    # Create components (PLUGGABLE: edit respective files)
    sim = ResearchSimulation(agents, flood_years=flood_years, flood_mode="fixed") # Default to fixed flood years from file

    # Instantiate Memory Engine via factory
    persistence_instance = None # Placeholder for persistence, if needed
    try:
        # Example of using SDK persistence if available
        # from governed_ai_sdk.v1_prototype.memory import create_persistence
        # persistence_instance = create_persistence("json", output_dir / "memory_store")
        pass
    except ImportError:
        print("INFO: governed_ai_sdk.v1_prototype.memory not available, persistence disabled.")
        pass # Handle cases where SDK is not installed

    memory_engine = create_memory_engine(
        engine_type=args.memory_engine,
        config=config,
        window_size=args.window_size,
        persistence=persistence_instance # Pass persistence if created
    )

    registry = SkillRegistry()
    registry_path = base_path / "skill_registry.yaml"
    if not registry_path.exists():
        print(f"WARNING: Skill registry not found at {registry_path}. Skills might not be loaded correctly.")
        # Consider exiting or using a default registry if critical
    else:
        registry.register_from_yaml(str(registry_path))

    graph = NeighborhoodGraph(list(agents.keys()), k=4) # Assuming k=4 is default or from config
    hub = InteractionHub(graph)

    # Initialize FloodContextBuilder
    ctx_builder = FloodContextBuilder(
        agents=agents,
        hub=hub,
        sim=sim,
        skill_registry=registry,
        prompt_templates={"household": config.get('household', {}).get('prompt_template', '')},
        yaml_path=str(config_path),
        memory_top_k=args.window_size
    )

    # Output directory setup
    if args.output:
        output_dir = Path(args.output)
    else:
        model_name_safe = args.model.replace(':', '_').replace('/', '_') # Sanitize model name
        model_folder = f"{model_name_safe}_{args.governance_mode}"
        output_dir = base_path / "results" / model_folder
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build experiment runner
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
    hooks = FloodHooks(
        sim=sim,
        runner=runner,
        # Reflection engine would be configured via config or injected if available
        reflection_engine=None, # Placeholder
        output_dir=str(output_dir) # Ensure output_dir is a string for Path object
    )
    runner.hooks = {
        "pre_year": hooks.pre_year,
        "post_step": hooks.post_step,
        "post_year": hooks.post_year
    }

    # Run the simulation
    llm_invoke_func = create_llm_invoke(args.model, verbose=args.verbose)
    try:
        runner.run(llm_invoke=llm_invoke_func)
    except Exception as e:
        print(f"Simulation run failed: {e}")
        # Potentially add more error handling or logging here
        # For now, we'll let it propagate or handle finalization after the exception

    # Finalize audit logs
    if runner.broker.audit_writer:
        runner.broker.audit_writer.finalize()

    # Save logs
    csv_path = output_dir / "simulation_log.csv"
    try:
        pd.DataFrame(hooks.logs).to_csv(csv_path, index=False)
        print(f"Simulation log saved to: {csv_path}")
    except Exception as e:
        print(f"ERROR: Failed to save simulation log to {csv_path}: {e}")

    # Plot results (PLUGGABLE: edit analysis/plotting.py)
    try:
        plot_adaptation_results(csv_path, output_dir)
    except Exception as e:
        print(f"Plotting failed: {e}")

    # Print summary
    GovernanceAuditor().print_summary()
    print(f"--- Complete! Results in {output_dir} ---")


if __name__ == "__main__":
    main()
