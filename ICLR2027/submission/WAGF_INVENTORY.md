# WAGF paper material and release inventory

Updated 2026-08-10. This is an internal release audit for the active ICLR
package. It records what is available, what supports the manuscript, and what
must remain outside the claim boundary.

## Study identity

The paper is an empirical computer-science paper about measurement validity in
governed LLM-agent evaluation. Its object is not a new water-management policy
and not a claim that validators are harmful. The object is a shared
agent-written condition: the runtime validator reads it while deciding what
can execute, and the evaluator reads it again when selecting records for a
conditional score.

The primary example is the coupled irrigation simulation because an accepted
action changes a reservoir state that enters later agent context. That feedback
makes the denominator issue observable over time. Flood is a secondary,
descriptive cross-testbed boundary check. It is not a matched control, a second
mechanism study, or a co-primary application.

## Material inventory

| Layer | Canonical material | What it supplies | Release status |
| --- | --- | --- | --- |
| Manuscript | `paper/manuscript.tex` and `paper/references.bib` | Anonymous ICLR paper, captions, claims, citations, declarations | Active |
| Concept figure | `figures/active/figure1_concept.png` plus the generated source asset and manifest | Domain-neutral shared-condition path, retry/default route, record-selection route | Active; visual review passed |
| Quantitative figures | `figures/active/fig1_rule_layers.pdf`, `fig2_mechanism.pdf`, `fig3_consequence.pdf` | Irrigation rule layers, coupled-world diagnosis, denominator consequence | Active; deterministic outputs |
| Evidence builders | `source/figure2_rule_layers.py`, `source/cross_testbed_summary.py`, `source/figure4_denominator_gap.py`, and the frozen TAE evidence scripts | Rebuildable derived summaries and figure/table inputs | Active and read-only audited |
| Frozen corpus | `SUBMISSION_2026/TAE/runs` plus the evidence inventory | Paired irrigation and bounded Flood results | Sufficient for current descriptive claims; historical provenance caveat remains |
| First-attempt branch | `ICLR2027/experiments/_smoke_firstattempt` and TAE first-attempt run folders | Governed-only retry/appraisal diagnostics | Outside manuscript; provenance RED |
| Coupling audit | `COUPLING_AUDIT.md` | State timing, units, action/diversion distinction, worker boundary | Active audit record |
| Venue and literature audits | `VENUE_MATRIX.md`, `LITERATURE_POSITIONING_AUDIT.md`, `REFERENCE_AUDIT.md` | Target rules, literature functions, metadata and claim support | Active audit record |

## Frozen corpus check

The read-only command below was run on 2026-08-08:

```text
python SUBMISSION_2026/TAE/evidence/corpus_inventory.py
```

It exited 0 with `VERDICT: PASS`. The runner found 42 irrigation run
directories and 90 Flood run directories. Irrigation cells contain the
expected 3,276 decision rows and balanced validator-on/off seed pairs for the
reported cells. Flood cells contain the expected 1,000-row arm/run artifacts
and balanced five-run coverage. The inventory also reports that all required
columns are present.

This is enough for the current descriptive paper because its primary results
come from the frozen irrigation corpus, its world-state check is explicitly
descriptive, and Flood is used only as a bounded table-level comparison. The
inventory does not repair the separate provenance audit: the historical corpus
has no clean committed run, and the new first-attempt branch is not a matched
two-arm experiment.

### Raw-tree versus release-corpus boundary

The canonical inventory intentionally filters auxiliary and quarantined
directories. A separate read-only sweep of the raw result trees found 62
irrigation result directories (42 with manifests) and 130 Flood/single-agent result
directories (109 with manifests). Those totals include FQL baselines, archived
or quarantined runs, and other historical branches. They are not the sample
reported in the manuscript. The release corpus is the smaller, explicit set
reported by `corpus_inventory.py`: 42 irrigation run directories and 90 Flood
run directories, with the ten irrigation arm-by-cell rows and eighteen Flood
arm-by-cell rows shown above. The full-tree sweep is retained as an audit
finding, not as additional evidence.

The two raw-tree audit outputs generated on 2026-08-08 are kept outside the
active manuscript path during this review because both correctly return RED on
mixed historical trees with missing, dirty, or incomplete manifests:

- `checks/reproducibility_audit_20260808_irrigation/reproducibility_report.md`
- `checks/reproducibility_audit_20260808_flood/reproducibility_report.md`

These reports support the existing reproducibility limitation. They do not
change any manuscript number or promote an auxiliary run into the frozen
corpus.

## Claim sufficiency matrix

| Claim or analysis | Evidence sufficient? | Boundary that must remain visible |
| --- | --- | --- |
| Irrigation condition-share and executed-action contrasts | Yes | Paired descriptive comparison; the executed action is primary |
| Five-cell irrigation denominator comparison | Yes | Conditional and all-decision rates answer different questions |
| Recorded-world reweighting | Yes for a descriptive diagnosis | World state is downstream of governance; no causal adjustment claim |
| Flood cross-testbed range | Yes for a secondary boundary check | Different ontology, feedback, field name, and seed matching; not a mechanism transfer |
| Within-decision appraisal drift | No | First response before retry is missing from the frozen corpus; first-attempt branch lacks a matched no-validator arm |
| Bitwise reproducibility of historical runs | No | Dirty manifests and incomplete clean-commit provenance are disclosed |
| Generic parallel safety for coupled WAGF runs | No | The paper's coupled runs use `workers=1`; the generic runner warns, but does not prove arbitrary parallel safety |

## Generic WAGF module audit

The read-only code audit covered the coupling contract, adapter, experiment
builder, experiment runner, retry loop, audit writer, governance dispatch, and
the irrigation integration path. The targeted coupling and irrigation tests
exited 0. No confirmed P0/P1 defect in a generic module was found, so no
generic source file is changed in this round.

The important limitation is architectural coverage rather than a newly found
bug:

- `broker/coupling/contract.py` provides explicit unit, range, cadence,
  direction, duplicate-consumer, and fail-loud checks.
- `broker/coupling/adapter.py` applies the declared boundary checks when an
  adapter is used.
- `broker/core/experiment_builder.py` rejects invalid worker counts and emits
  an explicit warning when a coupled build requests `workers > 1`.
- The direct irrigation path documents and tests the annual feedback sequence,
  but it does not instantiate the formal generic contract for every exchanged
  field. Some direct-path missing-field defaults therefore remain a YELLOW
  coupling risk.

The paper reports this as a scope boundary. Making the direct irrigation path
fully contract-backed would be a framework change, not a safe paper-only fix,
and would require a separate design and regression round.

## Ownership and cleanliness boundary

The active ICLR package is Codex-owned. Cloud-owned experimental files in
`broker/`, `examples/`, `SUBMISSION_2026/TAE/evidence/`, and active run
directories were not staged or modified. The dirty files shown by `git status`
belong to those ongoing experiments or historical/shared artifacts. This audit
does not delete them or rewrite their evidence.

## Release interpretation

The manuscript and figures are structurally coherent and evidence-sufficient
for the frozen descriptive claim. The package is not yet a final-upload
release because the provenance gate, submission-time OpenReview checks, and
the unresolved first-attempt matched-arm question remain open. Those gaps are
published in `EXPERIMENT_AUDIT.md`, `COUPLING_AUDIT.md`, and `HANDOFF.md`.

## Decision

Keep the current four-figure / three-table hierarchy. Do not add a Flood
mechanism panel, do not promote first-attempt diagnostics into the results,
and do not modify generic WAGF code without a confirmed defect and a separate
regression plan.

## Risks

The current paper can establish a measurement-validity warning and a reporting
protocol, but not a causal governance effect, deception, within-world report
revision, bitwise reproducibility, or generic parallel coupling safety.

## Required changes

Before upload, close or explicitly waive the provenance and submission-time
gates. A new matched first-attempt arm is optional for the current paper and is
required only if the manuscript wants to make an appraisal-drift claim.

## Next actions

1. Re-run the complete manuscript, evidence-boundary, TeX, and visual checks
   after any prose or figure change.
2. Refresh the venue rules at upload time and complete ICLR metadata and
   anonymity checks.
3. Keep AAMAS as a later fallback only after the ICLR decision or withdrawal.
