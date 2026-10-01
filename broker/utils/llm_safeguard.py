"""Generic LLM-failure safeguard: backoff + abort-rate stop.

A framework-generic, opt-in safeguard against LLM provider failures. Nothing
in this module names a domain; the request that motivated it, its default
values, and the domain that enables it are recorded in that domain's own
config and docs, not here.

Two independent mechanisms, both driven by ``global_config.llm_safeguard``:

1. Backoff (:func:`wrap_llm_invoke_with_backoff`): retries a TRANSPORT
   failure -- an ``OSError`` (which includes ``requests.exceptions.
   ConnectionError``) raised by the call, or the existing ``LLMStats.
   transport_error`` flag some invoke functions already set for an
   equivalent failure they caught internally (a refused connection, an
   HTTP 5xx status) -- with exponential delay, capped at
   ``backoff_max_seconds``. It deliberately does NOT retry a timeout (the
   inner call already waited its own configured timeout; waiting again
   buys nothing), an HTTP 4xx (a persistent client-side problem), empty or
   thinking-only content (the model's own empty-content retry loop already
   tried), or a generic exception such as ``TypeError`` (not a transport
   blip). Wired once, at ``ExperimentRunner.get_llm_invoke`` -- the single
   place every LLM call in the framework passes through -- so every caller
   (the format-retry loop, the governance retry loop, the advisory pass, a
   decider) benefits without being touched individually. Every attempt's
   calls/tokens are folded into the returned ``LLMStats`` (see
   ``backoff_retries`` below), so a retried decision does not undercount
   its own real network calls. When backoff finally gives up on a transport
   failure, ``broker/core/_retry_loop.py``'s format-retry and governance
   retry loops both recognise the ``transport_error`` flag on that outcome
   and stop re-prompting the same connection at once, instead of paying the
   whole backoff schedule again on every remaining loop attempt.

2. Abort-rate stop (:class:`LLMAbortTracker`): a rolling window of the last
   ``abort_window`` DECISIONS (one entry per ``SkillBrokerEngine.process_step``
   call, not per raw LLM call). A decision counts as failed when the
   provider call ultimately failed OR its output could not be parsed --
   ``skill_proposal is None``, the same signal ``process_step`` already uses
   to call ``self.auditor.log_parse_error()``. It aborts EARLY: as soon as
   the number of failures in the current (possibly still partial) window
   reaches ``ceil(abort_threshold * abort_window)``, not only once the
   window is completely full -- the two rules agree once the window fills,
   but the early one catches a badly-broken run sooner. Once that count is
   reached, :class:`LLMFailureRateAborted` is raised, which
   ``ExperimentRunner`` is taught to let through (not swallow into another
   ABORTED row) so the run actually stops.

Both are OFF by default (``enabled=False``): :func:`wrap_llm_invoke_with_backoff`
then returns its input unchanged, and :meth:`LLMAbortTracker.record` is a
no-op. That is what keeps every existing domain's audit CSV and simulation
log byte-identical -- neither mechanism runs a single extra line of code for
a config that never mentions ``llm_safeguard``. Its manifest and
``governance_summary.json`` are NOT untouched, though: every domain (opted
in or not) gains an ``llm_safeguard`` manifest key and a ``backoff_retries``
counter (both showing the all-disabled/zero state when unused) -- these are
unconditional, additive fields, not something only an opted-in domain sees.
"""
from __future__ import annotations

import collections
import logging
import math
import threading
import time
from dataclasses import dataclass, replace as _dataclasses_replace
from typing import Any, Callable, Dict, Optional

import requests

from .llm_utils import LLMStats

_LOGGER = logging.getLogger(__name__)


class LLMSafeguardConfigError(ValueError):
    """A malformed ``global_config.llm_safeguard`` block."""


