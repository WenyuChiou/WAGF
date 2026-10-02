"""Tests for the generic LLM-failure safeguard (spec item 24, audit gap F42).

``.research/design_specs/irrigation_v3_spec_2026-09-28.md`` item 24 (PI
approved 2026-09-29, "extra insurance" before the corpus launch): backoff on
a transient LLM provider-call failure, and an abort-rate stop that ends a
run cleanly once too many recent decisions failed. Both live in
``broker/utils/llm_safeguard.py`` and are OFF by default, so every domain
that never sets ``global_config.llm_safeguard`` is byte-identical -- see
``TestEngineAbortIntegration.test_disabled_never_aborts_even_when_every_call_is_unparsable``
and ``TestConfigValidation.test_absent_block_is_all_disabled_defaults`` for
the two most direct regression pins of that claim.

Four groups, each pinning one line of the task's TESTS requirement:
- ``TestConfigValidation`` / ``TestAgentTypeConfigGetter`` -- config validation.
- ``TestBackoffWrapper`` -- "a mock provider that fails twice and then
  succeeds: backoff is used and the decision succeeds."
- ``TestEngineAbortIntegration`` / ``TestRunAbortsCleanlyAndRecordsTheManifest``
  -- "a mock provider that always fails, or always returns unparseable
  text: the run aborts once the window fills ... the manifest records it,
  and the traces are flushed."
- Every class with "disabled" in its name -- "disabled means no behaviour
  change."
"""
from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from broker.utils.llm_safeguard import (
    LLMAbortTracker,
    LLMFailureRateAborted,
    LLMSafeguardConfig,
    LLMSafeguardConfigError,
    validate_llm_safeguard_dict,
    wrap_llm_invoke_with_backoff,
)
from broker.utils.llm_utils import LLMStats


def _enabled_config(**overrides) -> LLMSafeguardConfig:
    base = dict(
        enabled=True, backoff_max_retries=3, backoff_initial_seconds=1,
        backoff_max_seconds=60, abort_window=50, abort_threshold=0.5,
    )
    base.update(overrides)
    return LLMSafeguardConfig(**base)


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

class TestConfigValidation:
    def test_absent_block_is_all_disabled_defaults(self):
        cfg = validate_llm_safeguard_dict(None)
        assert cfg == {
            "enabled": False, "backoff_max_retries": 3,
            "backoff_initial_seconds": 2, "backoff_max_seconds": 60,
            "abort_window": 50, "abort_threshold": 0.5,
        }

    def test_valid_block_round_trips_unchanged(self):
        raw = {
            "enabled": True, "backoff_max_retries": 5,
            "backoff_initial_seconds": 1, "backoff_max_seconds": 30,
            "abort_window": 10, "abort_threshold": 0.25,
        }
        assert validate_llm_safeguard_dict(raw) == raw

    def test_partial_block_fills_in_the_rest_from_defaults(self):
        cfg = validate_llm_safeguard_dict({"enabled": True})
        assert cfg["enabled"] is True
        assert cfg["backoff_max_retries"] == 3
        assert cfg["backoff_max_seconds"] == 60
        assert cfg["abort_window"] == 50

    @pytest.mark.parametrize("bad", [-0.1, 1.1, 2, -1, "0.5", 0, 0.0])
    def test_threshold_out_of_unit_interval_or_wrong_type_raises(self, bad):
        """(0, 1] fix round: 0 is now rejected too (WARNING 6) -- a zero
        threshold trips on the very first decision, which is never what
        "abort on failures" is meant to express."""
        with pytest.raises(LLMSafeguardConfigError):
            validate_llm_safeguard_dict({"abort_threshold": bad})

    def test_threshold_just_above_zero_is_allowed(self):
        assert validate_llm_safeguard_dict({"abort_threshold": 0.0001})["abort_threshold"] == 0.0001

    def test_threshold_one_is_allowed(self):
        assert validate_llm_safeguard_dict({"abort_threshold": 1.0})["abort_threshold"] == 1.0

    @pytest.mark.parametrize("key", [
        "backoff_max_retries", "backoff_initial_seconds",
        "backoff_max_seconds", "abort_window",
    ])
    @pytest.mark.parametrize("bad", [0, -1, 1.5, "3", True])
    def test_counts_must_be_positive_integers(self, key, bad):
        with pytest.raises(LLMSafeguardConfigError):
            validate_llm_safeguard_dict({key: bad})

    @pytest.mark.parametrize("value", [1, 5, 8])
    def test_backoff_max_retries_up_to_eight_is_allowed(self, value):
        assert validate_llm_safeguard_dict(
            {"backoff_max_retries": value})["backoff_max_retries"] == value

    @pytest.mark.parametrize("value", [9, 10, 100])
    def test_backoff_max_retries_above_eight_is_rejected(self, value):
        """WARNING 7 fix round: an operator typo of one extra zero must not
        turn into dozens of attempts against a dead endpoint."""
        with pytest.raises(LLMSafeguardConfigError):
            validate_llm_safeguard_dict({"backoff_max_retries": value})

    def test_backoff_max_seconds_default_is_sixty(self):
        assert validate_llm_safeguard_dict(None)["backoff_max_seconds"] == 60

    def test_enabled_must_be_a_real_bool_not_a_truthy_value(self):
        with pytest.raises(LLMSafeguardConfigError):
            validate_llm_safeguard_dict({"enabled": 1})

    def test_non_mapping_block_raises(self):
        with pytest.raises(LLMSafeguardConfigError):
            validate_llm_safeguard_dict("yes")

    def test_unknown_key_raises(self):
        with pytest.raises(LLMSafeguardConfigError):
            validate_llm_safeguard_dict({"abort_windo": 10})

    def test_llm_safeguard_config_error_is_a_value_error(self):
        # AgentTypeConfig's other governance getters raise plain ValueError;
        # this stays catchable the same way.
        assert issubclass(LLMSafeguardConfigError, ValueError)

    def test_from_dict_validates_too(self):
        with pytest.raises(LLMSafeguardConfigError):
            LLMSafeguardConfig.from_dict({"abort_threshold": 5})

    def test_from_dict_none_is_the_disabled_default(self):
        assert LLMSafeguardConfig.from_dict(None) == LLMSafeguardConfig()


class TestAgentTypeConfigGetter:
    """The YAML-facing surface: ``AgentTypeConfig.get_llm_safeguard_config()``."""

    @staticmethod
    def _cfg(llm_safeguard=None):
        from broker.utils.agent_config import AgentTypeConfig

        cfg = AgentTypeConfig.__new__(AgentTypeConfig)
        block = {"llm_safeguard": llm_safeguard} if llm_safeguard is not None else {}
        cfg._config = {"global_config": block}
        return cfg

    def test_absent_block_reads_disabled(self):
        assert self._cfg().get_llm_safeguard_config()["enabled"] is False

    def test_malformed_block_raises_from_the_getter(self):
        cfg = self._cfg(llm_safeguard={"abort_threshold": 5})
        with pytest.raises(LLMSafeguardConfigError):
            cfg.get_llm_safeguard_config()

    def test_irrigation_config_enables_it_with_the_documented_values(self):
        """Pins examples/irrigation_abm/config/agent_types.yaml's
        global_config.llm_safeguard block (spec item 24)."""
        from broker.utils.agent_config import load_agent_config

        cfg = load_agent_config("examples/irrigation_abm/config/agent_types.yaml")
        assert cfg.get_llm_safeguard_config() == {
            "enabled": True, "backoff_max_retries": 5,
            "backoff_initial_seconds": 2, "backoff_max_seconds": 60,
            "abort_window": 50, "abort_threshold": 0.5,
        }


