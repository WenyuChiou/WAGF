# Current Session Handoff

## Last Updated
2026-01-31T03:00:00Z

---

## NEXT TASK: Task-060 — RL-ABM Irrigation Experiment (Hung 2021)

**Status**: `planning` — ready to start implementation
**Priority**: HIGH
**Branch**: Use `task-060` branch (exists locally and on remote)

### What to Do First

1. Read `.tasks/handoff/task-060-rlabm-ma.md` (full implementation plan, 194 lines)
2. Read `ref/Hung2021_extracted.txt` (extracted paper text)
3. Clone `https://github.com/hfengwe1/RL-ABM-CRSS` to `ref/RL-ABM-CRSS/`
4. Inventory available data vs needed data
5. Start subtasks 060-1 through 060-5 (infrastructure), then 060-6 through 060-11

### Paper Reference

**Hung, F., & Yang, Y. C. E. (2021)**. Assessing adaptive irrigation impacts on water scarcity in nonstationary environments — A multi-agent reinforcement learning approach. _Water Resources Research_, 57, e2020WR029262.

- **PDF**: `ref/Water Resources Research - 2021 - Hung - Assessing Adaptive Irrigation Impacts on Water Scarcity in Nonstationary.pdf`
- **Extracted text**: `ref/Hung2021_extracted.txt`
- **GitHub**: https://github.com/hfengwe1/RL-ABM-CRSS

### Core Concept

