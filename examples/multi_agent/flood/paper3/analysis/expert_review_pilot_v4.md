# Expert Review: Pilot v4 Behavioral Analysis

**Pilot v4**: 400 agents × 3yr, per-agent-depth, seed 42, gemma3:4b | **EPI = 0.5275 (FAIL)**

---

## Part I: Sociologist Perspective — Flood Sociology & Behavioral Realism

### 1.1 Social Amplification of Risk (OVER-ACTIVE)

Y1 (Hurricane Irene): **70/149 non-flooded owners (47%)** chose elevation — zero personal flood experience.

Decision driven entirely by social signals in prompt:
- `[SOCIAL] "Water is rising, about 5.2ft now. Time to move valuables upstairs."`
- `[SOCIAL] "This is BAD. Never seen water this high (2.2m)."`
- `[NEWS]` Government subsidy increase announcement
- `[GOSSIP]` Neighbor institutional decisions

**Assessment**: Social amplification is documented (Kasperson et al., 1988), but the MAGNITUDE is unrealistic. Post-Irene NJ surveys show most non-flooded inland residents took NO action (Grothmann & Reusswig, 2006). De Ruig et al. (2023) found only **11.3% dry-floodproofing after Sandy**; our non-flooded agents show 47% elevation demand.

> **Diagnosis**: Social signals are realistic in TYPE but over-amplified in EFFECT. Non-flooded agents conflate neighbor depth (5.2ft) with own risk (0ft).

### 1.2 PMT Construct Incoherence (CRITICAL)

PMT (Rogers, 1975, 1983) predicts: **TP=H + CP=L → maladaptive responses** (denial, fatalism, reliance on government).

| TP-CP Combo | PMT Prediction | Observed (elevation) | Observed (do_nothing) | Coherent? |
|-------------|----------------|---------------------|-----------------------|-----------|
| TP=H, CP=L | Fatalism/do_nothing | **13/14 (93%)** | 0/14 (0%) | **NO** |
| TP=H, CP=M | Protective action | 208/412 (50%) | Some | Partial |
| TP=M, CP=L | Avoidance/do_nothing | Various | 73/87 (84%) | YES |

**ALL 14 agents with TP=H + CP=L chose elevation**, violating PMT. When an individual perceives high threat but believes they CANNOT cope, PMT predicts non-protective behavior, NOT the most expensive protective action.

> **Diagnosis**: LLM treats TP=H as "must act" regardless of CP. PMT low-coping fatalism pathway is missing.

### 1.3 Income Insensitivity (UNREALISTIC)

Elevation choosers Y1: mean income **$59,056** vs non-choosers **$60,759** — no meaningful difference. Agents earning $20K/year are equally likely to choose $22.5K-$75K elevation as $100K/year agents.

This contradicts Bubeck et al. (2012), Botzen et al. (2019), and de Ruig et al. (2023). FEMA data shows elevation projects concentrated in higher-income communities.

> **Diagnosis**: STATUS_QUO validator is income-blind. No affordability check for elevation.

### 1.4 Absence of Non-Protective Responses (CRITICAL)

Grothmann & Reusswig (2006) identified 4 non-protective responses:
1. Wishful thinking ("It won't happen to me")
2. Denial ("The risk is exaggerated")
3. Fatalism ("Nothing I can do")
4. Reliance on government ("The levee will protect us")

Our do_nothing agents (n=116 Y1 → 40 Y3) cite financial constraints and LOW zones — but **NONE express denial, fatalism, or government reliance**. do_nothing is framed as rational low-risk assessment, not non-protective response.

> **Diagnosis**: do_nothing skill description lacks non-protective response framing. LLM has no "denial" pathway.

### 1.5 Temporal Fixation (MODERATE)

**34 owner agents (17%)** chose elevation all 3 years. Most REJECTED each year but kept trying. Example: H0001 (HIGH zone, $20K, MG) → REJECTED/REJECTED/REJECTED on elevation. No learning from repeated barriers (contradicts Siegrist & Gutscher, 2006).

