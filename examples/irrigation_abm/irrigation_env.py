"""
Irrigation Environment: water system simulation for the Colorado River Basin.

Implements the TieredEnvironmentProtocol for the Hung & Yang (2021) RL-ABM
irrigation experiment.  Provides:

- Global water system state (total allocation, drought index)
- Basin-level state (Upper Basin precipitation, Lower Basin lake level)
- Agent-level water requests and deliveries
- Preceding factor computation (binary signal from water level changes)
- A two-reservoir annual water balance (Lake Powell, Lake Mead) that
  limits deliveries on the SUPPLY side: what an agent receives is what the
  reservoirs can physically deliver, shared pro-rata, never more.

Annual balance (MAF/yr; see ``IrrigationEnvironment._settle`` and
docs/irrigation_physics.md)::

    Powell:  S_P' = S_P + (NF - UB_delivered) - Evap_P - Release
    Mead:    S_M' = S_M + Release + LB_trib - Evap_M - LB_withdrawals

Upper Basin deliveries are limited by the 5.0 MAF delivery capacity and by
what Powell needs to make its 7.0 MAF minimum release; Lower Basin
withdrawals are cut by the declared shortage tier and, when Mead cannot
supply them, scaled down pro-rata to what is physically available above the
dead pool. Hung and Yang (2021) take the delivered diversion from CRSS in
the same way: the basin total is limited by the water system, not by a
demand-side rule.

References:
    Hung, F., & Yang, Y. C. E. (2021). WRR, 57, e2020WR029262.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Minimum utilisation floor: agents cannot reduce demand below this fraction
# of their water right.  Prevents "economic hallucination" spiral to zero.
MIN_UTIL = 0.10

# CRSS 2019-2060 aggregate agricultural demand target for the 78 agents
# (5.86 MAF/yr; see initialize_synthetic's calibration note). Used only as
# the denominator of the logged basin_request_over_target ratio.
CRSS_DEMAND_TARGET_AF = 5_860_000.0


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
    # Reverted to v12 values: Stage 3 analysis showed shifting tiers down doubled
    # Tier 2 hard-block frequency (2.4%→4.8%) and collapsed Tier 1 warnings by 86%.
    mead_normal: float = 1100.0
    mead_shortage_tier1: float = 1075.0  # Tier 0→1 warning threshold
    mead_shortage_tier2: float = 1050.0  # Tier 1→2 hard-block threshold
    mead_shortage_tier3: float = 1025.0  # Tier 2→3 severe-block threshold

    # Lake Mead simplified mass balance coupling parameters
    # Storage(t+1) = Storage(t) + PowellRelease + LB_trib - LB_withdrawals - Evap
    mead_initial_elevation: float = 1081.46   # Dec 2018 observed (ft)
    evaporation_maf: float = 0.8              # Reservoir evaporation at ref storage (MAF/yr)
    mexico_treaty_maf: float = 1.5            # Treaty delivery to Mexico (MAF/yr)
    lb_non_ag_total_maf: float = 5.0           # LB non-ag: M&I + tribal + CAP + system losses (MAF/yr)
    lb_tributary_maf: float = 1.0             # LB tributary inflow (MAF/yr)
    natural_flow_base_maf: float = 12.0       # Natural flow at avg precip (MAF/yr)
    precip_baseline_mm: float = 100.0         # CRSS avg UB winter precip (mm)
    min_powell_release_maf: float = 7.0       # Min Powell release, USBR DCP floor (MAF/yr)
    ub_infrastructure_cap_maf: float = 5.0   # UB infrastructure-limited ceiling (MAF/yr)
    # Lake Mead physical bounds (total storage, MAF), the end points of the
    # USBR storage-elevation curve in IrrigationEnvironment._STORAGE_MAF.
    # Water below the dead pool cannot be released; deliveries are limited
    # to storage above it plus the year's inflow.
    mead_dead_pool_maf: float = 2.0           # 895 ft
    mead_capacity_maf: float = 26.1           # 1,220 ft
    # The former +/-3.5 MAF annual storage-change clamp on Mead
    # ("mead_max_storage_delta_maf", a proxy for Glen Canyon buffering) is
    # RETIRED: Lake Powell storage below now does the buffering, and the
    # clamp broke mass conservation (water was created or destroyed
    # whenever it bound).

    # Lake Powell storage buffer (total storage, MAF). Sources:
    #   * powell_capacity_maf: total storage at full pool (3,700 ft) in the
    #     1986 area-capacity table USBR operations used through 2019. USGS
    #     (2022, "Lake Powell's storage capacity updated for first time since
    #     1986"; SIR on the 2018 survey) gives 25.160 MAF for 2018 and a
    #     1.048 MAF loss since 1986, so 1986 = 26.21 MAF.
    #   * powell_dead_pool_maf: storage below the 3,370 ft dead pool (river
    #     outlet works), 26.21 MAF total minus 24.322 MAF live capacity (USBR
    #     Glen Canyon Dam data, 1986 table) = 1.89 MAF ("about 1.9 MAF").
    #   * powell_initial_storage_maf: live storage at the end of December
    #     2018 = 10,099 thousand acre-ft at 3,581.85 ft (USBR Lower Colorado
    #     Region, January 2019 24-Month Study, Most Probable, Lake Powell
    #     table), plus the 1.89 MAF dead storage = 11.99 MAF total.
    #   * powell_evaporation_maf: evaporation at full pool. The same 24-Month
    #     Study reports 386 thousand acre-ft of Lake Powell evaporation in
    #     water year 2018, when live storage averaged about 12.5 MAF (14.4 MAF
    #     total, 0.55 of capacity), so 0.386 / 0.55 = 0.70 MAF at full pool.
    #     Scaled by the storage fraction (a surface-area proxy), floored at
    #     evap_min_frac, the same shape as the Mead evaporation term.
    powell_capacity_maf: float = 26.21
    powell_dead_pool_maf: float = 1.89
    powell_initial_storage_maf: float = 11.99
    powell_evaporation_maf: float = 0.70
    evap_min_frac: float = 0.15               # on [0, 1]; same floor as Mead's evaporation term

    def __post_init__(self) -> None:
        if not 0.0 <= self.evap_min_frac <= 1.0:
            raise ValueError(f"evap_min_frac must be on [0, 1], got {self.evap_min_frac}")
        if not (0.0 <= self.powell_dead_pool_maf < self.powell_initial_storage_maf
                <= self.powell_capacity_maf):
            raise ValueError(
                "Powell storages must satisfy 0 <= dead pool < initial storage <= capacity, got "
                f"{self.powell_dead_pool_maf} / {self.powell_initial_storage_maf} / "
                f"{self.powell_capacity_maf}"
            )
        if not 0.0 <= self.mead_dead_pool_maf < self.mead_capacity_maf:
            raise ValueError("Mead dead pool must be below capacity")

    # Number of Monte Carlo runs
    n_monte_carlo: int = 100

    # Random seed
    seed: int = 42


class IrrigationEnvironment:
    """Water system environment for irrigation ABM experiments.

    Annual two-reservoir balance at the resolution of Hung and Yang (2021):
    Lake Powell is a storage stock with a minimum release, Lake Mead a
    storage stock whose withdrawals cannot exceed the water above its dead
    pool plus the year's inflow. It is a storage buffer with a minimum
    release, NOT the full operating rules: the 2007 Interim Guidelines'
    Powell release tiers (equalization, balancing, 7.48 / 8.23 MAF) and the
    Lake Mead protection levels are deliberately not modelled.

    Timing (one loop year, decisions at the start of the year)::

        advance_year()  commit last year's settlement (end storages become
                        this year's 1 January storages), draw precipitation,
                        declare the Lower Basin shortage tier from the
                        1 January Mead level, run a PROVISIONAL settlement at
                        the carried requests (what agents see as expected
                        delivery), freeze the 1 January snapshot.
        decisions       execute_skill -> update_agent_request
        settle_year()   FINAL settlement at this year's requests, rebuilt
                        from the frozen snapshot (idempotent); storage is
                        committed only by the next advance_year().

    Constraints: Powell minimum release 7.0 MAF, UB delivery capacity
    5.0 MAF, NF clamped [6, 17] MAF, dead pools and full pools at both
    reservoirs. Evaporation scales with storage; Mexico follows Minute 323.

    Usage::

        config = WaterSystemConfig()
        env = IrrigationEnvironment(config)

        # Initialise with historical data or synthetic
        env.initialize_synthetic(n_agents=31)

        # Each simulation year:
        env.advance_year()
        context = env.get_agent_context("MohaveValleyIDD")
        # → dict with water signals for LLM prompt injection
        # ... agents decide (execute_skill) ...
        env.settle_year()
    """

    # Lake Mead elevation–storage relationship (USBR data)
    _STORAGE_MAF = np.array(
        [2.0, 3.6, 5.8, 8.0, 9.5, 11.0, 13.0, 17.5, 23.3, 26.1]
    )
    _ELEVATION_FT = np.array(
        [895.0, 950.0, 1000.0, 1025.0, 1050.0, 1075.0, 1100.0, 1150.0, 1200.0, 1220.0]
    )

    def __init__(
        self,
        config: Optional[WaterSystemConfig] = None,
        *,
        coupling_contract_active: bool = False,
    ):
        self.config = config or WaterSystemConfig()
        # ENV-LEVEL generator — MAIN THREAD ONLY.
        #
        # Everything that draws from this one runs on the main thread:
        # `initialize_synthetic`'s cluster shuffle (setup) and
        # `_generate_precipitation`'s noise (called from `advance_year`,
        # once per year, before any agent decides).  The per-agent DECISION
        # phase must NOT touch it — `ExperimentRunner._run_agents_parallel`
        # runs that phase in a ThreadPoolExecutor under `--workers N`, and a
        # shared stream there hands out draws in thread-completion order.
        # Decision-phase draws go through `_decision_rng()` instead.
        self.rng = np.random.default_rng(self.config.seed)

        # PR-9 coupling-retrofit (F1): default OFF so every existing caller
        # (positional `IrrigationEnvironment(config)`) is byte-identical.
        # See examples/irrigation_abm/irrigation_coupling.py for what the
        # guard checks and why it is not a plain EnvironmentCouplingAdapter
        # wrap. Import is local to __init__ (not module-level) so a
        # flag-OFF run never even imports broker.coupling.
        self._coupling_contract_active = bool(coupling_contract_active)
        self._irrigation_contract = None
        # Review P2: "the flag was on" is an INTENT; "the guard ran N times"
        # is the EVIDENCE. A run whose flag is true but whose guard never
        # fired (a runner that builds the env but never reads a context, an
        # agent set that is empty) looks in the manifest exactly like a run
        # the guard protected end to end, unless the count is recorded too.
        self._coupling_guard_calls = 0
        if self._coupling_contract_active:
            from examples.irrigation_abm.irrigation_coupling import (
                build_irrigation_agent_context_contract,
            )
            self._irrigation_contract = build_irrigation_agent_context_contract()

        # Timeline
        # F12 follow-up (2026-09-25 code review): pre-loop _current_year must
        # NOT equal loop year 1's value (sim_start_year, 2019), or the first
        # advance_year() call re-keys nothing and _decision_rng repeats its
        # draw (a real regression the review caught in
        # tests/test_irrigation_execute_skill_thread_safety.py). sim_start_year
        # - 1 (2018) is also the semantically right pre-loop label: initial
        # conditions (Mead's Dec-2018 observed elevation, 2018 diversions)
        # are dated 2018, one year before loop year 1 begins. This value is
        # always overwritten by the first advance_year() call before any
        # hook or validator reads it, so no production output depends on it.
        self._current_year: int = self.config.sim_start_year - 1
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
        # 1 January Lake Mead levels, one per loop year (F17 history, then
        # the 2026-09-25 supply-side redesign). Seeded with the level on
        # 1 January 2018 (1082.52 ft, the observed end-of-2017 value);
        # advance_year() appends each loop year's 1 January level BEFORE
        # _update_preceding_factors reads it, so loop year 1 (2019) compares
        # 1081.46 ft (1 January 2019 = Dec 2018 observed) against 1082.52 ft,
        # a real one-year comparison. Before the redesign the level for year
        # t was generated from year t-1 withdrawals inside advance_year, so
        # the list mixed start- and end-of-year values.
        self._mead_history: List[float] = [1082.52]  # 1 Jan 2018

        # Reservoir storage (MAF, total storage). _mead_storage holds one
        # 1 January value per loop year (index 0 = 1 January 2019);
        # _powell_storage is the current 1 January value.
        _init_elev = self.config.mead_initial_elevation
        _init_storage = float(np.interp(
            _init_elev, self._ELEVATION_FT, self._STORAGE_MAF
        ))
        self._mead_storage: List[float] = [_init_storage]
        self._powell_storage: float = float(self.config.powell_initial_storage_maf)
        # Settlement bookkeeping (see settle_year): the frozen 1 January
        # snapshot of the current year, the final settlement not yet
        # committed, and every committed settlement (one per loop year).
        self._snapshot: Optional[Dict[str, float]] = None
        self._pending_settlement: Optional[Dict[str, Any]] = None
        self._settlement_history: List[Dict[str, Any]] = []

        # Real CRSS precipitation data (None = use synthetic)
        self._crss_precip: Optional[Any] = None  # pandas DataFrame when loaded
        # Review P2: years for which real CRSS data was LOADED but did not
        # cover the simulated year, so _generate_precipitation fell back to
        # the synthetic drying trend. Warned about once per run (see there):
        # a run that believes it used real projections and silently used
        # synthetic numbers for part of its span is a provenance claim the
        # artifacts cannot otherwise contradict.
        self._precip_synthetic_fallback_years: List[int] = []

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
                "delivery_ratio": 1.0,
                "gap_reason": "none",
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
                "delivery_ratio": 1.0,
                "gap_reason": "none",
                "at_allocation_cap": False,
                "has_efficient_system": getattr(p, "has_efficient_system", False),
                "below_minimum_utilisation": False,
                "cluster": p.cluster,
                # v17: Skill-level magnitude params + persona scale
                "persona_scale": getattr(p, "persona_scale", 1.0),
                "skill_magnitude": getattr(p, "skill_magnitude", {}),
                # v12 legacy: per-persona magnitude (fallback)
                "magnitude_default": getattr(p, "magnitude_default", 10),
                "magnitude_sigma": getattr(p, "magnitude_sigma", 0.0),
                "magnitude_min": getattr(p, "magnitude_min", 1.0),
                "magnitude_max": getattr(p, "magnitude_max", 30.0),
                "exploration_rate": getattr(p, "exploration_rate", 0.0),
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

        # v12: Assign cluster-based magnitude parameters with stochasticity
        # Mix of aggressive, forward-looking, and myopic clusters (50%-30%-20%)
        clusters = (
            ["aggressive"] * (n_agents // 2) +
            ["forward_looking_conservative"] * (n_agents * 3 // 10) +
            ["myopic_conservative"] * (n_agents * 2 // 10)
        )
        # Pad to exact n_agents if needed
        while len(clusters) < n_agents:
            clusters.append("myopic_conservative")
        # Shuffle for random assignment
        self.rng.shuffle(clusters)

        # Phase 1 + CRSS Calibration: Reduced magnitude ranges to match FQL + CRSS scaling
        # NOTE: Triple source of truth for cluster configuration:
        #   1. This hardcoded fallback (synthetic initialization, default behavior)
        #   2. config/agent_types.yaml (--real flag CSV loading)
        #   3. run_experiment.py target_dist (rebalance_to_target call)
        # All three sources must be kept in sync manually (verified by runtime assertion)
        # v17: Default skill-level Gaussian params (matches agent_types.yaml)
        _default_skill_magnitude = {
            "increase_large": {"mu": 12.0, "sigma": 3.0, "min": 8.0, "max": 20.0},
            "increase_small": {"mu": 4.0, "sigma": 1.5, "min": 1.0, "max": 8.0},
            "decrease_small": {"mu": 4.0, "sigma": 1.5, "min": 1.0, "max": 8.0},
            "decrease_large": {"mu": 12.0, "sigma": 3.0, "min": 8.0, "max": 20.0},
        }

        cluster_configs = {
            "aggressive": {
                "persona_scale": 1.15,
                "magnitude_default": 10.0,    # Phase 1: 15.0 → 10.0 (-33%)
                "magnitude_sigma": 3.5,        # Phase 1: 5.0 → 3.5 (-30%)
                "magnitude_min": 5.0,          # Phase 1: 10.0 → 5.0 (wider range bottom)
                "magnitude_max": 20.0,         # Phase 1: 30.0 → 20.0 (cap extremes)
                "exploration_rate": 0.02,      # Stage 3 v2: 0.001 → 0.02 (2%)
            },
            "forward_looking_conservative": {
                "persona_scale": 1.00,
                "magnitude_default": 7.5,      # Phase 1: 12.5 → 7.5 (-40%)
                "magnitude_sigma": 3.0,        # Phase 1: 4.0 → 3.0 (-25%)
                "magnitude_min": 3.0,          # Phase 1: 5.0 → 3.0
                "magnitude_max": 15.0,         # Phase 1: 20.0 → 15.0
                "exploration_rate": 0.02,      # Stage 3 v2: 0.001 → 0.02 (2%)
            },
            "myopic_conservative": {
                "persona_scale": 0.80,
                "magnitude_default": 4.0,      # Phase 1: 5.5 → 4.0 (-27%)
                "magnitude_sigma": 2.0,        # Phase 1: 2.5 → 2.0 (-20%)
                "magnitude_min": 1.0,          # Unchanged
                "magnitude_max": 8.0,          # Phase 1: 10.0 → 8.0
                "exploration_rate": 0.02,      # Stage 3 v2: 0.0005 → 0.02 (2%)
            },
        }

        agent_index = 0
        for i in range(n_ub):
            aid = f"UB_Agent_{i:03d}"
            cluster = clusters[agent_index] if agent_index < len(clusters) else "myopic_conservative"
            config = cluster_configs[cluster]

            # CRSS Calibration Layer: Scale water_right to match CRSS 2019-2060 aggregate demand
            # Derivation (from per-agent trajectory analysis):
            #   - v12 uncalibrated mean: 6.31 MAF/yr (80.87 KAF/agent × 78 agents)
            #   - CRSS baseline target:  5.86 MAF/yr (75.10 KAF/agent × 78 agents)
            #   - Required scaling:      75.10 / 80.87 = 0.9286 (-7.1% adjustment)
            # Result: Brings aggregate demand from 1.077x CRSS to 1.00x CRSS
            calibrated_wr = base_water_right * 0.9286
            self._agents[aid] = {
                "basin": "upper_basin",
                "diversion": calibrated_wr * 0.8,
                "request": calibrated_wr * 0.8,
                "water_right": calibrated_wr,
                "curtailment_ratio": 0.0,
                "delivery_ratio": 1.0,
                "gap_reason": "none",
                "at_allocation_cap": False,
                "has_efficient_system": False,
                "below_minimum_utilisation": False,
                "cluster": cluster,
                # v17: skill-level magnitude + persona scale
                "persona_scale": config["persona_scale"],
                "skill_magnitude": dict(_default_skill_magnitude),
                # v12 legacy: per-persona magnitude (fallback)
                "magnitude_default": config["magnitude_default"],
                "magnitude_sigma": config["magnitude_sigma"],
                "magnitude_min": config["magnitude_min"],
                "magnitude_max": config["magnitude_max"],
                "exploration_rate": config["exploration_rate"],
            }
            agent_index += 1

        for i in range(n_lb):
            aid = f"LB_Agent_{i:03d}"
            cluster = clusters[agent_index] if agent_index < len(clusters) else "myopic_conservative"
            config = cluster_configs[cluster]

            # CRSS Calibration Layer: Scale water_right to match CRSS 2019-2060 aggregate demand
            calibrated_wr = base_water_right * 0.9286
            self._agents[aid] = {
                "basin": "lower_basin",
                "diversion": calibrated_wr * 0.8,
                "request": calibrated_wr * 0.8,
                "water_right": calibrated_wr,
                "curtailment_ratio": 0.0,
                "delivery_ratio": 1.0,
                "gap_reason": "none",
                "at_allocation_cap": False,
                "has_efficient_system": False,
                "below_minimum_utilisation": False,
                "cluster": cluster,
                # v17: skill-level magnitude + persona scale
                "persona_scale": config["persona_scale"],
                "skill_magnitude": dict(_default_skill_magnitude),
                # v12 legacy: per-persona magnitude (fallback)
                "magnitude_default": config["magnitude_default"],
                "magnitude_sigma": config["magnitude_sigma"],
                "magnitude_min": config["magnitude_min"],
                "magnitude_max": config["magnitude_max"],
                "exploration_rate": config["exploration_rate"],
            }
            agent_index += 1

    def load_crss_precipitation(self, csv_path: str) -> None:
        """Load real CRSS/PRISM winter precipitation projections.

        Loads the PrismWinterPrecip_ST_NOAA_Future.csv file which contains
        annual winter precipitation (inches) for 9 state-groups from
        2017-2060.  Values are converted to mm and stored for use by
        ``_generate_precipitation()``.

        Columns: WY, UT1, UT2, UT3, NM, CO1, CO2, CO3, AZ
        Upper Basin average: WY, UT1-3, CO1-3
        Lower Basin average: NM, AZ

        A blank cell FAILS THE LOAD, naming the year and column (PR-9 review
        P1-e). ``pandas`` reads a blank as ``NaN``, and nothing downstream
        ever reports one — it is laundered into a plausible number twice
        over:

        * A FEW blank cells in a year: ``_generate_precipitation`` takes
          ``.mean()`` over the seven Upper Basin columns, and pandas' mean
          SKIPS NaN, so the year silently becomes the average of whichever
          stations reported. No error, no NaN, just a different number than
          the file was supposed to give.
        * A WHOLE blank Upper Basin row: the mean of nothing is ``NaN``, and
          the clamps then convert it into the most extreme legal value in
          each direction, because every comparison with NaN is False.
          ``max(6.0, min(17.0, NaN))`` returns ``17.0`` — the operational
          CEILING on natural flow — while
          ``max(0.0, min(1.0, 1.0 - NaN/baseline))`` in
          ``_compute_drought_index`` returns ``1.0``, MAXIMUM drought. One
          missing row thus reaches the agent as "wettest possible inflow,
          worst possible drought", and no artifact anywhere records that a
          cell was blank.

        Refusing at LOAD time is the only point where the year and the column
        are still known.

        This check runs only when real CRSS data is loaded, which the
        ``--model mock`` byte-identity runs never do (they leave
        ``_crss_precip`` as ``None`` and take the synthetic path), so no
        frozen corpus is affected.

        Args:
            csv_path: Path to PrismWinterPrecip_ST_NOAA_Future.csv

        Raises:
            ValueError: if any cell in the file is blank / non-numeric.
        """
        import pandas as pd

        df = pd.read_csv(csv_path, index_col=0)
        # Convert inches to mm (1 inch = 25.4 mm)
        mm = df * 25.4
        nan_mask = mm.isna()
        if bool(nan_mask.to_numpy().any()):
            bad = [
                f"{index_label}/{column}"
                for column in mm.columns
                for index_label in mm.index[nan_mask[column]]
            ]
            raise ValueError(
                f"load_crss_precipitation: {len(bad)} blank/non-numeric cell(s) in "
                f"{csv_path} at year/column {bad[:20]}"
                f"{' (first 20 shown)' if len(bad) > 20 else ''}. A blank precipitation "
                f"cell becomes NaN, and the min/max clamps downstream turn NaN into "
                f"maximum inflow and maximum drought rather than an error. Fix the "
                f"source file, or drop the affected year(s) deliberately."
            )
        self._crss_precip = mm

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
            },
            "reservoirs": {
                "powell_storage_maf": self._powell_storage,
                "mead_storage_maf": self._mead_storage[-1],
                "powell_capacity_maf": self.config.powell_capacity_maf,
                "powell_dead_pool_maf": self.config.powell_dead_pool_maf,
                "min_powell_release_maf": self.config.min_powell_release_maf,
            },
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
        # F12 (2026-09-25 audit): using _year_index as a straight offset made
        # loop year 1 calendar year 2020 (one year late) and loop year 42
        # calendar year 2061, one year past the CRSS PRISM CSV's real
        # 2017-2060 coverage, so the LAST year of every 42-year run silently
        # used the synthetic drying-trend fallback instead of a real CRSS
        # row. The "- 1" makes loop year 1 = sim_start_year (2019) and loop
        # year 42 = 2060, matching docs/irrigation_physics.md ("Y1 =
        # calendar year 2019"), DATA.md and README.md (already documented as
        # 2019-2060), and keeps every loop year inside real CRSS coverage.
        self._current_year = self.config.sim_start_year + self._year_index - 1
        self._global["year"] = self._current_year

        # 1. Commit last year's final settlement: its end-of-year storages
        #    become this year's 1 January storages. A caller that never
        #    called settle_year() (the FQL baseline, unit tests driving
        #    advance_year() directly) gets it here, at last year's final
        #    requests, so storage always evolves exactly once per year.
        #    Always recomputed here (settle_year is idempotent), so a request
        #    changed after an earlier settle_year() call in the same year is
        #    still what the committed storage reflects.
        if self._snapshot is not None:
            self._commit_settlement(self.settle_year())

        # 2. Water signals for this year
        precip = self._generate_precipitation()
        natural_flow = self._natural_flow_maf(precip)
        mead_level = self._storage_to_elevation(self._mead_storage[-1])
        self._mead_history.append(mead_level)

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

        # 3. Declarations from the 1 January Mead level: the Lower Basin
        #    shortage tier (curtailment_ratio, Lower Basin agents only) and
        #    the Minute 323 Mexico reduction.
        self._apply_curtailment()
        lb_cut = self._tier_curtailment_ratio(self._compute_shortage_tier())

        # 4. Freeze this year's 1 January snapshot, then the PROVISIONAL
        #    settlement at the carried requests: what each agent can expect
        #    this year at its current request (the value its prompt and the
        #    governance checks read). settle_year() redoes it at the final
        #    requests after every decision.
        self._snapshot = {
            "powell_storage": float(self._powell_storage),
            "mead_storage": float(self._mead_storage[-1]),
            "natural_flow": float(natural_flow),
            "lb_cut": float(lb_cut),
            "mexico": float(self._mexico_delivery_maf(mead_level)),
        }
        self._pending_settlement = None
        provisional = self._settle(self._snapshot)
        self._write_agent_deliveries(provisional)

        self._global["natural_flow_maf"] = float(natural_flow)
        self._global["powell_storage_maf"] = float(self._powell_storage)
        self._global["mead_storage_maf"] = float(self._mead_storage[-1])

        # Basin-level aggregate request: a logged metric (the retired
        # demand ceiling used to block on it); basin_request_over_target is
        # the request total over the 5.86 MAF CRSS 2019-2060 demand target.
        self._global["total_basin_demand"] = sum(
            a["request"] for a in self._agents.values()
        )
        self._global["basin_request_over_target"] = (
            self._global["total_basin_demand"] / CRSS_DEMAND_TARGET_AF
        )

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

        # PR-9 coupling-retrofit (F1): with the flag ON, fail loud on a
        # genuinely missing field INSTEAD of the .get(key, 0) defaults
        # below silently manufacturing a plausible-looking zero. No-op
        # (and no output change) when every field below is actually
        # present — see irrigation_coupling.guard_agent_context_sources.
        if self._coupling_contract_active:
            from examples.irrigation_abm.irrigation_coupling import (
                guard_agent_context_sources,
            )
            guard_agent_context_sources(
                self._irrigation_contract,
                agent=agent, basin_key=basin_key, basin=basin,
                global_state=self._global,
            )
            # Counted AFTER the guard returns, so the number means "calls
            # that passed", not "calls attempted" — a run that raised is
            # reported by the exception, not by this tally.
            self._coupling_guard_calls += 1

        return {
            # Agent state
            "agent_id": agent_id,
            "basin": basin_key,
            "current_diversion": agent.get("diversion", 0),
            "current_request": agent.get("request", 0),
            "water_right": agent.get("water_right", 0),
            "curtailment_ratio": agent.get("curtailment_ratio", 0),
            # Expected share of the request delivered this year, and why it
            # is below 1 (a settlement code, see _settle). Provisional until
            # settle_year() runs; after it, the final values for the year.
            "delivery_ratio": agent.get("delivery_ratio", 1.0),
            "gap_reason": agent.get("gap_reason", "none"),
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
            "total_basin_demand": self._global.get("total_basin_demand", 0),
            "basin_request_over_target": self._global.get("basin_request_over_target", 0),
            "natural_flow_maf": self._global.get("natural_flow_maf", 0),
            "powell_storage_maf": self._global.get("powell_storage_maf", 0),
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

        # Provisional delivery at the new request: this year's expected
        # delivery ratio (from the provisional settlement advance_year ran,
        # which already includes the shortage tier and any physical limit).
        # The authoritative value is written by settle_year() once every
        # decision for the year has executed.
        agent["diversion"] = new_request * agent.get("delivery_ratio", 1.0)

    def _decision_rng(self, agent_id: str, skill: str) -> np.random.Generator:
        """A generator private to one ``(seed, year, agent, skill)``.

        The decision phase runs inside
        ``ExperimentRunner._run_agents_parallel``'s ThreadPoolExecutor, so
        any draw taken from the shared env-level ``self.rng`` is handed out
        in thread-completion order rather than agent order.  The same seed
        then yields a different agent -> magnitude assignment under
        ``--workers 4`` than under ``--workers 1``, and a different one again
        between two ``--workers 4`` runs at that seed (measured 2026-09-15:
        13 of 16 agents diverged).  The distribution stays correct; which
        agent receives which sample does not, which is what an audit trace
        and every per-agent analysis read.

        Deriving a fresh generator per call removes the shared stream
        entirely, so no amount of thread interleaving can reach the draw:
        the value depends only on the four keys below.  Creation is cheap
        relative to one governed LLM step, and stateless, so no lock is
        needed and none is taken.

        ``zlib.crc32`` hashes the string keys, NOT the builtin ``hash``:
        the builtin is salted per process (``PYTHONHASHSEED``), which would
        trade a thread-order dependence for a process-launch dependence.

        INVARIANT this leans on: calling it twice with the same key returns
        the same value, so a domain that draws twice per ``(agent, year,
        skill)`` would get the same magnitude both times. That is safe here
        only because the engine executes at most one magnitude-drawing skill
        per key — ``broker/core/skill_broker_engine.py:716-718`` rejects a
        secondary skill whose name equals the primary's, the
        rejected-fallback execution lives in an ``elif`` arm that cannot run
        alongside the approved one, and ``advance_year`` increments
        ``_current_year`` unconditionally so a year never repeats. A future
        multi-decision-per-year domain must add a fifth key component (an
        attempt index) rather than assume this still holds.
        """
        return np.random.default_rng([
            int(self.config.seed) & 0xFFFF_FFFF,
            int(self._current_year) & 0xFFFF_FFFF,
            zlib.crc32(agent_id.encode("utf-8")),
            zlib.crc32(skill.encode("utf-8")),
        ])

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
        # v21 FIX: Use request (paper demand) as base for all skills.
        # Previously used diversion (physical delivery), which is compressed
        # by curtailment + Powell constraints.  This created an asymmetry:
        # maintain_demand preserved request while increase/decrease operated
        # on the much-lower diversion.  Using request ensures a consistent
        # base across all skill types.  A request is bounded by the water
        # right (min(current + change, wr) below); what the agent actually
        # receives is bounded by the supply-side settlement (_settle).
        current = agent["request"]
        meta = getattr(approved_skill, "parameters", {}) or {}

        # ═══ v17: Skill-level Gaussian magnitude sampling ═══
        # Each skill defines its own (mu, sigma, min, max) base parameters.
        # Persona's persona_scale multiplies mu and sigma (shifts distribution
        # center and spread) while min/max stay fixed (define skill identity).
        #
        # NOTE: LLM cannot generate continuous Gaussian distributions (v11 analysis
        # showed 56.6% chose 25%, only 6-7 unique values). Code-based sampling
        # provides true stochasticity matching Hung & Yang (2021) FQL behavior.

        persona_scale = agent.get("persona_scale", 1.0) or 1.0
        skill_mag_all = agent.get("skill_magnitude", {}) or {}
        skill_mag_cfg = skill_mag_all.get(skill, {})
        exploration_rate = agent.get("exploration_rate", 0.0) or 0.0

        # ═══ ε-UNBOUNDED EXPLORATION ═══
        magnitude_pct = 0.0
        is_exploration = False

        if skill != "maintain_demand" and skill_mag_cfg:
            # v17 path: per-skill Gaussian params scaled by persona
            base_mu = skill_mag_cfg.get("mu", 10.0)
            base_sigma = skill_mag_cfg.get("sigma", 3.0)
            mag_min = skill_mag_cfg.get("min", 1.0)
            mag_max = skill_mag_cfg.get("max", 20.0)

            mu = base_mu * persona_scale
            sigma = base_sigma * persona_scale

            if sigma > 0:
                # Per-(agent, year, skill) stream — see _decision_rng: this
                # runs on a worker thread, so a shared stream would make the
                # assignment depend on thread scheduling.
                rng = self._decision_rng(aid, skill)
                if exploration_rate > 0 and rng.random() < exploration_rate:
                    noise = rng.normal(0, sigma * 2.0)
                    magnitude_pct = mu + noise
                    magnitude_pct = float(np.clip(magnitude_pct, 0.5, 100.0))
                    is_exploration = True
                else:
                    noise = rng.normal(0, sigma)
                    magnitude_pct = mu + noise
                    magnitude_pct = float(np.clip(magnitude_pct, mag_min, mag_max))
            else:
                magnitude_pct = mu

        elif skill != "maintain_demand":
            # Legacy fallback: per-persona params (v12 compat)
            mag_default = agent.get("magnitude_default", 10) or 10
            mag_sigma = agent.get("magnitude_sigma", 0.0) or 0.0
            mag_min = agent.get("magnitude_min", 1.0) or 1.0
            mag_max = agent.get("magnitude_max", 30.0) or 30.0

            if mag_sigma > 0:
                # Same per-(agent, year, skill) stream as the v17 branch
                # above; the two branches are mutually exclusive, so they
                # never draw from one key twice.
                rng = self._decision_rng(aid, skill)
                if exploration_rate > 0 and rng.random() < exploration_rate:
                    noise = rng.normal(0, mag_sigma * 2.0)
                    magnitude_pct = mag_default + noise
                    magnitude_pct = float(np.clip(magnitude_pct, 0.5, 100.0))
                    is_exploration = True
                else:
                    noise = rng.normal(0, mag_sigma)
                    magnitude_pct = mag_default + noise
                    magnitude_pct = float(np.clip(magnitude_pct, mag_min, mag_max))
            else:
                magnitude_pct = mag_default

        state_changes: Dict[str, Any] = {}
        state_changes["is_exploration"] = is_exploration

        # F07 (2026-09-25 audit): the applied magnitude never reached memory
        # because ``_apply_state_changes`` (broker/core/experiment_runner.py)
        # reads ``params["magnitude_pct"]`` (the LLM's proposal, not what was
        # actually applied) or ``result.execution_result.action_context``,
        # and this method only ever set ``state_changes["magnitude_pct_applied"]``,
        # never ``action_context``. Populated below for every skill that
        # actually samples a magnitude, so build_action_outcome_feedback's
        # "(by N%)" reflects the Gaussian-sampled value the environment used,
        # not the LLM's discrete request.
        action_context: Dict[str, Any] = {}

        if skill in ("increase_large", "increase_small", "increase_demand"):
            # v21: Scale increase by request (paper demand), capped at the
            # water right; deliveries are limited by _settle, not here.
            change = current * (magnitude_pct / 100.0)
            new_req = min(current + change, wr)
            self.update_agent_request(aid, new_req)
            state_changes["request"] = new_req
            state_changes["magnitude_pct_applied"] = magnitude_pct
            action_context["magnitude_pct"] = magnitude_pct

        elif skill in ("decrease_large", "decrease_small", "decrease_demand"):
            # v21: Also use request as base (was water_right).
            change = current * (magnitude_pct / 100.0)
            floor = wr * MIN_UTIL
            utilisation = current / wr if wr > 0 else 1.0
            # P1: diminishing returns as utilisation approaches floor
            taper = max(0.0, (utilisation - MIN_UTIL) / (1.0 - MIN_UTIL))
            new_req = max(current - change * taper, floor)
            self.update_agent_request(aid, new_req)
            state_changes["request"] = new_req
            state_changes["magnitude_pct_applied"] = magnitude_pct
            action_context["magnitude_pct"] = magnitude_pct

        elif skill == "maintain_demand":
            # Preserve existing *request* (not diversion which includes
            # curtailment). Using diversion would cause double-curtailment
            # because update_agent_request re-applies the curtailment ratio.
            existing_request = agent["request"]
            self.update_agent_request(aid, existing_request)
            state_changes["request"] = existing_request

        else:
            return ExecutionResult(
                success=False, error=f"Unknown skill: {skill}"
            )

        return ExecutionResult(
            success=True, state_changes=state_changes, action_context=action_context
        )

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
            # Review P2: real data was loaded but does not reach this year, so
            # the synthetic trend below produces it. Said ONCE per run, naming
            # the year(s) and the span the file actually covers — silently
            # mixing synthetic years into a run labelled "real CRSS
            # projections" is a provenance defect no output artifact records.
            self._precip_synthetic_fallback_years.append(self._current_year)
            if len(self._precip_synthetic_fallback_years) == 1:
                from broker.utils.logging import logger as _logger

                index = self._crss_precip.index
                _logger.warning(
                    "[irrigation_env] real CRSS precipitation is loaded but does "
                    "not cover year %s (file covers %s-%s); this year and any "
                    "later uncovered year use the SYNTHETIC drying trend instead. "
                    "Read self._precip_synthetic_fallback_years for the full list.",
                    self._current_year,
                    min(index) if len(index) else "?",
                    max(index) if len(index) else "?",
                )

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

    def _natural_flow_maf(self, precip: float) -> float:
        """Natural flow at Lees Ferry (MAF/yr) from Upper Basin winter
        precipitation, clamped to the [6, 17] MAF operational range.
        Winter precipitation is known before the irrigation season, so the
        year's own value is used at decision time."""
        cfg = self.config
        natural_flow = cfg.natural_flow_base_maf * (precip / cfg.precip_baseline_mm)
        return max(6.0, min(17.0, natural_flow))

    def _mexico_delivery_maf(self, mead_level: float) -> float:
        """Treaty delivery to Mexico after the Minute 323 reductions keyed
        to the 1 January Lake Mead level."""
        cfg = self.config
        if mead_level < 1025:
            return cfg.mexico_treaty_maf - 0.275
        if mead_level < 1050:
            return cfg.mexico_treaty_maf - 0.104
        if mead_level < 1075:
            return cfg.mexico_treaty_maf - 0.080
        if mead_level < 1090:
            return cfg.mexico_treaty_maf - 0.041
        return cfg.mexico_treaty_maf

    def _mead_evaporation_maf(self, storage_maf: float) -> float:
        """Lake Mead evaporation, scaling with storage (surface-area proxy):
        0.8 MAF at the 13 MAF reference storage (about 1,100 ft), floored at
        evap_min_frac of that and capped at 1.5 times it (unchanged from the
        pre-redesign mass balance)."""
        cfg = self.config
        frac = storage_maf / 13.0
        return cfg.evaporation_maf * max(cfg.evap_min_frac, min(1.5, frac))

    def _powell_evaporation_maf(self, storage_maf: float) -> float:
        """Lake Powell evaporation: powell_evaporation_maf at full pool,
        scaled by the storage fraction and floored at evap_min_frac (the
        Mead term's shape, expressed on [0, 1])."""
        cfg = self.config
        frac = storage_maf / cfg.powell_capacity_maf
        return cfg.powell_evaporation_maf * max(cfg.evap_min_frac, min(1.0, frac))

    def _settle(
        self,
        snapshot: Dict[str, float],
        requests: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """One year's two-reservoir settlement. PURE: reads only its
        arguments, the agents' basin / request / water_right and the
        config; writes nothing.

        ``snapshot`` is the frozen 1 January state (see advance_year):
        ``powell_storage``, ``mead_storage`` (total storage, MAF),
        ``natural_flow`` (MAF), ``lb_cut`` (declared Lower Basin shortage
        ratio, on [0, 1]) and ``mexico`` (MAF). ``requests`` maps agent id
        to request (AF); default = every agent's current request.

        Steps (MAF/yr):

        U  Upper Basin. Requests r_U. Deliverable
           D_U = min(r_U, C_UB, max(0, NF + (S_P - S_P,dead) - E_P - R_min)):
           the 5.0 MAF delivery capacity, and what leaves Powell able to make
           its 7.0 MAF minimum release from inflow plus usable storage. So a
           year with NF below 7 does NOT zero the Upper Basin; it is cut only
           when Powell storage cannot cover the release. Shared pro-rata.
        P  Powell. Inflow I = NF - D_U. Release R = R_min, or everything
           above the dead pool when that is less (only reachable once D_U is
           already 0). Storage above full pool spills into R.
           New storage = S_P + I - E_P - R.
        L  Lake Mead. Withdrawals O = (r_LB + N) (1 - g) + X: the declared
           shortage cut g applies to the WHOLE Lower Basin consumptive use
           (agricultural agents and the 5.0 MAF non-agricultural bucket N);
           X is the Mexico delivery. Available A = (S_M - S_M,dead) + R + T
           - E_M. When O > A every withdrawal is scaled by phi = A / O
           (pro-rata). New storage = S_M + R + T - E_M - phi O; storage
           above full pool spills below Hoover (logged).

        Evaporation is taken on the 1 January storage and can never draw a
        reservoir below its dead pool. Conservation, checked by the tests:
        dS_P + dS_M = NF + T - D_U - E_P - E_M - phi O - spill_M.

        Each agent's ``gap_reason`` names the binding limit, as a code the
        prompt and memory text turn into a sentence: ``none``, ``ub_capacity``, ``ub_powell_release``,
        ``lb_shortage_tier``, ``lb_mead_availability`` or
        ``lb_shortage_tier+lb_mead_availability``.
        """
        cfg = self.config
        if requests is None:
            requests = {aid: a["request"] for aid, a in self._agents.items()}

        ub_ids = [aid for aid, a in self._agents.items() if a["basin"] == "upper_basin"]
        lb_ids = [aid for aid, a in self._agents.items() if a["basin"] != "upper_basin"]
        req = {
            aid: max(0.0, min(float(requests.get(aid, self._agents[aid]["request"])),
                              float(self._agents[aid]["water_right"])))
            for aid in self._agents
        }
        r_ub = sum(req[a] for a in ub_ids) / 1e6
        r_lb = sum(req[a] for a in lb_ids) / 1e6

        nf = snapshot["natural_flow"]
        s_p = snapshot["powell_storage"]
        s_m = snapshot["mead_storage"]
        g = snapshot["lb_cut"]
        mexico = snapshot["mexico"]

        # --- U + P: Upper Basin and Lake Powell ---
        p_usable = max(0.0, s_p - cfg.powell_dead_pool_maf)
        e_p = min(self._powell_evaporation_maf(s_p), p_usable + nf)
        ub_room = max(0.0, nf + p_usable - e_p - cfg.min_powell_release_maf)
        # Upper Basin use is upstream of Powell, so it can never exceed the
        # natural flow itself (never binding with the defaults: NF >= 6.0 >
        # the 5.0 MAF delivery capacity).
        d_u = min(r_ub, cfg.ub_infrastructure_cap_maf, ub_room, nf)
        if d_u >= r_ub:
            ub_reason = "none"
        elif ub_room < min(cfg.ub_infrastructure_cap_maf, nf):
            ub_reason = "ub_powell_release"
        else:
            # Delivery capacity, or (never with the defaults) the natural
            # flow itself: either way, no more can be diverted upstream.
            ub_reason = "ub_capacity"
        inflow_p = nf - d_u
        release = min(cfg.min_powell_release_maf, max(0.0, p_usable + inflow_p - e_p))
        s_p_end = s_p + inflow_p - e_p - release
        powell_spill = max(0.0, s_p_end - cfg.powell_capacity_maf)
        release += powell_spill
        s_p_end -= powell_spill

        # --- L: Lake Mead ---
        trib = cfg.lb_tributary_maf
        m_usable = max(0.0, s_m - cfg.mead_dead_pool_maf)
        e_m = min(self._mead_evaporation_maf(s_m), m_usable + release + trib)
        lb_ag = r_lb * (1.0 - g)
        non_ag = cfg.lb_non_ag_total_maf * (1.0 - g)
        outflow = lb_ag + non_ag + mexico
        available = max(0.0, m_usable + release + trib - e_m)
        phi = 1.0 if (outflow <= 0 or outflow <= available) else available / outflow
        s_m_end = s_m + release + trib - e_m - phi * outflow
        mead_spill = max(0.0, s_m_end - cfg.mead_capacity_maf)
        s_m_end -= mead_spill

        if g > 0 and phi < 1.0:
            lb_reason = "lb_shortage_tier+lb_mead_availability"
        elif phi < 1.0:
            lb_reason = "lb_mead_availability"
        elif g > 0:
            lb_reason = "lb_shortage_tier"
        else:
            lb_reason = "none"

        ub_ratio = (d_u / r_ub) if r_ub > 0 else 1.0
        lb_ratio = (1.0 - g) * phi
        agents: Dict[str, Dict[str, Any]] = {}
        for aid in ub_ids:
            agents[aid] = {
                "request": req[aid],
                "delivered": req[aid] * ub_ratio,
                "delivery_ratio": ub_ratio,
                "gap_reason": ub_reason,
            }
        for aid in lb_ids:
            agents[aid] = {
                "request": req[aid],
                "delivered": req[aid] * lb_ratio,
                "delivery_ratio": lb_ratio,
                "gap_reason": lb_reason,
            }

        return {
            "agents": agents,
            "natural_flow_maf": nf,
            "ub_request_maf": r_ub,
            "ub_delivered_maf": d_u,
            "lb_request_maf": r_lb,
            "lb_delivered_maf": lb_ag * phi,
            "lb_non_ag_delivered_maf": non_ag * phi,
            "mexico_delivered_maf": mexico * phi,
            "lb_cut": g,
            "lb_phys_ratio": phi,
            "powell_storage_maf": s_p,
            "powell_storage_end_maf": s_p_end,
            "powell_evap_maf": e_p,
            "powell_release_maf": release,
            "powell_spill_maf": powell_spill,
            "mead_storage_maf": s_m,
            "mead_storage_end_maf": s_m_end,
            "mead_evap_maf": e_m,
            "mead_spill_maf": mead_spill,
            "lb_tributary_maf": trib,
        }

    def _write_agent_deliveries(self, settlement: Dict[str, Any]) -> None:
        """Write a settlement's per-agent delivery onto the agent dicts
        (``diversion`` = delivered, plus ``delivery_ratio``/``gap_reason``)."""
        for aid, rec in settlement["agents"].items():
            agent = self._agents[aid]
            agent["diversion"] = rec["delivered"]
            agent["delivery_ratio"] = rec["delivery_ratio"]
            agent["gap_reason"] = rec["gap_reason"]

    def settle_year(self) -> Dict[str, Any]:
        """FINAL settlement of the current year at the agents' current
        requests, after every decision has executed.

        Keeps the F11b contract (2026-09-25): it rebuilds every agent's
        delivery from ``request`` and the frozen 1 January snapshot, never
        from ``diversion``, so an agent whose decision did not execute
        (ABORTED, no fallback, inactive) is treated exactly like one that
        executed ``maintain_demand``, and a second call with no decision in
        between is bitwise identical. Storage is NOT committed here; the
        next ``advance_year()`` commits the pending settlement once.

        Call exactly once per year, after the full decision loop and before
        anything logs or snapshots the year's deliveries
        (``IrrigationLifecycleHooks.post_year``). Returns the settlement.
        """
        if self._snapshot is None:
            raise RuntimeError(
                "settle_year() called before the first advance_year(): there "
                "is no 1 January snapshot to settle against."
            )
        settlement = self._settle(self._snapshot)
        settlement["year"] = self._current_year
        self._write_agent_deliveries(settlement)
        self._pending_settlement = settlement
        return settlement

    def apply_powell_cap_to_executed_diversions(self) -> None:
        """Deprecated alias of :meth:`settle_year` (the F11b name, kept so
        older call sites and tests keep working)."""
        self.settle_year()

    def _commit_settlement(self, settlement: Dict[str, Any]) -> None:
        """End-of-year storages become the next 1 January storages."""
        self._powell_storage = float(settlement["powell_storage_end_maf"])
        self._mead_storage.append(float(settlement["mead_storage_end_maf"]))
        self._settlement_history.append(settlement)
        self._pending_settlement = None

    @property
    def last_settlement(self) -> Optional[Dict[str, Any]]:
        """The current year's final settlement if settle_year() ran this
        year, else the last committed one (None before any)."""
        if self._pending_settlement is not None:
            return self._pending_settlement
        return self._settlement_history[-1] if self._settlement_history else None

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
        # Normal precip → 0.0 (not dry), zero precip → 1.0 (max drought)
        precip_norm = max(0.0, min(1.0, 1.0 - precip / self.config.precip_baseline_mm))

        # Lake Mead component (lower level = more drought)
        mead_norm = max(0.0, min(1.0, 1.0 - (mead_level - 900) / 320.0))

        return 0.5 * precip_norm + 0.5 * mead_norm

    def _compute_shortage_tier(self) -> int:
        """Compute Bureau of Reclamation shortage tier from Lake Mead level.

        Returns:
            0 = Normal, 1 = Tier 1, 2 = Tier 2, 3 = Tier 3 (most severe).

        Raises:
            KeyError: when the coupling context contract is active and
                ``lake_mead_level`` is absent. Review P2: the legacy default
                of 1100 ft is above ``mead_shortage_tier1``, so a MISSING
                reservoir level silently produced tier 0 — "no shortage, no
                curtailment" — which is both the most consequential answer
                this function can give and indistinguishable from a real
                healthy reservoir. Under the flag whose whole purpose is to
                refuse manufactured physical state, it must fail instead.
        """
        lower = self._basins["lower_basin"]
        if self._coupling_contract_active and "lake_mead_level" not in lower:
            raise KeyError(
                "lake_mead_level is missing from lower_basin and "
                "coupling.context_contract is ON: refusing to fall back to the "
                "1100 ft default, which would report shortage tier 0 (no "
                "curtailment) for a reservoir whose level was never set."
            )
        mead = lower.get("lake_mead_level", 1100)
        cfg = self.config
        if mead >= cfg.mead_shortage_tier1:
            return 0
        elif mead >= cfg.mead_shortage_tier2:
            return 1
        elif mead >= cfg.mead_shortage_tier3:
            return 2
        else:
            return 3

    @staticmethod
    def _tier_curtailment_ratio(tier: int) -> float:
        """Lower Basin reduction by declared shortage tier (Colorado River
        Interim Guidelines, simplified): 0 / 5 / 10 / 20 percent."""
        return {0: 0.0, 1: 0.05, 2: 0.10, 3: 0.20}.get(tier, 0.0)

    def _apply_curtailment(self) -> None:
        """Record the declared shortage on each agent: the tier's ratio for
        Lower Basin agents, 0 for Upper Basin agents (the Interim Guidelines
        and DCP shortage tiers bind Lower Basin users only). The deliveries
        themselves are computed by :meth:`_settle`."""
        ratio = self._tier_curtailment_ratio(self._compute_shortage_tier())
        for agent in self._agents.values():
            agent["curtailment_ratio"] = (
                0.0 if agent["basin"] == "upper_basin" else ratio
            )

    # -----------------------------------------------------------------
    # Utility
    # -----------------------------------------------------------------

    def get_coupling_retrofit_metadata(self) -> Dict[str, Any]:
        """PR-9 coupling-retrofit provenance (F1): reports whether the
        ``coupling.context_contract`` fail-loud guard is active on this
        run's ``get_agent_context()`` physical-state handoff, WHICH CHECK
        each covered field actually got, which returned keys it does NOT
        cover, and how many times the guard actually ran. Read generically
        (by method name only — no irrigation-specific code in broker/) by
        ``ExperimentRunner._collect_reproducibility_metadata`` and merged
        into ``run_integrity.json`` as a side artifact; never touches the
        audit CSV. Distinct from ``EnvironmentCouplingAdapter.get_provenance``
        on purpose: this hook covers the ``coupling.context_contract``
        guard on ``get_agent_context()`` (a per-agent accessor reading
        several source dicts lazily), never the ``coupling.enable`` /
        ``EnvironmentCouplingAdapter`` boundary (the ``advance_step()`` /
        ``execute_skill()`` single-flat-dict model) - the two flags compose
        independently (see ``irrigation_coupling.py``'s module docstring for
        why one guard does not substitute for the other).

        UPDATE (v0.6 coupling-layer wiring, ``examples/irrigation_abm/
        coupling_modules.py``): this environment CAN now also be wrapped in
        ``EnvironmentCouplingAdapter`` (via ``--coupling`` /
        ``global_config.coupling.enable``). When it is, this method is
        still reachable - ``EnvironmentCouplingAdapter.__getattr__``
        forwards ``get_coupling_retrofit_metadata`` to the wrapped real
        engine when the real engine defines it - so a coupled run's
        manifest carries BOTH this method's keys (the context_contract
        guard's own status) AND ``coupling_adapter: True`` /
        ``coupling_provenance`` (the adapter's own hook) side by side,
        truthfully: two independent, simultaneously-active guards, not one
        falsely standing in for the other.

        ``coupling_contract_fields`` is a MAPPING (field -> check kind), not
        a bare list: five of the fifteen fields are bool/str and get a
        presence+type check rather than a range one, and a flat list read as
        though all fifteen were range-guarded (review P1-c).
        ``coupling_guard_calls`` separates intent from evidence - flag true
        with zero calls is a run the guard never touched.
        """
        from examples.irrigation_abm.irrigation_coupling import (
            IRRIGATION_CONTEXT_UNCOVERED_KEYS,
            irrigation_contract_field_checks,
        )
        return {
            "coupling_contract_active": self._coupling_contract_active,
            "coupling_contract_fields": irrigation_contract_field_checks(),
            "coupling_contract_uncovered_keys": list(IRRIGATION_CONTEXT_UNCOVERED_KEYS),
            "coupling_guard_calls": self._coupling_guard_calls,
        }

    @property
    def current_year(self) -> int:
        return self._current_year

    @property
    def agent_ids(self) -> List[str]:
        return list(self._agents.keys())

    def get_agent_state(self, agent_id: str) -> Dict[str, Any]:
        return self._agents.get(agent_id, {}).copy()
