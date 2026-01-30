# Multi-Agent Flood Case: Comprehensive Settings Reference

> **Source of truth**: `ma_agent_types.yaml` (v24-nj-fema-pmt-refactored)
> **Domain**: Passaic River Basin (PRB), New Jersey — Flood Risk Adaptation
> **Framework**: Protection Motivation Theory (PMT) + Social Influence + Institutional Feedback
> **Last updated**: 2026-01-29

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Agent Types & Prompts](#2-agent-types--prompts)
3. [PMT Constructs (TP/CP/SP/SC/PA)](#3-pmt-constructs)
4. [Skills & Decision Space](#4-skills--decision-space)
5. [Governance Rules](#5-governance-rules)
6. [Memory Configuration](#6-memory-configuration)
7. [Interaction Mechanisms](#7-interaction-mechanisms)
8. [Environment & Hazard Module](#8-environment--hazard-module)
9. [FloodABM Parameters](#9-floodabm-parameters)
10. [Execution Flow (Year Lifecycle)](#10-execution-flow)
11. [Running the Experiment](#11-running-the-experiment)

---

## 1. Architecture Overview

```
Year N Lifecycle:
  ┌─────────────────────────────────────────────────────────────┐
  │ PRE_YEAR: HazardModule resolves flood event (PRB grid/synthetic)
  │           Pending actions complete (elevation, buyout)
  │           MediaHub broadcasts flood news
  │           Environment counters updated (elevated_count, insured_count)
  ├─────────────────────────────────────────────────────────────┤
  │ TIER 1 — Institutional Agents (sequential)
  │   ├── Government  → increase/decrease/maintain subsidy
  │   └── Insurance   → raise/lower/maintain premium
  │   POST_STEP: Updates env[subsidy_rate], env[premium_rate]
  ├─────────────────────────────────────────────────────────────┤
  │ TIER 2 — Household Agents (parallel via ThreadPoolExecutor)
  │   ├── Each agent receives: personal state + memory + policy
  │   │     updates + world events + social gossip + cost guidance
  │   ├── LLM generates: 5 PMT ratings + decision + reasoning
  │   ├── GovernanceValidator checks identity_rules + thinking_rules
  │   └── POST_STEP: Updates agent state, stores reasoning as memory
  ├─────────────────────────────────────────────────────────────┤
  │ POST_YEAR: Calculate flood damage per agent
  │            Store flood experience as memory (emotion: fear)
  │            Store unread MessagePool messages as memory
  │            Trigger year-end reflection (crisis years or every 5 years)
  └─────────────────────────────────────────────────────────────┘
```

### Agent Population

| Agent Type | Count | Tier | Role |
|---|---|---|---|
| `government` (alias: `nj_government`) | 1 | Tier 1 | NJ DEP Blue Acres — sets subsidy rate |
| `insurance` (alias: `fema_nfip`) | 1 | Tier 1 | FEMA NFIP — sets premium rate |
| `household_owner` | N (configurable) | Tier 2 | Homeowners — PMT-based decisions |
| `household_renter` | M (configurable) | Tier 2 | Renters — limited decision space |

Household agents are generated from:
- **Survey mode**: Real NJ survey data (Excel), stratified by tenure (own/rent) and MG/NMG
- **Random mode**: `generate_agents_random(n)` with configurable MG ratio (default 40%)

---

## 2. Agent Types & Prompts

### 2.1 Household Owner (`household_owner`)

**Prompt template sections** (in order):

| Section | Template Variable | Source |
|---|---|---|
| YOUR SITUATION | `{agent_id}`, `{income_range}`, `{household_size}`, `{residency_generations}`, `{flood_zone}`, `{flood_experience_summary}`, `{rcv_building}`, `{rcv_contents}`, `{elevation_status_text}`, `{insurance_status}` | Agent fixed/dynamic attributes |
| RELEVANT MEMORIES | `{memory}` | MemoryEngine.retrieve() — importance-weighted |
| CRITICAL RISK ASSESSMENT | (static text) | Emphasizes realistic threat assessment |
| POLICY UPDATES THIS YEAR | `{govt_message}`, `{insurance_message}` | PostStepHook after institutional agents |
| WORLD EVENTS | `{global_news}` | MediaHub (news + social media) |
| LOCAL NEIGHBORHOOD | `{social_gossip}` | SocialNetwork.observe_neighbors() |
| CURRENT COSTS | `{current_premium}`, `{subsidy_rate}` | env global state |
| COST GUIDANCE | (static text) | Elevation ~$150K, buyout irreversible, insurance moderate |
| ADAPTATION OPTIONS | `{options_text}` | Filtered by governance identity_rules |
| EVALUATION CRITERIA | `{criteria_definitions}`, `{rating_scale}` | PMT construct definitions |

**Response format**: JSON with 5 PMT appraisals + decision + reasoning

```json
{
  "threat_perception": {"label": "H", "reason": "..."},
  "coping_perception": {"label": "M", "reason": "..."},
  "stakeholder_perception": {"label": "L", "reason": "..."},
  "social_capital": {"label": "M", "reason": "..."},
  "place_attachment": {"label": "VH", "reason": "..."},
  "decision": "buy_insurance",
  "reasoning": "..."
}
```

**LLM params**: `num_ctx: 16384`, `num_predict: 2048`

### 2.2 Household Renter (`household_renter`)

Same prompt structure as owner, with differences:
- No `{rcv_building}` or `{elevation_status_text}` (renters don't own property)
- Shows `{rcv_contents}` only
- Cost guidance: contents insurance (moderate), relocation (high + loss of community)
- Explicit note: "As a renter, you cannot elevate the property or accept a buyout"

**LLM params**: `num_ctx: 16384`, `num_predict: 2048`

### 2.3 NJ Government (`nj_government` / `government`)

**Prompt sections**: IDENTITY → PROGRAM BACKGROUND → CURRENT CONTEXT → POLICY OPTIONS → RESPONSE FORMAT

Context variables: `{year}`, `{subsidy_rate}`, `{elevated_count}`, `{total_households}`, `{buyout_pending}`, `{mg_count}`, `{mg_ratio}`

**Objectives**: (1) Increase community resilience, (2) Manage budget, (3) Prioritize marginalized communities

**Response format**: JSON with `decision` + `reasoning` (no PMT constructs)

**LLM params**: `num_ctx: 16384`, `num_predict: 1024`

### 2.4 FEMA NFIP Insurance (`fema_nfip` / `insurance`)

**Prompt sections**: IDENTITY → PROGRAM BACKGROUND → MARKET STATISTICS → POLICY OPTIONS → OBJECTIVES → RESPONSE FORMAT

Context variables: `{premium_rate}`, `{insured_count}`, `{total_households}`, `{loss_ratio}`, `{crs_discount}`, `{recent_claims}`

**Objectives**: (1) Maintain solvency, (2) Encourage risk reduction, (3) Support resilience, (4) Balance actuarial soundness with equity

**Response format**: JSON with `decision` + `reasoning` (no PMT constructs)

**LLM params**: `num_ctx: 16384`, `num_predict: 1024`

---

## 3. PMT Constructs

Protection Motivation Theory constructs are output by **household agents only**. Each is rated on a 5-point scale.

### 3.1 Scale

| Code | Label | Numeric |
|---|---|---|
| VL | Very Low | 1 |
| L | Low | 2 |
| M | Medium | 3 |
| H | High | 4 |
| VH | Very High | 5 |

### 3.2 Construct Definitions (from `shared.criteria_definitions`)

| Construct | Code | Definition | Behavioral Influence |
|---|---|---|---|
| **Threat Perception** | TP | How serious do you perceive the flood risk? Consider likelihood and potential severity. | High TP → must act (do_nothing blocked) |
| **Coping Perception** | CP | How confident are you that mitigation options (insurance, elevation, buyout) are effective and affordable? | Low CP → complex actions blocked |
| **Stakeholder Perception** | SP | How much do you trust institutions (NJDEP, FEMA/NFIP) to provide reliable support? | Influences subsidy/insurance reliance |
| **Social Capital** | SC | How connected are you with neighbors? Are they taking protective actions? | Neighbor actions increase SC |
| **Place Attachment** | PA | How emotionally attached are you to your home and community? | High PA → resists buyout/relocation |

### 3.3 Construct Parsing

Each construct has `_LABEL` and `_REASON` parsers with:
- **Keywords**: domain-specific terms (e.g., TP: "threat", "severity", "vulnerability")
- **Regex**: `(?i)(?:label)?[:\s\*\[]*\b(VL|L|M|H|VH)\b`

Constructs logged per step: `threat_perception`, `coping_perception`, `stakeholder_perception`, `social_capital`, `place_attachment`

---

## 4. Skills & Decision Space

### 4.1 Household Owner Skills

| Skill ID | Aliases | Description | Constraints |
|---|---|---|---|
| `do_nothing` | DN, nothing, wait | Take no action this year | Blocked if TP = H or VH |
| `buy_insurance` | FI, insurance | Purchase NFIP flood insurance | Blocked if relocated |
| `elevate_house` | HE, elevate | Elevate house ($150K * (1 - subsidy_rate)) | Blocked if already elevated or relocated; blocked if CP = VL or L |
| `buyout_program` | BT, buyout, Blue Acres | Accept NJ Blue Acres buyout (irreversible) | Blocked if relocated; blocked if CP = VL or L |

### 4.2 Household Renter Skills

| Skill ID | Aliases | Description | Constraints |
|---|---|---|---|
| `do_nothing` | DN, nothing, wait | Take no action this year | Blocked if TP = H or VH |
| `buy_contents_insurance` | CI, contents_insurance | Purchase NFIP contents-only insurance | Blocked if relocated |
| `relocate` | RL, move | Relocate to lower flood-risk area | Blocked if relocated; blocked if CP = VL or L |

### 4.3 Government Skills

| Skill ID | Aliases | Description | Effect |
|---|---|---|---|
| `increase_subsidy` | INCREASE, 1 | Raise subsidy by +5% | `env[subsidy_rate] = min(0.95, current + 0.05)` |
| `decrease_subsidy` | DECREASE, 2 | Lower subsidy by -5% | `env[subsidy_rate] = max(0.20, current - 0.05)` |
| `maintain_subsidy` | MAINTAIN, 3 | Keep current rate | No change |

### 4.4 Insurance Skills

| Skill ID | Aliases | Description | Effect |
|---|---|---|---|
| `raise_premium` | RAISE, 1 | Increase premium by +0.5% | `env[premium_rate] = min(0.15, current + 0.005)` |
| `lower_premium` | LOWER, 2 | Decrease premium by -0.5% | `env[premium_rate] = max(0.01, current - 0.005)` |
| `maintain_premium` | MAINTAIN, 3 | Keep current rate | No change |

### 4.5 Parsing Configuration

All agent types use `smart_repair` preprocessor. Institutional agents additionally have:
- `decision_keywords: [decision, choice]`
- `default_skill` fallback (maintain_subsidy / maintain_premium)
- `strict_mode: false`

---

## 5. Governance Rules

Governance validation runs **after** LLM output, **before** skill execution. Two rule types:

### 5.1 Identity Rules (State-Based Blocks)

These block skills based on the agent's current dynamic state.

**Owner**:
| Rule ID | Precondition | Blocked Skills | Level |
|---|---|---|---|
| `elevated_already` | `dynamic_state["elevated"] == True` | `elevate_house` | ERROR |
| `relocated_already` | `dynamic_state["relocated"] == True` | `buy_insurance`, `elevate_house`, `buyout_program` | ERROR |

**Renter**:
| Rule ID | Precondition | Blocked Skills | Level |
|---|---|---|---|
| `relocated_already` | `dynamic_state["relocated"] == True` | `buy_contents_insurance`, `relocate` | ERROR |

**Institutional** (government, insurance): No identity rules.

### 5.2 Thinking Rules (PMT-Construct-Based Blocks)

These block skills based on the agent's self-reported PMT appraisal.

**Owner**:
| Rule ID | Condition | Blocked Skills | Message |
|---|---|---|---|
| `owner_inaction_high_threat` | TP = VH or H | `do_nothing` | "Inaction is irrational given your high threat perception." |
| `owner_complex_action_low_coping` | CP = VL or L | `elevate_house`, `buyout_program` | "Complex actions are blocked due to your low confidence in your ability to cope." |

**Renter**:
| Rule ID | Condition | Blocked Skills | Message |
|---|---|---|---|
| `renter_inaction_high_threat` | TP = VH or H | `do_nothing` | "Inaction is irrational given your high threat perception." |
| `renter_complex_action_low_coping` | CP = VL or L | `relocate` | "Relocation is blocked due to your low confidence in your ability to cope." |

**Institutional**: No thinking rules.

### 5.3 Governance Retry Behavior

When a rule is violated:
- `max_retries: 3` — LLM is re-prompted up to 3 times
- `max_reports_per_retry: 3` — up to 3 violation reports shown per retry
- Retry prompt includes the violation message and asks for a different choice

---

## 6. Memory Configuration

### 6.1 Engine Types per Agent

| Agent Type | Engine | Window | Notes |
|---|---|---|---|
| `household_owner` | `symbolic` (→ universal) | 3 | Flood sensor bins, importance-weighted retrieval |
| `household_renter` | `symbolic` (→ universal) | 3 | Same as owner |
| `government` | `window` | 5 | Recency-based retrieval |
| `insurance` | `window` | 5 | Recency-based retrieval |

### 6.2 Cognitive Configuration (`global_config.cognitive_config`)

| Agent Type | stimulus_key | arousal_threshold | ema_alpha | Engine |
|---|---|---|---|---|
| `household_owner` | `flood_depth_m` | 1.0 | 0.3 | universal |
| `household_renter` | `flood_depth_m` | 0.8 | 0.3 | universal |
| `nj_government` | `adaptation_gap` | 0.15 | 0.2 | window |
| `fema_nfip` | `loss_ratio` | 0.3 | 0.25 | window |

**Interpretation**: Household arousal is triggered by flood depth; government arousal by the gap between target and actual adaptation rates; insurance arousal by the loss ratio.

### 6.3 Symbolic Memory Sensors (Household)

```yaml
sensors:
  - path: flood_depth_m
    name: FLOOD
    bins:
      - label: SAFE      # depth <= 0.3m
        max: 0.3
      - label: MINOR      # 0.3 < depth <= 1.0m
        max: 1.0
      - label: MODERATE    # 1.0 < depth <= 2.0m
        max: 2.0
      - label: SEVERE      # depth > 2.0m
        max: 99.0
    arousal_threshold: 0.5
```

### 6.4 Retrieval Configuration

**Household** (importance-weighted):
| Emotional Tag | Weight | Source Tag | Weight |
|---|---|---|---|
| `critical` | 1.0 | `personal` | 1.0 |
| `fear` | 1.2 | `neighbor` | 0.7 |
| `major` | 0.9 | `community` | 0.5 |
| `positive` | 0.8 | | |
| `observation` | 0.4 | | |

Emotion keywords used for auto-tagging:
- **fear**: flood, damage, loss, destroy, water, inundation
- **hope**: subsidy, elevated, safe, protected, insurance, grant
- **anxiety**: premium, cost, afford, expense, budget

**MG household** additional retrieval tags: `subsidy`, `vulnerability`, `financial_hardship`
**NMG household** additional retrieval tags: `insurance`, `elevation`, `adaptation`

**Institutional** (recency-based): Top 5 most recent, no emotional weighting.

### 6.5 Reflection (`global_config.reflection`)

| Parameter | Value | Description |
|---|---|---|
| `interval` | 1 | Reflect every year |
| `batch_size` | 10 | Up to 10 memories per reflection batch |
| `importance_boost` | 0.9 | Reflection memories get 0.9 importance score |

Reflection triggers: after flood events (crisis years) or every 5 years. Uses stratified retrieval (1 personal + 1 neighbor + 3 reflection memories).

---

## 7. Interaction Mechanisms

### 7.1 Institutional → Household (Policy Broadcasting)

After each institutional agent's post_step:
1. Government decision updates `env["subsidy_rate"]` and `env["govt_message"]`
2. Insurance decision updates `env["premium_rate"]` and `env["insurance_message"]`
3. Household prompts include these via `{govt_message}` and `{insurance_message}` template vars

### 7.2 Household → Institutional (Feedback Loop)

| From | To | Data | Mechanism |
|---|---|---|---|
| Households | Government | `elevated_count`, `total_households`, `mg_ratio` | env global counters |
| Households | Insurance | `insured_count`, `total_households`, `loss_ratio`, `recent_claims` | env global counters |

### 7.3 Social Network (Household ↔ Household)

**Network type**: Watts-Strogatz Small World
- `max_neighbors: 5` per agent
- `same_region_weight: 0.7` — 70% neighbors from same geographic region, 30% random

**Observable neighbor data** (`observe_neighbors`):
- `elevated_count` / `insured_count` / `relocated_count`
- Formatted as `{social_gossip}` in household prompts

**Social influence multipliers**:
- SC multiplier: `1.0 + (elevation_rate + insurance_rate) * 0.3` (up to +30%)
- TP multiplier: `1.0 + relocation_rate * 0.2` (up to +20%)

### 7.4 Social Memory / Gossip (`social_memory_config`)

```yaml
gossip_enabled: true
max_gossip: 2              # Max gossip messages per agent per year
gossip_categories:
  - decision_reasoning      # "I decided to elevate because..."
  - flood_experience        # "We had severe flooding..."
  - adaptation_outcome      # "My elevation saved us from damage"
gossip_importance_threshold: 0.5
```

After each agent's post_step, if the agent's reasoning passes the importance threshold, it is stored as a social memory (`source: social`) accessible to neighbors.

### 7.5 Media Channels (`MediaHub`)

Two channels with distinct information properties:

| Channel | Delay | Reliability | Reach | Content Style |
|---|---|---|---|---|
| `NewsMediaChannel` | 1 year | 0.9 | Regional | Factual severity reports with water depth |
| `SocialMediaChannel` | Immediate | 0.4–0.8 | Local | 3–7 posts per event, exaggeration_factor=0.3 |

**News severity tiers**: catastrophic (≥1.5m), severe (≥1.0m), moderate (≥0.5m), minor, none

**Social media tones**: alarming, concerned, matter-of-fact, dismissive (randomly assigned)

MediaHub output is injected into `{global_news}` in household prompts.

### 7.6 Message Pool & Artifacts (Task-058)

**Generic infrastructure** (broker/):
- `MessagePool`: Typed message passing with `scope` (global/targeted)
- `ArtifactEnvelope`: Wraps domain artifacts for cross-agent communication
- `GameMaster`: Collects artifact submissions, runs cross-validation

**Flood domain artifacts** (examples/multi_agent/):
- `PolicyArtifact`: subsidy_rate, mg_priority, budget_remaining, target_adoption_rate
- `MarketArtifact`: premium_rate, loss_ratio, coverage_count, reserve_ratio
- `HouseholdIntention`: chosen_skill, threat_level, confidence, budget_available

### 7.7 Information Asymmetry

| Agent Type | Knows | Does NOT Know |
|---|---|---|
| Household | Local flood depth, own finances, neighbor gossip, public subsidies/premiums | FEMA solvency, government budget targets |
| Government | Global relocation rates, community damage averages, total budget | Individual agent's Place Attachment or debt |
| Insurance | Total claims, total premiums, community elevation rate | Agent's Threat Perception |

---

## 8. Environment & Hazard Module

### 8.1 Hazard Data Source

**Primary**: Passaic River Basin ASCII grid depth data (meters)
- Loaded via `PRBGridLoader` from `grid_dir`
- Per-agent depth assignment based on `(grid_x, grid_y)` position

**Fallback**: Synthetic depth sampling via `DepthSampler`
- Uses flood experience category to sample realistic depths

### 8.2 Flood Severity Classification

| Depth (m) | Depth (ft) | Severity | Memory Emotion |
|---|---|---|---|
| 0 | 0 | NONE | — |
| 0 < d < 0.6 | 0 < d < ~2 | MINOR | fear |
| 0.6 ≤ d < 1.2 | ~2 ≤ d < ~4 | MODERATE | fear |
| d ≥ 1.2 | d ≥ ~4 | SEVERE | fear |

### 8.3 Depth-Damage Curves

FEMA-style 20-point curves converting depth (feet) to damage ratio:
- `depth_damage_building(depth_ft)` → building damage ratio
- `depth_damage_contents(depth_ft)` → contents damage ratio

**Damage calculation**:
```
total_damage = rcv_building * damage_ratio_building + rcv_contents * damage_ratio_contents
```

If `is_elevated == True`: effective depth reduced by `h_elevate_ft` (5.0 ft freeboard).

### 8.4 Environmental State Variables

Updated in `pre_year` and `post_step`:

| Variable | Type | Updated By | Description |
|---|---|---|---|
| `year` | int | pre_year | Current simulation year |
| `flood_occurred` | bool | pre_year | Whether flood happened this year |
| `flood_depth_m` | float | pre_year | Max flood depth (meters) |
| `flood_depth_ft` | float | pre_year | Max flood depth (feet) |
| `avg_flood_depth_m` | float | pre_year | Average depth across agents |
| `flooded_household_count` | int | pre_year | Number of flooded agents |
| `total_households` | int | pre_year | Total household count |
| `elevated_count` | int | pre_year | Households with elevation |
| `insured_count` | int | pre_year | Households with insurance |
| `subsidy_rate` | float | post_step(govt) | Current subsidy rate [0.20, 0.95] |
| `premium_rate` | float | post_step(ins) | Current premium rate [0.01, 0.15] |
| `govt_message` | str | post_step(govt) | Government policy announcement |
| `insurance_message` | str | post_step(ins) | Insurance policy announcement |
| `crisis_event` | bool | pre_year | Same as flood_occurred |
| `crisis_boosters` | dict | pre_year | `{"emotion:fear": 1.5}` if flood |

### 8.5 Pending Action Resolution

Some skills take multiple years to complete:

| Action | Initiated By | Duration | Completion Effect |
|---|---|---|---|
| Elevation | `elevate_house` | +1 year | `dynamic_state["elevated"] = True` |
| Buyout | `buyout_program` | +2 years | `dynamic_state["relocated"] = True` |

Note: There is a bug in `lifecycle_hooks.py:163` where `elevate_house` sets pending_action to "buyout" instead of "elevation" on the second assignment. This should be fixed — the buyout branch should be under `elif decision == "buyout_program"`.

---

## 9. FloodABM Parameters

All statistical parameters are derived from the original FloodABM literature (Haer et al., Hung et al.).

### 9.1 PMT Construct Distributions (Beta)

Each construct is drawn from a Beta(alpha, beta) distribution, scaled to [1, 5].

| Construct | MG alpha | MG beta | NMG alpha | NMG beta |
|---|---|---|---|---|
| TP (Threat Perception) | 4.44 | 2.89 | 5.35 | 3.62 |
| CP (Coping Perception) | 4.07 | 3.30 | 5.27 | 4.18 |
| SP (Stakeholder Perception) | 1.37 | 1.69 | 1.73 | 1.93 |
| SC (Social Capital) | 2.37 | 3.11 | 4.56 | 2.39 |
| PA (Place Attachment) | 2.56 | 2.17 | 4.01 | 2.79 |

**MG** = Marginalized Group (lower income, higher vulnerability)
**NMG** = Non-Marginalized Group

### 9.2 TP Decay Model

Threat perception decays over time when no floods occur:

```
TP(t) = tau_inf + (tau_0 - tau_inf) * exp(-k * t) + alpha * exp(-beta * t) * shock
```

| Parameter | MG | NMG | Description |
|---|---|---|---|
| `alpha` | 0.50 | 0.22 | Shock response amplitude |
| `beta` | 0.21 | 0.10 | Shock decay rate |
| `tau_0` | 1.00 | 2.72 | Initial TP baseline |
| `tau_inf` | 32.19 | 50.10 | Long-term TP baseline |
| `k` | 0.03 | 0.01 | Baseline decay rate |
| `theta` | 0.50 | 0.50 | Decay threshold |
| `shock_scale` | 0.30 | 0.30 | Shock scaling factor |

MG agents have faster TP decay (forget risk faster) and lower baseline threat perception.

### 9.3 Insurance Parameters

| Parameter | Value | Source |
|---|---|---|
| `r1k_structure` | 3.56 | Rate per $1K structure coverage |
| `r1k_contents` | 4.90 | Rate per $1K contents coverage |
| `limit_structure` | $250,000 | NFIP maximum building coverage |
| `limit_contents` | $100,000 | NFIP maximum contents coverage |
| `deductible_structure` | $1,000 | Standard deductible |
| `deductible_contents` | $1,000 | Standard deductible |
| `reserve_fund_factor` | 1.15 | Reserve multiplier for solvency |
| `small_fee` | $100 | Minimum annual premium |

### 9.4 Initial Insurance Uptake

| Category | Rate |
|---|---|
| Flood-prone owner | 25% |
| Flood-prone renter | 8% |
| Non-flood-prone owner | 3% |
| Non-flood-prone renter | 1% |

### 9.5 Property Values (RCV Lognormal)

| Tenure | ln_mu | ln_sigma | Mean RCV (USD) | CV |
|---|---|---|---|---|
| Homeowner | 12.46 | 0.63 | $313,250 | 0.69 |
| Renter | 12.82 | 1.20 | $766,352 | 1.81 |

Contents-to-structure ratio (CSRV): **0.57**

### 9.6 Elevation Parameters

| Parameter | Value |
|---|---|
| `h_elevate_ft` | 5.0 ft (freeboard above BFE) |
| `ffe_default_ft` | 1.0 ft (default first-floor elevation) |

---

## 10. Execution Flow

### 10.1 Year-Level Lifecycle (MultiAgentHooks)

```python
hooks = MultiAgentHooks(
    environment=env,
    memory_engine=memory_engine,
    hazard_module=hazard_module,
    media_hub=media_hub,
    per_agent_depth=True,          # Per-agent spatial flood depths
    year_mapping=year_mapping,     # Maps sim year → PRB grid year
    game_master=game_master,       # Optional: Task-058 artifact routing
    message_pool=message_pool,     # Optional: Task-058 typed messaging
)
```

### 10.2 Detailed Step Flow

**pre_year(year, env, agents)**:
1. Resolve pending actions (elevation completes after 1 year, buyout after 2)
2. Query HazardModule for flood depths (per-agent from PRB grid or community-level)
3. Update env: `flood_occurred`, `flood_depth_m`, `flooded_household_count`
4. MediaHub broadcasts flood event (if occurred)
5. Count community stats: `total_households`, `elevated_count`, `insured_count`

**Tier 1 execution** (sequential):
1. Government agent runs → post_step updates `subsidy_rate` + `govt_message`
2. Insurance agent runs → post_step updates `premium_rate` + `insurance_message`

**Tier 2 execution** (parallel, via ThreadPoolExecutor):
1. Each household receives context (personal + memory + policy + media + gossip)
2. LLM generates PMT appraisals + decision
3. Governance validates (identity_rules → thinking_rules)
4. On violation: retry up to 3 times with violation feedback
5. post_step updates agent state + stores reasoning as social memory

**post_year(year, agents, memory_engine)**:
1. Calculate flood damage for each non-relocated household
2. Store flood experience memory: `"Year N: We experienced [severity] which caused $X damage"`
3. Store important unread MessagePool messages as memories (max 3)
4. Trigger reflection for household agents (crisis years or every 5 years)

### 10.3 Damage Calculation

```python
depth_ft = agent_depth_m * 3.28084
if agent.elevated:
    depth_ft = max(0, depth_ft - h_elevate_ft)  # Reduce by freeboard

damage_building = depth_damage_building(depth_ft) * rcv_building
damage_contents = depth_damage_contents(depth_ft) * rcv_contents
total_damage = damage_building + damage_contents
agent.cumulative_damage += total_damage
```

---

## 11. Running the Experiment

### 11.1 CLI Usage

```powershell
python examples/multi_agent/run_unified_experiment.py \
  --model llama3.2:3b \
  --agents 100 \
  --years 10 \
  --output examples/multi_agent/results_unified \
  --memory-engine humancentric \
  --gossip \
  --verbose
```

### 11.2 Key Arguments

| Argument | Default | Description |
|---|---|---|
| `--model` | `gpt-oss:latest` | LLM model identifier |
| `--agents` | 10 | Number of household agents (random mode) |
| `--years` | 10 | Simulation years |
| `--output` | `results_unified` | Output directory |
| `--memory-engine` | `humancentric` | Memory engine: window, humancentric, hierarchical, universal |
| `--gossip` | False | Enable neighbor gossip (social memory) |
| `--verbose` | False | Enable verbose LLM output |

### 11.3 LLM Configuration (`global_config.llm`)

| Parameter | Value |
|---|---|
| `temperature` | 0.1 |
| `top_p` | 0.9 |
| `top_k` | 40 |
| `max_retries` | 2 |

---

## 12. Phase Orchestrator Lifecycle (Detailed)

The MA simulation uses a 4-phase lifecycle orchestrated by `MultiAgentHooks` (in `orchestration/lifecycle_hooks.py`). Each phase maps to a method call from the broker engine:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        YEAR N LIFECYCLE                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PHASE 1: PRE_YEAR (hooks.pre_year)                                    │
│  ┌───────────────────────────────────────────────────────────┐          │
│  │ 1. Resolve pending actions (elevation, buyout timers)     │          │
│  │ 2. HazardModule → flood depths (PRB grid or synthetic)    │          │
│  │ 3. Update env: flood_occurred, flood_depth_m              │          │
│  │ 4. MediaHub.broadcast() → news + social media posts       │          │
│  │ 5. DriftDetector.analyze() → population entropy           │          │
│  │ 6. Count: elevated_count, insured_count, relocated_count  │          │
│  └───────────────────────────────────────────────────────────┘          │
│                            ↓                                            │
│  PHASE 2: INSTITUTIONAL TIER (sequential, via broker engine)           │
│  ┌───────────────────────────────────────────────────────────┐          │
│  │ Government → decide subsidy_rate                          │          │
│  │   └─ post_step: env[subsidy_rate], MessagePool.publish()  │          │
│  │ Insurance  → decide premium_rate                          │          │
│  │   └─ post_step: env[premium_rate], MessagePool.publish()  │          │
│  └───────────────────────────────────────────────────────────┘          │
│                            ↓                                            │
│  PHASE 3: HOUSEHOLD TIER (parallel, ThreadPoolExecutor)                │
│  ┌───────────────────────────────────────────────────────────┐          │
│  │ For each household agent (owner/renter):                  │          │
│  │   1. Build context (TieredContextBuilder)                 │          │
│  │      └─ Personal + Memory + Social + Institutional        │          │
│  │   2. LLM generates PMT ratings + decision                 │          │
│  │   3. GovernanceValidator checks rules                     │          │
│  │      └─ identity_rules → thinking_rules                   │          │
│  │   4. On violation: retry with feedback (max 3x)           │          │
│  │   5. post_step: update state + store memory               │          │
│  │      └─ MessagePool.publish(HouseholdIntention)           │          │
│  └───────────────────────────────────────────────────────────┘          │
│                            ↓                                            │
│  PHASE 4: POST_YEAR (hooks.post_year)                                  │
│  ┌───────────────────────────────────────────────────────────┐          │
│  │ 1. Calculate flood damage per agent (depth-damage curves) │          │
│  │ 2. Store flood memory (emotion: fear, importance: 0.95)   │          │
│  │ 3. Deliver unread MessagePool messages as memories         │          │
│  │ 4. Trigger reflection (crisis years or every 5 years)     │          │
│  │ 5. GameMaster.resolve() → cross-validate artifacts        │          │
│  │ 6. ObservableStateManager.compute() → metrics snapshot    │          │
│  └───────────────────────────────────────────────────────────┘          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 12.1 Hook Methods

| Method | Called By | Arguments | Key Actions |
|---|---|---|---|
| `pre_year(year, env, agents)` | Broker engine before agent loop | Year index, environment dict, agent dict | Flood resolution, pending actions, media broadcast |
| `post_step(agent_id, decision, env, agents)` | Broker engine after each agent | Agent ID, approved skill result, env, agents | State updates, memory storage, MessagePool publish |
| `post_year(year, agents, memory_engine)` | Broker engine after all agents | Year, agents, memory engine | Damage calc, reflection, message delivery |

### 12.2 Key Data Flow

```
HazardModule ──→ env[flood_depth_m] ──→ TieredContextBuilder ──→ LLM Prompt
                                    └──→ post_year damage calc

Government ──→ env[subsidy_rate] ──→ Household prompt {subsidy_rate}
           └──→ MessagePool(PolicyArtifact) ──→ GameMaster cross-validation

Insurance ──→ env[premium_rate] ──→ Household prompt {premium_rate}
          └──→ MessagePool(MarketArtifact) ──→ GameMaster cross-validation
```

---

## 13. Message Pool Architecture

The MessagePool (`broker/components/message_pool.py`) provides typed pub-sub messaging between agents across simulation tiers.

### 13.1 Core Concepts

| Concept | Description |
|---|---|
| **Message** | Typed payload with sender, scope, TTL, priority |
| **Scope** | `GLOBAL` (all agents) or `TARGETED` (specific recipients) |
| **TTL** | Time-to-live in simulation steps (default: 1 year) |
| **Mailbox** | Per-agent queue for incoming messages |
| **Priority** | Higher priority messages delivered first |

### 13.2 Message Types

| Type | Sender | Scope | Content |
|---|---|---|---|
| `policy_update` | Government | Global | New subsidy rate, MG priority, budget |
| `market_update` | Insurance | Global | Premium rate, loss ratio, reserves |
| `household_intention` | Household | Targeted (neighbors) | Chosen skill, threat level |
| `flood_report` | Environment (via MediaHub) | Global | Flood severity, depth |

### 13.3 Flow

```
Government                  Insurance
    │                          │
    ▼                          ▼
MessagePool.publish()     MessagePool.publish()
    │                          │
    └──────────┬───────────────┘
               ▼
        MessagePool (sorted by priority)
               │
    ┌──────────┼──────────────┐
    ▼          ▼              ▼
 Agent_1    Agent_2  ...   Agent_N
 (mailbox)  (mailbox)     (mailbox)
    │
    ▼
 post_year: deliver() → store as memory
```

### 13.4 Artifact System (Task-058)

Artifacts extend messages with structured data and cross-agent validation:

| Component | Role |
|---|---|
| `ArtifactEnvelope` | Wraps domain artifacts (PolicyArtifact, MarketArtifact, HouseholdIntention) |
| `GameMaster` | Collects envelopes, runs cross-validation rules |
| `CrossAgentValidator` | Checks consistency (e.g., subsidy + premium ≤ budget) |

---

## 14. Observable State Metrics

The `ObservableStateManager` (`broker/components/observable_state.py`) computes cross-agent metrics at multiple scopes. These metrics are used by institutional agents and drift detection.

### 14.1 Scope Levels

| Scope | Description | Example |
|---|---|---|
| `COMMUNITY` | Aggregate across all agents | Insurance penetration rate |
| `TYPE` | Grouped by agent type | Owner vs renter adaptation rate |
| `NEIGHBORS` | Per-agent neighborhood | Neighbor insurance rate |
| `SPATIAL` | Per-region (tract/grid cell) | Regional elevation rate |

### 14.2 Pre-built Flood Metrics

Registered via `create_flood_observables()`:

| Metric | Scope | Description | Computation |
|---|---|---|---|
| `insurance_penetration_rate` | Community | % active agents insured | `count(has_insurance) / count(active)` |
| `elevation_penetration_rate` | Community | % active agents elevated | `count(elevated) / count(active)` |
| `adaptation_rate` | Community | % with any protection | `count(elevated OR insured) / count(active)` |
| `relocation_rate` | Community | % of all agents relocated | `count(relocated) / count(all)` |
| `neighbor_insurance_rate` | Neighbors | % of neighbors insured | Per-agent, uses Watts-Strogatz graph |
| `neighbor_elevation_rate` | Neighbors | % of neighbors elevated | Per-agent, uses Watts-Strogatz graph |

### 14.3 Drift Metrics

Registered via `create_drift_observables()`:

| Metric | Description | Trigger |
|---|---|---|
| `decision_entropy` | Shannon entropy of action distribution | Low entropy = convergence/herding |
| `dominant_action_pct` | % of agents choosing most popular action | High = potential herd behavior |
| `stagnation_rate` | % of agents repeating same action (Jaccard) | High = lack of adaptation |

### 14.4 Usage

```python
from broker.components.observable_state import ObservableStateManager, create_flood_observables

manager = ObservableStateManager()
manager.register_many(create_flood_observables())
manager.set_neighbor_graph(social_network)

# Each year:
snapshot = manager.compute(agents, year=current_year)
insurance_rate = snapshot.community["insurance_penetration_rate"]
```

---

## 15. Skill Registry (Action Space Governance)

The Skill Registry (`broker/components/skill_registry.py`) defines the **action space governance contract** — what agents can do, who can do it, and under what conditions.

### 15.1 Purpose

```
LLM proposes skill → SkillBrokerEngine validates → Simulation executes
```

| Function | Description |
|---|---|
| **Governance** | Prevents impossible/illegal actions (e.g., renter can't elevate) |
| **Audit Trail** | Every decision traceable to a registered skill |
| **Precondition Checking** | Runtime validation (can't elevate if already elevated) |
| **Extensibility** | New actions via YAML, not code |
| **Eligibility Control** | Per-agent-type skill availability |

### 15.2 Skill Definition Structure

Each skill is defined in `skill_registry.yaml`:

```yaml
skills:
  - skill_id: elevate_house
    description: "Elevate your house above flood level (costs ~$30,000-80,000)"
    eligible_agent_types: [household_owner]
    preconditions:
      - type: attribute
        field: elevated
        operator: "=="
        value: false
    institutional_constraints:
      requires_subsidy: true
    allowed_state_changes:
      - field: pending_action
        value: elevate_house
    implementation_mapping: "agent.set_pending_action('elevate_house')"
```

### 15.3 Flood Domain Skills

| Skill ID | Eligible Types | Preconditions | Effect |
|---|---|---|---|
| `do_nothing` | All | None | No state change |
| `buy_insurance` | household_owner, household_renter | Not insured | Sets `has_insurance=True` |
| `drop_insurance` | household_owner, household_renter | Currently insured | Sets `has_insurance=False` |
| `elevate_house` | household_owner | Not elevated, not pending | Sets pending (completes next year) |
| `buyout_program` | household_owner | Not relocated | Sets pending (completes in 2 years) |
| `relocate` | household_owner | Not relocated | Sets `relocated=True` |
| `increase_subsidy` | government | None | Adjusts `subsidy_rate` |
| `decrease_subsidy` | government | None | Adjusts `subsidy_rate` |
| `maintain_subsidy` | government | None | No change |
| `raise_premium` | insurance | None | Adjusts `premium_rate` |
| `lower_premium` | insurance | None | Adjusts `premium_rate` |
| `maintain_premium` | insurance | None | No change |

### 15.4 Validation Flow

```
1. LLM outputs decision (e.g., "1" → buy_insurance)
2. ModelAdapter parses → SkillProposal(skill_name="buy_insurance")
3. SkillBrokerEngine calls:
   a. skill_registry.check_eligibility(skill, agent_type)
   b. identity_rules validation (agent state prerequisites)
   c. thinking_rules validation (PMT construct coherence)
4. If all pass → ApprovedSkill → simulation executes
5. If violation → retry with feedback (up to 3x) → fallout to do_nothing
```

---

## Appendix: File Map

### Configuration
| File | Purpose |
|---|---|
| `ma_agent_types.yaml` | Master configuration: prompts, skills, parsing, PMT, governance, memory |

### Orchestration
| File | Purpose |
|---|---|
| `run_unified_experiment.py` | Main experiment runner |
| `orchestration/lifecycle_hooks.py` | Year lifecycle: pre_year, post_step, post_year |
| `orchestration/agent_factories.py` | Agent creation: government, insurance, household |
| `orchestration/disaster_sim.py` | Depth-to-qualitative description mapping |

### Environment
| File | Purpose |
|---|---|
| `environment/hazard.py` | HazardModule, FloodEvent, VulnerabilityModule |
| `environment/social_network.py` | SocialNetwork: Watts-Strogatz graph, neighbor observation |
| `environment/depth_sampler.py` | DepthSampler: synthetic flood depth by experience category |
| `environment/prb_loader.py` | PRBGridLoader: ASCII grid data I/O |
| `environment/year_mapping.py` | YearMapping: simulation year → PRB grid year |
| `environment/vulnerability.py` | FEMA depth-damage curves |

### Components
| File | Purpose |
|---|---|
| `components/media_channels.py` | MediaHub, NewsMediaChannel, SocialMediaChannel |
| `generate_agents.py` | Agent generation from survey or random |
| `initial_memory.py` | Seed initial memories for agents |

### Task-058 Domain Files
| File | Purpose |
|---|---|
| `ma_artifacts.py` | Flood-specific artifact dataclasses |
| `ma_cross_validators.py` | Flood-specific cross-agent validation rules |
| `ma_role_config.py` | Flood-specific role permission config |
| `ma_saga_definitions.py` | Flood-specific saga workflow definitions |
