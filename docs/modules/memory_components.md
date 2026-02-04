# Components: Memory and Retrieval System

**🌐 Language: [English](memory_components.md) | [中文](memory_components_zh.md)**

The **Memory and Retrieval System** is the cognitive bridge between an agent's past experiences and its current decision-making. In this framework, we explicitly decouple **Memory (Storage)** from **Retrieval (Access Control)** to ensure that the agent remains rational even under high information density.

---

## WRR-Validated Configuration

For all WRR (Water Resources Research) experiments, the **HumanCentricMemoryEngine** in **basic ranking mode** is the validated configuration. This engine combines a recent-window buffer (5 most recent memories) with top-k retrieval (2 highest by decayed importance), using `importance = emotional_weight * source_weight` scoring. See `agent_types.yaml` in each experiment for domain-specific emotion keywords and source patterns.

The memory evolution roadmap below describes the full architecture including experimental engines (v3/v4) that are available but not used in WRR validation experiments.

## Memory Evolution & Roadmap

The system is a **Universal Cognitive Architecture** grounded in established cognitive science, evolving across three specific phases of retrieval depth.

![Memory Evolution: v1 to v4](../architecture/memory_evolution_v4.png)

---

## 1. The Memory Lifecycle: From Perception to Prompt

To understand how our agents "think" about the past, we follow a single event through its lifecycle:

### Step 1: Memory Systems, Appraisal & Symbol Dictionary

#### **A. Strategic Comparison of Memory Systems:**

| Feature               | Model v1: Legacy (Habit)        | Model v2: Weighted (Deliberate)      | Model v3: Universal (Switch)     | Model v4: Symbolic (Gestalt)  |
| :-------------------- | :------------------------------ | :----------------------------------- | :------------------------------- | :---------------------------- |
| **Retrieval Logic**   | **Saliency-Based**.             | **Unified Scoring** + Resonance + Interference. | **Surprise-Driven Gating**.      | **Signature-Based**.          |
| **Core Formula**      | $S(t) = I \cdot e^{-\lambda t}$ | $S = W_rR + W_iI + W_cC + W_{rel}Rel - W_{int}Int$ | $PE = \|Reality - Expectation\|$ | $S = 1 - P(Signature)$        |
| **Design Philosophy** | **Availability Heuristic**.     | **Contextual Relevance** + Cognitive Interference. | **Active Inference**.            | **Bounded Rationality**.      |
| **Goal**              | Remember "recent shocks".       | Remember "relevant history"; forget superseded info. | **Habit** until **Surprise**.    | **Context** without **Cost**. |
| **Status**            | Production (WRR)                | **Production (WRR)** — primary engine | Deprecated (use v2 + plugin)     | Deprecated (use v2 + plugin)  |

#### **B. Parameter & Symbol Dictionary (Scale: 0.0 to 1.0):**

| Symbol        | Component/Parameter     | Default | Definition                                                    |
| :------------ | :---------------------- | :------ | :------------------------------------------------------------ |
| **$R$**       | **Recency Score**       | (Calc)  | $1 - (\text{age} / \text{max\_age})$: Freshness (Now=1.0).    |
| **$I$**       | **Importance Score**    | (Calc)  | $I_{initial} \cdot e^{-\lambda t}$: Decay-adjusted intensity. |
| **$C$**       | **Context Score**       | (Calc)  | Binary match between memory tags and current prompt.          |
| **$PE$**      | **Prediction Error**    | (Calc)  | Level of "Surprise" (Reality vs Expectation).                 |
| **$\lambda$** | **Decay Rate**          | 0.1     | Constant determining forgetting speed.                        |
| $W_{rec}$     | **Recency Weight**      | 0.3     | Weight of "Freshness" in the prompt.                          |
| $W_{imp}$     | **Importance Weight**   | 0.5     | Weight of "Historical Significance" ($I$).                    |
| $W_{ctx}$     | **Context Weight**      | 0.2     | Weight of "Situational Relevance" ($C$).                      |
| $W_{rel}$     | **Relevance Weight**    | 0.0     | Weight for query-memory keyword overlap (P2).                 |
| $W_{int}$     | **Interference Weight** | 0.0     | Weight for retroactive interference penalty (P2).             |
| $\gamma$      | **Interference Cap**    | 0.8     | Max interference penalty (preserves partial retrieval).       |
| $I_{gate}$    | **Consolidation Gate**  | 0.6     | Min. $I_{initial}$ to attempt permanent storage.              |
| $P_{burn}$    | **Burning Probability** | 0.8     | Prob. a memory is consolidated if it passes the gate.         |

#### **C. Importance Calculation Logic (How we derive $I$):**

