# Expert Panel Review: WAGF Framework Architecture Diagram

**Target**: Nature Water (Analysis format)
**Date**: 2026-02-23
**Diagram under review**: `examples/multi_agent/flood/flowchart/framework.drawio.png`
**Reviewers**: Nature Water Editor (NW), Agent-Based Modelling Specialist (ABM), Visual Design / Scientific Figure Specialist (VD)

---

## 1. Individual Assessments

### Reviewer NW — Nature Water Editorial Perspective

**Overall verdict**: MAJOR REVISION REQUIRED. The diagram in its current form would likely be flagged by Nature Water production editors and could trigger a desk rejection of the figure.

**Strengths:**
- The three-layer separation (LLM Layer, Governed Broker, Environment) correctly mirrors the paper's architecture.
- The retry loop from Validator back to the LLM Layer captures a key governance mechanism.
- The inclusion of Auditor / audit traces is important for reproducibility claims.

**Problems:**

1. **Visual language is wrong for NW.** Nature Water system diagrams use clean geometric shapes, thin lines, muted palettes, and typographic hierarchy — not clipart icons (robot faces, shield emblems, clipboard icons, piggy banks, globes). Compare with the paper's own Fig 1 and Fig 2, which use standard matplotlib output with no decorative elements. The diagram looks like a software product brochure, not a scientific figure.

2. **Color is decorative, not informative.** Four background fills (blue, pink/mauve, green, yellow/beige) do not map to a consistent variable. NW convention: color encodes a *measured or categorical variable*, never ambient decoration. The existing Fig 1 uses exactly three colors (blue = governed, red = ungoverned, yellow = A1) with consistent meaning across all four panels.

3. **Missing NW figure conventions:**
   - No panel labels — (a), (b), etc.
   - No "Figure N |" title in the NW format
   - No scale-free, vector-clean rendering — the current PNG has aliased edges
   - Icons are raster clipart inserted into a draw.io canvas; NW requires vector or high-resolution (300+ dpi) figures

4. **Too CS-oriented for NW readership.** Terms like "Parser", "Validator", "Auditor", "Context Builder", "Memory & Retrieval" are software engineering vocabulary. NW readers think in terms of "institutional constraints", "physical feasibility checks", "behavioural theory alignment". The paper itself uses this water-science vocabulary — the diagram should match.

5. **The paper's key insight is invisible.** The abstract leads with *adaptive exploitation* and *feasibility boundaries*. The diagram shows generic software plumbing. A NW figure should make the *water science* visible — where do physical constraints enter? Where does institutional compliance happen? Where does the agent's reasoning become visible?

6. **"Evironment" typo** — minor but unacceptable for a Nature portfolio journal.

---

### Reviewer ABM — Agent-Based Modelling Specialist

**Overall verdict**: MAJOR REVISION. Architecturally accurate at the top level but missing the components that make the paper's contribution distinctive.

**Accuracy check (against Methods):**

| Paper describes | Diagram shows | Match? |
|----------------|---------------|--------|
| Three-layer architecture (LLM, broker, simulation) | Three colored regions | Partial — names differ |
| Six-step validation pipeline | Single "Validator" box with shield icon | NO — this is the paper's core contribution and it's invisible |
| Context builder with tiered read-only signals | "Context Builder" box with eye icon | Partial — tiers not shown |
| Retry with early-exit on repeated rule violations | "Retry with violated rule" arrow | YES (but early-exit not labeled) |
| Audit traces (JSONL) | "Auditor" box | YES |
| Declarative YAML configuration (skill registries, agent types, governance rules) | Not shown | NO |
| Domain-agnostic broker core | Not shown | NO |
| Two domains (irrigation + flood) | Not shown | NO |

**Critical gaps:**

1. **The six-step validation pipeline is collapsed into a single box.** The paper spends an entire paragraph on schema validation -> skill legality -> physical feasibility -> institutional compliance -> magnitude plausibility -> theory consistency. This is the mechanistic core. The diagram should show it.

