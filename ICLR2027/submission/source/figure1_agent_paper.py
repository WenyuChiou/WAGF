"""Stage the generated, paper-facing Figure 1.

Figure 1 is intentionally a single generated raster asset. The image
generator produced the LLM cue, functional icons, node fills, borders, arrows,
typography, and background as one compact two-lane composition after the
semantic layout was fixed. This builder only copies that immutable asset into
the active submission directory and records the labels and meaning for review;
it does not redraw or edit any visual element.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "figures" / "assets" / "figure1_generated_full_final.png"
ACTIVE = ROOT / "figures" / "active"
OUT = ACTIVE / "figure1_concept"


def build() -> dict[str, object]:
    if not ASSET.exists():
        raise FileNotFoundError(f"missing generated Figure 1 asset: {ASSET}")

    ACTIVE.mkdir(parents=True, exist_ok=True)
    png = OUT.with_suffix(".png")
    print_png = OUT.with_name(OUT.name + "_print.png")
    manifest_path = OUT.with_suffix(".json")
    shutil.copy2(ASSET, png)
    shutil.copy2(ASSET, print_png)

    with Image.open(ASSET) as image:
        width, height = image.size

    manifest = {
        "rendering_mode": "generated_full",
        "asset": str(ASSET.relative_to(ROOT)).replace("\\", "/"),
        "canvas_px": [width, height],
        "scale": 1,
        "pdf_size_in": [6.35, 3.18],
        "canvas_policy": "uniform light neutral-gray paper background; compact two-lane layout with no large white cards",
        "style": "generated agent-paper composition with a bounded execution path, a measurement lane, short labels, and functional icons",
        "text": [
            "Agent (LLM)", "emits", "response", "action", "condition", "proposed action",
            "Validator", "rule input", "accepted", "Environment", "next context",
            "accepted decision", "Decision log", "selects records", "recorded set",
            "Filter", "Conditional rate",
        ],
        "semantics": {
            "primary": "one agent-written condition is consumed by runtime governance and by the evaluation denominator",
            "runtime": "the response action and condition enter Validator; an accepted action changes Environment and the accepted decision is logged",
            "selection": "the condition and the recorded decision set enter Filter, which feeds Conditional rate",
            "secondary": "Environment produces next context for the next agent response",
            "retry_boundary": "retries are not drawn because the frozen corpus lacks the first response before a retry",
        },
        "manual_visual_review": {
            "required": True,
            "checks": [
                "all labels are legible at full size, print width, and thumbnail size",
                "no text or icon overlaps an arrow or node border",
                "the short emits arrow makes Agent-to-response ownership explicit",
                "the black proposed-action arrow starts at action and enters Validator",
                "the amber rule-input arrow starts at condition and enters Validator",
                "the black accepted arrow goes directly from Validator to Environment",
                "Validator has a separate accepted-decision arrow into Decision log",
                "the amber selects-records arrow starts at condition and enters Filter",
                "Decision log has a separate recorded-set arrow into Filter",
                "the next-context route is thin, dashed, and returns from Environment to Agent",
                "the compact gray canvas avoids a floating icon collage and excessive white space",
            ],
        },
        "geometry_status": "not_machine_verifiable_for_generated_raster",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"png": str(png), "print_png": str(print_png), "manifest": str(manifest_path), "asset": str(ASSET)}


if __name__ == "__main__":
    for key, value in build().items():
        print(f"{key}: {value}")
