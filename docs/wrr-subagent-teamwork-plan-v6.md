# WRR Subagent Teamwork Plan (v6)

## Objective

Prepare the next phase on:
- framework function introduction
- flood example narrative focused on rationality ratio and diversity

while preserving the current manuscript logic (`R_H` vs `R_R` vs `EBE`) and WRR Technical Note style.

---

## Prior-Plan Digest (What Was Already Settled)

From `wrr-intro-wagf-v6-plan.md` and `wrr-ch2` to `wrr-ch7` plans:
- Intro settled on: LLM expressivity + governance necessity, avoid over-claiming full rationality.
- Section 2 settled on: explicit boundary (`LLM propose -> broker govern -> execution mutate`).
- Section 3 settled on dual-metric taxonomy:
  - `R_H`: feasibility hallucination (identity failures)
  - `R_R`: rationality deviation (thinking failures)
  - `EBE` adjusted by `R_H` only.
- Sections 4-7 were aligned to this taxonomy and claim-bounded tone.

Open synthesis need:
- turn this into a reusable "function introduction + flood metric story" package.

---

## Subagent Team Design

### Agent A — Architecture Narrator

Scope:
- Produce concise framework function overview aligned with actual module boundaries.

Inputs:
- `broker/core/skill_broker_engine.py`
- `broker/components/*`
- `docs/wrr-ch2-review-plan-v6.md`

Output:
- 1-page function-flow paragraph set (non-promotional, method-first).

### Agent B — Metrics Theorist

Scope:
- Lock formal definitions and notation for `R_H`, `R_R`, `H_norm`, corrected entropy, `EBE`.

Inputs:
- `docs/wrr-ch3-review-plan-v6.md`
- current manuscript Section 3 text

Output:
- canonical metric block + notation checklist for all later sections.

### Agent C — Flood Evidence Analyst

Scope:
- Prepare flood case narrative with rationality ratio and diversity story.

Inputs:
- `docs/wrr-ch4-review-plan-v6.md`
- `docs/wrr-feature-flood-prep-v6.md`
- flood metric source-of-truth table (frozen file required before final text lock)

Output:
- paragraph pack for:
  - feasibility (`R_H`)
  - rationality (`R_R` or `1 - R_R`)
  - diversity (`H_norm`, corrected entropy, `EBE`)
- explicit caveat when a metric is audit-level vs inferential.

### Agent D — Data/Verification Auditor

Scope:
- Ensure metric claims use one consistent data source.

Inputs:
- `paper/flood/verification/verification_report.md`
- flood analysis CSVs used in manuscript

Output:
- "allowed numbers list" + mismatch flags to prevent citation drift.

### Agent E — Integration Editor (Controller)

Scope:
- Merge A-D outputs into final manuscript wording and SI-ready snippets.
- Enforce tone, length, notation, and claim boundaries.

Output:
- final paragraph set for function intro + flood example
- revision log with traceable source mapping.

---

## Parallel Execution Order

1. Run A, B, C, D in parallel (independent analysis tasks).
2. Integration pass by E.
3. Reviewer pass:
- spec-compliance check (against ch2-ch7 settled taxonomy)
- quality check (clarity, redundancy, over-claim risk)
4. Final patch + commit.

---

## Shared Rules Across Agents

- Do not collapse `R_H` and `R_R`.
- Do not introduce new numerical claims unless sourced from frozen dataset.
- Keep EBE definition fixed: feasibility-adjusted only.
- Prefer "evidence suggests" over absolute wording.
- Every paragraph must map to one concrete evidence source or implementation artifact.

---

## Immediate Sprint (Current Request)

Target deliverables:
1. Function introduction paragraph pack (Section 2-compatible, reusable in talks/slides).
2. Flood example paragraph pack:
- rationality ratio framing (`R_R` / `1 - R_R`)
- diversity framing (`H_norm`, corrected entropy, `EBE`)
3. One compact metric mini-table schema for manuscript/SI.

Definition freeze for this sprint:
- `R_H = n_id / n_total`
- `R_R = n_think / n_total`
- `Rationality pass ratio = 1 - R_R`
- `EBE = H_norm * (1 - R_H)`

---

## Risks to Control

1. Data inconsistency risk:
- Existing verification notes show cross-file mismatches.
- Mitigation: pick one source-of-truth file before final number insertion.

2. Terminology drift risk:
- "economic hallucination" wording can reintroduce taxonomy ambiguity.
- Mitigation: map to identity-feasibility or thinking-coherence explicitly.

3. Over-claim risk:
- novelty/priority claims ("first", "prevents") trigger reviewer pushback.
- Mitigation: use bounded claim language tied to reported experiments.