78 intelligent agents (agriculture water users) using FQL (Farmer's Q-Learning) to adapt water demands. Three behavioral clusters: Aggressive, Forward-looking Conservative, Myopic Conservative. Map to GBF via MemorySystem (Q-function), Governance (exploration control), PsychometricFramework (reward).

---

## Previous: Task-062 Chapter Docs + Zotero (COMPLETE)

**Status**: All subtasks complete
**Branch**: `feat/memory-embedding-retrieval`
**Commits**: `2fa64f1` (docs update), `8ef28d5` (encoding fix), `c967394` (encoding fix)

### Task-062 Deliverables

#### 1. Chapter Documentation Updates (14 files, +519/-224 lines)

| Module | EN | ZH | Key Additions |
|--------|----|----|---------------|
| governance_core | Updated | Updated (+tutorial) | ERROR vs WARNING semantics, cross-agent validation |
| memory_components | Updated | **Created** (was missing) | Cognitive constraints (Miller/Cowan), SDK extensions |
| reflection_engine | Updated | Updated (encoding fixed) | Trigger-based reflection (4 trigger types) |
| simulation_engine | Updated | Updated | Multi-phase execution, GameMaster, conflict resolution |
| context_system | Updated | Updated | Inter-agent messages, new providers, skill randomization |
| skill_registry | Updated | Updated | Role-based permissions (RoleEnforcer) |
| theoretical_basis | Updated | Updated | Cognitive constraints row in mapping table |

#### 2. Zotero Literature Organization

- **7 papers added** with research notes (Kahneman 2011, Friston 2010, Godden & Baddeley 1975, Schon 1983, Argyris & Schon 1978, A-MEM 2025, FAISS 2017)
- **Notes added** to Rogers 1983 (`65IXMWP2`) and Bamberg 2017 (`R76GP2F7`)
- **Tags**: `README-Citation` on 8 items, `Theoretical-Basis` on 6 theory items
- **Collection hierarchy**: 5 top-level categories, 17 subcollections, 20+ items assigned

#### 3. Encoding Fixes

- `memory_components_zh.md`, `reflection_engine_zh.md`, `governance_core_zh.md` had UTF-8 corruption from linter — all three rewritten

---

## Codex Task Status

| Task | Status | Commit | Verified |
|------|--------|--------|----------|
| 061-C5 (governed_flood README) | Done | — | — |
| 061-C6 (multi_agent README alignment) | Done | — | — |
| 061-C7 (docs/ path verification) | Done | — | — |
| 059-D (Reflection Triggers) | Done | `41514be` | 18/18 tests pass |

---

## Background Experiments

### BC Re-run (b519eb8) — Status Unknown

- 6 experiments: gemma3:4b/12b/27b x Groups B/C
- Fixed governance rules (v22) + sampling defaults (temp=0.8, top_p=0.9, top_k=40)
- DO NOT interfere

---

## DESIGN ISSUE: Domain-Specific Validators Need Generalization

### Problem

All 5 governance validators are **hardcoded for the flood domain**:

| Validator | Flood-Specific Logic | Cannot Reuse For Irrigation |
|-----------|---------------------|----------------------------|
| `personal_validator.py` | Elevation cost, savings check | Irrigation has water-right costs, not elevation |
| `physical_validator.py` | "Already elevated", "already relocated", renter check | Irrigation has acreage limits, water allocation caps |
| `thinking_validator.py` | PMT (TP/CP), utility, financial frameworks | Irrigation uses Q-learning reward/regret, not PMT |
| `social_validator.py` | Neighbor elevation %, herd behavior | Irrigation has upstream/downstream water competition |
| `cross_agent_validator.py` | Generic core (echo chamber, deadlock) + flood domain rules injected | Generic core is reusable; domain rules need replacement |

### What Task-060 Needs

For the Hung 2021 irrigation experiment, governance must enforce:
1. **Water allocation bounds** — agent cannot request more than physical supply
2. **Exploration constraints** — epsilon-greedy bounded by regret parameter
3. **Inter-basin fairness** — Upper Basin vs Lower Basin allocation rules (Colorado River Compact)
4. **Learning rate governance** — prevent catastrophic forgetting (alpha bounds)
5. **Physical water constraints** — diversion cannot exceed available flow

### Proposed Architecture: Domain-Agnostic Validator Layer

```
broker/validators/governance/
  base_validator.py              # KEEP — abstract base (already generic)
  cross_agent_validator.py       # KEEP — generic core + injectable domain rules
  # --- Domain-agnostic generic validators ---
  resource_validator.py          # NEW — generic resource constraint (water, money, etc.)
  action_bounds_validator.py     # NEW — generic action space bounds
  learning_validator.py          # NEW — generic RL parameter bounds (alpha, epsilon, gamma)
  # --- Domain packs (injectable) ---
  domains/
    flood/
      personal_validator.py      # MOVE existing personal_validator here
      physical_validator.py      # MOVE existing physical_validator here
      thinking_validator.py      # MOVE existing thinking_validator here
      social_validator.py        # MOVE existing social_validator here
    irrigation/
      water_rights_validator.py  # NEW — water allocation + compact rules
      irrigation_social.py       # NEW — upstream/downstream competition
      fql_bounds_validator.py    # NEW — FQL parameter bounds
```

### Key Design Principles

1. `base_validator.py` stays as-is — it's already domain-agnostic
2. `cross_agent_validator.py` already supports injectable `domain_rules` — good pattern to follow
3. Flood validators move to `domains/flood/` without code changes
4. New irrigation validators follow the same abstract interface
5. Domain selection via YAML config: `governance.domain: flood | irrigation`

### Refactoring Status: PHASE 1 COMPLETE

**Completed** (this session, not committed):
- `base_validator.py` — Added `BuiltinCheck` type alias, `_builtin_checks` injection via constructor, `_default_builtin_checks()` template method
- `personal_validator.py` — Extracted `flood_elevation_affordability()` → `FLOOD_PERSONAL_CHECKS`
- `physical_validator.py` — Extracted `flood_already_elevated()`, `flood_already_relocated()`, `flood_renter_restriction()` → `FLOOD_PHYSICAL_CHECKS`
- `thinking_validator.py` — Wrapped `_validate_pmt()`, `_validate_utility()`, `_validate_financial()` as `BuiltinCheck` callables. YAML condition engine unchanged (already generic).
- `social_validator.py` — Extracted `flood_majority_deviation()` → `FLOOD_SOCIAL_CHECKS`. Exposed `calculate_social_pressure()` as public utility.
- `__init__.py` — `validate_all()` now accepts `domain` parameter. `domain="flood"` = default (backward compat), `domain=None` = YAML-only mode.

**Tests**: 42/42 validator + core tests pass. 3 pre-existing MA reflection mock failures (unrelated).

**Zotero**:
- Added Sutton & Barto 1998 (`TAPEBZN6`), Watkins & Dayan 1992 (`ZATQW5HH`) with Task-060 notes
- Added validator generalization note to Hung 2021 (`BHJX2TS3`)
- Created `Reinforcement-Learning` subcollection (`TKRV48C6`) under `01-Theoretical-Foundations`
- Both RL items assigned to `Reinforcement-Learning` + `Water-Resources-ABM` collections

**Zotero Skill** (`.claude/skills/zotero-write/`):
- `SKILL.md` — Added Collection Management section, project collection hierarchy with keys, collection selection guide
- `references/api-reference.md` — Added Collections API (create, list, assign, remove, check)
- `scripts/add_literature.py` — Added `collections` param to `add_journal_article()` and `add_preprint()`, updated examples

### Still Needed for Task-060

- **HIGH**: Create `water_rights_validator.py` and `fql_bounds_validator.py` (irrigation domain checks)
- **MEDIUM**: Full domain-pack folder structure (`domains/flood/`, `domains/irrigation/`)
- **LOW**: Move existing flood validators to `domains/flood/` (backward-compat risk)

---

## Pending / Low Priority

| Task | Status | Owner |
|------|--------|-------|
| BC re-run verification (b519eb8) | Unknown | Check status |
| test_v3_2_full_integration mock fix | Low priority | Any |
| ZH encoding issue investigation | Low | Linter UTF-8 root cause unresolved |

---

## Comprehensive Handoff

For a FULL handoff document including framework architecture, MCP config, skills, Zotero state, task history, and theoretical concepts, see:

**Plan file**: `C:\Users\wenyu\.claude\plans\peaceful-beaming-peach.md`

This contains everything the next session needs to continue work.

---

## Commits This Session

| Hash | Description |
|------|-------------|
| `2fa64f1` | docs(task-062): update chapter docs for Tasks 050-060 features + Zotero organization |
| `8ef28d5` | fix(docs): restore reflection_engine_zh.md encoding (UTF-8 corruption) |
| `c967394` | fix(docs): restore governance_core_zh.md encoding (UTF-8 corruption) |
