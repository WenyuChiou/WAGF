# Components: The Reflection Engine (Meta-Cognition)

**🌐 Language: [English](reflection_engine.md) | [中文](reflection_engine_zh.md)**

While the **Memory System** stores the "What" (Episodic Events), the **Reflection Engine** produces the "Why" (Semantic Wisdom). It serves as the meta-cognitive layer of the agent, transforming raw experience into actionable insights.

---

## 1. The Mechanics of Reflection

### 1.1 The Loop: From Experience to Wisdom

1.  **Input (Episodic)**: "Year 1: Flood." + "Year 1: Bought Insurance."
2.  **Process (Reasoning)**: The LLM analyzes the causal link between Event and Action.
3.  **Output (Semantic)**: "Insight: Insurance is critical for financial survival during floods."

### 1.2 Decision vs. Reflection

| Feature          | Decision Logic (System 1/2)  | Reflection Logic (Meta)                |
| :--------------- | :--------------------------- | :------------------------------------- |
| **Question**     | "What should I do **NOW**?"  | "Was my past decision **GOOD**?"       |
| **Time Horizon** | Present / Immediate Future   | Past / Long-term Future                |
| **Mechanism**    | In-Context Learning          | Offline batch processing               |
| **Output**       | Action (e.g., Buy Insurance) | Wisdom (e.g., "Floods are increasing") |

**Without Reflection**, the agent is smart but static. **With Reflection**, the agent evolves its mental model over time, becoming more resilient to memory decay (The Goldfish Effect).

---

## 2. Theoretical Benefits of Reflection

Why invest computational resources in reflection? Behavioral science suggests three key benefits:

### 2.1 Double-Loop Learning (Argyris & Schön)

- **Single-Loop**: "Thermostat behavior." Correcting actions to match a goal (e.g., buying insurance to fix a loss).
- **Double-Loop**: "Questioning the goal." Reflection allows the agent to ask: _"Is living here even sustainable?"_ This leads to fundamental behavioral shifts (e.g., Relocation) rather than just iterative fixes.

### 2.2 Cognitive Economy (The Map vs. Territory)

- Raw episodic memory is expensive to search (The "Territory").
- Reflection compresses thousands of events into a few salient rules (The "Map").
- This allows the agent to make faster decisions in Year 10 without re-reading Year 1's logs.

### 2.3 Noise Filtering

- In a stochastic environment, not every outcome is a signal.
- Reflection acts as a **Low-Pass Filter**, ignoring one-off anomalies while amplifying consistent trends (Semantic Consolidation).

---

### 2.4 Comparative Outcome: The "Goldfish" vs. The "Strategist"

| Metric               | Without Reflection (System 1/2 only)                                            | With Reflection (Meta-Cognitive)                                              |
| :------------------- | :------------------------------------------------------------------------------ | :---------------------------------------------------------------------------- |
| **Reaction Pattern** | **Panic-Cycle**: Panics at every flood, relaxes when sun comes out.             | **Adaptive**: Shifts strategy permanently after detecting a trend.            |
| **Memory Limit**     | Fades after $T$ steps (Exponential Decay).                                      | **Permanent**: Synthesized rules generally have `retention=1.0`.              |
| **Efficiency**       | High Cost: Re-analyzes specific events every year.                              | High Speed: Retrieves 1 rule ("Floods are likely") vs 10 events.              |
| **Blind Spot**       | **Boiling Frog**: Fails to detect slow-moving threats (e.g., repeating floods). | **Trend Spotting**: Aggregates disparate data points to find invisible risks. |

---

## 3. Practical Case: The Reflection Loop (Input -> Process -> Output)

To understand how "Data" becomes "Wisdom," consider an agent facing repeated floods over 5 years.

#### **1. Input: Scattered Episodic Memories (The Puzzle Pieces)**

The memory store contains raw, time-stamped events:

- **Year 1 (Event)**: "Flood occurred. I did nothing." (Result: House damaged, \$10k loss)
- **Year 3 (Event)**: "Flood occurred. I bought insurance." (Result: Financial relief, \$0 loss)
- **Year 4 (Observation)**: "Neighbor A elevated their house. Neighbor B moved away."

#### **2. Process: Reasoning (The Synthesis)**

The Reflection Engine (LLM) analyzes these scattered points during the year-end review:

> _"I notice a pattern: floods are happening frequently (Y1, Y3). When I did nothing (Y1), I suffered financial loss. When I bought insurance (Y3), I was protected. However, my neighbors are taking permanent measures like elevation."_

