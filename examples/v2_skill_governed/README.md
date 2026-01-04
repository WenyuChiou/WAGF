# Flood Adaptation Skill-Governed Example

![Example Flow](example_flow.png)

## Overview

This example demonstrates the Skill-Governed Framework applied to flood adaptation decision-making. Agents decide annually whether to buy insurance, elevate their house, relocate, or do nothing based on flood risk assessment.

---

## Defined Skills

The following skills are registered in `skill_registry.yaml`:

| Skill ID | Description | Constraints | State Changes |
|----------|-------------|-------------|---------------|
| `buy_insurance` | Purchase flood insurance | Annual (renewable) | `has_insurance = true` |
| `elevate_house` | Elevate house structure | **Once-only** | `elevated = true` |
| `relocate` | Permanently leave flood zone | **Once-only, Permanent** | `relocated = true` |
| `do_nothing` | Take no action this year | None | None |

```yaml
# skill_registry.yaml excerpt
skills:
  - skill_id: elevate_house
    preconditions: ["not elevated"]
    institutional_constraints:
      once_only: true
      cost_type: "one_time"
```

---

## State Architecture

Agent state is organized in multiple levels:

### Individual State (Per-Agent)

```python
@dataclass
class FloodAgent:
    # Core attributes
    id: str
    elevated: bool = False           # Physical adaptation
    has_insurance: bool = False      # Financial protection
    relocated: bool = False          # Permanent migration
    
    # Trust attributes (PMT-related)
    trust_in_insurance: float = 0.3  # Affects coping appraisal
    trust_in_neighbors: float = 0.4  # Social influence
    
    # Context attributes
    memory: List[str] = []           # Recent experiences
    flood_threshold: float = 0.5     # Vulnerability perception
```

### State Levels

| Level | Examples | Access |
|-------|----------|--------|
| **Individual** | trust, elevated, has_insurance, memory | Agent-only |
| **Shared** | flood_event, year, community_stats | All agents (read) |
| **Institutional** | policy_mode, subsidy_rate | System-only |

### Trust in Context

Trust values are verbalized and included in LLM prompts:

```python
# trust_in_insurance: 0.3 → "have slight doubts about"
# trust_in_neighbors: 0.7 → "generally trust"
```

---

## Using Survey Data (Demographic Attributes)

The framework supports loading agent profiles from CSV files with real-world survey data.

### 1. Prepare CSV File

Create `agent_initial_profiles.csv` in the framework root:

```csv
id,elevated,has_insurance,trust_in_insurance,trust_in_neighbors,flood_threshold,age,income,education
Agent_1,False,False,0.35,0.45,0.5,45,high,master
Agent_2,False,True,0.52,0.38,0.6,32,middle,bachelor
Agent_3,True,False,0.28,0.62,0.4,58,low,high_school
...
```

### 2. Extend FloodAgent (Optional)

Add demographic fields to `FloodAgent` dataclass:

```python
@dataclass
class FloodAgent:
    # Existing fields...
    
    # Demographic attributes from survey
    age: int = 40
    income: str = "middle"           # low/middle/high
    education: str = "bachelor"      # high_school/bachelor/master/phd
    household_size: int = 3
    years_in_community: int = 10
    homeownership: str = "owner"     # owner/renter
```

### 3. Update ContextBuilder

Include demographics in LLM prompt context:

```python
def build(self, agent_id: str) -> Dict[str, Any]:
    return {
        # Existing context...
        "age": agent.age,
        "income": agent.income,
        "education": agent.education,
        # Can be used in prompt template
    }
```

### 4. Auto-Loading

The framework automatically loads CSV if present:

```python
# In FloodSimulation.__init__()
agent_file = base_dir / "agent_initial_profiles.csv"
if agent_file.exists():
    df = pd.read_csv(agent_file)
    for _, row in df.iterrows():
        self.agents[row['id']] = FloodAgent(
            trust_in_insurance=float(row['trust_in_insurance']),
            # Load any additional columns...
        )
```

