"""Regression tests for fail-closed generated-group verification."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import release_manifest


class GenerationMarkerTests(unittest.TestCase):
    def marker_context(self, root: Path, expected: set[str]):
        marker = root / "marker.sha256"
        return patch.multiple(
            release_manifest,
            SUBMISSION=root,
            GENERATION_MARKERS=(marker,),
            EXPECTED_GENERATED_GROUPS={"marker.sha256": expected},
        )

    def test_empty_marker_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "marker.sha256").write_text("", encoding="utf-8")
            with self.marker_context(root, {"output.pdf"}), self.assertRaises(SystemExit):
                release_manifest.validate_generation_markers()

    def test_partial_marker_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output.pdf"
            output.write_bytes(b"paper")
            digest = hashlib.sha256(output.read_bytes()).hexdigest()
            (root / "marker.sha256").write_text(
                f"{digest}  output.pdf\n", encoding="utf-8"
            )
            expected = {"output.pdf", "output.png"}
            with self.marker_context(root, expected), self.assertRaises(SystemExit):
                release_manifest.validate_generation_markers()

    def test_complete_marker_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output.pdf"
            output.write_bytes(b"paper")
            digest = hashlib.sha256(output.read_bytes()).hexdigest()
            (root / "marker.sha256").write_text(
                f"{digest}  output.pdf\n", encoding="utf-8"
            )
            with self.marker_context(root, {"output.pdf"}):
                release_manifest.validate_generation_markers()


if __name__ == "__main__":
    unittest.main()
