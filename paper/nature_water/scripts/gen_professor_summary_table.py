"""
Generate professor-facing summary table: IBR + Strategy Diversity across 6 models × 3 groups.
Style: clean academic table with colored deltas (similar to user's screenshot).
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from pathlib import Path

OUT = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\paper\nature_water\professor_briefing")

# ── Data from SI Table 1 + Table 2 ──
# IBR (R_H %) — means across 3 seeds
# Group A = Ungoverned, Group B = Governed (window memory, 4B only), Group C = Governed (HumanCentric)
models = [
    'Gemma-3 4B',
    'Gemma-3 12B',
    'Gemma-3 27B',
    'Ministral 3B',
    'Ministral 8B',
    'Ministral 14B',
]

ibr = {
    'A': [1.15, 3.35, 0.78, 8.89, 1.56, 11.61],
    'B': [0.86, None, None, None, None, None],  # Only 4B has Group B
    'C': [0.86, 0.15, 0.33, 1.70, 0.13, 0.40],
}

ehe = {
    'A': [0.307, 0.282, 0.322, 0.373, 0.555, 0.572],
    'B': [0.636, None, None, None, None, None],  # Only 4B has Group B
    'C': [0.636, 0.310, 0.496, 0.571, 0.531, 0.605],
}

# ── Figure setup ──
fig, ax = plt.subplots(figsize=(14, 4.5))
ax.axis('off')

# Column headers
col_headers_top = ['', 'IBR (%)', '', '', '', '',
                   'Strategy Diversity (EHE)', '', '', '', '']
col_headers = ['Model', 'Group A', 'Group B', 'Group C', 'ΔR (B−A)', 'ΔR (C−A)',
               'Group A', 'Group B', 'Group C', 'ΔEHE (B−A)', 'ΔEHE (C−A)']

n_rows = len(models)
n_cols = len(col_headers)

# Table dimensions
row_h = 0.065
header_h = 0.07
top_header_h = 0.06
left = 0.02
right = 0.98
top = 0.92
col_widths = [0.11, 0.07, 0.07, 0.07, 0.08, 0.08,
              0.07, 0.07, 0.07, 0.09, 0.09]
total_w = sum(col_widths)
scale = (right - left) / total_w
col_widths = [w * scale for w in col_widths]

# Colors
HEADER_BG = '#4472C4'
HEADER_TEXT = 'white'
ROW_BG_EVEN = '#D6E4F0'
ROW_BG_ODD = '#EBF0F7'
RED = '#C00000'
GREEN = '#008000'
BLACK = '#222222'

def get_col_x(col_idx):
    return left + sum(col_widths[:col_idx])

# ── Draw top header (merged) ──
# IBR block: cols 1-5
ibr_x = get_col_x(1)
ibr_w = sum(col_widths[1:6])
rect = plt.Rectangle((ibr_x, top), ibr_w, top_header_h,
                      facecolor=HEADER_BG, edgecolor='white', lw=1)
ax.add_patch(rect)
ax.text(ibr_x + ibr_w/2, top + top_header_h/2, 'IBR (%)',
        ha='center', va='center', color=HEADER_TEXT, fontsize=11, fontweight='bold')

# EHE block: cols 6-10
ehe_x = get_col_x(6)
ehe_w = sum(col_widths[6:11])
rect = plt.Rectangle((ehe_x, top), ehe_w, top_header_h,
                      facecolor=HEADER_BG, edgecolor='white', lw=1)
ax.add_patch(rect)
ax.text(ehe_x + ehe_w/2, top + top_header_h/2, 'Strategy Diversity (EHE)',
        ha='center', va='center', color=HEADER_TEXT, fontsize=11, fontweight='bold')

# Model header
rect = plt.Rectangle((left, top), col_widths[0], top_header_h,
                      facecolor=HEADER_BG, edgecolor='white', lw=1)
ax.add_patch(rect)

# ── Draw column headers ──
header_y = top - header_h
for j, h in enumerate(col_headers):
    x = get_col_x(j)
    w = col_widths[j]
    rect = plt.Rectangle((x, header_y), w, header_h,
                          facecolor=HEADER_BG, edgecolor='white', lw=1)
    ax.add_patch(rect)
    ax.text(x + w/2, header_y + header_h/2, h,
            ha='center', va='center', color=HEADER_TEXT, fontsize=9, fontweight='bold')

# ── Draw data rows ──
for i, model in enumerate(models):
    y = header_y - (i + 1) * row_h
    bg = ROW_BG_EVEN if i % 2 == 0 else ROW_BG_ODD

    # Compute deltas
    ibr_ba = (ibr['B'][i] - ibr['A'][i]) if ibr['B'][i] is not None else None
    ibr_ca = ibr['C'][i] - ibr['A'][i]
    ehe_ba = (ehe['B'][i] - ehe['A'][i]) if ehe['B'][i] is not None else None
    ehe_ca = ehe['C'][i] - ehe['A'][i]

    row_data = [
        model,
        f"{ibr['A'][i]:.2f}",
        f"{ibr['B'][i]:.2f}" if ibr['B'][i] is not None else '—',
        f"{ibr['C'][i]:.2f}",
        f"{ibr_ba:+.3f}" if ibr_ba is not None else '—',
        f"{ibr_ca:+.3f}",
        f"{ehe['A'][i]:.3f}",
        f"{ehe['B'][i]:.3f}" if ehe['B'][i] is not None else '—',
        f"{ehe['C'][i]:.3f}",
        f"{ehe_ba:+.3f}" if ehe_ba is not None else '—',
        f"{ehe_ca:+.3f}",
    ]

    # Delta color logic: IBR decrease = good (red), EHE increase = good (red)
    row_colors = [BLACK] * n_cols
    # IBR deltas (cols 4, 5): negative = good → red
    if ibr_ba is not None and ibr_ba < 0:
        row_colors[4] = RED
    if ibr_ca < 0:
        row_colors[5] = RED
    # EHE deltas (cols 9, 10): positive = good → red highlight
    if ehe_ba is not None and ehe_ba > 0.05:
        row_colors[9] = RED
    if ehe_ca > 0.05:
        row_colors[10] = RED

    for j in range(n_cols):
        x = get_col_x(j)
        w = col_widths[j]
        rect = plt.Rectangle((x, y), w, row_h,
                              facecolor=bg, edgecolor='white', lw=0.5)
        ax.add_patch(rect)

        ha = 'left' if j == 0 else 'center'
        tx = x + 0.008 if j == 0 else x + w/2
        fw = 'bold' if j == 0 else 'normal'

        ax.text(tx, y + row_h/2, row_data[j],
                ha=ha, va='center', color=row_colors[j],
                fontsize=9, fontweight=fw, family='sans-serif')

# ── Bottom border ──
bottom_y = header_y - n_rows * row_h
ax.plot([left, right], [bottom_y, bottom_y], color=HEADER_BG, lw=2)

# ── Footnote ──
ax.text(left, bottom_y - 0.04,
        'IBR = Irrational Behaviour Rate (lower is better). '
        'EHE = Strategy Diversity via normalized Shannon entropy (higher is better).\n'
        'Group A = Ungoverned.  Group B = Governed (window memory, Gemma-3 4B only).  '
        'Group C = Governed (HumanCentric memory).\n'
        'Red highlights: IBR reduction (governance reduces irrationality) or EHE increase > 0.05 '
        '(governance widens diversity).  All flood domain, 100 agents × 10 yr, 3 seeds.',
        fontsize=7.5, color='#555555', va='top', family='sans-serif')

ax.set_xlim(0, 1)
ax.set_ylim(bottom_y - 0.12, top + top_header_h + 0.02)

for fmt in ['png', 'pdf']:
    out = OUT / f"professor_summary_IBR_EHE.{fmt}"
    fig.savefig(out, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"  Saved: {out}")
plt.close()
print("Done.")
