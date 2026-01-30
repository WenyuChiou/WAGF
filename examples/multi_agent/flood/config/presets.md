# Multi-Agent Experiment Presets

## Overview

Presets simplify experiment configuration by bundling common parameter combinations.

## Available Presets

### `nj_hurricane` - New Jersey Hurricane Scenario

- Agents: 100 (40% MG, 62% Owner)
- Years: 10
- Flood probability: 0.3
- Subsidy rate: 50% (FEMA HMGP)
- Premium rate: 2% (NFIP Risk Rating 2.0)

### `fl_coastal` - Florida Coastal Flooding

- Agents: 100 (35% MG, 55% Owner)
- Years: 10
- Flood probability: 0.4
- Subsidy rate: 40%
- Premium rate: 3%

### `test_quick` - Quick Testing

- Agents: 20
- Years: 3
- Flood probability: 0.5

## Preset Configuration Format

```yaml
# config/presets/nj_hurricane.yaml
name: "New Jersey Hurricane"
description: "Atlantic hurricane scenario based on NJ demographics"

agents:
  count: 100
  mg_ratio: 0.40
  owner_ratio: 0.62
  income_nmg: [75000, 25000] # mean, std
  income_mg: [45000, 15000]

institutional:
  government:
    id: "NJ_STATE"
    subsidy_rate: 0.50
  insurance:
    id: "FEMA_NFIP"
    premium_rate: 0.02

environment:
  flood_probability: 0.30
  mean_depth_ft: 2.0
  elevation_offset_ft: 5.0

simulation:
  years: 10
  memory_engine: "humancentric"
  governance_profile: "strict"
```

## CLI Usage

```powershell
# Use preset
python examples/single_agent/run_flood.py --preset nj_hurricane

# Override specific values
python examples/single_agent/run_flood.py --preset nj_hurricane --agents 200 --years 5

# Custom configuration file
python examples/single_agent/run_flood.py --config custom_config.yaml
```
