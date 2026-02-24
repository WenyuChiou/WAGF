"""
Generate professor-facing summary table: Irrigation domain key outcomes.
Governed vs Ungoverned vs A1 vs FQL — water outcomes + framework metrics.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

OUT = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\paper\nature_water\professor_briefing")

# ── Data from Table 1 (section2_v11_results.md) ──
metrics = [
    'Mean demand ratio',
    '42-yr mean Mead elev. (ft)',
    'Demand–Mead coupling (r)',
    'Shortage years (/42)',
    'Min Mead elevation (ft)',
    'Strategy diversity (EHE)',
    'Behavioural Rationality (BRI %)',
]

conditions = ['Governed', 'Ungoverned', 'A1\n(No Ceiling)', 'FQL\nBaseline']

data = [
    ['0.394 ± 0.004', '0.288 ± 0.020', '0.440 ± 0.012', '0.395 ± 0.008'],
    ['1,094',          '1,173',          '1,069',          '1,065'],
    ['0.547 ± 0.083', '0.378 ± 0.081', '0.234 ± 0.127', '0.057 ± 0.323'],
    ['13.3 ± 1.5',    '5.0 ± 1.7',     '25.3 ± 1.5',    '24.7 ± 9.1'],
    ['1,002 ± 1',     '1,001 ± 0.4',   '984 ± 11',      '1,020 ± 4'],
    ['0.738 ± 0.017', '0.637 ± 0.017', '0.793 ± 0.002', '—'],
    ['58.0',           '9.4',            '—',              '—'],
]

# Key insight annotations (which cells to highlight)
# Green = good, Red = bad/notable
# Format: (row, col, 'good'|'bad'|'neutral')
highlights = {
    (0, 0): 'good',   # highest demand ratio with coupling
    (2, 0): 'good',   # highest coupling
    (2, 3): 'bad',    # near-zero coupling
    (5, 0): 'good',   # high diversity
    (5, 2): 'neutral', # higher diversity but decoupled
    (6, 0): 'good',   # high BRI
    (6, 1): 'bad',    # very low BRI
}

# ── Figure ──
fig, ax = plt.subplots(figsize=(12, 5.5))
ax.axis('off')

HEADER_BG = '#4472C4'
HEADER_TEXT = 'white'
ROW_BG_EVEN = '#D6E4F0'
ROW_BG_ODD = '#EBF0F7'
GOOD_BG = '#C6EFCE'
BAD_BG = '#FFC7CE'
BLACK = '#222222'
GREEN = '#006100'
RED = '#9C0006'

n_rows = len(metrics)
n_cols = len(conditions) + 1  # +1 for metric name

row_h = 0.075
header_h = 0.085
left = 0.02
right = 0.98

col_widths_raw = [0.22, 0.17, 0.17, 0.17, 0.17]
total_w = sum(col_widths_raw)
scale = (right - left) / total_w
col_widths = [w * scale for w in col_widths_raw]

top = 0.88

def get_col_x(col_idx):
    return left + sum(col_widths[:col_idx])

# ── Title ──
ax.text(0.5, 0.97, 'Irrigation Domain — Framework Effectiveness Summary',
        ha='center', va='center', fontsize=13, fontweight='bold', color=HEADER_BG)
ax.text(0.5, 0.93, '78 CRSS agents × 42 years × 3 seeds  |  Gemma-3 4B  |  Colorado River Basin',
        ha='center', va='center', fontsize=9, color='#555555')

# ── Column headers ──
headers = ['Metric'] + [c.replace('\n', ' ') for c in conditions]
for j, h in enumerate(headers):
    x = get_col_x(j)
    w = col_widths[j]
    rect = plt.Rectangle((x, top - header_h), w, header_h,
                          facecolor=HEADER_BG, edgecolor='white', lw=1)
    ax.add_patch(rect)
    ax.text(x + w/2, top - header_h/2, h,
            ha='center', va='center', color=HEADER_TEXT, fontsize=9.5, fontweight='bold')

# ── Data rows ──
for i in range(n_rows):
    y = top - header_h - (i + 1) * row_h
    base_bg = ROW_BG_EVEN if i % 2 == 0 else ROW_BG_ODD

    for j in range(n_cols):
        x = get_col_x(j)
        w = col_widths[j]

        # Check highlight
        bg = base_bg
        text_color = BLACK
        if j > 0 and (i, j-1) in highlights:
            hl = highlights[(i, j-1)]
            if hl == 'good':
                bg = GOOD_BG
                text_color = GREEN
            elif hl == 'bad':
                bg = BAD_BG
                text_color = RED

        rect = plt.Rectangle((x, y), w, row_h,
                              facecolor=bg, edgecolor='white', lw=0.5)
        ax.add_patch(rect)

        if j == 0:
            text = metrics[i]
            ha = 'left'
            tx = x + 0.008
            fw = 'bold'
            fs = 9
        else:
            text = data[i][j-1]
            ha = 'center'
            tx = x + w/2
            fw = 'normal'
            fs = 9.5

        ax.text(tx, y + row_h/2, text,
                ha=ha, va='center', color=text_color,
                fontsize=fs, fontweight=fw, family='sans-serif')

# ── Bottom border ──
bottom_y = top - header_h - n_rows * row_h
ax.plot([left, right], [bottom_y, bottom_y], color=HEADER_BG, lw=2)

# ── Key insights box ──
insights = [
    '● Governed agents extract MORE water (0.394 vs 0.288) while coupling to drought (r = 0.547) → adaptive exploitation',
    '● Removing 1 rule of 12 (demand ceiling) → coupling collapses (0.547 → 0.234), shortage doubles → institutional rule decomposition',
    '● FQL extracts same volume (0.395) but zero coupling (r = 0.057) → language reasoning required, not just governance',
    '● Governed BRI 58% vs Ungoverned 9.4% → governance eliminates increase-bias without prescribing actions',
]

box_y = bottom_y - 0.04
ax.text(left, box_y, 'Key Findings for CS Faculty:', fontsize=9, fontweight='bold',
        color=HEADER_BG, va='top')
for k, ins in enumerate(insights):
    ax.text(left + 0.01, box_y - 0.035 - k * 0.032, ins,
            fontsize=8, color='#333333', va='top', family='sans-serif')

ax.set_xlim(0, 1)
ax.set_ylim(box_y - 0.18, 1.0)

for fmt in ['png', 'pdf']:
    out = OUT / f"professor_summary_irrigation.{fmt}"
    fig.savefig(out, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"  Saved: {out}")
plt.close()
print("Done.")
