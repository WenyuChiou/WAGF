"""Integration tests: crash-resume for the irrigation v3 real-data pipeline
(broker/utils/llm_journal.py, examples/irrigation_abm/run_experiment.py).

Drives the REAL CLI entry point (examples.irrigation_abm.run_experiment.main)
as a subprocess, through fixtures/journal_resume_driver.py, which replaces
the stock mock with a deterministic (or os.urandom-seeded random) test mock
and can simulate a hard crash (os._exit) partway through a chosen year --
see that file's own docstring for exactly what it does and why.

Scope: --real (78 CRSS agents), a handful of years, strict governance,
workers=1. workers>1 crash-resume interaction is explicitly out of scope:
ExperimentRunner._run_agents_parallel is owned by another branch and was
not touched by this feature (see that method's own JournalReplayDivergence
handling gap, noted in this feature's delivery report).

Never contacts Ollama or any live model: --model mock, and the driver's
own test invoke never makes a network call.
"""
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from broker.tools.compare_audit_csv import compare as compare_audit_csv
from broker.utils.llm_journal import load_journal_for_resume

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DRIVER = Path(__file__).resolve().parent / "fixtures" / "journal_resume_driver.py"
_YEARS = 5
_CRASH_AT_STEP = 3
_CRASH_AFTER_CALLS = 20

_VOLATILE_KEYS = {
    "timestamp", "git_commit", "git_dirty",
    "git_commit_at_finalize", "git_dirty_at_finalize", "finalized_at",
}


def _strip_volatile(obj):
    if isinstance(obj, dict):
        return {
            k: _strip_volatile(v) for k, v in obj.items()
            if k not in _VOLATILE_KEYS and "timestamp" not in k.lower()
        }
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


def _assert_json_matches(path_a: Path, path_b: Path):
    a = _strip_volatile(json.loads(path_a.read_text(encoding="utf-8")))
    b = _strip_volatile(json.loads(path_b.read_text(encoding="utf-8")))
    assert a == b, f"{path_a} vs {path_b} differ (volatile keys excluded)"


def _assert_csv_matches(path_a: Path, path_b: Path):
    with open(path_a, encoding="utf-8-sig") as fa, open(path_b, encoding="utf-8-sig") as fb:
        rows_a = list(csv.reader(fa))
        rows_b = list(csv.reader(fb))
    assert rows_a == rows_b, f"{path_a} vs {path_b} differ"


def _run(output_dir: Path, *, resume_from=None, llm_journal=True,
         crash_at_step=0, mock_mode="hash", extra_env=None, seed=42,
         years=_YEARS, config_dir=None):
    args = [
        sys.executable, str(_DRIVER),
        "--model", "mock", "--real", "--years", str(years),
        "--governance-mode", "strict", "--workers", "1",
        "--seed", str(seed), "--memory-seed", str(seed),
        "--output", str(output_dir),
    ]
    if llm_journal:
        args.append("--llm-journal")
    if resume_from is not None:
        args += ["--resume-from", str(resume_from)]
    if config_dir is not None:
        args += ["--config-dir", str(config_dir)]
    env = dict(os.environ)
    env["WAGF_TEST_MOCK_MODE"] = mock_mode
    env["WAGF_TEST_CRASH_AT_STEP"] = str(crash_at_step)
    env["WAGF_TEST_CRASH_AFTER_CALLS_IN_STEP"] = str(_CRASH_AFTER_CALLS)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        args, cwd=str(_REPO_ROOT), env=env,
        capture_output=True, text=True, timeout=300,
    )


def _load_manifest(output_dir: Path) -> dict:
    return json.loads((output_dir / "reproducibility_manifest.json").read_text(encoding="utf-8"))


def _make_isolated_config_dir(dest: Path) -> Path:
    """A complete, isolated copy of examples/irrigation_abm/config/, the
    sanctioned --config-dir mechanism for a test that needs to edit a
    config file without ever touching the frozen in-tree copy."""
    src = _REPO_ROOT / "examples" / "irrigation_abm" / "config"
    shutil.copytree(src, dest)
    return dest