Importance ($I$) is not random; it is the product of **Emotional Weight** and **Source Reliability**.

$$I_{initial} = W_{emotion} \times W_{source}$$

---

## 2. Practical Case: Household Agent Retrieval Trace

**Current Setting (Year 11)**: The weather forecast just issued a **Red Alert**. Forecast: "Extreme rainfall expected. High risk of river flood."

> **Current Tags**: `[Flood, Danger, Rain]`

The agent has the following two historical memories stored in its long-term archive:

- **Memory A (The Disaster)**: "Year 1: A massive flood breached the levee. My basement was under 2 feet of water, and I lost all my furniture. It was terrifying."
  - **Stats**: $I_{initial}=1.0$, Age=10, Tags: `[Flood]`.
- **Memory B (The Routine)**: "Year 10: The sun was out all day. I spent the afternoon gardening in the backyard. It was a normal, quiet Saturday."
  - **Stats**: $I_{initial}=0.1$, Age=1, Tags: `[Routine]`.

---

#### **Model v1: The Habitual Agent (Habit)**

V1 only cares about Saliency ($I \cdot e^{-\lambda t}$).

1.  **Memory A Score**: $1.0 \cdot e^{-(0.1 \times 10)} = 0.36$.
2.  **Memory B Score**: $0.1 \cdot e^{-(0.1 \times 1)} \approx 0.09$.
3.  **The Result**: Memory A (Flood) is decaying. It is being heavily crowded out by the **Working Memory Window**, which is full of hundreds of routine memories like Memory B (Recent Sunny Days) with $S \approx 1.0$.
4.  **Action**: The agent stays calm and **ignores the warning** because the "Normalcy Bias" of the last 9 sunny years dominates its thoughts.

---

#### **Model v2: The Rational Agent (Deliberate)**

V2 uses $S = (R \times W_r) + (I \times W_i) + (C \times W_c) + (Rel \times W_{rel}) - (Int \times W_{int})$.
With defaults $W_r{=}0.3,\; W_i{=}0.5,\; W_c{=}0.2,\; W_{rel}{=}0,\; W_{int}{=}0$ this reduces to the classic formula.

1.  **Memory A (Disaster)**:
    - **Math**: $(R=0.0 \times 0.3) + (I=0.36 \times 0.5) + (C=1.0 \times 0.2) = 0.0 + 0.18 + 0.20 = \mathbf{0.38}$
    - **Why**: The **Context Score** ($C=1.0$) is triggered by the word "Flood" in the current forecast.
2.  **Memory B (Routine)**:
    - **Math**: $(R=0.9 \times 0.3) + (I=0.09 \times 0.5) + (C=0.0 \times 0.2) = 0.27 + 0.045 + 0.0 = \mathbf{0.315}$
    - **Why**: High recency ($R=0.9$) but zero context match ($C=0.0$).
3.  **The Result**: **0.38 > 0.315**. The catastrophe from 10 years ago beats the gardening trip from last year.
4.  **Action**: The agent **purchases flood insurance** immediately.

---

## 2b. v2-next: Cognitive Innovations (P0-P2)

The v2 engine received three rounds of enhancements that make it a self-contained cognitive memory system, eliminating the need for the v3/v4 wrappers in most scenarios.

### P0 — Critical Bug Fixes

- **Dual-storage isolation**: Consolidated memories are now `deepcopy`'d into long-term, preventing shared-reference mutations.
- **Memory capacity limits**: New `max_working` / `max_longterm` parameters with smart eviction (consolidated-first for working, lowest-importance for long-term). Defaults to 0 (unlimited) for backward compatibility.

### P2 — Three Retrieval Innovations

#### Contextual Resonance ($Rel$)

When a retrieval query is provided, each memory receives a **relevance score** based on keyword overlap (overlap coefficient):

$$Rel = \frac{|Q \cap M|}{\min(|Q|, |M|)}$$

where $Q$ and $M$ are the keyword sets (after stopword removal) of the query and memory content respectively. Activated by setting `W_relevance > 0`.

**Reference**: Park et al. (2023) *relevance* dimension; Tulving (1972) encoding-specificity principle.

#### Interference-Based Forgetting ($Int$)

Newer memories with similar content **retroactively suppress** older memories, modelling the well-established retroactive-interference effect:

$$Int = \min(\max_{m' \in newer}(Rel(m, m')) \cdot \gamma,\; \gamma)$$

where $\gamma$ is the interference cap (default 0.8). Activated by setting `W_interference > 0`.

**Reference**: Anderson & Neely (1996); Wixted (2004).

#### Decision-Consistency Surprise (DCS Plugin)