# ---------------------------------------------------------------------------
# Backoff wrapper
# ---------------------------------------------------------------------------

class TestBackoffWrapper:
    def test_disabled_returns_the_exact_same_callable_unchanged(self):
        def invoke(prompt):
            return ("x", LLMStats(success=True))

        wrapped = wrap_llm_invoke_with_backoff(invoke, LLMSafeguardConfig())
        assert wrapped is invoke, "disabled must not even wrap, not just no-op"

    def test_fails_twice_then_succeeds_backoff_is_used_and_decision_succeeds(self):
        """THE spec scenario: 'a mock provider that fails twice and then
        succeeds: backoff is used and the decision succeeds.' ConnectionError
        is a builtin OSError subclass, so this is also the transport-failure
        path WARNING 3 keeps retryable."""
        calls = []

        def flaky(prompt):
            calls.append(prompt)
            if len(calls) <= 2:
                raise ConnectionError("simulated transient provider failure")
            return ("ok content", LLMStats(success=True, calls=1))

        wrapped = wrap_llm_invoke_with_backoff(
            flaky, _enabled_config(backoff_max_retries=3, backoff_initial_seconds=1),
        )
        with patch("broker.utils.llm_safeguard.time.sleep") as sleep_mock:
            content, stats = wrapped("prompt")

        assert content == "ok content"
        assert stats.success is True
        assert len(calls) == 3
        # Exponential: 1s after the first failure, 2s after the second.
        assert [c.args[0] for c in sleep_mock.call_args_list] == [1, 2]
        # CRITICAL 2 fix round: every attempt (including the two that
        # failed) folds into the returned stats -- 3 real calls, not 1, and
        # 2 backoff retries recorded for the audit counter.
        assert stats.calls == 3
        assert stats.backoff_retries == 2

    def test_transport_error_flag_without_raising_is_retried(self):
        """The real Ollama/cloud paths never raise past their own try/except
        -- a connection failure or an HTTP 5xx they caught internally already
        comes back as ("", success=False, transport_error=True). The wrapper
        must retry that shape too, not only a raised exception."""
        calls = {"n": 0}

        def half_broken(prompt):
            calls["n"] += 1
            if calls["n"] == 1:
                return ("", LLMStats(success=False, transport_error=True))
            return ("recovered", LLMStats(success=True))

        wrapped = wrap_llm_invoke_with_backoff(half_broken, _enabled_config())
        with patch("broker.utils.llm_safeguard.time.sleep"):
            content, stats = wrapped("prompt")

        assert calls["n"] == 2
        assert content == "recovered"
        assert stats.success is True
        assert stats.calls == 2
        assert stats.backoff_retries == 1

    def test_success_false_without_transport_error_is_not_retried(self):
        """WARNING 3 fix round: success=False alone (no transport_error) is
        NOT retried -- this is the shape empty/thinking-only content and an
        HTTP 4xx both take. Retrying it would contradict 'do not retry empty
        content' and 'do not retry HTTP 4xx.'"""
        calls = {"n": 0}

        def not_a_transport_failure(prompt):
            calls["n"] += 1
            return ("", LLMStats(success=False))  # transport_error defaults False

        wrapped = wrap_llm_invoke_with_backoff(not_a_transport_failure, _enabled_config())
        with patch("broker.utils.llm_safeguard.time.sleep") as sleep_mock:
            content, stats = wrapped("prompt")

        assert calls["n"] == 1, "must not retry a non-transport failure"
        assert not sleep_mock.called
        assert content == ""
        assert stats.success is False

    def test_os_error_raised_is_retried(self):
        """A raised OSError (the exception-raising twin of the
        transport_error flag) is retried."""
        attempts = {"n": 0}

        def raises_os_error(prompt):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise OSError("simulated raw transport failure")
            return ("ok", LLMStats(success=True))

        wrapped = wrap_llm_invoke_with_backoff(raises_os_error, _enabled_config())
        with patch("broker.utils.llm_safeguard.time.sleep"):
            content, stats = wrapped("prompt")

        assert attempts["n"] == 2
        assert content == "ok"
        assert stats.success is True

    def test_requests_timeout_is_never_retried(self):
        """WARNING 3, the specific carve-out: a requests.exceptions.Timeout
        is never retried by the wrapper even though it is (via
        RequestException) itself an OSError subclass -- the inner call
        already waited its own configured timeout, so retrying doubles the
        wait for no benefit."""
        import requests

        attempts = {"n": 0}

        def always_times_out(prompt):
            attempts["n"] += 1
            raise requests.exceptions.Timeout("simulated: inner call already waited")

        wrapped = wrap_llm_invoke_with_backoff(always_times_out, _enabled_config())
        with patch("broker.utils.llm_safeguard.time.sleep") as sleep_mock:
            content, stats = wrapped("prompt")

        assert attempts["n"] == 1, "a timeout must not be retried at all"
        assert not sleep_mock.called
        assert content == ""
        assert stats.success is False

    def test_generic_exception_is_not_retried(self):
        """WARNING 3: a generic exception such as TypeError is not a
        transport failure -- retrying it could mask a real bug."""
        attempts = {"n": 0}

        def raises_type_error(prompt):
            attempts["n"] += 1
            raise TypeError("simulated bug, not a transport failure")

        wrapped = wrap_llm_invoke_with_backoff(raises_type_error, _enabled_config())
        with patch("broker.utils.llm_safeguard.time.sleep") as sleep_mock:
            content, stats = wrapped("prompt")

        assert attempts["n"] == 1
        assert not sleep_mock.called
        assert content == ""
        assert stats.success is False

    def test_always_transport_fails_gives_up_after_configured_retries_without_raising(self):
        """After backoff_max_retries retries the wrapper gives up and hands
        back the existing failure shape -- it does not itself raise, so 'the
        existing failure path continues exactly as today.'"""
        attempts = {"n": 0}

        def always_raises(prompt):
            attempts["n"] += 1
            raise OSError("simulated persistent transport failure")

        wrapped = wrap_llm_invoke_with_backoff(
            always_raises, _enabled_config(backoff_max_retries=2, backoff_initial_seconds=1),
        )
        with patch("broker.utils.llm_safeguard.time.sleep"):
            content, stats = wrapped("prompt")

        assert attempts["n"] == 3  # 1 initial attempt + 2 retries
        assert content == ""
        assert stats.success is False
        assert stats.calls == 3
        assert stats.backoff_retries == 2

    def test_delay_is_capped_at_backoff_max_seconds(self):
        """WARNING 7 fix round: each delay is capped, not the total -- a
        large backoff_initial_seconds or many retries cannot make a single
        wait balloon past backoff_max_seconds."""
        def always_raises(prompt):
            raise OSError("simulated persistent transport failure")

        wrapped = wrap_llm_invoke_with_backoff(
            always_raises,
            _enabled_config(backoff_max_retries=4, backoff_initial_seconds=10,
                             backoff_max_seconds=25),
        )
        with patch("broker.utils.llm_safeguard.time.sleep") as sleep_mock:
            wrapped("prompt")

        # Uncapped doubling from 10 would be 10, 20, 40, 80; capped at 25 it
        # is 10, 20, 25, 25.
        assert [c.args[0] for c in sleep_mock.call_args_list] == [10, 20, 25, 25]

    def test_every_retry_and_the_final_giveup_are_logged_not_silent(self, caplog):
        def always_raises(prompt):
            raise OSError("boom")

        wrapped = wrap_llm_invoke_with_backoff(
            always_raises, _enabled_config(backoff_max_retries=1, backoff_initial_seconds=1),
        )
        with patch("broker.utils.llm_safeguard.time.sleep"), \
                caplog.at_level(logging.WARNING, logger="broker.utils.llm_safeguard"):
            wrapped("prompt")

        messages = [r.getMessage() for r in caplog.records]
        assert any("transport error" in m for m in messages)
        assert any("retrying" in m for m in messages)
        assert any(r.levelno == logging.ERROR for r in caplog.records), (
            "the final give-up must log at ERROR, not disappear at WARNING"
        )

    def test_disabled_never_calls_sleep_even_on_a_failing_provider(self):
        """Disabled means no behaviour change: a raising provider is not
        retried at all when the safeguard is off -- the raw exception
        reaches the caller exactly as it always has."""
        def always_raises(prompt):
            raise OSError("boom")

        wrapped = wrap_llm_invoke_with_backoff(always_raises, LLMSafeguardConfig())
        assert wrapped is always_raises
        with patch("broker.utils.llm_safeguard.time.sleep") as sleep_mock:
            with pytest.raises(OSError):
                wrapped("prompt")
        assert not sleep_mock.called

    def test_backoff_through_the_real_create_llm_invoke_ollama_path(self):
        """CRITICAL 1 fix round 3: backoff never fired on the Ollama path --
        the one irrigation (and every shipped domain) actually uses --
        because create_llm_invoke's own _final_stats() rebuilt LLMStats
        without transport_error, even though _invoke_ollama_direct had
        already set it. This goes through the REAL create_llm_invoke (not a
        hand-written stub), so it fails on the pre-fix code exactly as the
        reviewer's real gemma3:4b repro did. No live Ollama contact:
        requests.post is stubbed to refuse the connection twice, then
        return a valid Ollama-shaped response -- never a real socket.
        overrides={"max_retries": 1} makes create_llm_invoke's OWN short
        internal empty-content retry loop a no-op, so each of the 3 stubbed
        responses maps to exactly one backoff-level attempt."""
        # create_llm_invoke builds its Ollama client from langchain-ollama,
        # which CI does not install.
        pytest.importorskip("langchain_ollama")
        import requests
        from broker.utils.llm_utils import create_llm_invoke

        good_response = MagicMock()
        good_response.status_code = 200
        good_response.json.return_value = {
            "response": '{"decision": 1}',
            "prompt_eval_count": 10,
            "eval_count": 5,
            "eval_duration": 1_000_000,
        }
        post_mock = MagicMock(side_effect=[
            requests.exceptions.ConnectionError("stubbed: refused, no live Ollama contact"),
            requests.exceptions.ConnectionError("stubbed: refused, no live Ollama contact"),
            good_response,
        ])

        raw_invoke = create_llm_invoke(
            "gemma3:4b", verbose=False, overrides={"max_retries": 1},
        )
        wrapped = wrap_llm_invoke_with_backoff(
            raw_invoke, _enabled_config(backoff_max_retries=3, backoff_initial_seconds=1),
        )

        with patch("requests.post", post_mock), \
                patch("broker.utils.llm_safeguard.time.sleep") as sleep_mock:
            content, stats = wrapped("PROMPT")

        assert post_mock.call_count == 3, (
            "pre-fix, transport_error never reached the wrapper, so it never "
            "retried at all -- post_mock.call_count would be 1"
        )
        assert content == '{"decision": 1}'
        assert stats.success is True
        assert stats.calls == 3
        assert stats.backoff_retries == 2
        assert [c.args[0] for c in sleep_mock.call_args_list] == [1, 2]

    def test_backoff_retries_counts_actual_calls_not_retry_rounds(self):
        """WARNING 4 fix round 3: one backoff-level RETRY can itself cost
        more than one inner HTTP call (create_llm_invoke's own short
        empty-content retry loop) -- backoff_retries must reflect that, not
        just '1 per round'. Here the FIRST (non-final, failed) backoff
        attempt's own stats already report calls=2 (it retried internally
        before this wrapper ever saw it fail), and the SECOND (final,
        successful) attempt costs calls=1 on its own. backoff_retries is
        the OTHER attempts' calls (total_calls - the final attempt's own
        calls = 3 - 1 = 2) -- pre-fix, counting rounds would have reported
        1 (only one wrapper-level retry happened)."""
        attempts = {"n": 0}

        def one_round_costs_two_inner_calls(prompt):
            attempts["n"] += 1
            if attempts["n"] == 1:
                # This ONE backoff-level attempt already made 2 raw calls
                # internally before giving up and reporting failure.
                return ("", LLMStats(success=False, transport_error=True, calls=2))
            return ("ok", LLMStats(success=True, calls=1))

        wrapped = wrap_llm_invoke_with_backoff(
            one_round_costs_two_inner_calls, _enabled_config(),
        )
        with patch("broker.utils.llm_safeguard.time.sleep"):
            content, stats = wrapped("prompt")

        assert attempts["n"] == 2
        assert content == "ok"
        assert stats.calls == 3
        assert stats.backoff_retries == 2, (
            "backoff_retries must count the 2 actual extra calls, not the "
            "1 backoff-level retry round"
        )
        assert stats.retries == 2

    def test_backoff_retries_excludes_the_final_attempts_own_retries(self):
        """Fix round 4, CRITICAL A: the final (successful) attempt's own
        internal retries must not be folded into backoff_retries a second
        time. Here attempt 1 fails with a plain single-call transport error
        (calls=1); attempt 2 succeeds but itself needed one internal retry
        of its own BEFORE backoff ever saw it, so it already reports
        calls=2 and retries=1 on its own. True extra calls beyond the very
        first one = total_calls(3) - 1 = 2, so the folded retries must be 2.
        backoff_retries -- the calls spent on the OTHER, non-final attempts
        only -- must be 1 (attempt 1's single call), not 2. Pre-fix
        (``backoff_retries = total_calls - 1``), backoff_retries came out
        as 2 and got added on top of the final attempt's own retries=1,
        giving retries=3 -- one too many, double-counting the final
        attempt's own internal retry that backoff_retries also claimed."""
        attempts = {"n": 0}

        def final_attempt_has_its_own_internal_retry(prompt):
            attempts["n"] += 1
            if attempts["n"] == 1:
                return ("", LLMStats(success=False, transport_error=True, calls=1))
            # The final, successful attempt already cost 2 raw calls and
            # recorded 1 of its own retries before backoff ever saw it.
            return ("ok", LLMStats(success=True, calls=2, retries=1))

        wrapped = wrap_llm_invoke_with_backoff(
            final_attempt_has_its_own_internal_retry, _enabled_config(),
        )
        with patch("broker.utils.llm_safeguard.time.sleep"):
            content, stats = wrapped("prompt")

        assert attempts["n"] == 2
        assert content == "ok"
        assert stats.calls == 3
        assert stats.backoff_retries == 1, (
            "backoff_retries must exclude the final attempt's own internal "
            "retry (already counted in its own retries field); only "
            "attempt 1's 1 call belongs to the wrapper's own retrying"
        )
        assert stats.retries == 2, (
            "retries must equal the true extra-calls-beyond-the-first (2), "
            "not double count the final attempt's own 1 retry on top of "
            "backoff_retries"
        )


