---
phase: 5
date: 2026-04-18
scope: Top-10 ranked actions synthesised from 4-phase broker audit
author: Claude
depends_on:
  - broker/_AUDIT_GAPS_2026-04-18.md
---

# Broker Audit — Top-10 Action List

Ranking rule: **impact × urgency** (higher-impact first, then NW-submission-blocking items). Each item has: severity, effort, concrete first step, blocker-for (what depends on it), owner proposal.

---

## Tier 1 — Pre-NW-submission (must fix)

### #1. Validator pipeline doc ↔ code alignment (S0 / S-M / H)

The Methods v4 6-step sequence (schema → action legality → physical → institutional → magnitude → theory) does not match code in 4 places. Fix EITHER the code or the Methods doc so they agree.

**First step**: open `paper/nature_water/drafts/methods_v4.md` section "Broker Architecture and Governance Pipeline" and cross-reference against `broker/core/skill_broker_engine.py:227-528` + `broker/core/_retry_loop.py:152-295`. Decide per FLAG:
- FLAG 1 (institutional is 3 labels): update Methods to name the 3 sublabels OR merge labels in code.
- FLAG 2 (magnitude is warning-only): update Methods to say "magnitude is advisory, not binding" OR upgrade validator severity.
- FLAG 3 (retry-loop deterministic requirement): update Methods to say "if the same deterministic blocker repeats".
- FLAG 4 (fallback is registry default): update Methods to name the fallback skill explicitly.

**Blocker for**: NW submission. Reviewer will check code; divergence becomes a credibility issue.

**Owner**: Claude direct (doc edits) + Codex review pass.

---

### #2. Add docstring to `broker/core/skill_broker_engine.py` matching Methods 6-step description (S1 / S / H)

A reader following the Methods paper should be able to find the 6-step sequence in code within one function's docstring. Currently there is no such anchor.

**First step**: add a module-level docstring to `broker/core/skill_broker_engine.py` that lists the 6 steps, names the method that implements each, and links back to Methods v4. Do the same for `_retry_loop.py`.

**Blocker for**: reviewer asking "show me the code that matches your Methods section".

**Owner**: Claude direct. ~20 min.

---

### #3. Rename `RuleCondition.construct` and `GovernanceRule.construct` (S1 / S / M)

Two real pydantic warnings that fire every test run and could break in a future pydantic. Field name `construct` shadows `BaseModel.construct`.

**First step**: rename to `rule_construct` (or similar) in `broker/config/schema.py:142, 172` and update every consumer. Grep shows ~few sites.

**Blocker for**: clean test-run output; future pydantic upgrade.

**Owner**: Codex delegation (mechanical rename across ~10 files). Safe because it is pure rename.

---

## Tier 2 — Pre-Paper-3-submission (should fix)

### #4. Decide fate of `broker/components/memory/engines/humancentric.py` write policy (S1 / S / M)

The 2026-04-11 broker-memory-governance generalization (`memory_write_policy`) was added for Paper 3's CLEAN vs LEGACY narrative. Audit it:
- If it is framework-level (applies to all domains), keep in `broker/components/memory/`.
- If it is Paper-3-only, move to `examples/multi_agent/flood/` — keep broker clean.

**First step**: read commit 9057097's diff. Identify which config keys belong to the broker and which to examples.

**Blocker for**: broker's cross-domain reusability claim.

**Owner**: Claude direct. ~30 min audit, surgical move if needed.

---

### #5. Add tests for `broker/components/prompt_templates` (S1 / S / H)

ZERO test files. This package is what Paper 3 dual-role finding leans on (memory-template vocabulary).

**First step**: write `tests/test_prompt_templates.py` with smoke tests for `MemoryTemplateProvider` and `MemoryTemplate`. Cover at least: (a) default template resolution, (b) policy-gated template choice (CLEAN vs LEGACY), (c) memory write goes through the template and ends up correctly in the store.

**Blocker for**: any defensibility of the dual-role finding under reviewer scrutiny.

**Owner**: Codex delegation (test boilerplate) + Claude review.

---

### #6. Fix parser alias bugs (S1 / M / M)

Phase 2 regressions surfaced real parser gaps:
- Government yaml aliases `INCREASE`/`DECREASE` (bare) → fall through to default
- Insurance yaml alias `IMPROVE_CRS` → resolves to `improve_crs` (wrong)
- Insurance yaml alias `SIGNIFICANTLY_REDUCE` → resolves to `reduce_crs` (wrong)

The yaml documents these aliases as intentional, so the parser should honour them. This is a code bug, not test drift.

**First step**: inspect `broker/utils/parsing/unified_adapter.py` alias resolution. Likely the alias table is built from yaml but LONGER aliases (`LARGE_INCREASE`) take precedence incorrectly over SHORTER ambiguous ones (`INCREASE`). Fix resolution order.

