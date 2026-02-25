# 2026-01-21-ai-ide-summary-design.md

## Summary
Add a single AI IDE¡Vfriendly summary file to prevent misreads across multiple task files. This file becomes the canonical, compact ¡§source of truth¡¨ for AI IDE consumption, while existing `.tasks` files remain unchanged for full detail.

## Goals
- Eliminate AI IDE confusion when reading multiple task files.
- Provide a concise, stable, and machine-friendly summary of status and assignments.
- Reduce the chance of ¡§tasks¡¨ being misread or merged.

## Non-Goals
- Replacing `.tasks/registry.json` or handoff docs.
- Changing task schemas or identifiers.

## Proposed Artifact
Create **one canonical summary file**:

```
.tasks/ai-ide-summary.md
```

This file is updated whenever task status changes. It intentionally avoids long narrative and preserves strict formatting to minimize parsing errors.

## File Structure (Strict)

```
# AI IDE Task Summary
last_updated: <ISO-8601 UTC>
source_of_truth: .tasks/registry.json

## ACTIVE
- Task-017 | JOH Stress Testing (Gemma/Llama) | planned | owner=Antigravity

## COMPLETED
- Task-015 | MA System Verification | completed | owner=antigravity
- Task-018 | MA Visualization | completed | owner=antigravity
- Task-024 | Integration Testing & Validation | completed | owner=Claude Code
- Task-027 | Universal v3 MA Integration | completed | owner=Claude Code

## NEXT
- Task-017 (owner: Antigravity)

## NOTES
- Use this file as the only input for AI IDE status queries.
- Full details remain in .tasks/handoff/*.md and registry.json.
```

Rules:
- All lines are single-line bullet entries (no wrapping).
- Use consistent separators: `Task-ID | Title | Status | owner=...`.
- Keep sections in fixed order: ACTIVE ¡÷ COMPLETED ¡÷ NEXT ¡÷ NOTES.
- Do not include multi-line tables (to avoid parsing issues).

## Update Workflow
- Any time task status changes, update `.tasks/ai-ide-summary.md`.
- Update it after modifying `.tasks/registry.json`.
- Optional: add a small helper script later to regenerate from registry.

## Verification
- After update, ensure no line wraps and that sections are present.
- Confirm Active section reflects registry status.

## Adoption
- Start using this file immediately for AI IDE consumption.
- Keep existing task files unchanged for humans and detailed context.
