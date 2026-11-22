#!/usr/bin/env python3
"""Share check for a WAGF run folder (or a staged copy of one).

Looks for what must not leave the author's machine:

  drive_letter   a Windows drive path ("C:\\" or "C:/")
  unc_path       a network path ("\\\\host\\share\\")
  user_folder    a user-folder path ("\\Users\\", "/Users/", "/home/", "\\home\\", "~/", "~\\"),
                 in any letter case
  encoded_path   a URL-encoded drive or user-folder path ("C%3A%5C", "%2FUsers%2F")
  literal_key    a value shaped like a provider key, or a key-like field in a .json,
                 .jsonl or .yaml file that holds a literal value instead of an environment
                 reference "${NAME}" (the provider factory accepts both)
  email          an e-mail address
  not_allowed    a file that is not on reproduction/share_allowlist.txt
  link           a symbolic link or junction inside the folder; it is never followed
  parse_error    a .json, .jsonl or .yaml file (or lines of one) that does not parse, so
                 its fields were not checked
  not_scanned    a binary file (by suffix or by content); its bytes were not checked
  unreadable     a file or folder that could not be read

A file counts as clean only when it was read and scanned. The output names file paths
(relative to the scanned folder), field names and counts; it never prints a matched
value, and a field name that itself looks like a path or key is printed as
"<field name hidden>". Exit code 0 = clean, 1 = something found, 2 = usage error.

    python reproduction/check_share.py <run-folder> [<run-folder> ...]
    python reproduction/check_share.py --scan-only <run-folder>   # skip the allowlist test
    python reproduction/check_share.py --stage <dest> <run-folder> # copy allowlisted files, paths redacted, then check the copy

A folder may also hold many run folders (it is walked without following links): every
directory that contains a reproducibility_manifest.json is one run folder. Each run
folder is named by its last path parts, as many as make the names unique, joined with
"__" (for example JOH_strict_defaults_gemma3_4b_9c4ba160__Run_42). With --stage each
one is copied to DEST/<that name>. Nothing is copied when any target already exists,
when the destination holds a source run folder, or when a target lies inside one.
"""
from __future__ import annotations

import argparse
import collections
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

import yaml  # PyYAML is a project dependency. Imported here so a missing module stops the check instead of passing files unparsed.

HERE = Path(__file__).resolve().parent
DEFAULT_ALLOWLIST = HERE / "share_allowlist.txt"
MANIFEST = "reproducibility_manifest.json"

# Where a path starts. The same pieces find paths (PATTERNS) and blank them (PATH_TOKEN).
_DRIVE = rb"(?<![A-Za-z0-9])[A-Za-z]:[\\/]"
# Two or more backslashes, a host name, a separator. Not after a path character, so the
# escaped separators of a relative path in JSON ("config\\\\prompts") do not count.
_UNC = rb"(?<![A-Za-z0-9._$%~:\\/-])\\{2,}[A-Za-z0-9][A-Za-z0-9._$-]*[\\/]"
_USER = rb"(?i:[\\/]+(?:users|home)[\\/])"
_TILDE = rb"(?<![A-Za-z0-9._-])~[\\/]"
_ENCODED = rb"(?i:[A-Za-z]%3A(?:%5C|%2F)|(?:%5C|%2F)(?:users|home)(?:%5C|%2F))"

PATTERNS = {
    "drive_letter": re.compile(_DRIVE),
    "unc_path": re.compile(_UNC),
    "user_folder": re.compile(_USER + rb"|" + _TILDE),
    "encoded_path": re.compile(_ENCODED),
    "literal_key": re.compile(
        rb"(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|ghp_[A-Za-z0-9]{30,}"
        rb"|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{30,}|gsk_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"
        rb"|xox[abprs]-[A-Za-z0-9-]{10,})"),
    "email": re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+"),
}
ENV_REF = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")
# Field names that hold a secret. A name with one of KEY_WORDS (api_key, client_secret,
# password) is flagged for any literal value. A name whose last word is "key", "token" or
# "pat" (hf_token, openaiKey; not max_tokens) is flagged only when its value looks like a
# secret (SECRET_SHAPED), because configs also use "key" for plain names (fields[].key: decision).
KEY_WORDS = ("apikey", "secret", "password", "passwd", "credential", "privatekey", "accesstoken",
             "authtoken", "refreshtoken", "bearer")
KEY_LAST_WORDS = ("key", "token", "pat")
SECRET_SHAPED = re.compile(r"^(?=[^ ]*[A-Za-z])(?=[^ ]*[0-9])[A-Za-z0-9_.+/=-]{16,}$")

