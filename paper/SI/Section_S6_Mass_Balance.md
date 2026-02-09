### S6. Mass Balance and Human-Water Coupling

The irrigation ABM couples agent demand decisions to reservoir dynamics through a surrogate mass balance model for Lake Mead that mirrors the core physics of CRSS/RiverWare at annual resolution. This section documents the equations and parameter values implemented in the simulation environment.

#### S6.1 Annual Mass Balance Equation

At each simulation year *t*, Lake Mead storage is updated as:

    Storage(t+1) = Storage(t) + clamp(Mead_inflow - Mead_outflow, +/-3.5 MAF)

where the +/-3.5 MAF annual storage change cap represents Glen Canyon Dam buffering of releases. Storage is further bounded to the physical range [2.0, 26.1] MAF (dead pool to full pool).

The inflow and outflow terms are computed as follows:

    NaturalFlow   = 12.0 * (Precip / 100.0)          [MAF/yr, clamped to 6-17 MAF]
    UB_effective  = min(UB_div, NF - 7.0, 5.0)        [MAF/yr]
    PowellRelease = NaturalFlow - UB_effective          [>= 7.0 MAF, USBR DCP floor]
    Mead_inflow   = PowellRelease + 1.0                [+1.0 MAF LB tributary inflow]

    Mead_outflow  = LB_div + Mexico(DCP) + Evap(storage) + 5.0

where 5.0 MAF represents Lower Basin non-agricultural demands (municipal and industrial, tribal, Central Arizona Project, and system losses). Natural flow at the basin's reference precipitation of 100.0 mm averages 12.0 MAF/yr. Upper Basin diversions are constrained by both the Powell minimum release of 7.0 MAF (USBR Drought Contingency Plan operating rules) and a 5.0 MAF infrastructure ceiling reflecting historical Upper Basin depletion capacity.

Evaporation scales with reservoir surface area using a storage-fraction proxy:

    Evap = 0.8 * clamp(Storage / 13.0, 0.15, 1.50)    [MAF/yr]

where 13.0 MAF corresponds to the reference storage at approximately 1100 ft elevation. Mexico treaty deliveries follow Minute 323 tiered reductions: 1.5 MAF at normal levels, reduced by 0.041-0.275 MAF as Lake Mead elevation declines through thresholds at 1090, 1075, 1050, and 1025 ft.

#### S6.2 Elevation-Storage Relationship

Lake Mead elevation (ft above sea level) is converted to and from storage (MAF) via linear interpolation of the USBR empirical curve:

| Storage (MAF) | 2.0 | 3.6 | 5.8 | 8.0 | 9.5 | 11.0 | 13.0 | 17.5 | 23.3 | 26.1 |
|---------------|-----|-----|-----|-----|-----|------|------|------|------|------|
| Elevation (ft) | 895 | 950 | 1000 | 1025 | 1050 | 1075 | 1100 | 1150 | 1200 | 1220 |

The initial condition is Lake Mead at 1081.46 ft (observed December 2018), corresponding to approximately 12.0 MAF of storage.

#### S6.3 Shortage Tier Mapping

Bureau of Reclamation shortage tiers are determined by Lake Mead elevation:

| Tier | Elevation Threshold | Curtailment Ratio |
|------|--------------------|--------------------|
| 0 (Normal) | Mead >= 1075 ft | 0% |
| 1 | 1050 < Mead <= 1075 ft | 5% |
| 2 | 1025 < Mead <= 1050 ft | 10% |
| 3 (Severe) | Mead <= 1025 ft | 20% |

#### S6.4 Curtailment Application

Each agent's actual diversion in year *t* is determined by:

    diversion = min(request, water_right) * (1 - curtailment_ratio)

where `request` is the agent's demand decision and `curtailment_ratio` is set by the current shortage tier. Upper Basin agents face an additional pro-rata constraint when aggregate UB diversions exceed the binding constraint of min(NF - 7.0, 5.0) MAF.

#### S6.5 Bidirectional Feedback Loop

The mass balance creates a fully coupled human-water system with bidirectional feedback:

1. **Agents to reservoir**: Each agent selects a skill (increase, maintain, or decrease demand). The environment samples a magnitude from a persona-scaled Gaussian distribution and computes the new request. After curtailment, agent diversions aggregate into total Lower Basin and Upper Basin withdrawals, which enter the mass balance as outflow (LB) or as reduced Powell release (UB).

2. **Reservoir to agents**: Updated storage maps to a new Lake Mead elevation, which determines the shortage tier for the next year. Higher tiers trigger stronger curtailment ratios and activate governance rules that block increase skills (e.g., `curtailment_awareness` blocks increases when curtailment > 0; `demand_ceiling_stabilizer` blocks increases when total basin demand exceeds 6.0 MAF).

This coupling ensures that collective over-extraction lowers Lake Mead, triggering shortage tiers that curtail future diversions and constrain agent choices through governance, while collective conservation raises storage and relaxes constraints. The feedback operates with a one-year lag: diversions during year *t* determine storage at the start of year *t*+1.
