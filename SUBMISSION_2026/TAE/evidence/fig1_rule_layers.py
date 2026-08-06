"""Figure 1 -- "The two rule layers separate".

WHAT THIS FIGURE CLAIMS
-----------------------
The governance system contains two mechanically distinct rule layers, and in this
corpus every rejection belongs to exactly one of them, determined entirely by arm:

  1. A WORLD-FEASIBILITY layer -- the skill-registry precondition
     ``not at_allocation_cap``. Verified in
     ``examples/irrigation_abm/config/skill_registry.yaml``: this precondition is
     attached to ``increase_large`` and ``increase_small`` and to NO other skill.
     It is evaluated before any behavioural rule; when it blocks, ``failed_rules``
     names no rule at all and ``error_messages`` reads
     "Precondition failed: 'not at_allocation_cap' (field is True)".

  2. A BEHAVIOURAL-RULE layer -- the validator stack, which names the rules it
     fired in ``failed_rules``.

Result, pooled over 5 seeds of the anchor cell (gemma3:4b), 16,380 decisions/arm:

     no-validator      4,757 / 16,380 rejected (29.0%)  -- 100.0% precondition
     with-validators   6,469 / 16,380 rejected (39.5%)  -- 100.0% named rules

Zero exceptions in either direction, and the same partition holds in all five
irrigation models (10/10 cells pure) -- so the separation is not one cell's
artifact.

Three things the figure is built to make visible:
  (a) IN THE ANCHOR CELL both arms reject a substantial share of proposals --
      there the no-validator arm is NOT "unconstrained" (29.0% of its proposals
      are still blocked). THIS IS AN ANCHOR-CELL STATEMENT AND DOES NOT
      GENERALISE: the no-validator rejection rate is 29.0% on gemma3:4b but
      5.3% (12b), 3.6% (e2b), 1.5% (e4b) and 1.0% (ministral3:8b). Panel B
      prints all five, and any "the water right still binds" sentence in the
      paper must be scoped to the anchor or panel B falsifies it;
  (b) the CAUSE is disjoint between arms;
  (c) the world layer binds only on INCREASE proposals -- i.e. on exactly the
      numerator of the conformance statistic the paper is about -- whereas
      neither of the behavioural layer's two rule kinds does.

An honest refinement this script computes rather than assumes: the validator
layer is not homogeneous. Two of its six fired rules
(``high_threat_high_cope_no_increase``, ``low_threat_no_increase``) condition on
the agent's SELF-REPORTED appraisal (WSA_LABEL / ACA_LABEL); the other four
(``demand_ceiling_stabilizer``, ``demand_floor_stabilizer``,
``curtailment_awareness``, ``supply_gap_block_increase``) condition on world
state. Panel A therefore splits the behavioural layer into "names an
appraisal-conditioned rule" and "names only world-conditioned rules". Calling the
whole with-validators layer "behavioural theory" without that split would
overstate it, and a reviewer reading the rule list would catch it.

THE WITHIN-STACK CONTRAST, AND WHERE IT IS ON THE PAGE
------------------------------------------------------
The split above is the paper's tightest comparison, because both rule kinds live
in the SAME validator stack, the same arm and the same run: no cross-testbed
comparison, and therefore none of the regime/testbed confounding that killed the
14-cell scatter. It is carried twice, deliberately:

  * Panel A's MIDDLE row RE-BASES the with-validators rejections on their own
    total, so the anchor split reads 3,840 / 6,469 = 59.4% appraisal-conditioned
    against 2,629 / 6,469 = 40.6% world-conditioned-only directly on the figure.
    Those two percentages, not the 23.4% / 16.1% they are of all decisions, are
    the numbers the 2026-07-31 correction was about.
    That middle row is NOT a third arm, and the panel is drawn so that this is
    geometric rather than something the reader has to be told: it is indented
    (its label is far shorter than either arm name and the labels are
    right-aligned), it is drawn thinner than the two arm bars, it is set in
    italic grey rather than upright black, its label reads "of which, rejected",
    and a rule runs beneath it so the panel divides into a two-row
    with-validators block and a one-row no-validator arm. Only the top and
    bottom rows are arms.
  * Panel C then asks what each of the two kinds actually blocks, pooled over the
    five irrigation models -- same arm, same runs, one variable changed.

Panel A is the ANCHOR CELL (gemma3:4b, 59.4 / 40.6 of 6,469). Panel C is the
FIVE-MODEL POOL (60.3 / 39.7 of 31,313). They are different denominators over
different corpora and must never be quoted as the same number.

WHAT WOULD FALSIFY IT
---------------------
Any of the following, checked by ``_verify()``, which exits 1 if it fails:
  * a no-validator rejection that names a behavioural rule (would make the
    layers overlap, and the "the water right is the only thing binding without
    validators" reading would collapse);
  * a with-validators rejection recorded as a bare precondition failure (would
    mean the two layers are not distinguishable by cause in the audit);
  * either of the above in ANY of the five irrigation models (would make the
    separation a single-cell artifact);
  * a no-validator rejection whose proposed action is not an increase (would
    break claim (c) -- the world layer would not be binding specifically on the
    metric's numerator);
  * the anchor counts departing from 4,757/16,380 and 6,469/16,380.

BASIS AND STATISTICS
--------------------
This figure is a COUNT DECOMPOSITION, pooled across seeds. That is the right
basis here and it matches the brief's own verified numbers (4,757/16,380 =
29.0%). No paired contrast, no confidence interval and no p-value is drawn from
it -- for anything inferential the seed is the unit and that lives in
``table1_cells.py``. Every irrigation cell holds the same seeds in both arms,
so no cell is marked or set aside; each per-arm n is stated regardless.

SIGN CONVENTION
---------------
No delta is plotted in this figure, so the project sign convention does not
arise. It is printed on the output anyway so the figure family stays consistent.

USAGE
-----
    python SUBMISSION_2026/TAE/evidence/fig1_rule_layers.py

Writes figures/fig1_rule_layers.{png,pdf} and figures/fig1_rule_layers.csv,
prints every plotted value and a suggested caption. Exits 1 if verification
fails.
"""
from __future__ import annotations

import csv
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _data as D  # noqa: E402
import _figstyle as FS  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.text import Text  # noqa: E402
from matplotlib.transforms import Bbox  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.abspath(os.path.join(HERE, "..", "figures"))
STEM = "fig1_rule_layers"
# Typeface and every point size come from _figstyle.py, which fig2 and fig3 also
# read. They were three separate rcParams blocks before this pass; a shared
# decision kept in three copies is how the palette drifted last time.
PRINT_SCALE = FS.PRINT_SCALE
MIN_PRINT_FONT = FS.MIN_PRINT_FONT
MIN_FONT = FS.MIN_FONT

# =============================================================================
# Rule taxonomy -- written out literally, sourced from the configs
# =============================================================================
#: Validator rules whose antecedent reads a SELF-REPORTED construct label.
#: Source: examples/irrigation_abm/config/agent_types.yaml thinking_rules --
#: each carries `construct: WSA_LABEL` / `ACA_LABEL`.
APPRAISAL_CONDITIONED_RULES = frozenset({
    "high_threat_high_cope_no_increase",   # WSA in {H,VH} AND ACA in {H,VH}
    "low_threat_no_increase",              # WSA in {VL}
    "high_threat_no_maintain",             # WSA in {VH}; WARNING level
})

#: Validator rules whose antecedent reads WORLD state only. Source:
#: examples/irrigation_abm/validators/irrigation_validators.py
WORLD_CONDITIONED_RULES = frozenset({
    "demand_ceiling_stabilizer",     # basin-wide aggregate demand vs 6.0 MAF
    "demand_floor_stabilizer",       # agent utilisation vs stability floor
    "curtailment_awareness",         # shortage tier / curtailment ratio
    "supply_gap_block_increase",     # diversion / request fulfilment ratio
    "water_right_cap",               # identity rule; same field as the precondition
    "minimum_utilisation_floor",
    "magnitude_cap",
    "drought_severity",
    "consecutive_increase_cap",
    "compact_allocation",
    "non_negative_diversion",
})

DECREASE = frozenset({"decrease_small", "decrease_large"})

