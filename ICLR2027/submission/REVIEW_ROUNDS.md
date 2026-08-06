# Review rounds

## Round 1: academic-writing and release pass

The manuscript was reorganized as why -> example -> mechanism -> estimands ->
reporting protocol. Technical terms are introduced in plain language before
the equations. Figure 1 is introduced in the Introduction, while Figures 2--4
carry quantitative evidence. The image generator is restricted to the
non-data-bearing icon base; exact labels and arrows are deterministic.

## Round 2: adversarial four-lens review

An independent read-only reviewer checked the current package as:

- a CS/AI-agent reviewer;
- an academic-writing reviewer;
- a methods/evidence skeptic; and
- a figure reviewer.

### Findings fixed without new experiments

- The scarcity marginal is now explicitly separated from the full conjunction,
  including the frozen anchor values `25.46%`, `68.61%`, and `+43.15 pp`.
- The old `agent-reported conjunction +45.73 pp` wording is removed; `+45.73 pp`
  is named as the scarcity marginal.
- Flood is now described as portability evidence only. Irrigation is the
  seed-paired inferential setting.
- The retry percentage is scoped to the anchor irrigation cell.
- The world-state table distinguishes governed/no-validator coverage, pooled
  direct-standardization residuals, and per-seed diagnostics with intervals.
- The seed-level estimand is explicit in the equations.
- Figure 1's red and purple routes now use separate lanes. The geometry checker
  additionally tests their centerline intersection.
- The Agent -> World arrow now says `accepted action`; the Agent card says
  `action + condition`.
- AI-use, ethics, and reproducibility statements follow the official ICLR style
  order before references.

### Findings that remain blocked or require a future decision

- The official ICLR TeX build has not run because no TeX engine is installed in
  Windows or the available WSL distribution. Page count, overfull boxes,
  caption clipping, embedded fonts, and final PDF anonymity remain unverified.
- The flood portability evidence remains limited by its frozen prompt/schema and
  seed-alignment provenance. Stronger cross-testbed inference would require new
  controlled runs; the current manuscript does not make that claim.
- Complete historic run-level reproducibility remains limited by absent/dirty
  provenance fields. The supplement discloses this boundary rather than calling
  the package bitwise reproducible.
- The WAGF reproducibility checker surveyed three manifests under the historical
  TAE run tree and returned RED because all three recorded `git_dirty=true`.
  This is preserved in `checks\reproducibility\reproducibility_report.md`.
- A broader claim across agent frameworks would require evidence outside WAGF;
  the current contribution is deliberately a bounded measurement-validity risk
  and reporting protocol.

## Round 3: Figure 1 structural and visual audit

The previous four-card composition was compared with the WAGF architecture and
feedback-loop figures, AgentSpec, AgentBench, and NeMo Guardrails. The main
problem was hierarchy rather than geometry: `AGENT`, `REPORT`, `WORLD`, and
`METRIC` had equal visual weight, so the shared agent-written condition did not
read as the paper's central object.

The figure was redesigned as one `AGENT OUTPUT` region, one `GOVERNANCE` gate,
and two consequences (`WORLD` and `METRIC`). The amber condition now has two
explicit routes (`checks` and `selects`), while accepted action and future
context use a separate green path. The blocked route is dashed and labelled
`blocked`, keeping the missing first-attempt report a visible caveat rather
than an implied measured result.

The regenerated figure has 19 short deterministic labels, zero text-box
overlaps, and zero declared route intersections. The icon base contains no
paper-facing text. No new experiment was required; the change is a
representation and caption-alignment change.

## Round 4: TAE/agent-paper style correction

The author noted that the Round 3 version still looked like a UI infographic:
colored arrows and white label pills made each item look like an independent
card. The figure was restyled to match the earlier TAE schematic and compact
agent-framework diagrams:

- all semantic arrows are black;
- labels are rendered directly on pale nodes or in open whitespace;
- white label backgrounds and nested icon cards are removed;
- the shared condition is an explicit central node;
- the blocked path terminates at a small conceptual `Retry` node;
- the environment and evaluation consequences remain separate.

The current regenerated figure has 24 short deterministic labels, zero
text-box overlaps, and zero declared route intersections. The current visual
contract is in `FIGURE1_DESIGN.md`; the historical 19-label version above is
kept as review history only.

## Round 5: evidence-based module-graph redesign

The author rejected the Round 4 icon-card composition as still too close to an
infographic. A fresh comparison of ReAct, Reflexion, AgentSpec, AutoGen, and
the historical TAE schematic showed that the stronger common pattern is a
small module graph whose arrows carry the explanation. Figure 1 was therefore
redrawn from scratch:

- the active figure no longer uses the generated icon strip;
- the source draws small deterministic vector symbols only as subordinate
  cues;
- the figure uses one Agent response frame, one Shared condition, and four
  downstream operations;
- all semantic routes are black, with only feedback/retry routes dashed;
- the only strong highlight is the shared condition;
- labels are direct-to-canvas and no white label backgrounds are used.

The current output has 21 labels, zero text-box overlaps, and zero declared
route intersections. The evidence and caption boundaries are unchanged.

## Round 6: paper-figure geometry and fill audit

The Round 5 output was inspected at full size and at the print-width preview,
and as a generated thumbnail. One awkward route label was removed because it
sat too close to the transparent Agent boundary, and the Measurement title
was compacted to preserve icon-to-text and text-to-border spacing.

The final visual contract is now stricter than “no white label pills”: the
white canvas is the only white surface. Every paper-facing module and
ownership region uses a semantic pale fill. The Agent response is bounded by a
dashed outline; the Shared field, Governance, Evaluation, and Environment
regions are pale and borderless. The regenerated output retains black primary
arrows, dashed feedback and retry routes, 25 short labels, zero text-box
overlaps, and zero declared route intersections.

## Round 7: reference-paper hierarchy audit

The actual reference pages were inspected rather than inferred from their
titles: Reflexion uses an ownership boundary and compact labeled modules;
AgentSpec uses short functional labels and one enforcement branch; ReAct uses
content highlights inside a compact trace; and AutoGen separates ownership
layers from message flow. The active Figure 1 follows the first two grammars
because its claim is a mechanism, not a trajectory result or a framework
inventory.

One remaining hierarchy issue was found: the agent-written condition and the
shared condition had the same amber fill. The agent-written field is now
neutral gray, while the shared condition remains the only strong highlight.
This makes the reuse relationship visible without adding another label. The
active source, manifest, and print/thumbnail previews were regenerated after
the change.

## Round 8: density, palette, and introduction alignment

The author added a hard constraint that Figure 1 should not leave large empty
white areas. The then-active source used five moderately pale, borderless
ownership regions: Agent response, Shared field, Governance, Evaluation, and
Environment. This increases visual density without adding cards, decorative
text, or extra arrows; white remains only the canvas and the breathing room
needed to keep routes and labels separate. The shared condition remains the
only strong highlight, and all semantic arrows remain black.

The Introduction was also tightened around the same visual claim. It now
states the measurement risk before the irrigation example, defines an
agent-written condition and a conditional rate in plain language, introduces
Figure 1 before the Evaluation Setting, and adds a short roadmap. The sentence
describing simulator state was rewritten to avoid implying that a logged state
is automatically unaffected. No numerical claim or evidence boundary changed;
the new figure and manuscript checks still pass.

## Round 9: terminology and readability audit

The prose was checked again for first-use explanations and sentence length.
`Estimands` was removed from the visible subsection title and replaced with
`quantities we compare`; the text now explains the fixed-denominator and
conditional quantities in direct language. `Construct validity`, simulator
state, the conditional rate, and the agent-written condition are either
defined at first use or explained in the surrounding sentence. A parser-based
prose audit still reports repeated LaTeX figure commands, the `.bib` file as
an unsupported prose artifact, and repeated limitation phrases; these are
tooling/required-terminology findings rather than prose sentences. The
human-readable manuscript, static check, evidence-boundary check, and figure
geometry check show no actionable readability or scope blocker.

## Round 10: replacement with a compact split-flow graph

The previous five-region layout was retired rather than treated as the final
style. The actual AgentSpec Figure 1, Reflexion Figure 2, AutoGen Figure 1,
and ReAct Figure 1 were compared again. Their common paper grammar is a small
number of semantic modules, a single dominant data/control path, short labels,
and color used to distinguish roles rather than to fill every region.

Figure 1 was therefore replaced with a split-flow composition: one response
packet inside one Agent boundary; a decision-shaped Validator; an external
World state; and a lower Record filter leading to the Conditional rate. The
same condition appears once and forks at a small junction, so the reuse claim
is visible without duplicating a Shared condition card. A light neutral canvas
and two lightly tinted lanes reduce unused white space while remaining
functional grouping rather than ownership panels. The new output has 21 labels,
zero text-box overlaps, and
zero declared route intersections at both full and thumbnail inspection.

## Round 11: replacement with a compact agent-paper rail graph

