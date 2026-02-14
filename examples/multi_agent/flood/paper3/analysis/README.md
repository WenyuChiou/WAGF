# LLM-ABM Construct & Validation Framework (C&V Framework)

## Overview

This module implements a three-level validation protocol for LLM-driven Agent-Based Models (LLM-ABM), evaluating **theory-informed behavioral fidelity** (structural plausibility) rather than predictive accuracy.

The design draws from the POM framework (Grimm et al. 2005), extended with LLM-ABM-specific quantitative validation criteria. Currently implemented for flood adaptation (PMT theory), but architected for extension to other behavioral theories and domains.

---

## Three-Level Validation Architecture

```
L3 Cognitive Validation (Pre-experiment)
   │  ICC, eta², directional sensitivity
   │  → Confirm LLM distinguishes between personas
   ▼
L1 Micro Validation (Per-decision)
   │  CACR, R_H, EBE
   │  → Confirm each decision follows behavioral theory
   ▼
L2 Macro Validation (Aggregate)
      EPI + 8 empirical benchmarks
      → Confirm population behavior matches empirical literature
```

### L1 Micro Metrics

| Metric | Full Name | Threshold | Description |
|--------|-----------|-----------|-------------|
| **CACR** | Construct-Action Coherence Rate | ≥ 0.75 | Do agent actions match construct mappings (e.g., PMT TP/CP → action)? |
| **CACR_raw** | Raw coherence (pre-governance) | Reference | LLM reasoning quality before governance intervention |
| **CACR_final** | Final coherence (post-governance) | Reference | System-level coherence (including governance filtering) |
| **R_H** | Hallucination Rate | ≤ 0.10 | Physically impossible actions (e.g., relocated agent still deciding) |
| **EBE** | Effective Behavioral Entropy | 0.1 < ratio < 0.9 | Behavioral diversity: neither all-same nor uniformly random |

**CACR decomposition** is the strongest defense against the "constrained RNG" critique: if CACR_raw is high, the LLM reasons coherently even before governance intervenes.

**Notes:**
- Traces with extraction failures are labeled `UNKNOWN` and **excluded** from CACR denominator (avoids inflating coherence)
- EBE is computed from the **combined** owner+renter action distribution (Shannon entropy is not additive)

### L2 Macro Metrics

| Metric | Full Name | Description |
|--------|-----------|-------------|
| **EPI** | Empirical Plausibility Index | Weighted benchmark pass rate (threshold ≥ 0.60) |

**8 Empirical Benchmarks (Flood Domain):**

| # | Benchmark | Range | Weight | Literature Source |
|---|-----------|-------|--------|-------------------|
| B1 | SFHA insurance rate | 0.30-0.60 | 1.0 | Choi et al. (2024), de Ruig et al. (2023) |
| B2 | Overall insurance rate | 0.15-0.55 | 0.8 | Gallagher (2014) |
| B3 | Cumulative elevation rate | 0.10-0.35 | 1.0 | Brick Township post-Sandy FEMA HMGP |
| B4 | Cumulative buyout/relocation rate | 0.05-0.25 | 0.8 | Mach et al. (2019), NJ Blue Acres |
| B5 | Post-flood inaction rate | 0.35-0.65 | 1.5 | Grothmann & Reusswig (2006), Bubeck et al. (2012) |
| B6 | MG adaptation gap (composite) | 0.05-0.30 | 2.0 | Elliott & Howell (2020) |
| B7 | Renter uninsured rate | 0.15-0.40 | 1.0 | FEMA/NFIP statistics |
| B8 | Insurance lapse rate | 0.15-0.30 | 1.0 | Michel-Kerjan et al. (2012) |

> **B6 Note**: MG adaptation gap uses a **composite metric**: any protective action = insurance OR elevation OR buyout OR relocation. Using insurance alone as a proxy is too narrow.

### L3 Cognitive Validation

| Metric | Threshold | Description |
|--------|-----------|-------------|
| ICC(2,1) | ≥ 0.60 | Intraclass correlation: response consistency for same persona |
| eta² | ≥ 0.25 | Effect size: discriminability between different personas |
| Directional sensitivity | ≥ 75% | Correct behavioral direction after construct input changes |

---

## Usage

### Prerequisites

```bash
pip install pandas numpy
```

### Quick Start (Synthetic Data)

```bash
# Run examples with synthetic traces (no experiment data needed)
python example_cv_usage.py
```

