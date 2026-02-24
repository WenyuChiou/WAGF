# Cover Letter — Nature Water

Dear Editors,

We are pleased to submit our manuscript, **"Institutional Governance Enables Adaptive Strategy Diversity in Language-Based Water Resource Simulation,"** for consideration as an Analysis article in *Nature Water*.

## Summary

Water resource models have long represented human decisions as parameterized functions — computable mappings that compress reasoning into mathematical objects. This paper proposes a governance architecture that validates natural-language agent reasoning against modular physical and institutional rules, and demonstrates that this approach addresses three longstanding limitations of agent-based water modelling:

1. **Opaque reasoning**: Traditional agents map numerical states to numerical actions; our language-based agents produce explicit reasoning traces that governance can evaluate, creating a transparent decision audit trail.

2. **Parametric homogeneity**: Conventional agent-based models differentiate agents only through parameter values within identical decision logic. Governed language agents generate qualitatively different reasoning paths, producing higher strategy diversity than both ungoverned agents and a hand-coded Protection Motivation Theory baseline.

3. **Hard-coded institutional rules**: In existing models, institutional rules are embedded in simulation code and cannot be independently manipulated. Our modular validator architecture enables experimental decomposition — we demonstrate that removing a single rule of twelve (the demand ceiling linking individual proposals to basin-wide demand) increases diversity but collapses drought responsiveness, distinguishing adaptive from arbitrary diversity.

## Key Findings

In a 42-year Colorado River irrigation simulation, governed agents extracted more water than ungoverned agents (demand ratio 0.394 vs 0.288) while maintaining stronger drought coupling (r = 0.547 vs 0.378) — a pattern of adaptive exploitation consistent with prior-appropriation dynamics. The governance effect generalized from chronic drought (78 agents, 42 years) to acute flood hazard (100 agents, 10 years), was positive for five of six language model scales tested (3B–27B parameters, two model families), and governance reduced irrational behaviour rates from 0.8–11.6% to below 1.7%, significantly for four of six models.

## Relevance to Nature Water

This work is relevant to *Nature Water* because it advances computational representation of human water decision-making — a core challenge in understanding human–water system dynamics. The governance architecture functions as a computational laboratory for water institutions: researchers can independently enable, disable, or reconfigure institutional rules and observe how populations of reasoning agents endogenously adapt their strategies. This capacity to experimentally probe institutional designs is distinct from sensitivity analysis and is enabled by the natural-language reasoning format that our method introduces.

## Manuscript Details

- **Format**: Analysis (main text ~4,000 words + Methods + Supplementary Information)
- **Domains**: Colorado River irrigation allocation + household flood adaptation
- **Models**: Six open-weight language models (Gemma-3 4B/12B/27B, Ministral 3B/8B/14B)
- **Experiments**: 9 irrigation runs (78 agents × 42 years × 3 conditions) + 54 flood runs (100 agents × 10 years × 6 models × 3 groups)

The manuscript has not been submitted elsewhere and all authors have approved the submission.

We look forward to your consideration.

Sincerely,
[Authors]
