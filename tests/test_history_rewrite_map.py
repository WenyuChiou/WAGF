"""Old -> new commit ids after the history rewrite of 2026-11-21.

Checks the files in reproduction/history_rewrite/: the full commit map, the
commits the paper relies on, and the commit fields of the 30 paper runs
(15 flood, 15 irrigation). See reproduction/history_rewrite/README.md.
"""
from __future__ import annotations

import collections
import csv
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "reproduction" / "history_rewrite"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX_IN_TEXT = re.compile(r"(?<![0-9a-fA-F])[0-9a-f]{7,40}(?![0-9a-fA-F])")

MAP_SIZE = 2072
FLOOD_NEW = "98b542986bd409786b8662710dbed4bf45500a77"
IRRIGATION_NEW = "258978134d67515c517677ce7b5f79d57aeeee00"
SEEDS = {"42", "43", "44", "45", "46"}
SETS = {
    "flood": {"disabled", "silent", "strict"},
    "irrigation": {"disabled", "disabled_withlimit", "strict"},
}
EXPECTED = {
    "flood": (FLOOD_NEW, "True"),
    "irrigation": (IRRIGATION_NEW, "False"),
}


def _read_tsv(name: str) -> list[dict[str, str]]:
    with open(D / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


@pytest.fixture(scope="module")
def commit_map() -> dict[str, str]:
    lines = (D / "commit-map.txt").read_text(encoding="ascii").splitlines()
    assert lines[0].split() == ["old", "new"], "header line changed"
    m: dict[str, str] = {}
    for n, line in enumerate(lines[1:], start=2):
        parts = line.split()
        assert len(parts) == 2, f"commit-map.txt line {n}: {line!r}"
        old, new = parts
        assert HEX40.match(old) and HEX40.match(new), f"commit-map.txt line {n}: not two 40-hex ids"
        assert new != "0" * 40, f"commit-map.txt line {n}: commit was dropped"
        assert old not in m, f"commit-map.txt line {n}: old id {old[:12]} listed twice"
        m[old] = new
    return m


def resolve(m: dict[str, str], short: str) -> str:
    """New id for an old id or a prefix of 7+ characters; exactly one match."""
    assert len(short) >= 7, f"{short!r} is too short to look up"
    hits = [old for old in m if old.startswith(short)]
    assert len(hits) == 1, f"{short!r} matches {len(hits)} old ids"
    return m[hits[0]]


def test_map_lists_every_rewritten_commit_once(commit_map):
    assert len(commit_map) == MAP_SIZE
    assert len(set(commit_map.values())) == MAP_SIZE, "two old commits map to one new commit"


def test_manifest_table_covers_the_30_paper_runs():
    rows = _read_tsv("paper_manifest_commits.tsv")
    assert len(rows) == 30
    for case, sets in SETS.items():
        got = {(r["set"], r["seed"]) for r in rows if r["case"] == case}
        assert got == {(s, seed) for s in sets for seed in SEEDS}, case


def test_every_manifest_commit_resolves_to_the_paper_commit(commit_map):
    for r in _read_tsv("paper_manifest_commits.tsv"):
        where = f"{r['case']} {r['set']} seed {r['seed']}"
        new, dirty = EXPECTED[r["case"]]
        for field in ("git_commit", "git_commit_at_finalize", "git_commit_short"):
            assert resolve(commit_map, r[field]) == new, f"{where}: {field}"
        assert r["git_dirty"] == dirty and r["git_dirty_at_finalize"] == dirty, f"{where}: dirty flag"
        assert r["git_commit"][:8] in r["run_folder"], f"{where}: folder does not name its commit"


def test_paper_commits_agree_with_the_map(commit_map):
    rows = {r["role"]: r for r in _read_tsv("paper_commits.tsv")}
    for role, r in rows.items():
        assert commit_map[r["old_commit"]] == r["new_commit"], role
    assert rows["flood_paper_runs"]["new_commit"] == FLOOD_NEW
    assert rows["irrigation_paper_runs"]["new_commit"] == IRRIGATION_NEW
    tags = [r["tag"] for r in rows.values() if r["tag"]]
    assert len(tags) == 4 and len(set(tags)) == 4, tags


def test_old_ids_named_in_tracked_files_resolve(commit_map):
    rows = {r["role"]: r for r in _read_tsv("paper_commits.tsv")}
    fig2 = (ROOT / "examples/single_agent/analysis/fig2_flood_sq1.py").read_text(encoding="utf-8")
    rulebased = re.search(r'^RULEBASED_COMMIT = "([0-9a-f]+)"', fig2, re.M).group(1)
    assert resolve(commit_map, rulebased) == rows["flood_rulebased_reference"]["new_commit"]
    baseline = (ROOT / "examples/reservoir_control_multidim/BASELINE_e4b.md").read_text(encoding="utf-8")
    code_commit = re.search(r"\| Code commit \| `([0-9a-f]+)`", baseline).group(1)
    assert resolve(commit_map, code_commit) == rows["reservoir_multidim_baseline"]["new_commit"]


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=60)


