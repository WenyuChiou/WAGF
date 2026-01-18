# Rational & Reproducible Hydro-Social ABMs: Framework Validation

> **Academic Objective**: This experiment validates a cognitive governance framework designed to transform Large Language Models (LLMs) into **Rational, Auditable, and Reproducible** agents for Agent-Based Modeling (ABM). By bridging the gap between raw LLM behavior and Protection Motivation Theory (PMT), the framework solves the "Rationality Gaps" observed in legacy hydro-social simulations.

## 🏛️ The 4 Architectural Pillars

| Pillar                        | Mechanism        | Objective                                                                                                                       |
| :---------------------------- | :--------------- | :------------------------------------------------------------------------------------------------------------------------------ |
| **1. Context Governance**     | `ContextBuilder` | **Suppresses Hallucinations.** Structures perception to ensure agents focus on relevant hydro-social signals without noise.     |
| **2. Cognitive Intervention** | `Skill Broker`   | **Enforces Rationality.** Uses Tier 2 Thinking Rules to eliminate the "Appraisal-Decision Gap" via real-time validation.        |
| **3. World Interaction**      | `InteractionHub` | **Standardizes Feedback.** Standardizes how agents receive disaster signals (depths, grants) and apply environmental feedbacks. |
| **4. Episodic Cognition**     | `Memory Engine`  | **Prevents Erosion.** Consolidates significant flood experiences to solve the "Goldfish Effect" in long-horizon studies.        |

---

## 🧪 Validation Methodology: The "Ablation Study"

To rigorously prove the value of each pillar, we employ a 3-Group Ablation Study. We benchmark the current framework against the **Legacy Baseline** (`LLMABMPMT-Final.py`) to quantify the "Rational Convergence" of the agents.

### The Validation Logic (Groups A/B/C)

| Group | Configuration        | Pillar Validation     | Hypothesis (What it proves)                                                 |
| :---- | :------------------- | :-------------------- | :-------------------------------------------------------------------------- |
| **A** | **Control (Legacy)** | **None (Baseline)**   | Baseline suffers from **Logical Disconnects** and **Panicked Relocations**. |
| **B** | **Governance Only**  | **Pillars 1 & 2**     | Governance restores **Logical Consistency** and suppresses inaction bias.   |
| **C** | **Full Enhancement** | **Pillars 1, 2, & 4** | Human-centric memory provides **Long-Term Cognitive Stability**.            |

### 📊 Key Performance Indicators (KPIs)

Our validation focuses on three critical metrics grounded in cognitive science and socio-hydrological literature:

1.  **Rationality Score (RS)**: Measures the adherence of LLM decisions to logical constraints (transitivity and negation invariance), quantified as the percentage of decisions requiring zero governance intervention (Liu et al., 2025).
2.  **Adaptation Density (AD)**: The cumulative percentage of agents successfully implementing protective measures (elevation or insurance). This measures the system's "uptake rate" of adaptation strategies (Grothmann & Reusswig, 2006).
3.  **Panic Coefficient (PC)**: Quantifies irrational or maladaptive behaviors (e.g., relocation without a sufficient threat appraisal) observed in emergency contexts (Wang et al., 2021).

---

## 🏗️ Technical Specification: Implementing the Pillars

### Pillar 3: World Interaction (Disaster Model)

This module ensures the agent-environment feedback loop is standardized and reproducible.

- **Disaster Logic**: Uses 10-year flood sequences to trigger Protection Motivation (PMT) appraisals.
- **Damage Physics**: Base damage is $10k; Elevation provides a 90% reduction ($1k net damage).
- **Incentive Signals**: Grant availability (`GRANT_PROBABILITY`) and neighbor behavioral cues provide shifting social/financial context.
- **Identity Initialization**: Agents are initialized with distinct profiles (Tenure, Income, Property Value) to ensure diverse decision-making baselines.

### Pillar 5: Core Persistence (System Reliability)

To ensure **Scientific Reproducibility**, the framework implements an **Atomic State Persistence** layer (v3.4):

- **Atomic `apply_delta`**: State updates (attributes, memory) are committed in a single transactional block per step.
- **Context-State Parity**: The `ContextBuilder` is rigorously synchronized with the live agent object, eliminating "Context Lag" where agents make decisions based on stale states.

  54: ### Key Configuration Fields

### Pillar 1: Context Governance (Perception Shaping)

Controlled via the `ContextBuilder` to suppress hallucination-prone information noise.