# --- plotted categories -------------------------------------------------------
C_APPROVED = "approved"
C_PRECOND = "world-feasibility precondition"
C_APPRAISAL = "behavioural rule (appraisal-conditioned)"
C_WORLDRULE = "behavioural rule (world-conditioned only)"
CAUSE_ORDER = [C_APPROVED, C_PRECOND, C_APPRAISAL, C_WORLDRULE]
#: the three REJECTION causes, i.e. CAUSE_ORDER minus "approved".
REJECTION_CAUSES = [C_PRECOND, C_APPRAISAL, C_WORLDRULE]
#: The two behavioural-rule kinds, in the order the within-stack contrast is read.
RULE_KINDS = [C_APPRAISAL, C_WORLDRULE]

#: Panel C rows: (arm, cause, row label). The two with-validators rows are
#: the WITHIN-STACK contrast -- same arm, same runs, only the rule kind differs.
#: The no-validator row is the other layer, shown for reference; it is the only
#: row that crosses arms and it is labelled as such on the figure.
#:
#: THESE LABELS ARE THE LEGEND'S WORDS, VERBATIM (2026-08-04). They used to read
#: "ON / appraisal rule", "ON / world rule", "OFF / precondition" -- an
#: abbreviation of a vocabulary the legend spelled out differently, so the same
#: three categories were named twice on one figure in two different registers and
#: the reader had to work out that they were the same three. They are now
#: identical strings to ``LEGEND_LABEL``. They now use one formal,
#: plain-language register throughout: ``rule reads self-report`` and ``rule
#: reads world state``. The b/c gutter remains wide enough for the longest row
#: label at the printed floor.
PANEL_C_ROWS = [
    ("gov",   C_APPRAISAL, "validators on\nrule reads self-report"),
    ("gov",   C_WORLDRULE, "validators on\nrule reads world state"),
    ("noval", C_PRECOND,   "validators off\nwater-right cap"),
]

A_INCREASE = "increase proposal"
A_DECREASE = "decrease proposal"
A_OTHER = "unparsed / no proposal"
ACTION_ORDER = [A_INCREASE, A_DECREASE, A_OTHER]

# =============================================================================
# THE PAPER'S SHARED FIGURE PALETTE
# =============================================================================
# One palette across all four figures, so a reader who learns the code on one
# figure is not misled by the next. Okabe-Ito throughout, colourblind-safe, and
# every category ALSO carries a hatch, so no meaning is encoded by colour alone.
#
#   #0072B2 blue and #D55E00 vermillion are RESERVED, in every figure, for the
#   with-validators and no-validator ARMS. Nothing else is ever drawn in either,
#   or in a shade of either. This figure plots causes and actions rather than
#   arms -- the arms are the row labels -- so neither colour appears here.
#   Before this pass the appraisal-conditioned rule was drawn in exactly the
#   arm blue and the precondition in an orange one step from the arm vermillion,
#   which is what made the code read differently on this figure than on fig2/3.
#
#   #009E73 bluish green   a quantity CONDITIONED ON WHAT THE AGENT REPORTED.
#                          Here: the appraisal-conditioned validator rules. In
#                          fig3 the same green carries the conditional statistic.
#   #CC79A7 reddish purple its WORLD-SIDE counterpart. Here: the validator rules
#                          that read only simulator state. In fig3 the same
#                          purple carries the unconditional statistic; in fig2
#                          the year-1 exogeneity marker.
#   #F0E442 yellow         the hard world-FEASIBILITY gate (the skill-registry
#                          precondition). A third hue, not a grey, because this
#                          is a whole rule layer and the figure's claim is that
#                          it is mechanically separate from the validator stack:
#                          giving it a tint of the purple would visually merge
#                          the two layers the panel exists to separate.
#   greys                  structural or neutral: approved, and the secondary
#                          action axis in panel c, which is a lightness ramp so
#                          it cannot be confused with the cause vocabulary above.
COLOUR = {
    C_APPROVED:  "#EFEFEF",
    C_PRECOND:   "#F0E442",   # yellow          world-feasibility gate
    C_APPRAISAL: "#009E73",   # bluish green    reads the agent's self-report
    C_WORLDRULE: "#CC79A7",   # reddish purple  reads world state only
    A_INCREASE:  "#4D4D4D",   # dark grey       action axis, lightness-ordered
    A_DECREASE:  "#B0B0B0",   # mid grey
    A_OTHER:     "#E8E8E8",   # light grey
}
#: Fills dark enough that bare text on them is illegible. Since 2026-08-03 EVERY
#: printed percent sits in a white box with a thin border regardless, so this is
#: kept only to document which segments the rule was introduced for.
DARK_FILL = frozenset({C_APPRAISAL, A_INCREASE})
#: WHAT THE READER SEES, as opposed to what the code calls it.
#:
#: The keys above (``C_PRECOND`` = "world-feasibility precondition", ``A_OTHER``
#: = "unparsed / no proposal", ...) are the CSV's category values and the
#: internal vocabulary; they do not change, so the audit trail is stable. What
#: changed on 2026-08-04 is every string that reaches the page. The old labels
#: -- "approved", "precondition", "appraisal rule", "world rule", "increase",
#: "decrease", "unparsed" -- were the codebase's names for these categories, and
#: each of them asks the reader to already know the mechanism before it can be
#: read. "unparsed" in particular is a property of the parser, not of the
#: decision. The replacements name what happened to the decision instead, and
#: the caption is where the plain word is tied back to the term the body uses.
LEGEND_LABEL = {
    C_APPROVED: "passed",
    C_PRECOND: "water-right cap",
    C_APPRAISAL: "rule reads self-report",
    C_WORLDRULE: "rule reads world state",
    A_INCREASE: "proposed increase",
    A_DECREASE: "proposed decrease",
    A_OTHER: "unparsed proposal",
}
HATCH = {
    C_APPROVED: "", C_PRECOND: "//", C_APPRAISAL: "xx", C_WORLDRULE: "..",
    A_INCREASE: "", A_DECREASE: "\\\\", A_OTHER: "",
}


# =============================================================================
# Classification
# =============================================================================
def fine_cause(audit_row: dict) -> str:
    """Cause of this decision's outcome, one of ``CAUSE_ORDER``.

    Delegates the two-layer split to ``_data.rejection_cause`` (which is the
    single definition used by every script in this folder) and only refines the
    behavioural layer. A rejection naming several rules is classed
    appraisal-conditioned if ANY named rule reads a self-reported construct --
    the conservative direction for a paper arguing that self-report-conditioned
    enforcement is the problematic case.
    """
    c = D.rejection_cause(audit_row)
    if c is None:
        return C_APPROVED
    if c == "precondition":
        return C_PRECOND
    names = {t.strip() for t in (audit_row.get("failed_rules") or "").split("|") if t.strip()}
    return C_APPRAISAL if (names & APPRAISAL_CONDITIONED_RULES) else C_WORLDRULE


def action_category(audit_row: dict) -> str:
    """Category of the action the agent PROPOSED (``proposed_skill``).

    Deliberately the proposal, not ``final_skill``: the question is what the
    layer was asked to allow, not what ended up executing.
    """
    p = (audit_row.get("proposed_skill") or "").strip()
    if p in D.INCREASE:
        return A_INCREASE
    if p in DECREASE:
        return A_DECREASE
    return A_OTHER


