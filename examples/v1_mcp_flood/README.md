# Flood Adaptation Example

## Overview

This example demonstrates using the Governed Broker Framework for a **PMT-based flood adaptation ABM** where LLM agents represent homeowners making flood protection decisions.

---

## Experiment Design

### Scenario
- **100 agents** (homeowners) in a flood-prone area
- **10-year simulation** with flood events in years 3, 4, 9
- Agents make annual decisions based on **Protection Motivation Theory (PMT)**

### Agent State
```
Agent:
├── elevated: bool        # House elevated?
├── has_insurance: bool   # Has flood insurance?
├── relocated: bool       # Relocated away?
├── trust_in_insurance: float (0-1)
├── trust_in_neighbors: float (0-1)
└── memory: list          # Last 5 events
```

### Available Actions
| Code | Action | Description | Constraints |
|------|--------|-------------|-------------|
| 1 | Buy Insurance | Financial protection | Not already insured |
| 2 | Elevate House | Physical protection | Not already elevated |
| 3 | Relocate | Leave area | One-time, permanent |
| 4 | Do Nothing | No action | Always available |

---

## Prompt Template

The LLM receives a prompt based on PMT constructs:

```
You are a homeowner in a city, with a strong attachment to your community.
{elevation_status}

Your memory includes:
{memory}

You currently {insurance_status} flood insurance.
You {trust_insurance_text} the insurance company.
You {trust_neighbors_text} your neighbors' judgment.

Using the Protection Motivation Theory, evaluate your current situation by considering:
- Perceived Severity: How serious the consequences of flooding feel to you.
- Perceived Vulnerability: How likely you think you are to be affected.
- Response Efficacy: How effective you believe each action is.
- Self-Efficacy: Your confidence in your ability to take that action.
- Response Cost: The financial and emotional cost of the action.
- Maladaptive Rewards: The benefit of doing nothing immediately.

Now, choose one of the following actions:
{options}

{flood_status}

Respond with:
Threat Appraisal: [Your assessment of threat]
Coping Appraisal: [Your assessment of coping ability]
Final Decision: [Choose {valid_choices}]
```

---

## Domain-Specific Validators

### PMT Consistency Validator (Rule 4)
**Detects**: High threat + High efficacy + "Do Nothing" = Inconsistent

```python
if high_threat_keywords in threat_appraisal:
    if high_efficacy_keywords in coping_appraisal:
        if decision == "do_nothing":
            ERROR: "PMT inconsistency detected"
```

### Flood Response Validator (Rule 5)
**Detects**: Flood occurred + Claims "safe" = Inconsistent

```python
if flood_occurred_this_year:
    if "feel safe" in threat_appraisal:
        ERROR: "Cognitive inconsistency after flood"
```

---

## Trust Dynamics

After each year, trust values update based on 4 scenarios:

| Scenario | Insurance Trust | Neighbor Trust |
|----------|-----------------|----------------|
| Insured + Flooded | -0.10 ("Hassle") | Depends on community |
| Insured + Safe | +0.02 ("Peace of Mind") | |
| Not Insured + Flooded | +0.05 ("Hard Lesson") | -0.05 if low action |
| Not Insured + Safe | -0.02 ("Gambler's Reward") | |

Community action rate > 30% → Neighbor trust +0.04

---

## Memory Updates

Each year, agents remember:
1. Flood event: "Year X: A flood occurred..."
2. Decision made: "Year X: You purchased insurance..."
3. Random recall (20% chance): Past events from community

Memory window = 5 (only last 5 events kept)

---

## Running the Example

```bash
cd examples/flood_adaptation

# Run with Llama
python run.py --model llama3.2:3b --num-agents 100 --num-years 10

# Run with GPT
python run.py --model gpt-oss --num-agents 100 --num-years 10
```

---

## Experiment Results (MCP Governance)

The following results demonstrate the effectiveness of MCP governance:

| Model | Total Decisions | First-Pass | Retry Success | Final Consistency |
|-------|-----------------|------------|---------------|-------------------|
| **Llama 3.2:3b** | 460 | 86.2% | 13.7% | **99.9%** |
| **Gemma 3:4b** | 976 | 98.7% | 1.3% | **100.0%** |
| **GPT-OSS** | 987 | 90.5% | 9.5% | **99.8%** |
| **DeepSeek R1:8b** | 879 | 85.3% | 14.7% | **99.4%** |

### Key Findings
- **100% retry success rate** across all models
- MCP effectively filters PMT-inconsistent decisions
- Gemma shows highest initial consistency; DeepSeek requires more retries but achieves high final consistency

---

## Output Files

```
results/
├── simulation_log.csv      # All decisions with adaptation states
├── governed_audit.jsonl    # Complete audit trail (per-step)
└── audit_summary.json      # Aggregate statistics
```

---

## File Structure

```
examples/flood_adaptation/
├── run.py            # Main simulation script
├── prompts.py        # PROMPT_TEMPLATE + build_prompt()
├── validators.py     # PMTConsistencyValidator + FloodResponseValidator
├── memory.py         # MemoryManager + PAST_EVENTS
├── trust_update.py   # TrustUpdateManager (4-scenario logic)
├── __init__.py       # Package exports
├── results/          # Sample output (Llama 3.2:3b)
│   ├── simulation_log.csv
│   ├── governed_audit.jsonl
│   └── audit_summary.json
└── analysis/         # Comparison scripts & visualizations
    ├── analyze_mcp_diff.py
    └── adaptation_states_comparison.png
```
