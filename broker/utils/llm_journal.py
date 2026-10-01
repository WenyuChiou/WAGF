"""Deterministic-replay journal for LLM invoke calls.

Problem this solves: a long batch (tens of real-LLM hours) has no
checkpoint, so a crash or a reboot partway through throws away every
completed step's GPU work.

Design: resume by DETERMINISTIC REPLAY of recorded responses, not by
serialising runtime state. Every call made through the invoke this module
wraps is journaled (prompt hash, returned content/stats, or the raised
exception). To resume, the caller re-executes its control flow from the
beginning on the CPU; for each step already completed in a prior attempt,
this module answers every LLM call from the journal instead of making a
live call, so the surrounding code (whatever state it keeps, however it
mutates it) rebuilds itself by running the SAME code paths that built it
the first time. Once the replay reaches the first step that was never
completed, calls go live again and are recorded into a new journal.

A call during replay is matched to its recorded answer purely by
``(agent_type, prompt hash)`` (see :func:`hash_prompt_call`). A call that
has no matching record is a DIVERGENCE: the rebuilt run asked something
the first run never asked (or asked it differently), which means the
state being rebuilt is not actually the same state, and continuing would
silently fabricate a decision history. :class:`JournalReplayDivergence`
is raised instead of ever falling back to a live call -- the divergence
itself is also the proof, on the HAPPY path, that the rebuild was exact:
if every recorded call for every replayed step was consumed with nothing
left over, the two states could not have differed anywhere the LLM path
can see.

STICKY errors: a caller of the wrapped invoke can have its own broad
``except Exception`` (a batch-reflection loop, an advisory pass) that
would otherwise swallow a :class:`JournalReplayDivergence` or
:class:`JournalWriteError` raised mid-step -- the exception never reaches
``run()``'s own (un-swallowed) code, so the run would silently continue
on a rebuild that is no longer proven exact. Both exceptions are stored on
the manager the moment they happen (see ``_replay_one`` /
``_record_call_safely``) and re-raised unconditionally at the next
:meth:`LLMJournalManager.step_end` call -- which always runs from ``run()``
itself, never from inside a per-agent try/except -- so a swallowed
exception still stops the run at the next step boundary at the latest.

No knowledge of any particular caller's domain lives here: this module
only knows "an invoke is a callable that takes a prompt (and optionally
extra positional/keyword arguments) and returns ``(content, stats)`` or a
bare value, and sometimes raises." The seam that wires this into the
experiment loop is ``broker/core/experiment_runner.py``
(``ExperimentRunner.get_llm_invoke``); domain-specific identifying-config
checks (which CLI flags make two runs "the same experiment") belong to the
domain's own runner script, which reads a source journal's header via
:func:`read_journal_header` and should fail fast with
:func:`check_identifying_config` before any heavy setup runs. A caller's
identifying-config dict must exclude :data:`RESUME_PROVENANCE_KEY` (e.g.
via ``allowed_to_differ``): that key records how THIS run's own journal
came to exist (resumed_from / source_journal_sha256 /
replay_last_complete_step), not what experiment it is, and a run that was
itself resumed carries it in its own header -- comparing it like any other
identifying field would make a once-resumed run impossible to resume again.

Known limitation: a replayed exception is reconstructed from its type NAME
and message only (see :func:`_reraise_recorded_exception`). A builtin
exception type (``OSError``, ``ValueError``, ``RuntimeError``, ...)
reconstructs exactly. A custom exception class whose constructor needs more
than a single message argument cannot be reconstructed byte-for-byte;
replay raises :class:`JournalReplayedException` instead, carrying the
original type name and message in its own message, so the failure is still
visible and still stops the run -- it is just not the identical Python
class. In the production invoke chain this module actually wraps
(``broker.utils.llm_utils.create_llm_invoke`` and
``broker.utils.llm_safeguard.wrap_llm_invoke_with_backoff``), every
provider failure is already converted to a non-raising
``(content, stats)`` return with ``stats.success == False`` before it
would ever reach here, so this path is a defensive generic capability, not
something the shipped invokes are expected to exercise.
"""
from __future__ import annotations

