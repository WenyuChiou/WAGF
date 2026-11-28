"""Thin exogenous fact schedule for injecting observed historical signals into AsyncKnowledgeGraph."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
import yaml

from broker.components.social.knowledge_graph import (
    VALID_VISIBILITIES,
    AsyncKnowledgeGraph,
    KnowledgeTriple,
)


@dataclass(frozen=True)
class ExogenousFactEntry:
    """Single scheduled exogenous fact asserted at a simulation period."""

    period: int
    subject: str
    predicate: str
    obj: str
    value: Optional[float] = None
    text: str = ""
    author_id: str = "environment"
    author_role: str = "exogenous"
    delivery_delay: int = 0
    ttl_periods: Optional[int] = None
    visibility: str = "global"
    target_ids: Tuple[str, ...] = ()
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.period, bool) or not isinstance(self.period, int) or self.period < 0:
            raise ValueError(f"ExogenousFactEntry.period must be an int >= 0, got {self.period!r}")
        if not self.subject or not self.predicate or not self.obj:
            raise ValueError("ExogenousFactEntry requires non-empty subject, predicate, and obj")
        if self.visibility not in VALID_VISIBILITIES:
            raise ValueError(
                f"ExogenousFactEntry.visibility must be one of {VALID_VISIBILITIES}, got {self.visibility!r}"
            )
        if not isinstance(self.target_ids, tuple):
            object.__setattr__(self, "target_ids", tuple(str(t) for t in self.target_ids))
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


class ExogenousFactSchedule:
    """Idempotent schedule feeding exogenous observations into :class:`AsyncKnowledgeGraph`.

    This class holds no parallel event store: all delivered facts live directly
    as ``KnowledgeTriple`` nodes inside the attached knowledge graph.
    """

    def __init__(
        self,
        entries: Sequence[ExogenousFactEntry] = (),
        *,
        source_path: Optional[Path] = None,
        sha256: Optional[str] = None,
    ) -> None:
        self._entries_by_period: Dict[int, List[ExogenousFactEntry]] = {}
        for entry in entries:
            self._entries_by_period.setdefault(entry.period, []).append(entry)
        self.source_path = Path(source_path) if source_path is not None else None
        if sha256 is not None:
            self.sha256: str = sha256
        elif self.source_path is not None and self.source_path.is_file():
            self.sha256 = hashlib.sha256(self.source_path.read_bytes()).hexdigest()
        else:
            canonical = json.dumps(
                [
                    {
                        "period": e.period,
                        "subject": e.subject,
                        "predicate": e.predicate,
                        "obj": e.obj,
                        "value": e.value,
                        "text": e.text,
                        "visibility": e.visibility,
                    }
                    for p in sorted(self._entries_by_period)
                    for e in self._entries_by_period[p]
                ],
                sort_keys=True,
                default=str,
            )
            self.sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self._applied_keys: Set[Tuple[int, int]] = set()
        self._applied_triple_count: int = 0

    @classmethod
    def from_records(
        cls,
        records: Sequence[Mapping[str, Any]],
        *,
        source_path: Optional[Path] = None,
        sha256: Optional[str] = None,
    ) -> "ExogenousFactSchedule":
        entries: List[ExogenousFactEntry] = []
        for idx, rec in enumerate(records):
            if not isinstance(rec, Mapping):
                raise ValueError(f"Exogenous schedule record #{idx} must be a mapping")
            raw_targets = rec.get("target_ids") or ()
            if isinstance(raw_targets, str):
                targets = tuple(t.strip() for t in raw_targets.split("|") if t.strip())
            else:
                targets = tuple(str(t) for t in raw_targets if str(t).strip())
            raw_val = rec.get("value")
            value = None if raw_val is None or raw_val == "" else float(raw_val)
            raw_ttl = rec.get("ttl_periods")
            ttl = None if raw_ttl is None or raw_ttl == "" else int(raw_ttl)
            entries.append(
                ExogenousFactEntry(
                    period=int(rec["period"]),
                    subject=str(rec["subject"]),
                    predicate=str(rec["predicate"]),
                    obj=str(rec.get("obj", rec.get("object", ""))),
                    value=value,
                    text=str(rec.get("text", "")),
                    author_id=str(rec.get("author_id", "environment")),
                    author_role=str(rec.get("author_role", "exogenous")),
                    delivery_delay=int(rec.get("delivery_delay", 0)),
                    ttl_periods=ttl,
                    visibility=str(rec.get("visibility", "global")),
                    target_ids=targets,
                    confidence=float(rec.get("confidence", 1.0)),
                    metadata=dict(rec.get("metadata") or {}),
                )
            )
        return cls(entries, source_path=source_path, sha256=sha256)

    @classmethod
    def from_csv(cls, path: Path) -> "ExogenousFactSchedule":
        resolved = Path(path)
        if not resolved.is_file():
            raise FileNotFoundError(f"Exogenous schedule CSV not found: {resolved}")
        sha256 = hashlib.sha256(resolved.read_bytes()).hexdigest()
        df = pd.read_csv(resolved)
        records: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            rec: Dict[str, Any] = {}
            for col in df.columns:
                val = row[col]
                if pd.isna(val):
                    continue
                rec[str(col)] = val.item() if hasattr(val, "item") else val
            records.append(rec)
        return cls.from_records(records, source_path=resolved, sha256=sha256)

    @classmethod
    def from_yaml(cls, path: Path) -> "ExogenousFactSchedule":
        resolved = Path(path)
        if not resolved.is_file():
            raise FileNotFoundError(f"Exogenous schedule YAML not found: {resolved}")
        sha256 = hashlib.sha256(resolved.read_bytes()).hexdigest()
        loaded = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        if isinstance(loaded, Mapping):
            records = loaded.get("facts") or loaded.get("schedule") or []
        elif isinstance(loaded, list):
            records = loaded
        else:
            raise ValueError(f"Invalid YAML schedule structure in {resolved}")
        return cls.from_records(records, source_path=resolved, sha256=sha256)

    @property
    def periods(self) -> List[int]:
        return sorted(self._entries_by_period)

    def apply_period(self, period: int, kg: AsyncKnowledgeGraph) -> List[KnowledgeTriple]:
        """Assert scheduled facts for ``period`` into ``kg`` idempotently."""
        key = (id(kg), int(period))
        if key in self._applied_keys:
            return []
        entries = self._entries_by_period.get(int(period), ())
        added: List[KnowledgeTriple] = []
        for entry in entries:
            merged_meta = dict(entry.metadata)
            merged_meta.setdefault("exogenous", True)
            triple = kg.assert_fact(
                subject=entry.subject,
                predicate=entry.predicate,
                obj=entry.obj,
                value=entry.value,
                text=entry.text,
                author_id=entry.author_id,
                author_role=entry.author_role,
                published_period=entry.period,
                delivery_delay=entry.delivery_delay,
                ttl_periods=entry.ttl_periods,
                visibility=entry.visibility,
                target_ids=entry.target_ids,
                confidence=entry.confidence,
                metadata=merged_meta,
            )
            added.append(triple)
            self._applied_triple_count += 1
        self._applied_keys.add(key)
        return added

    def as_pre_year_hook(
        self, kg: AsyncKnowledgeGraph
    ) -> Callable[[int, Dict[str, Any], Dict[str, Any]], None]:
        """Return a ``pre_year(year, env, agents)`` hook asserting scheduled facts."""

        def _pre_year(year: int, env: Dict[str, Any], agents: Dict[str, Any]) -> None:
            self.apply_period(int(year), kg)

        return _pre_year

    def snapshot(self) -> Dict[str, Any]:
        return {
            "source_path": str(self.source_path) if self.source_path is not None else None,
            "sha256": self.sha256,
            "scheduled_periods": self.periods,
            "scheduled_fact_count": sum(len(v) for v in self._entries_by_period.values()),
            "applied_triple_count": self._applied_triple_count,
        }


__all__ = ["ExogenousFactEntry", "ExogenousFactSchedule"]
