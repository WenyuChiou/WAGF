"""
WAGF Quickstart Tier 3 -- Multi-Agent with Phase Ordering
==========================================================
Demonstrates the key multi-agent features beyond the quickstart:
  - Two agent types: regulator (1) and farmer (6)
  - Phase ordering: regulator decides first, farmers react
  - Governance rules that cross agent types (warning blocks increase)
  - Lifecycle hooks for state injection and logging
  - Memory persistence across years

No Ollama required (uses mock LLM with state-aware responses).

Progression:
  01_barebone.py   -> 1 agent, 2 skills, no governance
  02_governance.py -> 1 agent, 2 skills, identity rule + retry
  03_multi_agent/  -> 7 agents, 5 skills, 2 types, phase ordering  <-- YOU ARE HERE

Usage:
  python run.py
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from broker.core.experiment import ExperimentBuilder
from broker.components.memory_engine import WindowMemoryEngine
from broker.interfaces.skill_types import ExecutionResult
from cognitive_governance.agents import BaseAgent, AgentConfig
from cognitive_governance.agents.base import StateParam, Skill

# -------------------------------------------------------------------
# 1. Create agents: 1 regulator + 6 farmers
# -------------------------------------------------------------------
def make_regulator():
    cfg = AgentConfig(
        name="Regulator",
        agent_type="regulator",
        state_params=[
            StateParam("warning_active", (0, 1), 0.0, "Whether a warning is issued"),
        ],
        objectives=[],
        constraints=[],
        skills=[
            Skill("issue_warning", "Issue conservation warning", "warning_active", "increase"),
            Skill("no_action", "No regulatory action", None, "none"),
        ],
    )
    return BaseAgent(cfg)


def make_farmer(farmer_id: int):
    cfg = AgentConfig(
        name=f"Farmer_{farmer_id}",
        agent_type="farmer",
        state_params=[
            StateParam("water_usage", (0, 100), 50.0, "Water usage units"),
            StateParam("warning_active", (0, 1), 0.0, "Synced from regulator"),
        ],
        objectives=[],
        constraints=[],
        skills=[
            Skill("increase_usage", "Increase water usage", "water_usage", "increase"),
            Skill("decrease_usage", "Decrease water usage", "water_usage", "decrease"),
            Skill("maintain_usage", "Keep current usage", None, "none"),
        ],
    )
    return BaseAgent(cfg)


agents = {"Regulator": make_regulator()}
for i in range(1, 7):
    agents[f"Farmer_{i}"] = make_farmer(i)


# -------------------------------------------------------------------
# 2. Simple basin simulation
# -------------------------------------------------------------------
class BasinSimulation:
    """Tracks a shared basin level that farmers draw from."""

    def __init__(self, agents, initial_level=80):
        self.agents = agents
        self.year = 0
        self.basin_level = initial_level  # percentage
        self.warning_active = False

    def advance_year(self):
        self.year += 1
        # Basin naturally replenishes 5% per year, but loses from usage
        total_usage = sum(
            a.dynamic_state.get("water_usage", 50)
            for a in self.agents.values()
            if a.agent_type == "farmer"
        )
        # Each farmer using 50 units is "neutral"; above that drains basin
        drain = (total_usage - 300) * 0.05  # 300 = 6 farmers x 50 neutral
        self.basin_level = max(0, min(100, self.basin_level - drain + 5))

        return {
            "current_year": self.year,
            "basin_level": round(self.basin_level, 1),
            "num_farmers": 6,
            "warning_active": self.warning_active,
            "warning_text": (
                "CONSERVATION WARNING: The regulator has issued a warning. "
                "You must not increase usage."
                if self.warning_active
                else "No conservation warnings are active."
            ),
        }

    def execute_skill(self, approved_skill):
        agent = self.agents.get(approved_skill.agent_id)
        if not agent:
            return ExecutionResult(success=False, error="Agent not found")

        name = approved_skill.skill_name
        if name == "issue_warning":
            self.warning_active = True
            agent.dynamic_state["warning_active"] = True
            return ExecutionResult(success=True, state_changes={"warning_active": True})

        elif name == "no_action":
            self.warning_active = False
            agent.dynamic_state["warning_active"] = False
            return ExecutionResult(success=True, state_changes={})

        elif name == "increase_usage":
            usage = agent.dynamic_state.get("water_usage", 50)
            agent.dynamic_state["water_usage"] = min(100, usage + 10)
            return ExecutionResult(success=True, state_changes={"water_usage": +10})

        elif name == "decrease_usage":
            usage = agent.dynamic_state.get("water_usage", 50)
            agent.dynamic_state["water_usage"] = max(0, usage - 10)
            return ExecutionResult(success=True, state_changes={"water_usage": -10})

        return ExecutionResult(success=True, state_changes={})


# -------------------------------------------------------------------
# 3. Mock LLM (state-aware)
# -------------------------------------------------------------------
call_count = 0


def mock_llm(prompt: str) -> str:
    """State-aware mock: regulator warns when basin is low,
    farmers decrease when warned, otherwise maintain."""
    global call_count
    call_count += 1

    # Regulator logic
    if "water basin regulator" in prompt.lower():
        for line in prompt.split("\n"):
            if "basin level" in line.lower() and "%" in line:
                try:
                    level = float(line.split(":")[1].strip().replace("%", "").split()[0])
                    if level < 50:
                        return json.dumps({"reasoning": "Basin is low", "decision": "issue_warning"})
                except (ValueError, IndexError):
                    pass
        return json.dumps({"reasoning": "Basin is adequate", "decision": "no_action"})

    # Farmer logic: if warned or governance-blocked, decrease
    if "conservation warning" in prompt.lower() and "must not" in prompt.lower():
        return json.dumps({"reasoning": "Warning active", "decision": "decrease_usage"})
    if "blocked" in prompt.lower():
        return json.dumps({"reasoning": "Correcting after block", "decision": "decrease_usage"})

    return json.dumps({"reasoning": "Conditions normal", "decision": "maintain_usage"})


# -------------------------------------------------------------------
# 4. Lifecycle hooks (use closure to access simulation object)
# -------------------------------------------------------------------
def make_hooks(sim):
    """Create hooks with a reference to the simulation object."""

    def pre_year(year, env, agents_dict):
        """Inject environment state into agent context for governance rules."""
        try:
            print(f"\n{'='*50}")
            print(f"  Year {year}  |  Basin: {sim.basin_level:.0f}%  |  Warning: {sim.warning_active}")
            print(f"{'='*50}")
        except UnicodeEncodeError:
            print(f"\n== Year {year} | Basin: {sim.basin_level:.0f}% | Warning: {sim.warning_active} ==")

        # Sync warning_active into each farmer's dynamic state
        # (so governance identity rule 'warning_active' can check it)
        for agent in agents_dict.values():
            if agent.agent_type == "farmer":
                agent.dynamic_state["warning_active"] = sim.warning_active

    def post_step(agent, result):
        """Log each agent's decision."""
        skill = getattr(result, "approved_skill", None)
        name = skill.skill_name if skill else "unknown"
        status = skill.approval_status if skill else "N/A"
        retries = getattr(result, "retry_count", 0)
        marker = f" [retried {retries}x]" if retries > 0 else ""

        if agent.agent_type == "regulator":
            print(f"  [REG] {agent.name}: {name} ({status}){marker}")
        else:
            usage = agent.dynamic_state.get("water_usage", "?")
            print(f"  [FRM] {agent.name}: {name} ({status}) -> usage={usage}{marker}")

    def post_year(year, agents_dict):
        """End-of-year summary."""
        usages = [
            a.dynamic_state.get("water_usage", 50)
            for a in agents_dict.values()
            if a.agent_type == "farmer"
        ]
        avg = sum(usages) / len(usages) if usages else 0
        print(f"  --- Summary: avg usage={avg:.0f}, basin={sim.basin_level:.0f}% ---")

    return {"pre_year": pre_year, "post_step": post_step, "post_year": post_year}


