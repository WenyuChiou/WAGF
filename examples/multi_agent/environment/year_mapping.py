from dataclasses import dataclass
from typing import List, Optional, Tuple


class YearMapping:
    """
    Maps simulation years to PRB data years.

    PRB data covers 2011-2023 (13 years). This class handles:
    - Converting simulation year (1, 2, 3...) to PRB year (2011, 2012...)
    - Cycling when simulation exceeds available data
    """
    start_sim_year: int = 1
    start_prb_year: int = 2011
    available_years: Optional[List[int]] = None

    def __post_init__(self):
        if self.available_years is None:
            self.available_years = list(range(2011, 2024))  # 13 years

    def sim_to_prb(self, sim_year: int) -> int:
        """
        Convert simulation year to PRB data year.

        Args:
            sim_year: Simulation year (1, 2, 3, ...)

        Returns:
            PRB data year (2011-2023, cycling if needed)
        """
        offset = sim_year - self.start_sim_year
        idx = offset % len(self.available_years)
        return self.available_years[idx]

    def get_prb_years_for_range(self, start: int, end: int) -> List[Tuple[int, int]]:
        """Get mapping of simulation years to PRB years for a range."""
        return [(y, self.sim_to_prb(y)) for y in range(start, end + 1)]
