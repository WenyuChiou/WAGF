# Handoff: ICLR 2027 WAGF submission

Updated 2026-08-05 after a fresh Figure 1 generation round based on the
rendered architecture figures of ReAct, Reflexion, AutoGen, SWE-agent, and
AgentSpec, followed by independent visual review, a plain-language and
academic-writing audit, and an official MiKTeX typeset build of the active
manuscript.

## Read this first

This file is the current handoff for the ICLR package. The file
`SUBMISSION_2026\TAE\HANDOVER.md` is historical TAE material and must not be
used as the current venue or figure instruction.

The single active manuscript is `paper\manuscript.tex`.

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
25.12: `paper\manuscript.pdf` is 9 pages total, with the final page containing
references only. The build has no undefined citations/references and no
overfull boxes. The title produces two non-fatal underfull hbox warnings; the
body produces non-fatal underfull vbox warnings.

## Manuscript and evidence status

Figures 2--4 are deterministic evidence outputs copied from the frozen
historical evidence package. The current ICLR draft preserves the existing
evidence boundary; the historical TAE package is untouched.

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

An independent adversarial CS reviewer rejected four fresh candidates for
record-path or endpoint ambiguity, then approved Candidate F's image-level
routes at full size, thumbnail size, and grayscale. The remaining caption
synchronization is now applied in `paper\manuscript.tex`. The earlier reviewer
requests for caption denominator clarity, Figure 1's scarcity-condition
abstraction, exact reweighting support rules, and claim softening are also in
that file. No new experiment was invented or run.

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
that limit; this PDF has 8 pages of main text plus one references-only page.
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
