"""Phase 6U-C (2026-05-28): InsuranceInfoProvider relocated from
``broker/components/context/providers.py``.

The class is structurally generic — a `premium_calculator` callable
is injected by the domain at construction time — but its name and
its written context keys (``insurance_cost_text``,
``insurance_premium_amount``, ``insurance_pct_of_income``,
``insurance_affordability``) hard-code the flood-domain insurance
concept. Generic broker code referencing it is the leak this
relocation closes.

Old import path remains available via a `__getattr__` shim in
``broker.components.context.providers`` with a DeprecationWarning.
"""
from __future__ import annotations

from typing import Any, Callable, Dict

from broker.components.context.providers import ContextProvider


class InsuranceInfoProvider(ContextProvider):
    """Pre-decision insurance cost disclosure for agents.

    Injects insurance premium information into agent context so agents
    have symmetric cost information for all adaptation options (not just
    elevation grants).

    Literature: DYNAMO model (de Ruig et al. 2023) injects actuarial
    premium structure into agent decisions; this provider is the broker
    analogue — the domain supplies a ``premium_calculator`` callable.

    Reference: Task-060A Insurance Premium Disclosure
    """

    def __init__(
        self,
        premium_calculator: Callable[[str, Any, Dict[str, Any]], Dict[str, Any]],
        mode: str = "qualitative",
    ):
        """Initialize with a domain-specific premium calculator.

        Args:
            premium_calculator: Function(agent_id, agent, env_context) -> dict
                with keys: text, amount, pct_of_income, affordability_level
            mode: "qualitative" (narrative) or "quantitative" (numeric)
        """
        self.premium_calculator = premium_calculator
        self.mode = mode

    def provide(self, agent_id, agents, context, **kwargs):
        agent = agents.get(agent_id)
        if not agent:
            return

        env_context = kwargs.get("env_context", {})
        # Also check context for env_state (TieredContextBuilder pattern)
        if not env_context:
            env_context = context.get("env_state", {})

        cost_info = self.premium_calculator(agent_id, agent, env_context)
        personal = context.setdefault("personal", {})
        personal["insurance_cost_text"] = cost_info.get("text", "")
        personal["insurance_premium_amount"] = cost_info.get("amount", 0)
        personal["insurance_pct_of_income"] = cost_info.get("pct_of_income", 0)
        personal["insurance_affordability"] = cost_info.get("affordability_level", "unknown")
