---
title: Reflection Engine (System 2)
description: Defines the periodic cognitive consolidation module for long-term memory resilience (The "Pillar 2" of the framework).
---

# Reflection Engine (System 2 Thinking)

The **Reflection Engine** is the module responsible for **Pillar 2** of the framework: **Periodic Reflection & Synthesis**. It combats the "Goldfish Effect" (memory fragmentation) by synthesizing fragmented episodic memories into cohesive, high-level **Semantic Rules**.

Inspired by human sleep consolidation and _Generative Agents_ (Park et al., 2023), this engine allows agents to form long-term strategies that persist beyond the immediate context window.

---

## 1. Core Responsibilities

1.  **Triggering Reflection**: Determines when an agent should stop and "think" (e.g., end of simulation year/epoch).
2.  **Prompt Generation**: Dynamically constructs prompts that feed recent memories into the LLM, asking for summarization and pattern recognition.
3.  **Insight Parsing**: Converts LLM text outputs into structured `ReflectionInsight` objects.
4.  **Integration**: Injects these insights back into the **Memory Engine** with artificially boosted importance scores, ensuring they survive decay.
5.  **Audit Logging**: Records all reflections to `reflection_log.jsonl` for **Cognitive Heatmap** visualization (Explainable AI).

---

## 2. Architecture & Data Flow

```mermaid
graph TD
    A[Year-End Trigger] -->|Activate| B[Reflection Engine]
    B -->|Fetch Recent Memoirs| C[Memory Engine]
    C -->|Top-k Episodes| B
    B -->|Synthesis Prompt| D[LLM (System 2)]
    D -->|High-Level Insight| E[Insight Parser]
    E -->|Structured Rule| F[Memory Engine (Long-Term)]
    E -->|JSON Report| G[reflection_log.jsonl]

    style B fill:#f9f,stroke:#333
    style D fill:#bbf,stroke:#333
```

---

## 3. Configuration

The engine is initialized within the `Broker` and configured via the main simulation config (or defaults):

```python
reflection_engine = ReflectionEngine(
    reflection_interval=1,         # Reflect every year
    max_insights_per_reflection=2, # Extract top 2 lessons
    insight_importance_boost=0.9,  # Boost score (0.0-1.0) to prevent decay
    output_path="results/reflection_log.jsonl" # Audit trail
)
```

| Parameter             | Type    | Description                                                                                                   | Default |
| :-------------------- | :------ | :------------------------------------------------------------------------------------------------------------ | :------ |
| `reflection_interval` | `int`   | How often (in epochs/years) to reflect.                                                                       | `1`     |
| `max_insights`        | `int`   | Max number of distinct insights to generate per cycle.                                                        | `2`     |
| `importance_boost`    | `float` | The hardcoded importance score for new insights. High values (e.g., 0.9) ensure insights persist for decades. | `0.9`   |
| `output_path`         | `str`   | File path for XAI logging.                                                                                    | `None`  |

---

## 4. Prompting Strategy

The default reflection prompt is **domain-agnostic**, relying on the content of the memories to provide context.

**Template:**

```text
You are reflecting on your experiences from the past {interval} year(s).

**Your Recent Memories:**
{bullet_list_of_memories}

**Task:** Summarize the key lessons you have learned from these experiences.
Focus on:
1. What patterns or trends have you noticed?
2. What actions proved beneficial or harmful?
3. How will this influence your future decisions?

Provide a concise summary (2-3 sentences) that captures the most important insight.
```

---

## 5. Integration with Memory Engine

Reflections are not stored in a separate database; they are stored **back into the same vector/list store** as regular memories, but with a special distinction:

1.  **High Importance**: They enter with a score of `0.9` (vs. ~0.3 for routine events).
2.  **Semantic Nature**: They represent _rules_ ("I should buy insurance") rather than _episodes_ ("I saw a flood yesterday").
3.  **Retrieval Priority**: When `retrieve()` is called, these high-score items naturally bubble to the top via the HeapQ optimization.

---

## 6. Audit & Visualization (XAI)

The engine writes to `reflection_log.jsonl`. Each entry contains:

```json
{
  "summary": "I realized that relying solely on savings is risky; insurance provides a necessary safety net.",
  "source_memory_count": 5,
  "importance": 0.9,
  "year_created": 3,
  "domain_tags": [],
  "agent_id": "Agent_042",
  "timestamp": "2025-01-18T12:00:00"
}
```

This log is used to generate the **Cognitive Heatmap**, visualizing how agent thinking evolves from "Reactive" (year 1) to "Proactive" (year 5).
