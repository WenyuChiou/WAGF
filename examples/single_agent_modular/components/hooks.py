"""
Flood Hooks for Research Simulation.

Handles reflection, logging, memory trace capture, and year-end reporting.
"""
import json
from typing import Dict, Any
from pathlib import Path

import pandas as pd

from broker.components.reflection_engine import ReflectionEngine
from broker.utils.logging import setup_logger
from examples.single_agent_modular.components.simulation import classify_adaptation_state

logger = setup_logger(__name__)


class FloodHooks:
    """
    Hook implementation for flood adaptation experiment.

    Tracks decisions, appraisals, memory, and provides reflection.
    """

    def __init__(self, sim, runner, output_dir: Path):
        self.sim = sim
        self.runner = runner
        self.output_dir = output_dir
        self.logs = []
        self.reflection_engine = ReflectionEngine(
            reflection_interval=1,
            max_insights_per_reflection=2,
            insight_importance_boost=0.9,
            output_path=str(output_dir / "reflection_log.jsonl")
        )

    def pre_year(self, year: int, agents: Dict[str, Any]):
        """Reset year state and advance simulation."""
        events = self.sim.advance_year()
        logger.info(f"[Year {year}] Flood event: {events['flood_event']}, Grant: {events['grant_available']}")

    def post_step(self, step_id: int, agents: Dict[str, Any]):
        """Capture agent state after each decision step."""
        for agent in agents.values():
            if getattr(agent, "is_active", True) is False:
                continue

            appraisals = getattr(agent, "appraisals", {})
            yearly_decision = getattr(agent, "last_decision", None)

            mem_str = ""
            if hasattr(agent, "memory"):
                try:
                    mem_str = agent.memory.format_for_prompt()
                except Exception:
                    mem_str = str(agent.memory)

            self.logs.append({
                "agent_id": agent.id,
                "year": step_id,
                "cumulative_state": classify_adaptation_state(agent),
                "yearly_decision": yearly_decision or "N/A",
                "threat_appraisal": appraisals.get("threat_appraisal", "N/A"),
                "coping_appraisal": appraisals.get("coping_appraisal", "N/A"),
                "elevated": getattr(agent, "elevated", False),
                "has_insurance": getattr(agent, "has_insurance", False),
                "relocated": getattr(agent, "relocated", False),
                "trust_insurance": getattr(agent, "trust_in_insurance", 0),
                "trust_neighbors": getattr(agent, "trust_in_neighbors", 0),
                "memory": mem_str
            })

    def post_year(self, year: int, agents: Dict[str, Any]):
        """Log year summary and run reflection if needed."""
        df_year = pd.DataFrame([l for l in self.logs if l['year'] == year])
        if df_year.empty:
            return

        stats = df_year['cumulative_state'].value_counts()
        categories = [
            "Do Nothing", "Only Flood Insurance", "Only House Elevation",
            "Both Flood Insurance and House Elevation", "Relocate"
        ]
        stats_str = " | ".join([f"{cat}: {stats.get(cat, 0)}" for cat in categories])
        logger.info(f"[Year {year}] Stats: {stats_str}")
        logger.info(
            f"[Year {year}] Avg Trust: Ins={df_year['trust_insurance'].mean():.3f}, "
            f"Nb={df_year['trust_neighbors'].mean():.3f}"
        )

        if self.reflection_engine.should_reflect("any", year):
            self._run_batch_reflection(year)

    def _run_batch_reflection(self, year: int):
        """Run batch reflection for all agents."""
        refl_cfg = self.runner.broker.config.get_reflection_config()
        batch_size = refl_cfg.get("batch_size", 10)

        candidates = []
        for agent_id, agent in self.sim.agents.items():
            if getattr(agent, "relocated", False):
                continue
            memories = self.runner.memory_engine.retrieve(agent, top_k=10)
            if memories:
                candidates.append({"agent_id": agent_id, "memories": memories})

        if not candidates:
            return

        logger.info(f"[Reflection:Batch] Processing {len(candidates)} agents in batches of {batch_size}...")
        llm_call = self.runner.get_llm_invoke("household")

        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i + batch_size]
            batch_ids = [c["agent_id"] for c in batch]
            prompt = self.reflection_engine.generate_batch_reflection_prompt(batch, year)

            try:
                raw_res = llm_call(prompt)
                response_text = raw_res[0] if isinstance(raw_res, tuple) else raw_res

                insights = self.reflection_engine.parse_batch_reflection_response(response_text, batch_ids, year)
                for agent_id, insight in insights.items():
                    if insight:
                        self.reflection_engine.store_insight(agent_id, insight)
                        self.runner.memory_engine.add_memory(
                            agent_id,
                            f"Consolidated Reflection: {insight.summary}",
                            {"significance": 0.9, "emotion": "major", "source": "personal"}
                        )
            except Exception as exc:
                logger.error(f"[Reflection:Batch:Error] Batch {i // batch_size + 1} failed: {exc}")

        logger.info(f"[Reflection:Batch] Completed reflection for Year {year}.")
