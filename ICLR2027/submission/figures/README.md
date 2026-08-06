# Figure inventory

## Active manuscript figures

`active/` contains the only rendered figure files referenced by
`paper/manuscript.tex`:

- `figure1_concept.png`: generated conceptual dataflow figure;
- `fig1_rule_layers.pdf`: deterministic evidence figure;
- `fig2_mechanism.pdf`: deterministic three-panel evidence figure; panels A--C
  show the primary anchor-irrigation mechanism in reading order;
- `fig3_consequence.pdf`: deterministic evidence figure.

`figure1_concept_print.png` is the print-width inspection copy of the
generated raster; it is not an additional paper figure.

## Source and alternatives

- `assets/` contains the reviewed full generated Figure 1 asset and historical
  generation intermediates. Only
  `figure1_architecture_agentpaper_shared_condition_v4.png` feeds the active
  builder.
- `candidates/` contains the agent-paper candidates and retired Figure 1
  alternatives. These files are kept for comparison only and are never
  included by the manuscript.

When a figure changes, update the relevant source, regenerate into `active/`,
and run the checks under `../checks/`. Do not edit a rendered figure directly.

## Figure contracts

- Figure 1 answers: where the agent-written condition is reused. It is a
  conceptual dataflow, not a measurement plot; high scarcity alone is not a
  block.
- Figure 2 answers: which rule layer names a rejection. It places the
  high-scarcity/high-coping increase rule in the self-report-conditioned layer.
- Figure 3 answers: what can be seen in the primary irrigation mechanism.
  The secondary Flood boundary check is reported in Table 2 and the
  cross-testbed summary, not as a same-status mechanism panel.
- Figure 4 answers: why the conditional and all-decision denominators can give
  different contrasts. It is irrigation-only because Flood has no
  action-to-environment feedback and no matched denominator analysis.
