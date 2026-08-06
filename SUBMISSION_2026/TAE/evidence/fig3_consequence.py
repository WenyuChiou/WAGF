"""Figure 3 -- "What it does to the reported statistic".

    python SUBMISSION_2026/TAE/evidence/fig3_consequence.py

Writes ``SUBMISSION_2026/TAE/figures/fig3_consequence.{png,pdf}`` (300 dpi PNG +
vector PDF) and the plotted values to ``fig3_consequence.csv`` beside them.


WHAT THIS FIGURE CLAIMS
-----------------------
For each of the five irrigation model cells it puts the CONDITIONAL governance
effect (increases among decisions the agent itself labelled HIGH water scarcity)
beside the UNCONDITIONAL one (increases over the design-fixed denominator of
78 agents x 42 years). Both are

    Delta = (no-validator value) MINUS (with-validators value),
    positive = the validators LOWERED the increase rate.

The claim is an estimand comparison, not a causal decomposition:

  (1) The conditional statistic differs from the unconditional one in every
      balanced cell. Their difference shows how the reported contrast changes
      when the denominator changes; it does not assign the difference to
      composition rather than behaviour.
  (2) On gemma3:12b the contrast changes from +11.44 conditional to +0.16
      unconditional. This fixed-denominator result is
      not distinguishable from zero in this cell, but it does not prove that
      governance left behavior unchanged.
  (3) The conditional statistic cannot itself tell (1) and (2) apart from a real
      behavioural effect, because its denominator is written by the process it is
      evaluating -- there is no independent channel on which to hold it fixed.

The figure does NOT claim that the unconditional rate is the "true" effect, that
the agent games the rule, or that the appraisal transmits the effect. The
world-state pattern described in Figure 2 is upstream of this figure and is not
converted here into a causal claim about behavior.

WHAT WOULD FALSIFY IT
---------------------
  * A balanced cell whose unconditional Delta EXCEEDS its conditional Delta, or
    whose conditional/unconditional 95% CIs coincide across all cells. Then
    conditioning would not be inflating anything and (1) fails.
  * gemma3:12b's unconditional Delta turning out significantly non-zero
    (its 95% CI excluding 0). Then (2)'s near-zero fixed-denominator reading
    must be withdrawn.
  * The ordering reversing under the EXECUTED action reading in a way that
    changes the sign of the argument. It does not -- but the reading is
    load-bearing and is therefore stated on the figure. Under the EXECUTED
    reading gemma3:12b's unconditional Delta is +27.82 (p=0.004), NOT +0.16,
    so claim (2) is specifically a LAST-PROPOSED-reading statement. This script
    computes and prints the EXECUTED reading as a cross-check so the restriction
    is visible rather than convenient.

BASIS
-----
  * Every number comes from ``_data.py``. This script owns no path, no glob and
    no definition.
  * The SEED is the inferential unit. A cell value is the MEAN OF THE PER-SEED
    rates; a Delta is the mean of the per-seed Deltas. Both are computed on the
    PAIRED seed set (seeds present in both arms).
  * Error bars are two-sided 95% CIs from a paired t on the per-seed Deltas,
    df = n-1. All five cells are balanced, so all five carry one.
  * ministral3:8b was drawn open and without a CI until 2026-08-03, when its
    no-validator seed 44 run landed and balanced the cell at 3 seeds against 3.
    It is now drawn and tested like the other four, on df = 2. The open-bar
    machinery below is kept, unused, for the next cell that needs it.
  * Action reading: LAST-PROPOSED (``yearly_decision``), which is the reading the
    published statistics use.
"""
from __future__ import annotations

import csv
import itertools
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
from matplotlib.collections import Collection                        # noqa: E402
from matplotlib.lines import Line2D                                  # noqa: E402
from matplotlib.patches import Patch                                 # noqa: E402
from matplotlib.text import Text                                     # noqa: E402
from matplotlib.transforms import Bbox                               # noqa: E402

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import _data as D                                                    # noqa: E402
import _figstyle as FS                                               # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.abspath(os.path.join(HERE, "..", "figures"))
STEM = "fig3_consequence"
# Typeface and every point size come from _figstyle.py, which fig1 and fig2 also
# read. They were three separate rcParams blocks before this pass; a shared
# decision kept in three copies is how the palette drifted last time.
PRINT_SCALE = FS.PRINT_SCALE
MIN_PRINT_FONT = FS.MIN_PRINT_FONT
MIN_FONT = FS.MIN_FONT

#: brief's verified list, LAST-PROPOSED reading, paired basis.
#: {model label: (n, cond gov, cond noval, cond delta, unc gov, unc noval, unc delta)}
BRIEF = {
    "gemma3:4b":     (5, 36.05, 59.07, +23.02, 40.90, 62.52, +21.62),
    "gemma3:12b":    (3,  5.45, 16.89, +11.44, 41.36, 41.52,  +0.16),
    "gemma4:e2b":    (5, 12.71, 31.65, +18.94, 22.80, 38.05, +15.25),
    "gemma4:e4b":    (5, 23.67, 41.08, +17.41, 36.36, 44.87,  +8.52),
    "ministral3:8b": (3,  3.25,  6.05,  +2.80, 54.35, 32.18, -22.17),
}
TOL = 0.005

