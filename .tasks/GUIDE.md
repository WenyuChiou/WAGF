# AI Collaboration Guide

This guide defines how tasks are tracked and handed off in this repo.
Keep it simple, deterministic, and easy to read.

## 1) Start checklist

- Read `handoff/current-session.md`.
- Read `registry.json`.
- Run `git status` to see local changes.
- Confirm no other AI is running the same task.

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