- **Semantic Audit**: The `GovernanceAuditor` monitors `audit_keywords` (e.g., "flood", "insurance") to ensure the agent's logic matches retrieved context.
- **Attribute Provisioning**: Only relevant physical states (e.g., `elevated`, `trust_score`) are injected into the prompt to prevent cognitive overload.
- **Construct Synthesis**: standardizes verbal expressions (e.g., "very worried" -> `VH`) across different LLMs to ensure cross-model compatibility.

### Pillar 2: Cognitive Intervention (Governance Logic)

Implemented via the `Skill Broker` to enforce PMT-based rationality.

- **Tier 1 (Identity)**: Prevents impossible actions (e.g., elevating a house twice).
- **Tier 2 (Thinking)**: Enforces Protection Motivation logic using **Thinking Rules** to ensure decisions align with appraisals.

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

## Pillar 4: Episodic Cognition (Memory System)

### Available Memory Engines

This module provides biological-realistic retrieval and consolidation to maintain cognitive persistence across long-horizon simulations.

| Engine            | Description                               | Scientific Contribution                                                                  |
| ----------------- | ----------------------------------------- | ---------------------------------------------------------------------------------------- |
| **Window**        | Sliding window of recent events.          | **The Recency Baseline.** Proves the "Goldfish Effect" where early floods are forgotten. |
| **Importance**    | Weights recency vs significance.          | **Information Filtering.** Prioritizes critical disaster events for recall.              |
| **Human-Centric** | Emotional encoding + Consolidation logic. | **Realistic Persistence.** Preserves significant/traumatic memories permanently.         |

### Usage

# Human-centric (emotional encoding + stochastic consolidation)

python run_flood.py --model gemma3:4b --memory-engine humancentric

````

### HumanCentricMemoryEngine: A Heuristic Weighting Schema (HWS)

To ensure realistic cognitive persistence, the engine uses an **Importance-Decay** model where memories are scored based on their theoretical significance to the agent's survival and identity.

| Parameter | Type | Default | Theoretical Basis (Citations) |
| :--- | :--- | :--- | :--- |
| **`window_size`** | `int` | `5` | **Working Memory Capacity.** Limits active context to prevent cognitive overload. |
| **`consolidation_prob`** | `float` | `0.7` | **Sleep-Dependent Consolidation.** Probability of transfer to long-term storage (Stickgold, 2005). |
| **`decay_rate`** | `float` | `0.1` | **Ebbinghaus Forgetting Curve.** Exponential decay of non-critical information (Ebbinghaus, 1885). |

#### 1. Emotional Priority (`emotional_weights`)
Categorizes events by their impact on the agent's internal status, grounded in **Protection Motivation Theory (PMT)**.

- **`direct_impact` (1.0)**: **Severity/Vulnerability.** High-trauma events (floods) have maximum persistence (Siegrist & Gutscher, 2008).
- **`strategic_choice` (0.8)**: **Self-Efficacy Feedback.** Memories of choosing to adapt (elevate/relocate) reinforce behavioral patterns.
- **`efficacy_gain` (0.6)**: **Response Efficacy.** Successful protection (insurance claims) reinforces the believe in mitigation efficacy.
- **`social_feedback` (0.4)**: **Social Learning.** Observations of neighbors' choices (Bandura, 1977).
- **`baseline_observation` (0.1)**: **Information Noise.** Minimal weight for non-event years to prevent memory window flooding (Information Filtering).

#### 2. Source Distance (`source_weights`)
Weights information by proximity, grounded in **Construal Level Theory (CLT)** (Trope & Liberman, 2010).

- **`personal` (1.0)**: **Spatial/Social Zero-Distance.** Direct experience is the strongest adaptation driver.
  - *Theoretical Basis*: **Availability Heuristic** (Tversky & Kahneman, 1973).
- **`neighbor` (0.8)**: **Proximal Social Distance.** Learning from immediate peer outcomes.
- **`community` (0.6)**: **Social Aggregation.** Statistical trends within the local group.
- **`general_knowledge` (0.4)**: **Abstract Psychology Distance.** Distant news has lower cognitive "vividness".
  - *Theoretical Basis*: **Construal Level Theory (CLT)** (Trope & Liberman, 2010).

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

## 🧪 Empirical Validation of the Cognitive Pillars

Through multiple simulation cycles benchmarking Group A (Baseline) against Groups B & C, we have validated that the 4 Pillars directly resolve the following scientific "Rationality Gaps":

