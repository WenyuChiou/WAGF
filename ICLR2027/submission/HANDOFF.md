# Handoff: ICLR 2027 WAGF submission

Updated 2026-08-08 after the figure-role/example-balance audit, WAGF material
inventory, refreshed CS-agent literature positioning, a plain-language and
academic-writing audit, and an official MiKTeX typeset build of the active
manuscript. The current pass also corrects the executed denominator-gap range,
aligns bibliography aliases with the manuscript, and adds an ICLR page gate.

## Read this first

This file is the current handoff for the ICLR package. The file
`SUBMISSION_2026\TAE\HANDOVER.md` is historical TAE material and must not be
used as the current venue or figure instruction.

The single active manuscript is `paper\manuscript.tex`.

The current operational fence is `ICLR2027\LIVE_STATE.md`. The real-LLM
batch that produced `firstattempt_gov_seed42` through `seed46` has finished,
but those five governed-only runs remain unreleased: their provenance audit is
RED and no matched no-validator first-attempt arm is present. Do not edit
`broker\` or `SUBMISSION_2026\TAE\runs\`, and do not use those runs in the
manuscript until the operational handoff releases their provenance. The active
package below continues to use only the frozen evidence and the canonical Flood
contrast CSV. See `EXPERIMENT_AUDIT.md` for the exact boundary.

Cloud's additional experiments remain outside this release. The first-attempt
branch is now inventoried, but its governed-only diagnostics, traces, and new
fields must not enter the manuscript, figures, tables, or claims until a
matching no-validator arm and clean provenance are released.

The current strategic direction is to present WAGF as an empirical testbed for
a general measurement-validity problem in governed LLM-agent evaluation:

> An agent-authored condition can be both a runtime governance input and an
> evaluation selection variable. When these roles are coupled, governance can
> change the population counted by a conditional rate.

The manuscript does not claim deception, causality, universal agent behavior,
or a within-world reporting revision. A controlled validation experiment would
strengthen ICLR generality; no new experiment result has yet been integrated
in this package.

For the Introduction, the framing decision is to omit the internal framework
name and present the coupled water-resource simulation as the empirical
example. The motivation should lead with agent--environment interaction and
the measurement-validity problem, not with the name of the implementation.
Later method and reproducibility sections may retain the framework name where
provenance requires it.

The current figure hierarchy is deliberate: Figure 1 is a domain-neutral
conceptual bridge; Figures 2--4 are irrigation-led rule, coupled-world, and
denominator analyses; Flood appears only in Table 3 as a secondary boundary
check. Do not add a Flood mechanism panel unless the study design gains a
matched mechanism question and evidence.

The release gate remains open until the current source passes the static,
evidence-boundary, rendered-page, and bounded code-review checks together. A
passing local package check does not close the historical provenance RED state
or the submission-time ICLR metadata and policy checks.

## Canonical package layout

| What to use | Location |
| --- | --- |
| Anonymous manuscript | `paper\manuscript.tex` |
| Bibliography | `paper\references.bib` |
| Figures cited by TeX | `figures\active\` |
| Figure 1 generated asset | `figures\assets\figure1_architecture_agentpaper_shared_condition_v6_retry_return.png` |
| Figure 1 staging builder | `source\figure1_agent_paper.py` |
| Figure 1 manifest | `figures\active\figure1_concept.json` |
| Figure 3 cross-testbed builder | `source\cross_testbed_summary.py` |
| Cross-testbed source summary | `supplement\cross_testbed_summary.csv` |
| Enforcement-pressure source | `supplement\enforcement_pressure_source.json` |
| Cross-testbed table fragment (paper Table 3) | `supplement\table2_cross_testbed.tex` |
| Design contract | `FIGURE1_DESIGN.md` |
| Reset rationale | `AGENT_ARCHITECTURE_FIGURE_RESET.md` |
| External-paper style audit | `..\FIGURE_STYLE_AUDIT.md` |
| Static check report | `checks\manuscript_static_report.json` |
| Evidence-boundary report | `checks\evidence_boundary_report.json` |
| Reproducibility audit | `checks\reproducibility\reproducibility_report.md` |
| Paper, figure, and example-role audit | `PAPER_AUDIT.md` |
| WAGF material and code inventory | `WAGF_INVENTORY.md` |
| Literature and contribution positioning | `LITERATURE_POSITIONING_AUDIT.md` |
| Water--human spinout boundary | `WATER_HUMAN_POSITIONING.md` |
| Reference verification audit | `REFERENCE_AUDIT.md` |
| First-attempt provenance audit | `EXPERIMENT_AUDIT.md` |
| Irrigation coupling audit | `COUPLING_AUDIT.md` |

`figures\active\` is the only directory whose rendered files may be included
by `paper\manuscript.tex`. `figures\candidates\` contains non-active
alternatives. Older v3 and D-v3 assets are historical and are not active.

## Figure 1 status

The active Figure 1 is the generated shared-condition composition
`figures\assets\figure1_architecture_agentpaper_shared_condition_v6_retry_return.png`. It
uses:

- an Agent response card with an AI cue and `action`/`condition` fields;
- a compact Validator gate with explicit black and amber input ports;
- a direct accepted-action path to Environment, a retry/default-action branch,
  and a separate final-record path to Decision log;
- a lower Counted records path that receives black `records` from Decision log
  and the amber `condition` route separately before feeding Conditional rate.

The image uses black borders/arrows, flat colored fills, and small functional
icons. The fills are semantic: blue is agent output, orange is runtime
validation, green is the environment, violet is the measurement path, and
amber is the shared agent-written condition; the warm light-gray background is
neutral. The retry/default-action branch is shown because the primary
statistics count the action that executed. The frozen corpus does not preserve
the first response before a retry, and the caption states this boundary.

The generated source and active/print copies are byte-identical after staging.
The current visual gate includes full-size, paper-width, thumbnail, grayscale,
and adversarial inspection. The official typeset PDF gate passes with MiKTeX
25.12: `paper\manuscript.pdf` is 11 pages total, with 9 pages of main text and
2 pages of references, within the current nine-page main-text limit. The build has no undefined citations/references and no
overfull boxes. The title and page fill produce non-fatal underfull hbox/vbox
warnings. Rendered checks of pages containing Figure 1, Table 3, Figures 3--4
found no clipping or overlap.

## Manuscript and evidence status

Figure 2 and Figure 3 are deterministic evidence outputs copied from the
frozen historical evidence package, with Figure 3 regenerated as a three-panel
primary irrigation mechanism figure in reading order. Figure 4 is the
executed-action denominator-gap plot generated by
`ICLR2027\fig_denominator_gap.py`. The active cross-testbed builder no longer
promotes Flood to a same-status mechanism panel. The current ICLR draft
preserves the existing evidence boundary; the historical TAE package is
untouched.

The cross-testbed summary contains five irrigation and nine Flood
configurations. Flood spans -3.66 to +6.24 percentage points, while irrigation
spans +21.27 to +47.53 percentage points. The comparison is a high-threat-
appraisal contrast: irrigation stores WSA_LABEL and Flood stores TP_LABEL, and
both use the high/very-high labels from the shared five-level appraisal
instrument. These are the same per-run-mean contrast, but Flood is not
seed-paired with irrigation and has a different action ontology and no
action-to-environment feedback. Table 3 is therefore a secondary descriptive
boundary check, not a causal comparison, dose-response estimate, or
mechanism-transfer test. Flood governance rejects 0--0.64% of proposed actions,
compared with 28--63% in irrigation. The
Flood gemma3:4b
cell excludes one divergent governed run, leaving four governed versus five
no-validator runs; including it changes that cell from +0.35 to -1.16
percentage points. The reported enforcement-pressure ranges are pinned in
`supplement\enforcement_pressure_source.json` and are not recomputed from the
Flood contrast CSV.

The static manuscript and evidence-boundary checks pass when run against the
current source. The WAGF reproducibility audit remains RED for three historic
smoke manifests marked `git_dirty=true`; this is a provenance limitation, not
a failed numerical crosscheck. Do not describe the historic corpus as bitwise
reproducible.

The 2026-08-08 content polish pass changed prose, captions, and release notes
only. A subsequent delivery pass added `\hypersetup{hidelinks}` to remove
printed hyperlink borders from citations and cross-references; it did not
regenerate a figure or add the unreleased first-attempt result. Figure 1
remains the reviewed generated conceptual asset, and Figures 2--4 remain
deterministic evidence displays. When Cloud releases the additional
experiments, reconcile their provenance against LIVE_STATE.md before changing
any number, caption, figure, table, or claim.

## Academic-writing and reviewer audit

The active manuscript now uses a why-first introduction, a model-fidelity
framing, and an executed-action primary reading, with
an explicit 80/100 decision example, and plain-language definitions for the
scarcity selection condition, all-decision rate, coverage, and direct
standardization. The methods now state the frozen inference procedure: a
two-sided one-sample $t$-test on per-seed off-minus-on deltas, 95\% $t$
intervals with $n-1$ degrees of freedom, and cellwise unadjusted $p$-values.
The latest LIVE_STATE 4g--4j pass also makes the on/off contrast the object
of study rather than an attempted governance-effect estimator, explains the
Rosenbaum connection in plain language, labels the year-1 comparison as a
placebo check, and uses the executed-action conclusion. Necessary boundaries
remain once in the relevant sections; repeated defensive causal language was
removed.

### Panel D decision

The earlier Panel D proposal put irrigation and Flood contrasts on one shared
axis as a visual control. That comparison was easy to misread as a co-primary
mechanism result: Flood uses a different action ontology, no action-to-
environment feedback, a different appraisal field, and different seed
matching. The panel is therefore not active. Flood remains in Table 3 as a
secondary descriptive cross-testbed boundary check, where the caption states the
shared measure and the non-comparability boundaries.

The generated Figure 1 routes were inspected at full size, paper width,
thumbnail size, and grayscale. A fresh bounded staged-diff CS reviewer then
approved the executed-primary separation, the irrigation-primary/Flood-
table-only hierarchy, the retired Panel D decision, and the corrected evidence
boundary check. The earlier reviewer requests for caption denominator clarity,
Figure 1's scarcity-condition abstraction, exact reweighting support rules,
and claim softening are applied in `paper\manuscript.tex`. No new experiment
was invented or run.

The rule semantics are explicit in the manuscript. The block is the testbed
policy branch `high_threat_high_cope_no_increase`: it applies to an increase
proposal only when both the agent-reported water-scarcity and coping-capacity
labels are high or very high. High scarcity alone is a warning, not a block.
This policy is not presented as a normative claim; it is the mechanism that
lets the same agent-authored fields enter both enforcement and the conditional
denominator.

## Official TeX build

MiKTeX 25.12 is installed at
`C:\Users\wenyu\AppData\Local\Programs\MiKTeX\miktex\bin\x64`.
From `paper\`, the verified build is two `pdflatex` runs after the existing
`bibtex manuscript` pass, with `TEXINPUTS` and `BSTINPUTS` pointing to
`source\iclr_style\iclr2027`. The static checker now discovers this per-user
MiKTeX installation even when the shell PATH has not been refreshed.

## Remaining release checks

The TeX and PDF checks are complete. The package is not yet a submission
because OpenReview author metadata, author profiles and reciprocal-review
requirements, final anonymity checks, and the live dual-submission decision
still belong to the actual submission window. The official ICLR 2027 author
guidelines allow at most 9 pages of main text and exclude the bibliography from
that limit; this PDF has 9 pages of main text plus 2 reference pages.
The current official ICLR 2027 author guidelines list the abstract deadline as
Sep 11, 2026 AOE and the paper deadline as Sep 16, 2026 AOE. Recheck the live
author page at submission time; the older dates in historical TAE handover
notes and the older planned dates still shown on the Call for Papers page are
superseded by the Author Guidelines.

## Next agent's order of work

1. Complete the final venue and dual-submission checks at submission time.
2. Re-run the frozen evidence inventory and all table/figure crosschecks; do
   not modify the historical TAE snapshot.
3. Decide whether the ICLR generality claim needs a minimum controlled
   validation experiment; do not broaden the claim without evidence.
4. Complete ICLR author metadata, profile, reciprocal-review, and quota checks
   only at submission time.

## Figure roles for the next agent

1. Figure 1 is the conceptual answer to where the agent-written condition is
   reused. It is not a data plot and must not be read as saying that high
   scarcity alone is blocked. Its retry/default-action branch explains why the
   executed action is the primary action reading.
2. Figure 2 is the rule-layer answer: it separates self-report-conditioned
   validator rules from simulator-recorded feasibility rules.
3. Figure 3 is the primary mechanism/evidence answer. Panels A--B use the
   anchor irrigation cell; panel C compares the all-decision and never-retried
   readings across the five irrigation configurations. Flood stays in Table 3
   and the cross-testbed summary as a secondary boundary check.
4. Figure 4 is the denominator answer under the executed-action reading. It
   remains irrigation-only because the Flood artifacts do not provide the
   coupled action-to-environment setting needed for that analysis.

The active generated Figure 1 is the v6 retry-return asset. It was regenerated
from the reviewed shared-condition composition and visually checked at full
size, paper width, thumbnail, and grayscale. The retry arrow now terminates at
Agent response; the previous detached retry pill is retired. Keep the retry
branch subordinate to the main propose--validate--accept flow; do not add a
data-bearing chart to this conceptual figure. The full figure/table hierarchy
and the irrigation-primary/Flood-secondary balance are recorded in
`PAPER_AUDIT.md`.
