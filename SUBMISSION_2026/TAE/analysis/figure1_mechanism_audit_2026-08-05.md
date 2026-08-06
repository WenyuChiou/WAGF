# Figure 1 Mechanism Audit

**Date:** 2026-08-05  
**Mode:** review only; no manuscript, figure, script, or non-report file changed  
**Review profile:** figure-specific mechanism audit for an AI/LLM computational submission  
**Modules:** `academic-writing-skills`; `paper-review` with the AI/LLM computational and display/provenance modules  
**Primary artifact:** `figures/fig0_problem_schematic.pdf`  
**Related artifact:** `figures/fig0_problem_schematic.png`

## Verdict first

The shipped Figure 1 is **adequate for a weaker structural claim but inadequate as a standalone
depiction of the paper's full feedback mechanism**.

It clearly shows that one agent-reported field is used twice: the validator reads it, and the
measurement selects records using it. It also shows that a blocked response leads to a
re-prompt. However, the picture does not show the re-prompt returning to a new agent answer, nor
does it show that the new answer can rewrite the reported condition and thereby change the set
selected by the metric. That missing temporal edge is the paper's distinctive contribution, not
decoration.

This is a material figure--claim mismatch, but it is an omission rather than a contradiction.
The image does not say that retries cannot change the report; it simply stops before showing the
step on which the denominator-changing claim depends. The caption can supply that missing fact
verbally, but the figure-only test requested here fails.

## 1. Figure-only reading, before reading the paper

I first inspected the shipped graphic with its caption covered. The corresponding PNG shows the
same wide, single-raster schematic embedded in the one-page PDF; the PDF has zero selectable text
characters and one embedded image, so the judgment below is about the visible graphic rather
than hidden PDF text.

**One-sentence figure-only reading:**

> An agent answer contains an action and a self-reported high-scarcity state; the same field is
> sent to a validator and to a measurement filter, while a blocked answer triggers a re-prompt
> and the metric counts actions among records selected by the reported state.

That sentence is supported by the visible labels `Agent answer`, `Action`, `Reported state`,
`Same field`, `Validator reads self-report`, `Measurement selects records`, `blocked`,
`Re-prompt`, `Increase actions in selected records`, and `Records reporting high scarcity`.

The figure-only reading does **not** include “the re-prompt produces a new answer” or “the new
reported state changes the denominator.” No arrow connects `Re-prompt` back to the `Agent answer`
box or to a new action/report record. The red path terminates at the re-prompt box.

## 2. The paper's claim

The narrowest one-sentence version of the paper's claim, using the paper's own words, is:

> **Enforcement can change an agent-written condition that both triggers the validator and
> selects the decisions in the metric, because a blocked response may be retried into a different
> recorded response.**

This combines the paper's two necessary parts:

1. **Shared measurement field:** the reported condition is read by both the validator and the
   metric.
2. **Feedback:** blocking leads to a new recorded response, which can change the condition and
   therefore the selected set/denominator.

The first part is visible in Figure 1. The second part is not fully visible in Figure 1.

## 3. Figure and paper side by side

| Element | Figure 1 shows | Paper claims | Match |
|---|---|---|---|
| One response contains action and report | `Agent answer` contains `Action` and `Reported state` | The condition is written by the agent in the response being judged. | Yes |
| Same field does two jobs | `Same field` branches to `rule input` and `record selection`. | The validator reads the label and the metric reads the same label. | Yes, clearly |
| Metric denominator/selection | `Conditional rate` contains selected actions and records reporting high scarcity. | The rate counts increases among decisions reporting high scarcity. | Yes, at the conceptual level |
| Enforcement intervention | `Validator` → `blocked` → `Re-prompt`. | A validator blocks the response and asks the agent to retry. | Yes, but incomplete |
| New response after intervention | No return edge to `Agent answer`; no second answer/report is drawn. | A blocked response may be retried, producing a different recorded response. | **No** |
| Denominator changes because of retry | No visual transition from the first report to a changed report or changed selected set. | Enforcement can change both the recorded action and the set of decisions counted. | **No** |

The important distinction is between **co-location** and **feedback**. The current diagram makes
co-location legible: the same field is used by two downstream components. It does not make the
feedback legible: the intervention does not visibly create a new answer that re-enters either
branch.