# =============================================================================
# THE PAPER'S SHARED FIGURE PALETTE
# =============================================================================
# One palette across all four figures, so a reader who learns the code on one
# figure is not misled by the next. Okabe-Ito, colourblind-safe, and meaning is
# ALSO encoded by hatch, never by colour alone: conditional = solid fill,
# unconditional = diagonal hatch.
#
#   #0072B2 blue and #D55E00 vermillion are RESERVED, in every figure, for the
#   with-validators and no-validator ARMS. This figure plots a Delta BETWEEN the
#   arms rather than the arms themselves, so neither colour appears on it. That
#   is the whole reason for the change here: the two bars used to be arm blue
#   and an orange one step from arm vermillion, so on the paper's last figure
#   the two colours a reader had been taught meant "with validators" and "no
#   validator" silently came to mean "conditional" and "unconditional" -- two
#   statistics computed across BOTH arms.
#
#   #009E73 bluish green   the statistic CONDITIONED ON WHAT THE AGENT REPORTED
#                          (the HIGH-appraisal denominator). Same green carries
#                          the appraisal-conditioned rules in fig1 and the
#                          HIGH-appraisal prevalence Delta in fig2.
#   #CC79A7 reddish purple its WORLD-SIDE counterpart: the unconditional rate
#                          over the design-fixed 78 x 42 denominator, which the
#                          agent's report cannot move. Same purple carries the
#                          world-conditioned rules in fig1 and the year-1
#                          exogeneity marker in fig2.
#   greys                  structural: the highlight band, and the open face of
#                          the unbalanced cell's bars.
C_COND = "#009E73"      # bluish green    conditional (agent-written denominator)
C_UNC = "#CC79A7"       # reddish purple  unconditional (design-fixed denominator)
HL = "#F0F0F0"          # neutral grey    highlight band behind gemma3:12b

HIGHLIGHT = "gemma3:12b"
#: the anchor cell, named in the caption so the reader is not left to infer that
#: "collapses" describes every cell. On the anchor the conditioning removes only
#: about a pp and a half of the effect.
ANCHOR = "gemma3:4b"


# ---------------------------------------------------------------------------
def _stat_block(per_seed_gov: dict, per_seed_nov: dict, seeds) -> dict:
    """Cell means, Delta, and the paired t on the per-seed Deltas.

    Identical in form to ``table1_cells._stat_block`` so the two artefacts cannot
    drift apart. The Delta of the means equals the mean of the per-seed Deltas on
    a paired basis; both are computed and their agreement is asserted.
    """
    g = {s: per_seed_gov[s] for s in seeds}
    n = {s: per_seed_nov[s] for s in seeds}
    gm, nm = D.cell_mean(g), D.cell_mean(n)
    deltas = [D.DELTA(noval=n[s], gov=g[s]) for s in seeds]
    t = D.paired_t(deltas)
    if abs(D.DELTA(noval=nm, gov=gm) - t.mean) > 1e-9:
        raise D.DataError(
            "mean-of-deltas disagrees with delta-of-means; the basis is not paired"
        )
    return {
        "gov": gm, "noval": nm, "delta": t.mean,
        "ci_lo": t.ci_lo, "ci_hi": t.ci_hi, "t": t.t, "df": t.df,
        "p": D.t_two_sided_p(t.t, t.df),
        "per_seed_gov": g, "per_seed_noval": n,
        "per_seed_delta": {s: d for s, d in zip(seeds, deltas)},
    }


def collect() -> list[dict]:
    """One record per irrigation cell, both statistics, both action readings."""
    out = []
    for m in D.IRRIGATION_MODELS:
        bal = D.seed_sets(m.prefix)
        seeds = list(bal.paired_seeds)
        if not seeds:
            raise D.DataError(f"{m.label}: no paired seeds")

        cond = _stat_block(
            D.irrigation_per_seed("gov", m.prefix, D.conditional_rate),
            D.irrigation_per_seed("noval", m.prefix, D.conditional_rate),
            seeds,
        )
        unc = _stat_block(
            D.irrigation_per_seed("gov", m.prefix, D.unconditional_rate),
            D.irrigation_per_seed("noval", m.prefix, D.unconditional_rate),
            seeds,
        )
        # cross-check only; NOT plotted
        cond_x = _stat_block(
            D.irrigation_per_seed_executed("gov", m.prefix, "conditional"),
            D.irrigation_per_seed_executed("noval", m.prefix, "conditional"),
            seeds,
        )
        unc_x = _stat_block(
            D.irrigation_per_seed_executed("gov", m.prefix, "unconditional"),
            D.irrigation_per_seed_executed("noval", m.prefix, "unconditional"),
            seeds,
        )
        # the composition term the conditional statistic is silent about
        high = _stat_block(
            D.irrigation_per_seed("gov", m.prefix, D.high_share),
            D.irrigation_per_seed("noval", m.prefix, D.high_share),
            seeds,
        )
        out.append({
            "model": m.label,
            "seeds": seeds,
            "n": len(seeds),
            "balanced": bal.balanced,
            "excluded": D.excluded_from_paired(m.prefix),
            "gov_seeds": list(bal.gov_seeds),
            "noval_seeds": list(bal.noval_seeds),
            "cond": cond, "unc": unc,
            "cond_exec": cond_x, "unc_exec": unc_x,
            "high": high,
        })
    return out


# ---------------------------------------------------------------------------
def check(rows: list[dict]) -> list[str]:
    """Line-by-line agreement against the brief. Returns disagreements."""
    bad = []
    print("-" * 104)
    print("SELF-CHECK vs the brief's verified list (LAST-PROPOSED reading, paired basis)")
    print("-" * 104)
    print(f"{'model':14s} {'quantity':22s} {'computed':>10s} {'brief':>10s} "
          f"{'diff':>9s}  verdict")
    for r in rows:
        b = BRIEF[r["model"]]
        checks = (
            ("n (paired seeds)", float(r["n"]), float(b[0])),
            ("conditional gov", r["cond"]["gov"], b[1]),
            ("conditional noval", r["cond"]["noval"], b[2]),
            ("conditional Delta", r["cond"]["delta"], b[3]),
            ("unconditional gov", r["unc"]["gov"], b[4]),
            ("unconditional noval", r["unc"]["noval"], b[5]),
            ("unconditional Delta", r["unc"]["delta"], b[6]),
        )
        for name, got, exp in checks:
            diff = got - exp
            ok = abs(diff) <= TOL
            if not ok:
                bad.append(f"{r['model']} {name}: computed {got:.4f} vs brief {exp:.4f}")
            print(f"{r['model']:14s} {name:22s} {got:>10.4f} {exp:>10.4f} "
                  f"{diff:>+9.4f}  {'ok' if ok else '<== DISAGREES WITH BRIEF'}")
    print()
    return bad


