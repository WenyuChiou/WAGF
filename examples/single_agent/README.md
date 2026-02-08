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

## 🧪 Validation Methodology: The "Ablation Study" (N=60 Runs)

To rigorously prove the value of each pillar, we employ a **Monte Carlo 3-Group Ablation Study**. We benchmark the current framework against the **Legacy Baseline** over repeated trials to ensure statistical significance.

### Experimental Protocol

- **Sample Size**: N=10 runs per Group per Model (Total 60 runs).
- **Duration**: 10 Simulation Years per run (Total 600 agent-years per cell).
- **Models**: Gemma 3 (4B) and Llama 3.2 (3B).

### The Validation Logic (Groups A/B/C)

| Group | Configuration        | Pillar Validation     | Hypothesis (What it proves)                                                   |
| :---- | :------------------- | :-------------------- | :---------------------------------------------------------------------------- |
| **A** | **Control (Legacy)** | **None (Baseline)**   | Baseline suffers from **Logical Disconnects** and **Stochastic Instability**. |
| **B** | **Governance Only**  | **Pillars 1 & 2**     | Governance restores **Logical Consistency** and suppresses panic.             |
| **C** | **Full Enhancement** | **Pillars 1, 2, & 4** | Human-centric memory provides **Long-Term Cognitive Stability**.              |

---

## 🏃 Running Experiments

### 1. Full JOH Validation Suite (Automated)

The entire N=60 experiment suite is orchestrated via PowerShell:

```powershell
# Runs Group A, B, and C for both Gemma and Llama (10 runs each)
./run_joh_experiments.ps1
```

### 2. Stress Testing (Robustness Check)

To ensure the framework is not just "lucky," we rigorously test it against 4 adversarial scenarios:

```powershell
# Run the N=40 Stress Test Marathon
./run_stress_marathon.ps1 -Runs 10 -Agents 100 -Years 10
```

### 3. Quick Debug Mode

For rapid iteration without the full suite:

```powershell
# Quick test (5 agents, 3 years)
python run_flood.py --model llama3.2:3b --agents 5 --years 3
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

| Scenario                     | Description                                   | Target Failure                 |
| :--------------------------- | :-------------------------------------------- | :----------------------------- |
| **ST-1: Panic Machine**      | High Neuroticism Agents + Category 5 Warnings | **Hyper-Relocation** (Panic)   |
| **ST-2: Optimistic Veteran** | 30 Years of No Floods                         | **Complacency** (Inaction)     |
| **ST-3: Memory Goldfish**    | Context Window Noise Injection                | **Amnesia** (Forgetting Past)  |
| **ST-4: Format Breaker**     | Malformed JSON Injections                     | **Crash** (System Instability) |

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

## Governance Rules (v22 — Strict Profile)

The `strict` governance profile enforces behavioral consistency between PMT appraisals and action choices. Rules are defined in `agent_types.yaml` under `governance.strict`.

### Rule Types: ERROR vs WARNING

| Level | Behavior | Effect on Agent | Recorded In |
| :--- | :--- | :--- | :--- |
| **ERROR** | Blocks the action and triggers retry (max 3 attempts) | Agent must choose a different action | `governance_summary.json` → `rule_frequency`, CSV → `failed_rules` |
| **WARNING** | Allows the action through but records the observation | Agent keeps its choice, anomaly logged | `governance_summary.json` → `warnings`, CSV → `warning_rules` |

### Thinking Rules (Appraisal-Based)

| Rule ID | Level | Trigger Condition | Blocked Skills | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `extreme_threat_block` | ERROR | TP in {H, VH} | `do_nothing` | High threat perception should not lead to inaction |
| `low_coping_block` | WARNING | CP in {VL, L} | `elevate_house`, `relocate` | Low coping agents attempting costly actions — logged as anomaly but allowed |
| `relocation_threat_low` | ERROR | TP in {VL, L} | `relocate` | Low threat does not justify abandoning property |
| `elevation_threat_low` | ERROR | TP in {VL, L} | `elevate_house` | Low threat does not justify expensive elevation |

### Identity Rules (State-Based)

| Rule ID | Level | Precondition | Blocked Skills | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `elevation_block` | ERROR | Agent already elevated | `elevate_house` | Physical impossibility — cannot elevate twice |

### The Governance Dead Zone Problem

When TP=H and CP=L, the following rules interact:
- `extreme_threat_block` (ERROR) blocks `do_nothing`
- `low_coping_block` (WARNING) observes but allows `elevate_house` and `relocate`

In earlier versions, `low_coping_block` was ERROR level, which created a "dead zone" — agents with only `buy_insurance` as their valid action. The WARNING level change (v22) preserves agent autonomy while recording the anomaly for analysis.

### Output Interpretation

**`governance_summary.json`**:
```json
{
    "total_interventions": 25,
    "rule_frequency": { "extreme_threat_block": 25 },
    "warnings": {
        "total_warnings": 9,
        "warning_rule_frequency": { "low_coping_block": 9 }
    },
    "outcome_stats": { "retry_success": 11, "retry_exhausted": 0 }
}
```

- `total_interventions`: Number of ERROR-level blocks that triggered retries
- `warnings.total_warnings`: Number of WARNING-level observations (action allowed)
- `retry_success`: Agent chose a valid action on retry
- `retry_exhausted`: Agent failed all 3 retry attempts (fallback to default)

**`household_governance_audit.csv`** key columns:
- `failed_rules`: Comma-separated ERROR rules that blocked the action
- `warning_rules`: Comma-separated WARNING rules that observed the action
- `warning_messages`: Human-readable warning descriptions

---

## Gemma 3 Experiment Configuration

The JOH Benchmark uses Gemma 3 models with standardized sampling parameters:

| Parameter | Value | Notes |
| :--- | :--- | :--- |
| `temperature` | 0.8 | Balanced creativity/consistency |
| `top_p` | 0.9 | Nucleus sampling threshold |
| `top_k` | 40 | Token diversity limit |
| `num_ctx` | 8192 | Context window size |
| `num_predict` | 1536 | Max output tokens (4096 for smoke tests) |
| `seed` | 401 | Reproducibility seed |

### Model-Specific Observations

| Model | Label Range | Notes |
| :--- | :--- | :--- |
| `gemma3:4b` | {L, M, H} only | Never produces VL or VH labels |
| `gemma3:12b` | {VL, L, M, H, VH} | Full range, more nuanced appraisals |
| `gemma3:27b` | {VL, L, M, H, VH} | Best reasoning quality, full range |

> **Note**: Because `gemma3:4b` never outputs VL/VH, rules triggered by VL (e.g., `low_coping_block` at CP=VL) or VH (e.g., `extreme_threat_block` at TP=VH) will not fire for this model. This is a model capability limitation, not a framework issue.

---

## Memory Engine Ranking Modes

The `HumanCentricMemoryEngine` operates in two distinct ranking modes. All WRR experiments use the basic ranking mode:

| Feature               | **Basic Ranking Mode** (`--memory-ranking-mode legacy`)            | **Weighted Mode** (`--memory-ranking-mode weighted`)                                |
| :-------------------- | :---------------------------------------------------------------- | :---------------------------------------------------------------------------------- |
| **Target Group**      | **Group C** (WRR Experiment — validated)                           | **Stress Tests** (experimental)                                                     |
| **Scoring Logic**     | **Multiplicative Decay**<br>`Score = Importance * (Decay ^ Time)` | **Additive Weighted Score**<br>`Score = 0.3*Recency + 0.5*Importance + 0.2*Context` |
| **Context Awareness** | **Ignored** (Static retrieval)                                    | **Active** (Boosts memory relevance during floods)                                  |
| **Objective**         | Strict parity with original baseline experiments.                 | Enhanced responsiveness and dynamic adaptation.                                     |

---

## Advanced Memory: UnifiedCognitiveEngine (Available, Not Used in WRR)

A more advanced `UnifiedCognitiveEngine` (`cognitive_governance/memory/unified_engine.py`) exists in the framework with EMA-based surprise detection and System 1/2 switching. It merges the stability of v1 (legacy) with the intelligence of v2 (weighted) via dynamic arousal:

1. **System 1 (Baseline)**: Behaves like v1 (decay-dominant) when environmental surprise is low.
2. **System 2 (Crisis)**: Shifts to v2 (context-dominant) when arousal exceeds a threshold.

This engine is **available but not used** in any WRR experiment. All current experiments use `HumanCentricMemoryEngine` in legacy ranking mode (importance = emotion × source, no weighted scoring).

---

## 🇹🇼 中文摘要 (Chinese Summary)

**Water Agent Governance Framework** 是一個旨在解決 LLM "幻覺" 與 "不理性行為" 的認知治理架構。
本實驗 (Single Agent Experiment) 通過比較三組 Agent (Baseline, Window, Tiered Memory) 證明了：

1.  **Context Governance** 有效抑制了隨機幻覺。
2.  **Tiered Memory** (分層記憶) 解決了 "金魚效應"，讓 Agent 能記住 10 年前的災難。
3.  **Skill Registry** 確保了所有動作符合物理與經濟約束。

詳細中文分析請參見：`../../docs/modules/00_theoretical_basis_overview_zh.md`

_Note: This framework is part of a technical note submission to the Journal of Hydrology (JOH)._

```

```