def _overwrite_header_field(journal_path: Path, key: str, value) -> None:
    """Rewrite a source journal's header record with one field changed --
    used to test the resume refusal's COMPARISON logic (a mismatched
    git_commit / git_diff_sha256) without needing an actual different git
    commit or a mutated worktree, neither of which a test may do here."""
    lines = journal_path.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    header[key] = value
    lines[0] = json.dumps(header)
    journal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_item49_off_derived_config_resumes_with_source_config_hash(tmp_path):
    """Derived item-49 wiring must preserve its own journal's resume identity."""
    import yaml

    config_dir = _make_isolated_config_dir(tmp_path / "config")
    config_path = config_dir / "agent_types.yaml"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["irrigation_farmer"]["beneficial_use_limit"]["enabled"] = False
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    crashed = tmp_path / "crashed"
    result = _run(crashed, years=2, crash_at_step=2, config_dir=config_dir)
    assert result.returncode != 0
    assert (crashed / "resolved_agent_types.yaml").is_file()
    journal = crashed / "llm_journal.jsonl"
    assert journal.is_file(), result.stdout[-4000:] + result.stderr[-4000:]
    resumed = _run(tmp_path / "resumed", years=2, resume_from=journal, config_dir=config_dir)
    assert resumed.returncode == 0, resumed.stdout[-4000:] + resumed.stderr[-4000:]


class TestCrashResumeDeterministicMock:
    """Run A completes uninterrupted; run B crashes mid-year-3 and is
    resumed into a fresh directory. A and resumed-B must be byte-identical
    (modulo documented volatile fields: wall-clock timestamps and git-dirty
    state, which the resume itself legitimately changes)."""

    @pytest.fixture(scope="class")
    def run_a(self, tmp_path_factory):
        out = tmp_path_factory.mktemp("run_a")
        result = _run(out, llm_journal=True, crash_at_step=0)
        assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
        return out

    @pytest.fixture(scope="class")
    def resumed_b(self, tmp_path_factory):
        crashed = tmp_path_factory.mktemp("run_b_crashed")
        crash_result = _run(crashed, llm_journal=True, crash_at_step=_CRASH_AT_STEP)
        assert crash_result.returncode != 0, (
            "the simulated crash did not happen -- adjust _CRASH_AFTER_CALLS"
        )

        resumed = tmp_path_factory.mktemp("run_b_resumed")
        resume_result = _run(
            resumed, resume_from=crashed / "llm_journal.jsonl",
            llm_journal=True, crash_at_step=0,
        )
        assert resume_result.returncode == 0, (
            resume_result.stdout[-4000:] + resume_result.stderr[-4000:]
        )
        return resumed

    def test_simulation_log_byte_identical(self, run_a, resumed_b):
        _assert_csv_matches(run_a / "simulation_log.csv", resumed_b / "simulation_log.csv")

    def test_validator_health_byte_identical(self, run_a, resumed_b):
        _assert_csv_matches(run_a / "validator_health.csv", resumed_b / "validator_health.csv")
        _assert_csv_matches(
            run_a / "validator_health_by_agent_type.csv",
            resumed_b / "validator_health_by_agent_type.csv",
        )

    def test_governance_audit_csv_matches_normalised(self, run_a, resumed_b):
        rc = compare_audit_csv(
            run_a / "irrigation_farmer_governance_audit.csv",
            resumed_b / "irrigation_farmer_governance_audit.csv",
        )
        assert rc == 0

    def test_governance_summary_matches(self, run_a, resumed_b):
        _assert_json_matches(
            run_a / "governance_summary.json", resumed_b / "governance_summary.json",
        )

    def test_run_integrity_matches(self, run_a, resumed_b):
        _assert_json_matches(run_a / "run_integrity.json", resumed_b / "run_integrity.json")

    def test_resumed_manifest_has_journal_provenance(self, resumed_b):
        manifest = _load_manifest(resumed_b)
        assert manifest["replayed_steps"] == _CRASH_AT_STEP - 1
        assert manifest["replayed_calls"] > 0
        assert manifest["source_journal_sha256"]

    def test_resumed_run_can_itself_be_resumed(self, run_a, tmp_path_factory):
        """A REAL second CLI resume: B crashes in year _CRASH_AT_STEP, is
        resumed into B2, which ITSELF crashes one year later
        (_CRASH_AT_STEP + 1) -- exercising B2's own header (which already
        carries resume_provenance from resuming B) as the identifying-
        config source for a THIRD run. B3 (resumed from B2) must match A.
        """
        b_crashed = tmp_path_factory.mktemp("run_b2_crashed")
        r1 = _run(b_crashed, llm_journal=True, crash_at_step=_CRASH_AT_STEP)
        assert r1.returncode != 0, "the first simulated crash did not happen"

        b2_crashed = tmp_path_factory.mktemp("run_b2_resumed_crashed")
        r2 = _run(
            b2_crashed, resume_from=b_crashed / "llm_journal.jsonl",
            llm_journal=True, crash_at_step=_CRASH_AT_STEP + 1,
        )
        assert r2.returncode != 0, "the second simulated crash did not happen"
        # Confirms B2 actually ran live past the replay boundary (year 3)
        # before crashing in year 4 -- otherwise this would not be
        # exercising a SECOND resume's own identifying-config comparison
        # against a header that itself carries resume_provenance.
        loaded_b2 = load_journal_for_resume(b2_crashed / "llm_journal.jsonl")
        assert loaded_b2.last_complete_step == _CRASH_AT_STEP

        b3_resumed = tmp_path_factory.mktemp("run_b3_resumed")
        r3 = _run(
            b3_resumed, resume_from=b2_crashed / "llm_journal.jsonl",
            llm_journal=True, crash_at_step=0,
        )
        assert r3.returncode == 0, r3.stdout[-4000:] + r3.stderr[-4000:]

        _assert_csv_matches(run_a / "simulation_log.csv", b3_resumed / "simulation_log.csv")
        rc = compare_audit_csv(
            run_a / "irrigation_farmer_governance_audit.csv",
            b3_resumed / "irrigation_farmer_governance_audit.csv",
        )
        assert rc == 0
        manifest = _load_manifest(b3_resumed)
        assert manifest["replayed_steps"] == _CRASH_AT_STEP

        loaded_b3 = load_journal_for_resume(b3_resumed / "llm_journal.jsonl")
        assert loaded_b3.last_complete_step == _YEARS


