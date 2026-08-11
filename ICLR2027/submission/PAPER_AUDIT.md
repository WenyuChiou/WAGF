# ICLR 2027 paper audit: claim, figures, examples, and evidence

Updated 2026-08-08 after the v6 generated Figure 1 retry-route fix, the
current frozen-corpus manuscript pass, and the first-attempt evidence audit.
This is an internal review record. The
anonymous manuscript remains `paper/manuscript.tex`.

## Current figure-position decision

The figures are an argument sequence, not a collection of application
illustrations. Figure 1 earns the first slot because it gives the reviewer the
paper's reusable dependency before any domain-specific result appears. The
remaining quantitative displays are irrigation-led because irrigation is the
only setting in the current corpus that supplies the coupled action -> state ->
next-context path needed for the mechanism diagnosis. Flood receives one
table-level boundary check so it contributes breadth without becoming a second
story.

The balance rule is strict: if a display cannot answer a distinct reviewer
question, it is removed or moved to the supplement. A Flood panel would fail
this rule because it would suggest a matched mechanism comparison that the
different feedback, action, field, and seed designs do not support.

## Paper identity

The paper studies a measurement-validity problem in governed LLM-agent
evaluation. An agent-authored condition is used twice: the runtime validator
reads it while deciding whether a proposal can execute, and the evaluator uses
it to select the records in a conditional score. The central claim is narrow:
the denominator is part of the evaluated system when governance can change the
condition that defines it.

The coupled irrigation simulation is the primary empirical example because it
has the required feedback loop: an accepted action changes a shared reservoir,
and the later world state enters subsequent agent context. It is an example of
the measurement dependency, not a claim that the result is specific to water
management. Flood is retained as a secondary cross-testbed boundary check. It
provides a bounded descriptive check on whether similarly large high-appraisal
contrasts appear in the non-coupled Flood setting, but it is not a second
mechanism analysis because its action ontology, feedback, field name, and seed
matching differ.

## Figure and table contract

Each display has one reader task. A reviewer should be able to answer the
question in the second column without reading another figure first.

| Display | Reader question | What it establishes | What it must not imply | Example role |
| --- | --- | --- | --- | --- |
| Figure 1 | Where can one agent-written condition affect both execution and scoring? | The response carries an action and condition; the Validator can accept, retry, or default; the executed record enters the log; the same condition selects counted records. | It is not a quantitative result, a causal diagram, a component inventory, or proof that every retry attempt was preserved. | Domain-neutral conceptual bridge. Water appears only as the motivating application, not as a second visual branch. |
| Figure 2 | Which rule layers read self-report versus simulator state? | The irrigation validator has distinct self-report-conditioned and world-state-conditioned blocking paths, with the blocked subset and action mix made explicit. | It is not an effect plot and does not say that high scarcity alone is blocked. | Primary irrigation rule audit. |
| Figure 3 | Why is the anchor validator-on/off contrast descriptive in a coupled setting? | The anchor time series, reservoir trajectories, and never-retried subset show matched initial worlds, later state divergence, and unequal filtering. | It is not a mediator analysis, causal adjustment, or proof of a unique mechanism. | Primary irrigation mechanism diagnosis. |
| Figure 4 | What changes when the action denominator includes every executed decision? | Conditional and all-decision executed-action contrasts differ in both directions across the five irrigation cells. | It is not an automatic correction or a claim that one denominator is universally valid. | Primary estimand consequence. |
| Table 1 | What are the primary irrigation condition and action rates? | Anchor and five-cell executed-action quantities, with seed-level inference. | It must not foreground Flood. | Primary result table. |
| Table 2 | How much of the anchor share contrast remains after recorded-state alignment? | Reweighting is a descriptive composition diagnostic with explicit coverage. | It is not causal adjustment because recorded state is downstream of governance. | Supporting primary irrigation diagnostic. |
| Table 3 | Is the broad contrast confined to irrigation? | A bounded descriptive comparison: irrigation has the larger range, Flood remains near zero and crosses signs. | It is not a clean matched control: Flood has incomplete audit coverage and differing manifest seed IDs across arms in six configurations; it is not a paired comparison, dose-response result, or mechanism-transfer test. | Secondary boundary check only. |

## Figure hierarchy and balance

The paper has one conceptual figure and three quantitative figures. The
quantitative figures are irrigation-led, so the visual center of gravity matches
the paper's feedback structure without making a causal claim:

```text
general measurement dependency
            |
            v
primary coupled irrigation evidence: rule -> world state -> denominator
            |
            v
secondary Flood boundary check in one table, not a co-primary panel
```

This is the intended balance. Adding a Flood mechanism panel would give the
reader equal visual weight for a setting that lacks the irrigation feedback
loop and is not seed-paired to it. It would invite a stronger comparison than
the evidence supports. The retired Panel D is therefore not part of the ICLR
package.

## Example-balance rule

The water-resource simulation is an instance of the problem, not the paper's
claim about all water agents. Irrigation earns the main visual and quantitative
space because it contains the feedback loop needed for the paper's central
diagnosis: an executed action changes the reservoir, and the later state enters
the next agent context. Flood has one narrower job: it provides a bounded
cross-testbed check that the large irrigation contrast is not automatically a
property of every setting in the corpus. It is therefore reported in one table
and described with its different action ontology, feedback structure, field
name, seed matching, audit coverage, and manifest seed-ID disagreement. We do not
call it a co-primary control or give it a mechanism panel. This keeps the example
concrete while keeping the claim at the level of measurement validity in governed
LLM-agent evaluation.

