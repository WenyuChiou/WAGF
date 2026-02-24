# Session Log

## 2026-02-24 Session W (CS briefing + R1 rewrite + Fig 2 update)

### Completed
1. **Professor briefing tables redesigned** — `gen_professor_word_tables.py`:
   - Removed "Change%" column from both tables
   - Removed 95% CI column (n=3 too weak, CI would expose weakness)
   - Removed seed counts from subtitles (user will add after more runs)
   - Removed ±SD from irrigation display values (cleaner for briefing)
   - "Ungov." → "Ungoverned" (full word, both tables)
   - "A1 (No Ceil.)" → "No Ceiling"
   - "Diff" → "Δ (G−U)"
   - "Demand–Mead coupling" → "Demand–reservoir coupling"
   - "Behavioural Rationality (BRI %)" → "Scarcity-rational actions (BRI %)"
   - "EHE" → "Behavioural Diversity" in key findings
   - Added "Bottom line" sentence at top of each table
   - Added "Setup" paragraph explaining agent decisions and governed/ungoverned meaning
   - Expanded footnotes: IBR with concrete example, coupling explained, FQL 2-action limitation disclosed
2. **CS professor agent review** — identified C1-C10 confusing items, M1-M5 missing context
   - Priority fixes applied: context paragraphs, metric renaming, bottom-line framing, FQL explanation
3. **10-minute talking points** — `professor_briefing/10min_talking_points.md` + `.docx`
   - 5-slide structure: Problem (2min) → Framework (3min) → Example (2min) → Results (2min) → Next steps (1min)
   - Key analogy: "governance = type checker for agent decisions"
   - 6 Q&A prepared (seeds, fine-tuning, memorization, cost, model choice, constitutional AI)

4. **R1 Results rewrite** — `section2_v11_results.md`:
   - Opening paragraph restructured: three-way comparison (Governed/Ungoverned/FQL) leads
   - Coupling (r) defined with motivation: "central coordination challenge in shared water systems"
   - FQL moved from buried in paragraph 2 to opening paragraph punchline
   - Explicit logic: Ungov = reasoning without rules, FQL = rules without reasoning, Governed = both
5. **Fig. 2 updated** — `gen_fig2_irrigation.py`:
   - Panel (a) now shows all 4 conditions (added FQL grey dotted line)
   - FQL SD band alpha reduced 0.15→0.08 to declutter
   - Tier threshold lines lightened (#BBBBBB, lw=0.5) to distinguish from FQL
   - Legend moved lower left → upper left
   - Panel (d) y-axis: "Behavioural diversity" → "Behavioural diversity (EHE)"
   - NW expert review: MINOR REVISION → all 4 fixes applied → PASS
6. **Word docs recompiled** (v14)

### Files Modified
- `paper/nature_water/scripts/gen_professor_word_tables.py` — major rewrite
- `paper/nature_water/professor_briefing/professor_summary_IBR_EHE.docx` — regenerated
- `paper/nature_water/professor_briefing/professor_summary_irrigation.docx` — regenerated
- `paper/nature_water/professor_briefing/10min_talking_points.md` — NEW
- `paper/nature_water/professor_briefing/10min_talking_points.docx` — NEW
- `paper/nature_water/scripts/gen_talking_points_docx.py` — NEW
- `paper/nature_water/drafts/section2_v11_results.md` — R1 rewritten
- `paper/nature_water/scripts/gen_fig2_irrigation.py` — Panel (a) + expert fixes
- `paper/nature_water/figures/Fig2_irrigation.png/pdf` — regenerated
- `paper/nature_water/NatureWater_MainText_v14.docx` — recompiled
- `paper/nature_water/NatureWater_SI_v14.docx` — recompiled

---

## 2026-02-24 Session V (NW jargon cleanup + figure promotion + professor review)

### Completed
1. **NW expert panel figure/table sufficiency review** — 3 reviewers (Hydrology, CSS, LLM Methods)
   - 5 MUST FIX + 6 SHOULD FIX identified
   - Key issues: missing Fig citations, Table 3 should be figure, no cross-domain visual, undefined terms
2. **Terminology cleanup** — all 5 submission files + 5 scripts:
   - "A1 (no ceiling)" → "No ceiling" (tables) / "no-ceiling" (prose)
   - "Group A/B/C" → "Ungoverned" / "Governed" / "Governed (HumanCentric memory)"
   - Stripped all changelog blocks from submission files
3. **Figure/table reconfiguration** — 4 figures + 2 tables (was 2 fig + 3 tables):
   - Table 3 (cross-model) → Fig. 4 forest plot (gen_fig3_crossmodel.py), added parameter sizes
   - Flood cumulative adaptation promoted from SI to main-text Fig. 3
   - Fig. 2 regenerated with "No ceiling" labels
   - Fig. 1 regenerated with "ablation" tag (was "A1")
4. **10 professor review fixes applied**:
   - MF-1: Changelog blocks stripped from abstract, results, discussion, methods
   - MF-2: HumanCentric memory disclosed in R4 with equivalence proof (0.636 both conditions)
   - MF-3: Abstract "demand ratio" and "demand–reservoir coupling" defined inline
   - MF-4: Orphan "EHE" acronym removed from Methods LLM section
   - MF-5: BRI↔IBR cross-references added to Table 1 and Table 2 footnotes
   - MF-6: Table 2 footnote clarifies IBR non-significant for Gemma-3 4B
   - MF-7: R4 opens with governed condition disclosure (HumanCentric memory)
   - MF-8: Prior-appropriation defined on first use in Results
   - MF-9: "no-ceiling" capitalization standardized
   - MF-10: Fig. 1 cited in Introduction, Fig. 2 in R1, Fig. 3 in R4
5. **Minor fixes**: Ministral → "Mistral AI" parenthetical, "code-level ceiling" disambiguated from "demand ceiling stabilizer"
6. **Word docs recompiled** (NatureWater_MainText_v14.docx + SI)

### Commit
- `a1c82d8` fix(nw): clear jargon, promote Fig 3-4, apply 10 professor review fixes

---

## 2026-02-24 Session U (NW review fixes + professor briefing + figure polish)

### Completed
1. **Fig 1 line styles**: solid/dashed/dash-dot/dotted for grayscale
2. **Fig 2 error bars**: seed-to-seed std whiskers
3. **Endmatter added**: Data/Code Availability, Author Contributions, etc.
4. **Professor briefing**: Word tables with diff+Change%, clean flood chart
5. **NW pre-submission review** — 3 reviewers, all Minor Revisions
6. **7 critical review fixes**: BRI reframed, temperature limitation, model-size confound, PA softened, premium doubling, EHE→behavioural diversity, shortage interpretation
7. **Terminology**: "strategy diversity" → "behavioural diversity" (17 files)
8. **SI Table 1b**: Governance rule trigger frequency (238 triggers, 97.6% correction)

### Commits
- `590bd78` through `caf7025` (8 commits)

---

## 2026-02-24 Session T (NW figure redesign)
- Okabe-Ito palette, hatching, NW panel labels, terminology review, file cleanup

## 2026-02-23 Session S (NW v14 figures + SA data verification)
- Fig1: 4-panel irrigation; Fig2: flood paired dot + forest plot; data verified

## 2026-02-21 Session R (FQL baseline + expert defense)
## 2026-02-21 Session Q (Paper 3 CACR_raw + reframe)
## 2026-02-21 Session P (NW major restructure)
## Earlier sessions: See previous log entries