class TestCrashResumeRandomMock:
    """Replay must not depend on the mock being deterministic: resuming a
    run whose mock was seeded from os.urandom reproduces that SAME run's
    own recorded answers for the replayed years, never a fresh (and, for a
    random mock, almost certainly different) live call.
    """

    def test_resumed_replay_matches_the_crashed_runs_own_journal(self, tmp_path):
        crashed = tmp_path / "crashed"
        crash_result = _run(
            crashed, llm_journal=True, crash_at_step=_CRASH_AT_STEP, mock_mode="random",
        )
        assert crash_result.returncode != 0, "the simulated crash did not happen"

        resumed = tmp_path / "resumed"
        resume_result = _run(
            resumed, resume_from=crashed / "llm_journal.jsonl",
            llm_journal=True, crash_at_step=0, mock_mode="random",
        )
        assert resume_result.returncode == 0, (
            resume_result.stdout[-4000:] + resume_result.stderr[-4000:]
        )

        crashed_loaded = load_journal_for_resume(crashed / "llm_journal.jsonl")
        resumed_loaded = load_journal_for_resume(resumed / "llm_journal.jsonl")
        k = crashed_loaded.last_complete_step
        assert k == _CRASH_AT_STEP - 1

        for step in range(1, k + 1):
            crashed_keys = sorted(crashed_loaded.pools.get(step, {}).keys())
            resumed_keys = sorted(resumed_loaded.pools.get(step, {}).keys())
            assert crashed_keys == resumed_keys
            for key in crashed_keys:
                assert (
                    list(crashed_loaded.pools[step][key])
                    == list(resumed_loaded.pools[step][key])
                )