def report(rows: list[dict]) -> None:
    print("-" * 104)
    print("PLOTTED VALUES -- Delta = no-validator MINUS with-validators "
          "(positive = validators lowered the rate)")
    print("-" * 104)
    print(f"{'model':14s} {'n':>2s} {'bal':>4s} "
          f"{'cond Delta':>11s} {'95% CI':>20s} {'p':>7s}   "
          f"{'unc Delta':>10s} {'95% CI':>20s} {'p':>7s}   {'gap':>7s}")
    for r in rows:
        c, u = r["cond"], r["unc"]
        ci_c = "-" if r["excluded"] else f"({c['ci_lo']:+6.2f},{c['ci_hi']:+6.2f})"
        ci_u = "-" if r["excluded"] else f"({u['ci_lo']:+6.2f},{u['ci_hi']:+6.2f})"
        p_c = "-" if r["excluded"] else f"{c['p']:.4f}"
        p_u = "-" if r["excluded"] else f"{u['p']:.4f}"
        mark = "  *EXCLUDED (unbalanced)" if r["excluded"] else ""
        print(f"{r['model']:14s} {r['n']:>2d} {'Y' if r['balanced'] else 'N':>4s} "
              f"{c['delta']:>+11.2f} {ci_c:>20s} {p_c:>7s}   "
              f"{u['delta']:>+10.2f} {ci_u:>20s} {p_u:>7s}   "
              f"{c['delta'] - u['delta']:>+7.2f}{mark}")
    print()
    print("  gap = conditional Delta MINUS unconditional Delta = the part of the reported")
    print("        gain carried by the conditioning variable's own distribution moving.")
    print()

    print("-" * 104)
    print("CONTEXT (computed, not plotted)")
    print("-" * 104)
    for r in rows:
        h = r["high"]
        print(f"  {r['model']:14s} HIGH-appraisal prevalence  "
              f"with-valid {h['gov']:6.2f}  no-valid {h['noval']:6.2f}  "
              f"Delta {h['delta']:+7.2f}   <- the denominator that moved")
    print()
    print("  EXECUTED action reading (maintain_demand substituted on rejected rows).")
    print("  Reported because claim (2) is a LAST-PROPOSED-reading statement:")
    for r in rows:
        c, u = r["cond_exec"], r["unc_exec"]
        p_u = "-" if r["excluded"] else f"p={u['p']:.4f}"
        print(f"  {r['model']:14s} cond Delta {c['delta']:+7.2f}   "
              f"unc Delta {u['delta']:+7.2f}  {p_u}")
    print()
    for r in rows:
        if r["excluded"]:
            print(f"  {r['model']}: UNBALANCED -- governed seeds {r['gov_seeds']}, "
                  f"no-validator seeds {r['noval_seeds']}. Paired basis {r['seeds']} "
                  f"(n={r['n']}). Excluded from every paired contrast per the brief; "
                  f"drawn open/hatched with no CI.")
    print()


