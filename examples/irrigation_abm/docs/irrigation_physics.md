# Irrigation Water System: Physics Reference

Detailed mass balance equations, variable definitions, storage-elevation curves, and CRSS comparison for the irrigation ABM. This supplements the main [README](../README.md) Section 4.

---

## Mass Balance Equations

All quantities in MAF (million acre-feet), annual resolution. Supply-side redesign (2026-09-25): deliveries are limited by what the two reservoirs can physically supply, as in Hung and Yang (2021), whose agents receive the diversion CRSS delivers. Lake Powell is a storage buffer: a pass-through release clamped to [7.0, 9.0] MAF subject to storage; not the full operating rules of the 2007 Interim Guidelines (no equalization or balancing release tiers, no Mead protection levels). The year's settlement, in order (`irrigation_env.py (IrrigationEnvironment._settle)`):

**1. Natural flow** (Lees Ferry long-term average 12 MAF; precipitation baseline 100 mm)

$$Q_{Nat} = 12 \times \frac{P_{winter}}{100}, \quad Q_{Nat} \in [6,\, 17] \;\text{MAF}$$

**2. Upper Basin delivery**: limited by the 5.0 MAF delivery capacity and by what leaves Lake Powell able to keep a 7.0 MAF release from inflow plus usable storage; shared pro-rata across Upper Basin agents

$$D_{UB} = \min\bigl(\textstyle\sum r_{UB},\; 5.0,\; Q_{Nat},\; \max(0,\; Q_{Nat} + (S_P - S_{P,dead}) - E_P - 7.0)\bigr)$$

A year with $Q_{Nat} < 7$ no longer zeroes the Upper Basin: storage covers the 7.0 MAF floor, and the Upper Basin is cut only when Powell's usable storage cannot.

