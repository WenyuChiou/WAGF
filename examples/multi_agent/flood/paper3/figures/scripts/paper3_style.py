from pathlib import Path

import matplotlib as mpl
from matplotlib.figure import Figure


FIGURE_WIDTH = 6.85
BASE_FONT_SIZE = 8
DPI = 300

OKABE_ITO = {
    "orange": "#E69F00",
    "sky_blue": "#56B4E9",
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "green": "#009E73",
    "yellow": "#F0E442",
    "pink": "#CC79A7",
    "black": "#000000",
}


def apply_style() -> None:
    mpl.rcParams.update(
        {
            "font.size": BASE_FONT_SIZE,
            "font.family": "sans-serif",
            "axes.titlesize": BASE_FONT_SIZE,
            "axes.labelsize": BASE_FONT_SIZE,
            "xtick.labelsize": BASE_FONT_SIZE,
            "ytick.labelsize": BASE_FONT_SIZE,
            "legend.fontsize": BASE_FONT_SIZE - 0.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "savefig.dpi": DPI,
            "figure.dpi": DPI,
        }
    )


def add_panel_label(ax, label: str, *, fontsize: float = 10) -> None:
    ax.text(
        0.0,
        1.02,
        label,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=fontsize,
        fontweight="bold",
    )


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def save_figure(fig: Figure, output_stem: Path) -> None:
    png_path = output_stem.with_suffix(".png")
    pdf_path = output_stem.with_suffix(".pdf")
    ensure_parent(png_path)
    ensure_parent(pdf_path)
    fig.savefig(png_path, dpi=DPI, bbox_inches="tight")
    fig.savefig(pdf_path, dpi=DPI, bbox_inches="tight")