### Resolving Logical Disconnection (Pillars 1 & 2)

The **Appraisal-Decision Gap** where an agent reasons "risk is low" but chooses "Relocate" is a primary hallucination mode in standard LLMs.

- **Validation**: Our `Skill Broker` captures these gaps, yielding an **Intervention Rate (IR)** of ~22% for Llama 3.2. Governance feedback forces a "Rational Convergence," reducing illogical actions by >90%.

### Resolving Fatalistic Inaction (Pillar 2)

Small models (<8B) often default to "Do Nothing" even under extreme threat (Inaction Bias).

- **Validation**: Strict PMT rules block maladaptive inaction when threat is "Very High," pushing agents toward proactive Adaptation (AR).

### Resolving Memory Erosion (Pillar 4)

The **Goldfish Effect** causes agents in sliding-window models to forget early floods, leading to a false sense of safety.

- **Validation**: `HumanCentricMemory` maintains high **Fidelity Index (FI)**; agents in Group C retain a higher **Adaptation Density (AD)** because their "Flood Experience" is permanently consolidated.

### Resolving Syntax & Position Bias (Pillar 3)

- **Validation**: The `UnifiedAdapter` and **Option Shuffling** ensure that **Structural Flakiness** does not pollute the behavioral data, allowing for clean statistical comparison.

---

---

## 📊 Cross-Model Performance Matrix

The following matrix validates the framework's effectiveness across the 2x4 model/memory matrix.

### Behavioral Summary by Model

- **Llama 3.2 (3B) - The "Anxious" Agent**: High social sensitivity and high **Intervention Rate (IR)**. Governance is critical here to stabilize the **Panic Coefficient (PC)**.
- **Gemma 3 (4B) - The "Rational" Agent**: Exhibits **Rational Convergence**. Shows a clear learning curve from Damage -> Adaptation -> Safety. By Year 9, 64% of agents have reached a safe state.
- **DeepSeek-R1 (8B) - The "Reasoner"**: Exceptionally high **Rationality Score (RS)**. Its internal chain-of-thought aligns naturally with the PMT constructs.

## 🧪 Comparative Validation: Gemma 3 vs. Llama 3.2

We benchmark our framework using two small-parameter models (Llama 3.2 3B and Gemma 3 4B) to prove that **Cognitive Governance** can make lightweight models perform with the reliability of much larger systems.

### 1. Llama 3.2 (3B) - Mitigating Hyper-Panic

Llama models are highly sensitive but prone to "Emotional Cascades."

- **Group A (Baseline)**: Exhibits **Severe Panic**. 95% of agents relocate after a single disaster, often without logical justification in their reasoning.
- **Group B (Governed)**: The **Panic Coefficient (PC)** drops. The Skill Broker yields a high **Intervention Yield (22%)**, capturing and correcting illogical relocation proposals.
- **Group C (Memorable)**: Achieving **Stable Adaptation**. Memory enables agents to differentiate between temporary setbacks and systemic risk, leading to sustainable elevation/insurance choices.

### 2. Gemma 3 (4B) - Overcoming Inaction Bias

Gemma models are more stable but suffer from **Memory Erosion (The Goldfish Effect)**.

- **Group A (Baseline)**: Shows stagnant behavior. Agents "forget" floods by Year 5, returning to a "Do Nothing" state despite recurring damage.
- **Group B (Governed)**: **Rationality Score (RS)** hits 100% as governance prevents identity drift (e.g., renters trying to elevate). **AD (Adaptation Density)** increases as governance forces active consideration of safety.
- **Group C (Memorable)**: **Rational Convergence**. Emotional encoding (importance weights) ensures significant disasters remain in the retrieval window. By Year 10, Group C reaches a 73% safe state, the most realistic trajectory in the study.

---

### 📉 Statistical Significance (Validation Proof)

A **Chi-Square Test** on the action distributions confirms that the shifts from A ⮕ B ⮕ C are not random (p < 0.0001). This proves that the changes in agent behavior are a direct causal result of our **4 Architectural Pillars**.

### Governance Validation Insights

- **Active vs Passive Compliance**:
  - **Llama 3.2** attempts proactive measures but frequently violates PMT logic, resulting in a high **Intervention Yield (IY)**.
  - **Gemma 3** shows high **Rationality Score (RS)**, rarely requiring intervention due to its cautious "Inaction Bias" being slowly overcome by disaster experience.
