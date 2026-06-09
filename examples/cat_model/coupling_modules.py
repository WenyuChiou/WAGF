"""Catastrophe-model coupling modules (Phase 6V worked example).

Concrete implementations of the generic ``broker.coupling`` interfaces for a
minimal hazard -> exposure -> vulnerability -> financial chain (OASIS Loss
Modelling Framework shape). All catastrophe vocabulary lives HERE under
``examples/`` — never in ``broker/coupling/`` (genericity invariant).

  FloodFootprintSource -> broker.coupling.EventSource    (HAZARD)
  PortfolioLedger      -> broker.coupling.FinancialLedger (FINANCIAL)
  CatBundle            -> broker.coupling.InterfaceBundle (composes the chain)

The bundle's ``run_pipeline`` projects the world->agent observations the insurer
agent reads (ground-up loss, policy terms, pool budget); ``commit_world_delta``
is the PURE COMMITTER (governance already ran in the retry loop) that debits the
pool for an approved payout exactly once (E2) and records the resolution (E4).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from broker.coupling import (
    CouplingViolation,
    Event,
    EventSource,
    FinancialLedger,
    InterfaceBundle,
    Settlement,
    WorldDelta,
)


# ----------------------------------------------------------------------------
# HAZARD — a deterministic flood-depth footprint source
# ----------------------------------------------------------------------------
class FloodFootprintSource:
    """Emits a flood event (depth, in feet) for periods with a configured depth.
    Deterministic + seed-free so the coupling is byte-reproducible."""

    def __init__(self, depths_by_period: Dict[int, float], unit: str = "ft"):
        self._depths = {int(k): float(v) for k, v in depths_by_period.items()}
        self._unit = unit

    def draw_events(self, period: int) -> List[Event]:
        depth = self._depths.get(int(period), 0.0)
        if depth <= 0.0:
            return []
        return [Event(event_id=f"flood_y{period}", period=int(period), payload={"depth": depth})]

    def intensity_at(self, agent_id: str, event: Event) -> float:
        return float(event.payload.get("depth", 0.0))

    def units(self) -> str:
        return self._unit


# ----------------------------------------------------------------------------
# FINANCIAL — a portfolio ledger with deductible/limit, reinsurance, shared pool
# ----------------------------------------------------------------------------
class PortfolioLedger:
    """Loss -> financial terms -> shared-pool settlement (E4 audited)."""

    def __init__(self, pool_budget: float, reinsurance_cede: float = 0.0):
        self.pool_budget = float(pool_budget)
        self._cede = float(reinsurance_cede)

    def ground_up_to_gross(self, loss: float, policy: Dict[str, Any]) -> float:
        deductible = float(policy.get("deductible", 0.0))
        limit = float(policy.get("limit", float("inf")))
        return min(max(0.0, float(loss) - deductible), limit)

    def gross_to_net(self, gross: float) -> float:
        return float(gross) * (1.0 - self._cede)

    def settle(self, claims: Dict[str, float]) -> Settlement:
        total = float(sum(claims.values()))
        if total <= 0.0:
            return Settlement(per_agent={k: 0.0 for k in claims}, rule="none", total=0.0,
                              pool_remaining=self.pool_budget)
        if total <= self.pool_budget:
            per = {k: float(v) for k, v in claims.items()}
            rule, paid = "full", total
        else:  # order-independent pro-rata (E4)
            scale = self.pool_budget / total
            per = {k: float(v) * scale for k, v in claims.items()}
            rule, paid = "pro_rata", self.pool_budget
        self.pool_budget -= paid
        return Settlement(per_agent=per, rule=rule, total=paid, pool_remaining=self.pool_budget)

    def _debit(self, amount: float) -> float:
        """INTERNAL: debit the pool by ``amount`` (clamped to remaining), return
        amount paid. Package-private: world-mutating payouts route through the
        governed commit path (``CatBundle.commit_world_delta``), never directly,
        so the solvency validator is not bypassed. Multi-claim contention uses
        ``settle()`` (pro-rata) instead."""
        paid = min(max(0.0, float(amount)), self.pool_budget)
        self.pool_budget -= paid
        return paid


# ----------------------------------------------------------------------------
# A simple depth -> damage-ratio curve (VULNERABILITY, inlined for the minimal slice)
# ----------------------------------------------------------------------------
def depth_damage_ratio(depth_ft: float) -> float:
    """Monotone FEMA-style depth-damage curve, capped at 1.0."""
    if depth_ft <= 0.0:
        return 0.0
    return min(1.0, 0.05 + 0.08 * float(depth_ft))


# ----------------------------------------------------------------------------
# COMPOSITION — the bundle for a single insured household + insurer
# ----------------------------------------------------------------------------
class CatBundle(InterfaceBundle):
    """Minimal event-based cat coupling: one insured exposure, one pool.

    ``run_pipeline`` rolls the period's event into the world->agent observations
    the insurer reads; ``commit_world_delta`` applies an approved payout once.
    """

    def __init__(
        self,
        event_src: EventSource,  # any EventSource — FloodFootprintSource OR a BmiEventSource-wrapped solver
        ledger: PortfolioLedger,
        exposure_value: float = 250_000.0,
        deductible: float = 5_000.0,
        limit: float = 200_000.0,
        policy_in_force: bool = True,
    ):
        super().__init__(event_src=event_src, financial=ledger)
        self.ledger = ledger
        self.exposure_value = float(exposure_value)
        self.deductible = float(deductible)
        self.limit = float(limit)
        self.policy_in_force = bool(policy_in_force)
        # Set by run_pipeline each period, consumed by commit_world_delta. None =
        # "no owed amount established this period" -> commit raises (no silent debit).
        self._last_owed: Optional[float] = None

    def run_pipeline(self, base_env, events, operation_order, control_hold_policy="constant"):
        env: Dict[str, Any] = dict(base_env)
        depth = float(events[0].payload["depth"]) if events else 0.0
        ground_up = depth_damage_ratio(depth) * self.exposure_value
        policy = {"deductible": self.deductible, "limit": self.limit}
        owed = self.ledger.ground_up_to_gross(ground_up, policy)
        self._last_owed = owed
        env["flood_depth_ft"] = depth
        env["agent_ground_up_loss"] = round(ground_up, 2)
        env["policy_deductible"] = self.deductible
        env["policy_limit"] = self.limit
        env["policy_in_force_before_event"] = self.policy_in_force
        env["pool_budget_remaining"] = round(self.ledger.pool_budget, 2)
        env["owed_payout"] = round(owed, 2)
        return env

    def commit_world_delta(self, approved_skill: Any) -> WorldDelta:
        skill = getattr(approved_skill, "skill_name", "")
        if skill != "approve_payout":
            return WorldDelta(agent_state_changes={}, world_changes={"payout": 0.0}, contention_rule="none")
        # E2: commit exactly once per period. _last_owed is set by run_pipeline and
        # consumed here; a commit without a matching same-period run_pipeline (stale
        # restart / replay / double-commit) is a HARD error, not a silent debit.
        if self._last_owed is None:
            raise CouplingViolation(
                "commit_world_delta(approve_payout) called without a preceding "
                "run_pipeline for this period — no owed amount established."
            )
        owed = self._last_owed
        self._last_owed = None  # consume -> a second commit raises (idempotent E2)
        paid = self.ledger._debit(owed)
        rule = "no_loss" if owed <= 0.0 else ("full" if paid >= owed else "pro_rata")
        return WorldDelta(
            agent_state_changes={"last_payout": paid},
            world_changes={"payout": paid, "pool_remaining": round(self.ledger.pool_budget, 2)},
            contention_rule=rule,
        )


__all__ = ["FloodFootprintSource", "PortfolioLedger", "CatBundle", "depth_damage_ratio"]
