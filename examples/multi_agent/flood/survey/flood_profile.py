
from dataclasses import dataclass


@dataclass
class FloodExposureProfile:
    """MA-specific flood exposure data."""
    flood_zone: str
    base_depth_m: float
    flood_probability: float
    building_rcv_usd: float
    contents_rcv_usd: float
    flood_experience: bool
    financial_loss: bool

    def experience_summary(self) -> str:
        if not self.flood_experience:
            return "No direct flood experience"
        if self.financial_loss:
            return "Experienced flooding with financial loss"
        return "Experienced flooding without major financial loss"
