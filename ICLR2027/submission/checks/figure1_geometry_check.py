"""Asset and semantic audit for the generated ICLR Figure 1.

For the active generated-raster rendering this check verifies the staged asset,
dimensions, and short-label manifest, then records that pixel-level text and
arrow separation requires visual review. The former vector geometry branch is
retained only for historical manifests.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "figures"
ACTIVE = FIGURES / "active"
MANIFEST = ACTIVE / "figure1_concept.json"
PNG = ACTIVE / "figure1_concept.png"
PRINT_PNG = ACTIVE / "figure1_concept_print.png"
THUMBNAIL = ROOT / "checks" / "figure1_thumbnail.png"


def overlaps(left: tuple[float, float, float, float],
             right: tuple[float, float, float, float]) -> bool:
    ax1, ay1, ax2, ay2 = left
    bx1, by1, bx2, by2 = right
    return max(ax1, bx1) < min(ax2, bx2) and max(ay1, by1) < min(ay2, by2)


def inside(point: tuple[float, float], zone: tuple[float, float, float, float]) -> bool:
    x, y = point
    x1, y1, x2, y2 = zone
    return x1 <= x <= x2 and y1 <= y <= y2


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def orientation(a: tuple[float, float], b: tuple[float, float],
                c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segments_intersect(a: tuple[float, float], b: tuple[float, float],
                       c: tuple[float, float], d: tuple[float, float]) -> bool:
    """Strict segment intersection test for routed arrow centerlines."""
    eps = 1e-9
    ab_c = orientation(a, b, c)
    ab_d = orientation(a, b, d)
    cd_a = orientation(c, d, a)
    cd_b = orientation(c, d, b)
    return ((ab_c > eps and ab_d < -eps) or (ab_c < -eps and ab_d > eps)) and ((cd_a > eps and cd_b < -eps) or (cd_a < -eps and cd_b > eps))


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("rendering_mode") == "generated_full":
        errors: list[str] = []
        warnings = [
            "generated raster: text, icon, and arrow geometry requires visual review",
            "automatic overlap and route-intersection checks are not applicable to this rendering mode",
        ]
        labels = manifest.get("text", [])
        expected_labels = {
            "Agent response", "AI", "action", "condition", "propose",
            "Validator", "rule input", "accepted", "Environment", "final record",
            "Decision log", "records", "Counted records", "selects", "Conditional rate",
            "retry / re-ask", "retry exhausted", "default action",
        }
        missing_labels = sorted(expected_labels - set(labels))
        unexpected_labels = sorted(set(labels) - expected_labels)
        if missing_labels or unexpected_labels or len(labels) != len(expected_labels):
            errors.append(
                "generated Figure 1 label set drifted: "
                f"missing={missing_labels}, unexpected={unexpected_labels}"
            )
        too_long = [label for label in labels if len(label) > 22 or len(label.split()) > 3]
        if too_long:
            errors.append(f"labels exceed the short-figure limit: {too_long}")

        source_asset = ROOT / manifest.get("asset", "")
        if source_asset.name != "figure1_architecture_agentpaper_shared_condition_v6_retry_return.png":
            errors.append(
                "generated Figure 1 source must remain the reviewed shared-condition retry asset: "
                f"{source_asset.name}"
            )
        expected_hashes = {
            "source asset": (source_asset, manifest.get("asset_sha256")),
            "active PNG": (PNG, manifest.get("staged_sha256")),
            "print PNG": (PRINT_PNG, manifest.get("print_sha256")),
        }
        observed_hashes: dict[str, str | None] = {}
        for label, (path, expected) in expected_hashes.items():
            if not expected:
                errors.append(f"missing SHA-256 in manifest for {label}")
                observed_hashes[label] = None
                continue
            if not path.exists() or path.stat().st_size == 0:
                errors.append(f"missing generated Figure 1 file for {label}: {path}")
                observed_hashes[label] = None
                continue
            observed = sha256(path)
            observed_hashes[label] = observed
            if observed != expected:
                errors.append(f"SHA-256 mismatch for {label}: expected {expected}, got {observed}")
        observed_values = [value for value in observed_hashes.values() if value]
        if len(observed_values) == len(expected_hashes) and len(set(observed_values)) != 1:
            errors.append("source, active, and print Figure 1 hashes do not match each other")
        for path in (PNG, PRINT_PNG):
            if not path.exists() or path.stat().st_size == 0:
                errors.append(f"missing generated figure output: {path}")
        if PNG.exists():
            with Image.open(PNG) as image:
                if image.size != tuple(manifest["canvas_px"]):
                    errors.append(f"PNG dimensions {image.size} differ from manifest {manifest['canvas_px']}")
                if image.mode not in {"RGB", "RGBA"}:
                    errors.append(f"PNG has unexpected color mode: {image.mode}")
                thumbnail = image.copy()
                thumbnail.thumbnail((900, 600), Image.Resampling.LANCZOS)
                thumbnail.save(THUMBNAIL, format="PNG")
        result = {
            "status": "PASS_MANUAL_VISUAL_REVIEW_REQUIRED" if not errors else "FAIL",
            "rendering_mode": "generated_full",
            "canvas_px": manifest.get("canvas_px"),
            "label_count": len(labels),
            "text_overlap_count": None,
            "route_intersection_count": None,
            "sha256": observed_hashes,
            "sha256_match": len(observed_values) == len(expected_hashes) and len(set(observed_values)) == 1,
            "warnings": warnings,
            "errors": errors,
        }
        report = ROOT / "checks" / "figure1_geometry_report.json"
        report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0 if not errors else 1

    width, height = (value / manifest["scale"] for value in manifest["canvas_px"])
    boxes = {key: tuple(value) for key, value in manifest["boxes"].items()}
    errors: list[str] = []
    warnings: list[str] = []

    for key, box in boxes.items():
        x1, y1, x2, y2 = box
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            errors.append(f"{key}: text box is outside the {width:g}x{height:g} canvas")

    keys = list(boxes)
    for index, left_key in enumerate(keys):
        for right_key in keys[index + 1:]:
            if overlaps(boxes[left_key], boxes[right_key]):
                errors.append(f"text boxes overlap: {left_key} / {right_key}")

    routes = manifest["routes"]
    target_zones = {
        name: tuple(zone)
        for name, zone in manifest.get("target_zones", {}).items()
    }
    if not target_zones:
        errors.append("manifest has no target_zones")
    for name, zone in target_zones.items():
        if name not in routes:
            errors.append(f"target zone has no matching route: {name}")
            continue
        endpoint = tuple(routes[name][-1])
        if not inside(endpoint, zone):
            errors.append(f"{name}: endpoint {endpoint} misses target zone {zone}")

    non_intersecting_pairs = [
        tuple(pair) for pair in manifest.get("non_intersecting_pairs", [])
    ]
    route_intersections = 0
    for left_name, right_name in non_intersecting_pairs:
        if left_name not in routes or right_name not in routes:
            errors.append(f"intersection pair references an unknown route: {left_name}/{right_name}")
            continue
        left_route = [tuple(point) for point in routes[left_name]]
        right_route = [tuple(point) for point in routes[right_name]]
        if any(
            segments_intersect(a, b, c, d)
            for a, b in zip(left_route, left_route[1:])
            for c, d in zip(right_route, right_route[1:])
        ):
            route_intersections += 1
            errors.append(f"routed centerlines intersect: {left_name} / {right_name}")

    labels = manifest["text"]
    too_long = [label for label in labels if len(label) > 22 or len(label.split()) > 3]
    if too_long:
        errors.append(f"labels exceed the short-figure limit: {too_long}")

    for path in (PNG, PRINT_PNG):
        if not path.exists() or path.stat().st_size == 0:
            errors.append(f"missing figure output: {path}")

    if PNG.exists():
        with Image.open(PNG) as image:
            if image.size != tuple(manifest["canvas_px"]):
                errors.append(f"PNG dimensions {image.size} differ from manifest {manifest['canvas_px']}")
            if image.mode not in {"RGB", "RGBA"}:
                errors.append(f"PNG has unexpected color mode: {image.mode}")

    # Regenerate a review thumbnail from the current output so it cannot go
    # stale after a label or route edit.
    if PNG.exists():
        with Image.open(PNG) as image:
            thumbnail = image.copy()
            thumbnail.thumbnail((900, 600), Image.Resampling.LANCZOS)
            thumbnail.save(THUMBNAIL, format="PNG")

    result = {
        "status": "PASS" if not errors else "FAIL",
        "canvas_logical": [width, height],
        "label_count": len(labels),
        "text_overlap_count": sum(
            1 for index, left_key in enumerate(keys)
            for right_key in keys[index + 1:]
            if overlaps(boxes[left_key], boxes[right_key])
        ),
        "route_intersection_count": route_intersections,
        "warnings": warnings,
        "errors": errors,
    }
    report = ROOT / "checks" / "figure1_geometry_report.json"
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
