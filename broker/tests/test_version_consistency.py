"""T7 (2026-06-10 lifecycle review): release version single-source check.

The v0.6.0 release review found THREE stale current-version claims that the
3,117-test suite could not see (README_zh banner, ARCHITECTURE header,
README banner). The machine-readable trio below is the part a test CAN pin;
prose banners stay a release-review duty (grep-old-value rule).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    assert m, "pyproject.toml has no version line"
    return m.group(1)


def _changelog_latest() -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    # first released section heading, skipping [Unreleased]
    m = re.search(r"^## \[(\d+\.\d+\.\d+)\] - \d{4}-\d{2}-\d{2}", text, re.M)
    assert m, "CHANGELOG.md has no released section heading"
    return m.group(1)


def test_version_trio_agrees():
    import broker

    py = _pyproject_version()
    pkg = broker.__version__
    log = _changelog_latest()
    assert py == pkg == log, (
        f"Version drift: pyproject.toml={py!r}, broker.__version__={pkg!r}, "
        f"latest CHANGELOG heading={log!r}. Bump all three together "
        f"(release trigger #2) — see the v0.6.0 release-review lesson."
    )


def test_version_is_semver():
    import broker

    assert re.fullmatch(r"\d+\.\d+\.\d+", _pyproject_version())
    assert re.fullmatch(r"\d+\.\d+\.\d+", broker.__version__)
