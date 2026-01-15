# Multi-Agent Benchmark: Social & Institutional Dynamics

This benchmark extends the framework to a **Multi-Agent System (MAS)** where 50+ household agents interact with each other and with institutional actors (Government, Insurance) over a 10-year period.

## Experiment Design

We test three distinct configurations to isolate the effects of **Social Interaction** and **Memory Systems**:

| Scenario             | Memory Engine   | Social Gossip | Description                                                                                                                             |
| :------------------- | :-------------- | :------------ | :-------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Isolated**      | Window (Size=1) | ❌ Disabled   | **Baseline Control**. Agents act independently with minimal memory context.                                                             |
| **2. Window**        | Window (Size=3) | ✅ Enabled    | **Social Standard**. Agents share reasoning ("Why I elevated") and valid social proof enters their memory stream.                       |
| **3. Human-Centric** | Human-Centric   | ✅ Enabled    | **Advanced Cognitive**. Uses Importance/Recency/Relevance scoring to retain critical memories (e.g., past floods) despite social noise. |

## Key Features

### 1. Institutional Agents

Unlike the Single-Agent simulation, this environment includes dynamic institutions:

- **NJ State Government**: Adjusts **Subsidy Rates** (Grant %) based on budget and adoption.
- **FEMA/NFIP**: Adjusts **Insurance Premiums** based on the program's Loss Ratio.
  - _Effect_: Agents must react to changing economic incentives (e.g., rising premiums might trigger relocation).

### 2. Social Network (Gossip)

- **Reasoning Propagation**: When an agent makes a decision (e.g., "Elevate House"), their _reasoning_ is broadcast to neighbors (k=4 network).
- **Social Proof**: Neighbors receive this as a memory trace: _"Neighbor X decided to Elevate because [Reason]"_. This influences their subsequent threat/coping appraisal.

### 3. Lifecycle Hooks

- **Pre-Year**: Flood event determination ($P=0.3$), pending action resolution (e.g., Elevation takes 1 year to complete).
- **Post-Step**: Institutional global state updates (Subsidy/Premium changes).
- **Post-Year**: Flood damage calculation (impacts emotional memory) and memory consolidation.

## How to Run

Use the provided PowerShell script to run the full benchmark across all models and scenarios:

```powershell
./examples/multi_agent/run_ma_benchmark.ps1
```

### Configuration

- **Agents**: 50 (Mix of Owners/Renters)
- **Years**: 10
- **Models**: Llama 3.2, Gemma 2, DeepSeek-R1 (configurable in script)

## Output Structure

Results are saved to `examples/multi_agent/results_benchmark/`:

```
results_benchmark/
├── llama3_2_3b_isolated/
├── llama3_2_3b_window/
├── llama3_2_3b_humancentric/
...
```

Each folder contains:

- `simulation_log.csv`: Decisions and actions.
- `household_governance_audit.csv`: Perception and validation logs.
- `institutional_log.csv`: Government/Insurance state changes.