2. **Domain configurability is invisible.** The paper's central claim is that the broker core is fixed and all domain knowledge enters through YAML configuration. The diagram shows a monolithic system with no indication of where domain boundaries live. For ABM reviewers, this is the difference between "yet another custom ABM" and "a reusable governance architecture."

3. **The A1 ablation cannot be conveyed.** If the validator is a single box, there is no way to visually indicate "remove one rule from this pipeline." The ablation is a key result (Introduction P7, Results, Discussion). A well-designed figure would let you point to a specific pipeline stage and say "we removed this."

4. **Agent heterogeneity is invisible.** The diagram shows three identical "Agent" icons. The paper describes 78 irrigation agents with heterogeneous seniority, storage, and basin membership, and 100 flood agents with heterogeneous income, tenure, and flood zone. Even a schematic indication of heterogeneity (different shading, different labels) would improve accuracy.

5. **The "Reflection" component shown at bottom-left does not appear in the Methods section.** If this is the surprise-weighted memory (Group C), it should be labeled as such or removed, since the paper states "Group C is not analysed in this paper."

6. **No indication of the temporal loop.** ABMs are inherently dynamic. The diagram is static — no indication that this cycle repeats yearly for 42 or 10 years.

---

### Reviewer VD — Scientific Figure / Visual Design Specialist

**Overall verdict**: REDESIGN. The current diagram fails Nature Water's figure guidelines on multiple dimensions.

**Assessment against NW figure standards:**

| Criterion | NW standard | Current diagram | Gap |
|-----------|-------------|-----------------|-----|
| Resolution | 300 dpi minimum, vector preferred | draw.io PNG, ~72 dpi | FAIL |
| Font | Consistent sans-serif, 7-9 pt minimum | Mixed sizes, some too small to read | FAIL |
| Color | Purposeful, accessible, max 3-4 | 5+ decorative fills | FAIL |
| Icons/clipart | Never | Robot faces, shields, clipboards, piggy banks, globes, locks, clocks, thinking person | FAIL |
| Panel labels | (a), (b), (c) lowercase bold | None | FAIL |
| White space | Generous margins, breathing room | Packed, cluttered | FAIL |
| Arrows | Thin, consistent weight, labeled when ambiguous | Multiple styles (solid, dashed), multiple colors, inconsistent weight | PARTIAL |

**Specific design problems:**

1. **Icon overload.** Every component has a decorative icon (robot, eye, gear, shield, clipboard, lock, globe, clock, thinking person). These add visual noise without encoding information. In NW figures, if an icon does not encode a variable, it should not exist.

2. **Too many visual channels used simultaneously.** Background color, border color, icon, text style, arrow color, arrow dash pattern, arrow direction — all competing for attention. Scientific figures should use 2-3 visual channels maximum.

3. **No clear reading order.** The eye scans from the LLM Layer (top right) to Context Builder (left) to Governed Broker (middle) to Environment (bottom right) to Memory (bottom left) to Reflection (further bottom left) — a zigzag that does not match the logical flow described in the Methods (context assembly -> LLM proposal -> governance validation -> execution -> environment update -> memory update).

4. **The "Governed Broker" region (pink/mauve) draws attention through color saturation but contains only three boxes.** The six-step pipeline — the paper's core mechanism — deserves proportionally more visual space.

5. **Text hierarchy is flat.** Layer names, component names, and arrow labels are all similarly sized. A reader cannot distinguish structural levels from implementation details at a glance.

---

## 2. Cross-Discussion

**NW**: The fundamental problem is that this diagram was designed for a software engineering audience — perhaps a README, a conference poster, or an arXiv preprint. Nature Water is a water science journal. The diagram must speak water science first, computation second.

**ABM**: Agreed. But I want to preserve the validation pipeline detail. For ABM reviewers, the six-step breakdown is what distinguishes this from black-box LLM-agent work. We need both: water-science framing AND mechanistic detail.

