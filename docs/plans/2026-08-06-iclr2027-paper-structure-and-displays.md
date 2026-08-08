# ICLR 2027 paper structure and display plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give the active ICLR 2027 WAGF paper a compact, reviewer-readable argument structure in which every paragraph, figure, and table has one explicit job.

**Architecture:** The paper moves from the measurement problem, to the governed-agent loop, to primary irrigation evidence, to a descriptive world-state diagnosis, and finally to a reporting protocol. Irrigation is the primary result. Flood is a secondary cross-testbed control check and must remain visually and rhetorically subordinate.

**Tech Stack:** LaTeX with the ICLR 2027 style, the frozen WAGF evidence CSVs and deterministic figure builders, `manuscript_static_check.py`, `evidence_boundary_check.py`, Figure 1 geometry checks, MiKTeX, and the academic-writing and visualization review gates.

## Scope and non-negotiable evidence boundaries

- The active package is `ICLR2027/submission`; the historical `SUBMISSION_2026/TAE` package is not edited by this plan.
- No broker code, experiment configuration, or running job is changed in this writing pass.
- The executed action is the primary action reading. The legacy final-proposal reading remains a declared sensitivity analysis only.
- World-state reweighting is descriptive, not causal, because the recorded world is downstream of governance.
- The frozen corpus does not preserve the first response before a retry; the paper cannot claim within-decision report revision.
- The paper does not claim deception, universal behavior across agents, mechanism transfer from Flood, or a causal validator effect.
- A later Cloud handoff or new run is not evidence for this release until its provenance and source-of-truth status are independently verified.

## Paragraph budget

The target is **22 argument paragraphs**, plus compact contribution/list blocks and required policy statements. A paragraph should normally make one claim, provide the evidence or citation needed for that claim, and end by handing the reader to the next claim. Definitions belong at first use; later paragraphs should use the short name.

| Major section | Target | Paragraph-by-paragraph contract |
| --- | ---: | --- |
| Abstract | 1 | **A1:** problem and why the denominator matters; **A2:** WAGF design and four readings; **A3:** primary irrigation result and descriptive world-state diagnosis; **A4:** reporting implication. These are four moves in one block, not four paragraphs. |
| Introduction | 6 + contribution list | **I1:** why governed-agent evaluation needs a defined evaluated population; define conditional score and runtime validator in plain language. **I2:** one short coding-agent example, followed by the 80/100 arithmetic; define agent-written condition. **I3:** explain impact on comparisons/rankings and the coupled-world warning; introduce Figure 1 as a conceptual dataflow. **I4:** position agent evaluation, agent loops, runtime enforcement, and construct validity; end at the unresolved measurement gap. **I5:** state WAGF, the primary irrigation design, four reported quantities, and Flood's strictly secondary role. **I6:** give only the frozen headline result, state the contribution list, scope the claims, and provide the roadmap. |
| Evaluation Setting | 3 | **E1:** governance loop, validator message, retry budget, default action, and why executed action is primary. **E2:** rule inputs and why the high-scarcity/high-coping increase is blocked; explicitly separate warning from block and agent-authored from simulator-recorded conditions; point to Figure 2. **E3:** paired runs, irrigation-first sample, Flood control boundary, estimands, seed unit, contrast direction, and inferential procedure. |
| The Denominator Moves | 3 | **D1:** anchor irrigation cell: condition share and executed conditional rate move together. **D2:** all five irrigation configurations and Table 1; keep the main claim about the primary setting. **D3:** Flood as a bounded, descriptive control check with Table 2; state why its different action ontology, feedback, and matching prevent a mechanism claim. Figure 2 belongs after the rule-layer explanation, not as a Flood comparison. |
| World-State Composition as a Descriptive Mechanism | 3 | **W1:** define the recorded-world stratification and direct-standardization calculation; state the descriptive limitation before results. **W2:** report anchor reweighting and coverage; interpret the remaining difference without causal language; Table 3 supplies diagnostics. **W3:** explain matched Year 1, later trajectory divergence, and the never-retried sensitivity subset as evidence about composition rather than proof of a mechanism; Figure 3 summarizes only primary irrigation. |
| Different Denominators and Action Readings | 2 | **R1:** distinguish conditional and all-decision questions and define why neither is automatically the correction. **R2:** report the five-cell executed-action gap and the limited legacy proposal-reading sensitivity; Figure 4 visualizes direction and magnitude without adding a new estimand. |
| Reporting Protocol and Limitations | 3 | **P1:** give the minimal reporting checklist: condition share, independent world record, all-decision rate, first response/validation message, and trajectory. **P2:** explain why replacing an agent report with a world-recorded condition measures a different quantity. **P3:** consolidate first-response, downstream-world, model-scope, historical-run, and Flood limitations; do not repeat the same caveat in multiple sections. |
| Conclusion | 2 | **C1:** restate the narrow finding: governance can change both execution and the scored population. **C2:** state the usable practice: show the denominator, pair it with an all-decision reading when available, and treat the contrast as an object of audit rather than an automatic causal estimator. |
| AI, ethics, reproducibility statements | separate blocks | Required venue statements; they are not counted as argument paragraphs and must not introduce new scientific claims. |

