"""Regression check: repo-relative paths named in public docs must exist.

In-scope markdown files:
  * ARCHITECTURE.md and broker/INVARIANTS.md
  * broker/**/README.md
  * docs/**/*.md except docs/internal/
  * .claude/skills/**/*.md
  * English files only (*_zh.md, README_zh.md, and Chinese prose excluded)

Limits: a file with any Chinese text is skipped whole, so mixed-language
docs (e.g. docs/architecture/agent_pipeline_specification.md) are not
checked. Paths inside code fences, link targets with a title, and
reference-style links are not checked either.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
BACKTICK_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
EXT_RE = re.compile(r"\.[A-Za-z][A-Za-z0-9_]{0,9}$")

OUT_OF_SCOPE_DIRS = ("docs/internal/",)
OUT_OF_SCOPE_FILES: frozenset[str] = frozenset()

FAILURE_HINT = "fix the path, or add a pattern with a reason"

# Explicit allowlist of (compiled pattern, one-line reason) for paths that docs
# name intentionally even though they are not tracked files in the repo.
ALLOWLIST_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"[<>{}*]"),
        "User-filled template or glob wildcard placeholder (<...>, {...}, *).",
    ),
    (
        re.compile(r"(?:^|/)(?:YOUR_[A-Z0-9_]*|your_[a-z0-9_]*|my_[a-z0-9_]*)(?:/|\.|$)"),
        "Illustrative user-named domain or file placeholder (YOUR_*, your_*, my_*).",
    ),
    (
        re.compile(r"^(?:\.tmp|\.research|\.coupling)(?:/|$)"),
        "Local runtime scratch, research-plan, or coupling-contract directory.",
    ),
    (
        re.compile(r"^(?:results|raw|analysis)(?:/|$)"),
        "Simulation output or post-run analysis directory created outside source.",
    ),
    (
        re.compile(r"^(?:config|adapters|validators|cognition|domain_adapters|experimental)(?:/|$)"),
        "Case-local folder relative to a user's domain directory, not repo root.",
    ),
    (
        re.compile(r"^references/$"),
        "Generic skill references/ subfolder cited without a skill prefix.",
    ),
    (
        re.compile(r"^\.ai/$"),
        "Local maintainer workspace folder name when no file inside it is named.",
    ),
    (
        re.compile(r"^ref/CRSS_DB(?:/|$)"),
        "Unshipped CRSS data bundle documented in DATA.md.",
    ),
    (
        re.compile(r"^paper(?:/|$)"),
        "External manuscript directory outside the public repository.",
    ),
    (
        re.compile(r"^(?:JOH_[A-Za-z0-9_]*|_archive_[A-Za-z0-9_.-]*)/$|^examples/(?:single_agent|irrigation_abm)/results/"),
        "Gitignored paper experiment output and archived run directories.",
    ),
    (
        re.compile(r"^code/chapter8/"),
        "External Hello-Agents book code folder cited in docs/references/Chapter8-Memory-and-Retrieval.md.",
    ),
)


def _tracked_files() -> set[str]:
    out = subprocess.check_output(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        stderr=subprocess.DEVNULL,
    ).decode("utf-8")
    return {line for line in out.split("\0") if line}


def _has_chinese_prose(path: Path) -> bool:
    if path.name.endswith("_zh.md") or path.name == "README_zh.md":
        return True
    text = path.read_text(encoding="utf-8", errors="replace")
    stripped = re.sub(r"\[中文\]\([^)]+\)", "", text)
    return bool(re.search(r"[\u4e00-\u9fff]", stripped))


def _is_in_scope(rel_path: str) -> bool:
    if not rel_path.endswith(".md"):
        return False
    in_scope_prefix = (
        rel_path in ("ARCHITECTURE.md", "broker/INVARIANTS.md")
        or (rel_path.startswith("broker/") and rel_path.endswith("/README.md"))
        or rel_path.startswith(".claude/skills/")
        or (
            rel_path.startswith("docs/")
            and not rel_path.startswith(OUT_OF_SCOPE_DIRS)
            and rel_path not in OUT_OF_SCOPE_FILES
        )
    )
    if not in_scope_prefix:
        return False
    return not _has_chinese_prose(ROOT / rel_path)


def _clean_candidate(raw: str, *, is_link: bool = False) -> str | None:
    s = raw.strip().strip("'\"")
    if not s:
        return None
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", s) or s.startswith(("mailto:", "#", "/", "~/", "~\\")):
        return None
    if re.match(r"^[A-Za-z]:[\\/]", s):
        return None
    s = re.split(r"#|::", s)[0]
    s = re.sub(r":\d+(?:-\d+)?$", "", s)
    s = re.sub(r"(\.[A-Za-z0-9_]+):[A-Za-z_][\w.]*$", r"\1", s)
    if any(ch in s for ch in (" ", "\t", "=", "|", "(", ")", "[", "]", ";", ",")):
        return None
    if "/" not in s:
        # A bare file name is checked only as a link target (e.g. `[next](02-rules.md)`,
        # resolved against the doc's own folder); in backticks it is too ambiguous.
        if is_link and not s.startswith(".") and EXT_RE.search(s):
            return s
        return None
    if s.endswith("/"):
        return s
    last = s.rsplit("/", 1)[-1]
    if "." in last and not last.startswith(".") and EXT_RE.search(last):
        return s
    return None


def _extract_paths(text: str) -> dict[str, bool]:
    """Return {candidate_path: seen_as_markdown_link} excluding code fences."""
    no_fence = FENCE_RE.sub("", text)
    found: dict[str, bool] = {}
    for match in BACKTICK_RE.finditer(no_fence):
        candidate = _clean_candidate(match.group(1))
        if candidate:
            found.setdefault(candidate, False)
    for match in LINK_RE.finditer(no_fence):
        candidate = _clean_candidate(match.group(1), is_link=True)
        if candidate:
            found[candidate] = True
    return found


def _allowlisted_reason(candidate: str) -> str | None:
    for pattern, reason in ALLOWLIST_PATTERNS:
        if pattern.search(candidate):
            return reason
    return None


def _exists_in_repo(rel_file: str, candidate: str, is_link: bool, tracked: set[str], dirs: set[str]) -> bool:
    rel = candidate.rstrip("/")
    md_path = ROOT / rel_file
    # A Markdown link target resolves only against the doc's own folder, as GitHub
    # renders it; a path in backticks is read from the repository root.
    if is_link:
        bases = [md_path.parent]
    else:
        bases = [ROOT]
    # Skill-folder-relative paths in .claude/skills/ are covered by tests/test_skill_paths_exist.py.
    if not is_link and rel_file.startswith(".claude/skills/"):
        skills_root = ROOT / ".claude" / "skills"
        rel_parts = Path(rel_file).parts
        if len(rel_parts) >= 3:
            bases.append(ROOT / rel_parts[0] / rel_parts[1] / rel_parts[2])
        bases.extend([md_path.parent, skills_root])

    for base in bases:
        try:
            resolved = (base / rel).resolve().relative_to(ROOT).as_posix()
        except ValueError:
            continue
        if resolved in tracked or resolved in dirs:
            return True
    return False


def _tracked_dirs(tracked: set[str]) -> set[str]:
    dirs: set[str] = set()
    for entry in tracked:
        parent = Path(entry).parent
        while parent != Path("."):
            dirs.add(parent.as_posix())
            parent = parent.parent
    return dirs


def find_missing_paths(rel_files: list[str] | None = None, *, text_overrides: dict[str, str] | None = None) -> list[str]:
    """Return formatted missing-path violations across in-scope markdown files."""
    tracked = _tracked_files()
    dirs = _tracked_dirs(tracked)
    files = rel_files if rel_files is not None else sorted(f for f in tracked if _is_in_scope(f))
    missing: list[str] = []
    for rel_file in files:
        text = text_overrides[rel_file] if text_overrides and rel_file in text_overrides else (ROOT / rel_file).read_text(encoding="utf-8", errors="replace")
        for candidate, is_link in sorted(_extract_paths(text).items()):
            if _allowlisted_reason(candidate) is not None:
                continue
            if not _exists_in_repo(rel_file, candidate, is_link, tracked, dirs):
                missing.append(f"{rel_file}: {candidate} ({FAILURE_HINT})")
    return missing


def test_every_repo_path_in_in_scope_docs_exists() -> None:
    missing = find_missing_paths()
    assert not missing, (
        f"Docs name repo-relative path(s) that do not exist ({FAILURE_HINT}):\n"
        + "\n".join(missing)
    )


def test_allowlist_skips_placeholders_and_flags_missing_repo_paths() -> None:
    sample = (
        "Valid: `broker/core/skill_broker_engine.py`, "
        "[ref](docs/AUDIT_SCHEMA.md#contract), "
        "URL `https://example.com/a/b.py`, "
        "placeholder `examples/<domain>/agent_types.yaml`, "
        "crss `ref/CRSS_DB/CRSS_DB/Div_States/UB_discrete_states.csv`, "
        "broken `broker/does_not_exist_xyz.py`, "
        "same-folder link [ok](README.md), "
        "broken same-folder link [bad](no_such_sibling_xyz.md), "
        "bare name in backticks `not_checked_xyz.md`."
    )
    missing = find_missing_paths(["ARCHITECTURE.md"], text_overrides={"ARCHITECTURE.md": sample})
    assert len(missing) == 2, missing
    assert all("ARCHITECTURE.md" in m and FAILURE_HINT in m for m in missing)
    assert any("broker/does_not_exist_xyz.py" in m for m in missing)
    assert any("no_such_sibling_xyz.md" in m for m in missing)


def test_link_target_in_nested_doc_resolves_only_against_its_folder() -> None:
    doc = "docs/tutorial/04-water-model.md"
    sample = "Root file linked as if local [bad](DATA.md), correct link [ok](../../DATA.md)."
    missing = find_missing_paths([doc], text_overrides={doc: sample})
    assert missing == [f"{doc}: DATA.md ({FAILURE_HINT})"], missing
