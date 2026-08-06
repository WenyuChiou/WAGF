"""Synthesis-lane checks. READ-ONLY over results; writes nothing outside this dir."""
import csv, glob, os, collections, statistics

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BAD = ("Group_A", "_bak", "_dead", "_QUARANTINE", "_logs", "rulebased")

def files(pat):
    out = []
    for p in glob.glob(os.path.join(REPO, pat)):
        if any(b in p for b in BAD):
            continue
        out.append(p)
    return sorted(out)

IRR_SEG = {"gemma3:4b": "", "gemma3:12b": "gemma3_12b_", "gemma4:e2b": "gemma4_e2b_",
           "gemma4:e4b": "gemma4_e4b_", "ministral3:8b": "ministral3_8b_"}
FLOOD = {"gemma3_4b": "JOH_FINAL", "gemma3_12b": "JOH_FINAL", "gemma3_27b": "JOH_FINAL",
         "ministral3_3b": "JOH_FINAL", "ministral3_8b": "JOH_FINAL", "ministral3_14b": "JOH_FINAL",
         "gemma4_e2b": "JOH_FINAL_v2", "gemma4_e4b": "JOH_FINAL_v2", "gemma4_26b": "JOH_FINAL_v2"}
HIGH = {"H", "VH"}

def irr_paths(seg, arm):
    pre = "production" if arm == "gov" else "ungoverned"
    return files(f"examples/irrigation_abm/results/{pre}_v21_42yr_{seg}seed*/irrigation_farmer_governance_audit.csv")

def flood_paths(model, arm):
    base = FLOOD[model]
    if arm == "gov":
        return files(f"examples/single_agent/results/{base}/{model}/Group_C/Run_*/household_governance_audit.csv")
    return files(f"examples/single_agent/results/{base.replace('JOH_FINAL','JOH_ABLATION_DISABLED')}/{model}/Group_C_disabled/Run_*/household_governance_audit.csv")

def scan(paths, col):
    """returns (n_all, n_high_all, n_r0, n_high_r0)"""
    n = h = n0 = h0 = 0
    for p in paths:
        with open(p, newline="", encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                v = (row.get(col) or "").strip().upper()
                if not v:
                    continue
                rc = (row.get("retry_count") or "").strip()
                n += 1
                ish = v in HIGH
                h += ish
                if rc == "0":
                    n0 += 1
                    h0 += ish
    return n, h, n0, h0

print(f"{'cell':<26} {'shift_all':>10} {'shift_r0':>10} {'gov_r0_share':>13} {'ung_r0_share':>13}")
print("-" * 78)
rows = []
for m, seg in IRR_SEG.items():
    g = scan(irr_paths(seg, "gov"), "construct_WSA_LABEL")
    u = scan(irr_paths(seg, "ung"), "construct_WSA_LABEL")
    rows.append(("irrigation " + m, g, u))
for m in FLOOD:
    g = scan(flood_paths(m, "gov"), "construct_TP_LABEL")
    u = scan(flood_paths(m, "ung"), "construct_TP_LABEL")
    rows.append(("flood " + m, g, u))

for cell, g, u in rows:
    pct = lambda a, b: 100.0 * a / b if b else float("nan")
    s_all = pct(u[1], u[0]) - pct(g[1], g[0])
    s_r0 = pct(u[3], u[2]) - pct(g[3], g[2])
    print(f"{cell:<26} {s_all:>+10.2f} {s_r0:>+10.2f} {pct(g[2],g[0]):>12.1f}% {pct(u[2],u[0]):>12.1f}%")

print()
irr = [r for r in rows if r[0].startswith("irrigation")]
fl = [r for r in rows if r[0].startswith("flood")]
def means(rs, idx):
    vals = []
    for cell, g, u in rs:
        pct = lambda a, b: 100.0 * a / b if b else float("nan")
        if idx == "all":
            vals.append(pct(u[1], u[0]) - pct(g[1], g[0]))
        else:
            vals.append(pct(u[3], u[2]) - pct(g[3], g[2]))
    return statistics.mean(vals), min(vals), max(vals)
for lbl, rs in [("HIGH regime (irrigation, n=5)", irr), ("LOW regime (flood, n=9)", fl)]:
    a = means(rs, "all"); b = means(rs, "r0")
    print(f"{lbl}: all-rows mean {a[0]:+.2f} ({a[1]:+.2f}..{a[2]:+.2f}) | never-retried-only mean {b[0]:+.2f} ({b[1]:+.2f}..{b[2]:+.2f})")