The Round 10 split-flow output still read as a wide pastel infographic because
its runtime and evaluation lanes were large background panels. A fresh audit of
the actual AgentSpec, Reflexion, AutoGen, and ReAct figures showed a tighter
grammar: a small number of colored semantic modules, short labels, direct
black routes, and icons subordinate to the labels.

The active source was therefore replaced with a compact rail graph. The agent
response contains the action and condition; the action travels through the
runtime rail to the validator and world state, while the single condition
forks to the record filter and conditional rate. The feedback route is retained
as a thin dashed path, but the retry endpoint is omitted because the frozen
corpus lacks the first response before a retry. The output has 20 labels, zero
text-box overlaps, and zero declared route intersections at full and thumbnail
inspection.

## Round 12: complete generated composition and reduced-white-space audit

The Round 11 vector rail graph was retired after visual review because its
labels and rails still read like a hand-built dashboard at paper width. Figure
1 is now a complete generated composition: the response document, shield,
database, funnel, globe, gauge, borders, fills, arrows, and labels are produced
in one coherent image-generation pass. The final rendering uses near-black
outlines, restrained fills, a uniform cool-gray canvas, and no large white
cards or bottom white strip.

The semantic graph was preserved and made explicit: the agent-written
condition branches to Validator and Record filter; Recorded decisions has a
separate arrow into Record filter; the accepted action changes World state;
the dashed future-context route returns outside the modules. At that historical
stage, `figures/assets/figure1_generated_full_final.png` was staged through the
normal builder. That asset is now superseded by D-v3; the historical checks
and wording below do not define the active source. Pixel-level text/arrow
separation remained a manual visual review item because the final artwork was
a generated raster.

## Round 13: reset from external agent-paper figures

The Round 12 composition was rejected as too close to an illustrated
dashboard. The redesign returned to the visual grammar of published agent
papers: one observable response, one compact execution loop, short semantic
modules, and arrows that state the relation. ReAct, Reflexion, AutoGen, and
AgentSpec were reviewed as primary references. The new figure has an upper
execution lane and a lower measurement lane. A small LLM chip marks the AI
producer; the condition is highlighted once and branches separately to
Validator and Filter.

Three candidates were generated. Candidate A was rejected for a misplaced
`rule input` label; candidate C was rejected for a visually heavy nested
boundary. Candidate D was selected after full-size and thumbnail review. It
keeps the process semantics, replaces the previous large robot/globe icons
with a small LLM chip and reservoir cue, and preserves clean arrow endpoints
with no text overlap. The manuscript caption, Figure 1 builder manifest,
design contract, source-of-truth, handoff, and regeneration note were updated
together. Official print-width PDF review remains open because the current
environment has no TeX engine.

## Current verdict

Content and figure static checks pass after the adversarial fixes. The package
is not yet upload-ready until the official ICLR TeX build and rendered-PDF
inspection pass.

## Round 14: explicit Agent-to-response ownership

Candidate D was visually clean but relied on adjacency to imply that the
agent produced the response. That is too weak for a mechanism figure. The
generated candidate E adds one short `emits` arrow from `Agent (LLM)` to
`response` and preserves every other route and label. Full-size and thumbnail
inspection show a clear endpoint, no overlap, and no new crossing. The active
asset and manifest were regenerated from E. Official typeset print-width
inspection remains open because this environment has no TeX engine.

## Round 15: accepted-decision logging and retry wording

The adversarial reviewer found two semantic ambiguities in candidate E. The
Validator-to-log arrow could be read as logging rejected decisions, and the
caption overstated the retry boundary by saying retry paths were not measured.
Candidate F changes the arrow label to the exact `accepted decision`. The
caption now says that blocked and retry paths are not drawn; the frozen corpus
does not preserve the first response before a retry. The active asset and
manifest were regenerated and checked at full size and thumbnail size. The
independent reviewer found no overlap or routing defect after these changes.
Official TeX build and typeset print-width review remain open.

## Round 16: full architecture reset and non-crossing route repair

The Round 15 candidate was rejected as a design direction after a fresh audit
of published agent-paper figures. Four new layouts were generated from the
grammar of ReAct, Reflexion, AgentSpec, and SWE-agent, with Voyager and
Magentic-One used as additional role/icon references. Candidate B was rejected
because its condition did not visibly reach Validator. Candidate D was kept as
the structural base because its Validator insertion point and shared-field
graph were clearest.

Candidate D was then regenerated through three targeted repairs: the condition
route was made to enter Filter directly while bypassing Decision log; the
condition route was routed below the log so it does not touch the database
icon; and the observation loop was moved above all modules so it does not
cross the accepted-decision or condition-selection paths. The final D-v3 also
aligns `proposed action` with the action field and labels the log input
`accepted decision`.

