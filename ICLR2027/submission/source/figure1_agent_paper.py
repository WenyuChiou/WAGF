"""Stage the generated, paper-facing Figure 1 shared-condition architecture.

The selected architecture is a single generated raster asset. The image
generator produced the LLM cue, functional icons, node fills, borders, arrows,
typography, and background as one shared-condition bridge composition.
This builder only copies that immutable asset into the active submission
directory and records its labels and meaning for review; it does not redraw or
edit any visual element.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "figures" / "assets" / "figure1_architecture_agentpaper_v3.png"
ACTIVE = ROOT / "figures" / "active"
OUT = ACTIVE / "figure1_concept"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build() -> dict[str, object]:
    if not ASSET.exists():
        raise FileNotFoundError(f"missing generated Figure 1 asset: {ASSET}")

    ACTIVE.mkdir(parents=True, exist_ok=True)
    png = OUT.with_suffix(".png")
    print_png = OUT.with_name(OUT.name + "_print.png")
    manifest_path = OUT.with_suffix(".json")
    shutil.copy2(ASSET, png)
    shutil.copy2(ASSET, print_png)

    asset_sha256 = sha256(ASSET)
    staged_sha256 = sha256(png)
    print_sha256 = sha256(print_png)
    if staged_sha256 != asset_sha256 or print_sha256 != asset_sha256:
        raise RuntimeError("staged Figure 1 copies do not match the source asset")

    with Image.open(ASSET) as image:
        width, height = image.size

    manifest = {
        "rendering_mode": "generated_full",
        "asset": str(ASSET.relative_to(ROOT)).replace("\\", "/"),
        "asset_sha256": asset_sha256,
        "staged_sha256": staged_sha256,
        "print_sha256": print_sha256,
        "canvas_px": [width, height],
        "scale": 1,
        "pdf_size_in": [6.35, 3.18],
        "canvas_policy": "pale blue-gray paper background; black borders with colored fills; compact shared-condition bridge with tight-to-content nodes",
        "style": "generated agent-paper architecture inspired by ReAct, Reflexion, AgentSpec, and SWE-agent: one bounded response, a clear validator insertion point, an accepted-decision log, an explicit shared-condition fork, short relation labels, and subordinate AI/function icons",
        "text": [
            "Agent", "LLM", "response", "action", "condition", "proposed action",
            "Validator", "rule input", "accepted", "Environment",
            "observation", "accepted decision", "Decision log", "records", "filter",
            "conditional rate", "selects records",
        ],
        "semantics": {
            "primary": "one agent-written condition is consumed by runtime governance and by the evaluation denominator",
            "runtime": "the response action enters Validator; the same condition supplies rule input; an accepted action changes Environment and the accepted decision is logged",
            "selection": "the condition enters Filter as a selection rule, while the logged records enter Filter as the record set; Filter feeds conditional rate",
            "secondary": "Environment returns an observation to the Agent for the next response",
            "retry_boundary": "retries are not drawn because the frozen corpus lacks the first response before a retry",
        },
        "manual_visual_review": {
            "required": True,
            "checks": [
                "all labels are legible at full size, print width, and thumbnail size",
                "no text or icon overlaps an arrow or node border",
                "the Agent boundary owns the response object and its action/condition fields",
                "the black proposed arrow starts at action and enters Validator",
                "the amber rule-input arrow starts at condition and enters Validator",
                "the black accepted arrow goes directly from Validator to Environment",
                "Validator has a separate accepted-decision arrow that terminates on the aligned Decision log",
                "the amber selects-records arrow starts at condition, bypasses Decision log, and enters Filter",
                "Decision log has a separate records arrow into Filter",
                "the observation route is thin, dashed, and returns from Environment to Agent",
                "the compact single-canvas composition avoids a floating icon collage and excessive unused space",
            ],
        },
        "geometry_status": "not_machine_verifiable_for_generated_raster",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"png": str(png), "print_png": str(print_png), "manifest": str(manifest_path), "asset": str(ASSET)}


if __name__ == "__main__":
    for key, value in build().items():
        print(f"{key}: {value}")
