"""The reproduction kit: recipes, manifest checker and share check.

See reproduction/recipes/, reproduction/check_manifests.py, reproduction/check_share.py.

Fixtures: tests/fixtures/repro_kit/repo/ holds a few synthetic tracked files (agent_types
and a prompt; the data files are written at run time because *.csv is gitignored). Each test that needs a git repository copies them into a
throw-away one and builds the run folders around them at run time. Anything that looks
like a drive path, user folder or key is assembled in code, never stored in the repo.

Tests that read the real run folders (they are not in git) run only when
WAGF_RESULTS_ROOT (or this checkout) holds them: skipped when none of the 30 is there,
failed when only some are.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "reproduction"
HIST = KIT / "history_rewrite"
FIXT = ROOT / "tests" / "fixtures" / "repro_kit" / "repo"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cm = _load("check_manifests", KIT / "check_manifests.py")
cs = _load("check_share", KIT / "check_share.py")

SEEDS = [42, 43, 44, 45, 46]
BS = chr(92)  # backslash: kept out of string literals so no path-looking text sits in this file
FAKE_DRIVE = "Q" + ":" + BS + "fixture"  # a synthetic drive path, built here, not stored


def _recipe(case: str) -> dict:
    return yaml.safe_load((KIT / "recipes" / f"{case}.yaml").read_text(encoding="utf-8"))


def _tsv(name: str) -> list[dict[str, str]]:
    with open(HIST / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _crlf(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


# ---------------------------------------------------------------- recipes (no run data)

def test_recipes_cover_the_30_paper_runs_and_name_their_folders():
    rows = _tsv("paper_manifest_commits.tsv")
    for case in ("flood", "irrigation"):
        r = _recipe(case)
        want = {(x["set"], x["seed"]): x["run_folder"] for x in rows if x["case"] == case}
        got = {}
        for arm in r["arms"]:
            for seed in r["seeds"]:
                got[(arm["set"], str(seed))] = arm["folder_pattern"].format(seed=seed)
        # irrigation folder_pattern names the folder; flood names the Run_<seed> folder
        assert got == want, case


def test_recipes_commits_tags_and_flags_agree_with_the_history_tables():
    cmap = {}
    for line in (HIST / "commit-map.txt").read_text(encoding="ascii").splitlines()[1:]:
        old, new = line.split()
        cmap[old] = new
    roles = {x["role"]: x for x in _tsv("paper_commits.tsv")}
    for case, runs_role, ref_role in (("flood", "flood_paper_runs", "flood_rulebased_reference"),
                                      ("irrigation", "irrigation_paper_runs", "irrigation_fql_reference")):
        r = _recipe(case)
        for key, role in (("runs", runs_role), ("reference", ref_role)):
            c = r["commits"][key]
            assert c["old"] == roles[role]["old_commit"] and c["new"] == roles[role]["new_commit"], (case, key)
            assert cmap[c["old"]] == c["new"], (case, key)
            assert r["tags"][key] == roles[role]["tag"], (case, key)
    assert _recipe("flood")["dirty_at_launch"] is True and _recipe("flood")["changed_files_recorded"] is False
    assert _recipe("irrigation")["dirty_at_launch"] is False
    assert _recipe("irrigation")["needs_crss"] is True and _recipe("flood")["needs_crss"] is False


def test_recipe_arm_names_follow_the_settled_wording():
    labels = {(c, a["set"]): a["label"] for c in ("flood", "irrigation") for a in _recipe(c)["arms"]}
    assert labels == {
        ("flood", "disabled"): "without rules",
        ("flood", "strict"): "with rules",
        ("flood", "silent"): "with rules, no reasons (SI)",
        ("irrigation", "disabled"): "without rules",
        ("irrigation", "strict"): "with rules",
        ("irrigation", "disabled_withlimit"): "with the use limit only (SI)",
    }


def _git_available_with(commit: str) -> bool:
    try:
        probe = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{commit}^{{commit}}"],
                               capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0


def test_recipe_hashes_match_the_tracked_files_at_the_new_commits():
    """Config and data hashes in the recipes against `git show <new commit>:<file>`."""
    flood, irr = _recipe("flood"), _recipe("irrigation")
    if not (_git_available_with(flood["commits"]["runs"]["new"]) and _git_available_with(irr["commits"]["runs"]["new"])):
        pytest.skip("paper commits not in this clone (shallow or fork)")
    git = cm.Git(ROOT)
    f = git.show(flood["commits"]["runs"]["new"], flood["config"]["agent_types"])
    assert _sha(f)[:12] == flood["config"]["config_hash_of_lf_file"]
    assert _sha(_crlf(f))[:12] == flood["config"]["config_hash_in_manifest"]
    new = irr["commits"]["runs"]["new"]
    for rel, want in irr["config_hashes"].items():
        assert _sha(git.show(new, rel))[:12] == want, rel
    for rel, want in irr["data_hashes"].items():
        b = git.show(new, rel)
        assert _sha(b.replace(b"\r\n", b"\n")) == want, rel
    for case, c in (("flood", flood), ("irrigation", irr)):
        tagged = git.tag_commit(c["tags"]["runs"])
        assert tagged in (None, c["commits"]["runs"]["new"]), f"{case}: tag {c['tags']['runs']} points elsewhere"


# ---------------------------------------------------------------- argv dry-run

def expand_argv(recipe: dict, arm: dict, seed: int) -> list[str]:
    out = []
    for tok in recipe["argv"]:
        out.append(tok.replace("{seed}", str(seed)).replace("{mode}", arm["governance_mode"])
                   .replace("{config_dir}", arm["config_dir"]))
    return out


def normalise_launch(text: str) -> list[str]:
    """A stored launch_command.txt (line 1: the working folder, line 2: the command) as the
    recipe's argv: interpreter -> python, absolute paths -> repo-relative, output -> {output}."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert lines[0].startswith("cwd:"), "unexpected launch_command.txt layout"
    argv = shlex.split(lines[1], posix=False)
    out = ["python"]
    prev = ""
    for tok in argv[1:]:
        if prev == "--output":
            out.append("{output}")
        elif prev == "--config-dir":
            out.append(cm.repo_rel(tok) or tok)
        else:
            out.append(tok)
        prev = tok
    return out