# ---------------------------------------------------------------------------
def write_csv(rows: list[dict], path: str) -> None:
    cols = [
        "model", "statistic", "action_reading", "n_paired", "paired_seeds",
        "balanced", "excluded_from_paired", "plotted",
        "gov_mean_pct", "noval_mean_pct", "delta_pp",
        "ci_lo_pp", "ci_hi_pp", "t", "df", "p_two_sided",
        "per_seed_delta_pp", "brief_delta_pp", "diff_vs_brief_pp",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            b = BRIEF[r["model"]]
            for key, label, reading, plotted, briefval in (
                ("cond", "conditional_increase_rate", "LAST-PROPOSED", 1, b[3]),
                ("unc", "unconditional_increase_rate", "LAST-PROPOSED", 1, b[6]),
                ("cond_exec", "conditional_increase_rate", "EXECUTED", 0, None),
                ("unc_exec", "unconditional_increase_rate", "EXECUTED", 0, None),
                ("high", "high_appraisal_prevalence", "n/a", 0, None),
            ):
                s = r[key]
                w.writerow({
                    "model": r["model"],
                    "statistic": label,
                    "action_reading": reading,
                    "n_paired": r["n"],
                    "paired_seeds": ";".join(str(x) for x in r["seeds"]),
                    "balanced": int(r["balanced"]),
                    "excluded_from_paired": int(r["excluded"]),
                    "plotted": plotted,
                    "gov_mean_pct": f"{s['gov']:.6f}",
                    "noval_mean_pct": f"{s['noval']:.6f}",
                    "delta_pp": f"{s['delta']:.6f}",
                    "ci_lo_pp": "" if r["excluded"] else f"{s['ci_lo']:.6f}",
                    "ci_hi_pp": "" if r["excluded"] else f"{s['ci_hi']:.6f}",
                    "t": "" if r["excluded"] else f"{s['t']:.6f}",
                    "df": s["df"],
                    "p_two_sided": "" if r["excluded"] else f"{s['p']:.6f}",
                    "per_seed_delta_pp": ";".join(
                        f"{k}:{v:.6f}" for k, v in sorted(s["per_seed_delta"].items())),
                    "brief_delta_pp": "" if briefval is None else f"{briefval:.2f}",
                    "diff_vs_brief_pp": ("" if briefval is None
                                         else f"{s['delta'] - briefval:+.6f}"),
                })
    print(f"wrote {path}")


# =============================================================================
# LAYOUT SELF-CHECK  (identical to the one in fig2_mechanism.py, deliberately)
# =============================================================================
# This used to compare Text boxes against each other and nothing else, which is
# why three rounds of "overlap check: 0" coexisted with figures whose labels
# visibly touched things. A label does not have to land on another LABEL to be
# broken -- it can run off the canvas, or land on a bar, on a CI whisker, on an
# annotation arrow, on a legend frame, on an axis spine, or in a neighbouring
# panel. All of those are checked now, geometrically, against the artist's real
# PATH where a bounding box would be useless.
#
# THREE EXEMPTIONS, NAMED RATHER THAN LEFT IMPLICIT
#   1. a text's own furniture -- its bbox patch and its own leader arrow.
#   2. a legend's own frame and handles against that legend's own labels.
#   3. BACKGROUND FIELDS -- grid lines, and axvspan/axhspan bands at zorder
#      <= 0.5. These are the field a label sits ON, and the Nature Water
#      reference this layout follows deliberately sets white-boxed labels on
#      exactly such fields. Nothing is silently forgiven: field contacts are
#      counted and printed on their own line, each marked with whether the label
#      carries a box, so the headline count can never be reduced by widening
#      this exemption.
def _inked_box(t, rend):
    """The box actually put on paper.

    When a Text carries a visible bbox patch, THAT patch is the answer: it is
    drawn from the text's own layout plus padding, so it encloses the glyphs by
    construction, and it is the shape a reader sees. It is used INSTEAD of the
    glyph extent rather than unioned with it, because Text.get_window_extent is
    not trustworthy for a multi-line annotation -- measured on matplotlib 3.10.7,
    this figure's three-line callout reports a glyph box 49 px wider on the left
    than the box actually drawn around it, which is wider than the text itself
    and produced a phantom contact with a shaded band the label plainly clears.
    The error is one-sided (too wide, never too narrow), so the old union only
    ever invented conflicts; it could not hide one.
    """
    patch = t.get_bbox_patch()
    if patch is not None and patch.get_visible():
        return patch.get_window_extent(rend)
    return t.get_window_extent(rend)


def _display_paths(a):
    """[(path in display coords, treat-as-filled)] for one drawn artist.

    Patches are deliberately NOT returned. Path.intersects_bbox is not reliable
    on a FancyArrowPatch: measured on matplotlib 3.10.7, an arrow whose display
    extent is x 526-1001, y 503-513 reports intersects_bbox(226,155,428,189) as
    True under BOTH filled=True and filled=False. Every patch these figures draw
    is a rectangle or an arrow, and for those the window extent is either exact
    or conservative, so patches are tested on their window extent alone. Lines
    and collections DO need the path -- a long line's window extent is the whole
    panel, and a bbox test on it would flag every label in the panel.
    """
    try:
        if isinstance(a, Collection):
            tr = a.get_transform()
            return [(p.transformed(tr), True) for p in a.get_paths()]
        if isinstance(a, Line2D):
            return [(a.get_path().transformed(a.get_transform()), False)]
    except Exception:
        return []
    return []


def _artist_name(a):
    lab = a.get_label() or ""
    return lab if lab and not lab.startswith("_") else type(a).__name__


def _layout_conflicts(fig):
    """(hard conflicts, background-field contacts). Hard must be empty."""
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    ax_name = {id(ax): chr(ord("a") + i) for i, ax in enumerate(fig.axes)}

    legends = list(fig.legends) + [ax.get_legend() for ax in fig.axes
                                   if ax.get_legend() is not None]
    legend_owned, legend_of = set(), {}
    for lg in legends:
        for child in lg.findobj():
            legend_owned.add(id(child))
        for t in lg.findobj(match=Text):
            legend_of[id(t)] = id(lg)

    # Tick labels belonging to ticks OUTSIDE the axis view interval are built by
    # matplotlib but never drawn. They sit at nonsense positions -- typically off
    # the canvas and on top of each other -- so leaving them in the pool reports
    # conflicts that are not on the page. Excluded by tick LOCATION, which is
    # what decides whether they are drawn, not by where they happen to land.
    stale = set()
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis):
            lo, hi = sorted(axis.get_view_interval())
            for tick in list(axis.get_major_ticks()) + list(axis.get_minor_ticks()):
                loc = tick.get_loc()
                if loc is None or not (lo - 1e-9 <= loc <= hi + 1e-9):
                    for lab in (tick.label1, tick.label2):
                        if lab is not None:
                            stale.add(id(lab))

    texts = []
    for t in fig.findobj(match=Text):
        label = t.get_text()
        if not label or not label.strip() or not t.get_visible():
            continue
        if id(t) in stale:
            continue
        box = _inked_box(t, rend)
        # A Text matplotlib never laid out reports the unit box at the origin.
        # At 300 dpi the smallest glyph this figure sets is over 20 px tall, so
        # anything under 2 px is that sentinel and not something on the page.
        if box.width < 2 or box.height < 2:
            continue
        own = {id(t)}
        for extra in (t.get_bbox_patch(), getattr(t, "arrow_patch", None)):
            if extra is not None:
                own.add(id(extra))
        texts.append({"label": label.replace("\n", " / "), "box": box,
                      "obj": t, "own": own, "ax": getattr(t, "axes", None)})

    hard, field = [], []

    # (0) label running off the canvas. Not an overlap at all, which is exactly
    # why this class went unnoticed for three rounds.
    fbox = fig.bbox
    for t in texts:
        b = t["box"]
        if (b.x0 < fbox.x0 - 0.5 or b.y0 < fbox.y0 - 0.5
                or b.x1 > fbox.x1 + 0.5 or b.y1 > fbox.y1 + 0.5):
            hard.append(("off-canvas", t["label"], "clipped by the figure edge"))

    # (1) label on label
    for a, b in itertools.combinations(texts, 2):
        if a["box"].overlaps(b["box"]):
            hard.append(("text", a["label"], b["label"]))

    # (2) label on a legend frame it is not a member of
    for lg in legends:
        fr = lg.get_frame().get_window_extent(rend)
        for t in texts:
            if legend_of.get(id(t["obj"])) == id(lg):
                continue
            if t["box"].overlaps(fr):
                hard.append(("legend", t["label"], "legend frame"))

    # (3) label on an axis spine, and (4) label inside another panel
    for t in texts:
        for ax in fig.axes:
            if t["ax"] is not ax and t["box"].overlaps(ax.get_window_extent(rend)):
                hard.append(("panel", t["label"],
                             f"data rectangle of panel {ax_name[id(ax)]}"))
            for side, sp in ax.spines.items():
                if sp.get_visible() and t["box"].overlaps(sp.get_window_extent(rend)):
                    hard.append(("spine", t["label"],
                                 f"panel {ax_name[id(ax)]} {side} spine"))

    # (5) label on a drawn artist
    #
    # Grid lines are collected from the AXIS, not from ax.lines -- they are not
    # in ax.lines, and an earlier version of this function built a set of their
    # ids and then never put them in the pool, so "background-field contacts: 0"
    # meant "never looked" rather than "none". They are in the pool now and are
    # classified, not skipped. Tick MARKS are deliberately left out: they are
    # axis furniture drawn against the spine, the spine is already checked, and
    # including them only produces noise about a tick label sitting next to its
    # own tick.
    drawn = []
    for ax in fig.axes:
        for a in (list(ax.lines) + list(ax.patches) + list(ax.collections)
                  + list(ax.artists)):
            if not a.get_visible() or id(a) in legend_owned:
                continue
            drawn.append(("field" if a.get_zorder() <= 0.5 else "data", a, ax))
        for gl in list(ax.xaxis.get_gridlines()) + list(ax.yaxis.get_gridlines()):
            if gl.get_visible():
                drawn.append(("grid", gl, ax))
    for t in fig.findobj(match=Text):                 # annotation leader arrows
        arrow = getattr(t, "arrow_patch", None)
        if arrow is not None and arrow.get_visible():
            drawn.append(("data", arrow, getattr(t, "axes", None)))

    for kind, a, ax in drawn:
        try:
            hull = a.get_window_extent(rend)
        except Exception:
            continue
        # AND, not OR. A horizontal rule -- every axhline, axvline and grid line
        # in these figures -- has a window extent of exactly zero thickness on
        # one side, and an "or" here silently dropped all of them from the pool.
        # That is the second way this check was reporting a clean figure without
        # having looked: the zero line, the 895 ft floor rule, the year-1 rules
        # and all six grid lines were being skipped.
        if hull.width <= 0 and hull.height <= 0:
            continue
        paths = _display_paths(a)
        where = f"panel {ax_name[id(ax)]} " if ax is not None and id(ax) in ax_name else ""
        for t in texts:
            if id(a) in t["own"]:
                continue
            if not hull.overlaps(t["box"]):           # coarse, always correct
                continue
            if paths and not any(p.intersects_bbox(t["box"], filled=filled)
                                 for p, filled in paths):
                continue                              # fine, for lines and bands
            boxed = t["obj"].get_bbox_patch() is not None
            entry = (kind, t["label"], f"{where}{_artist_name(a)}"
                                       + ("  [label is boxed]" if boxed else ""))
            (field if kind in ("grid", "field") else hard).append(entry)

    return hard, field


