"""Every file path a WAGF skill names must exist in the repository.

What counts as a path (checked in each ``SKILL.md`` and in the ``references/``
files it links):
  * backticked text that contains ``/`` and ends in a file suffix, or
  * a markdown link target.
Skipped: URLs, anchors-only links, and placeholders (text with ``<``, ``>``,
``{``, ``*``, ``$`` or spaces, or a template word such as ``your_``/``my_``).
A trailing ``::name``, ``:line`` or ``#anchor`` is dropped before the check.
Also skipped: files a user's own run or new domain creates (first folder is
``.research``, ``.coupling``, ``.baselines``, ``results``, ``analysis``,
``config`` or ``cognition``); these are outputs, not files of this repo.
A path is found if it exists from the repo root, from the file that names it,
from that skill's own folder (``references/x.md``) or from ``.claude/skills/``
(another skill's file, ``wagf-domain-builder/references/x.md``).
"""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".claude" / "skills"
SKILL_NAMES = [
    "abm-reproducibility-checker",
    "llm-agent-audit-trace-analyzer",
    "model-coupling-contract-checker",
    "wagf-coupling-designer",
    "wagf-domain-builder",
    "wagf-experiment-designer",
    "wagf-quickstart",
    "wagf-verification-ladder",
]
SUFFIX = r"(?:py|md|ya?ml|json|csv|txt|sh|toml|cfg|ini|ipynb|ps1|bat|html)"
BACKTICK = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
USER_MADE = {".research", ".coupling", ".baselines", "results", "analysis", "config", "cognition"}
PLACEHOLDER = re.compile(r"[<>{}*$\s]|\.\.\.|\b(?:your|my|new)_|/path/to/|\bXXX\b|\bfoo\b")


def _tracked():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8", check=True).stdout
    return set(out.split("\n"))


def _clean(raw):
    raw = raw.strip().strip("'\"")
    if re.match(r"^[a-z]+://", raw) or raw.startswith(("mailto:", "#")):
        return None
    raw = re.split(r"#|::", raw)[0]
    raw = re.sub(r":\d+(?:-\d+)?$", "", raw)
    if not raw or PLACEHOLDER.search(raw) or raw.split("/")[0] in USER_MADE:
        return None
    return raw


def named_paths(text):
    """Return the candidate paths named in ``text`` (see module docstring)."""
    found = set()
    for raw in BACKTICK.findall(text):
        path = _clean(raw)
        if path and "/" in path and re.search(rf"\.{SUFFIX}$", path):
            found.add(path)
    for raw in LINK.findall(text):
        path = _clean(raw)
        if path:
            found.add(path)
    return found


def _exists(path, origin, skill_dir, tracked):
    for base in (ROOT, origin.parent, skill_dir, SKILLS):
        candidate = (base / path).resolve()
        try:
            rel = candidate.relative_to(ROOT).as_posix()
        except ValueError:
            continue
        if rel in tracked or any(t.startswith(rel + "/") for t in tracked):
            return True
    return False


def _files_for(name):
    skill_dir = SKILLS / name
    skill_md = skill_dir / "SKILL.md"
    files = [skill_md]
    text = skill_md.read_text(encoding="utf-8")
    for target in LINK.findall(text) + [p for p in BACKTICK.findall(text)]:
        path = _clean(target)
        if not path or not path.startswith("references/") or not path.endswith(".md"):
            continue
        ref = skill_dir / path
        if ref.is_file() and ref not in files:
            files.append(ref)
    return skill_dir, files


def test_path_rule_skips_urls_and_placeholders():
    text = ("`broker/core/x.py` `<domain>/run.py` [d](https://a.b/c.md) "
            "[a](#top) `examples/*/r.csv` [l](docs/guides/g.md#sec) `pkg.mod` `results/smoke_42/a.csv`")
    assert named_paths(text) == {"broker/core/x.py", "docs/guides/g.md"}


@pytest.mark.parametrize("name", SKILL_NAMES)
def test_every_path_named_in_the_skill_exists(name):
    tracked = _tracked()
    skill_dir, files = _files_for(name)
    missing = []
    for origin in files:
        for path in sorted(named_paths(origin.read_text(encoding="utf-8"))):
            if not _exists(path, origin, skill_dir, tracked):
                missing.append(f"{origin.relative_to(ROOT).as_posix()}: {path}")
    assert not missing, "paths named but not in the repo:\n" + "\n".join(missing)
