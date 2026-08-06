# Figure 1: the retry path does not close, and the caption says it does

**Analysis only. Nothing was changed.** Written 2026-08-05 against the shipped
`figures/fig0_problem_schematic.pdf` and `paper/manuscript.md` as they stand after the
2026-08-05 Codex revision.

This report argues for one change. It does not ask for the figure to be redesigned, does not
question the decision to ship an image-generated concept figure, and does not touch the three
quantitative figures.

---

## 1. The finding

**The figure shows blocking as an outcome. It does not show blocking as a loop.**

In the shipped figure the red path runs `Validator` → `blocked` → `Re-prompt`, and stops there.
No edge returns from `Re-prompt` to the `Reported state` field inside `Agent answer`.

As drawn, the reader sees two independent facts:

- a rule reads the reported condition and can block an action;
- a measurement reads the same condition and selects records.

What the reader does **not** see is the thing connecting them: that blocking causes the agent to
write the condition again, and therefore changes which records the measurement selects.

## 2. Why this is a caption-figure mismatch, not a matter of taste

The manuscript states the closure twice, in its two most load-bearing places.

**Figure 1's own caption**, `paper/manuscript.md:52-53`:

> "A blocked response may be retried, **producing a different recorded response**."

**The abstract**, describing the paper's central mechanism:

> "**Blocking a response can change the final action and which decisions satisfy its condition.**"

Both sentences assert that the retry *changes the recorded condition*. The figure stops one edge
short of showing it. A caption that describes something the figure does not show is on the short
list of defects this project treats as unambiguously factual and correctable.

## 3. Why this particular edge is the paper

The paper's contribution is not "a rule can block an action" — that is what every guardrail does
and no one disputes it. The contribution is that **the metric's denominator is written by the
process the metric is evaluating**, and that enforcement moves it.

Take the edge away and the figure depicts an ordinary, unremarkable guardrail: rules block things,
metrics count things. The claim that makes the paper publishable is precisely the feedback that is
missing from the picture.

This matters most for the reader the figure exists for. Figure 1 sits at the end of §2, before any
statistics, and its job is to make the problem legible in one look. A reader who takes the figure
at face value and then meets §4's numbers has not been told why the two arms' denominators could
differ at all.

## 4. What the figure already gets right, and should keep

The `Same field` node is a better decomposition than the version it replaced. Naming the shared
field explicitly, and drawing **two** labelled edges out of it — `rule input` to the validator and
`record selection` to the measurement — states in one glance that a single agent-authored value
does two jobs at once. The earlier design carried this only as a shared colour, which asks the
reader to infer it.

The fraction on the right, with the numerator and denominator each colour-matched to their source
on the left, is also clearer than the earlier version.

**The proposed change is additive.** It keeps `Same field` and both of its outgoing edges, and adds
the one return edge that closes the loop.

## 5. The change, stated minimally

Add an edge from `Re-prompt` back to the `Reported state` field, labelled so that a reader
understands the field is rewritten rather than merely re-read. Something of the form
`writes a new one` is enough; the caption already carries the full sentence.

Nothing else in the figure needs to move for this to work.

## 6. Three secondary observations, explicitly lower priority

These are recorded for completeness. **None of them is a reason to change the figure on its own**,
and none should delay or complicate the edge above.

| | observation | why it is minor |
|---|---|---|
| a | The shield contains a **tick**. A tick reads as *approved*, while the adjacent red edge reads as *blocked*. | A reader resolves the contradiction from the red label. Wrong signal, not a wrong claim. |
| b | The figure is **sans-serif**; the body text and Figures 2-4 are Times New Roman. | Visible inconsistency on the page, no effect on meaning. |
| c | The figure is a **raster** — `pypdf` reports 1 embedded image and **0 text fonts**, and the file is 3,545 KB against 86 KB for the vector Figure 2. | Correctly disclosed in the current handoff section. The consequence to note is practical: no label in it can be corrected without regenerating the whole image, and the guards in `fig0_problem_schematic.py` (the directional data check, the collision check, the mutation test) cannot reach it. That is a maintenance cost the project has accepted, not a defect. |

