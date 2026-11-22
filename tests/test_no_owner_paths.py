"""Tracked public text must not contain a personal machine path."""
from pathlib import Path
import re
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
# A Windows drive path under Users, or a /Users/<name>/ or /home/<name>/ path.
OWNER_PATH = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]|/Users/[A-Za-z0-9._-]+/|/home/[A-Za-z0-9._-]+/")
# Generic placeholders that are not a real person.
PLACEHOLDERS = {"user", "username", "you", "your-name", "name", "<user>"}


def _tracked_docs():
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True,
                             check=True).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    for name in filter(None, out.split("\0")):
        parts = name.split("/")
        if not name.endswith(".md"):
            continue
        if parts[0] in ("docs", "examples") or len(parts) == 1 or name.endswith("README.md") \
                or name.endswith("README_zh.md"):
            if (ROOT / name).is_file():
                yield name


def _is_placeholder(match_text):
    m = re.search(r"/(?:Users|home)/([^/]+)/", match_text)
    return bool(m) and m.group(1).lower() in PLACEHOLDERS


def test_tracked_docs_have_no_owner_paths():
    hits = []
    for name in _tracked_docs():
        text = (ROOT / name).read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            for m in OWNER_PATH.finditer(line):
                if not _is_placeholder(m.group(0)):
                    hits.append(f"{name}:{number}")
    assert not hits, "personal machine path in tracked text: " + ", ".join(hits)


def test_pattern_catches_the_forms_it_names():
    for sample in (r"C:\Users\someone\x", "D:/Users/someone/x", "/Users/someone/x", "/home/someone/x"):
        assert OWNER_PATH.search(sample), sample
