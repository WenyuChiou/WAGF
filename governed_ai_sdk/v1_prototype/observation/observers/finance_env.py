"""Finance domain environment observer."""
from typing import Any, Dict, List
from ..environment import EnvironmentObserver


class FinanceEnvironmentObserver(EnvironmentObserver):
    """
    Environment observer for financial psychology domain.

    Agents can sense:
    - Market conditions (interest rates, inflation)
    - Economic indicators (unemployment, GDP)
    - Local economic events (layoffs, business closures)
    """

    @property
    def domain(self) -> str:
        return "finance"

    def sense_state(
        self,
        agent: Any,
        environment: Any
    ) -> Dict[str, Any]:
        """Sense finance-relevant environment state."""
        sensed = {}

        # Interest rates
        if hasattr(environment, "interest_rate"):
            sensed["interest_rate"] = environment.interest_rate

        # Inflation rate
        if hasattr(environment, "inflation_rate"):
            sensed["inflation_rate"] = environment.inflation_rate

        # Unemployment rate (local or regional)
        if hasattr(environment, "get_unemployment_rate"):
            location = getattr(agent, "location", None)
            sensed["unemployment_rate"] = environment.get_unemployment_rate(location)
        elif hasattr(environment, "unemployment_rate"):
            sensed["unemployment_rate"] = environment.unemployment_rate

        # Stock market index
        if hasattr(environment, "market_index"):
            sensed["market_index"] = environment.market_index

        # Housing market
        if hasattr(environment, "housing_price_index"):
            sensed["housing_price_index"] = environment.housing_price_index

        # Current economic phase
        if hasattr(environment, "economic_phase"):
            sensed["economic_phase"] = environment.economic_phase

        return sensed

    def detect_events(
        self,
        agent: Any,
        environment: Any
    ) -> List[Dict[str, Any]]:
        """Detect finance-related events."""
        events = []

        # Market crash
        if hasattr(environment, "market_crash") and environment.market_crash:
            events.append({
                "event_type": "market_crash",
                "description": "Significant market downturn detected",
                "severity": "high",
            })

        # Recession
        if hasattr(environment, "in_recession") and environment.in_recession:
            events.append({
                "event_type": "recession",
                "description": "Economy is in recession",
                "severity": "high",
            })

        # Interest rate change
        if hasattr(environment, "rate_changed") and environment.rate_changed:
            direction = "increased" if environment.rate_change_direction > 0 else "decreased"
            events.append({
                "event_type": "rate_change",
                "description": f"Interest rates {direction}",
                "severity": "moderate",
            })

        # Local layoffs
        if hasattr(environment, "major_layoffs") and environment.major_layoffs:
            events.append({
                "event_type": "layoffs",
                "description": "Major employer announced layoffs",
                "severity": "high",
            })

        return events

    def get_observation_accuracy(
        self,
        agent: Any,
        variable: str
    ) -> float:
        """
        Get accuracy based on financial literacy.

        More financially literate agents understand market signals better.
        """
        base_accuracy = 0.7

        # Better accuracy if agent has high financial literacy
        if getattr(agent, "financial_literacy", 0) > 0.7:
            base_accuracy += 0.2

        # Better accuracy if agent is employed in finance
        if getattr(agent, "occupation", "") in ["finance", "banking", "investment"]:
            base_accuracy += 0.1

        return min(base_accuracy, 1.0)
