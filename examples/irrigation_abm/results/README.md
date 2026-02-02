# Irrigation ABM — Experiment Results

Colorado River Basin irrigation demand experiments for the SAGE framework WRR Technical Note.
Domain: 78 CRSS-derived agricultural agents, 42-year horizon (2019-2060), three behavioral clusters.

## Experimental Design

All runs use a single governance group (strict governance + HumanCentric memory) since the
irrigation case study focuses on demand trajectory validation against CRSS baselines rather
than governance ablation.

### Agent Population

78 agents drawn from CRSS (Colorado River Simulation System) diversion nodes:
- 56 Upper Basin agents (9 state groups: AZ, CO1-3, NM, UT1-3, WY)
- 22 Lower Basin agents

### Behavioral Clusters (from Hung & Yang, 2021)

| Cluster | FQL mu | Description | v4 Count | v5 Count |
|---------|--------|-------------|----------|----------|
| aggressive | 0.36 | Bold, large swings | 67 (86%) | ~26 (33%) |
| forward_looking_conservative | 0.20 | Cautious, measured | 5 (6%) | ~26 (33%) |
| myopic_conservative | 0.16 | Status quo, slow | 6 (8%) | ~26 (33%) |

### Actions (5 choices per year)
`increase_demand`, `decrease_demand`, `adopt_efficiency`, `reduce_acreage`, `maintain_demand`

### Shared Parameters
- **Model**: gemma3:4b
- **Seed**: 42
- **LLM context**: `--num-ctx 8192 --num-predict 4096`
- **Governance**: strict (irrigation domain rules)
- **Memory**: HumanCentric (window=5, consolidation, reflection)

## Directory Layout

| Directory | Version | Description |
|-----------|---------|-------------|
| `production_4b_42yr_v6/` | **v6** | Full 78-agent, 42-year with P0+P1 fix + action feedback + configurable reflection |

## CRSS Baseline Comparison

CRSS reference data located at `ref/CRSS_DB/CRSS_DB/`:
- `Within_Group_Div/Annual_*_Div_req.csv` — UB projected demand (9 state groups)
- `LB_Baseline_DB/*_Div_req.txt` — LB projected demand (monthly RiverWare → annual)

v4 results (85% aggressive cluster): UB +73.6%, LB +28.2% above CRSS baseline.

## Key Finding: Economic Hallucination

v4 revealed a novel LLM failure mode — **economic hallucination**:

> Actions that are physically feasible but operationally absurd given quantitative context.

**Mechanism**: Forward-looking conservative (FLC) agents repeatedly chose `reduce_acreage`
(demand *= 0.75) despite receiving context showing 0% utilisation. The LLM's persona
anchoring ("cautious farmer") overwhelmed numerical awareness, compounding demand to zero
over ~30 years. Example: GilaMonsterFarms (water right = 17,400 AF) dropped from 13,920 AF
to 0 AF via 30 consecutive `reduce_acreage` decisions.

**Fix (v6)**: Three-layer defense implemented in commit `015a8d0`:
1. **MIN_UTIL floor** (P0): Hard floor at 10% of water right in `execute_skill`
2. **Diminishing returns** (P1): Taper = `(util - 0.10) / 0.90` — reductions shrink as utilisation approaches floor
3. **Governance identity rule**: `minimum_utilisation_floor` precondition blocks `decrease_demand`/`reduce_acreage` when `below_minimum_utilisation == True`
4. **Builtin validator**: `minimum_utilisation_check()` as final safety net

This finding extends the hallucination taxonomy beyond physical impossibility (flood domain)
to economic/operational absurdity, demonstrating that the same governance architecture
catches qualitatively different failure modes.

## Reproduction

```bash
# v4 production run (has economic hallucination bug)
python examples/irrigation_abm/run_experiment.py \
  --model gemma3:4b --years 42 --real --seed 42

# v6 production run (with P0+P1 fix)
python examples/irrigation_abm/run_experiment.py \
  --model gemma3:4b --years 42 --real --seed 42 \
  --output examples/irrigation_abm/results/production_4b_42yr_v6
```
