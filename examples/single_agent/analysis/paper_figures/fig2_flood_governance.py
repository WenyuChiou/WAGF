"""
Figure 2: Flood Governance Effectiveness (WRR Technical Note)
Panel (a): Cumulative protective action adoption over time
Panel (b): Behavioral hallucination rate R_H by group
"""
import pandas as pd, numpy as np, matplotlib.pyplot as plt
from pathlib import Path

BASE = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL\gemma3_4b")
GROUPS = {"A": "Group_A", "B": "Group_B", "C": "Group_C"}
LABELS = {"A": "A: Ungoverned", "B": "B: Governed\n+ Window", "C": "C: Governed\n+ HumanCentric"}
COLORS = {"A": "#d62728", "B": "#4682b4", "C": "#1a3a5c"}
STYLES = {"A": "--", "B": "-", "C": "-"}


def load_group(g):
    return pd.read_csv(BASE / GROUPS[g] / "Run_1" / "simulation_log.csv")


def protective_adoption(df, g):
    """% of agents with at least one protective action per year."""
    if g == "A":
        # Reconstruct state from decision history
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
        return {yr: sum(vals) / len(vals) * 100 for yr, vals in results.items()}
    else:
        out = {}
        for yr in sorted(df["year"].unique()):
            ydf = df[df["year"] == yr]
            has_action = (ydf["elevated"] == True) | (ydf["has_insurance"] == True) | (ydf["relocated"] == True)
            out[yr] = has_action.sum() / len(ydf) * 100
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

# ── Plot ──
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5), dpi=150,
                                gridspec_kw={"width_ratios": [1.6, 1]})
fig.subplots_adjust(wspace=0.35)

# Panel (a)
for g in "ABC":
    years = sorted(adoption[g].keys())
    vals = [adoption[g][y] for y in years]
    ax1.plot(years, vals, color=COLORS[g], ls=STYLES[g], lw=2.2,
             marker="o", ms=4, label=LABELS[g].replace("\n", " "))
ax1.set_xlabel("Year", fontsize=10)
ax1.set_ylabel("Agents with Protective Action (%)", fontsize=10)
ax1.set_title("(a) Cumulative Protective Action Adoption", fontsize=11, fontweight="bold", loc="left")
ax1.legend(fontsize=8.5, framealpha=0.9)
ax1.grid(True, alpha=0.25)
ax1.set_xlim(0.5, 10.5)
ax1.set_ylim(0, 105)

# Panel (b)
x = np.arange(3)
bars = ax2.bar(x, [rh[g] for g in "ABC"],
               color=[COLORS[g] for g in "ABC"], edgecolor="white", lw=1.2, width=0.6)
for i, (g, bar) in enumerate(zip("ABC", bars)):
    ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.25,
             f"{rh[g]:.1f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")
ax2.set_xticks(x)
ax2.set_xticklabels([LABELS[g] for g in "ABC"], fontsize=8.5)
ax2.set_ylabel("Hallucination Rate R$_H$ (%)", fontsize=10)
ax2.set_title("(b) Behavioral Hallucination Rate", fontsize=11, fontweight="bold", loc="left")
ax2.grid(True, axis="y", alpha=0.25)
ax2.set_ylim(0, max(rh.values()) * 1.4)

out = Path(__file__).parent / "fig2_flood_governance.png"
fig.savefig(out, bbox_inches="tight", dpi=200)
plt.close()
print(f"Saved: {out}")
for g in "ABC":
    print(f"  {LABELS[g].replace(chr(10),' ')}: adoption={list(adoption[g].values())[-1]:.0f}%, R_H={rh[g]:.1f}%")