#### **3. Output: Semantic Insight (The Wisdom)**

The engine generates a new, high-importance memory that persists even if the raw events fade:

- **Insight A (Rule)**: "Passive behavior ('Do Nothing') is financially risky in this area."
- **Insight B (Strategy)**: "Insurance provides a safety net, but Elevation offers permanent protection."

---

## 4. Trigger-Based Reflection (Task-059)

Prior to v3.3, reflection was exclusively **periodic** (end-of-year consolidation). The trigger-based system adds **event-driven reflection**, allowing agents to reflect in response to significant events.

### 4.1 Trigger Types

The `ReflectionTrigger` enum defines four trigger types:

| Trigger | When It Fires | Agent Types | Example |
| :------ | :------------ | :---------- | :------ |
| **CRISIS** | After a flood or disaster event | All | Agent experienced flood damage — reflects on preparedness |
| **PERIODIC** | Every N years (configurable) | All | End-of-year consolidation (default interval: 5) |
| **DECISION** | After major life decisions | Household | Agent chose `elevate_house` or `relocate` — reflects on the choice |
| **INSTITUTIONAL** | When policy change magnitude exceeds threshold | Government, Insurance | Government changed subsidy rate by > 5% — reflects on policy effectiveness |

### 4.2 Configuration

```yaml
reflection_triggers:
  crisis: true                    # Enable crisis-triggered reflection
  periodic_interval: 5            # Reflect every 5 years
  decision_types:                 # Which decisions trigger reflection
    - "elevate_house"
    - "buyout_program"
    - "relocate"
  institutional_threshold: 0.05   # 5% policy change triggers reflection
  method: "hybrid"                # hybrid | llm_only | rule_based
  batch_size: 10                  # Process N agents per reflection batch
  importance_boost: 0.85          # Importance score for generated insights
```

### 4.3 Theoretical Motivation

This design maps to **Reflection-in-Action** (Schön 1983): agents reflect _during_ significant events, not just _after_ them. Crisis triggers implement the psychological observation that traumatic events force immediate cognitive re-evaluation — the agent cannot simply continue on autopilot.

The INSTITUTIONAL trigger supports **Double-Loop Learning** (Argyris & Schön 1978) at the organizational level: government and insurance agents question whether their _policies_ (not just their actions) are effective.

---

## 5. WRR Experiment Configuration

In the validated WRR experiments, reflection uses a simplified interval-based trigger (every year) with domain-specific guidance questions defined in `agent_types.yaml`:

```yaml
global_config:
  reflection:
    interval: 1                       # Reflect every year
    batch_size: 10                    # Agents per reflection batch
    importance_boost: 0.9             # Insights are high-importance
    method: hybrid
    questions:                        # Domain-specific guidance
      - "Was your strategy effective given the conditions?"
      - "What patterns do you notice between your actions and outcomes?"
      - "How should you adjust your approach going forward?"
```

### Action-Outcome Feedback

Each year, agents receive combined memories connecting their decisions to consequences:

> "Year 5: You chose to decrease_demand by 15%. Outcome: Supply was adequate, utilisation dropped to 65%."

This feedback is injected via the `pre_year` lifecycle hook and enables causal learning through the reflection loop. The combination of guidance questions + action-outcome feedback allows agents to correlate specific action magnitudes with supply outcomes across years.

### Configurable Guidance Questions

Reflection questions are no longer hardcoded — they are defined per-domain in `agent_types.yaml` under `global_config.reflection.questions`. The flood domain uses PMT-aligned questions about risk, neighbor influence, and cost-safety trade-offs. The irrigation domain uses questions about demand strategy effectiveness and magnitude calibration.

### References

[1] **Schön, D. A. (1983)**. _The Reflective Practitioner_. (Basis for "Reflection-on-Action" vs "Reflection-in-Action").
[2] **Dewey, J. (1933)**. _How We Think_. (Defining Reflection as the active, persistent, and careful consideration of beliefs).
[3] **Argyris, C. (1976)**. _Single-Loop and Double-Loop Models in Research on Decision Making_. (Theoretical basis for updating mental models vs just actions).
[4] **Bandura, A. (1977)**. _Social Learning Theory_. (Basis for learning from neighbors/observations).
[5] **Park et al. (2023)**. _Generative Agents_. (Technical implementation of the Reflection Tree structure).
[6] **Kahneman (2011)**. _Thinking, Fast and Slow_. (Dual-Process Theory).
