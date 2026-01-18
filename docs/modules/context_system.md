# Context & Output System

**🌐 Language: [English](context_system.md) | [中文](context_system_zh.md)**

This document explains how the `FinalContextBuilder` constructs the agent's cognitive world and enforces strict output formats (such as JSON scoring).

---

## 1. Context Construction

The `ContextBuilder` transforms raw data into a narrative structure understandable by the LLM, divided into four layers:

1.  **Global Truth**:
    - Defines the Agent's identity and basic rules (e.g., "You are a homeowner living in a flood-prone area").
    - _Source_: `agent_initial_profiles.csv` and `narrative_persona` in `run_flood.py`.

2.  **Retrieved Memory**:
    - Retrieves the 3-5 most relevant segments from 10 years of history.
    - _Mechanism_: Uses `HumanCentricMemoryEngine` to calculate the $S_{retrieval}$ score.

3.  **Immediate Perception**:
    - Specific values for the current year (water level, neighbor actions, policy changes).
    - _Source_: `EnvironmentProvider` and `InteractionHub`.

### 📜 Context Prompt Example

The following is an actual context template for a `household` Agent, including **Shared Rules** and Policy definitions:

```text
[Role & Identity]
You are a homeowner in a coastal area (Flood Zone A).
Property Value: $200,000. Current Savings: $15,000.

[Policy & Shared Rules]
1. FLOOD_INSURANCE_ACT: Subsidy available if community participation > 50%.
2. ZONING_LAW_101: Elevation grants provided for houses < 0m elevation.
3. BUDGET_CONSTRAINT: You cannot spend more than your simulation savings.

[Prioritized Memory]
- Year 3: Flood depth 1.2m. "My basement was destroyed." (Importance: 0.9)
- Year 4: Neighbor Bob elevated his house. (Importance: 0.6)

[Current Situation - Year 5]
Flood Forecast: High Probability.
Neighbor Action: 3 neighbors bought insurance yesterday.
```

4.  **Output Directives**:
    - **Most Critical Part**: Forces the LLM to output a specific format.

---

## 2. Output Enforcement & Scoring

### Strict Formatting Rule

To ensure agent decisions can be parsed programmatically, the `SystemPromptProvider` injects the following directive:

```text
### [STRICT FORMATTING RULE]
You MUST wrap your final decision JSON in <decision> and </decision> tags.
Example: <decision>{{"strategy": "elevate_house", "confidence": 0.8, "decision": 1}}</decision>
DO NOT include any commentary outside these tags.
```

### JSON Constructs Definition

Users can define required JSON fields (Constructs) in the Prompt Template. For example, in `household_template`:

- **Decision**: Specific action code (0=Wait, 1=Insure, etc.)
- **Confidence**: Decision confidence score (0.0 - 1.0)
- **Reasoning**: Brief reason for the decision

### Parsing Decision

The `UnifiedAdapter` (in `broker/utils/model_adapter.py`) parses the output:

1.  **Extraction**: Uses regex to find content within `<decision>...</decision>` tags.
2.  **Repair**: If JSON is malformed (e.g., missing quotes), `SmartRepairPreprocessor` attempts auto-repair.
3.  **Validation**: Checks if all necessary fields (`strategy`, `confidence`) are present.

### Scoring Mechanism

If your application needs to score agent outputs (e.g., whether the reasoning is logical), this is typically done in the **Governance Layer**.

- **Validator**: Checks if output complies with definitions in `agent_types.yaml`.
- **Auditor**: Records `confidence` scores and calculates group averages (e.g., AC Metric in `all_groups_stability.csv`).

---

## 3. Customization

If you need to modify the context structure:

1.  **Modify Template**: Edit `broker/utils/prompts/household_template.txt`.
2.  **Modify Builder**: Inherit from `ContextBuilder` and override the `format_prompt` method.