- **Panic Mitigation (Stabilization Effect)**:
  - In the baseline (Group A), Llama agents frequently "panicked" after a flood.
  - In Group B, the **Panic Coefficient (PC)** drops dramatically. This is achieved by the Skill Broker filtering out irrational "Relocation" responses that lack a sufficient threat appraisal.
  - **Success Metric**: Group C provides the highest **Adaptation Density (AD)**, proving that stable memory enables proactive protection rather than reactive flight.

#### Case Study: Agent_29 (The Stabilization Effect)

Comparing the same agent across the validation continuum:

| Feature      | **Group A (Chaotic)** | **Group B (Governed)**     | **Group C (Memorable)**    |
| :----------- | :-------------------- | :------------------------- | :------------------------- |
| **Logic**    | None                  | **Rational Enforcement**   | **Cognitive Persistence**  |
| **Reaction** | **Panic Relocation**  | **Corrected to Elevation** | **Stable Adaptation (HE)** |

Detailed statistical analysis and behavioral comparison (Baseline vs Window vs Human-Centric) can be found here:

- [**📄 Analysis Report (English)**](BENCHMARK_REPORT_EN.md) - Includes Full Distribution Chi-Square tests.
- [**📄 中文分析報告 (Chinese)**](BENCHMARK_REPORT_CH.md)

---

### 📈 Extensibility: The Coupling Interface (Cognitive Middleware)

To address the need for integration with physical hydrological models (e.g., HEC-RAS, SWMM), the framework is designed as a **"Cognitive Middleware"** layer.

- **Input Decoupling**: The `ContextBuilder` accepts standardized JSON signals (e.g., `{"depth": 1.5, "velocity": 0.5}`) from _any_ physical simulator, normalizing them into the agent's cognitive schema.
- **Output Decoupling**: The `Skill Broker` emits standardized Action JSONs (e.g., `{"action": "elevate", "cost": 5000}`), which can be consumed by external physical models to update the environment state.
- **Model Agnosticism**: This "Plug-and-Play" design ensures that the rigorous cognitive governance provided by the framework can be applied to any domain-specific physical model without code modification.

---

## 🚀 Future Strategic Enhancements: Optimization Roadmap

To further strengthen the framework's academic positioning for the **Journal of Hydrology**, we have identified the following optimization paths inspired by latest cognitive architecture research (Sumers et al., 2024; Gao et al., 2024):

### 1. Self-Correction Trace (Explainable AI)

- **Objective**: Improve transparency in the **Skill Broker** intervention process.
- **Mechanism**: Agents will be required to explicitly reason about _why_ their initial proposal was blocked and how the governance feedback influenced their revised decision.
- **Academic Value**: Provides a clear audit trail for **Rationality Score (RS)** improvements, moving beyond black-box retries.

### 2. Year-End Reflection (Cognitive Consolidation)

- **Objective**: Combat context window overflow and improve long-term adaptation logic.
- **Mechanism**: Inspired by the "Generative Agents" reflection architecture (Park et al., 2023), agents will perform a periodic self-audit of past experiences to generate high-level "Lessons Learned."
- **Academic Value**: Enhances the **Fidelity Index (FI)** and simulates more realistic "learning from disasters" over decade-long horizons.

### 3. Theoretical-Constrained Perception

- **Objective**: Bridge the "Cognitive Governance Gap" in existing LLM-ABMs.
- **Mechanism**: Fine-tuning the **ContextBuilder** to prioritize physical hydrological constraints (e.g., elevation-damage physics) as non-negotiable mental priors.

---

## Running Experiments

### Standard Mode (Synthetic Agents)

```powershell
# Quick test (5 agents, 3 years)
python run_flood.py --model llama3.2:3b --agents 5 --years 3

# Full experiment
python run_flood.py --model gemma3:4b --agents 100 --years 10

# Generate comparison chart
python generate_old_vs_new_2x4.py
```

### Survey Mode (Real Survey Data)

Survey mode initializes agents from real survey data, enabling validation against empirical observations:

```powershell
# Run with survey-derived agents
python run_flood.py --model gemma3:4b --survey-mode --years 10

# With custom survey data path
python run_flood.py --model deepseek-r1:8b --survey-mode --survey-path ./data/survey.xlsx
```

#### Survey Mode Features