class TestCrossProcessHashSeed:
    """Resume in a subprocess with a DIFFERENT PYTHONHASHSEED from the one
    the original (crashed) run used. If the rebuilt prompt stream diverges
    (e.g. a hash-seed-dependent set iteration order embedded in a prompt),
    this must surface as a clear, named failure -- never a silently
    accepted different corpus.
    """

    def test_resume_under_a_different_hashseed(self, tmp_path):
        crashed = tmp_path / "crashed"
        crash_result = _run(
            crashed, llm_journal=True, crash_at_step=_CRASH_AT_STEP,
            extra_env={"PYTHONHASHSEED": "111"},
        )
        assert crash_result.returncode != 0, "the simulated crash did not happen"

        resumed = tmp_path / "resumed"
        resume_result = _run(
            resumed, resume_from=crashed / "llm_journal.jsonl",
            llm_journal=True, crash_at_step=0,
            extra_env={"PYTHONHASHSEED": "222"},
        )
        if resume_result.returncode != 0:
            pytest.fail(
                "Resume under a different PYTHONHASHSEED diverged from the "
                "source run -- this is a real finding about which "
                "component is not process-hash-independent, not a flaky "
                "test. stderr:\n" + resume_result.stderr[-4000:]
            )
        manifest = _load_manifest(resumed)
        assert manifest["replayed_steps"] == _CRASH_AT_STEP - 1


class TestDefaultOffByteIdentity:
    """With no --llm-journal / --resume-from, output is byte-identical
    across two runs of the UNMODIFIED CLI (no test driver, no crash hook --
    the stock mock and the real run_experiment.py entry point). Synthetic
    agents (not --real) for speed; --real was checked manually before
    implementing this feature (see this feature's delivery report) and is
    architecturally the same seam (get_llm_invoke), so this synthetic,
    fast check is the permanent regression pin for both.
    """

    def test_no_journal_flags_are_byte_identical_across_two_runs(self, tmp_path):
        out_a = tmp_path / "a"
        out_b = tmp_path / "b"
        pinned_env = {**os.environ, "PYTHONHASHSEED": "0"}
        for out in (out_a, out_b):
            result = subprocess.run(
                [
                    sys.executable, "examples/irrigation_abm/run_experiment.py",
                    "--model", "mock", "--agents", "5", "--years", "3",
                    "--governance-mode", "strict", "--workers", "1",
                    "--seed", "42", "--memory-seed", "42", "--output", str(out),
                ],
                cwd=str(_REPO_ROOT), env=pinned_env,
                capture_output=True, text=True, timeout=120,
            )
            assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
            assert not (out / "llm_journal.jsonl").exists()

        for name in (
            "simulation_log.csv", "validator_health.csv", "validator_health_by_agent_type.csv",
        ):
            _assert_csv_matches(out_a / name, out_b / name)

        rc = compare_audit_csv(
            out_a / "irrigation_farmer_governance_audit.csv",
            out_b / "irrigation_farmer_governance_audit.csv",
        )
        assert rc == 0

        for name in (
            "governance_summary.json", "run_integrity.json",
            "audit_summary.json", "reproducibility_manifest.json",
        ):
            _assert_json_matches(out_a / name, out_b / name)

        a_lines = (out_a / "raw" / "irrigation_farmer_traces.jsonl").read_text(
            encoding="utf-8").splitlines()
        b_lines = (out_b / "raw" / "irrigation_farmer_traces.jsonl").read_text(
            encoding="utf-8").splitlines()
        assert len(a_lines) == len(b_lines)
        for la, lb in zip(a_lines, b_lines):
            assert _strip_volatile(json.loads(la)) == _strip_volatile(json.loads(lb))