This demonstrates L1 metrics, L2 benchmarks, full pipeline I/O, and domain adaptation (irrigation).

### Run Validation

```bash
# Compute L1/L2 metrics (post-experiment)
python compute_validation_metrics.py \
    --traces ../results/main_400x13_seed42 \
    --profiles ../../data/agent_profiles_balanced.csv

# Output directory (default)
# paper3/results/validation/
#   ├── validation_report.json    # Full report
#   ├── l1_micro_metrics.json     # L1 details (with CACR decomposition)
#   ├── l2_macro_metrics.json     # L2 details (with supplementary metrics)
#   └── benchmark_comparison.csv  # Benchmark comparison table
```

### Input Format

**Decision Traces (JSONL)**: One JSON object per line:
```json
{
  "agent_id": "H0001",
  "year": 3,
  "outcome": "APPROVED",
  "skill_proposal": {
    "skill_name": "buy_insurance",
    "reasoning": {"TP_LABEL": "H", "CP_LABEL": "M"}
  },
  "approved_skill": {"skill_name": "buy_insurance"},
  "state_before": {"flood_zone": "HIGH", "elevated": false},
  "state_after": {"flood_zone": "HIGH"},
  "flooded_this_year": true
}
```

**Agent Profiles (CSV)**:
```csv
agent_id,tenure,flood_zone,mg
H0001,Owner,HIGH,True
H0002,Renter,LOW,False
```

---

## Adapting to Other Domains

The validation logic extends to any LLM-agent simulation. The core abstractions are:

1. **Behavioral theory** → construct-action mapping (CACR evaluation)
2. **Empirical benchmarks** → literature-supported plausibility ranges (EPI evaluation)
3. **Impossible behaviors** → domain-specific physical constraints (R_H evaluation)

### Step 1: Define Behavioral Theory Constructs

Replace `PMT_OWNER_RULES` with your theory's mapping table.

**Theory of Planned Behavior (TPB) example** (3D constructs):
```python
TPB_RULES = {
    # (Attitude, SubjectiveNorm, PBC) → allowed actions
    ("positive", "supportive", "high"): ["adopt_technology", "invest"],
    ("positive", "supportive", "low"): ["seek_information"],
    ("negative", "unsupportive", "low"): ["do_nothing"],
    # ...
}
```

**Water Scarcity Assessment (WSA/ACA) example** (irrigation domain):
```python
IRRIGATION_RULES = {
    # (WSA, ACA) → allowed skills
    ("VH", "VH"): ["decrease_large", "decrease_small"],
    ("VH", "VL"): ["maintain_demand", "decrease_small"],  # capacity-limited
    ("VL", "VH"): ["increase_large", "increase_small", "maintain_demand"],
    ("VL", "VL"): ["maintain_demand"],
    # ...
}
```

### Step 2: Define Empirical Benchmarks

Replace `EMPIRICAL_BENCHMARKS` with your domain benchmarks.

**Irrigation management example**:
```python
EMPIRICAL_BENCHMARKS = {
    "deficit_irrigation_rate": {
        "range": (0.20, 0.45),
        "weight": 1.0,
        "description": "Fraction of farmers adopting deficit irrigation",
    },
    "technology_adoption_rate": {
        "range": (0.05, 0.20),
        "weight": 1.0,
        "description": "Fraction of farmers adopting drip irrigation",
    },
    "demand_reduction_drought": {
        "range": (0.10, 0.30),
        "weight": 1.5,
        "description": "Demand reduction during drought periods",
    },
}
```

### Step 3: Define Hallucination Rules

Update `_is_hallucination()` with domain-specific impossible behaviors:

```python
def _is_hallucination(trace):
    action = trace["action"]
    state = trace["state_before"]
    # Bankrupt farmer cannot invest
    if state.get("bankrupt") and action == "invest":
        return True
    # No irrigation infrastructure → cannot use drip irrigation
    if not state.get("has_irrigation") and action == "drip_irrigation":
        return True
    # At water right cap → cannot increase
    if state.get("at_allocation_cap") and action in ("increase_large", "increase_small"):
        return True
    return False
```

### Step 4: Run L3 Cognitive Validation

Design 15-20 **extreme personas** (archetypes) spanning demographic-situational extremes:

