"""TemporalRuleEvaluator — apply rules to trajectory and return violations.

Post-hoc orchestrator. Reads per-agent audit data (as pandas DataFrame
or equivalent iterable of dicts), constructs AgentTurn objects via the
adapter, and evaluates each rule at each (agent, year).

Framework is evaluation-only in this module. Live enforcement (blocking
proposals based on temporal rules) is a separate concern and is NOT
implemented here — it would hook into skill_broker_engine validation
retry loop and is deferred to V2 paper work.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .base import AgentTurn, DomainTemporalAdapter, TemporalRule, Violation


@dataclass
class TrajectoryEvaluation:
    """Aggregate result of evaluating rules across an entire experiment."""

    model: str = ""
    condition: str = ""
    run: str = ""
    n_decisions: int = 0
    violations: List[Violation] = field(default_factory=list)
    by_rule: Dict[str, int] = field(default_factory=dict)
    rate_by_rule: Dict[str, float] = field(default_factory=dict)


class TemporalRuleEvaluator:
    """Evaluates a set of TemporalRule objects against agent trajectories.

    The evaluator consumes audit-row-like dicts — it does not hardcode
    column names beyond a minimal contract:

        agent_id:                str
        year:                    int-coercible
        construct_TP_LABEL:      VL/L/M/H/VH (optional)
        construct_CP_LABEL:      VL/L/M/H/VH (optional)
        final_skill:             str (optional)
        mem_top_emotion:         str (optional)
        _memories:               list of dicts with {'content','emotion'} (optional)

    Missing fields are passed to AgentTurn as None; rules are expected
    to handle None gracefully (typically by returning None → no trigger).
    """

    def __init__(
        self,
        rules: List[TemporalRule],
        adapter: DomainTemporalAdapter,
    ):
        self.rules = rules
        self.adapter = adapter

    # ---------- building AgentTurn from an audit row ----------

    @staticmethod
    def _row_to_turn(row: Dict[str, Any]) -> AgentTurn:
        memories = row.get("_memories") or []
        if not memories and row.get("mem_top_emotion"):
            # Degrade gracefully — reconstruct a pseudo-memory from the
            # aggregate audit field. Loses per-memory detail but keeps
            # emotion signal for adapter.is_salient_event().
            memories = [{"content": "", "emotion": row.get("mem_top_emotion")}]

        return AgentTurn(
            agent_id=str(row.get("agent_id", "")),
            year=int(row.get("year", 0) or 0),
            threat_label=_safe_upper(row.get("construct_TP_LABEL")),
            coping_label=_safe_upper(row.get("construct_CP_LABEL")),
            final_skill=_safe_lower(row.get("final_skill")),
            top_emotion=_safe_lower(row.get("mem_top_emotion")),
            retrieved_memories=memories,
            raw=dict(row),
        )

    # ---------- per-agent trajectory evaluation ----------

    def evaluate_agent(self, agent_rows: Iterable[Dict[str, Any]]) -> List[Violation]:
        turns = sorted(
            (self._row_to_turn(r) for r in agent_rows),
            key=lambda t: t.year,
        )
        if not turns:
            return []

        violations: List[Violation] = []
        for i, current in enumerate(turns):
            history = turns[:i]
            for rule in self.rules:
                v = rule.check(current, history, self.adapter)
                if v is not None:
                    violations.append(v)
        return violations

    # ---------- per-experiment orchestration ----------

    def evaluate_experiment(
        self,
        rows: Iterable[Dict[str, Any]],
        *,
        model: str = "",
        condition: str = "",
        run: str = "",
    ) -> TrajectoryEvaluation:
        by_agent: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        n_decisions = 0
        for row in rows:
            by_agent[str(row.get("agent_id", ""))].append(row)
            n_decisions += 1

        violations: List[Violation] = []
        for agent_rows in by_agent.values():
            violations.extend(self.evaluate_agent(agent_rows))

        by_rule: Dict[str, int] = defaultdict(int)
        for v in violations:
            by_rule[v.rule_id] += 1

        rate_by_rule: Dict[str, float] = {}
        for rule in self.rules:
            rate_by_rule[rule.rule_id] = (
                100.0 * by_rule.get(rule.rule_id, 0) / n_decisions
                if n_decisions else 0.0
            )

        return TrajectoryEvaluation(
            model=model,
            condition=condition,
            run=run,
            n_decisions=n_decisions,
            violations=violations,
            by_rule=dict(by_rule),
            rate_by_rule=rate_by_rule,
        )


def _safe_upper(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text if text and text != "NAN" else None


def _safe_lower(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text if text and text != "nan" else None
