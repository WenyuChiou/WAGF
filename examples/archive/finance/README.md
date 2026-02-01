# Finance Simulation: Multi-Agent Social Dynamics (Heterogeneous)

This experiment demonstrates a complex, multi-agent financial market simulation where heterogeneous agent types interact through social signals and are governed by psychological and institutional rules.

## 1. Multi-Agent Architecture

Unlike single-agent experiments, this simulation utilizes a pool of **10 heterogeneous agents**:

- **7 Retail Traders**: Focus on personal savings, highly sensitive to social gossip and market sentiment.
- **3 Institutional Investors**: High capital scale (10x-20x), utilizing bulk trading skills and governed by institutional mandates.

## 2. Social Interaction & Gossip (InteractionHub)

Agents are connected via a **Social Graph** (Random Graph with $p=0.3$).

- **InteractionHub**: Facilitates the exchange of "Gossip".
- **Gossip Mechanism**: Agents "listen" to their neighbors' memories. For example, if a neighbor recently sold during a crash, their memory of "bearish" sentiment is passed as gossip to the agent.
- **Multi-Scale Context**: The `TieredContextBuilder` aggregates macro market data (Environment) and neighbor gossip (Social) into the agent's prompt.

## 3. State Update & Feedback Loop

Social signals are not just transient; they update the agent's **internal state**:

- **Perceived Sentiment**: A calculated state variable on each agent.
- **Update Logic**: Updated every step via a `pre_step` lifecycle hook.
  - Formula: `perceived_sentiment = (Macro Sentiment * 0.6) + (Peer Gossip Average * 0.4)`.
- **Impact**: This updated state is injected into the prompt, directly influencing the agent's strategy and numeric decision.

## 4. Importance-Based Memory

The simulation utilizes the **ImportanceMemoryEngine**:

- **Filtering**: Only significant events (e.g., high profit or major loss) are stored with high weights.
- **Retrieval**: Agents recall these impactful memories during their decision-making process, creating a persistence of traumatic or successful market experiences.

## 5. Governance & Skill Registry

- **Role-Limited Skills**:
  - Retail: `buy`, `sell`, `hold`.
  - Institutional: `buy_bulk`, `sell_bulk`, `rebalance`.
- **Psychological Rules**:
  - `panic_selling`: Blocks buying if `perceived_sentiment` and macro uncertainty indicate extreme distress.
  - `institutional_discipline`: Blocks bulk trading for institutions during high-volatility periods.

## 6. How to Run

```bash
python examples/finance/run_finance_sim.py
```

Results, including separate audit logs for retail and institutional traders, are saved to `examples/finance/results_hetero`.
