# ICLR 2027 / WAGF completion audit

Updated 2026-08-08. This is an internal release-readiness record, not part of
the anonymous manuscript. It maps the original project objective to current
artifacts and separates completed local work from Cloud- or submission-time
gates.

## Current decision

The active manuscript is a frozen-evidence release candidate for ICLR 2027.
Its narrow claim is a measurement-validity claim: an agent-written condition
can affect runtime execution and also select the records counted by a
conditional score; in a coupled simulation, the resulting selection can also
change the later state trajectory. It is not a causal governance estimate, a
new validator, a deception claim, or a hydrological policy result.

## Requirement matrix

| Requirement | Authoritative evidence | Status | Remaining boundary |
| --- | --- | --- | --- |
| Inventory paper materials, code, cases, and artifacts | `WAGF_INVENTORY.md`, `SOURCE_OF_TRUTH.md`, active `paper/`, `figures/`, `source/`, and `supplement/` | PASS | Historical trees remain outside the active package |
| Define contribution, value, and innovation | `LITERATURE_POSITIONING_AUDIT.md`, `REFERENCE_AUDIT.md`, manuscript abstract/introduction | PASS for the narrow claim | Do not broaden beyond the evaluated governance loop |
| Recheck CS literature and introduction logic | 23 verified references; seven-paragraph why-to-gap-to-contribution funnel | PASS | Re-audit only if new claims or citations are added |
| Make figures readable and role-balanced | `PAPER_AUDIT.md`; Figure 1 visual audit; Figures 2--4 irrigation-led; Flood in Table 3 | PASS | Do not restore the retired Flood Panel D |
| Confirm current evidence is sufficient | 42 irrigation and 90 Flood release-corpus run directories; evidence boundary check | PASS for descriptive ICLR claims | Historical provenance is not bitwise-clean |
| Audit first-attempt experiments | `EXPERIMENT_AUDIT.md` | OPEN, correctly excluded | Needs clean matched no-validator arm before any appraisal-drift claim |
| Audit generic WAGF modules | `WAGF_INVENTORY.md`, `COUPLING_AUDIT.md`, full non-real-LLM tests | PASS with YELLOW caveat | Worker-1 boundary and direct-path defaults remain disclosed |
| Match target venue format and policy | `VENUE_MATRIX.md`; official ICLR Author Guidelines and AI Policy | PASS locally | OpenReview metadata and submission-window checks remain |
| Preserve water-human follow-up scope | `WATER_HUMAN_POSITIONING.md` | PASS as a boundary record | Follow-up needs water outcomes, uncertainty, and validation/design work |
| Keep package organized and auditable | `HANDOFF.md`, this file, deterministic builders, clean active submission tree | PASS | Cloud/TAE dirty work remains preserved by ownership |

## Evidence and display contract

- Irrigation is the primary empirical example because it supplies the tested
  action -> reservoir -> later-context feedback loop.
- Flood is a secondary descriptive boundary check. Its different action
  ontology, feedback structure, field name, seed matching, coverage, and
  reflection records do not support a matched mechanism comparison.
- Figure 1 is domain-neutral and conceptual; Figures 2--4 answer the rule,
  coupled-world, and denominator questions; Table 3 carries Flood only as a
  bounded cross-testbed result.
- The primary action reading is the executed action. `last-proposed` is a
  sensitivity reading only. The frozen corpus does not preserve the first
  response before a retry.

## Verification ledger

- Full WAGF test command `pytest tests broker -k "not real_llm" -q -rA` exited
  0 with three existing skips and two documented xfails.
- Manuscript static, evidence-boundary, ICLR page-gate, and Figure 1 geometry
  checks pass. The typeset PDF has 11 pages: 9 main-text and 2 reference pages.
- The cross-testbed builder passes twice with byte-stable Figure 3 PDF and PNG
  outputs; the page-gate JSON is also byte-stable across repeated runs.
- The active Table 3 fragment is named `supplement/table3_cross_testbed.tex`.
  No current builder, manifest, README, or handoff reference uses the
  superseded `table2` path; older review-log entries remain historical.
- The recent local submission commits are `9853aa97`, `a9e99abb`, and
  `1b807f95`; no manuscript number, experiment claim, or Cloud-owned file was
  changed in those cleanup commits.

## Gates that remain open

1. The five first-attempt runs are governed-only, have dirty manifests, and
   lack a matched no-validator arm. They stay outside the manuscript.
2. At submission time, all authors still need current OpenReview profiles and
   the required reciprocal-review, quota, anonymity, and dual-submission
   checks.
3. A water-human paper must be treated as a separate scientific paper. The
   current corpus supports descriptive action/state feedback, not calibration,
   policy effectiveness, equity, human validation, or basin transfer.

The current package should therefore be handed off as a release candidate,
not described as uploaded or fully provenance-closed.
