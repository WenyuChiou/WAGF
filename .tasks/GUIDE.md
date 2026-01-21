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

## 3.1) Status Synchronization

To ensure `registry.json` and handoff files stay in sync:

**Validation Script**: `.tasks/scripts/validate_sync.py`

```bash
# Check all tasks for status mismatches
python .tasks/scripts/validate_sync.py

# Check specific task
python .tasks/scripts/validate_sync.py --task Task-028

# Auto-fix mismatches (use with caution)
python .tasks/scripts/validate_sync.py --fix
```

**When to Run**:
- Before committing `.tasks/` changes
- After updating task status in registry.json
- When switching between agents

**Expected Output**:
- [OK] marks synchronized tasks
- [X] marks mismatches with location and conflicting values
- [RECOMMENDATION] suggests running with --fix if issues found

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

## 6.2) Handoff Templates

Two standardized templates are provided:

**Simple Template** (`.tasks/templates/handoff-simple.md`):
- Use for: Single-agent tasks, <5 subtasks, straightforward implementation
- Structure: Metadata, Objective, Changes Summary, Verification, Next Steps
- Example: Bug fixes, simple feature additions, documentation updates

**Complex Template** (`.tasks/templates/handoff-complex.md`):
- Use for: Multi-agent coordination, >5 subtasks, complex architectural changes
- Structure: Metadata, Objective, Agent Assignment Matrix, Design Decisions, Subtasks (Problem/Solution/Evidence), Data Flow, Risks & Rollback, Verification, Artifacts, Notes for Next Agent
- Example: Framework refactoring, multi-step integrations, system-wide changes

**Template Selection Rule**:
- If uncertain, prefer the complex template (better to have too much structure than too little)
- Claude Code chooses template when creating new `handoff/task-XXX.md` files
- Once chosen, stick with the same template for the entire task lifecycle

## 6.1) Ownership

- Only repo-assigned agents (Codex, Claude Code, Gemini CLI) update `.tasks/`.
- Do not mix personal task systems or other agents' logs into this repo.
- Other AI IDEs (e.g., antigravity) must report results to Claude Code instead of writing `.tasks/` directly.

## 7) Artifacts rules

Put outputs in `artifacts/` or project result folders.
Log artifact paths in handoff and registry.

## 7.1) Centralized Artifact Registry

**Registry File**: `.tasks/artifacts-index.json`

**Purpose**: Centralized tracking of all produced files with metadata

**Structure**:
```json
{
  "task_id": "Task-XXX",
  "subtask_id": "XXX-A",
  "file": "path/to/file.py",
  "type": "code|config|data|script|template|registry",
  "produced_by": "Claude Code|Codex|Gemini CLI",
  "timestamp": "2026-01-21T14:30:00Z",
  "description": "Brief description of artifact purpose"
}
```

**When to Update** (MANDATORY):
- **Immediately after** creating any new file (scripts, templates, docs, code)
- **Immediately after** modifying any tracked file significantly
- When completing a subtask that produces artifacts
- Before marking a task as completed

**How to Update**:
1. Add new entry to the `artifacts` array in `.tasks/artifacts-index.json`
2. Update `last_updated` timestamp to current UTC time
3. Include: task_id, subtask_id, file path, type, producer, timestamp, description

**Example Entry**:
```json
{
  "task_id": "Task-XXX",
  "subtask_id": "XXX-A",
  "file": ".tasks/CHANGELOG.md",
  "type": "documentation",
  "produced_by": "Claude Code",
  "timestamp": "2026-01-21T16:00:00Z",
  "description": "Created project-wide changelog"
}
```

**Verification**: Run `.tasks/scripts/validate_artifacts.py` (future tool) to check:
- All listed files exist
- No duplicate entries
- Timestamps are valid

**IMPORTANT**: If you create/modify a file but forget to update artifacts-index.json, this breaks the artifact tracking system. Always update both together.

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

## 10.1) Blocked Task Management

**New Blocker Format** (registry.json):
```json
{
  "id": "XXX-G",
  "status": "blocked",
  "blocker": {
    "reason": "Waiting for 028-C/D file moves to complete",
    "depends_on": ["028-C", "028-D"],
    "unblock_trigger": "all_dependencies_complete",
    "unblock_action": "python run_unified_experiment.py --args",
    "blocked_at": "2026-01-21T06:30:00Z"
  }
}
```

**Dependency Checker**: `.tasks/scripts/check_unblock.py`

```bash
# Check all blocked tasks
python .tasks/scripts/check_unblock.py

# Check specific task
python .tasks/scripts/check_unblock.py --task Task-028

# Auto-unblock ready tasks
python .tasks/scripts/check_unblock.py --fix
```

**Unblock Flow**:
1. Agent completes dependency subtask (e.g., 028-C)
2. Updates status to "completed" in registry.json
3. Runs `check_unblock.py` to identify ready tasks
4. Script automatically updates blocked tasks to "ready_for_execution" (if --fix used)
5. Adds "unblocked_at" timestamp to blocker metadata

**Expected Output**:
- [READY] marks tasks that can be unblocked
- [BLOCKED] marks tasks still waiting for dependencies
- Lists missing dependencies for each blocked task
- [RECOMMENDATION] suggests running with --fix to auto-unblock

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
   - Ends session with explicit RELAY message:

```
RELAY TO [Next Agent]: task-[id] ready

Branch: [git branch name]
Status in registry.json: ready_for_execution
Artifacts: [list of produced files]
Unblock action: [if applicable]
Context: [1-2 sentences summary of what was done]
```

2. **Agent B** (Receiver):
   - Starts session by reading `handoff/current-session.md`.
   - Confirms **"Active Task"** and **"Assigned To"** match.
   - Reads RELAY message for context
   - Begins execution immediately.

**RELAY Message Guidelines**:
- Always include branch name (critical for PR reviews)
- List key artifacts (helps next agent locate outputs)
- Provide concise context (avoids need to re-read full history)
- If unblocking a task, include the action command from blocker metadata

## 15) Branch Sync Rule for `.tasks/`

To avoid information asymmetry between agents on different branches:

1.  **All `.tasks/` updates** (registry.json, current-session.md, task-XXX.md) should be committed to a **shared tracking branch** (e.g., `main` or `dev`), OR merged back promptly.
2.  **Post-Delegation Sync**:
    - After Agent B completes a delegated task on a feature branch, it MUST merge `.tasks/` updates back to the main tracking branch OR inform the user to do so.
    - Command: `git checkout main && git merge <feature-branch> --no-edit`
3.  **Agent Startup Check**:
    - Before reading `.tasks/`, pull latest from shared branch: `git pull origin main --rebase`
