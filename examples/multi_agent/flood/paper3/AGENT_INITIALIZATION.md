# Agent Initialization Pipeline — Paper 3

> Full documentation for the 400-agent balanced 4-cell initialization used in Paper 3 (WRR).
>
> **Entry point**: `paper3/prepare_balanced_agents.py`
>
> **Reproducibility**: All randomness controlled via `--seed` (default 42).

---

## Pipeline Overview

```
Qualtrics CSV (920 raw)
    |  process_qualtrics_full.py
    v
cleaned_survey_full.csv (755 valid)
    |  BalancedSampler (stratified by MG/NMG x Owner/Renter)
    v
100 profiles per cell (400 total)
    |  generate_rcv() — lognormal / normal distributions
    v
HouseholdProfile objects (with RCV)
    |  assign_flood_zones() — real PRB ASCII raster
    v
agent_profiles_balanced.csv  +  initial_memories_balanced.json
```

---

## Step 1: Survey Cleaning

**Script**: `paper3/process_qualtrics_full.py`

- Input: Raw Qualtrics export (920 respondents)
- Cleans PMT construct scores (TP, CP, SP, SC, PA) to 1-5 scale
- Derives demographics: income bracket, tenure, household size, flood experience
- Classifies MG/NMG via `MGClassifier` (income < $50K OR housing cost burden OR no vehicle)
- Output: `data/cleaned_survey_full.csv` (755 valid respondents after exclusions)

---

## Step 2: Balanced Sampling

**Class**: `survey/balanced_sampler.py::BalancedSampler`

```python
BalancedSampler(n_per_cell=100, seed=42, allow_oversample=True)
```

Stratifies the 755 cleaned survey respondents into 4 cells:

| Cell | MG | Tenure | N | Purpose |
|------|:--:|--------|---|---------|
| A | Yes | Owner | 100 | Marginalized homeowners |
| B | Yes | Renter | 100 | Marginalized renters |
| C | No | Owner | 100 | Non-marginalized homeowners |
| D | No | Renter | 100 | Non-marginalized renters |

**Sampling method**:
- Stratum >= 100: `rng.sample(available, 100)` (without replacement)
- Stratum < 100 + `allow_oversample=True`: `rng.choices(available, k=100)` (with replacement, flagged)
- Otherwise: take all available, report shortfall

**Output**: `BalancedSampleResult` with 400 profiles, cell counts, shortfall/oversample flags.

---

## Step 3: RCV Generation

**Function**: `generate_agents.py::generate_rcv(tenure, income, mg)`

### Owner — Building RCV

Lognormal distribution differentiated by MG status:

```
rcv_building = np.random.lognormal(ln(mu), sigma=0.3)
```

| Group | mu (median) | sigma | Bounds |
|-------|-------------|-------|--------|
| MG Owner | $280,000 | 0.3 | [$100K, $1M] |
| NMG Owner | $400,000 | 0.3 | [$100K, $1M] |

**Rationale**: MG households have lower property values on average. The 0.3 sigma produces a coefficient of variation ~31%, consistent with PRB housing stock heterogeneity.

### Owner — Contents RCV

```
rcv_contents = rcv_building * Uniform(0.30, 0.50)
```

Contents typically 30-50% of structure value (FEMA HAZUS-MH guidance).

### Renter — Building RCV

$0 (renters do not own the structure).

### Renter — Contents RCV

Normal distribution scaled by income:

```
base = $20,000 + (income / $100,000) * $40,000
rcv_contents = Normal(base, sigma=$5,000)
```

| Bounds | Min | Max |
|--------|-----|-----|
| Contents | $10,000 | $80,000 |

**Rationale**: Higher-income renters accumulate more personal property. The $5K sigma provides within-bracket variation.

---

## Step 4: Spatial Assignment

**Function**: `paper3/prepare_balanced_agents.py::assign_flood_zones()`

### Data Source

Real PRB (Passaic River Basin) flood depth rasters in ESRI ASCII Grid format:

