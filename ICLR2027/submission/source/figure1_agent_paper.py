"""Stage the generated, paper-facing Figure 1 shared-condition architecture.

The selected architecture is a single generated raster asset. The image
generator produced the AI cue, functional icons, colored fills, black borders,
ports, arrows, typography, and background as one compact paper composition.
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
ASSET = ROOT / "figures" / "assets" / "figure1_architecture_agentpaper_shared_condition_v5_retry.png"
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
        "canvas_policy": "warm light-gray paper background; black module borders and black arrows with flat colored fills; compact shared-condition composition",
        "style": "generated agent-paper architecture inspired by ReAct, Reflexion, AgentSpec, and SWE-agent: one response card, an explicit validator interface with black and amber ports, a direct final-record log, a separate counted-records path, short relation labels, and subordinate AI/function icons",
        "color_roles": {
            "blue": "agent response and agent output",
            "orange": "runtime Validator",
            "green": "Environment or simulator",
            "violet": "measurement and record path",
            "amber": "shared agent-written condition and its routes",
            "black": "execution and record-flow arrows and module borders",
            "warm light-gray": "neutral paper canvas",
        },
        "text": [
            "Agent response", "AI", "action", "condition", "propose",
            "Validator", "rule input", "accepted", "Environment", "final record",
            "Decision log", "records", "Counted records", "selects", "Conditional rate",
            "fresh response", "retry / re-ask", "retry exhausted", "default action",
        ],
        "semantics": {
            "primary": "one agent-written condition is consumed by runtime governance and by the evaluation denominator",
            "runtime": "the response enters Validator; an accepted action reaches Environment; a retry may produce a fresh response or a default action; the final record enters Decision log",
            "selection": "records from Decision log enter Counted records; the same condition selects Counted records; Counted records feeds Conditional rate",
            "omitted": "the observation-to-next-context loop remains omitted; the retry branch is shown because primary statistics use the executed action",
        },
        "manual_visual_review": {
            "required": True,
            "checks": [
                "all labels are legible at full size, print width, and thumbnail size",
                "no text or icon overlaps an arrow or node border",
                "the Agent response card owns the action and condition fields",
                "the black propose arrow enters Validator's black input port",
                "the amber rule-input arrow starts at condition and enters Validator's amber input port",
                "the black accepted arrow goes directly from Validator to Environment",
                "Validator has a separate final-record arrow that terminates on Decision log",
                "the amber selects arrow starts at condition, bypasses Decision log, and enters Counted records",
                "Decision log has a separate records arrow into Counted records",
                "the retry / re-ask arrow returns to Agent response without crossing the condition-selection route",
                "the retry-exhausted / default-action arrow reaches the Environment execution path",
                "the observation-to-next-context path remains absent rather than an ambiguous connector",
                "black borders and colored fills remain distinct at full size, paper width, thumbnail size, and grayscale",
            ],
        },
        "geometry_status": "not_machine_verifiable_for_generated_raster",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"png": str(png), "print_png": str(print_png), "manifest": str(manifest_path), "asset": str(ASSET)}


if __name__ == "__main__":
    for key, value in build().items():
        print(f"{key}: {value}")
