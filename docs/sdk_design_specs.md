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

- **GovernanceTrace**: Instead of a simple "Blocked" signal, the SDK outputs a structured trace:
  - _Rule Hit_: `Financial-Prudence-V1`
  - _Metric_: `Current_Savings ($200) < Required_Premium ($500)`
  - _Rationale_: "Agent attempted to purchase insurance despite liquidity shortage."
- **Counter-Factual Explanations**: The engine identifies the "Minimal State Change" required for success.
  - _Logic_: "If `Savings` were > $500 (currently $200), this action would be valid. Theoretical Link: Bounded Rationality."
  - _Value_: Provides researchers with the 'Causal Logic' behind every intervention.

### 2.6 Calibration & Validation Suite

A critical requirement for ABM is ensuring the governance layer does not introduce **Researcher Bias**.

- **Entropy Friction Analysis**: The SDK calculates the ratio between raw agent entropy ($S_{raw}$) and governed entropy ($S_{gov}$).
  - _Insight_: A ratio $> 2.0$ indicates "Over-Governance," where the framework is suppressing too much emergent behavioral diversity.
- **KL-Divergence Validation**: Quantitative comparison between Governed Agent distributions and Empirical Human distributions (CSV import).
- **Functional Adapters**: Middleware that allows the SDK to read state from _any_ existing ABM environment (Mesa, NetLogo, etc.) using simple functional mappings:
  ```python
  GovernedAgent(agent, state_mapping={"wealth": lambda x: x.money})
  ```

### 2.7 The Governance Auditor (Scientific Rigor)

To ensure simulations are reproducible and trustable, the Auditor layer provides immutable traces of every decision lifecycle.

- **Scientific Replay**: Every step is logged as a "Replay Object" containing (Context + Prompt + Raw LLM Output + Governance Rationale). Researchers can reload any single step into a debugger to verify logic.
- **Integrity Hashing**: Traces are cryptographically hashed to prevent post-hoc data tampering in sensitive policy simulations.

### 2.8 The Execution Layer (Approval Gateway)

The SDK follows a **"Look, Don't Touch"** policy to remain framework-agnostic.

- **Decoupled Permissions**: Instead of executing code, the SDK returns a `ValidatedSkill` object.
- **Approval Semantics**: The external simulation engine receives this object and is responsible for the actual state mutation. This prevents the SDK from needing complex "Write Access" to the user's database or world model.

### 2.9 The External Environment Adapter

To avoid hardcoding, the SDK uses a **Schema Mapping** approach to read world state.

- **Universal Adapters**: Support for any environment (Mesa, NetLogo-Python, Custom).
- **Mapping Interface**: Users define how to extract metrics (e.g., `savings`) from their specific environment objects via a simple dictionary mapping.

### 2.10 Governed Memory (Temporal Consistency)

Governance is applied not just to the _Action_, but to the **Write Path** of the agent's memory.

- **Anti-Temporal Hallucination**: Prevents agents from "remembering" events that never occurred in the environment.
- **Selective Retention**: Policies can define which events are "significant" enough to be committed to Long-Term Memory (LTM), reducing cognitive noise in long-horizon simulations.

---

### 2.11 Heterogeneous Context (Subjective Reality)

To support complex ABMs where agents have limited or different information (e.g., Resident vs. Government), the SDK separates **Omniscient State** from **Subjective Context**.

- **Context Mappers**: Developers define filters that restrict what an agent "sees."
  - _Resident_: `Context = {local_flood_depth, family_health}`
  - _Government_: `Context = {district_flood_risk, budget_deficit}`
- **Fair Validation**: The Cognitive Interceptor validates the agent's reasoning against its _Subjective Context_, not the Omniscient State. This ensures agents aren't penalized for acting rationally based on incomplete information (Bounded Rationality).

### 2.12 Symbolic Mechanics (The v4 Logic)

To handle the scale of millions of agents, the SDK adopts the **v4 Neuro-Symbolic Engine**.

- **Symbolic Signatures**: Instead of heavy vector embeddings for every memory, the SDK converts context into lightweight "Hashes" (e.g., `FLOOD:HIGH|PANIC:LOW`).
- **Fast Retrieval**: $O(1)$ lookup for similar past experiences, enabling massive-scale memory systems without GPU overhead.

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