- Path: `examples/multi_agent/flood/input/PRB/`
- Reference year: 2021 (`maxDepth2021.asc`)
- Grid dimensions: 457 columns x 411 rows
- Cell size: 0.000277702 degrees (~30m at 40.9N)
- Extent: xll=-74.355, yll=40.859 (WGS84)

### Depth Categories

Cells are classified by `DepthCategory` enum (from `environment/depth_sampler.py`):

| Category | Depth Range | % of Grid (2021) |
|----------|-------------|-------------------|
| DRY | 0 m | 76.93% |
| SHALLOW | 0 - 0.5 m | 2.51% |
| MODERATE | 0.5 - 1.0 m | 2.93% |
| DEEP | 1.0 - 2.0 m | 8.95% |
| VERY_DEEP | 2.0 - 4.0 m | 7.41% |
| EXTREME | > 4.0 m | 1.27% |

### Assignment Decision Tree

```
Agent has flood experience?
|
+-- YES, flood_frequency >= 2
|   --> Sample from deep_pool (DEEP + VERY_DEEP + EXTREME)
|
+-- YES, flood_frequency < 2
|   --> Sample from shallow_pool (SHALLOW + MODERATE)
|
+-- NO
    |
    +-- MG agent: P(flood-prone) = 0.70
    |   --> 70% chance: sample from flood_prone_pool (SHALLOW + MODERATE + DEEP)
    |   --> 30% chance: sample from dry_pool
    |
    +-- NMG agent: P(flood-prone) = 0.50
        --> 50% chance: sample from flood_prone_pool
        --> 50% chance: sample from dry_pool
```

**Design rationale**:
- Experienced agents are placed where flooding occurs (face validity)
- MG households disproportionately live in flood-prone areas (environmental justice literature: Chakraborty et al. 2014, Choi et al. 2024)
- NMG still have 50% exposure (PRB is a high-risk basin overall)

### Coordinate Conversion

Grid indices (row, col) -> geographic coordinates using ESRI ASCII header:

```python
latitude  = yllcorner + (nrows - 1 - row) * cellsize   # row 0 = north
longitude = xllcorner + col * cellsize
```

### Zone Labels

Assigned from flood depth for use in agent prompts and governance rules:

| Depth | Zone Label | Meaning |
|-------|-----------|---------|
| 0 m | LOW | Outside flood extent |
| 0 - 0.5 m | MEDIUM | Marginal flooding |
| > 0.5 m | HIGH | Significant flood exposure |

### Seed 42 Results

```
MG flood-prone (HIGH+MEDIUM):  146/200 = 73%  (target: 70%)
NMG flood-prone (HIGH+MEDIUM): 126/200 = 63%  (target: 50%, higher due to 38 experienced NMG agents)
Experienced agents in flooded zones: 76/76 = 100%
Lat range: [40.8590, 40.9728]
Lon range: [-74.3550, -74.2282]
```

---

## Step 5: Initial Memory Generation

**Function**: `paper3/prepare_balanced_agents.py::generate_initial_memory(profile)`

Each agent receives 6 memories derived from their survey responses:

| # | Category | Importance | Source Field | Example |
|---|----------|-----------|--------------|---------|
| 1 | `flood_experience` | 0.3-0.8 | flood_experience, flood_frequency | "I experienced flooding 3 times causing $85K damage" |
| 2 | `insurance_history` | 0.5-0.6 | insurance_type | "I have NFIP flood insurance for structure and contents" |
| 3 | `social_connections` | 0.4-0.7 | sc_score (1-5) | "I have strong connections with my neighbors" |
| 4 | `government_trust` | 0.5-0.7 | sp_score (1-5) | "I believe government agencies can help with flood protection" |
| 5 | `place_attachment` | 0.3-0.7 | pa_score, generations | "I've lived here for 20+ years; cannot imagine living elsewhere" |
| 6 | `flood_zone` | 0.3-0.7 | flood_zone (from Step 4) | "My property is in a HIGH flood risk zone" |

