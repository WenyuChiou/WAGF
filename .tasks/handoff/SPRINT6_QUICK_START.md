# Sprint 6 Quick Start Guide

**For**: Gemini & Codex
**Date**: 2026-01-21
**Status**: ✅ Ready to Start

---

## 📋 Task Overview

**Sprint 6 = Final Verification & Documentation**

Sprint 5 完成了所有代碼重構 ✅
Sprint 6 需要驗證和文檔化這些更改。

---

## 👥 Who Does What?

### Gemini → Testing & Verification
- **Phase 6A**: Run 5-year MA regression test
- **Phase 6B**: Grep audit for MA pollution
- **Time**: 3-4 hours

### Codex → Documentation
- **Phase 6C**: Update ARCHITECTURE.md
- **Phase 6D**: Create migration guide
- **Time**: 3-4 hours

---

## 🚀 Gemini: Start Here

### Step 1: Run Regression Test (Phase 6A)

```bash
cd examples/multi_agent

# Run baseline (if needed)
python run_unified_experiment.py \
  --years 5 --agents 10 --model gemma3:4b \
  --output ../../results/task029_baseline/ \
  --mode survey

# Run verification
python run_unified_experiment.py \
  --years 5 --agents 10 --model gemma3:4b \
  --output ../../results/task029_verification/ \
  --mode survey
```

**What to check**:
- Does it run without errors?
- Are adaptation rates similar (within 5%)?
- Memory/reflection counts reasonable?

**Deliverable**: `.tasks/handoff/task-029-regression-report.md`

---

### Step 2: Grep Audit (Phase 6B)

```bash
# Check for flood-specific terms
grep -r "flood\|buyout\|elevation" broker/ \
  --include="*.py" --exclude-dir=__pycache__ \
  | grep -v "# " | grep -v '"""' | grep -v "DEPRECATION BRIDGE"

# Check for MA field names
grep -r "flood_zone\|flood_experience\|financial_loss" broker/ \
  --include="*.py" --exclude-dir=__pycache__ \
  | grep -v "# " | grep -v '"""' | grep -v "DEPRECATION BRIDGE"
```

**Acceptable exceptions**:
- `broker/interfaces/enrichment.py` - Protocol definitions
- `broker/modules/survey/agent_initializer.py` - DEPRECATION BRIDGE marked code
- Comments and docstrings

**Deliverable**: `.tasks/handoff/task-029-audit-report.md`

---

### Commit When Done:
```bash
git add .tasks/handoff/task-029-*-report.md
git commit -m "test(task-029): verify regression and audit (Phase 6A+6B)

- Ran 5-year MA experiment: metrics within tolerance
- Grep audit confirms no unexpected MA hardcoding

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## 🚀 Codex: Start Here

**Wait for Gemini to finish 6A+6B first!** (Or start in parallel if confident)

### Step 1: Update ARCHITECTURE.md (Phase 6C)

**Read first**:
- [task-029-sprint5-summary.md](.tasks/handoff/task-029-sprint5-summary.md)
- [elegant-honking-harbor.md](C:\Users\wenyu\.claude\plans\elegant-honking-harbor.md)

**Add to ARCHITECTURE.md**:

1. **Section: "Domain-Agnostic Design Patterns"**
   - Protocol-Based Dependency Injection
   - Extensions Pattern
   - Config-Driven Logic

2. **Section: "Migration from v0.28 to v0.29"**
   - Link to migration guide
   - Summarize breaking changes

3. **Update diagrams** (if applicable)

**Example structure**:
```markdown
## Domain-Agnostic Design Patterns (v0.29+)

### 1. Protocol-Based Dependency Injection
[Explain with code examples]

### 2. Extensions Pattern
[Show SurveyRecord → FloodSurveyRecord]

### 3. Config-Driven Logic
[Show YAML → memory tags]
```

---

### Step 2: Create Migration Guide (Phase 6D)

**Create**: `.tasks/handoff/task-029-migration-guide.md`

**Must include**:
1. Breaking changes with before/after code
2. Non-breaking deprecations
3. How to test migration
4. Examples for common scenarios

**Template**: See task-029-sprint6-assignment.md Phase 6D

---

### Commit When Done:
```bash
git add ARCHITECTURE.md .tasks/handoff/task-029-migration-guide.md
git commit -m "docs(task-029): add architecture guide and migration docs (Phase 6C+6D)

- Updated ARCHITECTURE.md with domain-agnostic patterns
- Created migration guide (v0.28 → v0.29)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## ✅ Success Criteria

Sprint 6 complete when:
- [ ] Regression test passes (Gemini)
- [ ] Audit clean (Gemini)
- [ ] ARCHITECTURE.md updated (Codex)
- [ ] Migration guide created (Codex)
- [ ] All commits pushed to main

---

## 📚 Reference Files

- **Full details**: [task-029-sprint6-assignment.md](.tasks/handoff/task-029-sprint6-assignment.md)
- **Sprint 5 summary**: [task-029-sprint5-summary.md](.tasks/handoff/task-029-sprint5-summary.md)
- **Master plan**: [elegant-honking-harbor.md](C:\Users\wenyu\.claude\plans\elegant-honking-harbor.md)
- **Current status**: [current-session.md](.tasks/handoff/current-session.md)

---

## ❓ Questions?

Contact: User (wenyu) or Claude Sonnet 4.5

**Ready to start!** 🚀
