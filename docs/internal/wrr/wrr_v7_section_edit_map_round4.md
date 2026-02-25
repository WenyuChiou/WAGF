# WRR v7 Section Edit Map (No "middleware")

Purpose: direct replacement map for `paper/verify_v7/word/document.xml` text blocks to match the updated framing:
- Primary claim: behavioral rationalization + diversity retention
- Secondary risk: hallucination concern (managed by governance)
- Explicit module constraints: identity rules + physical rules
- Terminology constraint: avoid the word `middleware`

## A) Abstract / Significance Blocks

### A1. Key-point line (replace)
- Current location hint: `paper/verify_v7/word/document.xml:180`
- Replace with:
`Governance rules transfer across domains: flood adaptation (100 agents, 10 yr) and irrigation (78 agents, 42 yr).`

### A2. Abstract core paragraph (replace entire block)
- Current location hint: `paper/verify_v7/word/document.xml:198`
- Replace with:
`Large language models (LLMs) offer a promising path toward cognitively realistic agent-based models (ABMs) for water resources planning, but unconstrained LLM agents can produce state-inconsistent and behaviorally incoherent decisions. We present WAGF (Water Agent Governance Framework), an open-source governance framework that enforces domain-specific physical and institutional constraints while preserving emergent behavioral diversity. WAGF integrates three components: (1) a rule-based validator chain, (2) a tiered cognitive memory system, and (3) a priority context builder. We report two complementary diagnostics: rationality deviation (R_R) and feasibility contradiction (R_H), and quantify diversity with Effective Behavioral Entropy (EBE). In flood adaptation experiments (100 agents, 10 years, three Gemma 3 sizes), governance reduces coherence deviations while maintaining higher effective diversity. We further demonstrate transferability in Colorado River irrigation management (78 districts, 42 years).`

### A3. Plain-language summary block (replace)
- Current location hint: `paper/verify_v7/word/document.xml:216`
- Replace with:
`Artificial intelligence language models can power virtual agents that make human-like decisions in water management simulations. Without governance, these agents may produce infeasible or behaviorally inconsistent choices. We developed WAGF, a governance framework that checks each decision against identity and physical constraints, then applies coherence checks, before execution. This process improves behavioral rationality while preserving diverse, realistic choices. We demonstrate the approach in two water domains: household flood adaptation and Colorado River irrigation management.`

## B) Introduction Theory Example Sentence (ABM examples required)

### B1. Replace generic theory-grounded sentence
- Current location hint: `paper/verify_v7/word/document.xml:241`
- Replace with:
`In water resources practice, many ABMs encode behavior through explicit theory-grounded rules and utility assumptions: flood adaptation studies often operationalize PMT and related PADM constructs for appraisal-action logic, whereas irrigation-demand studies commonly use utility/risk formulations that can be interpreted through Prospect Theory under scarcity (Rogers, 1983; Lindell & Perry, 2012; Kahneman & Tversky, 1979; Hung & Yang, 2021).`

## C) Methods: Architecture/Module Description

### C1. Remove "governance middleware" phrase
- Current location hint: `paper/verify_v7/word/document.xml:289`
- Replace with:
`WAGF is a governance framework between LLM reasoning and simulation state transition. The LLM layer proposes candidate actions, WAGF evaluates those proposals against explicit feasibility and behavioral constraints, and the execution layer applies only approved actions to the environment (Figure 1). WAGF does not generate domain decisions on behalf of agents and does not mutate environment state directly.`

### C2. Add explicit rule-order sentence (if absent near methods)
- Add sentence:
`Identity rules and physical rules are enforced as first-pass constraints before thinking-level coherence checks, so infeasible proposals are filtered prior to execution.`

## D) Metrics and Results Consistency Fixes

### D1. Denominator alignment
- Current locations: `paper/verify_v7/word/document.xml:958`, `paper/verify_v7/word/document.xml:967`
- Replace equation text with:
`R_H = n_id / n_active`
`R_R = n_think / n_active`

### D2. Remove obsolete high-R_H claim
- Current location hint: `paper/verify_v7/word/document.xml:1061`
- Replace with:
`Under the current strict feasibility definition (identity/precondition contradictions), R_H remains near zero across most runs. The dominant residual channel is coherence deviation (R_R), and governance (Groups B/C) substantially reduces this channel relative to ungoverned baselines.`

### D3. Table caption language update
- Current location hint: `paper/verify_v7/word/document.xml:371`
- Replace with:
`Table 1. Cross-model governance effectiveness in flood adaptation (100 agents, 10 years). Ungov. = Group A (raw LLM), WAGF = governed configurations. R_H = strict feasibility contradiction rate; R_R = coherence-deviation rate; EBE = Effective Behavioral Entropy.`

## E) Conclusion Framing

### E1. Remove "governance middleware" phrase
- Current location hint: `paper/verify_v7/word/document.xml:1908`
- Replace with:
`We present WAGF as a governance framework for LLM-driven agent-based modeling of human-water systems, together with a feasibility-aware diversity metric (EBE) and a coherence diagnostic (R_R). Across two domains, the experiments support three conclusions.`

## F) Terminology Lock

Use:
- `governance framework`
- `governance layer`
- `rule-based governance runtime`

Avoid:
- `middleware`

