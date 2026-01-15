This experiment simulates household flood adaptation decisions using LLM-based agents with the Governed Broker Framework. It compares agent behavior with and without the governance layer, utilizing a fully modularized configuration system that separates domain-specific logic from core framework code.

## Modular Domain Configuration

The framework uses a YAML-driven configuration (`agent_types.yaml`) to define domain-specific parameters. This allows the same core logic to be applied to different scenarios (Flood, Finance, etc.) without code changes.

### Key Configuration Fields

#### 1. Semantic Audit (`audit_keywords` & `audit_stopwords`)

Used by the `GovernanceAuditor` to evaluate the content-reasoning alignment.

- **`audit_keywords`**: Core domain terms. If the agent decision involves these (e.g., "insurance"), the auditor checks if the reasoning correctly mentions related factors retrieved from memory.
- **`audit_stopwords`**: Common filler words to ignore during semantic extraction to reduce noise.

#### 2. Governance Logic & Academic Basis (Strict Mode)

The governance layer enforces two tiers of rules to ensure agent consistency.

##### Tier 1: Identity Rules (State Constraints)

**"Can I physically do this?"**
These rules prevent impossible actions based on the agent's current state.

| Rule ID             | Condition            | Blocked Action  | Rationale                                                              |
| :------------------ | :------------------- | :-------------- | :--------------------------------------------------------------------- |
| **elevation_block** | `elevated` is `True` | `elevate_house` | **Physical Constraint.** You cannot elevate an already elevated house. |

##### Tier 2: Thinking Rules (Cognitive Consistency)

**"Does this make sense given my thoughts?"**
These rules enforce Protection Motivation Theory (PMT) logic, ensuring decisions align with appraisals using a **Set Membership** check (often misnamed `when_above` in configs, but behaving as `is_in_set`).

| Rule ID                         | Logic Trigger (Condition) | Blocked Action     | PMT Rationale (Theoretical Basis)                                                                                            | Verified Citation           |
| :------------------------------ | :------------------------ | :----------------- | :--------------------------------------------------------------------------------------------------------------------------- | :-------------------------- |
| **no_action_under_high_threat** | `TP_LABEL` is `VH`        | `do_nothing`       | **High Threat + High Efficacy → Action.** If an agent perceives extreme danger, inaction is maladaptive fatalism.            | Grothmann & Reusswig (2006) |
| **capability_deficit**          | `CP_LABEL` is `VL`        | `elevate/relocate` | **Low Efficacy → Inaction.** If an agent feels incapable (low self-efficacy/high cost), they cannot perform complex actions. | Bamberg et al. (2017)       |
| **elevation_threat_low**        | `TP_LABEL` is `VL` or `L` | `elevate_house`    | **Threat Appraisal Prerequisite.** Expensive mitigation requires a minimum threat threshold to be cost-effective.            | Rogers (1983)               |
| **relocation_threat_low**       | `TP_LABEL` is `VL` or `L` | `relocate`         | **Proportionality.** Relocation is an extreme measure justified only by significant threat.                                  | Bubeck et al. (2012)        |

#### 3. Governance Intervention Flow (Retry Mechanism)

When a **Strict** rule is violated (Level: `ERROR`), the framework does not silently fail. Instead, it triggers a **Cognitive Retry Loop**:

1.  **Block**: The invalid action is intercepted.
2.  **Feedback**: The agent receives a system message explaining _why_ the action was blocked (e.g., "You reasoned that Threat is 'Low', so you cannot choose 'Elevate House'.").
3.  **Retry**: The agent is prompted to generate a new decision considering this feedback.

_Note: In `relaxed` mode, these rules become WARNINGS, logged for audit but allowing the action to proceed._

#### 4. Classic Blocked Examples (From Traces)

**Example 1: The "Logical Disconnect" (Thinking Rule Violation)**

- **Context**: Year 1, No recent floods.
- **Agent Thought**: "I feel **Very Low (VL)** threat since no flood occurred."
- **Agent Decision**: `Elevate House` (Action 4)
- **Outcome**: **BLOCKED** by `elevation_threat_low`.
- **System Feedback**: _"[Rule: elevation_threat_low] Logic Block: elevate_house flagged by thinking rules"_
- **Correction**: Agent retries and chooses `Do Nothing` or `Buy Insurance`.

**Example 2: The "Impossible Action" (Identity Rule Violation)**

- **Context**: Agent already elevated their house in Year 3.
- **Agent Decision**: `Elevate House` (Action 4)
- **Outcome**: **BLOCKED** by `elevation_block`.
- **System Feedback**: _"Action 'elevate_house' is invalid for current state."_

#### 5. Robust Construct Extraction (`synonyms`)

Maps various LLM outputs to standardized internal constructs used by Governance Rules.

- **`tp` (Threat Perception)**: Maps variants like "severity", "danger", or "risk" to the canonical `TP_LABEL`.
- **`cp` (Coping Perception)**: Maps variants like "efficacy", "cost", or "ability" to the canonical `CP_LABEL`.
- This ensures that if Llama says "Risk: High" and Gemma says "Threat: High", the governance layer treats them identically.

#### 6. Protection Motivation Theory (PMT) Mapping

- **`skill_map`**: Maps numbered options (1, 2, 3...) to canonical skill IDs. Coupled with **Option Shuffling**, this prevents positional bias while maintaining consistent rule validation.

---

## Memory & Retrieval System

### Available Memory Engines