## 4. Paper passages relied on, with line numbers

The following are the manuscript lines used for the claim comparison. Line numbers refer to the
current `paper/manuscript.md` on disk.

### Abstract

```text
5: Runtime guardrails check proposed actions and ask an agent to retry when a rule is violated. Evaluations
6: often use a conformance rate: the share of decisions that satisfy a rule. That rate is difficult to interpret
7: when the condition is written by the agent in the response being judged. Blocking a response can change the
8: final action and which decisions satisfy its condition. This does not require deception. Some rules read an
```

Lines 5–8 state the full consequence: blocking can change both the final action and which
decisions satisfy the condition. The image shows the block and the selection rule, but not the
transition that connects them.

### Introduction: the metric and the feedback claim

```text
30: Runtime guardrails can change the response that they later score. This matters for large language model (LLM)
31: agents, which are often paired with runtime checks. We use *validator* for the component that applies a rule,
32: identifies a violation, and asks the agent to retry [1] [2] [3] [4]. A conformance rate is the share of
33: decisions that pass the rule. A paired evaluation can compare that share with and without validators, but the
34: comparison is meaningful only when the two arms count comparable decisions. The loop also builds on earlier
35: work on machine-readable norms and agent institutions [5] [6] [7] [8]. The central problem is that the
36: condition used to select decisions for the rate may itself be part of the agent's response. If enforcement
37: changes that condition, a changed rate may reflect a changed set of decisions counted rather than changed
38: behavior.
```

```text
40: Consider an irrigation agent that proposes increasing water demand while reporting high water scarcity. A
41: validator can block this response and ask for a retry. The retry may change both the action and the report.
42: Here, an *agent-reported condition* is a label written by the agent in the same response as the action. The
43: validator reads that label to decide whether to block. The metric reads the same label to decide whether the
44: decision enters the rate. If the evaluation counts increases only among decisions that report high scarcity,
45: enforcement can change both the recorded action and the set of decisions counted by the rate. Figure 1
46: summarizes this path. We observe the recorded response, not the agent's hidden intent.
```

Lines 40–45 are the most direct comparison target. Figure 1 covers lines 42–44 visually. It
does not show the “retry may change” step in line 41 or the resulting set change in line 45.

### Figure 1 caption

```text
50: **Figure 1.** How an agent-reported condition changes what a metric counts. One response contains an
51: action and a reported condition. The validator reads the condition to decide whether to block. The metric
52: reads the same condition to select decisions for the rate. A blocked response may be retried, producing a
53: different recorded response. High scarcity is an illustrative irrigation label. This is a conceptual example,
54: not a data figure.
```

The caption is accurate as prose, but line 52–53 describes a visual transition that the graphic
does not draw. With the caption visible, a reader can reconstruct the missing return edge. With
the caption covered, the figure does not establish that a new response is produced.

### Contributions and scope

```text
72: We make three contributions. First, we identify a construct-validity failure mode for runtime guardrail
73: evaluation. When a rule condition is written by the agent, enforcement can change both the response and
74: the set of responses used to score it. Second, we demonstrate this failure mode in paired simulations across
75: two agent testbeds. We separate rules that read agent reports from rules that read simulator-recorded state.
76: Third, we provide a reporting protocol. It pairs the conditional rate with condition prevalence, an
77: independent world-state record, and a rate over every decision when the design allows it. Our claims are
78: descriptive. We do not claim that agents deceive, that recorded-world reweighting is a causal adjustment,
79: or that the pattern applies to every model or governance stack. Section 2 defines the guardrail loop and
80: the paired simulation design.
```

Lines 72–74 confirm that the missing feedback is not a side detail: it is the stated failure
mode. Lines 77–79 also bound the conclusion; this audit does not infer deception or causality.

### Setup and missing-data boundary

```text
84: Both testbeds run the same guardrail loop. In each generation, the agent returns an action and two
85: agent-reported conditions about its situation. Validators check the proposal against those reports and
86: against the simulator's recorded state. An ERROR-level violation returns the broken rule and asks for
87: another answer, up to three attempts. If all attempts fail, a domain default executes.
```