This budget deliberately compresses the current introduction and limitations prose. It keeps the logical chain visible without turning every caveat into a separate paragraph.

## Current checkpoint: 2026-08-08

- The Introduction prose pass is complete: six prose paragraphs plus the contribution list.
- The introduction now uses a coupled water-resource simulation as its empirical example and does not name the internal framework.
- The paragraph openings follow why -> example -> consequence -> literature gap -> empirical design -> finding and scope.
- The introduction contains 10 unique cited works, concentrated in the background and gap paragraphs; the result paragraphs do not add background citations.
- The downstream prose/display polish pass is complete on the frozen corpus. Figure 1 is named and interpreted in the Introduction; the rule explanation separates the two-condition block from the broader scarcity metric; Flood is explicitly secondary; and the world-state section uses descriptive, non-causal language.
- The active figures were visually rechecked at full size and thumbnail size. No image asset was regenerated because Figure 1 already satisfies the reviewed icon, semantic-fill, black-arrow, and endpoint requirements, while Figures 2--4 are evidence-bearing plots that must remain deterministic.
- Cloud's four additional experiments remain outside this release. Their numbers, traces, and any new fields must not enter the manuscript, figures, tables, or claims until a handoff explicitly releases provenance and source-of-truth status.
- Static, evidence-boundary, and Figure 1 geometry checks pass. The TeX build produces 10 pages total, with the ICLR main-text limit still subject to the existing page audit.
- The full manuscript, figures, tables, bibliography, and release metadata still require the later integration and release passes.

## Figure and table allocation

The release keeps **four figures and three tables**. No new display is justified until a reviewer-facing gap is tied to a source CSV or a reproducible calculation.

| Display | Primary job | Placement and content boundary |
| --- | --- | --- |
| Figure 1, `fig:concept` | Explain the core dependency before any result: the agent writes a condition that participates in both runtime handling and record selection. | Introduction. Conceptual only; no result numbers. Use the generated agent-response/validator/environment/log/measurement composition, short labels, black arrows with unambiguous endpoints, semantic colored fills, and a compact retry/default branch. It must not imply that high scarcity alone is blocked or that the missing first response is observed. |
| Table 1, `tab:irrigation` | Provide exact primary per-configuration condition shares and executed conditional rates. | Denominator section, immediately after the five-cell primary result. Irrigation rows first and only; keep condition share and executed conditional rate together. The all-decision rate is referenced in Figure 4 rather than duplicated as an unreadable extra column. |
| Table 2, `tab:cross_testbed` | Bound the secondary Flood comparison. | Denominator section after the primary irrigation result. Label it "secondary cross-testbed control check," use ranges, and state the non-comparability in the caption. Flood must not receive a standalone figure or a visually equal mechanism panel. |
| Figure 2, `fig:layers` | Show what the validator actually reads and which rejection layer contains the studied rule. | Evaluation/denominator transition. Evidence-bearing rule decomposition, not a workflow overview and not a causal diagram. It must explain why the block requires the two-condition pair and why high scarcity alone is only a warning. |
| Figure 3, `fig:mechanism` | Diagnose whether the primary irrigation contrast is associated with recorded-world composition and downstream trajectory divergence. | World-state section. Three irrigation panels only: yearly contrast, recorded trajectories, and never-retried sensitivity. Include the matched Year 1 interpretation in the caption/text. Do not add a Flood panel; Table 2 is its deliberate boundary. |
| Table 3, `tab:world` | Give the reweighting estimates and coverage needed to audit Figure 3. | World-state section. Define pooled versus per-seed values and coverage in the caption. No causal-adjustment wording. |
| Figure 4, `fig:consequence` | Make the conditional-versus-all-decision executed-action gap immediately visible. | Denominator/action-reading section. Use the current endpoint/slope design, with the arrow pointing to the all-decision endpoint and one clear sentence explaining four cells versus one. Do not plot the legacy proposal reading as a competing headline. |

