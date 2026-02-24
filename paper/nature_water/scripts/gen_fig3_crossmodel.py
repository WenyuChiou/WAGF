"""
Nature Water -- Supplementary Figure 1: Cross-model behavioural diversity governance effect (flood domain)
  (a) Paired dot plot -- Behavioural diversity by model (ungoverned vs governed)
  (b) Forest plot -- Delta behavioural diversity with 95% CI
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path

# -- Paths --
BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework")
OUT = BASE / "paper" / "nature_water" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# -- Style (Nature Water) --
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica'],
    'font.size': 7.5,
    'axes.labelsize': 8,
    'axes.titlesize': 9,
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'legend.fontsize': 7,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.spines.top': False,
    'axes.spines.right': False,
})

# Colors
GOV_COLOR   = '#2166AC'   # blue
UNGOV_COLOR = '#B2182B'   # red
SIG_COLOR   = '#2166AC'   # significant CI
NS_COLOR    = '#999999'   # non-significant CI
LINE_COLOR  = '#888888'   # connecting lines

# ====================================================================
# DATA  (from Table 3 and Table S1b)
# Sorted by parameter count: 3B, 4B, 8B, 12B, 14B, 27B
# ====================================================================

models = [
    'Ministral 3B',
    'Gemma-3 4B',
    'Ministral 8B',
    'Gemma-3 12B',
    'Ministral 14B',
    'Gemma-3 27B',
]
families = ['Ministral', 'Gemma-3', 'Ministral', 'Gemma-3', 'Ministral', 'Gemma-3']

# EHE values (Table 3)
ungov_ehe  = np.array([0.373, 0.307, 0.555, 0.282, 0.572, 0.322])
ungov_sd   = np.array([0.061, 0.059, 0.009, 0.012, 0.018, 0.020])
gov_ehe    = np.array([0.571, 0.636, 0.531, 0.310, 0.605, 0.496])
gov_sd     = np.array([0.047, 0.044, 0.028, 0.048, 0.011, 0.051])

# Delta EHE + 95% CI (Table 3)
delta_ehe  = np.array([+0.198, +0.329, -0.024, +0.027, +0.034, +0.174])
ci_lo      = np.array([+0.072, +0.207, -0.085, -0.083, -0.002, +0.065])
ci_hi      = np.array([+0.325, +0.450, +0.038, +0.138, +0.069, +0.284])

# Significance: CI does not cross zero
significant = np.array([True, True, False, False, False, True])

n = len(models)
y_pos = np.arange(n)

# Pooled effect (computed from individual deltas; used in panel b)
pooled_mean = np.mean(delta_ehe)
pooled_se   = np.std(delta_ehe, ddof=1) / np.sqrt(n)
pooled_ci   = [pooled_mean - 1.96 * pooled_se, pooled_mean + 1.96 * pooled_se]
y_pooled    = n + 0.8  # one clear step below last model row

# ====================================================================
# FIGURE
# ====================================================================

fig = plt.figure(figsize=(7.09, 3.5))
gs = gridspec.GridSpec(1, 2, width_ratios=[1.1, 1], wspace=0.35)

# ------------------------------------------------------------------
# Panel (a): Paired dot plot
# ------------------------------------------------------------------
ax_a = fig.add_subplot(gs[0])

for i in range(n):
    # Connecting line
    ls = '-' if gov_ehe[i] >= ungov_ehe[i] else '--'
    ax_a.plot([ungov_ehe[i], gov_ehe[i]], [y_pos[i], y_pos[i]],
              color=LINE_COLOR, linewidth=1.0, linestyle=ls, zorder=1)

# Dots
ax_a.scatter(ungov_ehe, y_pos, c=UNGOV_COLOR, s=40, zorder=2,
             edgecolors='white', linewidths=0.5, label='Ungoverned')
ax_a.scatter(gov_ehe, y_pos, c=GOV_COLOR, s=40, zorder=2,
             edgecolors='white', linewidths=0.5, label='Governed')

ax_a.set_yticks(y_pos)
ax_a.set_yticklabels(models)
ax_a.set_xlabel('Behavioural diversity')
ax_a.set_xlim(0.15, 0.85)
ax_a.invert_yaxis()

# Family brackets (right side)
# Gemma-3 indices: 1, 3, 5  |  Ministral indices: 0, 2, 4
gemma_idx = [i for i, f in enumerate(families) if f == 'Gemma-3']
minis_idx = [i for i, f in enumerate(families) if f == 'Ministral']

bracket_x = 0.82  # in data coords
bracket_dx = 0.01

for idx_list, label in [(gemma_idx, 'Gemma-3'), (minis_idx, 'Ministral')]:
    y_min = min(idx_list)
    y_max = max(idx_list)
    # Draw bracket in axes fraction
    ax_a.annotate('', xy=(bracket_x, y_min - 0.15), xytext=(bracket_x, y_max + 0.15),
                  arrowprops=dict(arrowstyle='-', color='#555555', lw=0.8),
                  annotation_clip=False)
    # Ticks at top and bottom
    for y_end in [y_min - 0.15, y_max + 0.15]:
        ax_a.plot([bracket_x - bracket_dx, bracket_x], [y_end, y_end],
                  color='#555555', lw=0.8, clip_on=False)
    # Label
    mid_y = (y_min + y_max) / 2
    ax_a.text(bracket_x + 0.015, mid_y, label, fontsize=6.5, va='center',
              rotation=270, color='#555555', clip_on=False)

ax_a.legend(loc='lower right', frameon=False, markerscale=0.9)
ax_a.text(-0.15, -0.08, '(a)', transform=ax_a.transAxes,
          fontsize=9, fontweight='bold', va='top')

# ------------------------------------------------------------------
# Panel (b): Forest plot -- Delta EHE + 95% CI
# ------------------------------------------------------------------
ax_b = fig.add_subplot(gs[1])

for i in range(n):
    color = SIG_COLOR if significant[i] else NS_COLOR
    # CI bar
    ax_b.plot([ci_lo[i], ci_hi[i]], [y_pos[i], y_pos[i]],
              color=color, linewidth=2.0, solid_capstyle='round', zorder=1)
    # Point estimate
    ax_b.scatter(delta_ehe[i], y_pos[i], c=color, s=35, zorder=2,
                 edgecolors='white', linewidths=0.5)
    # Annotation
    x_annot = ci_hi[i] + 0.015
    ax_b.text(x_annot, y_pos[i], f'{delta_ehe[i]:+.3f}', fontsize=6.5,
              va='center', ha='left', color=color)

# Pooled-effect diamond
POOL_COLOR = '#222222'
# Horizontal separator above pooled row
ax_b.axhline(n + 0.35, color='#cccccc', linewidth=0.6, linestyle='-', zorder=0)
# CI bar
ax_b.plot([pooled_ci[0], pooled_ci[1]], [y_pooled, y_pooled],
          color=POOL_COLOR, linewidth=2.0, solid_capstyle='round', zorder=1)
# Diamond marker (rotated square via marker='D')
ax_b.scatter(pooled_mean, y_pooled, marker='D', c=POOL_COLOR, s=50, zorder=2,
             edgecolors='white', linewidths=0.5)
# Annotation
ax_b.text(pooled_ci[1] + 0.015, y_pooled,
          f'{pooled_mean:+.3f}', fontsize=6.5,
          va='center', ha='left', color=POOL_COLOR)

# Vertical zero line
ax_b.axvline(0, color='#333333', linewidth=0.6, linestyle='--', zorder=0)

# Y-axis ticks: individual models (blank labels, shared with panel a) + pooled row
all_yticks  = list(y_pos) + [y_pooled]
all_ylabels = [''] * n + ['Pooled']
ax_b.set_yticks(all_yticks)
ax_b.set_yticklabels(all_ylabels)
ax_b.set_xlabel('\u0394 Behavioural diversity (governed \u2212 ungoverned)')
ax_b.set_xlim(-0.15, 0.55)
ax_b.set_ylim(-0.6, y_pooled + 0.6)
ax_b.invert_yaxis()

ax_b.text(-0.08, -0.08, '(b)', transform=ax_b.transAxes,
          fontsize=9, fontweight='bold', va='top')

# ------------------------------------------------------------------
# Save
# ------------------------------------------------------------------
for ext in ['png', 'pdf']:
    fpath = OUT / f'FigS1_crossmodel.{ext}'
    fig.savefig(fpath, dpi=300, bbox_inches='tight', facecolor='white')
    print(f'Saved: {fpath}')

plt.close(fig)
print('Done.')
