# Four-round adversarial submission review

Date: 2026-08-10
Scope: exact ICLR PDF, Figures 1--4, Tables 1--3, machine-readable evidence,
claim boundaries, and release integrity.

Gate rule: a release PASS requires zero open S3/S4 findings. “Acceptance-
competitive” is not a guarantee of acceptance.

## Round outcomes

| Round | Test | Initial verdict | Resolution |
| --- | --- | --- | --- |
| 1 | Blind display/caption comprehension | HOLD | Removed Figure 2's ambiguous rebased row, defined Figure 3's arm direction and uncertainty, and replaced Figure 4's contradictory arrows with denominator endpoints. |
| 2 | Display-to-source result integrity | HOLD | Made Table 1 endpoints traceable, added a detailed Table 3 provenance record, corrected decision/proposal terminology, and fixed the Flood B6/run-count trail. |
| 3 | Reject-side versus author-side debate | HOLD | Closed three S3s: neutralized unsupported “error” language, added paired Figure 4 gap intervals, and reframed Figure 3 as a descriptive diagnosis. One S3 remained: historical cross-arm code provenance. |
| 4 | Independent exact-PDF release gate | HOLD | Visual/build gate passed. The exact package was frozen with tracked builders, evidence, PDF, and a SHA-256 manifest. The historical corpus provenance S3 remains open. |

## Current display verdicts

| Display | Role | Current verdict |
| --- | --- | --- |
| Figure 1 | Conceptual shared-condition path: response, validation, execution, logging, and record selection | PASS |
| Figure 2 | What blocking rules read and how often decisions are blocked | PASS with denominator distinction stated in panel titles/caption |
| Figure 3 | When arm trajectories cease to share a recorded world; not causal mediation | PASS |
| Figure 4 | Executed conditional versus all-decision contrasts and paired gap uncertainty | PASS |
| Table 1 | Primary irrigation condition shares and executed conditional rates | PASS |
| Table 2 | Recorded-world reweighting diagnosis and its coverage tradeoff | PASS |
| Table 3 | Secondary, non-causal cross-testbed boundary check | PASS within its explicitly limited role |

The data figures use embedded TrueType fonts; Figure 4's right column reports
the conditional-minus-all gap and its own paired 95% interval. The
`gemma4:e2b` interval includes zero and is described as directionally
uncertain. Table 3 has one canonical release-cell CSV; the B6-included row in
`table1_cells.csv` is labelled sensitivity/audit metadata and is not a release
source.

## Remaining submission blocker

**S3 -- cross-arm code provenance.** The 42-run historical irrigation corpus
contains 27 dirty manifests, 15 runs without a recorded commit, no clean runs,
and six of 21 paired seeds whose arms record different commits. Disclosure
does not exclude code-version differences from the validator-on/off contrast.

The blocker can be closed in one of two ways:

1. Recover run-time source snapshots or dirty patches and demonstrate code
   equivalence across each paired arm for prompts, validation, simulation
   updates, parsing, logging, and analysis; or
2. Replace/confirm the primary evidence with paired runs from one clean frozen
   commit. The strongest design reruns all five irrigation configurations with
   the same prompt/config/model identity and paired seeds in both arms.

Each confirmatory run must record the clean commit, `git_dirty=false`, config
and prompt hashes, model identifier, seed, arm, launch command, row contract,
and exact per-seed outputs used by every table and figure.

## Final disposition

S4: 0.
S3: 1 (historical cross-arm code provenance).
Scientific framing: no fundamental reframe required.
Display clarity: release-grade after the four rounds.
Submission status: **HOLD -- not yet submission-ready or acceptance-competitive.**

After clean confirmatory evidence or a verified code-equivalence audit is
integrated, rerun the numerical, page, PDF, and provenance gates. Only then can
the package be reconsidered for PASS.
