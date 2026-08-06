#!/usr/bin/env python
"""Replacement for Figure 3 under the EXECUTED action reading.

    python ICLR2027/fig_denominator_gap.py

Writes ICLR2027/fig_denominator_gap.{png,pdf} and fig_denominator_gap.csv.

WHY THIS FIGURE REPLACES THE OLD ONE
------------------------------------
`fig3_consequence.py` plots the conditional and all-decision deltas side by side on the
LAST-PROPOSED reading, and its visual argument is *look how unstable this is*: one cell at
+0.16 and one at -22.17. That instability is largely produced by the reading. On LAST-PROPOSED,
a governed decision that was blocked still records the blocked proposal, so the harder the
validators bind the more phantom increases are attributed to the governed arm.

Under EXECUTED the five all-decision deltas are +29.90, +27.82, +28.84, +36.57, +20.26 -- all
positive, all significant, none near zero. A grouped bar chart of that is a dull picture of a
stronger result.

So the figure has to argue something else, and there is something better to argue. Take the gap
between the two denominators per cell:

    gap = (conditional delta) - (all-decision delta)

    LAST-PROPOSED:  +1.39  +11.28  +3.69  +8.89  +24.97   -> all five positive
    EXECUTED:       -3.99  -14.86  -0.88   +3.38  -16.06   -> four negative, one positive

**On the reading the project's own rule requires, the direction of the denominator's bias is not
predictable.** "The conditional rate inflates your number" invites "then correct for it". "You
cannot know in advance which way it goes" forces the reporting protocol instead of asserting it.

WHAT IS DRAWN
-------------
A slope plot, one row per irrigation cell. A line runs from the conditional delta to the
all-decision delta, with a marker at each end and an arrowhead at the all-decision end. The
DIRECTION of the line is the sign of the gap, and the LENGTH is its size -- so levels and gaps
are both readable, which a bar chart of gaps alone would lose.

Cells are ordered by gap so the one cell that runs the other way sits apart from the four.
95% CIs from the shipped per-seed paired t are drawn on both ends.

BASIS
-----
Every number is read from the shipped supplement CSV produced by `fig3_consequence.py`, which
owns the definitions. This script computes nothing except the difference between two of its
columns, and it re-derives that difference from the per-seed deltas as a check rather than
trusting the rounded means.
"""
from __future__ import annotations

import csv
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "SUBMISSION_2026", "TAE", "evidence"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

try:
    import _figstyle as FS  # noqa: E402
    FS.apply()
    F_TICK, F_ANNOT, F_LEG, F_AX = FS.FS_TICK, FS.FS_ANNOT, FS.FS_LEGEND, FS.FS_AXIS_LABEL
except Exception as exc:                                    # pragma: no cover
    print(f"  [warn] _figstyle unavailable ({exc}); falling back to matplotlib defaults")
    F_TICK, F_ANNOT, F_LEG, F_AX = 8.75, 9.0, 9.25, 9.5

SRC = os.path.join(HERE, "..", "ICLR2027", "submission", "supplement", "fig3_consequence.csv")
if not os.path.exists(SRC):
    SRC = os.path.join(HERE, "..", "SUBMISSION_2026", "TAE", "figures", "fig3_consequence.csv")

READING = "EXECUTED"
ORDER = ["gemma3:4b", "gemma3:12b", "gemma4:e2b", "gemma4:e4b", "ministral3:8b"]

C_COND = "#1b6ca8"   # conditional -- the agent-authored denominator
C_ALL = "#c2571a"    # all-decision -- the denominator governance cannot move
C_RULE = "0.45"