import builtins
import dataclasses
import hashlib
import json
import os
import threading
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional, Tuple

from .llm_utils import LLMStats

FORMAT_VERSION = 1

#: The header key a resumed run's own journal nests its resume provenance
#: under (see the module docstring's "STICKY errors" section above it, and
#: :class:`LLMJournalManager`). Never an identifying field: a caller's
#: identifying-config comparison must pass this in ``allowed_to_differ``.
RESUME_PROVENANCE_KEY = "resume_provenance"

_LLMSTATS_FIELDS = {f.name for f in dataclasses.fields(LLMStats)}

_PoolKey = Tuple[str, str, Optional[str]]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class JournalReplayDivergence(RuntimeError):
    """A replayed step's call stream does not match the source journal.

    Raised instead of ever falling back to a live call: a caller rebuilding
    its state from replay must get a hard error the moment the rebuild is
    no longer proven exact, not a run that silently continues on a
    different footing than the one it is supposedly resuming. Also STICKY
    (see the module docstring): stored on the manager when raised, and
    re-raised at the next ``step_end`` even if this specific raise was
    caught and swallowed somewhere in between.
    """

    def __init__(
        self,
        message: str,
        *,
        step: int,
        agent_type: Optional[str] = None,
        prompt_sha256: Optional[str] = None,
    ):
        self.step = step
        self.agent_type = agent_type
        self.prompt_sha256 = prompt_sha256
        super().__init__(message)


class JournalWriteError(RuntimeError):
    """Writing a call record to the output journal failed (e.g. disk full).

    Raised at the next ``step_end``, never at the call site itself: a
    caller of the wrapped invoke (the format-retry loop, the governance
    retry loop) is reachable from there, and its own broad ``except
    Exception`` would otherwise mistake a journal-write failure for the
    MODEL call failing, burning a retry (or a re-prompt) on a problem that
    has nothing to do with the response. STICKY like
    :class:`JournalReplayDivergence` -- see the module docstring.
    """


class JournalReplayedException(RuntimeError):
    """Raised on replay in place of a recorded exception whose own type
    could not be reconstructed from its name and message alone (not a
    resolvable builtin, or its constructor rejects a single string
    argument). Carries the original type name and message in its own
    message so the failure is still named precisely, even though the
    raised Python class is this one, not the original.
    """


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="surrogatepass")).hexdigest()


def hash_prompt_call(
    prompt: Any, args: Tuple[Any, ...], kwargs: Dict[str, Any]
) -> Tuple[str, Optional[str]]:
    """``(prompt_sha256, extra_sha256)`` identifying one invoke call.

    ``extra_sha256`` is ``None`` when the call carried no positional
    arguments beyond the prompt and no keyword arguments -- every call
    site in this repository invokes ``llm_invoke(prompt)`` with nothing
    else, so in practice this is always ``None`` and the matching key
    (see :class:`LLMJournalManager`) degenerates to the prompt hash alone,
    exactly as a caller reading "keyed by (agent_type, prompt hash)" would
    expect. A non-string prompt (never produced by any invoke in this
    repo today, but not assumed away) is hashed via its canonical JSON
    form rather than failing.
    """
    prompt_text = prompt if isinstance(prompt, str) else _canonical_json(prompt)
    prompt_sha256 = _hash_text(prompt_text)
    extra_sha256 = None
    if args or kwargs:
        extra_sha256 = _hash_text(_canonical_json({"args": list(args), "kwargs": kwargs}))
    return prompt_sha256, extra_sha256


# ---------------------------------------------------------------------------
# Exception type resolution (record <-> re-raise)
# ---------------------------------------------------------------------------

def _resolve_exception_class(type_name: str) -> Optional[type]:
    candidate = getattr(builtins, type_name, None)
    if isinstance(candidate, type) and issubclass(candidate, BaseException):
        return candidate
    return None