# =============================================================================
# Collection -- one pass over the corpus, everything derived from it
# =============================================================================
def collect() -> dict:
    """Read every irrigation run once and tabulate. No estimation anywhere."""
    cells = {}
    unknown_rules = set()
    for m in D.IRRIGATION_MODELS:
        for arm in D.ARMS:
            runs = D.irrigation_runs(arm, m.prefix)
            cause = {k: 0 for k in CAUSE_ORDER}
            act = {k: 0 for k in ACTION_ORDER}
            # the same proposed-action tally, but kept SEPARATELY per rejection
            # cause. This is what makes the within-stack contrast computable:
            # appraisal-conditioned rules against world-conditioned rules, same
            # arm, same runs, no cross-testbed comparison anywhere.
            act_by_cause = {c: {k: 0 for k in ACTION_ORDER} for c in REJECTION_CAUSES}
            total = 0
            at_cap = 0            # sim-log rows with request >= 99% of water right
            sim_rows = 0
            for seed, d in runs.items():
                for r in D.load_audit(d):
                    total += 1
                    c = fine_cause(r)
                    cause[c] += 1
                    if c != C_APPROVED:
                        a = action_category(r)
                        act[a] += 1
                        act_by_cause[c][a] += 1
                        for t in (r.get("failed_rules") or "").split("|"):
                            t = t.strip()
                            if (t and t.lower() not in D._NO_RULE_TOKENS
                                    and t not in APPRAISAL_CONDITIONED_RULES
                                    and t not in WORLD_CONDITIONED_RULES):
                                unknown_rules.add(t)
                for s in D.load_sim(d):
                    sim_rows += 1
                    wr = float(s["water_right"])
                    if wr > 0 and float(s["request"]) >= 0.99 * wr:
                        at_cap += 1
            rejected = total - cause[C_APPROVED]
            cells[(m.label, arm)] = {
                "model": m.label,
                "arm": arm,
                "n_seeds": len(runs),
                "seeds": sorted(runs),
                "total": total,
                "rejected": rejected,
                "cause": cause,
                "action": act,
                "action_by_cause": act_by_cause,
                "at_cap_pct": 100.0 * at_cap / sim_rows,
            }
    return {"cells": cells, "unknown_rules": sorted(unknown_rules)}


def is_pure(cell: dict, arm: str) -> bool:
    """Does this (model, arm) cell keep the two rule layers disjoint?

    Single definition, used by BOTH the panel-B table and the caption's count.
    They were separate expressions until 2026-08-03, and the caption's was a
    hardcoded ``len(IRRIGATION_MODELS)*2``, so the caption read "10 of 10 cells
    pure" while the table beside it printed ``pure? False``. A caption may not
    be able to disagree with its own figure.
    """
    cz = cell["cause"]
    if arm == "noval":
        return cz[C_PRECOND] == cell["rejected"]
    return cz[C_PRECOND] == 0 and cell["rejected"] > 0


def n_pure_cells(cells: dict) -> tuple[int, int]:
    """(cells passing ``is_pure``, cells examined) over all irrigation models."""
    flags = [is_pure(cells[(m.label, arm)], arm)
             for m in D.IRRIGATION_MODELS for arm in ("gov", "noval")]
    return sum(flags), len(flags)


def pooled_by_cause(cells: dict) -> dict:
    """(arm, cause) -> (proposed-action tally, n rejections), five models pooled.

    Straight sums over the five irrigation models of the per-cell
    ``action_by_cause`` tallies, so the denominator of each row is the number of
    rejections that cause produced -- never a share of anything else.
    """
    out = {}
    for arm in D.ARMS:
        for cause in REJECTION_CAUSES:
            tot = {k: 0 for k in ACTION_ORDER}
            for m in D.IRRIGATION_MODELS:
                for k in ACTION_ORDER:
                    tot[k] += cells[(m.label, arm)]["action_by_cause"][cause][k]
            out[(arm, cause)] = (tot, sum(tot.values()))
    return out


# =============================================================================
# Verification -- the falsifiers from the docstring, as a gate
# =============================================================================
def _verify(data: dict) -> list[str]:
    fail = []
    cells = data["cells"]

    if data["unknown_rules"]:
        fail.append(
            "rule names appear in failed_rules that are in neither taxonomy list, so "
            "the appraisal/world split is incomplete: " + ", ".join(data["unknown_rules"])
        )

    for (model, arm), c in sorted(cells.items()):
        pre = c["cause"][C_PRECOND]
        theory = c["cause"][C_APPRAISAL] + c["cause"][C_WORLDRULE]
        if arm == "noval":
            if theory:
                fail.append(f"{model} no-validator: {theory} rejections name a behavioural "
                            f"rule; the two layers are NOT disjoint")
            if pre != c["rejected"]:
                fail.append(f"{model} no-validator: {c['rejected'] - pre} rejections are "
                            f"not the precondition")
            if c["action"][A_DECREASE]:
                fail.append(f"{model} no-validator: {c['action'][A_DECREASE]} rejections "
                            f"are DECREASE proposals; the world layer is not "
                            f"increase-only (claim (c) broken)")
        else:
            if pre:
                fail.append(f"{model} with-validators: {pre} rejections recorded as a bare "
                            f"precondition failure; layers not separable by cause")
            if theory != c["rejected"]:
                fail.append(f"{model} with-validators: {c['rejected'] - theory} rejections "
                            f"name no rule")

    # anchor counts against the brief
    for arm, exp_rej, exp_tot in (("noval", 4757, 16380), ("gov", 6469, 16380)):
        c = cells[("gemma3:4b", arm)]
        if (c["rejected"], c["total"]) != (exp_rej, exp_tot):
            fail.append(
                f"ANCHOR MISMATCH vs brief -- {D.ARM_DISPLAY[arm]}: computed "
                f"{c['rejected']}/{c['total']}, brief says {exp_rej}/{exp_tot}"
            )
    return fail


# =============================================================================
# Plot
# =============================================================================
def _style() -> None:
    """Shared typeface + size hierarchy, plus the three settings local to this
    figure. ``FS.apply`` runs the font and glyph guards before it sets anything,
    so a machine without Times New Roman stops here rather than rendering the
    figure in whatever matplotlib silently fell back to."""
    FS.apply(
        # Local, and genuinely local: this is the only one of the three figures
        # drawn from hatched stacked bars, and the only one that suppresses its
        # y ticks in favour of text row labels.
        **{
            "xtick.major.size": 2.5,
            "ytick.major.size": 0,
            "hatch.linewidth": 0.45,
        }
    )


def _pct_label(w: float, label_decimals: int) -> str:
    """Percent label for one segment.

    One decimal, except where one decimal would round to a flat 0.0% or 100.0%
    and so read as exact when it is not -- there the second decimal is spent.
    Panel C is the case that needs it (99.95% is the whole point of that row);
    everywhere else the shorter label is what fits inside a segment on a 5.5 in
    canvas, and the CSV carries four decimals regardless.
    """
    if label_decimals >= 2 and 0.0 < w < 100.0 and round(w, 1) in (0.0, 100.0):
        return f"{w:.2f}%"
    return f"{w:.1f}%"


#: Display-pixel slack. Two boxes that share an edge are not a collision; a box
#: that eats 1 px into its neighbour is not what a reader sees as "overlapping".
#: Everything beyond this is reported.
_COLLIDE_EPS = 1.0


def _shrink(box, eps: float = _COLLIDE_EPS):
    """``box`` pulled in by ``eps`` px on every side (never past degenerate)."""
    e = min(eps, box.width / 2.0 - 1e-6, box.height / 2.0 - 1e-6)
    if e <= 0:
        return box
    return Bbox.from_extents(box.x0 + e, box.y0 + e, box.x1 - e, box.y1 - e)


