# Paper3 MA Flood Research Question Plan

**Goal:** Define a defensible MA flood experiment plan for Paper 3 that is grounded in the current system design, uses identifiable interventions, and excludes memory ablation as a primary research axis.

**Scope:** [examples/multi_agent/flood/paper3](/c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/multi_agent/flood/paper3)

---

## Professor-Style Design Judgment

Based on the current Paper 3 system, the strongest publishable contribution is not "LLMs are human-like." The stronger claim is:

> A governed multi-agent LLM-ABM can expose how institutional feedback and social information jointly shape unequal flood adaptation trajectories, while keeping decision traces auditable and behavior theory-constrained.

Three design judgments follow from that:

1. The paper should center on **institutional feedback and inequality formation**, because this is the most identifiable, policy-relevant, and visually interpretable part of the model.
2. **Memory should remain part of the architecture**, but should not be the main intervention axis. Defending memory ablation would require too much additional argument about construct validity, retrieval validity, and whether the ablated system still represents the same behavioral theory.
3. Social channels are worth studying, but only through **clean experimental contrasts**. They should not be framed as vague "social influence matters" claims.

---

## Research Strategy

The Paper 3 design should use a simple logic:

1. Establish what the **full governed MA flood system** produces.
2. Remove one major mechanism at a time.
3. Measure what changes in inequality, timing, and diffusion.

This means the paper should be framed as an **intervention-based mechanism study**, not as three loosely parallel descriptive RQs.

---

## Recommended Research Questions

### RQ1: Full-System Outcome

**How does the full governed MA flood system produce unequal household flood adaptation trajectories over time?**

Purpose:
- Establish the baseline phenomenon under the complete model.
- Show the evolution of protection, damage, and adaptation gaps under the full system.

This RQ is descriptive but necessary. It defines the phenomenon that later ablations explain.

### RQ2: Institutional Feedback Contribution

**How does endogenous institutional feedback alter protection inequality relative to an exogenous-policy baseline?**

Purpose:
- Identify the contribution of LLM-driven government and insurance agents.
- Test whether dynamic subsidy and premium feedback narrow or widen inequality.

This should be the central causal RQ of the paper.

### RQ3: Social Information Contribution

**How do social information channels alter the timing and spread of protective actions relative to socially restricted baselines?**

Purpose:
- Identify whether social channels materially change adoption timing and diffusion structure.
- Compare not just total adoption, but the temporal and spatial pattern of spread.

This RQ should be framed as a mechanism contrast, not as a broad claim that "social learning exists."

---

## Explicit Non-RQ

The paper should **not** make memory ablation a primary RQ.

Reason:
- Memory is architecturally important, but isolating its contribution would require defending whether the simplified system is still theoretically comparable.
- The ablation would invite side debates about retrieval quality, consolidation quality, and narrative validity.
- That burden is too high relative to the current paper objective.

Memory can still appear as:
- architectural motivation
- qualitative interpretation
- future work
- supplementary sensitivity note, only if already available and low-risk

---

## Experimental Matrix

### Baseline Condition

**Full model**
- Config: [primary_experiment.yaml](/c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/multi_agent/flood/paper3/configs/primary_experiment.yaml)
- Mechanisms on:
  - LLM-driven government
  - LLM-driven insurance
  - gossip
  - news media
  - social media
  - governance strict profile

### Institutional Contrast

**Exogenous institutions**
- Config path: [si_ablations.yaml](/c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/multi_agent/flood/paper3/configs/si_ablations.yaml)
- Ablation: `si2_exogenous_institutions`

Interpretation:
- This isolates the contribution of institutional feedback.
- This is the key comparison for RQ2.

### Social Contrasts

Use the existing social ablations:
- `si3a_no_gossip`
- `si3b_no_social_media`
- `si3c_isolated`

Interpretation:
- `no_gossip`: tests interpersonal narrative transmission
- `no_social_media`: tests noisy broadcast-style influence
- `isolated`: tests the no-social baseline

These are the primary contrasts for RQ3.

### Governance Sensitivity

**No governance**
- Ablation: `si7_no_governance`

Interpretation:
- Not a main RQ, but an important robustness check.
- Useful for showing that behavior traces are not merely emergent but require governance to remain theory-coherent.

---

## Metrics by Research Question

### RQ1 Metrics

- MG/NMG adaptation rate by year
- MG/NMG protection gap by year
- cumulative damage by group
- insurance coverage by group
- elevation uptake by group
- buyout/relocation uptake by group

### RQ2 Metrics

- change in protection gap: full vs exogenous institutions
- change in cumulative damage gap: full vs exogenous institutions
- subsidy/adaptation lag
- premium/lapse relationship
- end-year group disparity under each institutional regime

### RQ3 Metrics

- time-to-first-adaptation by condition
- diffusion timing under full vs social ablations
- spatial or network clustering of adaptation
- reasoning citation rate for social signals, if extraction is reliable

---

## Figure Plan

### Main Figure 1: Full-System Inequality Trajectories

Show:
- MG vs NMG adaptation rate over time
- MG vs NMG cumulative damage over time
- flood-year annotations

Purpose:
- Answers RQ1.

### Main Figure 2: Institutional Feedback Contrast

Compare:
- full model
- exogenous institutions

Show:
- protection gap trajectories
- cumulative damage gap
- subsidy/premium overlays if readable

Purpose:
- Answers RQ2.

### Main Figure 3: Social Channel Contrast

Compare:
- full model
- no gossip
- no social media
- isolated

Show:
- adaptation timing curves
- diffusion/clustering summaries
- optional network snapshots if they are clean enough

Purpose:
- Answers RQ3.

---

## What Should Stay Out of the Main Claim

The paper should avoid centering:

- memory ablation as a core identification strategy
- broad claims of predictive accuracy
- generic claims that LLMs are "more human"
- overly fine-grained channel claims unless the signals are clearly measurable

The strongest framing is:

> The governed MA flood system reveals mechanism-level differences in inequality formation that are difficult to observe in traditional ABMs, especially when institutional feedback and social information are modeled endogenously.

---

## Practical Run Order

1. Run the full primary experiment.
2. Run `si2_exogenous_institutions`.
3. Run `si3a_no_gossip`, `si3b_no_social_media`, and `si3c_isolated`.
4. Run `si7_no_governance` as a robustness/sanity check.
5. Only revisit memory variants if a later supplementary need emerges.

---

## Decision Summary

Recommended paper structure:

- **Core phenomenon:** unequal adaptation trajectories in the full governed MA flood model
- **Main mechanism test:** endogenous institutional feedback
- **Secondary mechanism test:** social information channels
- **Support layer:** governance sensitivity
- **Not primary:** memory ablation

This is the most defensible plan given the current system design and the current paper objective.
