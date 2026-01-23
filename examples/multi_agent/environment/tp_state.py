from dataclasses import dataclass


@dataclass
class TPState:
    """Threat perception state for a group or agent."""

    tp: float           # Current TP value [0, 1]
    pa: float           # Place attachment score [0, 1]
    sc: float           # Social capital score [0, 1]
    year: int           # Current simulation year
    is_mg: bool = False  # Whether this is a marginalized group

    def to_dict(self) -> dict:
        return {
            "tp": round(self.tp, 4),
            "pa": round(self.pa, 4),
            "sc": round(self.sc, 4),
            "year": self.year,
            "is_mg": self.is_mg,
        }


@dataclass
class TPUpdateResult:
    """Result of TP update calculation."""

    tp_new: float       # Updated TP value
    tp_old: float       # Previous TP value
    tau_t: float        # Current half-life
    mu_t: float         # Current decay coefficient
    damage_ratio: float  # Computed damage ratio
    damage_gate: bool   # Whether damage gate was triggered
    tp_decay: float     # TP lost to decay
    tp_gain: float      # TP gained from damage

    def to_dict(self) -> dict:
        return {
            "tp_new": round(self.tp_new, 4),
            "tp_old": round(self.tp_old, 4),
            "tau_t": round(self.tau_t, 4),
            "mu_t": round(self.mu_t, 4),
            "damage_ratio": round(self.damage_ratio, 4),
            "damage_gate": self.damage_gate,
            "tp_decay": round(self.tp_decay, 4),
            "tp_gain": round(self.tp_gain, 4),
        }
