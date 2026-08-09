# Figure inventory

## Active manuscript figures

`active/` contains the only rendered figure files referenced by
`paper/manuscript.tex`:

- `figure1_concept.png`: generated conceptual dataflow figure;
- `fig1_rule_layers.pdf`: deterministic evidence figure;
- `fig2_mechanism.pdf`: deterministic three-panel evidence figure; panels A--C
  show the primary anchor-irrigation mechanism in reading order;
- `fig3_consequence.pdf`: deterministic executed-action denominator-gap figure.

`figure1_concept_print.png` is the print-width inspection copy of the
generated raster; it is not an additional paper figure.

## Source

- `assets/` contains the single reviewed generated Figure 1 source:
  `figure1_architecture_agentpaper_shared_condition_v6_retry_return.png`.
  Superseded assets and candidates are retained in Git history, not in this
  active package.

When a figure changes, update the relevant source, regenerate into `active/`,
and run the checks under `../checks/`. Do not edit a rendered figure directly.

## Figure contracts

- Figure 1 answers: where the agent-written condition is reused. It is a
  conceptual dataflow, not a measurement plot; high scarcity alone is not a
  block. The retry/default-action branch is shown because the primary paper
  reading counts the action that executed.
- Figure 2 answers: which rule layer names a rejection. It places the
  high-scarcity/high-coping increase rule in the self-report-conditioned layer.
- Figure 3 answers: how the primary irrigation setting changes the observed
  world and the filtered population. Panels A--C respectively show the yearly
  condition contrast, the reservoir trajectories, and the all-decision versus
  never-retried sensitivity. The secondary Flood boundary check is reported in Table 3 and the
  cross-testbed summary, not as a same-status mechanism panel. An earlier
  Panel D proposal placed the two settings on one contrast axis to show
  separation, but that juxtaposition obscured the different action ontology,
  feedback structure, appraisal field, and seed matching. It is therefore
  retained as a table-level boundary check rather than a visual co-primary
  result.
- Figure 4 answers: why the conditional and all-decision denominators can give
  different contrasts under the executed-action reading. It is irrigation-only
  because Flood has no action-to-environment feedback and no matched denominator
  analysis. Its source is `ICLR2027/fig_denominator_gap.py`, with the copied
  values in `supplement/fig3_denominator_gap.csv`.
