"""Launch orchestrator for the irrigation v3 corpus (spec WP7 Launch, 7.1-7.6).

Source: `.research/design_specs/irrigation_v3_spec_2026-09-28.md`, section
"WP7 Launch" (7.1-7.6) and section 4 "Pilot protocol". Two things changed
after that text was written and are followed here instead:

* the gate is the `pilot-gate` subcommand of
  `examples/irrigation_abm/analysis/v3_metrics.py` (there is no separate
  `v3_pilot_gate.py`);
* P5(c) needs a human review record, produced by that module's
  `p5c-sample` subcommand, before the gate can pass.

This module does not call Ollama, run_experiment.py's model code, or any
LLM directly. It only builds argv lists for three existing CLIs
(`run_fql_baseline.py`, `run_experiment.py`, `v3_metrics.py`) and launches
them as subprocesses, the same thing a human operator would type. Its own
test suite (`examples/irrigation_abm/tests/test_v3_corpus_launcher.py`)
mocks every `subprocess.run` / `subprocess.Popen` call, so running that
suite never starts Ollama or a real experiment. Every generated command
uses `sys.executable` (never the bare string "python"), so a relaunch
under this launcher always uses the SAME interpreter the launcher itself
is running under; `assert_correct_interpreter` additionally refuses to
launch anything at all unless that interpreter is Python 3.14, the corpus
interpreter (`python3` on this machine is 3.11 with a different numpy --
see the memory note on the two-Python-interpreters hazard).

Four run-plan phases, 27 total planned runs (dated note, 2026-10-07: the
PLACEBO arm is dropped -- decided in `.research/paper_scope_2026-10-06.md`
section 5 ("灌溉 v3 placebo | ... | 不做"), appended to
`.research/design_specs/irrigation_v3_spec_2026-09-28.md` as item 39 rather
than rewriting WP7 7.4's original 21-LLM-run text. Before this note the
corpus phase ran 19 post-gate runs / 21 LLM runs / 32 total; it now runs 14
post-gate runs / 16 LLM runs / 27 total):

* `fql`      (CPU, 10 runs):  FQL reference, seeds 42-51 (spec 7.5).
* `replays`  (CPU, 1 run):    the WP1b fixed-demand replays A and B, written
                               together by one `v3_metrics.py replay` call.
* `pilot`    (GPU, 2 runs):   strict and disabled, seed 42 (spec section 4).
                               These are also the strict/disabled seed-42
                               members of the corpus (spec 7.4).
* `corpus`   (GPU, 14 runs):  strict and disabled seeds 43-46, silent seeds
                               42-46, feasibility_only seed 42 (spec 7.4,
                               item 16; item 39 drops placebo).

A run's status is one of four, by inspecting its own directory (and, for an
LLM run, the launcher's own per-run record of its PID and exit code, see
below): "pending" (nothing there yet), "running" (a matching live PID,
an unknown process query with no recorded exit, or a fresh LLM journal
when no PID is available or a live Python process cannot be matched),
"crashed" (an unfinished attempt with a recorded exit or without
liveness evidence), or "done" (a clean
manifest, plus either a recorded exit 0 or a `run_integrity.json` showing
every configured row and year written for LLM runs).
`run <phase>` launches only the PENDING entries for
that phase, printing why every other one was skipped, since relaunching a
"done" entry fails at the audit writer (it refuses a directory that
already has a manifest) and relaunching a "crashed" entry without
`--resume-from` reopens `llm_journal.jsonl` in write mode, destroying its
resumability.

An LLM run's status is resolved against the LATEST attempt in its own
resume chain (`<dir>`, then `<dir>_resume1`, `<dir>_resume2`, ... -- every
one that exists): a finished `_resumeN` directory counts as the run's own
completion for `plan`, `gate` and `corpus`'s prerequisite checks, and
`resume <label>` always resumes from the latest CRASHED attempt (refusing
if the latest attempt is "running", not "crashed"), landing in the next
free `_resumeN` suffix -- never the original directory.

A PID is never trusted by its bare existence: Windows recycles PIDs, so a
crashed run's old PID can already belong to an unrelated process by the
time anyone checks it. Every liveness check (`is_run_process_alive`,
`is_chain_alive`) queries `Get-CimInstance Win32_Process` for that PID and
requires BOTH that the process name starts with `python` and ends with
`.exe` AND that its command line names the specific thing being checked
(a run's own `--output` directory,
or the `_run-chain` entry point for a chain-runner process) -- with a
timeout and one retry. An unavailable query conservatively counts as
alive; `plan` displays this as `running?`. `_process_command_line` is the
one mockable function that shells out.

Safety rules enforced here, beyond what run_experiment.py itself enforces:

* `run pilot`, `run corpus` and `resume` refuse outright while ANY chain
  PID recorded in the state file's `launches` list is still alive
  (`live_chain_launch`): entries queued later in a live chain have no
  attempt directory or run record yet and would otherwise look "pending"
  to a second invocation, launching them a second time into the same
  output directory. Wait for the live chain to finish (or `resume` it, if
  it already failed), then `run <phase>` again to launch what is left.
* `run`/`resume`/`gate` refuse unless `git status --porcelain` is empty and
  HEAD equals the commit a given `--tag` names (spec 7.2: "run from a
  fresh worktree of the tag").
* `pilot` and `corpus` (and `resume` of either) refuse without
  `--confirm-gpu`, and refuse a `--workers` value that does not match
  BOTH the one this launcher's state file already recorded for this
  campaign (first GPU launch records it) AND the one actually recorded in
  the pilot pair's own manifests once they exist (`corpus` and `resume`
  only: the pilot launch has no pilot-pair manifest to compare against
  yet). This exists because `v3_metrics.py`'s own provenance guard
  refuses to pool LLM runs whose `workers` differ, including a resumed
  run's `source_workers` (`examples/irrigation_abm/docs/v3_metrics.md`,
  section 10) -- so a campaign that silently drifted workers partway
  through, or whose state file fell out of sync with what was actually
  launched, would only fail much later, at analysis time.
* `pilot` additionally refuses unless all 10 FQL seeds and the replays
  already show "done" (spec 7.4 orders them before the pilot).
* `corpus` (and `resume` of a corpus-phase run) refuses unless this
  launcher's state file records a PASSED `pilot-gate` result for the SAME
  resolved commit.
* every run inside a phase runs inside ONE detached process
  (`subprocess.DETACHED_PROCESS` only, deliberately never combined with
  `CREATE_NEW_PROCESS_GROUP` -- see the memory note on long-running batch
  detach mode: that combination propagates a Ctrl-Break and can abort the
  whole chain), so the chain survives the launching terminal closing. Each
  individual command inside the chain is itself launched with
  `CREATE_NO_WINDOW` (its parent has no console at all, being detached, so
  without this a child could try to allocate its own). PID, logs, chain
  specs, per-run PID/exit records and the workers/gate state all live
  OUTSIDE the run worktree (default `~/.wagf_launcher/`), so the worktree
  stays clean for `git status --porcelain`.

Results root default: the PRIMARY clone's own irrigation results tree
(`governed_broker_framework/examples/irrigation_abm/results/v3_corpus`),
not a path inside whatever worktree this launcher runs from. That tree is
already gitignored and already covered by the nightly 04:30
`WAGF_Results_Backup_GDrive` task, so pointing there needs no new junction
into a worktree (junctions have cost a full results tree before: see the
memory note on removing a worktree with junctions) and the run worktree
itself never accumulates result data.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

# examples/irrigation_abm/tools/v3_corpus_launcher.py -> repo root is 3 parents up
# (tools -> irrigation_abm -> examples -> root), the same depth
# test_workers_resume_integration.py uses for its own _REPO_ROOT.
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[3]

_DEFAULT_RESULTS_ROOT = Path(
    "C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/"
    "examples/irrigation_abm/results/v3_corpus"
)
_DEFAULT_STATE_DIR = Path.home() / ".wagf_launcher"

_MANIFEST_NAME = "reproducibility_manifest.json"
_INTEGRITY_NAME = "run_integrity.json"
_JOURNAL_NAME = "llm_journal.jsonl"
_STATE_FILE_NAME = "state.json"

_PYTHON = sys.executable
_REQUIRED_PYTHON = (3, 14)
_MODEL = "gemma3:4b"
_YEARS = 42
_PAPER_WATER_MARGIN = "0.4"
_CLUSTER_METHOD = "hy2021"

_FQL_SEEDS = list(range(42, 52))          # 42..51 (spec 7.5)
_PILOT_SEED = 42
_POST_GATE_SEEDS = [43, 44, 45, 46]       # strict / disabled post-gate
# Item 39 (2026-10-07): the PLACEBO arm is dropped from the corpus (decided
# in paper_scope_2026-10-06.md section 5); only silent runs this seed list now.
_SILENT_SEEDS = [42, 43, 44, 45, 46]

_PHASES = ("fql", "replays", "pilot", "corpus")
_GPU_PHASES = ("pilot", "corpus")


# =============================================================================
# Run plan data model
# =============================================================================

@dataclass(frozen=True)
class PlannedRun:
    label: str
    phase: str              # "fql" | "replays" | "pilot" | "corpus"
    command: List[str]
    output_dir: Path
    is_llm: bool             # whether --llm-journal / --workers / --confirm-gpu apply


def _llm_command(
    seed: int, governance_mode: str, retry_feedback_mode: Optional[str],
    output_dir: Path, workers: Union[int, str],
) -> List[str]:
    """One `run_experiment.py` invocation (spec 7.5), explicit about every
    spec-7.2-pinned water-system value even where it matches the script's
    own default, so the plan's printed command line is self-describing."""
    cmd = [
        _PYTHON, "examples/irrigation_abm/run_experiment.py",
        "--real", "--model", _MODEL, "--years", str(_YEARS), "--seed", str(seed),
        # Item 36b (2026-10-05 design-basis audit + fix proposals, spec
        # item 36b, N11): without this, run_experiment.py's --memory-seed
        # default (42) applied to EVERY launcher-produced run regardless
        # of --seed, so every run drew the SAME memory-consolidation
        # stream -- the launcher-side half of the N9/N10/N11 finding
        # (the framework-side half is the three HumanCentricMemoryEngine
        # options above). --memory-seed now follows --seed, one memory
        # stream per corpus seed, same as every other per-run value here.
        "--memory-seed", str(seed),
        "--paper-water-margin", _PAPER_WATER_MARGIN,
        "--cluster-method", _CLUSTER_METHOD,
        "--governance-mode", governance_mode,
    ]
    if retry_feedback_mode:
        cmd += ["--retry-feedback-mode", retry_feedback_mode]
    cmd += [
        "--output", str(output_dir),
        "--llm-journal", "--workers", str(workers),
    ]
    return cmd


