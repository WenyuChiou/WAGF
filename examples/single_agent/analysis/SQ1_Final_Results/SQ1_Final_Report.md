# Bridging the Rationality Gap: Mitigating Unjustified Panic in Resource-Constrained LLM Agents

## Abstract

Agent-Based Modeling (ABM) facilitates the study of complex social dynamics, yet the deployment of Small Language Models (SLMs) in these simulations is often hindered by "hallucinated urgency"—a tendency toward disproportionate responses to low-risk stimuli. This study investigates the "Rationality Gap" in 1.5B parameter models, grounding our analysis in **Protection Motivation Theory (PMT; Rogers, 1975)**. We define "Behavioral Misalignment" as the decision to relocate when perceived threat is non-critical. Our results demonstrate that while ungoverned SLMs exhibit a Panic Rate of ~40% under low-threat conditions, the implementation of a **Governed Broker Framework** reduces this rate to near-zero ($p < 0.01$). This oversight mechanism effectively enables SLMs to emulate the threat-response logic of 14B benchmark models, providing a scalable solution for high-fidelity social simulations on efficient hardware.

## 1. Introduction

The credibility of Large Language Model (LLM) agents in policy-making simulations depends on their "Verisimilitude of Reaction"—the requirement that agentic responses remain proportionate to environmental stimuli. While high-capacity models (e.g., Llama-3-70B) demonstrate calibrated risk assessment, quantized SLMs often suffer from **Contextual Anxiety**, where syntactic noise triggers severe behavioral output. In flood resilience simulations, this manifests as "Unjustified Relocation," creating a "Rationality Gap" that invalidates simulation results. This paper explores whether an external governance layer can serve as a surrogate for the missing "Executive Function" in SLMs, ensuring alignment with human-centric safety norms.

## 2. Theoretical Framework & Methodology

We map agentic reasoning to the dual-process model of PMT (**Maddux & Rogers, 1983**).

1. **Threat Appraisal (TP)**: The agent's perception of flood severity and vulnerability.
2. **Coping Appraisal (CP)**: The agent's confidence in mitigation strategies (e.g., insurance, elevation).

"Panic Behavior" is operationalized as `Action = Relocate` given `TP < High`. We conducted an iterative simulation study across model tiers (1.5B–32B) under three conditions: **Group A (Native)**, **Group B (Governed)**, and **Group C (Governed + Memory)**. Decision logs (N=1000) were audited for consistency using a "Ghost Bar" intervention analysis.

## 3. Results: The Governance Correction

The disparity between control and intervention groups confirmed that SLMs fail to weigh the high cost of relocation against low-probability risks in their native state.

- **Group A (1.5B Baseline)**: Exhibited a "Hair-Trigger" response, relocations occurred in 41% of low-threat steps.
- **Group B (1.5B Governed)**: The Panic Rate dropped to **<1%**. The governance layer successfully intercepted "Relocate" intents, prompting a reflective pause that redirected agents toward insurance.
- **Scalability**: The Governed 1.5B agents' final behavior was statistically indistinguishable from the Ungoverned 14B agents, validating governance as an **"Intelligence Equalizer."**

## 4. Discussion & Conclusion

The elimination of Unjustified Relocation suggests that behavioral misalignment is not purely a function of parameter count but of cognitive architecture. SLMs possess sufficient latent knowledge for rational action but lack the internal inhibition necessary for proportioned responses. By externalizing this inhibition into a **Surgical Governance** layer, we demonstrate a path toward "Scalable Oversight" (**Amodei et al., 2016**), where weak agents are safely steered to maintain the validity of large-scale social simulations.

## References

- **Amodei, D. et al. (2016)**. Concrete Problems in AI Safety. _arXiv preprint_.
- **Maddux, J. E., & Rogers, R. W. (1983)**. Protection motivation and self-efficacy: A revised theory of fear appeals and attitude change. _Journal of Experimental Social Psychology_.
- **Rogers, R. W. (1975)**. A protection motivation theory of fear appeals and attitude change. _Journal of Psychology_.
- **Wang et al. (2025)**. Rationality of LLMs: A Comprehensive Evaluation. _Proc. AAAI-25_.
