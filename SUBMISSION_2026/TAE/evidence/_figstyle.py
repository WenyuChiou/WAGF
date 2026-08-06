"""_figstyle.py -- the ONE typeface and size hierarchy for fig1, fig2 and fig3.

    import _figstyle as FS
    FS.apply()                      # rcParams, font guard, glyph guard
    ax.set_title(t, fontsize=FS.FS_PANEL_TITLE)

WHY THIS FILE EXISTS
--------------------
fig1_rule_layers.py, fig2_mechanism.py and fig3_consequence.py each carried
their own `plt.rcParams.update({...})` block. Three copies of a shared decision
is how the palette drifted before this pass -- fig2's panel C was drawn in a
lighter shade of the arm blue that fig2's own panel B had just taught, because
nothing structural said the two panels answered to the same vocabulary. The
typeface and the size hierarchy are the same class of shared decision, so they
live here and nowhere else. A figure script may pass local overrides to
``apply()`` for things that really are local (hatch line width, tick length),
but never for the family or for a size in the hierarchy below.

THE TYPEFACE: Times New Roman
-----------------------------
The manuscript body is Times, so this makes figure text and body text match on
the page rather than setting a sans figure inside a serif paper.

    NOTE, AND THIS IS THE DELIBERATE TRADE: Times New Roman is a SYSTEM font
    (C:\\Windows\\Fonts\\times.ttf), not one that ships with matplotlib. These
    figures therefore depend on the machine they are built on. A rebuild on a
    machine without Times New Roman will FAIL LOUDLY at ``assert_font()``
    below rather than silently emitting a figure in a different typeface. That
    is the intended behaviour: a build that dies is a build someone fixes, and
    a build that quietly changes typeface is one that ships.

``pdf.fonttype`` stays 42, so glyphs embed as TrueType outlines.
template/neurips_2026.tex line 376 permits "Type 1 or Embedded TrueType"
verbatim and line 416 blocks Type 3; embedded TrueType is the permitted class.

WHY THE GUARDS ARE NOT OPTIONAL
-------------------------------
matplotlib does NOT raise when a font family is missing. ``findfont`` logs
"Font family ['X'] not found. Falling back to DejaVu Sans." at INFO level and
returns the DejaVu path. Nothing fails; the figure renders; the typeface is
simply not the one that was asked for. That is exactly the silent-failure class
this paper is about, so it is asserted rather than assumed:

  * ``assert_font()``   resolves regular / bold / italic through the same
                        ``findfont`` the renderer uses and requires the basename
                        to be times.ttf / timesbd.ttf / timesi.ttf. The DejaVu
                        fallback path fails this by construction.
  * ``assert_glyphs()`` reads the resolved font's own cmap and requires a
                        non-zero glyph index for every special character these
                        figures draw. A missing glyph in a TrueType font renders
                        as a box, or is silently substituted from another file,
                        and BOTH would ship. Querying the cmap catches it before
                        anything is drawn; looking at the PNG does not.

Mathtext must be set alongside the family. fig2 and fig3 draw "$\\Delta$", and
leaving ``mathtext.fontset`` on its default re-embeds DejaVuSans just to carry
that one glyph -- so the sans font comes back into the PDF even though the
family changed. ``mathtext.fontset = "custom"`` pointed at the same family is
what actually removes it.

THE SIZE HIERARCHY
------------------
Six roles, six values, ordered by HOW THE ELEMENT IS READ rather than by how
important its content is. Printed size is native x 0.80, because the manuscript
includes every one of these figures at 0.80\\linewidth.

    role                 native   printed   why it sits here
    -------------------  ------  --------  --------------------------------
    tick label            8.75      7.00    the floor. Two to four characters,
                                            read by POSITION along an axis and
                                            not as prose; the most numerous
                                            text on the page, so it is the one
                                            element that pays the full cost of
                                            any increase.
    in-plot annotation    9.00      7.20    sits ON the data field, so it must
                                            not outweigh the marks it explains
                                            -- but one step above the ticks,
                                            because in these figures the in-plot
                                            annotations are the DISCLOSURES (the
                                            year-1 null, the two significantly
                                            negative years, the gemma3:12b CI
                                            and p) and a disclosure set in the
                                            smallest type on the figure is a
                                            disclosure being hidden.
    legend text           9.25      7.40    decodes the marks. Full phrases,
                                            read once, sitting outside the data
                                            in its own box, so it can afford a
                                            step the annotations cannot.
    axis label            9.50      7.60    names the quantity. One per axis,
                                            and a reader who misreads it
                                            misreads every number on that axis.
    panel title           9.75      7.80    bold. The panel's claim in words;
                                            the second thing read.
    panel letter         10.50      8.40    bold. A DELIBERATE JUMP of 0.75
                                            rather than another 0.25 step: the
                                            five values above are a reading
                                            hierarchy and step evenly, but the
                                            letter is not read, it is FOUND --
                                            it is what a caption's "(b)" sends
                                            the eye to -- so it is set apart
                                            from the ramp instead of topping it.

THE FLOOR IS HARD. Nothing may print below 7.00 pt, so nothing here may be set
below 8.75 pt native. ``assert_print_floor()`` enforces it and every figure
script calls it. The floor is why the ramp climbs from 8.75 instead of
centring on it: there is no room underneath.

Times New Roman runs about 20% narrower than DejaVu Sans at the same point
size ("Anchor cell: each arm rejects for a different cause" is 3.53 in at 9 pt
DejaVu Sans Bold and 2.69 in at the same size in Times New Roman Bold), which
is what pays for the 0.25--0.75 pt increases above without widening anything.
"""