```text
360: An accepted report after a retry is selected by the rule that judged it. This stratum is
361: {{CLAIM:acceptance_selection_pct}} of governed decisions, and its first attempt is absent from the shipped
362: corpus. Three checks found no first-attempt record. The never-retried stratum is not a bound on this missing
363: quantity. No report there was rewritten, but the two arms are filtered differently.
```

```text
375: Two missing data streams would settle the remaining ambiguity. One is the first-attempt report before retry.
376: The other is enforcement with the environment pinned to the untreated trajectory. Neither exists here. This
377: is one guardrail stack with a nondeterministic backend, so comparisons are aggregates over *N* seeds.
```

Lines 84–87 establish the loop and fallback boundary. Lines 360–363 are especially important:
the paper claims that the accepted post-retry report is the selected record, while acknowledging
that the first attempt is missing. This makes the missing return edge materially relevant, but it
also prevents a stronger claim that every retry changed the report.

### Conclusion

```text
381: In a guardrail loop with environmental feedback, an agent-reported rule condition can change both the
382: recorded response and the decisions used to score it. Our irrigation results show why a changed conditional
383: rate is not enough to establish a change in the behavior being measured. Report condition prevalence,
384: preserve an independent world-state record, and show an all-decision rate when the design provides one.
```

The conclusion again names the recorded-response transition and the scoring-set transition.
Figure 1 currently makes only the shared-field part of that statement visual.

## 5. Retry implementation and claim provenance

### What the implementation actually does

The retry loop supports the existence of a new proposal after a rejection:

- `broker/core/_retry_loop.py:204–225` defines the governance retry loop as re-invoking the LLM
  with intervention reports and returning the updated proposal, validation results, and retry
  count.
- `broker/core/_retry_loop.py:236–268` increments the retry count, builds intervention reports,
  renders a retry prompt, and calls `llm_invoke(retry_prompt)`.
- `broker/core/_retry_loop.py:292–301` parses the returned raw output as the current
  `SkillProposal`.
- `broker/core/_retry_loop.py:303–333` records the current attempt, updates current proposal
  context, reruns validators, and either accepts the new proposal or continues the loop.
- `broker/core/_retry_loop.py:355–406` handles exhaustion and selects either the final proposal
  or a domain default according to the configured policy.

The implementation therefore substantiates the figure's `blocked` → `Re-prompt` path and the
paper's statement that a different recorded response is possible. It does **not**, by itself,
prove that the reported scarcity label changes on a retry, that the action changes, or that the
metric denominator changes. Those are empirical properties of the logged runs and their selection
rules, not consequences of the retry function alone.

### What the retry-related CLAIM entries establish

`paper/substitute.py` records:

```text
92:     "retry_budget": {
93:         "value": "three",
94:         "source": "NUMBERS.md §5a, retry-structure table · `retry budget, read from the data | 3
95:                    (max retry_count)`, e1_first_attempt_limits.py section 1 ·
96:                    `retry budget observed (max retry_count) : [3]`",
```