### Shared display rules

1. Every caption starts with the display's takeaway, then defines the quantities, then states the boundary or limitation that prevents over-reading it.
2. Every arrow has one semantic purpose and a visible endpoint. No arrow may cross an unrelated card, and no label may cover another label, border, or arrow.
3. Color is functional: agent response, validation, environment, measurement, and the shared condition keep stable roles. Decorative background fills are not allowed.
4. Figure 1 may use compact icons because it introduces an AI-agent architecture; quantitative figures should privilege data marks over decorative icons.
5. Flood remains subordinate in size, position, wording, and claim strength. A panel comparing Flood with irrigation is not part of this release because it invites a false symmetry.
6. Tables should expose the denominator and action reading rather than repeat prose. If a column cannot be read at thumbnail size, it is a candidate for removal or relocation to the supplement.

## Academic-writing review gates

The manuscript will be reviewed in four passes, following the academic-writing skill:

1. **Argument and structure:** verify the why-to-what-to-how chain, one job per section, the introduction's six-paragraph budget, and explicit links from Figure 1 to the later estimands.
2. **Evidence and scope:** map every number to frozen evidence; distinguish descriptive comparison from causal inference; keep Flood, reweighting, retry history, and the legacy proposal reading within their declared boundaries.
3. **Scholarly prose:** define technical terms at first use, shorten long sentences, replace opaque labels with plain-language explanations, remove AI-sounding repetition, and ensure each paragraph has a claim/evidence/bridge contract.
4. **Delivery integrity:** run static checks, evidence-boundary checks, Figure 1 geometry checks, citation checks, and a clean MiKTeX build; inspect the rendered PDF and figure thumbnails for clipping, overlap, unreadable labels, and page-limit compliance.

## Implementation order and commit record

The work proceeds in small, reviewable commits:

1. **Structure checkpoint (completed):** save this structure/display contract; preserve the Introduction v2 checkpoint and its regenerated static report; stage only active-package files.
2. **Prose pass (Introduction and frozen downstream polish completed):** compress the Introduction to six prose paragraphs, use the coupled water-resource example without naming the internal framework, and polish the downstream rule, denominator, world-state, action-reading, limitation, and conclusion prose without changing evidence values.
3. **Display pass (caption/placement audit completed; asset regeneration deferred):** audit captions, labels, color roles, arrow endpoints, and figure/table placement; regenerate only from the canonical active builders if a visual defect or released data change requires it.
4. **Reference pass:** expand or replace citations only when a source directly supports the paragraph's claim; rerun citation and evidence checks.
5. **Release pass:** perform an independent reviewer-style read, rebuild the PDF, inspect the final artifact, and record the final readiness decision. The package remains `WORKING` until this gate passes.

The commit for this planning round must contain a descriptive subject and identify the academic-writing review gate in the body. Unrelated dirty files in the shared workspace must remain unstaged.

## Acceptance criteria for the next prose/display pass

- The reader can state the paper's value after the introduction: a governed agent can change the scored population through an agent-authored condition, so the denominator must be reported and audited.
- The primary irrigation result is visibly primary; Flood is visibly secondary and never carries the mechanism claim.
- Figure 1 answers "what is being coupled?" Figure 2 answers "what rule is blocking?" Figure 3 answers "what world-state composition accompanies the contrast?" Figure 4 answers "how does the denominator change the action reading?"
- Each table has a distinct audit function and no table duplicates a figure without adding exact values or coverage.
- No paragraph relies on an unexplained acronym, a long unbounded sentence, an unsupported number, or a stronger claim than the frozen evidence permits.
