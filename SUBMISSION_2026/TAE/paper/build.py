#!/usr/bin/env python3
"""
build.py -- single-source build for the TAE manuscript.

Reads ONE source file, `manuscript.md`, and produces TWO outputs in this same
directory:

    manuscript.docx   (for the user to read / comment on)
    manuscript.tex     (for OpenReview submission, \\usepackage[dblblindworkshop]{neurips_2026})

Both are derived from the same parsed structure so they cannot drift apart.
{{CLAIM:name}} markers are NOT resolved here -- that is substitute.py's job.
If a marker is still present when build.py runs, it is carried into both
outputs literally and visibly flagged (red italic in docx, \\texttt{} in tex),
never silently dropped or invented.

DOUBLE-BLIND / CAMERA-READY SWITCH -- see the CAMERA_READY constant below
(with AUTHOR_NAME / AUTHOR_EMAIL / AUTHOR_AFFILIATION next to it). Default
is False = blind submission (empty \\author{}, plain [dblblindworkshop]
style option). Setting it True is the camera-ready state (populated
\\author{}, [dblblindworkshop, final]) and must only happen after
acceptance, as the LAST step -- see ANONYMITY.md Section 6.

FIGURE CONVENTION in manuscript.md
----------------------------------
A figure is TWO consecutive blocks, in this order and with nothing between
them:

    <!-- FIGURE 1 -- figures/fig1_rule_layers.pdf -->

    **Figure 1.** What causes a rejection, by arm and by rule kind, ...

The HTML comment is the insertion point and names the file, given relative to
SUBMISSION_2026/TAE/ (so `figures/<name>.pdf`, the sibling of paper/). The
paragraph immediately after it is the caption, recognised by its leading bold
"Figure N." run; a caption whose bold run continues past the number
(`**Figure 2. Some title.** (a) ...`) keeps that title bold.

build.py folds the two into ONE float. In the .tex that is a `figure`
environment holding \\includegraphics[width=\\linewidth], \\caption{...} and
\\label{fig:N}; in the .docx it is the PNG sibling plus a small caption
paragraph. The caption paragraph is CONSUMED, never also emitted as body
text. A figure marker with no caption paragraph after it still renders, with
no \\caption -- that is reported at the end of the run rather than passing
silently, since an uncaptioned float in a NeurIPS submission is a desk-check
finding.

CITATIONS AND THE BIBLIOGRAPHY -- where the one source of truth lives
---------------------------------------------------------------------
`references.bib` is the SINGLE SOURCE OF TRUTH for every reference. The
References section of manuscript.md is GENERATED from it by
`make_bibliography.py`, into the block between the `<!-- BIBLIOGRAPHY:BEGIN -->`
and `<!-- BIBLIOGRAPHY:END -->` markers, and that block must never be
hand-edited. To change a reference, edit the .bib and rerun the generator.

build.py itself does nothing bibliography-specific: it sees the generated
block as ordinary numbered paragraphs under an ordinary `## References`
heading, and in-text citations as the literal characters `[n]`, which are not
LaTeX specials and survive `_escape_tex` untouched. That is deliberate and it
is why the route works at all -- there is no bibtex and no biber on PATH, and
`_escape_tex` would turn a `\\cite{...}` or a `\\begin{thebibliography}` typed
into the markdown into `\\textbackslash{}cite...`. So no BibTeX pass runs and
none is needed.

Order of operations, all four steps, every time:

    python make_bibliography.py   # references.bib -> manuscript.md block
    python substitute.py          # {{CLAIM:...}} -> numbers
    python build.py               # manuscript.md -> .tex + .docx
    pdflatex manuscript.tex       # twice

`make_bibliography.py --check` is the guard: it fails if a numbered entry is
cited nowhere in the body, if the body cites a number with no entry, or if the
generated block has drifted from the .bib.

The venue style file (template/neurips_2026.sty) is copied next to
manuscript.tex on every run, so a fresh checkout compiles with no manual
download.

Tool detection, in priority order:
    1. pandoc on PATH               -> use it for both conversions
    2. python-docx importable       -> build docx directly; emit tex by
                                        template substitution (this script's
                                        own minimal converter)
    3. neither                      -> .tex is still written (the converter
                                        below needs no third-party library);
                                        .docx is skipped and the exact pip
                                        command needed is printed.

This script never fabricates a build path that did not actually run: each
branch below is only taken if the corresponding tool was positively detected
in this process, and the final report says which branch ran.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Build from the SUBSTITUTED source when it exists, so no {{CLAIM:...}} marker can
# reach LaTeX. A marker that survives to the .tex becomes a \claimplaceholder{...}
# whose underscores are math-mode characters, and pdflatex dies on it -- which is
# how this was found on 2026-08-01. Run substitute.py first; build.py consumes its
# output. Falling back to the raw manuscript is deliberate: an unsubstituted draft
# should still build a readable .docx for the author, it just will not compile.
_SUBSTITUTED = HERE / "manuscript.substituted.md"
MANUSCRIPT_MD = _SUBSTITUTED if _SUBSTITUTED.exists() else HERE / "manuscript.md"
OUT_DOCX = HERE / "manuscript.docx"
OUT_TEX = HERE / "manuscript.tex"

CLAIM_RE = re.compile(r"\{\{CLAIM:([a-zA-Z0-9_]+)\}\}")

# ---------------------------------------------------------------------------
# Double-blind / camera-ready switch -- read this before touching either flag
# ---------------------------------------------------------------------------
# AUTHOR_NAME / AUTHOR_EMAIL / AUTHOR_AFFILIATION are recorded once here so
# camera-ready never means retyping the author block by hand into a .tex
# file where it can drift from what OpenReview has on file.
AUTHOR_NAME = "Wenyu Chiou"
AUTHOR_EMAIL = "wec324@lehigh.edu"
AUTHOR_AFFILIATION = "Lehigh University"

# CAMERA_READY gates the ONLY two things that separate a blind submission
# from the accepted, de-anonymised camera-ready copy:
#   1. whether \author{...} is emitted with the real name/email/affiliation
#      above, or emitted empty; and
#   2. whether the venue style package loads plain [dblblindworkshop] or
#      [dblblindworkshop, final] -- "final" is what neurips_2026.sty's
#      \if@neuripsfinal / \@trackname machinery uses to typeset the author
#      block on the page, so it is the actual de-anonymising switch, not
#      \author{} alone.
#
# CAMERA_READY = False  ->  SUBMISSION state. This is the DEFAULT and the
#                            state this file must stay in for the entire
#                            review period -- every PDF produced from this
#                            script while CAMERA_READY is False is blind.
# CAMERA_READY = True   ->  CAMERA-READY state. \author{...} is populated
#                            and the style package gains ", final".
#
# Flipping this to True is the LAST step before producing the camera-ready
# PDF, taken only after acceptance is confirmed -- never before, never
# speculatively, and never left True in a commit while a submission-stage
# PDF is what the run is meant to produce. See ANONYMITY.md Section 6.
CAMERA_READY = False

# Sections rendered as unnumbered / special LaTeX blocks rather than a plain
# \section{...}. Matched case-insensitively against the parsed heading text.
SPECIAL_SECTIONS = {"abstract", "references", "appendix"}


# ---------------------------------------------------------------------------
# 1. Parse manuscript.md into a small structure both converters share.
# ---------------------------------------------------------------------------

# A note whose entire content is "FIGURE <n> -- <path>" is not an editorial
# aside -- it is a figure-insertion point naming the file to place there
# (paper/../figures/<name>.pdf, the convention introduced in sections/s3.md
# and followed when wiring sections 5-6 into manuscript.md). Both renderers
# below treat these specially instead of discarding them as a plain comment.
FIGURE_NOTE_RE = re.compile(r"^FIGURE\s+\d+\s*--\s*(\S+)\s*$", re.IGNORECASE)

# PAGE-BUDGET LEVER, added 2026-08-01 while trimming the body to the venue's
# 8-page limit. Every figure in figures/ is drawn at exactly 396 pt = 5.5 in,
# the NeurIPS textwidth, so \includegraphics[width=\linewidth] renders each at
# its natural size: fig1 5.25 in tall, fig2 5.95 in, fig3 4.10 in, 15.30 in of
# a 9 in text block in total, i.e. about 1.7 of the 8 pages. Scaling a figure
# here shrinks its type along with it, so the fractions below are kept as mild
# as the page count allows and are recorded per-figure rather than applied
# globally. A figure not named here renders at full \linewidth.
# 2026-08-02, rebuild-and-verify pass: 0.86 -> 0.80 on all three. At 0.86 the
# body ran 6 typeset lines past the bottom of page 8 and section 8 spilled onto
# page 9. Prose trims in the sanctioned order (section 7, then 2, then 1)
# recovered 2 of those lines and the rest had to come from somewhere that is
# not argument or evidence. 0.80 costs about 7% of each figure's type size and
# buys back the remaining 4. Revert this dict to 0.86 and the body is 9 pages
# again.
#
# fig0_problem_schematic.pdf sat at 0.55 while its natural width was 3.63 in,
# which placed it 3.03 in wide against 4.40 in for the other three. The
# 2026-08-03 rebuild of that figure changed the premise: it is now drawn at
# 5.50 in like every other figure, carries three text elements instead of ten,
# and prints no numbers. At 0.55 its \small type would print at 4.95 pt, well
# under the paper's 7 pt floor, so the fraction moves to 0.80 with the rest.
#
# This costs no column height. The old figure placed at 1.29 in tall
# (1.545 natural x 0.834); the new one is 1.49 in natural and places at 1.19 in.
# The four figures are now one visual system: same 5.50 in canvas, same 0.80
# placement, same 4.40 in printed width. fig0's type prints at 7.20 pt against
# 7.00 pt for the other three, so it remains the largest type in the set and
# clears the floor. fig0_problem_schematic.py asserts this itself and exits
# non-zero if the product drops below 7 pt -- PLACED_FRACTION there must be kept
# equal to the value below. The three matplotlib figures assert
# MIN_FONT * PRINT_SCALE >= MIN_PRINT_FONT, i.e. 8.75 * 0.80 = 7.0 exactly, so
# they are pinned at their 7 pt print floor and cannot give up any width at all.
# No data is redrawn.
FIGURE_WIDTH_FRACTION = {
    "fig0_problem_schematic.pdf": 0.80,
    "fig1_rule_layers.pdf": 0.80,
    "fig2_mechanism.pdf": 0.80,
    "fig3_consequence.pdf": 0.80,
}


def _figure_width_spec(basename: str) -> str:
    """LaTeX width= argument for a figure, honouring FIGURE_WIDTH_FRACTION."""
    frac = FIGURE_WIDTH_FRACTION.get(basename)
    if frac is None or frac == 1.0:
        return r"\linewidth"
    return r"%s\linewidth" % f"{frac:g}"

# The caption belonging to a figure marker is the paragraph IMMEDIATELY after
# it, and it opens with a bold "Figure N." run. manuscript.md already writes
# both shapes; both are recognised so no section has to be rewritten:
#
#   **Figure 1.** What causes a rejection, by arm and by rule kind, ...
#   **Figure 2. The appraisal shift is composition of world states.** (a) ...
#
# In the second shape the bold run continues past the number into a caption
# title, so the leading "**Figure 2. " is removed and the "**" re-opened,
# which keeps the title bold and the emphasis balanced.
_FIG_CAPTION_CLOSED_RE = re.compile(r"^\*\*Figure\s+(\d+)\.\s*\*\*\s*")
_FIG_CAPTION_OPEN_RE = re.compile(r"^\*\*Figure\s+(\d+)\.\s+")

# The second line of a markdown table: |---|---:|:---:|. Its colons carry the
# per-column alignment, which is the only place the manuscript states it.
_TABLE_ALIGN_ROW_RE = re.compile(r"^\|(\s*:?-{2,}:?\s*\|)+$")


def split_table_row(row: str) -> list[str]:
    """Cells of one markdown table row, outer pipes discarded."""
    return [c.strip() for c in row.strip().strip("|").split("|")]


def table_column_aligns(align_row: str) -> list[str]:
    """LaTeX column letters ('l'/'c'/'r') from a markdown alignment row."""
    aligns = []
    for cell in split_table_row(align_row):
        left, right = cell.startswith(":"), cell.endswith(":")
        aligns.append("c" if left and right else "r" if right else "l")
    return aligns


def split_figure_caption(text: str):
    """(figure_number, caption_markdown) if `text` is a figure caption
    paragraph, else None. The "Figure N." label itself is stripped: LaTeX's
    \\caption and the docx caption style both supply their own numbering, and
    leaving it in prints "Figure 1: Figure 1. ..."."""
    m = _FIG_CAPTION_CLOSED_RE.match(text)
    if m:
        return int(m.group(1)), text[m.end():].strip()
    m = _FIG_CAPTION_OPEN_RE.match(text)
    if m:
        return int(m.group(1)), "**" + text[m.end():].strip()
    return None


def attach_figure_captions(doc: dict) -> None:
    """Fold each caption paragraph into the figure block above it, in place.

    A ("figure", path) block becomes ("figure", (path, number, caption_md)),
    with `number`/`caption_md` None when no caption paragraph follows. The
    caption paragraph is consumed so it is not also typeset as body text --
    that duplication is what produced a floating image with no caption plus a
    stray bold paragraph in the 2026-08-01 build.
    """
    for sec in doc["sections"]:
        blocks = sec["blocks"]
        new_blocks = []
        i = 0
        while i < len(blocks):
            kind, content = blocks[i]
            if kind != "figure":
                new_blocks.append((kind, content))
                i += 1
                continue
            caption = None
            number = None
            if i + 1 < len(blocks) and blocks[i + 1][0] == "para":
                parsed = split_figure_caption(blocks[i + 1][1])
                if parsed is not None:
                    number, caption = parsed
                    i += 1  # consume the caption paragraph
            new_blocks.append(("figure", (content, number, caption)))
            i += 1
        sec["blocks"] = new_blocks


def parse_manuscript(path: Path) -> dict:
    """Minimal, format-specific parser for this repo's manuscript.md shape:

        # Title
        ## N Heading <!-- page budget: X pg -->
        paragraph text, possibly with {{CLAIM:name}} markers
        <!-- a standalone HTML comment becomes a NOTE block (single- or
             multi-line -- a comment that does not close on the line it
             opens on is accumulated until the line containing '-->' ) -->
        <!-- FIGURE N -- figures/name.pdf --> becomes a FIGURE block, not a
             NOTE, and is rendered as an actual image in both outputs.

    This is not a general Markdown parser -- it only needs to round-trip the
    constrained shape this project's manuscript.md is written in, and it
    fails loudly (KeyError / assertion) rather than guessing on anything it
    does not recognise.
    """
    if not path.exists():
        raise FileNotFoundError(f"manuscript source not found: {path}")

    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")

    doc = {"title": None, "sections": []}
    current = None
    para_buf: list[str] = []
    table_buf: list[str] = []
    in_comment = False
    comment_buf: list[str] = []

    def flush_para():
        nonlocal para_buf
        if para_buf:
            para_text = " ".join(l.strip() for l in para_buf).strip()
            if para_text and current is not None:
                current["blocks"].append(("para", para_text))
            para_buf = []

    def flush_table():
        # A run of pipe-delimited lines is a markdown table, not a paragraph.
        # Before this existed, flush_para() joined the rows with spaces and
        # every table reached the page as one run-on line of pipes with the
        # `|---|---:|` alignment row typeset verbatim (Tables 1 and 2, seen in
        # manuscript.pdf 2026-08-01). A run too short or without an alignment
        # row is handed back to the paragraph path rather than guessed at.
        nonlocal table_buf
        if not table_buf:
            return
        rows, table_buf = table_buf, []
        if current is None:
            return
        if len(rows) >= 3 and _TABLE_ALIGN_ROW_RE.match(rows[1]):
            current["blocks"].append(("table", rows))
        else:
            current["blocks"].append(("para", " ".join(rows)))

    def emit_comment(raw_content: str):
        # Mirrors the single-line branch's original behaviour: silently
        # dropped if no section has opened yet (matches the pre-Abstract
        # "Authors withheld..." byline comment, which was already discarded
        # before this function existed).
        if current is None:
            return
        content = raw_content.strip()
        fig = FIGURE_NOTE_RE.match(content)
        if fig:
            current["blocks"].append(("figure", fig.group(1)))
        else:
            current["blocks"].append(("note", content))

    for raw in lines:
        line = raw.rstrip("\n")
        stripped = line.strip()

        if in_comment:
            if "-->" in line:
                before, _, _ = line.partition("-->")
                comment_buf.append(before)
                emit_comment("\n".join(comment_buf))
                in_comment = False
                comment_buf = []
            else:
                comment_buf.append(line)
            continue

        comment_only = re.fullmatch(r"<!--(.*)-->", stripped)

        if stripped.startswith("# ") and doc["title"] is None and current is None:
            doc["title"] = stripped[2:].strip()
            continue

        if stripped.startswith("## "):
            flush_table()
            flush_para()
            heading_line = stripped[3:]
            budget_match = re.search(r"<!--\s*(.*?)\s*-->", heading_line)
            budget = budget_match.group(1).strip() if budget_match else None
            if budget:
                # manuscript.md writes the annotation as "page budget: ...";
                # normalise so every renderer can prefix it identically
                # instead of some headings ending up with the label doubled.
                budget = re.sub(r"(?i)^page budget:\s*", "", budget).strip()
            heading_text = re.sub(r"<!--.*?-->", "", heading_line).strip()
            current = {"heading": heading_text, "budget": budget, "blocks": []}
            doc["sections"].append(current)
            continue

        if comment_only:
            flush_table()
            flush_para()
            emit_comment(comment_only.group(1))
            continue

        if stripped.startswith("<!--"):
            # Opens but does not close on this line -- accumulate until a
            # later line contains '-->'. Without this branch a multi-line
            # editorial comment (used for DRAFT/HANDOFF notes in this
            # project's sections/*.md) silently falls through to the plain-
            # paragraph branch below and is typeset as visible body text,
            # literal '<!--'/'-->' and all -- caught 2026-08-01 wiring §4.
            flush_table()
            flush_para()
            comment_buf = [stripped[4:]]
            in_comment = True
            continue

        if stripped == "":
            flush_table()
            flush_para()
            continue

        if stripped.startswith("|"):
            flush_para()
            table_buf.append(stripped)
            continue

        flush_table()
        para_buf.append(line)

    flush_table()
    flush_para()

    if doc["title"] is None:
        raise ValueError("manuscript.md has no top-level '# Title' line")
    if not doc["sections"]:
        raise ValueError("manuscript.md has no '## Heading' sections")

    attach_figure_captions(doc)

    return doc


def claim_markers_in(doc: dict) -> set[str]:
    found: set[str] = set()
    for sec in doc["sections"]:
        for kind, content in sec["blocks"]:
            if kind == "para":
                found.update(CLAIM_RE.findall(content))
            elif kind == "table":
                for row in content:
                    found.update(CLAIM_RE.findall(row))
    return found


# ---------------------------------------------------------------------------
# Shared inline tokenizer: {{CLAIM:x}}, `code`, **bold**, *italic*, plain
# text. Both the docx and tex renderers walk the same token stream so bold/
# italic/code/claim markers cannot render differently -- or drift -- between
# the two outputs.
# ---------------------------------------------------------------------------

_INLINE_RE = re.compile(
    r"\{\{CLAIM:([a-zA-Z0-9_]+)\}\}"   # group 1: claim name
    r"|`([^`]+)`"                        # group 2: inline code
    r"|\*\*([^*]+)\*\*"                  # group 3: bold
    r"|\*([^*]+)\*"                      # group 4: italic
)


def tokenize_inline(text: str) -> list[tuple[str, str]]:
    """Returns a list of (kind, content) tokens, kind in
    {"text", "claim", "code", "bold", "italic"}."""
    tokens: list[tuple[str, str]] = []
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            tokens.append(("text", text[pos:m.start()]))
        if m.group(1) is not None:
            tokens.append(("claim", m.group(1)))
        elif m.group(2) is not None:
            tokens.append(("code", m.group(2)))
        elif m.group(3) is not None:
            tokens.append(("bold", m.group(3)))
        elif m.group(4) is not None:
            tokens.append(("italic", m.group(4)))
        pos = m.end()
    if pos < len(text):
        tokens.append(("text", text[pos:]))
    return tokens


# ---------------------------------------------------------------------------
# 2a. docx builder (python-docx branch)
# ---------------------------------------------------------------------------

def build_docx(doc: dict, out_path: Path) -> None:
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches

    d = Document()
    d.add_heading(doc["title"], level=0)

    byline = d.add_paragraph()
    r = byline.add_run("Authors withheld for double-blind review.")
    r.italic = True

    def add_para_with_claims(container, text):
        p = container.add_paragraph()
        for kind, content in tokenize_inline(text):
            if kind == "text":
                p.add_run(content)
            elif kind == "bold":
                p.add_run(content).bold = True
            elif kind == "italic":
                p.add_run(content).italic = True
            elif kind == "code":
                run = p.add_run(content)
                run.font.name = "Consolas"
            elif kind == "claim":
                run = p.add_run("{{CLAIM:%s}}" % content)
                run.italic = True
                run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
        return p

    def add_table(container, rows):
        # Same block kind the tex renderer turns into a tabular. Rendering it
        # here as a real docx table keeps the two outputs saying the same
        # thing; the alternative, letting the block fall through unhandled,
        # would drop Tables 1 and 2 from the docx without any warning.
        header = split_table_row(rows[0])
        body = [split_table_row(r) for r in rows[2:]]
        ncol = len(table_column_aligns(rows[1]))
        t = container.add_table(rows=1 + len(body), cols=ncol)
        t.style = "Table Grid"
        for j, cell in enumerate((header + [""] * ncol)[:ncol]):
            run = t.rows[0].cells[j].paragraphs[0].add_run(cell)
            run.bold = True
        for i, row in enumerate(body, start=1):
            for j, cell in enumerate((row + [""] * ncol)[:ncol]):
                add_para_with_claims(t.rows[i].cells[j], cell)
                # add_paragraph() appends; the cell's own empty first
                # paragraph would otherwise leave a blank line above.
                first = t.rows[i].cells[j].paragraphs[0]
                first._element.getparent().remove(first._element)

    def add_note(container, text):
        p = container.add_paragraph()
        # A multi-line comment carries its source line breaks in `text`;
        # collapse to one line here since a single docx run does not
        # honour embedded '\n' as a line break (the tex renderer, by
        # contrast, keeps one '%'-comment per original line -- see
        # build_tex, which is why this collapsing happens only here).
        r = p.add_run(f"[NOTE: {text.replace(chr(10), ' ')}]")
        r.italic = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
        return p

    def add_figure(container, spec):
        # spec is (rel_path, number, caption_md) -- see attach_figure_captions.
        # rel_path is written relative to SUBMISSION_2026/TAE/ (e.g.
        # "figures/fig1_rule_layers.pdf"), the convention fixed by
        # sections/s3.md's own FIGURE marker. python-docx cannot embed a
        # PDF directly, so use the PNG sibling the same evidence script
        # writes alongside it (BOUNDARY.md §2: every figure script emits
        # {png,pdf,csv} together).
        rel_path, number, caption_md = spec
        png_path = (HERE.parent / "figures" / (Path(rel_path).stem + ".png")).resolve()
        if png_path.exists():
            container.add_picture(str(png_path), width=Inches(5.5))
        else:
            p = container.add_paragraph()
            r = p.add_run(f"[FIGURE NOT FOUND: {rel_path} (expected {png_path})]")
            r.italic = True
            r.bold = True
            r.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
        if caption_md:
            # The caption keeps its own inline emphasis; the "Figure N."
            # label was stripped at parse time and is re-supplied here (LaTeX
            # gets its own from \caption) so the docx reads the same way the
            # typeset .tex does.
            cap = container.add_paragraph()
            lead = cap.add_run(f"Figure {number}. " if number else "Figure. ")
            lead.bold = True
            for kind, content in tokenize_inline(caption_md):
                if kind == "text":
                    cap.add_run(content)
                elif kind == "bold":
                    cap.add_run(content).bold = True
                elif kind == "italic":
                    cap.add_run(content).italic = True
                elif kind == "code":
                    cap.add_run(content).font.name = "Consolas"
                elif kind == "claim":
                    run = cap.add_run("{{CLAIM:%s}}" % content)
                    run.italic = True
                    run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
            for run in cap.runs:
                run.font.size = Pt(9)
        src = container.add_paragraph()
        r = src.add_run(f"[figure source: {rel_path}]")
        r.italic = True
        r.font.size = Pt(8)
        r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    for sec in doc["sections"]:
        d.add_heading(sec["heading"], level=1)
        if sec["budget"]:
            p = d.add_paragraph()
            r = p.add_run(f"[page budget: {sec['budget']}]")
            r.italic = True
            r.font.size = Pt(9)
            r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
        for kind, content in sec["blocks"]:
            if kind == "para":
                add_para_with_claims(d, content)
            elif kind == "table":
                add_table(d, content)
            elif kind == "note":
                add_note(d, content)
            elif kind == "figure":
                add_figure(d, content)

    d.save(str(out_path))


# ---------------------------------------------------------------------------
# 2b. tex builder (template-substitution branch; needs no third-party libs)
# ---------------------------------------------------------------------------

_LATEX_SPECIAL = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


# Characters that pdflatex's default 8-bit encoding cannot set, mapped to the
# LaTeX that produces the same glyph. Found on 2026-08-01, when the first real
# compile died on U+2212 and U+0394 -- both of which arrive routinely from the
# evidence pipeline, whose tables print a true minus sign and a capital delta.
# Anything added here must render identically in the .docx branch, which needs
# no mapping because python-docx writes real Unicode.
_TEX_UNICODE = {
    "§": r"\S{}",       # section sign; LaTeX needs the macro

    "−": r"$-$",        # true minus, not hyphen
    "Δ": r"$\Delta$",   # capital delta
    "≤": r"$\le$",
    "≥": r"$\ge$",
    "≈": r"$\approx$",
    "×": r"$\times$",
    "→": r"$\rightarrow$",
    "—": r"---",
    "–": r"--",
    "‘": r"`",
    "’": r"'",
    "“": r"``",
    "”": r"''",
    "…": r"\ldots{}",
    "±": r"$\pm$",

    # Accented letters in author names. Added 2026-08-02 with the bibliography
    # (Hübner, Simão, Rodríguez-Aguilar, Lluís). These arrive from
    # references.bib via make_bibliography.py, which expands BibTeX accent
    # macros to the real character so the .bib stays portable BibTeX and the
    # .docx branch (python-docx, real Unicode) needs no mapping. The set here
    # mirrors _ACCENTS in make_bibliography.py -- keep the two in step, or a
    # name added later fails the un-mappable-character guard rather than
    # reaching the page wrong.
    "á": r"\'{a}",
    "é": r"\'{e}",
    "í": r"\'{i}",
    "ó": r"\'{o}",
    "ú": r"\'{u}",
    "ä": r'\"{a}',
    "ö": r'\"{o}',
    "ü": r'\"{u}',
    "ã": r"\~{a}",
    "ñ": r"\~{n}",
    "ç": r"\c{c}",
}


def _escape_tex(s: str) -> str:
    out = []
    for c in s:
        if c in _LATEX_SPECIAL:
            out.append(_LATEX_SPECIAL[c])
        elif c in _TEX_UNICODE:
            out.append(_TEX_UNICODE[c])
        elif ord(c) > 127:
            # Fail loudly rather than emit a character pdflatex will choke on
            # three hundred lines into a log nobody reads.
            raise ValueError(
                f"un-mappable non-ASCII character {c!r} (U+{ord(c):04X}) in LaTeX output; "
                f"add it to _TEX_UNICODE in build.py"
            )
        else:
            out.append(c)
    return "".join(out)


def _tex_text(text: str) -> str:
    """Escape plain text for LaTeX; render **bold**/*italic*/`code` through
    the matching LaTeX command and {{CLAIM:x}} markers through
    \\claimplaceholder{x} (defined in the preamble) so they stay visually
    obvious as unresolved rather than being mangled by brace-escaping. Uses
    the same tokenizer as the docx renderer so the two outputs cannot render
    inline emphasis differently."""
    parts = []
    for kind, content in tokenize_inline(text):
        if kind == "text":
            parts.append(_escape_tex(content))
        elif kind == "bold":
            parts.append(r"\textbf{%s}" % _escape_tex(content))
        elif kind == "italic":
            parts.append(r"\textit{%s}" % _escape_tex(content))
        elif kind == "code":
            parts.append(r"\texttt{%s}" % _escape_tex(content))
        elif kind == "claim":
            parts.append(r"\claimplaceholder{%s}" % content)
    return "".join(parts)


TEX_PREAMBLE = r"""\documentclass{article}

