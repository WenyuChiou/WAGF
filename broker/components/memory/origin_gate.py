"""Memory write gate and memory log (Invariant 7, ``broker/INVARIANTS.md``).

Every memory write must say where its line comes from, in
``metadata["origin"]``:

==============  ==========================================================
``world``       the environment or the external model: outcomes, events,
                published program facts
``decision``    the executed action and its numbers only
``reflection``  the model's lesson
``social``      other agents' executed actions and their world / decision
                records
``seed``        the agent profile, before period 1
==============  ==========================================================

There is no "governance" origin: a line about a rejection, a rule or a
default has no place in memory. The tag can be wrong, so it is not the
guarantee (that is a twin run, Invariant 7); it is what the memory log shows.
The engines return text only, so a reader cannot filter on the tag; with
``reflection_prefix`` the gate refuses a reflection-origin line that does not
start with it, and broker.run's reflection reader leaves those lines out.

``install_origin_gate`` wraps the engine's own ``add_memory`` and
``add_memory_for_agent`` on the instance, not with a wrapper class, so the
engine keeps its class: ``SkillBrokerEngine`` turns skill retrieval off for a
``WindowMemoryEngine`` by ``isinstance``, and ``run_integrity.json`` records the
engine class. A write with a missing or unknown origin raises ``ValueError``;
every accepted write is appended to ``memory_log.jsonl``.

Used by ``python -m broker.run`` only. The frozen paper runners do not
install it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

ORIGINS = ("world", "decision", "reflection", "social", "seed")
MEMORY_LOG_NAME = "memory_log.jsonl"
_LOGGED_KEYS = ("importance", "emotion", "type", "source")


class OriginGate:
    """The gate installed on one engine; ``counts`` holds writes per origin."""

    def __init__(self, engine: Any, log_path: Path, period: Callable[[], Any],
                 reflection_prefix: Optional[str] = None):
        self.engine = engine
        self.reflection_prefix = reflection_prefix
        self.log_path = Path(log_path)
        self._period = period
        # While True (the builder seeding agent profiles), an untagged write
        # is a seed write. broker.run turns it off once the runner is built.
        self.seeding = True
        self.counts = {origin: 0 for origin in ORIGINS}
        self._depth = 0
        self._started = False
        self._add_memory = engine.add_memory
        self._add_memory_for_agent = getattr(engine, "add_memory_for_agent", None)

    def _check(self, agent_id, content, metadata):
        origin = metadata.get("origin") if isinstance(metadata, dict) else None
        if origin is None and self.seeding:
            origin = "seed"
        if origin not in ORIGINS:
            raise ValueError(
                f"memory write for {agent_id!r} has origin {origin!r}; every memory write on "
                f"python -m broker.run needs metadata['origin'] in {', '.join(ORIGINS)} "
                f"(Invariant 7, broker/INVARIANTS.md). Line: {str(content)[:120]!r}"
            )
        if (origin == "reflection" and self.reflection_prefix is not None
                and not str(content).startswith(self.reflection_prefix)):
            # The engines return text only, so the reflection reader leaves
            # earlier lessons out by this prefix (Invariant 7).
            raise ValueError(
                f"memory write for {agent_id!r} has origin 'reflection' but does not start "
                f"with {self.reflection_prefix!r}, so a later reflection would read it. "
                f"Line: {str(content)[:120]!r}"
            )
        return origin

    def _log(self, agent_id, content, metadata, origin):
        meta = metadata if isinstance(metadata, dict) else {}
        period = meta.get("period")
        if period is None:
            period = 0 if origin == "seed" else self._period()
        entry = {"agent_id": agent_id, "period": period, "origin": origin, "content": content}
        entry.update({key: meta.get(key) for key in _LOGGED_KEYS})
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        # The first write of this run replaces a log left by an earlier run.
        mode = "a" if self._started else "w"
        with open(self.log_path, mode, encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        self._started = True
        self.counts[origin] += 1

    def _gated(self, agent_id, content, metadata, write):
        # An engine's add_memory_for_agent may call its own add_memory: only
        # the outermost call is checked and logged.
        if self._depth:
            return write()
        origin = self._check(agent_id, content, metadata)
        self._depth += 1
        try:
            result = write()
        finally:
            self._depth -= 1
        self._log(agent_id, content, metadata, origin)
        return result

    def add_memory(self, agent_id, content, metadata=None, *args, **kwargs):
        return self._gated(agent_id, content, metadata,
                           lambda: self._add_memory(agent_id, content, metadata, *args, **kwargs))

    def add_memory_for_agent(self, agent, content, metadata=None, *args, **kwargs):
        return self._gated(getattr(agent, "id", agent), content, metadata,
                           lambda: self._add_memory_for_agent(agent, content, metadata, *args, **kwargs))


def install_origin_gate(engine: Any, output_dir: Path, period: Callable[[], Any],
                        reflection_prefix: Optional[str] = None) -> OriginGate:
    """Gate ``engine``'s writes in place and log them to ``output_dir``/memory_log.jsonl.

    ``period`` gives the period a write without ``metadata['period']`` is
    logged under. A log left in ``output_dir`` by an earlier run is replaced
    at this run's first write, not before. With ``reflection_prefix``, a
    reflection-origin line must start with it.
    """
    gate = OriginGate(engine, Path(output_dir) / MEMORY_LOG_NAME, period, reflection_prefix)
    engine.add_memory = gate.add_memory
    if gate._add_memory_for_agent is not None:
        engine.add_memory_for_agent = gate.add_memory_for_agent
    engine.origin_gate = gate
    return gate
