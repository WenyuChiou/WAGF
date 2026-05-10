"""
Vaccination ABM — minimal smoke-runnable entry point.

PoC scope: 3-5 years, 3-10 individuals making HBM-driven vaccination
decisions in a single-agent context. Uses real LLM (default
``gemma3:1b`` for smoke speed). No real survey data — synthetic personas.

Phase 6C-v3 reference: this script demonstrates that a brand-new
non-water domain plugs into WAGF using only ``examples/<domain>/``
files — no edits required to ``broker/``.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# CRITICAL: import the vaccination package BEFORE constructing the
# experiment so DomainPackRegistry / ValidatorRegistry / HBM framework
# metadata are all populated.
import examples.vaccination_demo  # noqa: F401 -- side-effect

from broker.agents import BaseAgent, AgentConfig
from broker.agents.base import StateParam, Skill
from broker.components.memory.engine import WindowMemoryEngine
from broker.core.experiment import ExperimentBuilder
from broker.interfaces.skill_types import ExecutionResult


# ─────────────────────────────────────────────────────────────────────
# Synthetic agent generation
# ─────────────────────────────────────────────────────────────────────

def build_synthetic_individuals(n: int, seed: int) -> Dict[str, BaseAgent]:
    rng = random.Random(seed)
    agents: Dict[str, BaseAgent] = {}
    for i in range(n):
        age_bracket = rng.choice(["18-34", "35-54", "55-74", "75+"])
        risk_tolerance = round(rng.uniform(0.2, 0.9), 2)
        trust_in_authority = round(rng.uniform(0.2, 0.95), 2)
        is_high_risk_group = age_bracket in ("55-74", "75+") or rng.random() < 0.15

        narrative = (
            f"You are a {age_bracket}-year-old. "
            f"You {'are' if is_high_risk_group else 'are not'} in a high-risk medical group. "
            f"Your trust in public health authorities is "
            f"{'high' if trust_in_authority > 0.6 else 'moderate' if trust_in_authority > 0.4 else 'low'}."
        )

        cfg = AgentConfig(
            name=f"Agent_{i+1:03d}",
            agent_type="individual",
            state_params=[
                StateParam("vaccinated", (0, 1), 0.0, "Has received a dose this cycle"),
                StateParam("weeks_since_dose", (0, 999), 999.0, "Weeks since last dose"),
                StateParam(
                    "had_infection", (0, 1), 0.0, "Has had a clinical infection"
                ),
            ],
            objectives=[],
            constraints=[],
            skills=[
                Skill("get_vaccinated", "Receive a vaccine dose", "vaccinated", "increase"),
                Skill("delay", "Wait for more information", None, "none"),
                Skill("refuse", "Decline vaccination this year", None, "none"),
            ],
        )
        agent = BaseAgent(cfg)
        agent.narrative_persona = narrative
        agent.is_high_risk_group = is_high_risk_group
        agent.trust_in_authority = trust_in_authority
        agent.risk_tolerance = risk_tolerance
        agents[cfg.name] = agent
    return agents


# ─────────────────────────────────────────────────────────────────────
# Vaccination environment — minimal outbreak schedule
# ─────────────────────────────────────────────────────────────────────


class VaccinationEnvironment:
    """Simple outbreak-schedule env. advance_year() emits global signals."""

    OUTBREAK_SCHEDULE = {2: 0.65}   # Year 2 moderate outbreak

    def __init__(self, agents: Dict[str, BaseAgent]):
        self.year = 0
        self.agents = agents
        self.global_state: Dict[str, Any] = {
            "outbreak_active": False,
            "outbreak_severity": 0.0,
            "vaccine_supply_label": "ample",
            "side_effect_signal": "no notable reports",
        }

    def advance_year(self) -> Dict[str, Any]:
        self.year += 1
        sev = self.OUTBREAK_SCHEDULE.get(self.year, 0.0)
        self.global_state["outbreak_active"] = sev > 0.4
        self.global_state["outbreak_severity"] = sev
        if sev >= 0.6:
            self.global_state["outbreak_severity_label"] = "severe"
        elif sev >= 0.4:
            self.global_state["outbreak_severity_label"] = "moderate"
        else:
            self.global_state["outbreak_severity_label"] = "low"
        self.global_state["current_year"] = self.year
        return dict(self.global_state)

    def execute_skill(self, approved_skill) -> ExecutionResult:
        agent = self.agents.get(approved_skill.agent_id)
        if not agent:
            return ExecutionResult(success=False, error=f"Agent {approved_skill.agent_id} not found")

        name = approved_skill.skill_name
        changes: Dict[str, Any] = {}
        if name == "get_vaccinated":
            agent.dynamic_state["vaccinated"] = True
            agent.dynamic_state["weeks_since_dose"] = 0
            changes = {"vaccinated": True, "weeks_since_dose": 0}
        elif name in ("delay", "refuse"):
            # Increment time-since-dose if previously vaccinated
            try:
                cur = int(agent.dynamic_state.get("weeks_since_dose", 999))
                agent.dynamic_state["weeks_since_dose"] = min(999, cur + 52)
                changes = {"weeks_since_dose": agent.dynamic_state["weeks_since_dose"]}
            except (TypeError, ValueError):
                pass
        return ExecutionResult(success=True, state_changes=changes)


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────


def main() -> None:
    p = argparse.ArgumentParser(description="Vaccination demo PoC")
    p.add_argument("--model", default="gemma3:1b")
    p.add_argument("--years", type=int, default=3)
    p.add_argument("--agents", type=int, default=5)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "results" / "smoke"),
    )
    p.add_argument("--num-ctx", type=int, default=4096)
    p.add_argument("--num-predict", type=int, default=1024)
    p.add_argument("--verbose", action="store_true", help="Print full prompt to stderr (debug)")
    args = p.parse_args()

    script_dir = Path(__file__).resolve().parent
    agents = build_synthetic_individuals(args.agents, args.seed)
    sim = VaccinationEnvironment(agents)

    runner = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.years)
        .with_agents(agents)
        .with_simulation(sim)
        .with_skill_registry(str(script_dir / "config" / "skill_registry.yaml"))
        .with_memory_engine(WindowMemoryEngine(window_size=5))
        .with_governance("strict", str(script_dir / "config" / "agent_types.yaml"))
        .with_exact_output(args.output)
        .with_workers(1)
        .with_seed(args.seed)
        .with_verbose(args.verbose)
    ).build()

    print(
        f"--- Vaccination demo PoC | {args.model} | "
        f"{len(agents)} agents | {args.years} years | seed={args.seed} ---"
    )
    runner.run()
    print(f"--- Complete! Results in {args.output} ---")


if __name__ == "__main__":
    main()