Observation (c) is the reason to fix (5) deliberately rather than incrementally: a raster cannot be
patched, so whatever is regenerated should be right the first time.

## 6b. Four existing artefacts in this repository contradict the figure as drawn

The case above rests on the caption. These four make it independent of the caption: each is a file
already in the project, written before this report, that asserts the loop closes.

### (i) The paper's own §8, which exists *because* the loop closes

`paper/manuscript.md:359-361`, the opening of Limitations — the paper's most carefully worded
paragraph:

> "An accepted report after a retry **is selected by the rule that judged it**. This stratum is
> **24.3%** of governed decisions, and **its first attempt is absent from the shipped corpus**."

Read what that concedes. The report *on record* is the one written **after** the block. The one
written **before** it no longer exists. That is the loop closing, and the paper treats it as
important enough to open its limitations with.

A figure that stops at `Re-prompt` cannot be reconciled with a limitation that is about what the
re-prompt *overwrote*.

### (ii) The measured retry pressure, which makes this the common case

From `paper/substitute.py`, sourced to the evidence pipeline:

| | |
|---|---|
| governed decisions retried at least once, all years | **63.8%** |
| governed year-1 decisions retried at least once | **82.1%** |
| governed year-1 decisions that ran to the retry budget | **70.5%** |

The retry is not a corner case the figure may reasonably omit for clarity. It happens to **most**
governed decisions. A schematic of this system that shows the retry terminating is not a
simplification; it is a different system.

### (iii) `broker/core/_retry_loop.py`, 23 KB of implementation

The loop is not a narrative device. It is a named module in the framework, and the block is
delivered back to the agent so that it generates again. The figure is meant to depict this system.

### (iv) The author's own framework figure, which draws the loop and labels it twice

`paper/nature_water/figures/Fig1_framework.png` — the WAGF architecture figure, the visual register
the current Figure 1 was asked to follow. It carries **two** dashed feedback edges running from the
governance layer back to the LLM agent, and labels them:

> `Re-ask if no valid action`
>
> `Revise with rule feedback`

The author already decided, in their own prior figure, that a return edge is required to describe
this system and that it deserves an explicit label. The present Figure 1 depicts the same
architecture with that edge removed.

### (v) The project's own record of rejecting a figure for this exact defect

`_archive/cleanup_2026-08-05/figure-history/_rejected_imagegen/README.md` records why three earlier
image-generation attempts were rejected. One was rejected because **"the red feedback arrow did not
originate at governance ... and the action-to-governance arrow was missing entirely"** — while every
text label was correct and the tool reported its own checks as passing.

A missing or mis-anchored arrow has already been treated once in this project as sufficient grounds
to reject a Figure 1 candidate. The current figure has the same class of defect at a different edge.

---

**Taken together:** the caption says the loop closes, the limitations section is *about* the loop
closing, the measurements say it closes for 63.8% of governed decisions, the framework implements
it in a module named for it, the author's own prior figure draws it with two labelled arrows, and
this project has already rejected a Figure 1 for omitting an arrow of exactly this kind.

The figure is the only artefact in the set that says otherwise.

## 7. Out of scope

- The three quantitative figures. They render statistics from 16,380 decisions per arm and must
  never be image-generated or redrawn by hand.
- The decision to ship an image-generated concept figure for Figure 1.
- Any change to what the paper claims. This report asks the figure to show a claim the paper
  already makes; it does not ask for a new one.
- The caption. It is already correct. The figure is what does not match it.

## 8. How to verify the fix

Read the figure with the caption covered, and answer one question: **does blocking change what the
metric counts?** If the picture alone does not answer yes, the edge is not doing its job yet.