**VD**: Those goals are compatible. The solution is a multi-panel figure:
- Panel (a): high-level architecture showing the water science flow (context -> reasoning -> governance -> execution -> feedback), using NW-appropriate visual language
- Panel (b): expanded view of the governance pipeline showing the six validation steps, with one step highlighted or removable to indicate the A1 ablation capability

**NW**: I like the two-panel approach. Panel (a) should be what a hydrologist sees first — the simulation loop with water-science labels. Panel (b) is what an ABM reviewer digs into — the governance mechanism.

**ABM**: Could we add a panel (c) showing how domain configuration plugs in? Even a simple schematic: one broker core, two sets of YAML files (irrigation rules, flood rules), two simulation outputs. That would visually communicate the domain-agnostic claim.

**VD**: Three panels is the NW maximum for a system diagram. We can do (a) + (b) + (c) if each is clean and focused. But if forced to choose, (a) + (b) is sufficient. The YAML configuration can be mentioned in the caption.

**NW**: The caption should do heavy lifting. NW captions are typically 50-100 words and can reference specific panel elements. Put the YAML/configuration detail there.

---

## 3. Consensus Recommendations

### REMOVE

| Element | Reason |
|---------|--------|
| All clipart icons (robot, shield, clipboard, eye, lock, globe, clock, thinking person) | NW does not use clipart; icons add noise, not information |
| Decorative background fills (blue, pink, green, beige) | Color must encode a variable, not decorate a region |
| "Parser" / "Auditor" / "Context Builder" as primary labels | Software engineering vocabulary; replace with water-science terms |
| "Reflection" component | Not analyzed in the NW paper; if included, mislabels architecture |
| "Memory & Retrieval" as a standalone component | Merge into the feedback loop; NW paper does not foreground memory architecture |
| Separate "Action Execution" and "Environment" boxes | Combine into "Simulation Engine" to match Methods vocabulary |

### CHANGE

| Current | Proposed | Reason |
|---------|----------|--------|
| Single "Validator" box | Six-step pipeline (schema -> legality -> physical -> institutional -> magnitude -> theory) | Core contribution; must be visible |
| Three identical agent icons | "Agent population" box with annotation "78 irrigation / 100 flood agents" | Matches paper's two-domain framing |
| Pink/magenta "governance flow" arrows | Single color for all arrows; use line weight or dash pattern for primary vs. feedback flow | Reduce visual channels |
| "Retry with violated rule" label | "Governance feedback (max 3 retries, early exit on repeated rule)" | Precision matters for Methods accuracy |
| "Evironment" | "Environment" | Typo |
| "Response & Skill Proposal" arrow label | "Structured proposal (skill + reasoning + constructs)" | Matches Methods description |
| Background color blocks | Thin borders or light grey shading to delineate regions; white internal background | NW convention |

### ADD

| Element | Reason |
|---------|--------|
| Panel labels (a), (b), optionally (c) | NW mandatory |
| "Figure N | Title" in NW format | NW mandatory |
| Panel (b): Exploded view of the six-step validation pipeline, with one step (e.g., "demand ceiling") visually removable or highlighted | Communicates A1 ablation capability |
| Temporal annotation: "Repeat annually" or a cycle arrow with "t = 1...T" | ABMs are dynamic; the loop must be visible |
| YAML/configuration mention in caption or as a small annotation | Domain-agnostic claim needs visual support |
| Caption (50-100 words) referencing panels and key mechanisms | NW standard |

### REDESIGN SPECIFICATION

**Panel (a) — System Architecture (main flow)**

```
[Agent Population] --(structured proposal)--> [Governance Broker] --(validated action)--> [Simulation Engine]
       ^                                              |                                        |
       |                                    (feedback if rejected)                             |
       |                                                                                       |
       +--------(tiered context: personal state, social signals, system state)--<--(env update)--+
```