def build_plan(results_root: Path, sha8: str, workers: Union[int, str]) -> List[PlannedRun]:
    """The full 27-entry ordered plan: 10 FQL + 1 replay call (A and B
    together) + 2 pilot + 14 post-gate corpus runs (spec 7.4, item 39;
    16 LLM runs in all -- the PLACEBO arm is dropped, item 39). `workers`
    is only baked into the LLM (pilot/corpus) commands;
    the CPU phases (fql, replays) never take --workers. `workers` may be a
    descriptive placeholder string (`cmd_plan` passes one when no value is
    known yet) since it is only ever embedded via `str()`, never compared
    or arithmetic'd here."""
    runs: List[PlannedRun] = []

    for seed in _FQL_SEEDS:
        out = results_root / f"v3_fql_reference_{sha8}_seed{seed}"
        cmd = [
            _PYTHON, "examples/irrigation_abm/run_fql_baseline.py",
            "--real", "--no-governance", "--fql-init", "calibrated",
            "--years", str(_YEARS), "--seed", str(seed),
            "--paper-water-margin", _PAPER_WATER_MARGIN,
            "--cluster-method", _CLUSTER_METHOD,
            "--output", str(out),
        ]
        runs.append(PlannedRun(f"fql_seed{seed}", "fql", cmd, out, False))

    replays_out = results_root / f"v3_replays_{sha8}"
    replays_cmd = [
        _PYTHON, "examples/irrigation_abm/analysis/v3_metrics.py", "replay",
        "--real", "--years", str(_YEARS), "--seed", str(_PILOT_SEED),
        "--paper-water-margin", _PAPER_WATER_MARGIN,
        "--cluster-method", _CLUSTER_METHOD,
        "--out", str(replays_out),
    ]
    runs.append(PlannedRun("replays_ab", "replays", replays_cmd, replays_out, False))

    for arm, mode in (("strict", "strict"), ("disabled", "disabled")):
        out = results_root / f"v3_{arm}_42yr_gemma3_4b_{sha8}_seed{_PILOT_SEED}"
        cmd = _llm_command(_PILOT_SEED, mode, None, out, workers)
        runs.append(PlannedRun(f"pilot_{arm}_{_PILOT_SEED}", "pilot", cmd, out, True))

    for seed in _POST_GATE_SEEDS:
        out = results_root / f"v3_strict_42yr_gemma3_4b_{sha8}_seed{seed}"
        runs.append(PlannedRun(
            f"strict_{seed}", "corpus", _llm_command(seed, "strict", None, out, workers), out, True,
        ))
    for seed in _POST_GATE_SEEDS:
        out = results_root / f"v3_disabled_42yr_gemma3_4b_{sha8}_seed{seed}"
        runs.append(PlannedRun(
            f"disabled_{seed}", "corpus", _llm_command(seed, "disabled", None, out, workers), out, True,
        ))
    for seed in _SILENT_SEEDS:
        out = results_root / f"v3_silent_42yr_gemma3_4b_{sha8}_seed{seed}"
        runs.append(PlannedRun(
            f"silent_{seed}", "corpus",
            _llm_command(seed, "strict", "silent", out, workers), out, True,
        ))
    fo_out = results_root / f"v3_feasibility_only_42yr_gemma3_4b_{sha8}_seed{_PILOT_SEED}"
    runs.append(PlannedRun(
        f"feasibility_only_{_PILOT_SEED}", "corpus",
        _llm_command(_PILOT_SEED, "feasibility_only", None, fo_out, workers), fo_out, True,
    ))

    return runs


# =============================================================================
# Interpreter check (item 9): the corpus runs under Python 3.14 specifically
# =============================================================================

