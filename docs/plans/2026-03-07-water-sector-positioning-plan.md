# Water-Sector Positioning Alignment Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align framework-facing documentation so WAGF is presented as a water-sector-first governance framework with an extensible core.

**Architecture:** Keep the reusable governance-core language, but anchor the repository identity in human-water systems. Reference non-water extensibility only as a secondary extension path, not the main claim.

**Tech Stack:** Markdown docs, repo structure, grep-based verification, git commits

---

### Task 1: Align top-level README positioning

**Files:**
- Create: `docs/plans/2026-03-07-water-sector-positioning-plan.md`
- Modify: `README.md`

**Step 1: Update the tagline and opening description**

- Replace overly generic phrasing with water-sector-first wording.

**Step 2: Update domain-pack description**

- Keep flood, irrigation, and multi-agent flood as primary water-sector reference packs.
- Keep extensibility language, but frame it as a secondary path.

**Step 3: Verify wording**

Run:

```bash
rg -n "domain-agnostic|non-water|water sector|human-water systems" README.md
```

**Step 4: Commit**

```bash
git add README.md docs/plans/2026-03-07-water-sector-positioning-plan.md
git commit -m "docs: align water-sector positioning"
```

### Task 2: Align developer guides

**Files:**
- Modify: `docs/guides/domain_pack_guide.md`
- Modify: `docs/guides/experiment_design_guide.md`

**Step 1: Adjust guide introductions**

- Present water-sector work as the home domain.
- Keep extensibility language, but describe it as optional follow-on use.

**Step 2: Verify wording**

Run:

```bash
rg -n "flood-only|non-water|water sector|home domain|optional extension" docs/guides/domain_pack_guide.md docs/guides/experiment_design_guide.md
```

**Step 3: Commit**

```bash
git add docs/guides/domain_pack_guide.md docs/guides/experiment_design_guide.md
git commit -m "docs: position WAGF as water-sector first"
```
