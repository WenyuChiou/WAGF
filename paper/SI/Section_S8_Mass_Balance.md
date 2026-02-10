# S8. Mass Balance and Human-Water Coupling

The irrigation ABM couples agent demand decisions to reservoir dynamics through a surrogate mass balance model for Lake Mead that mirrors the core physics of CRSS/RiverWare at annual resolution. This section documents the equations, parameter values, and design justifications implemented in the simulation environment (`irrigation_env.py`).

## S8.1 Single-Reservoir Justification

The Colorado River system has two major reservoirs — Lake Powell (upstream, Glen Canyon Dam) and Lake Mead (downstream, Hoover Dam) — but the model tracks only Lake Mead storage and elevation explicitly. This is justified for three reasons:

1. **Lake Mead is the decision-relevant reservoir.** All DCP shortage tiers, curtailment ratios, and Mexico treaty reductions are triggered by Lake Mead elevation. Lake Powell's operational role is to regulate releases to Lake Mead, which the model captures through the Powell minimum release constraint ($Q_{\min} = 7.0$ MAF/yr, Eq. 5) and the Upper Basin infrastructure ceiling ($C_{\text{infra}} = 5.0$ MAF/yr). Tracking Powell storage separately would not add information to the agent decision process.

2. **Powell is implicitly represented.** The effective UB diversion equation (Eq. 5: $D_{\text{UB,eff}} = \min(D_{\text{UB}}, Q_{\text{nat}} - Q_{\min}, C_{\text{infra}})$) encodes Powell's three operational constraints: (a) the 7.0 MAF/yr DCP minimum release floor ensuring downstream delivery, (b) the physical limit that UB cannot divert more than what flows in, and (c) the 5.0 MAF/yr infrastructure capacity ceiling. These constraints capture Powell's buffering role without requiring a separate storage state variable.

3. **Hung & Yang (2021) uses the same approach.** Their FQL model also uses a reduced-form mass balance with CRSS inputs rather than independent Powell modeling. Both studies focus on agent-reservoir feedback at the demand decision point, not on multi-reservoir operations.

The model omits monthly temporal resolution, multi-reservoir operations (Powell, Flaming Gorge, Blue Mesa), detailed hydrologic routing, return flows and groundwater interactions, and prior appropriation doctrine (all agents face uniform curtailment). These omissions are acceptable because the study examines how governance rules affect collective demand adaptation trajectories over 42 years — a process that operates at annual decision cycles.

## S8.2 Initial Condition

The simulation initializes Lake Mead at **1081.46 ft**, the USBR-observed elevation as of December 2018 — the year before the simulation begins (Y1 = calendar year 2019). This places the initial condition in Tier 0 (above the 1075 ft threshold), matching real-world conditions. The code also pre-seeds the elevation history with 2017 (1082.52 ft) and 2018 (1081.46 ft) values for the preceding-factor computation that requires a 2-year lookback.

During the cold-start transient (Y1-5), rapid demand adjustments by zero-memory agents cause Lake Mead to decline to the ~1050 ft range before stabilizing. The cold-start mean demand is 4.76 MAF with CoV = 11.4%, compared to steady-state (Y6-42) mean demand of 6.02 MAF with CoV = 5.3%. This initial decline reflects the learning dynamics of agents discovering equilibrium demand levels from scratch, not an artifact of the starting elevation.

## S8.3 Annual Mass Balance Equations

All quantities are in MAF (million acre-feet) at annual resolution.

**Storage update** — the core equation governing Lake Mead:

$$S(t+1) = S(t) + \text{clamp}\bigl(Q_{\text{in}}(t) - Q_{\text{out}}(t),\; -\Delta_{\max},\; +\Delta_{\max}\bigr) \qquad \text{(Eq.\ 1)}$$

where $S \in [2.0,\, 26.1]$ MAF (dead-pool to full-pool physical bounds) and $\Delta_{\max} = 3.5$ MAF (Glen Canyon Dam operational buffering).

**Inflow and outflow:**

$$Q_{\text{in}} = Q_{\text{Powell}} + Q_{\text{trib}} \qquad \text{(Eq.\ 2)}$$

$$Q_{\text{out}} = D_{\text{LB}} + M(h) + E(S) + D_{\text{muni}} \qquad \text{(Eq.\ 3)}$$

where $Q_{\text{trib}} = 1.0$ MAF/yr (Lower Basin tributary inflow: Virgin River, Little Colorado, Bill Williams) and $D_{\text{muni}} = 5.0$ MAF/yr (municipal and industrial demands, tribal, Central Arizona Project, and system losses).

**Powell release** — constrained by minimum release floor and UB infrastructure:

$$Q_{\text{Powell}} = Q_{\text{nat}} - D_{\text{UB,eff}} \qquad \text{(Eq.\ 4)}$$