# --stage: a path-looking token. A token that passes through a repo folder ("examples")
# keeps its repo-relative tail, written with forward slashes; any other becomes
# "<path removed>". A space belongs to the path when the next word runs into a separator
# ("My Project\run"), so a folder name with a space is not left half behind.
_BODY = rb"(?:[^\s\"'<>|,;]| (?=[^\s\"'<>|,;\\/]+[\\/]))*"
PATH_TOKEN = re.compile(rb"(?:" + rb"|".join((_DRIVE, _UNC, _USER, _TILDE, _ENCODED)) + rb")" + _BODY)
# The user name right after Users/home may hold spaces or an apostrophe and may end the
# path; it is replaced first ("First O'Last" -> "USER") so the whole path is one token for
# PATH_TOKEN. A work OneDrive folder ("OneDrive - Org Name") loses its organisation name.
USER_NAME = re.compile(rb"(?i)([\\/]+(?:users|home)[\\/]+)"
                       rb"(?:[^\\/\r\n\"<>|,;]{1,64}?(?=[\\/])|[^\\/\r\n\"'<>|,;]{1,64}?(?=[\\/\r\n\"'<>|,;]|$))")
ONEDRIVE = re.compile(rb"(?i)([\\/]OneDrive) - [^\\/\r\n\"<>|,;]{1,80}?(?=[\\/])")
REPO_ANCHOR = re.compile(rb"(?<=[\\/])examples[\\/]")
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".npy", ".npz", ".parquet", ".pkl"}


def load_allowlist(path: Path) -> list[str]:
    pats = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pats.append(line)
    return pats


def is_allowed(rel: str, patterns: list[str]) -> bool:
    """Case-sensitive, one path part at a time: a pattern without "/" matches only a file
    at the top of the run folder ("*" never crosses a "/")."""
    parts = rel.split("/")
    for pat in patterns:
        pp = pat.split("/")
        if len(pp) == len(parts) and all(fnmatch.fnmatchcase(a, b) for a, b in zip(parts, pp)):
            return True
    return False


# ---------------------------------------------------------------- walking, links not followed