# ---------------------------------------------------------------------------
# Abort-rate tracker (pure unit tests, no engine)
# ---------------------------------------------------------------------------

class TestAbortTracker:
    """The trigger is EARLY-STOP (WARNING 5, fix round): a decision count
    reaching ``ceil(abort_threshold * abort_window)``, not "window full AND
    failed share >= threshold". The two describe the same eventual outcome
    for a run whose failure rate holds steady, but early-stop can fire
    before the window is even full -- see
    ``test_fires_before_the_window_is_full_for_a_persistently_failing_run``
    below, the direct pin of that behaviour.
    """

    def test_disabled_never_raises_no_matter_how_many_failures(self):
        tracker = LLMAbortTracker(LLMSafeguardConfig(enabled=False, abort_window=2, abort_threshold=0.5))
        for _ in range(100):
            tracker.record(failed=True)  # would trip on record #1 if enabled

    def test_does_not_raise_before_enough_failures_accumulate(self):
        """abort_window=5, abort_threshold=0.9 -> ceil(4.5) = 5 failures
        needed. 4 failures (and a window not yet full either) must not
        raise."""
        tracker = LLMAbortTracker(_enabled_config(abort_window=5, abort_threshold=0.9))
        for _ in range(4):
            tracker.record(failed=True)

    def test_raises_once_the_failure_count_is_reached(self):
        tracker = LLMAbortTracker(_enabled_config(abort_window=3, abort_threshold=0.5))
        # ceil(0.5 * 3) = 2 failures needed.
        tracker.record(failed=True)
        tracker.record(failed=False)
        with pytest.raises(LLMFailureRateAborted) as exc_info:
            tracker.record(failed=True)  # 2 failures reached, window also just filled

        err = exc_info.value
        assert err.window == 3
        assert err.threshold == 0.5
        assert err.observed_rate == pytest.approx(2 / 3)
        # WARNING 3 fix round 3: the raw counts behind observed_rate.
        assert err.failed_count == 2
        assert err.decisions_in_window == 3

    def test_below_threshold_does_not_raise_even_when_window_is_full(self):
        tracker = LLMAbortTracker(_enabled_config(abort_window=4, abort_threshold=0.75))
        # ceil(0.75 * 4) = 3 failures needed; only 1 ever occurs.
        tracker.record(failed=True)
        tracker.record(failed=False)
        tracker.record(failed=False)
        tracker.record(failed=False)

    def test_fires_before_the_window_is_full_for_a_persistently_failing_run(self):
        """THE new behaviour (WARNING 5): irrigation's real values,
        abort_window=50 abort_threshold=0.5 -> ceil(25.0) = 25 failures. A
        run that fails every single decision must abort at decision 25, not
        wait for decision 50."""
        tracker = LLMAbortTracker(_enabled_config(abort_window=50, abort_threshold=0.5))
        for _ in range(24):
            tracker.record(failed=True)  # window still only half full, must not raise

        with pytest.raises(LLMFailureRateAborted) as exc_info:
            tracker.record(failed=True)  # the 25th failure, decision 25 of 50

        err = exc_info.value
        assert err.window == 50
        assert err.threshold == 0.5
        assert err.observed_rate == pytest.approx(1.0)
        # WARNING 3 fix round 3: decisions_in_window (25) is LESS than the
        # configured window (50) -- the direct, load-bearing proof that this
        # abort fired early, before the window ever filled.
        assert err.failed_count == 25
        assert err.decisions_in_window == 25

    def test_ceil_rounds_up_a_fractional_threshold_count(self):
        """abort_window=4, abort_threshold=0.3 -> raw count 1.2. ceil gives 2
        (must NOT raise on the 1st failure, which a floor of 1 would); the
        2nd failure must raise."""
        tracker = LLMAbortTracker(_enabled_config(abort_window=4, abort_threshold=0.3))
        tracker.record(failed=True)  # 1 failure: ceil(1.2) = 2, must not raise yet
        with pytest.raises(LLMFailureRateAborted):
            tracker.record(failed=True)  # 2 failures: reaches ceil(1.2) = 2

    def test_window_is_rolling_not_cumulative(self):
        """A window of all failures rolls the earliest ones off as new
        decisions arrive -- it is a ROLLING window, not a cumulative
        failure counter that only ever grows."""
        tracker = LLMAbortTracker(_enabled_config(abort_window=3, abort_threshold=0.99))
        # ceil(0.99 * 3) = 3 failures needed (the window's full size).
        tracker.record(failed=True)
        tracker.record(failed=True)
        with pytest.raises(LLMFailureRateAborted):
            tracker.record(failed=True)  # window [T, T, T] = 1.0 >= 0.99

        # Two clean decisions roll the earliest failures out: the window is
        # now [T, F, F] = 1/3 = 1 failure, well under the 3 needed -- must
        # not raise.
        tracker.record(failed=False)
        tracker.record(failed=False)