def _compare_argv(want: list[str], got: list[str]) -> bool:
    return len(want) == len(got) and all(w == g or w == "{output}" for w, g in zip(want, got))


def _fake_launch(recipe: dict, arm: dict, seed: int, mutate=None) -> str:
    argv = expand_argv(recipe, arm, seed)
    argv[0] = FAKE_DRIVE + BS + "Python314" + BS + "python.exe"
    i = argv.index("--config-dir") + 1
    argv[i] = FAKE_DRIVE + BS + arm["config_dir"].replace("/", BS)
    j = argv.index("--output") + 1
    argv[j] = FAKE_DRIVE + BS + "out" + BS + f"run_{seed}"
    if mutate:
        mutate(argv)
    return f"cwd: {FAKE_DRIVE}{BS}work\n" + " ".join(argv) + "\n"


def test_irrigation_recipe_argv_matches_a_stored_launch_command_fixture():
    r = _recipe("irrigation")
    for arm in r["arms"]:
        for seed in SEEDS:
            got = normalise_launch(_fake_launch(r, arm, seed))
            assert _compare_argv(expand_argv(r, arm, seed), got), (arm["set"], seed)


def test_argv_check_catches_a_changed_flag_a_changed_config_and_a_changed_seed():
    r = _recipe("irrigation")
    arm = r["arms"][2]  # strict
    want = expand_argv(r, arm, 42)

    def set_flag(flag, value):
        def f(argv):
            argv[argv.index(flag) + 1] = value
        return f

    for flag, value in (("--paper-water-margin", "0.5"), ("--governance-mode", "disabled"), ("--workers", "1"),
                        ("--memory-seed", "7")):
        got = normalise_launch(_fake_launch(r, arm, 42, mutate=set_flag(flag, value)))
        assert not _compare_argv(want, got), flag
    got = normalise_launch(_fake_launch(r, arm, 42, mutate=set_flag("--config-dir", FAKE_DRIVE + BS + "examples" + BS + "x")))
    assert not _compare_argv(want, got)
    assert not _compare_argv(want, normalise_launch(_fake_launch(r, arm, 43)))


# ---------------------------------------------------------------- checker, on a throw-away repo

@pytest.fixture()
def kit_repo(tmp_path):
    """A git repo built from the synthetic tracked files; returns (repo path, commit id)."""
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git not usable here")
    repo = tmp_path / "repo"
    shutil.copytree(FIXT, repo)
    # A Windows checkout with core.autocrlf=true holds the fixtures with CRLF endings; the
    # expected forms below ("crlf" for flood, "lf" for the irrigation source) assume LF files.
    for f in repo.rglob("*"):
        if f.is_file():
            f.write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))
    # The data files are written here, not stored: *.csv is gitignored in this repository.
    for rel in cm.DATA_FIELDS.values():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("year,value\n2020,1\n2021,2\n# " + Path(rel).stem + "\n", encoding="utf-8", newline="\n")
    env = {**os.environ, "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture", "GIT_COMMITTER_NAME": "fixture",
           "GIT_COMMITTER_EMAIL": "fixture"}

    def git(*a):
        return subprocess.run(["git", "-C", str(repo), "-c", "core.autocrlf=false", *a], capture_output=True, text=True,
                              env=env, timeout=60, check=True).stdout.strip()
    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "fixture")
    return repo, git("rev-parse", "HEAD")


OLD = "a" * 40