% --- NeurIPS 2026 TAE workshop style -------------------------------------
% neurips_2026.sty is vendored at paper/template/neurips_2026.sty and is
% copied next to this .tex by build.py on every run (see ensure_style_file),
% so a fresh checkout compiles without a manual download step.
%
% Style option list is driven by the CAMERA_READY constant above this
% template string. SUBMISSION mode (CAMERA_READY=False, per DECISION.md
% Section 1) loads plain [dblblindworkshop]. Camera-ready mode
% (CAMERA_READY=True) loads [dblblindworkshop, final] -- the "final" option
% is what de-anonymises the paper, so it must NOT be added until the paper
% is accepted and ANONYMITY.md's de-anonymisation step is deliberately taken.
\usepackage[__STYLE_OPTIONS__]{neurips_2026}

\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{amsmath}
\usepackage{hyperref}

% TYPE 3 FONT FIX, 2026-08-03. template/neurips_2026.tex:376-378 requires
% "only Type 1 or Embedded TrueType fonts" and :416-417 warns that a Type 3
% font will be sent back to be fixed. With [T1]{fontenc} loaded and no Type 1
% T1 typewriter family installed, MiKTeX silently fell back to the METAFONT
% bitmap ectt1000.pk at 600 dpi and embedded it as a Type 3 font on page 1 --
% the five glyphs a/e/i/l/m spelling the \texttt{email} line inside the .sty's
% own anonymous author block (neurips_2026.sty:341). Mapping the typewriter
% family to Courier (pcr, a Type 1 face from psnfss) removes it.
%
% Do NOT "fix" this with \usepackage{lmodern}: that also resets \rmdefault and
% would override the style file's \rmdefault=ptm (neurips_2026.sty:101-102),
% changing the body font away from Times. This line touches \ttdefault ONLY,
% so \rmdefault=ptm and \sfdefault=phv are left exactly as the .sty sets them.
\renewcommand{\ttdefault}{pcr}

