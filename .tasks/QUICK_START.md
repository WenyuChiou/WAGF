# Quick Start Guide for Agents

**Last Updated**: 2026-01-21

---

## For Gemini CLI / Execution Agents

### Step 1: Read Current Task

```bash
cat .tasks/handoff/current-session.md
```

Look for these sections:
- **Active Task**: What task ID is currently being worked on
- **Progress Overview**: Table showing subtask status
- **Next Action**: What YOU specifically need to do

### Step 2: Confirm Your Assignment

Check if **"Assigned To"** column in Progress Overview shows your name (e.g., "Gemini CLI").

### Step 3: Check for Blockers

- If status is **BLOCKED**, check the blocker reason
- Do NOT start work if dependencies are incomplete
- Report back to Claude Code if blocked

### Step 4: Execute Your Subtask

Follow the specific instructions in the **Next Action** section.

**IMPORTANT**:
- Do NOT read the plan file (`.claude/plans/*.md`) - that's for planning, not execution
- Do NOT modify `registry.json` - only update your subtask section in the handoff file
- Do NOT skip tests - always verify your work

### Step 5: Report Results

When done, create a report in this format:

```
REPORT
agent: Gemini CLI
task_id: Task-XXX
subtask_id: XXX-Y
status: done|blocked|partial
changes: [list files modified]
tests: [commands run or "none"]
artifacts: [output files or "none"]
issues: [problems or "none"]
next: [suggested next step or "none"]
```

---

## Common Commands

### Check task status
```bash
python .tasks/scripts/validate_sync.py --task Task-028
```

### Check if any tasks are unblocked
```bash
python .tasks/scripts/check_unblock.py
```

### Run verification test (example for Task-028-G)
```bash
cd examples/multi_agent
python run_unified_experiment.py \
  --model gemma3:4b \
  --years 3 \
  --agents 5 \
  --memory-engine universal \
  --output results_unified/v028_verification
```

---

## File Structure (What to Read)

```
.tasks/
├── QUICK_START.md          ← YOU ARE HERE (read this first)
├── handoff/
│   ├── current-session.md  ← Read this for current task
│   └── task-XXX.md         ← Detailed task documentation (optional)
├── registry.json           ← DO NOT EDIT (Claude Code manages this)
└── GUIDE.md                ← Full workflow guide (reference only)
```

---

## Red Flags - When to Stop and Ask

1. **Import errors** - Report immediately, do not try to fix without coordination
2. **Missing dependencies** - Check if Codex completed prerequisite tasks
3. **Non-ASCII path issues** - You cannot execute, report to Claude Code
4. **Conflicting instructions** - Ask for clarification

---

## Golden Rules

1. **Read `current-session.md` FIRST** - everything you need is there
2. **One task at a time** - complete current subtask before asking for next
3. **Always verify** - run tests, check imports, confirm outputs
4. **Report clearly** - use the REPORT format above
5. **When in doubt, ask** - better to clarify than to break things

---

## Current Task Quick Reference

**Task ID**: Task-028 (Framework Cleanup & Agent-Type Config)

**Your Role**: Gemini CLI

**Current Status**: BLOCKED (waiting for Codex to complete 028-C and 028-D)

**Your Subtask**: 028-G (Run verification tests)

**Blocker**:
- 028-C (Move media_channels.py) - PENDING
- 028-D (Move hazard module) - PENDING

**Next Action**: Wait for Codex to complete file moves, then run:
```bash
cd examples/multi_agent
python run_unified_experiment.py \
  --model gemma3:4b \
  --years 3 \
  --agents 5 \
  --memory-engine universal \
  --output results_unified/v028_verification
```

**Expected Outcome**:
- No import errors
- All agents execute successfully
- Crisis mechanism works (crisis_event/crisis_boosters)
- System 2 triggers on flood events

---

## Need Help?

1. Read `current-session.md` again
2. Check `.tasks/GUIDE.md` for detailed protocols
3. Report to Claude Code with REPORT format