def assert_correct_interpreter() -> None:
    """Refuses unless this process itself is Python 3.14 (the corpus
    interpreter, with its own numpy); `python3` on this machine resolves to
    3.11 with a DIFFERENT numpy. Every generated command uses
    `sys.executable`, so passing this check is enough to guarantee every
    launched command uses the same, correct interpreter too."""
    if sys.version_info[:2] != _REQUIRED_PYTHON:
        raise SystemExit(
            f"refused: this launcher must run under Python "
            f"{_REQUIRED_PYTHON[0]}.{_REQUIRED_PYTHON[1]} (the corpus interpreter); "
            f"got {sys.version_info.major}.{sys.version_info.minor} at {sys.executable}. "
            f"Invoke it as 'python ...', never 'python3 ...' (see the memory note on "
            f"the two-Python-interpreters hazard)."
        )


def _record_interpreter(state: dict) -> None:
    state["python_executable"] = sys.executable
    state["python_version"] = ".".join(str(p) for p in sys.version_info[:3])


# =============================================================================
# Run status (pending / running / crashed / done)
# =============================================================================

_LIVENESS_TIMEOUT = 30.0
_JOURNAL_LIVENESS_SECONDS = 900


@dataclass(frozen=True)
class ProcProbe:
    status: str             # "alive" | "absent" | "unknown"
    name: str = ""
    cmdline: str = ""


def _process_command_line(pid: int, timeout: float = _LIVENESS_TIMEOUT) -> Optional[str]:
    """Return the raw name, then command line, or None for an absent PID.
    Query failures propagate to probe_process so absence stays distinct
    from an unavailable query. This is the one process-query shell call.
    """
    result = subprocess.run(
        [
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "$ErrorActionPreference = 'Stop'; "
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
            f'$p = Get-CimInstance Win32_Process -Filter "ProcessId={int(pid)}"; '
            "if ($p) { $p.Name; $p.CommandLine }",
        ],
        capture_output=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, "powershell")
    text = (result.stdout or b"").decode("utf-8", errors="replace")
    return text or None


def probe_process(pid: Optional[int], timeout: float = _LIVENESS_TIMEOUT) -> ProcProbe:
    """Query once, retry one failure, and keep unknown distinct from absent."""
    if not pid:
        return ProcProbe("absent")
    for _ in range(2):
        try:
            text = _process_command_line(pid, timeout=timeout)
        except (subprocess.TimeoutExpired, OSError, subprocess.CalledProcessError):
            continue
        if not text:
            return ProcProbe("absent")
        text = text.lstrip("\ufeff").strip()
        if not text:
            return ProcProbe("absent")
        # examples/irrigation_abm/tests/test_v3_corpus_launcher.py
        # (TestLivenessProbeRegression) also supplies legacy formatted text.
        formatted = re.match(r"Name\s*:\s*([^\r\n]+)\s+CommandLine\s*:\s*(.*)", text, re.DOTALL)
        if formatted:
            name, cmdline = formatted[1].strip(), formatted[2].strip()
        else:
            name, separator, cmdline = text.partition("\n")
            if not separator:
                name, _, cmdline = text.partition(" ")
            name, cmdline = name.strip(), cmdline.strip()
        status = "unknown" if _is_python_name(name) and not cmdline else "alive"
        return ProcProbe(status, name, cmdline)
    return ProcProbe("unknown")


def _normalise_process_text(text: str) -> str:
    text = text.casefold().replace("/", "\\").replace('"', "").replace("'", "")
    return " ".join(text.split())


def _is_python_name(name: str) -> bool:
    name = name.casefold()
    return name.startswith("python") and name.endswith(".exe")


def _probe_matches(probe: ProcProbe, needle: str) -> bool:
    if probe.status == "unknown":
        return True
    if probe.status != "alive" or not _is_python_name(probe.name):
        return False
    needle = _normalise_process_text(needle)
    if needle in _normalise_process_text(probe.cmdline):
        return True
    # Format-List can split a path inside a token and indent the next line.
    unwrapped = re.sub(r"\r?\n[ \t]+", "", probe.cmdline)
    return needle in _normalise_process_text(unwrapped)


def is_process_alive_for(pid: Optional[int], needle: str, timeout: float = _LIVENESS_TIMEOUT) -> bool:
    """Match this Python process and command line, assuming alive if unknown."""
    return _probe_matches(probe_process(pid, timeout=timeout), needle)


def _probe_matches_run(probe: ProcProbe, output_dir: Path) -> bool:
    if probe.status == "unknown":
        return True
    if probe.status != "alive" or not _is_python_name(probe.name):
        return False
    cmdline = re.sub(r"\r?\n[ \t]+", "", probe.cmdline)
    tokens = re.findall(r'''"[^"]*"|'[^']*'|\S+''', cmdline)
    output_flags = [index for index, token in enumerate(tokens) if token == "--output"]
    folder = os.path.normcase(os.path.abspath(str(output_dir)))
    if output_flags:
        index = output_flags[-1] + 1
        if index >= len(tokens):
            return False
        argument = tokens[index].strip('"\'')
        return os.path.normcase(os.path.abspath(argument)) == folder
    needle = _normalise_process_text(folder)
    text = " ".join(cmdline.casefold().replace("/", "\\").split())
    return re.search(re.escape(needle) + r'''(?=$|[\s"'\\/])''', text) is not None


def is_run_process_alive(pid: Optional[int], output_dir: Path, timeout: float = _LIVENESS_TIMEOUT) -> bool:
    """Match a live Python process to this run's normalised --output value."""
    return _probe_matches_run(probe_process(pid, timeout=timeout), output_dir)


def is_chain_alive(pid: Optional[int], timeout: float = _LIVENESS_TIMEOUT) -> bool:
    """Item 1: a PID counts as a live CHAIN (the detached `_run-chain`
    process, not one of its inner per-run children) only if it is a live
    Python process whose command line names the `_run-chain` entry point."""
    return is_process_alive_for(pid, "_run-chain", timeout=timeout)


def _run_record_path(state_dir: Path, record_label: str, sha8: Optional[str] = None) -> Path:
    """Records are namespaced under `state_dir/runs/<sha8>/` when a sha8
    is given, so a fresh tag/campaign under the SAME --state-dir never
    reads a stale record left by an older sha8 (previously the record
    path carried only the plan label, so re-tagging without a fresh
    --state-dir made every new sha8's first status check misreport as
    "crashed" before the run even started -- the 2026-10-06 CPU rerun
    hit this). `sha8=None` keeps the old flat path, for callers that
    have no sha8 to namespace by (e.g. tests exercising this helper in
    isolation)."""
    if sha8:
        return state_dir / "runs" / sha8 / f"{record_label}.json"
    return state_dir / "runs" / f"{record_label}.json"


def read_run_record(
    state_dir: Optional[Path], record_label: str, sha8: Optional[str] = None,
) -> Optional[dict]:
    """The chain driver's own record of one run's PID / start / exit
    (written by `run_chain`, read by status detection). `None` when there
    is no state dir to look in, or no record yet."""
    if state_dir is None:
        return None
    path = _run_record_path(state_dir, record_label, sha8)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_run_record(
    state_dir: Path, record_label: str, record: dict, sha8: Optional[str] = None,
) -> None:
    path = _run_record_path(state_dir, record_label, sha8)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")


