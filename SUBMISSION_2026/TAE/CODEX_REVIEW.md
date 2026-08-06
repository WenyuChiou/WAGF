# Codex pre-submission review

Date: 2026-08-04
Review mode: composite academic-writing review, with top-down and bottom-up
passes plus four synthesized reviewer lenses.

## Executive verdict

**READY TO SUBMIT.** The final local package passes all seven delivery gates,
all 15 evidence scripts, and standalone plus print-size visual inspection. The
three conditions from the earlier review are resolved: the mechanism claim is
now residual-supported, the LLM-run inventory exposes verified metadata and
explicit absences, and Table 1 is automatically cross-checked against its
canonical CSV.

This is a delivery-ready workshop version, not a claim of bitwise LLM
reproducibility or a substitute for the author's final live-CFP check. The
release state is recorded as `READY_TO_SUBMIT` in `manuscript_state.json`. No
new experiment was required; the final pass added audit checks and narrowed
the wording to match existing evidence.

## What this review covered

The authority order was: verified evidence scripts and raw run artifacts, the
current `paper/manuscript.md`, `HANDOVER.md`, the generated figures/CSVs, and
the local submission gate. The review followed four passes:

1. argument and structure;
2. evidence, estimands, scope, and AI/LLM reproducibility;
3. scholarly prose and plain-language readability; and
4. delivery integrity and print-size visual inspection.

The final pass retained the Figure 2A reader-path repair and formal labels,
then completed the previously deferred scope and reproducibility decisions
using only verified files already in the workspace.

## Figure 2A: reader-function review

The earlier panel made the middle bar look like a third experimental arm. That
was a real comprehension problem because the panel mixed two denominators. It
is now repaired in the shipped figure:

- the outer rows are explicitly labelled `all decisions`;
- the middle row is labelled `blocked subset (n=6,469; re-based)`;
- the all-decision rows print 60.5/23.4/16.1 and 71.0/29.0 directly;
- the re-based blocked-only row prints 59.4/40.6 directly;
- the body text states that the middle row is not a third arm; and
- the caption states the anchor cell, the two outer denominators, the blocked
  subset denominator, and why the 59.4/40.6 split is the relevant within-arm
  decomposition.

The figure uses the same formal plain-language register throughout:
`blocking cause`, `proposed action`, `rule reads self-report`, and `rule reads
world state`. Panel B states the validators-on/validators-off bar order, and
Panel C states that each row uses its own blocking-rule denominator.

The one-second reading is now: "two arms are shown over all decisions; the
middle bar re-expresses only the blocked validators-on decisions." A reader who
needs the exact meaning receives it immediately in the caption rather than
having to infer it from colour or geometry. The generator reports zero text
overlap findings, and page-4 print-size inspection passed.

## Figure audit

Figure 1 now follows the preferred WAGF/GitHub register: white rounded regions,
sparse serif labels, simple line-art pictograms, one continuous pale-yellow
reported-state strip, one black `passes` route, and one restrained red
`blocked -> re-prompt` return route. A one-round adversarial design review
rejected a larger two-output flowchart because it would imply an exhaustive
retry protocol and an identified causal mediation path. The constrained hybrid
keeps one answer card and makes the two validator outcomes visible without
duplicating outputs. The caption identifies high scarcity as an illustrative
irrigation example, distinguishes the agent-authored field from simulator state,
and limits the claim to a pathway that can alter which decisions are counted.
Image generation was used for visual exploration, but the shipped schematic is
deterministic so labels and causal direction cannot drift. The caption calls the
right-hand quantity the `conformance rate`, matching the manuscript's
terminology.

Figure 3's panel titles were also shortened to `Gap is nonmonotone over time`,
`World states diverge after year 1`, and `Gap is larger without blocking`.
These labels state the plotted claim directly and leave definitions, intervals,
and limitations to the caption.

The figures are intentionally different in function:

| Figure | Job in the argument | Reviewer assessment |
|---|---|---|
| 1 | Establish the construct-validity problem before numbers | Cleanest conceptual entry point; now formal and readable |
| 2 | Separate world-feasibility and validator-rule layers | Previously confusing in panel A; repaired, still the densest taxonomy figure |
| 3 | Show the world-state/decomposition mechanism | Evidence-bearing but requires its caption for the stratification caveat |
| 4 | Show the fixed-denominator consequence | Clearest numerical consequence, including the near-zero and sign-reversal cases |

The narrative order should remain Figure 1 -> Figure 2 -> Figure 3 -> Figure 4.
The paper should not replace the data figures with image-generated artwork.

## Color, text density, and workshop-format audit

The palette is coherent and should remain restrained:

- blue/orange identify the two validator arms in the time-series panels;
- green identifies the agent-report-conditioned quantity/rule;
- purple identifies its world-side or design-fixed counterpart;
- yellow identifies the allocation-cap/precondition layer; and
- grey carries approvals, neutral structure, confidence bands, or hatches.

The meaning is never encoded by colour alone: hatches, line styles, bar order,
and captions repeat the distinction. This is suitable for grayscale printing
and common colour-vision deficiencies. Figure 1 uses a separate, deliberately
lighter visual grammar: neutral cards, one pale-yellow semantic strip, a black
pass route, and one red retry path. Adding more accent colours would make the
figure family less coherent.

Text is kept in the plot only when it answers one of three reader questions:
what is being compared, what denominator is used, or what exceptional result
must not be missed. Exact counts, confidence intervals, and methodological
caveats remain in captions or body text. The Figure 2A change follows this
rule: the denominator distinction and 59.4/40.6 split stay on the plot, while
the causal interpretation stays in the caption. Figure 3 and Figure 4 retain
their interval and near-null callouts because those are the claims a reviewer
would otherwise misread; no decorative annotations were added.

The local package follows the repository's NeurIPS-style constraints: 5.5 in
text width, 1 in margins, a 5.5 in figure canvas, 0.80 linewidth placement,
Times-compatible figure text, and a 7 pt printed minimum. The direct local gate
checks the resulting PDF, including page count, embedded fonts, and Type 3
absence. General NeurIPS 2026 guidance requires the official LaTeX style and
anonymized PDF, but the TAE-specific contribution format is not exposed by the
current OpenReview landing page. The local 8-page body guard is therefore a
conservative project constraint until the workshop chairs publish or confirm a
different contribution limit.

## Top-down argument audit

### Gap -> question

The gap is coherent and CS-relevant: a runtime governance metric can become
construct-invalid when its rule reads a state authored by the agent in the same
generation that is being scored. The paper asks whether the apparent
conformance contrast changes together with the antecedent and whether a
design-fixed denominator answers a different question.

### Question -> method

The paired validator-on/off design, rule-layer decomposition, fixed-denominator
recalculation, world-fixed decomposition, year-1 check, and never-retried
comparison are logically matched to those questions. The paper correctly
positions itself as a measurement and evaluation diagnosis, not as a new agent
algorithm.

### Method -> evidence

The evidence chain is strongest on the anchor irrigation cell. The cross-model
and flood material is useful as supporting or regime/portability evidence, but
the paper correctly does not treat the flood testbed as a negative control for
enforcement pressure. The no-action-to-environment-feedback limitation is
explicit and must remain.

### Evidence -> contribution

The defensible contribution is a bounded warning and reporting prescription:
report antecedent prevalence, an independent world record, and a design-fixed
rate beside the conditional rate. The paper must not imply that the
unconditional rate is the one corrected or true effect.

### Resolved top-down issue: mechanism wording

The final abstract/Section 5 language now says that the anchor evidence is
consistent with world-state composition as the dominant explanation while a
small within-world residual remains possible. It preserves the measured
range—−2.53 pp at 100% coverage, +0.21 pp at the finest reported rung, maximum
absolute residual 4.47 pp, and two intervals excluding zero—instead of turning
the decomposition into an exact behavioral exclusion.

## Bottom-up evidence audit

The evidence and delivery chain is unusually strong for this draft:

- corpus inventory: complete and balanced for the stated cells;
- evidence regeneration: 15/15 scripts pass, including the manuscript Table 1
  cross-check and independent value cross-checks;