def _assert_no_text_overlaps(fig) -> None:
    hard, field = _layout_conflicts(fig)
    print(f"TEXT OVERLAP CHECK: {len(hard)}   "
          "(label vs label / off-canvas / legend frame / spine / other panel / "
          "drawn artist)")
    for kind, a, b in hard:
        print(f"  !! [{kind}] {a}  <->  {b}")
    print(f"  background-field contacts (grid lines, shaded bands): {len(field)}"
          + ("" if field else "   none"))
    for kind, a, b in field:
        print(f"     -- [{kind}] {a}  on  {b}")
    if hard:
        raise RuntimeError("rendered labels collide")


# ---------------------------------------------------------------------------
def plot(rows: list[dict], stem: str) -> None:
    # Shared typeface + size hierarchy, plus the three settings local to this
    # figure. FS.apply runs the font and glyph guards before it sets anything,
    # so a machine without Times New Roman stops here rather than rendering this
    # figure in whatever matplotlib silently fell back to. (figure.dpi and
    # savefig.dpi are now in the shared block: the layout self-check measures the
    # figure the canvas actually holds, so the canvas has to be at the resolution
    # the artefact is written at, and that is true of all three figures.)
    FS.apply(**{
        # Local, and genuinely local: this figure's bars are edged in black at
        # 0.5, so its frame and ticks are set a shade heavier than the other
        # two to stay distinguishable from a bar edge.
        "axes.linewidth": 0.7,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
    })

    # SINGLE-column width. The venue's text block is 5.5 in wide
    # (neurips_2026.sty), and the manuscript includes this at 0.80\linewidth
    # (PRINT_SCALE). MIN_FONT is chosen to clear the 7 pt printed floor after
    # that scale. The axes rectangle is placed explicitly and the
    # file is saved WITHOUT bbox_inches="tight", so the emitted figure is exactly
    # 5.5 in wide -- an auto-expanded canvas, or a build at some other width that
    # LaTeX then rescales, would move every font away from the >=7 pt floor this
    # figure is laid out to hold at print size.
    FS.assert_print_floor()
    #
    # STRUCTURE, rebuilt 2026-08-03 against the Nature Water reference figure the
    # author named (paper/nature_water/figures/Fig2_irrigation_case.png):
    # ONE legend, in ONE box, at the top, outside the axes, spanning the figure.
    # It was previously a frameless three-row stack indented to x = 0.16, which
    # read as loose text floating over the top-left of the plot rather than as a
    # key. Height goes 3.30 -> 3.55 in to buy the box its own band plus clear air
    # between it and the top of the data.
    #
    # TITLE ADDED 2026-08-04. Figures 2 and 3 each carry a bold takeaway over
    # the axes ("The two runs are blocked for different reasons", "The gap is
    # not a steady drift", "Bigger where nothing was blocked"); this figure
    # carried none, so nothing printed on it said which way the two bars go.
    # Read-test: a one-sentence reading of this figure using only words that
    # appear ON it needed a comparative -- "smaller" -- that was nowhere on the
    # canvas. The title supplies it and reuses the key's own wording. It holds
    # in all five cells (23.02>21.62, 11.44>0.16, 18.94>15.27, 17.41>8.53,
    # 2.80>-21.83), which is the same statement section 6 makes in prose.
    # Height 3.55 -> 3.80 in buys the title its own band; the axes rectangle
    # below keeps its previous ABSOLUTE bottom (0.611 in) and height (2.425 in),
    # so no bar, tick or label moves and no font changes.
    fig = plt.figure(figsize=(5.5, 3.80))
    # bottom = 0.172 is set by the x axis stack, not chosen: two lines of tick
    # label (model name over seed count) plus the axis label plus both pads come
    # to 0.46 in, and at 0.150 the axis label was being cut by the canvas edge.
    #
    # LEFT 0.108 -> 0.150 on 2026-08-04. The y-axis label was
    # "$\\Delta$ increase rate (percentage points)" and is now "gap in how often
    # it asked for more water (pp)", which is the single most important label on
    # this figure and the one the author could not read. Set on one line it is
    # 2.40 in of type against 2.42 in of axis -- it would fit, by twenty
    # thousandths of an inch, and would sit on the page as one unbroken bar of
    # rotated text. It is set on two lines instead, which costs 0.11 in of left
    # margin and no height at all. The x-axis stack is untouched.
    # 0.172 * 3.55 = 0.611 in and 0.683 * 3.55 = 2.425 in; on the taller canvas
    # those same two inches are 0.1607 and 0.6381.
    ax = fig.add_axes([0.150, 0.1607, 0.835, 0.6381])
    ax.set_title("The denominator changes the apparent gain",
                 fontsize=FS.FS_PANEL_TITLE, fontweight="bold", pad=7.0)

    n = len(rows)
    xs = list(range(n))
    # A group is only ~0.97 in across on a 5.5 in canvas and a value label such
    # as "+23.02" is ~0.36 in at 7 pt, so the two bar CENTRES are pushed 0.44
    # units (~0.43 in) apart and the bars themselves narrowed to suit. The pair
    # still reads as a pair: the intra-pair gap stays smaller than the gap
    # between groups.
    w = 0.30
    off_c = 0.28

    # data extent of the bars and their intervals
    lo = min(min(r["cond"]["ci_lo"] if not r["excluded"] else r["cond"]["delta"],
                 r["unc"]["ci_lo"] if not r["excluded"] else r["unc"]["delta"])
             for r in rows)
    hi = max(max(r["cond"]["ci_hi"] if not r["excluded"] else r["cond"]["delta"],
                 r["unc"]["ci_hi"] if not r["excluded"] else r["unc"]["delta"])
             for r in rows)
    # A clear band below the data for the callouts. This was lo - 17.5, which
    # reserved 17.5 pp of empty axis -- a quarter of the panel -- for a two-line
    # note that then floated in the middle of it, and pushed every bar smaller to
    # pay for it. The note is now set as a compact boxed block near the cell it
    # describes, so the band only has to clear the block, not host it.
    band_top = lo - 3.0
    y_bot, y_top = lo - 8.0, hi + 4.0
    rng = y_top - y_bot
    pad = 0.018 * rng

    hl_idx = [i for i, r in enumerate(rows) if r["model"] == HIGHLIGHT]
    for i in hl_idx:
        ax.axvspan(i - 0.5, i + 0.5, color=HL, zorder=0, lw=0)

    ax.axhline(0.0, color="black", lw=0.8, zorder=2)

    for i, r in enumerate(rows):
        excl = r["excluded"]
        for off, key, colour, hatch in (
            (-off_c, "cond", C_COND, None),
            (+off_c, "unc", C_UNC, "///"),
        ):
            s = r[key]
            v = s["delta"]
            if excl:
                # visually distinct: open face, dashed edge, dense cross hatch
                ax.bar(i + off, v, w, facecolor="white", edgecolor=colour,
                       hatch="xxx", linewidth=1.0, linestyle="--", zorder=3)
            else:
                ax.bar(i + off, v, w, facecolor=colour, edgecolor="black",
                       hatch=hatch, linewidth=0.5, zorder=3)
                ax.errorbar(i + off, v,
                            yerr=[[v - s["ci_lo"]], [s["ci_hi"] - v]],
                            fmt="none", ecolor="black", elinewidth=0.8,
                            capsize=2.2, capthick=0.8, zorder=4)

    ax.set_xticks(xs)
    ax.set_xticklabels(
        [f"{r['model']}\n"
         + (f"{len(r['gov_seeds'])} vs {len(r['noval_seeds'])} seeds"
            if r["excluded"] else f"n = {r['n']} seeds")
         for r in rows]
    )
    ax.set_xlim(-0.62, n - 0.38)
    ax.set_ylim(y_bot, y_top)
    ax.set_yticks([-20, -10, 0, 10, 20, 30])
    ax.set_ylabel("gap in how often it asked\nfor more water (pp)")
    ax.set_xlabel("model", labelpad=4)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_position(("data", y_bot))
    ax.yaxis.grid(True, lw=0.4, color="#CCCCCC", zorder=0)
    ax.set_axisbelow(True)

    # --- the 12B callout: same numbers, set as a block beside its own cell ----
    # The CI and the p value are a DISCLOSURE -- they are what stops "+0.16 pp"
    # from being read as a precise zero rather than an interval that spans
    # -13.92 to +14.25 -- so neither may be dropped for room. What changed is
    # only where they sit. The block used to start at x = -0.50, two thirds of a
    # panel away from the cell, reached by a long thin leader that crossed most
    # of the figure's empty lower half. It now sits immediately right of the
    # shaded cell with a short leader, wrapped to three lines so it stays clear
    # of the shaded band on the left and of ministral3:8b's downward bar on the
    # right, and on a white ground with a hairline border -- the reference
    # figure's own device for a label that has to sit on a plotted field.
    if hl_idx:
        i = hl_idx[0]
        r = rows[i]
        # WORDING, 2026-08-04. The head line read "gemma3:12b composition cell:"
        # -- "composition cell" is the project's internal name for the cell where
        # the apparent contrast changes substantially with the denominator, and a reader who
        # does not already know that learns nothing from it. The shading and the
        # caption both identify the cell, so the head line only has to point,
        # and "95% CI" is spelled out here for the same reason it is spelled out
        # in the key. The interval and the p value themselves are a DISCLOSURE
        # and neither may be dropped for room: they are what stops "+0.16 pp"
        # being read as a precise zero rather than an interval spanning
        # -13.92 to +14.25.
        ax.annotate(
            "gemma3:12b, the shaded cell:\n"
            f"95% confidence interval\n"
            f"({r['unc']['ci_lo']:+.2f}, {r['unc']['ci_hi']:+.2f}), "
            f"p = {r['unc']['p']:.2f}",
            xy=(i + off_c, r["unc"]["ci_lo"]),
            # Anchored to the interval it points at rather than to a hand-picked
            # spot on the canvas. The 0.90 is measured, not guessed: the rounded
            # box's left edge lands 0.30 of a cell left of the text anchor, so
            # 0.90 puts it at 1.60 against a shaded band that ends at 1.50, and
            # its right edge at 3.98 against ministral3:8b's downward bar at
            # 4.13. 2.5 pp below the lower CI bound clears the whisker cap.
            xytext=(i + 0.90, r["unc"]["ci_lo"] - 2.5),
            fontsize=FS.FS_ANNOT, ha="left", va="top", zorder=6,
            linespacing=1.20,
            bbox=dict(boxstyle="round,pad=0.34", facecolor="white",
                      edgecolor="0.55", linewidth=0.6),
            arrowprops=dict(arrowstyle="->", lw=0.7, color="0.25",
                            shrinkA=2, shrinkB=2),
        )

    # --- the excluded-cell callout, same band, right-aligned --------------
    # "unbalanced / shown open / no CI". Every cell in this corpus is balanced
    # -- ministral3:8b's no-validator seed 44 landed on 2026-08-03 and closed
    # the last one, and ``D.IRRIGATION_UNBALANCED_PREFIXES`` is empty -- so this
    # loop has not put a character on the page since that day. It stays because
    # it is the disclosure the NEXT unbalanced cell needs, and it is guarded by
    # the same predicate that decides whether the open bar is drawn at all, so
    # the words and the treatment they explain cannot appear apart. What is NOT
    # allowed is for the string to reach the page while every cell is balanced;
    # that is what ``if not r["excluded"]: continue`` prevents.
    for i, r in enumerate(rows):
        if not r["excluded"]:
            continue
        ax.text(i, band_top, "seeds do not match\nshown open\nno interval",
                fontsize=FS.FS_ANNOT, ha="center", va="top", color="0.15")

    # THE TWO MOST IMPORTANT LABELS IN THE PAPER, and until 2026-08-04 they were
    # written as "conditional (HIGH-appraisal denominator)" and "unconditional
    # (all decisions)" -- the names of the two estimands, which is exactly the
    # knowledge a reader needs the figure to supply. They now state the
    # denominator itself, in words, which is the whole content of the
    # distinction: one rate is taken out of the decisions the agent labelled
    # high scarcity, the other out of every decision it made. The caption is
    # where these are tied back to the words the body uses.
    handles = [
        Patch(facecolor=C_COND, edgecolor="black", lw=0.5,
              label="out of decisions where it said scarcity was high"),
        Patch(facecolor=C_UNC, edgecolor="black", lw=0.5, hatch="///",
              label="out of every decision"),
    ]
    # The open-bar key is offered only when an open bar is actually drawn.
    # A legend entry explaining a treatment no cell receives is the same
    # defect as an unexplained treatment, pointing the other way. Every cell in
    # this corpus is balanced, so this entry is not currently on the figure.
    if any(r["excluded"] for r in rows):
        handles.append(
            Patch(facecolor="white", edgecolor="grey", lw=1.0, hatch="xxx",
                  linestyle="--", label="seeds do not match, no interval"))
    handles.append(
        Line2D([0], [0], color="black", lw=0.8, label="95% confidence interval"))
    # ONE box, at the top, outside the axes, centred on the figure. Column-major
    # fill with ncol=2 puts the two statistics in the left column, one above the
    # other so their labels line up and can be compared, and the interval key on
    # its own at the right. The frame is what makes it read as a key rather than
    # as stray text over the plot -- that, and being outside the axes entirely,
    # is the whole difference from the version the author rejected.
    leg = fig.legend(handles=handles, loc="upper center",
                     bbox_to_anchor=(0.5, 0.995), ncol=2, frameon=True,
                     handlelength=1.6, borderaxespad=0.0, borderpad=0.55,
                     columnspacing=1.4, labelspacing=0.34, handletextpad=0.5)
    leg.get_frame().set_linewidth(0.6)
    leg.get_frame().set_edgecolor("0.55")
    leg.get_frame().set_facecolor("white")

    png = os.path.join(FIGDIR, stem + ".png")
    pdf = os.path.join(FIGDIR, stem + ".pdf")
    _assert_no_text_overlaps(fig)
    fig.savefig(png, dpi=300)
    fig.savefig(pdf)
    plt.close(fig)
    for p in (png, pdf):
        print(f"wrote {p}  ({os.path.getsize(p):,} bytes)")


