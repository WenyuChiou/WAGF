# Current Session Handoff

## Last Updated
2026-01-22T12:00:00Z

---

## Active Task: Task-030

**Title**: FLOODABM Parameter Alignment

**Status**: In Progress - Sprint 1-5.1 Complete

---

## Task-030 Progress

### Completed Sprints

| Sprint | Description | Status | Agent |
|:-------|:------------|:-------|:------|
| 1.1 | CSRV = 0.57 in rcv_generator.py | **DONE** | Claude Code |
| 1.2 | Financial params in core.py | **DONE** | Claude Code |
| 1.3 | Damage threshold params | **DONE** | Claude Code |
| 2.1 | Create risk_rating.py module | **DONE** | Claude Code |
| 3.1 | Create tp_decay.py module | **DONE** | Claude Code |
| 4.1 | Beta params in YAML | **DONE** | Claude Code |
| 5.1 | Verification tests (33/33 pass) | **DONE** | Claude Code |

### Pending

| Sprint | Description | Status | Assigned |
|:-------|:------------|:-------|:---------|
| 2.2 | Integrate RR2.0 with insurance agent | Pending | Gemini CLI |
| 5.2 | Integration with run_unified_experiment.py | Pending | Claude Code |

---

## Files Created/Modified

### New Files
| File | Description |
|:-----|:------------|
| `examples/multi_agent/environment/risk_rating.py` | Risk Rating 2.0 premium calculator |
| `examples/multi_agent/environment/tp_decay.py` | TP decay formula engine |
| `examples/multi_agent/tests/test_floodabm_alignment.py` | Verification tests (33 tests) |

### Modified Files
| File | Change |
|:-----|:-------|
| `examples/multi_agent/environment/rcv_generator.py` | Added CSRV = 0.57 constant |
| `examples/multi_agent/environment/core.py` | Updated deductible ($1K), added RR2.0 rates, reserve factor |
| `examples/multi_agent/ma_agent_types.yaml` | Added floodabm_parameters section with Beta distributions |

---

## Key FLOODABM Parameters Aligned

| Parameter | Paper Value | Implementation |
|:----------|:------------|:---------------|
| CSRV | 0.57 | rcv_generator.py: `CSRV = 0.57` |
| r1k_structure | $3.56/1K | risk_rating.py: `R1K_STRUCTURE = 3.56` |
| r1k_contents | $4.90/1K | risk_rating.py: `R1K_CONTENTS = 4.90` |
| Deductible | $1,000 | core.py: `default_deductible: 1_000` |
| Reserve Factor | 1.15 | core.py: `reserve_fund_factor: 1.15` |
| Small Fee | $100 | core.py: `small_fee: 100` |
| Damage Threshold | 0.5 | core.py: `damage_ratio_threshold: 0.5` |
| Initial Uptake | 25%/8%/3%/1% | risk_rating.py: `INITIAL_UPTAKE` dict |

### Beta Distributions (Table S3)
| Construct | MG (α, β) | NMG (α, β) |
|:----------|:----------|:-----------|
| TP | (4.44, 2.89) | (5.35, 3.62) |
| CP | (4.07, 3.30) | (5.27, 4.18) |
| SP | (1.37, 1.69) | (1.73, 1.93) |
| SC | (2.37, 3.11) | (4.56, 2.39) |
| PA | (2.56, 2.17) | (4.01, 2.79) |

### TP Decay Calibrated (Table S4)
| Parameter | MG | NMG |
|:----------|:---|:----|
| α | 0.50 | 0.22 |
| β | 0.21 | 0.10 |
| τ₀ | 1.00 | 2.72 |
| τ∞ | 32.19 | 50.10 |
| k | 0.03 | 0.01 |

---

## Verification Results

```
pytest examples/multi_agent/tests/test_floodabm_alignment.py -v
============================= 33 passed in 0.22s ==============================
```

Test coverage:
- CSRV constant (3 tests)
- Risk Rating 2.0 parameters (5 tests)
- Initial uptake rates (5 tests)
- Core config parameters (6 tests)
- TP decay parameters (3 tests)
- TP decay calculations (4 tests)
- Premium calculations (3 tests)
- YAML configuration (4 tests)

---

## Next Steps for Gemini CLI

### Sprint 2.2: Integrate RR2.0 with Insurance Agent

**Files to modify**:
- `examples/multi_agent/ma_agents/insurance.py`
- `examples/multi_agent/flood_agents.py`

**Task**:
1. Import `RiskRating2Calculator` from `environment/risk_rating.py`
2. Replace simplified premium calculation with RR2.0 rates
3. Add CRS discount support

**Verification**:
```bash
pytest examples/multi_agent/tests/test_floodabm_alignment.py -v
```

---

## References

- Plan file: `C:\Users\wenyu\.claude\plans\cozy-roaming-perlis.md`
- FLOODABM Supplementary Materials (Tables S1-S6)
- USACE (2006) CSVR Report

---

## Task History

### Task-030: In Progress
- FLOODABM Parameter Alignment
- Sprint 1-5.1 complete (7/9)

### Task-029: COMPLETE
- MA Pollution Remediation
- broker/ is now domain-agnostic

### Task-028: COMPLETE
- Framework cleanup & agent-type config
