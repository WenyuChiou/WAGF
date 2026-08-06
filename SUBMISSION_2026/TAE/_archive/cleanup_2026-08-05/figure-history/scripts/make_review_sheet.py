r"""Build figures/ALL_FIGURES_REVIEW.png -- every figure at true print size.

WHY THIS EXISTS
A figure checked on its own always looks fine. The questions that only a
side-by-side answers are: do the four read as ONE paper's figures (same
typeface, same size hierarchy, same colour meanings), and is anything crowded
once it is shrunk to the size it actually prints at.

WHAT IT DOES
Renders each SHIPPED figure PDF -- the exact file \includegraphics pulls in --
at the exact placed width the manuscript uses, and stacks them in paper order.
Nothing is re-plotted and no native PNG is used: a native PNG is 5.5 in wide
and would show the type 25% larger than it prints, which is the specific
mistake this sheet is meant to make impossible.

PLACED WIDTH, MEASURED NOT ASSUMED
build.py emits \includegraphics[width=0.8\linewidth]. A probe build reports
\linewidth = 397.485 TeX pt = 5.5000 in, so the placed width is 4.4000 in, and
the drawn extent of Figure 2 in the shipped manuscript.pdf measures 316.81 PDF
pt = 4.4001 in, which confirms it end to end. PLACED_WIDTH_IN below is checked
against the manuscript at run time when the manuscript PDF is present.

THE SHEET'S OWN TYPE IS DELIBERATELY NOT TIMES
Every figure sets its text in Times. The sheet's labels are set in a sans face
on purpose, so that the rule for reading this sheet is unambiguous: anything in
Times is figure content, anything in sans is my annotation. A sheet that
labelled figures in the figures' own typeface would invite exactly the
confusion it is supposed to resolve.

Usage:  python SUBMISSION_2026/TAE/evidence/make_review_sheet.py
Output: SUBMISSION_2026/TAE/figures/ALL_FIGURES_REVIEW.png
"""
from __future__ import annotations

import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
TAE = os.path.dirname(HERE)
FIGURES = os.path.join(TAE, "figures")
MANUSCRIPT_PDF = os.path.join(TAE, "paper", "manuscript.pdf")
OUT = os.path.join(FIGURES, "ALL_FIGURES_REVIEW.png")

# Paper order. The filename stems are historical (fig0..fig3); the numbers are
# what the manuscript prints, so both are shown on every label.
FIGURE_ORDER = [
    (1, "fig0_problem_schematic.pdf", "what the statistic counts"),
    (2, "fig1_rule_layers.pdf", "which rules read what the agent says"),
    (3, "fig2_mechanism.pdf", "why it moves"),
    (4, "fig3_consequence.pdf", "what it does to the statistic"),
]

PLACED_WIDTH_IN = 4.40      # 0.80 * 5.5 in \linewidth
MIN_PRINT_FONT_PT = 7.0     # the paper's hard floor, after the 0.80 scaling
DPI = 300
MARGIN_PX = int(0.35 * DPI)
GAP_PX = int(0.30 * DPI)
LABEL_H_PX = int(0.60 * DPI)
HEADER_H_PX = int(1.15 * DPI)
FOOTER_H_PX = int(1.32 * DPI)

BG = (255, 255, 255)
INK = (17, 17, 17)
MUTED = (110, 110, 110)
FRAME = (205, 205, 205)

# The palette contract the three matplotlib figures state in their own source
# headers. Reproduced here so the sheet can be read against it directly.
PALETTE_CONTRACT = [
    ("#0072B2", "with-validators arm"),
    ("#D55E00", "no-validator arm"),
    ("#009E73", "conditioned on the agent's self-report"),
    ("#CC79A7", "its world-side counterpart"),
    ("#F0E442", "hard world-feasibility gate"),
]


def _font(size_px: int, bold: bool = False):
    """A sans face, deliberately not the figures' Times. Bundled with matplotlib."""
    from PIL import ImageFont
    import matplotlib
    base = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(os.path.join(base, name), size_px)