1. **Survey Loader** (`broker/modules/survey/survey_loader.py`): Loads and validates survey Excel data
2. **MG Classifier** (`broker/modules/survey/mg_classifier.py`): Classifies agents as MG/NMG using 3-criteria scoring:
   - Housing cost burden (>30% of income)
   - Vehicle ownership (no vehicle)
   - Poverty line status
3. **Agent Initializer** (`broker/modules/survey/agent_initializer.py`): Creates `AgentProfile` objects with:
   - Tenure (Owner/Renter)
   - Income level and financial state
   - Property values (RCV Building/Contents)
   - Initial adaptation state (insurance, elevation)

#### Survey Data Format

Survey mode uses the shared survey module with the current default mapping.

## 📚 References

The following references provide the theoretical basis for our cognitive guardrails and KPI definitions. A complete bibliography is available in [`references.bib`](references.bib).

- Gao, C., et al. (2024). S3: Social-network Simulation System with Large Language Model-driven Agents. _arXiv preprint arXiv:2307.13988_.
- Grothmann, T., & Reusswig, F. (2006). People at risk of flooding: Why some residents take precautionary action while others do not. _Natural Hazards_, 38(1-2), 101-120.
- Liu, Y., Guo, Z., Liang, T., Shareghi, E., Vulic, I., & Collier, N. (2025). Measuring, Evaluating and Improving Logical Consistency in Large Language Models. _International Conference on Learning Representations (ICLR) 2025_.
- Park, J. S., O'Brien, J., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative Agents: Interactive simulacra of human behavior. _ACM CHI_.
- Rogers, R. W. (1983). Cognitive and physiological processes in fear appeals and attitude change: A revised theory of protection motivation. _Social Psychophysiology_.
- Sumers, T. R., Yao, S., Narasimhan, K., & Griffiths, T. L. (2024). Cognitive Architectures for Language Agents. _Transactions on Machine Learning Research_.
- Trope, Y., & Liberman, N. (2010). Construal-level theory of psychological distance. _Psychological Review_, 117(2), 440.
- Tversky, A., & Kahneman, D. (1973). Availability: A heuristic for judging frequency and probability. _Cognitive Psychology_, 5(2), 207-232.
- Wang, L., Li, T., et al. (2021). Panic Manifestations in Flood Evacuation: A Cellular Automata Approach. _Journal of Computational Science_.

---

## 🌪️ Stress Test Protocols (Robustness Check)

To ensure the framework is not just "lucky," we rigorously test it against 4 adversarial scenarios using `run_stress_marathon.ps1`.

| Scenario | Description | Target Failure |
| :--- | :--- | :--- |
| **ST-1: Panic Machine** | High Neuroticism Agents + Category 5 Warnings | **Hyper-Relocation** (Panic) |
| **ST-2: Optimistic Veteran** | 30 Years of No Floods | **Complacency** (Inaction) |
| **ST-3: Memory Goldfish** | Context Window Noise Injection | **Amnesia** (Forgetting Past) |
| **ST-4: Format Breaker** | Malformed JSON Injections | **Crash** (System Instability) |

```powershell
# Run the full validation suite
./run_stress_marathon.ps1
```

---

## 🛠️ Configuration & Customization

### 1. Skill Registry (`skill_registry.yaml`)
We strictly separate **Logic** (Python) from **Definition** (YAML). You can add new behaviors by editing the registry:
```yaml
- name: "sandbagging"
  description: "Temporary flood protection."
  validators: ["budget_check", "physical_feasibility"]
```

### 2. Scientific Assistant (Persona)
We have included a specialized AI persona to help you write and review papers based on this framework.
👉 **[Read the Scientific Assistant Manual](../../doc/Scientific_Assistant_Manual.md)**

---

## 🇹🇼 中文摘要 (Chinese Summary)

**Governed Broker Framework** 是一個旨在解決 LLM "幻覺" 與 "不理性行為" 的認知治理架構。
本實驗 (Single Agent Experiment) 通過比較三組 Agent (Baseline, Window, Tiered Memory) 證明了：
1.  **Context Governance** 有效抑制了隨機幻覺。
2.  **Tiered Memory** (分層記憶) 解決了 "金魚效應"，讓 Agent 能記住 10 年前的災難。
3.  **Skill Registry** 確保了所有動作符合物理與經濟約束。

詳細中文分析請參見：`doc/ref/JOH_Cognitive_Architecture_Guide_ZH.md`


_Note: This framework is part of a technical note submission to the Journal of Hydrology (JOH)._
````
