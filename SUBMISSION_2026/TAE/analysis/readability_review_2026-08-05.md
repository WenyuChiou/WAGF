# WAGF TAE Workshop Readability and Submission Review

**Date:** 2026-08-05  
**Scope:** final plain-language revision of the TAE workshop manuscript  
**Audience:** CS and AI-agent evaluation reviewers  
**Source of truth:** `paper/manuscript.md`  
**Delivery artifact:** `paper/manuscript.pdf`

## Executive verdict

The manuscript is submission-gate ready for the TAE workshop. The revision now makes the
core problem visible before introducing the method: a guardrail can change an agent-written
rule condition, and that same condition can determine which decisions enter the reported
metric. The paper then moves from the problem to the paired simulation design, the bounded
decomposition, the denominator comparison, and a practical reporting protocol.

This is a release-readiness judgment, not a prediction of acceptance. The paper remains a
descriptive construct-validity study rather than a causal estimate, a deception study, or a
claim about every model and governance stack. The reproducibility audit remains RED because
27 enriched manifests are dirty and 15 identifying runs are minimal. That limitation is
explicit in the manuscript and is recorded as a narrowly scoped waiver for this PDF-only,
non-archival workshop submission.

## Revision method

The revision used four checks from the academic-writing workflow:

1. **Argument structure:** make the why important before the what and how; place the concrete
   irrigation example before the formal research questions; make each section answer the
   question raised by the previous section.
2. **Evidence and scope:** retain the existing evidence markers, numerical values, tables,
   figures, bibliography, and noncausal boundaries; do not add an unsupported experiment or
   claim.
3. **Scholarly prose:** define technical terms at first use, replace internal marker names in
   reader-facing text, split long sentences, and use conventional CS wording where possible.
4. **Delivery and review:** rebuild the PDF and DOCX from the master source, inspect figures
   and pages at print size, run the evidence pipeline, and run the venue submission gate.

A separate long-context readability pass was used as an adversarial input. Its wording was not
accepted wholesale: the final text was reconciled manually against the source claims and the
submission gate, including citation syntax and the distinction between paired seeds and action
counts.

## Readability change measured from the source

The following is a diagnostic sentence-length comparison. The parser excludes headings,
comments, Markdown tables, and figure/table caption paragraphs, and normalizes protected
`CLAIM` markers. It is useful for locating prose risk, but it is not a canonical readability
score.

| Diagnostic | Before revision | Current revision |
|---|---:|---:|
| Body words | 4,493 | 4,485 |
| Sentences | 168 | 242 |
| Median sentence length | 19 words | 13 words |
| 75th percentile | 25 words | 17 words |
| 90th percentile | 31 words | 20 words |
| 95th percentile | 33 words | 23 words |
| 99th percentile | 37 words | 27 words |
| Sentences with at least 35 words | 7 | 0 |
| Maximum sentence length | 50 words | 32 words |

The sentence count increased because long multi-clause sentences were deliberately divided
into shorter claims. The revision therefore improves local readability without materially
shortening the evidence-bearing content.

## Argument chain and section architecture

The paper now follows this chain:

**Why:** a conditional conformance metric can change because enforcement changes the condition
that selects its denominator.  
**What:** paired validator-on/off simulations test whether the reported condition and the rate
computed on it move together.  
**How:** the paper separates agent-reported inputs from simulator-recorded inputs, decomposes
the anchor result descriptively by recorded world state, and compares the conditional rate with
a design-fixed denominator.  
**What the evidence says:** condition prevalence can move more than the conditional rate; a
common recorded-world distribution removes much of the anchor contrast but does not identify a
causal effect; changing the denominator changes the estimand and can even reverse the sign.  
**What a reviewer should take away:** report condition prevalence, the independent world record,
and a rate over every decision beside the conditional rate when the design permits it.

