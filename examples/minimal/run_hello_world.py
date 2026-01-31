"""
SAGE Hello World — Minimal LLM-Governed Agent Example
======================================================
Demonstrates the core SAGE (Structured Agent Governance Engine) workflow:
  1. Define agents with state
  2. Register skills + governance rules
  3. Run a multi-step simulation where an LLM decides actions
  4. Governance validates decisions against physical constraints

Requires: Ollama running locally with a model (default: gemma3:4b)

Usage:
  python run_hello_world.py                    # uses gemma3:4b
  python run_hello_world.py --model llama3.2:3b
  python run_hello_world.py --model mock       # no LLM needed (testing)
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from broker.core.experiment import ExperimentBuilder
from broker.components.memory_engine import WindowMemoryEngine
from broker.utils.llm_utils import create_llm_invoke
from cognitive_governance.agents import BaseAgent, AgentConfig

# ---------- 1. Create agents ----------
def make_agents(n: int = 3):
    """Create N simple agents with initial state."""
    agents = {}
    for i in range(1, n + 1):
        config = AgentConfig(
            name=f"Agent_{i}",
            agent_type="simple_agent",
            state_params=[
                {"key": "protected", "value": False},
                {"key": "wealth", "value": 100},
            ],
            objectives=["Protect yourself from hazards"],
            constraints=[],
            skills=["take_action", "do_nothing"],
        )
        agent = BaseAgent(config)
        agents[agent.name] = agent
    return agents


# ---------- 2. Minimal simulation ----------
class MinimalSimulation:
    """A simple environment that tracks agent state."""

    def __init__(self, agents):
        self.year = 0
        self.agents = agents

    def advance_year(self):
        self.year += 1
        hazard = self.year % 3 == 0  # Hazard every 3rd year
        return {
            "current_year": self.year,
            "hazard_warning": hazard,
            "situation": (
                f"Year {self.year}. "
                + ("A hazard warning has been issued!" if hazard else "Conditions are calm.")
            ),
        }


# ---------- 3. Lifecycle hooks ----------
class SimpleHooks:
    """Log decisions to console."""

    def __init__(self, sim):
        self.sim = sim
        self.log = []

    def pre_year(self, year, env, agents):
        ctx = env if isinstance(env, dict) else {}
        warning = ctx.get("hazard_warning", False)
        print(f"\n--- Year {year} {'[HAZARD WARNING]' if warning else ''} ---")

    def post_step(self, agent, result):
        skill = getattr(result, "approved_skill", None)
        name = skill.skill_name if skill else "unknown"
        status = skill.approval_status if skill else "N/A"
        print(f"  {agent.name}: {name} ({status})")
        self.log.append({
            "year": self.sim.year,
            "agent": agent.name,
            "decision": name,
            "status": status,
        })

    def post_year(self, year, agents):
        for a in agents.values():
            state = a.state if hasattr(a, "state") else {}
            protected = state.get("protected", False)
            if protected:
                print(f"  >> {a.name} is now PROTECTED")


# ---------- 4. Main ----------
def main():
    parser = argparse.ArgumentParser(description="SAGE Hello World")
    parser.add_argument("--model", default="gemma3:4b", help="Ollama model ID")
    parser.add_argument("--years", type=int, default=5, help="Simulation years")
    parser.add_argument("--agents", type=int, default=3, help="Number of agents")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    agents = make_agents(args.agents)
    sim = MinimalSimulation(agents)
    hooks = SimpleHooks(sim)

    print(f"SAGE Hello World — {args.agents} agents × {args.years} years")
    print(f"Model: {args.model}")
    print("=" * 50)

    runner = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.years)
        .with_agents(agents)
        .with_simulation(sim)
        .with_skill_registry(str(script_dir / "skill_registry.yaml"))
        .with_memory_engine(WindowMemoryEngine(window_size=3))
        .with_governance("strict", str(script_dir / "agent_types.yaml"))
        .with_exact_output(str(script_dir / "results"))
        .with_workers(1)
        .with_seed(42)
    ).build()

    runner.hooks = {
        "pre_year": hooks.pre_year,
        "post_step": hooks.post_step,
        "post_year": hooks.post_year,
    }

    llm_invoke = create_llm_invoke(args.model, verbose=False)
    runner.run(llm_invoke=llm_invoke)

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    for entry in hooks.log:
        print(f"  Y{entry['year']}: {entry['agent']} -> {entry['decision']} ({entry['status']})")


if __name__ == "__main__":
    main()