**Blocker for**: any downstream analysis that parses text-mode decisions — including LLM output that uses bare keywords.

**Owner**: Claude direct (inspect) + fix. ~45 min.

---

## Tier 3 — Pre-next-domain (architecture debt)

### #7. Add `__init__.py` facades for `broker/utils/`, `broker/core/`, `broker/components/context/`, `broker/components/cognitive/`, `broker/components/analytics/` (S1 / M / H)

These are the 5 most-leaked-into namespaces (99 total deep imports from examples). Without facades, any API change propagates to every consumer. When the next domain arrives (groundwater, wastewater), they will leak just as badly.

**First step**: for each package, list the CURRENT deep-import targets from `examples/`. Export exactly those symbols through `__init__.py`. Leave everything else internal.

**Blocker for**: clean reuse when extending the framework to a new water domain.

**Owner**: Codex delegation (mechanical, bounded by the Phase 3 leakage table).

---

### #8. Trim root `broker/__init__.py` (S2 / M / M)

42 public exports, only 8 consumed by examples. The other 34 pollute the public surface.

**First step**: remove the 34 zero-consumer exports. Or mark them `__all__` only; keep `from broker import X` working but remove from advertised surface.

**Blocker for**: coherence of the root facade, which is the most visible API entry point.

**Owner**: Codex delegation + Claude review.

---

## Tier 4 — Hygiene (opportunistic)

### #9. Strip UTF-8 BOM from 5+ broker files (S2 / S / L)

`context/builder.py`, `prompt_templates/__init__.py`, `prompt_templates/memory_templates.py`, `config/__init__.py`, `config/schema.py` all have `\ufeff` at file start.

**First step**: run `sed -i '1s/^\xef\xbb\xbf//'` or equivalent cross-platform on the 5 files. Runtime imports already work; this is code hygiene.

**Blocker for**: static analysis tools that don't handle BOM gracefully (like the Phase 1 Codex false-positive).

**Owner**: Claude direct. ~5 min.

---

### #10. Add pre-Codex integrity snapshot (S2 / S / M)

The 190-file transient deletion today proved that running Codex against a live worktree is not fully safe, even with `read_only: true` in the brief. Add a cheap integrity guard.

**First step**: write a `.ai/codex_preflight.sh` (bash) that (a) records `find broker/ providers/ tests/ -name "*.py" | sort | sha256sum > /tmp/pre_codex`, (b) launches Codex, (c) compares after, (d) if changed, flag loudly. Every future Codex task should source it.

**Blocker for**: future audits; protects against re-occurrence of the Phase 2 incident.

**Owner**: Claude direct. ~20 min.

---

## Dependency graph

```
#1 (doc ↔ code align)  → #2 (docstring anchor)
#4 (memory policy scope) → (independent)
#7 (facades) → #8 (trim root)
#6 (parser fixes) → (independent)
#5 (prompt template tests) → (independent)
#3 (pydantic rename)  → (independent)
#9 (BOM strip) → (independent)
#10 (preflight) → all future audits
```

Parallelisable: {#1+#2}, #3, #4, #5, #6, #7, #9, #10 can run in parallel. Only #8 depends on #7.

## Effort totals

- **Pre-NW-submission (Tier 1)**: 3 items. ~2-3 hours Claude + Codex.
- **Pre-Paper-3 (Tier 2)**: 3 items. ~4-5 hours.
- **Pre-next-domain (Tier 3)**: 2 items. ~6-10 hours (architecture).
- **Hygiene (Tier 4)**: 2 items. ~30 min.

**Recommended immediate triage**: do Tier 1 (#1, #2, #3) this week while Paper 1b is still in revision. Tier 2 after Paper 3 submission. Tier 3 when next domain is scheduled. Tier 4 anytime.

## NOT recommended as actions

Several gaps were identified and explicitly de-ranked:

- **A5/A6 duplicate-namespace merge** (`broker/memory` vs `broker/components/memory`; `broker/governance` vs `broker/components/governance`). These are real duplications but the current pattern works and forcing a merge would break consumers without benefit. Revisit only if specific confusion arises.
- **B2 zero-coverage module deletion** — wait for actual evidence the modules are dead before removing. Some may be consumed by registry lookup or YAML wiring that grep misses.
- **E1/E2 performance profiling** — no evidence of a real performance issue yet. Don't optimise without a profile.
- **F3/F4/F5/F6 dependency warnings** — all non-blocking, wait for pandas/python upgrade cycle.

## Next step decision

Tier 1 item #1 (Methods ↔ code alignment) is the ONLY S0. Everything else can wait.

**Immediate next move**: do #1 now (~20 min editing Methods v4 or adding docstring clarifications), then commit all 5 audit files + regression fixes. That closes the audit cleanly and unblocks NW submission.
