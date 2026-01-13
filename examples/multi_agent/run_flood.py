
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
    
    def load_agents_from_excel(file_path, limit=50):
        # Read Sheet0 where the raw data resides
        df = pd.read_excel(file_path, sheet_name='Sheet0', header=None)
        # Row 0: Headers, Row 1: Queston Text, Data starts from Row 2 (Index 2)
        data_df = df.iloc[2:].copy()
        
        if limit and limit < len(data_df):
            data_df = data_df.sample(n=limit, random_state=42)
            
        loaded_agents = {}
        for idx, row in data_df.iterrows():
            a_id = f"Agent_{idx}"
            # Tenure check (Col 26 in Survey): 1=Own, 2=Rent
            tenure_val = row[26]
            a_type = "household_owner" if tenure_val == 1 else "household_renter"
            
            config = AgentConfig(
                name=a_id,
                agent_type=a_type,
                state_params=[], 
                objectives=[],
                constraints=[],
                skills=[],
                persona=f"A local {a_type.replace('household_', '')} participating in the flood survey."
            )
            agent = BaseAgent(config)
            
            # Map extended columns for Qualitative Grounding (Phase 21)
            agent.fixed_attributes = {
                "income_range": row[104],
                "housing_cost_burden": row[101],
                "occupation": row[102] if pd.notna(row[102]) else row[103],
                "residency_generations": row[30],
                "household_size": row[28],
                "education": row[96],
                "zip_code": row[105],
                # Flood Experience markers
                "flood_history": {
                    "has_experienced": str(row[34]).lower() == "yes",
                    "most_recent_year": row[35],
                    "significant_loss_year": row[37] if pd.notna(row[37]) else row[36],
                    "past_actions": row[40],
                    "received_assistance": str(row[39]).lower() == "yes"
                }
            }
            
            # Initial State (Minimalist)
            agent.dynamic_state = {
                "elevated": False,
                "has_insurance": False,
                "relocated": False,
                # Note: Trust/Budget normalized parameters are deprecated for prompts in Phase 21
                "flood_threshold": 0.5 
            }
            
            loaded_agents[a_id] = agent
        return loaded_agents

    # Initialize from raw Excel survey data
    agents = load_agents_from_excel("examples/multi_agent/input/initial_household data.xlsx", limit=agents_count)
    print(f" [Init] Loaded {len(agents)} households from raw Excel survey.")
    
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
        .with_verbose(verbose)
        .with_lifecycle_hooks(pre_step=pre_step, post_year=post_year_social)
        .build())
        
    print(" [Ready] Runner built. Starting simulation...")
    runner.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=20) # 20 Years for full scale
    parser.add_argument("--agents", type=int, default=50)
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()
    
    run_flood_interactive(model="mock", steps=args.steps, agents_count=args.agents, verbose=args.verbose)