def _reraise_recorded_exception(exception_type: str, exception_message: str) -> None:
    """Re-raise a recorded ``(exception_type, exception_message)`` pair.

    Always raises; never returns. See the module docstring's "Known
    limitation" paragraph for what happens when ``exception_type`` cannot
    be reconstructed.
    """
    cls = _resolve_exception_class(exception_type)
    if cls is not None:
        try:
            raise cls(exception_message)
        except TypeError:
            pass
    raise JournalReplayedException(f"{exception_type}: {exception_message}")


# ---------------------------------------------------------------------------
# LLMStats <-> JSON
# ---------------------------------------------------------------------------

def _stats_to_jsonable(stats_obj: Any) -> Optional[Dict[str, Any]]:
    if stats_obj is None:
        return None
    if dataclasses.is_dataclass(stats_obj):
        return dataclasses.asdict(stats_obj)
    try:
        return dict(vars(stats_obj))
    except TypeError:
        return None


def _stats_from_dict(data: Optional[Dict[str, Any]]) -> Optional[LLMStats]:
    if data is None:
        return None
    # Only fields LLMStats itself declares: a record from a newer/older
    # broker build must not fail reconstruction over an unknown or
    # missing field (forward/backward compatibility); a missing field
    # just takes the dataclass default.
    filtered = {k: v for k, v in data.items() if k in _LLMSTATS_FIELDS}
    return LLMStats(**filtered)


def _split_result_for_record(result: Any) -> Tuple[str, Any, Optional[Dict[str, Any]]]:
    """``(shape, content, stats_jsonable)`` for one invoke return value.

    ``shape`` is ``"tuple"`` for the production ``(content, LLMStats)``
    contract (``broker.utils.llm_utils.create_llm_invoke``'s own return
    type), or ``"bare"`` for anything else (the legacy
    ``Callable[[str], str]`` contract some decider callables still use).
    """
    if isinstance(result, tuple) and len(result) == 2 and dataclasses.is_dataclass(result[1]):
        content, stats_obj = result
        return "tuple", content, _stats_to_jsonable(stats_obj)
    return "bare", result, None


def _restore_result_from_record(rec: Dict[str, Any]) -> Any:
    shape = rec.get("shape", "tuple")
    content = rec.get("content")
    if shape == "bare":
        return content
    return content, _stats_from_dict(rec.get("stats"))


# ---------------------------------------------------------------------------
# Writer (recording)
# ---------------------------------------------------------------------------

class LLMJournalWriter:
    """Append-only, thread-safe JSONL sink for one run's LLM calls.

    One JSON record per line. Every record is flushed before the write
    call returns; ``os.fsync`` runs too UNLESS the caller passes
    ``fsync=False`` (used only when bulk-copying already-proven records
    from a source journal -- see
    ``LLMJournalManager._mirror_replayable_steps_into_new_journal`` --
    where a single fsync at the following ``step_end`` covers the whole
    batch instead of paying one fsync per mirrored record). Every LIVE
    call record (``ExperimentRunner``'s actual per-decision calls) keeps
    the default ``fsync=True``, so a record that reached the file during a
    live run survives a hard crash immediately afterward, same as before.

    Always creates a FRESH file (truncates if one exists at the path):
    a resumed run never modifies its source journal, so the output
    path is always a NEW path (never the source path) -- enforced by
    :class:`LLMJournalManager`, not by this class.
    """

    def __init__(self, path: Path, header: Dict[str, Any]):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._fh = open(self._path, "w", encoding="utf-8")
        self._write_record({"type": "header", "format_version": FORMAT_VERSION, **header})

    def _write_record(self, record: Dict[str, Any], *, fsync: bool = True) -> None:
        line = json.dumps(record, sort_keys=True)
        with self._lock:
            self._fh.write(line + "\n")
            self._fh.flush()
            if fsync:
                os.fsync(self._fh.fileno())

    def record_call(
        self,
        *,
        step: int,
        agent_type: str,
        prompt_sha256: str,
        extra_sha256: Optional[str],
        raised: bool,
        shape: str = "tuple",
        content: Any = None,
        stats: Optional[Dict[str, Any]] = None,
        exception_type: Optional[str] = None,
        exception_message: Optional[str] = None,
        fsync: bool = True,
    ) -> None:
        self._write_record({
            "type": "call",
            "step": step,
            "agent_type": agent_type,
            "prompt_sha256": prompt_sha256,
            "extra_sha256": extra_sha256,
            "raised": raised,
            "shape": shape,
            "content": content,
            "stats": stats,
            "exception_type": exception_type,
            "exception_message": exception_message,
        }, fsync=fsync)

    def record_step_end(self, step: int) -> None:
        # Always fsync'd (default True): this is the record a resume's
        # truncation point depends on, and it is also where a bulk mirror
        # copy's deferred fsync (fsync=False on each mirrored call record)
        # finally lands on disk -- see the class docstring.
        self._write_record({"type": "step_end", "step": step})

    def close(self) -> None:
        with self._lock:
            try:
                self._fh.close()
            except Exception:
                pass


