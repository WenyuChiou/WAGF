"""Alternative Figure 1 schematic for the TAE submission.

This variant keeps the data and print-size guards from
fig0_problem_schematic.py, but redraws the concept as one continuous strip:
the agent-written situation description begins inside the output box, passes
under the rule, and becomes the denominator band in the score box.

Usage:  python SUBMISSION_2026/TAE/evidence/fig0_variant_strip.py
Outputs: figures/fig0_variant_strip.{tex,pdf,png}
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import Counter

import fig0_problem_schematic as BASE

HERE = os.path.abspath(os.path.dirname(__file__))
TAE = os.path.dirname(HERE)
FIGURES = os.path.join(TAE, "figures")

OUT_STEM = "fig0_variant_strip"
OUT_TEX = os.path.join(FIGURES, OUT_STEM + ".tex")
OUT_PDF = os.path.join(FIGURES, OUT_STEM + ".pdf")
OUT_PNG = os.path.join(FIGURES, OUT_STEM + ".png")

LINEWIDTH_IN = 5.5
PLACED_FRACTION = 0.80
PRINT_WIDTH_IN = LINEWIDTH_IN * PLACED_FRACTION
DOCX_DPI = 300
MAX_WIDTH_IN = 5.50
MAX_HEIGHT_IN = 1.90
MIN_PRINT_FONT_PT = 7.0

CANVAS_W_CM = 13.75
CANVAS_H_CM = 4.55

TYPE_SIZES_PT = {
    "header": 9.40,
    "body": 8.75,
    "note": 8.75,
    "closing": 8.75,
}

FIGURE_TEXTS = (
    "one output",
    "what it wants to do",
    "what it says about its situation",
    "the rule",
    "blocked, so it writes a new one",
    "the score",
    "asked for more water",
    "decisions where it said the situation was bad",
    "the rule moves the strip, and the strip is what the score divides by",
)

TEXT_ELEMENTS = (
    "txt_one_output",
    "txt_wants",
    "txt_situation",
    "txt_rule_header",
    "txt_blocked",
    "txt_score_header",
    "txt_numerator",
    "txt_denominator",
    "txt_closing",
)

REGION_ELEMENTS = (
    "box_output",
    "row_wants",
    "strip",
    "box_rule",
    "red_note",
    "box_score",
    "frac_num",
    "closing_band",
)

ALLOWED_REGIONS = {
    "txt_one_output": {"box_output"},
    "txt_wants": {"box_output", "row_wants"},
    "txt_situation": {"box_output", "strip"},
    "txt_rule_header": {"box_rule"},
    "txt_blocked": {"strip", "red_note"},
    "txt_score_header": {"box_score"},
    "txt_numerator": {"box_score", "frac_num"},
    "txt_denominator": {"box_score", "strip"},
    "txt_closing": {"closing_band"},
}

STRIP_RGB = (255, 247, 199)
STRIP_PROBES_CM = {
    "inside_output": (4.28, 1.34),
    "after_output": (4.68, 1.34),
    "under_rule": (5.18, 1.34),
    "before_score": (7.58, 1.34),
    "score_end": (12.70, 1.34),
}

TEXPT_TO_BP = 72.0 / 72.27
CM_TO_BP = 72.0 / 2.54
STANDALONE_BORDER_PT = 3.0

TEX_TEMPLATE = r"""\documentclass[tikz,border=3pt]{standalone}
\usepackage{mathptmx}
\usepackage{xcolor}
\usetikzlibrary{arrows.meta,calc}
\definecolor{stripcolor}{RGB}{255,247,199}
\definecolor{loopred}{RGB}{190,20,35}
\definecolor{boxline}{RGB}{38,38,38}
\newcommand{\HeaderFont}{\fontsize{9.4}{10.0}\selectfont}
\newcommand{\BodyFont}{\fontsize{8.75}{8.9}\selectfont}
\newcommand{\NoteFont}{\fontsize{8.75}{8.9}\selectfont}
\newcommand{\ClosingFont}{\fontsize{8.75}{9.2}\selectfont}
\newcommand{\emitpt}[3]{%
  \pgfpointanchor{#2}{#3}\pgfgetlastxy{\ptx}{\pty}%
  \typeout{FIGPT #1 \ptx\space\pty}}
\newcommand{\emitnodebox}[2]{%
  \emitpt{#1.sw}{#2}{south west}%
  \emitpt{#1.ne}{#2}{north east}}
\newcommand{\emitrect}[3]{%
  \emitpt{#1.sw}{#2}{center}%
  \emitpt{#1.ne}{#3}{center}}
\begin{document}
\begin{tikzpicture}[
  >=Latex,
  every node/.style={inner sep=0.8pt},
  header/.style={font=\HeaderFont\bfseries, align=center},
  body/.style={font=\BodyFont, align=center},
  note/.style={font=\NoteFont, align=left},
  closing/.style={font=\ClosingFont, align=center},
  box/.style={rounded corners=6pt, line width=0.62pt, draw=boxline, fill=white},
  fine/.style={line width=0.42pt, draw=black!38},
  icon/.style={line width=0.58pt, draw=black!68, line cap=round, line join=round},
  redarrow/.style={->, line width=1.35pt, draw=loopred}
]
\path[use as bounding box] (0,0) rectangle (13.75,4.55);
\coordinate (canvasSW) at (0,0);
\coordinate (canvasNE) at (13.75,4.55);

\coordinate (outputSW) at (0.30,0.85);
\coordinate (outputNE) at (4.45,3.95);
\coordinate (ruleSW) at (4.90,2.05);
\coordinate (ruleNE) at (7.15,3.78);
\coordinate (scoreSW) at (8.30,0.85);
\coordinate (scoreNE) at (13.45,3.95);
\coordinate (stripSW) at (0.62,1.27);
\coordinate (stripNE) at (13.18,2.05);
\coordinate (rowwantsSW) at (0.55,2.31);
\coordinate (rowwantsNE) at (4.22,2.91);
\coordinate (rednoteSW) at (5.68,1.34);
\coordinate (rednoteNE) at (8.02,2.07);
\coordinate (fracnumSW) at (8.72,2.30);
\coordinate (fracnumNE) at (12.72,2.78);
\coordinate (closingSW) at (0.30,0.08);
\coordinate (closingNE) at (13.45,0.62);

\filldraw[box] (outputSW) rectangle (outputNE);
\filldraw[box] (scoreSW) rectangle (scoreNE);
\fill[stripcolor] (stripSW) rectangle (stripNE);
\filldraw[box] (ruleSW) rectangle (ruleNE);
\draw[box, fill opacity=0, draw opacity=1] (outputSW) rectangle (outputNE);
\draw[box, fill opacity=0, draw opacity=1] (scoreSW) rectangle (scoreNE);
\draw[fine] (0.58,2.10) -- (4.17,2.10);
\draw[fine] (8.70,2.17) -- (12.72,2.17);

% Output icon and label.
\draw[icon] (1.12,3.46) rectangle (1.48,3.76);
\draw[icon] (1.20,3.76) -- (1.20,3.88) -- (1.40,3.88) -- (1.40,3.76);
\draw[icon] (1.23,3.63) circle (0.025);
\draw[icon] (1.37,3.63) circle (0.025);
\draw[icon] (1.24,3.54) -- (1.36,3.54);
\node[header] (txtoneoutput) at (2.75,3.61) {one output};

% Action row.
\draw[icon] (0.72,2.36) -- (0.72,2.83) -- (1.00,2.83) -- (1.13,2.70) -- (1.13,2.36) -- cycle;
\draw[icon] (1.00,2.83) -- (1.00,2.70) -- (1.13,2.70);
\draw[icon] (0.80,2.66) -- (1.03,2.66);
\draw[icon] (0.80,2.56) -- (1.00,2.56);
\draw[icon] (0.97,2.40) -- (1.22,2.65);
\draw[icon] (1.19,2.68) -- (1.27,2.72);
\node[body, anchor=west, align=left, text width=2.55cm] (txtwants) at (1.45,2.61)
  {what it wants to do};

% Situation row: the continuous strip begins here.
\draw[icon, rounded corners=1.2pt]
  (0.70,1.51) -- (0.70,1.86) -- (1.15,1.86) -- (1.15,1.51) -- (0.95,1.51)
  -- (0.84,1.39) -- (0.85,1.51) -- cycle;
\draw[icon] (0.82,1.68) circle (0.105);
\draw[icon] (0.82,1.68) -- (0.91,1.74);
\draw[icon] (0.74,1.68) -- (0.78,1.68);
\draw[icon] (0.86,1.77) -- (0.88,1.81);
\node[body, anchor=west, align=left, text width=2.72cm] (txtsituation) at (1.43,1.66)
  {what it says about its situation};

% Rule box on the strip.
\draw[icon] (5.18,3.33) -- (5.43,3.45) -- (5.68,3.33) -- (5.66,3.11)
  .. controls (5.60,2.98) and (5.52,2.91) .. (5.43,2.87)
  .. controls (5.34,2.91) and (5.26,2.98) .. (5.20,3.11) -- cycle;
\draw[icon] (5.33,3.27) -- (5.53,3.07);
\draw[icon] (5.53,3.27) -- (5.33,3.07);
\node[header] (txtruleheader) at (6.30,3.34) {the rule};
\draw[icon] (5.45,2.45) -- (5.45,2.88);
\draw[icon] (6.60,2.45) -- (6.60,2.88);
\draw[icon] (5.38,2.45) -- (6.67,2.45);
\draw[icon] (5.38,2.88) -- (6.67,2.88);
\draw[icon] (5.62,2.45) -- (5.94,2.88);
\draw[icon] (5.98,2.45) -- (6.30,2.88);
\draw[icon] (6.34,2.45) -- (6.66,2.88);
\draw[redarrow] (5.56,2.05) -- (5.56,1.58);
\node[note, text=loopred, anchor=west, text width=2.18cm] (txtblocked) at (5.76,1.71)
  {blocked, so it writes a new one};

% Score box and denominator endpoint.
\draw[icon] (8.62,3.46) -- (8.62,3.12) -- (9.10,3.12);
\draw[icon] (8.70,3.12) rectangle (8.78,3.30);
\draw[icon] (8.84,3.12) rectangle (8.92,3.43);
\draw[icon] (8.98,3.12) rectangle (9.06,3.23);
\node[header] (txtscoreheader) at (10.88,3.34) {the score};
\node[body] (txtnumerator) at (10.72,2.54) {asked for more water};
\node[body, text width=4.10cm] (txtdenominator) at (10.62,1.66)
  {decisions where it said the situation was bad};
\draw[icon] (12.86,1.39) rectangle (13.13,1.94);
\draw[icon] (12.90,1.89) -- (13.03,1.89);
\draw[icon] (12.90,1.79) -- (12.98,1.79);
\draw[icon] (12.90,1.69) -- (13.03,1.69);
\draw[icon] (12.90,1.59) -- (12.98,1.59);
\draw[icon] (12.90,1.49) -- (13.03,1.49);

\node[closing] (txtclosing) at (6.88,0.35)
  {the rule moves the strip, and the strip is what the score divides by};

\emitrect{canvas}{canvasSW}{canvasNE}
\emitnodebox{txt_one_output}{txtoneoutput}
\emitnodebox{txt_wants}{txtwants}
\emitnodebox{txt_situation}{txtsituation}
\emitnodebox{txt_rule_header}{txtruleheader}
\emitnodebox{txt_blocked}{txtblocked}
\emitnodebox{txt_score_header}{txtscoreheader}
\emitnodebox{txt_numerator}{txtnumerator}
\emitnodebox{txt_denominator}{txtdenominator}
\emitnodebox{txt_closing}{txtclosing}
\emitrect{box_output}{outputSW}{outputNE}
\emitrect{row_wants}{rowwantsSW}{rowwantsNE}
\emitrect{strip}{stripSW}{stripNE}
\emitrect{box_rule}{ruleSW}{ruleNE}
\emitrect{red_note}{rednoteSW}{rednoteNE}
\emitrect{box_score}{scoreSW}{scoreNE}
\emitrect{frac_num}{fracnumSW}{fracnumNE}
\emitrect{closing_band}{closingSW}{closingNE}
\end{tikzpicture}
\end{document}
"""


def _text_contract_violations(tex: str) -> list[str]:
    problems = []
    node_texts = re.findall(
        r"\\node(?:\[[^\]]*\])?\s*\([^)]*\)\s*(?:at\s*\([^)]*\))?\s*\{([^{}]+)\};",
        tex,
        flags=re.S,
    )
    actual = Counter(" ".join(text.split()) for text in node_texts)
    expected = Counter(FIGURE_TEXTS)
    for text in FIGURE_TEXTS:
        if actual[text] != expected[text]:
            problems.append(
                f"{text!r} appears as a text node {actual[text]} time(s)")
    for text, count in sorted((actual - expected).items()):
        problems.append(f"unexpected text node {text!r} appears {count} time(s)")
    node_count = sum(actual.values())
    if node_count != len(FIGURE_TEXTS):
        problems.append(f"expected {len(FIGURE_TEXTS)} text node(s), found {node_count}")
    return problems


def _parse_boxes(log: str) -> dict[str, tuple[float, float, float, float]]:
    pts = {}
    for name, x, y in re.findall(r"FIGPT (\S+) (-?[\d.]+)pt (-?[\d.]+)pt", log):
        pts[name] = (float(x), float(y))
    boxes = {}
    for el in ("canvas",) + TEXT_ELEMENTS + REGION_ELEMENTS:
        sw, ne = pts.get(f"{el}.sw"), pts.get(f"{el}.ne")
        if sw is None or ne is None:
            raise SystemExit(f"FAIL: pdflatex did not report a box for {el}")
        boxes[el] = (min(sw[0], ne[0]), min(sw[1], ne[1]),
                     max(sw[0], ne[0]), max(sw[1], ne[1]))
    return boxes


def _check_layout(
        boxes: dict[str, tuple[float, float, float, float]],
        pdf_width_bp: float) -> tuple[list[str], float, dict]:
    bp_boxes = BASE._texpt_boxes_to_bp(boxes)
    text_boxes = {name: bp_boxes[name] for name in TEXT_ELEMENTS}
    regions = {name: bp_boxes[name] for name in REGION_ELEMENTS}
    violations, min_sep_bp = BASE._layout_violations(
        text_boxes, regions, ALLOWED_REGIONS)

    print_scale = PRINT_WIDTH_IN / (pdf_width_bp / 72.0)
    min_print_pt = min_sep_bp * print_scale
    print("\n  LAYOUT CHECK, from TeX boxes on the rendered figure")
    print(f"    text elements tested: {len(text_boxes)}")
    print(f"    regions tested: {len(regions)}")
    print(f"    violations: {len(violations)}")
    for item in violations[:15]:
        print(f"      {item}")
    if len(violations) > 15:
        print(f"      ... {len(violations) - 15} more")
    print(f"    minimum text-text separation: {min_print_pt:.2f} printed pt")

    mutation_text = dict(text_boxes)
    mutation_text["txt_denominator"] = BASE._center_like(
        text_boxes["txt_denominator"], regions["box_rule"])
    mutation_violations, mutation_min_sep = BASE._layout_violations(
        mutation_text, regions, ALLOWED_REGIONS)
    restored_violations, _ = BASE._layout_violations(
        text_boxes, regions, ALLOWED_REGIONS)
    mutation = {
        "moved": "txt_denominator -> box_rule",
        "mutation_violations": mutation_violations,
        "mutation_min_print_pt": mutation_min_sep * print_scale,
        "restored_violations": restored_violations,
    }
    print("\n  MUTATION CHECK")
    print(f"    moved {mutation['moved']}")
    print(f"    mutation test fired: {'yes' if mutation_violations else 'NO'}")
    print(f"    mutated checker violations: {len(mutation_violations)}")
    print(f"    restored checker violations: {len(restored_violations)}")
    if mutation_violations:
        print(f"    first mutated violation: {mutation_violations[0]}")
    return violations, min_print_pt, mutation


def _compile_tex(tex_path: str) -> tuple[str, dict[str, tuple[float, float, float, float]]] | None:
    pdflatex = next((p for p in BASE.PDFLATEX_CANDIDATES if p and os.path.exists(p)), None)
    if not pdflatex:
        print("  pdflatex NOT FOUND -- .tex written, PDF not built.")
        return None
    proc = subprocess.run(
        [pdflatex, "-interaction=nonstopmode", "-halt-on-error", "-enable-installer",
         "-output-directory", FIGURES, tex_path],
        cwd=FIGURES, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=300, env=BASE._tex_subprocess_env(pdflatex))
    if proc.returncode != 0 or not os.path.exists(OUT_PDF):
        print("  pdflatex FAILED:\n" + proc.stdout[-2500:])
        return None
    boxes = _parse_boxes(proc.stdout)
    for ext in (".aux", ".log"):
        p = os.path.join(FIGURES, OUT_STEM + ext)
        if os.path.exists(p):
            os.remove(p)
    return proc.stdout, boxes


def _render_pdf(pdf: str, png: str) -> tuple[float, float, int, int, float, float]:
    import fitz

    doc = fitz.open(pdf)
    page = doc[0]
    native_w_in = page.rect.width / 72.0
    native_h_in = page.rect.height / 72.0
    pix = page.get_pixmap(dpi=DOCX_DPI, alpha=False)
    pix.save(png)
    doc.close()
    placed_h_in = PRINT_WIDTH_IN * native_h_in / native_w_in
    include_scale = PRINT_WIDTH_IN / native_w_in
    return native_w_in, native_h_in, pix.width, pix.height, placed_h_in, include_scale


def _sample_rendered_strip(pdf: str) -> dict[str, tuple[int, int, int]]:
    import fitz

    doc = fitz.open(pdf)
    page = doc[0]
    scale = DOCX_DPI / 72.0
    pix = page.get_pixmap(dpi=DOCX_DPI, alpha=False)
    page_h_bp = page.rect.height
    out = {}
    for name, (x_cm, y_cm) in STRIP_PROBES_CM.items():
        x_bp = STANDALONE_BORDER_PT * TEXPT_TO_BP + x_cm * CM_TO_BP
        y_bp = STANDALONE_BORDER_PT * TEXPT_TO_BP + y_cm * CM_TO_BP
        px = int(round(x_bp * scale))
        py = int(round((page_h_bp - y_bp) * scale))
        patch = {pix.pixel(px + dx, py + dy)
                 for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
        if len(patch) != 1:
            raise SystemExit(
                f"FAIL: strip probe {name} at ({x_cm}, {y_cm}) cm is not on flat "
                f"colour; it sampled {len(patch)} distinct pixels")
        out[name] = patch.pop()
    doc.close()
    return out


def _check_strip(pdf: str) -> list[str]:
    fails = []
    sampled = _sample_rendered_strip(pdf)
    print("\n  CONTINUOUS-STRIP CHECK, sampled from the rendered page")
    for name, rgb in sampled.items():
        print(f"    {name:14s} RGB{rgb}")
    distinct = set(sampled.values())
    if len(distinct) != 1:
        fails.append("the strip probes do not render as one continuous colour")
    elif distinct.pop() != STRIP_RGB:
        fails.append(f"strip fill is not the declared RGB{STRIP_RGB}")
    print(f"    one yellow band: {'ok' if not fails else 'FAIL'}")
    return fails


def _print_type_report(scale: float) -> float:
    print("\n  TYPE HIERARCHY")
    for name, size in TYPE_SIZES_PT.items():
        print(f"    {name:8s} {size:4.2f} pt on canvas -> {size * scale:4.2f} pt in print")
    smallest = min(TYPE_SIZES_PT.values()) * scale
    print(f"    smallest after scaling: {smallest:.2f} pt "
          f"(floor {MIN_PRINT_FONT_PT:.2f} pt)")
    return smallest


def main() -> int:
    gov, ung = BASE._runs("production"), BASE._runs("ungoverned")
    seeds = sorted(set(gov) & set(ung))
    if not seeds:
        print("FAIL: governed and ungoverned runs have no shared seeds")
        return 1

    import statistics as st

    gh = st.mean([BASE._measure(gov[s])[0] for s in seeds])
    gr = st.mean([BASE._measure(gov[s])[1] for s in seeds])
    nh = st.mean([BASE._measure(ung[s])[0] for s in seeds])
    nr = st.mean([BASE._measure(ung[s])[1] for s in seeds])

    print("fig0 variant strip -- values recomputed from the corpus for the directional figure check\n")
    for key, value in (
            ("gov_rate", gr),
            ("nov_rate", nr),
            ("gov_high", gh),
            ("nov_high", nh)):
        print(f"  {key:10s} computed {value:6.2f}")
    direction_error = BASE._directional_claim_error(gh, nh)
    print(f"\n  directional claim gov_high < nov_high: "
          f"{gh:.2f} < {nh:.2f} {'ok' if direction_error is None else 'FAIL'}")
    if direction_error:
        print(f"\n  {direction_error}")
        return 1

    os.makedirs(FIGURES, exist_ok=True)
    tex = TEX_TEMPLATE
    text_problems = _text_contract_violations(tex)
    print(f"  text contract: {len(FIGURE_TEXTS)} expected string(s), "
          f"{len(TEXT_ELEMENTS)} text node(s)")
    if text_problems:
        print(f"\n  FAIL: text contract violated: {text_problems}")
        return 1

    with open(OUT_TEX, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(tex)
    print(f"\n  wrote {OUT_TEX}")

    compiled = _compile_tex(OUT_TEX)
    if compiled is None:
        return 1
    _, boxes = compiled
    print(f"  expected-node check: {len(TEXT_ELEMENTS)} text node(s) and "
          f"{len(REGION_ELEMENTS)} region(s) reported by pdflatex, ok")

    native_w, native_h, raster_w, raster_h, placed_h, include_scale = _render_pdf(
        OUT_PDF, OUT_PNG)
    print(f"  wrote {OUT_PNG} ({DOCX_DPI} dpi, {raster_w} x {raster_h} px)")

    fails = []
    print(f"  canvas size check: rendered {native_w:.2f} x {native_h:.2f} in "
          f"(budget {MAX_WIDTH_IN:.2f} x {MAX_HEIGHT_IN:.2f} in)")
    if native_w > MAX_WIDTH_IN + 0.01:
        fails.append(f"width {native_w:.2f} in exceeds {MAX_WIDTH_IN:.2f} in")
    if native_h > MAX_HEIGHT_IN + 0.01:
        fails.append(f"height {native_h:.2f} in exceeds {MAX_HEIGHT_IN:.2f} in")

    layout_violations, min_print_sep, mutation = _check_layout(boxes, native_w * 72.0)
    if layout_violations:
        fails.append("layout collisions")
    if not mutation["mutation_violations"]:
        fails.append("mutation check did not fail")
    if mutation["restored_violations"]:
        fails.append("mutation undo left checker failing")

    print(f"\n  figure size {native_w:.2f} x {native_h:.2f} in; placed at "
          f"{PRINT_WIDTH_IN:.2f} in wide -> {PRINT_WIDTH_IN:.2f} x {placed_h:.2f} in "
          f"(actual includegraphics scale {include_scale:.3f})")
    smallest = _print_type_report(PLACED_FRACTION)
    if smallest < MIN_PRINT_FONT_PT:
        fails.append("smallest type below print floor")

    fails.extend(_check_strip(OUT_PDF))

    print("\n  CONCEPT READABILITY CHECK")
    print("    The situation row and the denominator are not merely the same colour:")
    print("    they are sampled from one uninterrupted strip, so the reader sees the")
    print("    denominator as the thing the agent writes and the rule can move.")

    if fails:
        print(f"\n  FAIL: {len(fails)} check(s) did not pass: {fails}")
        return 1
    print("\n  all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