# backoff_max_retries is capped at 8 (a fix-round hardening): an operator
# typo of one extra zero must not turn into dozens of attempts against a
# genuinely dead endpoint, each waiting up to backoff_max_seconds.
_MAX_BACKOFF_RETRIES = 8

_DEFAULTS: Dict[str, Any] = {
    "enabled": False,
    "backoff_max_retries": 3,
    "backoff_initial_seconds": 2,
    "backoff_max_seconds": 60,
    "abort_window": 50,
    "abort_threshold": 0.5,
}


def validate_llm_safeguard_dict(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate and normalise a ``global_config.llm_safeguard`` block.

    Returns a dict with exactly the six keys, always present. ``None``
    (the block absent, the common case for every domain that has not opted
    in) returns the all-disabled defaults unchanged -- this is the byte-
    identity path for every pre-existing domain.

    Every value actually supplied is checked eagerly, the same "fail loud at
    config-read time" convention as the other ``global_config.governance.*``
    getters in ``broker/utils/agent_config.py``: the PI's framework-parameter
    rule (2026-09-25) is that a continuous share stays a fraction and every
    count is a positive integer, so ``abort_threshold`` must be a number in
    (0, 1] (0 rejected: a zero threshold aborts on the very first decision,
    which is never what "abort on failures" is meant to express, and reads
    as inert-vs-misconfigured with no signal either way) and
    ``backoff_max_retries`` / ``backoff_initial_seconds`` / ``abort_window``
    / ``backoff_max_seconds`` must each be a positive integer.
    ``backoff_max_retries`` additionally has a hard ceiling of 8. ``bool`` is
    rejected everywhere an int or float is expected even though ``bool`` is a
    Python ``int`` subclass -- ``enabled: 1`` reading as
    ``backoff_max_retries``-like would be a confusing way to fail.
    """
    if raw is None:
        return dict(_DEFAULTS)
    if not isinstance(raw, dict):
        raise LLMSafeguardConfigError(
            "global_config.llm_safeguard must be a mapping, got "
            f"{type(raw).__name__}"
        )
    unknown = sorted(set(raw) - set(_DEFAULTS))
    if unknown:
        raise LLMSafeguardConfigError(
            f"global_config.llm_safeguard has unknown key(s) {unknown}; "
            f"expected a subset of {sorted(_DEFAULTS)}"
        )

    out = dict(_DEFAULTS)

    if "enabled" in raw:
        if not isinstance(raw["enabled"], bool):
            raise LLMSafeguardConfigError(
                "global_config.llm_safeguard.enabled must be a bool, got "
                f"{raw['enabled']!r}"
            )
        out["enabled"] = raw["enabled"]

    for key in ("backoff_max_retries", "backoff_initial_seconds",
                "backoff_max_seconds", "abort_window"):
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise LLMSafeguardConfigError(
                f"global_config.llm_safeguard.{key} must be a positive "
                f"integer, got {value!r}"
            )
        if key == "backoff_max_retries" and value > _MAX_BACKOFF_RETRIES:
            raise LLMSafeguardConfigError(
                f"global_config.llm_safeguard.backoff_max_retries must be "
                f"<= {_MAX_BACKOFF_RETRIES}, got {value!r}"
            )
        out[key] = value

    if "abort_threshold" in raw:
        value = raw["abort_threshold"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise LLMSafeguardConfigError(
                "global_config.llm_safeguard.abort_threshold must be a "
                f"number in (0, 1], got {value!r}"
            )
        if not (0.0 < float(value) <= 1.0):
            raise LLMSafeguardConfigError(
                "global_config.llm_safeguard.abort_threshold must be in "
                f"(0, 1] (0 is rejected -- see this function's docstring), "
                f"got {value!r}"
            )
        out["abort_threshold"] = float(value)

    return out


@dataclass(frozen=True)
class LLMSafeguardConfig:
    """Resolved, validated ``global_config.llm_safeguard`` settings.

    Construct via :meth:`from_dict`, not directly -- that is what runs
    :func:`validate_llm_safeguard_dict` so a hand-built dict (a test, a
    programmatic caller) gets the same checks a YAML block does.
    """
    enabled: bool = False
    backoff_max_retries: int = 3
    backoff_initial_seconds: int = 2
    backoff_max_seconds: int = 60
    abort_window: int = 50
    abort_threshold: float = 0.5

    @classmethod
    def from_dict(cls, raw: Optional[Dict[str, Any]]) -> "LLMSafeguardConfig":
        return cls(**validate_llm_safeguard_dict(raw))


def wrap_llm_invoke_with_backoff(
    invoke: Callable, config: LLMSafeguardConfig,
) -> Callable:
    """Wrap ``invoke`` (the framework's ``llm_invoke(prompt) -> (content,
    LLMStats)`` contract) with retry and exponential backoff on a TRANSPORT
    failure only.

    Retried: ``invoke`` raising ``OSError`` (this includes ``requests.
    exceptions.ConnectionError``), or ``invoke`` returning normally with
    ``LLMStats.transport_error is True`` (the shape ``_invoke_ollama_direct``
    / ``create_provider_invoke``, ``broker/utils/llm_utils.py``, already use
    for a connection failure or an HTTP 5xx they caught internally).

    NEVER retried, even though each of these can also produce
    ``LLMStats.success is False``: a ``requests.exceptions.Timeout`` (the
    inner call already waited the full configured timeout; retrying doubles
    the wait for no benefit), an HTTP 4xx (a persistent client-side problem
    a retry cannot fix), empty or thinking-only content (the model's own
    empty-content retry loop, inside ``create_llm_invoke``, already tried and
    failed), or any other exception such as ``TypeError`` (not a transport
    blip -- likely a bug, and retrying it risks masking one).

    Every retry is logged at WARNING, the final give-up at ERROR -- never a
    silent swallow. Delay starts at ``backoff_initial_seconds``, doubles each
    retry, and is capped at ``backoff_max_seconds`` on every attempt (so a
    large ``backoff_initial_seconds`` or many retries cannot make a single
    wait balloon past the configured ceiling). After ``backoff_max_retries``
    retries (``backoff_max_retries + 1`` attempts total) the wrapper gives up
    and returns the LAST attempt's result: an empty ``success=False`` tuple
    for a raising provider, or whatever the provider itself last returned.
    Either way the caller (the existing format-retry loop, then the abort-rate
    tracker) sees exactly the failure shape it always has -- this is the
    "existing failure path continues exactly as today" the spec calls for.

    Every attempt this call makes -- including ones that failed and were
    retried -- is folded into the returned ``LLMStats``: ``calls`` and the
    two ``*_tokens_total`` fields are SUMMED across attempts (so a decision
    retried twice reports 3 real calls, not 1), and the new
    ``backoff_retries`` field records ``total_calls - stats.calls`` (fix
    round 4): the calls spent on the OTHER, non-final backoff attempts,
    excluding the final attempt's own call count so its own internal
    retries (already in its own ``stats.retries``) are not folded in twice.
    ``backoff_retries`` can still exceed "1 per backoff round" whenever a
    NON-final attempt's own call costs more than one raw request
    (``create_llm_invoke``'s outer closure has its own short empty-content
    retry loop) -- counting rounds would undercount exactly that case.
    Before this folding, a retried call's extra real network calls were
    invisible in the audit -- the caller only ever saw the last attempt's
    own numbers.

    ``config.enabled is False`` returns ``invoke`` UNCHANGED -- not a wrapper
    that immediately delegates, the SAME object -- which is what keeps every
    domain that never sets ``global_config.llm_safeguard`` byte-identical.
    """
    if not config.enabled:
        return invoke

    def _invoke_once(prompt: Any, *args: Any, **kwargs: Any):
        """``(result, succeeded, retryable)`` for one attempt."""
        try:
            result = invoke(prompt, *args, **kwargs)
        except requests.exceptions.Timeout as exc:
            _LOGGER.warning(
                "[LLM:Safeguard] provider call timed out (the inner call "
                "already waited its own timeout; not retried here): %s: %s",
                type(exc).__name__, exc,
            )
            return ("", LLMStats(retries=0, success=False)), False, False
        except OSError as exc:
            _LOGGER.warning(
                "[LLM:Safeguard] provider call raised a transport error "
                "%s: %s", type(exc).__name__, exc,
            )
            return (
                ("", LLMStats(retries=0, success=False, transport_error=True)),
                False, True,
            )
        except Exception as exc:  # noqa: BLE001 - generic by design, see module docstring
            _LOGGER.warning(
                "[LLM:Safeguard] provider call raised %s (not a transport "
                "failure; not retried): %s", type(exc).__name__, exc,
            )
            return ("", LLMStats(retries=0, success=False)), False, False
        if isinstance(result, tuple) and len(result) == 2:
            _content, stats = result
            if not bool(getattr(stats, "success", True)):
                return result, False, bool(getattr(stats, "transport_error", False))
        return result, True, False

    def _fold(result: Any, total_calls: int, total_prompt_tokens: int,
              total_response_tokens: int) -> Any:
        """Merge the accumulated call/token totals into the LAST attempt's
        stats object, so every other per-call field (success, latency,
        empty_content_*, ...) stays that attempt's own, unmodified.

        ``backoff_retries`` is ``total_calls - stats.calls`` (fix round 4,
        CRITICAL A): only the calls spent on the OTHER (non-final) backoff
        attempts. The final attempt's own ``stats.calls`` -- which can
        already be more than 1, from create_llm_invoke's own internal
        empty-content retry loop -- is excluded, because that attempt's own
        extra calls are already reflected in its own ``stats.retries``.
        Fix round 3's formula (``calls - 1``) folded the final attempt's own
        extra calls into ``backoff_retries`` and then added ``backoff_retries``
        onto ``stats.retries`` again, double-counting them whenever the
        final, successful attempt itself cost more than one raw call."""
        if not (isinstance(result, tuple) and len(result) == 2):
            return result
        content, stats = result
        calls = total_calls if total_calls > 0 else max(int(getattr(stats, "calls", 1) or 1), 1)
        stats_calls = max(int(getattr(stats, "calls", 1) or 1), 1)
        backoff_retries = max(calls - stats_calls, 0)
        merged = _dataclasses_replace(
            stats,
            calls=calls,
            prompt_tokens_total=total_prompt_tokens,
            response_tokens_total=total_response_tokens,
            retries=int(getattr(stats, "retries", 0) or 0) + backoff_retries,
            backoff_retries=backoff_retries,
        )
        return content, merged

    def wrapped(prompt: Any, *args: Any, **kwargs: Any):
        delay = min(config.backoff_initial_seconds, config.backoff_max_seconds)
        attempts_total = config.backoff_max_retries + 1
        result = None
        total_calls = 0
        total_prompt_tokens = 0
        total_response_tokens = 0
        for attempt in range(1, attempts_total + 1):
            result, ok, retryable = _invoke_once(prompt, *args, **kwargs)
            if isinstance(result, tuple) and len(result) == 2:
                _content, stats = result
                total_calls += max(int(getattr(stats, "calls", 1) or 1), 1)
                total_prompt_tokens += int(
                    getattr(stats, "prompt_tokens_total", None)
                    or getattr(stats, "prompt_tokens", 0) or 0
                )
                total_response_tokens += int(
                    getattr(stats, "response_tokens_total", None)
                    or getattr(stats, "response_tokens", 0) or 0
                )
            if ok or not retryable:
                return _fold(result, total_calls, total_prompt_tokens, total_response_tokens)
            if attempt < attempts_total:
                _LOGGER.warning(
                    "[LLM:Safeguard] transport failure (attempt %d/%d); "
                    "retrying in %ds.", attempt, attempts_total, delay,
                )
                time.sleep(delay)
                delay = min(delay * 2, config.backoff_max_seconds)
            else:
                _LOGGER.error(
                    "[LLM:Safeguard] transport failure persisted after %d "
                    "attempt(s); giving up -- the existing failure path "
                    "continues.", attempts_total,
                )
        return _fold(result, total_calls, total_prompt_tokens, total_response_tokens)

    return wrapped


class LLMFailureRateAborted(RuntimeError):
    """The rolling-window LLM failure count reached the abort threshold.

    ``ExperimentRunner._run_agents_sequential`` / ``_run_agents_parallel``
    re-raise this specifically, ahead of their normal broad ``except
    Exception`` (which turns a raising ``process_step`` into just another
    ABORTED row and keeps the run going) -- this exception is meant to stop
    the run, not become one more row.
    """

    def __init__(
        self, observed_rate: float, window: int, threshold: float,
        failed_count: int, decisions_in_window: int,
    ):
        self.observed_rate = observed_rate
        self.window = window
        self.threshold = threshold
        # Fix round 3, WARNING 3: the raw counts behind observed_rate, so a
        # reader is not left reconstructing them from a rounded percentage.
        # decisions_in_window can be LESS than window -- early-stop (see
        # LLMAbortTracker.record) can fire before the window ever fills.
        self.failed_count = failed_count
        self.decisions_in_window = decisions_in_window
        super().__init__(
            f"LLM failure rate {observed_rate:.1%} "
            f"({failed_count}/{decisions_in_window} decisions in the current "
            f"window) reached the abort threshold {threshold:.1%} of the "
            f"configured {window}-decision window; stopping the run."
        )


class LLMAbortTracker:
    """Rolling window of the last ``config.abort_window`` LLM decisions.

    Aborts EARLY: as soon as the number of failures in the current window
    (which may still be partially filled) reaches
    ``ceil(abort_threshold * abort_window)``, not only once the window is
    completely full. The two phrasings describe the same eventual outcome
    for a run whose failure rate stays constant, but the count-based one
    catches a badly-broken endpoint sooner -- a run that fails every single
    decision reaches ``ceil(threshold * window)`` failures well before it
    reaches ``window`` decisions.

    Thread-safe: ``SkillBrokerEngine`` (the intended owner of one tracker
    instance) is shared across the ``ThreadPoolExecutor`` that
    ``ExperimentRunner._run_agents_parallel`` uses for ``--workers > 1``
    runs, so more than one thread can call :meth:`record` concurrently. A
    fresh instance per engine -- never a module-level singleton -- so two
    engines in one process (two tests, two arms of one script) never share a
    window or a config.
    """

    def __init__(self, config: LLMSafeguardConfig):
        self._config = config
        self._lock = threading.Lock()
        self._window: "collections.deque[bool]" = collections.deque(
            maxlen=max(int(config.abort_window), 1)
        )

    def record(self, failed: bool) -> None:
        """Record one decision's outcome.

        Raises :class:`LLMFailureRateAborted` as soon as the failure count in
        the current window reaches ``ceil(abort_threshold * abort_window)``,
        which can happen before the window is full. A no-op when the
        safeguard is disabled.
        """
        if not self._config.enabled:
            return
        with self._lock:
            self._window.append(bool(failed))
            failed_count = sum(self._window)
            window_len = len(self._window)
        threshold_count = math.ceil(self._config.abort_threshold * self._config.abort_window)
        if failed_count >= threshold_count:
            rate = (failed_count / window_len) if window_len else 0.0
            raise LLMFailureRateAborted(
                observed_rate=rate,
                window=self._config.abort_window,
                threshold=self._config.abort_threshold,
                failed_count=failed_count,
                decisions_in_window=window_len,
            )
