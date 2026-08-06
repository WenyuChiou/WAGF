"""FIGURE 2 -- "What the decomposition can and cannot show". The core figure of the paper.

WHAT THIS FIGURE CLAIMS
-----------------------
The governed and no-validator arms differ enormously in the prevalence of the
HIGH water-scarcity appraisal that the published conformance statistic conditions
on (anchor cell gemma3:4b: 37.08 % vs 82.80 %, Delta +45.73 pp). This figure
shows that the two arms' recorded worlds diverge after enforcement and that a
world-state reweighting leaves a small residual on the anchor cell. It does not
identify a within-world reporting effect or establish that the agent reports the
world accurately.

Three independent pieces of evidence, all computed here from the run files:

  (A) PER-YEAR Delta in HIGH-appraisal prevalence, years 1..42, 95 % CI across the
      five paired seeds. At YEAR 1, the equality check finds identical values for
      every PRE-DECISION state column in each paired agent-year
      (e0_year1_exogeneity.py, in this folder: year-1 exact-equality 1.0; first
      divergence at year 2) and the Delta is
      NULL. The shift does not exist before the worlds separate. Note that
      utilisation_pct and below_minimum_utilisation are NOT pre-decision -- they
      are functions of the demand the year's skill has already set -- and e0
      excludes them from that claim with a control on the data.

      WHAT HAPPENS AFTER YEAR 1 IS NOT A CLEAN RAMP, AND THE PANEL SAYS SO.
      The Delta is null at year 1, OSCILLATES over years 2-11, and is
      established from year 12 onward. Over years 2-11 four years are
      significantly positive, three are not significant, year 3 is degenerate
      (both arms 100 % HIGH, zero variance), and TWO ARE SIGNIFICANTLY
      NEGATIVE -- year 4 at -18.46 pp (p = 0.0040) and year 7 at -6.41 pp
      (p = 0.0008, which the caption prints as 0.001 at 3 dp).
      Over years 12-42, 29 of 31 are significantly positive, none
      is significantly negative, and the two exceptions (years 37 and 39) are
      merely not significant. Those two negative years are marked on the panel
      and named in the caption, and both the marking and the title's year
      boundary are COMPUTED from the per-year table rather than written in, so
      neither can drift away from the data. A panel titled "moves only after"
      that left them unremarked would be an overclaim a reviewer catches.

  (B) THE RESERVOIR over the same years. Lake Mead elevation per arm. The two
      arms start on the same value at year 1 and separate from year 2, and the
      appraisal Delta in panel A tracks that separation. The no-validator arm
      reaches the floor of the model's elevation-storage curve (895 ft, 2.0 MAF,
      irrigation_env.py:118-124) in every seed, spends 6-12 of the 42 years on
      it, and ENDS the run on it in every seed; the governed arm never goes
      below 964 ft. It does NOT stay on the floor once it first reaches it --
      it recovers and returns, which ``main()`` prints per seed -- so any
      wording of the form "and stays there" is false and has been removed.

  (C) THE NEVER-RETRIED STRATUM. On decisions where retry_count == 0 no validator
      ever spoke to the agent -- there was no rejection message, no retry prompt,
      nothing to revise a premise in response to. The Delta on that stratum is
      LARGER than on all decisions, in 5 of 5 irrigation cells. Because the two
      arms enter this stratum through different filters, this is a sensitivity
      comparison rather than a test that rules out selection.

WHAT WOULD FALSIFY IT
---------------------
  * A year-1 Delta whose 95 % CI excludes zero. The worlds are identical there, so
    a real shift at year 1 would have to come from the agent's response to the
    governance apparatus itself, not from the world. (Measured: +3.33 pp,
    CI -3.75 to +10.42, p = 0.26.)
  * A per-year Delta that opens up BEFORE the reservoir separates, or that stays
    flat while the reservoir gap grows.
  * A never-retried Delta SMALLER than the all-decisions Delta would be a useful
    sensitivity result for the premise-revision explanation. (Measured: larger in
    5/5 cells, but the two arms are selected by different filters.)
  * Lake Mead levels that do not differ between arms, which would remove the
    world-change channel and leave only agent-side explanations.

WHAT THIS FIGURE DOES *NOT* CLAIM
---------------------------------
  * It does not claim the appraisal MEDIATES the governance effect (transmission
    is not tested here; see DECISION.md section 6).
  * It does not claim premise revision is zero. The corpus bounds the residual, it
    does not eliminate it -- the first-attempt appraisal of a retried-and-approved
    decision is not on disk (DECISION.md section 5).
  * It does not relate enforcement PRESSURE to the shift. That relationship is not
    identified in this corpus (DECISION.md section 9, the killed scatter). The
    per-year Spearman correlations printed to stdout are descriptive only and are
    NOT drawn on the figure, because the 42 years are strongly autocorrelated.

LAYOUT DECISION -- stacked panels, not a twin axis
--------------------------------------------------
Panels A and B share an x-axis rather than sharing a frame with two y-scales.
A twin axis puts percentage points and feet on the same gridlines, and the reader
recovers an apparent correlation whose strength is an artefact of whatever
scaling was chosen. The argument here is temporal co-movement -- the shift is
absent when the worlds are identical and appears as they separate -- and a shared
x-axis carries that completely without asserting a common scale.

SIGN CONVENTION (panels A and C)
    Delta = (no-validator value) MINUS (with-validators value).
    POSITIVE means the validators LOWERED it.
Panel B plots levels per arm, not a delta, and is labelled accordingly.

Usage:  python SUBMISSION_2026/TAE/evidence/fig2_mechanism.py
Writes: SUBMISSION_2026/TAE/figures/fig2_mechanism.{png,pdf}
        SUBMISSION_2026/TAE/figures/fig2_mechanism.csv   (every plotted value)
Exit 1 if any cross-check against the brief's verified numbers fails.
"""
from __future__ import annotations

import csv
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _data as D  # noqa: E402  (path set above)
import _figstyle as FS  # noqa: E402  (path set above)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import Collection  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.text import Text  # noqa: E402
from matplotlib.transforms import Bbox  # noqa: E402

FIGDIR = os.path.join(D.HERE, "..", "figures")
STEM = "fig2_mechanism"
# Typeface and every point size come from _figstyle.py, which fig1 and fig3 also
# read. They were three separate rcParams blocks before this pass; a shared
# decision kept in three copies is how the palette drifted last time.
PRINT_SCALE = FS.PRINT_SCALE
MIN_PRINT_FONT = FS.MIN_PRINT_FONT
MIN_FONT = FS.MIN_FONT

YEARS = list(range(1, 43))

# =============================================================================
# THE PAPER'S SHARED FIGURE PALETTE
# =============================================================================
# One palette across all four figures, so a reader who learns the code on one
# figure is not misled by the next. Okabe-Ito throughout, colourblind-safe, and
# meaning is ALSO carried by line style, marker and hatch, never by colour alone.
#
#   #0072B2 blue and #D55E00 vermillion are RESERVED, in every figure, for the
#   with-validators and no-validator ARMS -- panel B here, and the two blocks of
#   the fig0 schematic. Nothing else is drawn in either, or in a shade of either.
#   That is what changed in this file: the all-decisions bars in panel C used to
#   be #56B4E9, a lighter blue, so the panel's most prominent non-arm category
#   was drawn in a shade of the arm colour panel B had just taught; and the
#   significantly-negative-year markers used #E69F00, one step from the arm
#   vermillion. Both now sit outside the arm hues entirely.
#
#   #009E73 bluish green   the Delta in HIGH-appraisal prevalence -- a quantity
#                          conditioned on what the agent reported. Panel C draws
#                          the SAME quantity on two strata, so the two bars are
#                          one hue at two lightnesses (same quantity, different
#                          subset) rather than two hues (which the palette
#                          reserves for self-report-side vs world-side pairs).
#                          fig1 and fig3 use this green for the same idea.
#   #CC79A7 reddish purple the WORLD-SIDE / exogenous reference. Here it marks
#                          year 1, the one year whose worlds are provably
#                          identical, in both panel A and panel B. fig1 uses it
#                          for the world-conditioned rules, fig3 for the
#                          unconditional (design-fixed denominator) statistic.
#   black + greys          structural: the computed Delta line, its CI band and
#                          bars, and the flag on the two years that run the
#                          other way -- a flag, not a data category, so it is
#                          deliberately achromatic and set apart by shape.
C_GOV = "#0072B2"     # blue            with-validators arm (RESERVED)
C_NOVAL = "#D55E00"   # vermillion      no-validator arm    (RESERVED)
C_DELTA = "#000000"   # black           delta line
C_BAND = "#BBBBBB"    # grey            CI band
C_NR = "#009E73"      # bluish green    never-retried bars
C_ALL = "#7FCEB9"     # light green     all-decisions bars (same hue, lighter)
C_MARK = "#CC79A7"    # reddish purple  year-1 exogeneity marker
C_NEG = "#333333"     # near-black      significantly NEGATIVE years (a flag)