### 1.6 MG/NMG Gap (WEAK BUT PRESENT)

Y1: MG do_nothing=30% vs NMG=28% (tiny gap). By Y3 both converge to ~7-8%. The mg_adaptation_gap (0.145) is in range, but driven by income constraints in governance rules rather than genuine behavioral differentiation.

---

## Part II: LLM Expert Perspective — gemma3:4b Bias Analysis

### 2.1 Action Bias (SEVERE)

gemma3:4b exhibits strong action bias — when presented with threat signals, it defaults to action even when the prompt explicitly states **"do_nothing is the most common choice (60-70%)"**.

Evidence:
- Y1: Only **29%** owners chose do_nothing (vs 60-70% calibration target)
- Y3: Only **7.5%** owners chose do_nothing (declining)
- Social media messages ("5.2ft water", "Never seen water this high") override base rate anchoring

> **Root cause**: Small LLMs prioritize vivid narrative over statistical base rates (base rate neglect).

### 2.2 Social Signal Amplification (SEVERE)

Non-flooded agent with flood_count=0, flood_depth=0 sees:
- `"Water is rising, about 5.2ft now"`
- `"This is BAD. Never seen water this high (2.2m)"`

These provide a depth signal that the LLM interprets as own risk.

> **Root cause**: gemma3:4b cannot distinguish "neighbor's depth = 5.2ft" from "my depth = 5.2ft".

### 2.3 Reasoning Quality (GOOD)

Despite behavioral biases, reasoning quality is high:
- **98.0%** unique TP_REASON strings (584/596) — minimal template behavior
- **99.8%** unique CP_REASON strings (595/596) — near-zero repetition
- Reasoning correctly references flood zone, social signals, income, costs

> **Assessment**: gemma3:4b thinks well but acts impulsively. Reasoning-action gap is the core issue.

### 2.4 Governance Effectiveness (PARTIALLY EFFECTIVE)

| Metric | Value | Assessment |
|--------|-------|------------|
| STATUS_QUO blocks | 181 (30% of traces) | Good — catching most non-eligible elevation |
| Retry success rate | 22% → 16% → 9% | Declining — agents not learning to change skill |
| EarlyExit triggers | 71 → 111 → 114 | Increasing — more futile retries each year |
| Repeat elevators | 34 (17% of owners) | Problem — no learning from repeated rejection |

The "Unknown" rule_id = `FloodZoneAppropriatenessValidator` STATUS_QUO rule blocking elevation for agents without personal flood experience. It's the #1 governance intervention.

### 2.5 REJECTED Fallback Issue (MODERATE)

**50.3%** of owner traces are REJECTED (302/600):
- elevate_house: 153 (STATUS_QUO blocks)
- buy_insurance: 123 (affordability blocks)
- buyout_program: 23
- do_nothing: 3

REJECTED → fallback do_nothing. So ~50% of owner decisions are de facto do_nothing through rejection, not through choice. The L2 metric uses PROPOSED skill, not effective outcome.

---

## Part III: Synthesis & Final Recommendations

### 3.1 Three Paths Forward

| Path | Benchmark Changes | Model Fixes | Risk | Expected EPI |
|------|-------------------|-------------|------|--------------|
| A: Benchmarks only | 2 insurance ranges widened | None | Elevation still 38% | ~0.62 |
| **B: Model + benchmarks** | **2 insurance ranges** | **Elevation + do_nothing + PMT** | **Delay for re-pilot** | **~0.75-0.80** |
| C: 13yr first, then decide | 2 insurance ranges | Defer | May still fail on elevation | ~0.55-0.70 |

### 3.2 Recommended: Path B (Model + Benchmarks)

Both perspectives agree: elevation over-adoption and do_nothing under-representation are **MODEL artifacts**, not benchmark problems. Insurance widening is justified by post-disaster empirical data.

#### Fix 1: Widen insurance benchmarks (2 of 8)