def _verify_placed_width() -> str:
    """Re-measure the placed box in the shipped manuscript rather than trusting it."""
    if not os.path.exists(MANUSCRIPT_PDF):
        return "manuscript.pdf absent, placed width not re-measured"
    try:
        import pdfplumber
    except ImportError:
        return "pdfplumber absent, placed width not re-measured"
    with pdfplumber.open(MANUSCRIPT_PDF) as pdf:
        for page in pdf.pages:
            objs = (page.objects.get("rect", []) + page.objects.get("curve", [])
                    + page.objects.get("line", []))
            if len(objs) < 20:
                continue
            span = (max(o["x1"] for o in objs) - min(o["x0"] for o in objs)) / 72.0
            if abs(span - PLACED_WIDTH_IN) < 0.02:
                return f"placed width re-measured in manuscript.pdf: {span:.4f} in"
    return "placed width NOT confirmed against manuscript.pdf"


def _type_census(pdf_path: str, scale: float):
    """Every printed type size in a figure, measured off the shipped PDF.

    "Same size hierarchy" is one of the three questions this sheet exists to
    answer, and it is the one an eye cannot answer. So it is measured.

    pdfplumber's .size is the font size for horizontal text but the glyph
    HEIGHT for 90-degree-rotated text, which makes a rotated y-axis label look
    like 2 pt type. Rotated runs are therefore read from .width, which carries
    the em. Getting this wrong reports a false alarm on every figure that has a
    rotated axis label -- which is most of them.
    """
    try:
        import pdfplumber
    except ImportError:
        return None
    import collections
    sizes = collections.Counter()
    with pdfplumber.open(pdf_path) as pdf:
        for ch in pdf.pages[0].chars:
            if not ch["text"].strip():
                continue
            m = ch.get("matrix")
            rotated = m is not None and abs(m[1]) > abs(m[0])
            fs = ch["width"] if rotated else ch["size"]
            sizes[round(fs * scale, 2)] += 1
    return sorted(sizes) if sizes else None


def _render(pdf_path: str, width_px: int):
    """Rasterise page 1 of a PDF to exactly width_px wide."""
    import fitz
    from PIL import Image
    doc = fitz.open(pdf_path)
    page = doc[0]
    scale = width_px / page.rect.width
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    native_w = page.rect.width / 72.0
    native_h = page.rect.height / 72.0
    doc.close()
    return img, native_w, native_h


