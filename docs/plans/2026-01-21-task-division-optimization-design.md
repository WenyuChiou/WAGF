# 2026-01-21-task-division-optimization-design.md

## Summary
Adopt a phase-based task workflow to reduce rework and clarify ownership while preserving flexibility to reassign roles. Each phase has required artifacts and explicit handoff rules. Completion requires updates to task files, registry, cleanup, and a commit.

## Goals
- Reduce rework and back-and-forth changes.
- Make responsibility and ownership unambiguous.
- Ensure verification is repeatable and tied to artifacts.
- Standardize cleanup and commit practices.
- Allow mid-course reassignment without losing traceability.

## Non-Goals
- Overhaul of existing task taxonomy.
- Rewriting tools or automation beyond lightweight scripts.

## Phase Model

### Phase 1: Design & Decomposition (Owner: Claude Code)
- Decompose Task into subtasks with dependencies.
- Define pass/fail criteria and verification commands.
- Identify required artifacts and output locations.
- Decide which agent owns execution and verification.

Required artifacts:
- `.tasks/handoff/task-XXX.md` updated with plan and subtask table.
- `.tasks/registry.json` updated with status and owners.

### Phase 2: Execution & Implementation (Owner: Codex or Gemini CLI)
- Implement code changes or run experiments.
- Keep scope limited to planned files.
- Capture logs and outputs in designated paths.

Required artifacts:
- Code changes committed in local working tree (not yet committed to git).
- Output artifacts in expected directories.
- Short REPORT in handoff file with commands and outputs.

### Phase 3: Verification & Closure (Owners: Codex + Claude Code)
- Run verification commands specified in Phase 1.
- Validate acceptance criteria against artifacts.
- Clean up output directories if requested.
- Finalize task status and commit.

Required artifacts:
- `.tasks/handoff/task-XXX.md` updated with verification report.
- `.tasks/registry.json` status updated.
- `.tasks/handoff/current-session.md` updated.
- Outputs cleaned (if specified).
- Git commit created for the task.

### Phase 4: Research & Evidence (Owner: Antigravity)
- Provide literature review, benchmarks, or evidence.
- Deliver in separate handoff file and link from task.

Required artifacts:
- `.tasks/handoff/antigravity-*.md` summary.
- Links to manuscripts or citations in task handoff.

## Mandatory Deliverables (All Tasks)
- Update `.tasks/handoff/task-XXX.md`.
- Update `.tasks/registry.json`.
- Clean outputs if requested.
- Commit changes.
- Provide a short REPORT (commands + artifacts + results).

## Role Mapping (Default)
- Claude Code: Phase 1 and sign-off in Phase 3.
- Codex: Phase 2 execution + Phase 3 verification.
- Gemini CLI: Long-running experiments + evidence of completion.
- Antigravity: Phase 4 research/evidence.

## Handoff Protocol
- All transitions require a handoff entry in `.tasks/handoff/task-XXX.md`.
- Reassignment must update `assigned_to` and status in registry.
- Blockers must be recorded with concrete failure reason and next step.

## Verification Standard
- Verification must cite:
  - command(s) used
  - output path(s)
  - pass/fail thresholds
  - any deviations or skipped checks

## Cleanup Standard
- Remove temporary experiment outputs after verification unless explicitly retained.
- Keep only artifacts referenced by handoff or paper.

## Commit Standard
- One commit per task completion when possible.
- Commit message: `chore: close task-XXX` or `feat: task-XXX <short desc>`.

## Metrics
- Rework rate: % of tasks needing re-open.
- Verification compliance: % of tasks with full REPORT.
- Cleanup compliance: % of tasks with no stray outputs.
- Cycle time per phase.

## Example Phase Flow (Task-027)
- Phase 1: Define universal engine integration and required CLI changes.
- Phase 2: Implement runner/MemoryProvider changes.
- Phase 3: Run smoke + inline switching verification, clean outputs, commit.
- Phase 4: N/A.

## Adoption
- Start with new tasks and re-opened tasks only.
- Gradually retrofit high-risk tasks.
