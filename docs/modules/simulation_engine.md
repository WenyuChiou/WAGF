# Simulation Engine: The Physics of the World

**🌐 Language: [English](README.md) | [中文](README_zh.md)**

The `simulation/` directory handles the "Ground Truth" of the world. It manages time-stepping, environmental state (floods), and executes the physical consequences of agent actions.

## 🌍 Simulation Engine (`simulation_engine.py`)

This engine is the **Timekeeper** and **Physics Resolver**.

### Key Responsibilities

1.  **Time Stepping**: Advances the simulation year by year ($t \rightarrow t+1$).
2.  **External Shocks**: Injects flood events based on a probability distribution or external data.
3.  **Action Resolution**:
    - _Example_: If Agent A chooses `relocate`, the engine removes them from the active map and updates statistics.
    - _Sandboxing_: The engine ensures that an agent cannot modify another agent's property unless explicitly allowed (e.g., social influence).

---

## 🔌 External Model Integration

The framework is designed to couple with rigorous hydrological models.

### HEC-RAS / SWMM Coupling interface

To connect a real-time flood model:

1.  **Input**: The engine exports a `state_vector_t.json` (Agent Locations & Elevations).
2.  **Process**: Run your HEC-RAS script using this vector.
3.  **Output**: Import the resulting `flood_depth_map.csv`.
4.  **Update**: The `ContextBuilder` reads this map to generate next year's observations.

```python
# Example Pseudo-code for Coupling
def step_environment(self, year):
    # 1. Export Agent States
    self.export_agent_states(f"outputs/year_{year}/agents.json")

    # 2. Call External Model (e.g., HEC-RAS Wrapper)
    call_hec_ras(input="agents.json", return_map="depths.csv")

    # 3. Update Simulation Context
    self.flood_map = load_flood_map("depths.csv")
```

---

## ⚙️ Configuration & Parameters

The Physics and Loop settings.

| Parameter           | Type    | Default     | Recommended | Description                                                                         |
| :------------------ | :------ | :---------- | :---------- | :---------------------------------------------------------------------------------- |
| `simulation_years`  | `int`   | `10`        | `20+`       | How long the experiment runs. Longer runs allow "Reflection" to stabilize behavior. |
| `flood_probability` | `float` | `0.1`       | `0.1`       | Chance of a disaster in any given year (if using stochastic mode).                  |
| `output_dir`        | `str`   | `./results` | -           | Where `simulation_log.csv` and audit trails are saved.                              |

## 🔌 Experiment Connector: Putting It All Together

This is how you wire **Memory**, **Governance**, and **Simulation** into a single executable experiment.

### The "Main Loop" Pattern

Does the script `run.py` look complicated? It's just a loop:

```python
# 1. Setup Components
memory = HumanCentricMemoryEngine()
broker = SkillBroker()
sim = SimulationEngine()

# 2. Initialize Agents
agents = [Agent(id=i, memory=memory) for i in range(100)]

# 3. The Main Time Loop
for year in range(params.years):

    # A. Environment Step
    flood_depth = sim.get_flood_depth(year)

    # B. Agent Loop
    for agent in agents:
        # i. Observe (ContextBuilder)
        observation = context_builder.build(agent, flood_depth)

        # ii. Decide (Broker + LLM)
        action = broker.negotiate_action(agent, observation)

        # iii. Act (Simulation)
        sim.execute_action(agent, action)

    # C. Reflection (End of Year)
    if memory.type == 'human_centric':
        memory.run_reflection(agents)
```

## Multi-Phase Execution (Multi-Agent)

In multi-agent simulations, the flat `for agent in agents` loop is replaced by the `PhaseOrchestrator` (`broker/components/phase_orchestrator.py`), which coordinates agents by role and dependency order.

### Default Phase Order

| Phase | Role | Description |
| :---- | :--- | :---------- |
| 1. **INSTITUTIONAL** | Government, Insurance | Set policies, adjust premiums/subsidies before households decide |
| 2. **HOUSEHOLD** | Household agents | Make individual decisions (elevate, insure, relocate, do_nothing) |
| 3. **RESOLUTION** | GameMaster | Detect and resolve conflicts (resource over-allocation) |
| 4. **OBSERVATION** | All | Observe outcomes, update social networks |

Phases support configurable ordering per role: `sequential` (deterministic), `random` (shuffled), or `parallel`.

### GameMaster Coordination

The `GameMaster` (`broker/components/coordinator.py`) manages the RESOLUTION phase with pluggable strategies:

- **Passthrough**: Accept all proposals (single-agent default)
- **ConflictAware**: Detect resource conflicts using `ConflictDetector` and resolve via priority or proportional allocation
- **Custom**: User-defined resolution logic

### Conflict Resolution

The `ConflictDetector` (`broker/components/conflict_resolver.py`) detects resource over-allocation (e.g., more agents requesting government grants than the budget allows). Resolution strategies include `PriorityResolution` (highest-need agents first) and `ProportionalResolution` (distribute proportionally).

---

## 📝 Input / Output Examples

### Input: Initial Configuration

```yaml
n_agents: 50
years: 10
agent_distribution:
  subsidized_owners: 0.3
  regular_owners: 0.7
```

### Output: Simulation Log (`simulation_log.csv`)

| Year | AgentID | Event            | Action         | Outcome     | Wealth |
| :--- | :------ | :--------------- | :------------- | :---------- | :----- |
| 1    | 001     | No Flood         | do_nothing     | Stable      | 1000   |
| 2    | 001     | **FLOOD (1.5m)** | buy_insurance  | **Insured** | 900    |
| 3    | 001     | No Flood         | invest_measure | Protected   | 850    |

> **Analyst Note**: This CSV is your primary dataset for calculating "Adaptation Rates" and "Wealth Preservation".