from __future__ import annotations

import os

import matplotlib
from matplotlib import font_manager
from matplotlib.ft2font import FT2Font

# =============================================================================
# The typeface
# =============================================================================
#: The one family. Changing this string is a decision about the whole paper.
FAMILY = "Times New Roman"

#: What ``findfont`` must return for each style actually drawn by the figures.
#: fig1 sets the "of these, the blocked ones" row label in italic and every title
#: and panel letter in bold, so all three files have to be present -- checking
#: only the regular face would let a machine with a partial Times install pass
#: the guard and then silently render the bold titles in DejaVu.
EXPECTED_FILES = {
    ("normal", "normal"): "times.ttf",
    ("normal", "bold"): "timesbd.ttf",
    ("italic", "normal"): "timesi.ttf",
}

#: Every character these three figures draw that is not plain ASCII. Sources:
#:   U+0394  from "$\\Delta$" -- fig2 panel A y label, fig2 panel C x label,
#:           fig3 y label
#:   U+2212  matplotlib writes MINUS SIGN, not HYPHEN-MINUS, into every negative
#:           tick label (``axes.unicode_minus`` defaults True and is not
#:           overridden). fig2 panel A ticks -50/-25 and fig3 ticks -20/-10.
#: The rest are checked because the captions, the axis labels and the callouts
#: are edited between rounds and any of them is one keystroke away from being
#: needed; a guard that only covers today's strings is a guard that lapses.
SPECIAL_GLYPHS = (
    "\u0394",  # GREEK CAPITAL LETTER DELTA
    "\u2212",  # MINUS SIGN
    "\u00d7",  # MULTIPLICATION SIGN
    "\u00b1",  # PLUS-MINUS SIGN
    "\u2265",  # GREATER-THAN OR EQUAL TO
    "\u2264",  # LESS-THAN OR EQUAL TO
    "\u2013",  # EN DASH
    "\u2014",  # EM DASH
    "\u2192",  # RIGHTWARDS ARROW
    "\u00b0",  # DEGREE SIGN
    "\u2019",  # RIGHT SINGLE QUOTATION MARK
    "\u03bc",  # GREEK SMALL LETTER MU
)