# ---------------------------------------------------------------------------
# Engine-level integration: SkillBrokerEngine.process_step actually enforces
# the safeguard end to end (real engine, minimal stub parts -- same pattern
# as broker/tests/test_corrected_status_columns_pr3.py's `_engine` helper).
# ---------------------------------------------------------------------------

def _build_engine(safeguard: dict, corrected_status_columns: bool = False,
                   governance_retries: int = 1, always_reject: bool = False):
    from broker.components.governance.registry import SkillRegistry
    from broker.core.skill_broker_engine import SkillBrokerEngine
    from broker.interfaces.skill_types import (
        ExecutionResult, SkillDefinition, SkillProposal, ValidationResult,
    )

    registry = SkillRegistry()
    registry.register(SkillDefinition(
        skill_id="do_nothing", description="d", eligible_agent_types=["*"],
        preconditions=[], institutional_constraints={},
        allowed_state_changes=[], implementation_mapping="do_nothing",
    ))
    registry.set_default_skill("do_nothing")

    class _Adapter:
        """Mirrors UnifiedAdapter's contract for this test's purposes only:
        a real SkillProposal parses, anything else (raw text) does not."""

        def parse_output(self, raw_output, ctx):
            return raw_output if isinstance(raw_output, SkillProposal) else None

        def format_retry_prompt(self, prompt, messages, **kwargs):
            return prompt

    class _Sim:
        def execute_skill(self, approved_skill):
            return ExecutionResult(success=True, state_changes={})

    class _Ctx:
        def build(self, agent_id, env_context=None, **kwargs):
            return {"agent_id": agent_id, "state": {}}

        def format_prompt(self, context):
            return "PROMPT"

    class _Writer:
        def __init__(self):
            self.traces = []

        def write_trace(self, agent_type, trace, history=None):
            self.traces.append((agent_type, trace))

    validators = []
    if always_reject:
        # Same pattern as broker/tests/test_corrected_status_columns_pr3.py's
        # `_engine(blocking=True)`: a validator that ALWAYS rejects, so a
        # decision that DOES parse still needs the governance retry loop.
        validator = MagicMock()
        validator.validate.side_effect = lambda *_a, **_k: ValidationResult(
            valid=False, validator_name="AgentValidator:always_reject",
            errors=["blocked for test"],
            metadata={"rules_hit": ["test_rule"], "tier": "Tier 2: Thinking",
                      "level": "ERROR"},
        )
        validators.append(validator)

    config = MagicMock()
    config.get_log_fields.return_value = []
    config.get_governance_retries.return_value = governance_retries
    config.get_governance_max_reports.return_value = 1
    config.get_multi_skill_config.return_value = {}
    config.get_parsing_config.return_value = {}
    config.get_governance_on_retry_exhausted.return_value = "default"
    # Fix round 3 (CRITICAL 2): a real bool, defaulting to False (the
    # pre-existing framework default) -- a caller sets True to mirror
    # irrigation's now-static posture (global_config.audit.
    # corrected_status_columns: true), never derived from the safeguard.
    config.get_audit_corrected_status_columns.return_value = corrected_status_columns
    config.get_llm_safeguard_config.return_value = safeguard

    engine = SkillBrokerEngine(
        skill_registry=registry, model_adapter=_Adapter(), validators=validators,
        simulation_engine=_Sim(), context_builder=_Ctx(), config=config,
    )
    engine.audit_writer = _Writer()
    return engine


