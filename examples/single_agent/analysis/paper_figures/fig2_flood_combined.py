"""
Figure 2: Flood Governance Results (WRR Technical Note)
=======================================================
Three-panel combined figure:
  (a) Cumulative protective action adoption over time
  (b) Behavioral hallucination rate R_H by group (bar chart)
  (c) Raw H_norm vs EBE time series (years 2-10)

Data: results/JOH_FINAL/gemma3_4b/Group_{A,B,C}/Run_1/simulation_log.csv
      corrected_entropy_gemma3_4b.csv (pre-computed by corrected_entropy_analysis.py)

AGU/WRR: 300 DPI, serif, Okabe-Ito palette, 7.0 x 6.0 inches
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# ── Paths ──
SCRIPT_DIR = Path(__file__).resolve().parent
BASE = SCRIPT_DIR.parents[1]  # examples/single_agent
RESULTS = BASE / "results" / "JOH_FINAL" / "gemma3_4b"
ENTROPY_CSV = SCRIPT_DIR / "corrected_entropy_gemma3_4b.csv"
GROUPS = {"A": "Group_A", "B": "Group_B", "C": "Group_C"}

# ── WRR Style ──
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 10,
    "axes.titlesize": 10,
    "legend.fontsize": 7.5,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
})

# Okabe-Ito color-blind friendly
C_A = "#D55E00"  # vermillion (Group A)
C_B = "#0072B2"  # blue (Group B)
C_C = "#009E73"  # teal (Group C)
COLORS = {"A": C_A, "B": C_B, "C": C_C}
LABELS = {"A": "A: Ungoverned", "B": "B: Governed + Window", "C": "C: Governed + HumanCentric"}
SHORT_LABELS = {"A": "A (ungoverned)", "B": "B (gov. + window)", "C": "C (gov. + memory)"}
BAR_LABELS = {"A": "A: Ungoverned", "B": "B: Governed\n+ Window", "C": "C: Governed\n+ HumanCentric"}

YEARS = np.arange(1, 11)
FLOOD_YEARS = [3, 4, 9]


# ── Data Loaders ──
def load_group(g):
    return pd.read_csv(RESULTS / GROUPS[g] / "Run_1" / "simulation_log.csv")


def protective_adoption(df, g):
    """% of agents with at least one protective action per year."""
    if g == "A":
        agent_state = {}
        results = {}
        for _, row in df.sort_values(["agent_id", "year"]).iterrows():
            aid, yr = row["agent_id"], row["year"]
            raw = str(row.get("raw_llm_decision", row.get("decision", ""))).lower()
            if aid not in agent_state:
                agent_state[aid] = {"elevated": False, "insured": False, "relocated": False}
            s = agent_state[aid]
            if "elevat" in raw: s["elevated"] = True
            if "insur" in raw: s["insured"] = True
            if "both" in raw: s["elevated"] = s["insured"] = True
            if "relocat" in raw: s["relocated"] = True
            results.setdefault(yr, []).append(s["elevated"] or s["insured"] or s["relocated"])
        return {yr: sum(v) / len(v) * 100 for yr, v in results.items()}
    else:
        out = {}
        for yr in sorted(df["year"].unique()):
            ydf = df[df["year"] == yr]
            has = (ydf["elevated"] == True) | (ydf["has_insurance"] == True) | (ydf["relocated"] == True)
            out[yr] = has.sum() / len(ydf) * 100
        return out


def hallucination_rate(df, g):
    """R_H = redundant/impossible decisions / total active decisions."""
    hall, active = 0, 0
    if g == "A":
        agent_state = {}
        for _, row in df.sort_values(["agent_id", "year"]).iterrows():
            aid = row["agent_id"]
            raw = str(row.get("raw_llm_decision", "")).lower()
            if aid not in agent_state:
                agent_state[aid] = {"elevated": False, "insured": False, "relocated": False}
            s = agent_state[aid]
            if s["relocated"]: continue
            active += 1
            is_hall = False
            if "elevat" in raw and s["elevated"]: is_hall = True
            elif "insur" in raw and s["insured"]: is_hall = True
            elif "both" in raw and (s["elevated"] or s["insured"]): is_hall = True
            if is_hall: hall += 1
            if "elevat" in raw: s["elevated"] = True
            if "insur" in raw: s["insured"] = True
            if "both" in raw: s["elevated"] = s["insured"] = True
            if "relocat" in raw: s["relocated"] = True
    else:
        years = sorted(df["year"].unique())
        active += len(df[df["year"] == years[0]])
        for yr in years[1:]:
            ydf = df[df["year"] == yr]
            prev = df[df["year"] == yr - 1]
            for _, row in ydf.iterrows():
                aid = row["agent_id"]
                dec = str(row["yearly_decision"]).lower()
                p = prev[prev["agent_id"] == aid]
                if p.empty: continue
                p = p.iloc[0]
                if p.get("relocated", False): continue
                active += 1
                is_hall = False
                if "elevat" in dec and p["elevated"]: is_hall = True
                if "insur" in dec and p["has_insurance"]: is_hall = True
                if "both" in dec and (p["elevated"] or p["has_insurance"]): is_hall = True
                if is_hall: hall += 1
    return hall / active * 100 if active > 0 else 0.0


# ── Compute ──
data = {g: load_group(g) for g in "ABC"}
adoption = {g: protective_adoption(data[g], g) for g in "ABC"}
rh = {g: hallucination_rate(data[g], g) for g in "ABC"}

if not ENTROPY_CSV.exists():
    print(f"ERROR: {ENTROPY_CSV} not found. Run corrected_entropy_analysis.py first.")
    sys.exit(1)
entropy = pd.read_csv(ENTROPY_CSV)

# ── Plot: 3-panel layout ──
fig = plt.figure(figsize=(7.0, 6.0), constrained_layout=True)
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1], width_ratios=[1.5, 1])
ax_a = fig.add_subplot(gs[0, :])      # top row spans both columns
ax_b = fig.add_subplot(gs[1, 0])      # bottom-left
ax_c = fig.add_subplot(gs[1, 1])      # bottom-right

# ── Panel (a): Cumulative Protective Action Adoption ──
ax_a.set_title("(a) Cumulative Protective Action Adoption",
               fontweight="bold", loc="left", fontsize=9)
for g in "ABC":
    years = sorted(adoption[g].keys())
    vals = [adoption[g][y] for y in years]
    mkr = "o" if g == "A" else ("s" if g == "B" else "^")
    ax_a.plot(years, vals, color=COLORS[g],
              ls="--" if g == "A" else "-", lw=1.8,
              marker=mkr, ms=4, label=LABELS[g])

for fy in FLOOD_YEARS:
    ax_a.axvline(x=fy, color="gray", ls=":", lw=0.6, alpha=0.5)
ax_a.set_xlabel("Simulation Year")
ax_a.set_ylabel("Agents with Protective Action (%)")
ax_a.legend(fontsize=7.5, framealpha=0.9, edgecolor="none")
ax_a.grid(True, alpha=0.2)
ax_a.set_xlim(0.5, 10.5)
ax_a.set_ylim(0, 105)
ax_a.set_xticks(YEARS)

# ── Panel (b): Raw Entropy vs EBE Time Series ──
ax_b.set_title("(b) Raw Entropy vs. Effective Behavioral Entropy",
               fontweight="bold", loc="left", fontsize=9)

for group, color, label in [
    ("Group_A", C_A, SHORT_LABELS["A"]),
    ("Group_B", C_B, SHORT_LABELS["B"]),
    ("Group_C", C_C, SHORT_LABELS["C"]),
]:
    g_df = entropy[entropy["Group"] == group].sort_values("Year")
    g_df = g_df[g_df["Year"] >= 2]
    yrs = g_df["Year"].values
    mkr = "o" if "A" in group else ("s" if "B" in group else "^")

    ax_b.plot(yrs, g_df["Raw_H_norm"].values,
              color=color, ls="--", lw=0.8, alpha=0.5,
              label=f"{label} raw H" + r"$_{norm}$")
    ax_b.plot(yrs, g_df["EBE"].values,
              color=color, ls="-", lw=1.8, marker=mkr, ms=3.5,
              label=f"{label} EBE")

# Shade hallucination gap for Group A
ga = entropy[(entropy["Group"] == "Group_A") & (entropy["Year"] >= 2)].sort_values("Year")
ax_b.fill_between(ga["Year"].values, ga["EBE"].values, ga["Raw_H_norm"].values,
                  color=C_A, alpha=0.08)
mid_yr = 6
ga_mid = ga[ga["Year"] == mid_yr]
if not ga_mid.empty:
    mid_raw = ga_mid["Raw_H_norm"].values[0]
    mid_ebe = ga_mid["EBE"].values[0]
    ax_b.annotate("Hallucination\ngap", xy=(mid_yr, (mid_raw + mid_ebe) / 2),
                  xytext=(mid_yr + 2, 0.72), fontsize=6.5, color=C_A,
                  fontstyle="italic", ha="center",
                  arrowprops=dict(arrowstyle="->", color=C_A, lw=0.7))

for fy in FLOOD_YEARS:
    if fy >= 2:
        ax_b.axvline(x=fy, color="gray", ls=":", lw=0.6, alpha=0.5)

ax_b.set_xlabel("Simulation Year")
ax_b.set_ylabel(r"Entropy (H$_{norm}$ or EBE)")
ax_b.set_xlim(1.5, 10.5)
ax_b.set_ylim(-0.05, 1.0)
ax_b.set_xticks(np.arange(2, 11))
ax_b.legend(loc="upper right", framealpha=0.9, edgecolor="none",
            ncol=2, handlelength=1.6, columnspacing=0.6,
            borderpad=0.3, labelspacing=0.3, fontsize=6)
ax_b.grid(True, alpha=0.2)

# ── Panel (c): Hallucination Rate R_H Bar Chart ──
ax_c.set_title(r"(c) Behavioral Hallucination Rate R$_H$",
               fontweight="bold", loc="left", fontsize=9)
x = np.arange(3)
bars = ax_c.bar(x, [rh[g] for g in "ABC"],
                color=[COLORS[g] for g in "ABC"],
                edgecolor="white", lw=1.2, width=0.55)
for i, (g, bar) in enumerate(zip("ABC", bars)):
    ax_c.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.25,
              f"{rh[g]:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
ax_c.set_xticks(x)
ax_c.set_xticklabels([BAR_LABELS[g] for g in "ABC"], fontsize=7.5)
ax_c.set_ylabel(r"Hallucination Rate R$_H$ (%)")
ax_c.grid(True, axis="y", alpha=0.2)
ax_c.set_ylim(0, max(rh.values()) * 1.4)

# ── Save ──
out_png = SCRIPT_DIR / "fig2_flood_combined.png"
out_pdf = SCRIPT_DIR / "fig2_flood_combined.pdf"
fig.savefig(out_png)
fig.savefig(out_pdf)
plt.close()

print(f"Saved: {out_png}")
print(f"Saved: {out_pdf}")
for g in "ABC":
    print(f"  {LABELS[g]}: adoption={list(adoption[g].values())[-1]:.0f}%, R_H={rh[g]:.1f}%")

print("\n--- Entropy Summary (years 2-10 mean) ---")
for group in ["Group_A", "Group_B", "Group_C"]:
    g_df = entropy[(entropy["Group"] == group) & (entropy["Year"] >= 2)]
    print(f"  {group}: raw H_norm={g_df['Raw_H_norm'].mean():.2f}  "
          f"EBE={g_df['EBE'].mean():.2f}  "
          f"R_H={g_df['Hallucination_Rate'].mean():.1%}")