def _build_runs(tmp_path: Path, repo: Path, commit: str, *, bad_config=False, bad_data=False, bad_commit=False):
    """Fixture run folders + the three history tables. Returns paths for check_manifests.main."""
    root = tmp_path / "results"
    rows = []
    flood_cfg = (repo / "examples/single_agent/agent_types.yaml").read_bytes()
    irr_simple = (repo / "examples/irrigation_abm/config_variants/simple/agent_types.yaml").read_bytes()
    irr_nolimit = (repo / "examples/irrigation_abm/config_variants/simple_nolimit/agent_types.yaml").read_bytes()
    data = {f: (repo / rel).read_bytes() for f, rel in cm.DATA_FIELDS.items()}
    digest = "c" * 64
    runs = [
        # case, set, with digest, dirty
        ("flood", "disabled", True, True), ("flood", "silent", False, True),
        ("irrigation", "disabled", True, False), ("irrigation", "disabled_withlimit", False, False),
        ("irrigation", "strict", True, False),
    ]
    for case, set_, has_digest, dirty in runs:
        rel = f"{case}/{set_}/Run_42"
        folder = root / rel
        folder.mkdir(parents=True)
        base = FAKE_DRIVE + BS + "examples" + BS
        m = {"seed": 42, "git_commit": OLD if not bad_commit else "b" * 40, "git_commit_at_finalize": OLD,
             "git_dirty": dirty, "git_dirty_at_finalize": dirty, "python_version": "3.14.0"}
        if has_digest:
            m["model_digest"] = digest
        if case == "flood":
            m["agent_types_config"] = base + "single_agent" + BS + "agent_types.yaml"
            m["config_hash"] = _sha(_crlf(flood_cfg))[:12] if not bad_config else "0" * 12
            m["prompt_template_sha256"] = {"household": _sha((repo / "examples/single_agent/config/prompts/household.txt").read_bytes())}
            (folder / "config_snapshot.yaml").write_text("household:\n  prompt_template_file: config/prompts/household.txt\n", encoding="utf-8")
        else:
            cfg = irr_nolimit if set_ == "disabled" else irr_simple
            variant = "simple_nolimit" if set_ == "disabled" else "simple"
            variant_path = base + "irrigation_abm" + BS + "config_variants" + BS + variant + BS + "agent_types.yaml"
            if set_ == "disabled":
                resolved = cfg + b"# resolved copy\n"
                (folder / "resolved_agent_types.yaml").write_bytes(resolved)
                m["agent_types_config"] = FAKE_DRIVE + BS + "out" + BS + "resolved_agent_types.yaml"
                m["derived_from_config"] = variant_path
                m["derived_from_config_sha256"] = _sha(cfg)[:12]
                m["config_hash"] = _sha(resolved)[:12] if not bad_config else "0" * 12
            else:
                m["agent_types_config"] = variant_path
                m["config_hash"] = _sha(cfg)[:12] if not bad_config else "0" * 12
            (folder / "config_snapshot.yaml").write_text("global_config:\n  llm:\n    provider: ollama\n", encoding="utf-8")
            m.update({k: _sha(v) for k, v in data.items() if k.startswith("ub_")})
            m["coupling_retrofit_metadata"] = {k: _sha(v) for k, v in data.items() if k.startswith("water_")}
            if bad_data:
                m["ub_subbasin_supply_v3_sha256"] = "0" * 64
        (folder / "reproducibility_manifest.json").write_text(json.dumps(m), encoding="utf-8")
        (folder / "ollama_version.txt").write_text(
            "start fixture\nollama version is 0.0.1\ngpu check: fixture-model:1b    cccccccccccc    1 GB\n", encoding="utf-8")
        rows.append({"case": case, "set": set_, "seed": "42", "run_folder": rel, "git_commit": OLD,
                     "git_commit_at_finalize": OLD, "git_commit_short": OLD[:12], "git_dirty": str(dirty),
                     "git_dirty_at_finalize": str(dirty), "fields_naming_a_commit": ""})
    hist = tmp_path / "hist"
    hist.mkdir()
    with open(hist / "runs.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    with open(hist / "commits.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["role", "old_commit", "new_commit", "tag"])
        w.writerow(["flood_paper_runs", OLD, commit, "x"])
        w.writerow(["irrigation_paper_runs", OLD, commit, "y"])
    (hist / "map.txt").write_text(f"old new\n{OLD} {commit}\n", encoding="ascii")
    return ["--root", str(root), "--repo", str(repo), "--runs", str(hist / "runs.tsv"),
            "--commits", str(hist / "commits.tsv"), "--map", str(hist / "map.txt")]


