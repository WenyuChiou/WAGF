"""Per-run log of every model call: ``llm_calls.jsonl``.

One JSON line per call, flushed as it is written, so a reviewer can see exactly what the
model was sent and what it returned. The log only observes: it never changes a prompt or a
reply, and a failed write is counted (``write_failures``) instead of raised.

Who records:

* ``_invoke_ollama_direct`` (broker/utils/llm_utils.py) records every HTTP request it makes,
  with the options it really sent and Ollama's own counts and ``done_reason``.
* ``wrap_invoke_with_call_log`` (used by ``ExperimentRunner.get_llm_invoke``) records the
  calls nothing else records: the mock model and cloud providers.

Which agent, year, call kind and attempt a call belongs to is carried in a context variable
(``call_context``). The retry loops and the reflection code set it around their model calls.
Each worker thread sets its own, so parallel agents do not mix.

Optional per-call sampling seed (``global_config.llm.sampling_seed: per_call``, default off):
``sampling_seed_for_call`` returns a stable hash of (run seed, agent id, year, call kind,
attempt), which ``_build_ollama_options`` puts in the Ollama request as ``options.seed``.
"""
from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

LOG_FILENAME = "llm_calls.jsonl"
CALL_KINDS = ("decision", "decision_retry", "reflection", "reflection_retry", "other")
OPTION_KEYS = ("model", "temperature", "top_p", "top_k", "num_ctx", "num_predict", "think", "seed")
SEED_MODES = ("off", "per_call")

_CTX: "contextvars.ContextVar[Optional[dict]]" = contextvars.ContextVar(
    "wagf_llm_call_context", default=None)


def utc_now_iso() -> str:
    """Current UTC time as ISO 8601 with a trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "backslashreplace")).hexdigest()


# --------------------------------------------------------------------------- context

@contextlib.contextmanager
def call_context(*, agent_id: Any = None, agent_ids: Any = None, agent_type: Any = None,
                 year: Any = None, kind: Optional[str] = None, attempt: Optional[int] = None,
                 **extra: Any) -> Iterator[dict]:
    """Merge the given fields onto the current call context for the ``with`` block.

    ``None`` leaves the existing value alone. ``agent_id`` is shorthand for a one-item
    ``agent_ids``. Yields the merged context dict.
    """
    ctx = dict(_CTX.get() or {})
    if agent_ids is None and agent_id is not None:
        agent_ids = [agent_id]
    if agent_ids is not None:
        ctx["agent_ids"] = [str(a) for a in agent_ids]
    if agent_type is not None:
        ctx["agent_type"] = agent_type
    if year is not None:
        ctx["year"] = year
    if kind is not None:
        if kind not in CALL_KINDS:
            raise ValueError(f"call kind must be one of {CALL_KINDS}, got {kind!r}")
        ctx["kind"] = kind
    if attempt is not None:
        ctx["attempt"] = int(attempt)
    for key, value in extra.items():
        if value is not None:
            ctx[key] = value
    token = _CTX.set(ctx)
    try:
        yield ctx
    finally:
        _CTX.reset(token)


def current_context() -> dict:
    return dict(_CTX.get() or {})


def year_of(env_context: Any) -> Any:
    """The decision year out of a step's environment dict (``current_year``), else None."""
    if isinstance(env_context, dict):
        value = env_context.get("current_year")
        if isinstance(value, (int, float, str)) and not isinstance(value, bool):
            return value
    return None


# --------------------------------------------------------------------------- the log