class TestDirectoryCollision:
    """Review fix: resuming into the SAME directory as the source run must
    be refused up front (would truncate llm_journal.jsonl before/while it
    is read, and double-append reflection_log.jsonl for the replayed
    years)."""

    def test_resume_into_the_source_directory_via_dir_form_is_refused(self, tmp_path):
        crashed = tmp_path / "crashed"
        r1 = _run(crashed, llm_journal=True, crash_at_step=_CRASH_AT_STEP)
        assert r1.returncode != 0, "the simulated crash did not happen"
        original_journal_bytes = (crashed / "llm_journal.jsonl").read_bytes()

        r2 = _run(crashed, resume_from=crashed, llm_journal=True, crash_at_step=0)
        assert r2.returncode != 0
        assert "SAME directory" in (r2.stdout + r2.stderr)
        assert (crashed / "llm_journal.jsonl").read_bytes() == original_journal_bytes

    def test_resume_into_the_source_directory_via_file_form_is_also_refused(self, tmp_path):
        """--output == the crashed run's own dir; --resume-from points at
        that SAME dir's llm_journal.jsonl file directly (not the
        directory form) -- both spellings must be caught."""
        crashed = tmp_path / "crashed"
        r1 = _run(crashed, llm_journal=True, crash_at_step=_CRASH_AT_STEP)
        assert r1.returncode != 0
        original_journal_bytes = (crashed / "llm_journal.jsonl").read_bytes()

        r2 = _run(
            crashed, resume_from=crashed / "llm_journal.jsonl",
            llm_journal=True, crash_at_step=0,
        )
        assert r2.returncode != 0
        assert "SAME directory" in (r2.stdout + r2.stderr)
        assert (crashed / "llm_journal.jsonl").read_bytes() == original_journal_bytes


def _classify_journal_calls(journal_path: Path) -> dict:
    """``step -> {"decision": count, "reflection": count}``, classified by
    the shape of each call record's own recorded content: the test mock
    (fixtures/journal_resume_driver.py) always replies with a "decision"
    key for a decision prompt, and an ``{agent_id: text}`` dict with no
    "decision" key for a batch-reflection prompt.
    """
    counts: dict = {}
    for line in Path(journal_path).read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("type") != "call":
            continue
        step = rec["step"]
        counts.setdefault(step, {"decision": 0, "reflection": 0})
        content = rec.get("content")
        kind = "reflection"
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict) and "decision" in parsed:
                    kind = "decision"
            except (ValueError, TypeError):
                pass
        counts[step][kind] += 1
    return counts


def _llm_calls_total_per_year(raw_trace_path: Path) -> dict:
    """``year -> sum of llm_calls_total`` across every decision trace row
    for that year. ``llm_calls_total`` lives under each row's own
    ``llm_stats`` sub-dict (broker/core/_retry_loop.py's
    ``total_llm_stats``, written into the trace as-is), not at the row's
    top level. A decision retried N times contributes N to this sum (one
    per real LLM call), the same quantity
    :func:`_classify_journal_calls`'s "decision" count for that year
    measures from the journal's own side -- these two independent
    instrumentation layers must agree.
    """
    totals: dict = {}
    for line in Path(raw_trace_path).read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        year = rec.get("year")
        if year is None:
            continue  # the header/metadata-only first line
        llm_stats = rec.get("llm_stats") or {}
        totals[year] = totals.get(year, 0) + int(llm_stats.get("llm_calls_total", 0) or 0)
    return totals


def _reflection_log_entries(reflection_log_path: Path) -> list:
    """``[(agent_id, summary, year_created), ...]`` from a
    reflection_log.jsonl (broker/components/cognitive/reflection.py
    ReflectionEngine.store_insight's own write format)."""
    path = Path(reflection_log_path)
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        entries.append((rec.get("agent_id"), rec.get("summary"), rec.get("year_created")))
    return entries


