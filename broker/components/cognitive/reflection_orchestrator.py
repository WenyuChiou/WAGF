"""ReflectionOrchestrator — generic year/period-end batch reflection (Wave 3 / 3-5).

The collect -> batch -> prompt -> parse -> store loop was re-implemented in
four domain runners (run_flood.py:568-642, irrigation run_experiment.py:366-445,
governed_flood run_experiment.py:274-314, MA lifecycle_hooks.py:1078-1109) —
the 2026-06-09 architecture review's P1-6. This component is the SINGLE generic
home for that orchestration.

OPT-IN BY DESIGN: the four existing runners are frozen paper paths and keep
their local loops untouched; new domains wire this instead of copy-pasting a
fifth one. Construction is explicit (no flag) — a runner that never builds an
orchestrator pays nothing.

The parse stage is the engine's (``parse_batch_reflection_response``), kept
swappable via ``parse_fn`` so the PARKED 5-field structured-reflection design
([[project-reflection-formalize-question]]) can drop in without touching this
orchestration again.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReflectionOrchestrator:
    """Drives one period's batch reflection through a ReflectionEngine.

    Args:
        reflection_engine: a ``broker.components.cognitive.reflection.ReflectionEngine``
            (or anything exposing generate_batch_reflection_prompt /
            parse_batch_reflection_response / store_insight / should_reflect).
        memory_engine: where consolidated insights are written back
            (``add_memory(agent_id, content, metadata)``).
        llm_invoke: callable prompt -> response (or (response, stats) tuple).
        batch_size: agents per LLM call.
        questions: optional domain guidance questions (YAML
            ``global_config.reflection.questions``).
        tick_label: decision-period noun for prompt text ("Year" default —
            byte-identical to the four legacy loops; sub-annual domains pass
            e.g. "Day").
        eligible: optional per-agent predicate; ineligible agents are skipped
            (e.g. relocated households). Default: everyone.
        memories_per_agent: how many memories to retrieve as reflection input.
        insight_metadata: metadata dict for the consolidated write-back
            (default mirrors the legacy loops' significance/emotion/source).
        parse_fn: optional override for the parse stage
            ``(text, batch_ids, period) -> Dict[agent_id, insight]``.
    """

    def __init__(
        self,
        reflection_engine: Any,
        memory_engine: Any,
        llm_invoke: Callable[[str], Any],
        *,
        batch_size: int = 10,
        questions: Optional[List[str]] = None,
        tick_label: str = "Year",
        eligible: Optional[Callable[[Any], bool]] = None,
        memories_per_agent: int = 10,
        insight_metadata: Optional[Dict[str, Any]] = None,
        parse_fn: Optional[Callable[[str, List[str], int], Dict[str, Any]]] = None,
    ) -> None:
        self.reflection_engine = reflection_engine
        self.memory_engine = memory_engine
        self.llm_invoke = llm_invoke
        self.batch_size = int(batch_size)
        self.questions = list(questions or [])
        self.tick_label = tick_label
        self.eligible = eligible or (lambda agent: True)
        self.memories_per_agent = int(memories_per_agent)
        self.insight_metadata = dict(insight_metadata or {
            "significance": 0.9, "emotion": "major", "source": "personal",
        })
        self.parse_fn = parse_fn

    # ------------------------------------------------------------------
    def collect_candidates(self, agents: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Gather {agent_id, memories} for every eligible agent with memories."""
        candidates: List[Dict[str, Any]] = []
        for agent_id, agent in agents.items():
            if not self.eligible(agent):
                continue
            mems = self.memory_engine.retrieve(agent, top_k=self.memories_per_agent)
            if mems:
                candidates.append({"agent_id": agent_id, "memories": mems})
        return candidates

    def run_period(self, period: int, agents: Dict[str, Any]) -> int:
        """One period's full reflection pass. Returns #insights stored.

        Honors the engine's cadence (``should_reflect``) when present; a batch
        failure is logged and the remaining batches continue (matching the
        legacy loops' fail-soft posture — one bad LLM response must not void
        every other agent's reflection).
        """
        should = getattr(self.reflection_engine, "should_reflect", None)
        if callable(should) and not should("any", period):
            return 0
        candidates = self.collect_candidates(agents)
        if not candidates:
            return 0

        stored = 0
        n_batches = (len(candidates) + self.batch_size - 1) // self.batch_size
        logger.info(
            f"[Reflection] {len(candidates)} agents in {n_batches} batch(es) "
            f"of <= {self.batch_size} ({self.tick_label} {period})"
        )
        for i in range(0, len(candidates), self.batch_size):
            batch = candidates[i: i + self.batch_size]
            batch_ids = [c["agent_id"] for c in batch]
            prompt = self.reflection_engine.generate_batch_reflection_prompt(
                batch, period,
                reflection_questions=self.questions,
                tick_label=self.tick_label,
            )
            try:
                raw = self.llm_invoke(prompt)
                text = raw[0] if isinstance(raw, tuple) else raw
                parse = self.parse_fn or self.reflection_engine.parse_batch_reflection_response
                insights = parse(text, batch_ids, period)
                for agent_id, insight in (insights or {}).items():
                    if not insight:
                        continue
                    self.reflection_engine.store_insight(agent_id, insight)
                    summary = getattr(insight, "summary", str(insight))
                    self.memory_engine.add_memory(
                        agent_id,
                        f"Consolidated Reflection: {summary}",
                        dict(self.insight_metadata),
                    )
                    stored += 1
            except Exception as exc:
                # fail-soft per batch (legacy-loop posture): log, keep going.
                logger.warning(
                    f"[Reflection:Error] batch {i // self.batch_size + 1}/{n_batches}: {exc}"
                )
        return stored


__all__ = ["ReflectionOrchestrator"]
