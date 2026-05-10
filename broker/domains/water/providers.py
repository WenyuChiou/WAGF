"""
Water-domain (flood) context providers.

Phase 6C-v3 (2026-05-10): :class:`FinancialCostProvider` relocated here
from ``broker/components/context/providers.py``. The class is wholly
flood-specific — ELEVATION_COST_BASE keyed by feet, BUYOUT_OFFER_FRACTION,
NFIP renewal fatigue narrative, MG barrier text, premium escalation
warnings — so it lives with the rest of the water domain.

A backward-compat re-export shim remains at the original location so
existing flood-domain callers keep working with a one-time
DeprecationWarning.

New domains define their own analogous providers in
``broker/domains/<name>/providers.py`` (or in their example package).
"""
from __future__ import annotations

from typing import Callable, Optional

from broker.components.context.providers import ContextProvider


class FinancialCostProvider(ContextProvider):
    """Pre-decision financial cost disclosure for all adaptation options.

    Injects per-agent elevation costs, buyout offers, and other financial
    details into agent context. Uses agent RCV, subsidy rate, and foundation
    type to compute personalized cost estimates.

    Reference: Paper 3 Section 3.3 (Financial information in prompt)
    """

    # Baseline elevation costs by feet (pre-subsidy, average US)
    ELEVATION_COST_BASE = {
        3: 45000,
        5: 80000,
        8: 150000,
    }

    # Buyout offer as fraction of pre-flood RCV
    BUYOUT_OFFER_FRACTION = 0.75

    def __init__(self, subsidy_rate_fn: Optional[Callable] = None):
        """Initialize with optional dynamic subsidy rate function.

        Args:
            subsidy_rate_fn: Optional callable() -> float returning current
                subsidy rate. If None, reads from env_context.
        """
        self.subsidy_rate_fn = subsidy_rate_fn

    def provide(self, agent_id, agents, context, **kwargs):
        agent = agents.get(agent_id)
        if not agent:
            return

        env_context = kwargs.get("env_context", {})
        if not env_context:
            env_context = context.get("env_state", {})

        personal = context.setdefault("personal", {})

        # Get subsidy rate
        if self.subsidy_rate_fn:
            subsidy_rate = self.subsidy_rate_fn()
        else:
            subsidy_rate = env_context.get("subsidy_rate", 0.5)

        # Get agent's RCV (replacement cost value) from fixed_attributes or direct attribute
        fixed = getattr(agent, "fixed_attributes", {}) or {}
        rcv_building = fixed.get("rcv_building", 0)
        if not rcv_building:
            if hasattr(agent, "rcv_building"):
                rcv_building = agent.rcv_building
            elif isinstance(agent, dict):
                rcv_building = agent.get("rcv_building", 0)

        rcv_contents = fixed.get("rcv_contents", 0)
        income = fixed.get("income", 50000)
        premium_rate = env_context.get("premium_rate", 0.02)

        # Elevation costs (after subsidy)
        for feet, base_cost in self.ELEVATION_COST_BASE.items():
            after_subsidy = base_cost * (1 - subsidy_rate)
            personal[f"elevation_cost_{feet}ft"] = after_subsidy

        # Buyout offer
        buyout_offer = rcv_building * self.BUYOUT_OFFER_FRACTION
        personal["buyout_offer"] = buyout_offer

        # Per-agent insurance premium estimate
        property_value = rcv_building + rcv_contents
        current_premium = premium_rate * property_value
        personal["current_premium"] = current_premium

        # Subsidy rate (ensure it's in context for template)
        personal["subsidy_rate"] = subsidy_rate

        # Elevation cost burden: lowest option cost as % of annual income.
        min_elev_cost = min(personal.get(f"elevation_cost_{ft}ft", 0)
                            for ft in self.ELEVATION_COST_BASE)
        personal["elevation_burden_pct"] = (
            min_elev_cost / income * 100 if income > 0 else 999
        )

        # Insurance premium burden: premium as % of annual income.
        insurance_burden_pct = (
            current_premium / income * 100 if income > 0 else 999
        )
        personal["insurance_burden_pct"] = insurance_burden_pct

        # 3-tier affordability scheme calibrated to MG/NMG burden distributions in PRB
        if insurance_burden_pct < 5:
            affordability = "affordable"
        elif insurance_burden_pct < 12:
            affordability = (
                "a meaningful financial commitment. "
                "Some households at this income level delay or skip insurance"
            )
        else:
            affordability = (
                "a heavy financial burden. "
                "Many households at this income level choose not to "
                "sustain insurance"
            )

        personal["insurance_cost_text"] = (
            f"- Insurance Premium Burden: Your ${current_premium:,.0f}/year premium "
            f"is {insurance_burden_pct:.1f}% of your annual income (${income:,.0f}). "
            f"This is {affordability}. "
            f"Below 5% of income is generally affordable. "
            f"Above 12% is a heavy burden for most households."
        )

        # --- Hybrid prompt guidance for MG barrier and renewal fatigue ---
        is_mg = personal.get("mg", False)
        flood_count = personal.get("flood_count", 0)
        flooded_this_year = personal.get("flooded_this_year", False)
        years_since_flood = personal.get("years_since_flood", 99)
        flood_zone = personal.get("flood_zone", "MEDIUM")
        has_insurance = personal.get("has_insurance", False)

        # MG barrier prompt — DomainPack delegated (Phase 6C-v2)
        if (is_mg and flood_count == 1
                and not flooded_this_year and not has_insurance):
            barrier_text = ""
            try:
                from broker.domains.registry import DomainPackRegistry
                for _name in DomainPackRegistry.domains():
                    _pack = DomainPackRegistry.get(_name)
                    if _pack is None:
                        continue
                    candidate = _pack.mg_barrier_text(personal)
                    if candidate:
                        barrier_text = candidate
                        break
            except ImportError:
                pass

            if not barrier_text:
                # Legacy fallback (Passaic narrative) for partial bring-up.
                barrier_text = (
                    "- **Insurance Enrollment Context**: Among households with your "
                    "income profile and community background in the Passaic River Basin "
                    "who have experienced one prior flood, carrying NFIP flood insurance "
                    "is uncommon — many face enrollment barriers including documentation "
                    "requirements, upfront costs, and distrust of federal programs."
                )
            personal["mg_barrier_text"] = barrier_text
        else:
            personal["mg_barrier_text"] = ""

        # Renewal fatigue prompt
        renewal_fatigue_text = ""
        if (not flooded_this_year
                and 1 <= years_since_flood <= 2
                and flood_zone != "HIGH"
                and flood_count > 0
                and has_insurance):
            renewal_fatigue_text = (
                f"- **Insurance Renewal Context**: It has been {years_since_flood} "
                f"year(s) since your last flood. NFIP policy retention data shows "
                f"that many policyholders discontinue coverage within a few years "
                f"without a reinforcing flood event — a common pattern driven by "
                f"fading risk salience and annual cost."
            )

        # P4: HIGH-zone premium pressure
        premium_escalation_pct = env_context.get("premium_escalation_pct", 0)
        if (has_insurance
                and flood_zone == "HIGH"
                and premium_escalation_pct > 30):
            renewal_fatigue_text += (
                f"\n- **Premium Escalation Warning**: Your premium has increased "
                f"{premium_escalation_pct:.0f}% from when you first purchased. "
                f"Updated federal flood risk assessments have significantly "
                f"increased costs for homeowners in your area. Many are "
                f"reassessing whether insurance remains affordable."
            )

        personal["renewal_fatigue_text"] = renewal_fatigue_text

        # P3: Cost pressure prompt for long-term insured without claims
        insured_years = personal.get("insured_years", 0)
        cumulative_premiums = personal.get("cumulative_premiums_paid", 0)
        if (has_insurance
                and insured_years >= 3
                and years_since_flood >= 3):
            personal["cost_pressure_text"] = (
                f"- **Cumulative Cost Consideration**: You have been paying flood "
                f"insurance for {insured_years} consecutive years without filing a "
                f"claim. Your cumulative premiums total approximately "
                f"${cumulative_premiums:,.0f}. Some policyholders in this situation "
                f"decide the ongoing cost is not worth it."
            )
        else:
            personal["cost_pressure_text"] = ""


__all__ = ["FinancialCostProvider"]