$$D_{\text{UB,eff}} = \min\bigl(D_{\text{UB}},\; Q_{\text{nat}} - Q_{\min},\; C_{\text{infra}}\bigr) \qquad \text{(Eq.\ 5)}$$

where $Q_{\min} = 7.0$ MAF/yr (DCP minimum Powell release floor, USBR 2019) and $C_{\text{infra}} = 5.0$ MAF/yr (historical Upper Basin depletion capacity).

**Natural flow** — driven by CRSS PRISM precipitation:

$$Q_{\text{nat}} = Q_{\text{base}} \times \frac{P}{P_0}, \quad Q_{\text{nat}} \in [6,\, 17] \;\text{MAF} \qquad \text{(Eq.\ 6)}$$

where $Q_{\text{base}} = 12.0$ MAF/yr (historical natural flow baseline) and $P_0 = 100$ mm (UB winter precipitation baseline).

**Evaporation** — scales with storage as a surface-area proxy:

$$E(S) = E_{\text{ref}} \times \text{clamp}\!\left(\frac{S}{S_{\text{ref}}},\; 0.15,\; 1.50\right) \qquad \text{(Eq.\ 7)}$$

where $E_{\text{ref}} = 0.8$ MAF/yr and $S_{\text{ref}} = 13.0$ MAF (reference storage at approximately 1100 ft elevation). This simplified evaporation proxy is calibrated to match USBR published estimates of 0.6–1.0 MAF/yr for Lake Mead; no independent validation source exists.

**Agent diversion** — links agent decisions to mass balance:

$$d_i(t) = \min\bigl(r_i(t),\; w_i\bigr) \times \bigl(1 - \gamma_{\tau}\bigr) \qquad \text{(Eq.\ 8)}$$

where $r_i$ is agent $i$'s demand request (set by skill execution), $w_i$ is the legal water right, and $\gamma_{\tau}$ is the curtailment ratio for shortage tier $\tau$. Basin-level diversions aggregate over agents:

$$D_{\text{LB}} = \sum_{i \in \text{LB}} d_i, \qquad D_{\text{UB}} = \sum_{i \in \text{UB}} d_i \qquad \text{(Eq.\ 9)}$$

Upper Basin agents face an additional pro-rata constraint when aggregate UB diversions exceed the binding constraint of $\min(Q_{\text{nat}} - Q_{\min},\; C_{\text{infra}})$ MAF.

## S8.4 Variable Definitions

| Symbol | Definition | Value / Unit |
|--------|-----------|-------------|
| $S$ | Lake Mead storage | MAF |
| $h$ | Lake Mead elevation (from USBR storage-elevation curve) | ft |
| $Q_{\text{in}}$ | Total Mead inflow | MAF/yr |
| $Q_{\text{out}}$ | Total Mead outflow | MAF/yr |
| $Q_{\text{Powell}}$ | Powell release to Mead | MAF/yr |
| $Q_{\text{nat}}$ | Natural flow at Lee Ferry | MAF/yr |
| $Q_{\text{trib}}$ | LB tributary inflow | 1.0 MAF/yr |
| $Q_{\text{base}}$ | Natural flow baseline | 12.0 MAF/yr |
| $Q_{\min}$ | Minimum Powell release (DCP floor) | 7.0 MAF/yr |
| $D_{\text{UB}}$ | Upper Basin diversions (sum of UB agent diversions) | MAF/yr |
| $D_{\text{UB,eff}}$ | Effective UB diversions (constrained) | MAF/yr |
| $D_{\text{LB}}$ | Lower Basin diversions (sum of LB agent diversions) | MAF/yr |
| $D_{\text{muni}}$ | Municipal/M&I demand | 5.0 MAF/yr |
| $C_{\text{infra}}$ | UB infrastructure ceiling | 5.0 MAF/yr |
| $M(h)$ | Mexico treaty delivery (elevation-dependent) | MAF/yr |
| $E(S)$ | Reservoir evaporation (storage-dependent) | MAF/yr |
| $E_{\text{ref}}$ | Reference evaporation at $S_{\text{ref}}$ | 0.8 MAF/yr |
| $S_{\text{ref}}$ | Reference storage | 13.0 MAF |
| $P$ | UB winter precipitation (7-state average) | mm |
| $P_0$ | Precipitation baseline | 100 mm |
| $\Delta_{\max}$ | Max annual storage change | 3.5 MAF |
| $r_i$ | Agent $i$ demand request | AF/yr |
| $w_i$ | Agent $i$ legal water right | AF/yr |
| $\gamma_{\tau}$ | Curtailment ratio for shortage tier $\tau$ | dimensionless |
| $d_i$ | Agent $i$ actual diversion | AF/yr |

## S8.5 Elevation-Storage Relationship

Lake Mead elevation (ft above sea level) is converted to and from storage (MAF) via linear interpolation of the USBR empirical curve:

| Storage (MAF) | 2.0 | 3.6 | 5.8 | 8.0 | 9.5 | 11.0 | 13.0 | 17.5 | 23.3 | 26.1 |
|---------------|-----|-----|-----|-----|-----|------|------|------|------|------|
| Elevation (ft) | 895 | 950 | 1000 | 1025 | 1050 | 1075 | 1100 | 1150 | 1200 | 1220 |

## S8.6 Shortage Tier Mapping

Bureau of Reclamation shortage tiers are determined by Lake Mead elevation:

| Tier | Elevation Threshold | Curtailment Ratio |
|------|--------------------|--------------------|
| 0 (Normal) | Mead $\geq$ 1075 ft | 0% |
| 1 | 1050 < Mead $\leq$ 1075 ft | 5% |
| 2 | 1025 < Mead $\leq$ 1050 ft | 10% |
| 3 (Severe) | Mead $\leq$ 1025 ft | 20% |

Production results (v20, 78 agents × 42 years): Tier 0 in 30 years, Tier 1 in 5 years, Tier 2 in 2 years, Tier 3 in 5 years. Lake Mead elevation range: 1003.1–1178.7 ft.

## S8.7 Mexico DCP Reductions

Mexico treaty deliveries follow Minute 323 tiered reductions (IBWC, 2017):

| Lake Mead Elevation | Base Delivery (MAF/yr) | Reduction (MAF/yr) |
|---------------------|----------------------|---------------------|
| $\geq$ 1090 ft | 1.500 | 0 |
| 1075–1090 ft | 1.459 | 0.041 |
| 1050–1075 ft | 1.375 | 0.125 |
| 1025–1050 ft | 1.250 | 0.250 |
| $\leq$ 1025 ft | 1.225 | 0.275 |

## S8.8 Bidirectional Feedback Loop

The mass balance creates a fully coupled human-water system with bidirectional feedback, consistent with the socio-hydrology framework (Sivapalan et al., 2012). Agent appraisal constructs (Water Scarcity Assessment, Adaptive Capacity Assessment) follow the cognitive appraisal framework of Lazarus and Folkman (1984), implemented as categorical labels (VL/L/M/H/VH).

1. **Agents to reservoir**: Each agent selects a skill (increase_large, increase_small, maintain_demand, decrease_small, or decrease_large). The environment samples a magnitude from a persona-scaled Gaussian distribution (Section S7) and computes the new request. After curtailment (Eq. 8), agent diversions aggregate into total Lower Basin and Upper Basin withdrawals (Eq. 9), which enter the mass balance as outflow ($D_{\text{LB}}$) or as reduced Powell release ($D_{\text{UB,eff}}$, Eq. 5).

2. **Reservoir to agents**: Updated storage maps to a new Lake Mead elevation via the USBR curve (S8.5), which determines the shortage tier for the next year (S8.6). Higher tiers trigger stronger curtailment ratios and activate governance rules that block increase skills (e.g., `curtailment_awareness` blocks increases when curtailment > 0; `demand_ceiling_stabilizer` blocks increases when total basin demand exceeds 6.0 MAF; see Section S6).

This coupling ensures that collective over-extraction lowers Lake Mead, triggering shortage tiers that curtail future diversions and constrain agent choices through governance, while collective conservation raises storage and relaxes constraints. The feedback operates with a one-year lag: diversions during year $t$ determine storage at the start of year $t+1$.

## S8.9 Data Sources

| Data | Source | File |
|------|--------|------|
| Winter precipitation (2017-2060) | CRSS/PRISM NOAA projection | `PrismWinterPrecip_ST_NOAA_Future.csv` |
| Agent water rights (78 agents) | CRSS annual baseline time series | `annual_baseline_time_series.csv` |
| Lake Mead storage-elevation curve | USBR area-capacity tables | Hardcoded in `irrigation_env.py` |
| Initial Lake Mead elevation | USBR observed (Dec 2018) | 1081.46 ft |

Precipitation is the sole exogenous climate forcing. All other quantities — natural flow, Lake Mead level, shortage tiers, curtailment ratios — are computed endogenously by the mass balance model. This matches the approach in Hung and Yang (2021).

## References

Hung, W.-C., & Yang, Y. C. E. (2021). Learning to allocate: Managing water in the Colorado River Basin under deep uncertainty. *Water Resources Research*, 57(11), e2020WR029537.

IBWC. (2017). Minute 323: Extension of cooperative measures and adoption of a binational water scarcity contingency plan in the Colorado River Basin. International Boundary and Water Commission.

Lazarus, R. S., & Folkman, S. (1984). *Stress, appraisal, and coping*. Springer.

Sivapalan, M., Savenije, H. H. G., & Blöschl, G. (2012). Socio-hydrology: A new science of people and water. *Hydrological Processes*, 26(8), 1270-1276.

USBR. (2019). Colorado River Basin Drought Contingency Plans. U.S. Bureau of Reclamation.