```text
432:     "year1_retried_pct": {
433:         "value": "82.1%",
434:         "source": "NUMBERS.md §4 · `anchor, retried (retry_count > 0) | 79.5-84.6%, mean 82.1%`",
436:     "year1_exhausted_pct": {
437:         "value": "70.5%",
438:         "source": "NUMBERS.md §4 · `anchor, EXHAUSTED the budget (retry_count == 3) | ...",
444:     "allyears_retried_pct": {
445:         "value": "63.8%",
446:         "source": "NUMBERS.md §5a, retry-structure table · `retried at least once (retry_count > 0),
447:                    all years | ... pooled 10,450 / 16,380 = 63.8%`, ...",
```

```text
632:     "acceptance_selection_pct": {
633:         "value": "24.3%",
634:         "source": "NUMBERS.md §5a · `approved after at least one retry -- the selected stratum
635:                    | ... pooled 3,981 / 16,380 = 24.3%`",
```

These values show that retry and post-retry selection are common enough to matter. They do not
show that a report changed. In particular, `retry_count > 0` is not equivalent to
`reported_condition_after != reported_condition_before`; the manuscript explicitly says that the
first-attempt report is missing. The existing defect analysis is right to treat the retry path as
important, but it overstates what these percentages alone prove when it says that the measurements
show the loop “closes” in the sense of a changed denominator.

## 6. Comparison with the author's earlier framework figure

The read-only earlier figure, `paper/nature_water/figures/Fig1_framework.png`, draws a broader
WAGF architecture. It contains two explicit dashed return paths from the governance layer toward
the LLM agent, labelled:

- `Re-ask if no valid action`
- `Revise with rule feedback`

It also shows the final water action entering execution and the environment returning information
to the context builder. This is useful design precedent: when the architecture depends on a
retry/revision loop, the earlier figure draws the return edge and labels its function.

It is not, however, independent empirical proof of the TAE mechanism. It is a broader framework
diagram with different visual granularity. Its strongest relevance here is visual and architectural:
the current Figure 1 omits a return edge that the author's own earlier architecture made explicit.

## 7. What the rejected-image history does and does not establish

The rejected-image README records three prior failures:

1. a geometry/data mismatch;
2. a feedback arrow that originated at the wrong component and a missing action-to-governance
   arrow; and
3. a close candidate that lost the three region tints, left one box without an icon, and was a
   raster.

This history supports a project-level principle: a correct label set does not guarantee correct
structural semantics. It also supports checking arrow origins and destinations independently of
the generator's own claims.

It does not, by itself, prove that the shipped figure is defective. It is process evidence, not
mechanism evidence. The current mismatch is established independently by inspecting the shipped
graphic against the manuscript's retry-and-rewrite sentence.

The README's final sentence says that the shipped figure is drawn in TikZ from data. That
description is stale for the current artifact: a read-only inspection of the current PDF found
one embedded PNG image and zero selectable text characters, and the current state ledger records
the figure as an image-generated flat-icon raster. The historical README should not be used to
override the current PDF geometry.

## 8. Assessment of `analysis/figure1_loop_defect_2026-08-05.md`

### Where it is correct

The analysis is correct on the central visual observation: the red path ends at `Re-prompt`, and
no visible edge returns to the `Agent answer` or to a new `Reported state`. It is also correct that
the `Same field` node, the `rule input` edge, and the `record selection` edge are strong parts of
the current figure. Its classification of the missing return edge as material rather than
cosmetic is justified because the paper's contribution is the interaction between enforcement,
the agent-authored condition, and the selected set.

Its proposed minimal direction is also sound in spirit: a return edge should target a new answer
or response record and should say that the action/report may be rewritten. A return arrow merely
to the old `Reported state` box would be ambiguous; it could mean rereading the old value rather
than generating a new response.

### Where it overreaches

1. **“Two independent facts” is too strong.** The current picture does visibly connect the two
   jobs through `Same field`. They are not independent in the structural sense; they are
   temporally disconnected. The precise criticism is “shared field shown, feedback closure
   omitted,” not “two independent facts.”
2. **The figure is silent, not contradictory.** The `blocked` → `Re-prompt` arrow is compatible
   with a loop. It does not show the loop, but it does not assert that the retry terminates without
   another answer. The statement that the figure is “the only artefact in the set that says
   otherwise” should be softened to “the only artifact that fails to show the closure.”
3. **Retry frequency is not condition-change evidence.** The 63.8%, 82.1%, 70.5%, and 24.3%
   values establish that retries/post-retry selection are common. They do not establish that the
   report changed or that the denominator changed. That requires the logged comparison and its
   carefully bounded interpretation.
4. **The implementation proves re-invocation, not the full empirical mechanism.** `_retry_loop.py`
   shows a new LLM call, new proposal parsing, and revalidation. It does not alone prove a changed
   scarcity report. The manuscript's “may change” wording and missing-first-attempt limitation are
   more careful than a deterministic statement that every retry rewrites the condition.
5. **“One edge is enough” needs a target and label constraint.** A return edge to the old answer
   box without indicating “new response” could create a different ambiguity. The smallest adequate
   repair is a directed edge from `Re-prompt` to a new `Agent answer`/`Retry answer` state, labelled
   something like `may rewrite action + report`, with the arrowhead visibly inside the target.

## 9. Recommended disposition

No figure change was made in this audit.

If the author wants Figure 1 to function as the paper's standalone mechanism figure, a material
revision is warranted:

> Add a clean, directed return edge from `Re-prompt` to a new answer record (or a visibly marked
> second-generation `Agent answer`), labelled `may rewrite action + report` or equivalent. Keep
> the existing `Same field` branches to validator and measurement. The label should preserve the
> paper's non-deterministic wording (“may change”), not imply that every retry changes the report.

This would make the visual chain explicit:

```text
agent answer (action + report)
        -> validator reads report
        -> blocked / re-prompt
        -> new answer may rewrite action + report
        -> same report field selects the recorded denominator
```

Because the shipped Figure 1 is raster, the change should be regenerated as a whole and then
checked at standalone and manuscript print size. If that change is made, the visual state ledger,
the handover's current Figure 1 description, and the PDF/hash manifest must be synchronized after
the new gate run. No such change is authorized or performed by this report.

## Addendum: the validation-message handoff is real

The implementation confirms the additional point raised after this audit: a validator rejection
does not merely set a red status. It creates a structured message for the next LLM call.

`broker/core/_advise.py:180–220` builds `InterventionReport` objects from validator errors. Each
report carries a rule id, blocked skill, human-readable `violation_summary`, optional
`suggested_correction`, severity, and domain context. `broker/interfaces/skill_types.py:150–181`
then formats that object as prompt text containing the blocked action, the reason, and—when
present—the suggestion.

`broker/utils/parsing/unified_adapter.py:1052–1099` wraps those reports in the retry prompt. In
the legacy retry framing, the visible message is conceptually:

```text
Your previous response was flagged by the governance layer.
**Issues Detected:**
- [ERROR] Your proposed action '<skill>' was BLOCKED.
  - Reason: <validator message>
  - Suggestion: <optional correction>
Please reconsider your decision. Ensure your new response addresses the violations above.
<original prompt>
```

Finally, `broker/core/_retry_loop.py:263–301` passes that rendered prompt to
`llm_invoke(retry_prompt)` and parses the returned output as a new `SkillProposal`; lines
303–333 update the current proposal context and run the validators again.

This refines the main finding in two ways:

1. The current Figure 1's `Validator → blocked → Re-prompt` path is a defensible high-level
   abstraction of the validation-message handoff. The audit should not claim that this handoff
   is absent.
2. The remaining visual omission is downstream of that box: the figure does not show the LLM
   receiving the message and producing a new `Agent answer` containing a potentially new action
   and reported state. The code confirms that this second stage exists, but the picture leaves it
   implicit. The proposed return edge therefore remains useful if Figure 1 is meant to carry the
   paper's full denominator-changing feedback claim on its own.

The implementation also clarifies terminology: this path is a fresh LLM invocation with a retry
prompt, not retrieval of a prior answer from memory. The evidence supports “receive validation
feedback and retry,” while “retrieve” would describe a different operation unless the user means
retry colloquially.

## Read-only delivery note

The current source manuscript and Figure 1 PNG still match the recorded release manifest. The
current `paper/manuscript.pdf` and `figures/fig0_problem_schematic.pdf` hashes do not match that
manifest, although the current PDF still has the same one-page raster structure and embeds the
same-sized Figure 1 image (1883 × 642 pixels) inspected above. This is a separate release-metadata
drift finding, not evidence that the figure's visible mechanism changed. It was not repaired here
because this task forbids regenerating or editing release artifacts.

## Functional-completeness retrospective

- **Lifecycle stage:** submission-stage figure/mechanism audit.
- **Artifacts covered:** current Figure 1 PDF/PNG, manuscript claim passages, retry claim entries,
  retry implementation, earlier framework figure, rejected-image history, current state ledger,
  and the pre-existing defect analysis.
- **Evidence boundary:** no manuscript, figure, script, or outside project file was edited; no
  new experiment or mechanism was inferred from the code alone.
- **Checks performed:** figure-only visual reading, PDF structure inspection, line-numbered source
  reading, implementation trace, cross-figure comparison, and adversarial comparison with the
  existing analysis.
- **Unresolved issue:** the shipped figure is incomplete for the paper's full feedback claim.
- **Readiness consequence:** the overall PDF may still pass the venue gate, but Figure 1 is not
  fully paper-ready as a standalone explanation of why enforcement can change the metric's
  denominator. A human decision is required before any visual revision.