The same rule applies within each display: Figure 1 abstracts away from water
and shows the reusable dependency; Figures 2--4 use irrigation because they
answer progressively more specific empirical questions; Table 3 carries the
Flood boundary check without suggesting that the two settings form a matched
mechanism comparison.

## Figure-to-text order

The manuscript introduces Figure 1 in the Introduction immediately after the
80/100 arithmetic example. This follows the CS convention that the first
figure appears when the reader first needs the system-level dependency. The
methods then use Figure 2 to define the validator inputs. The world-state
section uses Figure 3 for the anchor diagnosis. The denominator section uses
Figure 4 for the primary executed-action comparison. Table 3 is introduced as
a secondary boundary check after the primary irrigation result, not before it.

The caption contracts are:

1. Figure 1 names the direct retry return to `Agent response`, the default
   branch, the final executed record, and the shared condition route. It also
   states that the first pre-retry response is unavailable.
2. Figure 2 names all panels: rule-layer shares, model-by-arm blocked shares,
   and proposed-action mix. It explicitly says that the display identifies
   validator inputs rather than a behavioral or causal effect.
3. Figure 3 names the yearly contrast, world-state trajectories, and
   never-retried subset. It states why Flood is not combined with this figure.
4. Figure 4 names the executed-action endpoints, the direction of the gap,
   and the fact that neither endpoint is an automatic correction.

## Visual quality gate

Figure 1 is the generated non-data asset
`figures/assets/figure1_architecture_agentpaper_shared_condition_v6_retry_return.png`.
Its visual grammar is intentionally compact: one dominant left-to-right
execution path, a small AI cue inside the Agent response card, an explicit
Validator interface, a separate record path, short edge labels, black borders
and arrows, and semantic fills. Blue denotes agent output, orange validation,
green the environment, violet measurement, and amber the shared condition.
The warm-gray canvas is neutral; it carries no data meaning.

The v6 correction removed the detached `retry / re-ask` pill and made the
return arrow terminate at `Agent response`. The active, print, and source
copies are hash-identical. The geometry checker passes its machine-verifiable
checks and requires the documented visual review because the asset is a
generated raster. Full-size and paper-width inspection show no text-arrow or
text-border collision. Figures 2--4 remain deterministic, data-bearing plots;
they are not image-generated substitutes for quantitative evidence.

## Literature and positioning check

The Introduction uses four literature functions rather than a catalogue:

1. Agent evaluation is interactive and process-dependent, not only a final
   success score (`AgentBench`, `AgentBoard`, `WebArena`, and `SWE-bench`).
2. Agent loops and tool interaction make runtime feedback part of the system
   (`ReAct`, `Reflexion`, `AutoGen`, and `tau`-bench).
3. Runtime enforcement can inspect or constrain model output (`NeMo
   Guardrails` and `AgentSpec`).
4. Construct-validity and benchmark-rigor work motivate checking whether the
   recorded score measures the stated behavior (`Measuring What Matters`,
   `AI Agents That Matter`, and the Agentic Benchmark Checklist).

The gap statement is specific: existing work motivates interactive evaluation,
runtime enforcement, and construct validity, but the manuscript tests the case
where the evaluated agent writes the condition that selects its own scored
records. The literature is evidence for the problem setting, not evidence for
the manuscript's numerical results. The 23 cited entries and their claim-level
locators are recorded in `REFERENCE_AUDIT.md`; no bibliography metadata blocker
remains in the current package.

## Evidence and readiness status

The frozen manuscript checks currently pass for citation-key matching, figure
paths, key evidence values, the executed-action primary reading, and the
generated Figure 1 asset. The official TeX build produces nine main-text
pages and two reference pages, within the current nine-page main-text limit,
with no undefined citations or overfull boxes.

The following are still submission blockers or caveats, not reasons to hide the
paper's limitations:

- Cloud's additional experiments remain outside the manuscript until the
  operational handoff releases their provenance.
- The completed first-attempt branch is governed-only and fails the clean
  provenance gate; without a matched no-validator arm it cannot support a
  between-arm appraisal-drift claim. `EXPERIMENT_AUDIT.md` records the result
  without changing the frozen manuscript.
- The historical reproducibility audit is RED: the available 42-run history
  has no clean committed run. The manuscript reports this rather than claiming
  bitwise reproducibility.
- The current mock command does not exercise the scripted LLM seam and therefore
  is not a passing verification-ladder Gate 2 result. A valid scripted mock
  smoke test must be run or explicitly marked unavailable.
- The irrigation prompt configuration emits a strict-validation warning for
  the unused relaxed profile. This belongs to the examples/ owner and must not
  be changed while the live experiment fence is active.
- Coupled runs use one worker, but the general CLI still exposes larger worker
  counts. The paper should retain the worker-1 boundary unless a multi-worker
  coupling proof is added. The read-only contract review is recorded in
  `COUPLING_AUDIT.md`; it supports the paper's annual feedback-loop reading but
  does not justify a generic parallel-safety claim.
- ICLR author metadata, reciprocal-review, quota, anonymity, and final
  dual-submission checks occur at submission time.

Current verdict: **paper package is structurally coherent and figure-ready for
the frozen evidence, but not yet final-upload ready until the provenance and
submission-time gates are closed.**