def _call_kwargs_from_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "step": rec["step"],
        "agent_type": rec["agent_type"],
        "prompt_sha256": rec["prompt_sha256"],
        "extra_sha256": rec.get("extra_sha256"),
        "raised": bool(rec.get("raised", False)),
        "shape": rec.get("shape", "tuple"),
        "content": rec.get("content"),
        "stats": rec.get("stats"),
        "exception_type": rec.get("exception_type"),
        "exception_message": rec.get("exception_message"),
    }


# ---------------------------------------------------------------------------
# Reader (resume source)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class LoadedJournal:
    header: Dict[str, Any]
    last_complete_step: int
    pools: Dict[int, Dict[_PoolKey, "Deque[Dict[str, Any]]"]]
    sha256: str


def _check_format_version(path: Path, record: Dict[str, Any]) -> None:
    if record.get("format_version") != FORMAT_VERSION:
        raise ValueError(
            f"{path}: journal format_version {record.get('format_version')!r} "
            f"is not the version this code reads ({FORMAT_VERSION!r})."
        )


def read_journal_header(path: Path) -> Dict[str, Any]:
    """The header record only (first line), for a fast pre-flight check
    before any heavy setup (loading data, building agents) runs. Checks
    ``format_version`` before returning anything -- an incompatible
    journal must be refused at THIS cheap read, not only later when
    :func:`load_journal_for_resume` parses the whole file after heavy
    setup has already run. Raises ``ValueError`` if the file is empty, its
    first line is not a header record, or the version does not match.
    """
    path = Path(path)
    with open(path, "r", encoding="utf-8") as fh:
        first_line = fh.readline()
    if not first_line.strip():
        raise ValueError(f"{path}: empty journal file (no header record).")
    record = json.loads(first_line)
    if record.get("type") != "header":
        raise ValueError(f"{path}: first record is not a header record.")
    _check_format_version(path, record)
    return {k: v for k, v in record.items() if k not in ("type", "format_version")}