class LLMCallLog:
    """Append-only JSONL writer plus the tallies the integrity block reports."""

    def __init__(self, path: Any):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._fh = None
        self.calls = 0
        self.calls_done_reason_length = 0
        self.calls_prompt_eval_count_ge_num_ctx = 0
        self.calls_with_done_reason = 0
        self.calls_with_prompt_eval_count = 0
        self.max_prompt_eval_count: Optional[int] = None
        self.write_failures = 0
        # First failure to record a call, kept until the run stops on it
        # (ExperimentRunner raises RunRecordsError at the next step end or at finalize).
        self.failure: Optional[str] = None
        self._roles: dict = {}
        self._index = self._existing_lines()

    def _existing_lines(self) -> int:
        """Lines already in the file (a resumed run appends and keeps counting)."""
        try:
            if self.path.is_file():
                with self.path.open("rb") as fh:
                    return sum(1 for line in fh if line.strip())
        except OSError:
            pass
        return 0

    def record(self, *, prompt: Any, reply: Any, options: Optional[dict] = None,
               prompt_eval_count: Optional[int] = None, eval_count: Optional[int] = None,
               done_reason: Optional[str] = None, wall_seconds: Optional[float] = None,
               error: Optional[str] = None, ctx: Optional[dict] = None,
               started_at_utc: Optional[str] = None) -> None:
        ctx = ctx if ctx is not None else (_CTX.get() or {})
        prompt_text = prompt if isinstance(prompt, str) else ("" if prompt is None else str(prompt))
        reply_text = reply if (isinstance(reply, str) or reply is None) else str(reply)
        opts = {k: None for k in OPTION_KEYS}
        for key, value in (options or {}).items():
            if key in opts:
                opts[key] = value
        kind = ctx.get("kind") or "other"
        with self._lock:
            self._index += 1
            record = {
                "call_index": self._index,
                "started_at_utc": started_at_utc or utc_now_iso(),
                "agent_ids": list(ctx.get("agent_ids") or []),
                "agent_type": ctx.get("agent_type"),
                "year": ctx.get("year"),
                "kind": kind,
                "attempt": ctx.get("attempt", 1),
                "prompt": prompt_text,
                "prompt_sha256": _sha256(prompt_text),
                "reply": reply_text,
                "options": opts,
                "prompt_eval_count": prompt_eval_count,
                "eval_count": eval_count,
                "done_reason": done_reason,
                "wall_seconds": None if wall_seconds is None else round(float(wall_seconds), 3),
                "error": error,
            }
            self.calls += 1
            role = "decision" if kind.startswith("decision") else (
                "reflection" if kind.startswith("reflection") else "other")
            slot = self._roles.setdefault(role, {})
            key = (ctx.get("agent_type"), opts.get("model"))
            slot[key] = slot.get(key, 0) + 1
            if done_reason is not None:
                self.calls_with_done_reason += 1
                if done_reason == "length":
                    self.calls_done_reason_length += 1
            if isinstance(prompt_eval_count, int) and not isinstance(prompt_eval_count, bool):
                self.calls_with_prompt_eval_count += 1
                if self.max_prompt_eval_count is None or prompt_eval_count > self.max_prompt_eval_count:
                    self.max_prompt_eval_count = prompt_eval_count
                num_ctx = opts.get("num_ctx")
                if isinstance(num_ctx, int) and not isinstance(num_ctx, bool) \
                        and prompt_eval_count >= num_ctx:
                    self.calls_prompt_eval_count_ge_num_ctx += 1
            try:
                if self._fh is None:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    self._fh = self.path.open("a", encoding="utf-8", errors="backslashreplace",
                                              newline="\n")
                self._fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                self._fh.flush()
            except (OSError, ValueError) as exc:
                self.write_failures += 1
                if self.failure is None:
                    self.failure = f"could not write {self.path}: {type(exc).__name__}: {exc}"
                if self.write_failures == 1:
                    logger.error("[LLMCallLog] could not write %s (%s); the run will stop at "
                                 "the next step end.", self.path, exc)

    def close(self) -> None:
        with self._lock:
            if self._fh is not None:
                try:
                    self._fh.close()
                except OSError:
                    pass
                self._fh = None

    def file_sha256(self) -> Optional[str]:
        """sha256 of the file as it is now, or None when nothing was written."""
        try:
            if not self.path.is_file():
                return None
            digest = hashlib.sha256()
            with self.path.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except OSError:
            return None

    def roles_used(self) -> dict:
        """``{role: {"calls": n, "agent_type_models": [(agent_type, model, calls), ...]}}``.

        Roles are ``decision`` (first calls and governance retries), ``reflection`` and
        ``other``. Counts the calls made by this process; a resumed run counts only its own.
        """
        with self._lock:
            return {role: {"calls": sum(slot.values()),
                           "agent_type_models": sorted(
                               ((k[0], k[1], n) for k, n in slot.items()),
                               key=lambda x: (str(x[0]), str(x[1])))}
                    for role, slot in self._roles.items()}

    def summary(self) -> dict:
        """The block the manifest and run_integrity.json carry. Counts only: no verdict."""
        with self._lock:
            return {
                "file": self.path.name,
                "file_sha256": None,  # filled by the caller after close()
                "calls_logged": self.calls,
                "calls_done_reason_length": self.calls_done_reason_length,
                "calls_prompt_eval_count_ge_num_ctx": self.calls_prompt_eval_count_ge_num_ctx,
                "max_prompt_eval_count": self.max_prompt_eval_count,
                "calls_with_done_reason": self.calls_with_done_reason,
                "calls_with_prompt_eval_count": self.calls_with_prompt_eval_count,
                "write_failures": self.write_failures,
            }