| Engine         | Description                                   | Parameters                             | Use Case                |
| -------------- | --------------------------------------------- | -------------------------------------- | ----------------------- |
| `window`       | Sliding window (last N items)                 | `window_size=5`                        | Simple, predictable     |
| `importance`   | Active retrieval (recency + significance)     | `window_size=5`, `top_k_significant=2` | Retains critical events |
| `humancentric` | Emotional encoding + stochastic consolidation | See below                              | Human-realistic memory  |

### Usage

# Human-centric (emotional encoding + stochastic consolidation)

python run_flood.py --model gemma3:4b --memory-engine humancentric

````

### HumanCentricMemoryEngine Parameters

All weights and probabilities use 0-1 scale:

```python
HumanCentricMemoryEngine(
    window_size=5,              # int: Recent items always included
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
    window_size=5,              # int: Recent items always included
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

![Comparison Chart](old_vs_window_vs_humancentric_3x4.png)

- **Llama 3.2 (3B)**: Highly sensitive to social observations. Shows the highest rate of "Decision-Reasoning Gaps," frequently corrected by the Governance Layer.
- **Gemma 3 (4B)**: Most "Optimistic." Tends to prefer "Do Nothing" unless multiple floods are explicitly consolidated in memory. Requires specialized synonym mapping due to unique category naming (e.g., "Concern" vs "Threat").
- **DeepSeek-R1 (8B)**: Exceptional reasoning consistency. Rarely requires Governance retries, as its `<think>` chain aligns well with the PMT constructs. Shows distinct behavioral shifts when emotional memories (Human-Centric) are retrieved.

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
results/
├── Gemma_3_4B/                  # OLD baseline
├── gemma3_4b_strict/            # NEW governed
│   ├── audit_summary.json       # Validation stats
│   ├── household_governance_audit.csv
│   ├── simulation_log.csv       # Decision traces
│   └── comparison_results.png
└── old_vs_new_comparison_2x4.png
```

## Benchmark Analysis

### Statistical Summary (Chi-Square Test)

We performed a **5x2 Chi-Square Test** on the full distribution of agent decisions (Do Nothing, FI, HE, Both, Relocate) to quantify behavioral shifts caused by the Governance Layer and Memory Systems.

| Model              | Comparison (vs Baseline) | p-value      | Significant? |
| :----------------- | :----------------------- | :----------- | :----------- |
| **Gemma 3 (4B)**   | Window Memory            | $p < 0.0001$ | ✅ Yes       |
|                    | Human-Centric Memory     | $p < 0.0001$ | ✅ Yes       |
| **Llama 3.2 (3B)** | Window Memory            | $p < 0.0001$ | ✅ Yes       |
|                    | Human-Centric Memory     | $p < 0.0001$ | ✅ Yes       |

### Governance Validation Findings

- **Active vs Passive Compliance**:
  - **Llama 3.2** attempts proactive measures (Elevation) but often fails strict PMT rules (e.g., `elevation_threat_low`), resulting in a **22% rejection rate** under Window Memory.
  - **Gemma 3** defaults to "Do Nothing" when threat is low, resulting in **0% rejections** but lower overall adaptation.
- **Implication**: The governance layer successfully blocks "hallucinated" or "disproportional" actions from smaller models, enforcing theoretical consistency even when the model's own reasoning is flawed.

Detailed statistical analysis and behavioral comparison (Baseline vs Window vs Human-Centric) can be found here:

- [**📄 Analysis Report (English)**](BENCHMARK_REPORT_EN.md) - Includes Full Distribution Chi-Square tests.
- [**📄 中文分析報告 (Chinese)**](BENCHMARK_REPORT_CH.md)

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

### 1. Protection Motivation Theory (PMT) & Flood Behavior

The governance rules are grounded in the following empirical studies:

1.  **Grothmann, T., & Reusswig, F. (2006).** People at risk of flooding: Why some residents take precautionary action while others do not. _Natural Hazards_, 38(1-2), 101-120. [DOI: 10.1007/s11069-005-8604-6](https://doi.org/10.1007/s11069-005-8604-6)
    - _Basis for Rule 1 (High Threat -> Action)_
2.  **Rogers, R. W. (1983).** Cognitive and physiological processes in fear appeals and attitude change: A revised theory of protection motivation. In _Social Psychophysiology_, Guilford Press.
    - _Basis for Rule 3 (Threat is prerequisite for action)_
3.  **Bamberg, S., et al. (2017).** Threat, coping and flood prevention – A meta-analysis. _Journal of Environmental Psychology_, 54, 116-126. [DOI: 10.1016/j.jenvp.2017.08.001](https://doi.org/10.1016/j.jenvp.2017.08.001)
    - _Basis for Rule 2 (Coping Appraisal importance)_
4.  **Bubeck, P., et al. (2012).** A review of risk perceptions and other factors that influence flood mitigation behavior. _Risk Analysis_, 32(9), 1481-1495. [DOI: 10.1111/j.1539-6924.2011.01783.x](https://doi.org/10.1111/j.1539-6924.2011.01783.x)
    - _Basis for Rule 4 (Experience & Proportionality)_

### 2. Cognitive Memory Systems

- **Park, J. S., et al. (2023).** Generative Agents: Interactive Simulacra of Human Behavior. [arXiv:2304.03442](https://arxiv.org/abs/2304.03442)
- **Tulving, E. (1972).** Episodic and semantic memory. In _Organization of Memory_, Academic Press.

---

_See [`docs/references/pmt_validator_references.md`](../../docs/references/pmt_validator_references.md) for the complete annotated bibliography._
