# Data Files Reference

This document describes input data and instructions for obtaining datasets
not shipped with the code.

## External Reference Data

### CRSS Database (`ref/CRSS_DB/`)

Colorado River Simulation System reference data used by the irrigation ABM
(Case Study 2). Original source: USBR CRSS model (2012, 2019 projections).

This data is gitignored and is **not distributed with the repository**. The prepared
reference bundle is available from the authors on request. Anything that reads it
(tutorial chapter 4, real-agent irrigation runs) fails with a missing-file error
until you have it. Place the directories
below under `ref/CRSS_DB/CRSS_DB/` (the repeated directory name is expected by
the loaders). Real-agent runs also read the tracked parameter table
`ref/RL-ABM-CRSS/ALL_colorado_ABM_params_cal_1108.csv`; calibrated FQL runs
expect `Initial_Files/All-1109/` inside that CRSS data directory.

| Directory | Contents | Used By |
|-----------|----------|---------|
| `Div_States/` | Diversion state discretization (UB/LB) | Agent initialization |
| `Group_Agt/` | Agent-to-group mapping (k-means clusters) | Persona assignment |
| `HistoricalData/` | Historical diversions, depletions, Lake Mead levels, PRISM precip | Mass balance, calibration |
| `Initial_Files/` | CRSS initial condition files (P_Tran_*.txt) | Demand baseline |
| `PRISM/` | CRSS PRISM precipitation projections (2019-2060) | Environmental driver |
| `WaterRights/` | Per-agent water right allocations | Demand ceiling |

**Source**: USBR CRSS model data; obtain the prepared layout from the authors.

## Included Data

### Flood Input Data (`examples/multi_agent/flood/`)

| File | Contents | Source |
|------|----------|--------|
| `input/PRB/maxDepth*.asc` | Passaic River Basin (PRB) maximum flood depth grids by year (ASCII raster) | Tracked in this repository; upstream hydrology provenance available from the authors |
| `data/agents_init.csv` | Initial household table for the multi-agent flood example | Tracked in this repository; upstream survey provenance available from the authors |
| `data/initial_memories*.json` | Initial household memories | Tracked in this repository; upstream survey provenance available from the authors |

### Configuration Reference

| File | Purpose |
|------|---------|
| `examples/single_agent/flood_years.csv` | Deterministic flood schedule for the single-agent flood case |

## Not Included (Large Files)

The following are generated during experiments and not tracked in git:

- **Audit traces** (`*_traces.jsonl`): Raw LLM decision logs (~100 MB per full run)
- **Simulation results** (`results*/`): Per-agent state histories
- **Model weights**: Download via [Ollama](https://ollama.com/) (e.g., `ollama pull gemma3:4b`)

## Reproducing Experiments

1. Install Ollama and pull the required model
2. For real-agent irrigation runs, obtain the CRSS bundle from the authors and
   place it in `ref/CRSS_DB/CRSS_DB/` as described above. Synthetic mode needs no CRSS data.
3. The multi-agent flood depth grids are tracked under `examples/multi_agent/flood/input/PRB/`
4. Run experiments per the instructions in each example's README
