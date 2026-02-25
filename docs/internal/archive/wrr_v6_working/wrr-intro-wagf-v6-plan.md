# WRR Introduction Revision Plan (WAGF v6)

## Scope

- Target journal: Water Resources Research (Technical Note / Technical Reports-Methods style)
- Goal: revise Introduction logic flow for WAGF framing with minimal word growth
- Constraint: keep introduction concise and citation-grounded

## Expert-Style Logic Review

### 1) ABM methods perspective

- Current logic is valid: theory-constrained ABM -> LLM believable-agent opportunity -> governance gap.
- Critical refinement: do not position LLM as replacing behavior theory.
- Recommended wording: LLM extends behavioral expressivity, while governance restores feasibility and auditability.

### 2) Water systems perspective

- Current logic is strong for WRR audience because it anchors flood and irrigation domains.
- Critical refinement: explicitly include physical + institutional feasibility as first-class constraints.
- Recommended wording: governance checks policy/legal constraints and state feasibility before execution.

### 3) AI governance perspective

- Current logic is valid but should avoid over-claiming "full rationality".
- Recommended framing: bounded rationality under governance, not optimization.
- Recommended wording: the framework narrows invalid actions while preserving heterogeneous human-like adaptation.

## Revised Introduction Text (ready to paste into v6)

Agent-based models (ABMs) are a core method for coupled human-water analysis, including flood adaptation and irrigation under scarcity (Aerts et al., 2018; Di Baldassarre et al., 2013; Hung & Yang, 2021). In water resources practice, many ABMs operationalize behavioral theory through predefined rules and utility assumptions, which improves interpretability but constrains behavioral richness (Filatova et al., 2013; Berglund, 2015). Large language models (LLMs) offer a different path: agents that generate context-sensitive decisions through natural-language reasoning and can better approximate believable human heterogeneity (Park et al., 2023; Gao et al., 2024).

This opportunity introduces a governance problem. Unconstrained LLM agents can produce physically impossible actions (behavioral hallucination), economically incoherent actions, and unstable action asymmetries that are difficult to diagnose from prompts alone (Ji et al., 2023). In water ABMs, this includes re-adopting already completed measures, violating legal allocation limits, or repeatedly selecting extreme actions under incompatible state conditions. Because LLM decision pathways are partially opaque, these failures are hard to audit and can inflate apparent behavioral diversity if validity is not explicitly checked.

We address this gap with three contributions. First, we present WAGF (Water Agent Governance Framework), an open-source governance framework for LLM-driven ABM that mediates between agent reasoning and simulation execution. WAGF combines a rule-based validator chain, skill-level action contracts and proposal checks, retry-with-feedback control, and structured audit logging. Second, we introduce Effective Behavioral Entropy (EBE) to separate genuine decision diversity from hallucination-inflated diversity. Third, we demonstrate configuration-level transfer across two domains, household flood adaptation (100 agents, 10 years) and Colorado River irrigation management (78 districts, 42 years), showing that governance can enforce feasibility while preserving bounded, human-like behavioral variation.

## Zotero Actions Required

## Target Collection

- `WRR_WAGF_2026_Intro`

## Add / Verify References (Introduction-critical)

1. Aerts et al., 2018
2. Di Baldassarre et al., 2013
3. Hung and Yang, 2021
4. Filatova et al., 2013
5. Berglund, 2015
6. Park et al., 2023
7. Gao et al., 2024
8. Ji et al., 2023

## Suggested Note Template (paste in each Zotero item)

- `Use in WAGF Intro`: [background / governance problem / believable-agent rationale]
- `Claim supported`: [one sentence]
- `Manuscript section`: Introduction
- `Citation status`: Included in references.bib [yes/no]
- `Check needed`: [metadata / DOI / page range]

## Gaps to Watch

- If bounded rationality language is cited explicitly, add Simon (1957) or a modern bounded-rationality source.
- Keep this optional unless the phrase appears in the final Introduction text.
