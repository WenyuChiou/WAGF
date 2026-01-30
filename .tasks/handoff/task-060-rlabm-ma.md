# Task-060: RL-ABM Multi-Agent Irrigation Experiment

**Status**: `planning`
**Owner**: Claude Code (Planner) + Antigravity (Executor)
**Priority**: HIGH
**Created**: 2026-01-29T22:38:00Z

---

## Objective

Adapt the **Hung 2021 RL-ABM-CRSS** framework (Reinforcement Learning Agent-Based Modeling) for use with the **Governed Broker Framework** to study adaptive irrigation decision-making under climate uncertainty.

---

## Source Paper

**Citation**: Hung, F., & Yang, Y. C. E. (2021). Assessing adaptive irrigation impacts on water scarcity in nonstationary environments—A multi-agent reinforcement learning approach. _Water Resources Research_, 57, e2020WR029262. https://doi.org/10.1029/2020WR029262

**GitHub**: [https://github.com/hfengwe1/RL-ABM-CRSS](https://github.com/hfengwe1/RL-ABM-CRSS)

---

## Core Methodology

### Framework: FQL (Farmer's Q-Learning)

A variant of Q-learning adapted for **Partial Observable Markov Decision Processes (POMDP)** where agents cannot directly observe the maximum available water supply.

### Decision Loop

```python
for agent in agents:
    # Observe current state
    Div_y = current_year_diversion
    a_t = Div_req_y0 - Div_y0  # Previous action

    # Q-learning step
    a_t_new = Q_learning(params, States, a_t, Div_y, f_t, agent)

    # Update request
    Div_req_update = Div_y + a_t_new
```

---

## Agent Configuration

### Total Agents

| Basin            | Agent Count | Groups       | Data Level  |
| ---------------- | ----------- | ------------ | ----------- |
| Upper Basin (UB) | 56          | 9 sub-basins | Sub-basin   |
| Lower Basin (LB) | 22          | 15 groups    | Agent-level |
| **Total**        | **78**      | 24           | -           |

### Agent Parameters (6 per agent)

| Parameter             | Symbol | Range       | Description                                 |
| --------------------- | ------ | ----------- | ------------------------------------------- |
| Diversion Change Mean | μ      | [0, 0.5]    | Average magnitude of request change         |
| Diversion Change Std  | σ      | [0.5, 1.5]  | Variability in request change               |
| Learning Rate         | α      | [0.5, 0.95] | Speed of accepting new information          |
| Discount Rate         | γ      | [0.5, 0.95] | Importance of future rewards                |
| Exploration Rate      | ε      | [0.05, 0.3] | Probability of exploration vs. exploitation |
| Regret                | regret | [0.5, 3]    | Sensitivity to unmet demand penalty         |

### Agent Behavioral Types (3 Clusters)

| Cluster                      | μ    | σ    | α    | γ    | ε    | regret | Description                         |
| ---------------------------- | ---- | ---- | ---- | ---- | ---- | ------ | ----------------------------------- |
| Aggressive                   | 0.36 | 1.22 | 0.62 | 0.77 | 0.16 | 0.78   | Swift actions, low penalty aversion |
| Forward-looking Conservative | 0.20 | 0.60 | 0.85 | 0.78 | 0.19 | 2.22   | Cautious but willing to learn       |
| Myopic Conservative          | 0.16 | 0.87 | 0.67 | 0.64 | 0.09 | 1.54   | Relies on prior knowledge           |

---

## Data Inventory

### Required Data Sources

| Data                       | Source                        | Period    | Resolution        | Status             |
| -------------------------- | ----------------------------- | --------- | ----------------- | ------------------ |
| UB Depletion               | USBR Consumptive Uses Reports | 1971-2018 | Sub-basin, Annual | 🔴 Need to acquire |
| LB Diversion               | USBR Consumptive Uses Reports | 1971-2018 | Agent, Annual     | 🔴 Need to acquire |
| Winter Precipitation (UB)  | PRISM                         | 1971-2018 | Sub-basin         | 🔴 Need to acquire |
| Lake Mead Water Level (LB) | USBR                          | 1971-2018 | Monthly           | 🔴 Need to acquire |
| Calibrated Agent Params    | GitHub Repo                   | -         | 31 agents         | ✅ Available       |

### Data URLs

- **UB Depletion**: https://www.usbr.gov/uc/envdocs/plans.html#CCULR
- **LB Diversion**: https://www.usbr.gov/lc/region/g4000/wtracct.html
- **PRISM Precipitation**: https://catalog.data.gov/dataset/parameter-elevation-regressions-on-independent-slopes-model-prism-dataset
- **Lake Mead Elevation**: https://www.usbr.gov/lc/region/g4000/hourly/mead-elv.html

---

## Integration with Governed Broker Framework

### Mapping to Existing Components

| RL-ABM Component         | GBF Equivalent          | Notes                       |
| ------------------------ | ----------------------- | --------------------------- |
| Agent (farmer)           | `BaseAgent`             | Water user profile          |
| Q-function               | `MemorySystem`          | Store learned policy        |
| Transition Probability P | `ReflectionTemplate`    | Update beliefs              |
| ε-greedy exploration     | Governance layer        | Control exploration policy  |
| Water Info (Of)          | `EnvironmentalFeeds`    | External water signal       |
| Reward function          | `PsychometricFramework` | Utility/penalty calculation |

### Proposed Agent Type (YAML)

```yaml
irrigation_farmer:
  base: cognitive_agent
  framework: fql # Farmer's Q-Learning
  parameters:
    mu: 0.2 # Diversion change mean
    sigma: 0.7 # Diversion change std
    alpha: 0.75 # Learning rate
    gamma: 0.7 # Discount rate
    epsilon: 0.15 # Exploration rate
    regret: 1.5 # Penalty sensitivity
  state_space_size: 21 # Discretized states
  action_space: [increase, decrease]
  water_signal: precipitation # or lake_level for LB
```

---

## Experiment Settings

### Simulation Parameters

| Parameter          | Value                        | Notes                                        |
| ------------------ | ---------------------------- | -------------------------------------------- |
| Simulation Period  | 2019-2060                    | 42 years                                     |
| Climate Scenario   | Drier-than-normal            | Historical resampling (1988-2015, 1934-1947) |
| Training Data Size | 2000 episodes                | Monte Carlo generated                        |
| Validation Metric  | KGE (Kling-Gupta Efficiency) | Pearson r, mean ratio, std ratio             |
| Monte Carlo Runs   | 100                          | For uncertainty quantification               |

### Groupings (Similar to Flood Experiment)

| Group   | Description        | Governance Level                 |
| ------- | ------------------ | -------------------------------- |
| Group A | Native FQL         | No governance                    |
| Group B | Governed FQL       | Strict resource constraints      |
| Group C | Full Cognitive FQL | Memory + Reflection + Governance |

---

## Subtasks

- [ ] **060-1**: Clone `hfengwe1/RL-ABM-CRSS` to `ref/RL-ABM-CRSS/`
- [ ] **060-2**: Download USBR/PRISM historical data
- [ ] **060-3**: Create `IrrigationAgent` base class in `broker/core/`
- [ ] **060-4**: Implement FQL algorithm in `cognitive_governance/`
- [ ] **060-5**: Create `examples/irrigation_abm/` experiment folder
- [ ] **060-6**: Define agent types YAML for 3 behavioral clusters
- [ ] **060-7**: Implement water signal interfaces (Precipitation, Lake Level)
- [ ] **060-8**: Run training phase (2000 episodes per agent)
- [ ] **060-9**: Run validation phase (1971-2018 historical replay)
- [ ] **060-10**: Run simulation phase (2019-2060, 100 Monte Carlo runs)
- [ ] **060-11**: Generate analysis outputs (KGE, uncertainty ranges, cluster comparison)

---

## Risks

| Risk                       | Mitigation                               |
| -------------------------- | ---------------------------------------- |
| Data acquisition from USBR | Use simplified synthetic data if blocked |
| CRSS coupling complexity   | Start with standalone FQL, defer CRSS    |
| 78 agents too large        | Start with 5-agent prototype             |
| Training time              | Use GPU acceleration or reduce epochs    |

---

## Next Steps

1. Clone the GitHub repository
2. Inventory data files available locally vs. need to download
3. Create implementation plan for Phase 1 (Standalone FQL Agent)

---

## References

- Hung, F., & Yang, Y. C. E. (2021). Water Resources Research. https://doi.org/10.1029/2020WR029262
- Sutton, R. S., & Barto, A. G. (1998). Reinforcement Learning: An Introduction.
- Watkins, C., & Dayan, P. (1992). Q-learning. Machine Learning.