_ACTIVE: Optional[LLMCallLog] = None


def activate(log: Optional[LLMCallLog]) -> None:
    global _ACTIVE
    _ACTIVE = log


def deactivate(log: Optional[LLMCallLog] = None) -> None:
    """Stop recording. With ``log`` given, only when it is still the active one."""
    global _ACTIVE
    if log is None or _ACTIVE is log:
        _ACTIVE = None


def active_log() -> Optional[LLMCallLog]:
    return _ACTIVE


def record_llm_call(*, prompt: Any, reply: Any, options: Optional[dict] = None,
                    prompt_eval_count: Optional[int] = None, eval_count: Optional[int] = None,
                    done_reason: Optional[str] = None, wall_seconds: Optional[float] = None,
                    error: Optional[str] = None,
                    started_at_utc: Optional[str] = None) -> None:
    """Record one call in the active log (no-op without one); never raises."""
    log = _ACTIVE
    if log is None:
        return
    try:
        ctx = _CTX.get() or {}
        counter = ctx.get("_recorded")
        if isinstance(counter, list) and counter:
            counter[0] += 1
        log.record(prompt=prompt, reply=reply, options=options,
                   prompt_eval_count=prompt_eval_count, eval_count=eval_count,
                   done_reason=done_reason, wall_seconds=wall_seconds, error=error, ctx=ctx,
                   started_at_utc=started_at_utc)
    except Exception as exc:  # noqa: BLE001 - raised later, at a step end, never inside a call
        # A model call must not be mistaken for a failed call, so the error is kept on the log
        # and the runner stops the run with it at the next step end.
        log.write_failures += 1
        if log.failure is None:
            log.failure = f"record failed: {type(exc).__name__}: {exc}"
        logger.error("[LLMCallLog] record failed: %s: %s", type(exc).__name__, exc)


def options_for_log(resolved: Optional[dict], model: Any) -> dict:
    """The OPTION_KEYS subset of a resolved-params dict, for calls recorded by the wrapper.

    ``seed`` is the per-call seed that applies to this call (the mock model never sends it;
    a cloud provider has none), so a mock run's log shows the same seeds a real run would send.
    """
    out = {k: (resolved or {}).get(k) for k in OPTION_KEYS}
    out["model"] = model if isinstance(model, str) else out.get("model")
    is_cloud = isinstance(model, str) and ":" in model and \
        model.split(":", 1)[0].lower() in _cloud_providers()
    out["seed"] = None if is_cloud else sampling_seed_for_call()
    return out


def _cloud_providers() -> Any:
    from broker.utils.llm_utils import KNOWN_CLOUD_PROVIDERS
    return KNOWN_CLOUD_PROVIDERS


