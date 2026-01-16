# Multi-Agent Benchmark: Social & Institutional Dynamics

This benchmark extends the framework to a **Multi-Agent System (MAS)** where 50+ household agents interact with each other and with institutional actors (Government, Insurance) over a 10-year period.

## Research Questions

This experiment addresses three core research questions about flood adaptation differences between renters and homeowners:

### RQ1: Adaptation Continuation vs Inaction

> **How does continued adaptation, compared with no action, differentially affect long-term flood outcomes for renters and homeowners?**

**Hypothesis**: Homeowners benefit more from continued adaptation due to structure ownership, while renters face mobility constraints that may limit sustained investment.

**Metrics**:
- Cumulative damage over 10 years by tenure
- Adaptation state distribution (None/Insurance/Elevation/Both/Relocate)
- Financial recovery trajectories

### RQ2: Post-Flood Adaptation Trajectories

> **How do renters and homeowners differ in their adaptation trajectories following major flood events?**

**Hypothesis**: Major flood events trigger faster adaptation in homeowners (elevation, insurance) vs renters (relocation preference).

**Metrics**:
- Adaptation action within 1 year post-flood
- Trajectory divergence (owner vs renter paths)
- Memory salience of flood events

### RQ3: Insurance Coverage & Financial Outcomes

> **How do tenure-based insurance coverage differences shape long-term financial outcomes under repeated flood exposure?**

**Hypothesis**: Contents-only coverage for renters provides less financial protection than full structure+contents coverage for owners.

**Metrics**:
- Insured vs uninsured losses by tenure
- Insurance persistence (renewal rates)
- Out-of-pocket expenses ratio

---

## Experiment Design

We test three distinct configurations to isolate the effects of **Social Interaction** and **Memory Systems**:

| Scenario             | Memory Engine   | Social Gossip | Description                                                                                                                             |
| :------------------- | :-------------- | :------------ | :-------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Isolated**      | Window (Size=1) | ❌ Disabled   | **Baseline Control**. Agents act independently with minimal memory context.                                                             |
| **2. Window**        | Window (Size=3) | ✅ Enabled    | **Social Standard**. Agents share reasoning ("Why I elevated") and valid social proof enters their memory stream.                       |
| **3. Human-Centric** | Human-Centric   | ✅ Enabled    | **Advanced Cognitive**. Uses Importance/Recency/Relevance scoring to retain critical memories (e.g., past floods) despite social noise. |

## Key Features

### 1. Institutional Agents

Unlike the Single-Agent simulation, this environment includes dynamic institutions:

- **NJ State Government**: Adjusts **Subsidy Rates** (Grant %) based on budget and adoption.
- **FEMA/NFIP**: Adjusts **Insurance Premiums** based on the program's Loss Ratio.
  - _Effect_: Agents must react to changing economic incentives (e.g., rising premiums might trigger relocation).

### 2. Social Network (Gossip)

- **Reasoning Propagation**: When an agent makes a decision (e.g., "Elevate House"), their _reasoning_ is broadcast to neighbors (k=4 network).
- **Social Proof**: Neighbors receive this as a memory trace: _"Neighbor X decided to Elevate because [Reason]"_. This influences their subsequent threat/coping appraisal.

### 3. Lifecycle Hooks

- **Pre-Year**: Flood event determination ($P=0.3$), pending action resolution (e.g., Elevation takes 1 year to complete).
- **Post-Step**: Institutional global state updates (Subsidy/Premium changes).
- **Post-Year**: Flood damage calculation (impacts emotional memory) and memory consolidation.

### 4. Hazard Analysis Tools (PRB ASCII Grid)

Use the PRB multi-year analysis utilities to inspect hazard history and generate plots:

```powershell
# Run PRB multi-year analysis
python examples/multi_agent/hazard/prb_analysis.py --data-dir "C:\path\to\PRB" --output analysis_results/

# Generate visualizations
python examples/multi_agent/hazard/prb_visualize.py --data-dir "C:\path\to\PRB" --output plots/
```

## How to Run

Use the provided PowerShell script to run the full benchmark across all models and scenarios:

```powershell
./examples/multi_agent/run_ma_benchmark.ps1
```

### Configuration

- **Agents**: 50 (Mix of Owners/Renters)
- **Years**: 10
- **Models**: Llama 3.2, Gemma 2, DeepSeek-R1 (configurable in script)

## Output Structure

Results are saved to `examples/multi_agent/results_benchmark/`:

```
results_benchmark/
├── llama3_2_3b_isolated/
├── llama3_2_3b_window/
├── llama3_2_3b_humancentric/
...
```

Each folder contains:

- `simulation_log.csv`: Decisions and actions.
- `household_governance_audit.csv`: Perception and validation logs.
- `institutional_log.csv`: Government/Insurance state changes.

