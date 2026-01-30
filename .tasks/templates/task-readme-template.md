# Task-XXX: [Task Title]

> **Status**: [In Progress | Complete | On Hold]
> **Version**: v0.XX.0
> **Total Tests**: [N] passing
> **Dependencies**: [List dependencies, e.g., FAISS, NetworkX]
> **Created**: YYYY-MM-DD
> **Last Updated**: YYYY-MM-DD

---

## Overview

[1-2 paragraphs describing the task objectives and background]

| Phase | Feature | Complexity | Tests | Status |
|-------|---------|------------|-------|--------|
| **XXX-A** | [Feature name] | [Low/Medium/High] | [N] | [✅/⏳/🔲] |
| **XXX-B** | [Feature name] | [Low/Medium/High] | [N] | [✅/⏳/🔲] |

---

## Literature Foundation

| Paper | Key Contribution | Applied In |
|-------|-----------------|------------|
| **[Author]** ([Year]) | [Contribution description] | [Module name] |

### Key Citations (Add to Zotero)

1. **[Author], [Initials]. ([Year])**
   - Title: [Paper title]
   - Journal: [Journal name], [Volume]([Issue]), [Pages]
   - DOI: [DOI link]

---

## Quick Start

```python
from [module] import (
    [Class1],
    [Class2],
)

# Usage example
example = Class1()
result = example.method()
```

---

## Phase Details

### XXX-A: [Subtask Title]

**Problem**: [Problem description]

**Solution**: [Solution description]

```python
# Code example
from module import Class
instance = Class(param=value)
result = instance.method()
```

**Files**:
- `path/to/file1.py` (new/modified)
- `path/to/file2.py` (new/modified)

**Tests**:
- `tests/test_xxx.py` ([N] tests)

---

### XXX-B: [Subtask Title]

**Problem**: [Problem description]

**Solution**: [Solution description]

**Files**:
- `path/to/file.py`

---

## Performance Impact

| Metric | Before | After |
|--------|--------|-------|
| [Metric name] | [value] | [value] |

---

## Changes Summary

### Files Created

| File | Description |
|------|-------------|
| `path/to/new_file.py` | [Description] |

### Files Modified

| File | Changes |
|------|---------|
| `path/to/existing.py` | [Change description] |

---

## Running Tests

```bash
# All Task-XXX tests
pytest tests/test_xxx_a.py tests/test_xxx_b.py -v

# Individual phases
pytest tests/test_xxx_a.py -v  # XXX-A
pytest tests/test_xxx_b.py -v  # XXX-B
```

---

## Changelog

| Date | Change |
|------|--------|
| YYYY-MM-DD | XXX-A: [Description] complete |
| YYYY-MM-DD | XXX-B: [Description] complete |

---

## References

- Plan: `C:\Users\wenyu\.claude\plans\[plan-file].md`
- Handoff: `.tasks/handoff/task-XXX.md`
- Registry: `.tasks/registry.json` (Task-XXX entry)
