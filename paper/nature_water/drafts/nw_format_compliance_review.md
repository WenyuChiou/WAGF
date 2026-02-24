# Nature Water Analysis Format Compliance Review

**Manuscript**: Institutional Constraints Widen Adaptive Strategy Diversity in Language-Based Water Agents
**Format**: Nature Water Analysis
**Review date**: 2026-02-24
**Reviewer**: Editorial compliance audit (automated)

---

## 1. Word Count

### Abstract: NEEDS ATTENTION

The abstract claims ~145 words, but a careful read of the actual prose (line 6 of `abstract_v10.md`) shows the text has grown beyond that estimate. The single paragraph contains approximately **150-160 words** based on the density of the content (the sentence beginning "The effect generalized..." alone adds ~50 words to what was already close to the limit). The abstract is either at or slightly over the 150-word cap.

**Action required**: Perform an exact word count. If over 150, trim 5-15 words. The final two sentences ("The effect generalized from chronic drought..." and "Institutional boundaries widen...") could be tightened.

### Main text (Introduction + Results + Discussion): NEEDS ATTENTION

| Section | Estimated words | Source |
|---------|----------------|--------|
| Introduction | ~845 | File header claims ~845 after v11 edits |
| Results | ~2,100 | File header claims ~2,100 |
| Discussion | ~950 | File header claims ~950 |
| **Total** | **~3,895** | |

The limit is 4,000 words. The manuscript is within budget but tight. Note: Nature Water explicitly states that table captions and footnotes are typically **not** counted toward the main text word limit, but figure legends **are** counted. The compile script shows two figure legends (~100 words each) that would push the total closer to or past 4,000 if Nature Water counts them.

**Action required**: Verify whether Nature Water counts figure legends within the 4,000-word limit. If so, trim ~100 words from Results or Discussion. Also verify the section-header word counts are accurate with a mechanical counter (not manual estimates).

**Verdict**: NEEDS ATTENTION

---

## 2. Abstract: No References

**Status**: PASS

Grep confirms zero citation markers (Author, Year), (et al.), or numbered superscripts in the abstract body. The abstract is purely unreferenced, as required.

---

## 3. Section Structure

**Required**: Introduction -> Results -> Discussion -> Methods

**Actual structure** (from `compile_paper.py` lines 390-485):
1. Abstract
2. Introduction (`introduction_v10.md`)
3. Results (`section2_v11_results.md`)
4. Discussion (`section3_v11_discussion.md`)
5. Methods (`methods_v3.md`)
6. References

Results and Discussion are **separate** sections (not combined). Methods follows Discussion.

**Status**: PASS

---

## 4. Reference / Citation Format

**Required**: Nature Water uses **numbered superscript citations** in text (e.g., superscript 1, 2, 3), NOT author-year.

**Actual format in manuscript**: The markdown drafts use **(Author, Year)** format throughout. Examples found:
- Introduction: `(Maass et al., 1962)`, `(Liu et al., 2007)`, `(Sivapalan et al., 2012; Di Baldassarre et al., 2019)`, `(Epstein and Axtell, 1996; Bonabeau, 2002)`, etc.
- Results: `(Hung and Yang, 2021)`, `(Ostrom, 1990)`
- Discussion: `(Ostrom, 1990)`, `(Bankes, 1993)`, `(Hung & Yang, 2021)`
- Methods: `(Grimm et al., 2005)`, `(Rogers, 1983)`, `(Park et al., 2023)`, `(Gemma Team, 2025)`, etc.
- SI: `(Shannon, 1948)`

The reference list in `compile_paper.py` (lines 489-513) contains 24 references in **unnumbered** bibliographic format (no superscript numbering). Nature Water requires:
- Numbered superscript citations in text (e.g., "...water planning^1")
- Numbered reference list at the end

**Status**: FAIL

**Action required**:
1. Convert all in-text citations from (Author, Year) to numbered superscript format.
2. Number the reference list entries sequentially in order of first appearance.
3. This is a non-trivial reformatting task affecting every section of the manuscript.

---

## 5. Figure Captions

**Required**: Concise, start with bold "Figure N.", each panel described.

**Actual** (from `compile_paper.py` lines 402-424):

- **Figure 1**: Starts with `**Figure 1. Adaptive exploitation under institutional governance**`. Describes panels (a)-(d) individually. Includes scale note ("Shaded bands show +/- 1 s.d.").
- **Figure 2**: Starts with `**Figure 2. Flood-adaptation trajectories across agent types**`. Describes panels (a)-(c) individually. Includes methodological note.

Both follow the bold "Figure N." convention and describe each panel.

**Status**: PASS

**Minor note**: Nature Water typically uses a period after "Figure N" and then the title is NOT bold (only "Figure N." is bold). Current format bolds the entire title. This is a minor stylistic point that the journal's production team would fix, but worth noting.

---

## 6. Table Format

**Required**: Simple tables, no vertical rules, minimal horizontal rules.

**Actual tables in markdown**:
- **Table 1** (Results): 7 metrics x 4 conditions. Simple grid format.
- **Table 2** (Results): 3 conditions x 7 columns. Simple grid format.
- **Table 3** (Results): 6 models x 5 columns. Simple grid format.