def _manifest_counts_as_done(
    manifest: dict, output_dir: Path, is_llm: bool, record: Optional[dict],
) -> bool:
    """Item 3(b): a manifest with a clean (non-aborted) `run_status` is not
    by itself enough for an LLM run, since `_finalize_experiment` writes
    the manifest unconditionally in a `finally` on ANY exit path. "done"
    additionally needs either this launcher's OWN recorded exit 0 for the
    run (the fast, authoritative path once we have it), or -- when we do
    not (a dir this launcher never tracked the launch of) --
    `run_integrity.json` showing every configured row and year actually
    written. FQL and replay runs never write run_integrity.json (only
    ExperimentRunner does), so they keep the simpler manifest-only check."""
    status = manifest.get("run_status")
    if status and str(status).startswith("aborted"):
        return False
    if not is_llm:
        return True
    if record is not None and record.get("returncode") == 0:
        return True
    integrity_path = output_dir / _INTEGRITY_NAME
    if integrity_path.is_file():
        try:
            integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if (
            integrity.get("audit_rows_missing_vs_configured_grid") == 0
            and integrity.get("audit_years") == _YEARS
        ):
            return True
    return False


def run_status_for_dir(
    output_dir: Path, *, is_llm: bool = False, record: Optional[dict] = None,
) -> str:
    """Return one of the four status words for one concrete attempt."""
    return _run_status_for_dir(output_dir, is_llm=is_llm, record=record)[0]


def _journal_is_fresh(output_dir: Path) -> bool:
    try:
        age = time.time() - (output_dir / _JOURNAL_NAME).stat().st_mtime
    except OSError:
        return False
    return 0 <= age < _JOURNAL_LIVENESS_SECONDS


def _run_status_for_dir(
    output_dir: Path, *, is_llm: bool = False, record: Optional[dict] = None,
) -> Tuple[str, bool]:
    """Return status and query uncertainty using the same probe result."""
    manifest_path = output_dir / _MANIFEST_NAME
    has_manifest = output_dir.exists() and manifest_path.is_file()
    if has_manifest:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            manifest = None
        if manifest is not None and _manifest_counts_as_done(manifest, output_dir, is_llm, record):
            return "done", False

    if record is not None:
        if record.get("returncode") is None:
            pid = record.get("pid")
            if pid:
                probe = probe_process(pid)
                if _probe_matches_run(probe, output_dir):
                    return "running", probe.status == "unknown"
                if probe.status == "alive" and _is_python_name(probe.name) and is_llm and _journal_is_fresh(output_dir):
                    return "running", True
            elif not has_manifest and is_llm and _journal_is_fresh(output_dir):
                return "running", False
        return "crashed", False

    if has_manifest:
        return "crashed", False
    if is_llm and _journal_is_fresh(output_dir):
        return "running", False
    if not output_dir.exists():
        return "pending", False
    has_partial = (output_dir / _JOURNAL_NAME).exists() or any(output_dir.iterdir())
    return ("crashed" if has_partial else "pending"), False


def resume_chain_dirs(base_output_dir: Path) -> List[Path]:
    """[base, base_resume1, base_resume2, ...] -- every attempt that
    currently exists on disk, in order. Always includes base, whether or
    not it exists yet."""
    dirs = [base_output_dir]
    n = 1
    while True:
        candidate = base_output_dir.parent / f"{base_output_dir.name}_resume{n}"
        if not candidate.exists():
            break
        dirs.append(candidate)
        n += 1
    return dirs


def record_label_for_attempt(label: str, attempt_index: int) -> str:
    """attempt_index 0 = the base run itself; N >= 1 = its Nth resume
    (matching the `_resumeN` suffix and the label `cmd_resume` gives that
    attempt's own PlannedRun)."""
    return label if attempt_index == 0 else f"{label}_resume{attempt_index}"


def run_status_for_plan_entry(
    run: PlannedRun, state_dir: Optional[Path] = None, sha8: Optional[str] = None,
) -> str:
    """Item 4(a): an LLM run's status is resolved against the LATEST
    attempt in its resume chain, so a finished `_resumeN` directory counts
    as the run's own completion. The replay entry is a special case: one
    `v3_metrics.py replay` call writes BOTH `A/` and `B/` under its --out
    directory (never resumed -- only LLM runs are), so the entry is "done"
    only when both are, "pending" only when both are, "running" if either
    is, and "crashed" otherwise.

    `sha8` namespaces the run-record lookup (see `_run_record_path`) so a
    fresh tag never reads a stale record left by an older sha8 under the
    same --state-dir; `None` keeps the old flat lookup."""
    return _status_for_plan_entry(run, state_dir, sha8)[0]


def status_is_uncertain(
    run: PlannedRun, state_dir: Optional[Path] = None, sha8: Optional[str] = None,
) -> bool:
    """Whether this entry is running with uncertain process identity."""
    return _status_for_plan_entry(run, state_dir, sha8)[1]


def _status_for_plan_entry(
    run: PlannedRun, state_dir: Optional[Path] = None, sha8: Optional[str] = None,
) -> Tuple[str, bool]:
    if run.label == "replays_ab":
        record = read_run_record(state_dir, run.label, sha8) if state_dir else None
        a, a_uncertain = _run_status_for_dir(run.output_dir / "A", is_llm=False, record=record)
        b, b_uncertain = _run_status_for_dir(run.output_dir / "B", is_llm=False, record=record)
        if a == "done" and b == "done":
            return "done", False
        if a == "pending" and b == "pending":
            return "pending", False
        if "running" in (a, b):
            return "running", a_uncertain or b_uncertain
        return "crashed", False

    if not run.is_llm:
        record = read_run_record(state_dir, run.label, sha8) if state_dir else None
        return _run_status_for_dir(run.output_dir, is_llm=False, record=record)

    chain = resume_chain_dirs(run.output_dir)
    attempt_index = len(chain) - 1
    latest_dir = chain[attempt_index]
    record_label = record_label_for_attempt(run.label, attempt_index)
    record = read_run_record(state_dir, record_label, sha8) if state_dir else None
    return _run_status_for_dir(latest_dir, is_llm=True, record=record)


def journaled_attempt_dirs(base_output_dir: Path) -> List[Path]:
    """Item 2(d): every attempt in base_output_dir's resume chain that
    actually has `llm_journal.jsonl` on disk, in order. An empty
    `_resumeN` (a resume that died before writing anything, e.g. a bad
    --resume-from argument) has no journal and must not be mistaken for a
    resumable attempt; `resume` resumes from the LATEST one that is."""
    return [d for d in resume_chain_dirs(base_output_dir) if (d / _JOURNAL_NAME).is_file()]


def latest_done_attempt_dir(
    base_output_dir: Path, state_dir: Optional[Path], label: str, is_llm: bool,
    sha8: Optional[str] = None,
) -> Optional[Path]:
    """Item 3: the latest attempt in base_output_dir's resume chain that
    is "done", or None if none is. `cmd_gate` and
    `pilot_pair_manifest_workers` need the directory that ACTUALLY
    finished (e.g. `..._seed42_resume1`), never the crashed base dir, even
    though the base dir is still the stable path identifying the run.
    `sha8` namespaces the run-record lookup; see `_run_record_path`."""
    chain = resume_chain_dirs(base_output_dir)
    for attempt_index in range(len(chain) - 1, -1, -1):
        d = chain[attempt_index]
        record_label = record_label_for_attempt(label, attempt_index)
        record = read_run_record(state_dir, record_label, sha8) if state_dir else None
        if run_status_for_dir(d, is_llm=is_llm, record=record) == "done":
            return d
    return None