def _step(engine, llm_invoke, year=1):
    return engine.process_step(
        agent_id="A1", step_id=year, run_id="r", seed=42,
        llm_invoke=llm_invoke, agent_type="household",
        env_context={"current_year": year},
    )


_FULL_SAFEGUARD_DEFAULTS = {
    "backoff_max_retries": 1, "backoff_initial_seconds": 1,
    "backoff_max_seconds": 1,
}


class TestEngineAbortIntegration:
    def test_disabled_never_aborts_even_when_every_call_is_unparsable(self):
        """'Disabled means no behaviour change': hammer the engine with an
        always-unparsable llm_invoke well past what abort_window would be
        if enabled, and confirm process_step never raises."""
        from broker.interfaces.skill_types import SkillOutcome

        engine = _build_engine({
            "enabled": False, **_FULL_SAFEGUARD_DEFAULTS,
            "abort_window": 3, "abort_threshold": 0.5,
        })
        for year in range(1, 11):
            result = _step(engine, lambda p: "unparseable garbage", year=year)
            assert result.outcome is SkillOutcome.ABORTED

    def test_always_unparsable_text_aborts_before_the_window_is_full(self):
        """THE spec scenario, under the fix round's EARLY-STOP rule (WARNING
        5): abort_window=3, abort_threshold=0.5 -> ceil(1.5) = 2 failures
        needed, so the abort fires on decision 2, before the 3-decision
        window is even full."""
        from broker.interfaces.skill_types import SkillOutcome

        engine = _build_engine({
            "enabled": True, **_FULL_SAFEGUARD_DEFAULTS,
            "abort_window": 3, "abort_threshold": 0.5,
        })
        result = _step(engine, lambda p: "unparseable garbage", year=1)
        assert result.outcome is SkillOutcome.ABORTED

        with pytest.raises(LLMFailureRateAborted) as exc_info:
            _step(engine, lambda p: "unparseable garbage", year=2)
        err = exc_info.value
        assert err.window == 3
        assert err.threshold == 0.5
        assert err.observed_rate == pytest.approx(1.0)

    def test_always_raising_provider_aborts_before_the_window_is_full(self):
        """The other half of the same scenario: the provider CALL fails
        (raises OSError, a transport failure) rather than returning
        unparsable text. Composed with the backoff wrapper first, exactly as
        ExperimentRunner.get_llm_invoke hands process_step its llm_invoke in
        production -- the wrapper converts the raise into the standard
        failure shape the abort tracker already understands."""
        safeguard = {
            "enabled": True, **_FULL_SAFEGUARD_DEFAULTS,
            "abort_window": 3, "abort_threshold": 0.5,  # ceil(1.5) = 2
        }
        engine = _build_engine(safeguard)

        def always_raises(prompt):
            raise OSError("simulated persistent transport failure")

        wrapped_invoke = wrap_llm_invoke_with_backoff(
            always_raises, LLMSafeguardConfig.from_dict(safeguard),
        )

        with patch("broker.utils.llm_safeguard.time.sleep"):
            _step(engine, wrapped_invoke, year=1)
            with pytest.raises(LLMFailureRateAborted):
                _step(engine, wrapped_invoke, year=2)

    def test_a_recovering_mix_below_threshold_never_trips(self):
        from broker.interfaces.skill_types import SkillOutcome, SkillProposal

        engine = _build_engine({
            "enabled": True, **_FULL_SAFEGUARD_DEFAULTS,
            "abort_window": 4, "abort_threshold": 0.75,  # ceil(3.0) = 3
        })

        def sometimes_ok(prompt):
            return SkillProposal(skill_name="do_nothing", agent_id="A1", reasoning={})

        # 1 failure then 3 successes -> failure count stays at 1, never
        # reaches 3 -> must not raise.
        _step(engine, lambda p: "garbage", year=1)
        for year in (2, 3, 4):
            result = _step(engine, sometimes_ok, year=year)
            assert result.outcome is not SkillOutcome.ABORTED

    def test_aborted_run_still_writes_the_audit_csv_with_its_sentinels(self):
        """CRITICAL 2 fix round 3 re-verification (2 of 3): with
        corrected_status_columns ON (irrigation's now-static config posture,
        set directly -- NOT derived from the safeguard, which no longer
        special-cases this gate at all, see skill_broker_engine.py), the
        decision that TRIPS the abort still gets its own sentinel row.
        abort_window=1 makes the FIRST decision itself the one that trips
        (ceil(1.0*1) = 1)."""
        safeguard = {
            "enabled": True, **_FULL_SAFEGUARD_DEFAULTS,
            "abort_window": 1, "abort_threshold": 1.0,
        }
        engine = _build_engine(safeguard, corrected_status_columns=True)
        assert engine._corrected_status_columns is True

        with pytest.raises(LLMFailureRateAborted):
            _step(engine, lambda p: "unparseable garbage", year=1)

        assert len(engine.audit_writer.traces) == 1, (
            "the triggering decision must still write its own audit row"
        )
        from broker.components.analytics.audit import trace_to_csv_row

        _agent_type, trace = engine.audit_writer.traces[0]
        row = trace_to_csv_row(trace)
        assert row["agent_id"] == "A1"
        assert row["status"] == "ABORTED"

    def test_schema_is_the_same_with_and_without_a_parse_failure(self):
        """CRITICAL 2 fix round 3 re-verification (1 of 3): the audit schema
        must not depend on whether a run happened to hit a parse failure.
        The corrected-status columns the PI's decision names -- execution_path
        and executed_skill, the ones "the metrics need" -- must be present on
        BOTH a clean decision's row and a parse-failure decision's row, not
        only on rows that happen to parse. (Other opt-in column families such
        as initial_proposal_columns / advise / grounding are gated by their
        OWN, separate flags, which this engine's config leaves at their
        coerced-off default -- they are unrelated to this PI decision and out
        of scope here.)"""
        from broker.interfaces.skill_types import SkillProposal
        from broker.components.analytics.audit import trace_to_csv_row

        # Safeguard disabled here -- this is a property of
        # corrected_status_columns alone, independent of the safeguard.
        engine = _build_engine(
            {"enabled": False, **_FULL_SAFEGUARD_DEFAULTS,
             "abort_window": 50, "abort_threshold": 0.5},
            corrected_status_columns=True,
        )

        def ok_invoke(prompt):
            return SkillProposal(skill_name="do_nothing", agent_id="A1", reasoning={})

        _step(engine, ok_invoke, year=1)
        clean_row = trace_to_csv_row(engine.audit_writer.traces[0][1])

        _step(engine, lambda p: "unparseable garbage", year=2)
        failure_row = trace_to_csv_row(engine.audit_writer.traces[1][1])

        for col in ("execution_path", "executed_skill", "executed_via_fallback", "status"):
            assert col in clean_row, f"{col} missing from the clean decision's row"
            assert col in failure_row, f"{col} missing from the parse-failure decision's row"
        assert failure_row["status"] == "ABORTED"
        assert failure_row["execution_path"] == "aborted"

    def test_backoff_exhaustion_stops_the_format_retry_loop_at_once(self):
        """TIME TO ABORT fix round 3: once the backoff wrapper has already
        given up on a transport failure (the shape it returns:
        success=False, transport_error=True), the format-retry loop must
        treat the decision as failed immediately -- NOT call llm_invoke
        again up to max_initial_attempts more times, each of which would (in
        production, wrapped) pay the full backoff schedule again against a
        connection already proven dead. Pre-fix this stub would have been
        called 3 times (1 initial + 2 format retries); post-fix, once."""
        calls = {"n": 0}

        def backoff_already_exhausted(prompt):
            calls["n"] += 1
            return "", LLMStats(success=False, transport_error=True)

        engine = _build_engine({
            "enabled": True, **_FULL_SAFEGUARD_DEFAULTS,
            "abort_window": 50, "abort_threshold": 0.5,
        })

        # A single decision must not itself trip the (large) abort window;
        # this test is purely about the format-retry loop's call count.
        result = _step(engine, backoff_already_exhausted, year=1)
        from broker.interfaces.skill_types import SkillOutcome
        assert result.outcome is SkillOutcome.ABORTED
        assert calls["n"] == 1, (
            f"expected exactly 1 call (no re-prompting a dead endpoint), "
            f"got {calls['n']}"
        )

    def test_disabled_safeguard_keeps_the_old_retry_the_format_loop_behaviour(self):
        """Disabled means no behaviour change: WITHOUT the safeguard, a
        transport_error-shaped failure (which a real invoke function can
        still report even with the safeguard off -- it is a raw signal, not
        something the safeguard invents) must still be retried by the
        format loop exactly as before -- 3 total calls, not 1."""
        calls = {"n": 0}

        def transport_failure_shaped(prompt):
            calls["n"] += 1
            return "", LLMStats(success=False, transport_error=True)

        engine = _build_engine({
            "enabled": False, **_FULL_SAFEGUARD_DEFAULTS,
            "abort_window": 50, "abort_threshold": 0.5,
        })
        _step(engine, transport_failure_shaped, year=1)
        assert calls["n"] == 3, (
            "disabled must keep the pre-fix-round retry-3-times behaviour"
        )

    def test_backoff_exhaustion_stops_the_governance_retry_loop_at_once(self):
        """TIME TO ABORT fix round 3, the governance-retry-loop half: an
        initial decision that DOES parse but is always rejected (forcing
        entry into the governance retry loop) must still stop re-prompting
        once a governance-retry LLM call reports a backoff-already-exhausted
        transport failure -- not keep retrying up to governance_retries more
        times. governance_retries=3 here so a pre-fix run (which does not
        recognise the transport failure and just treats it as another
        unparsable retry attempt) would call llm_invoke 4 times (1 initial +
        3 governance retries); post-fix it must stop after the 2nd call."""
        from broker.interfaces.skill_types import SkillOutcome, SkillProposal

        calls = {"n": 0}

        def parses_once_then_dead_endpoint(prompt):
            calls["n"] += 1
            if calls["n"] == 1:
                return SkillProposal(skill_name="do_nothing", agent_id="A1", reasoning={})
            return "", LLMStats(success=False, transport_error=True)

        engine = _build_engine(
            {"enabled": True, **_FULL_SAFEGUARD_DEFAULTS,
             "abort_window": 50, "abort_threshold": 0.5},
            governance_retries=3, always_reject=True,
        )
        result = _step(engine, parses_once_then_dead_endpoint, year=1)

        assert calls["n"] == 2, (
            f"expected exactly 2 calls (1 initial + 1 governance retry that "
            f"hit the dead endpoint and stopped), got {calls['n']}"
        )
        assert result.outcome in (SkillOutcome.REJECTED, SkillOutcome.UNCERTAIN)


