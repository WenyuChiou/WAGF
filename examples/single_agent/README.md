This experiment simulates household flood adaptation decisions using LLM-based agents with the Governed Broker Framework. It compares agent behavior with and without the governance layer, utilizing a fully modularized configuration system that separates domain-specific logic from core framework code.

## Modular Domain Configuration

The framework uses a YAML-driven configuration (`agent_types.yaml`) to define domain-specific parameters. This allows the same core logic to be applied to different scenarios (Flood, Finance, etc.) without code changes.

### Key Configuration Fields

#### 1. Semantic Audit (`audit_keywords` & `audit_stopwords`)

Used by the `GovernanceAuditor` to evaluate the content-reasoning alignment.

- **`audit_keywords`**: Core domain terms. If the agent decision involves these (e.g., "insurance"), the auditor checks if the reasoning correctly mentions related factors retrieved from memory.
- **`audit_stopwords`**: Common filler words to ignore during semantic extraction to reduce noise.

#### 2. Robust Construct Extraction (`synonyms`)

Maps various LLM outputs to standardized internal constructs used by Governance Rules.

- **`tp` (Threat Perception)**: Maps variants like "severity", "danger", or "risk" to the canonical `TP_LABEL`.
- **`cp` (Coping Perception)**: Maps variants like "efficacy", "cost", or "ability" to the canonical `CP_LABEL`.
- This ensures that if Llama says "Risk: High" and Gemma says "Threat: High", the governance layer treats them identically.

#### 3. Protection Motivation Theory (PMT) Mapping

- **`skill_map`**: Maps numbered options (1, 2, 3...) to canonical skill IDs. Coupled with **Option Shuffling**, this prevents positional bias while maintaining consistent rule validation.

---

## Memory & Retrieval System

### Available Memory Engines

| Engine         | Description                                   | Parameters                             | Use Case                |
| -------------- | --------------------------------------------- | -------------------------------------- | ----------------------- |
| `window`       | Sliding window (last N items)                 | `window_size=3`                        | Simple, predictable     |
| `importance`   | Active retrieval (recency + significance)     | `window_size=3`, `top_k_significant=2` | Retains critical events |
| `humancentric` | Emotional encoding + stochastic consolidation | See below                              | Human-realistic memory  |

### Usage

# Human-centric (emotional encoding + stochastic consolidation)

python run_flood.py --model gemma3:4b --memory-engine humancentric

````

### HumanCentricMemoryEngine Parameters

All weights and probabilities use 0-1 scale:

