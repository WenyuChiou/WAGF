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