```yaml
# Archetype examples
archetypes:
  - id: "wealthy_low_risk"
    income: 150000
    flood_zone: LOW
    flood_count: 0
    expected_tp: VL

  - id: "poor_high_risk_flooded"
    income: 25000
    flood_zone: HIGH
    flood_count: 5
    expected_tp: VH
```

Probe each persona multiple times (≥ 10 replicates), compute ICC and eta².

---

## Supplementary Metrics

### REJECTED Tracking

Governance-intercepted proposals are output as **supplementary metrics** (not counted in EPI):

- `rejection_rate_overall`: Overall rejection rate
- `rejection_rate_mg` / `rejection_rate_nmg`: Rejection rates by marginalization status
- `rejection_gap_mg_minus_nmg`: Rejection rate gap (environmental justice indicator)
- `constrained_non_adaptation_rate`: Constrained non-adaptation rate (wanted to act but blocked)

These metrics transform "methodological embarrassment" into environmental justice findings: governance constraints disproportionately affect marginalized groups.

### Construct Extraction Quality

- `extraction_failures`: Number of traces with failed TP/CP label extraction
- Failed traces are excluded from CACR (avoids silent default bias)

---

## Known Limitations and Future Directions

### Current Limitations

1. **Construct label circularity**: CACR checks whether LLM-generated TP/CP labels are consistent with actions = self-consistency, not construct validity. Future: "construct grounding" validation.
2. **No spatial validation**: All metrics are aspatial. Water resources applications need Moran's I (spatial autocorrelation), flood zone gradient analysis.
3. **No temporal trajectory validation**: EPI compresses multi-year dynamics into a single number. Future: post-flood adaptation spike ratio, insurance survival half-life, adaptation S-curve fitting.
4. **Single theory support**: Currently hard-codes PMT. Future: `BehavioralTheory` protocol supporting TPB, HBM, PADM, Prospect Theory, etc.
5. **Memory limitations**: 500K+ traces require streaming processing. Currently loads all into memory.

### Architecture Evolution Plan

| Phase | Content | Status |
|-------|---------|--------|
| Phase 0 | Fix P0 bugs (EBE averaging, UNKNOWN sentinel) | ✅ Complete |
| Phase 1 | Externalize constants to YAML (rules, benchmarks) | 🔲 Planned |
| Phase 2 | Split into sub-modules (metrics/, io/, reporting/) | 🔲 Planned |
| Phase 3 | BehavioralTheory protocol + TheoryRegistry | 🔲 Planned |
| Phase 4 | Pluggable BenchmarkComputation plugins | 🔲 Planned |
| Phase 5 | Streaming TraceReader + ValidationRunner facade | 🔲 Planned |

---

## Key Design Decisions

1. **Structural plausibility, not predictive accuracy**: LLM-ABM is not a statistical prediction model; validation targets behavioral fidelity
2. **Calibration vs. validation separation**: Explicitly label which benchmarks were iterated during development (calibration targets) vs. held out (validation targets)
3. **Governance ≈ institutional constraints**: REJECTED proposals are analogous to real-world institutional barriers (eligibility, affordability)
4. **4B model as scope condition**: Small LLMs represent "model capability lower bound"; results are conservative but credible
5. **Base rate neglect ≈ bounded rationality**: LLM ignoring calibration text can be interpreted as bounded rationality (feature, not bug)
6. **UNKNOWN sentinel**: Failed construct extraction defaults to "UNKNOWN" (not "M"), excluded from CACR for metric honesty

---

## References

- Grimm, V. et al. (2005). Pattern-oriented modeling of agent-based complex systems. *Science*.
- Grothmann, T. & Reusswig, F. (2006). People at risk of flooding. *Natural Hazards*.
- Bubeck, P. et al. (2012). A review of risk perceptions and coping. *Risk Analysis*.
- Michel-Kerjan, E. et al. (2012). Policy tenure under the NFIP. *Risk Analysis*.
- Mach, K.J. et al. (2019). Managed retreat through voluntary buyouts. *Science Advances*.
- Elliott, J.R. & Howell, J. (2020). Beyond disasters. *Social Problems*.
- Choi, J. et al. (2024). National Flood Insurance Program participation.
- Lindell, M.K. & Perry, R.W. (2012). The Protective Action Decision Model. *Risk Analysis*.
- Ajzen, I. (1991). The Theory of Planned Behavior. *Organizational Behavior and Human Decision Processes*.

---

*Last updated: 2026-02-14*
