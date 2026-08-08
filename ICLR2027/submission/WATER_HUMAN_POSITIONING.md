# Water--human interaction spinout: scope and readiness audit

Updated 2026-08-08. This is an internal positioning record, not part of the
anonymous ICLR manuscript.

## Two papers, two questions

The ICLR paper asks whether a governed-agent evaluation score remains a valid
measurement when an agent-authored condition both affects execution and
selects the records being scored. Irrigation is the primary empirical example;
Flood is a bounded secondary check.

A water-resources or water--human-systems paper would ask a different question:
how do water-use decisions, governance rules, and reservoir dynamics interact,
and what do those dynamics imply for a water-management policy? It should treat
the coupled simulation as the scientific object, not as a stress test for an
evaluation metric. The two papers may share released runs, but they must not
share claims by copy-and-paste.

## What the current corpus can support

| Claim for a water paper | Current evidence | Status |
| --- | --- | --- |
| Agent decisions feed a shared reservoir and later state returns to agent context | 78 farm agents, 42 simulated years, 3,276 decision rows per run; reservoir trajectories and action/state records | Supported descriptively |
| Governance changes the simulated water trajectory under the studied rule | Five seed-paired irrigation configurations; governed and no-validator trajectories; no-validator arm reaches the 895-ft floor in all five seeds | Supported for this rule and corpus |
| The simulated system is a calibrated or predictive representation of a real basin | No calibration-to-observation analysis is in the ICLR package | Not supported |
| A policy improves water sustainability, equity, or welfare | No preregistered domain outcome, uncertainty analysis, or policy counterfactual is reported | Not supported |
| Human decision behavior is empirically validated | The current agents are simulated LLM agents; no human or observed behavioral calibration is included | Not supported |
| A general water-human mechanism transfers across basins | One coupled irrigation setting, with a non-coupled Flood boundary check | Not supported |

The current data are therefore a credible starting point for a water--human
simulation paper, but they are not by themselves a final water-resources
submission. The ICLR manuscript should not imply hydrological validation or a
policy recommendation that the corpus does not test.

## Recommended water-paper contribution

The strongest defensible water direction is a methodological simulation paper
about how behavioral governance rules alter the co-evolution of agent water
demand and reservoir state. The paper should compare explicitly specified rule
regimes, report water-system outcomes and uncertainty, and explain which
behavioral assumptions create each trajectory. It should not present the
validator-on/off contrast as a causal treatment effect without a design that
supports that interpretation.

Relevant domain anchors include coupled watershed modeling with agent decisions
and hydrology (Khan et al., 2017; Lin et al., 2022), and coupled drought-
adaptation feedbacks (Streefkerk et al., 2023). These references are included
in the ICLR bibliography because they justify why the irrigation example has a
meaningful human--environment feedback structure; they do not validate the
current simulator.

## Minimum work before a water venue

1. State the basin, water-accounting units, behavioral theory, and policy
   question independently of the ICLR measurement problem.
2. Add calibration or validation against observations, or explicitly position
   the work as a synthetic methodological study and justify the synthetic
   design.
3. Predefine water outcomes (for example reservoir reliability, shortage
   duration, demand, equity, or ecological constraints), scenario factors, and
   uncertainty intervals.
4. Run rule-regime and sensitivity comparisons with clean, seed-paired
   provenance. Do not use the unreleased governed-only first-attempt branch as
   a matched behavioral result.
5. Report model limitations, parameter sensitivity, and reproducible water
   accounting before selecting an AGU or water-resources venue.

The AGU Annual Meeting window is 2026-12-07--2026-12-11. It is a separate
submission track from ICLR 2027; the current ICLR package remains the active
paper and this spinout remains a planned follow-up until the domain evidence
is added.
