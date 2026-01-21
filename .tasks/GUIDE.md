# AI Collaboration Guide

This guide defines how tasks are tracked and handed off in this repo.
Keep it simple, deterministic, and easy to read.

## 1) Start checklist

- Read `handoff/current-session.md`.
- Read `registry.json`.
- Run `git status` to see local changes.
- Confirm no other AI is running the same task.

## Workflow Guidelines
- **Planning-to-Execution Flow**: After an agent (e.g., Claude Code) completes planning, the task must first be recorded in `handoff/current-session.md` before any execution begins. This ensures clear communication and state management.

## 2) Terminology

- `SA` = single agent (`examples/single_agent/`).
- `MA` = multi agent (`examples/multi_agent/`).
- Handoff = status, decisions, next steps.
- Artifact = output data or results.

## 3) Read task shortcut

When a user says "Read task":

1. Read `handoff/current-session.md`
2. Read `registry.json`
3. Respond with: current task, progress, next_step, blockers.
4. If `next_step` is empty, set it to `none` and ask for planning.

## 4) Registry fields (minimum)

Each task entry in `registry.json` must include:

- `id`, `title`, `status`, `type`, `priority`
- `owner`, `reviewer`, `assigned_to`
- `scope`, `done_when`, `tests_run`
- `risks`, `rollback`, `artifacts`
- `next_step`, `handoff_file`

## 5) Logs (what and why)

Purpose: small, human-readable run notes.

Store in `logs/{agent}-{timestamp}.log` and include:

- command(s) executed
- model/seed/params
- output folder
- errors or anomalies

Do NOT store large datasets or plots in `logs/`.

## 6) Handoff rules

Update `handoff/current-session.md` when:

- a decision is made
- a run finishes
- a task state changes

Handoff should answer:

- What changed
- Why it changed
- What is next

Keep `handoff/current-session.md` concise. Move long details to `handoff/task-XXX.md`.

## 6.1) Ownership

- Only repo-assigned agents (Codex, Claude Code, Gemini CLI) update `.tasks/`.
- Do not mix personal task systems or other agents' logs into this repo.
- Other AI IDEs (e.g., antigravity) must report results to Claude Code instead of writing `.tasks/` directly.

## 7) Artifacts rules

Put outputs in `artifacts/` or project result folders.
Log artifact paths in handoff and registry.

## 8) Plan usage

Use a plan only for multi-step work.
One plan at a time. Update it after completing a sub-step.

## 9) Git commit rules

- Use conventional commit style.
- One logical change per commit.
- Update handoff + registry in the same work session.

## 10) Task commands (keywords)

- `Start task <id>`
- `Update task` / `Record task`: Updates `registry.json` and active `handoff/*.md`.
- `Block task <reason>`
- `Unblock task`
- `Switch task <id>`
- `Add todo <item>`
- `Clear todo` (sets next_step to `none`)
- `Run test <cmd>`
- `Log artifact <path>`

## 11) Execution Report Format

Execution-only agents must report in this format to Claude Code:

```
REPORT
agent: <name>
task_id: <task-XXX or none>
scope: <area/dir>
status: <done|blocked|partial>
changes: <files touched or "none">
tests: <commands run or "none">
artifacts: <paths or "none">
issues: <bugs/risks or "none">
next: <suggested next_step or "none">
```

## 12) Micro-plan Policy

Small work (single step, <30 minutes, low risk) does not require a new task.
Record a one-line "Micro-plan" note in `handoff/current-session.md`.
Multi-step or shared work must be tracked in `registry.json` + `handoff/task-XXX.md`.

## 13) Assignment Rule

Plans must explicitly include `assigned_to` plus `owner/reviewer` for each step.
If assignment is missing, the plan is incomplete and should not proceed.

## 14) PR and Branch Visibility

- Only Claude Code opens PRs and merges.
- If work is done on a branch, report the branch name in the execution report.
- Claude Code must fetch/pull that branch before review; otherwise changes are invisible.

## 15) Hooks / Orchestration

- Hooks live under `.tasks/hooks/` (optional).
- Supported phases: `pre-task`, `post-task`, `pre-commit`, `post-commit`.
- Only Claude Code triggers hooks.
- Each hook run must log to `.tasks/logs/` (what ran + outputs).

## 16) Subtask Handoff

Subtasks live inside the parent `handoff/task-XXX.md`:

```
## Subtasks
- id: task-XXX/1
  assigned_to: codex
  status: done|partial|blocked
  summary: ...
  changes: ...
  tests: ...
  artifacts: ...
  issues: ...
```

Execution agents only update their own subtask block; Claude Code consolidates.

## 17) Collaboration Defaults

- Roles: Claude Code = planning/review/PR; Codex = implementation/tests; Gemini CLI = execution/logs; AI IDEs = execute-only.
- Plan steps must include `assigned_to`, `owner`, `reviewer`, `difficulty`.
- Report in three phases when possible: start / progress / done.
- If you detect unexpected changes, stop and report to Claude Code.
- Branch naming: `agent/<name>/<task-id>`; report branch names in execution reports.
- Tests: if skipped, report `tests: none (reason)`.
- Subtask results must list `changes` + `artifacts`.

## 18) Accept or Handoff

Execution agents must explicitly accept or decline a subtask.
If declined, notify Claude Code and propose a different assignee.
Claude Code confirms reassignment in `handoff/task-XXX.md`.

## 14) Task Relay Protocol

To hand off work from Agent A to Agent B:

1. **Agent A** (Completer):
   - Marks current task `completed` in `registry.json`.
   - Updates `current-session.md` **"Active Task"** to the _next_ ID.
   - Sets `current-session.md` **"Status"** to `ready_for_execution`.
   - Updates **"Instructions"** in `current-session.md` for Agent B.
   - Ends session with string: `RELAY TO [Agent B]: [Next Task ID]`

2. **Agent B** (Receiver):
   - Starts session by reading `handoff/current-session.md`.
   - Confirms **"Active Task"** and **"Assigned To"** match.
   - Begins execution immediately.

## 15) Branch Sync Rule for `.tasks/`

To avoid information asymmetry between agents on different branches:

1.  **All `.tasks/` updates** (registry.json, current-session.md, task-XXX.md) should be committed to a **shared tracking branch** (e.g., `main` or `dev`), OR merged back promptly.
2.  **Post-Delegation Sync**:
    - After Agent B completes a delegated task on a feature branch, it MUST merge `.tasks/` updates back to the main tracking branch OR inform the user to do so.
    - Command: `git checkout main && git merge <feature-branch> --no-edit`
3.  **Agent Startup Check**:
    - Before reading `.tasks/`, pull latest from shared branch: `git pull origin main --rebase`
