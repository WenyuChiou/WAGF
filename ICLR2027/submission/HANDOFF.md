# Handoff: ICLR 2027 WAGF submission

Updated 2026-08-05 after a full Figure 1 reset based on published agent-paper
architecture figures and adversarial route review.

## Read this first

This file is the current handoff for the ICLR package. The file
`SUBMISSION_2026\TAE\HANDOVER.md` is historical TAE material and must not be
used as the current venue or figure instruction.

The single active manuscript is:
`paper\manuscript.tex`

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
| Figure 1 generated asset | `figures\assets\figure1_architecture_compact_v1.png` |
| Figure 1 staging builder | `source\figure1_agent_paper.py` |
| Figure 1 builder | `source\figure1_overlay.py` (compatibility entry point) |
| Figure 1 manifest | `figures\active\figure1_concept.json` |
| Figure 1 geometry report | `checks\figure1_geometry_report.json` |
| Design contract | `FIGURE1_DESIGN.md` |
| Design comparison audit | `FIGURE1_DESIGN_AUDIT.md` |
| External-paper style audit | `..\FIGURE_STYLE_AUDIT.md` |
| Agent-paper redesign contract | `AGENT_PAPER_FIGURE_REDESIGN.md` |
| Figure 1 reset design contract | `AGENT_ARCHITECTURE_FIGURE_RESET.md` |
| Static check report | `checks\manuscript_static_report.json` |
| Evidence-boundary report | `checks\evidence_boundary_report.json` |
| Reproducibility audit | `checks\reproducibility\reproducibility_report.md` |

`figures\active\` is the only directory whose rendered files may be included
by `paper\manuscript.tex`. `figures\candidates\` contains non-active
alternatives. `figures\assets\figure1_architecture_compact_v1.png` is the
reviewed source asset for the active generated Figure 1. Legacy and
intermediate versions are under `figures\candidates\legacy\figure1\` and
`figures\candidates\architecture-reset-round\`.

## Figure 1 status

Figure 1 is a conceptual agent/evaluation diagram, not a quantitative result.
It uses an AgentSpec/SWE-agent-style interface insertion point: an `Agent`
contains a response with `action` and `condition`, the `Validator` sits before
`Environment`, and the accepted decision enters `Decision log`. The same
condition takes a separate amber route directly to `filter`, while logged
records enter the filter through `records` and feed `conditional rate`.

The active composition is the compact v1 architecture generated after
auditing ReAct, Reflexion, AutoGen, AgentSpec, SWE-agent, Voyager, and
Magentic-One. It uses a single warm-gray canvas with local semantic nodes,
keeps the response inside the Agent boundary, aligns the accepted-decision
arrow with `Decision log`, and routes the shared condition directly to
`filter`. It also uses short relation labels, black primary routes, a small
LLM cue, semantic flat fills, and a top dashed `observation` return lane. The earlier
dashboard-like and D-v3 compositions are historical and preserved under
`figures\candidates\legacy\figure1\` and
`figures\candidates\architecture-reset-round\`.

The generated asset (compact v1, with `proposed action`, an aligned
`accepted decision` arrow, direct condition-to-filter routing, and a
non-crossing observation loop) is visually reviewed at full size, paper-width
preview, grayscale, and thumbnail size.
The geometry check reports `PASS_MANUAL_VISUAL_REVIEW_REQUIRED`: image
dimensions and short labels are checked automatically, while pixel-level
text/arrow separation is reviewed manually. The remaining delivery gate is
print-width inspection in the official typeset PDF.

The Introduction states the measurement risk before the irrigation example,
defines `agent-written condition` and `conditional rate` in plain language, and
places Figure 1 immediately after the contribution summary. The caption maps
the action, condition, Validator, Environment, accepted decision, Decision log,
filter, and conditional rate to the upper execution and lower measurement
paths, and states the missing-first-attempt boundary.

Use the active generated image and print preview for inspection:
`figures\active\figure1_concept.png`
`figures\active\figure1_concept_print.png`

Do not add paragraph text inside the figure. Put explanations in the caption
or body text. If Figure 1 is changed, regenerate it and rerun both the
geometry and manuscript static checks.

## Manuscript and evidence status

Figures 2--4 are deterministic evidence outputs copied from the frozen
historical evidence package. The current ICLR draft preserves the existing
evidence boundary; the historical TAE package is untouched.

The static manuscript check, Figure 1 geometry check, and evidence-boundary
check pass in the current package. The WAGF reproducibility audit remains RED
for three historic smoke manifests marked `git_dirty=true`; this is a
provenance limitation, not a failed numerical crosscheck. Do not describe the
historic corpus as bitwise reproducible.

## Known blocker

The Windows environment has no `pdflatex`, `xelatex`, `lualatex`, `tectonic`,
or `bibtex` executable, and the installed WSL distribution has no TeX engine.
The official ICLR PDF build, page-count check, overfull-box check, and final
print-size inspection are therefore still pending. Do not call the package
fully upload-ready until a real TeX build passes.

## Next agent's order of work

1. Decide whether to add the minimum controlled validation needed for the ICLR
   generality claim; do not silently broaden the claim without evidence.
2. Rewrite the title, abstract, introduction, and measurement-model section
   around the general selection-variable problem, with WAGF as the testbed.
3. Build with the official ICLR style in a TeX-enabled environment and inspect
   the PDF at 100% and print size for page count, overfull boxes, clipped
   captions, and anonymity leaks.
4. Re-run the frozen evidence inventory and all table/figure crosschecks in
   this release directory; do not modify the historical TAE snapshot.
5. Complete ICLR author metadata, profile, reciprocal-review, quota, and live
   dual-submission checks only at submission time.