def _is_link(p: Path) -> bool:
    try:
        if p.is_symlink():
            return True
    except OSError:
        return True
    isjunction = getattr(os.path, "isjunction", None)  # Python 3.12+
    if isjunction is not None:
        return isjunction(p)
    try:
        st = os.lstat(p)
    except OSError:
        return False
    return bool(getattr(st, "st_file_attributes", 0) & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT (Windows)


def walk(folder: Path):
    """Yield (kind, path): kind is "file", "link" (a symlink or junction, not followed) or
    "unreadable" (a folder that could not be listed)."""
    errors: list[OSError] = []
    for dirpath, dirnames, filenames in os.walk(folder, followlinks=False, onerror=errors.append):
        while errors:
            e = errors.pop(0)
            yield "unreadable", Path(e.filename) if e.filename else Path(dirpath)
        d = Path(dirpath)
        keep = []
        for name in sorted(dirnames):
            if _is_link(d / name):
                yield "link", d / name
            else:
                keep.append(name)
        dirnames[:] = keep
        for name in sorted(filenames):
            p = d / name
            yield ("link" if _is_link(p) else "file"), p
    for e in errors:
        yield "unreadable", Path(e.filename) if e.filename else folder


def _rel(path: Path, folder: Path) -> str:
    try:
        return path.relative_to(folder).as_posix() or "."
    except ValueError:
        return "<outside the folder>"


def _inside(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root)
    except OSError:
        return False


# ---------------------------------------------------------------- scanning one file

def _text_bytes(raw: bytes) -> tuple[bytes | None, str | None]:
    """(bytes to scan, encoding to write back): UTF-16 is decoded and handed on as UTF-8;
    other text is scanned as stored (every pattern is ASCII). (None, None) = binary."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        enc = "utf-16"
    elif b"\x00" in raw[:4096]:
        head = raw[:4096]
        if head[1::2].count(0) > len(head) // 4:      # ASCII text in UTF-16-LE: every odd byte NUL
            enc = "utf-16-le"
        elif head[0::2].count(0) > len(head) // 4:
            enc = "utf-16-be"
        else:
            return None, None
    else:
        return raw, None
    try:
        decoded = raw.decode(enc)
    except UnicodeDecodeError:
        return None, None
    if "\x00" in decoded:  # UTF-32, or binary that happened to decode: never pass it as scanned
        return None, None
    return decoded.encode("utf-8"), enc


def _structured(suffix: str, text: bytes) -> tuple[list, int]:
    """Parsed documents and the number of parse failures (whole file, or lines of a .jsonl)."""
    s = text.decode("utf-8-sig", errors="replace")
    if suffix == ".json":
        try:
            return [json.loads(s)], 0
        except ValueError:
            return [], 1
    if suffix == ".jsonl":
        docs, bad = [], 0
        for line in s.splitlines():
            if line.strip():
                try:
                    docs.append(json.loads(line))
                except ValueError:
                    bad += 1
        return docs, bad
    if suffix in (".yaml", ".yml"):
        try:
            return list(yaml.safe_load_all(s)), 0
        except yaml.YAMLError:
            return [], 1
    return [], 0


def _walk_fields(obj, path: str = "", name: str = ""):
    """Yield (field path, key name, value) for every scalar; array positions collapse to []."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            k = str(k)
            yield from _walk_fields(v, f"{path}.{k}" if path else k, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_fields(v, f"{path}[]", name)
    else:
        yield path, name, obj


def key_field_kind(name: str) -> str | None:
    """"strong" (any literal counts), "weak" (only a secret-shaped value counts) or None."""
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()
    words = [w for w in re.split(r"[^a-z0-9]+", snake) if w]
    if any(k in "".join(words) for k in KEY_WORDS):
        return "strong"
    return "weak" if words and words[-1] in KEY_LAST_WORDS else None


def _literal(value, kind: str | None) -> bool:
    if kind is None or value is None or isinstance(value, bool):
        return False
    if isinstance(value, str):
        s = value.strip()
        if not s or ENV_REF.match(s):
            return False
        return kind == "strong" or bool(SECRET_SHAPED.match(s))
    return kind == "strong"  # a number, a date: still a literal value


def _safe_where(fpath: str) -> str:
    b = fpath.encode("utf-8", "replace")
    return "<field name hidden>" if any(rx.search(b) for rx in PATTERNS.values()) else fpath


def scan_file(path: Path) -> list[tuple[str, str, int]]:
    """Return (category, where, count): where is a field path or '-' for plain text."""
    if path.suffix.lower() in BINARY_SUFFIXES:
        return [("not_scanned", "-", 1)]
    try:
        raw = path.read_bytes()
    except OSError:
        return [("unreadable", "-", 1)]
    text, _ = _text_bytes(raw)
    if text is None:
        return [("not_scanned", "-", 1)]
    counts = {cat: len(rx.findall(text)) for cat, rx in PATTERNS.items()}
    docs, bad = _structured(path.suffix.lower(), text)
    where: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    key_fields: collections.Counter = collections.Counter()
    for doc in docs:
        for fpath, name, value in _walk_fields(doc):
            if isinstance(value, str):
                b = value.encode("utf-8", "replace")
                for cat, rx in PATTERNS.items():
                    if rx.search(b):
                        where[fpath][cat] += 1
            if _literal(value, key_field_kind(name)):
                key_fields[fpath] += 1
    found: list[tuple[str, str, int]] = []
    for cat, n in counts.items():
        in_fields = sum(c[cat] for c in where.values())
        if n or in_fields:  # a value written as JSON escapes (\\u0043...) is seen only once parsed
            fields = sorted({_safe_where(p) for p, c in where.items() if c[cat]})
            found.append((cat, ", ".join(fields) if fields else "-", max(n, in_fields)))
    for fpath, n in sorted(key_fields.items()):
        if where.get(fpath, collections.Counter())["literal_key"]:
            continue  # this field's value is already counted above as key-shaped
        found.append(("literal_key", _safe_where(fpath), n))
    if bad:
        found.append(("parse_error", "-", bad))
    return found


# ---------------------------------------------------------------- folders

def run_folders(arg: Path) -> list[Path]:
    if (arg / MANIFEST).is_file() and not _is_link(arg / MANIFEST):
        return [arg]
    hits = sorted({p.parent for kind, p in walk(arg) if kind == "file" and p.name == MANIFEST})
    return hits or [arg]


def check_folder(folder: Path, patterns: list[str] | None) -> list[tuple[str, str, str, int]]:
    """Findings as (relative file, category, where, count)."""
    findings = []
    root = folder.resolve()
    for kind, path in walk(folder):
        rel = _rel(path, folder)
        if kind != "file" or not _inside(path, root):
            findings.append((rel, "link" if kind != "unreadable" else "unreadable", "-", 1))
            continue
        if patterns is not None and not is_allowed(rel, patterns):
            findings.append((rel, "not_allowed", "-", 1))
            continue  # a file that may not be shared is not scanned further
        for cat, where, n in scan_file(path):
            findings.append((rel, cat, where, n))
    return findings


def unique_names(parts: list[tuple[str, ...]]) -> list[str]:
    """The last path parts of each folder, as many as make all names unique without regard to
    letter case (a Windows folder name ignores it), joined by "__". The drive or root part is
    never used; if the names still collide, a number is added."""
    parts = [tuple(p[1:]) if p and (p[0].endswith(("\\", "/")) or p[0].endswith(":")) else tuple(p) for p in parts]
    longest = max((len(p) for p in parts), default=1)
    names: list[str] = []
    for k in range(1, longest + 1):
        names = ["__".join(p[-k:]) or "run" for p in parts]
        if len({n.casefold() for n in names}) == len(names):
            return names
    seen: dict[str, int] = {}
    out = []
    for n in names:
        seen[n.casefold()] = seen.get(n.casefold(), 0) + 1
        out.append(n if seen[n.casefold()] == 1 else f"{n}__{seen[n.casefold()]}")
    return out


def display_names(folders: list[Path]) -> list[str]:
    return unique_names([f.resolve().parts for f in folders])


def _blank_path(m: re.Match) -> bytes:
    tok = m.group(0)
    a = REPO_ANCHOR.search(tok)
    if a is None:
        return b"<path removed>"
    return re.sub(rb"[\\/]+", b"/", tok[a.start():])


def blank_paths(text: bytes) -> bytes:
    return PATH_TOKEN.sub(_blank_path, ONEDRIVE.sub(rb"\1", USER_NAME.sub(rb"\1USER", text)))


def stage(folder: Path, target: Path, patterns: list[str]) -> tuple[int, list[tuple[str, str, str, int]]]:
    """Copy the allowlisted files of `folder` to `target`, blanking absolute paths.
    Returns (files copied, findings about the source: links and unreadable entries, which
    are never copied)."""
    copied, findings = 0, []
    root = folder.resolve()
    for kind, path in walk(folder):
        rel = _rel(path, folder)
        if kind != "file" or not _inside(path, root):
            findings.append((rel, "link" if kind != "unreadable" else "unreadable", "-", 1))
            continue
        if not is_allowed(rel, patterns):
            continue
        out = target / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            raw = path.read_bytes()
        except OSError:
            findings.append((rel, "unreadable", "-", 1))
            continue
        text, enc = (None, None) if path.suffix.lower() in BINARY_SUFFIXES else _text_bytes(raw)
        if text is None:
            out.write_bytes(raw)  # binary: copied as is; the check of the copy reports it as not_scanned
        else:
            blanked = blank_paths(text)
            out.write_bytes(blanked.decode("utf-8").encode(enc) if enc else blanked)
        copied += 1
    return copied, findings


def _refuse_stage(dest: Path, folders: list[Path], names: list[str]) -> str | None:
    dest = dest.resolve()
    for folder, name in zip(folders, names):
        src, target = folder.resolve(), dest / name
        if target.exists():
            return f"{target} already exists; stage into an empty destination"
        if src.is_relative_to(dest) or target.is_relative_to(src):
            return f"the destination and the run folder {name} overlap; stage outside the run folders"
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("folders", nargs="+", type=Path)
    ap.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    ap.add_argument("--scan-only", action="store_true", help="skip the allowlist test; scan every file")
    ap.add_argument("--stage", type=Path, metavar="DEST",
                    help="copy allowlisted files (paths blanked) under DEST/<name>, then check the copies")
    args = ap.parse_args(argv)

    try:
        patterns = None if args.scan_only else load_allowlist(args.allowlist)
        if args.stage and patterns is None:
            raise ValueError("--stage needs the allowlist; do not combine it with --scan-only")
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    folders: list[Path] = []
    for arg in args.folders:
        if not arg.is_dir():
            print(f"error: {arg} is not a folder", file=sys.stderr)
            return 2
        for f in run_folders(arg):
            if all(f.resolve() != g.resolve() for g in folders):
                folders.append(f)
    names = display_names(folders)
    if args.stage:
        why = _refuse_stage(args.stage, folders, names)
        if why:
            print(f"error: {why}; nothing was copied", file=sys.stderr)
            return 2

    total = 0
    for folder, name in zip(folders, names):
        target, findings = folder, []
        if args.stage:
            target = args.stage / name
            copied, findings = stage(folder, target, patterns)
            print(f"staged {copied} files: {name}")
        findings += check_folder(target, patterns) if target.is_dir() else []
        if not findings:
            print(f"OK     {name}")
            continue
        print(f"FOUND  {name}")
        for rel, cat, where, n in findings:
            total += n
            print(f"  {rel}: {cat} x{n}" + (f" in field {where}" if where != "-" else ""))
    print(f"{len(folders)} folder(s) checked, {total} finding(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
