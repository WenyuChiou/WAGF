"""
Generate professor-facing summary table: Irrigation domain key outcomes.
Governed vs Ungoverned with Diff + Change% columns (matching flood table style).
Plus A1 and FQL as additional reference columns.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

OUT = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\paper\nature_water\professor_briefing")

# ── Numeric data for diff computation ──
metrics = [
    'Mean demand ratio',
    '42-yr mean Mead elev. (ft)',
    'Demand–Mead coupling (r)',
    'Shortage years (/42)',
    'Min Mead elevation (ft)',
    'Strategy diversity (EHE)',
    'Behavioural Rationality (BRI %)',
]

# Values: [Governed, Ungoverned, A1, FQL]
gov_vals   = [0.394, 1094, 0.547, 13.3, 1002, 0.738, 58.0]
ungov_vals = [0.288, 1173, 0.378, 5.0,  1001, 0.637, 9.4]
a1_vals    = [0.440, 1069, 0.234, 25.3, 984,  0.793, None]
fql_vals   = [0.395, 1065, 0.057, 24.7, 1020, None,  None]

# Display strings (with ± where applicable)
gov_str   = ['0.394 ± 0.004', '1,094', '0.547 ± 0.083', '13.3 ± 1.5', '1,002 ± 1', '0.738 ± 0.017', '58.0']
ungov_str = ['0.288 ± 0.020', '1,173', '0.378 ± 0.081', '5.0 ± 1.7',  '1,001 ± 0.4', '0.637 ± 0.017', '9.4']
a1_str    = ['0.440 ± 0.012', '1,069', '0.234 ± 0.127', '25.3 ± 1.5', '984 ± 11',  '0.793 ± 0.002', '—']
fql_str   = ['0.395 ± 0.008', '1,065', '0.057 ± 0.323', '24.7 ± 9.1', '1,020 ± 4', '—',             '—']

# For each metric: is higher "good" for governed? (determines green/red of diff)
# demand ratio: higher = more exploitation (good with coupling)
# Mead elev: lower = more stress (context-dependent)
# coupling: higher = good
# shortage years: more = consequence of exploitation (context)
# min Mead: context
# EHE: higher = good
# BRI: higher = good
higher_is_good = [True, False, True, None, None, True, True]
# None = neutral (no color)

# ── Layout ──
# Columns: Metric | Ungov | Gov | Diff | Change% | A1 | FQL
col_headers = ['Metric', 'Ungov.', 'Governed', 'Diff', 'Change', 'A1\n(No Ceil.)', 'FQL\nBaseline']
n_rows = len(metrics)
n_cols = len(col_headers)

col_widths_raw = [0.19, 0.12, 0.12, 0.09, 0.09, 0.12, 0.12]

fig, ax = plt.subplots(figsize=(13, 6.2))
ax.axis('off')

row_h = 0.058
header_h = 0.055
top_header_h = 0.050
left = 0.02
right = 0.98
top = 0.86

total_w = sum(col_widths_raw)
scale = (right - left) / total_w
col_widths = [w * scale for w in col_widths_raw]

# Colors
HEADER_BG = '#2F5496'
HEADER_TEXT = 'white'
ROW_BG_EVEN = '#F2F2F2'
ROW_BG_ODD = '#FFFFFF'
GOOD_BG = '#C6EFCE'
GOOD_TEXT = '#006100'
BAD_BG = '#FFC7CE'
BAD_TEXT = '#9C0006'
NEUTRAL_BG = '#FFF2CC'
NEUTRAL_TEXT = '#7F6000'
BLACK = '#222222'

def get_col_x(col_idx):
    return left + sum(col_widths[:col_idx])

# ── Title ──
ax.text(0.5, 0.96, 'Irrigation Domain — Framework Effectiveness Summary',
        ha='center', va='center', fontsize=13, fontweight='bold', color=HEADER_BG)
ax.text(0.5, 0.92, '78 CRSS agents × 42 years × 3 seeds  |  Gemma-3 4B  |  Colorado River Basin',
        ha='center', va='center', fontsize=9, color='#777777')

# ── Top merged headers ──
# Gov vs Ungov comparison block: cols 1-4
comp_x = get_col_x(1)
comp_w = sum(col_widths[1:5])
rect = plt.Rectangle((comp_x, top), comp_w, top_header_h,
                      facecolor=HEADER_BG, edgecolor='white', lw=1)
ax.add_patch(rect)
ax.text(comp_x + comp_w/2, top + top_header_h/2,
        'Governed vs Ungoverned (core comparison)',
        ha='center', va='center', color=HEADER_TEXT, fontsize=9.5, fontweight='bold')

# Reference conditions: cols 5-6
ref_x = get_col_x(5)
ref_w = sum(col_widths[5:7])
rect = plt.Rectangle((ref_x, top), ref_w, top_header_h,
                      facecolor='#8FAADC', edgecolor='white', lw=1)
ax.add_patch(rect)
ax.text(ref_x + ref_w/2, top + top_header_h/2,
        'Ablation references',
        ha='center', va='center', color='white', fontsize=9.5, fontweight='bold')

# Metric top header
rect = plt.Rectangle((left, top), col_widths[0], top_header_h,
                      facecolor=HEADER_BG, edgecolor='white', lw=1)
ax.add_patch(rect)

# ── Sub-headers ──
header_y = top - header_h
for j, h in enumerate(col_headers):
    x = get_col_x(j)
    w = col_widths[j]
    rect = plt.Rectangle((x, header_y), w, header_h,
                          facecolor='#D6DCE4', edgecolor='white', lw=1)
    ax.add_patch(rect)
    ax.text(x + w/2, header_y + header_h/2, h.replace('\n', '\n'),
            ha='center', va='center', color=BLACK, fontsize=8.5, fontweight='bold',
            linespacing=0.9)

# ── Data rows ──
for i in range(n_rows):
    y = header_y - (i + 1) * row_h
    bg = ROW_BG_EVEN if i % 2 == 0 else ROW_BG_ODD

    g = gov_vals[i]
    u = ungov_vals[i]
    diff = g - u if (g is not None and u is not None) else None
    pct = (diff / abs(u)) * 100 if (diff is not None and u != 0) else None

    # Format diff and pct
    if diff is not None:
        if abs(diff) < 1:
            diff_str = f"{diff:+.3f}"
        else:
            diff_str = f"{diff:+.1f}"
        pct_str = f"{pct:+.0f}%"
    else:
        diff_str = '—'
        pct_str = '—'

    row_data = [
        metrics[i],
        ungov_str[i],
        gov_str[i],
        diff_str,
        pct_str,
        a1_str[i],
        fql_str[i],
    ]

    # Cell colors
    cell_bgs = [bg] * n_cols
    cell_colors = [BLACK] * n_cols

    if diff is not None and higher_is_good[i] is not None:
        is_good = (diff > 0) == higher_is_good[i]
        if is_good:
            cell_bgs[3] = GOOD_BG; cell_colors[3] = GOOD_TEXT
            cell_bgs[4] = GOOD_BG; cell_colors[4] = GOOD_TEXT
        else:
            cell_bgs[3] = BAD_BG; cell_colors[3] = BAD_TEXT
            cell_bgs[4] = BAD_BG; cell_colors[4] = BAD_TEXT
    elif diff is not None:
        # Neutral metrics (Mead elev, min Mead, shortage years)
        cell_bgs[3] = NEUTRAL_BG; cell_colors[3] = NEUTRAL_TEXT
        cell_bgs[4] = NEUTRAL_BG; cell_colors[4] = NEUTRAL_TEXT

    for j in range(n_cols):
        x = get_col_x(j)
        w = col_widths[j]
        rect = plt.Rectangle((x, y), w, row_h,
                              facecolor=cell_bgs[j], edgecolor='white', lw=0.5)
        ax.add_patch(rect)

        ha = 'left' if j == 0 else 'center'
        tx = x + 0.008 if j == 0 else x + w/2
        fw = 'bold' if j == 0 else 'normal'
        fs = 8.5 if j == 0 else 9

        ax.text(tx, y + row_h/2, row_data[j],
                ha=ha, va='center', color=cell_colors[j],
                fontsize=fs, fontweight=fw, family='sans-serif')

# ── Bottom border ──
bottom_y = header_y - n_rows * row_h
ax.plot([left, right], [bottom_y, bottom_y], color=HEADER_BG, lw=2)

# ── Key Findings ──
box_y = bottom_y - 0.035
ax.text(left, box_y, 'Key Findings:', fontsize=9.5, fontweight='bold',
        color=HEADER_BG, va='top')

insights = [
    '● Governed agents extract +37% MORE water (0.394 vs 0.288) while coupling to drought (r = 0.547) → adaptive exploitation',
    '● Removing 1 rule of 12 (demand ceiling) → coupling collapses (0.547 → 0.234), shortage doubles → institutional rule decomposition',
    '● FQL extracts same volume (0.395) but zero coupling (r = 0.057) → language reasoning required, not just governance',
    '● Governed BRI 58% vs Ungoverned 9.4% (+517%) → governance eliminates increase-bias without prescribing actions',
    '● Strategy diversity: Governed 0.738 vs Ungoverned 0.637 (+16%) → governance expands decision repertoire',
]

for k, ins in enumerate(insights):
    ax.text(left + 0.01, box_y - 0.033 - k * 0.031, ins,
            fontsize=8, color='#333333', va='top', family='sans-serif')

# ── Footnote ──
fn_y = box_y - 0.033 - len(insights) * 0.031 - 0.012
ax.text(left, fn_y,
        'Green = governance improvement.  Red = governance regression.  '
        'Amber = context-dependent (not inherently good/bad).  '
        'A1 = demand ceiling removed.  FQL = fuzzy Q-learning baseline (Hung & Yang, 2021).',
        fontsize=7.5, color='#999999', va='top', family='sans-serif')

ax.set_xlim(0, 1)
ax.set_ylim(fn_y - 0.03, 1.0)

for fmt in ['png', 'pdf']:
    out = OUT / f"professor_summary_irrigation.{fmt}"
    fig.savefig(out, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"  Saved: {out}")
plt.close()
print("Done.")