- Figure 2 generator: 10/10 rule-layer cells pure, anchor counts match
  4,757/16,380 and 6,469/16,380, and text-overlap check is zero;
- build: zero LaTeX errors and zero overfull boxes;
- PDF: 9 pages total, body ends on page 8 and references begin on page 9;
- fonts: 13 embedded fonts, 10 Type 1 + 3 TrueType, 0 Type 3;
- anonymity: 9 artefacts scanned, no identity hits; and
- citations: 17 bibliography entries, 14 cited, contiguous [1]-[14], with no
  unverified cited entry.

The bottom-up checks support the numerical claims. The reproducibility
inventory also reports the exact metadata coverage instead of silently
upgrading incomplete manifests into a stronger claim.

## Four reviewer lenses

These are synthesized red-team perspectives, not claims that four external
reviewers have already evaluated the paper.

| Lens | Likely verdict | Strongest positive | Main reason for hesitation |
|---|---|---|---|
| TAE / AI-evaluation reviewer | Acceptable after scope edit | Clear construct-validity failure mode and a low-cost reporting prescription | Residuals remain descriptive; the paper now states that boundary explicitly |
| Statistical/computational methods reviewer | Acceptable with stated limitations | Paired arms, explicit denominators, seed-level inference, independent decomposition checks, and automated Table 1 provenance | Small *n*=3 cells and treatment-affected world state remain limitations, not hidden assumptions |
| AI-agent / CS-systems reviewer | Acceptable workshop version | The problem is an actual runtime governance loop positioned against agent guardrail systems; the release inventory exposes metadata coverage | Some older manifests are incomplete, so no bitwise-reproducibility claim is made |
| Skeptical meta-reviewer | Acceptable with bounded interpretation | The figures explain the measurement path and the manuscript scopes the anchor mechanism | Cross-testbed portability remains descriptive, as stated in §8 |

### Final verification checklist

1. The claim is now the bounded one: world-state composition is the dominant
   explanation on the anchor cell, while a within-world residual remains possible.
2. Flood remains portability/regime evidence, never a control for enforcement
   pressure.
3. `evidence/reproducibility_inventory.csv` exposes the 42-run manifest matrix,
   enriched/minimal coverage, prompt paths, and absent fields.
4. `table1_manuscript_crosscheck.py` compares the five irrigation rows and flood
   range against the canonical CSV on every evidence run.
5. The abstract distinguishes the self-report's lack of an independent channel
   from a deployment that separately logs world state.
6. The local package is ready; the author should still check the live workshop CFP
   for deadline, anonymity, template, and dual-submission rules before uploading.

## Scholarly prose audit

The manuscript now has a clear CS-paper reading order, defines the conditional
and design-fixed rates in plain language, and avoids presenting deception or
gaming as a required explanation. Figure captions define their denominators
and explicitly distinguish decomposition from contrast.

The consistency audit passes with zero findings. The prose-pattern audit reports
32 diagnostic repetition findings across the active manuscript and generated
release companion. These are mostly legitimate technical repetitions, duplicated
source/companion text, or protected terminology such as "anchor cell" and
"positive means the validators lowered"; they are not evidence of a factual
conflict or an automatic-writing failure. They are non-blocking style
diagnostics.

## Delivery and human-only decisions

The local package is **ready to submit** under the encoded workshop template:
the body is eight pages, the PDF is anonymous, all evidence and figures are
current, and the three previously open S2 issues are resolved. The local gate
does not submit the paper and does not verify live venue rules that are not
encoded in the repository; only the final CFP/deadline check remains human.

## Functional-completeness retrospective

- manuscript, figures, captions, evidence scripts, and generated PDF are present;
- Figure 2A's denominator mismatch is now resolved in source, figure, caption,
  and print rendering;
- Figure 1's final visual semantics are deterministic and reproducible;
- all seven local delivery gates and the manuscript-state audit pass; and
- no new experiment is required for this workshop version. Any future run
  should be treated as a new evidence revision, not silently mixed into this
  checked artifact.
