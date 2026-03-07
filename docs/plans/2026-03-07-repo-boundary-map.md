# WAGF Repo Boundary Map

Date: 2026-03-07

## Purpose

This document defines which parts of the repository are:

- framework-facing
- reference-domain-facing
- paper/private working space
- archive or local-only

It is intended to reduce ambiguity before continuation work.

## 1. Framework-Facing Surface

These are the parts that should define the public identity of the project.

### Core framework

- `broker/`
- `providers/`
- `tests/`
- `pyproject.toml`
- `requirements.txt`
- `README.md`
- `ARCHITECTURE.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`

### Framework docs

- `docs/guides/`
- `docs/modules/`
- `docs/architecture/`
- `docs/references/`

Note:
- `docs/internal/` is not framework-facing
- `docs/plans/` is planning/support material, not end-user documentation

## 2. Reference Domain Surface

These are valid examples of how to instantiate the framework and should remain visible, but they should be described as reference packs rather than core framework modules.

### Primary reference experiments

- `examples/minimal/`
- `examples/minimal_nonwater/`
- `examples/quickstart/`
- `examples/single_agent/`
- `examples/irrigation_abm/`
- `examples/multi_agent/flood/`

### Secondary or historical examples

- `examples/governed_flood/`
- `examples/multi_agent_simple/`

These should not be presented as the main entry path for new external users unless they are intentionally maintained.

## 3. Paper / Manuscript Working Space

These directories are valuable research assets, but they are not framework-facing:

- `paper/`
- `paper/nature_water/`
- `paper/flood/`
- `paper/irrigation/`
- `paper/experiments/`
- `paper/archive/`
- `paper/shared/`

Rule:
- Keep them in the repository if needed for active writing.
- Do not let them dominate public onboarding.
- Link to them only from paper-specific notes, not from framework quickstart paths.

## 4. Private / Local / Ignored Working Space

These should be treated as local operational support, not part of the framework product surface:

- `.ai/`
- `.agents/`
- `.claude/`
- `.codex/`
- `.cursor/`
- `.opencode/`
- `.zencoder/`
- `.zenflow/`
- `.tasks/`
- `.worktrees/`
- `.mcp.json`
- `hooks/`

## 5. Archive / Low-Priority Surface

These are useful for historical reference but should not be part of the active framework story:

- `_archive/`
- `examples/archive/`
- `paper/archive/`
- `ref/` except where explicitly needed for research replication

## 6. Immediate Boundary Rules

### Rule A

Do not add new framework-facing docs under `paper/`.

### Rule B

Do not add new manuscript/private working notes under top-level `docs/guides/`.

### Rule C

New continuation work should prefer:

- framework changes in `broker/`
- public guidance in `docs/guides/`
- runnable reference examples in `examples/minimal_nonwater/`, `examples/minimal/`, or the maintained water-domain packs

### Rule D

Paper-specific figures, review notes, and exploratory analysis should stay under:

- `paper/`
- domain-local `analysis/`
- or ignored working folders

## 7. Recommended Next Cleanup Pass

High value, low risk:

1. Add a short repo-surface section to `README.md`
2. Add a short note to `paper/PAPER_README.md` clarifying that `paper/` is manuscript-facing, not framework-facing
3. Classify `examples/governed_flood/` and `examples/multi_agent_simple/` as either maintained examples or legacy demonstrations
4. Keep `docs/internal/` out of public onboarding links