## Active Validators

This example uses the following validation pipeline:

| # | Validator | Purpose | Example Rejection |
|---|-----------|---------|-------------------|
| 1 | **Admissibility** | Skill exists? Agent eligible? | Unknown skill "buy_boat" |
| 2 | **Feasibility** | Preconditions met? | Already elevated → cannot elevate again |
| 3 | **Constraints** | Once-only/annual rules? | Already relocated → cannot relocate |
| 4 | **Effect Safety** | State changes valid? | Invalid state mutation |
| 5 | **PMT Consistency** | Reasoning matches decision? | "Too expensive" + chose relocate |

### Key PMT Consistency Rules

```python
# Rule 4: Financial Consistency (most impactful)
if skill in ["elevate_house", "relocate"]:
    if "cannot afford" in coping or "too expensive" in coping:
        REJECT("Claims cannot afford but chose expensive option")
```

### Literature Support for Validator Rules

All PMTConsistencyValidator rules are backed by peer-reviewed empirical research:

| Rule | Logic | Key Study | DOI |
|------|-------|-----------|-----|
| R1 | HIGH TP + HIGH CP + do_nothing | Bamberg et al. (2017) Meta, N=35,419 | 10.1016/j.jenvp.2017.08.001 |
| R2 | LOW TP + relocate | Weyrich et al. (2020), N=1,019 | 10.5194/nhess-20-287-2020 |
| R3 | Flood + claims safe | Choi et al. (2024) US County | 10.1029/2023EF004110 |
| R4 | Cannot afford + expensive | Botzen et al. (2019) NYC, N=1,000+ | 10.1111/risa.13318 |

**Full literature documentation**: See [`docs/validator_design_readme.md`](../../docs/validator_design_readme.md)

**BibTeX for Zotero**: 
- `docs/references/pmt_flood_literature.bib` (14 entries, global)
- `docs/references/us_flood_literature.bib` (20 entries, US-specific)

---

## Experiment Results

### Dataset
- **Models**: Llama 3.2 (3B), Gemma 3 (4B), GPT-OSS (20B), DeepSeek R1 (8B)
- **Duration**: 10 years simulation
- **Agents**: 100 per model

### Decision Distribution (Skill-Governed)

| Model | Total | Elevation | Insurance | Relocate | Do Nothing |
|-------|-------|-----------|-----------|----------|------------|
| Llama 3.2 | 814 | **587** (72%) | 192 (24%) | 47 (6%) | 153 (19%) |
| Gemma 3 | 999 | **799** (80%) | 206 (21%) | 1 (<1%) | 177 (18%) |
| GPT-OSS | 976 | **859** (88%) | 459 (47%) | 4 (<1%) | 51 (5%) |
| DeepSeek | 945 | **679** (72%) | 384 (41%) | 22 (2%) | 164 (17%) |

### Relocation Rate Comparison

| Model | No MCP | Old MCP | Skill-Governed | Improvement |
|-------|--------|---------|----------------|-------------|
| Llama 3.2 | 95% | 99% | **6%** | ↓ 93pp |
| Gemma 3 | 6% | 13% | **<1%** | ↓ 12pp |
| GPT-OSS | 0% | 2% | **<1%** | - |
| DeepSeek | 14% | 39% | **2%** | ↓ 37pp |

---

## Model-Specific Analysis

### Llama 3.2 (3B) - Panic-Prone Model
**Problem Without Framework:**
- 95% relocation rate = "panic-driven" decisions
- LLM generates: "I'm scared, I'll relocate" even when unaffordable

**With Skill-Governed:**
- Financial consistency check catches "too expensive + relocate" contradictions
- Retry mechanism allows LLM to reconsider → chooses Elevation instead
- Result: Rational 72% Elevation, only 6% Relocation

### Gemma 3 (4B) - Conservative Model
**Baseline Behavior:**
- Already low relocation (6%) without governance
- Tends toward Elevation naturally

