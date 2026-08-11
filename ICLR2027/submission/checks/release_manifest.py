#!/usr/bin/env python
"""Write or verify hashes for the exact ICLR submission package."""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


SUBMISSION = Path(__file__).resolve().parents[1]
OUTPUT = SUBMISSION / "release_manifest.sha256"
EXCLUDED_DIRS = {"$out", ".tmp", "__pycache__"}
EXCLUDED_SUFFIXES = {".aux", ".blg", ".log", ".out"}
GENERATION_MARKERS = (
    SUBMISSION / "supplement" / "figure2_generation.sha256",
    SUBMISSION / "supplement" / "cross_testbed_generation.sha256",
    SUBMISSION / "supplement" / "fig4_generation.sha256",
)
EXPECTED_GENERATED_GROUPS = {
    "supplement/figure2_generation.sha256": {
        "figures/active/fig1_rule_layers.png",
        "figures/active/fig1_rule_layers.pdf",
    },
    "supplement/cross_testbed_generation.sha256": {
        "figures/active/fig2_mechanism.png",
        "figures/active/fig2_mechanism.pdf",
        "supplement/cross_testbed_summary.csv",
        "supplement/table3_cross_testbed.tex",
        "supplement/cross_testbed_provenance.json",
    },
    "supplement/fig4_generation.sha256": {
        "figures/active/fig3_consequence.png",
        "figures/active/fig3_consequence.pdf",
        "supplement/fig4_gap_intervals.csv",
    },
}
CANONICAL_TRACKED_INPUTS = (
    SUBMISSION / "supplement" / "cross_testbed_release_cells.csv",
    SUBMISSION / "supplement" / "fig4_per_seed.csv",
)


