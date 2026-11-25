"""Minimal 1-reservoir mass-balance world, hooks, and mock for templates/water_starter.

Variable & unit summary:
    storage         [maf]   Current end-of-year reservoir storage (initialized at 11.0 maf)
    capacity        [maf]   Maximum physical reservoir capacity (20.0 maf)
    dead_pool       [maf]   Minimum allowable storage floor (5.0 maf)
    demand_year     [maf]   Full annual target demand (9.0 maf/yr)
    inflow_forecast [maf]   Synthetic annual inflow for the coming year (10.0 then 1.5 maf)
    release_actual  [maf]   Actual annual release executed in the just-finished year
"""
from __future__ import annotations

import json
from typing import Any, Dict

from broker.agents import AgentConfig, BaseAgent
from broker.agents.base import Skill
from broker.interfaces.skill_types import ExecutionResult
from broker.run import RunContext
from broker.utils.llm_utils import LLMStats

# Reservoir physical parameters (units: million acre-feet, maf)
CAPACITY_MAF = 20.0
DEAD_POOL_MAF = 5.0
INITIAL_STORAGE_MAF = 11.0
ANNUAL_DEMAND_MAF = 9.0
SYNTHETIC_INFLOWS_MAF = (10.0, 1.5)  # Year 1 wet, Year 2 drought

OPTIONS_TEXT = "\n".join(
    [
        "1. set_release — set release fraction of annual demand in [0, 1]",
        "2. maintain_release — keep the previous annual release fraction",
    ]
)


class StarterReservoirWorld:
    """Minimal annual-step reservoir mass-balance simulation for broker.run."""

    def __init__(self) -> None:
        self.current_year = 0
        self.storage = INITIAL_STORAGE_MAF
        self.last_release_fraction = 1.0
        self.release_actual = 0.0

    def _forecast_for_year(self, year: int) -> float:
        return SYNTHETIC_INFLOWS_MAF[(year - 1) % len(SYNTHETIC_INFLOWS_MAF)]

    def advance_step(self) -> Dict[str, Any]:
        """Advance simulation clock by 1 year and publish prompt/rule state."""
        self.current_year += 1
        return {
            "current_year": self.current_year,
            "storage": round(self.storage, 3),
            "inflow_forecast": round(self._forecast_for_year(self.current_year), 3),
            "demand_year": ANNUAL_DEMAND_MAF,
            "dead_pool": DEAD_POOL_MAF,
            "capacity": CAPACITY_MAF,
            "release_actual": round(self.release_actual, 3),
        }

    def execute_skill(self, approved_skill: Any) -> ExecutionResult:
        """Apply the governed release fraction and advance 1 year of mass balance."""
        if approved_skill.skill_name == "set_release":
            raw = approved_skill.parameters.get("magnitude_pct", self.last_release_fraction)
            self.last_release_fraction = max(0.0, min(1.0, float(raw)))

        target_release = ANNUAL_DEMAND_MAF * self.last_release_fraction
        inflow = self._forecast_for_year(self.current_year)
        available = self.storage + inflow
        actual_release = min(target_release, max(0.0, available - DEAD_POOL_MAF))
        self.storage = min(CAPACITY_MAF, max(DEAD_POOL_MAF, available - actual_release))
        self.release_actual = actual_release
        return ExecutionResult(
            success=True,
            state_changes={
                "storage": round(self.storage, 3),
                "release_actual": round(actual_release, 3),
                "release_fraction": round(self.last_release_fraction, 3),
            },
        )


def build_world(ctx: RunContext) -> StarterReservoirWorld:
    """Factory registered at global_config.run.world."""
    return StarterReservoirWorld()


def build_agents(ctx: RunContext) -> Dict[str, BaseAgent]:
    """Factory registered at global_config.run.agents."""
    cfg = AgentConfig(
        name="OPERATOR",
        agent_type="operator",
        state_params=[],
        objectives=[],
        constraints=[],
        skills=[
            Skill("set_release", "Set annual release fraction [0..1]", None, "none"),
            Skill("maintain_release", "Keep previous release fraction", None, "none"),
        ],
    )
    return {"OPERATOR": BaseAgent(cfg)}


def build_hooks(ctx: RunContext) -> Dict[str, Any]:
    """Sync annual world state onto each agent's prompt context."""

    def on_pre_year(year: int, env: Dict[str, Any], agents: Dict[str, BaseAgent]) -> None:
        for agent in agents.values():
            agent.dynamic_state.update(env)
            agent.dynamic_state["options_text"] = OPTIONS_TEXT

    return {"pre_year": on_pre_year}


def _scripted_operator(prompt: str):
    """Demo mock: request 1.0 of demand initially, then curtail to 0.4 if blocked."""
    blocked = "BLOCKED" in prompt or "dead_pool_guard" in prompt
    magnitude = 0.4 if blocked else 1.0
    payload = {
        "reasoning": f"Propose release fraction {magnitude} for coming water year.",
        "decision": 1,
        "magnitude": magnitude,
    }
    text = f"<<<DECISION_START>>>\n{json.dumps(payload)}\n<<<DECISION_END>>>"
    return text, LLMStats(retries=0, success=True)


def operator_mock(ctx: RunContext):
    """Factory registered at global_config.run.mock for `--model mock`."""
    return {"operator": _scripted_operator}