#: two-sided level at which a per-year Delta is called significant. Used ONLY to
#: classify years for the panel-A title, annotation and caption. Nothing is
#: selected, dropped or weighted on it.
ALPHA = 0.05
#: the window the figure describes as "established". It is a DECLARED window,
#: not a fitted change point; every count reported inside it is computed.
ESTABLISHED_FROM_YEAR = 12

# Model elevation floor: lowest point of the USBR elevation-storage table in
# examples/irrigation_abm/irrigation_env.py:118-124 (2.0 MAF <-> 895.0 ft).
MEAD_FLOOR_FT = 895.0

# Shared typeface + size hierarchy, plus the one setting local to this figure.
# FS.apply runs the font and glyph guards before it sets anything, so a machine
# without Times New Roman stops here rather than rendering this figure in
# whatever matplotlib silently fell back to.
FS.apply(**{
    # Local, and genuinely local: this is the only one of the three figures
    # whose primary marks are plotted LINES rather than bars.
    "lines.linewidth": 1.1,
})


# =============================================================================
# Computation. Every number below comes from reading a run file via _data.py.
# =============================================================================
def year_rows(rows, year):
    return [r for r in rows if str(r.get("year", "")).strip() == str(year)]


def panel_a():
    """Per-year Delta in HIGH-appraisal prevalence, anchor cell, paired seeds."""
    seeds = D.paired_seeds("")
    sim = {(arm, s): D.load_sim(D.irrigation_run(arm, "", s))
           for arm in D.ARMS for s in seeds}
    out = []
    for y in YEARS:
        deltas, g_rates, n_rates = [], [], []
        for s in seeds:
            g = D.high_share(year_rows(sim[("gov", s)], y))
            n = D.high_share(year_rows(sim[("noval", s)], y))
            g_rates.append(g)
            n_rates.append(n)
            deltas.append(D.DELTA(noval=n, gov=g))
        t = D.paired_t(deltas)
        out.append({
            "year": y,
            "gov_high_pct": D.mean(g_rates),
            "noval_high_pct": D.mean(n_rates),
            "delta_pp": t.mean,
            "ci_lo_pp": t.ci_lo,
            "ci_hi_pp": t.ci_hi,
            "t": t.t,
            "df": t.df,
            "p": D.t_two_sided_p(t.t, t.df),
            "n_seeds": len(seeds),
        })
    return out, seeds


def panel_b():
    """Lake Mead elevation per year per arm, anchor cell, paired seeds.

    lake_mead_level is a GLOBAL state variable repeated on every agent row; this
    asserts it is single-valued within each (arm, seed, year) rather than
    averaging over agents and hoping.
    """
    seeds = D.paired_seeds("")
    per = {arm: {s: {} for s in seeds} for arm in D.ARMS}
    for arm in D.ARMS:
        for s in seeds:
            for r in D.load_sim(D.irrigation_run(arm, "", s)):
                y = int(r["year"])
                v = float(r["lake_mead_level"])
                prev = per[arm][s].setdefault(y, v)
                if abs(prev - v) > 1e-9:
                    raise D.DataError(
                        f"lake_mead_level is not single-valued in arm={arm} "
                        f"seed={s} year={y}: {prev} vs {v}"
                    )
    out = []
    for y in YEARS:
        g = [per["gov"][s][y] for s in seeds]
        n = [per["noval"][s][y] for s in seeds]
        out.append({
            "year": y,
            "gov_mead_ft": D.mean(g),
            "gov_mead_min_ft": min(g),
            "gov_mead_max_ft": max(g),
            "noval_mead_ft": D.mean(n),
            "noval_mead_min_ft": min(n),
            "noval_mead_max_ft": max(n),
            # NOTE the sign here is GOV MINUS NOVAL: this is a level gap in feet,
            # not the project Delta. Named explicitly so it cannot be confused.
            "gov_minus_noval_ft": D.mean(g) - D.mean(n),
            "n_seeds": len(seeds),
        })
    # Floor statistics, computed rather than eyeballed. NOTE the no-validator arm
    # does NOT stay on the floor once it reaches it -- it recovers and returns.
    # Saying "and stays there" would be false; the true statement is that it
    # reaches the floor, spends a large share of the run on it, and ENDS on it.
    floor = {"first": {}, "n_years": {}, "ends_on_floor": {}, "min_ft": {}}
    for arm in D.ARMS:
        for s in seeds:
            at = [y for y in YEARS if per[arm][s][y] <= MEAD_FLOOR_FT + 1e-3]
            floor["first"][(arm, s)] = at[0] if at else None
            floor["n_years"][(arm, s)] = len(at)
            floor["ends_on_floor"][(arm, s)] = YEARS[-1] in at
            floor["min_ft"][(arm, s)] = min(per[arm][s].values())
    return out, per, floor


def panel_c():
    """Never-retried vs all-decisions Delta in HIGH-appraisal prevalence.

    retry_count == 0 means the governance loop never returned a rejection to the
    agent for that decision. The audit csv is the only source of retry_count, so
    both strata are computed on AUDIT rows (construct_WSA_LABEL). VERIFIED that
    this does not change the appraisal definition: sim.wsa_label and
    audit.construct_WSA_LABEL differ on 108 / 32,760 anchor rows and every one of
    those is the unparsed encoding ("N/A" in sim vs "" in audit); neither is HIGH,
    and high_share agrees to 4 dp on both arms.
    """
    rows = []
    seed_rates = {arm: {"all": [], "nr": []} for arm in D.ARMS}
    for m in D.IRRIGATION_MODELS:
        ps = D.paired_seeds(m.prefix)
        cell = {arm: {"all": {}, "nr": {}} for arm in D.ARMS}
        nr_share = {}
        for arm in D.ARMS:
            for s in ps:
                aud = D.load_audit(D.irrigation_run(arm, m.prefix, s))
                nr = [r for r in aud if str(r.get("retry_count", "")).strip() == "0"]
                if not nr:
                    raise D.DataError(
                        f"no retry_count==0 rows for {m.label} {arm} seed {s}")
                cell[arm]["all"][s] = D.high_share(aud)
                cell[arm]["nr"][s] = D.high_share(nr)
                seed_rates[arm]["all"].append(cell[arm]["all"][s])
                seed_rates[arm]["nr"].append(cell[arm]["nr"][s])
                nr_share.setdefault(arm, []).append(100.0 * len(nr) / len(aud))
        rec = {
            "cell": m.label,
            "n_paired_seeds": len(ps),
            "excluded_from_paired": D.excluded_from_paired(m.prefix),
        }
        for stratum in ("all", "nr"):
            g = D.cell_mean(cell["gov"][stratum])
            n = D.cell_mean(cell["noval"][stratum])
            rec[f"{stratum}_gov_high_pct"] = g
            rec[f"{stratum}_noval_high_pct"] = n
            rec[f"{stratum}_delta_pp"] = D.DELTA(noval=n, gov=g)
            per_seed_d = [D.DELTA(noval=cell["noval"][stratum][s],
                                  gov=cell["gov"][stratum][s]) for s in ps]
            t = D.paired_t(per_seed_d)
            rec[f"{stratum}_ci_lo_pp"] = t.ci_lo
            rec[f"{stratum}_ci_hi_pp"] = t.ci_hi
            rec[f"{stratum}_df"] = t.df
        rec["nr_share_gov_pct"] = D.mean(nr_share["gov"])
        rec["nr_share_noval_pct"] = D.mean(nr_share["noval"])
        rec["nr_larger"] = rec["nr_delta_pp"] > rec["all_delta_pp"]
        rows.append(rec)

    # Pooled = mean of ALL per-(model, seed) rates, the basis that reproduces the
    # brief's +48.21. Reported as a point estimate with NO interval: the 21
    # (model, seed) units are not independent across models, so a t interval over
    # them would understate the true uncertainty.
    pooled = {"cell": "pooled", "n_paired_seeds": len(seed_rates["gov"]["all"]),
              "excluded_from_paired": False}
    for stratum in ("all", "nr"):
        g = D.mean(seed_rates["gov"][stratum])
        n = D.mean(seed_rates["noval"][stratum])
        pooled[f"{stratum}_gov_high_pct"] = g
        pooled[f"{stratum}_noval_high_pct"] = n
        pooled[f"{stratum}_delta_pp"] = D.DELTA(noval=n, gov=g)
        pooled[f"{stratum}_ci_lo_pp"] = float("nan")
        pooled[f"{stratum}_ci_hi_pp"] = float("nan")
        pooled[f"{stratum}_df"] = -1
    pooled["nr_share_gov_pct"] = float("nan")
    pooled["nr_share_noval_pct"] = float("nan")
    pooled["nr_larger"] = pooled["nr_delta_pp"] > pooled["all_delta_pp"]
    return rows, pooled


