# Canonical Datasets for WAGF WRR Technical Note

## Irrigation ABM (Section 5)

| Field | Value |
|-------|-------|
| **Primary dataset** | `production_v16_42yr` |
| **Path** | `examples/irrigation_abm/results/production_v16_42yr/` |
| **Model** | Gemma 3 4B (`gemma3:4b` via Ollama) |
| **Agents** | 78 real CRSS irrigation districts |
| **Duration** | 42 years (2019-2060) |
| **Seed** | 42 |
| **Governance** | Phase C (strict, 11 validators, BLOCK+retry) |
| **Skills** | 3: increase_demand, decrease_demand, maintain_demand |
| **Config** | `config/agent_types_pilot.yaml` (v16-3skill-reduced) |
| **CRSS reference** | `ref/CRSS_DB/CRSS_DB/annual_baseline_time_series.csv` |
| **Figure** | `paper/figures/fig_irrigation_wrr.pdf` |
| **Script** | `examples/irrigation_abm/analysis/fig_wrr_irrigation.py` |

### Previous Datasets (archived)

| Dataset | Status | Notes |
|---------|--------|-------|
| `production_phase_c_42yr` | Superseded by v16 | 5-skill, old drought index |
| `v12_production_42yr_78agents` | Reference | Different governance level |
| `production_4b_42yr_v11` | Historical | Pre-pilot governance |
| `stage3_v2_production_42yr_78agents` | Historical | Stage 3 reference |

## Flood ABM (Section 4)

| Field | Value |
|-------|-------|
| **Primary dataset** | Multi-model results in `paper3/results/` |
| **Path** | `examples/multi_agent/flood/paper3/results/` |
| **Models** | 6 models: gemma3:4b, ministral3, llama3.2:3b, phi4-mini, qwen3:4b, gemma3:12b |
| **Agents** | 400 household profiles (28 pilot, 400 production) |
| **Duration** | 10 years per model |
| **Figure** | `paper/figures/fig2_flood_combined.pdf` |
| **Validation** | `paper3/analysis/compute_validation_metrics.py` (EPI >= 0.60) |

## CRSS Reference Data

| Field | Value |
|-------|-------|
| **Source** | USBR Colorado River Simulation System (2012) |
| **Mean demand target** | 5.86 MAF/yr |
| **Success range** | 5.56-6.45 MAF/yr (0.95-1.10x) |
| **CoV target** | <4% (strict), <10% (soft) |

## Reproducibility

All experiments use deterministic seeds. To reproduce:

```bash
# Irrigation (Section 5)
cd examples/irrigation_abm
python run_experiment.py --model gemma3:4b --years 42 --real --seed 42 \
    --output results/production_v16_42yr --pilot-phase C --workers 1

# Flood (Section 4) - see examples/multi_agent/flood/paper3/scripts/
```

Note: LLM outputs are stochastic even with fixed seeds due to model sampling.
Governance validators and environment dynamics are fully deterministic.

