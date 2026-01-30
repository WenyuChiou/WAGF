# Documentation Guide

> **Purpose**: Ensure consistent documentation for every task/version change
> **Created**: 2026-01-29
> **Reference**: Task-051 Documentation Protocol

---

## Mandatory Checklist (Every Task Completion)

Before marking any task as complete, verify ALL items:

```
[ ] 1. Updated .tasks/CHANGELOG.md with version entry
[ ] 2. Updated .tasks/registry.json status to "completed"
[ ] 3. Created/updated docs/task-XXX-description/README.md
[ ] 4. Updated .tasks/handoff/current-session.md (progress)
[ ] 5. Added literature to Zotero (if applicable, tag: Task-XXX)
[ ] 6. Ran tests and documented results
[ ] 7. Listed all created/modified files
```

---

## Directory Structure

```
docs/task-XXX-description/
├── README.md                    # Task overview (REQUIRED)
├── XXX-A-subtask-name.md       # Subtask A details (if needed)
├── XXX-B-subtask-name.md       # Subtask B details (if needed)
└── assets/                     # Diagrams/images (optional)
    └── architecture.png
```

---

## Version Numbering

| Task Number | Version | Example |
|-------------|---------|---------|
| Task-050 | v0.50.0 | Memory Optimization |
| Task-051 | v0.51.0 | Documentation Protocol |
| Task-052 | v0.52.0 | [Next task] |

**Format**: `v0.{task_number}.{patch}`

---

## CHANGELOG Entry Format

```markdown
## [v0.XX.0] - YYYY-MM-DD - Task-XXX [Title]

### Added
- **XXX-A: [Feature]** - [Description] ([N] tests)
- **XXX-B: [Feature]** - [Description] ([N] tests)

### Changed
- `[file.py]` - [Change description]

### Literature References
- [Author] ([Year]). DOI: [DOI]

### Documentation
- Created `docs/task-XXX-description/`
- Updated Zotero with Task-XXX tag

### Tests
- Total: [N] new tests (all passing)

---
```

---

## registry.json Entry Format

```json
{
  "id": "Task-XXX",
  "title": "[Task Title]",
  "status": "completed",
  "type": "[feature/refactor/bugfix]",
  "priority": "[high/medium/low]",
  "owner": "[Claude Code/Codex/Gemini]",
  "created_at": "YYYY-MM-DDTHH:MM:SSZ",
  "completed_at": "YYYY-MM-DD",
  "tests_passed": N,
  "plan_file": "C:\\Users\\wenyu\\.claude\\plans\\[file].md",
  "subtasks": [
    {
      "id": "XXX-A",
      "title": "[Subtask Title]",
      "status": "completed",
      "tests_passed": N
    }
  ],
  "handoff_file": "handoff/task-XXX.md",
  "note": "[Brief description]"
}
```

---

## Literature Management (Zotero)

### Tag System

| Tag | Purpose |
|-----|---------|
| `Task-XXX` | Links to specific task |
| `Memory` | Memory system related |
| `Cognitive-Architecture` | Architecture papers |
| `LLM-Agent` | LLM agent research |
| `Governance` | Governance mechanisms |

### Citation Format in Code

```python
"""
Module description.

References:
- Author, A. (Year). Title. Journal, Vol(Issue), Pages.
  DOI: 10.xxxx/xxxxx

Reference: Task-XXX [Subtask Name]
"""
```

---

## Validation Script

Run before completing any task:

```bash
python .tasks/scripts/validate_docs.py --task XXX
```

This checks:
- [ ] `docs/task-XXX-*/README.md` exists
- [ ] CHANGELOG has v0.XX.0 entry
- [ ] registry.json has Task-XXX entry
- [ ] All referenced files exist

---

## Quick Reference

### Template Location
`.tasks/templates/task-readme-template.md`

### Example Documentation
`docs/task-050-memory-optimization/README.md`

### Validation Script
`.tasks/scripts/validate_docs.py`

---

## Claude Code Integration

When completing a task, Claude Code should:

1. **Before marking complete**:
   - Ask: "Have all documentation items been updated?"
   - Run validation script

2. **Session end reminder**:
   - List modified files
   - Remind about CHANGELOG/registry updates

---

## Troubleshooting

### Missing Documentation Folder

```bash
# Create folder structure
mkdir -p docs/task-XXX-description
cp .tasks/templates/task-readme-template.md docs/task-XXX-description/README.md
```

### Sync Validation Failed

```bash
# Check and fix registry sync
python .tasks/scripts/validate_sync.py --fix
```

---

## Revision History

| Date | Change |
|------|--------|
| 2026-01-29 | Initial version (Task-051) |
