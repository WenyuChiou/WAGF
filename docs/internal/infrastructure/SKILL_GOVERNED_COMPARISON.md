# Skill-Governed Framework (Experiment 10)

## Overview

The Skill-Governed Framework represents a significant evolution from the original MCP (Model Context Protocol) Governed Broker approach. This framework introduces **multi-layer validation** and **skill-based governance** to achieve more consistent and rational agent decision-making.

## Framework Comparison

### Architecture Differences

| Feature | Old MCP (Exp 9) | Skill-Governed (Exp 10) |
|---------|-----------------|-------------------------|
| **Core Concept** | Context-based action governance | Skill-based proposal validation |
| **Validation Layers** | 1 (PMT Keyword Validator) | 5+ (Multi-layer pipeline) |
| **Affordability Check** | ❌ None | ✅ Explicit financial consistency |
| **State Persistence** | Manual tracking | Registry-enforced constraints |
| **Audit Trail** | Basic logging | Skill-level audit with reasoning |

### Validator Pipeline Comparison

#### Old MCP Validators (`pmt_validator.py`)
```
1. High Threat + High Coping → Cannot Do Nothing
2. Low Threat → Cannot Relocate  
3. High Threat → Cannot Do Nothing
```
**Limitations:**
- No financial consistency checking
- Only 3 rules, easily bypassed by inconsistent reasoning
- No state persistence validation

#### Skill-Governed Validators (`skill_validators.py`)
```
1. SkillAdmissibilityValidator - Skill exists in registry?
2. ContextFeasibilityValidator - Preconditions met?
3. InstitutionalConstraintValidator - Once-only/permanent rules
4. EffectSafetyValidator - State change safety
5. PMTConsistencyValidator - Enhanced PMT with 4+ rules
   - Rule 1: High Threat + High Efficacy + Do Nothing = REJECT
   - Rule 2: Low Threat + Relocate = REJECT
   - Rule 3: Flood Occurred + Claims Safe = REJECT
   - Rule 4: Cannot Afford + Expensive Option = REJECT ← KEY ADDITION
6. UncertaintyValidator - Detects ambiguous responses (optional)
```

## Key Innovation: Financial Consistency Rule

The most impactful addition in Skill-Governed is **Rule 4** in `PMTConsistencyValidator`:

```python
# Rule 4: Cannot afford + Expensive option = REJECT
is_expensive = skill in ["elevate_house", "relocate"]
if is_expensive and any(kw in coping for kw in CANNOT_AFFORD_KEYWORDS):
    errors.append("Claims cannot afford but chose expensive option")
```

**CANNOT_AFFORD_KEYWORDS:**
- "cannot afford"
- "too expensive"  
- "not enough money"
- "high cost"
- "financial burden"

## Empirical Results

### Relocation Rate Comparison

| Model | No MCP (Baseline) | Old MCP | Skill-Governed | Change |
|-------|-------------------|---------|----------------|--------|
| Llama 3.2 | 95% | 99% | **47%** | ↓52% |
| Gemma 3 | 6% | 13% | **1%** | ↓12% |
| GPT-OSS | 0% | 2% | **<1%** | - |
| DeepSeek | 14% | 39% | **2%** | ↓37% |

### Decision Distribution (Skill-Governed)

```
Llama 3.2:
├── Only House Elevation: 52% (422/814)
├── Both FI + HE: 20% (165/814)
├── Do Nothing: 19% (153/814)
├── Relocate: 6% (47/814)
└── Only Insurance: 3% (27/814)

Gemma 3:
├── Only House Elevation: 62% (615/999)
├── Both FI + HE: 18% (184/999)
├── Do Nothing: 18% (177/999)
├── Only Insurance: 2% (22/999)
└── Relocate: <1% (1/999)
```

## Why Does This Work?

### Old MCP Failure Mode
1. LLM generates: "I'm very worried about floods and it's too expensive, but I'll relocate anyway"
2. Old MCP: ✅ PASS (no affordability check)
3. Result: 99% relocation rate (panic-driven, irrational)

### Skill-Governed Success
1. LLM generates: "I'm very worried about floods and it's too expensive, but I'll relocate anyway"
2. Skill-Governed: ❌ REJECT (Rule 4: Cannot Afford + Relocate)
3. LLM retries: "Given my budget constraints, I'll elevate my house instead"
4. Skill-Governed: ✅ PASS
5. Result: 47% relocation, 52% elevation (rational, budget-aware)

## Conclusion

The Skill-Governed Framework achieves **more rational agent behavior** through:

1. **Multi-layer validation** that catches inconsistencies at multiple levels
2. **Financial consistency checking** (Rule 4) that prevents irrational expensive choices
3. **Skill-based governance** that enforces institutional constraints (once-only, permanent)
4. **Enhanced PMT validation** with more comprehensive rule coverage

This results in a **52% reduction in panic-relocation** for Llama and similar improvements across all models.

## Files

- `skill_types.py` - Core type definitions (SkillProposal, ValidationResult)
- `skill_registry.py` - Skill registration and lookup
- `validators/skill_validators.py` - Multi-layer validation pipeline
- `run_experiment.py` - Experiment runner with integrated validation

## Citation

If using this framework, please cite:
```
Skill-Governed LLM Agent Framework for Flood Adaptation ABM
Experiment 10, 2024
```
