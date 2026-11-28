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
_OPTIONAL_PROVENANCE_KEYS = (
    "triple_id",
    "author_id",
    "source_step_id",
    "hop",
    "effective_available_period",
    "reflection_id",
)


class OriginGate:
    """The gate installed on one engine; ``counts`` holds writes per origin."""

    def __init__(self, engine: Any, log_path: Path, period: Callable[[], Any],
                 reflection_prefix: Optional[str] = None,
                 run_id: Optional[str] = None):
        self.engine = engine
        self.reflection_prefix = reflection_prefix
        self.run_id = run_id
        self.log_path = Path(log_path)
        self._period = period
        # While True (the builder seeding agent profiles), an untagged write
        # is a seed write. broker.run turns it off once the runner is built.
        self.seeding = True
        self.counts = {origin: 0 for origin in ORIGINS}
        self._seq = 0
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

    def _log(self, agent_id, content, metadata, origin, memory_id):
        meta = metadata if isinstance(metadata, dict) else {}
        period = meta.get("period")
        if period is None:
            period = 0 if origin == "seed" else self._period()
        entry = {
            "agent_id": agent_id,
            "period": period,
            "origin": origin,
            "memory_id": memory_id,
            "content": content,
        }
        if self.run_id is not None:
            entry["run_id"] = self.run_id
        entry.update({key: meta.get(key) for key in _LOGGED_KEYS})
        for key in _OPTIONAL_PROVENANCE_KEYS:
            val = meta.get(key)
            if val is not None:
                entry[key] = val
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        # The first write of this run replaces a log left by an earlier run.
        mode = "a" if self._started else "w"
        with open(self.log_path, mode, encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        self._started = True
        self.counts[origin] += 1

    def _snapshot_buffer_ids(self, agent_id: Any) -> dict[str, set[int]]:
        aid = str(agent_id)
        out: dict[str, set[int]] = {}
        for attr in ("working", "longterm", "storage", "episodic"):
            buf = getattr(self.engine, attr, None)
            if isinstance(buf, dict):
                out[attr] = {
                    id(item)
                    for item in (buf.get(aid) or ())
                    if isinstance(item, dict)
                }
        return out

    def _stamp_stored_item(
        self,
        agent_id: Any,
        memory_id: str,
        origin: str,
        pre_ids: Optional[dict[str, set[int]]] = None,
    ) -> None:
        """Attach memory_id/origin to newly created stored dict(s) when metadata was omitted.

        Matches by object identity against a pre-write snapshot so bounded
        capacity eviction/reordering (e.g. sorting longterm by importance)
        still stamps the newly inserted record regardless of final list index.
        """
        aid = str(agent_id)
        for attr in ("working", "longterm", "storage", "episodic"):
            buf = getattr(self.engine, attr, None)
            if not isinstance(buf, dict):
                continue
            items = buf.get(aid)
            if not isinstance(items, list) or not items:
                continue
            if pre_ids is None:
                candidates = [items[-1]] if isinstance(items[-1], dict) else []
            else:
                known = pre_ids.get(attr, set())
                candidates = [
                    item for item in items
                    if isinstance(item, dict) and id(item) not in known
                ]
            for item in candidates:
                if "memory_id" not in item:
                    item["memory_id"] = memory_id
                    item.setdefault("origin", origin)

    def _gated(self, agent_id, content, metadata, write):
        # An engine's add_memory_for_agent may call its own add_memory: only
        # the outermost call is checked and logged.
        if self._depth:
            return write(metadata)
        origin = self._check(agent_id, content, metadata)
        next_seq = self._seq + 1
        memory_id = f"mem-{next_seq}"
        if isinstance(metadata, dict) and metadata:
            # Never mutate caller's dict; keep empty/None seeding branch untouched
            # so HumanCentricMemoryEngine._add_memory_internal keeps identical scoring.
            write_meta = dict(metadata)
            write_meta.setdefault("origin", origin)
            write_meta["memory_id"] = memory_id
            log_meta = write_meta
            stamped_in_store = False
            pre_ids = None
        else:
            write_meta = metadata
            log_meta = {"origin": origin, "memory_id": memory_id}
            stamped_in_store = True
            pre_ids = self._snapshot_buffer_ids(agent_id)
        self._depth += 1
        try:
            result = write(write_meta)
        finally:
            self._depth -= 1
        if stamped_in_store:
            self._stamp_stored_item(agent_id, memory_id, origin, pre_ids=pre_ids)
        self._seq = next_seq
        self._log(agent_id, content, log_meta, origin, memory_id)
        return result

    def add_memory(self, agent_id, content, metadata=None, *args, **kwargs):
        return self._gated(
            agent_id, content, metadata,
            lambda meta: self._add_memory(agent_id, content, meta, *args, **kwargs),
        )

    def add_memory_for_agent(self, agent, content, metadata=None, *args, **kwargs):
        return self._gated(
            getattr(agent, "id", agent), content, metadata,
            lambda meta: self._add_memory_for_agent(agent, content, meta, *args, **kwargs),
        )


def install_origin_gate(engine: Any, output_dir: Path, period: Callable[[], Any],
                        reflection_prefix: Optional[str] = None,
                        run_id: Optional[str] = None) -> OriginGate:
    """Gate ``engine``'s writes in place and log them to ``output_dir``/memory_log.jsonl.

    ``period`` gives the period a write without ``metadata['period']`` is
    logged under. A log left in ``output_dir`` by an earlier run is replaced
    at this run's first write, not before. With ``reflection_prefix``, a
    reflection-origin line must start with it.
    """
    gate = OriginGate(
        engine, Path(output_dir) / MEMORY_LOG_NAME, period,
        reflection_prefix=reflection_prefix, run_id=run_id,
    )
    engine.add_memory = gate.add_memory
    if gate._add_memory_for_agent is not None:
        engine.add_memory_for_agent = gate.add_memory_for_agent
    engine.origin_gate = gate
    return gate
