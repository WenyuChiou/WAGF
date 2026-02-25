# WRR Prep: Function Overview + Flood Example (Rationality Ratio & Diversity)

## Purpose

This note prepares the next writing/presentation step for:
- framework function overview (what WAGF does, module-to-function mapping)
- flood case explanation with metric split:
  - feasibility hallucination (`R_H`)
  - rationality deviation (`R_R`)
  - diversity (`H_norm`, corrected entropy, `EBE`)

---

## 1) Function Overview (What to Present)

Use this sequence for a concise technical walkthrough:

1. `Context Builder`
- assembles bounded agent/environment context (no state mutation)
- files: `broker/core/unified_context_builder.py`, `broker/components/context_builder.py`

2. `Model Adapter & Parser`
- converts LLM output to `SkillProposal` with robust fallback parsing
- file: `broker/utils/model_adapter.py`

3. `Skill Registry`
- declares executable skill space + eligibility/preconditions/schema
- file: `broker/components/skill_registry.py`

4. `Validator Chain`
- identity feasibility + thinking coherence + other categories
- files: `broker/validators/governance/`, `broker/governance/type_validator.py`

5. `Execution Gate`
- only approved skills are executed in simulation layer
- files: `broker/core/skill_broker_engine.py`, `broker/core/experiment.py`

6. `Auditor`
- writes full decision/validation traces for post-hoc verification
- file: `broker/components/audit_writer.py`

Key message:
- LLM proposes, broker governs, simulation executes.
- domain change is configuration-level (YAML), not broker rewrite.

---

## 2) Flood Example: Metric Semantics

For flood single-agent, keep metric semantics strict:

- `R_H = n_id / n_total`
  - feasibility hallucination rate
  - identity/feasibility rule ERROR rejections

- `R_R = n_think / n_total`
  - rationality deviation rate
  - thinking-rule ERROR rejections

- `EBE = H_norm * (1 - R_H)`
  - feasibility-adjusted diversity
  - does **not** include `R_R`

- Optional communication metric:
  - rationality pass ratio: `1 - R_R`

Narrative rule:
- infeasible -> hallucination (`R_H`)
- feasible but incoherent -> rationality issue (`R_R`)

---

## 3) Flood Results to Emphasize

Current manuscript-compatible points:
- Group A/B/C feasibility pattern is already reported via `R_H` + `EBE`.
- Discussion and Conclusions now align with `R_H`/`R_R` separation.
- Section 4 text now treats `R_R` as complementary audit diagnostic.

Use this presentation order:
1. raw diversity (`H_norm`)
2. feasibility burden (`R_H`)
3. adjusted diversity (`EBE`)
4. coherence burden (`R_R`, audit-level unless inferential stats are added)

---

## 4) Data Source Caution (Important)

Verification artifacts indicate cross-file metric inconsistencies:
- `paper/flood/verification/verification_report.md`
- `paper/flood/verification/verify_flood_metrics.py`

Practical guidance:
- For manuscript consistency, use one frozen source-of-truth table per section.
- If `R_R` inferential stats are needed, compute from the same frozen audit set used for `R_H/EBE`.

---

## 5) Next Action Options

1. Build a compact flood metric table for manuscript/SI:
- columns: `R_H`, `R_R`, `H_norm`, corrected `H_norm`, `EBE`
- rows: Group A/B/C (years 2-10)

2. Add one explicit formula block in SI:
- `R_H`, `R_R`, `EBE` definitions + counting rules

3. Add one figure-caption sentence:
- "EBE is adjusted by feasibility hallucination (`R_H`) only; `R_R` is reported separately as coherence diagnostic."
