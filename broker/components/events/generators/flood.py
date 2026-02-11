"""
Flood Event Generator - Domain-specific implementation.

Supports three modes:
- probabilistic: Random flood with given probability
- fixed: Flood occurs in specific years
- historical: Use historical intensity data
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import random

from broker.interfaces.event_generator import (
    EnvironmentEvent,
    EventSeverity,
    EventScope,
)


@dataclass
class FloodConfig:
    """Configuration for flood event generation.

    Args:
        mode: Generation mode - "probabilistic", "fixed", or "historical"
        probability: Flood probability per year (for probabilistic mode)
        fixed_years: List of years when floods occur (for fixed mode)
        historical_data: Dict mapping year to intensity (for historical mode)
        intensity_range: Min/max intensity for random generation
    """
    mode: str = "probabilistic"  # "probabilistic", "fixed", "historical"
    probability: float = 0.2     # For probabilistic mode
    fixed_years: List[int] = None  # For fixed mode
    historical_data: Dict[int, float] = None  # For historical mode
    intensity_range: Tuple[float, float] = (0.3, 1.0)  # Min/max intensity

    def __post_init__(self):
        self.fixed_years = self.fixed_years or []
        self.historical_data = self.historical_data or {}


class FloodEventGenerator:
    """Generates flood events based on configuration.

    Usage:
        # Probabilistic mode (default)
        generator = FloodEventGenerator()
        events = generator.generate(year=1)

        # Fixed years mode
        config = FloodConfig(mode="fixed", fixed_years=[3, 5, 8])
        generator = FloodEventGenerator(config)

        # Historical mode
        config = FloodConfig(mode="historical", historical_data={1: 0.6, 3: 0.8})
        generator = FloodEventGenerator(config)
    """

    def __init__(self, config: FloodConfig = None):
        self._config = config or FloodConfig()
        self._update_frequency = "per_year"

    @property
    def domain(self) -> str:
        """Domain identifier."""
        return "flood"

    @property
    def update_frequency(self) -> str:
        """Update frequency."""
        return self._update_frequency

    def configure(self, **kwargs) -> None:
        """Configure generator parameters.

        Args:
            mode: Generation mode
            probability: Flood probability
            fixed_years: List of flood years
            update_frequency: When to generate
        """
        if "mode" in kwargs:
            self._config.mode = kwargs["mode"]
        if "probability" in kwargs:
            self._config.probability = kwargs["probability"]
        if "fixed_years" in kwargs:
            self._config.fixed_years = kwargs["fixed_years"]
        if "historical_data" in kwargs:
            self._config.historical_data = kwargs["historical_data"]
        if "update_frequency" in kwargs:
            self._update_frequency = kwargs["update_frequency"]

    def generate(
        self,
        year: int,
        step: int = 0,
        context: Dict[str, Any] = None
    ) -> List[EnvironmentEvent]:
        """Generate flood events for current year.

        Args:
            year: Simulation year
            step: Step within year (unused for per_year)
            context: Optional global context

        Returns:
            List containing flood or no_flood event
        """
        events = []

        flood_occurred, intensity = self._determine_flood(year)

        if flood_occurred:
            severity = self._intensity_to_severity(intensity)
            events.append(EnvironmentEvent(
                event_type="flood",
                severity=severity,
                scope=EventScope.GLOBAL,
                description=self._get_description(severity),
                data={
                    "intensity": intensity,
                    "year": year,
                    "occurred": True,
                },
                domain="flood",
            ))
        else:
            events.append(EnvironmentEvent(
                event_type="no_flood",
                severity=EventSeverity.INFO,
                scope=EventScope.GLOBAL,
                description="No flood occurred this year.",
                data={"intensity": 0.0, "year": year, "occurred": False},
                domain="flood",
            ))

        return events

    def _determine_flood(self, year: int) -> Tuple[bool, float]:
        """Determine if flood occurs and its intensity.

        Args:
            year: Simulation year

        Returns:
            Tuple of (occurred, intensity)
        """
        min_int, max_int = self._config.intensity_range

        if self._config.mode == "fixed":
            if year in self._config.fixed_years:
                return True, random.uniform(min_int, max_int)
            return False, 0.0

        elif self._config.mode == "historical":
            intensity = self._config.historical_data.get(year, 0.0)
            return intensity > 0, intensity

        else:  # probabilistic
            if random.random() < self._config.probability:
                return True, random.uniform(min_int, max_int)
            return False, 0.0

    def _intensity_to_severity(self, intensity: float) -> EventSeverity:
        """Convert intensity to severity level.

        Args:
            intensity: Flood intensity (0-1)

        Returns:
            EventSeverity corresponding to intensity
        """
        if intensity >= 0.8:
            return EventSeverity.CRITICAL
        elif intensity >= 0.6:
            return EventSeverity.SEVERE
        elif intensity >= 0.4:
            return EventSeverity.MODERATE
        else:
            return EventSeverity.MINOR

    def _get_description(self, severity: EventSeverity) -> str:
        """Get human-readable description for severity.

        Args:
            severity: Event severity

        Returns:
            Description string
        """
        descriptions = {
            EventSeverity.CRITICAL: "Catastrophic flooding with extreme damage potential.",
            EventSeverity.SEVERE: "Severe flooding causing significant damage.",
            EventSeverity.MODERATE: "Moderate flooding with localized damage.",
            EventSeverity.MINOR: "Minor flooding with minimal impact.",
        }
        return descriptions.get(severity, "Flood event occurred.")

    @property
    def config(self) -> FloodConfig:
        """Current configuration."""
        return self._config


__all__ = ["FloodEventGenerator", "FloodConfig"]
