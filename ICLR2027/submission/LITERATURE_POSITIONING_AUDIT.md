# Literature and contribution positioning audit

Updated 2026-08-08. This audit applies the academic-writing and senior-author
review rules to the ICLR manuscript. It checks whether the Introduction uses
literature to build a logic chain rather than to list popular agent systems.

## One-sentence paper position

The paper shows that a runtime-governed LLM-agent evaluation can change its
conditional score by changing which agent decisions satisfy the condition that
defines the scored population, and it gives a reporting protocol that makes
that dependency visible.

This is a measurement-validity contribution demonstrated with a coupled
water-resource simulation. It is not a new validator, a new benchmark, a
causal estimate of governance, or a claim that the agent is deceptive.

## Literature functions in the current Introduction

| Function in the argument | Current sources | Why the sources are needed | What the paper adds beyond them |
| --- | --- | --- | --- |
| Agent evaluation is interactive and multi-dimensional | AgentBench, AgentBoard, WebArena, SWE-bench, `\tau`-bench | Establishes that agent scores depend on tools, trajectories, state, and task outcomes | Audits the population entering a conditional score when that population is agent-authored |
| Agent behavior includes action, feedback, and repeated context | ReAct, Reflexion, AutoGen, SWE-agent, `\tau`-bench | Establishes the loop in which a response can affect later inputs and records | Connects that loop to the score denominator rather than only to task success |
| Runtime systems inspect or constrain responses | NeMo Guardrails, AgentSpec | Establishes that a response can be checked before execution and re-asked | Identifies the same response field as both an enforcement input and a selection variable |
| Scores need construct and benchmark validity | AI Agents That Matter, Measuring What Matters, Agentic Benchmark Checklist, Rosenbaum | Provides the measurement and conditioning vocabulary | Tests the specific shared-condition failure mode and reports both conditional and all-decision endpoints |

The current bibliography has 15 cited entries, all used by a claim sentence and
all verified in `REFERENCE_AUDIT.md`. This is enough for a concise ICLR
Introduction because the sources cover the four functions above without
turning the section into a survey. Adding more framework names would not fill
the paper's gap unless they directly study a score-defining field that is also
consumed by runtime enforcement.

## Fresh adjacent-literature scan

The following primary sources were checked during this pass:

| Source | What it contributes to the field | Decision for this manuscript |
| --- | --- | --- |
| [AgentDojo, NeurIPS 2024](https://proceedings.nips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html) | Dynamic agent environments and security evaluation over tool outputs | Reviewed but not added; current AgentBench/WebArena/`\tau`-bench citations already support the interactive-setting sentence, while AgentDojo's prompt-injection target is not the paper's metric gap |
| [AgentIF, NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/hash/51bb3a8a33610a25aae074bfc51b1b1f-Abstract-Datasets_and_Benchmarks_Track.html) | Constraint-level instruction-following evaluation in agentic scenarios | Reviewed but not added; it evaluates instruction adherence, not a runtime-selected denominator |
| [GUITAR, ACL ARR 2026](https://openreview.net/forum?id=QHqd5m6Wcv) | State/transition diagnostics for frequency-weighted GUI-agent scores | Reviewed as a conceptual neighbor, but not cited because the current record is an ARR submission rather than a stable archival venue and the paper uses a different failure mode |
| Agentic Benchmark Checklist | Benchmark design and reward choices can distort measured performance | Already included as `zhu2025abc`; it supplies the closest general benchmark-rigor support |

The scan therefore does not require a new citation or a new related-work
subsection. The gap is specific enough that a longer bibliography would dilute
the Introduction's why-to-gap progression.

## Introduction logic audit

The current seven-paragraph funnel has the following jobs:

1. State why the scored population matters and define a conditional score.
2. Give one concrete coupled water example, including the retry/default path.
3. Give a small arithmetic example so the denominator change is immediately
   checkable, then introduce Figure 1.
4. Use the literature to establish interactive evaluation, feedback loops,
   runtime enforcement, and construct validity.
5. Pivot with the unresolved case: the agent writes the condition that selects
   its own scored records.
6. State the primary irrigation design and keep Flood in a secondary boundary
   role.
7. State the measured result, the non-claims, the roadmap, and the three
   contributions.

This order follows why -> concrete example -> mechanism -> literature gap ->
what we did -> what we found -> contribution. Figure 1 appears directly after
the arithmetic example because that is the first point at which a reader needs
the complete shared-condition dependency. The results figures are deferred to
the sections where their quantities are defined.

## Language and claim controls

- Use `agent-written condition`, `validator`, `executed action`, and
  `conditional rate` consistently; define each at first use.
- Prefer `changes which records are counted` over abstract phrases such as
  `alters the estimand` in the Introduction. The formal term can appear after
  the plain-language explanation.
- Keep `descriptive` beside every validator-on/off contrast and every
  reweighting result. Do not use causal, deception, gaming, manipulation, or
  universal-generalization language.
- Explain Flood as a boundary check, not as a control. Do not use equal visual
  space for two settings with different feedback and seed-matching designs.
- Keep the distinction between the full two-condition blocking rule and the
  broader high-scarcity conditioning variable visible in the methods and
  Figure 2 caption.

## Reviewer-facing contribution test

A reviewer should be able to answer three questions from the Introduction:

1. What is the practical problem? A conditional score can change because the
   condition changes the records entering the denominator.
2. What is the technical contribution? Paired coupled simulations, an
   independent recorded-world diagnosis, executed-action denominator analysis,
   and a compact reporting protocol.
3. Why should an agent-evaluation reader care? Runtime validators and dynamic
   environments make response filtering and state feedback common enough that
   score population must be treated as part of the evaluation design.

## Decision

Keep the current 15-reference bibliography and the four-function Introduction.
Make the primary/secondary example hierarchy explicit in the manuscript prose
and captions; do not add citations merely to increase the count.

## Risks

The literature does not prove the manuscript's numerical results. It only
supports the setting and the importance of measurement validity. The exact
shared-condition gap remains the paper's empirical contribution and must not be
presented as established by prior work.

## Required changes

None to the bibliography at this stage. Re-run metadata and claim-support
verification if a future revision adds AgentDojo, AgentIF, or another source.

## Next actions

1. Preserve the example hierarchy in every new figure, table, and paragraph.
2. Re-run the academic prose, evidence-boundary, and TeX checks after the
   current wording pass.