def main() -> int:
    from PIL import Image, ImageDraw

    width_px = int(round(PLACED_WIDTH_IN * DPI))
    f_head = _font(int(0.155 * DPI), bold=True)
    f_sub = _font(int(0.105 * DPI))
    f_lab = _font(int(0.120 * DPI), bold=True)
    f_dim = _font(int(0.098 * DPI))

    panels, missing = [], []
    for num, fname, gist in FIGURE_ORDER:
        path = os.path.join(FIGURES, fname)
        if not os.path.exists(path):
            missing.append((num, fname))
            panels.append((num, fname, gist, None, 0.0, 0.0))
            continue
        img, nw, nh = _render(path, width_px)
        panels.append((num, fname, gist, img, nw, nh))

    body_h = 0
    for _, _, _, img, _, _ in panels:
        body_h += LABEL_H_PX + (img.height if img is not None else int(0.9 * DPI)) + GAP_PX
    sheet_h = HEADER_H_PX + body_h + FOOTER_H_PX
    sheet_w = width_px + 2 * MARGIN_PX

    sheet = Image.new("RGB", (sheet_w, sheet_h), BG)
    d = ImageDraw.Draw(sheet)

    y = int(0.28 * DPI)
    d.text((MARGIN_PX, y), "All figures at true print size", font=f_head, fill=INK)
    y += int(0.21 * DPI)
    # Wrap to the sheet's own text column so nothing is clipped at the edge --
    # a review sheet that silently truncates its own caption would be a poor
    # advertisement for the argument this paper is making.
    avail = sheet_w - 2 * MARGIN_PX
    for para in (
        f"Each rendered from its shipped PDF at {PLACED_WIDTH_IN:.2f} in wide, the width "
        f"the manuscript places it at (0.80 x 5.5 in linewidth), at {DPI} dpi.",
        "Labels are sans on purpose: type set in Times is figure content, type set in "
        "sans is this sheet's annotation.",
    ):
        line = ""
        for word in para.split():
            trial = (line + " " + word).strip()
            if d.textlength(trial, font=f_sub) > avail and line:
                d.text((MARGIN_PX, y), line, font=f_sub, fill=MUTED)
                y += int(0.135 * DPI)
                line = word
            else:
                line = trial
        if line:
            d.text((MARGIN_PX, y), line, font=f_sub, fill=MUTED)
            y += int(0.135 * DPI)

    y = HEADER_H_PX
    for num, fname, gist, img, nw, nh in panels:
        d.text((MARGIN_PX, y), f"Figure {num}", font=f_lab, fill=INK)
        tw = d.textlength(f"Figure {num}", font=f_lab)
        d.text((MARGIN_PX + tw + int(0.10 * DPI), y + int(0.018 * DPI)),
               f"{gist}   |   {fname}", font=f_dim, fill=MUTED)
        if img is None:
            d.text((MARGIN_PX, y + int(0.17 * DPI)),
                   "NOT ON DISK -- this figure is missing and is not shown.",
                   font=f_dim, fill=(190, 60, 30))
            y += LABEL_H_PX + int(0.9 * DPI) + GAP_PX
            continue
        placed_h = PLACED_WIDTH_IN * nh / nw
        census = _type_census(os.path.join(FIGURES, fname), PLACED_WIDTH_IN / nw)
        if census:
            span = (f"type {census[0]:.2f}-{census[-1]:.2f} pt printed, "
                    f"{len(census)} size(s)")
            if census[0] < MIN_PRINT_FONT_PT - 0.005:
                span += "  << BELOW THE %.2f pt FLOOR" % MIN_PRINT_FONT_PT
        else:
            span = "type sizes not measured"
        # Two rows, not one: the combined line overran the sheet width and was
        # silently clipped, which is the failure mode this sheet reports on.
        d.text((MARGIN_PX, y + int(0.175 * DPI)),
               f"prints at {PLACED_WIDTH_IN:.2f} x {placed_h:.2f} in"
               f"     (native {nw:.2f} x {nh:.2f} in, scaled to {PLACED_WIDTH_IN / nw:.3f})",
               font=f_dim, fill=MUTED)
        d.text((MARGIN_PX, y + int(0.305 * DPI)), span, font=f_dim,
               fill=(190, 60, 30) if census and census[0] < MIN_PRINT_FONT_PT - 0.005
               else MUTED)
        top = y + LABEL_H_PX
        sheet.paste(img, (MARGIN_PX, top))
        d.rectangle([MARGIN_PX - 1, top - 1, MARGIN_PX + img.width,
                     top + img.height], outline=FRAME, width=1)
        y = top + img.height + GAP_PX

    y = sheet_h - FOOTER_H_PX + int(0.10 * DPI)
    d.line([MARGIN_PX, y, sheet_w - MARGIN_PX, y], fill=FRAME, width=1)
    y += int(0.14 * DPI)
    d.text((MARGIN_PX, y), "Palette contract, as stated in the figure sources",
           font=f_lab, fill=INK)
    y += int(0.20 * DPI)
    sw = int(0.17 * DPI)
    for hexcol, meaning in PALETTE_CONTRACT:
        rgb = tuple(int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
        d.rectangle([MARGIN_PX, y, MARGIN_PX + sw, y + int(0.11 * DPI)],
                    fill=rgb, outline=(90, 90, 90))
        d.text((MARGIN_PX + sw + int(0.09 * DPI), y - int(0.004 * DPI)),
               f"{hexcol}   {meaning}", font=f_dim, fill=INK)
        y += int(0.155 * DPI)

    sheet.save(OUT, "PNG", optimize=True)

    print("=" * 78)
    print("REVIEW SHEET")
    print("=" * 78)
    print(f"  {_verify_placed_width()}")
    for num, fname, _, img, nw, nh in panels:
        if img is None:
            print(f"  Figure {num}: MISSING ({fname})")
        else:
            print(f"  Figure {num}: {fname:32s} native {nw:.3f} x {nh:.3f} in"
                  f"  -> prints {PLACED_WIDTH_IN:.2f} x {PLACED_WIDTH_IN * nh / nw:.2f} in")
    total = sum(PLACED_WIDTH_IN * nh / nw for _, _, _, img, nw, nh in panels if img is not None)
    print(f"  total placed height of all figures: {total:.2f} in")
    print(f"  wrote {OUT}  ({os.path.getsize(OUT) / 1e6:.2f} MB, "
          f"{sheet_w} x {sheet_h} px)")
    if missing:
        print("  WARNING: %d figure(s) missing from disk and shown as a gap."
              % len(missing))
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