A **domain-agnostic** surprise strategy based on the agent's own action history. Unlike EMA (requires a stimulus key) or Symbolic (requires sensor config), DCS needs **zero domain configuration**:

- **Unigram mode**: $Surprise = 1 - P(action \mid history)$ with Laplace smoothing
- **Bigram mode**: $Surprise = 1 - P(action \mid prev\_action)$ for transition-aware detection

Available at `cognitive_governance.memory.strategies.DecisionConsistencySurprise`.

**Reference**: Itti & Baldi (2009) Bayesian Surprise; Sun et al. (2016) KISS principle.

### P1 — SurprisePlugin Interface

The v2 engine now accepts an **optional** `surprise_strategy` parameter, replacing the heavyweight v3/v4 wrapper pattern (~680 lines) with 4 lightweight methods:

| Method | Returns | Purpose |
| :--- | :--- | :--- |
| `observe(obs)` | `float` | Feed observation to plugin, get surprise [0-1] |
| `get_cognitive_system()` | `str` | `"SYSTEM_1"` or `"SYSTEM_2"` based on arousal |
| `reset_surprise()` | `None` | Reset plugin state for new episode |
| `get_surprise_trace()` | `dict` | XAI trace from the plugin |

When no plugin is attached, all methods return safe defaults (0.0 / SYSTEM_1 / None).

---

## 3. v3: Universal Memory (The Surprise Engine)

> **Deprecation notice**: v3 is superseded by v2 + SurprisePlugin (P1). Use `HumanCentricMemoryEngine(surprise_strategy=EMASurpriseStrategy(...))` instead.

V3 is the "controller" of the cognitive architecture. It models the **Arousal Loop**—deciding when to act on habit (v1) and when to wake up and act rationally (v2).

### 3.1 The Arousal Loop Mechanics

1.  **Sensory Input ($Reality$)**: The agent sees `flood_depth = 2.0m`.
2.  **Internal Prediction ($Expectation$)**: The agent expects `flood_depth = 0.1m` (based on EMA of past years).
3.  **Surprise ($PE$)**: $PE = |2.0 - 0.1| = 1.9$.
4.  **Arousal Switch**:
    - If $PE \ge 0.5$ (Threshold): **Switch to System 2**.

---

## 4. v4: The Symbolic Architecture (Symbolic Context)

> **Deprecation notice**: v4 is superseded by v2 + SurprisePlugin (P1). Use `HumanCentricMemoryEngine(surprise_strategy=SymbolicSurpriseStrategy(...))` instead.

### 4.1 Motivation: Why Symbolic? (The "Goldilocks" Solution)