% Figure blocks below give the path recorded in manuscript.md relative to
% SUBMISSION_2026/TAE/ (e.g. "figures/fig1_rule_layers.pdf"); this compile
% happens from SUBMISSION_2026/TAE/paper/, one level under that, so the
% search path is the sibling figures/ directory, and \includegraphics below
% is called with just the basename.
\graphicspath{{../figures/}}

% Unresolved-number markers stay visually obvious rather than silently
% compiling as blank groups -- see substitute.py for the resolution step.
\newcommand{\claimplaceholder}[1]{\texttt{\{\{CLAIM:#1\}\}}}

\title{__TITLE__}

% dblblindworkshop mode requires \workshoptitle{} IN ADDITION TO \title{}
% (template/neurips_2026.tex:41-43). The two are not interchangeable: the
% .sty consumes \workshoptitle only inside \@trackname, which typesets the
% first-page footnote "...(NeurIPS 2026). Workshop: <workshoptitle>."
% (neurips_2026.sty:81-92). It therefore holds the WORKSHOP's name, not the
% paper's -- setting it to the paper title prints the paper title in the
% venue footnote, which is wrong and was the state before 2026-08-01.
%
% Do not expect to see it in the submission PDF. \@trackname is expanded
% only under \if@neuripsfinal (neurips_2026.sty:396-398); without "final"
% the footnote is the generic "Submitted to 40th Conference ... Do not
% distribute." This line is silent now and correct at camera-ready.
\workshoptitle{TAE (Trust-AI-Eval): Can We Trust AI Evaluation?}

__AUTHOR_BLOCK__

\begin{document}

\maketitle
"""

TEX_CLOSING = r"""
\end{document}
"""


def _style_options() -> str:
    """[dblblindworkshop] blind, [dblblindworkshop, final] camera-ready.

    Driven solely by the module-level CAMERA_READY switch -- see its
    docstring-comment above for what flipping it means and when that is
    allowed.
    """
    return "dblblindworkshop, final" if CAMERA_READY else "dblblindworkshop"


def _author_block() -> str:
    """\\author{} empty when blind, populated when CAMERA_READY is True.

    Driven solely by the module-level CAMERA_READY switch plus the
    AUTHOR_NAME / AUTHOR_EMAIL / AUTHOR_AFFILIATION constants above it.
    """
    if not CAMERA_READY:
        return "% Double-blind: no \\author{} content until de-anonymisation.\n\\author{}"
    author_tex = (
        r"%s \\ %s \\ \texttt{%s}"
        % (_tex_text(AUTHOR_NAME), _tex_text(AUTHOR_AFFILIATION), AUTHOR_EMAIL)
    )
    return (
        "%% Camera-ready (CAMERA_READY=True): de-anonymised author block.\n"
        r"\author{%s}" % author_tex
    )


def _tex_preamble(title: str) -> str:
    # Plain .replace(), not %-formatting: the preamble text is full of
    # literal LaTeX '%' comment characters that %-style formatting would
    # misparse as format specifiers.
    text = TEX_PREAMBLE.replace("__TITLE__", _tex_text(title))
    text = text.replace("__STYLE_OPTIONS__", _style_options())
    text = text.replace("__AUTHOR_BLOCK__", _author_block())
    return text


def _tex_table(rows: list[str]) -> list[str]:
    """A markdown table as a booktabs-free \\tabular, centred and \\small.

    Set \\small rather than \\footnotesize so the table type stays one step
    from body size, and centre the whole thing so a narrow table does not
    sit flush left against a full-width paragraph. \\tabcolsep is halved:
    Table 1 carries nine columns across a 5.5 in text block and overflows at
    the default 6 pt gutter.
    """
    aligns = table_column_aligns(rows[1])
    header = split_table_row(rows[0])
    body = [split_table_row(r) for r in rows[2:]]
    ncol = len(aligns)

    def line(cells: list[str]) -> str:
        cells = (cells + [""] * ncol)[:ncol]
        return " & ".join(_tex_text(c) for c in cells) + r" \\"

    out = [
        r"\begin{center}",
        r"\small",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular}{%s}" % "".join(aligns),
        r"\hline",
        line(header),
        r"\hline",
    ]
    out.extend(line(r) for r in body)
    out.extend([r"\hline", r"\end{tabular}", r"\end{center}"])
    return out


def build_tex(doc: dict, out_path: Path) -> None:
    out = [_tex_preamble(doc["title"])]

    for sec in doc["sections"]:
        heading_key = sec["heading"].split(" ", 1)
        heading_lower = sec["heading"].strip().lower()
        # Strip a leading "N " numeral so \section supplies its own numbering
        # and does not double-number against DECISION.md's own §N scheme.
        heading_text = re.sub(r"^\d+\s+", "", sec["heading"]).strip()

        budget_comment = f"  % page budget: {sec['budget']}" if sec["budget"] else ""

        if heading_lower.startswith("abstract"):
            out.append(f"\\begin{{abstract}}{budget_comment}")
        elif (
            heading_lower.startswith("references")
            or heading_lower.startswith("appendix")
            or heading_lower.startswith("artifact")
        ):
            # Unnumbered. "Artifact availability" is a venue statement, not a ninth
            # section of the argument -- numbering it would put a "9" in a body the
            # page budget and the readiness check both define as sections 1-8.
            out.append(f"\\section*{{{_tex_text(heading_text)}}}{budget_comment}")
        else:
            out.append(f"\\section{{{_tex_text(heading_text)}}}{budget_comment}")

        for kind, content in sec["blocks"]:
            if kind == "para":
                out.append(_tex_text(content))
                out.append("")
            elif kind == "table":
                out.extend(_tex_table(content))
                out.append("")
            elif kind == "note":
                # LaTeX comments are invisible when typeset, mirroring the
                # markdown HTML-comment convention in the source.
                for line in content.splitlines():
                    out.append(f"% {line}")
                out.append("")
            elif kind == "figure":
                # `content` is (rel_path, number, caption_md). rel_path is
                # recorded in manuscript.md relative to SUBMISSION_2026/TAE/
                # (e.g. "figures/fig1_rule_layers.pdf"); \graphicspath in the
                # preamble points at ../figures/, so only the basename is
                # passed to \includegraphics here.
                rel_path, number, caption_md = content
                basename = Path(rel_path).name
                out.append(f"% figure source (as recorded in manuscript.md): {rel_path}")
                out.append(r"\begin{figure}[t]")
                out.append(r"\centering")
                out.append(
                    r"\includegraphics[width=%s]{%s}"
                    % (_figure_width_spec(basename), basename)
                )
                if caption_md:
                    out.append(r"\caption{%s}" % _tex_text(caption_md))
                    # Label after \caption, never before -- \label binds to
                    # the last counter stepped, and inside a float that is
                    # the figure counter only once \caption has run.
                    out.append(r"\label{fig:%s}" % (number if number else basename))
                out.append(r"\end{figure}")
                out.append("")

        if heading_lower.startswith("abstract"):
            out.append("\\end{abstract}")

    out.append(TEX_CLOSING)
    out_path.write_text("\n".join(out), encoding="utf-8")


# ---------------------------------------------------------------------------
# 2c. pandoc branch (preferred when available; not exercised unless pandoc
#     is actually found on PATH in this process)
# ---------------------------------------------------------------------------

def build_with_pandoc(pandoc_path: str, doc: dict) -> tuple[bool, bool, list[str]]:
    """Returns (docx_ok, tex_ok, messages)."""
    messages = []
    docx_ok = False
    tex_ok = False

    try:
        subprocess.run(
            [pandoc_path, str(MANUSCRIPT_MD), "-o", str(OUT_DOCX)],
            check=True, capture_output=True, text=True,
        )
        docx_ok = OUT_DOCX.exists()
        messages.append(f"pandoc -> {OUT_DOCX.name} ({'ok' if docx_ok else 'no file produced'})")
    except subprocess.CalledProcessError as e:
        messages.append(f"pandoc docx conversion FAILED: {e.stderr.strip()[:400]}")

    # pandoc's raw --to=latex output has no NeurIPS preamble; wrap its body
    # in the same TEX_PREAMBLE/TEX_CLOSING used by the template-substitution
    # branch so the two tool paths still agree on the preamble contract.
    try:
        result = subprocess.run(
            [pandoc_path, str(MANUSCRIPT_MD), "-t", "latex"],
            check=True, capture_output=True, text=True,
        )
        body = result.stdout
        full = _tex_preamble(doc["title"]) + "\n" + body + TEX_CLOSING
        OUT_TEX.write_text(full, encoding="utf-8")
        tex_ok = True
        messages.append(f"pandoc -> {OUT_TEX.name} (ok)")
    except subprocess.CalledProcessError as e:
        messages.append(f"pandoc tex conversion FAILED: {e.stderr.strip()[:400]}")

    return docx_ok, tex_ok, messages


# ---------------------------------------------------------------------------
# 3. Orchestration + honest reporting
# ---------------------------------------------------------------------------

TEMPLATE_DIR = HERE / "template"
STYLE_FILE = "neurips_2026.sty"


def ensure_style_file() -> str:
    """Put the venue style file next to manuscript.tex, and say what happened.

    manuscript.tex does \\usepackage{neurips_2026}, which pdflatex resolves
    only from its own working directory (or TEXINPUTS). Before this ran, a
    fresh checkout produced a .tex that could not compile even though the .sty
    was sitting in template/ two directories away. Copy is unconditional when
    the bytes differ, so an edited template propagates instead of being
    shadowed by a stale copy.
    """
    src = TEMPLATE_DIR / STYLE_FILE
    dst = HERE / STYLE_FILE
    if not src.exists():
        return (f"style file: MISSING at {src} -- manuscript.tex will not compile "
                f"until {STYLE_FILE} is placed next to it")
    if dst.exists() and dst.read_bytes() == src.read_bytes():
        return f"style file: {dst.name} already current next to manuscript.tex (matches template/)"
    action = "refreshed (differed from template/)" if dst.exists() else "copied from template/"
    shutil.copyfile(src, dst)
    return f"style file: {dst.name} {action} -> {dst}"


def uncaptioned_figures(doc: dict) -> list[str]:
    """Figure paths that got no caption paragraph. An uncaptioned float is a
    desk-check finding at this venue, so it is reported, not swallowed."""
    missing = []
    for sec in doc["sections"]:
        for kind, content in sec["blocks"]:
            if kind == "figure" and not content[2]:
                missing.append(content[0])
    return missing


def main() -> int:
    # See substitute.py for why: legacy Windows console codepages cannot
    # encode every character this file's own status messages may contain.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    print(f"source: {MANUSCRIPT_MD}")
    doc = parse_manuscript(MANUSCRIPT_MD)
    markers = claim_markers_in(doc)
    print(f"parsed {len(doc['sections'])} sections, {len(markers)} distinct {{{{CLAIM:*}}}} markers "
          f"(unresolved -- run substitute.py separately to check/resolve them)")

    figures = [c for s in doc["sections"] for k, c in s["blocks"] if k == "figure"]
    captioned = [f for f in figures if f[2]]
    print(f"figures: {len(figures)} found, {len(captioned)} with a caption paragraph attached")
    for path in uncaptioned_figures(doc):
        print(f"  WARNING: no caption paragraph follows the FIGURE marker for {path}; "
              f"it will render as a float with no \\caption")

    print(ensure_style_file())

    pandoc_path = shutil.which("pandoc")
    try:
        import docx  # noqa: F401
        have_python_docx = True
    except ImportError:
        have_python_docx = False

    print(f"pandoc on PATH:        {'yes -> ' + pandoc_path if pandoc_path else 'no'}")
    print(f"python-docx importable: {'yes' if have_python_docx else 'no'}")

    docx_done = False
    tex_done = False
    reasons = []

    if pandoc_path:
        print("\n-- branch: pandoc --")
        docx_done, tex_done, messages = build_with_pandoc(pandoc_path, doc)
        for m in messages:
            print(m)
        if not docx_done:
            reasons.append("docx: pandoc was found but the conversion failed (see message above)")
        if not tex_done:
            reasons.append("tex: pandoc was found but the conversion failed (see message above)")
    else:
        print("\n-- pandoc not found; falling back --")
        if have_python_docx:
            print("branch: python-docx (direct) + template-substitution tex")
            try:
                build_docx(doc, OUT_DOCX)
                docx_done = OUT_DOCX.exists()
                print(f"python-docx -> {OUT_DOCX.name} ({'ok' if docx_done else 'no file produced'})")
            except Exception as e:  # noqa: BLE001 -- report, don't hide
                reasons.append(f"docx: python-docx raised {type(e).__name__}: {e}")
        else:
            reasons.append(
                "docx: NEITHER pandoc nor python-docx is available. "
                "Install one to get manuscript.docx: "
                "`pip install python-docx`  (or install pandoc and put it on PATH)."
            )

        # The template-substitution tex converter needs no third-party
        # library, so it always runs regardless of the docx branch outcome.
        try:
            build_tex(doc, OUT_TEX)
            tex_done = OUT_TEX.exists()
            print(f"template-substitution -> {OUT_TEX.name} ({'ok' if tex_done else 'no file produced'})")
        except Exception as e:  # noqa: BLE001
            reasons.append(f"tex: template converter raised {type(e).__name__}: {e}")

    print("\n== RESULT ==")
    print(f"manuscript.docx: {'PRODUCED' if docx_done else 'NOT PRODUCED'} -> {OUT_DOCX}")
    print(f"manuscript.tex:  {'PRODUCED' if tex_done else 'NOT PRODUCED'} -> {OUT_TEX}")
    if reasons:
        print("\nReasons for anything not produced:")
        for r in reasons:
            print(f"  - {r}")
    if tex_done:
        sty_present = (HERE / STYLE_FILE).exists()
        mode = "CAMERA-READY (de-anonymised)" if CAMERA_READY else "SUBMISSION (double-blind)"
        if sty_present:
            print(
                f"\nNote: {STYLE_FILE} is in place next to manuscript.tex, copied from template/ "
                f"by this build, so the .tex compiles as-is:\n"
                "  pdflatex -interaction=nonstopmode manuscript.tex\n"
                f"CAMERA_READY = {CAMERA_READY!r} -> this build emitted the {mode} style option "
                "and author block. Flip CAMERA_READY in build.py only after acceptance, as the "
                "LAST step before producing the camera-ready PDF -- see ANONYMITY.md Section 6."
            )
            if CAMERA_READY:
                print(
                    "WARNING: CAMERA_READY is True -- this .tex is DE-ANONYMISED "
                    f"({AUTHOR_NAME}, {AUTHOR_EMAIL}, {AUTHOR_AFFILIATION}). Do not submit this "
                    "PDF as a blind submission."
                )
        else:
            print(
                f"\nNote: manuscript.tex will NOT compile -- {STYLE_FILE} is neither next to it "
                f"nor in {TEMPLATE_DIR}. Restore the venue author kit before building."
            )

    return 0 if (docx_done and tex_done) else 1


if __name__ == "__main__":
    raise SystemExit(main())
