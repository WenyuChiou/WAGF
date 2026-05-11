"""Cross-agent state management for vaccination_ma_demo (Phase 6E).

This is THE load-bearing piece that proves Phase 1 verdict: a multi-agent
domain's cross-agent communication is the env-dict-whitelist pattern.

Per-year flow:

    pre_year(): pick outbreak severity, sync self.env -> runner env
        ↓
    [phase 1] health_authority decides → post_step writes advisory_*
        ↓
    [phase 2] community_org reads advisory_* from env → decides → post_step
              writes community_support_text + per-individual support
        ↓
    [phase 3] individual reads advisory_* + community_support_text from env
              → decides → post_step increments vaccinated_count
        ↓
    post_year(): aggregate vaccination_rate, store institutional memory,
                 reset transient state

No broker/ edits; this entirely user-code per Phase 1 verdict.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from broker.interfaces.skill_types import SkillOutcome


# Outbreak schedule — year → severity in [0, 1].
# Year 2 moderate outbreak mirrors the single-agent vaccination_demo default.
DEFAULT_OUTBREAK_SCHEDULE: Dict[int, float] = {2: 0.65}


class VaccinationMAHooks:
    """Lifecycle hooks for the 3-agent-type vaccination multi-agent demo."""

    def __init__(
        self,
        environment: Dict[str, Any],
        memory_engine: Optional[Any] = None,
        outbreak_schedule: Optional[Dict[int, float]] = None,
    ):
        self.env = environment
        self.memory_engine = memory_engine
        self.outbreak_schedule = outbreak_schedule or DEFAULT_OUTBREAK_SCHEDULE

        # --- Cross-agent state (defaults) -----------------------------
        # All keys here are the SOURCE OF TRUTH for cross-agent prompt
        # placeholders. They MUST be in run_experiment.py's
        # dynamic_whitelist for SafeFormatter to inject them.
        self.env.setdefault("advisory_strength_label", "none")
        self.env.setdefault("advisory_text", "No advisory issued.")
        self.env.setdefault("outbreak_severity_label", "low")
        self.env.setdefault("outbreak_severity", 0.0)
        self.env.setdefault("vaccination_rate_text", "no prior data")
        self.env.setdefault("vaccination_rate", 0.0)
        self.env.setdefault("community_activity_label", "none")
        self.env.setdefault("community_support_text", "no active outreach this year")

        # Counters / running aggregates
        self._vaccinated_count = 0
        self._n_individuals = 0
        self._community_orgs_decided_this_year = []

    # ------------------------------------------------------------------
    # pre_year
    # ------------------------------------------------------------------

    def pre_year(self, year: int, env: Dict[str, Any], agents: Dict[str, Any]) -> None:
        """Set outbreak severity for the year; alias self.env to runner env.

        CRITICAL (Phase 6E Finding #3): when no simulation engine is provided,
        ExperimentRunner creates a fresh `env = {}` each year and passes it
        here. If we keep our own self.env dict and only `env.update(self.env)`
        once, subsequent post_step writes won't propagate to context_builder
        reads in the same year. The fix is to ALIAS self.env to the runner's
        env dict for the rest of this year, so post_step writes land directly
        in the dict that context_builder reads.
        """
        # First sync any persistent state we carried over from last post_year
        # into the runner's fresh env dict.
        env.update(self.env)
        # Then alias self.env → runner's env for the rest of this year.
        # post_step writes now go directly into the runner's dict.
        self.env = env

        self.env["year"] = year

        # Reset per-year transient state
        self._vaccinated_count = 0
        self._n_individuals = sum(
            1 for a in agents.values() if a.agent_type == "individual"
        )
        self._community_orgs_decided_this_year = []

        # Outbreak severity for this year
        severity = self.outbreak_schedule.get(year, 0.0)
        self.env["outbreak_severity"] = severity
        if severity >= 0.6:
            label = "severe"
        elif severity >= 0.4:
            label = "moderate"
        elif severity >= 0.2:
            label = "mild"
        else:
            label = "low"
        self.env["outbreak_severity_label"] = label

        # Reset advisory + community_support at year start; institutional
        # agents will overwrite during their phase.
        self.env["advisory_strength_label"] = "none"
        self.env["advisory_text"] = "No advisory issued yet this year."
        self.env["community_support_text"] = "no active outreach yet this year"
        self.env["community_activity_label"] = "none"

        # Vaccination rate text uses LAST year's aggregate (set by post_year)
        # — left untouched here.
        # (No final env.update needed — self.env IS env now, post-aliasing.)

    # ------------------------------------------------------------------
    # post_step (per agent, after their action)
    # ------------------------------------------------------------------

    def post_step(self, agent: Any, result: Any) -> None:
        """Update env based on which agent type just decided."""
        # REJECTED outcomes fall back to safe defaults
        if result.outcome not in (SkillOutcome.APPROVED, SkillOutcome.RETRY_SUCCESS):
            if hasattr(agent, "dynamic_state"):
                agent.dynamic_state["last_decision"] = "fallback"
            return

        decision = result.skill_proposal.skill_name

        if agent.agent_type == "health_authority":
            self._handle_health_authority(decision, agent)
        elif agent.agent_type == "community_org":
            self._handle_community_org(decision, agent)
        elif agent.agent_type == "individual":
            self._handle_individual(decision, agent)

    def _handle_health_authority(self, decision: str, agent: Any) -> None:
        """Write env["advisory_*"] for downstream agents to read."""
        if decision == "advisory_strong":
            self.env["advisory_strength_label"] = "strong"
            self.env["advisory_text"] = (
                "Public health is STRONGLY urging vaccination this year; "
                "consider it as close to a directive as voluntary policy allows."
            )
        elif decision == "advisory_mild":
            self.env["advisory_strength_label"] = "mild"
            self.env["advisory_text"] = (
                "Public health is encouraging vaccination through an "
                "information campaign — no mandate, but the recommendation is clear."
            )
        else:  # advisory_none
            self.env["advisory_strength_label"] = "none"
            self.env["advisory_text"] = (
                "No public health advisory has been issued this year."
            )
        if hasattr(agent, "dynamic_state"):
            agent.dynamic_state["last_advisory_strength"] = (
                self.env["advisory_strength_label"]
            )

    def _handle_community_org(self, decision: str, agent: Any) -> None:
        """Aggregate community_org actions; write env["community_support_text"]."""
        self._community_orgs_decided_this_year.append(decision)

        # Aggregate label based on what community_orgs collectively did
        if any(d == "org_clinic" for d in self._community_orgs_decided_this_year):
            self.env["community_activity_label"] = "clinic"
            self.env["community_support_text"] = (
                "A mobile clinic is operating in your community this year; "
                "access barriers (cost, transport, scheduling) are lower than usual."
            )
        elif any(
            d == "org_education" for d in self._community_orgs_decided_this_year
        ):
            self.env["community_activity_label"] = "education"
            self.env["community_support_text"] = (
                "A community education campaign is active; awareness about "
                "vaccination is higher than usual this year."
            )
        else:
            self.env["community_activity_label"] = "none"
            self.env["community_support_text"] = (
                "No active community outreach this year."
            )
        if hasattr(agent, "dynamic_state"):
            agent.dynamic_state["last_outreach"] = decision

    def _handle_individual(self, decision: str, agent: Any) -> None:
        """Count vaccinations; update agent's own state."""
        if decision == "get_vaccinated":
            self._vaccinated_count += 1
            if hasattr(agent, "dynamic_state"):
                agent.dynamic_state["vaccinated"] = True
                agent.dynamic_state["weeks_since_dose"] = 0
        elif decision in ("delay", "refuse"):
            if hasattr(agent, "dynamic_state"):
                cur = agent.dynamic_state.get("weeks_since_dose", 999)
                try:
                    agent.dynamic_state["weeks_since_dose"] = min(999, int(cur) + 52)
                except (TypeError, ValueError):
                    pass

    # ------------------------------------------------------------------
    # post_year (aggregate)
    # ------------------------------------------------------------------

    def post_year(
        self, year: int, agents: Dict[str, Any], memory_engine: Optional[Any] = None
    ) -> None:
        """Aggregate vaccination_rate for next year's prompts."""
        if self._n_individuals > 0:
            rate = self._vaccinated_count / self._n_individuals
        else:
            rate = 0.0
        self.env["vaccination_rate"] = round(rate, 3)
        if rate >= 0.7:
            self.env["vaccination_rate_text"] = f"high uptake ({rate:.0%})"
        elif rate >= 0.4:
            self.env["vaccination_rate_text"] = f"moderate uptake ({rate:.0%})"
        elif rate > 0:
            self.env["vaccination_rate_text"] = f"low uptake ({rate:.0%})"
        else:
            self.env["vaccination_rate_text"] = "no uptake recorded"
