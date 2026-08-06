"""Render the review-only Figure 1 D v2 candidate.

This source deliberately uses deterministic vector primitives.  It borrows the
icon-plus-short-label register from the WAGF/agent-collab diagrams, while
keeping paper labels, arrow endpoints, and routing machine-checkable.

The script writes only into this review directory.  It does not replace the
active Figure 1 or rebuild the submission PDF.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon


OUT = Path(__file__).resolve().parent
W, H = 18.0, 8.4

NAVY = "#172B4D"
BLUE = "#2166D1"
BLUE_FILL = "#EAF1FF"
YELLOW = "#D89000"
YELLOW_FILL = "#FFF4C7"
CORAL = "#E84855"
CORAL_FILL = "#FFECEF"
PURPLE = "#5B37C7"
PURPLE_FILL = "#F0ECFF"
MUTED = "#5D6B82"
PALE = "#F7F9FC"
GRID = "#D7DEE8"
RETRY_FILL = "#FBFCFE"

# The review canvas is intentionally roomy, but the paper-width export is
# rendered at the same data geometry in a much smaller physical canvas.  Keep
# labels legible without letting them grow into neighboring cards when the
# figure is reduced for a two-column paper.
FONT_SCALE = 1.0


def card(ax, x, y, w, h, *, edge=NAVY, fill="white", lw=1.8,
         radius=0.16, linestyle="-"):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.025,rounding_size={radius}",
        linewidth=lw,
        edgecolor=edge,
        facecolor=fill,
        linestyle=linestyle,
        zorder=1,
    )
    ax.add_patch(patch)
    return patch


def label(ax, texts, role, x, y, value, *, size=10.5, color=NAVY,
          weight="normal", ha="center", va="center", linespacing=1.08):
    artist = ax.text(
        x, y, value,
        color=color,
        fontsize=size * FONT_SCALE,
        fontweight=weight,
        ha=ha,
        va=va,
        linespacing=linespacing,
        zorder=10,
    )
    texts.append((role, artist))
    return artist


def arrow(ax, routes, name, points, *, color=NAVY, lw=2.0,
          dashed=False, scale=15, target=None):
    """Draw one route and register its semantic endpoint for validation."""
    style = (0, (5, 3)) if dashed else "-"
    for p1, p2 in zip(points[:-2], points[1:-1]):
        ax.plot(
            [p1[0], p2[0]], [p1[1], p2[1]],
            color=color,
            linewidth=lw,
            linestyle=style,
            solid_capstyle="round",
            zorder=4,
        )
    patch = FancyArrowPatch(
        points[-2], points[-1],
        arrowstyle="-|>",
        mutation_scale=scale,
        linewidth=lw,
        color=color,
        linestyle=style,
        shrinkA=0,
        shrinkB=0,
        zorder=5,
    )
    ax.add_patch(patch)
    routes.append((name, points, target))
    return patch


def agent_icon(ax, x, y, color=NAVY, scale=1.0):
    ax.add_patch(Circle((x, y + 0.13 * scale), 0.10 * scale,
                        fill=False, edgecolor=color, linewidth=1.7, zorder=6))
    ax.plot([x - 0.19 * scale, x, x + 0.19 * scale],
            [y - 0.15 * scale, y - 0.01 * scale, y - 0.15 * scale],
            color=color, linewidth=1.7, solid_capstyle="round", zorder=6)
    ax.plot([x - 0.08 * scale, x + 0.08 * scale],
            [y - 0.20 * scale, y - 0.20 * scale],
            color=color, linewidth=1.4, solid_capstyle="round", zorder=6)


def document_icon(ax, x, y, color=BLUE, scale=1.0):
    w, h = 0.29 * scale, 0.39 * scale
    pts = [(x - w / 2, y - h / 2), (x + w / 2 - 0.07 * scale, y - h / 2),
           (x + w / 2, y - h / 2 + 0.07 * scale),
           (x + w / 2, y + h / 2), (x - w / 2, y + h / 2)]
    ax.add_patch(Polygon(pts, closed=True, fill=False, edgecolor=color,
                         linewidth=1.7, zorder=6))
    ax.plot([x - 0.07 * scale, x + 0.10 * scale],
            [y + 0.08 * scale, y + 0.08 * scale], color=color,
            linewidth=1.3, zorder=6)
    ax.plot([x - 0.07 * scale, x + 0.10 * scale],
            [y - 0.02 * scale, y - 0.02 * scale], color=color,
            linewidth=1.3, zorder=6)


def state_icon(ax, x, y, color=YELLOW, scale=1.0):
    w, h = 0.43 * scale, 0.28 * scale
    ax.add_patch(FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle=f"round,pad=0.01,rounding_size={0.07 * scale}",
        fill=False, edgecolor=color, linewidth=1.7, zorder=6,
    ))
    ax.plot([x - 0.10 * scale, x + 0.10 * scale],
            [y - h / 2 - 0.07 * scale, y - h / 2],
            color=color, linewidth=1.5, zorder=6)
    ax.add_patch(Circle((x + 0.10 * scale, y + 0.02 * scale), 0.035 * scale,
                        fill=False, edgecolor=color, linewidth=1.2, zorder=6))


def shield_stop_icon(ax, x, y, color=CORAL, scale=1.0):
    pts = [(x - 0.22 * scale, y + 0.20 * scale),
           (x + 0.22 * scale, y + 0.20 * scale),
           (x + 0.16 * scale, y - 0.13 * scale),
           (x, y - 0.31 * scale),
           (x - 0.16 * scale, y - 0.13 * scale)]
    ax.add_patch(Polygon(pts, closed=True, fill=False, edgecolor=color,
                         linewidth=1.8, joinstyle="round", zorder=6))
    ax.plot([x - 0.10 * scale, x + 0.10 * scale],
            [y - 0.02 * scale, y - 0.02 * scale], color=color,
            linewidth=2.0, solid_capstyle="round", zorder=6)


def funnel_records_icon(ax, x, y, color=PURPLE, scale=1.0):
    pts = [(x - 0.25 * scale, y + 0.19 * scale),
           (x + 0.25 * scale, y + 0.19 * scale),
           (x + 0.08 * scale, y - 0.03 * scale),
           (x + 0.08 * scale, y - 0.29 * scale),
           (x - 0.08 * scale, y - 0.29 * scale),
           (x - 0.08 * scale, y - 0.03 * scale)]
    ax.add_patch(Polygon(pts, closed=True, fill=False, edgecolor=color,
                         linewidth=1.8, joinstyle="round", zorder=6))
    for yy in (-0.02, -0.12, -0.22):
        ax.add_patch(Circle((x + 0.17 * scale, y + yy * scale), 0.025 * scale,
                            fill=False, edgecolor=color, linewidth=1.1, zorder=6))


def fraction_icon(ax, x, y, color=PURPLE, scale=1.0):
    """Draw a neutral ratio mark; it is not an observed metric value."""
    ax.text(x, y + 0.10 * scale, "x", color=color,
            fontsize=8.5 * scale * FONT_SCALE,
            ha="center", va="center", fontweight="bold", zorder=6)
    ax.plot([x - 0.12 * scale, x + 0.12 * scale],
            [y, y], color=color, linewidth=1.6, zorder=6)
    ax.text(x, y - 0.13 * scale, "y", color=color,
            fontsize=8.5 * scale * FONT_SCALE,
            ha="center", va="center", fontweight="bold", zorder=6)


def retry_icon(ax, x, y, color=CORAL, scale=1.0):
    ax.add_patch(FancyArrowPatch(
        (x - 0.20 * scale, y - 0.03 * scale),
        (x + 0.18 * scale, y + 0.15 * scale),
        connectionstyle="arc3,rad=0.55",
        arrowstyle="-|>", mutation_scale=12 * scale,
        linewidth=1.8, color=color, zorder=6,
    ))


def records_icon(ax, x, y, color=PURPLE, scale=1.0):
    for dy in (0.10, 0.0, -0.10):
        ax.add_patch(FancyBboxPatch(
            (x - 0.23 * scale, y + dy * scale - 0.055 * scale),
            0.46 * scale, 0.11 * scale,
            boxstyle="round,pad=0.005,rounding_size=0.025",
            fill=False, edgecolor=color, linewidth=1.3, zorder=6,
        ))
        ax.add_patch(Circle((x - 0.14 * scale, y + dy * scale),
                            0.018 * scale, fill=False, edgecolor=color,
                            linewidth=1.0, zorder=6))


def text_collisions(fig, texts):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = []
    for role, artist in texts:
        bbox = artist.get_window_extent(renderer).expanded(1.01, 1.06)
        boxes.append((role, bbox))
    collisions = []
    for idx, (role_a, box_a) in enumerate(boxes):
        for role_b, box_b in boxes[idx + 1:]:
            if box_a.overlaps(box_b):
                collisions.append((role_a, role_b))
    return collisions


def point_in_rect(point, rect, margin=0.0):
    x, y = point
    rx, ry, rw, rh = rect
    return (rx - margin <= x <= rx + rw + margin and
            ry - margin <= y <= ry + rh + margin)


def assert_routes(routes):
    for name, points, target in routes:
        if target is not None and not point_in_rect(points[-1], target, margin=0.03):
            raise RuntimeError(f"{name}: endpoint {points[-1]} misses target {target}")


def build(show_header=True, figsize=(W, H)):
    global FONT_SCALE
    # At 6.8 in wide, 0.60 keeps the nominal 8--13 pt labels in the range
    # normally used for conference figures while preserving their hierarchy.
    FONT_SCALE = 1.0 if show_header else 0.60
    fig, ax = plt.subplots(figsize=figsize, dpi=240)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    texts = []
    routes = []

    if show_header:
        label(ax, texts, "header", 0.42, 8.08,
              "Reported state: one field, two downstream roles",
              size=15.0, weight="bold", ha="left")
        label(ax, texts, "subheader", 0.42, 7.72,
              "The same agent-reported state is read by governance and used to select records for measurement.",
              size=8.8, color=MUTED, ha="left")

    # Main nodes.
    answer = (0.45, 3.45, 3.25, 3.30)
    shared = (4.35, 4.45, 2.75, 1.55)
    validator = (8.00, 5.35, 3.15, 1.45)
    selector = (8.00, 3.45, 3.15, 1.45)
    rate = (12.15, 3.15, 5.25, 3.65)
    action_row = (0.72, 5.48, 2.70, 0.72)
    state_row = (0.72, 4.05, 2.70, 1.00)
    numerator = (12.55, 5.20, 4.35, 0.75)
    denominator = (12.55, 3.75, 4.35, 0.90)

    card(ax, *answer, edge=NAVY, fill=PALE, lw=2.0, radius=0.18)
    agent_icon(ax, 0.93, 6.27, scale=0.9)
    label(ax, texts, "answer-title", 1.16, 6.34, "agent answer",
          size=12.0, weight="bold", ha="left")
    card(ax, *action_row, edge=BLUE, fill=BLUE_FILL, lw=1.5, radius=0.10)
    document_icon(ax, 1.05, 5.84, scale=0.78)
    label(ax, texts, "action-label", 2.10, 5.91, "action",
          size=10.8, weight="bold")
    card(ax, *state_row, edge=YELLOW, fill=YELLOW_FILL, lw=1.5, radius=0.10)
    state_icon(ax, 1.05, 4.61, scale=0.82)
    label(ax, texts, "state-label", 2.40, 4.76, "reported state",
          size=10.4, weight="bold")
    label(ax, texts, "state-example", 2.25, 4.38, "high scarcity",
          size=8.8, color=YELLOW)

    card(ax, *shared, edge=YELLOW, fill=YELLOW_FILL, lw=2.4, radius=0.22)
    # In the compact card, stack the icon above the label so the icon never
    # competes with the long phrase "reported state" at paper width.
    state_icon(ax, 4.72, 5.70, scale=0.52)
    label(ax, texts, "shared-title", 5.75, 5.38, "reported state",
          size=11.4, weight="bold")
    label(ax, texts, "shared-subtitle", 5.75, 4.82, "shared field",
          size=9.0, color=YELLOW, weight="bold")

    card(ax, *validator, edge=CORAL, fill=CORAL_FILL, lw=2.0, radius=0.16)
    shield_stop_icon(ax, 8.45, 6.10, scale=0.78)
    label(ax, texts, "validator-title", 9.85, 6.28, "rule check",
          size=11.5, weight="bold")
    label(ax, texts, "validator-body", 9.85, 5.78, "reads state",
          size=9.4, color=CORAL)

    card(ax, *selector, edge=PURPLE, fill=PURPLE_FILL, lw=2.0, radius=0.16)
    funnel_records_icon(ax, 8.45, 4.20, scale=0.78)
    label(ax, texts, "selector-title", 9.85, 4.38, "record filter",
          size=11.5, weight="bold")
    label(ax, texts, "selector-body", 9.85, 3.88, "selects rate records",
          size=9.4, color=PURPLE)

    card(ax, *rate, edge=PURPLE, fill="white", lw=2.2, radius=0.20)
    fraction_icon(ax, 12.78, 6.34, scale=0.78)
    label(ax, texts, "rate-title", 14.82, 6.39,
          "conditional conformance\nrate", size=12.0, weight="bold",
          linespacing=1.0)
    # The numerator card itself is the visual separator below the title;
    # another line here would run into its rounded top border at paper scale.
    card(ax, *numerator, edge=BLUE, fill=BLUE_FILL, lw=1.4, radius=0.09)
    label(ax, texts, "numerator", 14.73, 5.58,
          "actions in selected\nrecords", size=9.6, weight="bold")
    ax.plot([12.78, 16.67], [5.03, 5.03], color=NAVY, linewidth=1.3, zorder=2)
    card(ax, *denominator, edge=YELLOW, fill=YELLOW_FILL, lw=1.5, radius=0.09)
    label(ax, texts, "denominator", 14.73, 4.20,
          "records with\nhigh scarcity", size=9.8)

    # Retry strip: separate from all main routes.
    retry_panel = (6.75, 0.35, 6.55, 1.85)
    card(ax, *retry_panel, edge=GRID, fill=RETRY_FILL, lw=1.3,
         radius=0.15, linestyle="--")
    label(ax, texts, "retry-header", 6.95, 2.02, "retry path",
          size=9.0, color=CORAL, weight="bold", ha="left")
    blocked = (7.10, 0.78, 1.50, 0.98)
    reprompt = (9.00, 0.78, 1.50, 0.98)
    recorded = (10.90, 0.78, 2.15, 0.98)
    card(ax, *blocked, edge=CORAL, fill=CORAL_FILL, lw=1.6, radius=0.12)
    shield_stop_icon(ax, 7.37, 1.30, scale=0.40)
    label(ax, texts, "blocked-label", 8.15, 1.31, "blocked",
          size=9.3, color=CORAL, weight="bold")
    card(ax, *reprompt, edge=CORAL, fill=CORAL_FILL, lw=1.6, radius=0.12)
    label(ax, texts, "reprompt-label", 9.75, 1.31, "re-prompt",
          size=8.7, color=CORAL, weight="bold")
    card(ax, *recorded, edge=PURPLE, fill=PURPLE_FILL, lw=1.6, radius=0.12)
    document_icon(ax, 11.25, 1.31, color=PURPLE, scale=0.56)
    label(ax, texts, "recorded-title", 12.20, 1.49, "new answer",
          size=9.1, color=PURPLE, weight="bold")
    label(ax, texts, "recorded-body", 12.20, 1.08, "recorded set\nmay change",
          size=7.8, color=PURPLE)

    # Main routes.  Each endpoint is inside a target card, not on a label.
    arrow(ax, routes, "action_to_validator",
          [(3.42, 5.84), (3.85, 5.84), (3.85, 6.42), (8.08, 6.42)],
          color=BLUE, lw=2.0, target=validator)
    arrow(ax, routes, "state_to_shared",
          [(3.42, 4.55), (3.92, 4.55), (3.92, 5.22), (4.40, 5.22)],
          color=YELLOW, lw=2.0, target=shared)
    arrow(ax, routes, "shared_to_validator",
          [(7.10, 5.48), (7.55, 5.48), (7.55, 5.96), (8.08, 5.96)],
          color=CORAL, lw=2.0, target=validator)
    arrow(ax, routes, "shared_to_selector",
          [(7.10, 4.96), (7.55, 4.96), (7.55, 4.16), (8.08, 4.16)],
          color=PURPLE, lw=2.0, target=selector)
    arrow(ax, routes, "selector_to_rate",
          # Route above the retry corridor, then enter the rate container as
          # a whole.  This avoids implying that the filter only changes the
          # denominator and keeps the purple path separate from the dashed
          # coral feedback path.
          [(11.18, 4.16), (11.80, 4.16), (11.80, 5.55), (12.22, 5.55)],
          color=PURPLE, lw=2.0, target=rate)

    # A dashed feedback route uses the outer whitespace corridor to avoid the
    # measurement card and the rate card entirely.
    arrow(ax, routes, "validator_to_blocked",
          [(10.90, 5.35), (11.55, 5.35), (11.55, 2.38),
           (8.30, 2.38), (8.30, 1.74)],
          color=CORAL, lw=1.8, dashed=True, scale=14, target=blocked)
    arrow(ax, routes, "blocked_to_reprompt",
          [(8.62, 1.27), (9.08, 1.27)],
          color=CORAL, lw=1.8, target=reprompt)
    arrow(ax, routes, "reprompt_to_recorded",
          [(10.52, 1.27), (10.98, 1.27)],
          color=PURPLE, lw=1.8, target=recorded)

    return fig, ax, texts, routes


def save_variant(name, *, show_header=True, figsize=(W, H), dpi=260):
    fig, ax, texts, routes = build(show_header=show_header, figsize=figsize)
    assert_routes(routes)
    collisions = text_collisions(fig, texts)
    if collisions:
        raise RuntimeError(f"{name}: text collisions: {collisions}")
    png = OUT / f"{name}.png"
    pdf = OUT / f"{name}.pdf"
    fig.savefig(png, dpi=dpi, bbox_inches="tight", pad_inches=0.10)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.10)
    plt.close(fig)
    print(f"{name}: PASS text-overlap=0 routes={len(routes)} -> {png.name}")


if __name__ == "__main__":
    save_variant("fig1_D_v2_icon_lens", show_header=True)
    save_variant("fig1_D_v2_paper_preview", show_header=False,
                 figsize=(6.8, 3.18), dpi=320)
