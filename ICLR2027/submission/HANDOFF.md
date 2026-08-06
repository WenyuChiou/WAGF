# Handoff: ICLR 2027 WAGF submission

Updated 2026-08-06 after a cross-testbed evidence round and a fresh Figure 1
generation review based on the rendered architecture figures of ReAct,
Reflexion, AutoGen, SWE-agent, and AgentSpec, followed by independent visual
review, a plain-language and academic-writing audit, and an official MiKTeX
typeset build of the active manuscript.

## Read this first

This file is the current handoff for the ICLR package. The file
`SUBMISSION_2026\TAE\HANDOVER.md` is historical TAE material and must not be
used as the current venue or figure instruction.

The single active manuscript is `paper\manuscript.tex`.

The current operational fence is `ICLR2027\LIVE_STATE.md`: an 11-hour
real-LLM experiment is running. Do not edit `broker\`, touch
`SUBMISSION_2026\TAE\runs\`, start another GPU job, or use the live run's
answer in the manuscript until the operational handoff explicitly releases
it. The package below uses only the frozen evidence and the canonical Flood
contrast CSV.

The current strategic direction is to present WAGF as an empirical testbed for
a general measurement-validity problem in governed LLM-agent evaluation:

> An agent-authored condition can be both a runtime governance input and an
> evaluation selection variable. When these roles are coupled, governance can
> change the population counted by a conditional rate.

The manuscript does not claim deception, causality, universal agent behavior,
or a within-world reporting revision. A controlled validation experiment would
strengthen ICLR generality; no new experiment has yet been run in this package.

## Canonical package layout

| What to use | Location |
| --- | --- |
| Anonymous manuscript | `paper\manuscript.tex` |
| Bibliography | `paper\references.bib` |
| Figures cited by TeX | `figures\active\` |
| Figure 1 generated asset | `figures\assets\figure1_architecture_agentpaper_shared_condition_v4.png` |
| Figure 1 staging builder | `source\figure1_agent_paper.py` |
| Figure 1 manifest | `figures\active\figure1_concept.json` |
| Figure 3 cross-testbed builder | `source\cross_testbed_summary.py` |
| Cross-testbed source summary | `supplement\cross_testbed_summary.csv` |
| Enforcement-pressure source | `supplement\enforcement_pressure_source.json` |
| Cross-testbed Table 2 fragment | `supplement\table2_cross_testbed.tex` |
| Design contract | `FIGURE1_DESIGN.md` |
| Reset rationale | `AGENT_ARCHITECTURE_FIGURE_RESET.md` |
| External-paper style audit | `..\FIGURE_STYLE_AUDIT.md` |
| Static check report | `checks\manuscript_static_report.json` |
| Evidence-boundary report | `checks\evidence_boundary_report.json` |
| Reproducibility audit | `checks\reproducibility\reproducibility_report.md` |

`figures\active\` is the only directory whose rendered files may be included
by `paper\manuscript.tex`. `figures\candidates\` contains non-active
alternatives. Older v3 and D-v3 assets are historical and are not active.

## Figure 1 status

The active Figure 1 is the generated shared-condition composition
`figures\assets\figure1_architecture_agentpaper_shared_condition_v4.png`. It
uses:

- an Agent response card with an AI cue and `action`/`condition` fields;
- a compact Validator gate with explicit black and amber input ports;
- a direct accepted-action path to Environment and a separate final-record
  path to Decision log;
- a lower Counted records path that receives black `records` from Decision log
  and the amber `condition` route separately before feeding Conditional rate.

The image uses black borders/arrows, flat colored fills, and small functional
icons. The fills are semantic: blue is agent output, orange is runtime
validation, green is the environment, violet is the measurement path, and
amber is the shared agent-written condition; the warm light-gray background is
neutral. Observation and retry paths are intentionally omitted for clarity;
the frozen corpus does not preserve the first response before a retry, and the
caption states this boundary.

The generated source and active/print copies are byte-identical after staging.
The current visual gate includes full-size, paper-width, thumbnail, grayscale,
and adversarial inspection. The official typeset PDF gate passes with MiKTeX
25.12: `paper\manuscript.pdf` is 10 pages total, with 8 pages of main text and
2 pages of references. The build has no undefined citations/references and no
overfull boxes. The title and page fill produce non-fatal underfull hbox/vbox
warnings. Rendered checks of pages containing Figure 1, Table 2, Figures 3--4
found no clipping or overlap.

## Manuscript and evidence status

Figure 2 and Figure 4 are deterministic evidence outputs copied from the
frozen historical evidence package. Figure 3 is now a three-panel primary
irrigation mechanism figure in reading order; the active builder no longer
promotes Flood to a same-status panel. The current ICLR draft preserves the
existing evidence boundary; the historical TAE package is untouched.

The cross-testbed summary contains five irrigation and nine Flood
configurations. Flood spans -3.66 to +6.24 percentage points, while irrigation
spans +21.27 to +47.53 percentage points. The comparison is a high-threat-
appraisal contrast: irrigation stores WSA_LABEL and Flood stores TP_LABEL, and
both use the high/very-high labels from the shared five-level appraisal
instrument. These are the same per-run-mean contrast, but Flood is not
seed-paired with irrigation and has a different action ontology and no
action-to-environment feedback. Table 2 is therefore a secondary descriptive
boundary check, not a causal comparison or a mechanism-transfer test. The
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

## Academic-writing and reviewer audit

The active manuscript now uses a why-first introduction, a 242-word abstract
(raw-token count before LaTeX rendering),
an explicit 80/100 decision example, and plain-language definitions for the
scarcity selection condition, all-decision rate, coverage, and direct
standardization. The methods now state the frozen inference procedure: a
two-sided one-sample $t$-test on per-seed off-minus-on deltas, 95\% $t$
intervals with $n-1$ degrees of freedom, and cellwise unadjusted $p$-values.

An independent adversarial CS reviewer rejected four fresh generated Figure 1
candidates for record-path or endpoint ambiguity, then approved Candidate F's
image-level routes at full size, thumbnail size, and grayscale. The remaining
caption synchronization is now applied in `paper\manuscript.tex`. The earlier
reviewer requests for caption denominator clarity, Figure 1's scarcity-
condition abstraction, exact reweighting support rules, and claim softening
are also in that file. No new experiment was invented or run.

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
that limit; this PDF has 8 pages of main text plus 2 reference pages.
The abstract deadline is Sep 18, 2026 AOE and the paper deadline is Sep 25,
2026 AOE.

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
   scarcity alone is blocked.
2. Figure 2 is the rule-layer answer: it separates self-report-conditioned
   validator rules from simulator-recorded feasibility rules.
3. Figure 3 is the primary mechanism/evidence answer. Panels A--C show why
   the anchor irrigation contrast is descriptive. Flood stays in Table 2 and
   the cross-testbed summary as a secondary boundary check.
4. Figure 4 is the denominator answer. It remains irrigation-only because the
   Flood artifacts do not provide the coupled action-to-environment setting
   needed for that analysis.

Do not replace the active generated Figure 1 with the newly generated
candidates from 2026-08-06. They were rejected because their amber selection
routes had ambiguous arrow origins or endpoints at paper size. The reviewed
shared-condition v4 asset remains the active Figure 1.