**3. Lake Powell** (decision 2026-09-26, option e): the inflow $I_P = Q_{Nat} - D_{UB}$ is the pass-through, clamped to [7.0, 9.0] MAF subject to storage, and Powell holds wet-year surplus only until it is back at its 2019 level. Dry year ($I_P < 7.0$): storage above the dead pool tops the release up to 7.0 MAF, or the release is what is available. Normal year ($7.0 \le I_P \le 9.0$): the release is the pass-through, as in the pre-redesign physics. Wet year ($I_P > 9.0$): the excess over 9.0 MAF is kept in storage only up to the target storage $S_{target} = S_{P,dead} + f_{target}(S_{P,cap} - S_{P,dead})$; a Powell already at or above it (after the year's evaporation) passes the whole inflow through, a crude equalization. Storage above full pool spills into the release.

$$A_P = \max(0,\; I_P + S_P - S_{P,dead} - E_P), \qquad R = \begin{cases} \min(7.0,\; A_P) & I_P < 7.0 \\ \min(I_P,\; A_P) & 7.0 \le I_P \le 9.0 \\ \min\bigl(\max(9.0,\; \min(I_P,\; S_P + I_P - E_P - S_{target})),\; A_P\bigr) & I_P > 9.0 \end{cases} + spill_P$$

$$S_P(t+1) = S_P(t) + I_P - E_P - R$$

The two release bounds are TO VERIFY like the other Powell constants: 7.0 MAF is the minimum objective release (Long-Range Operating Criteria / 2007 Interim Guidelines); 9.0 MAF is a modelling ceiling motivated by the 2007 Interim Guidelines, under which releases above about 9.0 MAF occur only in balancing or equalization years (lower-elevation balancing can go to 9.5 MAF). $f_{target}$ = `powell_target_fill` (on [0, 1], default 0.42: the 1 January 2019 live fill, 10.10 / 24.32 MAF = 0.415, rounded; TO VERIFY) gives $S_{target}$ = 12.10 MAF total, about 0.11 MAF above the 11.99 MAF of 1 January 2019.

**4. Lake Mead withdrawals**: the declared shortage cut $\gamma_\tau$ applies to the whole Lower Basin consumptive use (agricultural agents and the 5.0 MAF non-agricultural bucket); Mexico per Minute 323

$$O = \Bigl(\textstyle\sum r_{LB} + D_{muni}\Bigr)(1 - \gamma_\tau) + M_{DCP}(h)$$

**5. Lake Mead availability**: withdrawals cannot exceed storage above the dead pool plus the year's inflow; when they would, every Lower Basin withdrawal is scaled by the same $\phi$

$$A = (S_M - 2.0) + R + 1.0 - E_M, \qquad \phi = \min(1,\; A / O)$$

$$S_M(t+1) = S_M(t) + R + 1.0 - E_M - \phi\, O, \qquad S_M \le 26.1 \text{ (excess spills below Hoover)}$$

The former $\pm 3.5$ MAF clamp on the annual Mead storage change is retired (Powell storage now does the buffering, and the clamp broke mass conservation). Both balances close exactly:

$$\Delta S_P + \Delta S_M = Q_{Nat} + 1.0 - D_{UB} - E_P - E_M - \phi\, O - spill_M$$

(`tests/test_irrigation_supply_side.py (TestMassBalance)` checks this for 3,000 random states.)

**6. Agent delivery** ($r_i$ = request, capped at the water right $w_i$)

$$d_i = r_i \times \frac{D_{UB}}{\sum r_{UB}} \;\;(\text{Upper Basin}), \qquad d_i = r_i\,(1 - \gamma_\tau)\,\phi \;\;(\text{Lower Basin})$$

Each agent also carries a `gap_reason` code (`none`, `ub_capacity`, `ub_powell_release`, `lb_shortage_tier`, `lb_mead_availability`, or the last two joined by `+`), which the prompt and memory text turn into a sentence.

### Auxiliary Equations

**Evaporation** (storage as a surface-area proxy; taken on the 1 January storage and never below a dead pool):

$$E_M(S) = 0.8 \times \max\!\left(0.15,\; \min\!\left(\frac{S}{13.0},\; 1.50\right)\right), \qquad E_P(S) = 0.70 \times \max\!\left(0.15,\; \min\!\left(\frac{S}{26.21},\; 1\right)\right)$$

### Lake Powell constants and sources

All four values are TO VERIFY against the USBR/USGS originals: they were read from search results and a machine text extraction of the 24-Month Study PDF, and the code review could not open the sources.

| Constant | Value | Source |
| :------- | :---- | :----- |
| Total capacity at full pool (3,700 ft) | 26.21 MAF | 1986 area-capacity table (used by USBR operations through 2019). USGS (2022), "Lake Powell's storage capacity updated for first time since 1986": 25.160 MAF in the 2018 survey, a 1.048 MAF loss since 1986 |
| Dead-pool storage (below 3,370 ft) | 1.89 MAF | 26.21 MAF total minus 24.322 MAF live capacity (USBR Glen Canyon Dam data, 1986 table); reported as "about 1.9 MAF" |
| Storage on 1 January 2019 | 11.99 MAF total (10.099 MAF live) | USBR Lower Colorado Region, January 2019 24-Month Study (Most Probable), Lake Powell table: end of December 2018, 3,581.85 ft, 10,099 thousand acre-ft live |
| Evaporation at full pool | 0.70 MAF/yr | Same study: 386 thousand acre-ft in water year 2018 at about 12.5 MAF mean live storage (0.55 of capacity), so 0.386 / 0.55 |
| Release floor | 7.0 MAF/yr | minimum objective release, Long-Range Operating Criteria / 2007 Interim Guidelines (existing constant); TO VERIFY |
| Release ceiling (wet year) | 9.0 MAF/yr | modelling ceiling motivated by the 2007 Interim Guidelines (releases above about 9.0 MAF only in balancing or equalization years); TO VERIFY |
| Target fill `powell_target_fill` (on [0, 1]) | 0.42 of live capacity (12.10 MAF total) | the 1 January 2019 live fill, 10.10 / 24.32 MAF = 0.415, rounded: Powell holds wet-year surplus only until it is back at its 2019 level; TO VERIFY |

The 2018 survey gives about 1 MAF less capacity than the 1986 table; the model uses the 1986 table because the Dec 2018 storage it starts from was reported on that table.

---

## Variable Definitions

| Symbol | Definition | Value / Unit |
| :----- | :--------- | :----------- |
| $S_M$, $S_P$ | Lake Mead, Lake Powell total storage (1 January) | MAF |
| $h$ | Lake Mead elevation (USBR storage-elevation curve) | ft |
| $Q_{Nat}$ | Natural flow at Lees Ferry | MAF/yr |
| $P_{winter}$ | UB winter precipitation (7-state average) | mm |
| $D_{UB}$ | Upper Basin delivered total | MAF/yr |
| $R$ | Powell release to Mead | MAF/yr |
| $O$ | Scheduled Lower Basin withdrawals from Mead (after the tier cut) | MAF/yr |
| $A$ | Water Mead can deliver this year | MAF/yr |
| $\phi$ | Physical delivery ratio at Mead | [0, 1] |
| $D_{muni}$ | Municipal/M&I demand (CAP + MWD + losses) | 5.0 MAF/yr |
| $M_{DCP}(h)$ | Mexico treaty delivery (elevation-dependent, Minute 323) | MAF/yr |
| $E_M$, $E_P$ | Reservoir evaporation (storage-dependent) | MAF/yr |
| $r_i$ | Agent $i$ request (post-governance, capped at $w_i$) | AF/yr |
| $w_i$ | Agent $i$ water right (see note below) | AF/yr |
| $\gamma_\tau$ | Lower Basin shortage cut for tier $\tau$ (0, 0.05, 0.10, 0.20) | [0, 1] |
| $d_i$ | Agent $i$ delivered water (`diversion` in the code and logs) | AF/yr |

F10 (2026-09-25 audit): $w_i$ is `col.iloc[-1]` of that agent's
`Div_States/*_discrete_states.csv`, the TOP of the discretised FQL
diversion grid (Hung & Yang's `Div_max`), not a legal Colorado River
entitlement. Initial requests come from 2018 diversions, and most
agents' 2018 use sits well under that grid-top ceiling: 61 of 78 agents
(52 of 56 Upper Basin) start below 50% utilisation. See
`irrigation_personas.py:create_profiles_from_data`.

---

## Implementation Pseudocode

From `irrigation_env.py (IrrigationEnvironment.advance_year, settle_year, _settle)` and `run_experiment.py (IrrigationLifecycleHooks.post_year)`:

```text
advance_year(t)                          [before any agent decides]
  |-- 1. commit settlement(t-1): end storages -> 1 January storages of t
  |        (settles now at the final requests if settle_year() was never called)
  |-- 2. _generate_precipitation()          <- P_winter from CRSS PRISM (UB 7-state avg)
  |        Q_Nat = 12.0 * (P / 100)          [bounded 6-17 MAF]
  |-- 3. h(t) = elevation(S_M on 1 January) <- appended to the Mead history
  |-- 4. _update_preceding_factors(), _compute_drought_index()
  |-- 5. _apply_curtailment()               <- shortage tier from h(t); gamma on LB agents, 0 on UB
  |-- 6. freeze the 1 January snapshot; PROVISIONAL _settle() at the carried requests
  |        -> each agent's expected delivery, delivery_ratio, gap_reason
  +-- 7. total_basin_demand, basin_request_over_target (= total / 5.86 MAF)
decisions                                 execute_skill -> update_agent_request
post_year(t) -> settle_year()             FINAL _settle() at this year's requests, from the
                                          frozen snapshot; idempotent; not committed until t+1
```

---

## Action Model (Hung and Yang 2021)

The agent's decision changes its diversion REQUEST; the water balance above decides what it receives. The size of the change follows `ref/RL-ABM-CRSS/ABM_CRSS_coupling.py (Q_learning)` (2026-09-26):

$$\Delta r_i = \pm\,(\mu_i + |z|)\, b_i, \qquad z \sim N(0, \sigma_i)$$

- $\mu_i, \sigma_i$: agent $i$'s calibrated parameters (`ALL_colorado_ABM_params_cal_1108.csv`, rows `mu`, `sigma`); data, not tunables.
- $b_i$: the step of agent $i$'s discretised diversion grid, `agt_states[2] - agt_states[1]` of `Div_States/*_discrete_states.csv` (acre-ft); data.
- The LLM picks the sign and the class. Small: $|z| \le 0.6745\,\sigma_i$ (the half-normal median), so $\Delta \le T_i = (\mu_i + 0.6745\,\sigma_i)\,b_i$. Large: $|z| > 0.6745\,\sigma_i$. The two classes are the halves of one H&Y distribution; `hy_step_af` draws $|z|$ by inverse CDF from one uniform of the per-(seed, year, agent, skill) stream.
- Bounds: $r_i \le w_i$ (water right), and a decrease never goes below $\min(0.1\,w_i, r_i)$ (minimum use). No taper, no magnitude exploration (H&Y explore over direction only).
- Fallbacks (mock runs only): $b = w/25$ whenever a profile has no grid step; $\mu = 0.218$, $\sigma = 0.923$ (CSV medians) when the environment builds agents itself; synthetic profiles from the runners keep their cluster-centroid $\mu, \sigma$.

---

## Mexico DCP Reductions (Minute 323)

When Lake Mead elevation drops, Mexico voluntarily reduces delivery:

| Mead Elevation | Mexico Reduction | Effective Delivery |
| :------------- | :--------------- | :----------------- |
| >= 1090 ft | 0 | 1.500 MAF |
| 1075-1090 ft | 0.041 MAF | 1.459 MAF |
| 1050-1075 ft | 0.080 MAF | 1.420 MAF |
| 1025-1050 ft | 0.104 MAF | 1.396 MAF |
| < 1025 ft | 0.275 MAF | 1.225 MAF |

---

## Storage-Elevation Curve

Lake Mead storage-to-elevation is interpolated from the USBR 2009 area-capacity survey (9 control points hardcoded in `irrigation_env.py` as `_STORAGE_MAF` and `_ELEVATION_FT`).

---

## Agent-Reservoir Feedback Loop

```mermaid
flowchart LR
    subgraph P1 ["Phase 1: advance_year(t)"]
        direction TB
        A0["Commit settlement t-1"] --> H["1 January storages S_P, S_M"]
        A["P(t) precipitation"] --> B["Natural flow"]
        H --> I["Mead level h(t), shortage tier"]
        I --> J["Provisional settlement: expected delivery"]
        B --> J
    end

    subgraph P3 ["Phase 2: per agent"]
        direction TB
        K["Build prompt"] --> L["LLM reasoning"]
        L --> M["Governance"]
        M --> N["Execute skill: request r_i(t)"]
    end

    subgraph P4 ["Phase 3: post_year(t)"]
        direction TB
        O["settle_year: final deliveries d_i(t), end storages"]
    end

    J --> K
    N --> O
    O -.->|"end storages -> 1 January t+1"| A0

    style P1 fill:#fff3e0
    style P3 fill:#e3f2fd
    style P4 fill:#fce4ec
```

| Step | Equation | Constants |
| :--- | :------- | :-------- |
| 1 Natural flow | $Q_{Nat} = 12 \times P_{winter}/100$ | bounded [6, 17] MAF |
| 2 Upper Basin delivery | $D_{UB} = \min(\sum r_{UB}, 5.0, Q_{Nat}, \max(0, Q_{Nat} + S_P - S_{P,dead} - E_P - 7.0))$ | pro-rata |
| 3 Powell | $S_P' = S_P + Q_{Nat} - D_{UB} - E_P - R$; $R$ = pass-through $Q_{Nat} - D_{UB}$ clamped to [7.0, 9.0] MAF (dry-year top-up from storage; wet-year excess kept only up to the target fill, 12.10 MAF), capped so storage stays at or above the dead pool | dead pool 1.89, capacity 26.21 MAF, target fill 0.42 |
| 4 Mead withdrawals | $O = (\sum r_{LB} + 5.0)(1 - \gamma_\tau) + M_{DCP}(h)$ | tier cut on the whole Lower Basin |
| 5 Mead | $S_M' = S_M + R + 1.0 - E_M - \phi O$, $\phi = \min(1, A/O)$ | $S_M \in [2.0, 26.1]$ |
| 6 Delivery | $d_i = r_i D_{UB}/\sum r_{UB}$ (UB), $r_i(1-\gamma_\tau)\phi$ (LB) | |

**Feedback loop**: Over-extraction lowers Mead, a lower 1 January level declares a higher tier, the Lower Basin cut grows and Lower Basin increases are blocked, requests level off or fall, Mead recovers, the tier drops. Requests made in year $t$ are settled in year $t$; their effect on storage is seen by agents on 1 January of $t+1$.

---

## Comparison with Full CRSS

| Aspect | Our Model | Full CRSS |
| :----- | :-------- | :-------- |
| Temporal resolution | Annual | Monthly |
| Spatial resolution | 2 basins (UB/LB) | 3,700+ objects |
| Reservoir model | Powell and Mead storage stocks | Powell + Mead + Flaming Gorge + ... |
| Operating rules | Powell pass-through release clamped to [7.0, 9.0] MAF, wet-year retention only up to the 2019 fill; Mead shortage tiers (simplified DCP) | Full Interim Guidelines + DCP + Minute 323 |
| Demand model | 78 LLM agents | Exogenous demand schedules |
| Precipitation | CRSS PRISM (real) | CRSS PRISM (same source) |
| Natural flow | Scaled by precip | Full hydrologic routing |
| Agent feedback | Bidirectional | None (exogenous demand) |

**Key advantage**: Bidirectional coupling (agent demand <-> reservoir state) enables studying how governance rules affect collective demand trajectories, something standard CRSS cannot do because it uses fixed exogenous demand schedules.

---

## Two-Reservoir Simplification (what is and is not modelled)

Before the 2026-09-25 supply-side redesign the model tracked Lake Mead only: the Powell release was natural flow minus Upper Basin use, the 7.0 MAF minimum release was enforced by capping Upper Basin use at $\max(0, Q_{Nat} - 7)$ (so every Upper Basin agent received 0 in a 6.0 MAF year such as 2022, audit finding F11), and a $\pm 3.5$ MAF clamp on the annual Mead storage change stood in for Glen Canyon buffering. F11b (same day) made that cap survive each agent's own decision by re-applying it once after the decision loop.

The redesign keeps the F11b pattern (one idempotent settlement after the decision loop, rebuilt from requests and a frozen 1 January snapshot) and replaces the physics:

* Lake Powell is a storage stock between 1.89 MAF (dead pool) and 26.21 MAF (full pool), starting from the USBR end-of-2018 storage. It passes its inflow through to Mead within [7.0, 9.0] MAF: below 7.0 MAF storage above the dead pool tops the release up (or it releases what is available); above 9.0 MAF it releases 9.0 and keeps the excess, but only until it is back at its 2019 fill (above that it passes the whole inflow through). It spills above full pool.
* Upper Basin use is cut only when Powell's usable storage cannot cover the 7.0 MAF floor, and then pro-rata, not to zero.
* Lake Mead deliveries cannot exceed its usable storage plus inflow; when they would, all Lower Basin withdrawals are scaled pro-rata.
* Mead shortage tiers apply to the Lower Basin only (Law of the River), to the whole Lower Basin consumptive use including the 5.0 MAF non-agricultural bucket.
* The $\pm 3.5$ MAF clamp is retired; mass balance closes.

Not modelled, on purpose (simplification to disclose): the Interim Guidelines Powell release tiers (equalization, upper and mid elevation balancing, 7.48 / 8.23 MAF releases), Lake Mead protection levels, Drought Response Operations, and Flaming Gorge.

**Consequence to disclose (measured 2026-09-26, 42 years on the CRSS PRISM series).** Old = the pre-redesign Mead-only balance (fcd74a5f). The redesign went through four Powell release rules: pinned at 7.0 MAF (fe72e43f), pass-through with a 7.0 MAF floor (option c, dc503b5d), pass-through clamped to [7.0, 9.0] MAF (option d, 56c33faf), and the current one, option (e): the same band with wet-year retention only up to the 2019 fill.

2018 requests held fixed:

| Physics | Years at Tier 2 or 3 | Mean 1 January Mead | Minimum | 2020 tier | Powell end-of-year min / max | Powell first at dead pool | Upper Basin cut years | Powell spill years |
| :------ | :------------------- | :------------------ | :------ | :-------- | :--------------------------- | :------------------------ | :-------------------- | :----------------- |
| Old (Mead only) | 3 of 42 | 1121 ft | 1006 ft | 1 (end-of-year series, one year earlier than the 1 January series) | n/a | n/a | 20 | n/a |
| Release pinned at 7.0 MAF | 24 of 42 | 1053 ft | 1016 ft | 1 | up to 26.21 MAF (full by 2029) | never | 0 | 9 |
| Option (c): pass-through, 7.0 MAF floor | 3 of 42 | 1132 ft | 1026 ft | 0 | 1.89 / 11.67 MAF | 2031 | 14 | 0 |
| Option (d): clamped to [7.0, 9.0] MAF | 17 of 42 | 1053 ft | 1017 ft | 0 | 3.41 / 26.21 MAF | never | 0 | 2 |
| Option (e) (current) | 6 of 42 | 1081 ft | 1021 ft | 0 | 3.38 / 12.10 MAF | never | 0 | 0 |

Full water-right requests: old 40 of 42 years at Tier 2 or 3 (mean 976 ft), option (c) 39 (996 ft), options (d) and (e) 41 (960 ft); Mead reaches its dead pool (895 ft) and Powell its dead pool in 2022 under every redesign variant.

Reading. Option (c) matched the old physics on Mead but let Powell drain for good; option (d) refilled Powell to capacity at Mead's expense. Option (e) sits between them: Powell never reaches its dead pool, oscillates below its 2019 level (end-of-year mean 9.6 MAF, median 11.1 MAF, within 1 MAF of the 12.10 MAF target in 21 of 42 years, retaining in all 17 wet years), no Upper Basin cuts and no spills. The cost is on Mead: 6 of 42 years at Tier 2 or 3 and a mean of 1081 ft, below the old physics (3, 1121 ft), because Powell spends much of the run below its target and keeps every wet-year surplus while it refills.

### Initial State: Mead 1081.46 ft, Powell 11.99 MAF (1 January 2019)

Lake Mead starts at 1081.46 ft, the USBR-observed elevation at the end of December 2018 (Y1 = calendar year 2019), which places loop year 1 in Tier 0. The Mead elevation history is a 1 January series seeded with 1082.52 ft (1 January 2018), so loop year 1's rising/declining flag compares 1081.46 ft against 1082.52 ft. Lake Powell starts at 11.99 MAF total (10.099 MAF live, 3,581.85 ft), from the January 2019 24-Month Study.

---

## Data Sources

| Data | Source | File |
| :--- | :----- | :--- |
| Winter precipitation (2017-2060) | CRSS/PRISM NOAA projection | `ref/CRSS_DB/CRSS_DB/HistoricalData/PrismWinterPrecip_ST_NOAA_Future.csv` |
| Agent water rights (78 agents) | Top of each agent's discretised FQL diversion grid (Hung & Yang's `Div_max`); not a legal entitlement, see the F10 note above | `ref/CRSS_DB/CRSS_DB/Div_States/UB_discrete_states.csv`, `.../LB_discrete_states.csv` |
| Historical UB depletion | CRSS (2018 baseline) | `ref/CRSS_DB/CRSS_DB/HistoricalData/UB_historical_annual_depletion.csv` |
| Historical LB diversion | CRSS (2018 baseline) | `ref/CRSS_DB/CRSS_DB/HistoricalData/LB_historical_annual_diversion.csv` |
| Lake Mead storage-elevation | USBR 2009 area-capacity survey | Hardcoded in `irrigation_env.py` (`_STORAGE_MAF`, `_ELEVATION_FT`) |
| Lake Powell capacity, dead pool, 1 January 2019 storage, evaporation | USGS (2022) capacity release; USBR January 2019 24-Month Study | `WaterSystemConfig` (see the Lake Powell constants table above) |
| FQL calibrated parameters | Hung & Yang (2021) Table 2 | Embedded in `config/agent_types.yaml` under `fql_reference` |

**Precipitation as sole exogenous forcing**: The PRISM CSV contains annual winter precipitation projections for 9 Upper Basin state-groups (WY, UT1-3, NM, CO1-3, AZ), generated by CRSS via bootstrapping from the 1906-2018 historical PRISM/NOAA record. Values are in inches, converted to mm (*25.4) at load time. The UB 7-state average drives the natural flow calculation (Eq. 1). All other quantities are computed endogenously.
