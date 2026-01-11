import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from broker.core.experiment import ExperimentBuilder
from broker.components.social_graph import NeighborhoodGraph
from broker.components.interaction_hub import InteractionHub
from broker.components.context_builder import TieredContextBuilder
from simulation.environment import TieredEnvironment
from examples.single_agent.run_experiment import FloodSimulation, GRANT_PROBABILITY
import random

def run_modular_approach(model: str = "llama3.2:3b", years: int = 10, agents_count: int = 100):
    print(f"--- Launching Modular Experiment: {model} ---")
    
    # 1. Initialize Simulation (World Layer)
    sim = FloodSimulation(num_agents=agents_count)
    agent_ids = list(sim.agents.keys())

    # [NEW] Lego Block: Legacy Parity Hook 🧪
    # Replicates exactly what the original run_experiment.py loop did
    # to ensure agents "remember" being flooded, which drives diversity.
    def legacy_parity_hook(context):
        if context.event == "pre_year":
            year = context.year
            env = sim.environment # Use legacy simulation environment
            
            # 1. Determine local flood event (Simulation already did this in advance_year)
            flood_event = env.get('flood_event', False)
            grant_available = random.random() < GRANT_PROBABILITY
            
            print(f" [Parity] Processing Year {year} | Flood: {flood_event} | Grants: {grant_available}")
            
            # 2. Update memory for all agents (Legacy Style)
            for agent in sim.agents.values():
                if getattr(agent, 'relocated', False): continue
                
                # Dynamic Damage Logic
                base_damage = 10000
                damage = base_damage * 0.1 if agent.elevated else base_damage
                
                if flood_event:
                    # Individual threshold check
                    if random.random() < agent.flood_threshold:
                        mem_text = f"Year {year}: Got flooded with ${damage:,.0f} damage on my house."
                    else:
                        mem_text = f"Year {year}: A flood occurred, but my house was spared damage."
                else:
                    mem_text = f"Year {year}: No flood occurred this year."
                
                # Add to memory engine
                runner.memory_engine.add_memory(agent.id, mem_text)
                
                if grant_available:
                    runner.memory_engine.add_memory(agent.id, f"Year {year}: Elevation grants are available.")

                # Force agent_type for correct logging/parsing
                agent.agent_type = "household"

    # 2. Setup Social Interaction Layer (PR 2)
    # Using NeighborhoodGraph (K=4) to simulate local street-level influence
    graph = NeighborhoodGraph(agent_ids, k=4)
    hub = InteractionHub(graph)
    
    # 3. Setup Tiered Context Builder (PR 2)
    # This automatically handles Tier 0 (Personal), Tier 1 (Local), and Tier 2 (Global)
    ctx_builder = TieredContextBuilder(
        agents=sim.agents,
        hub=hub,
        global_news=["City Council discusses new flood wall construction."]
    )

    # 4. Assemble the Experiment Using Fluent API (PR 1)
    builder = ExperimentBuilder()
    runner = (
        builder
        .with_model(model)
        .with_years(years)
        .with_agents(sim.agents)
        .with_simulation(sim)
        .with_context_builder(ctx_builder)
        .with_governance("strict", "examples/single_agent/agent_types.yaml")
        .with_output("results_modular")
        .with_hooks([legacy_parity_hook]) # <--- Replaced science model with parity logic
        .build()
    )

    # 5. LLM
    from examples.single_agent.run_experiment import create_llm_invoke
    llm_invoke = create_llm_invoke(model)

    # 6. Execute
    runner.run(llm_invoke=llm_invoke)
    print(f"--- Modular Experiment Complete! Results in results_modular ---")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run modular experiment approach.")
    parser.add_argument("--model", type=str, default="llama3.2:3b", help="LLM model name")
    parser.add_argument("--years", type=int, default=5, help="Number of years")
    parser.add_argument("--agents", type=int, default=10, help="Number of agents")
    
    args = parser.parse_args()
    run_modular_approach(model=args.model, years=args.years, agents_count=args.agents)
