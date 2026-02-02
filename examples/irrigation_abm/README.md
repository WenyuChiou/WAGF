# Irrigation ABM Experiment — Hung & Yang (2021) LLM Adaptation

LLM-driven reproduction of the Colorado River Basin irrigation ABM from Hung & Yang (2021, *Water Resources Research*). 78 agricultural water users make annual demand decisions using language model reasoning instead of Q-learning (FQL).

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
| 2 | **Cognitive Memory** | `HumanCentricMemoryEngine` + year-end reflection | Emotional encoding of droughts and outcomes |
| 3 | **Priority Schema** | Water situation enters context before preferences | Physical reality anchors LLM reasoning |

## Recent Enhancements (v7 — Group D)

| Feature | Description |
|---------|-------------|
| **Schema-Driven Magnitude** | `magnitude_pct` is a formal `numeric` field in `response_format.fields`. Per-persona defaults: aggressive=20%, FLC=10%, myopic=5%. Opt-out via `--no-magnitude`. |
| **Action-Outcome Feedback** | Agents receive combined "You chose X → outcome Y" memories each year, enabling causal learning through reflection. |
| **Configurable Reflection** | Domain-specific reflection guidance questions defined in `agent_types.yaml` under `global_config.reflection.questions`. |

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
| `--model` | `gemma3:4b` | Ollama model name |
| `--years` | `5` | Simulation years |
| `--agents` | `5` | Number of agents (synthetic mode) |
| `--real` | disabled | Use 78 real CRSS agents instead of synthetic |
| `--seed` | random | Random seed for reproducibility |
| `--no-magnitude` | disabled | Disable schema-driven magnitude_pct field |
| `--num-ctx` | auto | Ollama context window override |
| `--num-predict` | auto | Ollama max tokens override |
| `--output` | auto | Output directory |

## Behavioral Clusters

Three k-means clusters from Hung & Yang (2021) Section 4.1, mapped from FQL parameters to LLM personas:

| Cluster | FQL mu/sigma | LLM Persona | Governance Effect |
|---------|-------------|-------------|-------------------|
| **Aggressive** | 0.36/1.22 | Bold, large demand swings | Low regret sensitivity |
| **Forward-looking Conservative** | 0.20/0.60 | Cautious, future-oriented | High regret sensitivity |
| **Myopic Conservative** | 0.16/0.87 | Tradition-oriented, slow updates | Status quo preference |

## Available Skills

| Skill | Description | Constraints |
|-------|-------------|-------------|
| `increase_demand` | Request more water allocation | Blocked at allocation cap |
| `decrease_demand` | Request less allocation | Blocked at minimum utilisation floor |
| `adopt_efficiency` | Invest in drip/precision irrigation | One-time only |
| `reduce_acreage` | Fallow farmland to lower requirement | Blocked at minimum utilisation floor |
| `maintain_demand` | No change to practices | Default action |

## Governance Rules — Three Rule Types

SAGE governance uses a **priority-ordered rule chain** with three distinct rule types:

### Identity Rules (Physical Constraints)
Identity rules enforce **physical impossibilities** — actions that violate conservation laws or state preconditions. These are never debatable; they are hard constraints derived from the simulation engine's state.

| Rule ID | Precondition | Blocked Skill | Rationale |
|---------|-------------|---------------|-----------|
| `water_right_cap` | `at_allocation_cap` | `increase_demand` | Cannot request water beyond legal right allocation |
| `already_efficient` | `has_efficient_system` | `adopt_efficiency` | Cannot adopt technology already in use |
| `minimum_utilisation_floor` | `below_minimum_utilisation` | `decrease_demand`, `reduce_acreage` | Cannot reduce demand below 10% of water right (economic hallucination guard) |

Identity rules use **state-based preconditions** (boolean flags from the simulation engine). They fire regardless of the agent's appraisal — even if the LLM "wants" to increase demand, physical law prevents exceeding the water right.

### Thinking Rules (Behavioral Coherence)
Thinking rules enforce **appraisal-consistent behavior** — ensuring that the agent's chosen action is logically compatible with its own WSA/ACA assessment. These are softer than identity rules but still block actions that contradict the agent's stated reasoning.

