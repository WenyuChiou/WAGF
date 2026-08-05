"""Stage the generated, paper-facing Figure 1.

Figure 1 is intentionally a single generated raster asset.  The image
generator produced the icons, node fills, borders, arrows, typography, and
background as one coherent composition after the semantic layout was fixed.
This builder only copies that immutable asset into the active submission
directory and records the labels and meaning for review; it does not redraw
or edit any visual element.
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
        "pdf_size_in": [6.35, 4.76],
        "canvas_policy": "uniform cool-gray paper background; no large white cards or empty white strip",
        "style": "generated icon-and-flow composition with near-black outlines and flat muted fills",
        "text": [
            "AGENT RESPONSE", "Action", "Agent-written", "condition", "Validator",
            "Recorded", "decisions", "World state", "Record filter", "Conditional", "rate",
            "proposed action", "rule input", "accept", "recorded set", "same condition",
            "selects records", "accepted action", "future context",
        ],
        "semantics": {
            "primary": "the same agent-written condition is read by runtime validation and evaluation",
            "runtime": "Validator directly sends the accepted action to World state and separately records the accepted decision",
            "selection": "the recorded decision set and the same condition enter the record filter, which feeds the conditional rate",
            "secondary": "an accepted action changes world state, which returns as future context",
            "retry_boundary": "retries are not drawn because the frozen corpus lacks the first report before a retry",
        },
        "manual_visual_review": {
            "required": True,
            "checks": [
                "all labels are legible at full size and print width",
                "no text or icon overlaps an arrow or node border",
                "the single black action arrow starts at Action and enters Validator",
                "the condition branches only to Validator and Record filter",
                "Validator directly sends accepted action to World state",
                "Recorded decisions has a separate arrow to Record filter",
                "the future-context route stays outside the modules",
                "the uniform gray background avoids excessive white space",
            ],
        },
        "geometry_status": "not_machine_verifiable_for_generated_raster",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"png": str(png), "print_png": str(print_png), "manifest": str(manifest_path), "asset": str(ASSET)}


if __name__ == "__main__":
    for key, value in build().items():
        print(f"{key}: {value}")