class TestReflectionReplay:
    """Review fix: the test mock now answers batch-reflection prompts
    (fixtures/journal_resume_driver.py), so a run exercises and journals
    BOTH call kinds, and reflection_log.jsonl content can be checked for
    exact replay fidelity across a crash + resume."""

    def test_raw_calls_per_step_and_kind_match_the_journal(self, tmp_path):
        out = tmp_path / "out"
        result = _run(out, llm_journal=True, crash_at_step=0, years=3)
        assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]

        journal_counts = _classify_journal_calls(out / "llm_journal.jsonl")
        trace_totals = _llm_calls_total_per_year(out / "raw" / "irrigation_farmer_traces.jsonl")
        for year, decision_calls in trace_totals.items():
            assert journal_counts.get(year, {}).get("decision", 0) == decision_calls, (
                f"year {year}: {decision_calls} llm_calls_total in the raw trace vs "
                f"{journal_counts.get(year, {}).get('decision', 0)} decision-kind "
                f"journal records"
            )
        # Since irrigation spec item 45a the year-end reflection also sees
        # the outcome of the year just ended, so it runs from year 1 (before,
        # it needed a prior year's memory line and started at year 2); with
        # 3 years configured, at least one must have been journaled.
        assert sum(c["reflection"] for c in journal_counts.values()) > 0

    def test_year_2_reflection_log_matches_after_crash_and_resume(self, tmp_path):
        crashed = tmp_path / "crashed"
        r1 = _run(crashed, llm_journal=True, crash_at_step=_CRASH_AT_STEP)
        assert r1.returncode != 0, "the simulated crash did not happen"

        resumed = tmp_path / "resumed"
        r2 = _run(
            resumed, resume_from=crashed / "llm_journal.jsonl",
            llm_journal=True, crash_at_step=0,
        )
        assert r2.returncode == 0, r2.stdout[-4000:] + r2.stderr[-4000:]

        crashed_entries = {
            (aid, summary) for aid, summary, year in
            _reflection_log_entries(crashed / "reflection_log.jsonl")
            if year == 2
        }
        resumed_entries = {
            (aid, summary) for aid, summary, year in
            _reflection_log_entries(resumed / "reflection_log.jsonl")
            if year == 2
        }
        assert crashed_entries, "no year-2 reflection entries were produced to compare"
        assert crashed_entries == resumed_entries


class TestConfigContentRefusals:
    """Review fix: an in-place edit to the agent-config YAML, the prompt
    template, or the skill registry (all read from --config-dir) must
    refuse resume even when --config-dir itself is unchanged -- each is
    content-hashed, not just path-compared. Uses an ISOLATED --config-dir
    copy (the sanctioned mechanism) so the frozen in-tree config is never
    touched.
    """

    def test_edited_agent_config_yaml_blocks_resume(self, tmp_path):
        config_dir = _make_isolated_config_dir(tmp_path / "config_copy")
        crashed = tmp_path / "crashed"
        r1 = _run(crashed, llm_journal=True, crash_at_step=_CRASH_AT_STEP, config_dir=config_dir)
        assert r1.returncode != 0, "the simulated crash did not happen"

        yaml_path = config_dir / "agent_types.yaml"
        yaml_path.write_text(
            yaml_path.read_text(encoding="utf-8") + "\n# test-only trailing edit\n",
            encoding="utf-8",
        )

        resumed = tmp_path / "resumed"
        r2 = _run(
            resumed, resume_from=crashed / "llm_journal.jsonl",
            llm_journal=True, crash_at_step=0, config_dir=config_dir,
        )
        assert r2.returncode != 0
        assert "agent_config_sha256" in (r2.stdout + r2.stderr)

    def test_edited_prompt_template_blocks_resume(self, tmp_path):
        config_dir = _make_isolated_config_dir(tmp_path / "config_copy")
        crashed = tmp_path / "crashed"
        r1 = _run(crashed, llm_journal=True, crash_at_step=_CRASH_AT_STEP, config_dir=config_dir)
        assert r1.returncode != 0

        template_path = config_dir / "prompts" / "irrigation_farmer.txt"
        template_path.write_text(
            template_path.read_text(encoding="utf-8") + "\ntest-only trailing edit\n",
            encoding="utf-8",
        )

        resumed = tmp_path / "resumed"
        r2 = _run(
            resumed, resume_from=crashed / "llm_journal.jsonl",
            llm_journal=True, crash_at_step=0, config_dir=config_dir,
        )
        assert r2.returncode != 0
        assert "prompt_template_sha256" in (r2.stdout + r2.stderr)

    def test_edited_skill_registry_blocks_resume(self, tmp_path):
        config_dir = _make_isolated_config_dir(tmp_path / "config_copy")
        crashed = tmp_path / "crashed"
        r1 = _run(crashed, llm_journal=True, crash_at_step=_CRASH_AT_STEP, config_dir=config_dir)
        assert r1.returncode != 0

        registry_path = config_dir / "skill_registry.yaml"
        registry_path.write_text(
            registry_path.read_text(encoding="utf-8") + "\n# test-only trailing edit\n",
            encoding="utf-8",
        )

        resumed = tmp_path / "resumed"
        r2 = _run(
            resumed, resume_from=crashed / "llm_journal.jsonl",
            llm_journal=True, crash_at_step=0, config_dir=config_dir,
        )
        assert r2.returncode != 0
        assert "skill_registry_sha256" in (r2.stdout + r2.stderr)


