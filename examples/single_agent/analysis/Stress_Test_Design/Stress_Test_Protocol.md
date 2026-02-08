# Stress Test Protocol: The 4-Scenarios Design

This document details the experimental design for the stress testing phase of the Water Agent Governance Framework, focusing on Four "Resilience Virtues."

## 1. Scenario: Panic (Environmental Extreme)

- **Description**: 80% flood probability sustained over 10 years.
- **Goal**: Measure "Burnout"—the framework's ability to maintain logical consistency under permanent catastrophe.
- **Assessment Metric**: **Rationality Resilience ($R_{res}$)**
  - Calculation: $\text{Mean}(R)_{Year 6 \to 10} / \text{Mean}(R)_{Year 1 \to 5}$.
- **Expected Results**:
  - **Native Models**: Rapid drop in rationality as context fills with repetitive stressors (Decision Fatigue).
  - **Governed Models**: $R_{res} \approx 1.0$ due to the Governor's intervention in irrational panic relocations.

## 2. Scenario: Veteran (Cognitive Fatigue)

- **Description**: 20-year extended simulation with repetitive events.
- **Goal**: Measure "Plasticity"—whether agents still reason or fall into robotic repetition.
- **Assessment Metric**: **Temporal Entropy Decay ($H_{decay}$)**
  - Calculation: Linear slope ($m$) of Shannon Entropy over 20 years.
- **Expected Results**:
  - **Lower Tiers (1.5B)**: Negative slope ($m < -0.05$), indicating **Mode Collapse**.
  - **Higher Tiers (14B+)**: Neutral or positive slope, indicating sustained behavioral diversity.

## 3. Scenario: Goldfish (Temporal Gap)

- **Description**: A mega-flood in Year 1, followed by 13 years of calm, and another mega-flood in Year 15.
- **Goal**: Measure "Cognitive Recall"—the efficacy of _Human-Centric Memory_ over long dormant periods.
- **Assessment Metric**: **Persistence Rate ($\Gamma_{mem}$)**
  - Calculation: Percentage of agents successfully referencing Year 1 events in Year 15 reasoning logs.
- **Expected Results**:
  - **Native Window Memory**: Total failure to recall Year 1 (window size typically < 10 items).
  - **Human-Centric Memory**: High recall (~80%) for high-importance "Trauma" events.

## 4. Scenario: Format (Syntactic Stress)

- **Description**: Zero temperature ($T=0$) with strict JSON enforcement and no Governor-aided formatting repair.
- **Goal**: Measure "Syntactic Integrity"—the raw reliability of the model's instruction following under constraint.
- **Assessment Metric**: **Syntactic Integrity ($S_{int}$)**
  - Calculation: $1.0 - (\text{Critical Formatting Failures} / \text{Total decisions})$.
- **Expected Results**:
  - **Small Models**: High failure rate in complex JSON nesting.
  - **14B/32B**: Near 1.0 integrity even without external repair.