# =============================================================================
# Git preflight: clean tree + HEAD == the given tag's commit (spec 7.2)
# =============================================================================

def _run_git(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def is_tree_clean(cwd: Path) -> bool:
    """Full `git status --porcelain` (no --untracked-files=no filtering):
    spec 7.2 and the task's own hard rule both say "git status --porcelain
    empty", unlike run_experiment.py's own per-run dirty check (which
    excludes untracked files so a run's own output sitting inside the repo
    tree cannot flip it). A fresh worktree of a tag has no untracked files
    at all, so the stricter check is the right one here."""
    result = _run_git(["status", "--porcelain"], cwd)
    if result.returncode != 0:
        raise SystemExit(f"git status failed in {cwd}: {result.stderr.strip()}")
    return result.stdout.strip() == ""


def resolve_commit(ref: str, cwd: Path) -> str:
    """The commit a tag (or any ref) names, dereferencing an annotated tag
    to its commit (`^{commit}`) rather than its tag object."""
    result = _run_git(["rev-parse", f"{ref}^{{commit}}"], cwd)
    if result.returncode != 0:
        raise SystemExit(f"git rev-parse {ref!r} did not resolve to a commit: {result.stderr.strip()}")
    return result.stdout.strip()


def current_head(cwd: Path) -> str:
    result = _run_git(["rev-parse", "HEAD"], cwd)
    if result.returncode != 0:
        raise SystemExit(f"git rev-parse HEAD failed in {cwd}: {result.stderr.strip()}")
    return result.stdout.strip()


def preflight_for_tag(tag: str, cwd: Optional[Path] = None) -> str:
    """Refuses (SystemExit) unless the tree is clean and HEAD equals the
    tag's commit; returns the resolved short sha (8 hex chars) on success."""
    cwd = cwd or _REPO_ROOT
    if not is_tree_clean(cwd):
        raise SystemExit(
            f"preflight refused: git status --porcelain is not empty in {cwd}. "
            f"Run from a clean worktree of the tag (spec 7.2)."
        )
    tag_commit = resolve_commit(tag, cwd)
    head = current_head(cwd)
    if head != tag_commit:
        raise SystemExit(
            f"preflight refused: HEAD ({head[:8]}) does not match tag {tag!r} "
            f"({tag_commit[:8]}). Checkout the tag before launching."
        )
    return head[:8]


def _resolve_sha8_for_preview(tag: Optional[str], cwd: Path) -> str:
    """Used by `plan` only: no dirty-tree or HEAD-match requirement, since
    a preview must work on an ordinary development tree too. Resolves the
    given tag's commit, or falls back to the current HEAD when no tag is
    given yet."""
    if tag:
        commit = resolve_commit(tag, cwd)
    else:
        commit = current_head(cwd)
    return commit[:8]


# =============================================================================
# Launcher state file (workers consistency + pilot-gate result), outside the
# worktree, default ~/.wagf_launcher/
# =============================================================================

def _state_path(state_dir: Path) -> Path:
    return state_dir / _STATE_FILE_NAME


def load_state(state_dir: Path) -> dict:
    path = _state_path(state_dir)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_state(state_dir: Path, state: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    _state_path(state_dir).write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def check_and_record_workers(state: dict, workers: int) -> None:
    """The first GPU launch in a campaign records --workers; every later
    GPU launch (including a resume) must pass the SAME value. This is
    stricter than run_experiment.py's own resume check (which explicitly
    allows --workers to differ across a crash/resume pair) because
    v3_metrics.py's provenance guard refuses to POOL LLM runs whose
    workers differ at all, including a resumed run's source_workers
    (docs/v3_metrics.md section 10): better to refuse here, at launch
    time, than discover a mixed campaign at analysis time."""
    recorded = state.get("workers")
    if recorded is not None and recorded != workers:
        raise SystemExit(
            f"refused: --workers {workers} does not match the workers this launcher "
            f"already recorded for this campaign ({recorded}). Pass --workers {recorded}, "
            f"or use a fresh --state-dir if this is genuinely a new campaign."
        )
    state["workers"] = workers


def pilot_pair_manifest_workers(
    results_root: Path, sha8: str, state_dir: Optional[Path] = None,
) -> Optional[int]:
    """Item 6: the `workers` value actually recorded in the pilot pair's
    OWN manifests (ground truth from run_experiment.py itself), cross-
    checked against state.json's recorded value for `corpus` and
    `resume` -- state.json could in principle fall out of sync (a hand
    edit, a copied state dir) with what was really launched; the
    manifests cannot. `None` when neither pilot manifest exists yet
    (nothing to cross-check against). Raises if the two pilot manifests
    themselves disagree (should never happen; refuse rather than guess
    which one is right).

    Item 3: reads the LATEST DONE attempt in each pilot run's resume
    chain (never the crashed base dir if a resume finished it)."""
    plan = build_plan(results_root, sha8, 1)
    by_label = {r.label: r for r in plan}
    values = set()
    for label in ("pilot_strict_42", "pilot_disabled_42"):
        done_dir = latest_done_attempt_dir(
            by_label[label].output_dir, state_dir, label, is_llm=True, sha8=sha8,
        )
        if done_dir is None:
            continue
        manifest_path = done_dir / _MANIFEST_NAME
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            w = manifest.get("workers")
            if w is not None:
                values.add(w)
    if len(values) > 1:
        raise SystemExit(f"refused: the pilot pair's own manifests disagree on workers: {sorted(values)}")
    return next(iter(values)) if values else None


def live_chain_launch(state: dict) -> Optional[dict]:
    """Item 1: the first launch record in state["launches"] whose
    chain-runner process is still alive, or None. Used to refuse a NEW
    `run pilot` / `run corpus` / `resume` while an existing chain is still
    working through its own queue: entries later in that queue have no
    attempt directory or run record yet and would otherwise look
    "pending" to a second invocation, launching them a second time into
    the same output directory."""
    for launch in state.get("launches", []):
        if is_chain_alive(launch.get("pid")):
            return launch
    return None


def _fql_and_replays_not_done(
    results_root: Path, sha8: str, state_dir: Path,
) -> List[str]:
    """Labels of any FQL seed or the replay entry that is not yet "done"
    (item 5: `pilot` needs these first; `gate` needs them too)."""
    plan = build_plan(results_root, sha8, 1)  # workers irrelevant to these commands
    not_done = []
    for r in plan:
        if r.phase != "fql" and r.label != "replays_ab":
            continue
        if run_status_for_plan_entry(r, state_dir, sha8) != "done":
            not_done.append(r.label)
    return sorted(not_done)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Detached process launching (Windows DETACHED_PROCESS only -- never combined
# with CREATE_NEW_PROCESS_GROUP; see the module docstring)
# =============================================================================

def _detached_creationflags() -> int:
    return getattr(subprocess, "DETACHED_PROCESS", 0)


def _popen_detached(argv: Sequence[str], *, cwd: Path, log_path: Path) -> subprocess.Popen:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(log_path, "ab", buffering=0)
    return subprocess.Popen(
        list(argv),
        cwd=str(cwd),
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        close_fds=True,
        creationflags=_detached_creationflags(),
    )


def _write_chain_spec(
    state_dir: Path, chain_name: str, entries: Sequence[PlannedRun], log_path: Path,
    sha8: Optional[str] = None,
) -> Path:
    spec = {
        "chain": chain_name,
        "cwd": str(_REPO_ROOT),
        "log": str(log_path),
        "state_dir": str(state_dir),
        "sha8": sha8,
        "runs": [
            {"label": r.label, "command": r.command, "output_dir": str(r.output_dir)}
            for r in entries
        ],
    }
    spec_dir = state_dir / "chains"
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_path = spec_dir / f"{chain_name}_{int(time.time())}.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return spec_path


def run_chain(spec_path: Path) -> int:
    """Runs every command in spec_path in order inside THIS process (the
    detached child the launcher spawned), recording each one's PID before
    it starts and its exit code after (item 2: so status detection can
    tell "running" from "crashed"), and stops at the first failure (spec
    section 4: "After a failure there is no automatic retry: fix, re-tag,
    rerun" -- for the GATE; an ordinary crashed RUN is resumed instead,
    item 11). Each child gets `CREATE_NO_WINDOW` (its parent, this
    process, is itself detached and has no console to inherit) and its
    stdout/stderr explicitly redirected to the phase log (item 7). This is
    what `_run-chain` executes."""
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    cwd = spec["cwd"]
    state_dir = Path(spec["state_dir"])
    log_path = Path(spec["log"])
    sha8 = spec.get("sha8")  # absent in specs written before this field existed
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as log_fh:
        def _log(message: str) -> None:
            print(message, file=log_fh, flush=True)

        def _write_record_safely(record: dict) -> None:
            # A record write must never crash the chain itself: a failure
            # here (disk full, a permissions hiccup) is logged and the
            # chain keeps going, still trying the LATER write (the exit
            # record matters most for status detection) rather than
            # aborting a run that is otherwise fine.
            try:
                write_run_record(state_dir, label, record, sha8)
            except OSError as exc:
                _log(f"[v3_corpus_launcher] WARNING: could not write the run record for {label}: {exc}")

        for entry in spec["runs"]:
            label = entry["label"]
            _log(f"[v3_corpus_launcher] {label}: {' '.join(entry['command'])}")
            started_at = _timestamp()
            proc = subprocess.Popen(
                entry["command"], cwd=cwd,
                stdout=log_fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            _write_record_safely({
                "label": label, "output_dir": entry["output_dir"],
                "pid": proc.pid, "started_at": started_at, "returncode": None,
            })
            returncode = proc.wait()
            _write_record_safely({
                "label": label, "output_dir": entry["output_dir"],
                "pid": proc.pid, "started_at": started_at, "returncode": returncode,
                "exited_at": _timestamp(),
            })
            if returncode != 0:
                _log(
                    f"[v3_corpus_launcher] {label} FAILED (exit {returncode}); stopping "
                    f"the chain here. This run crashed: use this launcher's "
                    f"'resume {label}' subcommand to relaunch it from its journal. "
                    f"(Re-tagging and a fresh pilot pair are needed only after a "
                    f"FAILED pilot-gate, not after an ordinary crash.)"
                )
                return returncode
        _log("[v3_corpus_launcher] chain complete.")
    return 0


def _launch_chain_detached(
    state_dir: Path, chain_name: str, entries: Sequence[PlannedRun],
    sha8: Optional[str] = None,
) -> "tuple[subprocess.Popen, Path, Path]":
    log_path = state_dir / "logs" / f"{chain_name}_{int(time.time())}.log"
    spec_path = _write_chain_spec(state_dir, chain_name, entries, log_path, sha8)
    proc = _popen_detached(
        [sys.executable, str(_THIS_FILE), "_run-chain", "--spec", str(spec_path)],
        cwd=_REPO_ROOT, log_path=log_path,
    )
    return proc, spec_path, log_path


# =============================================================================
# Resume helpers
# =============================================================================

def _set_flag(command: List[str], flag: str, value: str) -> List[str]:
    cmd = list(command)
    if flag in cmd:
        cmd[cmd.index(flag) + 1] = value
    else:
        cmd += [flag, value]
    return cmd


def build_resume_command(
    original_command: Sequence[str], *, crashed_dir: Path, new_output: Path, workers: int,
) -> List[str]:
    """The crashed run's own command, with --output redirected to a NEW
    directory, --workers set to this resume's (possibly different) value,
    and --resume-from pointed at the crashed run's directory. Never edits
    or deletes the crashed directory itself."""
    cmd = _set_flag(list(original_command), "--output", str(new_output))
    cmd = _set_flag(cmd, "--workers", str(workers))
    cmd += ["--resume-from", str(crashed_dir)]
    return cmd


# =============================================================================
# Subcommand implementations
# =============================================================================

def cmd_plan(args: argparse.Namespace) -> int:
    results_root = Path(args.results_root)
    state_dir = Path(args.state_dir)
    state = load_state(state_dir)
    sha8 = _resolve_sha8_for_preview(args.tag, _REPO_ROOT)
    if args.workers is not None:
        workers: Union[int, str] = args.workers
    elif state.get("workers") is not None:
        workers = state["workers"]
    else:
        workers = "N (set at the first GPU launch)"
    entries = build_plan(results_root, sha8, workers)

    print(f"[v3_corpus_launcher] plan for sha8={sha8} results_root={results_root} workers={workers}")
    if not args.tag:
        print("[v3_corpus_launcher] no --tag given: sha8 resolved from the current HEAD (preview only).")
    counts: Dict[str, int] = {}
    for run in entries:
        status, uncertain = _status_for_plan_entry(run, state_dir, sha8)
        counts[run.phase] = counts.get(run.phase, 0) + 1
        pid_suffix = ""
        if status in ("running", "crashed"):
            chain = resume_chain_dirs(run.output_dir) if run.is_llm else [run.output_dir]
            record_label = record_label_for_attempt(run.label, len(chain) - 1) if run.is_llm else run.label
            record = read_run_record(state_dir, record_label, sha8)
            if record and record.get("pid"):
                pid_suffix = f" pid={record['pid']}"
        display_status = "running?" if status == "running" and uncertain else status
        print(f"[{run.phase:8s}] [{display_status:7s}]{pid_suffix} {run.label}")
        print(f"             {' '.join(run.command)}")
        print(f"             -> {run.output_dir}")
    print(
        f"[v3_corpus_launcher] {len(entries)} planned runs "
        f"({', '.join(f'{p}={counts.get(p, 0)}' for p in _PHASES)})"
    )
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    results_root = Path(args.results_root)
    state_dir = Path(args.state_dir)
    state = load_state(state_dir)

    assert_correct_interpreter()
    sha8 = preflight_for_tag(args.tag, _REPO_ROOT)

    if args.phase in _GPU_PHASES:
        live = live_chain_launch(state)
        if live is not None:
            raise SystemExit(
                f"refused: a chain is still running (phase {live.get('phase')!r}, "
                f"pid {live.get('pid')}, log {live.get('log')}). Entries later in that "
                f"chain's own queue have no attempt dir yet and would be launched a "
                f"second time. Wait for it to finish, or 'resume' it if it already "
                f"failed, before launching anything else."
            )
        if not args.confirm_gpu:
            raise SystemExit(
                f"refused: phase {args.phase!r} runs real LLM calls against Ollama; "
                f"pass --confirm-gpu after checking nobody else is using the GPU."
            )
        if args.workers is None:
            raise SystemExit(f"refused: phase {args.phase!r} needs --workers N.")
        check_and_record_workers(state, args.workers)
        workers: Union[int, str] = args.workers

        if args.phase == "pilot":
            not_done = _fql_and_replays_not_done(results_root, sha8, state_dir)
            if not_done:
                raise SystemExit(
                    f"refused: these CPU-phase runs are not done yet: {', '.join(not_done)}. "
                    f"Run 'run fql' and 'run replays' first (spec 7.4 orders them before the pilot)."
                )

        if args.phase == "corpus":
            gate = state.get("pilot_gate", {})
            if not (gate.get("passed") and gate.get("sha8") == sha8):
                raise SystemExit(
                    "refused: no PASSED pilot-gate result recorded for this commit yet. "
                    "Run the 'pilot' phase, then 'gate', before 'corpus'."
                )
            recorded = pilot_pair_manifest_workers(results_root, sha8, state_dir)
            if recorded is not None and recorded != args.workers:
                raise SystemExit(
                    f"refused: --workers {args.workers} does not match the pilot pair's own "
                    f"recorded workers ({recorded})."
                )
    else:
        workers = 1  # unused by CPU-phase commands; build_plan needs a value

    all_entries = [r for r in build_plan(results_root, sha8, workers) if r.phase == args.phase]
    if not all_entries:
        raise SystemExit(f"no planned runs for phase {args.phase!r}")

    to_launch: List[PlannedRun] = []
    _SKIP_REASON = {
        "done": "already complete",
        "crashed": "crashed; relaunch it with 'resume' instead",
        "running": "already running (a live process holds its PID)",
    }
    for run in all_entries:
        status = run_status_for_plan_entry(run, state_dir, sha8)
        if status == "pending":
            to_launch.append(run)
        else:
            print(f"[v3_corpus_launcher] skipping {run.label} ({status}): {_SKIP_REASON[status]}")
    if not to_launch:
        print(f"[v3_corpus_launcher] nothing pending for phase {args.phase!r}")
        return 0

    state["tag"] = args.tag
    state["sha8"] = sha8
    state["results_root"] = str(results_root)
    _record_interpreter(state)

    proc, spec_path, log_path = _launch_chain_detached(state_dir, args.phase, to_launch, sha8)
    state.setdefault("launches", []).append({
        "phase": args.phase, "pid": proc.pid, "spec": str(spec_path), "log": str(log_path),
        "started_at": _timestamp(),
    })
    save_state(state_dir, state)

    print(f"[v3_corpus_launcher] launched phase {args.phase!r}: pid={proc.pid} log={log_path}")
    for run in to_launch:
        print(f"  {run.label}: {run.output_dir}")
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    results_root = Path(args.results_root)
    state_dir = Path(args.state_dir)
    state = load_state(state_dir)

    assert_correct_interpreter()
    sha8 = preflight_for_tag(args.tag, _REPO_ROOT)

    live = live_chain_launch(state)
    if live is not None:
        raise SystemExit(
            f"refused: a chain is still running (phase {live.get('phase')!r}, "
            f"pid {live.get('pid')}, log {live.get('log')}). Wait for it to finish "
            f"before resuming anything else."
        )

    if not args.confirm_gpu:
        raise SystemExit("refused: resume launches a real LLM run; pass --confirm-gpu.")
    if args.workers is None:
        raise SystemExit("refused: resume needs --workers N.")
    check_and_record_workers(state, args.workers)
    workers = args.workers

    plan_by_label = {r.label: r for r in build_plan(results_root, sha8, workers)}
    run = plan_by_label.get(args.run_label)
    if run is None:
        raise SystemExit(f"unknown run label {args.run_label!r}; see 'plan' for valid labels.")
    if not run.is_llm:
        raise SystemExit(f"{args.run_label!r} is not an LLM run; only pilot/corpus runs can be resumed.")

    if run.phase == "corpus":
        gate = state.get("pilot_gate", {})
        if not (gate.get("passed") and gate.get("sha8") == sha8):
            raise SystemExit(
                "refused: no PASSED pilot-gate result recorded for this commit yet; "
                "resuming a corpus run needs the same passing gate 'run corpus' needs."
            )

    recorded = pilot_pair_manifest_workers(results_root, sha8, state_dir)
    if recorded is not None and recorded != workers:
        raise SystemExit(
            f"refused: --workers {workers} does not match the pilot pair's own "
            f"recorded workers ({recorded})."
        )

    # Item 2(d): resume from the LATEST attempt that actually has a
    # journal, never blindly the highest-numbered _resumeN dir -- an empty
    # _resumeN (a resume that died at startup, before writing anything)
    # must not hide an earlier, genuinely crashed attempt. The NEW
    # output dir's suffix still follows the highest EXISTING attempt
    # (never reusing or colliding with an empty dir's own number), and the
    # base dir is never relaunched -- a new _resumeN is always created.
    all_attempts = resume_chain_dirs(run.output_dir)
    next_index = len(all_attempts)
    journaled = journaled_attempt_dirs(run.output_dir)
    if not journaled:
        raise SystemExit(
            f"refused: {args.run_label!r} has no journal in any attempt "
            f"(base or any _resumeN); nothing to resume from."
        )
    resume_from_dir = journaled[-1]
    resume_from_index = all_attempts.index(resume_from_dir)
    record_label = record_label_for_attempt(run.label, resume_from_index)
    record = read_run_record(state_dir, record_label, sha8)
    status = run_status_for_dir(resume_from_dir, is_llm=True, record=record)
    if status != "crashed":
        raise SystemExit(
            f"refused: {args.run_label!r} (latest journaled attempt {resume_from_dir.name}) "
            f"is {status!r}, not crashed; nothing to resume."
        )

    new_output = run.output_dir.parent / f"{run.output_dir.name}_resume{next_index}"
    resume_cmd = build_resume_command(
        run.command, crashed_dir=resume_from_dir, new_output=new_output, workers=workers,
    )
    # This attempt's own label doubles as its run-record key (item 4(a)):
    # record_label_for_attempt(run.label, next_index) == this string.
    resume_run = PlannedRun(f"{args.run_label}_resume{next_index}", run.phase, resume_cmd, new_output, True)

    state["tag"] = args.tag
    state["sha8"] = sha8
    state["results_root"] = str(results_root)
    _record_interpreter(state)

    proc, spec_path, log_path = _launch_chain_detached(
        state_dir, f"resume_{args.run_label}_{next_index}", [resume_run], sha8,
    )
    state.setdefault("launches", []).append({
        "phase": f"resume:{args.run_label}", "pid": proc.pid, "spec": str(spec_path), "log": str(log_path),
        "started_at": _timestamp(),
    })
    save_state(state_dir, state)

    print(f"[v3_corpus_launcher] resuming {args.run_label!r} from {resume_from_dir} (untouched)")
    print(f"  -> {new_output}  pid={proc.pid}  log={log_path}")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    results_root = Path(args.results_root)
    state_dir = Path(args.state_dir)
    state = load_state(state_dir)

    assert_correct_interpreter()
    tag = args.tag or state.get("tag")
    if not tag:
        raise SystemExit("refused: no --tag given and none recorded yet in the state file.")
    sha8 = preflight_for_tag(tag, _REPO_ROOT)

    entries = {r.label: r for r in build_plan(results_root, sha8, 1)}
    # Item 3: pass the LATEST DONE attempt (e.g. a resumed "..._resume1")
    # to p5c-sample and pilot-gate, never the crashed base dir, even when
    # the pilot run only finished after being resumed once.
    strict42 = latest_done_attempt_dir(
        entries["pilot_strict_42"].output_dir, state_dir, "pilot_strict_42", True, sha8,
    )
    disabled42 = latest_done_attempt_dir(
        entries["pilot_disabled_42"].output_dir, state_dir, "pilot_disabled_42", True, sha8,
    )
    if strict42 is None:
        raise SystemExit(
            f"refused: pilot_strict_42 ({entries['pilot_strict_42'].output_dir}) is not done yet "
            f"(checked its resume chain too); run the 'pilot' phase first."
        )
    if disabled42 is None:
        raise SystemExit(
            f"refused: pilot_disabled_42 ({entries['pilot_disabled_42'].output_dir}) is not done yet "
            f"(checked its resume chain too); run the 'pilot' phase first."
        )

    not_done = _fql_and_replays_not_done(results_root, sha8, state_dir)
    if not_done:
        raise SystemExit(
            f"refused: these CPU-phase runs are not done yet: {', '.join(not_done)}. "
            f"Run 'run fql' and 'run replays' first (spec 7.4 orders them before the pilot)."
        )

    fql_entries = [r for r in entries.values() if r.phase == "fql"]
    replay_entry = entries["replays_ab"]

    p5c_dir = results_root / f"v3_pilot_p5c_{sha8}"
    p5c_cmd = [
        _PYTHON, "examples/irrigation_abm/analysis/v3_metrics.py", "p5c-sample",
        "--runs", str(strict42), str(disabled42), "--out", str(p5c_dir),
    ]
    print(f"[v3_corpus_launcher] {' '.join(p5c_cmd)}")
    subprocess.run(p5c_cmd, cwd=_REPO_ROOT, check=True)

    review_path = Path(args.p5c_review) if args.p5c_review else (p5c_dir / "p5c_review.json")
    if not review_path.is_file():
        print(
            f"[v3_corpus_launcher] P5(c) human review record needed: a reviewer who did not "
            f"write this code must fill in {p5c_dir / 'p5c_review_template.json'} "
            f"(reviewer, reviewer_wrote_code, and sentences_without_source per sampled prompt) "
            f"and save the filled copy as {review_path} (or pass its path via --p5c-review), "
            f"then rerun 'gate'. Running the gate now without it."
        )

    fql_dirs = [str(r.output_dir) for r in fql_entries]
    gate_out = results_root / f"v3_pilot_gate_{sha8}"
    gate_cmd = [
        _PYTHON, "examples/irrigation_abm/analysis/v3_metrics.py", "pilot-gate",
        "--runs", str(strict42), str(disabled42),
        "--fql", *fql_dirs,
        "--replays", str(replay_entry.output_dir),
        "--out", str(gate_out),
    ]
    if review_path.is_file():
        gate_cmd += ["--p5c-review", str(review_path)]
    print(f"[v3_corpus_launcher] {' '.join(gate_cmd)}")
    result = subprocess.run(gate_cmd, cwd=_REPO_ROOT)
    passed = result.returncode == 0

    state["tag"] = tag
    state["sha8"] = sha8
    state["results_root"] = str(results_root)
    _record_interpreter(state)
    state["pilot_gate"] = {
        "passed": passed,
        "exit_code": result.returncode,
        "sha8": sha8,
        "results_root": str(results_root),
        "timestamp": _timestamp(),
        "report": str(gate_out / "v3_pilot_gate_report.json"),
        "p5c_review_used": str(review_path) if review_path.is_file() else None,
    }
    save_state(state_dir, state)

    print(f"[v3_corpus_launcher] pilot gate {'PASSED' if passed else 'FAILED'} (exit {result.returncode})")
    return 0 if passed else 1


def cmd_run_chain(args: argparse.Namespace) -> int:
    return run_chain(Path(args.spec))


# =============================================================================
# CLI
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch orchestrator for the irrigation v3 corpus (spec WP7 Launch).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="print the full ordered run list, commands, output dirs and status")
    p_plan.add_argument("--tag", default=None, help="resolve output-dir sha8 from this tag (default: current HEAD)")
    p_plan.add_argument("--workers", type=int, default=None,
                         help="shown in LLM command lines (default: the recorded value, or a placeholder)")
    p_plan.add_argument("--results-root", default=str(_DEFAULT_RESULTS_ROOT))
    p_plan.add_argument("--state-dir", default=str(_DEFAULT_STATE_DIR))

    p_run = sub.add_parser("run", help="launch one phase's PENDING runs, chained in one detached process")
    p_run.add_argument("phase", choices=_PHASES)
    p_run.add_argument("--tag", required=True, help="HEAD must equal this tag's commit; tree must be clean")
    p_run.add_argument("--workers", type=int, default=None, help="required for pilot/corpus")
    p_run.add_argument("--confirm-gpu", action="store_true", help="required for pilot/corpus")
    p_run.add_argument("--results-root", default=str(_DEFAULT_RESULTS_ROOT))
    p_run.add_argument("--state-dir", default=str(_DEFAULT_STATE_DIR))

    p_resume = sub.add_parser(
        "resume", help="relaunch the LATEST crashed attempt of one LLM run, into the next _resumeN dir",
    )
    p_resume.add_argument("run_label", help="a label from 'plan', e.g. strict_43 or pilot_disabled_42")
    p_resume.add_argument("--tag", required=True)
    p_resume.add_argument("--workers", type=int, default=None, required=False)
    p_resume.add_argument("--confirm-gpu", action="store_true")
    p_resume.add_argument("--results-root", default=str(_DEFAULT_RESULTS_ROOT))
    p_resume.add_argument("--state-dir", default=str(_DEFAULT_STATE_DIR))

    p_gate = sub.add_parser("gate", help="p5c-sample then pilot-gate on the pilot pair; records pass/fail")
    p_gate.add_argument("--tag", default=None, help="default: the tag recorded by the last GPU launch")
    p_gate.add_argument("--p5c-review", default=None, help="the filled-in P5(c) review record")
    p_gate.add_argument("--results-root", default=str(_DEFAULT_RESULTS_ROOT))
    p_gate.add_argument("--state-dir", default=str(_DEFAULT_STATE_DIR))

    # Internal: the entry point the detached process itself runs. Hidden
    # from --help; never invoked directly by a user.
    p_chain = sub.add_parser("_run-chain", help=argparse.SUPPRESS)
    p_chain.add_argument("--spec", required=True)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "plan":
        return cmd_plan(args)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "resume":
        return cmd_resume(args)
    if args.command == "gate":
        return cmd_gate(args)
    if args.command == "_run-chain":
        return cmd_run_chain(args)
    raise SystemExit(f"unknown command {args.command!r}")


if __name__ == "__main__":
    sys.exit(main())
