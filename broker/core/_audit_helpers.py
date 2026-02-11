"""AuditMixin — audit trace writing and state management helpers.

Extracted from SkillBrokerEngine to reduce file size.  These methods
access ``self.*`` attributes defined on SkillBrokerEngine; this is the
standard Python mixin pattern where the mixin is always combined with
the host class via multiple inheritance.
"""
from typing import Any, Dict, List, Optional
import hashlib
import json

from ..interfaces.skill_types import (
    ExecutionResult, SkillOutcome,
)
from ..utils.logging import logger


class AuditMixin:
    """Mixin providing audit trace writing and state management helpers."""

    # ------------------------------------------------------------------
    # Audit trace
    # ------------------------------------------------------------------
    def _write_audit_trace(
        self, *, agent_type: str, context: Dict, run_id: str,
        step_id: str, timestamp: str, env_context: Optional[Dict],
        seed: Any, agent_id: str, all_valid: bool, prompt: str,
        raw_output: str, context_hash: str, memory_pre: list,
        memory_post: list, skill_proposal, approved_skill,
        execution_result, outcome: SkillOutcome, retry_count: int,
        format_retry_count: int, total_llm_stats: Dict,
        all_validation_history: List,
    ) -> None:
        """Write full audit trace to audit_writer."""
        # Robust agent_type extraction (Tiered or Flat)
        agent_type_final = agent_type
        if "personal" in context and isinstance(context["personal"], dict):
            agent_type_final = context["personal"].get("agent_type", agent_type_final)
        elif "agent_type" in context:
            agent_type_final = context.get("agent_type", agent_type_final)

        # Extract audit priority fields from config
        log_fields = self.config.get_log_fields(agent_type_final)
        audit_priority = [f"reason_{f.lower()}" for f in log_fields]

        # Build memory_audit from pre-retrieval data for audit CSV
        memory_audit = {
            "retrieved_count": len(memory_pre),
            "memories": [
                {"content": m, "emotion": "neutral", "source": "personal"}
                if isinstance(m, str) else m
                for m in memory_pre
            ],
            "retrieval_mode": "humancentric" if memory_pre else "",
        }

        self.audit_writer.write_trace(agent_type_final, {
            "run_id": run_id,
            "step_id": step_id,
            "timestamp": timestamp,
            "year": env_context.get("current_year") if env_context else None,
            "seed": seed,
            "agent_id": agent_id,
            "validated": all_valid,
            "_audit_priority": audit_priority,
            "input": prompt,
            "raw_output": raw_output,
            "context_hash": context_hash,
            "memory_pre": memory_pre,
            "memory_post": memory_post,
            "memory_audit": memory_audit,
            "environment_context": env_context or {},
            "state_before": context.get("state", {}),
            "state_after": self._merge_state_after(context.get("state", {}), execution_result),
            "skill_proposal": skill_proposal.to_dict() if skill_proposal else None,
            "approved_skill": {
                "skill_name": approved_skill.skill_name,
                "status": approved_skill.approval_status,
                "mapping": approved_skill.execution_mapping,
            } if approved_skill else None,
            "execution_result": execution_result.__dict__ if execution_result else None,
            "outcome": outcome.value,
            "retry_count": retry_count,
            "format_retries": format_retry_count,
            "llm_stats": total_llm_stats,
        }, all_validation_history)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def _merge_state_after(self, state_before: Dict[str, Any], execution_result: Optional[ExecutionResult]) -> Dict[str, Any]:
        """Approximate state-after snapshot using execution_result state changes."""
        merged = dict(state_before) if isinstance(state_before, dict) else {}
        if execution_result and getattr(execution_result, "state_changes", None):
            merged.update(execution_result.state_changes)
        return merged

    def _get_memory_snapshot(self, agent_id: str) -> List[Dict[str, Any]]:
        """Extract a structured memory snapshot for audit traces."""
        mem_engine = getattr(self.context_builder, "memory_engine", None)
        if not mem_engine and hasattr(self.context_builder, "hub"):
            mem_engine = getattr(self.context_builder.hub, "memory_engine", None)
        if not mem_engine:
            return []

        # HumanCentricMemoryEngine
        if hasattr(mem_engine, "working") and hasattr(mem_engine, "longterm"):
            working = mem_engine.working.get(agent_id, [])
            longterm = mem_engine.longterm.get(agent_id, [])
            return [m for m in working + longterm if isinstance(m, dict)]

        # WindowMemoryEngine
        if hasattr(mem_engine, "storage"):
            items = mem_engine.storage.get(agent_id, [])
            snapshot = []
            for item in items:
                if isinstance(item, dict):
                    snapshot.append(item)
                else:
                    content = str(item)
                    source = "reflection" if content.lower().startswith("reflection") else "memory"
                    snapshot.append({"content": content, "source": source})
            return snapshot

        # HierarchicalMemoryEngine
        if hasattr(mem_engine, "episodic"):
            items = mem_engine.episodic.get(agent_id, [])
            snapshot = []
            for item in items:
                if isinstance(item, dict):
                    entry = dict(item)
                    entry.setdefault("source", "episodic")
                    snapshot.append(entry)
                else:
                    snapshot.append({"content": str(item), "source": "episodic"})
            return snapshot

        return []

    def _hash_context(self, context: Dict) -> str:
        """Create hash of context for audit."""
        return hashlib.md5(json.dumps(context, sort_keys=True, default=str).encode()).hexdigest()[:16]
