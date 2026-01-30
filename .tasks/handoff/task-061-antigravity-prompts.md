# Task-061: Antigravity Image Generation Prompts

> **Purpose**: Generate academic-quality diagrams for the Governed Broker Framework documentation, targeting Water Resources Research (AGU) publication style.
> **Output directory**: `docs/`
> **Style**: Clean technical diagrams, academic/scientific aesthetic, suitable for a water resources journal. No emojis, no playful elements. Use blues, grays, and whites.

---

## Image 1: Memory Evolution Diagram

**Filename**: `docs/memory_evolution_v1_v2_v3.png`
**Replaces**: Broken link at old README.md line 124 (local Gemini cache path, now removed)
**Used in**: Root README.md "Framework Evolution" section (currently uses `docs/framework_evolution.png` — this is an additional diagram)

### Description

A horizontal 3-panel comparison showing the evolution of the memory architecture:

**Panel 1 — v1 (Window Memory)**

- Title: "v1: Availability Heuristic"
- Visual: A simple sliding window of 5 boxes (representing years), with the most recent highlighted
- Key concept: "Recent events only — recency bias"
- Label: "Group A/B Baseline"

**Panel 2 — v2 (Weighted Retrieval)**

- Title: "v2: Context-Dependent Memory"
- Visual: Same 5 boxes but with varying sizes/colors based on importance score
- Formula: S = W_rec _ R + W_imp _ I + W_ctx \* C
- Key concept: "Importance-weighted retrieval"
- Label: "Modular SkillBrokerEngine"

**Panel 3 — v3 (Surprise Engine)**

- Title: "v3: Dual-Process & Active Inference"
- Visual: Two pathways (System 1 and System 2) branching from a "Prediction Error" node
  - Low PE → System 1 (routine, decay-dominant)
  - High PE → System 2 (rational focus, context-dominant)
- Key concept: "Dynamic switching based on surprise"
- Label: "Universal Cognitive Architecture"

**Arrows**: Left to right showing progression. Each panel should be clearly separated.
**Dimensions**: Wide format (1200x400 or similar), high DPI (300+)

---

## Image 2: Example Progression Diagram (Optional)

**Filename**: `docs/example_progression.png`
**Used in**: `examples/README.md` (if generated, otherwise text-only is fine)

### Description

A horizontal flow diagram showing the learning path through the examples:

```
governed_flood  →  single_agent  →  multi_agent  →  finance
(Beginner)         (Intermediate)   (Advanced)      (Extension)
```

Each box shows:

- Example name
- Complexity level
- Key components added at this level:
  - governed_flood: Governance + HumanCentric Memory
  - single_agent: + Groups A/B/C ablation, stress tests, survey mode
  - multi_agent: + Social network, insurance market, government policy
  - finance: + Financial resilience (Catastrophe bonds, flood-resilient investment)

**Style**: Simple boxes connected by arrows, with a "complexity gradient" from light blue (beginner) to dark blue (extension).
**Dimensions**: Wide format (1000x300), high DPI (300+)

---

## Style Guide

- **Font**: Sans-serif (Helvetica, Arial, or similar)
- **Colors**:
  - Primary: #2563EB (blue)
  - Secondary: #64748B (slate gray)
  - Accent: #059669 (green for "success" elements)
  - Background: White
  - Borders: #E2E8F0 (light gray)
- **Line weight**: 1.5-2px for borders, 2-3px for arrows
- **No emojis, no decorative elements** — pure technical illustration
- **Resolution**: 300 DPI minimum for print quality