def _layout_collisions(fig) -> list[tuple[str, str, str]]:
    """Every collision a reader would see, as ``(kind, what, what it hit)``.

    Four kinds, not one. The pairwise Text-vs-Text test that this check used to
    be is necessary but nowhere near sufficient -- the collisions the author was
    actually looking at were a label sitting on a legend, a label crossing an
    axes frame, and one panel's label running into the panel beside it, none of
    which involve two Text artists at all. So:

      1. ``text/text``    two rendered strings overlap;
      2. ``text/legend``  a string that is not part of a legend overlaps that
                          legend's frame (which is why the legend now lives
                          outside every panel, at the top);
      3. ``text/spine``   a string crosses a visible axes spine;
      4. ``text/axes``    a string overlaps the plotting area of an axes it does
                          NOT belong to -- panel b's x-label reaching into panel
                          c, panel c's row labels reaching back into panel b.

    A Text is exempt from (4) for its OWN axes, since axis labels, titles and
    in-bar percent labels legitimately sit on or beside their own panel.
    """
    fig.canvas.draw()
    r = fig.canvas.get_renderer()

    texts = []
    for t in fig.findobj(match=Text):
        label = t.get_text()
        if not label or not label.strip() or not t.get_visible():
            continue
        box = t.get_window_extent(r)
        if box.width <= 0 or box.height <= 0:
            continue
        texts.append((label.replace("\n", " / "), t, _shrink(box)))

    issues: list[tuple[str, str, str]] = []

    # 1. text vs text
    for (la, _ta, ba), (lb, _tb, bb) in itertools.combinations(texts, 2):
        if ba.overlaps(bb):
            issues.append(("text/text", la, lb))

    # 2. text vs legend frame
    legends = list(fig.legends)
    for ax in fig.axes:
        if ax.get_legend() is not None:
            legends.append(ax.get_legend())
    for lg in legends:
        own = set(lg.get_texts())
        if lg.get_title() is not None and lg.get_title().get_text().strip():
            own.add(lg.get_title())
        frame = _shrink(lg.get_window_extent(r))
        for la, ta, ba in texts:
            if ta in own:
                continue
            if frame.overlaps(ba):
                issues.append(("text/legend", la, "<legend frame>"))

    # 3. text vs a visible axes spine
    for ax_i, ax in enumerate(fig.axes):
        for name, sp in ax.spines.items():
            if not sp.get_visible():
                continue
            sb = _shrink(sp.get_window_extent(r), 0.5)
            for la, ta, ba in texts:
                if ba.overlaps(sb):
                    issues.append(("text/spine", la, f"axes{ax_i}:{name} spine"))

    # 4. text vs a FOREIGN axes' plotting area
    for ax_i, ax in enumerate(fig.axes):
        ab = _shrink(ax.patch.get_window_extent(r), 2.0)
        for la, ta, ba in texts:
            if ta.axes is ax:
                continue
            if ab.overlaps(ba):
                issues.append(("text/axes", la, f"axes{ax_i} plotting area"))

    # 5. anything running off the canvas. A legend wide enough to be CLIPPED at
    #    the figure edge reads exactly like a collision to the author -- the
    #    label is destroyed either way -- and the four tests above cannot see it,
    #    because a clipped artist overlaps nothing. Caught here instead: the
    #    2026-08-03 first attempt at the top legend was 5.94 in wide on a 5.5 in
    #    canvas and lost the last entry, and every test above still reported 0.
    canvas = fig.bbox
    for la, _ta, ba in texts:
        if not canvas.containsx(ba.x0) or not canvas.containsx(ba.x1) \
                or not canvas.containsy(ba.y0) or not canvas.containsy(ba.y1):
            issues.append(("off-canvas", la, "<figure edge>"))
    for lg_i, lg in enumerate(legends):
        fb = lg.get_window_extent(r)
        if not canvas.containsx(fb.x0) or not canvas.containsx(fb.x1) \
                or not canvas.containsy(fb.y0) or not canvas.containsy(fb.y1):
            issues.append(("off-canvas", f"<legend {lg_i} frame>", "<figure edge>"))

    return issues


def _assert_no_text_overlaps(fig) -> None:
    issues = _layout_collisions(fig)
    kinds = ("text/text", "text/legend", "text/spine", "text/axes", "off-canvas")
    per = {k: sum(1 for i in issues if i[0] == k) for k in kinds}
    print(f"TEXT OVERLAP CHECK: {len(issues)}"
          + "   (" + ", ".join(f"{k}={per[k]}" for k in kinds) + ")")
    if issues:
        for kind, a, b in issues:
            print(f"  !! [{kind}] {a}  <->  {b}")
        raise RuntimeError("rendered layout collides")


def _stack(ax, y, height, segments, denom, *, order, label_min_pct,
           fontsize=FS.FS_ANNOT,
           label_decimals=1, show_labels=True, label_keys=None):
    """Draw one horizontal 100%-stacked bar, labelled with PERCENT only.

    Labels go INSIDE the segments so nothing can be clipped at the axes edge.
    ``label_decimals`` is the MAXIMUM precision; see ``_pct_label``.

    ``label_keys``, when given, restricts labelling to those categories, so a
    row cannot end up printing two numbers where its neighbours print one. It
    changes nothing that is drawn or written to the CSV -- every segment is
    still plotted at its computed width and still recorded -- only which of
    them carries a printed percent.
    """
    left = 0.0
    drawn = []
    for k in order:
        v = segments.get(k, 0)
        if v <= 0:
            continue
        w = 100.0 * v / denom
        ax.barh(y, w, left=left, height=height, color=COLOUR[k], hatch=HATCH[k],
                edgecolor="#333333", linewidth=0.5, zorder=3)
        if show_labels and w >= label_min_pct and (label_keys is None or k in label_keys):
            # A number printed ON a coloured field always sits in an OPAQUE
            # WHITE box with a thin border, whatever the fill under it. That is
            # the reference figure's treatment, and it is also what makes the
            # value legible on the dark segments -- white type on #4D4D4D under
            # a hatch was the worst-reading text on the old figure. One rule for
            # every segment, so a reader never has to work out why this label is
            # styled differently from that one.
            ax.text(left + w / 2.0, y, _pct_label(w, label_decimals),
                    ha="center",
                    va="center", fontsize=fontsize, zorder=5, linespacing=1.15,
                    color="#111111",
                    bbox=dict(boxstyle="round,pad=0.24", linewidth=0.5,
                              facecolor="white", edgecolor="#555555"))
        drawn.append((k, left, w, v))
        left += w
    return drawn


#: Panel-title type. The reference figure sets panel titles BOLD and CENTRED
#: over their own panel, with the panel letter as a separate bold glyph out in
#: the margin, and puts nothing else near either. Both are done here. The two
#: sizes are the shared hierarchy's, not this file's.
TITLE_FS = FS.FS_PANEL_TITLE
LETTER_FS = FS.FS_PANEL_LETTER
TITLE_PAD_PT = 5.0


def _panel_letter(ax, letter: str, n_title_lines: int = 1) -> None:
    """Bold panel letter in the left margin, aligned with the title's TOP line.

    Placed by annotation offset rather than by a figure coordinate so it tracks
    the axes if the gridspec changes. It is offset far enough left that it sits
    clear of the tick-label gutter, and it is anchored to the top line of a
    multi-line title (matplotlib grows a title upward from its pad, so a naive
    va="bottom" would align it with the LAST line).
    """
    ax.annotate(
        letter, xy=(0.0, 1.0), xycoords="axes fraction",
        xytext=(-10.0, TITLE_PAD_PT + (n_title_lines - 1) * TITLE_FS * 1.22),
        textcoords="offset points", ha="right", va="bottom",
        fontsize=LETTER_FS, fontweight="bold", annotation_clip=False,
    )


