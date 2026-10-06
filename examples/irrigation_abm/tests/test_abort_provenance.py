"""Regression test for spec item 24 fix round CRITICAL-1.

``examples/irrigation_abm/run_experiment.py``'s ``main()`` must not lose its
post-run provenance patches or ``simulation_log.csv`` when ``runner.run()``
raises ``LLMFailureRateAborted`` (the LLM safeguard, spec item 24, on by
default for this domain).

Pre-fix, the four ``_record_*_provenance`` calls, the explicit audit
``finalize()``, and the ``simulation_log.csv`` save all ran only AFTER
``runner.run()`` returned -- an abort skipped every one of them, including
``_record_hold_requests_fixed_provenance``, whose key every manifest must
carry (``main()`` itself asserts ``hold_requests_fixed is False`` right
before the run starts). The fix wraps ``runner.run(...)`` in ``try/finally``
so these always run, then lets the exception propagate.

No live Ollama contact, per the fix-round instruction: ``create_llm_invoke``
is monkeypatched to a stand-in that always raises ``OSError`` -- a
zero-network transport failure -- and the safeguard's own config is
monkeypatched to small, fast-tripping values so the test does not wait
through the real irrigation config's 62s backoff schedule (5 retries,
2-4-8-16-32s) or its 25-failure abort window.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from broker.utils.llm_safeguard import LLMFailureRateAborted


def _always_transport_fails(model, verbose=False, overrides=None):
    """Stand-in for ``create_llm_invoke``: returns a callable that always
    raises ``OSError`` -- the one exception type the backoff wrapper treats
    as a retryable transport failure -- without ever touching a socket."""
    def invoke(prompt, *args, **kwargs):
        raise OSError("stubbed transport failure: no live Ollama contact in this test")
    return invoke


def _succeeds_then_fails(succeed_calls: int):
    """Stand-in for ``create_llm_invoke``: mimics the framework's own
    built-in mock model (a bare ``{"decision": 1}`` JSON, parses fine, always
    ``success=True``) for the first ``succeed_calls`` raw calls, THEN always
    raises ``OSError``. ``succeed_calls`` is set generously above one full
    year's worst-case call budget (format retries + governance retries, per
    agent), so year 1 completes -- and its ``post_year`` hook populates
    ``hooks.logs`` -- before the persistent failures start in a later year.
    No live Ollama contact either way: the "success" path never leaves this
    process."""
    import json as _json

    from broker.utils.llm_utils import LLMStats

    state = {"n": 0}

    def factory(model, verbose=False, overrides=None):
        def invoke(prompt, *args, **kwargs):
            state["n"] += 1
            if state["n"] <= succeed_calls:
                return _json.dumps({"decision": 1}), LLMStats(retries=0, success=True)
            raise OSError("stubbed transport failure: no live Ollama contact in this test")
        return invoke

    return factory


@pytest.fixture
def fast_tripping_safeguard(monkeypatch):
    """Override the resolved safeguard config to trip on the FIRST failing
    decision with at most ~1s of real sleep, instead of irrigation's real
    25-failure / 62s-backoff schedule (abort_window=50, abort_threshold=0.5,
    backoff_max_retries=5, backoff_initial_seconds=2)."""
    from broker.utils.agent_config import AgentTypeConfig

    monkeypatch.setattr(
        AgentTypeConfig, "get_llm_safeguard_config",
        lambda self: {
            "enabled": True, "backoff_max_retries": 1,
            "backoff_initial_seconds": 1, "backoff_max_seconds": 1,
            "abort_window": 1, "abort_threshold": 1.0,
        },
    )
    monkeypatch.setattr(
        "broker.utils.llm_utils.create_llm_invoke", _always_transport_fails,
    )


def _run_main_expecting_abort(tmp_path: Path, monkeypatch) -> None:
    from examples.irrigation_abm.run_experiment import main

    argv = [
        "run_experiment.py",
        "--model", "mock",
        "--years", "3",
        "--agents", "3",
        "--seed", "42",
        "--workers", "1",
        "--output", str(tmp_path),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(LLMFailureRateAborted):
        main()


class TestAbortPreservesProvenanceAndSimulationLog:
    """Every assertion here fails on the pre-fix code: without the
    try/finally, runner.run() raising means main() returns via the
    exception immediately after that call, and NONE of these files or
    keys -- other than what ExperimentRunner._finalize_experiment itself
    (inside run()'s own finally) already writes -- would exist."""

    def test_manifest_carries_hold_requests_fixed_and_run_status(
        self, tmp_path, monkeypatch, fast_tripping_safeguard,
    ):
        _run_main_expecting_abort(tmp_path, monkeypatch)
        manifest = json.loads((tmp_path / "reproducibility_manifest.json").read_text())
        # Written by ExperimentRunner._finalize_experiment (already fixed in
        # the prior round) -- sanity-checks the fixture actually aborted.
        assert manifest["run_status"] == "aborted_llm_failure_rate"
        # Written by main()'s OWN post-run provenance patches -- the part
        # THIS fix adds. hold_requests_fixed is unconditional (not gated on
        # --real), and main() asserts it False before the run even starts.
        assert "hold_requests_fixed" in manifest
        assert manifest["hold_requests_fixed"] is False

    def test_manifest_carries_all_four_provenance_patches(
        self, tmp_path, monkeypatch, fast_tripping_safeguard,
    ):
        _run_main_expecting_abort(tmp_path, monkeypatch)
        manifest = json.loads((tmp_path / "reproducibility_manifest.json").read_text())
        for key in (
            "paper_water_margin", "paper_water_margin_applied",
            "cluster_method", "cluster_method_applied",
            "step_bin_source", "step_bin_source_applied",
            "hold_requests_fixed",
        ):
            assert key in manifest, f"{key} missing from manifest on an aborted run"

    def test_manifest_carries_water_system_config_provenance_on_abort(
        self, tmp_path, monkeypatch, fast_tripping_safeguard,
    ):
        """Re-review 2026-09-29 round 4 (MEDIUM 4; spec items 25-27):
        ``_record_water_system_config_provenance`` is called in the SAME
        try/finally block as ``_record_hold_requests_fixed_provenance``
        (added alongside it, same call site) -- fails on the pre-fix code,
        where this function does not exist at all, on EITHER a normal or
        an aborted run, not only on abort."""
        _run_main_expecting_abort(tmp_path, monkeypatch)
        manifest = json.loads((tmp_path / "reproducibility_manifest.json").read_text())
        assert manifest["run_status"] == "aborted_llm_failure_rate"
        assert manifest["powell_release_mode"] == "ig2007_tiers"
        # Item 36c (2026-10-05): the default is "extend_slope", not
        # "hold_2026" (now the SI sensitivity).
        assert manifest["powell_post2026_equalization"] == "extend_slope"
        assert manifest["lb_non_ag_total_maf"] == pytest.approx(5.2)

    def test_simulation_log_csv_written_on_abort_after_a_complete_year(
        self, tmp_path, monkeypatch,
    ):
        """hooks.logs is populated ONCE PER YEAR (a post_year hook logs every
        agent after that year's decisions are all in) -- NOT per decision --
        so proving the fix needs year 1 to fully complete before the abort
        trips in a later year. Uses _succeeds_then_fails instead of the
        fast_tripping_safeguard fixture's always-fails stub for exactly that
        reason."""
        from broker.utils.agent_config import AgentTypeConfig

        monkeypatch.setattr(
            AgentTypeConfig, "get_llm_safeguard_config",
            lambda self: {
                "enabled": True, "backoff_max_retries": 1,
                "backoff_initial_seconds": 1, "backoff_max_seconds": 1,
                "abort_window": 1, "abort_threshold": 1.0,
            },
        )
        # One year (3 agents) needs at most ~6 raw calls each (3 format-retry
        # attempts x up to 2x for a further governance-retry round) = ~18;
        # 25 comfortably covers year 1's worst case while staying well under
        # two years' worth (~36), so year 2 is where the failures start.
        monkeypatch.setattr(
            "broker.utils.llm_utils.create_llm_invoke",
            _succeeds_then_fails(succeed_calls=25),
        )
        _run_main_expecting_abort(tmp_path, monkeypatch)

        csv_path = tmp_path / "simulation_log.csv"
        assert csv_path.exists(), (
            "simulation_log.csv must be written from main()'s finally block "
            "even though runner.run() raised, once at least one year of "
            "hooks.logs exists to save"
        )
        assert len(csv_path.read_text().strip().splitlines()) > 1, (
            "simulation_log.csv must have a header plus at least year 1's "
            "agent rows, not just an empty file"
        )


class TestGenericExceptionRecordsAbortedExceptionRunStatus:
    """Opus review of WP7 launcher, item 3(a): ``run()``'s try block only
    special-cased two exception families (``LLMFailureRateAborted``, the
    crash-resume journal's ``JournalReplayDivergence`` / ``JournalWriteError``).
    Anything else escaping the loop (a hook bug, a provider error neither of
    those two catch) used to reach ``finally`` with neither
    ``_llm_safeguard_abort`` nor ``_llm_journal_abort`` set, so
    ``_finalize_experiment``'s manifest build added no ``run_status`` key at
    all -- indistinguishable from a normal completion that merely covered
    fewer years than configured. Fixed with a third, generic
    ``except Exception as exc`` clause that stashes ``self._generic_abort``
    before re-raising, read by `_finalize_experiment` the same way.

    ``ExperimentRunner._call_hook`` is monkeypatched directly (domain-
    agnostic: every runner calls ``self._call_hook(name, *args)`` from
    inside ``run()``'s own try block, and ``_call_hook``'s own documented
    job is to log and RE-RAISE a hook exception, never swallow it) to
    raise a plain ``RuntimeError`` on its very first call -- a stand-in for
    "some exception neither of the two special-cased families" that needs
    no real Ollama contact and no safeguard/journal configuration."""

    def test_generic_exception_sets_aborted_exception_run_status(self, tmp_path, monkeypatch):
        from broker.core.experiment_runner import ExperimentRunner
        from examples.irrigation_abm.run_experiment import main

        def _raising_call_hook(self, name, *args):
            raise RuntimeError("stubbed hook failure: no live Ollama contact in this test")

        monkeypatch.setattr(ExperimentRunner, "_call_hook", _raising_call_hook)

        argv = [
            "run_experiment.py", "--model", "mock", "--years", "3", "--agents", "3",
            "--seed", "42", "--workers", "1", "--output", str(tmp_path),
        ]
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(RuntimeError, match="stubbed hook failure"):
            main()

        manifest = json.loads((tmp_path / "reproducibility_manifest.json").read_text())
        assert manifest["run_status"] == "aborted_exception"
        assert manifest["aborted_exception_type"] == "RuntimeError"
        assert "stubbed hook failure" in manifest["aborted_exception_message"]
        # Mutually exclusive with the other two abort families on this run.
        assert "llm_safeguard_abort" not in manifest
        assert "llm_journal_abort" not in manifest


class TestNormalRunKeepsExactlyItsKeys:
    """Companion regression to the class above: a run that raises NOTHING
    must come out of _finalize_experiment with no run_status key at all
    (absent, not null) and none of the three abort-detail keys -- proving
    the new generic except clause adds nothing on the ordinary path."""

    def test_clean_run_has_no_run_status_or_abort_keys(self, tmp_path, monkeypatch):
        from examples.irrigation_abm.run_experiment import main

        argv = [
            "run_experiment.py", "--model", "mock", "--years", "2", "--agents", "3",
            "--seed", "42", "--workers", "1", "--output", str(tmp_path),
        ]
        monkeypatch.setattr(sys, "argv", argv)
        main()

        manifest = json.loads((tmp_path / "reproducibility_manifest.json").read_text())
        for key in (
            "run_status", "aborted_exception_type", "aborted_exception_message",
            "llm_safeguard_abort", "llm_journal_abort",
        ):
            assert key not in manifest, f"{key!r} must be absent on a clean completion"