**Format**: Each memory is a dict with `text`, `importance`, `category`, `source` fields, compatible with `UnifiedCognitiveEngine.encode()`.

**Output**: `data/initial_memories_balanced.json` — keyed by agent_id, 2,400 total memories.

---

## Randomness Control

| Component | RNG Type | Seed Source |
|-----------|----------|-------------|
| `prepare_balanced_agents()` | `random.Random(seed)` + `np.random.seed(seed)` | CLI `--seed` |
| `BalancedSampler.sample()` | `random.Random(seed)` | Inherited |
| `generate_rcv()` | `np.random.lognormal()`, `random.uniform()` | Global np seed |
| `assign_flood_zones()` | `np.random.default_rng(rng.randint(0, 2^31))` | Derived from main RNG |
| Grid loading | Deterministic (file read) | N/A |

All steps are fully reproducible given the same `--seed` value.

---

## Output Files

| File | Format | Size | Contents |
|------|--------|------|----------|
| `data/agent_profiles_balanced.csv` | CSV | 400 rows x 70+ cols | All agent attributes |
| `data/initial_memories_balanced.json` | JSON | 2,400 entries | 6 memories per agent |

### Key CSV Columns

| Column | Type | Description |
|--------|------|-------------|
| `agent_id` | str | H0001-H0400 |
| `mg` | bool | Marginalized Group status |
| `tenure` | str | Owner / Renter |
| `income` | float | Midpoint of bracket ($) |
| `rcv_building` | float | Structure replacement cost ($) |
| `rcv_contents` | float | Contents replacement cost ($) |
| `flood_zone` | str | HIGH / MEDIUM / LOW |
| `flood_depth` | float | Reference depth (m) |
| `grid_x` | int | Raster column index |
| `grid_y` | int | Raster row index |
| `latitude` | float | WGS84 latitude |
| `longitude` | float | WGS84 longitude |
| `flood_experience` | bool | Has prior flood experience |
| `flood_frequency` | int | Number of past floods (0-7+) |
| `tp_score` - `pa_score` | float | PMT construct scores (1-5) |

---

## Usage

```bash
cd examples/multi_agent/flood/

# Default: 100 per cell, seed 42
python paper3/prepare_balanced_agents.py --seed 42

# Custom cell size
python paper3/prepare_balanced_agents.py --seed 42 --n-per-cell 25

# Custom output
python paper3/prepare_balanced_agents.py --seed 42 --output-dir paper3/data/custom/
```

---

## Paper Reference

This pipeline is described in the Methods section of Paper 3 (WRR):

> **Section 3.1 Agent Design**: "400 household agents are initialized from a stratified sample of 755 NJ flood survey respondents (4-cell balanced design: 100 MG-Owner, 100 MG-Renter, 100 NMG-Owner, 100 NMG-Renter). Building replacement cost values (RCV) follow lognormal distributions calibrated to PRB housing stock (MG median $280K, NMG median $400K, sigma=0.3). Spatial positions are assigned from real ESRI ASCII flood depth rasters (2021 reference year) using a depth-stratified sampling scheme: agents with flood experience are placed in cells matching their exposure severity, while remaining agents are assigned probabilistically (MG: 70% flood-prone, NMG: 50%). Each agent is seeded with 6 memories derived from survey responses (flood experience, insurance history, social capital, institutional trust, place attachment, flood zone awareness)."

### Citations for Paper

- **Environmental justice / spatial assignment**: Chakraborty et al. (2014), Choi et al. (2024)
- **RCV distributions**: FEMA HAZUS-MH Flood Model Technical Manual (2022)
- **Depth-damage curves**: Scawthorn et al. (2006)
- **Memory seeding rationale**: Park et al. (2023) Generative Agents, McEwen et al. (2017)
- **Balanced design**: Kish (1965) Survey Sampling; Cochran (1977) Sampling Techniques
