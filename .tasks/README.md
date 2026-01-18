# .tasks/ overview

This folder holds coordination data for humans and multiple AIs.
Keep it small, readable, and up to date.

## Structure

```
.tasks/
  README.md
  GUIDE.md
  registry.json
  handoff/
    current-session.md
    {task-id}.md
  artifacts/
    claude-code/
    gemini/
    codex/
    shared/
  logs/
    {agent}-{timestamp}.log
  templates/
```

## Core files

- `handoff/current-session.md`: living status, decisions, next steps.
- `registry.json`: task registry (status, done_when, risks, next_step).
- `logs/`: short run logs (what was run, where outputs went, errors).
- `skills-mcp.md`: how to share skills and MCP setup.

## Quick rules

- On "Read task": read `handoff/current-session.md` and `registry.json` first.
- If no next_step, set `next_step` to `none` and ask for planning.
- Artifacts are outputs (csv, plots, summaries). Handoff is status only.
- Keep `current-session.md` short; move long notes to `handoff/task-XXX.md`.
- Only repo-assigned agents update `.tasks/` (Codex, Claude Code, Gemini CLI). Others must not mix their own task systems here.
- Any new work item must be recorded in `registry.json` first (task or plan) before execution.
- Do not rely on private model memory; all plans and task scopes must be written in `.tasks` for handoff.
- Execution-only agents should not edit `.tasks`; they must report results to Claude Code, who owns task records and final review.
- If `next_step` is missing/empty, execution agents must report it and wait for Claude Code to plan and assign work.

## Execution Report Format

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

## Micro-plan Policy

If work is small (single step, <30 minutes, low risk), do not create a new task.
Log a short "Micro-plan" line in `handoff/current-session.md` with outcome.
For multi-step or shared work, create a task entry and a `handoff/task-XXX.md`.

## Assignment Rule

When a plan is created, every step must have `assigned_to` (who executes) and `owner/reviewer`.
Plans without explicit assignment are considered incomplete.

## PR and Branch Visibility

- Only Claude Code opens PRs and merges.
- If work is done on a branch, report the branch name in the execution report.
- Claude Code must fetch/pull that branch before review; otherwise changes are invisible.

## Hooks / Orchestration

- Hooks live under `.tasks/hooks/` (optional).
- Supported phases: `pre-task`, `post-task`, `pre-commit`, `post-commit`.
- Only Claude Code triggers hooks.
- Each hook run must log to `.tasks/logs/` (what ran + outputs).

## Subtask Handoff

Subtasks are recorded inside the parent `handoff/task-XXX.md`:

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

## Accept or Handoff

Execution agents must explicitly accept or decline a subtask.
If declined, notify Claude Code and propose a different assignee.
Claude Code confirms reassignment in `handoff/task-XXX.md`.

## New Task Workflow

When adding a new task:

1.  **Add entry to `registry.json`**: Ensure `id` is unique (e.g., `task-003`).
2.  **Create Handoff File**: You **MUST** create a corresponding markdown file in `handoff/` (e.g., `handoff/task-003.md`).
3.  **Link**: Set the `handoff_file` field in `registry.json` to point to this new file.

## Common commands

- `Start task <id>`
- `Update task`
- `Add todo <item>`
- `Clear todo` (sets `next_step` to `none`)
- `Run test <cmd>`
- `Log artifact <path>`

---

## Agent Compatibility

### Available Executors

| Agent | Path Encoding | Role | Notes |
|:------|:--------------|:-----|:------|
| Claude Code | ✅ Full Unicode | Planner/Reviewer | Task coordination, PR review |
| Codex | ✅ Full Unicode | Executor | CLI agent, good for batch operations |
| Gemini CLI | ❌ ASCII only | Executor | **Blocked** on non-ASCII paths |
| Cursor | ✅ Full Unicode | Executor | AI IDE, good for code editing |
| Antigravity | ✅ Full Unicode | Executor | AI IDE, alternative to Cursor |

### Workarounds for Gemini CLI

If the project is in a non-ASCII path (e.g., `我的雲端硬碟`), Gemini CLI cannot execute file operations. Options:

1. **Reassign to Codex** - CLI agent, handles non-ASCII paths
2. **Reassign to Cursor/Antigravity** - AI IDEs, full Unicode support
3. **Use relative paths** - May work for some operations
4. **Move project** - Last resort: move to ASCII-only path (e.g., `C:\projects\`)

### Best Practices

- When assigning execution tasks, check agent compatibility first
- If Gemini CLI is blocked, reassign to Codex or AI IDE immediately
- For complex code changes, prefer AI IDEs (Cursor/Antigravity)
- For batch operations or tests, prefer CLI agents (Codex)
- Record path-related blockers in `known_issues` section of `registry.json`
