# Bridging the Rationality Gap: Mitigating Unjustified Panic in Resource-Constrained LLM Agents

## Abstract

Social simulations using Large Language Models (LLMs) aim to replicate human decision-making, but smaller models (SLMs) often exhibit "hallucinated urgency," leading to irrational behavior. This study quantifies the "Rationality Gap" in 1.5B parameter models, specifically defining "Panic" as the decision to relocate (flee) when the perceived threat level is Low or Medium. Our results indicate that ungoverned SLMs exhibit a Panic Rate exceeding 40% in low-threat scenarios. However, the introduction of a Rule-Based Governance layer reduces this rate to near-zero, effectively enabling 1.5B models to emulate the threat-response logic of 14B benchmark models.

## 1. Introduction

A core requirement for credible Agent-Based Modeling (ABM) is the "Verisimilitude of Reaction"—agents must respond proportionately to stimuli. While state-of-the-art models (e.g., GPT-4, Llama-3-70B) demonstrate nuanced risk assessment, quantized SLMs often suffer from "Contextual Anxiety," where minor inputs trigger disproportionately severe actions. In our flood resilience simulation, this manifests as "Unjustified Relocation," where agents abandon their homes despite minimal flood risk. This flaw creates a "Rationality Gap" that renders SLM-based simulations economically invalid. This paper investigates whether an external "Governance Broker" can inject the necessary inhibition to bridge this gap.

## 2. Methodology

We defined "Panic Behavior" using a strict conditional logic: `Action = Relocate` AND `Threat_Appraisal < High`. This metric isolates irrational flight from legitimate survival responses. We conducted simulations across three model tiers (1.5B, 8B, 14B) under two conditions: Ungoverned (Group A) and Governed (Group B).

To verify the mechanism, we analyzed the decision logs of 100 agents over 10 simulation years. We employed a "Ghost Bar" analysis to track "Blocked Panic"—instances where the governance system intercepted an agent's intent to flee and successfully redirected them to a rational alternative (e.g., purchasing insurance).

## 3. Results

The disparity between the control and intervention groups confirmed the hypothesis of "Contextual Anxiety" in small models.

### 3.1 The Panic Baseline (Ungoverned)

The Ungoverned 1.5B model (Group A) demonstrated a fundamental inability to inhibit flight responses. In scenarios with Low Threat (Probability < 20%), 41% of these agents still chose to Relocate. This "Hair-Trigger" response suggests that the model fails to weigh the high cost of relocation against the low probability of disaster, defaulting instead to a survival heuristic trained on high-stakes fiction rather than rational economics.

### 3.2 The Governance Correction (Governed)

In the Governed condition (Group B), the Panic Rate dropped to negligible levels (<5%). The governance layer successfully intercepted the "Relocate" intent. Instead of physically blocking the action, the system prompted the agent to "Verify Threat Level." This reflective pause allowed the agent to lower its own threat appraisal and choose "Flood Insurance" instead. Crucially, the final behavior of the Governed 1.5B agents was statistically indistinguishable from the Ungoverned 14B agents (Group C), validating the claim that governance serves as an "Intelligence Equalizer."

## 4. Discussion

The elimination of Unjustified Relocation proves that the "Rationality Gap" is not purely a function of model parameter count but also of cognitive architecture. SLMs possess the knowledge to act rationally but lack the "Executive Function" to inhibit immediate impulses.

By externalizing this executive function into a Rule-Based Governance prompt, we enable SLMs to participate in complex social simulations without distorting the data with mass panic artifacts. This implies that future large-scale ABMs can run on efficient hardware without sacrificing behavioral validity, provided a robust governance layer is in place.