def test_paper_commits_are_in_this_history():
    try:
        probe = _git("rev-parse", "--is-shallow-repository")
    except (OSError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"git not usable here: {exc}")
    if probe.returncode != 0:
        pytest.skip("not a git checkout")
    if probe.stdout.strip() == "true":
        pytest.skip("shallow clone: old commits not fetched")
    for r in _read_tsv("paper_commits.tsv"):
        res = _git("merge-base", "--is-ancestor", r["new_commit"], "HEAD")
        assert res.returncode == 0, f"{r['role']}: {r['new_commit'][:12]} is not in HEAD's history ({res.stderr.strip()})"
        if not r["tag"]:
            continue
        # A clone without the tags (a fork, a tarball) passes; a tag that exists must point here.
        tag = _git("rev-parse", "--verify", "--quiet", f"refs/tags/{r['tag']}^{{commit}}")
        if tag.returncode == 0:
            assert tag.stdout.strip() == r["new_commit"], f"tag {r['tag']} points at {tag.stdout.strip()[:12]}, not {r['new_commit'][:12]}"


def _strings(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v, f"{path}[]")
    elif isinstance(obj, str):
        yield path, obj


def test_run_manifests_match_the_table_when_present(commit_map):
    """Runs only where the run folders exist (they are not in git).

    WAGF_RESULTS_ROOT points at the checkout that holds them; default is this one.
    """
    root = Path(os.environ.get("WAGF_RESULTS_ROOT") or ROOT)
    rows = _read_tsv("paper_manifest_commits.tsv")
    paths = {id(r): root / r["run_folder"] / "reproducibility_manifest.json" for r in rows}
    present = [r for r in rows if paths[id(r)].is_file()]
    if not present:
        pytest.skip(f"no paper run folders under {root}; set WAGF_RESULTS_ROOT to check them")
    missing = [r["run_folder"] for r in rows if not paths[id(r)].is_file()]
    assert not missing, f"{len(missing)} of 30 run manifests missing under {root}: {missing}"

    named = collections.Counter()
    for r in rows:
        where = r["run_folder"]
        d = json.loads(paths[id(r)].read_text(encoding="utf-8-sig"))
        prov = d.get("run_integrity", {}).get("framework_provenance", {})
        assert d["git_commit"] == r["git_commit"], where
        assert d.get("git_commit_at_finalize", "") == r["git_commit_at_finalize"], where
        assert prov.get("git_commit_short", "") == r["git_commit_short"], where
        assert str(d.get("git_dirty")) == r["git_dirty"], where
        assert str(d.get("git_dirty_at_finalize")) == r["git_dirty_at_finalize"], where

        # Every value in the manifest that names an old commit names the paper commit.
        fields = set()
        for path, text in _strings(d):
            for h in HEX_IN_TEXT.findall(text):
                hits = [old for old in commit_map if old.startswith(h)]
                if len(hits) == 1:
                    assert commit_map[hits[0]] == EXPECTED[r["case"]][0], f"{where}: {path} names {h}"
                    fields.add(path)
                    named[r["case"]] += 1
        assert ";".join(sorted(fields)) == r["fields_naming_a_commit"], where
    assert named["flood"] == 45 and named["irrigation"] == 50, dict(named)