class TestGovernanceRetryLoopAttemptSkillsInvariant:
    """Fix round 4, CRITICAL B: the transport-failure break inside
    ``_governance_retry_loop`` must keep ``attempt_skills`` (the P0-1a
    per-attempt trace, seeded at index 0 with the initial proposal) in
    lockstep with ``retry_count`` -- one more entry per retry attempt,
    including a retry attempt that broke out early with nothing usable.
    Calls ``_governance_retry_loop`` directly, the same no-engine harness
    ``test_retry_loop_skillproposal.py`` uses (the method's own docstring
    names this a supported entry point: "this method is also entered
    DIRECTLY (tests and domain code do)")."""

    def test_attempt_skills_stays_in_lockstep_with_retry_count_under_a_forced_outage(self):
        from broker.core._retry_loop import RetryMixin
        from broker.interfaces.skill_types import SkillProposal, ValidationResult

        class _Adapter:
            def format_retry_prompt(self, prompt, errors, max_reports=3, **kwargs):
                return f"{prompt}\nretry"

        class _Host(RetryMixin):
            max_retries = 1
            max_reports = 3

            def __init__(self):
                self.auditor = MagicMock()
                self.model_adapter = _Adapter()
                self._llm_safeguard = SimpleNamespace(enabled=True)
                # Reached only by the loop's own post-exhaustion fallout
                # logging (skill_proposal is None by then, so the
                # keep_proposal branch short-circuits before touching this)
                # -- not part of what this test is pinning.
                self.skill_registry = MagicMock()
                self.skill_registry.get_default_skill.return_value = "do_nothing"

            def _run_validators(self, proposal, context):
                raise AssertionError(
                    "a transport failure that stops the loop must not "
                    "reach validation for a retry attempt that produced "
                    "nothing parseable"
                )

        host = _Host()
        initial = SkillProposal(
            skill_name="do_nothing", agent_id="A1", agent_type="household",
            reasoning={},
        )
        rejected = [ValidationResult(valid=False, validator_name="reject", errors=["blocked"])]
        # Seeded by the caller per the method's own P0-1a contract: index 0
        # is the initial (pre-retry-loop) proposal.
        attempt_skills = ["do_nothing"]

        result = host._governance_retry_loop(
            all_valid=False,
            skill_proposal=initial,
            validation_results=rejected,
            all_validation_history=list(rejected),
            validation_context={},
            prompt="prompt",
            llm_invoke=lambda _prompt: ("", LLMStats(success=False, transport_error=True)),
            context={},
            agent_id="A1",
            agent_type="household",
            env_context={"current_year": 1},
            raw_output=initial,
            total_llm_stats={"llm_retries": 0, "llm_success": False},
            attempt_skills=attempt_skills,
        )
        _, _, _, _, _, retry_count = result

        assert retry_count == 1
        assert len(attempt_skills) == retry_count + 1, (
            f"attempt_skills has {len(attempt_skills)} entries for "
            f"retry_count={retry_count}; the transport-failure attempt "
            f"that happened and produced nothing usable must still be "
            f"recorded (as None), the same as _advise_pass's own "
            f"failure branches"
        )
        assert attempt_skills[-1] is None