```python
HumanCentricMemoryEngine(
    window_size=3,              # int: Recent items always included
    top_k_significant=2,        # int: Top historical events to retrieve
    consolidation_prob=0.7,     # float [0-1]: Base P(consolidate) for important items
    decay_rate=0.1,             # float [0-1]: Exponential decay rate (λ)
    emotional_weights={
        "fear": 1.0,            # Flood damage, high threat
        "regret": 0.9,          # "I should have elevated"
        "relief": 0.8,          # Insurance claim success
        "trust_shift": 0.7,     # Trust changes
        "observation": 0.4,     # Neutral social observation
        "routine": 0.1          # No notable event
    },
    source_weights={
        "personal": 1.0,        # MY house flooded
        "neighbor": 0.7,        # Neighbor's experience
        "community": 0.5,       # Community statistics
        "abstract": 0.3         # General information
    }
)
````

### ImportanceMemoryEngine Parameters

All weights use 0-1 scale:

```python
ImportanceMemoryEngine(
    window_size=3,              # int: Recent items always included
    top_k_significant=2,        # int: Top historical events
    weights={
        "critical": 1.0,        # float: Maximum importance (floods, damage)
        "high": 0.8,            # float: High importance (claims, decisions)
        "medium": 0.5,          # float: Medium importance (observations)
        "routine": 0.1          # float: Minimal importance
    }
)
```

---

## LLM Behavioral Phenomena & Governance Solutions

Through multiple simulation cycles, we have identified several systemic failure modes in LLMs (especially models < 8B) and implemented specific framework-level solutions.

### 1. Observed LLM Failure Modes

- **Structural Flakiness (JSON Breakdown)**: Small models (Llama 3B, Gemma 4B) often fail to maintain strict JSON syntax when reasoning becomes complex.
- **Positional & Digit Bias**: Models occasionally favor specific option numbers (e.g., always choosing 1) or hallucinate non-existent IDs.
- **Appraisal-Decision Gap (Logical Disconnect)**: An agent might reason "risk is very low" but then choose "Relocate," showing a disconnect between internal logic and final action selection.
- **Identity Drifting**: In long-horizon simulations (10+ turns), models may "forget" their base constraints (e.g., a renter attempting to elevate a house they don't own).

### 2. Framework Solutions

- **Multi-Layer Robust Parsing**: The `UnifiedAdapter` uses a fall-through strategy (**Enclosure -> JSON Repair -> Regex -> Digit Fallback**) to capture intent even when formatting fails.
- **Dynamic Option Shuffling**: Prevents positional bias by randomizing the index of choices (FI, HE, RL, DN) for every agent while using the `skill_map` to normalize back to canonical IDs.
- **Real-Time Governance Feedback**: The `SkillBrokerEngine` detects the "Logical Disconnect" (via `thinking_rules`) and triggers an immediate **Retry Loop** with explicit error feedback, forcing the model to re-align its decision with its reasoning.
- **Identity-Based Guardrails**: Pre-conditions in the governance layer (e.g., `elevation_block`) act as "World Physics," preventing agents from performing impossible or redundant tasks.

---

## Memory Retrieval Benchmarks (2x4 Matrix)

The following matrix compares performance across four language models and two memory retrieval strategies.

### Cross-Model Behavioral Summary (v3.2)

- **Llama 3.2 (3B)**: Highly sensitive to social observations. Shows the highest rate of "Decision-Reasoning Gaps," frequently corrected by the Governance Layer.
- **Gemma 3 (4B)**: Most "Optimistic." Tends to prefer "Do Nothing" unless multiple floods are explicitly consolidated in memory. Requires specialized synonym mapping due to unique category naming (e.g., "Concern" vs "Threat").
- **DeepSeek-R1 (8B)**: Exceptional reasoning consistency. Rarely requires Governance retries, as its `<think>` chain aligns well with the PMT constructs. Shows distinct behavioral shifts when emotional memories (Human-Centric) are retrieved.

---

## Technical Validation

Governance discipline is strictly enforced via the `strict` profile, ensuring that High Threat signals combined with "Do Nothing" actions are minimized across all models. The RAG system ensures that Global Skills remain always available for selection.

---

---

## Results Structure

```
results/
├── Gemma_3_4B/                  # OLD baseline
├── gemma3_4b_strict/            # NEW governed
│   ├── audit_summary.json       # Validation stats
│   ├── household_governance_audit.csv
│   ├── simulation_log.csv       # Decision traces
│   └── comparison_results.png
└── old_vs_new_comparison_2x4.png
```

## Running Experiments

```powershell
# Quick test (5 agents, 3 years)
python run_flood.py --model llama3.2:3b --agents 5 --years 3

# Full experiment
python run_flood.py --model gemma3:4b --agents 100 --years 10

# Generate comparison chart
python generate_old_vs_new_2x4.py
```

## References

### PMT Validator Literature (Verified DOIs)

| Validator Rule               | Citation                    | Key Finding                            | DOI                                                                                    |
| ---------------------------- | --------------------------- | -------------------------------------- | -------------------------------------------------------------------------------------- |
| R1: HIGH TP+CP → Block DN    | Grothmann & Reusswig (2006) | HIGH TP + HIGH CP → should take action | [`10.1007/s11069-005-8604-6`](https://doi.org/10.1007/s11069-005-8604-6)               |
| R2: LOW TP → Block Relocate  | Rogers (1983)               | PMT original theory                    | Book Chapter                                                                           |
| R3: Flood + Safe claim       | Bubeck et al. (2012)        | Flood experience ↑ threat perception   | [`10.1111/j.1539-6924.2011.01783.x`](https://doi.org/10.1111/j.1539-6924.2011.01783.x) |
| R4: LOW CP → Block Expensive | Bamberg et al. (2017)       | CP stronger predictor than TP          | [`10.1016/j.jenvp.2017.08.001`](https://doi.org/10.1016/j.jenvp.2017.08.001)           |

### Memory System References

- **Park et al. (2023)** "Generative Agents" - Memory stream architecture ([arXiv:2304.03442](https://arxiv.org/abs/2304.03442))
- **Chapter 8 Memory and Retrieval** - Cognitive science foundations (Atkinson & Shiffrin 1968, Miller 1956)
- **Tulving (1972)** - Episodic vs Semantic memory distinction

### Additional References

See also:

- [`docs/references/pmt_validator_references.md`](../../docs/references/pmt_validator_references.md) - Full validator literature
- [`docs/references/pmt_flood_literature.bib`](../../docs/references/pmt_flood_literature.bib) - BibTeX for citation managers
