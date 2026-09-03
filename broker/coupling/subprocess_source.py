"""``SubprocessModelConnector`` — Archetype C (service model) made real.

``docs/COUPLING_CONNECTORS.md`` describes archetype C ("Service model:
REST / subprocess") as a documented pattern, but before this module no
code implemented it: a researcher following the pattern would have had
to hand-write the JSON round trip, the fail-loud contract check, and the
exit-code/stderr bookkeeping themselves (PR-9 coupling-retrofit audit,
finding F2). This module ships the SUBPROCESS half so that gap is closed;
REST stays documented-but-deferred (no first-party consumer exists yet —
see the "What NOT to build" note in COUPLING_CONNECTORS.md).

Protocol: one call per period.
  * stdin  <- ``{"period": <int>}`` (UTF-8 JSON, newline-terminated).
  * stdout -> a single UTF-8 JSON object naming every declared observation.
  * exit 0 required; anything else is refused (``CouplingViolation``, with
    the stderr tail attached so the failure is diagnosable without
    re-running the external process by hand).

The reply is validated against ``contract.observations`` with the SAME
fail-loud + range-check logic ``EnvironmentCouplingAdapter`` uses (a
missing key names itself in the raised ``CouplingViolation`` rather than
degrading to a zero — the discipline this whole coupling layer exists to
enforce). ``VarSpec.on_missing`` accepts only ``"fail_loud"`` (see
``contract.py``); a flaky external process needs its OWN retry/cache
policy inside the process (or a wrapping adapter, per
``adapter_A_file_replay.py.tmpl``'s ``last_good`` pattern) — this
connector will never silently paper over a bad or missing reply.

Domain-vocab-free: the command, value variable, and contract are all
constructor parameters, so the same connector drives any per-tick
external model over stdin/stdout.
"""
from __future__ import annotations

import json
import logging
import subprocess
import time
from typing import Any, Dict, List, Optional, Sequence

from .adapter import CouplingViolation
from .contract import CouplingContract
from .interfaces import Event

logger = logging.getLogger(__name__)

# ``CouplingViolation`` is re-exported (not re-defined) so every raise below
# IS ``broker.coupling.adapter.CouplingViolation`` (isinstance-identical) —
# one exception identity across the whole coupling layer, never a same-named
# shadow that would fail an `except CouplingViolation` written against the
# adapter's import path.


def _reject_constant(name: str) -> float:
    """``json.loads(parse_constant=...)`` hook: refuse ``NaN`` / ``Infinity``
    / ``-Infinity`` AT PARSE TIME.

    Defence in depth, one layer earlier than ``VarSpec.range_violation``'s
    finite check: those three tokens are a Python-only extension that strict
    JSON does not define, so a reply carrying them is already outside the
    protocol this connector documents, whether or not the field it lands in
    happens to be declared with bounds. Refusing here also covers a
    non-finite value in a field the contract does NOT declare (which the
    per-VarSpec loop never inspects).
    """
    raise ValueError(
        f"non-finite JSON constant {name!r} in reply -- NaN/Infinity are not "
        f"valid JSON numbers and are never a reading"
    )


def _guard_reply(contract: CouplingContract, reply: Dict[str, Any]) -> None:
    """Apply ``on_missing`` + range/dtype checks from every declared
    observation to a subprocess reply. Same message shape as
    ``EnvironmentCouplingAdapter._validate_observations`` on purpose — one
    failure vocabulary across the coupling layer.

    Undeclared reply keys are WARNED about, not refused: an external model
    that reports extra diagnostics is not broken, but a key the contract
    never declared is also a key nothing validates, nothing projects into the
    prompt, and nothing records — most often a typo'd field name whose
    declared twin then fails the missing check with no hint as to why. The
    warning names both sides so the mismatch is one line to diagnose.
    """
    problems: List[str] = []
    for vs in contract.observations:
        if vs.name not in reply or reply[vs.name] is None:
            if vs.on_missing == "fail_loud":
                problems.append(f"{vs.name}: missing (on_missing=fail_loud)")
            continue
        rv = vs.range_violation(reply[vs.name])
        if rv:
            problems.append(rv)
    undeclared = sorted(set(reply) - set(contract.observation_specs()))
    if undeclared:
        logger.warning(
            "SubprocessModelConnector: reply carries key(s) %s that the "
            "contract does not declare -- they are ignored (not validated, "
            "not projected into any prompt). Declared observations: %s.",
            undeclared, sorted(contract.observation_specs()),
        )
    if problems:
        raise CouplingViolation(f"observation contract violations: {problems}")