class TestGitStateRefusals:
    """Review fix: refuse resume when the commit or the uncommitted-diff
    hash differs. Tested by editing the SOURCE JOURNAL's own header field
    (never an actual git commit or a mutated worktree -- this test may do
    neither), which exercises the exact same comparison the real check
    runs.
    """

    def test_different_commit_blocks_resume(self, tmp_path):
        crashed = tmp_path / "crashed"
        r1 = _run(crashed, llm_journal=True, crash_at_step=_CRASH_AT_STEP)
        assert r1.returncode != 0, "the simulated crash did not happen"

        journal_path = crashed / "llm_journal.jsonl"
        _overwrite_header_field(journal_path, "git_commit", "0" * 40)

        resumed = tmp_path / "resumed"
        r2 = _run(resumed, resume_from=journal_path, llm_journal=True, crash_at_step=0)
        assert r2.returncode != 0
        assert "git_commit" in (r2.stdout + r2.stderr)

    def test_different_diff_hash_blocks_resume(self, tmp_path):
        crashed = tmp_path / "crashed"
        r1 = _run(crashed, llm_journal=True, crash_at_step=_CRASH_AT_STEP)
        assert r1.returncode != 0, "the simulated crash did not happen"

        journal_path = crashed / "llm_journal.jsonl"
        _overwrite_header_field(journal_path, "git_diff_sha256", "f" * 64)

        resumed = tmp_path / "resumed"
        r2 = _run(resumed, resume_from=journal_path, llm_journal=True, crash_at_step=0)
        assert r2.returncode != 0
        assert "git_diff_sha256" in (r2.stdout + r2.stderr)

    def test_untracked_file_after_crash_does_not_block_resume(self, tmp_path):
        """The dirty flag and the diff hash are both computed from TRACKED
        changes only (git status --untracked-files=no; git diff HEAD) --
        a new untracked file appearing in the repo after the crash (e.g.
        the crashed run's own output, if --output happened to sit inside
        the tree) must never block the resume."""
        crashed = tmp_path / "crashed"
        r1 = _run(crashed, llm_journal=True, crash_at_step=_CRASH_AT_STEP)
        assert r1.returncode != 0, "the simulated crash did not happen"

        scratch_file = _REPO_ROOT / f"_test_untracked_scratch_{os.getpid()}.tmp"
        scratch_file.write_text("simulated untracked file appearing after a crash\n")
        try:
            resumed = tmp_path / "resumed"
            r2 = _run(
                resumed, resume_from=crashed / "llm_journal.jsonl",
                llm_journal=True, crash_at_step=0,
            )
            assert r2.returncode == 0, r2.stdout[-4000:] + r2.stderr[-4000:]
        finally:
            scratch_file.unlink(missing_ok=True)