# ---------------------------------------------------------------------------
# Runner-level: the abort exception must not be swallowed into another
# ABORTED row, and run()'s finally-block must record it in the manifest
# (and have already flushed the audit writer) before the process exits.
# ---------------------------------------------------------------------------

def _make_agent(agent_id: str, agent_type: str = "household"):
    agent = MagicMock()
    agent.id = agent_id
    agent.agent_type = agent_type
    return agent


def _make_runner(process_step_side_effect, output_dir, workers: int = 1, num_years: int = 5):
    """A minimal ExperimentRunner (broker mocked out) whose
    ``broker.process_step`` follows ``process_step_side_effect``. Mirrors
    ``broker/tests/test_silent_failure_fixes.py``'s
    ``_make_runner_with_mocks`` helper, extended just enough to also drive
    the full ``run()`` loop (that file only ever calls
    ``_run_agents_sequential`` / ``_run_agents_parallel`` directly)."""
    from broker.core.experiment_runner import ExperimentRunner

    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.broker = MagicMock()
    runner.broker.audit_writer = MagicMock()
    # Falsy on purpose: `_finalize_experiment` does `Path(model_adapter.config_path)`
    # when this is truthy, which raises on a bare Mock. `agent_config` falsy
    # skips run()'s own schema-validation block for the same reason (it
    # iterates whatever `.validate_schema()` returns, which a Mock is not).
    runner.broker.model_adapter.config_path = None
    runner.broker.model_adapter.agent_config = None
    runner.broker.context_builder = MagicMock()
    runner.broker.context_builder.build = MagicMock(return_value={"state": {}})
    runner.broker.process_step = MagicMock(side_effect=process_step_side_effect)
    runner.sim_engine = MagicMock()
    runner.sim_engine.advance_step = MagicMock(return_value={})
    runner.agents = {"A1": _make_agent("A1")}
    runner.step_counter = 0
    runner._current_year = 0
    runner.memory_engine = MagicMock()
    runner.efficiency = None
    runner._hooks = {}
    runner.config = SimpleNamespace(
        experiment_name="t", model="mock", seed=1, num_steps=None,
        num_years=num_years, governance_profile="strict", workers=workers,
        phase_order=None, verbose=False, output_dir=output_dir,
    )
    runner._resolve_declared_deciders = lambda: {}
    runner._finalize_step = MagicMock()
    runner._collect_reproducibility_metadata = MagicMock(return_value={})
    runner.get_llm_invoke = MagicMock(return_value=lambda *a, **kw: None)
    return runner


class TestRunnerDoesNotSwallowTheAbortException:
    def test_sequential_path_propagates_it(self):
        err = LLMFailureRateAborted(observed_rate=1.0, window=2, threshold=0.5, failed_count=2, decisions_in_window=2)
        runner = _make_runner(err, output_dir=None)

        with pytest.raises(LLMFailureRateAborted):
            runner._run_agents_sequential(
                [_make_agent("A1")], run_id="r",
                llm_invoke=lambda *a, **kw: None, env={"current_year": 1},
            )

    def test_parallel_path_propagates_it(self):
        err = LLMFailureRateAborted(observed_rate=1.0, window=2, threshold=0.5, failed_count=2, decisions_in_window=2)
        runner = _make_runner(err, output_dir=None, workers=2)

        with pytest.raises(LLMFailureRateAborted):
            runner._run_agents_parallel(
                [_make_agent("A1")], run_id="r",
                llm_invoke=lambda *a, **kw: None, env={"current_year": 1},
            )

    def test_parallel_path_cancels_queued_futures_before_reraising(self):
        """WARNING 4 fix round: on abort, _run_agents_parallel must call
        executor.shutdown(wait=True, cancel_futures=True) BEFORE re-raising,
        so queued (not-yet-started) agents never begin. Spies on
        ThreadPoolExecutor.shutdown by subclassing it (still a REAL
        executor underneath, so the run itself behaves normally) rather than
        mocking the class away entirely."""
        import broker.core.experiment_runner as experiment_runner_module
        from concurrent.futures import ThreadPoolExecutor

        shutdown_calls = []

        class _SpyExecutor(ThreadPoolExecutor):
            def shutdown(self, wait=True, *, cancel_futures=False):
                shutdown_calls.append({"wait": wait, "cancel_futures": cancel_futures})
                super().shutdown(wait=wait, cancel_futures=cancel_futures)

        err = LLMFailureRateAborted(observed_rate=1.0, window=2, threshold=0.5, failed_count=2, decisions_in_window=2)
        runner = _make_runner(err, output_dir=None, workers=2)

        with patch.object(experiment_runner_module, "ThreadPoolExecutor", _SpyExecutor):
            with pytest.raises(LLMFailureRateAborted):
                runner._run_agents_parallel(
                    [_make_agent("A1")], run_id="r",
                    llm_invoke=lambda *a, **kw: None, env={"current_year": 1},
                )

        assert any(
            call["cancel_futures"] is True and call["wait"] is True
            for call in shutdown_calls
        ), f"expected an explicit shutdown(wait=True, cancel_futures=True) call, got {shutdown_calls}"