def build_figure(data: dict) -> tuple:
    _style()
    cells = data["cells"]
    plotted = []          # rows for the audit csv

    # SINGLE-column width: the venue's text block is 5.5 in (neurips_2026.sty).
    # The manuscript includes this at 0.80\linewidth, so MIN_FONT is chosen to
    # clear the 7 pt printed floor after that scale factor.
    #
    # THE 2026-08-03 DECROWDING PASS -- what changed and why.
    # The figure was rejected for crowding, and the diagnosis was structural
    # rather than a matter of a few points of padding:
    #
    #   * there were TWO legends, both DOWN IN THE PLOT REGION -- one at the
    #     bottom left under panel b, one at the bottom right under panel c. They
    #     competed with the panels for the same band of page, and having two of
    #     them meant a reader had to work out which key applied to which panel
    #     from their positions. There is now ONE boxed legend, at the very top,
    #     outside every panel, spanning the full figure width, carrying both
    #     vocabularies as two labelled rows. Same seven entries, nothing
    #     dropped; the grouping that used to be carried by "which corner is it
    #     in" is now carried by a row label, which is stateable.
    #   * panels b and c had a 0.86 gutter that panel c's two-line row labels
    #     ate entirely, so those labels ran up against panel b's bars and panel
    #     b's x-label ran under panel c. The gutter is now 1.16 with panel b
    #     widened, so panel b's x-label fits over its own axes and panel c's row
    #     labels have clear air on both sides. The strengthened collision check
    #     (kind ``text/axes``) is what holds this: it fails if either panel's
    #     text reaches the other panel's plotting area at all.
    #   * panel titles were left-aligned with the letter inside them, so a long
    #     title started under its own panel and ended over its neighbour's.
    #     They are now bold and CENTRED over their own panel, with the letter
    #     out in the margin.
    #
    # Height goes 4.05 -> 4.55 in to pay for the legend band and the row
    # spacing. The three matplotlib figures' budget is 12.5 in and they were
    # 11.10 in, so this spends 0.50 of the 1.40 in of slack.
    #
    # Panel C is the WIDE column here, not the narrow one, which is the reverse
    # of the old 6.8 in layout. Its segment labels are the smallest thing on the
    # figure: at 7 pt "99.95%" is ~0.37 in, so the segment carrying it has to be
    # at least that wide, and the narrowest segment panel C now labels is the
    # 48.53% increase share of the world-rule row.
    FS.assert_print_floor()
    # Height 4.55 -> 4.40 in on 2026-08-04 to repay the page budget. Measured:
    # 4.40 is the largest height at which the manuscript body ends by page 8,
    # and this figure was the cheapest of the four to take it from (8.6 pt of
    # placed height, 3.3% of its own). Nothing was cut from the paper to buy
    # this. _assert_no_text_overlaps below re-verifies at the new height; the
    # guard first fires at 4.20, so 4.40 is not sitting on the boundary.
    #
    # THEN 4.40 -> 4.80 in, LATER THE SAME DAY, TO PAY FOR THE PLAIN LABELS.
    # Every visible string on this figure was rewritten out of the codebase's
    # vocabulary and into the vocabulary of the thing measured, and the plain
    # words are longer than the jargon they replace ("rule reading what it said"
    # against "appraisal rule"). The instruction that came with the rewrite was
    # explicit that room is bought with canvas and never with type: the 7 pt
    # printed floor is hard and FS.assert_print_floor() above still holds it.
    # Two structural costs, both measured rather than guessed:
    #   * the legend goes from two rows to THREE (+0.21 in). Laid out flat it is
    #     6.96 in wide on a 5.5 in canvas -- the seven category names alone are
    #     5.26 in of type -- so it cannot stay two rows at any padding.
    #   * panel b's title goes from three lines to four (+0.16 in), because
    #     "validators on above, off below" is 1.73 in and the panel is 1.45 in;
    #     set on one line it overhangs its own panel letter.
    # The three matplotlib figures' shared budget is 12.5 in; at 4.80 + 4.15 +
    # 3.55 they now come to exactly 12.50, so nothing further may be spent here
    # without taking it from fig2 or fig3.
    fig = plt.figure(figsize=(5.5, 4.80))
    gs = fig.add_gridspec(
        2, 2, height_ratios=[1.00, 1.34], width_ratios=[1.45, 1.47],
        hspace=0.86, wspace=0.89, left=0.205, right=0.972, top=0.812, bottom=0.132,
    )
    # WIDTH_RATIOS AND WSPACE ARE SET BY PANEL C'S ROW LABELS, NOT BY THE BARS.
    # Those labels now carry the legend's full words ("rule reading what it
    # said", 1.18 in at the tick size), and they have to fit on one line or the
    # three-line block they would otherwise become is taller than panel c's row
    # pitch. So the b/c gutter is 1.30 in rather than 1.10, and panel b gives up
    # the width: 1.45 in against panel c's 1.47. Panel b still clears its own
    # content -- its widest x tick label is "80" and its x-label
    # "decisions blocked (%)" is 1.17 in -- and panel c's narrowest LABELLED
    # segment (48.53%) is 0.71 in against a 0.37 in "99.95%" box.
    # Nothing here is asserted by arithmetic; ``_layout_collisions`` kinds
    # ``text/axes`` and ``off-canvas`` are what actually hold it.
    axA = fig.add_subplot(gs[0, :])
    axB = fig.add_subplot(gs[1, 0])
    axC = fig.add_subplot(gs[1, 1])

    # ---------------- Panel A: anchor cell, full decomposition ---------------
    # TWO ARMS and ONE BREAKDOWN OF ONE OF THEM -- not three arms. The top and
    # bottom rows are the two arms over ALL decisions, and the first thing the
    # panel has to show is that their rejections have disjoint causes: yellow
    # (world-feasibility precondition) in one, green/purple (named behavioural
    # rules) in the other, no overlap.
    #
    # The middle row RE-BASES the with-validators row's own rejections on their
    # own total (6,469) so the within-stack split reads 59.4% / 40.6% on the
    # page instead of only as 23.4% / 16.1% of all decisions. It is a breakdown
    # of the row above it, not a third condition, and the panel is drawn so that
    # this is geometry rather than something the reader is told:
    #
    #   * it is INDENTED -- its label is much shorter than either arm name, and
    #     the tick labels are right-aligned, so its text block starts well to
    #     the right of "with-validators" and "no-validator";
    #   * it is THINNER than the two arm bars (0.28 against 0.52);
    #   * it is set in italic grey against the arms' upright black;
    #   * a RULE runs under it, so the panel divides into a with-validators
    #     block of two rows and a no-validator row, not into three peers;
    #   * and its label reads "of which, rejected", which is subordinate
    #     language and completes the row above it as a sentence.
    #
    # The middle row is a re-based subset rather than a third arm. Its row label
    # states that relationship and prints the computed count directly; an arrow
    # was rejected because it collided with the percentage labels at the
    # manuscript's placed size and introduced a second visual encoding.
    #
    # Two different denominators in one panel, so each row states its own n and
    # the x-label says which row a percentage is a share OF.
    axA.set_title("Anchor cell: the validator changes the blocking cause",
                  loc="center", fontweight="bold", pad=TITLE_PAD_PT)
    _panel_letter(axA, "a", 1)
    g_anchor = cells[("gemma3:4b", "gov")]
    # Row positions opened up in the 2026-08-03 pass: the two-line italic
    # "of which, rejected" label used to sit hard against the bar above it and
    # against the separating rule below it.
    Y_PARENT, Y_CHILD, Y_NOVAL = 2.16, 1.30, 0.14
    H_ARM, H_CHILD = 0.50, 0.26
    labA = []
    for i, arm in enumerate(("gov", "noval")):
        c = cells[("gemma3:4b", arm)]
        y = Y_PARENT if arm == "gov" else Y_NOVAL
        segs = _stack(axA, y, H_ARM, c["cause"], c["total"],
                      order=CAUSE_ORDER, label_min_pct=7.0, show_labels=True)
        for k, left, w, v in segs:
            plotted.append(dict(panel="a", model="gemma3:4b", arm=D.ARM_DISPLAY[arm],
                                n_seeds=c["n_seeds"], basis="all decisions",
                                category=k, count=v, denominator=c["total"],
                                percent=round(w, 4)))
        labA.append(D.ARM_DISPLAY[arm])

    # the re-based row -- WITHIN-STACK, same arm, same runs, only rule kind differs
    segs = _stack(axA, Y_CHILD, H_CHILD,
                  {k: g_anchor["cause"][k] for k in RULE_KINDS},
                  g_anchor["rejected"], order=RULE_KINDS, label_min_pct=7.0,
                  show_labels=True)
    for k, left, w, v in segs:
        plotted.append(dict(panel="a", model="gemma3:4b",
                            arm=D.ARM_DISPLAY["gov"], n_seeds=g_anchor["n_seeds"],
                            basis="with-validators rejections (re-based)",
                            category=k, count=v, denominator=g_anchor["rejected"],
                            percent=round(w, 4)))
    labA = [
        "with validators\nall decisions",
        f"blocked subset\n(n={g_anchor['rejected']:,}; re-based)",
        "without validators\nall decisions",
    ]
    axA.set_yticks([Y_PARENT, Y_CHILD, Y_NOVAL])
    axA.set_yticklabels(labA)
    # the breakdown row's label is set off from the two arm labels
    axA.get_yticklabels()[1].set_style("italic")
    axA.get_yticklabels()[1].set_color("#444444")
    # the rule: with-validators block above, the other arm below. Drawn past the
    # axes into the label gutter so it separates the row NAMES too, which is
    # where "three peers" was being read.
    y_rule = (Y_CHILD - H_CHILD / 2.0 + Y_NOVAL + H_ARM / 2.0) / 2.0
    # -25 rather than -22 axis units: the rule has to run past the row NAMES,
    # and the longest of them is now "the blocked ones" (0.82 in) where it used
    # to be "with-validators" (0.79 in).
    axA.plot([-25.0, 100.0], [y_rule, y_rule], color="#B5B5B5", linewidth=0.6,
             clip_on=False, zorder=2)
    axA.set_xlim(0, 100)
    axA.set_xticks([0, 20, 40, 60, 80, 100])
    axA.set_xlabel("share of each row (%)", labelpad=3.0)
    axA.set_ylim(-0.32, 2.62)

    # ---------------- Panel B: per-model, rejections only --------------------
    # The title is CENTRED over panel b and wrapped, so it cannot start under
    # its own panel and end over panel c the way the old left-aligned title did.
    # WHICH BAR IS WHICH ARM. Every model contributes two bars, drawn in the
    # same order throughout -- upper = validators ON, lower = OFF -- and nothing
    # in a bar states its arm: the cause colours are a CONSEQUENCE of the arm,
    # not a name for it, so a reader made to infer the condition from the
    # palette is being asked to assume the panel's own finding. The pair spacing
    # is 0.24 in per model, less than two lines of type, so a per-bar label in
    # the tick gutter cannot be set at the 7 pt printed floor and a per-bar tag
    # at the bar ends collides in the anchor row (29.0% and 39.5% are 0.14 in
    # apart). The order is therefore declared once, in the LOWER HALF OF THE
    # PANEL TITLE, which costs zero extra text elements and covers all five
    # models rather than one. "validators on / off" is the vocabulary panel c's
    # row labels now use, so the two agree word for word.
    #
    # THREE LINES: the title states the measured quantity and the bar order
    # without using a conversational question.
    axB.set_title("Blocked decisions by model\nvalidators on above,\noff below",
                  loc="center", fontweight="bold", pad=TITLE_PAD_PT)
    _panel_letter(axB, "b", 3)
    ytick_pos, ytick_lab = [], []
    y = 0.0
    for m in reversed(D.IRRIGATION_MODELS):        # anchor ends up on top
        pair_y = []
        pair_rate = {}
        for arm in ("noval", "gov"):
            c = cells[(m.label, arm)]
            left = 0.0
            for k in (C_PRECOND, C_APPRAISAL, C_WORLDRULE):
                v = c["cause"][k]
                if v <= 0:
                    continue
                w = 100.0 * v / c["total"]
                axB.barh(y, w, left=left, height=0.34, color=COLOUR[k], hatch=HATCH[k],
                         edgecolor="#333333", linewidth=0.5, zorder=3)
                plotted.append(dict(panel="b", model=m.label, arm=D.ARM_DISPLAY[arm],
                                    n_seeds=c["n_seeds"], basis="all decisions",
                                    category=k, count=v, denominator=c["total"],
                                    percent=round(w, 4)))
                left += w
            rate = 100.0 * c["rejected"] / c["total"]
            pair_rate[arm] = rate
            pair_y.append(y)
            y += 0.52
        lab = m.label + ("*" if D.excluded_from_paired(m.prefix) else "")
        ytick_pos.append(sum(pair_y) / 2.0)
        ytick_lab.append(lab)
        y += 0.46
    axB.set_yticks(ytick_pos)
    axB.set_yticklabels(ytick_lab)
    axB.set_ylim(-0.42, y - 0.42)
    axB.set_xlim(0, 82)
    axB.set_xticks([0, 40, 80])
    axB.set_xlabel("decisions blocked (%)", labelpad=3.0)


    # ---------------- Panel C: what each RULE KIND blocks ---------------------
    # The top two rows are the within-stack contrast: both are the SAME arm and
    # the SAME runs, and the only thing that changes between them is which kind
    # of validator rule fired. The third row is the other layer, in the other
    # arm, and is the only cross-arm comparison on this panel.
    axC.set_title("Proposed actions among\nblocked decisions",
                  loc="center", fontweight="bold", pad=TITLE_PAD_PT)
    _panel_letter(axC, "c", 2)
    labC = []
    pooled_c = pooled_by_cause(cells)
    n_rows = len(PANEL_C_ROWS)
    for i, (arm, cause, lab) in enumerate(PANEL_C_ROWS):
        tot_act, n_rej = pooled_c[(arm, cause)]
        y = n_rows - 1 - i
        # ONE NUMBER PER ROW, and the same one in every row: the share of that
        # cause's rejections that proposed an INCREASE. That is the quantity the
        # panel exists to compare, the rows are 100%-stacked so the remainder is
        # readable straight off the bar, and restricting the label this way is
        # what stops the world-rule row printing two numbers (48.5% increase AND
        # 51.0% decrease) where its neighbours print one. Nothing about what is
        # drawn or recorded changes; the decrease and unparsed segments are
        # plotted at full width and written to the CSV exactly as before.
        segs = _stack(axC, y, 0.52, tot_act, n_rej, order=ACTION_ORDER,
                      label_min_pct=48.0, label_decimals=2, fontsize=FS.FS_ANNOT,
                      label_keys={A_INCREASE})
        for k, left, w, v in segs:
            plotted.append(dict(panel="c", model="all five pooled",
                                arm=D.ARM_DISPLAY[arm], n_seeds=0,
                                basis=f"rejections caused by: {cause}",
                                category=k, count=v,
                                denominator=n_rej, percent=round(w, 4)))
        labC.append(lab)
    axC.set_yticks(list(range(n_rows - 1, -1, -1)))
    axC.set_yticklabels(labC, fontsize=FS.FS_TICK)
    axC.set_xlim(0, 105)
    axC.set_xticks([0, 50, 100])
    axC.set_xlabel("share of those blocks (%)", labelpad=3.0)
    axC.set_ylim(-0.62, n_rows - 1 + 0.62)

    for ax in (axA, axB, axC):
        ax.xaxis.grid(True, color="#DDDDDD", linewidth=0.4, zorder=0)
        ax.set_axisbelow(True)

    # ---------------- the legend ---------------------------------------------
    # ONE BOX, AT THE TOP, OUTSIDE EVERY PANEL, SPANNING THE FULL WIDTH.
    #
    # The figure uses two vocabularies -- a CAUSE vocabulary in panels a and b,
    # an ACTION vocabulary in panel c -- and it used to carry one unframed key
    # for each, dropped into opposite bottom corners of the plot region. That
    # put two blocks of type inside the panels' own band of page and left the
    # correspondence ("which key goes with which panel?") to be inferred from
    # position. Here they are one framed box with two labelled rows, so the
    # correspondence is written down and the plot region is given back.
    #
    # Matplotlib fills a legend COLUMN-major, so the handle list below is
    # interleaved (row 1 entry, row 2 entry, row 1 entry, ...) to come out as
    # two readable rows of a 5-column grid. The two group labels are the first
    # column, carried by an invisible handle so their text lines up with the
    # swatches beside them.
    def _swatch(k):
        return Patch(facecolor=COLOUR[k], hatch=HATCH[k], edgecolor="#333333",
                     linewidth=0.5, label=LEGEND_LABEL[k])

    def _group(text):
        return Patch(facecolor="none", edgecolor="none", linewidth=0, label=text)

    # THREE ROWS, not two, and the arrangement is measured rather than chosen.
    #
    # The group labels used to be "cause (a, b)" / "action (c)" -- the words the
    # panel titles and the axis labels used. Those words are gone: they name the
    # figure's machinery rather than what the reader is looking at, and a reader
    # who does not already know what "cause" means here learns nothing from
    # seeing it twice. The heads now ask the two questions the two vocabularies
    # answer, "why it was blocked" and "what it wanted", and every category name
    # under them is a plain phrase instead of a code identifier.
    #
    # THAT COSTS WIDTH, AND THE WIDTH IS WHAT SETS THE SHAPE. The seven category
    # names plus the two heads are 5.26 in of type; laid out as the old two-row,
    # five-column grid the box measures 6.96 in on a 5.5 in canvas, i.e. an inch
    # and a half off the page. Three rows of four columns fit -- but only for
    # ONE assignment of labels to columns, because a column is as wide as its
    # widest member. Pairing the two longest names ("rule reading what it said",
    # "rule reading the world") into a SINGLE column and letting the four short
    # ones share the other two brings the label total to 4.24 in and the box to
    # about 5.42 in. Matplotlib fills column-major, so the handle list below is
    # written column by column, and the layout it produces is
    #
    #   blocking cause (a, b) | passed          | rule reads self-report |
    #                         | water-right cap | rule reads world state |
    #   proposed action (c)   | proposed increase | proposed decrease | unparsed proposal
    #
    # -- the blocking vocabulary in the first two rows under its own head, the
    # action vocabulary in the third under its own. The blank in the first
    # column's middle slot is an invisible handle carrying an empty label, which
    # is what holds the grid open; the collision check treats it as absent
    # because it has no text.
    #
    # Nothing was dropped in the reshape: seven categories and two heads before,
    # seven categories and two heads after. Do not re-tighten this back to two
    # rows -- the off-canvas test in ``_layout_collisions`` is what catches it,
    # and it caught exactly this on 2026-08-03 when the box was 5.94 in wide and
    # every other test still reported a clean figure.
    handles = [
        _group("blocking cause  (a, b)"), _group(""), _group("proposed action  (c)"),
        _swatch(C_APPROVED),   _swatch(C_PRECOND),     _swatch(A_INCREASE),
        _swatch(C_APPRAISAL),  _swatch(C_WORLDRULE),   _swatch(A_DECREASE),
        _group(""),            _group(""),             _swatch(A_OTHER),
    ]
    leg = fig.legend(
        handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.996), ncol=4,
        frameon=True, fancybox=False, edgecolor="#333333", facecolor="white",
        borderpad=0.50, handlelength=1.10, handleheight=0.85, columnspacing=0.75,
        labelspacing=0.38, handletextpad=0.38, borderaxespad=0.0, alignment="left",
    )
    leg.get_frame().set_linewidth(0.6)
    # the two group heads are set off from the seven category names
    for t in leg.get_texts():
        if t.get_text().startswith(("blocking cause", "proposed action")):
            t.set_fontweight("bold")
    return fig, plotted