# =============================================================================
# The size hierarchy. Read the module docstring for the ordering argument.
# =============================================================================
#: The manuscript includes all three figures at 0.80\linewidth.
PRINT_SCALE = 0.80
#: Nothing may print smaller than this.
MIN_PRINT_FONT = 7.0

FS_TICK = 8.75          # -> 7.00 printed. The floor.
FS_ANNOT = 9.00         # -> 7.20 printed.
FS_LEGEND = 9.25        # -> 7.40 printed.
FS_AXIS_LABEL = 9.50    # -> 7.60 printed.
FS_PANEL_TITLE = 9.75   # -> 7.80 printed.
FS_PANEL_LETTER = 10.50  # -> 8.40 printed. Set apart from the ramp on purpose.

#: The whole hierarchy, smallest first, for the floor assert and for reporting.
HIERARCHY = (
    ("tick label", FS_TICK),
    ("in-plot annotation", FS_ANNOT),
    ("legend text", FS_LEGEND),
    ("axis label", FS_AXIS_LABEL),
    ("panel title", FS_PANEL_TITLE),
    ("panel letter", FS_PANEL_LETTER),
)

#: Backwards-compatible alias. The three figure scripts called the floor size
#: MIN_FONT before the hierarchy existed and their print-floor asserts read
#: `MIN_FONT * PRINT_SCALE >= MIN_PRINT_FONT`. The floor is now the smallest
#: value in the hierarchy rather than the only value, so the name points at it.
MIN_FONT = FS_TICK


# =============================================================================
# Guards
# =============================================================================
class FontGuardError(RuntimeError):
    """Raised when the resolved font is not the one that was asked for."""


def resolve(family: str = FAMILY, style: str = "normal", weight: str = "normal") -> str:
    """The font FILE matplotlib's renderer would actually use for ``family``.

    Deliberately the same ``findfont`` call the renderer makes, rather than a
    scan of the font directory: what matters is not whether Times is installed
    somewhere on the machine, it is what this matplotlib resolves the name to.
    """
    return font_manager.findfont(
        font_manager.FontProperties(family=family, style=style, weight=weight)
    )


def assert_font(family: str = FAMILY, expected: dict | None = None) -> dict:
    """Require ``family`` to resolve to the expected files. Raise if it does not.

    THE GUARD THIS MODULE EXISTS FOR. matplotlib answers a request for a family
    it cannot find by returning DejaVu Sans and logging a line nobody reads, so
    without this the figures would render in the wrong typeface and every other
    check in the pipeline would still pass.

    Returns {(style, weight): resolved path} on success, for reporting.
    """
    expected = EXPECTED_FILES if expected is None else expected
    got, wrong = {}, []
    for (style, weight), want in expected.items():
        path = resolve(family, style, weight)
        got[(style, weight)] = path
        if os.path.basename(path).lower() != want.lower():
            wrong.append((style, weight, want, path))
    if wrong:
        lines = [
            "FONT GUARD FAILED -- matplotlib did not resolve %r to the expected "
            "file(s). It does NOT raise on a missing family; it falls back to "
            "DejaVu Sans silently, so this is the only place the substitution "
            "becomes visible." % family
        ]
        for style, weight, want, path in wrong:
            lines.append("  %-8s %-8s expected %-14s got %s" % (style, weight, want, path))
        lines.append(
            "  Install Times New Roman, or change FAMILY/EXPECTED_FILES in "
            "_figstyle.py deliberately -- do not delete this assert."
        )
        raise FontGuardError("\n".join(lines))
    return got