class SubprocessModelConnector:
    """Drive an external model as a subprocess, one JSON round trip per
    period. Satisfies ``broker.coupling.EventSource`` structurally
    (``draw_events`` / ``intensity_at`` / ``units``).

    Args:
        command: argv for the external process (e.g.
            ``[sys.executable, "external_model.py"]``).
        contract: the ``CouplingContract`` whose ``observations`` the
            reply is validated against (fail-loud on any missing field).
        value_var: which declared observation names this source's event
            "intensity" (the connector may host a model with several
            observation fields; the event payload carries all of them,
            but ``intensity_at`` needs one headline number).
        event_threshold: emit an ``Event`` only when ``value_var``'s
            reading exceeds this (matches ``BmiEventSource``'s convention
            of >=0 events per period).
        timeout_sec: wall-clock budget for one call. A timeout is a
            refusal (``CouplingViolation``), never a silent skip.
        cwd: working directory for the subprocess (default: inherit).
    """

    def __init__(
        self,
        command: Sequence[str],
        *,
        contract: CouplingContract,
        value_var: str,
        event_threshold: float = 0.0,
        timeout_sec: float = 10.0,
        cwd: Optional[str] = None,
    ) -> None:
        spec = contract.observation_specs().get(value_var)
        if spec is None:
            raise ValueError(
                f"SubprocessModelConnector: value_var {value_var!r} is not a "
                f"declared observation on the contract (known: "
                f"{sorted(contract.observation_specs())})"
            )
        # Review W4: value_var becomes an event INTENSITY (a float, compared
        # against event_threshold and returned by intensity_at). A bool or str
        # observation cannot be one, and letting it through would mean
        # float()-coercing a flag or a label into a magnitude at the exact
        # boundary this class exists to police. Refuse at CONSTRUCTION so the
        # wiring error surfaces at build time, not mid-run.
        if spec.dtype not in (int, float):
            raise ValueError(
                f"SubprocessModelConnector: value_var {value_var!r} is declared "
                f"dtype {getattr(spec.dtype, '__name__', spec.dtype)!r} on the "
                f"contract; the event intensity must be numeric (int | float). "
                f"Pick a numeric observation, or declare this one numeric."
            )
        self._command = tuple(command)
        self._contract = contract
        self._value_var = value_var
        self._unit = spec.unit
        self._event_threshold = float(event_threshold)
        self._timeout_sec = float(timeout_sec)
        self._cwd = cwd
        self._last_audit: Optional[Dict[str, Any]] = None

    def draw_events(self, period: int) -> List[Event]:
        payload_in = (json.dumps({"period": int(period)}) + "\n").encode("utf-8")
        started = time.monotonic()
        try:
            proc = subprocess.run(
                list(self._command),
                input=payload_in,
                capture_output=True,
                timeout=self._timeout_sec,
                cwd=self._cwd,
            )
        except subprocess.TimeoutExpired as exc:
            # Record the audit BEFORE raising. A timeout is the one failure a
            # caller most wants the provenance for (how long it actually ran,
            # what the process said on stderr before it hung), and leaving
            # _last_audit at its previous value made get_provenance report the
            # LAST SUCCESSFUL call as if it were the current state of the
            # world — a stale success where the truth is a hang.
            #
            # exit_code is None, not a number: the process was killed, it never
            # exited on its own, and writing any integer there would invent one.
            #
            # subprocess.run kills the direct child on timeout (it calls
            # Popen.kill() then reaps it), which is all this connector can do
            # portably: a process-GROUP kill needs CREATE_NEW_PROCESS_GROUP +
            # taskkill /T on Windows and os.killpg on POSIX, and subprocess.run
            # exposes no Popen handle to do either. LIMITATION, stated rather
            # than papered over: a model that spawns its OWN children can leave
            # grandchildren running after this raises. A model that does that
            # should trap the signal and clean up after itself, or be driven by
            # a wrapper that owns the process group.
            elapsed = time.monotonic() - started
            raw_err = getattr(exc, "stderr", None) or b""
            if isinstance(raw_err, str):
                raw_err = raw_err.encode("utf-8", errors="replace")
            self._last_audit = {
                "period": int(period),
                "exit_code": None,
                "timed_out": True,
                "wall_time_sec": round(elapsed, 4),
                "stderr_tail": raw_err.decode("utf-8", errors="replace")[-2000:],
            }
            raise CouplingViolation(
                f"SubprocessModelConnector: external model timed out after "
                f"{self._timeout_sec}s (period={period}, command={list(self._command)!r}); "
                f"the direct child was killed, but any grandchildren it spawned "
                f"were not (see this method's timeout note)"
            ) from exc
        elapsed = time.monotonic() - started
        stderr_tail = proc.stderr.decode("utf-8", errors="replace")[-2000:]
        self._last_audit = {
            "period": int(period),
            "exit_code": proc.returncode,
            # Same key shape as the timeout branch above, so a consumer reads
            # ONE field to tell the two apart instead of inferring it from a
            # null exit code.
            "timed_out": False,
            "wall_time_sec": round(elapsed, 4),
            "stderr_tail": stderr_tail,
        }
        if proc.returncode != 0:
            raise CouplingViolation(
                f"SubprocessModelConnector: external model exited "
                f"{proc.returncode} (period={period}, command={list(self._command)!r}); "
                f"refusing a non-zero exit rather than guessing at a partial reply. "
                f"stderr tail: {stderr_tail!r}"
            )
        try:
            reply = json.loads(
                proc.stdout.decode("utf-8"), parse_constant=_reject_constant,
            )
        except (ValueError, UnicodeDecodeError) as exc:
            raise CouplingViolation(
                f"SubprocessModelConnector: reply is not valid JSON "
                f"(period={period}, command={list(self._command)!r}): {exc}"
            ) from exc
        if not isinstance(reply, dict):
            raise CouplingViolation(
                f"SubprocessModelConnector: reply must be a JSON object, got "
                f"{type(reply).__name__} (period={period})"
            )

        _guard_reply(self._contract, reply)  # fail-loud on any missing/out-of-range field

        value = float(reply[self._value_var])
        if value <= self._event_threshold:
            return []
        return [Event(
            event_id=f"{self._value_var}_t{period}",
            period=int(period),
            payload=dict(reply),
        )]

    def intensity_at(self, agent_id: str, event: Event) -> float:
        """The event's headline reading.

        Indexed, not ``.get``-with-a-default: every Event this source emits
        was built from a reply that ``_guard_reply`` had already proved
        carries ``value_var`` in range, so on the guarded path the key is
        always there. The old ``.get(value_var, .get("intensity", 0.0))``
        chain could only ever fire for an Event from SOMEWHERE ELSE — and
        for that Event it returned a silent 0.0 intensity, the exact
        plausible-looking zero this layer refuses everywhere else. A KeyError
        naming the missing field is the honest answer to a foreign event.
        """
        return float(event.payload[self._value_var])

    def units(self) -> str:
        return self._unit

    def get_provenance(self) -> Dict[str, Any]:
        """World-side identity for the reproducibility manifest, including
        the last call's exit code / wall time / stderr tail (inc-3 review
        pattern: BmiEventSource reports component identity; this connector
        additionally reports the runtime health of the LAST subprocess call
        since a subprocess, unlike an in-process BMI component, can fail
        independently of the Python process)."""
        return {
            "source_class": type(self).__name__,
            "command": list(self._command),
            "protocol": "json-stdin/json-stdout-subprocess-v1",
            "value_var": self._value_var,
            "unit": self._unit,
            "event_threshold": self._event_threshold,
            "timeout_sec": self._timeout_sec,
            "last_call_audit": self._last_audit,
        }


__all__ = ["SubprocessModelConnector", "CouplingViolation"]
