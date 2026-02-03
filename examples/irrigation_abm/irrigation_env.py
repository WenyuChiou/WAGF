"""
Irrigation Environment — Water system simulation for Colorado River Basin.

Implements the TieredEnvironmentProtocol for the Hung & Yang (2021) RL-ABM
irrigation experiment.  Provides:

- Global water system state (total allocation, drought index)
- Basin-level state (Upper Basin precipitation, Lower Basin lake level)
- Agent-level water allocation and diversion history
- Preceding factor computation (binary signal from water level changes)
- Simplified Lake Mead mass balance coupling (demand → storage → elevation)

The environment uses a surrogate mass balance model for Lake Mead that
mirrors the core physics of CRSS/RiverWare at annual resolution:
    Storage(t+1) = Storage(t) + PowellRelease + Tributaries
                   − LB_diversions − Mexico − Evaporation − Municipal

This couples agent demand decisions back to reservoir elevation, creating
the feedback loop where collective over-extraction triggers shortage tiers
and curtailment.

References:
    Hung, F., & Yang, Y. C. E. (2021). WRR, 57, e2020WR029262.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Minimum utilisation floor: agents cannot reduce demand below this fraction
# of their water right.  Prevents "economic hallucination" spiral to zero.
MIN_UTIL = 0.10


@dataclass
class WaterSystemConfig:
    """Colorado River Basin water system parameters."""

    # Compact allocations (acre-ft/year)
    upper_basin_allocation: float = 7_500_000
    lower_basin_allocation: float = 7_500_000
    mexico_allocation: float = 1_500_000

    # Simulation timeline
    sim_start_year: int = 2019
    sim_end_year: int = 2060
    hist_start_year: int = 1971
    hist_end_year: int = 2018

    # Climate scenario: resampling windows for "drier-than-normal"
    dry_resample_windows: List[Tuple[int, int]] = field(
        default_factory=lambda: [(1988, 2015), (1934, 1947)]
    )

    # Lake Mead thresholds (feet above sea level)
    mead_normal: float = 1100.0
    mead_shortage_tier1: float = 1075.0
    mead_shortage_tier2: float = 1050.0
    mead_shortage_tier3: float = 1025.0

    # Lake Mead simplified mass balance coupling parameters
    # Storage(t+1) = Storage(t) + PowellRelease + LB_trib - LB_div - Mexico - Evap - Muni
    mead_initial_elevation: float = 1081.46   # Dec 2018 observed (ft)
    evaporation_maf: float = 0.8              # Reservoir evaporation at ref storage (MAF/yr)
    mexico_treaty_maf: float = 1.5            # Treaty delivery to Mexico (MAF/yr)
    lb_municipal_maf: float = 4.5             # LB non-ag: M&I + tribal + system losses (MAF/yr)
    lb_tributary_maf: float = 1.0             # LB tributary inflow (MAF/yr)
    natural_flow_base_maf: float = 12.0       # Natural flow at avg precip (MAF/yr)
    precip_baseline_mm: float = 100.0         # CRSS avg UB winter precip (mm)
    min_powell_release_maf: float = 7.0       # Min Powell release, USBR DCP floor (MAF/yr)

    # Number of Monte Carlo runs
    n_monte_carlo: int = 100

    # Random seed
    seed: int = 42


class IrrigationEnvironment:
    """Water system environment for irrigation ABM experiments.

    Provides a water availability model with simplified Lake Mead mass
    balance coupling that feeds agent demand decisions back to reservoir
    elevation.  This mirrors the core physics of CRSS/RiverWare at
    annual resolution without requiring the full RiverWare installation.

    Mass balance:
        UB_effective  = min(UB_diversions, NaturalFlow - MinPowellRelease)
        PowellRelease = NaturalFlow - UB_effective   (≥ MinPowellRelease)
        Storage(t+1)  = Storage(t) + PowellRelease + LB_trib
                        - LB_diversions - Mexico(DCP) - Evap(storage) - Municipal

    Powell minimum release (7.0 MAF) follows USBR DCP operating rules.
    Evaporation scales with reservoir surface area.  Mexico deliveries
    are reduced under Minute 323 DCP shortage tiers.

    Usage::

        config = WaterSystemConfig()
        env = IrrigationEnvironment(config)

        # Initialise with historical data or synthetic
        env.initialize_synthetic(n_agents=31)

        # Each simulation year:
        env.advance_year()
        context = env.get_agent_context("MohaveValleyIDD")
        # → dict with water signals for LLM prompt injection
    """

    # Lake Mead elevation–storage relationship (USBR data)
    _STORAGE_MAF = np.array(
        [2.0, 3.6, 5.8, 8.0, 9.5, 11.0, 13.0, 17.5, 23.3, 26.1]
    )
    _ELEVATION_FT = np.array(
        [895.0, 950.0, 1000.0, 1025.0, 1050.0, 1075.0, 1100.0, 1150.0, 1200.0, 1220.0]
    )

    def __init__(self, config: Optional[WaterSystemConfig] = None):
        self.config = config or WaterSystemConfig()
        self.rng = np.random.default_rng(self.config.seed)

        # Timeline
        self._current_year: int = self.config.sim_start_year
        self._year_index: int = 0

        # Global state
        self._global: Dict[str, Any] = {
            "year": self._current_year,
            "total_available_water": (
                self.config.upper_basin_allocation
                + self.config.lower_basin_allocation
            ),
            "drought_index": 0.0,
        }

        # Basin-level state
        self._basins: Dict[str, Dict[str, Any]] = {
            "upper_basin": {
                "allocation": self.config.upper_basin_allocation,
                "precipitation": 0.0,
                "preceding_factor": 0,
            },
            "lower_basin": {
                "allocation": self.config.lower_basin_allocation,
                "lake_mead_level": 1080.0,
                "preceding_factor": 0,
            },
        }

        # Agent-level state: agent_id → {diversion, request, water_right, basin}
        self._agents: Dict[str, Dict[str, Any]] = {}

        # History for preceding factor computation
        self._precip_history: List[float] = []
        self._mead_history: List[float] = [1081.46, 1082.52]  # 2017, 2018

        # Mass balance storage tracking (MAF)
        _init_elev = self.config.mead_initial_elevation
        _init_storage = float(np.interp(
            _init_elev, self._ELEVATION_FT, self._STORAGE_MAF
        ))
        self._mead_storage: List[float] = [_init_storage]

        # Real CRSS precipitation data (None = use synthetic)
        self._crss_precip: Optional[Any] = None  # pandas DataFrame when loaded

    # -----------------------------------------------------------------
    # Initialization
    # -----------------------------------------------------------------

    def initialize_from_csv(self, params_csv_path: str) -> None:
        """Load agent configuration from the calibrated parameters CSV.

        Args:
            params_csv_path: Path to ALL_colorado_ABM_params_cal_1108.csv
        """
        import pandas as pd

        df = pd.read_csv(params_csv_path, index_col=0)
        for agent_name in df.columns:
            self._agents[agent_name] = {
                "basin": "lower_basin" if not agent_name.startswith(
                    ("WY", "UT", "NM", "CO", "AZ_UB")
                ) else "upper_basin",
                "diversion": 0.0,
                "request": 0.0,
                "water_right": 100_000.0,  # Default; override from data
                "curtailment_ratio": 0.0,
                "at_allocation_cap": False,
                "has_efficient_system": False,
                "below_minimum_utilisation": False,
                "cluster": "unknown",
            }

    def initialize_from_profiles(self, profiles) -> None:
        """Initialise agents from IrrigationAgentProfile list.

        This is the production initialisation path that uses real data
        (water_right, basin, cluster) from the paper's calibrated files.

        Args:
            profiles: List of IrrigationAgentProfile objects created by
                ``create_profiles_from_data()`` or ``create_profiles_from_csv()``.
        """
        for p in profiles:
            wr = getattr(p, "water_right", 100_000.0)
            _actual = getattr(p, "actual_2018_diversion", None)
            _init_div = _actual if _actual is not None else wr * 0.8
            self._agents[p.agent_id] = {
                "basin": p.basin,
                "diversion": _init_div,
                "request": _init_div,
                "water_right": wr,
                "curtailment_ratio": 0.0,
                "at_allocation_cap": False,
                "has_efficient_system": getattr(p, "has_efficient_system", False),
                "below_minimum_utilisation": False,
                "cluster": p.cluster,
                "magnitude_default": getattr(p, "magnitude_default", 10),
            }

    def initialize_synthetic(
        self,
        n_agents: int = 31,
        basin_split: Tuple[int, int] = (9, 22),
        base_water_right: float = 100_000.0,
    ) -> None:
        """Create synthetic agents for testing.

        Args:
            n_agents: Total number of agents.
            basin_split: (n_upper, n_lower) agent counts.
            base_water_right: Default annual allocation per agent (acre-ft).
        """
        n_ub, n_lb = basin_split
        for i in range(n_ub):
            aid = f"UB_Agent_{i:03d}"
            self._agents[aid] = {
                "basin": "upper_basin",
                "diversion": base_water_right * 0.8,
                "request": base_water_right * 0.8,
                "water_right": base_water_right,
                "curtailment_ratio": 0.0,
                "at_allocation_cap": False,
                "has_efficient_system": False,
                "below_minimum_utilisation": False,
                "cluster": "unknown",
            }
        for i in range(n_lb):
            aid = f"LB_Agent_{i:03d}"
            self._agents[aid] = {
                "basin": "lower_basin",
                "diversion": base_water_right * 0.8,
                "request": base_water_right * 0.8,
                "water_right": base_water_right,
                "curtailment_ratio": 0.0,
                "at_allocation_cap": False,
                "has_efficient_system": False,
                "below_minimum_utilisation": False,
                "cluster": "unknown",
            }

    def load_crss_precipitation(self, csv_path: str) -> None:
        """Load real CRSS/PRISM winter precipitation projections.

        Loads the PrismWinterPrecip_ST_NOAA_Future.csv file which contains
        annual winter precipitation (inches) for 9 state-groups from
        2017-2060.  Values are converted to mm and stored for use by
        ``_generate_precipitation()``.

        Columns: WY, UT1, UT2, UT3, NM, CO1, CO2, CO3, AZ
        Upper Basin average: WY, UT1-3, CO1-3
        Lower Basin average: NM, AZ

        Args:
            csv_path: Path to PrismWinterPrecip_ST_NOAA_Future.csv
        """
        import pandas as pd

        df = pd.read_csv(csv_path, index_col=0)
        # Convert inches to mm (1 inch = 25.4 mm)
        self._crss_precip = df * 25.4

    # -----------------------------------------------------------------
    # TieredEnvironmentProtocol interface
    # -----------------------------------------------------------------

    @property
    def global_state(self) -> Dict[str, Any]:
        return self._global.copy()

    @property
    def local_states(self) -> Dict[str, Dict[str, Any]]:
        return {k: v.copy() for k, v in self._basins.items()}

    @property
    def institutions(self) -> Dict[str, Dict[str, Any]]:
        return {
            "colorado_compact": {
                "upper_allocation": self.config.upper_basin_allocation,
                "lower_allocation": self.config.lower_basin_allocation,
                "shortage_tier": self._compute_shortage_tier(),
            }
        }

    @property
    def social_states(self) -> Dict[str, Dict[str, Any]]:
        return {}  # Irrigation agents don't have social state in this model

    def get_observable(self, path: str, default: Any = None) -> Any:
        """Safe dot-notation access to environment state."""
        parts = path.split(".")
        if not parts:
            return default

        if parts[0] == "global":
            return self._global.get(parts[1], default) if len(parts) > 1 else default
        if parts[0] == "local" and len(parts) > 1:
            basin = self._basins.get(parts[1], {})
            return basin.get(parts[2], default) if len(parts) > 2 else basin or default
        if parts[0] == "agent" and len(parts) > 1:
            agent = self._agents.get(parts[1], {})
            return agent.get(parts[2], default) if len(parts) > 2 else agent or default

        return default

    def set_global(self, key: str, value: Any) -> None:
        self._global[key] = value

    def set_local(self, location_id: str, key: str, value: Any) -> None:
        if location_id in self._basins:
            self._basins[location_id][key] = value

    def get_local(self, location_id: str, key: str, default: Any = None) -> Any:
        return self._basins.get(location_id, {}).get(key, default)

    def set_social(self, agent_id: str, key: str, value: Any) -> None:
        pass  # No social state in current model

    def to_dict(self) -> Dict[str, Any]:
        return {
            "global": self._global.copy(),
            "basins": {k: v.copy() for k, v in self._basins.items()},
            "institutions": self.institutions,
            "n_agents": len(self._agents),
            "year": self._current_year,
        }

    # -----------------------------------------------------------------
    # Simulation control
    # -----------------------------------------------------------------

    def advance_year(self) -> Dict[str, Any]:
        """Advance to next simulation year and generate water signals.

        Returns:
            Updated global state dict.
        """
        self._year_index += 1
        self._current_year = self.config.sim_start_year + self._year_index
        self._global["year"] = self._current_year

        # Generate stochastic water signals
        precip = self._generate_precipitation()
        mead_level = self._generate_lake_mead_level()

        # Update basin states
        self._basins["upper_basin"]["precipitation"] = precip
        self._basins["lower_basin"]["lake_mead_level"] = mead_level

        # Compute preceding factors
        self._update_preceding_factors(precip, mead_level)

        # Compute drought index (0 = no drought, 1 = severe)
        self._global["drought_index"] = self._compute_drought_index(precip, mead_level)

        # Compute total available water with some variability
        base = self.config.upper_basin_allocation + self.config.lower_basin_allocation
        variability = 1.0 - self._global["drought_index"] * 0.3
        self._global["total_available_water"] = base * variability

        # Apply curtailment to agents based on shortage tier
        self._apply_curtailment()

        # Enforce Powell minimum release: pro-rata reduce UB diversions
        # when aggregate UB demand exceeds available supply
        self._apply_powell_constraint()

        return self._global.copy()

    def get_agent_context(self, agent_id: str) -> Dict[str, Any]:
        """Build context dict for a specific agent's LLM prompt.

        Returns:
            Dictionary with all water signals and agent state suitable
            for prompt template injection.
        """
        agent = self._agents.get(agent_id, {})
        basin_key = agent.get("basin", "lower_basin")
        basin = self._basins.get(basin_key, {})

        return {
            # Agent state
            "agent_id": agent_id,
            "basin": basin_key,
            "current_diversion": agent.get("diversion", 0),
            "current_request": agent.get("request", 0),
            "water_right": agent.get("water_right", 0),
            "curtailment_ratio": agent.get("curtailment_ratio", 0),
            "at_allocation_cap": agent.get("at_allocation_cap", False),
            "has_efficient_system": agent.get("has_efficient_system", False),
            "below_minimum_utilisation": agent.get("below_minimum_utilisation", False),
            "cluster": agent.get("cluster", "unknown"),
            # Basin signals
            "precipitation": basin.get("precipitation", 0),
            "lake_mead_level": basin.get("lake_mead_level", 0),
            "preceding_factor": basin.get("preceding_factor", 0),
            # Global signals
            "year": self._current_year,
            "drought_index": self._global.get("drought_index", 0),
            "total_available_water": self._global.get("total_available_water", 0),
            "shortage_tier": self._compute_shortage_tier(),
        }

    def update_agent_request(
        self,
        agent_id: str,
        new_request: float,
    ) -> None:
        """Apply agent's decision (new diversion request).

        The environment computes the actual diversion received based on
        water availability and compact rules.
        """
        if agent_id not in self._agents:
            return

        agent = self._agents[agent_id]
        # Cap at water right
        new_request = max(0.0, min(new_request, agent["water_right"]))
        agent["request"] = new_request
        agent["at_allocation_cap"] = new_request >= agent["water_right"] * 0.99
        agent["below_minimum_utilisation"] = (
            new_request < agent["water_right"] * MIN_UTIL
        )

        # Actual diversion = request * (1 - curtailment_ratio)
        curtailment = agent.get("curtailment_ratio", 0.0)
        agent["diversion"] = new_request * (1.0 - curtailment)

    def execute_skill(self, approved_skill) -> "ExecutionResult":
        """Execute an approved irrigation skill.

        This satisfies the ``sim_engine.execute_skill()`` interface expected
        by ``ExperimentRunner`` for the broker pipeline.

        Args:
            approved_skill: An ``ApprovedSkill`` instance with
                ``.skill_name``, ``.agent_id``, and ``.parameters``.

        Returns:
            ExecutionResult with success status and state changes.
        """
        from broker.interfaces.skill_types import ExecutionResult

        aid = approved_skill.agent_id
        skill = approved_skill.skill_name
        agent = self._agents.get(aid)
        if agent is None:
            return ExecutionResult(success=False, error=f"Unknown agent: {aid}")

        wr = agent["water_right"]
        current = agent["request"]
        meta = getattr(approved_skill, "parameters", {}) or {}
        # Magnitude: LLM output → persona default → hardcoded 10
        magnitude_pct = meta.get("magnitude_pct")
        if magnitude_pct is None or not isinstance(magnitude_pct, (int, float)):
            magnitude_pct = agent.get("magnitude_default", 10) or 10
        change = wr * (magnitude_pct / 100.0)

        state_changes: Dict[str, Any] = {}

        if skill == "increase_demand":
            new_req = min(current + change, wr)
            self.update_agent_request(aid, new_req)
            state_changes["request"] = new_req

        elif skill == "decrease_demand":
            floor = wr * MIN_UTIL
            utilisation = current / wr if wr > 0 else 1.0
            # P1: diminishing returns as utilisation approaches floor
            taper = max(0.0, (utilisation - MIN_UTIL) / (1.0 - MIN_UTIL))
            new_req = max(current - change * taper, floor)
            self.update_agent_request(aid, new_req)
            state_changes["request"] = new_req

        elif skill == "adopt_efficiency":
            if agent.get("has_efficient_system"):
                return ExecutionResult(
                    success=False, error="Already using efficient system."
                )
            agent["has_efficient_system"] = True
            new_req = max(current * 0.80, wr * MIN_UTIL)
            self.update_agent_request(aid, new_req)
            state_changes["has_efficient_system"] = True
            state_changes["request"] = new_req

        elif skill == "reduce_acreage":
            floor = wr * MIN_UTIL
            utilisation = current / wr if wr > 0 else 1.0
            # P1: diminishing returns — taper toward no-op near floor
            taper = max(0.0, (utilisation - MIN_UTIL) / (1.0 - MIN_UTIL))
            effective_ratio = 1.0 - (0.25 * taper)  # 0.75 at full, 1.0 at floor
            new_req = max(current * effective_ratio, floor)
            self.update_agent_request(aid, new_req)
            state_changes["request"] = new_req

        elif skill == "maintain_demand":
            # No change — re-confirm existing request
            self.update_agent_request(aid, current)
            state_changes["request"] = current

        else:
            return ExecutionResult(
                success=False, error=f"Unknown skill: {skill}"
            )

        return ExecutionResult(success=True, state_changes=state_changes)

    # -----------------------------------------------------------------
    # Internal: water signal generation
    # -----------------------------------------------------------------

    def _generate_precipitation(self) -> float:
        """Generate annual winter precipitation (mm).

        When real CRSS data is loaded, returns the Upper Basin average
        (WY, UT1-3, CO1-3) for the current simulation year.  Falls back
        to synthetic drying trend when no real data is available.
        """
        if self._crss_precip is not None:
            ub_cols = ["WY", "UT1", "UT2", "UT3", "CO1", "CO2", "CO3"]
            if self._current_year in self._crss_precip.index:
                precip = float(self._crss_precip.loc[self._current_year, ub_cols].mean())
                self._precip_history.append(precip)
                return precip

        # Synthetic fallback: drying trend matching CRSS winter precip range
        base = self.config.precip_baseline_mm
        trend = -0.2 * self._year_index  # Gradual drying
        noise = self.rng.normal(0, 12)
        precip = max(20.0, base + trend + noise)
        self._precip_history.append(precip)
        return precip

    def _storage_to_elevation(self, storage_maf: float) -> float:
        """Convert Lake Mead storage (MAF) to elevation (ft) via USBR curve."""
        return float(np.interp(storage_maf, self._STORAGE_MAF, self._ELEVATION_FT))

    def _elevation_to_storage(self, elevation_ft: float) -> float:
        """Convert Lake Mead elevation (ft) to storage (MAF) via USBR curve."""
        return float(np.interp(elevation_ft, self._ELEVATION_FT, self._STORAGE_MAF))

    def _generate_lake_mead_level(self) -> float:
        """Generate Lake Mead level via simplified mass balance.

        Couples agent demand back to reservoir elevation, mirroring the
        core physics of CRSS/RiverWare at annual resolution:

            UB_effective  = min(UB_diversions, NaturalFlow − MinPowellRelease)
            PowellRelease = NaturalFlow − UB_effective   (≥ MinPowellRelease)
            Mead_inflow   = PowellRelease + LB_tributaries
            Mead_outflow  = LB_diversions + Mexico(DCP) + Evap(storage) + Municipal
            Storage(t+1)  = Storage(t) + Mead_inflow − Mead_outflow

        Powell minimum release follows USBR DCP operating rules (7.0 MAF
        floor).  Evaporation scales with reservoir surface area (storage
        proxy).  Mexico deliveries are reduced under Minute 323 DCP tiers.

        Agent diversions are from the *previous* year's decisions, which
        is physically correct (withdrawals during year t determine storage
        at the start of year t+1).
        """
        cfg = self.config

        # --- Inflow: natural flow scaled by precipitation ---
        precip = self._precip_history[-1] if self._precip_history else cfg.precip_baseline_mm
        natural_flow = cfg.natural_flow_base_maf * (precip / cfg.precip_baseline_mm)
        natural_flow = max(6.0, min(20.0, natural_flow))

        # --- Upper Basin diversions (constrained by Powell min release) ---
        ub_div_maf = sum(
            a["diversion"] for a in self._agents.values()
            if a["basin"] == "upper_basin"
        ) / 1e6
        ub_available = max(0.0, natural_flow - cfg.min_powell_release_maf)
        ub_div_effective = min(ub_div_maf, ub_available)
        powell_release = natural_flow - ub_div_effective
        mead_inflow = powell_release + cfg.lb_tributary_maf

        # --- Lake Mead outflow ---
        lb_div_maf = sum(
            a["diversion"] for a in self._agents.values()
            if a["basin"] == "lower_basin"
        ) / 1e6
        prev_storage = self._mead_storage[-1]

        # Evaporation scales with surface area (storage fraction proxy)
        storage_frac = prev_storage / 13.0  # 13 MAF ≈ 1100 ft reference
        evap_actual = cfg.evaporation_maf * max(0.15, min(1.5, storage_frac))

        # Mexico DCP reductions (Minute 323 tiered reductions)
        prev_elev = self._storage_to_elevation(prev_storage)
        if prev_elev < 1025:
            mexico = cfg.mexico_treaty_maf - 0.275
        elif prev_elev < 1050:
            mexico = cfg.mexico_treaty_maf - 0.104
        elif prev_elev < 1075:
            mexico = cfg.mexico_treaty_maf - 0.080
        elif prev_elev < 1090:
            mexico = cfg.mexico_treaty_maf - 0.041
        else:
            mexico = cfg.mexico_treaty_maf

        mead_outflow = lb_div_maf + mexico + evap_actual + cfg.lb_municipal_maf

        # --- Mass balance ---
        new_storage = prev_storage + mead_inflow - mead_outflow
        new_storage = max(2.0, min(26.1, new_storage))  # Dead pool to full pool
        self._mead_storage.append(new_storage)

        # --- Convert to elevation ---
        level = self._storage_to_elevation(new_storage)
        self._mead_history.append(level)
        return level

    def _update_preceding_factors(self, precip: float, mead_level: float) -> None:
        """Compute binary preceding factors from signal changes.

        UB preceding factor: 1 if precipitation increased, 0 otherwise
        LB preceding factor: 1 if Lake Mead level increased, 0 otherwise
        """
        # Upper Basin: precipitation change
        if len(self._precip_history) >= 2:
            ub_pf = int(self._precip_history[-1] >= self._precip_history[-2])
        else:
            ub_pf = 0
        self._basins["upper_basin"]["preceding_factor"] = ub_pf

        # Lower Basin: Lake Mead level change
        if len(self._mead_history) >= 2:
            lb_pf = int(self._mead_history[-1] >= self._mead_history[-2])
        else:
            lb_pf = 0
        self._basins["lower_basin"]["preceding_factor"] = lb_pf

    def _compute_drought_index(self, precip: float, mead_level: float) -> float:
        """Compute composite drought severity index [0, 1]."""
        # Precipitation component (lower = more drought)
        # Divisor = 2× baseline so average precip → 0.5 (moderate)
        precip_ref = 2.0 * self.config.precip_baseline_mm
        precip_norm = max(0.0, min(1.0, 1.0 - precip / precip_ref))

        # Lake Mead component (lower level = more drought)
        mead_norm = max(0.0, min(1.0, 1.0 - (mead_level - 900) / 320.0))

        return 0.5 * precip_norm + 0.5 * mead_norm

    def _compute_shortage_tier(self) -> int:
        """Compute Bureau of Reclamation shortage tier from Lake Mead level.

        Returns:
            0 = Normal, 1 = Tier 1, 2 = Tier 2, 3 = Tier 3 (most severe).
        """
        mead = self._basins["lower_basin"].get("lake_mead_level", 1100)
        cfg = self.config
        if mead >= cfg.mead_shortage_tier1:
            return 0
        elif mead >= cfg.mead_shortage_tier2:
            return 1
        elif mead >= cfg.mead_shortage_tier3:
            return 2
        else:
            return 3

    def _apply_curtailment(self) -> None:
        """Apply water curtailment to agents based on shortage tier."""
        tier = self._compute_shortage_tier()
        # Curtailment ratios by tier (from Colorado River Interim Guidelines)
        curtailment_map = {0: 0.0, 1: 0.05, 2: 0.10, 3: 0.20}
        ratio = curtailment_map.get(tier, 0.0)

        for agent in self._agents.values():
            agent["curtailment_ratio"] = ratio
            # Update actual diversion
            agent["diversion"] = agent["request"] * (1.0 - ratio)

    def _apply_powell_constraint(self) -> None:
        """Reduce UB diversions when they exceed Powell release capacity.

        USBR operating rules require a minimum annual release from Glen
        Canyon Dam (Powell) to Lake Mead.  When Upper Basin diversions
        would reduce Powell release below this floor, UB agent diversions
        are pro-rata scaled down so that the physical flow constraint is
        satisfied.  This provides feedback to UB agents: their reported
        diversion is lower than requested, signalling supply scarcity.
        """
        cfg = self.config
        precip = (self._precip_history[-1]
                  if self._precip_history else cfg.precip_baseline_mm)
        natural_flow = cfg.natural_flow_base_maf * (precip / cfg.precip_baseline_mm)
        natural_flow = max(6.0, min(20.0, natural_flow))

        ub_agents = [a for a in self._agents.values()
                     if a["basin"] == "upper_basin"]
        ub_div_total = sum(a["diversion"] for a in ub_agents)
        ub_available_af = max(0.0, natural_flow - cfg.min_powell_release_maf) * 1e6

        if ub_div_total > ub_available_af and ub_div_total > 0:
            scale = ub_available_af / ub_div_total
            for a in ub_agents:
                a["diversion"] *= scale

    # -----------------------------------------------------------------
    # Utility
    # -----------------------------------------------------------------

    @property
    def current_year(self) -> int:
        return self._current_year

    @property
    def agent_ids(self) -> List[str]:
        return list(self._agents.keys())

    def get_agent_state(self, agent_id: str) -> Dict[str, Any]:
        return self._agents.get(agent_id, {}).copy()
