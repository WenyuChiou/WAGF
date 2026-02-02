# Governed Flood Adaptation Experiment

Standalone demonstration of **Full Cognitive Governance** (Group C) for flood adaptation agent-based modeling.  100 household agents make annual protective-action decisions using LLM reasoning governed by Protection Motivation Theory (PMT; Rogers, 1983; Grothmann & Reusswig, 2006).

This experiment showcases the three pillars of the SAGE governance middleware in a nonstationary hydro-social system where agents face recurring flood events over a 10-year horizon.

> **Scope**: This is a simplified, self-contained demo of the Group C configuration.  The full JOH validation suite (Groups A/B/C, stress tests, survey mode) lives in `examples/single_agent/run_flood.py`.

## Three Pillars

| Pillar | Mechanism | Configuration | Effect |
|--------|-----------|---------------|--------|
| 1. **Strict Governance** | YAML-driven thinking + identity rules | `governance.strict` profile in `agent_types.yaml` | Blocks cognitively inconsistent decisions (appraisal-action gap) |
| 2. **Cognitive Memory** | `HumanCentricMemoryEngine` (basic ranking mode) | `importance = emotion * source`, decay-based retrieval | Emotional encoding preserves salient flood experiences |
| 3. **Reflection Loop** | Year-end batch reflection with domain-specific questions | `ReflectionEngine` + configurable guidance questions | Agents consolidate episodic memories into long-term insights |

## Theoretical Foundation

### Protection Motivation Theory (PMT)

Each household agent evaluates two independent cognitive dimensions before choosing an action (Rogers, 1983):

| Dimension | Construct | Description |
|-----------|-----------|-------------|
| **Threat Appraisal** | TP_LABEL | Perceived severity and vulnerability to flooding |
| **Coping Appraisal** | CP_LABEL | Perceived self-efficacy and response efficacy for protective action |

**Rating scale**: Both TP and CP use a 5-level ordinal scale: VL (Very Low), L (Low), M (Medium), H (High), VH (Very High).

Governance rules enforce behavioral coherence between appraisals and actions.  For example, an agent that reports VH threat perception but chooses `do_nothing` is blocked and re-prompted — the appraisal-decision gap is a form of cognitive hallucination.

## Quick Start

```bash
# Smoke test (10 agents, 2 years)
python run_experiment.py --model gemma3:4b --years 2 --agents 10

# Validation run (100 agents, 10 years, fixed seed)
python run_experiment.py --model gemma3:4b --years 10 --agents 100 --seed 42

# Custom model with extended context
python run_experiment.py --model gemma3:12b --years 10 --agents 100 --seed 42 --num-ctx 8192 --num-predict 1536
```

## CLI Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | `gemma3:1b` | Ollama model name |
| `--years` | `10` | Simulation years |
| `--agents` | `100` | Number of household agents |
| `--workers` | `1` | Parallel LLM workers |
| `--seed` | random | Random seed for reproducibility |
| `--memory-seed` | `42` | Memory engine seed |
| `--window-size` | `5` | Memory window size (short-term buffer) |
| `--output` | auto-generated | Output directory |
| `--num-ctx` | `8192` | Ollama context window override |
| `--num-predict` | `4096` | Ollama max tokens override |

## Agent Configuration

### Available Actions

| Skill ID | Description | Cost Type | Constraint |
|----------|-------------|-----------|------------|
| `buy_insurance` | Partial financial protection; does not reduce physical damage | Recurring (annual) | Can renew yearly |
| `elevate_house` | Prevents most physical damage via structural elevation | One-time | Cannot elevate if already elevated |
| `relocate` | Eliminates flood risk permanently by leaving the area | One-time (permanent) | Cannot undo |
| `do_nothing` | No cost or effort; leaves household exposed | None | Always available |

### Response Format

Agent responses use the **Reasoning Before Rating** pattern — the `reasoning` field is placed first in the YAML field ordering to improve autoregressive generation quality:

```
<<<DECISION_START>>>
reasoning: [free-text analysis of situation]
threat_appraisal: {"TP_LABEL": "H", "TP_REASON": "Recent flood caused significant damage"}
coping_appraisal: {"CP_LABEL": "M", "CP_REASON": "I have savings but elevation is expensive"}
decision: 2
<<<DECISION_END>>>
```

