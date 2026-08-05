# Figure inventory

## Active manuscript figures

`active/` contains the only rendered figure files referenced by
`paper/manuscript.tex`:

- `figure1_concept.png`: generated conceptual dataflow figure;
- `fig1_rule_layers.pdf`: deterministic evidence figure;
- `fig2_mechanism.pdf`: deterministic evidence figure;
- `fig3_consequence.pdf`: deterministic evidence figure.

`figure1_concept_print.png` is the print-width inspection copy of the
generated raster; it is not an additional paper figure.

## Source and alternatives

- `assets/` contains the reviewed full generated Figure 1 asset and historical
  generation intermediates. Only `figure1_architecture_agentpaper_nested_v3.png`
  feeds the active builder.
- `candidates/` contains the agent-paper candidates and retired Figure 1
  alternatives. These files are kept for comparison only and are never
  included by the manuscript.

When a figure changes, update the relevant source, regenerate into `active/`,
and run the checks under `../checks/`. Do not edit a rendered figure directly.
