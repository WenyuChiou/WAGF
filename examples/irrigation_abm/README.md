# Irrigation ABM Experiment — Hung & Yang (2021) LLM Adaptation

LLM-driven reproduction of the Colorado River Basin irrigation ABM from Hung & Yang (2021, *Water Resources Research*). 78 agricultural water users make annual demand decisions using language model reasoning instead of Q-learning (FQL).

This experiment demonstrates the SAGE governance middleware applied to a nonstationary water supply system where agents face chronic drought stress over a 42-year planning horizon.

## Dual-Appraisal Framework (WSA / ACA)

Irrigation agents use a **dual-appraisal** framework adapted from the FQL behavioral model in Hung & Yang (2021). Each year, agents assess two independent dimensions before choosing an action:

| Dimension | Construct | Description |
|-----------|-----------|-------------|
| **Threat** | Water Scarcity Assessment (WSA) | Chronic, season-level water supply threat based on drought index, curtailment, and shortage tier |
| **Capacity** | Adaptive Capacity Assessment (ACA) | General seasonal ability to adapt practices based on farm resources and technology status |

The two dimensions are assessed **independently** — governance rules may condition on one or both, but there is no multiplicative interaction. This reflects the continuous, multi-year nature of irrigation demand management (unlike acute, binary threat domains).

**Rating scale**: Both WSA and ACA use a 5-level ordinal scale: VL (Very Low), L (Low), M (Medium), H (High), VH (Very High).

## Three Pillars

| Pillar | Name | Configuration | Effect |
|--------|------|---------------|--------|
| 1 | **Strict Governance** | Water rights, curtailment caps, efficiency checks | Blocks physically impossible or redundant actions |
| 2 | **Cognitive Memory** | `HumanCentricMemoryEngine` (basic ranking mode) + year-end reflection | Emotional encoding (importance = emotion * source) of droughts and outcomes |
| 3 | **Reflection Loop** | Year-end consolidation with domain-specific guidance questions | Agents reflect on demand strategy effectiveness and form long-term insights |

## Quick Start

```bash
# Smoke test (5 synthetic agents, 5 years)
python run_experiment.py --model gemma3:4b --years 5 --agents 5

# Validation (10 synthetic agents, 10 years)
python run_experiment.py --model gemma3:4b --years 10 --agents 10 --seed 42

# Production (78 real CRSS agents, 42 years — requires ref/CRSS_DB data)
python run_experiment.py --model gemma3:4b --years 42 --real --seed 42 --num-ctx 8192 --num-predict 4096
```

## CLI Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | `gemma3:1b` | Ollama model name |
| `--years` | `5` | Simulation years |
| `--agents` | `5` | Number of agents (synthetic mode) |
| `--workers` | `1` | Parallel LLM workers |
| `--real` | disabled | Use 78 real CRSS agents instead of synthetic |
| `--seed` | `42` | Random seed for reproducibility |
| `--memory-seed` | `42` | Memory engine seed |
| `--window-size` | `5` | Memory window size |
| `--no-magnitude` | disabled | Disable schema-driven magnitude_pct field |
| `--rebalance-clusters` | disabled | Force each behavioral cluster to have at least 15% of agents |
| `--num-ctx` | auto | Ollama context window override |
| `--num-predict` | auto | Ollama max tokens override |
| `--output` | auto-generated | Output directory |

## Behavioral Clusters

Three k-means clusters from Hung & Yang (2021) Section 4.1, mapped from FQL parameters to LLM personas:

| Cluster | FQL mu/sigma | LLM Persona | magnitude_default | Governance Effect |
|---------|-------------|-------------|-------------------|-------------------|
| **Aggressive** | 0.36/1.22 | Bold, large demand swings | 20% | Low regret sensitivity |
| **Forward-looking Conservative** | 0.20/0.60 | Cautious, future-oriented | 10% | High regret sensitivity |
| **Myopic Conservative** | 0.16/0.87 | Tradition-oriented, slow updates | 5% | Status quo preference |

Each persona receives a tailored narrative in the prompt template, with cluster-specific language for trust in forecasts, neighbor influence, and adaptation willingness.

## Response Format

Agent responses use the **Reasoning Before Rating** pattern — the `reasoning` field is placed first to improve autoregressive generation quality:

```
<<<DECISION_START>>>
reasoning: [free-text analysis of water situation]
water_scarcity_assessment: {"WSA_LABEL": "H", "WSA_REASON": "Drought index high, Tier 2 shortage"}
adaptive_capacity_assessment: {"ACA_LABEL": "M", "ACA_REASON": "Farm has some reserves but no drip system"}
decision: 2
magnitude_pct: 15
<<<DECISION_END>>>
```