**Field definitions** (from `agent_types.yaml → shared.response_format.fields`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `reasoning` | text | No | Free-text situational analysis |
| `threat_appraisal` | appraisal | Yes | `TP_LABEL` (VL/L/M/H/VH) + `TP_REASON` |
| `coping_appraisal` | appraisal | Yes | `CP_LABEL` (VL/L/M/H/VH) + `CP_REASON` |
| `decision` | choice | Yes | Numeric skill ID (1–4) |

### Skill Mapping

The numeric skill map adapts to agent state:

| State | 1 | 2 | 3 | 4 |
|-------|---|---|---|---|
| Default | `buy_insurance` | `elevate_house` | `relocate` | `do_nothing` |
| Already elevated | `buy_insurance` | `relocate` | `do_nothing` | — |
| Already relocated | *(no property actions available — agent has left the area)* | — | — | — |

## Governance Rules

### Three Rule Types

The SAGE framework uses a **priority-ordered rule chain** evaluated in this order:

```
1. Identity Rules    → Physical state constraints (always enforced first)
2. Thinking Rules    → Appraisal-action coherence (PMT consistency)
3. Domain Validators → Custom checks (physical, social, semantic)
```

When a rule triggers at **ERROR** level, the action is **rejected** and the LLM is re-prompted with the rejection reason (up to 3 governance retries).  **WARNING**-level rules log the concern but allow the action to proceed.  Rules within each category are evaluated in the order defined in `agent_types.yaml`; the first ERROR-level violation terminates evaluation.

### Strict Profile — Thinking Rules

| Rule ID | Construct(s) | Condition | Blocked Skill | Level | Rationale |
|---------|-------------|-----------|---------------|-------|-----------|
| `extreme_threat_block` | TP | TP = VH | `do_nothing` | ERROR | Very High threat requires protective action |
| `low_coping_block` | CP | CP = VL | `elevate_house`, `relocate` | ERROR | Very Low coping cannot justify expensive actions |
| `relocation_threat_low` | TP | TP in {VL, L} | `relocate` | ERROR | Low threat does not justify abandoning property |
| `elevation_threat_low` | TP | TP in {VL, L} | `elevate_house` | ERROR | Low threat does not justify expensive elevation |

### Strict Profile — Identity Rules

| Rule ID | Precondition | Blocked Skill | Level | Rationale |
|---------|-------------|---------------|-------|-----------|
| `elevation_block` | `elevated = true` | `elevate_house` | ERROR | Physical impossibility — cannot elevate twice |

### Domain Validators

Domain-specific validators in `validators/flood_validators.py` provide additional checks beyond the YAML-driven rules:

| Category | Check | Trigger | Level |
|----------|-------|---------|-------|
| Physical | `flood_already_elevated` | `elevate_house` when `elevated=true` | ERROR |
| Physical | `flood_already_relocated` | Any property action when `relocated=true` | ERROR |
| Physical | `flood_renter_restriction` | `elevate_house` or `buyout` when `tenure="renter"` | ERROR |
| Personal | `flood_elevation_affordability` | `elevate_house` when `savings < cost` | ERROR |
| Social | `flood_majority_deviation` | `do_nothing` when >50% neighbors adapted | WARNING |
| Semantic | `flood_social_proof_hallucination` | Reasoning cites neighbors but agent has none | ERROR |
| Semantic | `flood_temporal_grounding` | Reasoning references a flood that did not occur | WARNING |
| Semantic | `flood_state_consistency` | Reasoning contradicts actual state (e.g., claims insurance when uninsured) | WARNING |

### The Governance Dead Zone Problem

When TP=H and CP=VL, the following rules interact:
- `extreme_threat_block` (ERROR) blocks `do_nothing`
- `low_coping_block` (ERROR) blocks `elevate_house` and `relocate`

This creates a narrow action space where only `buy_insurance` is available.  In earlier versions (`low_coping_block` at ERROR level), this was called the "dead zone."  The current strict profile keeps ERROR level to enforce strong cognitive consistency — agents in this state are channeled toward the most accessible protective action.

## Memory Configuration

The `HumanCentricMemoryEngine` operates in **basic ranking mode** (the validated configuration for all WRR experiments):

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
| `direct_impact` | flood, flooded, damage, destroyed, loss, trauma | 1.0 |
| `strategic_choice` | decision, grant, relocate, elevate, move | 0.8 |
| `efficacy_gain` | protected, safe, insurance, saved, relief | 0.6 |
| `social_feedback` | trust, neighbor, judgment, observe | 0.4 |
| `baseline_observation` | (default) | 0.1 |

| Source Category | Patterns | Weight |
|----------------|----------|--------|
| `personal` | "I ", "my ", "me ", "got flooded", "my house" | 1.0 |
| `neighbor` | "neighbor", "others", "friend" | 0.8 |
| `community` | "%", "residents", "community", "everyone" | 0.6 |
| `general_knowledge` | (default) | 0.4 |

### Retrieval

In basic ranking mode, retrieval combines the recent **window** (5 most recent memories) with the **top-k** (2 highest by decayed importance), without weighted scoring.  This provides a stable, reproducible baseline for validation experiments.

## Reflection Configuration

The `ReflectionEngine` is invoked automatically at the end of each simulation year (interval = 1).

| Parameter | Value |
|-----------|-------|
| `interval` | 1 (every year) |
| `batch_size` | 10 agents per batch |
| `importance_boost` | 0.9 |
| `method` | hybrid |

### Guidance Questions

Defined in `agent_types.yaml` under `global_config.reflection.questions`:

1. "What risks feel most urgent to your family right now?"
2. "Have your neighbors' choices influenced your thinking?"
3. "What trade-offs have you faced between cost and safety?"

### Action-Outcome Feedback

Each year, agents receive combined memories like:
> "Year 3: You chose to buy_insurance. Outcome: You had flood insurance when the flood hit, reducing financial losses."

This enables causal learning through the reflection loop.

## Simulation Pipeline

```
1. Initialize agents (100 households with profiles from CSV)
2. For each year (1..10):
   a. Pre-Year Hook:
      - Inject flood/grant/social memories
      - Update neighbor adaptation observations
      - Add random historical recalls (20% chance)
      - Append action-outcome feedback from prior year
   b. Agent Decision Step (per agent):
      - Retrieve memories (window + top-k significant)
      - Build PMT prompt with tiered context
      - Call LLM → parse response → extract TP/CP + decision
      - Validate against governance rules (strict profile)
      - Approve skill or retry (up to 3 governance retries)
   c. Skill Execution:
      - Apply state changes (elevated, has_insurance, relocated)
   d. Post-Step Hook:
      - Record yearly decision and appraisals
   e. Post-Year Hook:
      - Update trust dynamics
      - Trigger batch reflection
      - Save reflection insights to memory
3. Write output files and governance summary
```

### Flood Schedule

Floods occur on a fixed schedule defined in `config/flood_years.csv` (default: years 3, 4, 9).

## Output Files

```
results/
  simulation_log.csv                     # Per-agent per-year decisions
  household_governance_audit.csv         # Governance validation trace
  governance_summary.json                # Aggregate governance statistics
  config_snapshot.yaml                   # Full config for reproducibility
  reproducibility_manifest.json          # Seed, model, timestamp
  reflection_log.jsonl                   # Year-end reflection insights
  raw/
    household_traces.jsonl               # Full LLM interaction traces
```

### Output Interpretation

| File | Key Fields |
|------|------------|
| `simulation_log.csv` | `agent_id`, `year`, `yearly_decision`, `threat_appraisal`, `coping_appraisal`, `elevated`, `has_insurance`, `relocated` |
| `governance_summary.json` | `total_interventions` = ERROR blocks; `warnings.total_warnings` = WARNING observations; `retry_success` = agent corrected on retry |
| `household_governance_audit.csv` | `failed_rules` = ERROR rules that blocked; `warning_rules` = WARNING observations; `warning_messages` = human-readable descriptions |

### Two Retry Mechanisms

The framework implements two distinct retry mechanisms:

1. **Format retries** (up to 2): Triggered when the LLM output cannot be parsed into a valid `SkillProposal` (structural parse failure).
2. **Governance retries** (up to 3): Triggered when a parsed proposal violates governance rules (appraisal-action inconsistency).

Both are tracked separately in `governance_summary.json` under `structural_faults` and `outcome_stats`.

## Difference from `single_agent/run_flood.py`

| Aspect | `single_agent/run_flood.py` (1239 lines) | `governed_flood/run_experiment.py` (~490 lines) |
|--------|-------------------------------------------|--------------------------------------------------|
| Purpose | Full JOH validation (Groups A/B/C) | Showcase Group C only |
| Custom classes | FinalContextBuilder, DecisionFilteredMemoryEngine, FinalParityHook | None — uses broker API directly |
| Memory engine | Dynamic (window / importance / humancentric) | Fixed: HumanCentricMemoryEngine |
| Governance | Configurable (strict / relaxed / disabled) | Fixed: strict |
| Stress tests | 4 adversarial profiles | None |
| Survey mode | Supported | Not included |

## Project Structure

```
governed_flood/
  run_experiment.py              # Main runner (~490 lines)
  config/
    agent_types.yaml             # Agent config, governance rules, memory
    skill_registry.yaml          # Available flood adaptation skills
    flood_years.csv              # Flood event schedule
    prompts/
      household.txt              # PMT prompt template
  adapters/
    flood_adapter.py             # DomainReflectionAdapter for flood domain
  validators/
    flood_validators.py          # 8 custom governance validators
  data/
    agent_initial_profiles.csv   # Agent initialization profiles
```

## References

- Grothmann, T., & Reusswig, F. (2006). People at risk of flooding: Why some residents take precautionary action while others do not. *Natural Hazards*, 38(1-2), 101-120. https://doi.org/10.1007/s11069-005-8604-6
- Park, J. S., et al. (2023). Generative Agents: Interactive simulacra of human behavior. *ACM CHI*. https://doi.org/10.1145/3586183.3606763
- Rogers, R. W. (1983). Cognitive and physiological processes in fear appeals and attitude change: A revised theory of protection motivation. *Social Psychophysiology*.
