# Multi-Agent Experiment Configuration

## Quick Start

```powershell
# Run multi-agent experiment
python examples/multi_agent/run_unified_experiment.py --agents 100 --years 10 --model llama3.2:3b
```

## Configuration Parameters

### Agent Generation (`generate_agents.py`)

| Parameter      | Default            | Literature Source | Notes                         |
| -------------- | ------------------ | ----------------- | ----------------------------- |
| MG ratio       | 40%                | US Census ACS     | Marginalized group proportion |
| Owner ratio    | 62%                | US Census         | Home ownership rate           |
| Income (NMG)   | μ=$75K, σ=$25K     | BLS               | Annual household income       |
| Income (MG)    | μ=$45K, σ=$15K     | BLS               | Lower for marginalized        |
| RCV (Building) | $150K-$350K        | Zillow            | Log-normal distribution       |
| RCV (Contents) | 25-35% of building | FEMA              | Contents-to-building ratio    |

### Institutional Agents

#### StateGovernmentAgent (NJ_STATE)

| Parameter     | Default | Literature Source        |
| ------------- | ------- | ------------------------ |
| subsidy_rate  | 50%     | FEMA HMGP (20-75% range) |
| annual_budget | $500K   | State allocation         |

**References**:

- FEMA Individual Assistance: 75% federal / 25% state cost share
- Hazard Mitigation Grant Program (HMGP): up to 75% federal funding
- Increased Cost of Compliance (ICC): up to $30,000 for elevation

#### FEMAInsuranceAgent (FEMA_NFIP)

| Parameter    | Default | Literature Source                 |
| ------------ | ------- | --------------------------------- |
| premium_rate | 2%      | NFIP Risk Rating 2.0 (1-3% range) |
| max_building | $250K   | NFIP limit                        |
| max_contents | $100K   | NFIP limit                        |

**References**:

- Average NFIP claim payout: ~$52,000 (FEMA 2019)
- Risk Rating 2.0: Actuarially sound pricing (2021+)

### Hazard Module (`environment/hazard.py`)

Primary source is PRB ASCII grid depth data (meters). If no grid is provided,
the module falls back to synthetic depths in meters.

| Parameter     | Default | Notes |
| ------------- | ------- | ----- |
| grid_dir      | None    | Path to PRB ASCII grid directory |
| grid_years    | None    | Comma-separated list of years to load |
| depth_unit    | meters  | Converted to feet only for FEMA curves |
| elevation_ft  | 5.0 ft  | Freeboard for elevated homes |

**Depth-Damage Curves**: FEMA-style fine-grained 20-point curves (meters -> feet conversion).

### Validation Rules

| Rule  | Description            | Literature                  |
| ----- | ---------------------- | --------------------------- |
| R1    | Renters cannot buyout  | Tenure-based constraints    |
| R2    | Renters cannot elevate | Property ownership          |
| R3    | Owners cannot relocate | Use buyout instead          |
| R4-R5 | State constraints      | Cannot repeat actions       |
| R6    | HIGH TP+CP → act       | Grothmann & Reusswig (2006) |
| R7    | LOW CP → no expensive  | Bamberg et al. (2017)       |

## Simplification Opportunities

### Current Complexity Assessment

The current configuration requires understanding of:

1. Agent generation parameters (6+ settings)
2. Institutional agent settings (5+ settings)
3. Hazard module parameters (3+ settings)
4. Validation rules (7 rules)

**Total: ~20 configurable parameters**

### Proposed Simplification

#### Option 1: Preset Configurations

```yaml
# config/presets/new_jersey.yaml
preset: "new_jersey_hurricane"
agents:
  n: 100
  mg_ratio: 0.40 # NJ demographics
institutional:
  subsidy_rate: 0.50 # FEMA baseline
hazard:
  type: "hurricane"
  flood_prob: 0.30
```

#### Option 2: Single YAML Config

```yaml
# experiment_config.yaml
experiment:
  name: "NJ Flood Adaptation"
  years: 10

agents:
  count: 100
  preset: "nj_demographics" # Predefined demographic distribution

environment:
  preset: "atlantic_hurricane" # Predefined hazard profile

# Advanced users can override any preset value
overrides:
  agents.mg_ratio: 0.45
```

#### Option 3: CLI Presets

```powershell
# Simple usage with preset
python examples/single_agent/run_flood.py --preset nj_hurricane

# Override specific values
python examples/single_agent/run_flood.py --preset nj_hurricane --agents 200
```

## Full Citation List

See `references.bib` in this directory for BibTeX entries.
