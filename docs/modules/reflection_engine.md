# Reflection Engine (Meta-Cognition)

**🌐 Language: [English](reflection_engine.md)**

The **Reflection Engine** is the meta-cognitive layer of the agent architecture. Unlike the "fast" decision-making loop (System 1/2), Reflection is a "slow", periodic process dedicated to **synthesizing wisdom** from raw experience.

---

## 1. Core Purpose: From Data to Wisdom

The engine solves the **"Scatter Problem"** of episodic memory.

- **Without Reflection**: An agent has 10 scattered memories about floods.
- **With Reflection**: An agent has 1 synthesized rule: _"Floods are frequent here, so insurance is a must."_

### The Transformation Pipeline

| Stage          | Type          | Content Example                                                             | Focus          | Logic               |
| :------------- | :------------ | :-------------------------------------------------------------------------- | :------------- | :------------------ |
| **1. Input**   | **Episodic**  | "Year 1: Flood." <br> "Year 1: Bought Insurance."                           | **Raw Events** | "What happened?"    |
| **2. Process** | **Reasoning** | "Looking back, buying insurance saved me money because the flood happened." | **Analysis**   | "Was it good?"      |
| **3. Output**  | **Semantic**  | **Insight**: "Insurance is a critical hedge against local flood risks."     | **Rule**       | "What did I learn?" |

---

## 2. Decision vs. Reflection

A common confusion is between _Decision-Making_ and _Reflection_, as both use LLMs. They are fundamentally different functions:

| Feature       | Decision-Making (The Exam)                    | Reflection (The Review)                          |
| :------------ | :-------------------------------------------- | :----------------------------------------------- |
| **Question**  | "Given context X, what should I do **NOW**?"  | "Looking at the past, was my decision **GOOD**?" |
| **Direction** | **Forward-Looking** (Proactive)               | **Backward-Looking** (Retrospective)             |
| **Goal**      | **Apply** existing wisdom to solve a problem. | **Create** new wisdom for the future.            |
| **Output**    | An **Action** (Buy, Elevate).                 | An **Insight** (Memory Object).                  |

---

## 3. The "Boiling Frog" Solution

Reflection is critical for countering the **Boiling Frog Effect** (System 1 Habituation).

- **System 1 (Habit)** might say: "Flood again? Just ignore it like last year." (Numbness).
- **Reflection** might say: "Wait, I've ignored it 3 times and lost $30k total. This strategy is failing."
- **Result**: The _Insight_ ("Strategy Failing") has high **Importance**, forcing the agent to wake up next year even if the flood event itself isn't surprising.

---

## 4. Technical Implementation

### A. The S-R Loop (Stimulus-Response)

We explicitly feed **Context-Action Pairs** to the LLM to enable Reinforcement Learning behavior.

1.  **Stimulus (Context)**: `"Year 5: Flood occurred."`
2.  **Response (Action)**: `"Year 5: Decided to: Do Nothing."`
3.  **Outcome**: `"Year 5: Suffered financial loss."`

The Reflection Prompt asks: _"What actions proved beneficial or harmful?"_
The LLM sees the sequence **[Do Nothing -> Loss]** and generates the insight: _"Doing nothing during floods leads to loss."_

### B. Configuration (`agent_types.yaml`)

```yaml
reflection:
  interval: 1 # Reflect every N years
  batch_size: 10 # Efficiency optimization
  importance_boost: 0.9 # New insights are "Sticky" (hard to forget)
```