- **Problem with v3 (Scalar)**: Single-variable thresholds (e.g., `Depth > 0.5`) are brittle. They fail to capture complex context (e.g., "High Water" is fine if it's a "Controlled Release").
- **Problem with Vector Embeddings**: While powerful, calculating 1000-dimensional cosine similarities for every agent step is **computationally prohibitive** ($O(N)$) for 100+ agents.
- **The v4 Solution**: **Symbolic Signatures**. By hashing discrete states, we get the **contextual flexibility** of vectors with the **$O(1)$ speed** of hash maps.

### 4.2 The Mechanism

1.  **Sensors**: Detect `FLOOD:HIGH` and `PANIC:LOW`.
2.  **Signature**: `Hash("FLOOD:HIGH|PANIC:LOW")`.
3.  **Surprise**: $S = 1 - P(\text{Signature})$.

### 4.3 Practical Calculation: The "Boiling Frog" Trace

**Q: How does the agent react to repeating disasters?**

| Year    | Event (Stimulus) | Signature                           | Probability ($P$) | Surprise ($S = 1-P$) | System State                | Agent Action       |
| :------ | :--------------- | :---------------------------------- | :---------------- | :------------------- | :-------------------------- | :----------------- |
| **Y1**  | **Flash Flood**  | `FLOOD:HIGH`                        | 0.0 (New)         | **1.0 (High)**       | **System 2 (Panic)**        | **Buy Insurance**  |
| **Y2**  | Flood Again      | `FLOOD:HIGH`                        | 0.5 (Seen)        | 0.5 (Med)            | System 1 (Habit)            | Renew / Complacent |
| **Y3**  | Flood Again      | `FLOOD:HIGH`                        | 0.66 (Common)     | 0.33 (Low)           | System 1 (Habit)            | Ignore / Numb      |
| **Y4**  | Flood Again      | `FLOOD:HIGH`                        | 0.75 (Frequent)   | 0.25 (Very Low)      | **System 1 (Boiling Frog)** | **Do Nothing**     |
| **Y10** | **New Context**  | `FLOOD:HIGH` + `NEIGHBOR:ELEVATING` | 0.0 (New Combo)   | **1.0 (High)**       | **System 2 (Wake Up)**      | **Elevate House**  |

> [!IMPORTANT]
> **The Boiling Frog Effect**: Note how in Year 4, despite the high risk (`FLOOD:HIGH`), the Surprise is effectively zero ($S=0.25$). The agent has "normalized" the disaster. Only a **Context Shift** (Year 10) can break this habit loop.

---

## 5. Related Components

- **[Reflection Engine (Meta-Cognition)](reflection_engine.md)**: Defines how this memory system's outputs are processed into semantic wisdom.
- **[Simulation Engine](../modules/simulation_engine.md)**: The environment that generates the `Event` and `Observation` signals.

### 5.1 Cognitive Constraints (Memory Capacity)

The `CognitiveConstraints` dataclass (`cognitive_governance/memory/config/cognitive_constraints.py`) parameterizes how many memories are retrieved per arousal level, grounded in established psychology:

- **System 1 (Low arousal)**: 5 recent memories (Cowan 2001: working memory holds 4±1 items)
- **System 2 (High arousal)**: 7 recent memories (Miller 1956: 7±2 chunks)
- **Supplemental**: +2 high-importance long-term memories regardless of arousal

| Profile | System 1 | System 2 | Working Capacity | Use Case |
| :------ | :------- | :------- | :--------------- | :------- |
| `MILLER_STANDARD` | 5 | 7 | 10 | Recommended default |
| `COWAN_CONSERVATIVE` | 3 | 5 | 7 | Resource-constrained |
| `EXTENDED_CONTEXT` | 7 | 9 | 15 | Complex reasoning |
| `MINIMAL` | 3 | 4 | 5 | Fast inference / small models |

The `get_memory_count(arousal)` method interpolates between System 1 and System 2 counts based on the current arousal level, providing smooth transitions rather than a hard cutoff.

### 5.2 Advanced Extensions (cognitive_governance/)

The following capabilities exist in the `cognitive_governance/` extension package:

- **Decision-Consistency Surprise** (`cognitive_governance/memory/strategies/decision_consistency.py`): Domain-agnostic action-history surprise. **Integrated** via P1 SurprisePlugin interface.
- **EMA Surprise** (`cognitive_governance/memory/strategies/ema.py`): Scalar EMA-based surprise. **Integrated** via P1 SurprisePlugin.
- **Symbolic Surprise** (`cognitive_governance/memory/strategies/symbolic.py`): Frequency-based state signature surprise. **Integrated** via P1 SurprisePlugin.
- **Multi-dimensional Surprise** (`cognitive_governance/memory/strategies/multidimensional.py`): Extends scalar PE to a vector of surprise dimensions for richer arousal modeling.
- **Embedding-based Retrieval** (`cognitive_governance/memory/embeddings.py`): Vector similarity search using `all-MiniLM-L6-v2` via `SentenceTransformerProvider`. Alternative to keyword/tag matching.
- **Memory Graph** (`cognitive_governance/memory/`): Bidirectional linking between memories for associative retrieval.

---

## 6. Configuration & References

```yaml
# Recommended v2 configuration (production)
memory_config:
  type: "humancentric"
  params:
    ranking_mode: "weighted"
    W_recency: 0.3
    W_importance: 0.5
    W_context: 0.2
    # P2 innovations (set > 0 to enable)
    W_relevance: 0.0        # Contextual Resonance
    W_interference: 0.0     # Interference-Based Forgetting
    interference_cap: 0.8
    # Capacity limits (0 = unlimited)
    max_working: 0
    max_longterm: 0
    # P1 surprise plugin (optional, configured in code)
    # surprise_strategy: DecisionConsistencySurprise(mode="unigram")
    # arousal_threshold: 0.5
```

### References

[1] **Tversky & Kahneman (1973)**. *Availability Heuristic*. (Basis for Recency Bias).
[2] **Friston (2010)**. *The free-energy principle*. (Basis for Surprise Minimization).
[3] **Kahneman (2011)**. *Thinking, Fast and Slow*. (Dual-Process Theory).
[4] **Park et al. (2023)**. *Generative Agents*. (Recency x Importance x Relevance).
[5] **Anderson & Neely (1996)**. *Retroactive Interference*. (Basis for Interference-Based Forgetting).
[6] **Itti & Baldi (2009)**. *Bayesian Surprise*. (Basis for DCS plugin).
[7] **Sun et al. (2016)**. *KISS for ABM*. (Mechanism complexity justification).
[8] **Tulving (1972)**. *Episodic vs Semantic Memory*. (Encoding-specificity principle).
