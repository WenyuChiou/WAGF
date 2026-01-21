# Task-XXX: [Title]

## Metadata

- **ID**: Task-XXX
- **Type**: [feature|bug_fix|refactor|verification|documentation]
- **Priority**: [high|medium|low]
- **Owner**: [Agent Name]
- **Reviewer**: [Reviewer Name]
- **Status**: [pending|in_progress|completed|blocked]
- **Created**: YYYY-MM-DDTHH:MM:SSZ
- **Completed**: YYYY-MM-DDTHH:MM:SSZ (if applicable)
- **Dependencies**: [Task-XXX, Task-YYY]

## Objective

[Detailed description of what this task aims to achieve, including context and motivation]

## Agent Assignment Matrix

| Subtask | Assigned Agent | Prerequisites | Status | Started | Completed | Report |
|---------|----------------|---------------|--------|---------|-----------|--------|
| XXX-A   | Agent Name     | None          | DONE   | 2026-01-21T06:00Z | 2026-01-21T08:00Z | [OK] |
| XXX-B   | Agent Name     | XXX-A         | DONE   | 2026-01-21T08:00Z | 2026-01-21T10:00Z | [OK] |
| XXX-C   | Agent Name     | XXX-B         | PENDING| -       | -         | -    |

## Design Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| [Decision 1] | Option A, Option B | Option A | [Why Option A was chosen] |
| [Decision 2] | Option X, Option Y | Option Y | [Why Option Y was chosen] |

## Subtasks

### XXX-A: [Subtask Title]

**Problem**: [What was the issue or requirement?]

**Solution**: [How was it resolved?]

**Evidence**:
```
[Code snippet, log output, or link to artifact]
```

**Status**: [DONE/PENDING/BLOCKED]

---

### XXX-B: [Subtask Title]

**Problem**: [What was the issue or requirement?]

**Solution**: [How was it resolved?]

**Evidence**:
```
[Code snippet, log output, or link to artifact]
```

**Status**: [DONE/PENDING/BLOCKED]

---

## Data Flow / Architecture

[If the task involves complex interactions, include a diagram or textual description]

```
Example:
ComponentA
  └─> calls ComponentB.method()
      └─> updates StateC
          └─> triggers EventD
```

## Risks & Rollback

| Risk | Mitigation | Rollback Command |
|------|------------|------------------|
| [Risk 1] | [How to prevent/handle] | `git revert <commit>` |
| [Risk 2] | [How to prevent/handle] | `[Specific rollback steps]` |

## Verification

### Test Commands

```bash
# Test 1: [Description]
[command]

# Test 2: [Description]
[command]
```

### Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

### Test Results

[Summary of test execution results, or "Pending"]

## Artifacts

- `path/to/file1` (type: code|config|data) - [Description]
- `path/to/file2` (type: code|config|data) - [Description]

## Notes for Next Agent

[Context, gotchas, recommendations, or anything the next agent should know]

---

## Template Usage Guide

**When to use this template**:
- Multi-agent coordination required
- > 5 subtasks
- Complex architectural changes
- Requires detailed decision documentation
- Cross-system dependencies

**When NOT to use this template**:
- Simple single-agent tasks
- < 5 subtasks
- Straightforward implementation

Use `handoff-simple.md` for simple tasks instead.