def load_journal_for_resume(path: Path) -> LoadedJournal:
    """Parse a source journal for resume, tolerating a truncated or
    corrupt FINAL line (the power-loss case) and dropping any step that
    never reached its own ``step_end`` marker (a partial step).

    Only the file's LAST line may fail to parse as JSON; an earlier bad
    line is a different, worse problem (mid-file corruption, not "the
    writer died mid-record") and is raised rather than silently skipped.
    """
    path = Path(path)
    raw_bytes = path.read_bytes()
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    text = raw_bytes.decode("utf-8", errors="surrogatepass")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # trailing newline, not a record

    records: List[Dict[str, Any]] = []
    for i, line in enumerate(lines):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            if i == len(lines) - 1:
                break  # tolerated: a truncated/corrupt final write
            raise ValueError(
                f"{path}: line {i + 1} of {len(lines)} is not valid JSON and "
                f"is not the file's last line -- this is mid-file corruption, "
                f"not a tolerated truncated final write."
            )

    if not records or records[0].get("type") != "header":
        raise ValueError(f"{path}: missing or malformed header record.")
    _check_format_version(path, records[0])
    header = {k: v for k, v in records[0].items() if k not in ("type", "format_version")}

    pools: Dict[int, Dict[_PoolKey, Deque]] = defaultdict(lambda: defaultdict(deque))
    last_complete_step = 0
    for rec in records[1:]:
        rtype = rec.get("type")
        if rtype == "call":
            step = rec["step"]
            key: _PoolKey = (rec["agent_type"], rec["prompt_sha256"], rec.get("extra_sha256"))
            pools[step][key].append(rec)
        elif rtype == "step_end":
            step = rec["step"]
            if step > last_complete_step:
                last_complete_step = step
        # Any other record type is ignored (forward-compatibility), not fatal.

    # A step with calls but no step_end marker never completed in the
    # source run; drop it rather than replay a partial step.
    pools = {step: per_step for step, per_step in pools.items() if step <= last_complete_step}

    return LoadedJournal(
        header=header, last_complete_step=last_complete_step, pools=pools, sha256=sha256,
    )


# ---------------------------------------------------------------------------
# Identifying-config check (generic; domain decides what goes in the dicts)
# ---------------------------------------------------------------------------

def check_identifying_config(
    source_config: Dict[str, Any],
    current_config: Dict[str, Any],
    *,
    allowed_to_differ: Iterable[str] = (),
) -> None:
    """Raise ``ValueError`` naming every key whose value differs between a
    source journal header's config and the current run's config, except
    keys in ``allowed_to_differ``.

    Generic: this module has no opinion on what "identifying" means for a
    given caller's domain -- a caller decides that by what it puts into
    the two config dicts in the first place (the header's config at
    record time, and its own freshly-built config at resume time). A
    caller comparing a full header must include :data:`RESUME_PROVENANCE_KEY`
    in ``allowed_to_differ`` -- see the module docstring.
    """
    allowed = set(allowed_to_differ)
    keys = (set(source_config) | set(current_config)) - allowed
    diffs = {}
    for key in sorted(keys):
        left = source_config.get(key, "<absent>")
        right = current_config.get(key, "<absent>")
        if left != right:
            diffs[key] = (left, right)
    if diffs:
        detail = "; ".join(
            f"{key}: source={left!r} current={right!r}"
            for key, (left, right) in diffs.items()
        )
        raise ValueError(
            f"Cannot resume: {len(diffs)} identifying setting(s) differ from "
            f"the source journal's header config: {detail}"
        )


# ---------------------------------------------------------------------------
# Manager: the stateful, per-run object a caller actually holds
# ---------------------------------------------------------------------------