class TestRunAbortsCleanlyAndRecordsTheManifest:
    def test_run_records_run_status_and_flushes_before_reraising(self, tmp_path):
        """THE spec scenario, at the runner level: '... the run aborts once
        the window fills ... the manifest records it, and the traces are
        flushed.'"""
        from broker.interfaces.skill_types import SkillBrokerResult, SkillOutcome

        ok_result = SkillBrokerResult(
            outcome=SkillOutcome.APPROVED, skill_proposal=None,
            approved_skill=None, execution_result=None,
        )
        abort_err = LLMFailureRateAborted(observed_rate=1.0, window=2, threshold=0.5, failed_count=2, decisions_in_window=2)
        runner = _make_runner([ok_result, abort_err], output_dir=tmp_path, num_years=5)

        with pytest.raises(LLMFailureRateAborted):
            runner.run()

        assert runner._llm_safeguard_abort is abort_err
        assert runner.broker.audit_writer.finalize.called, (
            "finalize() (which flushes + fsyncs the JSONL traces) must run "
            "even though the run aborted"
        )

        manifest = json.loads((tmp_path / "reproducibility_manifest.json").read_text())
        assert manifest["run_status"] == "aborted_llm_failure_rate"
        assert manifest["llm_safeguard_abort"] == {
            "observed_rate": 1.0, "window": 2, "threshold": 0.5,
            "failed_count": 2, "decisions_in_window": 2,
        }

    def test_clean_run_manifest_has_no_run_status_key(self, tmp_path):
        """Byte-identity guard on the manifest itself: a run that never
        aborts must not grow a `run_status` / `llm_safeguard_abort` key."""
        from broker.interfaces.skill_types import SkillBrokerResult, SkillOutcome

        ok_result = SkillBrokerResult(
            outcome=SkillOutcome.APPROVED, skill_proposal=None,
            approved_skill=None, execution_result=None,
        )
        runner = _make_runner([ok_result, ok_result], output_dir=tmp_path, num_years=2)

        runner.run()

        manifest = json.loads((tmp_path / "reproducibility_manifest.json").read_text())
        assert "run_status" not in manifest
        assert "llm_safeguard_abort" not in manifest

    def test_a_second_clean_run_does_not_inherit_the_first_runs_abort(self, tmp_path):
        """SUGGESTION 10 fix round: run() must reset _llm_safeguard_abort at
        its OWN top, not only set it on abort. Without the reset, a second
        run() on the same instance (a reused runner, a test harness) that
        finishes cleanly would still carry the FIRST run's abort and
        wrongly stamp a clean corpus's manifest with
        run_status: aborted_llm_failure_rate."""
        from broker.interfaces.skill_types import SkillBrokerResult, SkillOutcome

        ok_result = SkillBrokerResult(
            outcome=SkillOutcome.APPROVED, skill_proposal=None,
            approved_skill=None, execution_result=None,
        )
        abort_err = LLMFailureRateAborted(observed_rate=1.0, window=2, threshold=0.5, failed_count=2, decisions_in_window=2)

        first_dir = tmp_path / "first"
        second_dir = tmp_path / "second"
        first_dir.mkdir()
        second_dir.mkdir()

        runner = _make_runner([ok_result, abort_err], output_dir=first_dir, num_years=5)
        with pytest.raises(LLMFailureRateAborted):
            runner.run()
        assert runner._llm_safeguard_abort is abort_err

        # Re-point at a fresh output dir, a side_effect that never fails, and
        # num_years matching that side_effect's length exactly (2), then run
        # the SAME instance again.
        runner.config.output_dir = second_dir
        runner.config.num_years = 2
        runner.broker.process_step = MagicMock(side_effect=[ok_result, ok_result])
        runner.run()

        assert runner._llm_safeguard_abort is None
        manifest = json.loads((second_dir / "reproducibility_manifest.json").read_text())
        assert "run_status" not in manifest

    def test_a_second_clean_run_does_not_inherit_the_first_runs_generic_abort(self, tmp_path):
        """Opus review of WP7 launcher, round 2 (non-blocking): twin of the
        test above for `_generic_abort` (added round 1 for any exception
        other than LLMFailureRateAborted / the crash-resume journal pair),
        which needs the SAME reset-at-the-top discipline run() now gives
        it. Without the reset, a second run() on the same instance that
        finishes cleanly would still carry the FIRST run's generic abort
        and wrongly stamp a clean corpus's manifest with
        run_status: aborted_exception.

        The generic exception comes from a HOOK, not `process_step`:
        `_run_agents_sequential` catches a plain exception from
        `process_step` per-agent-step and turns it into an ABORTED row
        (proven empirically: reusing the process_step-side_effect pattern
        above with a bare RuntimeError just produces more ABORTED rows,
        never reaching run()'s own try/except) -- only the three
        specially-recognized abort types are exempted from that catch. A
        hook exception is the one path proven (here and in
        test_abort_provenance.py's integration-level equivalent) to escape
        all the way to run()'s try/except for an ARBITRARY exception type,
        since `_call_hook`'s own documented job is to log and re-raise,
        never swallow."""
        from broker.interfaces.skill_types import SkillBrokerResult, SkillOutcome

        ok_result = SkillBrokerResult(
            outcome=SkillOutcome.APPROVED, skill_proposal=None,
            approved_skill=None, execution_result=None,
        )
        generic_err = RuntimeError("stubbed failure: no live Ollama contact in this test")

        first_dir = tmp_path / "first"
        second_dir = tmp_path / "second"
        first_dir.mkdir()
        second_dir.mkdir()

        runner = _make_runner([ok_result] * 5, output_dir=first_dir, num_years=5)
        runner._hooks = {"post_year": lambda *a, **kw: None}
        runner._call_hook = MagicMock(side_effect=generic_err)
        with pytest.raises(RuntimeError, match="stubbed failure"):
            runner.run()
        assert runner._generic_abort is generic_err
        manifest = json.loads((first_dir / "reproducibility_manifest.json").read_text())
        assert manifest["run_status"] == "aborted_exception"
        assert manifest["aborted_exception_type"] == "RuntimeError"

        # Re-point at a fresh output dir, a hook that never fails, and
        # num_years matching the fresh process_step side_effect exactly
        # (2), then run the SAME instance again.
        runner.config.output_dir = second_dir
        runner.config.num_years = 2
        runner.broker.process_step = MagicMock(side_effect=[ok_result, ok_result])
        runner._call_hook = MagicMock(return_value=None)
        runner.run()

        assert runner._generic_abort is None
        manifest = json.loads((second_dir / "reproducibility_manifest.json").read_text())
        assert "run_status" not in manifest
        assert "aborted_exception_type" not in manifest
        assert "llm_safeguard_abort" not in manifest
