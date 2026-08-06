"""SCRATCH PROBE -- settles which matplotlib font setting the three figure
scripts should use. Not part of the evidence pipeline: nothing imports it,
run_all.py does not call it, and it writes no file that survives the run.

WHY THIS EXISTS
---------------
submission_gate.py reports 12 embedded fonts in manuscript.pdf: 9 Type 1 from
the LaTeX body, and 3 CIDFontType2 (TrueType) -- DejaVuSans, DejaVuSans-Bold,
DejaVuSans-Oblique -- coming from figures/fig{1,2,3}*.pdf via `pdf.fonttype: 42`
in fig1_rule_layers.py, fig2_mechanism.py and fig3_consequence.py. That setting
was the fix for an earlier Type 3 problem, and it traded one non-Type-1 class
for another.

The venue rule is NOT violated. template/neurips_2026.tex says, verbatim:

    line 376  "Your PDF file must only contain Type 1 or Embedded TrueType
               fonts."
    line 416  "If your file contains type 3 fonts or non embedded TrueType
               fonts, we will ask you to fix it."

Embedded TrueType is explicitly permitted. The open question was therefore
cosmetic, not compliance: the body is Times (NimbusRomNo9L) and the figures are
DejaVu Sans, and the figures sit inline with the text.

This probe renders a throwaway figure under each candidate setting and reads
the emitted PDF's font dictionaries with pypdf -- BaseFont, Subtype, and which
/FontFile* key carries the outlines, i.e. whether the font is really embedded,
which is what the venue rule turns on.

It deliberately does NOT import _data.py. While the irrigation ministral3:8b
seed-44 no-validator run is still being written, _data.py refuses to return a
partial cell and every importer of it raises.

WHAT IT SETTLED  (run 2026-08-03, matplotlib 3.10.7, pypdf 6.4.0)
-----------------------------------------------------------------
PART A -- embedding:

  (a) fonttype=42 + DejaVu Sans   CIDFontType2, embedded via /FontFile2. Today.
  (b) use14corefonts + Times      Type1, NOT EMBEDDED (no /FontFile* at all)
                                  -- AND it re-introduces a Type 3 font, see
                                  the note below.
  (c) fonttype=42 + DejaVu Serif  CIDFontType2, embedded via /FontFile2.
  (d) fonttype=42 + STIXGeneral   CIDFontType2, embedded via /FontFile2.
  (e) fonttype=3 (the old bug)    Type3. This is the class the venue blocks.

(b) IS DISQUALIFIED OUTRIGHT, and not on taste. use14corefonts has no AFM route
for mathtext, so a "$\\Delta$" label falls back to DejaVu Sans drawn as TYPE 3
-- precisely the class neurips_2026.tex line 416 blocks. Isolated by contrast:

    use14corefonts + Times, NO mathtext   -> [('/Times-Roman', '/Type1')]
    use14corefonts + Times, WITH $\\Delta$ -> [('/BMQQDV+DejaVuSans', '/Type3'),
                                              ('/Times-Roman', '/Type1')]

fig2 and fig3 both use "$\\Delta$", so choosing (b) would put the forbidden font
class back into the submission that pdf.fonttype=42 was adopted to remove.

PART B -- the minus sign independently disqualifies (b). Under use14corefonts
the font is
written with /WinAnsiEncoding, and matplotlib emits byte 0x3F for U+2212 MINUS
SIGN -- 0x3F is a literal question mark in that encoding. A tick label of -100
renders as "?100". This is silent: no warning is raised. It is not a
text-extraction artifact; the byte in the content stream really is 0x3F. And it
is not hypothetical -- the built figures contain 6 such glyphs today:

    figures/fig2_mechanism.pdf    4  (-100, -75, -50, -25)
    figures/fig3_consequence.pdf  2  (-20, -10)

The Times AFM does carry a `minus` glyph name; the loss is in the encoding
matplotlib chooses, not in the font.

PART C -- mathtext leaks the old family back in. fig2 and fig3 use "$\\Delta$"
(fig2_mechanism.py:581,685; fig3_consequence.py:465). Setting font.family alone
leaves mathtext on its default fontset, and DejaVuSans is re-embedded just to
draw that one glyph. mathtext.fontset must be set alongside font.family, or the
change does not actually remove the sans font.

RECOMMENDATION: (d) -- fonttype=42 + STIXGeneral + mathtext.fontset="stix".
Keeps embedding (compliant, and renders identically everywhere), and STIX is
Times-metric, so it matches the NimbusRomNo9L body far more closely than
DejaVu Serif does. (b) is rejected twice over -- it emits a Type 3 font and it
corrupts every negative tick label -- so the real choice is only between
staying with (a) and moving to (c)/(d), all three of which are venue-compliant.
The change is therefore cosmetic and optional, and must not be rushed.

CAUTION -- this probe cannot clear the change. Changing the family changes text
metrics, and each of the three figure scripts carries `_assert_no_text_overlaps`
(fig1:472, fig2:484, fig3:369) whose printed "TEXT OVERLAP CHECK: 0" is the
acceptance criterion. Those scripts import _data.py and cannot run until the
corpus is complete. Apply and re-verify AFTER the run lands.

USAGE
-----
    PYTHONIOENCODING=utf-8 python SUBMISSION_2026/TAE/evidence/probe_figure_font.py
    ... --keep     leave the throwaway PDFs on disk for manual inspection

By default every PDF it writes is deleted before it exits.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import tempfile
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from pypdf import PdfReader  # noqa: E402


REPO_FIGURES = Path(__file__).resolve().parent.parent / "figures"

# Each candidate is (label, rcParams-delta, note).
CANDIDATES: list[tuple[str, dict, str]] = [
    ("(a) fonttype=42 + DejaVu Sans  [TODAY]",
     {"pdf.fonttype": 42, "font.family": "DejaVu Sans"},
     "current state of fig1/2/3"),
    ("(b) use14corefonts + Times",
     {"pdf.use14corefonts": True, "font.family": "Times"},
     "base-14, not embedded"),
    ("(c) fonttype=42 + DejaVu Serif",
     {"pdf.fonttype": 42, "font.family": "DejaVu Serif",
      "mathtext.fontset": "dejavuserif"},
     "ships with matplotlib"),
    ("(d) fonttype=42 + STIXGeneral",
     {"pdf.fonttype": 42, "font.family": "STIXGeneral",
      "mathtext.fontset": "stix"},
     "ships with matplotlib, Times-metric -- RECOMMENDED"),
    ("(e) fonttype=3  [the old bug]",
     {"pdf.fonttype": 3, "font.family": "DejaVu Sans"},
     "shown for contrast; venue blocks this"),
]


def _draw(outfile: Path, delta: dict) -> list[str]:
    """Render a throwaway figure exercising the text kinds the real ones use."""
    with plt.rc_context(rc={"savefig.dpi": 300, **delta}):
        fig, ax = plt.subplots(figsize=(3.2, 2.0))
        # Regular, bold, italic, tick labels, a legend, a NEGATIVE tick (U+2212
        # by default) and a mathtext Delta -- the last two are what Parts B and
        # C turn on.
        ax.plot([-1, 0, 1], [-0.5, 0.2, 0.9], label="governed")
        ax.set_xlabel("regular label")
        ax.set_ylabel("$\\Delta$ increase rate (pp)")
        ax.set_title("bold title", fontweight="bold")
        ax.text(0.0, 0.0, "italic annotation", style="italic", fontsize=7)
        ax.legend(fontsize=7)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            fig.savefig(outfile, format="pdf", bbox_inches="tight")
        plt.close(fig)
    return [str(w.message) for w in caught]


def _fonts_in(pdf: Path) -> list[tuple[str, str, str]]:
    """(BaseFont, Subtype, embedding) for every font in the PDF.

    Type0 fonts carry no outlines themselves; the descendant CIDFont does, so
    this resolves through /DescendantFonts the way submission_gate.py does.
    """
    out: set[tuple[str, str, str]] = set()
    for page in PdfReader(str(pdf)).pages:
        res = page.get("/Resources")
        fonts = res.get_object().get("/Font") if res is not None else None
        if fonts is None:
            continue
        for ref in fonts.get_object().values():
            obj = ref.get_object()
            targets = ([d.get_object() for d in obj["/DescendantFonts"]]
                       if obj.get("/Subtype") == "/Type0" and "/DescendantFonts" in obj
                       else [obj])
            for t in targets:
                desc = t.get("/FontDescriptor")
                embed = "NOT EMBEDDED"
                if desc is not None:
                    d = desc.get_object()
                    for key in ("/FontFile", "/FontFile2", "/FontFile3"):
                        if key in d:
                            embed = f"embedded via {key}"
                            break
                elif t.get("/Subtype") == "/Type3":
                    embed = "Type 3 (glyphs inline, no font program)"
                out.add((str(t.get("/BaseFont", "(none)")),
                         str(t.get("/Subtype", "?")), embed))
    return sorted(out)


def part_a(workdir: Path) -> None:
    print("=" * 78)
    print("PART A -- what ends up in the PDF, per candidate")
    print("=" * 78)
    for i, (label, delta, note) in enumerate(CANDIDATES):
        pdf = workdir / f"probe_{i}.pdf"
        warns = _draw(pdf, delta)
        print(f"\n{label}   -- {note}")
        print(f"    rc: {delta}")
        for base, subtype, embed in _fonts_in(pdf):
            print(f"    FONT  {base:<34} {subtype:<14} {embed}")
        for w in warns:
            print(f"    WARN  {w}")


def part_b(workdir: Path) -> None:
    print("\n" + "=" * 78)
    print("PART B -- the U+2212 minus sign under base-14 Times")
    print("=" * 78)
    pdf = workdir / "minus.pdf"
    with plt.rc_context({"pdf.use14corefonts": True, "font.family": "Times"}):
        fig, ax = plt.subplots(figsize=(3, 2))
        ax.plot([-1, 0, 1], [-0.5, 0.2, 0.9])
        fig.savefig(pdf, format="pdf")
        plt.close(fig)
    page = PdfReader(str(pdf)).pages[0]
    for key, ref in page["/Resources"]["/Font"].items():
        o = ref.get_object()
        print(f"    {key}  {o.get('/BaseFont')}  /Encoding={o.get('/Encoding')}")
    stream = page.get_contents().get_data().decode("latin-1")
    print("    Tj literals emitted for the negative tick labels:")
    for lit in re.findall(r"\(([^)]*)\)\s*Tj", stream)[:6]:
        print(f"        {lit!r:14} bytes={[hex(ord(c)) for c in lit]}")
    print("    -> 0x3f is '?' in WinAnsiEncoding. The minus is lost, silently.")

    print("\n    Minus signs in the figures as built today:")
    for name in ("fig1_rule_layers", "fig2_mechanism", "fig3_consequence"):
        f = REPO_FIGURES / f"{name}.pdf"
        if not f.exists():
            print(f"        {name:20} (not built)")
            continue
        text = "".join(p.extract_text() for p in PdfReader(str(f)).pages)
        hits = [w for w in text.split() if "−" in w]
        print(f"        {name:20} {text.count(chr(0x2212))}  {hits[:6]}")


def part_c(workdir: Path) -> None:
    print("\n" + "=" * 78)
    print("PART C -- mathtext re-embeds the sans font unless fontset is set too")
    print("=" * 78)
    cases = [
        ("STIXGeneral, mathtext DEFAULT",
         {"pdf.fonttype": 42, "font.family": "STIXGeneral"}),
        ("STIXGeneral, mathtext=stix",
         {"pdf.fonttype": 42, "font.family": "STIXGeneral", "mathtext.fontset": "stix"}),
        ("DejaVu Serif, mathtext DEFAULT",
         {"pdf.fonttype": 42, "font.family": "DejaVu Serif"}),
        ("DejaVu Serif, mathtext=dejavuserif",
         {"pdf.fonttype": 42, "font.family": "DejaVu Serif", "mathtext.fontset": "dejavuserif"}),
    ]
    for j, (label, rc) in enumerate(cases):
        pdf = workdir / f"math_{j}.pdf"
        _draw(pdf, rc)
        names = sorted({b.split("+")[-1] for b, _, _ in _fonts_in(pdf)})
        print(f"    {label:36} -> {names}")


def main() -> None:
    ap = argparse.ArgumentParser(description="figure-font probe")
    ap.add_argument("--keep", action="store_true",
                    help="do not delete the throwaway PDFs")
    args = ap.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="probe_figure_font_"))
    print(f"matplotlib {matplotlib.__version__}   scratch dir {workdir}\n")
    try:
        part_a(workdir)
        part_b(workdir)
        part_c(workdir)
    finally:
        print()
        if args.keep:
            print(f"kept: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)
            print(f"deleted scratch dir (exists: {workdir.exists()})")
        leftovers = [p for p in Path(__file__).parent.glob("probe_*.pdf")]
        print(f"stray probe PDFs in evidence/: {len(leftovers)}")


if __name__ == "__main__":
    main()