def classify_years(A):
    """Sort the per-year table into sign/significance classes.

    Exists so that panel A's title, its annotation and the caption all state the
    SAME structure, and state it from the data rather than from a sentence
    somebody wrote once. ``sig_neg`` in particular must never be silently
    dropped: a panel implying a one-directional shift while two years run
    significantly the other way is exactly the overclaim this function prevents.

    A year is DEGENERATE when its paired t is undefined because every seed gives
    the identical Delta (year 3: both arms 100% HIGH in all five seeds, so the
    Delta is exactly 0 with zero variance and p is nan). It is counted on its
    own rather than folded into "not significant".
    """
    def cls(r):
        p = r["p"]
        if p != p:                      # nan -> zero variance across seeds
            return "degenerate"
        if p >= ALPHA:
            return "ns"
        return "sig_pos" if r["delta_pp"] > 0 else "sig_neg"

    out = {"per_year": {r["year"]: cls(r) for r in A}}
    for name, lo, hi in (("early", 2, ESTABLISHED_FROM_YEAR - 1),
                         ("established", ESTABLISHED_FROM_YEAR, YEARS[-1])):
        win = [r for r in A if lo <= r["year"] <= hi]
        out[name] = {
            "lo": lo, "hi": hi, "n": len(win),
            "sig_pos": [r["year"] for r in win if cls(r) == "sig_pos"],
            "sig_neg": [r["year"] for r in win if cls(r) == "sig_neg"],
            "ns": [r["year"] for r in win if cls(r) == "ns"],
            "degenerate": [r["year"] for r in win if cls(r) == "degenerate"],
        }
    # every significantly negative year anywhere in the run, year 1 included
    out["sig_neg_all"] = [r for r in A if cls(r) == "sig_neg"]
    return out


def year1_retry_pressure():
    """Year-1 retry pressure, two DIFFERENT statistics that were conflated upstream.

    ``retried``   share of year-1 decisions with retry_count > 0, i.e. the
                  validator returned a rejection to the agent at least once.
    ``exhausted`` share with retry_count == the budget (3), i.e. the agent was
                  told and re-prompted until the loop gave up.

    The brief's "68-88% of governed year-1 decisions having exhausted their retry
    budget" is the RETRIED statistic, not the exhausted one, and it is the range
    of PER-CELL MEANS across the five irrigation configurations rather than an
    anchor-cell range. Both are computed here and both are printed, so the paper
    can state whichever it means without inheriting the conflation.
    """
    budget = 3
    anchor = {"retried": [], "exhausted": []}
    for s in D.paired_seeds(""):
        y1 = year_rows(D.load_audit(D.irrigation_run("gov", "", s)), 1)
        rc = [int(r["retry_count"]) for r in y1 if str(r["retry_count"]).strip() != ""]
        if max(rc) != budget:
            raise D.DataError(
                f"anchor gov seed {s} year 1: max retry_count is {max(rc)}, "
                f"expected the budget {budget}")
        anchor["retried"].append(100.0 * sum(1 for v in rc if v > 0) / len(rc))
        anchor["exhausted"].append(100.0 * sum(1 for v in rc if v == budget) / len(rc))
    per_cell = {}
    for m in D.IRRIGATION_MODELS:
        v = []
        for s in sorted(D.irrigation_runs("gov", m.prefix)):
            y1 = year_rows(D.load_audit(D.irrigation_run("gov", m.prefix, s)), 1)
            rc = [int(r["retry_count"]) for r in y1 if str(r["retry_count"]).strip() != ""]
            v.append(100.0 * sum(1 for x in rc if x > 0) / len(rc))
        per_cell[m.label] = D.mean(v)
    return anchor, per_cell


