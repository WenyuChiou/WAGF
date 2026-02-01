import sys
import os
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent.parent))

from broker import (
    ExperimentBuilder, BaseAgent, AgentConfig, 
    SkillRegistry, InteractionHub, create_social_graph
)
from broker.components.context_builder import create_context_builder, TieredContextBuilder
from broker.interfaces.skill_types import ExecutionResult

class DynamicFinanceEngine:
    """
    Unsteady State Finance Engine (V3).
    Supports Retail and Institutional skill execution.
    """
    def __init__(self, initial_price=100.0):
        self.price = initial_price
        self.trend = 0.005
        self.volatility = 0.03
        self.step = 0
        self.market_sentiment = 0.5
        self.news = "Market stable."

    def advance_step(self):
        self.step += 1
        change = random.gauss(self.trend, self.volatility)
        
        # Market Shock
        if random.random() < 0.15:
            shock = random.uniform(-0.15, -0.05) if random.random() < 0.6 else random.uniform(0.05, 0.15)
            change += shock
            self.news = "BREAKING: Economic shock detected!" if shock < 0 else "BREAKING: Positive earnings surge!"
        else:
            self.news = f"Step {self.step}: Trading within normal bounds."

        self.price *= (1 + change)
        self.market_sentiment = max(0.1, min(0.9, self.market_sentiment + (change * 2)))
        
        return {
            "market_price": round(self.price, 2),
            "sentiment_index": round(self.market_sentiment, 2),
            "news": self.news,
            "uncertainty": round(random.uniform(0.1, 0.5), 2)
        }

    def execute_skill(self, approved_skill):
        """Execute a trade with role-specific scaling."""
        action = approved_skill.skill_name
        lot_price = getattr(self, 'price', 100.0)
        state_changes = {}

        # Scale Factors: Bulk = 10x Retail
        if action == "buy":
            state_changes = {"cash_balance": -round(lot_price, 2), "shares": 1}
        elif action == "sell":
            state_changes = {"cash_balance": +round(lot_price, 2), "shares": -1}
        elif action == "buy_bulk":
            state_changes = {"cash_balance": -round(lot_price * 10.5, 2), "shares": 10} # Slight premium for liquidity
        elif action == "sell_bulk":
            state_changes = {"cash_balance": +round(lot_price * 9.5, 2), "shares": -10} # Slight discount
        elif action == "rebalance":
            # Just a placeholder for complex logic
            state_changes = {"last_action": "rebalanced", "transaction_cost": 50.0}
        
        return ExecutionResult(success=True, state_changes=state_changes, error=None)

def update_agent_perceived_state(agents, market_data, hub):
    """
    Update agents' psychological state based on Market + Social signals.
    'perceived_sentiment' = 60% Macro + 40% Peer Gossip average.
    """
    macro_sentiment = market_data["sentiment_index"]
    for aid, agent in agents.items():
        # Get gossip from hub (List of strings)
        gossip_list = hub.get_social_context(aid, agents)
        gossip = " ".join(gossip_list)
        
        # Simple heuristic: Peer influence
        # Peer sentiment extracted from gossip (mocked here or based on recent memory)
        peer_influence = 0.5 # Default neutral
        if "bullish" in gossip.lower(): peer_influence = 0.8
        elif "bearish" in gossip.lower(): peer_influence = 0.2
        
        # Blend: Macro + Social
        agent.perceived_sentiment = round((macro_sentiment * 0.6) + (peer_influence * 0.4), 2)
        
        # Standard updates
        agent.market_price = market_data["market_price"]
        agent.market_trend = market_data["news"]
        agent.sentiment_index = market_data["sentiment_index"]
        agent.uncertainty = market_data["uncertainty"]
        if hasattr(agent, 'shares'):
            agent.portfolio_value = round(agent.shares * agent.market_price, 2)
        agent.global_news = [market_data["news"]]

def run_heterogeneous_finance_sim():
    print("\n" + "="*60)
    print("   HETEROGENEOUS FINANCE SIMULATION: MULTI-AGENT & SOCIAL")
    print("="*60)
    
    base_path = Path(__file__).parent
    agent_types_path = str(base_path / "agent_types.yaml")
    skill_reg_path = str(base_path / "skill_registry.yaml")

    # 1. Setup Agents (Mixed Population)
    agents = {}
    
    # Retail Traders (7)
    for i in range(1, 8):
        aid = f"Retail_{i}"
        config = AgentConfig(name=aid, agent_type="retail_trader", state_params=[], objectives=[], constraints=[], skills=[])
        agent = BaseAgent(config)
        agent.cash_balance = round(random.uniform(3000, 7000), 2)
        agent.shares = random.randint(5, 15)
        agent.risk_tolerance = random.choice(["aggressive", "balanced", "conservative"])
        agent.perceived_sentiment = 0.5 # Initial
        agents[aid] = agent

    # Institutional Investors (3)
    for i in range(1, 4):
        aid = f"Insto_{i}"
        config = AgentConfig(name=aid, agent_type="institutional_investor", state_params=[], objectives=[], constraints=[], skills=[])
        agent = BaseAgent(config)
        agent.cash_balance = round(random.uniform(50000, 150000), 2)
        agent.shares = random.randint(100, 500)
        agent.risk_tolerance = "institutional"
        agent.perceived_sentiment = 0.5 # Initial
        agents[aid] = agent
    
    # 2. Social & Engines
    agent_ids = list(agents.keys())
    graph = create_social_graph("random", agent_ids, p=0.3, seed=42)
    hub = InteractionHub(graph=graph)
    market_engine = DynamicFinanceEngine()
    
    # 3. Context & Experiment
    ctx_builder = create_context_builder(agents=agents, yaml_path=agent_types_path, hub=hub)

    # Define lifecycle hook for state-perception sync
    def pre_step_hook(step, env_data, agents_map):
        update_agent_perceived_state(agents_map, env_data, hub)

    runner = (ExperimentBuilder()
        .with_model("llama3.2:3b")
        .with_agents(agents)
        .with_simulation(market_engine)
        .with_skill_registry(skill_reg_path)
        .with_governance("strict", agent_types_path)
        .with_context_builder(ctx_builder)
        .with_output("examples/finance/results_hetero")
        .with_steps(5)
        .with_verbose(True) # Force diagnostic logging
        .with_lifecycle_hooks(pre_step=pre_step_hook)
        .build())

    hub.memory_engine = runner.memory_engine

    # 4. Run
    print(f"Running simulation with {len(agents)} heterogeneous agents...")
    runner.run()
    
    print("\n[Done] Heterogeneous Finance Simulation finished.")
    print(f"Audit logs saved to: {runner.config.output_dir}")

if __name__ == "__main__":
    run_heterogeneous_finance_sim()
