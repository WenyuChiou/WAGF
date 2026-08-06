"""Generate five candidate Figure 1 concepts for user selection.

These are review-only previews.  They deliberately use deterministic
Matplotlib primitives rather than image-generated text: every label and arrow
can therefore be checked before one candidate is promoted into the paper
source.  The candidates differ in visual argument, not in the scientific
claim:

    A  two-lane flow: one answer feeds validation and measurement
    B  central hinge: the same reported field is visibly split in two
    C  retry timeline: re-prompting can change the recorded answer set
    D  measurement lens: the denominator is the visual focal point
    E  four-step storyboard: a one-glance lifecycle for a single decision

Usage:
    python SUBMISSION_2026/TAE/figures/_candidates/generate_fig1_candidates.py
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon


OUT = Path(__file__).resolve().parent
NAVY = "#172B4D"
BLUE = "#2166D1"
BLUE_FILL = "#EAF1FF"
YELLOW = "#E39A00"
YELLOW_FILL = "#FFF5C7"
CORAL = "#E84855"
CORAL_FILL = "#FFECEF"
PURPLE = "#5B37C7"
PURPLE_FILL = "#F0ECFF"
MUTED = "#5D6B82"
PALE = "#F7F9FC"


def canvas(title: str, message: str, width: float = 18.0, height: float = 7.0):
    fig, ax = plt.subplots(figsize=(width, height), dpi=220)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")
    texts = []
    texts.append(("title", ax.text(0.42, height - 0.36, title, color=NAVY,
                                    fontsize=16, fontweight="bold", ha="left", va="top")))
    texts.append(("message", ax.text(0.42, height - 0.78, message, color=MUTED,
                                      fontsize=9.2, ha="left", va="top")))
    return fig, ax, texts


def text(ax, texts, x, y, value, *, size=11, color=NAVY, weight="normal",
         ha="center", va="center", role="body", linespacing=1.12):
    artist = ax.text(x, y, value, color=color, fontsize=size, fontweight=weight,
                     ha=ha, va=va, linespacing=linespacing)
    texts.append((role, artist))
    return artist


def box(ax, x, y, w, h, *, edge=NAVY, fill="white", lw=2.0, radius=0.18):
    patch = FancyBboxPatch((x, y), w, h,
                           boxstyle=f"round,pad=0.025,rounding_size={radius}",
                           linewidth=lw, edgecolor=edge, facecolor=fill)
    ax.add_patch(patch)
    return patch


def arrow(ax, points, *, color=NAVY, lw=2.25, dashed=False, scale=17):
    """Draw an orthogonal polyline with one unambiguous terminal arrowhead."""
    style = (0, (5, 3)) if dashed else "-"
    for p1, p2 in zip(points[:-2], points[1:-1]):
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=color, lw=lw,
                linestyle=style, solid_capstyle="round", zorder=3)
    line = FancyArrowPatch(points[-2], points[-1], arrowstyle="-|>",
                           mutation_scale=scale, linewidth=lw, color=color,
                           linestyle=style, shrinkA=0, shrinkB=0, zorder=4)
    ax.add_patch(line)
    return line


def person_icon(ax, x, y, color=NAVY, scale=1.0):
    ax.add_patch(Circle((x, y + 0.18 * scale), 0.11 * scale,
                        fill=False, edgecolor=color, linewidth=1.8, zorder=5))
    ax.plot([x - 0.2 * scale, x, x + 0.2 * scale],
            [y - 0.18 * scale, y - 0.02 * scale, y - 0.18 * scale],
            color=color, linewidth=1.8, solid_capstyle="round", zorder=5)


def shield_icon(ax, x, y, color=CORAL, scale=1.0):
    pts = [(x - 0.22 * scale, y + 0.20 * scale),
           (x + 0.22 * scale, y + 0.20 * scale),
           (x + 0.17 * scale, y - 0.17 * scale),
           (x, y - 0.33 * scale),
           (x - 0.17 * scale, y - 0.17 * scale)]
    ax.add_patch(Polygon(pts, closed=True, fill=False, edgecolor=color,
                         linewidth=1.8, zorder=5))


def funnel_icon(ax, x, y, color=PURPLE, scale=1.0):
    pts = [(x - 0.25 * scale, y + 0.20 * scale),
           (x + 0.25 * scale, y + 0.20 * scale),
           (x + 0.08 * scale, y - 0.02 * scale),
           (x + 0.08 * scale, y - 0.30 * scale),
           (x - 0.08 * scale, y - 0.30 * scale),
           (x - 0.08 * scale, y - 0.02 * scale)]
    ax.add_patch(Polygon(pts, closed=True, fill=False, edgecolor=color,
                         linewidth=1.8, zorder=5))


def answer_card(ax, texts, x, y, w=3.15, h=3.25, title="agent answer",
                state="high scarcity", compact=False):
    box(ax, x, y, w, h, edge=NAVY, fill=PALE, lw=2.0, radius=0.16)
    person_icon(ax, x + 0.38, y + h - 0.42, scale=0.8)
    text(ax, texts, x + 1.60, y + h - 0.42, title, size=13.0,
         weight="bold", role="card-title")
    row_h = 0.62 if compact else 0.72
    box(ax, x + 0.25, y + h - 1.35, w - 0.5, row_h,
        edge=BLUE, fill=BLUE_FILL, lw=1.5, radius=0.10)
    text(ax, texts, x + w / 2, y + h - 1.04, "action", size=11.5,
         weight="bold", role="field-action")
    box(ax, x + 0.25, y + 0.35, w - 0.5, row_h + (0.12 if not compact else 0),
        edge=YELLOW, fill=YELLOW_FILL, lw=1.5, radius=0.10)
    text(ax, texts, x + w / 2, y + 0.88, "reported state", size=10.7,
         weight="bold", role="field-state")
    text(ax, texts, x + w / 2, y + 0.57, state, size=9.8,
         color=YELLOW, role="field-value")


def rate_card(ax, texts, x, y, w=5.0, h=4.3, title="conditional rate"):
    box(ax, x, y, w, h, edge=PURPLE, fill="white", lw=2.0, radius=0.18)
    text(ax, texts, x + w / 2, y + h - 0.45, title, size=14.0,
         weight="bold", role="rate-title")
    ax.plot([x + 0.55, x + w - 0.55], [y + h - 0.88, y + h - 0.88],
            color=NAVY, linewidth=1.5, zorder=2)
    box(ax, x + 0.55, y + 2.25, w - 1.1, 0.75,
        edge=BLUE, fill=BLUE_FILL, lw=1.5, radius=0.10)
    text(ax, texts, x + w / 2, y + 2.62, "actions in\nselected records",
         size=10.4, weight="bold", role="rate-num")
    box(ax, x + 0.55, y + 0.78, w - 1.1, 0.92,
        edge=YELLOW, fill=YELLOW_FILL, lw=1.5, radius=0.10)
    text(ax, texts, x + w / 2, y + 1.24, "records with\nhigh scarcity",
         size=10.2, role="rate-den")


def compact_rate_card(ax, texts, x, y, w, h, title="conditional rate"):
    """A legible small rate card for layouts where the full fraction is too tall."""
    box(ax, x, y, w, h, edge=PURPLE, fill="white", lw=2.0, radius=0.14)
    text(ax, texts, x + w / 2, y + h - 0.23, title, size=9.2,
         weight="bold", role="compact-rate-title")
    ax.plot([x + 0.30, x + w - 0.30], [y + h - 0.43, y + h - 0.43],
            color=NAVY, linewidth=1.2, zorder=2)
    if h < 1.8:
        # At storyboard height, put numerator and denominator side by side.
        # This avoids squeezing two labels into a single vertical stack.
        cell_w = w / 2 - 0.48
        cell_h = 0.42
        cell_y = y + 0.25
        left_x = x + 0.30
        right_x = x + w / 2 + 0.18
        box(ax, left_x, cell_y, cell_w, cell_h,
            edge=BLUE, fill=BLUE_FILL, lw=1.2, radius=0.07)
        box(ax, right_x, cell_y, cell_w, cell_h,
            edge=YELLOW, fill=YELLOW_FILL, lw=1.2, radius=0.07)
        text(ax, texts, left_x + cell_w / 2, cell_y + cell_h / 2,
             "selected actions", size=7.0, weight="bold",
             role="compact-rate-num")
        text(ax, texts, right_x + cell_w / 2, cell_y + cell_h / 2,
             "eligible records", size=6.9, role="compact-rate-den")
        text(ax, texts, x + w / 2, cell_y + cell_h / 2, "/", size=11.0,
             weight="bold", role="compact-rate-slash")
        return
    num_h = 0.31 if h < 1.8 else 0.48
    den_h = 0.30 if h < 1.8 else 0.48
    num_y = y + h - 0.88 - num_h / 2
    den_y = y + 0.18 + den_h / 2
    box(ax, x + 0.30, num_y - num_h / 2, w - 0.60, num_h,
        edge=BLUE, fill=BLUE_FILL, lw=1.2, radius=0.07)
    box(ax, x + 0.30, den_y - den_h / 2, w - 0.60, den_h,
        edge=YELLOW, fill=YELLOW_FILL, lw=1.2, radius=0.07)
    text(ax, texts, x + w / 2, num_y, "selected actions", size=7.5,
         weight="bold", role="compact-rate-num")
    text(ax, texts, x + w / 2, den_y, "eligible records", size=7.3,
         role="compact-rate-den")


def simple_role_box(ax, texts, x, y, w, h, title, body, *, edge, fill,
                    icon=None, body_color=NAVY, body_size=10.5):
    box(ax, x, y, w, h, edge=edge, fill=fill, lw=2.0, radius=0.16)
    if icon == "shield":
        shield_icon(ax, x + 0.46, y + h / 2 + 0.03, scale=0.8)
        tx = x + w / 2 + 0.20
    elif icon == "funnel":
        funnel_icon(ax, x + 0.46, y + h / 2 + 0.03, scale=0.8)
        tx = x + w / 2 + 0.20
    else:
        tx = x + w / 2
    text(ax, texts, tx, y + h * 0.65, title, size=12.0,
         weight="bold", role=f"{title}-title")
    text(ax, texts, tx, y + h * 0.32, body, size=body_size,
         color=body_color, role=f"{title}-body")


def check_text_overlap(fig, texts):
    fig.canvas.draw()
    boxes = []
    for role, artist in texts:
        if role in {"title", "message"}:
            continue
        bbox = artist.get_window_extent(fig.canvas.get_renderer()).expanded(1.01, 1.05)
        boxes.append((role, bbox))
    collisions = []
    for i, (role_a, a) in enumerate(boxes):
        for role_b, b in boxes[i + 1:]:
            if a.overlaps(b):
                collisions.append((role_a, role_b))
    return collisions


def save(fig, texts, name):
    collisions = check_text_overlap(fig, texts)
    if collisions:
        raise RuntimeError(f"{name}: text collisions: {collisions}")
    png = OUT / f"{name}.png"
    pdf = OUT / f"{name}.pdf"
    fig.savefig(png, dpi=240, bbox_inches="tight", pad_inches=0.12)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.12)
    print(f"{name}: PASS text-overlap=0 -> {png.name}")
    plt.close(fig)


def candidate_a():
    fig, ax, t = canvas("A — Two-lane flow", "One answer feeds two different operations: validation and measurement.")
    answer_card(ax, t, 0.45, 1.55)
    simple_role_box(ax, t, 5.0, 4.05, 3.55, 1.25, "validator",
                    "checks action + appraisal", edge=CORAL, fill=CORAL_FILL,
                    icon="shield", body_size=9.6)
    simple_role_box(ax, t, 5.0, 1.65, 3.55, 1.25, "measurement",
                    "selects records", edge=PURPLE, fill=PURPLE_FILL,
                    icon="funnel", body_size=10.3)
    box(ax, 5.35, 0.62, 2.85, 0.55, edge=CORAL, fill=CORAL_FILL, lw=1.7, radius=0.12)
    text(ax, t, 6.78, 0.895, "blocked → re-prompt", size=9.7, color=CORAL,
         role="retry")
    rate_card(ax, t, 10.45, 1.03, 6.9, 4.55)
    # Arrowheads terminate inside the target boxes, never on a label.
    arrow(ax, [(3.62, 4.20), (4.38, 4.20), (4.38, 4.96), (5.18, 4.96)], color=BLUE)
    arrow(ax, [(3.62, 2.42), (4.20, 2.42), (4.20, 4.48), (5.18, 4.48)], color=YELLOW)
    arrow(ax, [(3.62, 2.42), (4.45, 2.42), (5.18, 2.22)], color=YELLOW)
    arrow(ax, [(6.78, 4.02), (6.78, 1.27)], color=CORAL)
    arrow(ax, [(5.35, 0.90), (3.95, 0.90), (3.50, 0.90), (3.50, 3.05)],
          color=CORAL, dashed=True)
    arrow(ax, [(8.62, 2.27), (9.55, 2.27), (10.62, 2.27)], color=PURPLE)
    save(fig, t, "fig1_candidate_A_two_lanes")


def candidate_b():
    fig, ax, t = canvas("B — Central hinge", "The same reported field is used once to gate an answer and once to choose the denominator.", 18.0, 7.0)
    answer_card(ax, t, 0.45, 1.55)
    box(ax, 4.55, 2.70, 2.85, 1.35, edge=YELLOW, fill=YELLOW_FILL, lw=2.3, radius=0.22)
    text(ax, t, 5.98, 3.44, "same", size=13.2, weight="bold", color=NAVY, role="hinge-a")
    text(ax, t, 5.98, 3.06, "reported field", size=11.0, color=YELLOW, role="hinge-b")
    simple_role_box(ax, t, 8.55, 4.25, 3.45, 1.25, "rule gate",
                    "reads appraisal", edge=CORAL, fill=CORAL_FILL,
                    icon="shield", body_size=10.4)
    simple_role_box(ax, t, 8.55, 1.35, 3.45, 1.25, "score filter",
                    "selects records", edge=PURPLE, fill=PURPLE_FILL,
                    icon="funnel", body_size=10.4)
    rate_card(ax, t, 13.05, 1.03, 4.45, 4.55)
    arrow(ax, [(3.62, 2.42), (4.56, 3.20)], color=YELLOW)
    arrow(ax, [(7.42, 3.42), (8.05, 3.42), (8.05, 4.86), (8.72, 4.86)], color=CORAL)
    arrow(ax, [(7.42, 3.05), (8.05, 3.05), (8.05, 1.98), (8.72, 1.98)], color=PURPLE)
    arrow(ax, [(11.98, 1.98), (12.55, 1.98), (13.22, 2.20)], color=PURPLE)
    # A short, separate retry route keeps the main hinge readable.
    box(ax, 8.70, 5.68, 2.05, 0.45, edge=CORAL, fill=CORAL_FILL, lw=1.5, radius=0.10)
    text(ax, t, 9.72, 5.905, "blocked → retry", size=8.8, color=CORAL, role="retry")
    arrow(ax, [(10.20, 5.68), (10.20, 5.35), (3.50, 5.35), (3.50, 3.05)],
          color=CORAL, dashed=True, scale=14)
    save(fig, t, "fig1_candidate_B_central_hinge")


def mini_answer(ax, texts, x, y, title, state):
    box(ax, x, y, 3.0, 2.18, edge=NAVY, fill=PALE, lw=2.0, radius=0.15)
    text(ax, texts, x + 1.5, y + 1.84, title, size=12.0, weight="bold", role=f"{title}-title")
    box(ax, x + 0.28, y + 1.05, 2.44, 0.47, edge=BLUE, fill=BLUE_FILL, lw=1.4, radius=0.08)
    text(ax, texts, x + 1.5, y + 1.285, "action", size=10.3, weight="bold", role=f"{title}-action")
    box(ax, x + 0.28, y + 0.32, 2.44, 0.50, edge=YELLOW, fill=YELLOW_FILL, lw=1.4, radius=0.08)
    text(ax, texts, x + 1.5, y + 0.57, state, size=9.0, color=YELLOW, role=f"{title}-state")


def candidate_c():
    fig, ax, t = canvas("C — Retry timeline", "A rejected answer can be replaced; the recorded decision set is therefore part of the measurement story.", 18.0, 7.0)
    mini_answer(ax, t, 0.45, 3.65, "answer 1", "reported state")
    simple_role_box(ax, t, 4.45, 4.00, 3.2, 1.45, "validator",
                    "reads reported state", edge=CORAL, fill=CORAL_FILL,
                    icon="shield", body_size=9.8)
    box(ax, 8.35, 4.32, 2.15, 0.72, edge=CORAL, fill=CORAL_FILL, lw=2.0, radius=0.13)
    text(ax, t, 9.42, 4.68, "blocked", size=11.0, color=CORAL, weight="bold", role="blocked")
    mini_answer(ax, t, 11.20, 3.65, "answer after retry", "reported state′")
    box(ax, 4.55, 0.95, 4.05, 1.45, edge=PURPLE, fill=PURPLE_FILL, lw=2.0, radius=0.16)
    funnel_icon(ax, 5.08, 1.70, scale=0.75)
    text(ax, t, 6.65, 1.78, "recorded decision set", size=11.0, weight="bold", role="set-title")
    text(ax, t, 6.65, 1.38, "may change after retry", size=9.5, color=PURPLE, role="set-body")
    compact_rate_card(ax, t, 10.15, 0.82, 7.0, 2.1, title="conditional rate")
    arrow(ax, [(3.48, 4.74), (4.55, 4.74)], color=BLUE)
    arrow(ax, [(7.65, 4.74), (8.43, 4.74)], color=CORAL)
    arrow(ax, [(10.50, 4.68), (11.15, 4.68)], color=CORAL, dashed=True)
    arrow(ax, [(2.00, 3.65), (2.00, 2.70), (5.05, 2.70), (5.05, 2.42)], color=YELLOW)
    arrow(ax, [(12.70, 3.65), (12.70, 2.90), (7.95, 2.90), (7.95, 2.42)], color=YELLOW)
    arrow(ax, [(8.60, 1.67), (9.45, 1.67), (10.35, 1.67)], color=PURPLE)
    save(fig, t, "fig1_candidate_C_retry_timeline")


def candidate_d():
    fig, ax, t = canvas("D — Measurement lens", "The central visual question is not only what the agent did, but which records the score includes.", 18.0, 7.0)
    answer_card(ax, t, 0.45, 1.55)
    # Large lens-like hinge, intentionally the dominant object.
    box(ax, 4.35, 2.42, 3.15, 1.90, edge=YELLOW, fill=YELLOW_FILL, lw=2.5, radius=0.27)
    text(ax, t, 5.93, 3.67, "reported", size=13.5, weight="bold", role="lens-a")
    text(ax, t, 5.93, 3.27, "state", size=13.5, weight="bold", color=YELLOW, role="lens-b")
    text(ax, t, 5.93, 2.82, "one field · two uses", size=9.0, color=MUTED, role="lens-c")
    simple_role_box(ax, t, 8.50, 4.30, 3.25, 1.23, "rule condition",
                    "reads appraisal", edge=CORAL, fill=CORAL_FILL,
                    icon="shield", body_size=10.2)
    simple_role_box(ax, t, 8.50, 1.22, 3.25, 1.23, "score condition",
                    "selects records", edge=PURPLE, fill=PURPLE_FILL,
                    icon="funnel", body_size=10.2)
    rate_card(ax, t, 12.75, 1.03, 4.75, 4.55)
    arrow(ax, [(3.62, 2.42), (4.36, 3.10)], color=YELLOW)
    arrow(ax, [(7.51, 3.65), (8.00, 3.65), (8.00, 4.91), (8.68, 4.91)], color=CORAL)
    arrow(ax, [(7.51, 3.08), (8.00, 3.08), (8.00, 1.84), (8.68, 1.84)], color=PURPLE)
    arrow(ax, [(11.73, 1.84), (12.25, 1.84), (12.93, 2.22)], color=PURPLE)
    # Validator retry is shown as a small side effect, not a competing main route.
    box(ax, 8.75, 5.67, 2.32, 0.45, edge=CORAL, fill=CORAL_FILL, lw=1.5, radius=0.10)
    text(ax, t, 9.91, 5.895, "blocked → retry", size=8.8, color=CORAL, role="retry")
    arrow(ax, [(9.91, 5.67), (9.91, 5.38), (3.50, 5.38), (3.50, 3.05)],
          color=CORAL, dashed=True, scale=14)
    save(fig, t, "fig1_candidate_D_measurement_lens")


def candidate_e():
    fig, ax, t = canvas("E — Four-step storyboard", "A single decision moves through writing, checking, possible revision, and scoring.", 18.0, 7.0)
    xs = [0.42, 4.55, 8.68, 12.81]
    titles = ["1  agent writes", "2  validator reads", "3  answer may change", "4  scorer selects"]
    bodies = ["action +\nreported state", "the reported\nstate field", "re-prompt after\na block", "records with\nthe same field"]
    edges = [BLUE, CORAL, CORAL, PURPLE]
    fills = [BLUE_FILL, CORAL_FILL, CORAL_FILL, PURPLE_FILL]
    for i, (x, title, body, edge, fill) in enumerate(zip(xs, titles, bodies, edges, fills)):
        box(ax, x, 3.15, 3.25, 1.65, edge=edge, fill=fill, lw=2.0, radius=0.16)
        text(ax, t, x + 1.625, 4.33, title, size=10.8, weight="bold", role=f"step-{i}-title")
        text(ax, t, x + 1.625, 3.78, body, size=10.1, color=edge if i in (1, 3) else NAVY,
             role=f"step-{i}-body")
    for x in xs[:-1]:
        arrow(ax, [(x + 3.30, 3.98), (x + 3.98, 3.98), (x + 4.05, 3.98)], color=NAVY)
    # Same-field bracket below steps 2 and 4.
    ax.plot([6.15, 6.15, 14.40, 14.40], [2.73, 2.52, 2.52, 2.73],
            color=YELLOW, linewidth=2.0, zorder=2)
    text(ax, t, 10.27, 2.22, "the same reported field changes both the gate and the score", size=10.3,
         color=YELLOW, weight="bold", role="bracket")
    compact_rate_card(ax, t, 5.25, 0.35, 7.55, 1.45, title="conditional rate")
    arrow(ax, [(14.40, 3.15), (14.40, 1.95), (12.60, 1.95)], color=PURPLE)
    save(fig, t, "fig1_candidate_E_storyboard")


def contact_sheet():
    names = [
        ("fig1_candidate_A_two_lanes", "A  two-lane flow"),
        ("fig1_candidate_B_central_hinge", "B  central hinge"),
        ("fig1_candidate_C_retry_timeline", "C  retry timeline"),
        ("fig1_candidate_D_measurement_lens", "D  measurement lens"),
        ("fig1_candidate_E_storyboard", "E  four-step storyboard"),
    ]
    fig, axes = plt.subplots(3, 2, figsize=(16, 13), dpi=160)
    fig.patch.set_facecolor("white")
    for ax, (name, label) in zip(axes.flat, names):
        img = plt.imread(OUT / f"{name}.png")
        ax.imshow(img)
        ax.set_title(label, loc="left", fontsize=13, color=NAVY, fontweight="bold", pad=6)
        ax.axis("off")
    axes.flat[-1].axis("off")
    fig.suptitle("Figure 1 candidate set — choose the visual argument before paper integration",
                 fontsize=17, color=NAVY, fontweight="bold", y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    path = OUT / "fig1_candidate_contact_sheet.png"
    fig.savefig(path, dpi=180, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    print(f"contact sheet -> {path.name}")


if __name__ == "__main__":
    candidate_a()
    candidate_b()
    candidate_c()
    candidate_d()
    candidate_e()
    contact_sheet()