**Field definitions** (from `agent_types.yaml → shared.response_format.fields`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `reasoning` | text | No | Free-text situational analysis |
| `water_scarcity_assessment` | appraisal | Yes | `WSA_LABEL` (VL/L/M/H/VH) + `WSA_REASON` |
| `adaptive_capacity_assessment` | appraisal | Yes | `ACA_LABEL` (VL/L/M/H/VH) + `ACA_REASON` |
| `decision` | choice | Yes | Numeric skill ID (1–5) |
| `magnitude_pct` | numeric | No | Demand change magnitude (1–30%). Defaults to persona-specific value if omitted |

## Available Skills

| # | Skill ID | Description | Magnitude | Constraints |
|---|----------|-------------|-----------|-------------|
| 1 | `increase_demand` | Request more water allocation | max 30%, default 10% | Blocked at allocation cap |
| 2 | `decrease_demand` | Request less allocation | max 30%, default 10% | Blocked at minimum utilisation floor |
| 3 | `adopt_efficiency` | Invest in drip/precision irrigation | One-time | One-time only |
| 4 | `reduce_acreage` | Fallow farmland to lower requirement | reduction_factor: 0.75 | Blocked at minimum utilisation floor |
| 5 | `maintain_demand` | No change to practices | No magnitude | Default/fallback action |

### Schema-Driven Magnitude

`magnitude_pct` is a formal `numeric` field in `response_format.fields`. The full pipeline:

```
LLM Output → parse_output() [SkillProposal.magnitude_pct]
  → SkillBrokerEngine [validation_context["proposed_magnitude"]]
  → Validators check cluster-specific caps
  → ApprovedSkill.parameters["magnitude_pct"]
  → Environment applies demand change
```

Per-persona defaults when the LLM outputs 0% or omits the field:
- Aggressive: 20%
- Forward-Looking Conservative: 10%
- Myopic Conservative: 5%

Opt-out via `--no-magnitude` to remove the field entirely (reduces context burden for smaller models).

## Governance Rules — Three Rule Types

SAGE governance uses a **priority-ordered rule chain** with three distinct rule types:

```
1. Identity Rules    → Hard physical constraints (always enforced first)
2. Thinking Rules    → Appraisal coherence (evaluated in priority order)
3. Domain Validators → Custom checks (physical, social)
```

When a rule triggers at **ERROR** level, the action is **rejected** and the LLM is re-prompted with the rejection reason (up to 3 governance retries). **WARNING**-level rules log the concern but allow the action to proceed.  Rules within each category are evaluated in the order defined in `agent_types.yaml`; the first ERROR-level violation terminates evaluation.

### Identity Rules (Physical Constraints)

| Rule ID | Precondition | Blocked Skill | Level | Rationale |
|---------|-------------|---------------|-------|-----------|
| `water_right_cap` | `at_allocation_cap` | `increase_demand` | ERROR | Cannot request water beyond legal right allocation |
| `already_efficient` | `has_efficient_system` | `adopt_efficiency` | ERROR | Cannot adopt technology already in use |
| `minimum_utilisation_floor` | `below_minimum_utilisation` | `decrease_demand`, `reduce_acreage` | ERROR | Cannot reduce demand below 10% of water right |

### Thinking Rules (Behavioral Coherence)

| Rule ID | Construct(s) | Condition | Blocked Skill | Level | Rationale |
|---------|-------------|-----------|---------------|-------|-----------|
| `high_threat_no_maintain` | WSA | WSA = VH | `maintain_demand` | ERROR | Very High water scarcity requires adaptive action |
| `low_coping_block_expensive` | ACA | ACA = VL | `adopt_efficiency` | ERROR | Very Low capacity cannot justify expensive investment |
| `low_threat_no_increase` | WSA | WSA in {VL, L} | `increase_demand` | ERROR | Low scarcity does not justify requesting more water |
| `high_threat_high_cope_no_increase` | WSA + ACA | WSA in {H, VH} AND ACA in {H, VH} | `increase_demand` | WARNING | High threat + high capacity should conserve, not consume |

### Domain Validators

Custom validators in `validators/irrigation_validators.py` provide additional physical and social checks:

| Category | Check | Trigger | Level |
|----------|-------|---------|-------|
| Physical | `water_right_cap_check` | `increase_demand` when at allocation cap | ERROR |
| Physical | `non_negative_diversion_check` | `decrease_demand` when current diversion = 0 | ERROR |
| Physical | `efficiency_already_adopted_check` | `adopt_efficiency` when already adopted | ERROR |
| Physical | `minimum_utilisation_check` | `decrease_demand`/`reduce_acreage` below 10% floor | ERROR |
| Physical | `drought_severity_check` | `increase_demand` when drought_index >= 0.8 | ERROR |
| Physical | `magnitude_cap_check` | Magnitude exceeds cluster cap (30/15/10%) | ERROR |
| Social | `curtailment_awareness_check` | `increase_demand` during active curtailment | WARNING |
| Social | `compact_allocation_check` | Basin aggregate demand exceeds Compact share | WARNING |

### Semantic Rules

Semantic rules are **not yet active** for irrigation because the experiment runs agents independently (no social network). They are relevant for the multi-agent flood domain where agents observe neighbors. Future irrigation extensions with inter-district information sharing would benefit from semantic grounding rules.

## Memory Configuration

The `HumanCentricMemoryEngine` operates in **basic ranking mode**:

| Parameter | Value | Description |
|-----------|-------|-------------|
| `engine_type` | `humancentric` | HumanCentric memory engine |
| `window_size` | 5 | Short-term working memory buffer |
| `top_k_significant` | 2 | Top memories by decayed importance |
| `consolidation_threshold` | 0.6 | Minimum importance for LTM transfer |
| `consolidation_probability` | 0.7 | Stochastic consolidation gate |
| `decay_rate` | 0.1 | Exponential forgetting rate |

### Importance Scoring

```
importance = emotional_weight * source_weight
```

| Emotional Category | Keywords | Weight |
|-------------------|----------|--------|
| `water_crisis` | curtailment, shortage, drought, dry, depleted, crisis | 1.0 |
| `strategic_choice` | decision, increase, decrease, efficiency, conservation | 0.8 |
| `positive_outcome` | sufficient, surplus, saved, adequate, improved | 0.6 |
| `social_feedback` | neighbor, upstream, downstream, compact, agreement | 0.4 |
| `baseline_observation` | (default) | 0.1 |

| Source Category | Patterns | Weight |
|----------------|----------|--------|
| `personal` | "i ", "my ", "me ", "my farm", "my water" | 1.0 |
| `neighbor` | "neighbor", "upstream", "downstream", "adjacent" | 0.8 |
| `basin` | "basin", "compact", "allocation", "bureau" | 0.6 |
| `policy` | "regulation", "policy", "mandate", "restriction" | 0.4 |

### Retrieval

In basic ranking mode, retrieval combines the recent **window** (5 most recent memories) with the **top-k** (2 highest by decayed importance), without weighted scoring.

## Reflection Configuration

| Parameter | Value |
|-----------|-------|
| `interval` | 1 (every year) |
| `batch_size` | 10 agents per batch |
| `importance_boost` | 0.9 |
| `method` | hybrid |

### Guidance Questions

Defined in `agent_types.yaml` under `global_config.reflection.questions`:

1. "Was your water demand strategy effective given the supply conditions?"
2. "Did the magnitude of your demand change match the outcome?"
3. "What patterns do you notice between your actions and supply shortfalls?"

### Action-Outcome Feedback

Each year, agents receive combined memories with magnitude context:
> "Year 5: You chose to decrease_demand by 15%. Outcome: Supply was adequate, utilisation dropped to 65%."

This enables causal learning — agents can correlate demand change magnitudes with supply outcomes across the reflection loop.

## Economic Hallucination

v4 experiments revealed a novel LLM failure mode: **economic hallucination** — actions that are physically feasible but operationally absurd given quantitative context.

Forward-looking conservative (FLC) agents repeatedly chose `reduce_acreage` (demand *= 0.75) despite their context showing 0% utilisation. Persona anchoring ("cautious farmer") overwhelmed numerical awareness, compounding demand to zero over ~30 years.

**Three-layer defense (v6)**:
1. **MIN_UTIL floor (P0)**: `execute_skill` enforces `max(new_request, water_right * 0.10)` across all reduction skills
2. **Diminishing returns (P1)**: Taper = `(utilisation - 0.10) / 0.90` — reductions shrink smoothly as utilisation approaches 10%
3. **Governance identity rule**: `minimum_utilisation_floor` precondition blocks `decrease_demand`/`reduce_acreage` when `below_minimum_utilisation == True`
4. **Builtin validator**: `minimum_utilisation_check()` in `irrigation_validators.py` as final safety net

This extends the hallucination taxonomy beyond physical impossibility (flood domain: re-elevating an already-elevated house) to economic/operational absurdity.

## Simulation Pipeline

```
1. Initialize agents (synthetic or 78 real CRSS agents)
   - Assign behavioral cluster (aggressive/FLC/myopic)
   - Set initial water rights, diversions, efficiency status
2. For each year (1..42):
   a. Pre-Year Hook:
      - Update water situation (drought index, shortage tier, curtailment)
      - Inject basin condition memories
      - Sync physical state flags (at_cap, below_floor, has_efficient)
      - Append action-outcome feedback from prior year
   b. Agent Decision Step (per agent):
      - Retrieve memories (window + top-k significant)
      - Build dual-appraisal prompt with persona context
      - Call LLM → parse response → extract WSA/ACA + decision + magnitude
      - Validate against governance rules (strict profile)
      - Approve skill or retry (up to 3 governance retries)
   c. Skill Execution:
      - Apply demand change (with magnitude_pct)
      - Update state (water_right, diversion, efficiency_status)
   d. Post-Step Hook:
      - Record yearly decision, appraisals, magnitude
   e. Post-Year Hook:
      - Trigger batch reflection
      - Save reflection insights to memory
3. Write output files and governance summary
```

## Output Files

```
results/<run_name>/
  simulation_log.csv                     # Year, agent, skill, constructs, magnitude
  irrigation_farmer_governance_audit.csv # Governance interventions
  governance_summary.json                # Aggregate audit stats
  config_snapshot.yaml                   # Reproducibility snapshot
  raw/irrigation_farmer_traces.jsonl     # Full LLM traces
  reflection_log.jsonl                   # Memory consolidation events
```

### Output Interpretation

| File | Key Columns / Fields |
|------|---------------------|
| `simulation_log.csv` | `agent_id`, `year`, `skill`, `WSA_LABEL`, `ACA_LABEL`, `magnitude_pct`, `water_right`, `diversion`, `utilisation` |
| `governance_summary.json` | `total_interventions` = ERROR blocks; `warnings.total_warnings` = WARNING observations; `retry_success` = agent corrected on retry |
| `irrigation_farmer_governance_audit.csv` | `failed_rules` = ERROR rules that blocked; `warning_rules` = WARNING observations |

### Two Retry Mechanisms

1. **Format retries** (up to 2): Triggered when the LLM output cannot be parsed (structural failure).
2. **Governance retries** (up to 3): Triggered when a parsed proposal violates governance rules.

Both are tracked separately in `governance_summary.json`.

## Enhancements (v7 — Group D)

| Feature | Description |
|---------|-------------|
| **Schema-Driven Magnitude** | `magnitude_pct` is a formal `numeric` field in `response_format.fields`. Per-persona defaults: aggressive=20%, FLC=10%, myopic=5%. Opt-out via `--no-magnitude`. |
| **Action-Outcome Feedback** | Agents receive combined "You chose X → outcome Y" memories each year, enabling causal learning through reflection. |
| **Configurable Reflection** | Domain-specific reflection guidance questions defined in `agent_types.yaml` under `global_config.reflection.questions`. |

## Project Structure

```
irrigation_abm/
  run_experiment.py          # Main runner (ExperimentBuilder pipeline)
  irrigation_env.py          # Water system simulation environment
  irrigation_personas.py     # Cluster persona builder + context helpers
  config/
    agent_types.yaml         # Agent config, governance rules, personas
    skill_registry.yaml      # Available irrigation skills
    policies/                # Domain-specific governance policies
    prompts/                 # LLM prompt templates
  validators/
    irrigation_validators.py # 8 custom governance validators
  learning/
    fql.py                   # Reference FQL algorithm (not used by LLM runner)
```

## Colorado River Basin Parameters

| Parameter | Value |
|-----------|-------|
| Total Compact allocation | 16,500,000 acre-ft/year |
| Upper Basin share | 7,500,000 acre-ft/year |
| Lower Basin share | 7,500,000 acre-ft/year |
| Mexico share | 1,500,000 acre-ft/year |
| Simulation period | 2019–2060 |
| Historical baseline | 1971–2018 |
| Monte Carlo runs | 100 |

## Reference

Hung, F., & Yang, Y. C. E. (2021). Assessing adaptive irrigation impacts on water scarcity in nonstationary environments — A multi-agent reinforcement learning approach. *Water Resources Research*, 57, e2020WR029262. https://doi.org/10.1029/2020WR029262