At that historical stage, the candidate asset was
`figures/assets/figure1_architecture_reset_D_final_v3.png`, staged through the
normal builder. It was later superseded by compact v1 because the large
runtime/measurement panels still read like a dashboard. Full-size,
paper-width, grayscale, and thumbnail inspections of D-v3 showed exact short
labels, clear endpoints, and no visible connector crossings; its adversarial
re-review passed. Official typeset PDF inspection remains the release gate
because the local environment still lacks a TeX engine.

## Round 17: compact single-canvas architecture reset

The D-v3 composition was rejected after adversarial review because its large
runtime/measurement panels, equal-weight cards, and oversized icons still read
like a dashboard rather than a contemporary agent-paper architecture figure.
New generated candidates were produced from the actual grammar of ReAct,
Reflexion, AgentSpec, and SWE-agent: a bounded Agent response, a compact
Validator insertion point, a separate Environment, and a small measurement
chain.

The selected compact v1 candidate removed the full-canvas lane frames and
headers. Its black `proposed action` connector starts at the `action` field;
the amber `rule input` connector starts at the right edge of `condition`; and
the amber `selects records` route starts independently at the bottom edge of
`condition` and bypasses `Decision log`. The accepted-decision branch lands on
the log, records flow through the filter, and the observation loop remains
above the graph. The extra Environment database icon was removed so it cannot
be confused with the Decision log.

At that historical stage, the active generated asset was
`figures/assets/figure1_architecture_compact_v1.png`, staged through the normal
builder. Full-size, paper-width, grayscale, and 900-pixel thumbnail inspection
passed. The compact v1 candidate was then superseded by the agent-paper v2
candidate to anchor `proposed action` directly to the `action` field. Official
typeset PDF inspection remains the release gate because the local environment
still lacks a TeX engine.

## Round 18: agent-paper v2 integration and endpoint audit (historical)

The compact v1 candidate was not retained as the final design. A fresh
generated candidate was produced from the paper grammar audit: a small dashed
Agent ownership boundary, a tight response object, a compact Validator
insertion point, a small Environment node, and a short lower log/filter chain.
The highlighted `condition` field has two explicit uses: `rule input` enters
the Validator before execution, while `selects records` enters the filter
without passing through the Decision log. The black `proposed action` arrow
was then regenerated so its visible origin is the `action` field itself.

At that historical stage, the generated source was
`figures/assets/figure1_architecture_agentpaper_v2.png`, with SHA-256
`cd94aaba55f3db872ea283401954689c2e86a1bdc710f731a0e94de1e2a52861`.
The builder copied the same raster into the manuscript-facing PNG and print
PNG. Full-size, paper-width, grayscale, and 900-pixel thumbnail inspection
passed. The adversarial review of the exact active files passed all endpoints,
overlap checks, information-density checks, and paper-grammar checks; it also
confirmed that the single-headed dashed observation return is directionally
unambiguous. Official typeset PDF inspection remains open because the local
environment still lacks a TeX engine.

## Round 19: shared-condition bridge v3

The v2 composition was not treated as the endpoint because its module layout
still gave the execution and measurement paths comparable visual weight. A new
generated candidate was designed from the paper audit as a compact grid: the
Agent response is on the left, Validator and Environment form the upper
execution chain, and Decision log, filter, and conditional rate form the lower
measurement chain. The amber `condition` field has two independent routes:
`rule input` enters Validator, while `selects records` bypasses Decision log and
enters filter. The black `accepted decision` route bends directly into the top
edge of Decision log.

The active generated source is
`figures/assets/figure1_architecture_agentpaper_v3.png`, with SHA-256
`295553a8c925f1250b42d6064a6cc792409841f4a4c574f8504f7e648e758a0b`.
The candidate, active source, active PNG, print PNG, and regenerated thumbnail
must all be copied from this exact raster. Full-size, paper-width, grayscale,
and thumbnail review found no text overlap or route crossing. The exact-active
adversarial review then passed all seven required routes, the agent-paper
grammar, the exact thumbnail synchronization, and the caption alignment.
Official typeset PDF inspection remains open because the local environment still
lacks a TeX engine.

## Round 21: academic-writing audit and evidence-boundary clarification

