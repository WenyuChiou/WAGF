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

## 🧠 Memory Engine Modes: v1 vs v2

To ensure both historical comparability and future robustness, the `HumanCentricMemoryEngine` operates in two distinct modes:

| Feature               | **v1 (Legacy)**                                                   | **v2 (Weighted)**                                                                   |
| :-------------------- | :---------------------------------------------------------------- | :---------------------------------------------------------------------------------- |
| **Target Group**      | **Group C** (ABC Experiment)                                      | **Stress Tests**                                                                    |
| **Scoring Logic**     | **Multiplicative Decay**<br>`Score = Importance * (Decay ^ Time)` | **Additive Weighted Score**<br>`Score = 0.3*Recency + 0.5*Importance + 0.2*Context` |
| **Context Awareness** | **Ignored** (Static retrieval)                                    | **Active** (Boosts memory relevance during floods)                                  |
| **Objective**         | Strict parity with original baseline experiments.                 | Enhanced responsiveness and dynamic adaptation.                                     |

---

## 🚀 Roadmap: v3 Integrated Model (Proposed)

We are actively designing a **v3 Hybrid Model** to merge the stability of v1 with the intelligence of v2.

**Core Concept:**
Instead of a hard toggle, v3 will use a **Dynamic Weighting Mechanism**:

1.  **Baseline State**: Behaves like v1 (Decay-dominant) when environmental stress is low.
2.  **Crisis State**: Shifts to v2 (Context-dominant) when `threat_appraisal` exceeds a threshold.

**Proposed Architecture:**

```python
# v3 Concept
dynamic_context_weight = sigmoid(current_threat_level) * max_context_weight
final_score = (1 - dynamic_context_weight) * decay_score + (dynamic_context_weight) * context_score
```

This ensures agents are "calm" during peace but "alert" during disaster, mimicking human cognitive arousal.

---

## 🇹🇼 中文摘要 (Chinese Summary)

**Governed Broker Framework** 是一個旨在解決 LLM "幻覺" 與 "不理性行為" 的認知治理架構。
本實驗 (Single Agent Experiment) 通過比較三組 Agent (Baseline, Window, Tiered Memory) 證明了：

1.  **Context Governance** 有效抑制了隨機幻覺。
2.  **Tiered Memory** (分層記憶) 解決了 "金魚效應"，讓 Agent 能記住 10 年前的災難。
3.  **Skill Registry** 確保了所有動作符合物理與經濟約束。

詳細中文分析請參見：`../../docs/modules/00_theoretical_basis_overview_zh.md`

_Note: This framework is part of a technical note submission to the Journal of Hydrology (JOH)._

```

```
