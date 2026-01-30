# Data Inventory for Task-060: CRSS Database

**Extracted Data Location:** `ref/CRSS_DB/CRSS_DB/`

## Extracted Files and Folders:

*   **`all_st/`**: Contains time series for Per-agent Depletion (`_Dep_req.txt`) and Diversion (`_Div_req.txt`). Includes `ABM_Div/` for agent-level diversion.
*   **`Div_States/`**: Contains discrete state definitions for UB and LB agents (`UB_discrete_states.csv`, `LB_discrete_states.csv`, `States_dict_all_st.csv`), and CRSS 2018 agent lists.
*   **`Group_Agt/`**: Contains Group-to-Agent mappings (`UB_ABM_Groups_and_Agents.csv`, `LB_agents.csv`, and within-group CSVs).
*   **`HistoricalData/`**: Contains historical data:
    *   Lake Mead Elevation (monthly, 1935-2018): `Lake_Mead_Historical_WaterLevels.csv`
    *   LB historical diversion (annual): `LB_historical_annual_diversion.csv`
    *   Winter Precipitation (PRISM NOAA, 1905-2018): `PrismWinterPrecip_NOAA_Winter_1905-2018.csv`
    *   CRB depletion time series.
*   **`Initial_Files/`**: Contains Q-table initializations in sub-folders like `All/`, `All_SA/`, `All_UA/`, `All-WRR/`.
*   **`LB_Baseline_DB/`**: Contains Lower Basin baseline depletion/diversion per agent.
*   **`Within_Group_Div/`**: Contains monthly/annual diversion by state group (AZ, CO1-3, NM, UT1-3, WY).
*   **`RW-AgAgent-Obs Water Diversion-20200414.xlsx`**: Excel file for water diversion observations.
*   **`RW-AgAgent-Obs Water Diversion-revised_20200608xlsx.xlsx`**: Revised version of the above Excel file.

## Mapping to Paper's Key Data Files:

*   **Lake Mead Elevation**: `HistoricalData/Lake_Mead_Historical_WaterLevels.csv` (monthly 1935-2018)
*   **Winter Precipitation**: `HistoricalData/PrismWinterPrecip_NOAA_Winter_1905-2018.csv` (8 stations, 1905-2018)
*   **UB Agent Diversions**: `Div_States/CRSS_2018_UB_Div_agts.csv` (58 UB agent water rights)
*   **LB Historical Diversion**: `HistoricalData/LB_historical_annual_diversion.csv`
*   **Agent Groups**: `Group_Agt/UB_ABM_Groups_and_Agents.csv`, `Group_Agt/LB_agents.csv`
*   **Discrete States**: `Div_States/UB_discrete_states.csv`, `Div_States/LB_discrete_states.csv`
*   **Q-Table Init**: `Initial_Files/All-WRR/` (paper final version)
*   **Observed Water Diversion**: `RW-AgAgent-Obs Water Diversion-20200414.xlsx`, `RW-AgAgent-Obs Water Diversion-revised_20200608xlsx.xlsx`

## Files Needed for LLM Experiment vs. FQL Baseline:

*   **Likely needed for both LLM Experiment and FQL Baseline**:
    *   `HistoricalData/Lake_Mead_Historical_WaterLevels.csv`
    *   `HistoricalData/PrismWinterPrecip_NOAA_Winter_1905-2018.csv`
    *   `Div_States/CRSS_2018_UB_Div_agts.csv`
    *   `HistoricalData/LB_historical_annual_diversion.csv`
    *   `Group_Agt/UB_ABM_Groups_and_Agents.csv`
    *   `Group_Agt/LB_agents.csv`
    *   `Div_States/UB_discrete_states.csv`
    *   `Div_States/LB_discrete_states.csv`
    *   `RW-AgAgent-Obs Water Diversion-20200414.xlsx`
    *   `RW-AgAgent-Obs Water Diversion-revised_20200608xlsx.xlsx`
    *   Contents of `all_st/`, `LB_Baseline_DB/`, `Within_Group_Div/` folders.

*   **Potentially FQL Baseline Specific**:
    *   `Initial_Files/All-WRR/` (Explicitly mentioned as "paper final version," likely for FQL baseline training/initialization). LLM agents might require different initialization or learning strategies.
