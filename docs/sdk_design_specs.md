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

## 2. Architecture Components

### 2.1 The Interceptor (Middleware)

- **Role**: Hooks into the Agent's `step()` or `run()` method.
- **Input**: `(User Prompt, Agent Thought, Proposed Action)`
- **Process**:
  1.  **Audit**: Log the intent.
  2.  **Police**: Check against Policy Engine.
  3.  **Tutor**: If blocked, generate "Correction Prompt".
- **Output**: Either `ApprovedAction` or `FeedbackString`.

### 2.2 The Policy Engine (Rule-Based & LLM-Based)

- **Static Rules**: Simple arithmetic checks (e.g., `budget < 100`).
- **Constitutional Rules**: LLM-evaluated norms (e.g., "Actions must be ethical").
  - _Implementation_: `LLM(Question: "Is {Action} ethical?", Context: Constitution)`

### 2.3 The Vector Memory (Neuro-Symbolic)

- Standardized `VectorMemory` interface.
- Supports `add(text, metadata)` and `retrieve(query, filter)`.
- Backends: `ChromaDB` (Local default), `Pinecone` (Cloud).

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
