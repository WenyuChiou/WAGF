
"""
Run Flood Multi-Agent Simulation (Phase 18)
Interacts Government, Insurance, and Household agents with Social Network propagation.
"""
import sys
import argparse
from pathlib import Path
import random
import networkx as nx

# Adjust path to find broker modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from broker.core.experiment import ExperimentBuilder
from broker.components.context_builder import TieredContextBuilder, InteractionHub
from broker.components.memory_engine import HumanCentricMemoryEngine
from examples.multi_agent.flood_agents import NJStateAgent, FemaNfipAgent

def run_flood_interactive(model: str, steps: int = 5, agents_count: int = 50, verbose: bool = False):
    print(f"\n🌊 Starting Flood Multi-Agent Simulation (Agents={agents_count}, Steps={steps})")
    
    # 1. Initialize Institutional Agents
    govt_agent = NJStateAgent()
    insurance_agent = FemaNfipAgent()
    print(f" [Init] Government: {govt_agent.id}, Insurance: {insurance_agent.id}")
    
    # 2. Initialize Social Graph (Small World)
    # We use a custom adapter to bridge NetworkX -> SocialGraph
    from broker.components.social_graph import SocialGraph
    
    class NetworkXAdapter(SocialGraph):
        def __init__(self, agent_ids, nx_graph):
            super().__init__(agent_ids)
            # Map integer nodes to agent IDs
            # node 0 -> agent_ids[0]
            sorted_nodes = sorted(list(nx_graph.nodes()))
            id_map = {n: agent_ids[i] for i, n in enumerate(sorted_nodes)}
            
            for u, v in nx_graph.edges():
                self.add_edge(id_map[u], id_map[v])

    nx_G = nx.watts_strogatz_graph(n=agents_count, k=4, p=0.1)
    # Helper to get generic ID list since agents dict isn't filled yet
    temp_ids = [f"Agent_{i}" for i in range(agents_count)]
    
    # 3. Setup Experiment
    from agents.base_agent import BaseAgent, AgentConfig
    import pandas as pd
    
    def load_agents_from_csv(file_path, limit=50):
        df = pd.read_csv(file_path)
        if limit and limit < len(df):
            df = df.sample(n=limit, random_state=42)
            
        loaded_agents = {}
        for _, row in df.iterrows():
            a_id = row['id']
            # Map CSV to standard AgentConfig
            config = AgentConfig(
                name=a_id,
                agent_type="household",
                state_params=[], # Standard params defined in ma_agent_types.yaml
                objectives=[],
                constraints=[],
                skills=[],
                persona="A local resident concerned about flood risk."
            )
            agent = BaseAgent(config)
            
            # Populate internal state from CSV
            agent.dynamic_state = {
                "elevated": bool(row.get('elevated', False)),
                "has_insurance": bool(row.get('has_insurance', False)),
                "relocated": bool(row.get('relocated', False)),
                "trust_insurance": float(row.get('trust_in_insurance', 0.5)),
                "trust_neighbors": float(row.get('trust_in_neighbors', 0.5)),
                "flood_threshold": float(row.get('flood_threshold', 0.5))
            }
            # Initial Memory
            raw_mem = row.get('memory', "")
            if isinstance(raw_mem, str) and raw_mem.strip():
                agent.memory = [raw_mem]
            
            loaded_agents[a_id] = agent
        return loaded_agents

    # Initialize from real data
    agents = load_agents_from_csv("agent_initial_profiles.csv", limit=agents_count)
    print(f" [Init] Loaded {len(agents)} households from pre-processed profiles.")
    
    # Create final graph with populated IDs
    social_graph = NetworkXAdapter(list(agents.keys()), nx_G)
    print(f" [Init] Social Network: Small World (Edges={nx_G.number_of_edges()})")
        
    # 4. Define Lifecycle Hooks
    
    def pre_step(step_year, env_context, agent_dict):
        """Update Global Policies based on previous year stats."""
        print(f"\n--- Year {step_year} Institutional Update ---")
        
        # Calculate stats from agent states 
        relocated_count = sum(1 for a in agent_dict.values() if a.dynamic_state.get('relocated', False))
        elevated_count = sum(1 for a in agent_dict.values() if a.dynamic_state.get('elevated', False))
        
        claims_total = random.uniform(1000, 50000) # Mock claims for prototype
        
        global_stats = {
            "relocation_rate": relocated_count / len(agent_dict),
            "elevation_rate": elevated_count / len(agent_dict),
            "total_claims": claims_total,
            "total_premiums": 20000 
        }
        
        # Government Act
        govt_dec = govt_agent.step(global_stats)
        print(f" [Govt] {govt_dec}")
        env_context["subsidy_level"] = govt_dec["subsidy_level"]
        
        # Insurance Act
        ins_dec = insurance_agent.step(global_stats)
        print(f" [NIFP] {ins_dec}")
        env_context["premium_rate"] = ins_dec["premium_rate"]

    def post_year_social(step_year, agent_dict):
        """Propagate Social Influence (Gossip)."""
        print(f"--- Year {step_year} Social Propagation ---")
        
        # Access Memory Engine from Broker (via closure or passed arg? 
        # Standard hook signature doesn't pass broker, usually loop handles this.
        # But we can access agents' memory directly if using HumanCentric)
        
        # Mock Decision Propagation
        # For each edge (u, v), if u made a decision, tell v
        count = 0
        nodes = list(nx_G.nodes())
        for u, v in nx_G.edges():
            # Map node index to agent ID
            # Assuming standard ordering Agent_0...Agent_N matching nodes 0...N
            agent_u_id = f"Agent_{u}"
            agent_v_id = f"Agent_{v}"
            
            agent_u = agent_dict.get(agent_u_id)
            agent_v = agent_dict.get(agent_v_id)
            
            if agent_u and agent_v:
                # Simulating a decision event (In real code, check agent_u.last_decision)
                # Here we just inject a test gossip
                if random.random() < 0.1: # 10% chance to talk
                     msg = f"My neighbor {agent_u.id} is worried about floods."
                     # Inject into V's memory
                     # Note: In real integration, we should use the broker's memory_engine.
                     # But strictly, BaseAgent doesn't own the engine. 
                     # For this prototype script, we assume a globally accessible engine or mock it.
                     pass 
                     count += 1
        print(f" [Social] Propagated {count} gossip messages.")

    # Init Memory Engine
    memory_engine = HumanCentricMemoryEngine()

    # 5. Build Experiment
    # Using TieredContextBuilder with DynamicStateProvider
    ctx_builder = TieredContextBuilder(
        agents=agents,
        hub=InteractionHub(graph=social_graph, memory_engine=memory_engine),
        dynamic_whitelist=["subsidy_level", "premium_rate"] # Whitelist our dynamic vars
    )
    
    # We use NullSimulationEngine for valid structure but manual stepping logic above?
    # Actually ExperimentBuilder.build() returns a runner that calls lifecycle hooks.
    
    runner = (ExperimentBuilder()
        .with_model("mock-llm") # Use Mock for logic test
        .with_agents(agents)
        .with_context_builder(ctx_builder)
        .with_memory_engine(memory_engine) # Pass object, not string
        .with_governance("strict", "examples/multi_agent/ma_agent_types.yaml")
        .with_skill_registry("examples/single_agent/skill_registry.yaml")
        .with_steps(steps)
        .with_lifecycle_hooks(pre_step=pre_step, post_year=post_year_social)
        .build())
        
    print(" [Ready] Runner built. Starting simulation...")
    runner.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=20) # 20 Years for full scale
    parser.add_argument("--agents", type=int, default=50)
    args = parser.parse_args()
    
    run_flood_interactive(model="mock", steps=args.steps, agents_count=args.agents)
