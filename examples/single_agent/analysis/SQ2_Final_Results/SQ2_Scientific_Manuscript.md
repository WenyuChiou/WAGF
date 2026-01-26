# Governing Cognitive Collapse: The Role of Rule-Based Constraints in Sustaining LLM Agency

## Abstract

Agent-Based Modeling (ABM) powered by Large Language Models (LLMs) promises to revolutionize social simulation, yet it faces a critical stability challenge: small models often exhibit "Mode Collapse," converging into irrational panic loops that render simulations scientifically invalid. This study investigates whether a Governance Framework can serve as a "Cognitive Prosthetic," preventing this collapse in 1.5B resource-constrained models. By analyzing the "Cognitive Lifespan"—defined via Shannon Entropy of agent decisions—we demonstrate that governance extends the useful life of a simulation from 4 years to over 10 years, effectively bridging the rationality gap between 1.5B and 14B models.

## 1. Introduction

The democratization of large-scale social simulations requires the use of efficient, smaller language models (SLMs). However, preliminary studies indicate a "Rationality Gap": models below 10B parameters frequently lack the reasoning depth to maintain stable long-term strategies in high-stress scenarios. In our flood adaptation simulation, ungrouped 1.5B agents consistently succumbed to "Panic Relocation," abandoning the environment en masse regardless of actual risk. This phenomenon mirrors "Mode Collapse" in generative AI, where the model output distribution degrades into a single, repetitive mode. To address this, we integrated the "Governed Broker Framework," a rule-based constraint system designed to interrupt heuristic panic and force deliberative processing. This paper asks: **Can external governance prevent behavioral mode collapse and sustain the heterogeneity required for valid social simulation?**

## 2. Methodology

We conducted a comparative longitudinal study across three intelligence tiers (1.5B, 8B, 14B) over a simulated decade. Agents were divided into three conditions: Ungoverned (Group A), Governed (Group B), and Context-Only Reference (Group C).

Our primary metric for evaluation was **Shannon Entropy ($H$)**, calculated annually on the decision distribution of the active agent population. We define the "Cognitive Lifespan" of a simulation as the duration for which $H > 1.0$. An entropy nearing zero indicates a "Monoculture," representing a failed simulation where individual agency has been replaced by deterministic algorithmic bias. To ensure rigorous auditing, we applied an "Active Agent Filter," filtering out agents who had relocated in previous years while retaining valid relocation decisions made in the current year.

## 3. Results

The analysis revealed a stark dichotomy between governed and ungoverned populations.

### 3.1 The Line of Death (Ungoverned 1.5B)

The Ungoverned 1.5B model (Group A) exhibited a rapid decay in behavioral diversity. Starting with an entropy of 1.85 in Year 1, the population entered a "Panic Spiral" by Year 3. By Year 4, the entropy collapsed to 0.00, implying that 100% of the active population had engaged in the same panic relocation behavior. This rapid convergence confirms that without constraints, small models possess a functional lifespan of less than 4 years before simulation failure.

### 3.2 The Line of Life (Governed 1.5B)

In contrast, the Governed 1.5B model (Group B) maintained a stable entropy plateau, fluctuating between 1.02 and 2.09 throughout the decade. The governance protocols acted as a "Sanity Firewall," preventing the initial panic wave and forcing agents to distribute their choices among "Do Nothing," "Insurance," and "Elevation." This intervention successfully extended the cognitive lifespan of the simulation indefinitely, allowing the 1.5B model to mimic the stability profile of the 14B benchmark.

### 3.3 The 8B Anomaly

An unexpected finding emerged in the 8B Ungoverned group. While it did not flee, it converged into a "Lazy Monoculture" of blind elevation. Step-by-step auditing revealed that in Year 9, 97% of agents chose "Elevation," with only 3% choosing "Relocate" ($H=0.21$). While technically "alive," this low-diversity state represents a secondary form of failure, highlighting that even mid-sized models require governance to maintain true heterogeneity.

## 4. Discussion

These findings suggest that rule-based governance functions as a "Cognitive Prosthetic." It does not merely constrain behavior; it mathematically regularizes the output probability distribution of the LLM. By introducing "Rule Tokens" into the system prompt, we create competing attention heads that flatten the logit distribution, preventing the "winner-take-all" dynamics of panic.

For the field of computational social science, this is a distinct validation of hybrid neuro-symbolic architectures. We conclude that valid, long-term ABMs can be run on efficient hardware (1.5B models) _only_ if encased in a rigorous governance framework. Diversity is not just a nice-to-have feature; it is the vital sign of a living simulation.
