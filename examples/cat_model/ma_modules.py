"""Multi-agent catastrophe-model coupling modules.

Default scripted arithmetic for ``run_cat_ma.py``:

* Year 1 base depth 2.0 ft. PH1/PH2/PH3 are in force and owe
  47,500.00 + 21,280.00 + 82,680.00 = 151,460.00 against a pool of
  60,000.00 + 3 x 1,200.00 premiums = 63,600.00, so settlement is
  pro-rata at a 63,600 / 151,460 = 0.419913 insurance payout ratio.
  PH4 has ground-up loss but starts out of force, so it has no legitimate
  covered claim (and pays no premium).
* Year 2 base depth 8.0 ft. PH1/PH2/PH3 owe 167,500.00 + 73,120.00 +
  200,000.00 = 440,620.00. Year-1 settlement exhausted the pool, so Year 2
  opens with only the 3 x 1,200.00 = 3,600.00 fresh premiums; the scripted
  government releases the 30,000.00 relief budget in Year 2.

The model is deterministic and seed-free. Policyholder claim filing only
adds to the period claim queue; the shared pool mutates exactly once in
``settle_period()`` through ``PortfolioLedger.settle()``.

DESIGN LINEAGE (FLOODABM alignment, 2026-06-10): the per-claim payout
semantics follow FLOODABM ``modules/finance/finance.py:75-77`` —
``owed = min(max(0, gross - deductible), limit)``, a FLAT per-claim
deductible subtracted FIRST, with the limit capping the net. Per-period
premiums (in-force policyholders credit the pool each period) follow
FLOODABM's premium-as-decision-cost role — they give ``lapse_policy`` a
real economic motive. Deliberate simplifications vs FLOODABM (this stays
ONE generic-module example, not a port): single combined exposure (no
structure/contents split), toy linear damage curve (FLOODABM uses
empirical piecewise tables), and an insurer pool + government relief
that FLOODABM does not have at all (its insurer is exogenous and
unbounded — the pool/settlement layer is THIS framework's addition).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from broker.coupling import Event, InterfaceBundle, WorldDelta

from examples.cat_model.coupling_modules import (
    FloodFootprintSource,
    PortfolioLedger,
    depth_damage_ratio,
)


class MaFootprintSource(FloodFootprintSource):
    """Flood footprint with deterministic per-agent zone multipliers."""

    def __init__(
        self,
        depths_by_period: Dict[int, float],
        zone_multipliers: Dict[str, float],
        unit: str = "ft",
    ):
        super().__init__(depths_by_period, unit=unit)
        self._zone_multipliers = {
            str(agent_id): float(multiplier)
            for agent_id, multiplier in zone_multipliers.items()
        }

    def intensity_at(self, agent_id: str, event: Event) -> float:
        base_depth = super().intensity_at(agent_id, event)
        return base_depth * self._zone_multipliers.get(str(agent_id), 1.0)

    def get_provenance(self) -> Dict[str, Any]:
        prov = super().get_provenance()
        prov["zone_multipliers"] = dict(sorted(self._zone_multipliers.items()))
        return prov


class MaCatBundle(InterfaceBundle):
    """N policyholders, one insurer, and one government sharing one pool."""

    def __init__(
        self,
        event_src: MaFootprintSource,
        ledger: PortfolioLedger,
        households: Dict[str, Dict[str, Any]],
        gov_budget: float,
        premium_per_period: float = 1_200.0,
    ):
        super().__init__(event_src=event_src, financial=ledger)
        self.ledger = ledger
        self.households: Dict[str, Dict[str, Any]] = {
            aid: {
                "exposure": float(terms["exposure"]),
                "deductible": float(terms["deductible"]),
                "limit": float(terms["limit"]),
                "in_force": bool(terms["in_force"]),
                "zone_multiplier": float(terms["zone_multiplier"]),
            }
            for aid, terms in households.items()
        }
        self.gov_budget = float(gov_budget)
        # FLOODABM-alignment amendment 2 (2026-06-10): flat per-period premium
        # credited to the pool by each in-force policyholder at period start —
        # the economic motive behind lapse_policy (premium saved, coverage
        # lost). Flat, not FLOODABM's per-$1k rate tables (do-NOT-port).
        self.premium_per_period = float(premium_per_period)
        self.period_losses: Dict[str, tuple[float, float]] = {}
        self.pending_claims: Dict[str, float] = {}
        self.disposition: Optional[str] = None
        self.relief_intent = False
        self.last_settlement: Dict[str, Any] = self._empty_settlement("none")
        self._settled_this_period = False

    def run_pipeline(
        self,
        base_env: Dict[str, Any],
        events: List[Event],
        operation_order,
        control_hold_policy: str = "constant",
    ) -> Dict[str, Any]:
        env: Dict[str, Any] = dict(base_env)
        self.pending_claims = {}
        self._settled_this_period = False

        # Premiums first (amendment 2): every in-force policyholder credits
        # the pool at period start — collected BEFORE this period's losses.
        premiums_collected = 0.0
        for terms in self.households.values():
            if terms["in_force"] and self.premium_per_period > 0.0:
                premiums_collected += self.premium_per_period
        if premiums_collected:
            self.ledger.pool_budget += premiums_collected

        base_depth = float(events[0].payload["depth"]) if events else 0.0
        period_losses: Dict[str, tuple[float, float]] = {}
        for aid, terms in self.households.items():
            intensity = (
                self.event_src.intensity_at(aid, events[0])
                if events and self.event_src is not None
                else 0.0
            )
            ground_up = depth_damage_ratio(intensity) * terms["exposure"]
            if terms["in_force"]:
                owed = min(
                    max(0.0, ground_up - terms["deductible"]),
                    terms["limit"],
                )
            else:
                owed = 0.0
            period_losses[aid] = (round(ground_up, 2), round(owed, 2))

        self.period_losses = period_losses
        total_ground = sum(ground for ground, _owed in period_losses.values())
        last = self.last_settlement or self._empty_settlement("none")
        last_total_owed = float(last.get("total_owed", 0.0) or 0.0)
        last_ratio = (
            float(last.get("total_paid", 0.0) or 0.0) / last_total_owed
            if last_total_owed > 0.0
            else 1.0
        )

        env.update(
            {
                "flood_depth_ft": round(base_depth, 3),
                "total_ground_up_loss": round(total_ground, 2),
                "n_agents_with_loss": sum(
                    1 for ground, _owed in period_losses.values() if ground > 0.0
                ),
                "pool_budget_remaining": round(self.ledger.pool_budget, 2),
                "gov_budget_remaining": round(self.gov_budget, 2),
                "premium_per_period": round(self.premium_per_period, 2),
                "premiums_collected": round(premiums_collected, 2),
                "last_settlement_rule": last.get("rule", "none"),
                "last_payout_ratio": round(last_ratio, 6),
                "total_claims_owed": 0.0,
                "n_claims": 0,
                "settlement_disposition": "undecided",
            }
        )
        return env

    def commit_world_delta(self, approved_skill: Any) -> WorldDelta:
        skill = getattr(approved_skill, "skill_name", "")
        agent_id = getattr(approved_skill, "agent_id", "")
        agent_type = self._agent_type(agent_id)

        if agent_type == "policyholder":
            if skill == "file_claim":
                owed = self.period_losses.get(agent_id, (0.0, 0.0))[1]
                self.pending_claims[agent_id] = float(owed)
                return WorldDelta(
                    world_changes={"claim_filed": float(owed)},
                    contention_rule="claim_queue",
                )
            if skill == "lapse_policy":
                if agent_id in self.households:
                    # The lapse takes effect immediately after this decision;
                    # that is equivalent to "next period" for settlement,
                    # because filed claims have already been queued.
                    self.households[agent_id]["in_force"] = False
                return WorldDelta(
                    world_changes={"lapsed": 1},
                    contention_rule="policy_status",
                )
            return WorldDelta(world_changes={}, contention_rule="none")

        if agent_type == "insurer_ma":
            if skill in {"settle_full", "settle_prorata"}:
                self.disposition = skill
                return WorldDelta(
                    world_changes={"disposition": skill},
                    contention_rule="pending_settlement",
                )
            return WorldDelta(world_changes={}, contention_rule="none")

        if agent_type == "government_ma":
            if skill == "fund_shortfall_relief":
                self.relief_intent = True
                return WorldDelta(
                    world_changes={"relief_intent": True},
                    contention_rule="pending_relief",
                )
            if skill == "no_action":
                self.relief_intent = False
                return WorldDelta(
                    world_changes={"relief_intent": False},
                    contention_rule="no_relief",
                )
        return WorldDelta(world_changes={}, contention_rule="none")

    def settle_period(self) -> Dict[str, Any]:
        """Settle queued claims once; repeated calls pay nothing."""
        if self._settled_this_period:
            return {
                "rule": "already_settled",
                "per_agent_paid": {},
                "per_agent_relief": {},
                "pool_remaining": round(self.ledger.pool_budget, 2),
                "gov_budget_remaining": round(self.gov_budget, 2),
                "total_owed": 0.0,
                "total_paid": 0.0,
                "total_relief": 0.0,
                "payout_ratio": 1.0,
            }

        claims = {aid: float(v) for aid, v in self.pending_claims.items() if v > 0.0}
        if not claims:
            record = self._empty_settlement("none")
            self.last_settlement = record
            self._clear_period_decisions()
            self._settled_this_period = True
            return record

        disposition = self.disposition or "settle_prorata"
        settlement = self.ledger.settle(claims)
        per_agent_paid = {aid: round(v, 2) for aid, v in settlement.per_agent.items()}
        per_agent_relief = {aid: 0.0 for aid in claims}

        if settlement.rule == "pro_rata" and self.relief_intent:
            shortfalls = {
                aid: max(0.0, claims[aid] - settlement.per_agent.get(aid, 0.0))
                for aid in claims
            }
            total_shortfall = sum(shortfalls.values())
            available = max(0.0, self.gov_budget)
            if total_shortfall > 0.0 and available > 0.0:
                relief_scale = min(1.0, available / total_shortfall)
                relief_raw = {
                    aid: shortfall * relief_scale
                    for aid, shortfall in shortfalls.items()
                }
                per_agent_relief = {
                    aid: round(amount, 2) for aid, amount in relief_raw.items()
                }
                # Ledger consistency (review W5): debit EXACTLY the sum of the
                # rounded per-agent payments, so gov_budget_remaining always
                # equals budget_before - sum(per_agent_relief). The max(0, ...)
                # clamp absorbs the worst-case rounding overshoot (<= n/2 cents).
                relief_total = round(sum(per_agent_relief.values()), 2)
                self.gov_budget = max(0.0, self.gov_budget - relief_total)

        total_owed = sum(claims.values())
        total_paid = float(settlement.total)
        total_relief = sum(per_agent_relief.values())
        record = {
            "rule": settlement.rule,
            "disposition": disposition,
            "claims": {aid: round(v, 2) for aid, v in claims.items()},
            "per_agent_paid": per_agent_paid,
            "per_agent_relief": per_agent_relief,
            "pool_remaining": round(settlement.pool_remaining, 2),
            "gov_budget_remaining": round(self.gov_budget, 2),
            "total_owed": round(total_owed, 2),
            "total_paid": round(total_paid, 2),
            "total_relief": round(total_relief, 2),
            "payout_ratio": round(total_paid / total_owed, 6) if total_owed else 1.0,
        }
        self.last_settlement = record
        self._clear_period_decisions()
        self._settled_this_period = True
        return record

    def get_provenance(self) -> Dict[str, Any]:
        src_prov: Dict[str, Any] = {}
        fn = getattr(self.event_src, "get_provenance", None)
        if callable(fn):
            src_prov = fn()
        return {
            "bundle_class": type(self).__name__,
            "household_count": len(self.households),
            "total_exposure": round(
                sum(float(h["exposure"]) for h in self.households.values()), 2
            ),
            "pool_budget_at_provenance": round(self.ledger.pool_budget, 2),
            "gov_budget_at_provenance": round(self.gov_budget, 2),
            "event_source_provenance": src_prov,
        }

    def _agent_type(self, agent_id: str) -> str:
        """Map agent_id -> role for ``commit_world_delta`` dispatch.

        NAMING CONTRACT (review W2): policyholders are recognised by
        membership in ``self.households`` (authoritative); insurer/government
        only by the ``INS``/``GOV`` id prefix. Reusing this bundle with other
        naming conventions makes ``commit_world_delta`` a silent no-op for
        unrecognised ids — pass ids that honour the prefix contract, or
        subclass and override this method.
        """
        if agent_id in self.households or str(agent_id).upper().startswith("PH"):
            return "policyholder"
        if str(agent_id).upper().startswith("INS"):
            return "insurer_ma"
        if str(agent_id).upper().startswith("GOV"):
            return "government_ma"
        return "unknown"

    def _empty_settlement(self, rule: str) -> Dict[str, Any]:
        return {
            "rule": rule,
            "claims": {},
            "per_agent_paid": {},
            "per_agent_relief": {},
            "pool_remaining": round(self.ledger.pool_budget, 2),
            "gov_budget_remaining": round(self.gov_budget, 2),
            "total_owed": 0.0,
            "total_paid": 0.0,
            "total_relief": 0.0,
            "payout_ratio": 1.0,
        }

    def _clear_period_decisions(self) -> None:
        self.pending_claims = {}
        self.disposition = None
        self.relief_intent = False


# MA validator + DomainPack registration lives in examples/cat_model/__init__.py
# (review C2: one registration site, mirroring the single-agent pattern).
# Importing this module triggers the package __init__ anyway, so consumers
# still get the registrations without a dangling side-effect import here.
__all__ = ["MaFootprintSource", "MaCatBundle"]
