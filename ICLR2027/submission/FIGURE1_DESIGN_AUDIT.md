# Figure 1 design audit and revision contract

> **Historical record only.** Every composition and contract described below
> predates the full D-v3 reset and is superseded. Do not use its “active
> source”, “Record filter”, “World state”, “future context”, or candidate-F
> wording for regeneration. The active reset design is documented in
> `AGENT_ARCHITECTURE_FIGURE_RESET.md` and operationalized in
> `FIGURE1_DESIGN.md`; the external-paper comparison is
> `..\FIGURE_STYLE_AUDIT.md`.

## Verdict on the previous version

The previous Figure 1 passed its geometric checks, but it was not yet a
strong paper figure. Its four equal cards (`AGENT`, `REPORT`, `WORLD`, and
`METRIC`) made the diagram read like a component inventory. The paper's
important claim is a relationship: one agent-written condition is read by
governance and also selects the records used by a conditional rate. That
relationship did not have enough visual priority.

## What the comparison shows

| Design dimension | WAGF project examples | Agent/guardrail paper convention | Previous Figure 1 | Revision decision |
| --- | --- | --- | --- | --- |
| Composition | One dominant pipeline with grouped layers | A small number of stages; arrows carry the process | Four equal cards plus several perimeter loops | Use one `AGENT OUTPUT` source, one `GOVERNANCE` gate, and two consequences |
| Semantic ownership | A response or layer owns related fields | A node represents a meaningful operation, not a noun list | `AGENT` and `REPORT` were separated by `contains` | Combine action and condition into one response card |
| Visual hierarchy | One highlighted input or layer | The central operation is visually dominant | All five colors had similar weight | Highlight the amber condition because it is the shared selection field |
| Connectors | Short, mostly orthogonal, labelled relationships | Arrow direction and short verbs explain the mechanism | Long bottom loops competed with the main flow | Keep primary routes short; move feedback to a thin outer route |
| Icons | Small, repeated pictograms with a common stroke | Icons support the node label; they do not become decoration | Earlier generated icons varied in visual weight | Use one reviewed generated composition with a common stroke language |
| Text | Compact labels inside clear ownership regions | Short stage names and verbs; details belong in captions | Descriptors and labels made the image feel like an infographic | Keep labels to one or two words where possible; explain in the caption |
| Color | Black outlines with pale WAGF fills | Color marks role or flow, not every object equally | Several saturated card colors created equal emphasis | Use pale fills, black borders, and color-matched semantic routes |
| Main takeaway | A visible output or layer consequence | The figure should answer “What changes?” | `Measured set changes` was disconnected from the main flow | Place the takeaway inside the metric region as its direct consequence |

The project comparison uses the existing WAGF architecture and feedback-loop
figures in `docs/architecture.png` and
`examples/irrigation_abm/analysis/feedback_loop.png`. The external comparison
uses AgentSpec's compact trigger/check/enforce vocabulary, AgentBench's
small set of evaluation dimensions and environments, and NeMo Guardrails'
stage-oriented sequence diagram. These references motivate the vocabulary and
hierarchy; no artwork is copied.

