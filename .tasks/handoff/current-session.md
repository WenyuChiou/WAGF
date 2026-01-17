
---

## Session Summary (2026-01-16)
- Task 4-7 scope notes moved to handoff/task-003.md to keep current-session.md short.


---

## Update (2026-01-16)
- Clarified .tasks ownership and scoping: only repo-assigned agents (Codex, Claude Code, Gemini CLI) update .tasks; others must not mix their own task systems.
- Clarified handoff hygiene: keep current-session.md short and move details to handoff/task-XXX.md.


---

## Update (2026-01-17)
- Fixed .tasks/registry.json encoding (UTF-8 BOM) to remove garbling; normalized task-010 description/notes.


---

## Update (2026-01-17)
- Added Claude pending items under handoff/task-003.md (task-003 still in progress; untracked MA assets and analysis drafts awaiting decision).


---

## Update (2026-01-17)
- Clarified .tasks rule: new work must be recorded in egistry.json before execution; do not rely on private model memory.


---

## Update (2026-01-17)
- Rebuilt .tasks/registry.json from last good commit (dd97bc3) to fix encoding corruption; marked task-003 completed and preserved task-010 details.


---

## Update (2026-01-17)
- Added rule: non-repo AI IDEs (e.g., antigravity) must report to Claude Code; they must not write .tasks/ directly.


---

## Update (2026-01-17)
- Clarified execution-only agents: do not edit .tasks; report results to Claude Code. If 
ext_step is missing, wait for Claude planning.


---

## Update (2026-01-17)
- Added execution report format to .tasks/README.md and .tasks/GUIDE.md for non-Claude agents.


---

## Update (2026-01-17)
- Added Micro-plan policy to .tasks/README.md and .tasks/GUIDE.md (small work logs only; multi-step work requires task files).

