# Irrigation ABM Experiment Design — Hung & Yang (2021) LLM Adaptation

> **Date**: 2026-01-30
> **Task**: 060
> **Branch**: `feat/memory-embedding-retrieval`
> **Goal**: Prove GBF is domain-agnostic by applying it to irrigation water demand

---

## Research Objective

Demonstrate that the Governed Broker Framework generalizes beyond flood adaptation to a different domain (irrigation water demand) without core framework changes. The experiment adapts Hung & Yang (2021) RL-ABM-CRSS — 78 agents managing Colorado River Basin water allocations — into an LLM-driven cognitive agent system using existing GBF modules.

**Paper**: Hung, F., & Yang, Y. C. E. (2021). Assessing adaptive irrigation impacts on water scarcity in nonstationary environments — A multi-agent reinforcement learning approach. *Water Resources Research*, 57, e2020WR029262.

---

## Design Decisions (from brainstorming)

| Decision | Choice | Rationale |
|---|---|---|
| Primary research question | GBF generalizability | Prove framework transfers to new domain |
| Information depth | Paper-faithful minimal | Same signals as Q-learning, keeps comparison fair |
| Action mapping | Governance-bounded LLM magnitude | LLM proposes direction + %, governance clamps to cluster bounds |
| Regret feedback | Neutral across all clusters | Factual shortfall data; persona drives behavioral differences |
| Experiment structure | No ABC groups | Single configuration with full GBF stack (memory + reflection + governance) |
| Validation approach | Integration test suite | Automated verification that each GBF module handles irrigation data |

---

## Information Architecture

Each agent receives the same information available to a Q-learning agent, expressed in natural language:

| Signal | Source (Hung 2021) | LLM Prompt Form |
|---|---|---|
| Div_y (diversion received) | CRSS output | "You received X acre-ft this year" |
| Div_req (previous request) | Agent state | "You requested Y acre-ft" |
| Preceding factor f_t | Precip (UB) / Lake Mead (LB) | "Precipitation was above/below last year" |
| Shortage tier | Mead thresholds | "Bureau declared Tier N shortage" |
| Water right | Static allocation | "Your water right is Z acre-ft/year" |
| Utilisation ratio | Div_y / water_right | "You are using X% of allocation" |

**Not included** (paper scope): neighbor demand patterns, crop economics, social network effects.

---

## LLM Output Format

```json
{
  "water_threat_appraisal": {"label": "H", "reason": "..."},
  "water_coping_appraisal": {"label": "M", "reason": "..."},
  "decision": "1",
  "magnitude": 15,
  "reasoning": "..."
}
```

- `decision`: 1-5 mapping to increase/decrease/efficiency/reduce_acreage/maintain
- `magnitude`: Integer 1-30, representing % change in demand

---

## Governance: Cluster-Bounded Magnitudes

Governance clamps LLM-proposed magnitude to cluster-appropriate bounds derived from FQL mu/sigma parameters:

| Cluster | Max % Change | FQL Reference |
|---|---|---|
| Aggressive | +-30% | mu=0.36, sigma=1.22 |
| Forward-looking Conservative | +-15% | mu=0.20, sigma=0.60 |
| Myopic Conservative | +-10% | mu=0.16, sigma=0.87 |

Physical constraints (all clusters):
- Cannot exceed water right allocation
- Cannot go below zero diversion
- Cannot increase during severe drought (drought_index >= 0.8)
- Cannot adopt efficiency if already adopted

Retry loop: If LLM proposes magnitude exceeding cluster cap, governance rejects with a message explaining the cap, and the LLM re-reasons.

---

## Regret Feedback (Memory)

After each year, all agents receive factual shortfall feedback (neutral tone, no cluster variation):

```
Year {year}: You requested {request} acre-ft and received {diversion} acre-ft.
[Shortfall: {gap} acre-ft ({gap_pct}% unmet) | Demand fully met].
Drought index: {drought_index}. Precipitation was [above/below] last year.
```

The persona description already encodes regret sensitivity:
- Aggressive: "you're not particularly worried about unmet demand"
- Forward-looking: "running short of water is your worst-case scenario"
- Myopic: "moderately concerned about water shortages"

---

## Integration Test Plan

### 1. Memory System
- Store water curtailment event → verify memory item created
- Store 10 years → verify working memory window (size=5)
- Trigger consolidation → important events (shortfall > 10%) move to LTM
- Verify Ebbinghaus decay on old water memories

### 2. Reflection Engine
- Crisis trigger: severe drought (index > 0.8)
- Periodic trigger: every 5 years
- Decision trigger: agent chooses `decrease_demand`
- Institutional trigger: shortage tier change (0 → 2)
- Verify reflection output contains irrigation reasoning

### 3. Governance Validators
- 15 existing tests (water rights, curtailment, drought, efficiency, compact)
- Add: magnitude capping by cluster
- Add: YAML rule evaluation with WTA/WCA constructs

### 4. Prompt → Parse (end-to-end)
- Build complete prompt with irrigation context
- Mock LLM response with valid JSON
- Parse decision + magnitude
- Governance validation of parsed output
- State update (new diversion request)

### 5. Full Loop (5 agents, 5 years, mocked LLM)
- Complete simulation loop: environment → prompt → decision → governance → memory
- Verify no flood-specific code paths triggered
- All modules interact correctly

---

## File Structure

```
examples/irrigation_abm/
  config/
    agent_types.yaml              # Agent types, personas, governance
    prompts/
      irrigation_farmer.txt       # LLM prompt template
  data/                           # Historical data (if available)
  irrigation_personas.py          # Persona builder
  run_experiment.py               # Experiment runner

cognitive_governance/
  learning/
    __init__.py
    fql.py                        # FQL baseline (Group A reference)
  simulation/
    irrigation_env.py             # Water system environment

broker/validators/governance/
  irrigation_validators.py        # Water rights, curtailment, drought checks

tests/
  test_fql.py                     # 26 tests
  test_irrigation_env.py          # 35 tests
  test_irrigation_integration.py  # Integration tests (TBD)
```

---

## GBF Component Mapping

| RL-ABM (Hung 2021) | GBF Module | Verification |
|---|---|---|
| Q-function | Memory + LLM reasoning | Memory stores past outcomes; LLM reasons about them |
| epsilon-greedy | Persona + Governance | Persona drives exploration; governance bounds it |
| Reward function | Post-decision feedback → Memory | Factual shortfall data stored as memory |
| Transition probability P | Reflection | Periodic reflection synthesises water availability patterns |
| Agent parameters | Persona + Governance bounds | mu/sigma → magnitude caps; alpha/gamma → persona text |
| Preceding factor | Environment signal | Precipitation/lake level change in prompt |

---

## References

- Hung, F., & Yang, Y. C. E. (2021). WRR, 57, e2020WR029262.
- Sutton, R. S., & Barto, A. G. (1998). Reinforcement Learning: An Introduction.
- Watkins, C., & Dayan, P. (1992). Q-learning. Machine Learning.