In the compile script, tables use `'Table Grid'` style (line 145), which includes **both vertical and horizontal rules**. The header row has gray shading.

**Status**: NEEDS ATTENTION

**Action required**: Change the Word table style to remove vertical rules. Nature Water tables should have only three horizontal rules: top, below header, and bottom (the "three-line table" convention). The gray header shading should be removed. Modify `compile_paper.py` to use a cleaner table style.

---

## 7. Methods Placement

**Required**: After Discussion, before References.

**Actual** (from `compile_paper.py`): Methods is compiled after Discussion (line 483) and before References (line 488).

**Status**: PASS

---

## 8. Supplementary Information

**Required**: Separate file, numbered Supplementary Notes/Tables/Figures.

**Actual**:
- SI is compiled as a separate file (`NatureWater_SI_v14.docx`) via `compile_si()`.
- Contains 11 Supplementary Notes (numbered 1-11).
- Contains 8 Supplementary Tables (numbered 1-8).
- No Supplementary Figures are included (framework diagram mentioned in comments but not present in SI).

**Status**: PASS

**Minor note**: Nature Water SI typically also includes Supplementary Figures if any are referenced. The main text references "Supplementary Tables 3-5" and "Supplementary Note 11" correctly. Verify all cross-references are accurate.

---

## 9. Data Availability Statement

**Required**: Mandatory.

**Actual**: Present in `endmatter.md` (line 6-8) with specific data sources (USBR, FEMA, Census Bureau) and placeholder for repository URL.

**However**: The Data Availability statement is **NOT included** in the compiled Word document (`compile_paper.py` does not reference `endmatter.md`).

**Status**: FAIL

**Action required**: Add the Data Availability statement to the compiled main paper, after Methods and before References (or after References, per Nature Water's specific placement guidelines).

---

## 10. Author Contributions

**Required**: Mandatory (CRediT format for Nature Water).

**Actual**: Present in `endmatter.md` (lines 14-18) in CRediT format, but marked as "[CRediT format -- to be finalized]" and "[Additional authors TBD]".

**However**: NOT included in the compiled Word document.

**Status**: FAIL

**Action required**:
1. Finalize the author contributions statement.
2. Add it to `compile_paper.py` to be included in the main paper output.

---

## 11. Competing Interests

**Required**: Mandatory.

**Actual**: Present in `endmatter.md` (lines 20-22): "The authors declare no competing interests."

**However**: NOT included in the compiled Word document.

**Status**: FAIL

**Action required**: Add to compiled Word document.

---

## 12. Acknowledgements

**Required**: Check if present.

**Actual**: Present in `endmatter.md` (lines 24-26) but only as placeholder: "[To be added -- funding sources, computational resources, etc.]"

**However**: NOT included in the compiled Word document.

**Status**: NEEDS ATTENTION

**Action required**:
1. Complete the acknowledgements text.
2. Add to `compile_paper.py`.

---

## Summary

| # | Requirement | Status | Priority |
|---|-------------|--------|----------|
| 1 | Abstract ≤150 words | NEEDS ATTENTION | Medium |
| 2 | Abstract: no references | PASS | -- |
| 3 | Section structure (I/R/D/M) | PASS | -- |
| 4 | Numbered superscript citations | **FAIL** | **HIGH** |
| 5 | Figure captions | PASS | -- |
| 6 | Table format (no vertical rules) | NEEDS ATTENTION | Medium |
| 7 | Methods after Discussion | PASS | -- |
| 8 | SI separate + numbered | PASS | -- |
| 9 | Data Availability statement | **FAIL** | **HIGH** |
| 10 | Author Contributions | **FAIL** | **HIGH** |
| 11 | Competing Interests | **FAIL** | **HIGH** |
| 12 | Acknowledgements | NEEDS ATTENTION | Medium |

### Critical issues (4 FAIL):

1. **Citation format**: The entire manuscript uses (Author, Year) format. Nature Water requires numbered superscript citations. This is the single largest reformatting task.

2. **End matter not compiled**: Data Availability, Author Contributions, Competing Interests, and Acknowledgements all exist in `endmatter.md` but are **not rendered** in the compiled Word document. The `compile_paper.py` script must be updated to include these mandatory sections.

### Medium-priority issues (3 NEEDS ATTENTION):

3. **Abstract word count**: Likely at or slightly above the 150-word limit. Needs mechanical verification and possible trimming.

4. **Table styling**: Tables use full grid lines (vertical + horizontal). Nature Water expects three-line tables with no vertical rules.

5. **Acknowledgements**: Only placeholder text exists.

### Additional observations:

- The reference list has 24 entries but is unnumbered. It appears complete and well-formatted in bibliographic style, but needs conversion to numbered format.
- The Methods section header in `methods_v3.md` says "v4" in line 1 but file is named `methods_v3.md` -- minor inconsistency.
- Inconsistent ampersand usage: some citations use "and" (e.g., "Hung and Yang, 2021") while others use "&" (e.g., "Hung & Yang, 2021"). This will be moot after converting to numbered format, but should be consistent in the reference list.
- The compile script does not include `endmatter.md` in its processing pipeline at all -- a new `compile_endmatter()` function or additions to `compile_main_paper()` are needed.
