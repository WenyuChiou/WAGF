#!/usr/bin/env python3
"""Read-only manifest checker: prints the Data availability table for the 30 paper runs.

For each run (case, set of simulations, seed) it reads the run folder's
reproducibility_manifest.json under a results root and prints:

  commit   the old id the manifest names -> the new id from
           reproduction/history_rewrite/commit-map.txt
  dirty    git_dirty at launch / at finalize (T or F)
  digest   full   the manifest carries the model digest
           short  only the short id in ollama_version.txt ("ollama ps" line)
           none   neither
  config   config_hash in the manifest against the tracked file at the new commit
           (lf / crlf = which line-ending form matched; the manifests hashed a
           Windows checkout, so a CRLF form is expected for flood)
  prompt   prompt_template_sha256 against the tracked prompt file, or "absent"
  data     irrigation data-file hashes in the manifest against the tracked files
  ollama   server version from ollama_version.txt

Nothing is written, copied or executed except `git show` and `git rev-parse` reads.
Only commit ids, hashes, flags and counts are printed; never a path taken from a manifest.

Every cell that is not a positive match is listed as a problem: a hash that does not
match, a hash or file that is absent, a manifest or config snapshot that does not parse,
an irrigation run without all six data-file hashes, a seed that differs from the table.
A run without the full model digest in its manifest (digest "short" or "none") is a
problem too, unless --expect-missing-digest N names how many such runs are known; the
check then fails only when the count differs. The one cell that is never a problem is a
prompt hash absent from the manifest ("absent"): none of the 30 paper manifests carries
one, and the recipes say so. The ollama column is information only ("-" means the run
folder holds no ollama_version.txt).

Exit code: 0 consistent; 1 at least one problem (listed at the end);
2 usage error or no run folder found under the root.

    python reproduction/check_manifests.py --root <checkout that holds the run folders>
    python reproduction/check_manifests.py --root <root> --expect-missing-digest 5
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml  # PyYAML is a project dependency; a missing module stops the check

REPO = Path(__file__).resolve().parents[1]
HIST = REPO / "reproduction" / "history_rewrite"

# Manifest field -> tracked data file (irrigation). Fields sit at the top level or in
# coupling_retrofit_metadata.
DATA_FIELDS = {
    "ub_subbasin_supply_v3_sha256": "examples/irrigation_abm/data/ub_subbasin_supply_v3.csv",
    "ub_subbasin_envelope_v3_sha256": "examples/irrigation_abm/data/ub_subbasin_envelope_v3.csv",
    "ub_subbasin_variant_means_v3_sha256": "examples/irrigation_abm/data/ub_subbasin_variant_means_v3.csv",
    "water_system_hydrology_v3_sha256": "examples/irrigation_abm/data/hydrology_v3.csv",
    "water_system_mead_capacity_sha256": "examples/irrigation_abm/data/mead_capacity_usbr2009_1ft.csv",
    "water_system_lb_priority_split_sha256": "examples/irrigation_abm/data/lb_priority_split_v3.csv",
}
ROLE = {"flood": "flood_paper_runs", "irrigation": "irrigation_paper_runs"}
HEX = re.compile(r"^[0-9a-fA-F]{12,64}$")  # a recorded hash: at least its 12-character prefix


def forms(b: bytes) -> dict[str, bytes]:
    """The three line-ending forms of one file: as stored, LF, and CRLF."""
    lf = b.replace(b"\r\n", b"\n")
    return {"raw": b, "lf": lf, "crlf": lf.replace(b"\n", b"\r\n")}


def match_forms(b: bytes | None, want: str, full: bool = False) -> str | None:
    """Name of the line-ending form whose sha256 starts with `want`, else None.
    `want` must be at least a 12-hex prefix (all 64 when `full`)."""
    if b is None or not isinstance(want, str) or not HEX.match(want):
        return None
    for name in ("lf", "crlf", "raw"):  # lf first: a LF-only file matches lf, raw and crlf-less alike
        digest = hashlib.sha256(forms(b)[name]).hexdigest()
        if digest.startswith(want.lower()) and (not full or len(want) == 64):
            return name
    return None


def repo_rel(path_text: str | None) -> str | None:
    """Repo-relative path from a path the manifest recorded, found by its `examples` folder."""
    if not path_text:
        return None
    parts = str(path_text).replace("\\", "/").split("/")
    return "/".join(parts[parts.index("examples"):]) if "examples" in parts else None


class Git:
    def __init__(self, repo: Path):
        self.repo = repo

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, timeout=60)

    def show(self, commit: str, rel: str) -> bytes | None:
        r = self._run("show", f"{commit}:{rel}")
        return r.stdout if r.returncode == 0 else None

    def has_commit(self, commit: str) -> bool:
        return self._run("cat-file", "-e", f"{commit}^{{commit}}").returncode == 0

    def tag_commit(self, tag: str) -> str | None:
        r = self._run("rev-parse", "--verify", "--quiet", f"refs/tags/{tag}^{{commit}}")
        return r.stdout.decode().strip() if r.returncode == 0 else None


def read_tsv(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def read_map(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="ascii").splitlines()
    m = {}
    for line in lines[1:]:
        parts = line.split()
        if len(parts) == 2:
            m[parts[0]] = parts[1]
    return m


def lookup(cmap: dict[str, str], short: str) -> str | None:
    if len(short or "") < 7:
        return None
    hits = [o for o in cmap if o.startswith(short)]
    return cmap[hits[0]] if len(hits) == 1 else None


def ollama_info(folder: Path) -> tuple[str, str]:
    """(server version, short model id) from ollama_version.txt; '-' when absent."""
    p = folder / "ollama_version.txt"
    if not p.is_file():
        return "-", "-"
    text = p.read_text(encoding="utf-8", errors="replace")
    v = re.search(r"ollama version is ([0-9][0-9.]*)", text)
    s = re.search(r"\b[\w.-]+:[\w.-]+\s+([0-9a-f]{12})\b", text)
    return (v.group(1) if v else "-", s.group(1) if s else "-")


def check_run(row: dict[str, str], root: Path, git: Git, cmap: dict[str, str],
              expected: dict[str, dict[str, str]]) -> dict:
    folder = root / row["run_folder"]
    out = {"case": row["case"], "set": row["set"], "seed": row["seed"], "problems": [], "found": False}
    mpath = folder / "reproducibility_manifest.json"
    if not mpath.is_file():
        out["problems"].append("run folder or manifest missing")
        out["status"] = "MISSING"
        return out
    try:
        m = json.loads(mpath.read_text(encoding="utf-8-sig"))
        if not isinstance(m, dict):
            raise ValueError("not a JSON object")
    except (OSError, ValueError):
        out["problems"].append("manifest does not parse as a JSON object")
        out["status"] = "UNREADABLE"
        return out
    out["found"] = True
    exp = expected[row["case"]]
    P = out["problems"]
    if str(m.get("seed")) != str(row["seed"]):
        P.append("seed in the manifest differs from paper_manifest_commits.tsv")

    # commit: manifest id -> new id; compare with the history-rewrite tables.
    old = m.get("git_commit") or ""
    new = lookup(cmap, old)
    out["old"], out["new"] = old[:8], (new or "?")[:8]
    if new is None:
        P.append("commit not found in commit-map")
    elif new != exp["new_commit"]:
        P.append("commit is not the paper commit for this case")
    if old != row["git_commit"]:
        P.append("git_commit differs from paper_manifest_commits.tsv")
    for f in ("git_commit_at_finalize",):
        if (m.get(f) or "") != row["git_commit_at_finalize"]:
            P.append(f"{f} differs from paper_manifest_commits.tsv")
    dl, df = m.get("git_dirty"), m.get("git_dirty_at_finalize")
    out["dirty"] = f"{'T' if dl else 'F'}/{'T' if df else 'F'}"
    if str(dl) != row["git_dirty"] or str(df) != row["git_dirty_at_finalize"]:
        P.append("dirty flag differs from paper_manifest_commits.tsv")

    # model digest
    server, short = ollama_info(folder)
    out["ollama"] = server
    d = m.get("model_digest")
    if d:
        out["digest"] = "full"
        if short not in ("-", d[:12]):
            P.append("model digest differs from the id in ollama_version.txt")
    else:
        out["digest"] = "short" if short != "-" else "none"

    # config hash
    rel = repo_rel(m.get("agent_types_config"))
    ch = m.get("config_hash") or ""
    derived = repo_rel(m.get("derived_from_config")) if m.get("derived_from_config") else None
    if not ch:
        out["config"] = "absent"
        P.append("config_hash absent from the manifest")
    elif not new:
        out["config"] = "?"  # the commit problem is already listed
    elif derived:
        # the run read a derived copy kept in the run folder; its source is tracked
        res = folder / "resolved_agent_types.yaml"
        got = match_forms(res.read_bytes(), ch) if res.is_file() else None
        src = match_forms(git.show(new, derived), str(m.get("derived_from_config_sha256") or ""))
        if not res.is_file():
            out["config"] = "derived (copy absent)"
            P.append("resolved_agent_types.yaml absent from the run folder")
        elif got is None:
            out["config"] = "MISMATCH"
            P.append("config_hash does not match the derived config in the run folder")
        else:
            out["config"] = f"derived+{src or 'NO'}"
        if src is None:
            P.append("derived_from_config_sha256 does not match the tracked source file")
    else:
        tracked = git.show(new, rel) if rel else None
        got = match_forms(tracked, ch)
        if tracked is None:
            out["config"] = "no file"
            P.append("tracked config file not found at the new commit")
        elif got is None:
            out["config"] = "MISMATCH"
            P.append("config_hash does not match the tracked config file")
        else:
            out["config"] = got

    # prompt hash
    ph = m.get("prompt_template_sha256")
    if not ph:
        out["prompt"] = "absent"  # documented: none of the paper manifests records one
    elif not isinstance(ph, dict):
        out["prompt"] = "?"
        P.append("prompt_template_sha256 is not a table of agent types")
    elif not new:
        out["prompt"] = "?"  # the commit problem is already listed
    else:
        out["prompt"] = "?"
        snap = folder / "config_snapshot.yaml"
        cfg = None
        if not snap.is_file():
            P.append("config_snapshot.yaml absent, so the prompt files cannot be found")
        else:
            try:
                cfg = yaml.safe_load(snap.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeDecodeError, yaml.YAMLError):
                P.append("config_snapshot.yaml does not parse")
            else:
                if not isinstance(cfg, dict):
                    P.append("config_snapshot.yaml is not a mapping")
                    cfg = None
        if cfg is not None:
            base = (rel or "").rsplit("/", 1)[0] if rel else ""
            results = []
            for agent_type, want in ph.items():
                entry = cfg.get(agent_type)
                ref = entry.get("prompt_template_file") if isinstance(entry, dict) else None
                cands = [repo_rel(ref)] if repo_rel(ref) else ([f"{base}/{ref}".replace("//", "/")] if ref and base else [])
                hit = None
                for c in cands:
                    b = git.show(new, c)
                    if b is not None:
                        hit = match_forms(b, want) or "NO"
                        break
                results.append(hit)
            if any(r == "NO" for r in results):
                out["prompt"] = "MISMATCH"
                P.append("prompt_template_sha256 does not match the tracked prompt file")
            elif results and all(results):
                out["prompt"] = "ok"
            else:
                P.append("a prompt file named in config_snapshot.yaml is not tracked at the new commit")

    # data-file hashes (irrigation)
    pools = [m, m.get("coupling_retrofit_metadata") or {}]
    seen = ok = 0
    for fld, drel in DATA_FIELDS.items():
        want = next((p[fld] for p in pools if isinstance(p, dict) and p.get(fld)), None)
        if not want:
            if row["case"] == "irrigation":
                P.append(f"{fld} absent from the manifest")
            continue
        seen += 1
        if new and match_forms(git.show(new, drel), want, full=True):
            ok += 1
        else:
            P.append(f"{fld} does not match the tracked data file")
    # irrigation must carry all six; flood records none
    out["data"] = f"{ok}/{len(DATA_FIELDS)}" if row["case"] == "irrigation" else ("-" if not seen else f"{ok}/{seen}")
    return out


def render(results: list[dict]) -> str:
    cols = [("case", 10), ("set", 19), ("seed", 4), ("commit", 19), ("dirty", 5), ("digest", 6),
            ("config", 12), ("prompt", 6), ("data", 4), ("ollama", 6)]
    head = "  ".join(n.ljust(w) for n, w in cols)
    lines = [head, "  ".join("-" * w for _, w in cols)]
    for r in results:
        if not r["found"]:
            lines.append("  ".join([r["case"].ljust(10), r["set"].ljust(19), str(r["seed"]).ljust(4), r.get("status", "MISSING")]))
            continue
        cells = [r["case"], r["set"], r["seed"], f"{r['old']} -> {r['new']}", r["dirty"], r["digest"],
                 r["config"], r["prompt"], r["data"], r["ollama"]]
        lines.append("  ".join(str(c).ljust(w) for c, (_, w) in zip(cells, cols)))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, required=True, help="checkout that holds the run folders")
    ap.add_argument("--repo", type=Path, default=REPO, help="git repository with the tracked files (default: this one)")
    ap.add_argument("--runs", type=Path, default=HIST / "paper_manifest_commits.tsv")
    ap.add_argument("--commits", type=Path, default=HIST / "paper_commits.tsv")
    ap.add_argument("--map", type=Path, default=HIST / "commit-map.txt")
    ap.add_argument("--expect-missing-digest", type=int, default=None, metavar="N",
                    help="fail unless exactly N manifests lack the full model digest")
    args = ap.parse_args(argv)

    try:
        rows = read_tsv(args.runs)
        by_role = {r["role"]: r for r in read_tsv(args.commits)}
        expected = {case: by_role[role] for case, role in ROLE.items()}
        cmap = read_map(args.map)
    except (OSError, KeyError) as exc:
        print(f"error: cannot read the history-rewrite tables: {exc}", file=sys.stderr)
        return 2
    if not args.root.is_dir():
        print(f"error: {args.root} is not a folder", file=sys.stderr)
        return 2

    git = Git(args.repo)
    results = [check_run(r, args.root, git, cmap, expected) for r in rows]
    found = [r for r in results if r["found"]]
    unreadable = sum(1 for r in results if r.get("status") == "UNREADABLE")
    if not found and not unreadable:
        print(f"error: no paper run folder found under the root; set --root to the checkout that holds them", file=sys.stderr)
        return 2

    print(render(results))
    problems = [(r, p) for r in results for p in r["problems"]]
    n = len(results)
    missing_digest = sum(1 for r in found if r["digest"] != "full")
    dirty = sum(1 for r in found if r["dirty"] != "F/F")
    print()
    print(f"runs listed {n}, found {len(found)}, missing folders {n - len(found) - unreadable}, unreadable manifests {unreadable}")
    print(f"without a full model digest in the manifest: {missing_digest}"
          f" (short id in ollama_version.txt: {sum(1 for r in found if r['digest'] == 'short')}, none: {sum(1 for r in found if r['digest'] == 'none')})")
    print(f"dirty at launch or finalize: {dirty}  (flood {sum(1 for r in found if r['case'] == 'flood' and r['dirty'] != 'F/F')}, "
          f"irrigation {sum(1 for r in found if r['case'] == 'irrigation' and r['dirty'] != 'F/F')})")
    print(f"config mismatches: {sum(1 for r in found if r['config'] == 'MISMATCH')}, "
          f"prompt mismatches: {sum(1 for r in found if r['prompt'] == 'MISMATCH')}, "
          f"data-hash mismatches: {sum(1 for r, p in problems if 'tracked data file' in p)}")
    if args.expect_missing_digest is None and missing_digest:
        problems.append(({"case": "-", "set": "-", "seed": "-"},
                         f"{missing_digest} run(s) without the full model digest; if that is known, "
                         f"pass --expect-missing-digest {missing_digest}"))
    if args.expect_missing_digest is not None and missing_digest != args.expect_missing_digest:
        problems.append(({"case": "-", "set": "-", "seed": "-"},
                         f"expected {args.expect_missing_digest} runs without a digest, found {missing_digest}"))
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for r, p in problems:
            print(f"  {r['case']} {r['set']} {r['seed']}: {p}")
        return 1
    print("\nno problem found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
