"""Tests for examples/irrigation_abm/run_experiment.py's
``--retry-feedback-mode`` CLI flag (added 2026-09-27), replacing the earlier
``config_variants/silent_gemma3_4b/`` full-config-copy approach (removed the
same day -- a plain file copy silently drifted out of parity with
``config/`` once already, during the supply-side redesign). Mirrors
``examples/single_agent/run_flood.py``'s flag of the same name.

``broker/tests/test_retry_feedback_silent.py`` already covers the mode's own
retry-loop BEHAVIOR (prompt content under each mode) end to end, including a
real ``SkillBrokerEngine`` for both domains -- that file is domain-agnostic
and is left unchanged. This file covers only the CLI WIRING three things
that file does not:

(a) omitting the flag leaves the resolved governance config byte-identical
    to main's un-flagged default (``full``, read straight off the on-disk
    ``agent_types.yaml``, which declares no ``retry_feedback_mode`` key);
(b)/(c) ``--retry-feedback-mode {silent,placebo}`` sets the ENGINE's runtime
    attribute (``RetryMixin._governance_retry_loop`` reads
    ``self._retry_feedback_mode`` at every retry call, not just once at
    construction) and is recorded in both ``reproducibility_manifest.json``
    and ``config_snapshot.yaml`` -- the SAME generic broker mechanism
    ``run_flood.py``'s flag already relies on
    (``ExperimentRunner._finalize_experiment`` /
    ``_collect_reproducibility_metadata`` read ``runner.broker.
    _retry_feedback_mode`` generically, domain-agnostic), so no
    irrigation-specific manifest patch was needed to wire this up (unlike
    ``--paper-water-margin``, which has no generic-framework home and needs
    ``_record_paper_water_margin_provenance``).

``TestRetryFeedbackModeFlagResolvedValue`` reuses
``test_governance_mode_wiring.py``'s ``_StopBeforeRun``-at-``build()``
pattern, but one step LATER: the CLI override is applied AFTER
``ExperimentBuilder.build()`` returns (same hook point as
``runner.broker._derived_from_config`` for ``--coupling``), so a fixture
that aborts as early as ``build()`` itself would never see it. Stubbing
``ExperimentRunner.run`` instead lets the real broker/engine construct
fully -- override included -- while still doing zero LLM calls.
``TestRetryFeedbackModeManifestRecording`` then runs a real (small, mock
model) subprocess for the two things that only exist after
``_finalize_experiment`` actually writes them, the same pattern
``test_coupling.py``'s manifest tests use for ``--coupling``.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RUN_EXPERIMENT = PROJECT_ROOT / "examples" / "irrigation_abm" / "run_experiment.py"
CONFIG_DIR = PROJECT_ROOT / "examples" / "irrigation_abm" / "config"


class _StopBeforeExecute(Exception):
    """Raised by a monkeypatched ``ExperimentRunner.run`` to abort ``main()``
    right after the runner + broker are fully constructed and the
    ``--retry-feedback-mode`` override (if any) has already been applied
    (``run_experiment.py`` applies it immediately after ``builder.build()``,
    before calling ``runner.run()``), but before any LLM call or governance
    decision executes. Unlike ``test_governance_mode_wiring.py``'s
    ``_StopBeforeRun`` (which aborts INSIDE ``ExperimentBuilder.build()``,
    before the broker exists), this aborts one step later -- the override
    needs the real broker object to already exist.
    """


@pytest.fixture
def captured_runner(monkeypatch):
    from broker.core.experiment_runner import ExperimentRunner
    from broker.utils.llm_utils import LLM_CONFIG

    # Same leak guard as test_governance_mode_wiring.py's captured_build:
    # main() calls apply_to_llm_config(), which mutates this module-level
    # singleton and never restores it.
    monkeypatch.setattr(LLM_CONFIG, "num_ctx", LLM_CONFIG.num_ctx)
    monkeypatch.setattr(LLM_CONFIG, "num_predict", LLM_CONFIG.num_predict)

    captured: dict = {}

    def fake_run(self, llm_invoke=None):
        captured["runner"] = self
        captured["broker"] = self.broker
        raise _StopBeforeExecute()

    monkeypatch.setattr(ExperimentRunner, "run", fake_run)
    return captured


def _run_main_with_retry_feedback_mode(tmp_path, mode):
    from examples.irrigation_abm.run_experiment import main

    argv = [
        "run_experiment.py",
        "--model", "mock",
        "--years", "1",
        "--agents", "2",
        "--seed", "42",
        "--workers", "1",
        "--governance-mode", "strict",
        "--output", str(tmp_path / f"rfm_{mode or 'default'}"),
    ]
    if mode is not None:
        argv += ["--retry-feedback-mode", mode]
    old_argv = sys.argv
    sys.argv = argv
    try:
        with pytest.raises(_StopBeforeExecute):
            main()
    finally:
        sys.argv = old_argv


class TestRetryFeedbackModeFlagResolvedValue:
    """Fast in-process checks of the ENGINE-level resolved value (no LLM
    call, no manifest write yet -- ExperimentRunner.run is stubbed out
    before it ever reaches _finalize_experiment)."""

    def test_flag_omitted_matches_main_default(self, tmp_path, captured_runner):
        _run_main_with_retry_feedback_mode(tmp_path, None)
        broker = captured_runner["broker"]
        # Same default AgentTypeConfig.get_governance_retry_feedback_mode()
        # resolves to when agent_types.yaml declares no retry_feedback_mode
        # key at all -- i.e. exactly what an unflagged main() run has always
        # produced, unchanged by this CLI addition. SkillBrokerEngine.
        # __init__ always calls set_retry_feedback_mode (opus review,
        # 2026-09-27), so the attribute is always set directly; no getattr
        # fallback needed here.
        assert broker._retry_feedback_mode == "full"
        with open(CONFIG_DIR / "agent_types.yaml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        assert "retry_feedback_mode" not in cfg.get("global_config", {}).get("governance", {})

    def test_flag_silent_sets_engine_attribute(self, tmp_path, captured_runner):
        _run_main_with_retry_feedback_mode(tmp_path, "silent")
        assert captured_runner["broker"]._retry_feedback_mode == "silent"

    def test_flag_placebo_sets_engine_attribute(self, tmp_path, captured_runner):
        _run_main_with_retry_feedback_mode(tmp_path, "placebo")
        assert captured_runner["broker"]._retry_feedback_mode == "placebo"

    def test_flag_never_mutates_resolved_config_object(self, tmp_path, captured_runner):
        """The override lives on the broker RUNTIME ATTRIBUTE only -- the
        AgentTypeConfig resolved from the on-disk (unmutated)
        agent_types.yaml must stay 'full' even while the override is
        'silent'. This is what makes the flag safe to omit by default: a
        --config-dir-free CLI override never edits the frozen paper config,
        unlike the old config_variants/ copy-with-one-line-changed
        approach."""
        _run_main_with_retry_feedback_mode(tmp_path, "silent")
        broker = captured_runner["broker"]
        assert broker.config.get_governance_retry_feedback_mode() == "full"
        assert broker._retry_feedback_mode == "silent"


def _run_subprocess(output_dir: Path, mode: str = None, timeout: int = 90):
    args = [
        sys.executable, str(RUN_EXPERIMENT),
        "--model", "mock", "--agents", "2", "--years", "1", "--seed", "42",
        "--workers", "1", "--governance-mode", "strict",
        "--output", str(output_dir),
    ]
    if mode is not None:
        args += ["--retry-feedback-mode", mode]
    result = subprocess.run(
        args, cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=timeout,
    )
    assert result.returncode == 0, (
        f"run_experiment.py failed (mode={mode}):\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    return result


class TestRetryFeedbackModeManifestRecording:
    """End-to-end (real mock-model subprocess run, real
    ExperimentRunner._finalize_experiment) checks that the resolved mode
    reaches both provenance files -- slower than the captured_runner tests
    above but exercises the actual write path test_coupling.py's manifest
    tests use for --coupling."""

    def test_flag_omitted_manifest_records_full(self, tmp_path):
        out = tmp_path / "rfm_default"
        _run_subprocess(out, mode=None)
        manifest = json.loads((out / "reproducibility_manifest.json").read_text(encoding="utf-8"))
        assert manifest.get("retry_feedback_mode") == "full"
        snapshot = yaml.safe_load((out / "config_snapshot.yaml").read_text(encoding="utf-8"))
        assert snapshot.get("metadata", {}).get("retry_feedback_mode") == "full"

    def test_flag_silent_manifest_records_silent(self, tmp_path):
        out = tmp_path / "rfm_silent"
        _run_subprocess(out, mode="silent")
        manifest = json.loads((out / "reproducibility_manifest.json").read_text(encoding="utf-8"))
        assert manifest.get("retry_feedback_mode") == "silent"
        snapshot = yaml.safe_load((out / "config_snapshot.yaml").read_text(encoding="utf-8"))
        assert snapshot.get("metadata", {}).get("retry_feedback_mode") == "silent"

    def test_flag_placebo_manifest_records_placebo(self, tmp_path):
        out = tmp_path / "rfm_placebo"
        _run_subprocess(out, mode="placebo")
        manifest = json.loads((out / "reproducibility_manifest.json").read_text(encoding="utf-8"))
        assert manifest.get("retry_feedback_mode") == "placebo"
        snapshot = yaml.safe_load((out / "config_snapshot.yaml").read_text(encoding="utf-8"))
        assert snapshot.get("metadata", {}).get("retry_feedback_mode") == "placebo"