def wrap_invoke_with_call_log(invoke: Callable, *, model: Any, agent_type: Any,
                              resolved: Optional[dict] = None) -> Callable:
    """Wrap an invoke function so a call nothing else recorded is still logged.

    The reply is passed through untouched. A call the Ollama layer already recorded is not
    recorded twice.
    """
    def logged(prompt, *args, **kwargs):
        log = _ACTIVE
        if log is None:
            return invoke(prompt, *args, **kwargs)
        recorded = [0]
        extra = {"_recorded": recorded}
        if not (_CTX.get() or {}).get("agent_type"):
            extra["agent_type"] = agent_type
        started = utc_now_iso()
        t0 = time.perf_counter()
        with call_context(**extra):
            try:
                result = invoke(prompt, *args, **kwargs)
            except BaseException as exc:
                if not recorded[0]:
                    record_llm_call(prompt=prompt, reply=None,
                                    options=options_for_log(resolved, model),
                                    wall_seconds=time.perf_counter() - t0,
                                    error=type(exc).__name__, started_at_utc=started)
                raise
            if not recorded[0]:
                reply, stats = (result if isinstance(result, tuple) and len(result) == 2
                                else (result, None))
                tokens_in = getattr(stats, "prompt_tokens", 0) or 0
                tokens_out = getattr(stats, "response_tokens", 0) or 0
                record_llm_call(
                    prompt=prompt, reply=reply, options=options_for_log(resolved, model),
                    prompt_eval_count=tokens_in or None, eval_count=tokens_out or None,
                    done_reason=getattr(stats, "done_reason", None),
                    wall_seconds=time.perf_counter() - t0, started_at_utc=started,
                    error=None if getattr(stats, "success", True) else "call_failed")
            return result

    logged.__wrapped__ = invoke  # the callable that was wrapped (functools convention)
    return logged


# --------------------------------------------------------------------------- seed

_SEED_STATE: Dict[str, Any] = {"mode": "off", "run_seed": None}


def normalise_seed_mode(value: Any) -> str:
    """``global_config.llm.sampling_seed`` -> ``off`` or ``per_call``; anything else raises."""
    if value is None or value is False:
        return "off"
    if isinstance(value, str) and value.strip().lower() in ("", "off", "none", "false"):
        return "off"
    if isinstance(value, str) and value.strip().lower() == "per_call":
        return "per_call"
    raise ValueError(
        f"global_config.llm.sampling_seed must be off (the default) or per_call, got {value!r}")


def configure_sampling_seed(mode: Any, run_seed: Any) -> str:
    resolved = normalise_seed_mode(mode)
    _SEED_STATE["mode"] = resolved
    _SEED_STATE["run_seed"] = run_seed
    return resolved


def sampling_seed_mode() -> str:
    return _SEED_STATE["mode"]


def derive_call_seed(run_seed: Any, agent_ids: Any, year: Any, kind: Any, attempt: Any) -> int:
    """Stable seed from (run seed, agent id(s), year, call kind, attempt); 0 <= seed < 2**31."""
    if isinstance(agent_ids, (list, tuple)):
        agents = ",".join(sorted(str(a) for a in agent_ids))
    else:
        agents = "" if agent_ids is None else str(agent_ids)
    key = f"{run_seed}|{agents}|{year}|{kind}|{attempt}"
    return int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big") % (2 ** 31)


def describe_call_seed(mode: Any, run_seed: Any) -> dict:
    """How each call's Ollama ``seed`` is derived (``derive_call_seed``), for the manifest."""
    return {
        "mode": mode,
        "base_seed": run_seed,
        "function": "broker.utils.llm_call_log.derive_call_seed",
        "inputs": ["base_seed", "agent_ids", "year", "kind", "attempt"],
        "formula": ("seed = int.from_bytes(sha256(key.encode('utf-8')).digest()[:8], 'big') % 2**31; "
                    "key = f'{base_seed}|{agents}|{year}|{kind}|{attempt}'; "
                    "agents = ','.join(sorted(str(a) for a in agent_ids)) for a list or tuple, "
                    "'' for None, else str(agent_ids)"),
        "kind_values": list(CALL_KINDS),
        "applies": "only when mode == 'per_call'; otherwise no seed is sent",
    }


def sampling_seed_for_call() -> Optional[int]:
    """The seed to send with this call, or None when per-call seeding is off."""
    if _SEED_STATE["mode"] != "per_call":
        return None
    ctx = _CTX.get() or {}
    return derive_call_seed(_SEED_STATE["run_seed"], ctx.get("agent_ids"), ctx.get("year"),
                            ctx.get("kind") or "other", ctx.get("attempt", 1))
