"""
WAGF Quickstart Tier 2 — Governance in Action
===============================================
Demonstrates how governance rules validate LLM decisions:
  1. Agent proposes "take_action" -> APPROVED (first time)
  2. State changes: protected = True
  3. Agent proposes "take_action" again -> BLOCKED by "already_protected" rule
  4. Governance retry: LLM retries and picks "do_nothing" -> APPROVED

No Ollama required (uses mock LLM with state-aware responses).

Usage:
  python 02_governance.py
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

# --- 1. Agent with "protected" and "wealth" state ---
agent_cfg = AgentConfig(
    name="Agent_1",
    agent_type="simple_agent",
    state_params=[
        StateParam("protected", (0, 1), 0.0, "Whether agent is protected"),
        StateParam("wealth", (0, 200), 100.0, "Agent wealth"),
    ],
    objectives=[],
    constraints=[],
    skills=[
        Skill("take_action", "Take protective action", "protected", "increase"),
        Skill("do_nothing", "Wait and observe", None, "none"),
    ],
)
agents = {"Agent_1": BaseAgent(agent_cfg)}

# --- 2. Simulation that applies state changes ---
class GovernanceDemo:
    def __init__(self, agents):
        self.year = 0
        self.agents = agents

    def advance_year(self):
        self.year += 1
        return {
            "current_year": self.year,
            "situation": f"Year {self.year}: hazard warning active!",
            "hazard_warning": True,
        }

    def execute_skill(self, approved_skill):
        agent = self.agents.get(approved_skill.agent_id)
        if not agent:
            return ExecutionResult(success=False, error="Agent not found")
        if approved_skill.skill_name == "take_action":
            agent.dynamic_state["protected"] = True
            agent.dynamic_state["wealth"] -= 20
            return ExecutionResult(success=True, state_changes={"protected": True, "wealth": -20})
        return ExecutionResult(success=True, state_changes={})

# --- 3. Mock LLM: always proposes take_action (governance will block if invalid) ---
# NOTE: Responses MUST be valid JSON — the adapter parses with json.loads()
TAKE_ACTION = '{"decision": "take_action"}'
DO_NOTHING = '{"decision": "do_nothing"}'

call_count = 0
def mock_llm(prompt: str) -> str:
    global call_count
    call_count += 1
    # After a governance block, the prompt contains "BLOCKED" — switch to do_nothing
    if "BLOCKED" in prompt or "blocked" in prompt.lower():
        return DO_NOTHING
    return TAKE_ACTION

# --- 4. Build and run ---
script_dir = Path(__file__).resolve().parent

sim = GovernanceDemo(agents)
runner = (
    ExperimentBuilder()
    .with_model("mock")
    .with_years(4)
    .with_agents(agents)
    .with_simulation(sim)
    .with_skill_registry(str(script_dir / "skill_registry.yaml"))
    .with_memory_engine(WindowMemoryEngine(window_size=3))
    .with_governance("strict", str(script_dir / "agent_types.yaml"))
    .with_exact_output(str(script_dir / "results"))
    .with_workers(1)
    .with_seed(42)
).build()

# Inject custom mock LLM (runner ignores llm_invoke param, uses internal cache)
runner._llm_cache["simple_agent"] = mock_llm

def on_pre_year(year, env, agents):
    a = agents.get("Agent_1")
    protected = a.dynamic_state.get("protected", False) if a else "?"
    print(f"\n--- Year {year} --- (protected={protected})")

def on_post_step(agent, result):
    skill = getattr(result, "approved_skill", None)
    name = skill.skill_name if skill else "unknown"
    status = skill.approval_status if skill else "N/A"
    retries = getattr(result, "retry_count", 0)
    marker = f" [retried {retries}x]" if retries > 0 else ""
    print(f"  {agent.name}: {name} ({status}){marker}")

runner.hooks = {"pre_year": on_pre_year, "post_step": on_post_step}

# --- 5. Run ---
print("WAGF Quickstart — Governance in Action")
print("=" * 40)
print("Watch: Year 1 approves take_action. Year 2+ blocks it (already protected).")
print()
runner.run()
print(f"\nTotal LLM calls: {call_count} (includes retries after governance blocks)")
print("Done! The governance system prevented redundant protection.")
