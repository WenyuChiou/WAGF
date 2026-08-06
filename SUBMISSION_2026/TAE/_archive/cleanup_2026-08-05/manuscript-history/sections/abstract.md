<!-- SUPERSEDED -- NOT A BUILD INPUT.
     paper/build.py reads paper/manuscript.md and nothing else; no script in this
     repository reads paper/sections/. These files are an earlier per-section draft,
     kept for history. manuscript.md is the single source of truth for every number,
     caption and CLAIM marker. Do not copy values out of this file and do not edit it
     to fix a number -- fix manuscript.md. (Banner added 2026-08-03, when the
     ministral3:8b cell balanced and these files were found holding the old
     2-seed values.) -->

## Abstract <!-- page budget: ~0.15 pg, counts against the 8-page body -->

Runtime governance layers for language-model agents report success as a conformance rate, and some
of their rules condition on a state the agent itself reports rather than on one the environment
records. A norm of that kind has no observation channel independent of the process it governs, so
enforcement rewrites the distribution of its own antecedent and the reported gain cannot be separated
into behaviour and composition by that statistic. We measure the consequence on paired runs with
validators and without, over {{CLAIM:n_model_configs}} model configurations in two agent testbeds.
The conditioning variable moves further than the rate it supports, by
{{CLAIM:anchor_high_delta_bare}} in the anchor configuration, and the movement is composition of
world states rather than an agent working around the rule: holding the simulator-recorded world fixed
leaves {{CLAIM:world_residual_coarse}} at {{CLAIM:world_coverage_coarse}} coverage and
{{CLAIM:world_residual_finest}} at the finest stratification. An honest agent is enough to break the
statistic, and it breaks it most where the intervention worked best. On one configuration the whole
apparent gain is composition, {{CLAIM:b12_cond_delta_bare}} conditional falling to
{{CLAIM:b12_uncond_delta_bare}} over a denominator fixed by design. Moving the antecedent to world
state is tested here and fails. Report the conditioning variable's prevalence in both arms beside
every conformance rate, and log the world state a self-reported antecedent refers to.