- Horizontal left-to-right flow for the main pipeline
- Clean boxes with thin black borders, white or very light grey fill
- One accent color (the blue used in Fig 1 "governed" condition) for the Governance Broker box only — this is the paper's contribution
- Arrow labels in 7-8 pt sans-serif
- "Repeat annually (t = 1...T)" annotation on the feedback loop
- Agent Population box annotated: "LLM agents (Gemma-3 4B)" with sub-annotation "Irrigation: 78 agents, 42 yr | Flood: 100 agents, 10 yr"

**Panel (b) — Governance Pipeline (exploded view)**

```
Proposal --> [1. Schema] --> [2. Skill legality] --> [3. Physical feasibility] --> [4. Institutional compliance] --> [5. Magnitude plausibility] --> [6. Theory consistency] --> Validated
```

- Horizontal chain of six numbered boxes
- One box (4. Institutional compliance) highlighted with a dashed border or distinct shading to indicate "removable rule (A1 ablation)"
- Caption note: "Dashed border indicates the demand ceiling rule removed in the A1 ablation experiment"
- Annotation below: "ERROR-level violations trigger retry (max 3); WARNING-level violations log but allow execution"

**Optional Panel (c) — Domain Configuration**

```
                +-- [Irrigation YAML] --> 78 CRSS agents, 42-yr simulation
[Broker Core] --+
                +-- [Flood YAML] -------> 100 household agents, 10-yr simulation
```

- Minimal: one box branching to two domain-specific configurations
- If space permits; otherwise fold into caption

### COLOR PALETTE

Align with the paper's existing figures:
- **Blue** (#4472C4 or similar — matches Fig 1/Fig 2 "governed"): Governance Broker box and pipeline
- **Light grey** (#F2F2F2): Background regions if needed
- **Black**: All text, arrows, borders
- **One warm accent** (optional): Dashed highlight on the removable A1 rule

No other colors. Two colors plus black is sufficient for a system diagram.

### PRODUCTION FORMAT

- Export as vector PDF (not PNG) for Nature submission
- Minimum 300 dpi if rasterized
- Font: Arial or Helvetica, 7-9 pt body, 9-11 pt panel titles
- Line weight: 0.5-1.0 pt for borders, 1.0-1.5 pt for arrows
- Render in matplotlib, Inkscape, or Adobe Illustrator — not draw.io (which produces non-standard SVG that NW production may reject)

---

## 4. Priority Ranking

| Priority | Action | Effort |
|----------|--------|--------|
| P0 (blocking) | Remove all clipart icons | Low |
| P0 (blocking) | Remove decorative background colors | Low |
| P0 (blocking) | Fix "Evironment" typo | Trivial |
| P1 (essential) | Redesign as 2-panel figure with NW conventions | High |
| P1 (essential) | Show six-step validation pipeline explicitly | Medium |
| P1 (essential) | Add panel labels, NW figure title format | Low |
| P1 (essential) | Export as vector PDF at publication resolution | Low |
| P2 (recommended) | Add A1 ablation visual indicator on pipeline | Medium |
| P2 (recommended) | Add temporal loop annotation | Low |
| P2 (recommended) | Add domain configuration annotation (panel c or caption) | Low |
| P3 (nice to have) | Add two-domain branching panel (c) | Medium |

---

## 5. Final Verdict

**REDESIGN REQUIRED.** The current diagram is architecturally reasonable but visually and editorially incompatible with Nature Water. A clean two-panel redesign — (a) system architecture loop with water-science vocabulary, (b) exploded six-step governance pipeline with A1 ablation indicator — would serve the paper well. The diagram should be rebuilt from scratch in a publication-quality tool (matplotlib/tikz/Illustrator), not patched in draw.io.

**Estimated effort**: 4-6 hours for a clean redesign and vector export, assuming the designer has access to the Methods section and the existing Fig 1/Fig 2 color palette.

---

*Panel generated by: NW Editor, ABM Specialist, Visual Design Specialist*
*Consensus: 3/3 agree on REDESIGN verdict*