def caption(rows: list[dict]) -> str:
    """Build the caption FROM THE COMPUTED VALUES.

    Deliberately not a hand-written string: every number a caption states is a
    number a reviewer will check, and a stale literal here is exactly the class
    of error this project has already published once.
    """
    by = {r["model"]: r for r in rows}
    h = by[HIGHLIGHT]
    ex = [r for r in rows if r["excluded"]]
    gaps = [r["cond"]["delta"] - r["unc"]["delta"] for r in rows if not r["excluded"]]
    ex_txt = ""
    for r in ex:
        ex_txt = (
            f" {r['model']} does not hold the same seeds in both runs "
            f"({len(r['gov_seeds'])} with-validator against {len(r['noval_seeds'])} "
            f"no-validator) and is therefore excluded from every paired statistic; it is "
            f"drawn unfilled, without a confidence interval, rather than dropped."
        )
    a = by[ANCHOR]
    a_gap = a["cond"]["delta"] - a["unc"]["delta"]
    return (
        "Figure 4. The denominator changes the apparent gain. On one model "
        f"the conditional contrast nearly disappears after the denominator change. For each of the {len(rows)} irrigation model cells the governance "
        "effect on the increase rate is shown twice: as the published conditional statistic "
        "(increases among decisions the agent itself labelled HIGH water scarcity, solid) and as "
        "the unconditional statistic over the design-fixed denominator of 78 agents x 42 years "
        "(hatched). The two keys state those denominators rather than name them: the solid bars "
        "are the CONDITIONAL rate, that is, the share computed out of decisions where the agent "
        "said scarcity was high, and the hatched bars the UNCONDITIONAL rate, the share out of "
        "every decision it made; the y axis is the Delta in that increase rate, in percentage "
        "points. Delta = (no-validator) MINUS (with-validators), so a positive value means the "
        "validators lowered the increase rate; error bars are two-sided 95% confidence intervals "
        "from a paired t-test on the per-seed deltas (df = n-1), the seed being the inferential "
        "unit. The action reading is LAST-PROPOSED (yearly_decision), the reading the published "
        "statistics use. The denominator changes the contrast in every balanced cell: the "
        "unconditional contrast is smaller in four cells, nearly zero on gemma3:12b, and reverses "
        "sign on ministral3:8b. The gap between the two estimates on the anchor cell "
        f"{ANCHOR} is only {a_gap:+.2f} pp ({a['cond']['delta']:+.2f} conditional against "
        f"{a['unc']['delta']:+.2f} unconditional), so the reported gain there survives the "
        "denominator change almost intact. The gap exists because the prevalence of a HIGH appraisal "
        f"is itself far lower under governance. On {HIGHLIGHT} (shaded), the conditional contrast "
        "changes sharply under the alternative estimand, consistent with a large "
        "composition contribution but not a causal decomposition: "
        f"{h['cond']['delta']:+.2f} pp conditional (95% CI {h['cond']['ci_lo']:+.2f}, "
        f"{h['cond']['ci_hi']:+.2f}; p = {h['cond']['p']:.3f}) becomes "
        f"{h['unc']['delta']:+.2f} pp unconditional (95% CI {h['unc']['ci_lo']:+.2f}, "
        f"{h['unc']['ci_hi']:+.2f}; p = {h['unc']['p']:.3f}). The unconditional rate is a "
        "DIFFERENT ESTIMAND, not a corrected version of the conditional one: it answers "
        "\"how often did the agent ask for more water, out of every decision it made\", while the "
        "conditional rate answers \"how often did it ask for more water when it said scarcity was "
        "high\". It is shown here as a decomposition term -- the difference between the two "
        "shows how the reported contrast changes with the conditioning variable's own distribution -- "
        "and it is not offered as a corrected effect size for the conformance "
        "gain. No number in this figure is the \"true\" governance effect." + ex_txt
    )


def main() -> int:
    os.makedirs(FIGDIR, exist_ok=True)
    print("=" * 104)
    print("FIGURE 4 -- what the denominator does to the reported statistic")
    print("=" * 104)
    print(f"SIGN CONVENTION : {D.DELTA_LABEL}")
    print("BASIS           : paired seed set; cell value = mean of per-seed rates; "
          "seed is the inferential unit")
    print("ACTION READING  : LAST-PROPOSED (yearly_decision) -- the published reading")
    print()

    rows = collect()
    bad = check(rows)
    report(rows)

    write_csv(rows, os.path.join(FIGDIR, STEM + ".csv"))
    plot(rows, STEM)

    print()
    print("-" * 104)
    print("SUGGESTED CAPTION")
    print("-" * 104)
    print(caption(rows))
    print()

    if bad:
        print("!" * 104)
        print("DISAGREEMENT WITH THE BRIEF -- reported, NOT tuned away:")
        for b in bad:
            print("  !!", b)
        print("!" * 104)
        return 1
    print("AGREEMENT: every plotted value matches the brief's verified list "
          f"to within {TOL} pp.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