# =============================================================================
# Main
# =============================================================================
def main() -> int:
    print("=" * 100)
    print("FIG 1 -- THE TWO RULE LAYERS SEPARATE")
    print("=" * 100)
    print(f"sign convention (not used in this figure): {D.DELTA_LABEL}")
    print("basis: POOLED COUNT DECOMPOSITION across seeds; no paired contrast, no CI, no p.")
    print()

    data = collect()
    cells = data["cells"]

    # ---- verification gate --------------------------------------------------
    print("-" * 100)
    print("VERIFICATION (each of these would falsify the figure; see module docstring)")
    print("-" * 100)
    fails = _verify(data)
    if fails:
        for f in fails:
            print("  !! FALSIFIED:", f)
    else:
        _np, _ne = n_pure_cells(cells)
        print(f"  {_np}/{_ne} irrigation cells pure: no-validator rejections name ZERO behavioural")
        print("  rules; with-validators rejections are ZERO bare precondition failures.")
        print("  No no-validator rejection is a decrease proposal.")
        print("  Anchor counts match the brief exactly (4,757/16,380 and 6,469/16,380).")
        print("  Every rule name seen in failed_rules is covered by the rule taxonomy, so")
        print("  the appraisal-conditioned / world-conditioned split is exhaustive.")
    print()

    # ---- plotted values -----------------------------------------------------
    print("-" * 100)
    print("PANEL A -- anchor cell gemma3:4b, 5 seeds, all decisions")
    print("-" * 100)
    print(f"  {'arm':17s} {'total':>7s} {'approved':>10s} {'precond':>9s} "
          f"{'rule:appr':>10s} {'rule:world':>11s} {'rejected':>9s} {'rej%':>6s}")
    for arm in ("gov", "noval"):
        c = cells[("gemma3:4b", arm)]
        cz = c["cause"]
        print(f"  {D.ARM_DISPLAY[arm]:17s} {c['total']:>7,d} {cz[C_APPROVED]:>10,d} "
              f"{cz[C_PRECOND]:>9,d} {cz[C_APPRAISAL]:>10,d} {cz[C_WORLDRULE]:>11,d} "
              f"{c['rejected']:>9,d} {100*c['rejected']/c['total']:>6.1f}")
    g = cells[("gemma3:4b", "gov")]
    print(f"  -> of the {g['rejected']:,} with-validators rejections, "
          f"{g['cause'][C_APPRAISAL]:,} "
          f"({100*g['cause'][C_APPRAISAL]/g['rejected']:.1f}%) name at least one rule whose")
    print("     antecedent is the agent's SELF-REPORTED appraisal (WSA_LABEL / ACA_LABEL);")
    print(f"     the other {g['cause'][C_WORLDRULE]:,} "
          f"({100*g['cause'][C_WORLDRULE]/g['rejected']:.1f}%) name only world-conditioned "
          f"validator rules.")
    print("  -> THIS re-based pair, not the 23.4% / 16.1% those same counts are OF ALL")
    print("     DECISIONS, is the split the 2026-07-31 correction was about, and it is")
    print("     drawn as panel A's middle bar so it is on the page and not only here.")
    print()

    print("-" * 100)
    print("PANEL B -- all five irrigation models")
    print("-" * 100)
    print(f"  {'model':14s} {'arm':17s} {'n':>2s} {'total':>7s} {'rejected':>9s} "
          f"{'rej%':>6s} {'precond':>9s} {'rule:appr':>10s} {'rule:world':>11s} {'pure?':>6s}")
    for m in D.IRRIGATION_MODELS:
        for arm in ("gov", "noval"):
            c = cells[(m.label, arm)]
            cz = c["cause"]
            pure = is_pure(c, arm)
            star = "*" if D.excluded_from_paired(m.prefix) else " "
            print(f"  {m.label + star:14s} {D.ARM_DISPLAY[arm]:17s} {c['n_seeds']:>2d} "
                  f"{c['total']:>7,d} {c['rejected']:>9,d} "
                  f"{100*c['rejected']/c['total']:>6.1f} {cz[C_PRECOND]:>9,d} "
                  f"{cz[C_APPRAISAL]:>10,d} {cz[C_WORLDRULE]:>11,d} {str(pure):>6s}")
    print()

    print("-" * 100)
    print("PANEL C -- proposed action of rejected decisions, BY RULE KIND")
    print("           (all five irrigation models pooled)")
    print("-" * 100)
    print("  The first two rows are the WITHIN-STACK contrast: same arm, same runs,")
    print("  same decisions -- only the kind of validator rule that fired differs.")
    print("  The third row is the other layer in the other arm.")
    print()
    pooled_c = pooled_by_cause(cells)
    print(f"  {'arm':17s} {'cause':42s} {'n rej':>7s} {'increase':>9s} "
          f"{'decrease':>9s} {'unparsed':>9s} {'increase%':>10s}")
    for arm, cause, _lab in PANEL_C_ROWS:
        tot, n = pooled_c[(arm, cause)]
        print(f"  {D.ARM_DISPLAY[arm]:17s} {cause:42s} {n:>7,d} "
              f"{tot[A_INCREASE]:>9,d} {tot[A_DECREASE]:>9,d} {tot[A_OTHER]:>9,d} "
              f"{100*tot[A_INCREASE]/n:>9.2f}%")
    ap_tot, ap_n = pooled_c[("gov", C_APPRAISAL)]
    wr_tot, wr_n = pooled_c[("gov", C_WORLDRULE)]
    print(f"  -> pooled within-stack split: {ap_n:,} appraisal-conditioned "
          f"({100*ap_n/(ap_n+wr_n):.1f}%) vs")
    print(f"     {wr_n:,} world-conditioned-only ({100*wr_n/(ap_n+wr_n):.1f}%) of "
          f"{ap_n+wr_n:,} with-validators rejections.")
    print("     NOT the same number as panel A's 59.4 / 40.6, which is the ANCHOR CELL")
    print("     alone (6,469 rejections). Different corpus, different denominator.")
    print("  -> the two rule kinds do NOT block the same thing: the appraisal-conditioned")
    print("     rules block increases on "
          f"{100*ap_tot[A_INCREASE]/ap_n:.2f}% of their rejections, the "
          f"world-conditioned-only")
    print(f"     rules on {100*wr_tot[A_INCREASE]/wr_n:.2f}%, and only the world-feasibility")
    print("     precondition is essentially increase-exclusive.")
    print("  Structural reason, read from examples/irrigation_abm/config/skill_registry.yaml:")
    print("  the precondition 'not at_allocation_cap' is attached to increase_large and")
    print("  increase_small and to NO other skill, so the world layer CANNOT block anything")
    print("  else. The unparsed no-validator rows are REJECTED_FALLBACK rows whose")
    print("  error_messages still read the allocation-cap precondition.")
    print()

    print("-" * 100)
    print("SUPPORTING (not plotted): how often an agent actually sits at its water right")
    print("-" * 100)
    print("  share of agent-years with request >= 99% of water_right, from simulation_log.csv.")
    print("  Indicative of cap proximity; it is not a re-evaluation of the precondition.")
    print(f"  {'model':14s} {'with-validators':>16s} {'no-validator':>14s}")
    for m in D.IRRIGATION_MODELS:
        print(f"  {m.label:14s} {cells[(m.label,'gov')]['at_cap_pct']:>15.2f}% "
              f"{cells[(m.label,'noval')]['at_cap_pct']:>13.2f}%")
    print("  -> the world layer is not merely evaluated second in the governed arm; agents")
    print("     there essentially never reach the cap. Enforcement in the behavioural layer")
    print("     removes the world layer's binding, which is the coupling the paper argues for.")
    print()

    # ---- render -------------------------------------------------------------
    os.makedirs(FIGDIR, exist_ok=True)
    fig, plotted = build_figure(data)
    _assert_no_text_overlaps(fig)
    png = os.path.join(FIGDIR, STEM + ".png")
    pdf = os.path.join(FIGDIR, STEM + ".pdf")
    fig.savefig(png, dpi=300)
    fig.savefig(pdf)
    plt.close(fig)

    csv_path = os.path.join(FIGDIR, STEM + ".csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["panel", "model", "arm", "n_seeds", "basis",
                                           "category", "count", "denominator", "percent"])
        w.writeheader()
        w.writerows(plotted)

    print("-" * 100)
    print("WRITTEN")
    print("-" * 100)
    for p in (png, pdf, csv_path):
        print(f"  {os.path.getsize(p):>9,d} bytes  {p}")
    print()

    print("-" * 100)
    print("SUGGESTED CAPTION")
    print("-" * 100)
    print(caption(data))
    print()
    print("=" * 100)
    print("FIG 1: " + ("FALSIFIED -- SEE ABOVE" if fails else "VERIFIED"))
    print("=" * 100)
    return 1 if fails else 0