- [WAGF architecture](../../docs/architecture.png)
- [WAGF feedback loop](../../examples/irrigation_abm/analysis/feedback_loop.png)
- [AgentSpec](https://cposkitt.github.io/files/publications/agentspec_llm_enforcement_icse26.pdf)
- [AgentBench](https://proceedings.iclr.cc/paper_files/paper/2024/hash/e9df36b21ff4ee211a8b71ee8b7e9f57-Abstract-Conference.html)
- [NeMo Guardrails sequence diagrams](https://docs.nvidia.com/nemo/guardrails/reference/guardrails-sequence-diagrams)

## Revised Figure 1 contract

The figure now follows the visual sentence:

> One agent output enters governance; its condition also selects the measured
> set; an accepted action changes the future world.

The current generated-full revision follows the compact agent-paper grammar:
near-black arrows carry semantics, labels are short and separated from routes,
the canvas is uniform cool gray, and there are no white label cards. The
generated composition has one response packet, one runtime gate, one recorded
decision set, and one evaluation fork:

1. `Agent response` contains `Action` and the highlighted `Agent-written condition`.
2. The condition reaches a small fork and is sent to `Validator` and `Record filter`.
3. `Validator` sends an accepted action to `Recorded decisions`, which changes
   `World state`; the dashed feedback route returns future context to the next
   response.
4. `Recorded decisions` and the shared condition enter `Record filter`, which
   sends the selected set to `Conditional rate`.

The routes are deliberately asymmetric because the relationships are
asymmetric:

- action to validator: `proposed action`;
- condition fork to validator: `rule input`;
- condition fork to record filter: the node text `selects records`;
- validator to decision log: `accepted decision`;
- validator to world: `accepted action`;
- recorded decisions to record filter: `recorded set`;
- record filter to conditional rate: `selects records`;
- world to agent response: `future context` (dashed feedback route).

The amber condition appears once inside the response packet and reaches a
small fork with two outgoing routes. This is the visual proof of the paper's
central measurement concern; it is not an extra architecture claim. Retry is
omitted from the drawing because the frozen corpus does not preserve the first
response before a retry; the caption states this boundary.

## Acceptance criteria

- A reviewer can identify the agent-written condition and its two roles at
  thumbnail size without reading the caption.
- The accepted-action route reaches `World state`; the dashed feedback route visibly
  returns future context to the agent response.
- No arrow passes through a label or icon, and no primary centerlines cross.
- All paper-facing labels are short, legible, and visually separated from
  arrows and icon strokes.
- Generated icons share one stroke language, restrained colored fills, and no
  decorative elements beyond their semantic roles.
- The figure remains conceptual; quantitative values stay in Figures 2--4.

## Build and review order

```powershell
python ICLR2027\submission\source\figure1_overlay.py
python ICLR2027\submission\checks\figure1_geometry_check.py
```

After staging, inspect the full-size PNG, the print-width raster, and a
thumbnail. The generated-raster geometry checker verifies dimensions and
short labels, but manual inspection is required for pixel-level text/arrow
separation. Only then should the manuscript caption and Figure 1 manifest be
considered synchronized.

## Round 13: agent-paper reset and candidate D

The previous complete generated composition was rejected as too close to an
illustrated dashboard. The redesign returned to the visual grammar of
published agent papers: one observable response, one compact execution loop,
short semantic modules, and arrows that state the relation. ReAct, Reflexion,
AutoGen, and AgentSpec were reviewed as primary references.

Three new candidates were generated and checked at full size and thumbnail
size. Candidate A was rejected because its `rule input` label sat on the wrong
route. Candidate C was rejected because its nested boundaries over-weighted the
measurement lane. Candidate D preserved the correct two-use condition routing
and replaced the large robot and globe with a small LLM chip and a
water-reservoir cue. It is now the active generated source.

The active D composition has one `condition` field with two distinct amber
routes, a direct Validator-to-Environment path, a separate
Validator-to-Decision-log path, a separate log-to-Filter path, and one dashed
next-context return. The source, active copy, manifest, caption, handoff, and
regeneration instructions were synchronized after selection. Official
print-width PDF review remains open because the current environment has no TeX
engine.

## Round 14: explicit producer relation and candidate E

The thumbnail review of candidate D found one semantic weakness: the `Agent
(LLM)` and `response` boxes were adjacent, but no arrow stated that the agent
produces the response. Candidate E was generated by adding exactly one short
black `emits` arrow between those boxes. The existing action, condition,
validator, environment, log, filter, rate, and dashed next-context routes were
preserved.

Candidate E passed full-size and thumbnail review at that stage: the new arrow
had clear endpoints, did not touch text or icons, and made the first relation
explicit. It was later superseded by candidate F after semantic review. The
official typeset print-width inspection remains open.

## Round 15: accepted-decision logging label and evidence boundary

The adversarial review found that `recorded decision` on the Validator-to-log
arrow could imply that rejected decisions were also logged. Candidate F was
generated from E with only that label changed to `accepted decision`. Full-size
and thumbnail inspection confirm that the label is exact, legible, and clear
of the arrow and node borders.

The caption now says that blocked and retry paths are not drawn, rather than
claiming that they are not measured. This matches the manuscript's actual
boundary: accepted actions after retries are retained, but the first response
before a retry is absent from the frozen corpus. Official typeset print-width
inspection remains open.