**With Skill-Governed:**
- Reinforces conservative behavior
- Highest Elevation rate (80%)
- Minimal improvement needed, framework validates existing rationality

### GPT-OSS (20B) - Balanced Model
**Baseline Behavior:**
- Near-zero relocation even without governance
- Most balanced Insurance + Elevation combination

**With Skill-Governed:**
- Best combined adaptation: 88% Elevation + 47% Insurance
- Lowest "Do Nothing" rate (5%) = most proactive
- Framework confirms already-rational behavior

### DeepSeek R1 (8B) - Moderate Improvement
**Problem Without Framework:**
- 14% → 39% relocation jump with Old MCP
- Old MCP actually worsened behavior

**With Skill-Governed:**
- Financial check prevents 37pp of irrational relocations
- Good Insurance adoption (41%)
- Framework essential for this model

---

## Key Improvement Points

### 1. Financial Consistency Check (Biggest Impact)
```
❌ OLD: "Too expensive but I'll relocate" → PASS
✅ NEW: Same response → REJECT → Retry → "I'll elevate instead"
```
**Impact:** Llama relocation ↓ 93pp, DeepSeek ↓ 37pp

### 2. Once-Only Constraint Enforcement
```
❌ OLD: Agent can say "relocate" every year
✅ NEW: Registry enforces permanent/once-only rules
```
**Impact:** Prevents repeated expensive decisions

### 3. Structured Skill Proposal
```
❌ OLD: Free-form LLM output, parsing errors
✅ NEW: JSON structure { skill, reasoning } - always parseable
```
**Impact:** 99.8% approval rate after retry

### 4. Audit Trail for Reproducibility
```
❌ OLD: Only final decision logged
✅ NEW: Full reasoning + validation result logged
```
**Impact:** Complete reproducibility for research

## Performance Analysis

### Why Skill-Governed Works Better

1. **Financial Consistency Check (Rule 4)**
   - Old MCP: "Too expensive but I'll relocate" → ✅ PASS (no check)
   - Skill-Governed: Same response → ❌ REJECT → Agent retries with budget-aware choice

2. **State Persistence Enforcement**
   - Once-only skills (elevate, relocate) enforced at registry level
   - Prevents repeated expensive actions

3. **Multi-Layer Validation**
   - 5 validators catch different types of inconsistency
   - Each layer filters out irrational decisions

### Approval Rate

| Model | First-Pass Approved | Retry Success | Rejected | Total Approval |
|-------|---------------------|---------------|----------|----------------|
| Llama | 752 (92%) | 58 (7%) | 4 (<1%) | **99.5%** |
| Gemma | 941 (94%) | 56 (6%) | 2 (<1%) | **99.8%** |
| GPT-OSS | 900 (92%) | 74 (8%) | 2 (<1%) | **99.8%** |
| DeepSeek | 876 (93%) | 67 (7%) | 2 (<1%) | **99.8%** |

---

## How to Run

```bash
cd examples/v2_skill_governed
python run_experiment.py --model llama3.2:3b --num-agents 100 --num-years 10
```

### Customize Skills

Edit `skill_registry.yaml` to add new skills:

```yaml
- skill_id: apply_for_grant
  description: "Apply for government elevation grant"
  preconditions: ["not elevated", "income < threshold"]
  institutional_constraints:
    requires_approval: true
```

### Customize Validators

Edit validator config to enable/disable rules:

```yaml
validators:
  - name: pmt_consistency
    enabled: true
    rules:
      - financial_check: true
      - threat_coping_match: true
```

---

## Files

| File | Purpose |
|------|---------|
| `run_experiment.py` | Main experiment runner |
| `skill_registry.yaml` | Skill definitions |
| `example_flow.png` | Architecture diagram |
| `README.md` | This documentation |

---

## Citation

```bibtex
@misc{skill_governed_flood_2024,
  title={Skill-Governed LLM Agent Framework for Flood Adaptation ABM},
  author={Chiou, Wen-Yu},
  year={2024}
}
```

