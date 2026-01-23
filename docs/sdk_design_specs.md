# GovernedAI SDK: Design Specification (vNext)

**Goal**: Transform the research codebase into a universal "Safety Layer" (Middleware) for any LLM Agent (LangChain, CrewAI, AutoGen).

## 1. Core Philosophy: "The Governance Wrapper"

The SDK does not build agents. It **wraps** them.

```python
# User Code (Before)
agent = LangChainAgent(model="gpt-4", tools=[trade_stock])
agent.run("Buy $10k AAPL")

# User Code (After - with GovernedAI)
from governed_ai import GovernanceWrapper

# 1. Define Policy
policy = """
block_if:
  - action: "trade_stock"
    condition: "amount > 5000 and market_volatility > 0.8"
    message: "High risk trade blocked. Check volatility first."
"""

# 2. Wrap Agent
governed_agent = GovernanceWrapper(agent, policy=policy)

# 3. Run (Safe)
governed_agent.run("Buy $10k AAPL")
# -> Output: "Action Blocked: High risk trade blocked..."
```

## 2. Architecture: The Dual-Layer Interceptor Pattern

To solve the **Hallucination** and **Cognitive Asymmetry** problems in ABM settings, the SDK implements a dual-stage interception pipeline. This ensures "Behavioral Calibration" by correcting logical drift and environment violations in real-time.

```python
agent = GovernedAgent(
    backend=MyBaseAgent,  # Support for LangChain/AutoGen/Custom
    policy=my_abm_policy,
    interceptors=[
        # Layer 1: Cognitive Interceptor (Anti-Hallucination)
        # Targets the "Reasoning/Thought" phase.
        CognitiveInterceptor(mode="LogicalConsistency"),

        # Layer 2: Action Interceptor (Anti-Asymmetry)
        # Targets the "Tool/Action" phase.
        ActionInterceptor(mode="EnvironmentConstraints")
    ]
)
```

### 2.1 Layer 1: Cognitive Interceptor (The "Sanity Check")

- **Target**: Internal "Thought/Plan" tokens.
- **Problem Solved**: **Hallucination**. Validates that the agent's reasoning premises (e.g., current account balance, flood history) match the ground truth in the simulation environment.
- **Mechanism**: If a hallucinated premise is detected, it triggers a **Pedagogical Retry** (e.g., "Note: You only have $500, not $5000. Please revise your plan.").

### 2.2 Layer 2: Action Interceptor (The "Reality Check")

- **Target**: Output JSON / Tool Call.
- **Problem Solved**: **Cognitive Asymmetry**. Ensures that probabilistically generated actions adhere to the deterministic physics and rules of the ABM environment.
- **Mechanism**: Validates parameters (e.g., `amount <= balance`). If invalid, converts the environment error into **Structured Feedback** for the agent to adapt.

### 2.3 Policy Engine: From "Blocking" to "Calibration"

Instead of a binary "Permit/Block," the SDK allows researchers to define **Quantitative Constraints**. This ensures that the agent's behavior is "calibrated" for realistic outcome assessment without losing the "Rational Adaptation" signal.

### 2.3 The Vector Memory (Neuro-Symbolic)

- Standardized `VectorMemory` interface.
- Supports `add(text, metadata)` and `retrieve(query, filter)`.
- Backends: `ChromaDB` (Local default), `Pinecone` (Cloud).

### 2.4 Behavioral Rule Generalization (The Research Core)

The SDK will formalize the **Identity** and **Thinking** rules (based on behavioral psychology) currently found in our research code into a reusable "Rule Library."

- **Identiy Patterns (Status-Based)**: Formalizing "Right-to-Act" based on agent status (e.g., "Anxious" agents blocked from "Optimistic Planning").
- **Thinking Patterns (Cognitive-Based)**: Formalizing "Reasoning Integrity" based on cognitive labels (e.g., "High Threat Appraisal" must lead to "Protective Action").

Developers will be able to import these patterns:

```python
from governed_ai.library import PsychologyTemplates as pmt

# Create a policy using optimized research-backed rules
policy = pmt.get_flood_recovery_policy(strictness="High")
```

---

### 2.5 The Explanation Engine (XAI Layer)

To ensure governance is transparent and non-arbitrary, the SDK provides **Narrative Justifications** for every intervention.

- **GovernanceTrace**: Instead of a "Blocked" signal, the SDK outputs a structured trace:
  - _Rule Hit_: `Financial-Prudence-V1`
  - _Metric_: `Current_Savings ($200) < Required_Premium ($500)`
  - _Rationale_: "Agent attempted to purchase high-premium insurance despite critical liquidity shortage. This behavior is inconsistent with Risk-Averse household profiles."
  - _Corrective Path_: "Recommend applying for government flood-relief grant (Skill: `apply_grant`)."

### 2.6 Calibration & Validation Suite

A critical requirement for ABM is ensuring the governance layer does not introduce **Researcher Bias** or suppress **Emergent Human Diversity**.

- **Calibration Sweeps**: An automated tool to find the "Goldilocks Zone" of rule strictness. It sweeps through `Rationality_Thresholds` and plots the **Safety vs. Agency Curve**.
- **Behavioral Fidelity Benchmarking**: Built-in support for loading human survey data (e.g., Household Flood Surveys). The SDK calculates the **KL-Divergence** between the governed agent distribution and the human empirical distribution to validate simulation realism.

---

## 3. Directory Structure (Proposed)

```
governed_ai_sdk/
├── core/
│   ├── wrapper.py          # The main wrapper class
│   ├── interceptor.py      # Hooks for LangChain/CrewAI
│   └── policy_engine.py    # Rule evaluation logic
├── memory/
│   ├── vector_store.py     # Chroma/FAISS wrapper
│   └── symbolic_filter.py  # Signature logic (v4 Concept)
├── policies/
│   ├── basic_financial.yaml
│   └── ethical_guidelines.yaml
└── dashboard/
    └── app.py              # Streamlit Observer
```

## 4. Roadmap

1.  **Prototype**: Build `wrapper.py` and `policy_engine.py` (Simple YAML support).
2.  **Integration**: Create an adapter for a simple LangChain agent.
3.  **Memory**: Port the v4 "Neuro-Symbolic" logic into `memory/`.