def test_checker_on_fixtures_reports_the_expected_counts(tmp_path, kit_repo, capsys):
    repo, commit = kit_repo
    argv = _build_runs(tmp_path, repo, commit)
    rc = cm.main(argv + ["--expect-missing-digest", "2"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "runs listed 5, found 5, missing folders 0, unreadable manifests 0" in out
    assert "no problem found" in out
    assert "without a full model digest in the manifest: 2 (short id in ollama_version.txt: 2, none: 0)" in out
    assert "dirty at launch or finalize: 2  (flood 2, irrigation 0)" in out
    assert "config mismatches: 0, prompt mismatches: 0, data-hash mismatches: 0" in out
    assert "crlf" in out and "derived+lf" in out  # flood hashed a CRLF checkout; the derived copy's source is LF
    assert FAKE_DRIVE not in out  # no path from a manifest is echoed


def test_checker_fails_when_the_expected_digest_count_is_wrong(tmp_path, kit_repo, capsys):
    repo, commit = kit_repo
    assert cm.main(_build_runs(tmp_path, repo, commit) + ["--expect-missing-digest", "5"]) == 1
    assert "expected 5 runs without a digest, found 2" in capsys.readouterr().out


@pytest.mark.parametrize("kw,needle", [
    ({"bad_config": True}, "config_hash does not match"),
    ({"bad_data": True}, "ub_subbasin_supply_v3_sha256 does not match the tracked data file"),
    ({"bad_commit": True}, "commit not found in commit-map"),
])
def test_checker_fails_on_a_wrong_hash_or_commit(tmp_path, kit_repo, capsys, kw, needle):
    repo, commit = kit_repo
    rc = cm.main(_build_runs(tmp_path, repo, commit, **kw))
    out = capsys.readouterr().out
    assert rc == 1, out
    assert needle in out


def test_checker_fails_on_a_wrong_prompt_hash_and_on_a_missing_folder(tmp_path, kit_repo, capsys):
    repo, commit = kit_repo
    argv = _build_runs(tmp_path, repo, commit)
    root = Path(argv[1])
    mp = root / "flood/disabled/Run_42/reproducibility_manifest.json"
    d = json.loads(mp.read_text(encoding="utf-8"))
    d["prompt_template_sha256"] = {"household": "0" * 64}
    mp.write_text(json.dumps(d), encoding="utf-8")
    assert cm.main(argv) == 1
    assert "prompt_template_sha256 does not match" in capsys.readouterr().out
    shutil.rmtree(root / "irrigation/strict")
    assert cm.main(argv) == 1
    assert "run folder or manifest missing" in capsys.readouterr().out


def _manifest(folder: Path) -> dict:
    return json.loads((folder / "reproducibility_manifest.json").read_text(encoding="utf-8"))


def _save_manifest(folder: Path, m: dict) -> None:
    (folder / "reproducibility_manifest.json").write_text(json.dumps(m), encoding="utf-8")


def _mutate(root: Path, what: str) -> None:
    irr, flood = root / "irrigation/disabled/Run_42", root / "flood/disabled/Run_42"
    if what == "drop_resolved":
        (irr / "resolved_agent_types.yaml").unlink()
    elif what == "drop_config_hash":
        m = _manifest(flood)
        del m["config_hash"]
        _save_manifest(flood, m)
    elif what == "bad_snapshot":
        (flood / "config_snapshot.yaml").write_text("household: [unclosed\n", encoding="utf-8")
    elif what == "missing_prompt":
        (flood / "config_snapshot.yaml").write_text("household:\n  prompt_template_file: config/prompts/nope.txt\n", encoding="utf-8")
    elif what == "drop_data_field":
        m = _manifest(irr)
        del m["coupling_retrofit_metadata"]["water_system_hydrology_v3_sha256"]
        _save_manifest(irr, m)
    elif what == "corrupt_manifest":
        (flood / "reproducibility_manifest.json").write_text("{not json", encoding="utf-8")
    elif what == "short_hash":
        m = _manifest(flood)
        m["config_hash"] = m["config_hash"][:6]
        _save_manifest(flood, m)
    elif what == "wrong_seed":
        m = _manifest(flood)
        m["seed"] = 7
        _save_manifest(flood, m)
    elif what == "short_digest":
        m = _manifest(flood)
        m["model_digest"] = m["model_digest"][:12]  # only the short id, not the 64-hex digest
        _save_manifest(flood, m)
    elif what == "drop_snapshot_no_prompt_hash":
        (irr / "config_snapshot.yaml").unlink()  # irrigation manifests carry no prompt hash
    elif what == "bad_snapshot_no_prompt_hash":
        (irr / "config_snapshot.yaml").write_text("global_config: [unclosed\n", encoding="utf-8")


@pytest.mark.parametrize("what,needle", [
    ("drop_resolved", "resolved_agent_types.yaml absent from the run folder"),
    ("drop_config_hash", "config_hash absent from the manifest"),
    ("bad_snapshot", "config_snapshot.yaml does not parse"),
    ("missing_prompt", "a prompt file named in config_snapshot.yaml is not tracked at the new commit"),
    ("drop_data_field", "water_system_hydrology_v3_sha256 absent from the manifest"),
    ("corrupt_manifest", "manifest does not parse as a JSON object"),
    ("short_hash", "config_hash does not match the tracked config file"),
    ("wrong_seed", "seed in the manifest differs from paper_manifest_commits.tsv"),
    ("short_digest", "model_digest is not a 64-character hex digest"),
    ("drop_snapshot_no_prompt_hash", "config_snapshot.yaml absent from the run folder"),
    ("bad_snapshot_no_prompt_hash", "config_snapshot.yaml does not parse"),
])
def test_checker_counts_missing_or_unparsed_data_as_a_problem(tmp_path, kit_repo, capsys, what, needle):
    repo, commit = kit_repo
    argv = _build_runs(tmp_path, repo, commit)
    _mutate(Path(argv[1]), what)
    rc = cm.main(argv)
    out = capsys.readouterr().out
    assert rc == 1, out
    assert needle in out
    assert "no problem found" not in out


def test_checker_exits_2_when_the_root_holds_no_run(tmp_path, kit_repo):
    repo, commit = kit_repo
    argv = _build_runs(tmp_path, repo, commit)
    argv[1] = str(tmp_path / "empty")
    (tmp_path / "empty").mkdir()
    assert cm.main(argv) == 2


# ---------------------------------------------------------------- share check, on generated folders

def _run_folder(tmp_path: Path, name: str = "Run_1") -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / "reproducibility_manifest.json").write_text(json.dumps({"seed": 1, "model": "m"}), encoding="utf-8")
    (d / "config_snapshot.yaml").write_text("global_config:\n  llm:\n    provider: ollama\n    api_key: ${PROVIDER_KEY}\n", encoding="utf-8")
    (d / "simulation_log.csv").write_text("year,agent\n1,A\n", encoding="utf-8")
    return d


def test_share_check_passes_a_clean_folder(tmp_path, capsys):
    d = _run_folder(tmp_path)
    assert cs.main([str(d)]) == 0
    assert "0 finding(s)" in capsys.readouterr().out


def test_share_check_catches_a_drive_letter_a_user_folder_and_a_key_without_printing_them(tmp_path, capsys):
    planted_drive = "Z" + ":" + BS + "somewhere"
    planted_user = BS + "Users" + BS + "somebody"
    planted_key = "sk-" + "FIXTURE" * 5
    d = _run_folder(tmp_path)
    (d / "reproducibility_manifest.json").write_text(
        json.dumps({"agent_types_config": planted_drive + planted_user}), encoding="utf-8")
    (d / "config_snapshot.yaml").write_text(f"global_config:\n  llm:\n    api_key: {planted_key}\n", encoding="utf-8")
    (d / "simulation_log.csv").write_text("year,note\n1," + "/" + "home" + "/somebody/x\n", encoding="utf-8")
    assert cs.main([str(d)]) == 1
    out = capsys.readouterr().out
    assert "reproducibility_manifest.json: drive_letter x1 in field agent_types_config" in out
    assert "reproducibility_manifest.json: user_folder x1 in field agent_types_config" in out
    assert "config_snapshot.yaml: literal_key x1 in field global_config.llm.api_key" in out
    assert "simulation_log.csv: user_folder x1" in out
    for secret in (planted_drive, planted_user, planted_key, "somebody", "somewhere", "FIXTURE"):
        assert secret not in out


def test_share_check_flags_a_literal_value_under_a_key_name_but_not_an_environment_reference(tmp_path, capsys):
    d = _run_folder(tmp_path)
    (d / "config_snapshot.yaml").write_text("llm:\n  api_key: not-a-real-key-shape\n", encoding="utf-8")
    assert cs.main([str(d)]) == 1
    assert "literal_key x1 in field llm.api_key" in capsys.readouterr().out
    (d / "config_snapshot.yaml").write_text("llm:\n  api_key: ${SOME_ENV}\n  max_tokens: 100\n", encoding="utf-8")
    assert cs.main([str(d)]) == 0


def test_share_check_flags_files_off_the_allowlist_and_an_email(tmp_path, capsys):
    d = _run_folder(tmp_path)
    (d / "run.log").write_text("fine\n", encoding="utf-8")
    assert cs.main([str(d)]) == 1
    assert "run.log: not_allowed x1" in capsys.readouterr().out
    assert cs.main(["--scan-only", str(d)]) == 0
    (d / "run.log").write_text("contact " + "someone" + "@" + "example.invalid\n", encoding="utf-8")
    assert cs.main(["--scan-only", str(d)]) == 1
    out = capsys.readouterr().out
    assert "run.log: email x1" in out and "someone" not in out


def test_share_stage_blanks_paths_keeps_the_repo_relative_tail_and_leaves_a_clean_copy(tmp_path, capsys):
    d = _run_folder(tmp_path)
    cfg = FAKE_DRIVE + BS + "wt" + BS + "examples" + BS + "single_agent" + BS + "agent_types.yaml"
    (d / "reproducibility_manifest.json").write_text(json.dumps({"agent_types_config": cfg, "python": FAKE_DRIVE + BS + "py.exe"}), encoding="utf-8")
    (d / "launch_command.txt").write_text(f"cwd: {FAKE_DRIVE}{BS}wt\n{FAKE_DRIVE}{BS}py.exe run.py --seed 1\n", encoding="utf-8")
    (d / "run.log").write_text("log\n", encoding="utf-8")
    out_dir = tmp_path / "staged"
    assert cs.main(["--stage", str(out_dir), str(d)]) == 0
    staged = out_dir / d.name
    assert not (staged / "run.log").exists()  # not allowlisted: not copied
    m = json.loads((staged / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    assert m["agent_types_config"] == "examples/single_agent/agent_types.yaml"
    assert m["python"] == "<path removed>"
    assert "--seed 1" in (staged / "launch_command.txt").read_text(encoding="utf-8")


def _make_dir_link(link: Path, target: Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass
    if os.name == "nt":
        try:
            import _winapi

            _winapi.CreateJunction(str(target), str(link))
            return
        except (ImportError, AttributeError, OSError):
            pass
    pytest.skip("cannot make a directory link here")


def test_share_check_and_stage_never_follow_a_link_out_of_the_folder(tmp_path, capsys):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leak_governance_audit.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    d = _run_folder(tmp_path)
    _make_dir_link(d / "sub", outside)
    assert cs.main([str(d)]) == 1
    out = capsys.readouterr().out
    assert "  sub: link x1" in out and "leak_governance_audit" not in out
    dest = tmp_path / "staged"
    assert cs.main(["--stage", str(dest), str(d)]) == 1
    assert "  sub: link x1" in capsys.readouterr().out
    assert not (dest / d.name / "sub").exists()
    assert (dest / d.name / "reproducibility_manifest.json").is_file()


def test_share_allowlist_matches_the_top_of_the_run_folder_only_and_case_sensitively(tmp_path, capsys):
    pats = cs.load_allowlist(KIT / "share_allowlist.txt")
    assert cs.is_allowed("household_governance_audit.csv", pats)
    assert not cs.is_allowed("sub/household_governance_audit.csv", pats)
    assert not cs.is_allowed("REPRODUCIBILITY_MANIFEST.JSON", pats)
    d = _run_folder(tmp_path)
    (d / "sub").mkdir()
    (d / "sub" / "x_governance_audit.csv").write_text("a\n1\n", encoding="utf-8")
    assert cs.main([str(d)]) == 1
    assert "sub/x_governance_audit.csv: not_allowed x1" in capsys.readouterr().out


def test_stage_refuses_to_overwrite_or_overlap_a_run_folder(tmp_path, capsys):
    d = _run_folder(tmp_path)
    (d / "reproducibility_manifest.json").write_text(json.dumps({"python": FAKE_DRIVE + BS + "py.exe"}), encoding="utf-8")
    before = {f.name: f.read_bytes() for f in d.iterdir()}
    assert cs.main(["--stage", str(tmp_path), str(d)]) == 2       # the destination holds the run folder
    assert cs.main(["--stage", str(d / "out"), str(d)]) == 2      # the target would sit inside it
    assert {f.name: f.read_bytes() for f in d.iterdir()} == before
    dest = tmp_path / "staged"
    assert cs.main(["--stage", str(dest), str(d)]) == 0
    assert cs.main(["--stage", str(dest), str(d)]) == 2           # the target exists now
    assert "nothing was copied" in capsys.readouterr().err


def test_stage_names_same_named_run_folders_apart(tmp_path, capsys):
    results = tmp_path / "results"
    srcs = []
    for set_ in ("disabled", "silent", "strict"):
        (results / f"JOH_{set_}").mkdir(parents=True)
        srcs.append(_run_folder(results / f"JOH_{set_}", "Run_42"))
    want = ["JOH_disabled__Run_42", "JOH_silent__Run_42", "JOH_strict__Run_42"]
    assert cs.main(["--stage", str(tmp_path / "s1"), *map(str, srcs)]) == 0
    assert sorted(x.name for x in (tmp_path / "s1").iterdir()) == want
    assert cs.main(["--stage", str(tmp_path / "s2"), str(results)]) == 0  # found by walking the parent
    assert sorted(x.name for x in (tmp_path / "s2").iterdir()) == want


def test_share_check_reports_a_file_that_does_not_parse(tmp_path, capsys):
    d = _run_folder(tmp_path)
    (d / "config_snapshot.yaml").write_text("llm:\n  api_key: plainliteralvalue\n  hook: !!python/name:os.system\n",
                                            encoding="utf-8")
    assert cs.main([str(d)]) == 1
    out = capsys.readouterr().out
    assert "config_snapshot.yaml: parse_error x1" in out and "plainliteral" not in out
    (d / "config_snapshot.yaml").write_text("seed: 1\n", encoding="utf-8")
    (d / "reproducibility_manifest.json").write_text("{not json", encoding="utf-8")
    assert cs.main([str(d)]) == 1
    assert "reproducibility_manifest.json: parse_error x1" in capsys.readouterr().out


def test_share_check_reads_utf16_and_reports_binary_files_as_not_scanned(tmp_path, capsys):
    d = _run_folder(tmp_path)
    planted = FAKE_DRIVE + BS + "Users" + BS + "somebody" + BS + "x"
    (d / "simulation_log.csv").write_bytes(("year,note\n1," + planted + "\n").encode("utf-16"))
    assert cs.main([str(d)]) == 1
    out = capsys.readouterr().out
    assert "simulation_log.csv: drive_letter x1" in out and "simulation_log.csv: user_folder x1" in out
    dest = tmp_path / "staged"
    assert cs.main(["--stage", str(dest), str(d)]) == 0
    staged = (dest / d.name / "simulation_log.csv").read_bytes()
    assert staged.startswith((b"\xff\xfe", b"\xfe\xff"))
    assert "somebody" not in staged.decode("utf-16") and "<path removed>" in staged.decode("utf-16")
    (d / "cache.pkl").write_bytes(b"\x80\x04" + planted.encode("utf-8"))
    (d / "blob.bin").write_bytes(bytes(range(256)) * 4)
    assert cs.main(["--scan-only", str(d)]) == 1
    out = capsys.readouterr().out
    assert "cache.pkl: not_scanned x1" in out and "blob.bin: not_scanned x1" in out


@pytest.mark.parametrize("planted,cat", [
    (BS * 2 + "fileserver" + BS + "share" + BS + "somebody", "unc_path"),
    (BS + "home" + BS + "somebody" + BS + "x", "user_folder"),
    (BS + "users" + BS + "somebody" + BS + "x", "user_folder"),
    ("~/" + "somebody", "user_folder"),
    ("~" + BS + "somebody", "user_folder"),
    ("Q%3A%5C" + "somebody", "encoded_path"),
    ("%2F" + "Users%2F" + "somebody", "encoded_path"),
])
def test_share_check_finds_and_stage_blanks_other_path_forms(tmp_path, capsys, planted, cat):
    d = _run_folder(tmp_path)
    (d / "simulation_log.csv").write_text("year,note\n1," + planted + " end\n", encoding="utf-8")
    assert cs.main([str(d)]) == 1
    out = capsys.readouterr().out
    assert f"simulation_log.csv: {cat} x1" in out and "somebody" not in out
    dest = tmp_path / "staged"
    assert cs.main(["--stage", str(dest), str(d)]) == 0, capsys.readouterr().out
    text = (dest / d.name / "simulation_log.csv").read_text(encoding="utf-8")
    assert "somebody" not in text and " end" in text


def test_share_check_leaves_relative_paths_in_json_alone(tmp_path, capsys):
    d = _run_folder(tmp_path)
    rel = "config" + BS + "prompts" + BS + "household.txt"
    (d / "reproducibility_manifest.json").write_text(json.dumps({"prompt": rel, "glob": "a" + BS + "w" + BS + "s"}),
                                                     encoding="utf-8")
    assert cs.main([str(d)]) == 0, capsys.readouterr().out


def test_stage_blanks_a_user_folder_name_with_a_space(tmp_path):
    d = _run_folder(tmp_path)
    users = FAKE_DRIVE + BS + "Users" + BS + "First Last"
    (d / "launch_command.txt").write_text(
        "cwd: " + users + "\n" + users + BS + "My Project" + BS + "run.py --seed 1\n", encoding="utf-8")
    dest = tmp_path / "staged"
    assert cs.main(["--stage", str(dest), str(d)]) == 0
    text = (dest / d.name / "launch_command.txt").read_text(encoding="utf-8")
    for word in ("First", "Last", "Project", "fixture"):
        assert word not in text
    assert "--seed 1" in text


@pytest.mark.parametrize("value", ["hf_" + "A" * 34, "github_pat_" + "A" * 30, "AKIA" + "A" * 16,
                                   "gsk_" + "A" * 30, "xoxb-" + "1" * 12])
def test_share_check_finds_more_key_shapes(tmp_path, capsys, value):
    d = _run_folder(tmp_path)
    (d / "simulation_log.csv").write_text("year,note\n1," + value + "\n", encoding="utf-8")
    assert cs.main([str(d)]) == 1
    out = capsys.readouterr().out
    assert "simulation_log.csv: literal_key x1" in out and value not in out


def test_share_check_flags_key_named_fields_and_keeps_similar_names_apart(tmp_path, capsys):
    d = _run_folder(tmp_path)
    shaped = "sk-" + "FIXTURE" * 5
    (d / "config_snapshot.yaml").write_text(
        "llm:\n  api_key_2: " + shaped + "\n  api_key: plainliteral\n  hf_token: " + "abcdEFGH" + "1234" * 3 + "\n"
        "  private_key: abc\n  credential: abc\n  password: 123456\n  max_tokens: 100\n  token_limit: 5\n"
        "  provider: ollama\n  recall_skip_key: skip\n  fields:\n    - key: decision\n", encoding="utf-8")
    assert cs.main([str(d)]) == 1
    lines = capsys.readouterr().out.splitlines()
    for f in ("api_key_2", "api_key", "hf_token", "private_key", "credential", "password"):
        assert f"  config_snapshot.yaml: literal_key x1 in field llm.{f}" in lines, f
    for n in ("max_tokens", "token_limit", "provider", "recall_skip_key", "fields[].key"):
        assert not any(n in line for line in lines), n


def test_share_check_hides_a_field_name_that_looks_like_a_path(tmp_path, capsys):
    d = _run_folder(tmp_path)
    key = FAKE_DRIVE + BS + "Users" + BS + "somebody"
    (d / "reproducibility_manifest.json").write_text(json.dumps({key: key}), encoding="utf-8")
    assert cs.main([str(d)]) == 1
    out = capsys.readouterr().out
    assert "in field <field name hidden>" in out
    assert "somebody" not in out and "fixture" not in out


@pytest.mark.parametrize("encoding", ["utf-32", "utf-32-le", "utf-32-be"])
def test_share_check_fails_closed_on_utf32(tmp_path, capsys, encoding):
    """UTF-32 is not decoded: the file must be reported, never passed as clean."""
    d = _run_folder(tmp_path)
    planted = FAKE_DRIVE + BS + "Users" + BS + "somebody" + BS + "x"
    (d / "simulation_log.csv").write_bytes(("year,note\n1," + planted + "\n").encode(encoding))
    assert cs.main([str(d)]) == 1
    assert "simulation_log.csv: not_scanned x1" in capsys.readouterr().out
    assert cs.main(["--stage", str(tmp_path / "staged"), str(d)]) == 1  # the copy fails the check too


def test_share_check_reports_a_path_written_as_json_escapes(tmp_path, capsys):
    d = _run_folder(tmp_path)
    planted = FAKE_DRIVE + BS + "Users" + BS + "somebody" + BS + "x"
    escaped = "".join(f"\\u{ord(c):04x}" for c in planted)
    (d / "reproducibility_manifest.json").write_text('{"python": "' + escaped + '"}', encoding="utf-8")
    assert cs.main([str(d)]) == 1
    out = capsys.readouterr().out
    assert "reproducibility_manifest.json: drive_letter x1 in field python" in out
    assert cs.main(["--stage", str(tmp_path / "staged"), str(d)]) == 1  # not blanked in the copy, so the copy fails


@pytest.mark.parametrize("tail,hidden", [
    (BS + "Users" + BS + "First O'Last" + BS + "x", ("First", "Last")),
    (BS + "Users" + BS + "somebody" + BS + "OneDrive - Some Org" + BS + "Desktop" + BS + "x", ("somebody", "Some", "Org")),
])
def test_stage_blanks_an_apostrophe_name_and_a_work_onedrive_folder(tmp_path, tail, hidden):
    d = _run_folder(tmp_path)
    (d / "launch_command.txt").write_text("cwd: " + FAKE_DRIVE + tail + "\n" + FAKE_DRIVE + tail + " --seed 1\n",
                                          encoding="utf-8")
    dest = tmp_path / "staged"
    assert cs.main(["--stage", str(dest), str(d)]) == 0
    text = (dest / d.name / "launch_command.txt").read_text(encoding="utf-8")
    for word in hidden:
        assert word not in text, word
    assert "--seed 1" in text


def test_stage_names_differ_without_letter_case(tmp_path):
    srcs = []
    for parent, name in (("x", "Run_42"), ("y", "run_42")):
        (tmp_path / parent).mkdir()
        srcs.append(_run_folder(tmp_path / parent, name))
    dest = tmp_path / "staged"
    assert cs.main(["--stage", str(dest), *map(str, srcs)]) == 0
    assert len(list(dest.iterdir())) == 2


def test_unique_names_never_hold_a_drive_or_root():
    names = cs.unique_names([("C:" + BS, "x", "Run_1"), ("D:" + BS, "x", "Run_1"), ("/", "y", "Run_1")])
    assert len({n.casefold() for n in names}) == 3
    assert not any(":" in n or BS in n or "/" in n for n in names)


def test_checker_fails_on_a_missing_digest_unless_the_count_is_given(tmp_path, kit_repo, capsys):
    repo, commit = kit_repo
    argv = _build_runs(tmp_path, repo, commit)
    assert cm.main(argv) == 1
    assert "2 run(s) without the full model digest" in capsys.readouterr().out
    assert cm.main(argv + ["--expect-missing-digest", "2"]) == 0


def test_share_allowlist_leaves_out_the_files_that_hold_paths_and_raw_traces():
    pats = cs.load_allowlist(KIT / "share_allowlist.txt")
    for rel in ("reproducibility_manifest.json", "config_snapshot.yaml", "launch_command.txt", "household_governance_audit.csv"):
        assert cs.is_allowed(rel, pats), rel
    for rel in ("run.log", "llm_journal.jsonl", "run_metadata.json", "raw/household_traces.jsonl", "adaptation_cumulative_state.png"):
        assert not cs.is_allowed(rel, pats), rel


# ---------------------------------------------------------------- real run folders (not in git)

def _real_root_and_rows():
    root = Path(os.environ.get("WAGF_RESULTS_ROOT") or ROOT)
    rows = _tsv("paper_manifest_commits.tsv")
    present = [r for r in rows if (root / r["run_folder"] / "reproducibility_manifest.json").is_file()]
    if not present:
        pytest.skip(f"no paper run folders under {root}; set WAGF_RESULTS_ROOT to check them")
    missing = [r["run_folder"] for r in rows if r not in present]
    assert not missing, f"{len(missing)} of 30 run folders missing under {root}: {missing}"
    return root, rows


def test_real_irrigation_launch_commands_match_the_recipe():
    root, rows = _real_root_and_rows()
    r = _recipe("irrigation")
    arms = {a["set"]: a for a in r["arms"]}
    n = 0
    for row in rows:
        if row["case"] != "irrigation":
            continue
        text = (root / row["run_folder"] / "launch_command.txt").read_text(encoding="utf-8")
        got = normalise_launch(text)
        want = expand_argv(r, arms[row["set"]], int(row["seed"]))
        assert _compare_argv(want, got), f"irrigation {row['set']} seed {row['seed']}"
        n += 1
    assert n == 15


def test_real_flood_manifests_match_the_recipe():
    root, rows = _real_root_and_rows()
    r = _recipe("flood")
    arms = {a["set"]: a for a in r["arms"]}
    n = 0
    for row in rows:
        if row["case"] != "flood":
            continue
        folder = root / row["run_folder"]
        m = json.loads((folder / "reproducibility_manifest.json").read_text(encoding="utf-8-sig"))
        snap = yaml.safe_load((folder / "config_snapshot.yaml").read_text(encoding="utf-8"))
        where = f"flood {row['set']} seed {row['seed']}"
        for k, v in r["manifest_common"].items():
            assert m.get(k) == v, f"{where}: {k}"
        exp = arms[row["set"]]["manifest_expect"]
        assert m["governance_profile"] == exp["governance_profile"], where
        assert m["retry_feedback_mode"] == exp["retry_feedback_mode"], where
        assert snap["metadata"]["retry_feedback_mode"] == exp["retry_feedback_mode"], where
        assert m["seed"] == int(row["seed"]) and m["run_integrity"]["audit_agents"] == 100, where
        assert m["git_dirty"] is True, where
        n += 1
    assert n == 15


def test_real_fql_reference_manifests_match_the_recipe():
    root, _ = _real_root_and_rows()
    ref = _recipe("irrigation")["reference"]
    for seed in ref["seeds"]:
        p = root / ref["folder_pattern"].format(seed=seed) / "reproducibility_manifest.json"
        assert p.is_file(), f"FQL reference seed {seed} missing"
        m = json.loads(p.read_text(encoding="utf-8-sig"))
        assert m["seed"] == seed
        assert m["git_head"] == _recipe("irrigation")["commits"]["reference"]["old"]
        for k, v in ref["manifest_expect"].items():
            assert m.get(k) == v, (seed, k)
        assert m["paper_water_margin"] == 0.4 and m["cluster_method"] == "hy2021" and m["fql_init"] == "calibrated"


def test_real_manifests_pass_the_checker_with_five_runs_without_a_digest(capsys):
    root, _ = _real_root_and_rows()
    rc = cm.main(["--root", str(root), "--expect-missing-digest", "5"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "without a full model digest in the manifest: 5" in out


def test_real_run_folders_pass_the_share_check_after_staging(tmp_path, capsys):
    """One folder per set of simulations (6 of 30) to keep the test fast; scan_only covers raw traces."""
    root, rows = _real_root_and_rows()
    pick = {}
    for row in rows:
        pick.setdefault((row["case"], row["set"]), root / row["run_folder"])
    assert cs.main(["--stage", str(tmp_path / "staged"), *map(str, pick.values())]) == 0, capsys.readouterr().out
    assert len(list((tmp_path / "staged").iterdir())) == 6  # one target per run folder, none overwritten