def caption(data: dict) -> str:
    """Build the caption FROM the computed values so it can never drift.

    THE CAPTION IS THE BRIDGE. Since 2026-08-04 the figure's own labels are in
    the vocabulary of the thing measured -- "blocked", "passed", "water-right
    cap", "rule reads self-report", "proposed increase" -- while the body text
    keeps the technical terms the venue expects, "rejected", "approved",
    "precondition", "appraisal-conditioned rule", "increase proposal". Neither
    register is wrong and both have to stay, so the correspondence is stated
    here, once, the first time each pair matters. A figure whose labels no
    longer match the words the body uses, with nothing joining them, is worse
    than either vocabulary on its own.
    """
    cells = data["cells"]
    g = cells[("gemma3:4b", "gov")]
    n = cells[("gemma3:4b", "noval")]
    ap = g["cause"][C_APPRAISAL]

    rates = {arm: [100.0 * cells[(m.label, arm)]["rejected"] / cells[(m.label, arm)]["total"]
                   for m in D.IRRIGATION_MODELS] for arm in D.ARMS}

    wr = g["cause"][C_WORLDRULE]
    n_pure, n_examined = n_pure_cells(cells)

    # THE UNBALANCED-CELL DISCLOSURE, COMPUTED RATHER THAN REMEMBERED.
    # This used to be a hardcoded closing sentence naming ministral3:8b and the
    # star beside it. The star itself has always been computed
    # (``"*" if D.excluded_from_paired(...)``) and ministral3:8b was balanced at
    # 3 seeds against 3 on 2026-08-03, so since that day the caption asserted an
    # asterisk the figure did not draw and an imbalance the corpus did not have
    # -- printed on every run, including the ones whose output went into the
    # manuscript. Built from ``excluded_from_paired`` now, which is the same
    # predicate the panel-b tick labels use, so the sentence appears exactly
    # when the star does and names whichever cells are actually unbalanced.
    unbal = [m for m in D.IRRIGATION_MODELS if D.excluded_from_paired(m.prefix)]
    unbal_txt = "".join(
        f" {m.label} (*) is unbalanced, "
        f"{cells[(m.label, 'gov')]['n_seeds']} governed seeds against "
        f"{cells[(m.label, 'noval')]['n_seeds']} no-validator, and is shown "
        f"descriptively only."
        for m in unbal
    )
    pooled_c = pooled_by_cause(cells)
    ap_act, ap_n = pooled_c[("gov", C_APPRAISAL)]
    wr_act, wr_n = pooled_c[("gov", C_WORLDRULE)]
    pc_act, pc_n = pooled_c[("noval", C_PRECOND)]

    return f"""\
Figure 2. The two rule layers separate, and the behavioural layer is not one
thing. Governance in the irrigation testbed contains a world-feasibility layer --
the skill-registry precondition "not at_allocation_cap", which is attached to the
two increase skills and to no other -- and a behavioural-rule layer, the
validator stack. The panels are labelled in the terms of the run rather than of
the code: "blocked" is a rejected proposal, "passed" is an approved one, "water-
    right cap" is that world-feasibility precondition, "rule reads self-report"
    is a validator rule whose antecedent is the agent's own reported appraisal and
    "rule reads world state" one whose antecedent is simulator state only, and
    "proposed increase" / "proposed decrease" / "unparsed proposal" are the
    corresponding action categories.
(a) Anchor cell, gemma3:4b ({g['n_seeds']} seeds). The outer rows show all
{g['total']:,} decisions per arm, by outcome and cause. With validators disabled,
{n['rejected']:,} of {n['total']:,} proposals ({100*n['rejected']/n['total']:.1f}%) are still rejected, and
{100*n['cause'][C_PRECOND]/n['rejected']:.1f}% of those are the water-right precondition, with no behavioural rule
named. With validators enabled, {g['rejected']:,} of {g['total']:,} ({100*g['rejected']/g['total']:.1f}%) are rejected and
the named causes are validator rules. The two arms have disjoint blocking causes, with zero exceptions
in either direction. The middle row is not a third arm: its label states that it contains only the
{g['rejected']:,} with-validators rejections, re-based on that blocked-only total. It therefore shows
the within-arm split that an all-decisions denominator hides: {ap:,} ({100*ap/g['rejected']:.1f}%) name a rule
whose antecedent is the agent's own reported appraisal (WSA_LABEL / ACA_LABEL), while the other
{wr:,} ({100*wr/g['rejected']:.1f}%) name only world-conditioned validator rules. Calling the whole
with-validators layer behavioural theory would therefore overstate it by {100*wr/g['rejected']:.1f}
percentage points. (b) The same partition holds in all five irrigation
models -- each contributes two bars, validators on above and off below --
{n_pure} of {n_examined} cells pure, so the separation is not one cell's artifact;
rejection rates span {min(rates['gov']):.1f}-{max(rates['gov']):.1f}% with validators and {min(rates['noval']):.1f}-{max(rates['noval']):.1f}% without, and the
no-validator arm rejects a substantial share only in the anchor cell. (c) Proposed
actions among the three rejection causes, pooled over the five irrigation models.
The top two rows are a
within-system contrast -- the same arm, the same runs and the same decisions,
with only the kind of rule that fired changing -- so no cross-testbed comparison
enters. The allocation-cap precondition is attached only to the two increase
skills and to no other, so structurally that layer cannot block anything but an
increase: {100*pc_act[A_INCREASE]/pc_n:.2f}% of its {pc_n:,} rejections are increase proposals, exactly the
action the conformance statistic counts. Neither behavioural rule kind carries
that restriction: the appraisal-conditioned rules block an increase on {100*ap_act[A_INCREASE]/ap_n:.1f}% of
their {ap_n:,} rejections and the world-conditioned-only rules on {100*wr_act[A_INCREASE]/wr_n:.1f}% of their
{wr_n:,}, the remainder being decreases except for {ap_act[A_OTHER]:,} and {wr_act[A_OTHER]:,} rows respectively
whose proposal did not parse. Panel c pools five models and
panel a is the anchor cell alone, so their splits ({100*ap_n/(ap_n+wr_n):.1f}% and {100*ap/g['rejected']:.1f}%
appraisal-conditioned) are different denominators over different corpora and are
not the same number. Counts are pooled across seeds; this is a decomposition and
not a contrast, so no interval or test is attached.{unbal_txt}"""


if __name__ == "__main__":
    sys.exit(main())
