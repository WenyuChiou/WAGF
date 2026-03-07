# Paper3 And Nature Water Separation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Separate the multi-agent flood Paper 3 workspace from the Nature Water manuscript workspace so their drafts, outputs, and working materials stay isolated.

**Architecture:** Keep `examples/multi_agent/flood/paper3/` as the source of truth for MA flood runtime, validation, and MA-specific results. Keep `paper/nature_water/` as the source of truth for the Nature Water manuscript package, with figures/tables/drafts living only under that tree. Move local Paper 3 review materials into an ignored working area and add boundary documentation so future work does not mix the two pipelines.

**Tech Stack:** Markdown, gitignore, filesystem reorganization, existing Python/CLI runners

---

### Task 1: Document workspace boundaries

**Files:**
- Create: `paper/nature_water/README.md`
- Create: `examples/multi_agent/flood/paper3/results/README.md`
- Modify: `examples/multi_agent/flood/paper3/README.md`

**Steps:**
1. Add a Paper 3 boundary section explaining that MA flood runtime and MA results live only under `paper3/`.
2. Add a Nature Water README explaining that `paper/nature_water/` owns manuscript outputs only.
3. Add a results README under `paper3/results/` defining it as the source of truth for MA flood run outputs.

### Task 2: Isolate local working materials

**Files:**
- Modify: `.gitignore`
- Move: `examples/multi_agent/flood/paper3/analysis/*.md`
- Move: `examples/multi_agent/flood/paper3/analysis/*.docx`

**Steps:**
1. Add ignore rules for Paper 3 local working notes and stray local files.
2. Create `examples/multi_agent/flood/paper3/analysis/working/`.
3. Move untracked review, panel, and bug-investigation materials into that working area.

### Task 3: Remove stray files

**Files:**
- Delete: `examples/multi_agent/flood/paper3/nul`
- Delete: `paper/nature_water/'`

**Steps:**
1. Remove the obvious stray zero-byte files.
2. Verify that no runtime or manuscript source files were altered unintentionally.

### Task 4: Verify boundaries

**Files:**
- Verify: `git status --short`

**Steps:**
1. Confirm that `paper3` runtime/results remain under `examples/multi_agent/flood/paper3/`.
2. Confirm that Nature Water outputs remain under `paper/nature_water/`.
3. Confirm that moved working materials no longer pollute the main manuscript/runtime trees.