def load(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    out = {}
    for m in ORDER:
        rec = {}
        for stat, key in (("conditional_increase_rate", "cond"),
                          ("unconditional_increase_rate", "all")):
            r = next((x for x in rows if x["model"] == m
                      and x["statistic"] == stat
                      and x["action_reading"] == READING), None)
            if r is None:
                break
            per_seed = {}
            for pair in (r.get("per_seed_delta_pp") or "").split(";"):
                if ":" in pair:
                    s, v = pair.split(":", 1)
                    per_seed[s.strip()] = float(v)
            rec[key] = dict(delta=float(r["delta_pp"]),
                            lo=float(r["ci_lo_pp"]), hi=float(r["ci_hi_pp"]),
                            p=float(r["p_two_sided"]), per_seed=per_seed)
        if len(rec) == 2:
            out[m] = rec
    return out


data = load(SRC)
if len(data) != len(ORDER):
    raise SystemExit(f"expected {len(ORDER)} cells, read {len(data)} from {SRC}")

# The gap, and a check that the rounded means agree with the per-seed arithmetic.
for m, rec in data.items():
    rec["gap"] = rec["cond"]["delta"] - rec["all"]["delta"]
    seeds = sorted(set(rec["cond"]["per_seed"]) & set(rec["all"]["per_seed"]))
    if seeds:
        recomputed = st.mean(rec["cond"]["per_seed"][s] - rec["all"]["per_seed"][s] for s in seeds)
        if abs(recomputed - rec["gap"]) > 0.01:
            raise SystemExit(f"{m}: gap {rec['gap']:+.4f} disagrees with per-seed "
                             f"{recomputed:+.4f} -- refusing to plot")
        rec["n"] = len(seeds)

order = sorted(ORDER, key=lambda m: data[m]["gap"])

fig, ax = plt.subplots(figsize=(5.5, 2.85))
for i, m in enumerate(order):
    d = data[m]
    c, a = d["cond"]["delta"], d["all"]["delta"]
    ax.plot([d["cond"]["lo"], d["cond"]["hi"]], [i, i], color=C_COND, lw=3.0, alpha=0.22,
            solid_capstyle="butt", zorder=1)
    ax.plot([d["all"]["lo"], d["all"]["hi"]], [i, i], color=C_ALL, lw=3.0, alpha=0.22,
            solid_capstyle="butt", zorder=1)
    ax.annotate("", xy=(a, i), xytext=(c, i), zorder=3,
                arrowprops=dict(arrowstyle="-|>", color="0.30", lw=1.15,
                                shrinkA=3.2, shrinkB=1.6))
    ax.plot([c], [i], "o", ms=5.4, color=C_COND, zorder=4)
    ax.plot([a], [i], "o", ms=5.4, color=C_ALL, zorder=4)
    ax.text(max(c, a) + 1.4, i, f"{d['gap']:+.1f}", va="center", ha="left",
            fontsize=F_ANNOT, color="0.15", zorder=5)

ax.axvline(0, color=C_RULE, lw=0.8, ls=(0, (4, 3)), zorder=0)
ax.set_yticks(range(len(order)))
ax.set_yticklabels(order, fontsize=F_TICK)
ax.set_ylim(-0.7, len(order) - 0.3)
ax.set_xlabel(r"$\Delta$ = no-validator $-$ validator-on  (pp; executed action)",
              fontsize=F_AX)
ax.tick_params(axis="x", labelsize=F_TICK)
for side in ("top", "right"):
    ax.spines[side].set_visible(False)
ax.grid(axis="x", color="0.90", lw=0.6, zorder=0)
ax.set_axisbelow(True)

# Upper left. The lower-right corner looks empty but is not: the largest gap label sits
# there, and a legend placed by eye covered it in the first draft.
ax.legend(handles=[
    Line2D([], [], marker="o", ls="none", ms=5.4, color=C_COND,
           label="conditional (agent-written)"),
    Line2D([], [], marker="o", ls="none", ms=5.4, color=C_ALL,
           label="all decisions"),
], loc="upper left", frameon=False, fontsize=F_LEG, handletextpad=0.5,
   borderaxespad=0.3, labelspacing=0.35)

# Headroom so the legend clears the top row's marker, and right margin for the gap labels.
lo = min(min(d["cond"]["lo"], d["all"]["lo"]) for d in data.values())
hi = max(max(d["cond"]["hi"], d["all"]["hi"]) for d in data.values())
ax.set_xlim(min(lo, 0) - 2.0, hi + 7.5)
ax.set_ylim(-0.7, len(order) + 0.45)

fig.tight_layout(pad=0.55)
for ext in ("pdf", "png"):
    out = os.path.join(HERE, f"fig_denominator_gap.{ext}")
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"  wrote {out}")

csv_out = os.path.join(HERE, "fig_denominator_gap.csv")
with open(csv_out, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["model", "reading", "cond_delta_pp", "cond_ci_lo", "cond_ci_hi", "cond_p",
                "all_delta_pp", "all_ci_lo", "all_ci_hi", "all_p", "gap_pp", "n_paired_seeds"])
    for m in order:
        d = data[m]
        w.writerow([m, READING,
                    round(d["cond"]["delta"], 4), round(d["cond"]["lo"], 4),
                    round(d["cond"]["hi"], 4), d["cond"]["p"],
                    round(d["all"]["delta"], 4), round(d["all"]["lo"], 4),
                    round(d["all"]["hi"], 4), d["all"]["p"],
                    round(d["gap"], 4), d.get("n", "")])
print(f"  wrote {csv_out}")

print()
print(f"  {'model':<15} {'conditional':>12} {'all-decision':>13} {'gap':>8}")
for m in order:
    d = data[m]
    print(f"  {m:<15} {d['cond']['delta']:+12.2f} {d['all']['delta']:+13.2f} {d['gap']:+8.2f}")
neg = sum(1 for m in order if data[m]["gap"] < 0)
print(f"\n  {neg} of {len(order)} cells understate, {len(order) - neg} overstate "
      f"-- the direction of the denominator's bias is not predictable")