The active manuscript received a four-pass academic-writing review: claim and
outline order, paragraph transitions, plain-language and first-use definitions,
and reviewer/red-team scope. The abstract was reduced to 242 raw-token words
before LaTeX rendering. The
introduction now opens with the measurement consequence, then gives an 80/100
decision example before introducing the full irrigation setting. The manuscript
uses `condition share` and `all-decision rate` in place of unnecessary
`prevalence`, `marginal proxy`, and `fixed-denominator` jargon.

The methods now state the frozen statistical procedure: per-seed off-minus-on
deltas, a two-sided one-sample t-test, 95% t intervals with df = n - 1, and
cellwise unadjusted p-values. The world-state section defines direct
standardization, the pooled weighting target, the 40-record-per-arm support
rule, arm-level coverage, and the eight-record per-seed diagnostic rule. The
Figure 1 caption explicitly defines the Counted-set denominator and says that
the displayed condition abstracts the scarcity report while the full validator
rule also reads coping capacity.

An independent adversarial CS review passed the denominator example, citation
resolution, noncausal/deception scope, and active Figure 1 routes. Its S2/S1
readability and reproducibility findings were addressed in the manuscript and
source-of-truth docs. Static and evidence-boundary checks pass; official TeX/PDF
inspection remains the release gate because no TeX engine is available locally.

## Round 20: nested-interface reset from agent-paper figures

The v3 shared-condition bridge was retired as the active direction after a
fresh comparison with the rendered ReAct, Reflexion, AutoGen, SWE-agent, and
AgentSpec figures. The new generated candidate uses a bounded Agent, a black
dashed governance boundary around Validator, a direct accepted-action path to
Environment, and a separate accepted-record path to Decision log.

The lower Counted set receives two visibly distinct inputs: the black `records`
route from Decision log and the amber `selects` route from the response's
`condition` field. The retry connector was removed because its first response is
not preserved in the frozen corpus; the caption states that boundary. All
boundaries and arrows use black outlines with flat colored fills and subordinate
functional icons, following the compact interface grammar of the reference
agent papers.

The active generated source is
`figures/assets/figure1_architecture_agentpaper_nested_v3.png`. The source,
active PNG, print PNG, and regenerated thumbnail must be byte-identical after
staging. Full-size, paper-width, grayscale, and thumbnail inspection is
required, followed by adversarial semantic review. Official typeset PDF
inspection remains open because the local environment still lacks a TeX engine.

## Round 22: fresh shared-condition architecture round

The nested-interface composition was then retired rather than defended. A new
round generated six compact alternatives from the actual WAGF flow and the
rendered figure grammar of ReAct, Reflexion, SWE-agent, AutoGen, and AgentSpec.
The candidates were required to show only short semantic modules, a single
execution path, a direct final-record path, and the two distinct uses of the
same condition. Candidates A, B, and D were rejected because their record paths
started at Environment or visually merged into the counting path. Candidate C
had an ambiguous observation origin. Candidate E had the right topology but
needed an explicit Validator input port and a caption reset.

Candidate F is the active generated source:
`figures/assets/figure1_architecture_agentpaper_shared_condition_v4.png`, with
SHA-256 `df3f36fe83772e4dd5598188dc72343c1d082533f1b7332f6e0c154228b29286`.
It uses black borders and arrows, colored fills, short relation labels, and
black/amber ports. The black `final record` arrow terminates at Decision log;
black `records` then enters Counted records; amber `rule input` enters
Validator; and amber `selects` enters Counted records while bypassing the log.
Observation and retry paths are omitted for clarity rather than represented by
an ambiguous connector.

The independent adversarial visual review approved Candidate F at full size,
manuscript-width thumbnail size, and grayscale, with no P0/P1/P2 image-level
findings. It required synchronizing the caption's stale observation sentence
and replacing `Counted set` with the visible term `Counted records`; both fixes
are now applied.

## Round 23: official MiKTeX build and ICLR 2027 page check

MiKTeX 25.12 was used to run the ICLR style build: `bibtex manuscript` plus
two final `pdflatex` passes with the staged style directory supplied through
`TEXINPUTS` and `BSTINPUTS`. The build produced `paper/manuscript.pdf` with 9
pages total: 8 pages of main text and one references-only page. The final log
has no undefined citations or references, no overfull boxes, and no remaining
label-rerun warning. It has non-fatal underfull hbox/vbox warnings, including a
long title line and several page-fill warnings; rendered inspection found no
clipped figure, caption, or author metadata.

The official ICLR 2027 author guidelines allow at most 9 pages of main text
and exclude the bibliography. The typeset artifact therefore passes the
current page-limit check. OpenReview metadata, profiles, reciprocal-review
eligibility, anonymity, and live dual-submission checks remain submission-time
gates.