## Disaster Model Equations

### Damage Calculation

Flood damage is calculated using FEMA depth-damage curves:

```
Damage = f(depth_ft, RCV, elevation_status, insurance)
```

**Building Damage Ratio** (USACE depth-damage function):
```
if depth_ft <= 0:
    ratio = 0
elif depth_ft <= 1:
    ratio = 0.08 * depth_ft
elif depth_ft <= 4:
    ratio = 0.08 + (depth_ft - 1) * 0.12
elif depth_ft <= 8:
    ratio = 0.44 + (depth_ft - 4) * 0.10
else:
    ratio = min(0.84 + (depth_ft - 8) * 0.02, 1.0)
```

**Elevation Reduction**:
- Elevated homes (BFE+1): 95% damage reduction
- Overtopped (severity > 0.9): 50% damage reduction

**Total Damage**:
```
building_damage = RCV_building * building_ratio * elevation_factor
contents_damage = RCV_contents * contents_ratio  # ~30% of building ratio
total_damage = building_damage + contents_damage
```

### Insurance Settlement

**NFIP Coverage Limits**:
- Building: $250,000 max
- Contents: $100,000 max
- Deductible: $1,000-$10,000 (default: $2,000)

**Payout Calculation**:
```
covered_building = min(building_damage, 250_000)
covered_contents = min(contents_damage, 100_000)
gross_claim = covered_building + covered_contents
payout = max(0, gross_claim - deductible)
out_of_pocket = total_damage - payout
```

### Subsidy Allocation

**Government Grant Program** (FEMA HMA):
```
base_cost = action_cost  # e.g., $150,000 for elevation
subsidy_amount = base_cost * subsidy_rate
net_cost = base_cost - subsidy_amount
```

**MG Priority Bonus**:
- MG households: Up to +25% additional subsidy (max 75% total)
- Subsidy rate range: 20%-95%

### Premium Adjustment

**Insurance Premium Logic** (Risk Rating 2.0):
```
base_premium = property_value * base_rate  # ~0.4% typical
loss_ratio = total_claims / total_premiums  # Target: <0.70

if loss_ratio > 0.80:
    premium_rate += 0.5%  # Raise premium
elif loss_ratio < 0.60 and insured_rate < target:
    premium_rate -= 0.5%  # Lower to attract customers
```

**Premium Rate Range**: 1%-15%

## Agent Demographics

### Population Distribution (N=50)

| Group | Count | Share |
|-------|-------|-------|
| **Owners** | 32 | 64% |
| **Renters** | 18 | 36% |
| **MG (Marginalized)** | 17 | 35% |
| **NMG (Non-Marginalized)** | 33 | 65% |

### MG Classification Criteria

An agent is classified as **Marginalized Group (MG)** if they meet 2+ of:
1. **Housing Cost Burden**: >30% of income on housing
2. **No Vehicle**: Limits evacuation options
3. **Below Poverty Line**: Federal poverty threshold

### Income Stratification

| Level | Range | Share | Typical RCV |
|-------|-------|-------|-------------|
| Low | <$35K | 30% | $150K building, $40K contents |
| Medium | $35K-$75K | 50% | $220K building, $55K contents |
| High | >$75K | 20% | $350K building, $85K contents |

### Initial Adaptation State

| State | Owner Rate | Renter Rate |
|-------|------------|-------------|
| Has Insurance | 40% | 20% |
| Elevated | 15% | N/A |
| Neither | 45% | 80% |

## Analysis Tools

### Policy Impact Assessment

Analyze government/insurance policy effects:

```powershell
python analysis/policy_impact.py --results results/window/simulation_log.csv
```

Outputs:
- Subsidy sensitivity analysis (MG vs NMG adoption rates)
- Premium sensitivity analysis (insurance uptake by level)
- Threshold identification for behavioral change

### Equity Metrics

Track equity across demographic groups:

```powershell
python analysis/equity_metrics.py --results results/simulation_log.csv
```

Outputs:
- MG/NMG adoption gap (Target: <15%)
- Owner/Renter adaptation gap
- Gini coefficient for adaptation distribution
- Vulnerability index

### RQ Experiment Scripts

Run the research question experiments:

```powershell
# RQ1: Adaptation impact analysis
python experiments/run_rq1_adaptation_impact.py --results results/simulation_log.csv

# RQ2: Post-flood trajectory analysis
python experiments/run_rq2_postflood_trajectory.py --results results/simulation_log.csv

# RQ3: Insurance outcomes analysis
python experiments/run_rq3_insurance_outcomes.py --results results/simulation_log.csv

# Test with mock data
python experiments/run_rq1_adaptation_impact.py --model mock
```

Each script outputs:
- Console summary with key metrics
- JSON report file (e.g., `rq1_results.json`)