def assert_glyphs(family: str = FAMILY, glyphs=SPECIAL_GLYPHS) -> list[tuple[str, int]]:
    """Require the resolved font to CARRY every special glyph, by cmap lookup.

    A TrueType font missing a glyph does not fail. Depending on the backend the
    character is drawn as a box, dropped, or quietly fetched from some other
    font -- and a PDF that substituted one glyph from DejaVu looks fine in a
    viewer while carrying a second embedded font nobody chose. ``get_char_index``
    returns 0 for "this font has no glyph for that code point", which is a fact
    about the file rather than about how it happened to render today.

    Returns [(char, glyph index)] on success.
    """
    path = resolve(family)
    face = FT2Font(path)
    out, missing = [], []
    for ch in glyphs:
        idx = face.get_char_index(ord(ch))
        out.append((ch, idx))
        if idx == 0:
            missing.append(ch)
    if missing:
        raise FontGuardError(
            "GLYPH GUARD FAILED -- %s (%s) has no glyph for: %s. These would "
            "render as boxes or be substituted from another font, and neither "
            "fails on its own."
            % (family, path, ", ".join("U+%04X" % ord(c) for c in missing))
        )
    return out


def assert_print_floor(scale: float = PRINT_SCALE, floor: float = MIN_PRINT_FONT) -> None:
    """Require every size in the hierarchy to clear the printed floor.

    Kept as an assert over the WHOLE hierarchy rather than over one size,
    because the hierarchy is the thing that can now drift: raising the ramp is
    safe, lowering any rung is not, and only the smallest rung would show it.
    """
    for name, pt in HIERARCHY:
        assert pt * scale >= floor, (
            "%s is %.2f pt, which prints at %.2f pt after the %.2f scale -- "
            "below the %.2f pt floor" % (name, pt, pt * scale, scale, floor)
        )


# =============================================================================
# Application
# =============================================================================
def rcparams() -> dict:
    """The shared rcParams. Same dict for all three figures."""
    return {
        "font.family": FAMILY,
        # Set alongside the family or the sans font comes back into the PDF to
        # carry "$\\Delta$" alone -- see the module docstring.
        "mathtext.fontset": "custom",
        "mathtext.rm": FAMILY,
        "mathtext.it": "%s:italic" % FAMILY,
        "mathtext.bf": "%s:bold" % FAMILY,
        "font.size": FS_TICK,
        "axes.labelsize": FS_AXIS_LABEL,
        "axes.titlesize": FS_PANEL_TITLE,
        "xtick.labelsize": FS_TICK,
        "ytick.labelsize": FS_TICK,
        "legend.fontsize": FS_LEGEND,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "figure.dpi": 300,
        "savefig.dpi": 300,
        # Embedded TrueType outlines. Type 3 is the class the venue blocks.
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }


def apply(**overrides) -> None:
    """Guard the font, then install the shared rcParams plus local overrides.

    The guards run FIRST and on every call. Checking once at import would let a
    script that re-set the family later render in something else, and these
    checks cost about a millisecond.
    """
    assert_font()
    assert_glyphs()
    assert_print_floor()
    rc = rcparams()
    rc.update(overrides)
    matplotlib.rcParams.update(rc)


def describe() -> str:
    """One block naming the typeface and the hierarchy, for a script's log."""
    paths = assert_font()
    lines = [
        "TYPEFACE: %s   (regular %s)" % (FAMILY, paths[("normal", "normal")]),
        "SIZE HIERARCHY (native pt -> printed pt at %.2f scale, floor %.2f):"
        % (PRINT_SCALE, MIN_PRINT_FONT),
    ]
    for name, pt in HIERARCHY:
        lines.append("    %-20s %5.2f -> %5.2f" % (name, pt, pt * PRINT_SCALE))
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe())
    print()
    ok = assert_glyphs()
    print("GLYPH GUARD: %d/%d present in %s" % (len(ok), len(SPECIAL_GLYPHS), FAMILY))
    for ch, idx in ok:
        print("    U+%04X  glyph index %-6d %s" % (ord(ch), idx, ch))
    assert_print_floor()
    print("\nPRINT FLOOR: every rung clears %.2f pt printed." % MIN_PRINT_FONT)