| Section | Job in the argument | Connection to the next section |
|---|---|---|
| Abstract | States the problem, design, main numbers, boundary, and recommendation in that order. | Gives the reader a reason to read the introduction. |
| 1. Introduction | Opens with the why, defines LLM, validator, conformance rate, and agent-reported condition, then gives the irrigation example, prior-work context, questions, and contributions. | Figure 1 makes the feedback loop concrete before the formal setup. |
| 2. Experimental Setup | Defines the shared retry loop, the full conjunction and marginal proxy, the two testbeds, and paired cells/seeds. | Establishes exactly which inputs are agent-written and which are simulator-recorded. |
| 3. Rule Inputs | Separates agent-reported state from world-recorded state and explains the denominator created by each rule type. | Makes the prevalence and conditional-rate comparison in Section 4 interpretable. |
| 4. Enforcement Changes the Reported Condition | Reports the prevalence shift and conditional-rate shift, then separates rule layers and testbed scope. | Motivates the mechanism check rather than treating prevalence change as a causal explanation. |
| 5. Recorded-World Reweighting | Uses a bounded, descriptive common-world reweighting on the anchor cell and states what it cannot identify. | Shows why the remaining question is about the metric's denominator, not only the mechanism. |
| 6. Changing the Denominator | Compares the conditional and design-fixed rates, including the sign reversal and sensitivity reading. | Converts the finding into a reporting protocol. |
| 7. Reporting Protocol | Gives an actionable minimum report for evaluations with agent-authored conditions. | Makes the contribution useful beyond this particular simulation. |
| 8. Limitations | Names missing first-attempt logs, downstream world state, coverage loss, testbed confounding, and provenance limits. | Prevents the conclusion from overreaching. |
| 9. Conclusion and Artifact Availability | Restates the scoped lesson and accurately describes the current release artifact. | Closes with a defensible workshop-level claim. |

## Figure-to-text alignment

The figures now have distinct jobs rather than repeating the same workflow.

| Figure | Reviewer question it answers | Text that prepares the reader |
|---|---|---|
| Figure 1 | How can a guardrail change what a metric counts? | Introduction defines the answer record, validator retry, and shared reported condition before the caption. |
| Figure 2 | Which rule layers read the report, and what records are being counted? | Sections 2--4 distinguish all decisions, blocked subsets, rule types, and their denominators. |
| Figure 3 | Can a recorded-world composition check explain the anchor contrast? | Section 5 defines the reweighting ladder, coverage, residual, and descriptive scope before the figure. |
| Figure 4 | What changes when the denominator is fixed? | Section 6 defines conditional rate, all-decision rate, estimand, and the sensitivity reading before the figure. |

Figure 1 is deliberately conceptual and not presented as a data figure. It uses a compact
flat-icon visual register: one answer record, a separated validator gate, a measurement lens,
short labels, and explicit arrow targets. The figure does not supply numbers or replace the
quantitative data figures. The manuscript mentions it in the introduction before the rendered
callout, which is the conventional CS reading order for a figure that explains the paper's
central idea.

## Terminology audit

The current wording uses a technical term only when it earns explanatory work. The first use
is paired with a plain definition.

| Term | First-use explanation | Why it is retained |
|---|---|---|
| LLM | “large language model (LLM)” | Standard CS term; the abbreviation is used only after expansion. |
| Validator | Component that applies a rule, identifies a violation, and requests a retry. | Standard agent/runtime terminology and needed to name the intervention component. |
| Conformance rate | Share of decisions that satisfy a rule. | The paper's central metric; the plain definition appears before the formal comparison. |
| Agent-reported condition | A label written by the agent in the same response as the action. | Names the construct-validity problem without implying hidden intent or deception. |
| World state | Environment condition recorded by the simulator. | Separates an external record from the agent's report. |
| Full conjunction | The rule requiring both high scarcity and high coping. | Retained because the paper compares the conjunction with the scarcity-only marginal proxy. |
| Marginal proxy | A simpler condition that includes the full conjunction and additional cases. | Needed to explain why the reported scarcity condition is not identical to the enforced rule. |
| Estimand | The quantity being estimated. | Retained once in Section 6 because the denominator comparison is a standard statistical distinction. |
| LAST-PROPOSED | The final proposed action retained by the existing analysis convention. | Protected evidence-reading label; the prose defines it before using the sensitivity comparison. |

Terms such as “antecedent,” “de-conditioning,” and “inferential unit” are not used as unexplained
shortcuts in the revised reader-facing prose. The protected seed-level meaning remains in the
state ledger and the evidence-backed analysis.

## Citation and literature support

No new citation was inserted during the readability pass because the existing verified
bibliography already supports the claims made in the revised introduction:

- **[1]--[4]:** runtime guardrails, validators, and agent evaluation infrastructure;
- **[5]--[8]:** machine-readable norms, institutions, and rule-based agent governance;
- **[9]--[10]:** variables observed after intervention and the causal-method caution against
  treating treatment-affected variables as independent controls;
- **[11]:** the Protection Motivation Theory flood testbed;
- **[12]--[14]:** benchmark interpretation, evaluation conditions, and construct validity.

The citations remain individual `[n]` tokens rather than compressed ranges because the local
submission gate verifies the cited numeric sequence directly. The final build reports 17
bibliography entries, 14 cited entries, and contiguous body citations `[1]` through `[14]`.

## Four-perspective reviewer check

### 1. CS/AI-agent reviewer

**Strength:** The paper identifies a concrete interface-level failure mode in runtime agent
evaluation: the rule reads a field that is also produced by the system being evaluated. The
contribution is a construct-validity warning plus a low-cost reporting protocol, not a claim to
invent a new agent architecture. That scope fits a trust-and-evaluation workshop.

**Risk:** The work is simulation-based and the empirical setting is narrow. The manuscript now
states this directly, separates the irrigation anchor from the flood portability demonstration,
and avoids claiming cross-testbed identification.

### 2. Academic-writing reviewer

**Strength:** The introduction is why-first, the example appears before the formal questions,
technical terms are defined at first use, and each section answers the question raised by the
previous section. The prose audit found no body sentence at or above 35 words under the stated
diagnostic.

**Risk:** Some repetition of “conditional rate,” “agent-reported condition,” and “world state”
is necessary for figure and table captions to stand alone. Those repetitions are intentional
reader aids, not filler.

### 3. Methods and reproducibility reviewer

**Strength:** The paper preserves paired arms, seed-level interpretation, claim markers,
denominator definitions, coverage, residuals, and all stated nonclaims. The evidence pipeline
rebuilds the current tables and figures without GPU or network.

**Risk:** Historic source-run provenance is incomplete; first attempts are not logged; the world
state is downstream of enforcement; and fine strata lose coverage. These are now explicit in the
abstract, Section 5, Section 8, and artifact statement. They are limitations, not reasons to
call the current PDF unreleasable under the TAE CFP.

### 4. Figure and venue reviewer

**Strength:** The figures have non-overlapping roles, standalone captions, clean arrow targets,
and matching terminology. The final PDF is anonymous, uses the required workshop option and
title, stays within the body-page limit, and has no forbidden Type 3 fonts.

**Risk:** Figure 1 is a conceptual schematic rather than a quantitative result. Its purpose is
to orient the reviewer to the paper's central problem; Figures 2--4 carry the evidence. The
caption explicitly prevents Figure 1 from being read as a data figure.

## Source fidelity and change boundary

The final master preserves all 98 `CLAIM` markers, all claim values and definitions, the
heading structure, all four figure markers, the two table blocks, and the bibliography block.
The revision changes exposition, paragraph order, definitions, captions, and transitions. It
does not add an experiment, change a result, add a new model, or introduce a new causal claim.

## Remaining optional work

No new experiment is required for the current PDF-only workshop submission gate. If a later
revision or artifact track permits additional work, the highest-value additions would be:

1. log the first attempted response separately from the final accepted response;
2. add an untreated-trajectory or frozen-world branch to distinguish treatment effects from
   downstream world-state composition; and
3. repair the dirty/minimal manifests so that historic source-run reproduction can be checked
   rather than only current table/figure regeneration.

These additions would strengthen identification and reproducibility. They are not silently
claimed by the current paper.

## Final measured release evidence

The final on-disk release gate reports:

- evidence: **15/15 scripts PASS**;
- figures: **4/4 referenced figures present and current**;
- build: **0 LaTeX errors and 0 overfull boxes**;
- venue: **TAE workshop option/title and CFP contract PASS**;
- pages: **9 total pages, body ends on page 8, references start on page 9**;
- fonts: **11 embedded fonts: 8 Type 1 and 3 TrueType; 0 Type 3**;
- anonymity: **PASS**;
- citations: **17 bibliography entries, 14 cited, body uses [1]--[14]**.

**Release conclusion:** ready to submit as a TAE workshop PDF, with the reproducibility and
causal limitations stated plainly. Acceptance remains a reviewer decision.
