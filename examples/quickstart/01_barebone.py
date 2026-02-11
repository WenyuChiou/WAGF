"""
WAGF Quickstart Tier 1 — Barebone Decision Loop
=================================================
Demonstrates the core WAGF workflow:
  Agent proposes a skill -> Broker validates -> Simulation executes

No Ollama required (uses mock LLM).

Usage:
  python 01_barebone.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from broker.core.experiment import ExperimentBuilder
from broker.components.memory_engine import WindowMemoryEngine
from broker.interfaces.skill_types import ExecutionResult
from broker.agents import BaseAgent, AgentConfig
from broker.agents.base import StateParam, Skill

# --- 1. One agent, two skills ---
agent_cfg = AgentConfig(
    name="Agent_1",
    agent_type="simple_agent",
    state_params=[
        StateParam("protected", (0, 1), 0.0, "Whether agent is protected"),
    ],
    objectives=[],
    constraints=[],
    skills=[
        Skill("take_action", "Take protective action", "protected", "increase"),
        Skill("do_nothing", "Wait and observe", None, "none"),
    ],
)
agents = {"Agent_1": BaseAgent(agent_cfg)}

# --- 2. Minimal simulation ---
class TinySimulation:
    def __init__(self):
        self.year = 0

    def advance_year(self):
        self.year += 1
        return {"current_year": self.year, "situation": f"Year {self.year}: calm conditions."}

    def execute_skill(self, approved_skill):
        return ExecutionResult(success=True, state_changes={})

# --- 3. Build experiment ---
script_dir = Path(__file__).resolve().parent

runner = (
    ExperimentBuilder()
    .with_model("mock")
    .with_years(3)
    .with_agents(agents)
    .with_simulation(TinySimulation())
    .with_skill_registry(str(script_dir / "skill_registry.yaml"))
    .with_memory_engine(WindowMemoryEngine(window_size=3))
    .with_governance("strict", str(script_dir / "agent_types.yaml"))
    .with_exact_output(str(script_dir / "results"))
    .with_workers(1)
    .with_seed(42)
).build()

# --- 4. Hooks: print decisions ---
def on_pre_year(year, env, agents):
    print(f"\n--- Year {year} ---")

def on_post_step(agent, result):
    skill = getattr(result, "approved_skill", None)
    name = skill.skill_name if skill else "unknown"
    status = skill.approval_status if skill else "N/A"
    print(f"  {agent.name}: {name} ({status})")

runner.hooks = {"pre_year": on_pre_year, "post_step": on_post_step}

# --- 5. Run (built-in mock LLM picks the first skill option) ---
print("WAGF Quickstart — Barebone Decision Loop")
print("=" * 40)
runner.run()
print("\nDone! Check examples/quickstart/results/ for audit CSV.")