| Rule ID | Construct(s) | Condition | Blocked Skill | Severity | Rationale |
|---------|-------------|-----------|---------------|----------|-----------|
| `high_threat_no_maintain` | WSA | WSA = VH | `maintain_demand` | ERROR | If you assess water threat as Very High, doing nothing is incoherent |
| `low_coping_block_expensive` | ACA | ACA = VL | `adopt_efficiency` | ERROR | If you assess your capacity as Very Low, investing in expensive technology is incoherent |
| `low_threat_no_increase` | WSA | WSA ∈ {VL, L} | `increase_demand` | ERROR | If water is abundant, requesting more allocation is unjustified |
| `high_threat_high_cope_no_increase` | WSA + ACA | WSA ∈ {H, VH} AND ACA ∈ {H, VH} | `increase_demand` | WARNING | High threat + high capacity → should conserve, not consume more |

Thinking rules enforce **independent consistency checks**: each appraisal dimension independently constrains the action space. Rule R4 is the only rule that conditions on both WSA and ACA jointly, and it issues a WARNING (not ERROR), allowing the agent to override if its reasoning is compelling.

### Semantic Rules (Grounding Validation)
Semantic rules validate that the agent's **reasoning content** is grounded in simulation reality. The SAGE framework includes a `SemanticGroundingValidator` (`broker/validators/governance/semantic_validator.py`) that checks for:

- **Hallucinated Social Proof**: Agent cites "neighbors" or "community influence" but has no neighbors in the simulation
- **Consensus Exaggeration**: Agent claims "everyone is doing X" but actual adoption rate is low

**Current irrigation status**: Semantic rules are **not yet active** for irrigation because the experiment runs agents independently (no social network). They are relevant for the multi-agent flood domain where agents observe neighbors. Future irrigation extensions with inter-district information sharing would benefit from semantic grounding rules (e.g., "cannot cite upstream district behavior if no information channel exists").

### Rule Evaluation Order

```
1. Identity Rules    → Hard physical constraints (always enforced first)
2. Thinking Rules    → Appraisal coherence (evaluated in priority order)
3. Semantic Rules    → Reasoning grounding (optional, domain-specific)
4. Custom Validators → Domain validators (e.g., irrigation_validators.py)
```

When a rule triggers at ERROR level, the action is REJECTED and the LLM is re-prompted with the rejection reason (up to 3 retries). WARNING-level rules log the concern but allow the action to proceed.

## Output Files

```
results/<run_name>/
  simulation_log.csv                     # Year, agent, skill, constructs
  irrigation_farmer_governance_audit.csv # Governance interventions
  governance_summary.json                # Aggregate audit stats
  config_snapshot.yaml                   # Reproducibility snapshot
  raw/irrigation_farmer_traces.jsonl     # Full LLM traces
  reflection_log.jsonl                   # Memory consolidation events
```

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
    irrigation_validators.py # 7 custom governance validators
  learning/
    fql.py                   # Reference FQL algorithm (not used by LLM runner)
```

## Economic Hallucination

v4 experiments revealed a novel LLM failure mode: **economic hallucination** — actions that are physically feasible but operationally absurd given quantitative context.

Forward-looking conservative (FLC) agents repeatedly chose `reduce_acreage` (demand *= 0.75) despite their context showing 0% utilisation. Persona anchoring ("cautious farmer") overwhelmed numerical awareness, compounding demand to zero over ~30 years.

**Three-layer defense (v6)**:
1. **MIN_UTIL floor (P0)**: `execute_skill` enforces `max(new_request, water_right * 0.10)` across all reduction skills
2. **Diminishing returns (P1)**: Taper = `(utilisation - 0.10) / 0.90` — reductions shrink smoothly as utilisation approaches 10%
3. **Governance identity rule**: `minimum_utilisation_floor` precondition blocks `decrease_demand`/`reduce_acreage` when `below_minimum_utilisation == True`
4. **Builtin validator**: `minimum_utilisation_check()` in `irrigation_validators.py` as final safety net

This extends the hallucination taxonomy beyond physical impossibility (flood domain: re-elevating an already-elevated house) to economic/operational absurdity. The same governance architecture catches both failure modes.

## Reference

Hung, F., & Yang, Y. C. E. (2021). Assessing adaptive irrigation impacts on water scarcity in nonstationary environments — A multi-agent reinforcement learning approach. *Water Resources Research*, 57, e2020WR029262.
