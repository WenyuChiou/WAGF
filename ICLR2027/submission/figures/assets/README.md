# Figure 1 generated assets

`figure1_architecture_agentpaper_shared_condition_v6_retry_return.png` is the reviewed
generated shared-condition figure used by the active ICLR manuscript. It
contains the AI and environment cues, functional icons, black borders, flat
colored fills, explicit black/amber ports, arrows, labels, and background as
one generated raster image. The response enters Validator, a rejected proposal
returns directly to Agent response for retry or a default action can execute,
the final record enters
Decision log, and the shared condition routes separately to Validator and
Counted records.

This is the only generated source asset retained in the active package. Run
`source/figure1_agent_paper.py` to stage it into `figures/active/`. Superseded
generation intermediates remain recoverable from Git history.
