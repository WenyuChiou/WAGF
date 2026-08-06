# Academic and CS workshop review — 2026-08-04

## Scope

This review applies the academic-writing workflow to the active source, evidence scripts, figures, and
submission build. It covers top-down argument structure, bottom-up evidence-to-claim alignment,
plain-language prose, figure/caption agreement, provenance, and delivery integrity. Historical
`CODEX_REVIEW.md` and `SUBMISSION_READINESS.md` are treated as prior decisions, not as current evidence.

## Paper identity and importance

The paper studies conformance metrics for runtime-governed LLM agents when a rule condition is emitted by
the agent in the same response as the action. The central CS problem is an estimand/construct-validity
problem: enforcement can change both the proposed action and the later set of decisions satisfying the
condition used by the metric. The contribution is a bounded warning plus a reporting protocol, not a new
governance algorithm or a causal estimate of model behavior.

The active title is:

> When Guardrails Change What Gets Counted: Conformance Metrics with Agent-Reported Rule Conditions

## Review findings

The argument chain is now explicit: paired validator-on/off simulations → rule-layer decomposition →
reported-condition prevalence → descriptive world-state reweighting → design-fixed denominator comparison
→ reporting prescription. The primary HIGH-scarcity statistic is explicitly described as a marginal proxy
that is a superset of the full HIGH-scarcity/HIGH-coping rule condition; the conjunction and coping marginal
are reported separately.

The world-state analysis is explicitly limited to descriptive reweighting. The state is independent of the
current generation's text but downstream of validator status, so the residual is not a causal adjustment
and does not identify equal reporting probabilities within each world. The never-retried comparison is now
a sensitivity check, not a bound: the two arms enter that subset through different, treatment-affected
filters.

The figures remain clean at print size. Figure 1 is an image-generated flat-icon concept schematic with
black borders, restrained color fills, short labels, and non-overlapping directed arrows. Figures 2–4 are
deterministic data figures; their captions state denominators, inferential units, coverage, and the limits
of the displayed comparisons. The rendered Introduction now previews Figure 1 before the figure appears,
and Figure 2 and Figure 4 no longer encode a stronger causal/mechanistic claim than the manuscript supports.

The paragraph audit found seven Introduction paragraphs, with a maximum of 133 words, and no body prose
paragraph above 150 words after excluding captions and tables. The abstract is 251 words; it remains a single
compact evidence summary rather than a second Introduction, while the longer figure captions carry the
denominator and scope details needed for standalone reading.

## Independent reviewer synthesis

- Hegel: WEAK REJECT before revision; identified post-treatment reweighting, never-retried selection,
  marginal-versus-conjunctive construct mismatch, and source-run provenance as the main risks.
- Popper: CONDITIONAL before final propagation; confirmed the same S3 validity and delivery issues, plus
  incomplete RQ visibility, flood over-interpretation, and unadjusted exploratory yearwise tests. The final
  source/PDF hash refresh and Introduction rewrite close the delivery and visibility findings.
- Einstein: adversarial A/B review was CONDITIONAL after the final source audit. It identified and
  closed the duplicate abstract interval and terminology overclaims. The official TAE CFP is now
  verified, and provenance is recorded as a venue-limited waiver rather than a hidden pass.

## Release conditions and decisions

1. The WAGF reproducibility audit remains RED for the identifying corpus because dirty and minimal manifests
   prevent a clean code-state-linked source-run reproduction for every run. This is explicitly disclosed,
   and no bitwise-reproducibility claim is made. Under the official TAE CFP it is a scientific limitation,
   not an upload-format blocker; the project-state issue is therefore WAIVED, not falsely marked resolved.
2. The official TAE CFP was checked at <https://tai-eval.github.io/cfp/>. It requires an anonymized NeurIPS
   workshop PDF, `dblblindworkshop`, the explicit TAE workshoptitle, up to 8 body pages, and one PDF through
   OpenReview. The generated source and the new venue gate match those requirements.
3. `manuscript_state.json` hashes and the measured gate output were refreshed after the final successful
   build; the exact hashes and gate record are preserved in `analysis/release_manifest_2026-08-05.json`.
   The CFP does not state a dual-submission permission or prohibition, so this release record makes no
   inference on that policy question.

## Readiness rule

The package is ready to submit to the named TAE workshop after the final eight-gate build completed. It should
not be described as fully reproducible or as identifying a causal within-world reporting effect. A different
venue with a mandatory clean artifact package would require new or cleanly recorded runs.

## Functional-completeness retrospective

Scope covered: active Markdown source, generated TeX/PDF, evidence scripts, four figures, state record,
release manifest, official TAE CFP, WAGF reproducibility audit, and full broker/tests pytest suite.

Authority and locks: verified run files and current manuscript remain authoritative; historical review files
were used only as prior decisions; the official CFP supersedes the local handover for venue requirements.

Alignment: all three research questions have a method, evidence, bounded answer, limitation, and reporting
contribution; the abstract, figures, captions, and conclusion use the same scope.

Adapters and overlays: academic-writing managed-project workflow, computational/LLM review module, WAGF
reproducibility checker, and official TAE venue overlay were applied.

Change propagation: source, generated PDF, gate, state, review memo, provenance decision, and release manifest
were rechecked after the plain-language Introduction/Figure 1 rewrite, including the fresh PDF and figure hashes.

Deterministic and visual checks: 15/15 evidence scripts, full `python -m pytest broker/ tests/ -q`, PDF build,
page/font/anonymity/citation checks, and print-size visual inspection were performed; the historical
provenance RED result remains explicit.

Open issues and unknowns: no open upload blocker; one S3 provenance issue is WAIVED with remaining risk.

Readiness: READY_TO_SUBMIT for the named TAE workshop PDF, with no claim of full bitwise reproducibility or
causal within-world identification.
