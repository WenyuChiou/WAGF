# Multi-Agent Experiment Plan & Configuration

## 1. Q&A: Experiment Configuration

### Q1: Is initialization using a module with demographic attributes?

**Yes.**

-   **Module**: `examples/multi_agent/generate_agents.py`
-   **Mechanism**: The `generate_agents()` function explicitly assigns demographic attributes based on sociological distributions:
    -   **Income**: Log-normal distribution (lower for Marginalized Groups).
    -   **Tenure**: Owner vs. Renter split.
    -   **Trust**: Beta distributions for Trust in Gov/Insurance/Neighbors.
    -   **Property**: Replacement Cost Values (RCV) derived from income/tenure.

### Q2: Is this module general-purpose?

**Yes, highly modular.**

-   The `generate_agents.py` script accepts high-level parameters (`n_agents`, `mg_ratio`, `owner_ratio`) via CLI.
-   The `ma_agent_types.yaml` file defines the _cognitive_ architecture (prompts, decision logic) separately from the demographics, allowing you to plug different agent types into the same demographic population.

### Q3: Are there fixes for the "context too long" issue?

**Yes, multiple layers of mitigation:**

1.  **Dynamic Skill Retrieval (RAG)**: The `SkillBrokerEngine` (in `broker/core/skill_broker_engine.py`) explicitly checks `should_rag`. If active, it _only_ retrieves the top-N relevant skills for the prompt, rather than dumping the entire registry.
2.  **Memory Windowing**: The default `WindowMemoryEngine` and `HumanCentricMemoryEngine` enforce a strict `retrieve(top_k=...)` limit (default 3-5 items) to keep the history section bounded.
3.  **Summarization (Hierarchy)**: The `HierarchicalMemoryEngine` contains logic to consolidate episodic memories into semantic summaries, though the benchmark default is currently `WindowMemory` for stability.

### Q4: How is the retrieval and memory system currently configured?

**Configuration:**

-   **Engine**: The system defaults to `WindowMemoryEngine` (Sliding Window, Size=5) for the benchmark to ensure fair comparison.
-   **Retrieval**: Agents have access to a `retrieve_memory` skill (defined in `skill_registry.yaml`), but primarily memory is **automatically injected** into the prompt via the `ContextBuilder`.
-   **Injection**: The prompt template `{{memory}}` slot is populated by calling `memory_engine.retrieve(agent_context)`.

### Q5: How do "Agent Type" and "Skills" influence behavior?

-   **Influence**:
    -   **Permissions**: `skill_registry.yaml` enforces rigid permissions. `household_renter` _cannot_ access `buy_insurance` (structure); they can only use `buy_contents_insurance`.
    -   **Governance**: "Thinking Rules" in `ma_agent_types.yaml` actively _block_ skills based on internal states (e.g., "Block `do_nothing` if Threat Perception is VH").
-   **Optimization**: The current setup uses "Hard Governance" (Rules). Optimization would involve moving to "Soft Governance" (Suggestions) or expanding the definition of skills to be more granular.

---

## 2. Proposed Experiment Design

### Objective

Evaluate the Multi-Agent interaction dynamics between Households, Government, and Insurance under the "Skill-Governed" architecture.

### Global Claude-Style Skills

We will utilize the **Skill Registry** (`skill_registry.yaml`) which follows the comprehensive "Tool Use" standard (name, description, explicit parameters), similar to Claude's function calling capability.

#### 1. Core Skills (Universal)

-   `retrieve_memory`: Recall past floods or social interactions.
-   `do_nothing`: Explicit choice to wait.

#### 2. Specialized Skills (Role-Based)

| Agent Type             | Key Skills                                                            |
| :--------------------- | :-------------------------------------------------------------------- |
| **Household (Owner)**  | `buy_insurance`, `elevate_house` (Requires capital), `buyout_program` |
| **Household (Renter)** | `buy_contents_insurance`, `relocate`                                  |
| **Government**         | `increase_subsidy`, `decrease_subsidy`, `set_mg_priority`             |
| **Insurance**          | `raise_premium`, `lower_premium`                                      |

### Experiment Parameters

-   **Population**: 50 Agents (40 Owners, 10 Renters) + 1 Gov + 1 Ins.
-   **Duration**: 10 Years (Steps).
-   **Environment**: "NJDPC_Floods" (New Jersey Disaster Profile).
-   **Memory**: `WindowMemory` (Size=5).

### Execution Plan

1.  **Data Generation**: Run `generate_agents.py` to create a fresh population `agents_experiment_v1.csv`.
2.  **Simulation**: Execute `examples/multi_agent/run_unified_experiment.py` using this population.
3.  **Analysis**: Use the Audit Logs to verify skill usage frequencies (e.g., "Did Renters actually use `buy_contents_insurance`?").

### Validation Steps

-   [ ] **Init**: Verify demographic spread (Income/MG).
-   [ ] **Skills**: Verify `Government` actually reacts to `elevated_count` by changing subsidies.
-   [ ] **Context**: Monitor prompt token counts to ensure they stay within `16k` limit.

---

## 3. Risk Mitigation & Versioning Strategy

### Impact on Single-Agent (SA) Benchmark

**Diagnosis:** The SA benchmark currently relies on `broker.components`.
**Strategy:** We will invoke a strict **"Add-Only"** policy for shared components.

1.  **Versioning**: All new MA-specific scripts will use the `v2_` prefix (e.g., `v2_run_unified_experiment.py`) to avoid confusing legacy scripts.
2.  **Isolation**:
    -   MA-specific configurations (Skills, Agents) are already isolated in `examples/multi_agent/`.
    -   If core changes are needed (e.g., to `MemoryEngine`), we will **Subclass** them in the local `examples/multi_agent/broker/` folder rather than modifying the global core.
3.  **General Optimizations**:
    -   The "Empty Output Fix" (Retry Logic) _was_ a general optimization applied to `broker/core` and _is_ beneficial to SA (currently running safely).
    -   Future "General" optimizations will be flagged with `[Global]` in `task.md`.

### Naming Convention

-   **Experiment Tag**: `ma_v2_skill_governed`
-   **Output Directory**: `examples/multi_agent/results_v2/`