def spearman(a, b):
    """Spearman rho, stdlib only, average ranks on ties."""
    def rank(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    ra, rb = rank(list(a)), rank(list(b))
    ma, mb = D.mean(ra), D.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else float("nan")


def governed_enforcement_by_year():
    """Governed-arm rejection rate per year, anchor cell. Descriptive only."""
    seeds = D.paired_seeds("")
    aud = {s: D.load_audit(D.irrigation_run("gov", "", s)) for s in seeds}
    return [D.mean([D.rejection_pressure(year_rows(aud[s], y)) for s in seeds])
            for y in YEARS]


# =============================================================================
# LAYOUT SELF-CHECK
# =============================================================================
# This used to compare Text boxes against each other and nothing else, which is
# why three rounds of "overlap check: 0" coexisted with a figure whose labels
# visibly touched things. A label does not have to land on another LABEL to be
# broken -- it can land on the plotted line, on the CI band, on a bar, on an
# arrow, on a legend frame, on an axis spine, or in the neighbouring panel. All
# six are now checked, geometrically, against the artist's real PATH rather than
# its bounding box (a 42-point line's bounding box is the whole panel, so a
# bbox test here would be useless in both directions).
#
# THREE EXEMPTIONS, NAMED RATHER THAN LEFT IMPLICIT
#   1. a text's own furniture -- its bbox patch and, for an annotation, its own
#      leader arrow. Those belong to the label; hitting them is not a collision.
#   2. a legend's own frame and handles against that same legend's own labels.
#   3. BACKGROUND FIELDS -- grid lines, and axvspan/axhspan bands drawn at
#      zorder <= 0.5. These are the field a label sits ON, not something it can
#      collide with, and the reference figure this layout follows deliberately
#      puts white-boxed labels on exactly such fields. Nothing is silently
#      forgiven: field contacts are counted and printed on their own line, so
#      the headline count can never be reduced by widening this exemption.
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
    True under BOTH filled=True and filled=False. Every patch this figure draws
    is a rectangle or an arrow, and for those the window extent is either exact
    or conservative, so patches are tested on their window extent alone. Lines
    and collections DO need the path -- a 42-point line's window extent is the
    whole panel, and a bbox test on it would flag every label in the panel.
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
    # why it went unnoticed: panel c's two-line x label was being cut in half by
    # the bottom edge while the label-vs-label check reported a clean figure.
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
        fbox = lg.get_frame().get_window_extent(rend)
        for t in texts:
            if legend_of.get(id(t["obj"])) == id(lg):
                continue
            if t["box"].overlaps(fbox):
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


# =============================================================================
# Drawing
# =============================================================================
#: Points between the panel letter's anchor and the title's. It has to clear the
#: letter's own advance width: at 10.5 pt Times New Roman Bold "a", "b" and "c"
#: are 4.7-5.3 pt wide, so 13.0 leaves about 8 pt of daylight -- more than the
#: three spaces the old single-string title used, and far more than the 1 px
#: (0.24 pt at 300 dpi) tolerance the collision check works to.
LETTER_GAP_PT = 13.0
#: Points from the axes' top edge to the shared baseline of letter and title.
#: The two are set at DIFFERENT sizes, so they are anchored on their BASELINE
#: rather than on their bounding boxes: with va="bottom" a title containing a
#: descender ("Reservoir levels diverge", "Larger with no retry") would ride
#: higher than one without ("Shift is not monotone"), which is the state the
#: single-string titles were in.
LETTER_PAD_PT = 4.5


def _panel_head(ax, letter: str, words: str) -> None:
    """Panel letter and panel title as two Texts, at their two sizes.

    These used to be one string -- ``set_title("a   Shift is not monotone")`` --
    which meant the letter could only ever be the title's size. The shared
    hierarchy sets the letter apart from the title deliberately (10.50 against
    9.75 pt; see _figstyle.py), and one string cannot carry two sizes. Geometry
    is otherwise unchanged: the letter still sits on the axes' left edge and the
    title still starts a little to its right, which is what the three spaces in
    the old string did by eye.
    """
    common = dict(xy=(0.0, 1.0), xycoords="axes fraction", textcoords="offset points",
                  ha="left", va="baseline", fontweight="bold", annotation_clip=False)
    ax.annotate(letter, xytext=(0.0, LETTER_PAD_PT),
                fontsize=FS.FS_PANEL_LETTER, **common)
    ax.annotate(words, xytext=(LETTER_GAP_PT, LETTER_PAD_PT),
                fontsize=FS.FS_PANEL_TITLE, **common)


def draw(A, B, C, pooled, floor, y1_retry, yc):
    # SINGLE-column width: the venue's text block is 5.5 in (neurips_2026.sty).
    # The manuscript includes this at 0.80\linewidth (PRINT_SCALE), so MIN_FONT
    # is chosen to clear the 7 pt printed floor after that scale factor.
    FS.assert_print_floor()
    #
    # STRUCTURE, rebuilt 2026-08-03 against the Nature Water reference figure the
    # author named (paper/nature_water/figures/Fig2_irrigation_case.png). Three
    # things there make it read cleanly, and all three were missing here:
    #
    #   ONE LEGEND BOX, AT THE TOP, OUTSIDE EVERY PANEL, SPANNING THE WIDTH.
    #   This figure previously had TWO legends -- panel B's arms keyed inside
    #   panel B, on top of its own curves, and panel C's bars keyed in a
    #   frameless row at the foot. Both are now one framed box above everything,
    #   three columns wide: column 1 is panel b's two arms, column 2 panel c's
    #   two strata, column 3 the interval and the arrow. Nothing was dropped;
    #   each label now carries its panel letter, which the two separate legends
    #   did not need and the merged one does.
    #
    #   PANEL TITLES WITH CLEAR SPACE. hspace is 0.30 rather than 0.22 so panel
    #   b's bold heading has air above it instead of sitting against panel a's
    #   x-axis; the self-check enforces this (a title landing in the panel above
    #   is a "panel" conflict).
    #
    #   NO LABEL ON A DATA FIELD. Panel a's two annotations both move into the
    #   band below the lowest plotted CI bound (-27.08 pp), which no line, no
    #   marker and no band ever enters; panel b's "895 ft floor" sits below the
    #   floor rule, where the model cannot put data by construction. Both are
    #   verified geometrically, not by eye -- see _layout_conflicts.
    #
    # COLUMN WIDTHS, written in inches because that is what they are. left..right
    # spans 0.860 x 5.5 = 4.73 in: 2.02 in for the shared-x column, a 1.15 in
    # gutter, 1.56 in for panel C. wspace = 1.15 / mean(2.02, 1.56) = 0.6425
    # reproduces that exactly. The gutter WIDENED from 0.98 in: panel C's longest
    # y tick label, "ministral3:8b", is 0.87 in, so the old gutter left about
    # 0.06 in of daylight between that label and panel A's frame and the two
    # columns read as one crowded block. It is now about 0.24 in.
    #
    # HEIGHT is 4.05 in, up from 3.75. The foot legend is gone, which returns
    # 0.07 in at the bottom, and the top legend box costs 0.37 in; the balance is
    # the growth. Measured on the built PDF, not asserted: the body still ends on
    # page 8 and References still starts on page 9. Do not spend more without
    # re-measuring that -- at 0.80\linewidth this figure's height reaches the
    # page at 0.80x, and page 8 is the venue's budget, nearly spent.
    #
    # 4.05 -> 4.15 in on 2026-08-04, when every label was rewritten out of the
    # statistics vocabulary and into the vocabulary of the run. The plain words
    # are longer, and the one that does not fit anywhere is panel c's heading:
    # the long panel-c result title is wider than its 1.64 in panel
    # between its own left edge and the paper's edge, so on one line it runs
    # clean off the canvas. Set on two it grows UPWARD from the same baseline
    # (measured: +0.14 in) and lands in the legend, so the 0.10 in bought here
    # plus the `top` drop below is what gives it room. The type was not touched:
    # FS.assert_print_floor() above still holds the 7 pt printed floor, and the
    # instruction that came with the rewrite was that room is bought with canvas.
    fig = plt.figure(figsize=(5.5, 4.15))
    gs = fig.add_gridspec(
        2, 2, width_ratios=[1.94, 1.56], height_ratios=[1.55, 1.0],
        wspace=0.6570, hspace=0.300, left=0.142, right=0.985, top=0.795,
        bottom=0.148)
    # bottom is set by panel C, not panel B: panel C carries one row of tick
    # labels and a TWO-line x label, 0.47 in of stack, and at bottom=0.120 the
    # second line was being cut off by the canvas edge.
    axA = fig.add_subplot(gs[0, 0])
    axB = fig.add_subplot(gs[1, 0], sharex=axA)
    axC = fig.add_subplot(gs[:, 1])

    yrs = [r["year"] for r in A]

    # ---------------- Panel A ------------------------------------------------
    # NOTE there is deliberately no shading of the negative half. A grey
    # axhspan(-100, 0) used to fill it. It was checked against the caption, the
    # legend and this docstring and carried NOTHING -- no threshold, no window,
    # no significance region -- while covering roughly half the panel's area, so
    # a reader had to decode a large grey block that encoded nothing. The zero
    # line already separates the two directions, and the two significantly
    # negative years are marked individually and named. Do not reinstate it: a
    # shaded region a reader cannot decode is a cost with no matching claim.
    axA.axhline(0, color="0.35", lw=0.7, ls=(0, (4, 3)), zorder=2)
    axA.fill_between(yrs, [r["ci_lo_pp"] for r in A], [r["ci_hi_pp"] for r in A],
                     color=C_BAND, alpha=0.55, lw=0, zorder=3)
    axA.plot(yrs, [r["delta_pp"] for r in A], color=C_DELTA, marker="o", ms=2.2,
             mew=0, zorder=4)

    a1 = A[0]
    axA.axvline(1, color=C_MARK, lw=0.8, ls=":", zorder=2)
    axA.errorbar([1], [a1["delta_pp"]], yerr=[[a1["delta_pp"] - a1["ci_lo_pp"]],
                                              [a1["ci_hi_pp"] - a1["delta_pp"]]],
                 fmt="D", ms=4.2, mfc="white", mec=C_MARK, mew=1.2,
                 ecolor=C_MARK, elinewidth=1.2, capsize=2.4, zorder=6)
    # The year-1 label used to sit at (2, 90), inside the plotted field: two 8.75
    # pt lines there run from year 2 to year 11, and the CI band reaches 83.04 pp
    # at year 9 and 86.07 at year 10, so the label's lower line and the band
    # occupied the same paper. It moves to the clear band below the data, beside
    # the year-1 rule -- the dotted vertical at year 1 runs the full height of the
    # panel and is what ties the label to the marker, so no leader is needed.
    axA.text(1.7, -32, "year 1: no gap", fontsize=FS.FS_ANNOT, color=C_MARK,
             ha="left", va="top", linespacing=1.12, zorder=7)

    # ---- the years that run the OTHER way -----------------------------------
    # Computed, never written in. A panel asserting "the shift appears once the
    # worlds separate" must show the years where the Delta is significantly
    # NEGATIVE, or it is claiming a monotone ramp the data does not contain.
    neg = [r for r in yc["sig_neg_all"] if r["year"] > 1]
    # The YEAR NUMBERS IN THE LABEL are now built from ``neg`` as well. They used
    # to be the literal "years 4, 7" sitting beside a marker series that was
    # computed -- and ``neg_years``, the computed string, was assembled forty
    # lines below and never used. So the markers moved with the corpus and the
    # words next to them did not. One expression feeds both now.
    neg_years = " and ".join(str(r["year"]) for r in neg) if neg else "none"
    if neg:
        axA.plot([r["year"] for r in neg], [r["delta_pp"] for r in neg],
                 ls="none", marker="s", ms=5.2, mfc="none", mec=C_NEG, mew=1.3,
                 zorder=7)
        # x moved 13.0 -> 19.5. "year 1: no gap" is one line where it used to be
        # two ("year 1 / null"), so it now runs to about year 17 instead of
        # year 8 and the two callouts shared the same strip of paper. The band
        # below the data is unchanged and still clear of every plotted mark: the
        # lowest thing this panel draws is the year-4 CI bound at -27.08 pp.
        axA.text(19.5, -32, f"gap reverses in\nyears {neg_years}",
                 fontsize=FS.FS_ANNOT, color=C_NEG, ha="left", va="top",
                 linespacing=1.12, zorder=7)

    axA.set_ylabel("gap in how often it said\nscarcity was high (pp)")
    # Both annotations now share ONE clear band under the data rather than a
    # reserved empty half, so the limit tightens from -105 to -72. The lowest
    # thing this panel draws is the year-4 CI bound at -27.08 pp; the labels
    # start at -32 and end at -61, and the check below proves the separation
    # rather than trusting these numbers. The plotted range now fills 71% of the
    # panel instead of 60%, which is the only reason the lines are legible at
    # 0.80 scale. Nothing is dropped and nothing is clipped: +103.95 is the
    # highest CI bound and the top limit is 112.
    axA.set_ylim(-72, 112)
    axA.set_yticks([-50, -25, 0, 25, 50, 75, 100])
    axA.tick_params(labelbottom=False)
    _panel_head(axA, "a", "Gap is nonmonotone over time")

    # ---------------- Panel B ------------------------------------------------
    g = [r["gov_mead_ft"] for r in B]
    n = [r["noval_mead_ft"] for r in B]
    axB.fill_between(yrs, n, g, where=[a >= b for a, b in zip(g, n)],
                     color=C_GOV, alpha=0.13, lw=0, zorder=1)
    axB.fill_between(yrs, [r["gov_mead_min_ft"] for r in B],
                     [r["gov_mead_max_ft"] for r in B],
                     color=C_GOV, alpha=0.20, lw=0, zorder=2)
    axB.fill_between(yrs, [r["noval_mead_min_ft"] for r in B],
                     [r["noval_mead_max_ft"] for r in B],
                     color=C_NOVAL, alpha=0.20, lw=0, zorder=2)
    axB.plot(yrs, g, color=C_GOV, ls="-", marker="o", ms=2.2, mew=0, zorder=4,
             label="with-validators")
    axB.plot(yrs, n, color=C_NOVAL, ls=(0, (5, 2)), marker="s", ms=2.2, mew=0,
             zorder=4, label="no-validator")
    axB.axhline(MEAD_FLOOR_FT, color="0.35", lw=0.7, ls=(0, (1, 2)), zorder=3)
    # Below the plotted floor rather than above it: 895 ft is the lowest point of
    # the model's elevation-storage curve, so nothing can be drawn under this
    # rule by construction and the label cannot land on a curve at any seed. What
    # changed is the LIMIT, not the placement -- the bottom was 845 ft and the
    # label's second half ran to 842, i.e. off the axis and into the bottom
    # spine. The limit is now 820 ft and the label clears the spine by 13 ft.
    axB.text(1.6, MEAD_FLOOR_FT - 9, "895 ft: the floor",
             fontsize=FS.FS_ANNOT, color="0.30", ha="left", va="top")
    axB.axvline(1, color=C_MARK, lw=0.8, ls=":", zorder=3)
    # "same start" moves out of the curves' own field and up to the clear top-left
    # corner, where the highest thing drawn over years 1-15 is 1164.6 ft. As in
    # panel a, the dotted year-1 rule runs the full panel height and is what
    # carries the label back to the year it is about.
    axB.text(2.0, 1252, "same start", fontsize=FS.FS_ANNOT, color=C_MARK,
             ha="left", va="top")
    axB.set_xlabel("year (1-42)")
    axB.set_ylabel("Lake Mead\nelevation (ft)")
    axB.set_xlim(0.2, 42.8)
    axB.set_xticks([1, 5, 10, 15, 20, 25, 30, 35, 42])
    # Top limit 1310 rather than 1252 so "same start" has clear air BOTH above
    # and below: the highest thing drawn over years 1-15 is 1164.6 ft, and panel
    # b's bold heading sits just above the frame. A label wedged against a title
    # is the crowding the author objected to even when it technically clears it.
    axB.set_ylim(820, 1310)
    # Six labels 50 ft apart need 0.111 in of panel per label and an 8.75 pt
    # digit is 0.121 in tall, so 900/950/1000/1050/1100/1150 were touching each
    # other -- a defect the old label-vs-label check should have caught and did
    # not, because it compared only the two boxes' overlap after matplotlib had
    # already been asked to draw them. Every hundred feet instead: 0.222 in of
    # panel per label. The axis is continuous and the caption carries the exact
    # elevations, so this costs no information.
    axB.set_yticks([900, 1000, 1100])
    _panel_head(axB, "b", "World states diverge after year 1")
    # NO per-panel legend here any more. The two arms are keyed in the single box
    # at the top of the figure. The old axB.legend sat at "upper left" INSIDE the
    # axes, which put its two handle lines and both labels directly over the
    # region the curves occupy in years 3-14 -- the one thing the reference
    # figure never does.

    # ---------------- Panel C ------------------------------------------------
    recs = list(C) + [pooled]
    labels, ypos = [], []
    h = 0.36
    for i, r in enumerate(recs):
        ypos.append(len(recs) - 1 - i)
        lab = r["cell"]
        if r["excluded_from_paired"]:
            lab += "*"
        if r["cell"] == "pooled":
            lab = "pooled"
        labels.append(lab)

    for r, y in zip(recs, ypos):
        axC.barh(y + h / 2, r["all_delta_pp"], height=h, color=C_ALL,
                 edgecolor="black", lw=0.5, zorder=3,
                 label="all decisions" if y == ypos[0] else None)
        # "never blocked", not "never retried (retry_count = 0)". These two
        # labels are carried on the bars themselves rather than drawn -- the key
        # is the single box at the top -- but they are what an `axC.legend()`
        # would print, so leaving the old wording here would reintroduce the
        # column name on the page the moment anyone added one.
        axC.barh(y - h / 2, r["nr_delta_pp"], height=h, color=C_NR,
                 edgecolor="black", lw=0.5, hatch="///", zorder=3,
                 label="never blocked" if y == ypos[0] else None)
        # CI only where a paired t on >=3 seeds exists; df=1 gives a useless
        # interval and is stated in words instead of drawn.
        if r["all_df"] >= 2:
            axC.plot([r["all_ci_lo_pp"], r["all_ci_hi_pp"]], [y + h / 2] * 2,
                     color="black", lw=0.7, zorder=5,
                     solid_capstyle="butt")
            axC.plot([r["nr_ci_lo_pp"], r["nr_ci_hi_pp"]], [y - h / 2] * 2,
                     color="black", lw=0.7, zorder=5, solid_capstyle="butt")
        # This arrow runs from the all-decisions value to the never-retried
        # value -- it is the panel's claim drawn as a direction, NOT a mark on
        # the interval. It is drawn at y - h/2, which is also where the
        # never-retried CI is drawn, so its head lands ON that whisker (and,
        # checked on the data, strictly INSIDE the interval in 4 of the 4 cells
        # that have one). A reader meeting an arrowhead on a confidence interval
        # reads "the interval runs off the axis"; that reading is false here --
        # xlim is 1.18x the largest CI bound, so nothing is clipped. The legend
        # at the foot therefore names the arrow explicitly. Do not remove that
        # entry while this annotate call exists.
        axC.annotate("", xy=(r["nr_delta_pp"], y - h / 2),
                     xytext=(r["all_delta_pp"], y - h / 2), zorder=6,
                     arrowprops=dict(arrowstyle="-|>", color="0.15", lw=0.7,
                                     shrinkA=0, shrinkB=0,
                                     mutation_scale=6))

    axC.axhline(0.5, color="0.75", lw=0.6, ls=(0, (2, 2)), zorder=1)
    axC.set_yticks(ypos)
    axC.set_yticklabels(labels, fontsize=FS.FS_TICK)
    axC.set_ylim(-0.62, len(recs) - 1 + 1.55)
    hi = max(max(r["all_delta_pp"], r["nr_delta_pp"]) for r in recs)
    hi = max([hi] + [r[f"{s}_ci_hi_pp"] for r in recs for s in ("all", "nr")
                     if r[f"{s}_df"] >= 2])
    axC.set_xlim(0, hi * 1.18)
    axC.set_xticks([0, 40, 80])
    axC.axvline(0, color="0.35", lw=0.7)
    # The sign convention that used to be the third line is now stated once,
    # for every panel, in the note at the foot.
    axC.set_xlabel("gap in how often it said\nscarcity was high (pp)",
                   fontsize=FS.FS_AXIS_LABEL)
    # Panel C's heading goes through _panel_head, the same call panels A and B
    # use, so it is anchored above THIS panel's frame and moves with it. It used
    # to be an axC.text placed inside the axes at the top of the right-hand
    # column, where it read as a heading floating over panel A and wrapped after
    # "Never retried", breaking the phrase across two lines. One line now, and
    # with more room than before rather than less: the string was 1.62 in when
    # the figure was set in DejaVu Sans Bold at 9 pt against 1.67 in of column
    # plus right margin, and in Times New Roman Bold at the hierarchy's 10.50 pt
    # letter + LETTER_GAP_PT + 9.75 pt title it measures 1.436 in. Times runs
    # about 20% narrower at the same size, which is what paid for the larger
    # type while leaving MORE daylight than the sans version had.
    # Two lines, and the break is forced: the panel states that the gap is
    # 1.98 in, and from panel c's left edge to the paper's edge there is 1.64 in.
    # Set on one line the heading does not overrun a neighbour, it leaves the
    # canvas -- which the label-vs-label test cannot see and the off-canvas test
    # in _layout_conflicts can.
    _panel_head(axC, "c", "Gap is larger without\nblocking")

    # ---------------- ONE legend box, at the top, outside every panel ---------
    # The structural change of this round. Previously this figure keyed itself in
    # two places -- panel B's arms inside panel B's own data area, and panel C's
    # bars in a frameless row at the foot -- so a reader had to hunt for the key
    # twice and one of the two was drawn over the curves it described.
    #
    # Column-major fill puts the pairs where they belong: column 1 is panel b,
    # column 2 is panel c's two strata, column 3 is panel c's interval and arrow.
    # Every label carries its panel letter, which is new and is what lets one box
    # serve two panels without ambiguity. Nothing was dropped in the merge; the
    # arrow entry in particular stays, because without it the arrowhead in panel
    # c sits on a confidence interval with nothing to read it by, and the reading
    # that suggests -- an interval running off the axis -- is not true here.
    leg = fig.legend(loc="upper center", bbox_to_anchor=(0.5, 0.997), ncol=3,
                     frameon=True, handlelength=1.5, borderaxespad=0.0,
                     columnspacing=1.0, handletextpad=0.45, labelspacing=0.34,
                     borderpad=0.55, fontsize=FS.FS_LEGEND,
                     handles=[
                         Line2D([0], [0], color=C_GOV, ls="-", marker="o",
                                ms=2.6, mew=0, label="with-validators (b)"),
                         Line2D([0], [0], color=C_NOVAL, ls=(0, (5, 2)),
                                marker="s", ms=2.6, mew=0,
                                label="no-validator (b)"),
                         Patch(facecolor=C_ALL, edgecolor="black", lw=0.5,
                               label="all decisions (c)"),
                         Patch(facecolor=C_NR, edgecolor="black", lw=0.5,
                               hatch="///", label="never blocked (c)"),
                         Line2D([0], [0], color="black", lw=0.7,
                                label="95% confidence interval (c)"),
                         Line2D([0, 1], [0, 0], color="0.15", lw=0.7, marker=">",
                                markersize=2.6, markevery=[1], mfc="0.15",
                                mec="0.15", label="shift between the two (c)"),
                     ])
    leg.get_frame().set_linewidth(0.6)
    leg.get_frame().set_edgecolor("0.55")
    leg.get_frame().set_facecolor("white")
    os.makedirs(FIGDIR, exist_ok=True)
    png = os.path.abspath(os.path.join(FIGDIR, STEM + ".png"))
    pdf = os.path.abspath(os.path.join(FIGDIR, STEM + ".pdf"))
    _assert_no_text_overlaps(fig)
    fig.savefig(png, dpi=300)
    fig.savefig(pdf)
    plt.close(fig)
    return png, pdf


# =============================================================================
# Audit trail + cross-checks
# =============================================================================
def write_csv(A, B, C, pooled):
    path = os.path.abspath(os.path.join(FIGDIR, STEM + ".csv"))
    cols = ["panel", "series", "x", "value", "lo", "hi", "unit", "n", "note"]
    rows = []
    for r in A:
        rows.append(dict(panel="A", series="delta_high_appraisal_prevalence",
                         x=r["year"], value=round(r["delta_pp"], 4),
                         lo=round(r["ci_lo_pp"], 4), hi=round(r["ci_hi_pp"], 4),
                         unit="percentage points (noval minus gov)",
                         n=r["n_seeds"],
                         note=f"gov={r['gov_high_pct']:.4f} noval={r['noval_high_pct']:.4f} "
                              f"p={r['p']:.4f} df={r['df']}"))
    for r in B:
        for arm, key in (("with-validators", "gov"), ("no-validator", "noval")):
            rows.append(dict(panel="B", series=f"lake_mead_level[{arm}]",
                             x=r["year"], value=round(r[f"{key}_mead_ft"], 4),
                             lo=round(r[f"{key}_mead_min_ft"], 4),
                             hi=round(r[f"{key}_mead_max_ft"], 4),
                             unit="feet (level, not a delta)", n=r["n_seeds"],
                             note="lo/hi = seed range"))
        rows.append(dict(panel="B", series="lake_mead_gap[gov_minus_noval]",
                         x=r["year"], value=round(r["gov_minus_noval_ft"], 4),
                         lo="", hi="", unit="feet (gov MINUS noval)",
                         n=r["n_seeds"],
                         note="NOT the project Delta; a level gap"))
    for r in list(C) + [pooled]:
        for stratum, name in (("all", "all decisions"),
                              ("nr", "never retried (retry_count=0)")):
            rows.append(dict(
                panel="C", series=f"delta_high_appraisal_prevalence[{name}]",
                x=r["cell"], value=round(r[f"{stratum}_delta_pp"], 4),
                lo=("" if r[f"{stratum}_df"] < 2 else round(r[f"{stratum}_ci_lo_pp"], 4)),
                hi=("" if r[f"{stratum}_df"] < 2 else round(r[f"{stratum}_ci_hi_pp"], 4)),
                unit="percentage points (noval minus gov)",
                n=r["n_paired_seeds"],
                note=f"gov={r[f'{stratum}_gov_high_pct']:.4f} "
                     f"noval={r[f'{stratum}_noval_high_pct']:.4f}"
                     + ("  UNBALANCED CELL" if r["excluded_from_paired"] else "")))
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return path, len(rows)


def main() -> int:
    print("=" * 100)
    print("FIG 2 -- MECHANISM: why the conditioning variable moves")
    print("=" * 100)
    print(f"SIGN CONVENTION : {D.DELTA_LABEL}")
    print("Panel B plots LEVELS per arm in feet, not a delta.")
    print()

    A, seeds = panel_a()
    B, _per, floor = panel_b()
    C, pooled = panel_c()
    y1_retry, y1_percell = year1_retry_pressure()
    yc = classify_years(A)

    ok = True

    # ---- Panel A ------------------------------------------------------------
    print("-" * 100)
    print("PANEL A  per-year Delta in HIGH-appraisal prevalence "
          f"(anchor gemma3:4b, seeds {list(seeds)})")
    print("-" * 100)
    print(f"  {'yr':>3s} {'gov%':>7s} {'noval%':>7s} {'Delta':>8s} "
          f"{'95% CI':>19s} {'p':>7s}")
    for r in A:
        star = "  <== YEAR 1, worlds identical" if r["year"] == 1 else ""
        print(f"  {r['year']:>3d} {r['gov_high_pct']:>7.2f} {r['noval_high_pct']:>7.2f} "
              f"{r['delta_pp']:>+8.2f} ({r['ci_lo_pp']:>+7.2f},{r['ci_hi_pp']:>+7.2f}) "
              f"{r['p']:>7.3f}{star}")
    print()
    print(f"  PER-YEAR STRUCTURE (two-sided alpha = {ALPHA}). The panel-A title, its")
    print("  annotation and the caption are all built from THIS classification.")
    for key in ("early", "established"):
        w = yc[key]
        print(f"    years {w['lo']:>2d}-{w['hi']:<2d} (n={w['n']:>2d})  "
              f"significantly +: {len(w['sig_pos']):>2d}   "
              f"significantly -: {len(w['sig_neg']):>2d} {w['sig_neg'] if w['sig_neg'] else ''}   "
              f"n.s.: {len(w['ns']):>2d} {w['ns'] if w['ns'] else ''}   "
              f"zero-variance: {len(w['degenerate']):>2d} "
              f"{w['degenerate'] if w['degenerate'] else ''}")
    print("    SIGNIFICANTLY NEGATIVE YEARS, the ones a 'moves only after' framing hides:")
    for r in yc["sig_neg_all"]:
        print(f"      year {r['year']:>2d}  Delta {r['delta_pp']:+7.2f} pp  "
              f"95% CI ({r['ci_lo_pp']:+.2f}, {r['ci_hi_pp']:+.2f})  p = {r['p']:.4f}")
    print("    Year 3 is zero-variance, not 'not significant': both arms are 100% HIGH in")
    print("    all five seeds, so the Delta is exactly 0 and the paired t is undefined.")
    print(f"    The year-{ESTABLISHED_FROM_YEAR} boundary is a DECLARED window, not a fitted change")
    print("    point. The counts inside it are computed; the boundary is not inferred.")
    print()
    print("  YEAR-1 RETRY PRESSURE, governed arm -- two statistics the brief conflates")
    print(f"    anchor, retried (retry_count > 0), per seed: "
          f"{['%.1f' % v for v in y1_retry['retried']]}  "
          f"-> {min(y1_retry['retried']):.1f}-{max(y1_retry['retried']):.1f}%, "
          f"mean {D.mean(y1_retry['retried']):.1f}%")
    print(f"    anchor, EXHAUSTED the budget (retry_count == 3), per seed: "
          f"{['%.1f' % v for v in y1_retry['exhausted']]}  "
          f"-> {min(y1_retry['exhausted']):.1f}-{max(y1_retry['exhausted']):.1f}%, "
          f"mean {D.mean(y1_retry['exhausted']):.1f}%")
    print("    per-cell MEAN retried (retry_count > 0), all five irrigation cells:")
    for k, v in y1_percell.items():
        print(f"       {k:14s} {v:6.2f}%")
    print(f"    -> range of per-cell means "
          f"{min(y1_percell.values()):.1f}-{max(y1_percell.values()):.1f}%")
    print("    The brief's '68-88% ... exhausted their retry budget' is the RETRIED")
    print("    statistic (retry_count > 0), reported as the range of PER-CELL MEANS.")
    print("    On the anchor cell the retried share is 82% and the truly exhausted")
    print("    share is 70%. Do not write 'exhausted' for the 68-88 number.")
    print()

    # ---- Panel B ------------------------------------------------------------
    print("-" * 100)
    print("PANEL B  Lake Mead elevation per arm (feet, mean of 5 seeds)")
    print("-" * 100)
    print(f"  {'yr':>3s} {'gov ft':>9s} {'noval ft':>9s} {'gov-noval':>10s}")
    for r in B:
        if r["year"] in (1, 2, 3, 5, 10, 15, 17, 18, 20, 25, 30, 35, 40, 42):
            print(f"  {r['year']:>3d} {r['gov_mead_ft']:>9.2f} "
                  f"{r['noval_mead_ft']:>9.2f} {r['gov_minus_noval_ft']:>+10.2f}")
    mean_gap = D.mean([r["gov_minus_noval_ft"] for r in B])
    print(f"  year-1 gap        {B[0]['gov_minus_noval_ft']:+.4f} ft   "
          "(the two arms start on the identical value)")
    print(f"  final-year gap    {B[-1]['gov_minus_noval_ft']:+.2f} ft")
    print(f"  42-year mean gap  {mean_gap:+.2f} ft")
    print()
    print("  895 ft ELEVATION FLOOR, per seed (the arm does NOT stay on it once")
    print("  reached -- it recovers and returns, so 'and stays there' is FALSE):")
    print(f"    {'seed':>5s} {'noval first yr':>15s} {'noval yrs on floor':>19s} "
          f"{'noval ends on it':>17s} {'noval min ft':>13s} {'gov min ft':>11s}")
    for s in seeds:
        print(f"    {s:>5d} {str(floor['first'][('noval', s)]):>15s} "
              f"{floor['n_years'][('noval', s)]:>19d} "
              f"{str(floor['ends_on_floor'][('noval', s)]):>17s} "
              f"{floor['min_ft'][('noval', s)]:>13.2f} "
              f"{floor['min_ft'][('gov', s)]:>11.2f}")
    print(f"    governed arm reaches the floor in "
          f"{sum(1 for s in seeds if floor['first'][('gov', s)] is not None)}/5 seeds")
    print()

    # ---- Panel C ------------------------------------------------------------
    print("-" * 100)
    print("PANEL C  never-retried vs all-decisions Delta in HIGH-appraisal prevalence")
    print("-" * 100)
    print(f"  {'cell':14s} {'n':>2s} {'ALL gov':>8s} {'ALL nov':>8s} {'d ALL':>8s} "
          f"{'NR gov':>8s} {'NR nov':>8s} {'d NR':>8s} {'NR-ALL':>8s} {'NR share gov/nov':>18s}")
    for r in list(C) + [pooled]:
        nrs = ("      -           " if r["nr_share_gov_pct"] != r["nr_share_gov_pct"]
               else f"{r['nr_share_gov_pct']:>8.1f}%/{r['nr_share_noval_pct']:.1f}%")
        print(f"  {r['cell']:14s} {r['n_paired_seeds']:>2d} "
              f"{r['all_gov_high_pct']:>8.2f} {r['all_noval_high_pct']:>8.2f} "
              f"{r['all_delta_pp']:>+8.2f} "
              f"{r['nr_gov_high_pct']:>8.2f} {r['nr_noval_high_pct']:>8.2f} "
              f"{r['nr_delta_pp']:>+8.2f} "
              f"{r['nr_delta_pp'] - r['all_delta_pp']:>+8.2f} {nrs:>18s}"
              f"{'  *UNBALANCED' if r['excluded_from_paired'] else ''}")
    print()

    # ---- descriptive correlations (NOT plotted) -----------------------------
    print("-" * 100)
    print("DESCRIPTIVE ONLY -- NOT DRAWN ON THE FIGURE")
    print("-" * 100)
    d = [r["delta_pp"] for r in A]
    gap = [r["gov_minus_noval_ft"] for r in B]
    enf = governed_enforcement_by_year()
    print(f"  Spearman(per-year Delta, reservoir gap)          rho = {spearman(d, gap):+.3f}")
    print(f"  Spearman(per-year Delta, governed rejection %)   rho = {spearman(d, enf):+.3f}")
    print("  CAVEAT: the 42 years are strongly autocorrelated, so these are not")
    print("  inferential. They are printed because DECISION.md section 9 killed the")
    print("  pressure-vs-shift scatter; do not reintroduce it as a correlation claim.")
    print()

    # ---- cross-checks against the brief ------------------------------------
    print("-" * 100)
    print("CROSS-CHECK against the brief's verified numbers "
          "(no code was tuned to match these)")
    print("-" * 100)

    def check(name, got, want, tol=0.005):
        nonlocal ok
        good = abs(got - want) <= tol
        if not good:
            ok = False
        print(f"  {'OK ' if good else '!! '} {name:56s} got {got:>+9.2f}  "
              f"brief {want:>+9.2f}  diff {got - want:>+7.3f}"
              f"{'' if good else '   <== DISAGREES WITH THE BRIEF'}")

    a1 = A[0]
    check("year 1 Delta HIGH prevalence", a1["delta_pp"], 3.33, 0.02)
    check("year 1 CI low", a1["ci_lo_pp"], -3.75, 0.02)
    check("year 1 CI high", a1["ci_hi_pp"], 10.42, 0.02)
    # The two significantly NEGATIVE years the panel is required to remark on.
    # Pinned so that a change in the corpus that removed or moved them would
    # break the run rather than quietly leave the title and caption stale.
    by_year = {r["year"]: r for r in A}
    check("year 4 Delta (significantly negative)", by_year[4]["delta_pp"], -18.46, 0.02)
    check("year 4 p", by_year[4]["p"], 0.004, 0.0006)
    check("year 7 Delta (significantly negative)", by_year[7]["delta_pp"], -6.41, 0.02)
    check("year 7 p", by_year[7]["p"], 0.001, 0.0006)
    n_neg = len([r for r in yc["sig_neg_all"] if r["year"] > 1])
    print(f"  {'OK ' if n_neg == 2 else '!! '} "
          f"{'significantly negative post-year-1 years, count':56s} got {n_neg:>+9d}"
          f"  brief {2:>+9d}")
    if n_neg != 2:
        ok = False
    anchor = C[0]
    check("anchor all-decisions Delta (all 42 yr)", anchor["all_delta_pp"], 45.73)
    check("anchor gov HIGH prevalence", anchor["all_gov_high_pct"], 37.08)
    check("anchor noval HIGH prevalence", anchor["all_noval_high_pct"], 82.80)
    for rec, want in zip(C, (53.46, 24.31, 50.93, 63.05, 34.09)):
        check(f"never-retried Delta, {rec['cell']}", rec["nr_delta_pp"], want)
    check("never-retried Delta, pooled", pooled["nr_delta_pp"], 48.21)
    check("all-decisions Delta, pooled", pooled["all_delta_pp"], 40.02)
    check("year-1 retried, min per-cell mean (brief '68')",
          min(y1_percell.values()), 68.0, 0.10)
    check("year-1 retried, max per-cell mean (brief '88')",
          max(y1_percell.values()), 88.0, 0.10)
    n_larger = sum(1 for r in C if r["nr_larger"])
    print(f"  {'OK ' if n_larger == len(C) else '!! '} "
          f"{'never-retried Delta LARGER in k of 5 cells':56s} got {n_larger:>+9d}"
          f"  brief {5:>+9d}")
    if n_larger != len(C):
        ok = False

    print()
    print("-" * 100)
    print("CAVEATS CARRIED BY THIS FIGURE")
    print("-" * 100)
    print("  1. The appraisal is post-treatment in BOTH arms; nothing here makes it")
    print("     a covariate. The figure explains why it moves, it does not repair it.")
    print("  2. Panel A years 2+ are NOT a clean contrast: the worlds have diverged,")
    print("     which is the point. Only year 1 is a controlled comparison.")
    print("  3. Panel C cannot adjudicate premise revision because the two arms are")
    print("     selected differently. The first-attempt appraisal of a retried-and-")
    print("     approved decision is not on disk (DECISION.md section 5).")
    print("  4. Panel C 'never retried' covers a much larger share of the")
    print("     no-validator arm than the governed arm, so the two strata are not")
    print("     the same population. That asymmetry is itself a consequence of")
    print("     enforcement and is reported in the csv (nr_share columns).")
    print()

    png, pdf = draw(A, B, C, pooled, floor, y1_retry, yc)
    csv_path, nrows = write_csv(A, B, C, pooled)
    print("-" * 100)
    print("OUTPUTS")
    print("-" * 100)
    for p in (png, pdf, csv_path):
        print(f"  {os.path.getsize(p):>9,d} bytes  {p}")
    print(f"  csv rows: {nrows}")
    print()

    print("-" * 100)
    print("SUGGESTED CAPTION")
    print("-" * 100)
    print(CAPTION.format(
        y1=a1["delta_pp"], y1lo=a1["ci_lo_pp"], y1hi=a1["ci_hi_pp"], y1p=a1["p"],
        retried=D.mean(y1_retry["retried"]),
        exhausted=D.mean(y1_retry["exhausted"]),
        gap_end=B[-1]["gov_minus_noval_ft"], gap_mean=mean_gap,
        fy_lo=min(floor["first"][("noval", s)] for s in seeds),
        fy_hi=max(floor["first"][("noval", s)] for s in seeds),
        nf_lo=min(floor["n_years"][("noval", s)] for s in seeds),
        nf_hi=max(floor["n_years"][("noval", s)] for s in seeds),
        gmin=min(floor["min_ft"][("gov", s)] for s in seeds),
        d_all=anchor["all_delta_pp"], d_nr=anchor["nr_delta_pp"],
        p_all=pooled["all_delta_pp"], p_nr=pooled["nr_delta_pp"],
        e_lo=yc["early"]["lo"], e_hi=yc["early"]["hi"],
        e_pos=len(yc["early"]["sig_pos"]), e_ns=len(yc["early"]["ns"]),
        e_neg=len(yc["early"]["sig_neg"]),
        s_lo=yc["established"]["lo"], s_n=yc["established"]["n"],
        s_pos=len(yc["established"]["sig_pos"]),
        s_ns=len(yc["established"]["ns"]),
        neg_txt="; ".join(
            f"year {r['year']} at {r['delta_pp']:+.2f} pp (p = {r['p']:.3f})"
            for r in yc["sig_neg_all"] if r["year"] > 1),
    ))
    print()
    print("=" * 100)
    print(f"FIG 2: {'CLEAN' if ok else 'DISAGREEMENTS ABOVE -- READ THEM'}")
    print("=" * 100)
    return 0 if ok else 1


CAPTION = """\
Figure 2. The conditioning variable moves alongside a change in the recorded world;
the panels provide a descriptive decomposition, not a causal mechanism test.
Irrigation testbed, anchor configuration (gemma3:4b), five
seeds present in both arms. Throughout, Delta = (no-validator) MINUS
(with-validators), so a positive Delta means the validators lowered the quantity.
The axes are labelled in the terms of the run rather than of the statistic: "gap
in how often it said scarcity was high" is that Delta in the prevalence of the
HIGH self-reported water-scarcity appraisal, and "never blocked" is the
never-retried stratum, the decisions with retry_count = 0 on which the governance
loop returned nothing to the agent.
(a) Per-year Delta in the prevalence of the HIGH self-reported water-scarcity
appraisal, the variable the published conformance rate conditions on; band is the
95% CI across seeds (paired t, df = 4). At year 1 the two arms' worlds are
the equality check finds identical values for every pre-decision candidate-
state column in each paired agent-year, and the Delta is null, {y1:+.2f} pp
(95% CI {y1lo:+.2f},
{y1hi:+.2f}; p = {y1p:.2f}), even though the validator had already rejected and
re-prompted {retried:.0f}% of governed year-1 decisions, with {exhausted:.0f}% of governed year-1
decisions re-prompted to the end of the retry budget. The shift appears only
after year 1, once the arms' trajectories separate, but it does not then rise
monotonically: over years {e_lo}-{e_hi} it oscillates, with {e_pos} years significantly
positive, {e_ns} not significant, year 3 exactly zero in every seed, and {e_neg}
significantly NEGATIVE -- {neg_txt} -- both marked on the panel. From
year {s_lo} onward it is established and one-directional: {s_pos} of the {s_n} years are
significantly positive, {s_ns} are not significant and none is significantly
negative. Year {s_lo} is a stated window boundary, not a fitted change point.
(b) Lake Mead elevation per arm
over the same years (levels in feet, not a delta); line is the seed mean, band
the seed range. The arms start on the identical value and diverge from year 2.
The no-validator arm first reaches the floor of the model's elevation-storage
curve (895 ft, 2.0 MAF) at year {fy_lo}-{fy_hi} in all five seeds, spends
{nf_lo}-{nf_hi} of the 42 years on it and ends the run on it in all five; the
governed arm never reaches it (minimum {gmin:.0f} ft) and ends {gap_end:+.1f} ft
higher, with a 42-year mean gap of {gap_mean:+.1f} ft.
(c) The same Delta computed on all decisions versus on the never-retried stratum
(retry_count = 0), where the governance loop never returned anything to the
agent. The Delta is larger on the never-retried stratum in every irrigation
configuration (anchor {d_all:+.1f} to {d_nr:+.1f} pp; pooled {p_all:+.1f} to
{p_nr:+.1f} pp). Because the two arms are filtered differently, this larger
contrast is compatible with treatment-affected selection as well as with world
composition. Bars carry 95% CIs from a paired t over seeds where
three or more paired seeds exist, which is now every configuration. Panel c is computed on the
audit records, which are the only source of retry_count; the appraisal column
there agrees with the simulation log on 32,652 of 32,760 anchor rows, the 108
exceptions being an encoding difference on unparsed labels that are not HIGH
under either encoding. Together the panels show a world-state composition pattern,
while leaving within-world reporting and selection unresolved."""


if __name__ == "__main__":
    sys.exit(main())
