
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
from examples.multi_agent.world_models.grid_flood_model import GridFloodModel

def run_flood_interactive(model: str, steps: int = 5, agents_count: int = 50, verbose: bool = False, workers: int = 1):
    print(f"\n🌊 Starting Flood Multi-Agent Simulation (Agents={agents_count}, Steps={steps}, Workers={workers})")

    
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
            # Tenure check (Col 22: Housing Status)
            tenure_val = str(row[22]).lower() if pd.notna(row[22]) else ""
            base_type = "household_owner" if "own" in tenure_val else "household_renter"
            
            # --- MG Classification Logic (2 out of 3) ---
            # 1. Below Poverty Line (via 2D lookup)
            # row[28]: Size, row[104]: Income Range (1=<25k, 2=25-30k, 3=30-35k, 4=35-40k, 5=40-45k, 6=45-50k, 7=50-55k, 8=55-60k, 9=60-75k, 10=>75k)
            hh_size = int(row[28]) if pd.notna(row[28]) else 1
            inc_opt = int(row[104]) if pd.notna(row[104]) else 10 # Default to high income if missing
            
            is_poverty = False
            if hh_size == 1 and inc_opt <= 1: is_poverty = True
            elif hh_size == 2 and inc_opt <= 2: is_poverty = True
            elif hh_size == 3 and inc_opt <= 4: is_poverty = True
            elif hh_size == 4 and inc_opt <= 5: is_poverty = True
            elif hh_size == 5 and inc_opt <= 7: is_poverty = True
            elif (hh_size == 6 or hh_size == 7) and inc_opt <= 8: is_poverty = True
            elif hh_size >= 8 and inc_opt <= 9: is_poverty = True
            
            # 2. Housing Cost Burden (Col 101)
            # 1=Yes, 2=No
            is_burdened = (int(row[101]) == 1) if pd.notna(row[101]) else False
            
            # 3. Without Vehicle (Col 26)
            # 1=Yes (Owns), 2=No (Doesn't) -> MG if NO vehicle
            no_vehicle = (int(row[26]) == 2) if pd.notna(row[26]) else False
            
            # MG = 2 out of 3
            mg_score = (1 if is_poverty else 0) + (1 if is_burdened else 0) + (1 if no_vehicle else 0)
            is_mg = (mg_score >= 2)
            
            # Differentiate Agent Type for auditing
            a_type = f"{base_type}_{'mg' if is_mg else 'nmg'}"
            
            config = AgentConfig(
                name=a_id,
                agent_type=a_type,
                state_params=[], 
                objectives=[],
                constraints=[],
                skills=[],
                persona=f"A local {base_type.replace('household_', '')} participating in the flood survey. Group: {'Marginalized' if is_mg else 'Non-Marginalized'}."
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
                "is_mg": is_mg, # Explicitly store for tracking
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
                "has_contents_insurance": False,
                "relocated": False,
                "flood_threshold": 0.5,
                "current_premium": 1500, # Base premium estimate
                "last_premium": 1500,
                "historical_damage": 0,
                "historical_payout": 0
            }
            
            loaded_agents[a_id] = agent
        return loaded_agents

    # Initialize from raw Excel survey data
    agents = load_agents_from_excel("examples/multi_agent/input/initial_household data.xlsx", limit=agents_count)
    print(f" [Init] Loaded {len(agents)} households from raw Excel survey.")
    
    # Initialize Disaster Model & Project Agents
    flood_model = GridFloodModel()
    flood_model.project_agents(agents)
    print(f" [Init] Disaster Model: PRB Grid (Projected {len(agents)} agents to virtual locations)")

    # Create final graph with populated IDs
    social_graph = NetworkXAdapter(list(agents.keys()), nx_G)
    print(f" [Init] Social Network: Small World (Edges={nx_G.number_of_edges()})")
        
    # 4. Define Lifecycle Hooks
    
    def pre_step(step_year, env_context, agent_dict):
        """Update Global Policies and Trigger Flood Event."""
        print(f"\n--- Year {step_year} Institutional & World Evolution ---")
        
        # 1. Trigger Flood for the year
        # Note: step_year starts from 1, mapping to 2011 + (step-1)
        sim_year = 2011 + (step_year - 1)
        if sim_year > 2023:
             # Loop or stick to 2023 for long runs
             sim_year = 2023
             
        # Calculate local hazards for each agent
        flood_impacts = {}
        total_damage = 0
        for a_id, agent in agent_dict.items():
            zone = agent.dynamic_state.get("virtual_zone", "Safe")
            depth_m = flood_model.get_local_depth(zone, sim_year)
            depth_ft = flood_model.m_to_ft(depth_m)
            
            # Calculate FEMA damage if flood occurred
            damage_info = {"total_damage": 0}
            if depth_m > 0:
                # Assuming property value from survey or default 300k
                prop_val = 300000 
                damage_info = flood_model.calculate_damage(depth_m, prop_val, agent.dynamic_state.get("elevated", False))
                total_damage += damage_info["total_damage"]
            
            # Track history for context
            agent.dynamic_state["historical_damage"] = damage_info.get("total_damage", 0)
            agent.dynamic_state["historical_payout"] = damage_info.get("payout", 0)
            
            # Premium tracking
            last_premium = agent.dynamic_state.get("current_premium", 1500)
            current_premium = last_premium * (1 + env_context.get("premium_rate_change", 0))
            agent.dynamic_state["current_premium"] = current_premium
            agent.dynamic_state["last_premium"] = last_premium
            
            flood_impacts[a_id] = {
                "local_depth_ft": depth_ft,
                "damage_dollars": damage_info.get("total_damage", 0),
                "payout_dollars": damage_info.get("payout", 0),
                "current_premium": current_premium,
                "premium_change_pct": ((current_premium - last_premium) / last_premium) if last_premium > 0 else 0
            }
        
        # Inject into env_context for agent perception
        env_context["flood_impacts"] = flood_impacts
        env_context["sim_year"] = sim_year
        
        # 2. Institutional Updates
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
        
        # Government Act (NJ State Blue Acres)
        govt_dec = govt_agent.step(global_stats)
        print(f" [Govt] {govt_dec}")
        env_context["subsidy_rate"] = govt_dec["subsidy_level"]
        env_context["govt_message"] = govt_dec["message"]
        
        # Insurance Act (FEMA NFIP Risk Rating 2.0)
        ins_dec = insurance_agent.step(global_stats)
        print(f" [NIFP] {ins_dec}")
        env_context["premium_rate"] = ins_dec["premium_rate"]
        env_context["solvency_status"] = ins_dec["solvency_status"]

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
        dynamic_whitelist=["subsidy_rate", "premium_rate"] # Whitelist standardized vars
    )
    
    # 6. Execute Experiment using ExperimentBuilder
    builder = ExperimentBuilder("modular_exp")
    builder.with_agents(list(agents.values()))
    builder.with_context_builder(ctx_builder)
    builder.with_model(model)
    builder.with_pre_step_hook(pre_step)
    builder.with_post_step_hook(post_year_social)
    
    experiment = builder.build()
    results = experiment.run(steps=steps)
    
    print("\n✅ Simulation Complete.")
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flood Adaptation Multi-Agent Simulation")
    parser.add_argument("--steps", type=int, default=3, help="Number of years to simulate")
    parser.add_argument("--agents", type=int, default=20, help="Number of household agents")
    parser.add_argument("--model", type=str, default="llama3.2:3b", help="LLM model to use")
    parser.add_argument("--workers", type=int, default=2, help="Parallel workers")
    args = parser.parse_args()
    
    run_flood_interactive(model=args.model, steps=args.steps, agents_count=args.agents, workers=args.workers)