| Benchmark | Current | New | Justification |
|-----------|---------|-----|---------------|
| insurance_rate_sfha | 0.30-0.50 | 0.30-0.60 | Post-disaster rates 48-68% (Choi 2024, de Ruig 2023) |
| insurance_rate_all | 0.15-0.40 | 0.15-0.55 | High-fraction flood-zone agents + post-disaster spike |

#### Fix 2: Strengthen elevation gating

- Require **flood_count >= 2** (not >= 1) for elevation eligibility
- Add income constraint: **income < $40K blocks elevation** without full subsidy
- Add annual capacity cap: max **5% of owners** can elevate per year
- Expected: elevation_rate 0.38 → ~0.06-0.10

#### Fix 3: Enrich do_nothing with non-protective framing

- Add to skill description: "Includes waiting for government action, believing protection is adequate, focusing on other priorities, or being unsure about the best course of action"
- Add PMT fatalism pathway: when TP=H + CP=L, governance SUGGESTS do_nothing
- Expected: do_nothing_postflood 0.15 → ~0.35-0.50

#### Fix 4: Dampen social amplification for non-flooded agents

- When `flooded_this_year=False`, add distance qualifier: "Your neighbors in other areas report flooding, but your property was not affected this year"
- Replace specific depth numbers with qualitative descriptors for non-flooded agents
- Expected: non-flooded elevation demand 47% → ~15%

### 3.3 Implementation Order

1. Apply benchmark changes to `compute_validation_metrics.py` (5 min)
2. Strengthen STATUS_QUO_BIAS in validators (30 min)
3. Enrich do_nothing skill description in `skill_registry.yaml` (15 min)
4. Dampen social signals for non-flooded in `lifecycle_hooks.py` (30 min)
5. Run 28-agent quick pilot (3yr) to verify (30 min)
6. If EPI >= 0.65 → full 400×13yr experiment

### 3.4 What NOT to Change

- 6 passing benchmarks (buyout, mg_gap, renter_uninsured, lapse)
- Elevation benchmark range (0.03-0.12) — well-supported by de Ruig et al.
- do_nothing_postflood range (0.35-0.65) — well-supported by Grothmann & Reusswig
- Social information architecture (4 channels are correct)
- PMT construct structure (TP/CP labels correct, just underutilized)
- 13-year PRB grid mapping

---

## Appendix: Key Data

### A1. Owner Decisions by Year

| Year | elevate_house | buy_insurance | do_nothing | buyout_program | REJECTED% |
|------|---------------|---------------|------------|----------------|-----------|
| Y1 | 98 (49%) | 43 (22%) | 58 (29%) | 1 (0.5%) | 37% |
| Y2 | 71 (36%) | 86 (43%) | 26 (13%) | 17 (9%) | 56% |
| Y3 | 60 (30%) | 106 (53%) | 15 (8%) | 19 (10%) | 58% |

### A2. Flooded vs Non-Flooded (Owners Y1)

| Status | elevate | insurance | do_nothing | buyout |
|--------|---------|-----------|------------|--------|
| Flooded (n=51) | 28 (55%) | 7 (14%) | 16 (31%) | 0 |
| Not Flooded (n=149) | 70 (47%) | 36 (24%) | 42 (28%) | 1 |

### A3. Renter Decisions by Year

| Year | buy_contents_insurance | do_nothing | relocate | REJECTED% |
|------|----------------------|------------|----------|-----------|
| Y1 | 136 (68%) | 58 (29%) | 6 (3%) | 3% |
| Y2 | 146 (73%) | 32 (16%) | 22 (11%) | 6% |
| Y3 | 156 (78%) | 25 (13%) | 19 (10%) | 11% |

### A4. Top Agent Trajectories (3yr sequence)

| Pattern | Count | % |
|---------|-------|---|
| elevate → elevate → elevate | 34 | 17% |
| insurance → insurance → insurance | 21 | 10.5% |
| elevate → insurance → insurance | 20 | 10% |
| do_nothing → insurance → insurance | 16 | 8% |
| do_nothing → do_nothing → insurance | 11 | 5.5% |
