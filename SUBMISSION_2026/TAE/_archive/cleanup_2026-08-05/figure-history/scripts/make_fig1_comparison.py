"""Build figures/FIG1_COMPARISON.png from the two Figure 1 candidates.

Both PDFs are rendered from their shipped/vector sources at the size the paper
actually prints them: 4.40 in wide, i.e. 0.80 x 5.5 in linewidth.

Usage:  python SUBMISSION_2026/TAE/evidence/make_fig1_comparison.py
Output: SUBMISSION_2026/TAE/figures/FIG1_COMPARISON.png
"""
from __future__ import annotations

import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
TAE = os.path.dirname(HERE)
FIGURES = os.path.join(TAE, "figures")
OUT = os.path.join(FIGURES, "FIG1_COMPARISON.png")

PLACED_WIDTH_IN = 4.40
DPI = 300
MARGIN_PX = int(0.28 * DPI)
GAP_PX = int(0.22 * DPI)
LABEL_H_PX = int(0.42 * DPI)

BG = (255, 255, 255)
INK = (16, 16, 16)
MUTED = (98, 98, 98)
FRAME = (205, 205, 205)

PANELS = (
    ("fig0_problem_schematic.pdf", "fig0_problem_schematic"),
    ("fig0_variant_strip.pdf", "fig0_variant_strip"),
)


def _font(size_px: int, bold: bool = False):
    from PIL import ImageFont
    import matplotlib

    base = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(os.path.join(base, name), size_px)


def _render(pdf_path: str, width_px: int):
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
    rendered = []
    missing = []
    for fname, label in PANELS:
        path = os.path.join(FIGURES, fname)
        if not os.path.exists(path):
            missing.append(path)
            continue
        img, native_w, native_h = _render(path, width_px)
        rendered.append((fname, label, img, native_w, native_h))

    if missing:
        print("FAIL: comparison input PDF(s) missing:")
        for path in missing:
            print("  " + path)
        return 1

    sheet_w = width_px + 2 * MARGIN_PX
    sheet_h = (
        MARGIN_PX
        + sum(LABEL_H_PX + img.height for _, _, img, _, _ in rendered)
        + GAP_PX * (len(rendered) - 1)
        + MARGIN_PX
    )
    sheet = Image.new("RGB", (sheet_w, sheet_h), BG)
    d = ImageDraw.Draw(sheet)
    f_name = _font(int(0.122 * DPI), bold=True)
    f_dim = _font(int(0.092 * DPI))

    y = MARGIN_PX
    for idx, (fname, label, img, native_w, native_h) in enumerate(rendered):
        placed_h = PLACED_WIDTH_IN * native_h / native_w
        d.text((MARGIN_PX, y), label, font=f_name, fill=INK)
        d.text((MARGIN_PX, y + int(0.17 * DPI)),
               f"{fname} | rendered {PLACED_WIDTH_IN:.2f} x {placed_h:.2f} in "
               f"(native {native_w:.2f} x {native_h:.2f} in)",
               font=f_dim, fill=MUTED)
        top = y + LABEL_H_PX
        sheet.paste(img, (MARGIN_PX, top))
        d.rectangle([MARGIN_PX - 1, top - 1, MARGIN_PX + img.width,
                     top + img.height], outline=FRAME, width=1)
        y = top + img.height
        if idx < len(rendered) - 1:
            y += GAP_PX

    os.makedirs(FIGURES, exist_ok=True)
    sheet.save(OUT, "PNG", optimize=True)

    print("=" * 78)
    print("FIGURE 1 COMPARISON")
    print("=" * 78)
    for fname, _, _, native_w, native_h in rendered:
        print(f"  {fname:32s} native {native_w:.3f} x {native_h:.3f} in"
              f" -> rendered {PLACED_WIDTH_IN:.2f} x "
              f"{PLACED_WIDTH_IN * native_h / native_w:.2f} in")
    print(f"  wrote {OUT} ({sheet_w} x {sheet_h} px)")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