class LLMJournalManager:
    """Owns one run's LLM-call journal: writing while live, replaying
    while resuming a prior run's completed steps. One instance per run,
    shared by every invoke this module wraps for that run (regardless of
    how many distinct ``agent_type`` values exist) and by the caller's
    own step-boundary notification (:meth:`step_end`).

    Step tracking: the manager starts at step 1 and advances only when
    :meth:`step_end` is called (by the caller, once per completed step,
    in order) -- every call made through :meth:`wrap`'s returned
    function between two ``step_end`` calls is attributed to the step
    the manager is currently on.

    Resume provenance (``resumed_from`` / ``source_journal_sha256`` /
    ``replay_last_complete_step``) is nested in the OUTPUT header under
    :data:`RESUME_PROVENANCE_KEY`, never as top-level keys -- a resumed
    run's own header otherwise could never be used as the SOURCE of a
    later resume, since those keys would never match a fresh run's
    identifying config (see the module docstring).
    """

    def __init__(
        self,
        *,
        header: Dict[str, Any],
        output_path: Optional[Path] = None,
        resume_from: Optional[Path] = None,
    ):
        self._lock = threading.Lock()
        self._current_step = 1
        self._replayed_calls = 0
        self._sticky_error: Optional[BaseException] = None

        if output_path is not None and resume_from is not None:
            if Path(output_path).resolve() == Path(resume_from).resolve():
                raise ValueError(
                    f"llm_journal output_path and resume_from both resolve "
                    f"to {Path(output_path).resolve()}: opening it for "
                    f"writing would destroy the very journal being "
                    f"replayed. A resumed run must write to a path "
                    f"different from its source journal."
                )

        self.source_path: Optional[Path] = Path(resume_from) if resume_from is not None else None
        self.loaded: Optional[LoadedJournal] = (
            load_journal_for_resume(self.source_path) if self.source_path is not None else None
        )

        out_header = dict(header)
        if self.loaded is not None:
            out_header[RESUME_PROVENANCE_KEY] = {
                "resumed_from": str(self.source_path),
                "source_journal_sha256": self.loaded.sha256,
                "replay_last_complete_step": self.loaded.last_complete_step,
            }

        self._writer: Optional[LLMJournalWriter] = (
            LLMJournalWriter(Path(output_path), out_header) if output_path is not None else None
        )

        if self.loaded is not None and self._writer is not None:
            self._mirror_replayable_steps_into_new_journal()

    @property
    def replay_last_step(self) -> int:
        return self.loaded.last_complete_step if self.loaded is not None else 0

    def _mirror_replayable_steps_into_new_journal(self) -> None:
        """Copy every replayable call record and its step's ``step_end``
        marker into the NEW journal up front, in (step, recorded order).

        This mirrors what the source already proved happened; it does not
        consume the pools, which :meth:`wrap`'s returned function still
        serves from as the simulation re-executes those steps live. Each
        mirrored call record is written WITHOUT its own fsync
        (``fsync=False``) -- the ``step_end`` marker that follows each
        step's records is still fsync'd (``LLMJournalWriter.record_step_end``
        never takes ``fsync=False``), so one fsync covers the whole step
        instead of one per record.
        """
        assert self.loaded is not None and self._writer is not None
        for step in sorted(self.loaded.pools):
            for key in self.loaded.pools[step]:
                for rec in self.loaded.pools[step][key]:
                    self._writer.record_call(**_call_kwargs_from_record(rec), fsync=False)
            self._writer.record_step_end(step)

    def wrap(self, agent_type: str, invoke: Callable) -> Callable:
        """Return a journaled wrapper around ``invoke`` for one agent type.

        ``invoke`` is called live only for a step past the replay
        boundary; a step still being replayed is answered from the
        source journal's pool and never reaches ``invoke`` at all.
        """

        def journaled(prompt: Any, *args: Any, **kwargs: Any) -> Any:
            with self._lock:
                step = self._current_step
            prompt_sha256, extra_sha256 = hash_prompt_call(prompt, args, kwargs)
            if self.loaded is not None and step <= self.loaded.last_complete_step:
                return self._replay_one(step, agent_type, prompt_sha256, extra_sha256)
            return self._invoke_live(
                step, agent_type, prompt_sha256, extra_sha256, invoke, prompt, args, kwargs,
            )

        return journaled

    def _replay_one(
        self, step: int, agent_type: str, prompt_sha256: str, extra_sha256: Optional[str],
    ) -> Any:
        assert self.loaded is not None
        key: _PoolKey = (agent_type, prompt_sha256, extra_sha256)
        with self._lock:
            dq = self.loaded.pools.get(step, {}).get(key)
            if not dq:
                exc = JournalReplayDivergence(
                    f"no matching recorded call left in the source journal for "
                    f"step {step}, agent_type {agent_type!r} "
                    f"(prompt sha256={prompt_sha256[:16]}...). The rebuilt run "
                    f"asked something the source run's journal does not account "
                    f"for at this step.",
                    step=step, agent_type=agent_type, prompt_sha256=prompt_sha256,
                )
                # STICKY (module docstring): stored even though we also
                # raise immediately, so a caller that swallows THIS raise
                # (a broad except somewhere upstream) still cannot prevent
                # the run from stopping at the next step_end.
                if self._sticky_error is None:
                    self._sticky_error = exc
                raise exc
            rec = dq.popleft()
            self._replayed_calls += 1
        if rec.get("raised"):
            _reraise_recorded_exception(
                rec.get("exception_type", "RuntimeError"),
                rec.get("exception_message", ""),
            )
        return _restore_result_from_record(rec)

    def _invoke_live(
        self,
        step: int,
        agent_type: str,
        prompt_sha256: str,
        extra_sha256: Optional[str],
        invoke: Callable,
        prompt: Any,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
    ) -> Any:
        try:
            result = invoke(prompt, *args, **kwargs) if (args or kwargs) else invoke(prompt)
        except Exception as exc:
            self._record_call_safely(
                step=step, agent_type=agent_type,
                prompt_sha256=prompt_sha256, extra_sha256=extra_sha256,
                raised=True,
                exception_type=type(exc).__name__, exception_message=str(exc),
            )
            raise
        shape, content, stats_jsonable = _split_result_for_record(result)
        self._record_call_safely(
            step=step, agent_type=agent_type,
            prompt_sha256=prompt_sha256, extra_sha256=extra_sha256,
            raised=False, shape=shape, content=content, stats=stats_jsonable,
        )
        return result

    def _record_call_safely(self, **kwargs: Any) -> None:
        """Write one call record, never raising here (see
        :class:`JournalWriteError` and the module docstring's "STICKY
        errors" section): a write failure is deferred to the next
        ``step_end`` instead of surfacing at the call site, where a
        caller's own retry loop could mistake it for the model call
        itself failing. The live result the caller received is never
        affected either way.
        """
        if self._writer is None:
            return
        try:
            self._writer.record_call(**kwargs)
        except Exception as exc:
            with self._lock:
                if self._sticky_error is None:
                    self._sticky_error = JournalWriteError(
                        f"failed to write a call record to the output "
                        f"journal at step {kwargs.get('step')} for agent "
                        f"type {kwargs.get('agent_type')!r}: "
                        f"{type(exc).__name__}: {exc}"
                    )

    def step_end(self, step: int) -> None:
        """Notify the manager that ``step`` has fully completed.

        Checks (in order): (1) a STICKY error from earlier in this step
        (a divergence or a journal-write failure, possibly already
        swallowed by some other caller) -- raised here unconditionally;
        (2) for a step still within the replay boundary, whether any
        recorded call for that step was never consumed (the rebuilt run
        asked FEWER questions than the source run did, which is just as
        much a divergence as asking different ones); (3) otherwise, for a
        step past the boundary, writes this step's ``step_end`` marker to
        the output journal. Either way, advances the manager to
        ``step + 1``.
        """
        with self._lock:
            if self._sticky_error is not None:
                raise self._sticky_error
            is_replayed_step = self.loaded is not None and step <= self.loaded.last_complete_step
            if is_replayed_step:
                leftover = {
                    key: len(dq) for key, dq in self.loaded.pools.get(step, {}).items() if dq
                }
                if leftover:
                    total = sum(leftover.values())
                    exc = JournalReplayDivergence(
                        f"{total} recorded call(s) for step {step} were never "
                        f"replayed before this step ended: {leftover}. The "
                        f"rebuilt run asked fewer questions than the source "
                        f"run did at this step.",
                        step=step,
                    )
                    self._sticky_error = exc
                    raise exc
            elif self._writer is not None:
                self._writer.record_step_end(step)
            self._current_step = step + 1

    def provenance_metadata(self) -> Optional[Dict[str, Any]]:
        """Manifest-ready provenance dict, or ``None`` for a run that is
        not resuming anything (the manifest must keep exactly its current
        keys for a normal run)."""
        if self.loaded is None:
            return None
        return {
            "resumed_from": str(self.source_path),
            "source_journal_sha256": self.loaded.sha256,
            "replayed_steps": self.loaded.last_complete_step,
            "replayed_calls": self._replayed_calls,
        }

    def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
