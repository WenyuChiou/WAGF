# Irrigation ABM Data Files Dictionary (`examples/irrigation_abm/data/`)

Committed CSV inputs for the Colorado River Basin irrigation ABM (`irrigation_env.py`, `hindcast_env.py`). Most v3 tables are SHA-256 checksum-pinned at load time and can be regenerated/verified with [../tools/build_v3_data.py](../tools/build_v3_data.py).

Unless noted otherwise, volumes are in **acre-feet (`af`)** (`1 MAF = 1,000,000 AF`) and elevations are in **feet above mean sea level (`ft`)**.

## Projection Inputs (2019–2060)

| File | Key Columns | Units / Meaning |
|---|---|---|
| `hydrology_v3.csv` | `sim_year`, `source_calendar_year`, `lees_ferry_cy_natural_flow_af`, `lees_ferry_to_below_hoover_cy_intervening_af` | Basin natural flow time series (`af/yr`) mapping simulation years `2019–2060` to historical USBR calendar years |
| `mead_capacity_usbr2009_1ft.csv` | `elevation_ft`, `available_capacity_above_895ft_af` | 2009 USBR 1-ft Lake Mead elevation-storage lookup (`895–1,229 ft`; dead-pool offset above `895 ft` in `af`) |
| `lb_priority_split_v3.csv` | `agent_id`, `water_right_af`, `senior_entitlement_af`, `junior_entitlement_af`, `p56_entitlement_af`, `basis`, `priority_classes`, `source` | Lower Basin 22 agricultural agents' published USBR priority splits (`af/yr`; `junior_entitlement_af = 0` for single-class agents) |
| `ub_subbasin_envelope_v3.csv` | `subbasin`, `gauges`, `c_s`, `binding_year`, `runner_up_year`, `runner_up_c_s`, `q_s_mean_1971_2018_af` | Per-subbasin (`WY`, `UT1`–`UT3`, `NM`, `CO1`–`CO3`, `AZ`) empirical envelope coefficient `c_s`, USGS gauges, and 1971–2018 mean flow (`af`) |
| `ub_subbasin_supply_v3.csv` | `sim_year`, `source_calendar_year`, `q_<S>_af`, `a_<S>_af` | Default Upper Basin annual subbasin natural flow `q_<S>_af` and depletion `a_<S>_af` (`af/yr`) across the 9 subbasins |
| `ub_subbasin_supply_v3_rho02.csv` | Same as `ub_subbasin_supply_v3.csv` | Sensitivity variant (`rho_0_2`) |
| `ub_subbasin_supply_v3_lees_ferry_all.csv` | Same as `ub_subbasin_supply_v3.csv` | Sensitivity variant (`lees_ferry_all`) |
| `ub_subbasin_supply_v3_tributary.csv` | Same as `ub_subbasin_supply_v3.csv` | Sensitivity variant (`tributary_gauges`) |
| `ub_subbasin_variant_means_v3.csv` | `variant`, `q_<S>_mean_af` | 1971–2018 baseline mean flow (`af/yr`) per subbasin for each variant |

## Historical Hindcast Inputs (observed 1999–2018, precipitation 1998–2018)

| File | Key Columns | Units / Meaning |
|---|---|---|
| `hindcast_observed_v3.csv` | `year`, `mead_elev_ft_eoy`, `mead_live_af_eoy_usbr`, `powell_elev_ft_eoy`, `powell_live_af_eoy`, `lees_ferry_release_af`, `lees_ferry_natural_af`, `intervening_natural_af`, `q_<S>_af`, `a_<S>_af` | End-of-year observed reservoir elevations (`ft`), live storages (`af`), releases, natural flows, and subbasin flows/depletions (`af/yr`) |
| `hindcast_observed_v3_sources.csv` | `column`, `unit`, `date_convention`, `source`, `query_or_location`, `retrieved` | Column-level provenance, date conventions, and USBR source URLs for `hindcast_observed_v3.csv` |
| `hindcast_precip_v3.csv` | `<year>`, `WY`, `UT1`, `UT2`, `UT3`, `NM`, `CO1`, `CO2`, `CO3`, `AZ` | Annual winter precipitation (`inches`) per subbasin (`1998–2018`) |