def run_checked(command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run one release dependency and preserve useful output on failure."""

    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        raise SystemExit(
            f"Release dependency failed ({' '.join(command)}):\n{result.stdout}\n{result.stderr}"
        )
    return result


def rebuild_and_validate() -> None:
    """Regenerate every release display and pass all gates before hashing."""

    source = SUBMISSION / "source"
    checks = SUBMISSION / "checks"
    paper = SUBMISSION / "paper"
    for script in (
        source / "figure1_agent_paper.py",
        checks / "figure1_geometry_check.py",
        source / "figure2_rule_layers.py",
        source / "cross_testbed_summary.py",
        source / "figure4_denominator_gap.py",
    ):
        run_checked([sys.executable, str(script)])

    pdflatex = shutil.which("pdflatex")
    bibtex = shutil.which("bibtex")
    if not pdflatex or not bibtex:
        raise SystemExit("pdflatex and bibtex are required to refresh the release manifest")
    tex_env = os.environ.copy()
    style_dir = source / "iclr_style" / "iclr2027"
    tex_env["TEXINPUTS"] = str(style_dir) + os.pathsep + tex_env.get("TEXINPUTS", "")
    tex_env["BSTINPUTS"] = str(style_dir) + os.pathsep + tex_env.get("BSTINPUTS", "")
    run_checked([pdflatex, "-interaction=nonstopmode", "-halt-on-error", "manuscript.tex"], cwd=paper, env=tex_env)
    run_checked([bibtex, "manuscript"], cwd=paper, env=tex_env)
    run_checked([pdflatex, "-interaction=nonstopmode", "-halt-on-error", "manuscript.tex"], cwd=paper, env=tex_env)
    run_checked([pdflatex, "-interaction=nonstopmode", "-halt-on-error", "manuscript.tex"], cwd=paper, env=tex_env)

    for script in (
        checks / "manuscript_static_check.py",
        checks / "evidence_boundary_check.py",
        checks / "iclr_page_gate.py",
    ):
        run_checked([sys.executable, str(script)])
    pdffonts = shutil.which("pdffonts")
    if not pdffonts:
        raise SystemExit("pdffonts is required to audit embedded figure fonts")
    fonts = run_checked([pdffonts, str(paper / "manuscript.pdf")])
    if "Type 3" in fonts.stdout or "Type3" in fonts.stdout:
        raise SystemExit("Release PDF contains Type 3 fonts")


def validate_tracked_inputs() -> None:
    for path in CANONICAL_TRACKED_INPUTS:
        relative = path.relative_to(SUBMISSION.parents[1]).as_posix()
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative],
            cwd=SUBMISSION.parents[1],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise SystemExit(f"Canonical release input is not tracked: {relative}")


def scan_for_identity_leaks() -> None:
    local_username = bytes((119, 101, 110, 121, 117))
    patterns = (
        re.compile(rb"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE),
        re.compile(re.escape(local_username), re.IGNORECASE),
    )
    for path in release_files():
        data = path.read_bytes()
        if any(pattern.search(data) for pattern in patterns):
            raise SystemExit(
                f"Release file contains an absolute user path or identifying username: "
                f"{path.relative_to(SUBMISSION).as_posix()}"
            )


def release_files() -> list[Path]:
    """Return every release file except transient TeX/cache outputs and the manifest itself."""
    files = []
    for path in SUBMISSION.rglob("*"):
        if not path.is_file() or path == OUTPUT:
            continue
        relative = path.relative_to(SUBMISSION)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        files.append(path)
    return sorted(files, key=lambda path: path.relative_to(SUBMISSION).as_posix())


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_generation_markers() -> None:
    """Reject partial multi-file generations before package verification."""

    for marker in GENERATION_MARKERS:
        if not marker.is_file():
            raise SystemExit(f"Missing generation marker: {marker}")
        marker_key = marker.relative_to(SUBMISSION).as_posix()
        seen: set[str] = set()
        lines = marker.read_text(encoding="utf-8").splitlines()
        if not lines:
            raise SystemExit(f"Empty generation marker: {marker}")
        for line in lines:
            expected_hash, separator, relative = line.partition("  ")
            if not separator or not re.fullmatch(r"[0-9a-f]{64}", expected_hash) or not relative:
                raise SystemExit(f"Malformed generation marker line in {marker}: {line}")
            if relative in seen:
                raise SystemExit(f"Duplicate generation marker target in {marker}: {relative}")
            seen.add(relative)
            target = (SUBMISSION / relative).resolve()
            try:
                target.relative_to(SUBMISSION.resolve())
            except ValueError as exc:
                raise SystemExit(f"Generation marker escapes submission root: {relative}") from exc
            if not target.is_file() or digest(target) != expected_hash:
                raise SystemExit(f"Generation marker mismatch: {relative}")
        if seen != EXPECTED_GENERATED_GROUPS[marker_key]:
            raise SystemExit(
                f"Generation marker membership mismatch for {marker_key}: "
                f"missing={sorted(EXPECTED_GENERATED_GROUPS[marker_key] - seen)}, "
                f"unexpected={sorted(seen - EXPECTED_GENERATED_GROUPS[marker_key])}"
            )


def manifest_paths(text: str) -> set[str]:
    paths: set[str] = set()
    for line in text.splitlines():
        _hash, separator, relative = line.partition("  ")
        if not separator or not relative:
            raise SystemExit("Existing release manifest is malformed")
        paths.add(relative)
    return paths


def expected_text() -> str:
    lines = [
        f"{digest(path)}  {path.relative_to(SUBMISSION).as_posix()}"
        for path in release_files()
    ]
    if not lines:
        raise SystemExit("No release files found")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="explicitly refresh the manifest; verification is the default",
    )
    parser.add_argument(
        "--allow-inventory-change",
        action="store_true",
        help="explicitly approve added/removed release paths when refreshing",
    )
    args = parser.parse_args()
    if args.write:
        validate_tracked_inputs()
        rebuild_and_validate()
        validate_generation_markers()
        scan_for_identity_leaks()
        expected = expected_text()
        if OUTPUT.is_file() and not args.allow_inventory_change:
            old_paths = manifest_paths(OUTPUT.read_text(encoding="utf-8"))
            new_paths = manifest_paths(expected)
            if old_paths != new_paths:
                raise SystemExit(
                    "Release inventory changed. Review paths and rerun with "
                    "--write --allow-inventory-change. "
                    f"Added={sorted(new_paths - old_paths)}, removed={sorted(old_paths - new_paths)}"
                )
        OUTPUT.write_text(expected, encoding="utf-8", newline="\n")
        print(f"wrote {OUTPUT} ({len(expected.splitlines())} files)")
        return
    validate_generation_markers()
    validate_tracked_inputs()
    scan_for_identity_leaks()
    expected = expected_text()
    if not OUTPUT.is_file():
        raise SystemExit(f"Missing release manifest: {OUTPUT}; run with --write")
    actual = OUTPUT.read_text(encoding="utf-8")
    if actual != expected:
        expected_lines = set(expected.splitlines())
        actual_lines = set(actual.splitlines())
        added = sorted(expected_lines - actual_lines)
        removed = sorted(actual_lines - expected_lines)
        raise SystemExit(
            "Release manifest mismatch. Refresh only after review with --write. "
            f"Changed/added={len(added)}, stale/missing={len(removed)}"
        )
    print(f"PASS: {OUTPUT} verifies {len(expected.splitlines())} release files")


if __name__ == "__main__":
    main()
