# Components: Memory and Retrieval System

**🌐 Language: [English](memory_components.md) | [中文](memory_components_zh.md)**

The **Memory and Retrieval System** is the cognitive bridge between an agent's past experiences and its current decision-making. In this framework, we explicitly decouple **Memory (Storage)** from **Retrieval (Access Control)** to ensure that the agent remains rational even under high information density.

---

## 🏛️ Memory Evolution & Roadmap

The system is a **Universal Cognitive Architecture** grounded in established cognitive science, evolving across three specific phases of retrieval depth.

![Memory Evolution Roadmap](../architecture/memory_evolution_roadmap.png)

---

## 1. The Memory Lifecycle: From Perception to Prompt

To understand how our agents "think" about the past, we follow a single event through its lifecycle:

### Step 1: Memory Systems, Appraisal & Symbol Dictionary

#### **A. Strategic Comparison of Memory Systems:**

| Feature               | Model v1: Legacy (Habit)        | Model v2: Weighted (Deliberate)      | Model v3: Universal (Both)    |
| :-------------------- | :------------------------------ | :----------------------------------- | :---------------------------- |
| **Retrieval Logic**   | **Saliency-Based**.             | **Unified Scoring**.                 | **Surprise-Driven Gating**.   |
| **Core Formula**      | $S(t) = I \cdot e^{-\lambda t}$ | $S = W_{rec}R + W_{imp}I + W_{ctx}C$ | Toggles between v1 and v2.    |
| **Design Philosophy** | **Availability Heuristic**.     | **Contextual Relevance**.            | **Cognitive Arousal (PE)**.   |
| **Goal**              | Remember "recent shocks".       | Remember "relevant history".         | **Habit** until **Surprise**. |

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
| $I_{gate}$    | **Consolidation Gate**  | 0.6     | Min. $I_{initial}$ to attempt permanent storage.              |
| $P_{burn}$    | **Burning Probability** | 0.8     | Prob. a memory is consolidated if it passes the gate.         |

> [!NOTE]
> **Why are $R, C,$ and $PE$ "Dynamic Variables"?**
> Unlike static weights ($W$), these values are recalculated during every retrieval cycle/perception step:
>
> - **$R$ (Recency)**: Changes every step because "Time" is constantly moving forward. Yesterday's memory is less "recent" today.
> - **$C$ (Context)**: Changes because it depends on the **current prompt**. A memory of "buying a boat" has $C=0.0$ during a fire, but $C=1.0$ during a flood discussion.
> - **$PE$ (Prediction Error)**: Changes because it is the "Surprise" of the **current moment** (Reality vs. what was expected).

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

V2 uses $S = (R \times 0.3) + (I \times 0.5) + (C \times 0.2)$.

1.  **Memory A (Disaster)**:
    - **Math**: $(R=0.0 \times 0.3) + (I=0.36 \times 0.5) + (C=1.0 \times 0.2) = 0.0 + 0.18 + 0.20 = \mathbf{0.38}$
    - **Why**: The **Context Score** ($C=1.0$) is triggered by the word "Flood" in the current forecast.
2.  **Memory B (Routine)**:
    - **Math**: $(R=0.9 \times 0.3) + (I=0.09 \times 0.5) + (C=0.0 \times 0.2) = 0.27 + 0.045 + 0.0 = \mathbf{0.315}$
    - **Why**: High recency ($R=0.9$) but zero context match ($C=0.0$).
3.  **The Result**: **0.38 > 0.315**. The catastrophe from 10 years ago beats the gardening trip from last year.
4.  **Action**: The agent **purchases flood insurance** immediately.

---

## 3. v3: Universal Memory (The Surprise Engine)

V3 is the "controller" of the cognitive architecture. It models the **Arousal Loop**—deciding when to act on habit (v1) and when to wake up and act rationally (v2).

### 🧠 The Arousal Loop Mechanics

1.  **Sensory Input ($Reality$ from State)**:
    Every cycle, the engine reads the `world_state`. In our case, it tracks the `flood_depth`. This is a **Dynamic State Variable**.
2.  **Internal Prediction ($Expectation$)**:
    The agent maintains an internal "Normalcy Model" using an **EMA Predictor** (Exponential Moving Average).
    - **Formula**: $E_t = (\alpha \times R_t) + ((1 - \alpha) \times E_{t-1})$
    - This creates **Normalcy Bias**: even if a flood starts, the agent's expectation moves slowly, creating a gap between reality and belief.

3.  **Prediction Error ($PE$ / Surprise)**:
    The "Surprise" is the absolute difference: $PE = |Reality - Expectation|$.
    - **Dynamic Calculation**: As $Reality$ shoots up (Flood alert), $PE$ spikes.
    - **Dynamic Toggling**:
      - If $PE < \text{Arousal Threshold}$ (0.5): The agent remains in **System 1 (Model v1)**. It trusts its habits and filters out deep archives.
      - If $PE \ge \text{Arousal Threshold}$: The agent enters **System 2 (Model v2)**. It triggers a "Context Search," enabling the weighted scoring that brings back the 10-year-old flood trauma.

### 🔄 Does v3 change with State?

**YES.** All core components of v3 are state-dependent:

- **Reality**: Direct feed from `world_state`.
- **Expectation**: Updates every step based on new observations.
- **Arousal Mode**: Flips between "Legacy" and "Weighted" based on the current Environment-to-Mind mismatch.

> [!TIP]
> **Theory Link**: This implements **Active Inference (Friston, 2010)**, where the brain's goal is to minimize surprise, and **Thinking, Fast and Slow (Kahneman, 2011)**, which defines the two speeds of thought.

---

## 4. ⚙️ Configuration & References

```yaml
memory_config:
  type: "universal" # v3
  params:
    arousal_threshold: 0.5
    W_recency: 0.3
    W_importance: 0.5
    W_context: 0.2
```

[1] Tversky & Kahneman (1973). _Availability Heuristic_. (v1: Basis for recency/saliency bias).
[2] Friston (2010). _The free-energy principle: a rough guide to the brain?_. (v3: Basis for surprise-driven arousal).
[3] Ebbinghaus (1885). _Memory: A Contribution to Experimental Psychology_. (v1/v2: The Forgetting Curve).
[4] Park et al. (2023). _Generative Agents: Interactive Simulacra of Human Behavior_. (v2: The Weighted Scoring model of _Recency, Importance, and Relevance_).
[5] Kahneman (2011). _Thinking, Fast and Slow_. (v3: Dual-Process Theory - switching between System 1 habits and System 2 rational deliberation).
