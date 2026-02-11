# Data Files Reference

This document describes external data files included in the repository
and instructions for obtaining large datasets not shipped with the code.

## Included Data

### CRSS Database (`ref/CRSS_DB/`)

Colorado River Simulation System reference data used by the irrigation ABM
(Case Study 2). Original source: USBR CRSS model (2012, 2019 projections).

| Directory | Contents | Used By |
|-----------|----------|---------|
| `Div_States/` | Diversion state discretization (UB/LB) | Agent initialization |
| `Group_Agt/` | Agent-to-group mapping (k-means clusters) | Persona assignment |
| `HistoricalData/` | Historical diversions, depletions, Lake Mead levels, PRISM precip | Mass balance, calibration |
| `Initial_Files/` | CRSS initial condition files (P_Tran_*.txt) | Demand baseline |
| `PRISM/` | CRSS PRISM precipitation projections (2019-2060) | Environmental driver |
| `WaterRights/` | Per-agent water right allocations | Demand ceiling |

**License**: CRSS data is publicly available from the US Bureau of Reclamation.

### Flood Input Data (`examples/multi_agent/flood/input/`)

| File | Contents | Source |
|------|----------|--------|
| `census/` | Synthetic census tract profiles | Generated from ACS data |
| `*.asc` | FEMA flood zone rasters | FEMA National Flood Hazard Layer |

### Configuration Reference

| File | Purpose |
|------|---------|
| `ref/flood_years.csv` | Deterministic flood schedule for experiments |

## Not Included (Large Files)

The following are generated during experiments and not tracked in git:

- **Audit traces** (`*_traces.jsonl`): Raw LLM decision logs (~100 MB per full run)
- **Simulation results** (`results*/`): Per-agent state histories
- **Model weights**: Download via [Ollama](https://ollama.com/) (e.g., `ollama pull gemma3:4b`)

## Reproducing Experiments

1. Install Ollama and pull the required model
2. CRSS data is included in `ref/CRSS_DB/` — no additional download needed
3. Flood input rasters should be placed in `examples/multi_agent/flood/input/`
4. Run experiments per the instructions in each example's README
