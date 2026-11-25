"""MkDocs build hooks for the WAGF User Manual.

Keeps repo-relative links inside ``docs/**/*.md`` intact for GitHub browsing and
``tests/test_docs_paths_exist.py`` while rewriting links that target files or
directories outside ``docs/`` so the built static manual contains working URLs.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

_TOKEN_RE = re.compile(
    r"(?P<fence>```[\s\S]*?```|~~~[\s\S]*?~~~)"
    r"|(?P<code>`[^`\n]+`)"
    r"|(?P<link>(?P<bang>!?)\[(?P<label>[^\]\n]*)\]\((?P<inner>[^)\n]+)\))"
)
_INNER_RE = re.compile(r'^(?P<target>\S+)(?P<title>\s+(?:"[^"]*"|\'[^\']*\'))?$')
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_DEFAULT_REPO_URL = "https://github.com/WenyuChiou/WAGF"


def _split_suffix(target: str) -> tuple[str, str]:
    for idx, ch in enumerate(target):
        if ch in ("?", "#"):
            return target[:idx], target[idx:]
    return target, ""


def _rewrite_target(
    raw_target: str,
    *,
    page_fs_dir: Path,
    docs_dir: Path,
    repo_root: Path,
    repo_url: str,
) -> str | None:
    if raw_target.startswith(("#", "/")) or _SCHEME_RE.match(raw_target):
        return None
    path_part, suffix = _split_suffix(raw_target)
    if not path_part:
        return None

    try:
        resolved = (page_fs_dir / path_part).resolve()
    except OSError:
        return None

    if resolved == docs_dir or resolved.is_relative_to(docs_dir):
        if ".." in Path(path_part).parts:
            rel_inside = os.path.relpath(resolved, page_fs_dir).replace(os.sep, "/")
            return f"{rel_inside}{suffix}"
        return None

    if resolved != repo_root and not resolved.is_relative_to(repo_root):
        return None
    if not resolved.exists():
        return None

    repo_rel = resolved.relative_to(repo_root).as_posix()
    kind = "tree" if resolved.is_dir() else "blob"
    return f"{repo_url}/{kind}/main/{repo_rel}{suffix}"


def on_page_markdown(markdown: str, page, config, files) -> str:
    """Rewrite repo-external links in built pages to the GitHub repository URL."""
    docs_dir = Path(config["docs_dir"]).resolve()
    repo_root = docs_dir.parent
    page_fs_dir = (docs_dir / page.file.src_path).resolve().parent
    repo_url = (config.get("repo_url") or _DEFAULT_REPO_URL).rstrip("/")

    def _replace(match: re.Match[str]) -> str:
        if match.group("fence") or match.group("code"):
            return match.group(0)
        inner = match.group("inner").strip()
        parsed = _INNER_RE.match(inner)
        if not parsed:
            return match.group(0)
        rewritten = _rewrite_target(
            parsed.group("target"),
            page_fs_dir=page_fs_dir,
            docs_dir=docs_dir,
            repo_root=repo_root,
            repo_url=repo_url,
        )
        if rewritten is None:
            return match.group(0)
        title = parsed.group("title") or ""
        return f"{match.group('bang')}[{match.group('label')}]({rewritten}{title})"

    return _TOKEN_RE.sub(_replace, markdown)