# -------------------------------------------------------------------
# 5. Build & run
# -------------------------------------------------------------------
if __name__ == "__main__":
    script_dir = Path(__file__).resolve().parent
    sim = BasinSimulation(agents, initial_level=80)

    runner = (
        ExperimentBuilder()
        .with_model("mock")
        .with_years(5)
        .with_agents(agents)
        .with_simulation(sim)
        .with_skill_registry(str(script_dir / "skill_registry.yaml"))
        .with_memory_engine(WindowMemoryEngine(window_size=5))
        .with_governance("strict", str(script_dir / "agent_types.yaml"))
        .with_phase_order([["regulator"], ["farmer"]])   # Phase ordering!
        .with_exact_output(str(script_dir / "results"))
        .with_workers(1)
        .with_seed(42)
    ).build()

    # Inject mock LLM for both agent types
    runner._llm_cache["regulator"] = mock_llm
    runner._llm_cache["farmer"] = mock_llm

    runner.hooks = make_hooks(sim)

    print("WAGF Quickstart -- Multi-Agent with Phase Ordering")
    print("=" * 50)
    print("Regulator decides first; farmers react to warnings.")
    print(f"Agents: 1 regulator + 6 farmers = {len(agents)} total")
    print()

    runner.run()

    print(f"\nTotal LLM calls: {call_count}")
    print("Done! Check examples/multi_agent_simple/results/ for audit CSV.")
