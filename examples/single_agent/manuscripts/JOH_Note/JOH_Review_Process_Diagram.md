# Scientific Review Board: Methodology Visualization

This diagram illustrates the **Iterative Scientific Review Process** employed to analyze the Water Agent Governance Framework results (Groups A, B, C). It highlights the interaction between Data Generation, Metric Critique (Subagents), and Hypothesis Refinement.

```mermaid
graph TD
    %% Nodes
    Data[Raw Data Generation]
    subgraph "Phase 1: Metric Calculation"
        M1[Calculate RS (Rationality)]
        M2[Calculate IF (Int. Fidelity)]
        M3[Calculate Gap Rate (Silent)]
    end

    subgraph "Phase 2: Scientific Review Board (Subagents)"
        Skeptic[Reviewer 1: The Skeptic]
        Method[Reviewer 2: The Methodologist]
        Lead[Lead Investigator]
    end

    subgraph "Phase 3: Synthesis & Pivot"
        Pivot[Pivot to Stress Tests]
        Comp[Composite Error Metric]
        Sig[Chi-Square Verification]
    end

    Final[Final Diagnosis: "Cognitive Stabilizer"]

    %% Edges
    Data --> M1 & M2 & M3
    M1 & M2 & M3 --> Skeptic

    %% The Critique Loop
    Skeptic --"RS=1.0 for all (Ceiling Effect)"--> Lead
    Method --"IF is noise (Inaction Bias)"--> Lead
    Lead --"Standard conditions are too benign"--> Pivot

    %% The Refinement
    Pivot --"Need Variance"--> Data
    Skeptic --"Llama B has 1.3% Gap"--> Comp
    Comp --"Combine Retries + Gaps"--> Sig

    %% Conclusion
    Sig --"p < 0.01 confirmed"--> Final

    %% Styling
    style Skeptic fill:#ffcccc,stroke:#333
    style Method fill:#ffeebb,stroke:#333
    style Lead fill:#ccffcc,stroke:#333
    style Final fill:#ccccff,stroke:#333,stroke-width:2px
```

## Description of Roles

1.  **The Skeptic**: Challenges "Null Results" (e.g., "Why is Group C equal to B?"). Forces the pivot to looking at "Silent Failures" (Gaps) instead of just Compliance.
2.  **The Methodologist**: Critiques metric validity (e.g., "Internal Fidelity is invalid if Action is always 0"). Suggests the "Composite Error" approach.
3.  **Lead Investigator**: Synthesizes conflicting views into a unified hypothesis ("The Safety Belt" theory) and directs the "Stress Pivot".
