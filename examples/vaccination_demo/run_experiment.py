"""
Vaccination ABM — Tier-2 showcase entry point.

L3-1A scope (2026-05-23): 3-5 years, 25 individuals (default) making
HBM-driven vaccination decisions in a single-agent context. Uses real
LLM (default ``gemma3:1b`` for smoke speed). Agent attributes sampled
from literature-grounded distributions — see
``data/persona_distributions.yaml`` (US Census 2020 ACS age, Pew 2024
trust-in-public-health, CDC high-risk-group probability). No real
survey data behind the population; for paper-grade use an IRB-
approved primary survey calibration.

Phase 6C-v3 reference: this script demonstrates that a brand-new
non-water domain plugs into WAGF using only ``examples/<domain>/``
files — no edits required to ``broker/``.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

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
# Synthetic agent generation (L3-1A: literature-grounded distributions)
# ─────────────────────────────────────────────────────────────────────

_DEFAULT_DISTRIBUTIONS_PATH = (
    Path(__file__).resolve().parent / "data" / "persona_distributions.yaml"
)


def _load_persona_distributions(
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Load the literature-anchored persona distributions YAML.

    Schema documented at `examples/vaccination_demo/data/persona_distributions.yaml`
    (Pew + Carpenter 2010 + US Census 2020 ACS citations at the top).
    """
    src = Path(path) if path else _DEFAULT_DISTRIBUTIONS_PATH
    if not src.exists():
        raise FileNotFoundError(
            f"persona_distributions.yaml not found at {src}; "
            f"L3-1A sampler requires the literature anchor file."
        )
    with open(src, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _sample_categorical(rng: random.Random, dist: Dict[str, float]) -> str:
    """Categorical draw from a {category: probability} dict."""
    cats = list(dist.keys())
    weights = [float(dist[c]) for c in cats]
    return rng.choices(cats, weights=weights, k=1)[0]


def _sample_clipped_normal(
    rng: random.Random, mean: float, sd: float,
    lo: float = 0.05, hi: float = 0.99,
) -> float:
    """Gaussian draw clipped to [lo, hi] and rounded to 2 dp."""
    val = rng.gauss(mean, sd)
    return round(max(lo, min(hi, val)), 2)


def build_synthetic_individuals(
    n: int, seed: int,
    distributions_path: Optional[Path] = None,
) -> Dict[str, BaseAgent]:
    """Sample `n` agents from literature-grounded distributions.

    Phase L3-1A (2026-05-23): replaces the random.uniform(0.2, 0.9)
    PoC sampler with categorical age (US Census 2020 ACS) +
    age-stratified trust (Pew 2024) + age-stratified risk tolerance
    + CDC-anchored high-risk-group probability.

    All citations are recorded in `data/persona_distributions.yaml`.
    """
    rng = random.Random(seed)
    dists = _load_persona_distributions(distributions_path)
    age_dist = dists["age_distribution"]
    trust_by_age = dists["trust_in_authority_by_age"]
    risk_by_age = dists["risk_tolerance_by_age"]
    hr_by_age = dists["high_risk_group_probability"]

    agents: Dict[str, BaseAgent] = {}
    for i in range(n):
        age_bracket = _sample_categorical(rng, age_dist)

        trust_params = trust_by_age[age_bracket]
        trust_in_authority = _sample_clipped_normal(
            rng, trust_params["mean"], trust_params["sd"],
        )

        risk_params = risk_by_age[age_bracket]
        risk_tolerance = _sample_clipped_normal(
            rng, risk_params["mean"], risk_params["sd"],
        )

        is_high_risk_group = rng.random() < float(hr_by_age[age_bracket])

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
        agent.age_bracket = age_bracket
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
    p.add_argument("--agents", type=int, default=25)
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
