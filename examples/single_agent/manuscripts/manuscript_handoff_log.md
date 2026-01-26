# Manuscript Handoff Log: JOH Technical Note (Part 1)

**Date**: 2026-01-24
**Status**: Experimental Validation Phase (Scaling Laws)
**Target Manuscript**: Technical Note on "Three Big Questions" (Scalability, Heterogeneity, Governance)

## 1. The Core Proposal (JOH Technical Note)

We are writing a Technical Note titled: **"Governed Agency in Crisis: A Technical Note on Scaling LLM-ABMs for Climate Adaptation"**.

### The "Three Big Questions" Framework

The paper is structured to answer three specific questions posed by the Journal of Open Humanities (JOH) scope:

1.  **Scalability**: Can this framework run 100+ agents for 10+ years without crashing?
    - _Proof_: Demonstrated by our 100-Agent Simulation (1.5B/8B tests).
2.  **Heterogeneity**: Does it capture diverse human behaviors (not just one "average" agent)?
    - _Proof_: The "1.5B Panic" vs "8B Rationality" contrast, plus individual traces (`Low to Medium` coping).
3.  **Governance Utility**: Does the "Broker" actually fix anything?
    - _Proof_: The **Governance Scaling Law** (U-Shaped Curve).
      - **1.5B**: High Intervention (Survival Mode).
      - **8B**: Moderate Intervention (Optimization Mode).
      - **32B**: Low Intervention (Expert Mode).

## 2. Current Context (for Next AI/Subagent)

We are in the middle of a massive parallel experiment to validate the **Governance Scaling Law** and **U-Shaped Curve Hypothesis**.

- **User Goal**: Produce the first "Technical Note" (JOH Paper 1) showcasing the 100-Agent/10-Year simulation capability.
- **Key Hypothesis**: Governance overhead is non-linear; smaller models need more "guidance" (high intervention), larger models might need less but have subtle "stubbornness". 8B is expected to be the "Sweet Spot".

## 3. Active Experiments

We are currently running a full ABC Matrix scan across DeepSeek-R1 tiers:

- **DeepSeek 1.5B**: Running Group C (Priority Schema). _Status: Healthy, ~96% Intervention Success._
- **DeepSeek 8B**: Running Group C (Priority Schema). _Status: Healthy, ~100% Parsing Success, "Sweet Spot" candidate._
- **DeepSeek 14B & 32B**: Queued in `run_deepseek_large_tiers.ps1`, will start automatically.

## 4. Key Files & Locations

- **Results**: `examples/single_agent/results/JOH_FINAL/` (This is the Source of Truth for the paper).
- **Metric Analysis**: `examples/single_agent/analyze_abc_metrics.py` (Use this to generate charts once runs are done).
- **Log Analysis**: `examples/single_agent/analyze_interventions.py` (For qualitative case studies of "Fallout" or "Retries").

## 5. Immediate Next Steps (Roadmap)

1.  **Monitor Completion**: Wait for 1.5B/8B Group C to finish.
2.  **Data Synthesis**: Run `analyze_abc_metrics.py` to aggregate CSVs from all tiers.
3.  **Visualization**: Generate the "U-Shaped Curve" plot:
    - X-Axis: Model Size (1.5B -> 32B)
    - Y-Axis: Governance Intervention Rate / Fallout Rate
4.  **Drafting**: Update `manuscripts/technical_note_three_questions.md` with real data.

## 6. Technical Notes

- **Model Adapter**: Fully generalized (embedded PMT normalization). No need to touch `model_adapter.py` or `.yaml` unless adding a non-DeepSeek model.
- **Governance Auditor**: Active and recording metrics. Check `execution.log` for qualitative traces.
- **Performance**: 8B is running at `workers=1` due to VRAM constraints on the user's machine; do not increase workers for >8B models.
