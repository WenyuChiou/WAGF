# Skill-Governed Framework Architecture

## Overview

The Skill-Governed Framework uses a **proposal-validation-execution** pipeline where LLM outputs are parsed, validated through multiple layers, and only approved decisions are executed.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SKILL-GOVERNED PIPELINE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐     ┌──────────────┐     ┌─────────────────────────┐  │
│  │    LLM      │     │    Model     │     │     Skill Broker        │  │
│  │  (Ollama/   │────▶│   Adapter    │────▶│  (Validation Pipeline)  │  │
│  │   OpenAI)   │     │              │     │                         │  │
│  └─────────────┘     └──────────────┘     └─────────────────────────┘  │
│        │                   │                         │                  │
│        │                   │                         ▼                  │
│        │                   │              ┌─────────────────────┐       │
│        │                   │              │     Validators      │       │
│        │                   │              │  ┌───────────────┐  │       │
│        │                   │              │  │ Admissibility │  │       │
│        │                   │              │  │ Feasibility   │  │       │
│        │                   │              │  │ Institutional │  │       │
│        │                   │              │  │ EffectSafety  │  │       │
│        │                   │              │  │ PMTConsistency│  │       │
│        │                   │              │  └───────────────┘  │       │
│        │                   │              └─────────────────────┘       │
│        │                   │                         │                  │
│        │                   │              ┌──────────┴──────────┐       │
│        │                   │              ▼                     ▼       │
│        │                   │       ┌──────────┐          ┌──────────┐   │
│        │                   │       │ APPROVED │          │ REJECTED │   │
│        │             ◀─────┼───────│          │          │          │   │
│        │  (Retry)          │       └──────────┘          └──────────┘   │
│        │                   │              │                     │       │
│        ▼                   │              ▼                     ▼       │
│  ┌─────────────┐           │       ┌──────────┐          ┌──────────┐   │
│  │   Retry     │◀──────────┘       │ Execute  │          │  Format  │   │
│  │   Prompt    │                   │ (Sim)    │          │  Retry   │───┘
│  └─────────────┘                   └──────────┘          └──────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Model Adapter (`model_adapter.py`)

**Purpose**: Thin translation layer between LLM output and SkillProposal

**Responsibilities (ONLY TWO):**
1. **Parse LLM output → SkillProposal**
2. **Format rejection → Retry prompt**

**Key Design Principle**: NO domain logic in adapters!

```python
class ModelAdapter(ABC):
    @abstractmethod
    def parse_output(raw_output: str, context: Dict) -> SkillProposal:
        """Parse raw LLM text into structured SkillProposal"""
        
    @abstractmethod
    def format_retry_prompt(original_prompt: str, errors: List[str]) -> str:
        """Format retry prompt with validation errors"""
```

**Implementations:**
- `OllamaAdapter` - For local models (Llama, Gemma, DeepSeek)
- `OpenAIAdapter` - For OpenAI API models

### 2. Skill Types (`skill_types.py`)

Core data types for information flow:

| Type | Purpose | Key Fields |
|------|---------|------------|
| `SkillProposal` | LLM's parsed output | skill_name, agent_id, reasoning, confidence |
| `SkillDefinition` | Registry entry | preconditions, constraints, allowed_state_changes |
| `ValidationResult` | Validator output | valid, errors, warnings |
| `ApprovedSkill` | Post-validation | approval_status, validation_results |
| `ExecutionResult` | Simulation output | success, state_changes |

### 3. Skill Registry (`skill_registry.py`)

Manages skill definitions and provides:
- Skill existence checking
- Eligibility verification
- Precondition validation

### 4. Validators (`validators/skill_validators.py`)

Multi-layer validation pipeline:

| Order | Validator | Checks |
|-------|-----------|--------|
| 1 | SkillAdmissibilityValidator | Skill exists? Agent can use it? |
| 2 | ContextFeasibilityValidator | Context conditions met? |
| 3 | InstitutionalConstraintValidator | once-only, permanent rules |
| 4 | EffectSafetyValidator | State changes allowed? |
| 5 | PMTConsistencyValidator | Reasoning matches decision? |

## Information Flow

### Step-by-Step Process

```
1. LLM INVOCATION
   Input:  PMT Prompt (threat, options, memory)
   Output: Raw text response
   
2. MODEL ADAPTER PARSING
   Input:  Raw text + Context (agent_id, is_elevated)
   Output: SkillProposal {
     skill_name: "buy_insurance",
     reasoning: {"threat": "...", "coping": "..."},
     raw_output: "..."
   }
   
3. VALIDATION PIPELINE
   Input:  SkillProposal + Context + Registry
   For each validator:
     result = validator.validate(proposal, context, registry)
     if not result.valid:
       collect errors
   Output: List[ValidationResult]
   
4. DECISION POINT
   If all validators pass:
     → ApprovedSkill (proceed to execution)
   If any validator fails:
     → Retry (up to max_retries)
     → format_retry_prompt with errors
     → Go back to Step 1
   
5. EXECUTION (if approved)
   Input:  ApprovedSkill
   Output: ExecutionResult {
     success: True,
     state_changes: {"has_insurance": True}
   }
```

### Data Flow Diagram

```
┌────────────┐      ┌────────────────┐      ┌──────────────┐
│            │      │                │      │              │
│  Context   │─────▶│  SkillProposal │─────▶│  Validators  │
│            │      │                │      │              │
│ - agent_id │      │ - skill_name   │      │ - result 1   │
│ - elevated │      │ - reasoning    │      │ - result 2   │
│ - memory   │      │ - confidence   │      │ - ...        │
│            │      │ - raw_output   │      │              │
└────────────┘      └────────────────┘      └──────────────┘
                                                  │
                    ┌─────────────────────────────┘
                    │
                    ▼
           ┌───────────────┐         ┌──────────────────┐
           │               │         │                  │
           │ ApprovedSkill │────────▶│ ExecutionResult  │
           │               │         │                  │
           │ - approved    │         │ - state_changes  │
           │ - validations │         │ - success        │
           │               │         │                  │
           └───────────────┘         └──────────────────┘
```

## Key Design Decisions

### 1. Separation of Concerns
- **Adapter**: Only parses, no validation logic
- **Validators**: Only validate, no parsing logic
- **Registry**: Only lookups, no execution logic

### 2. Fail-Safe Defaults
- If parsing fails → default to `do_nothing`
- If validator errors → retry with feedback
- If execution fails → log and continue

### 3. Extensibility
- New LLM types: Add new Adapter
- New validation rules: Add new Validator
- New skills: Update Registry YAML

## Files

| File | Purpose |
|------|---------|
| `skill_types.py` | Core type definitions |
| `model_adapter.py` | LLM output parsing |
| `skill_registry.py` | Skill definitions |
| `validators/skill_validators.py` | Validation pipeline |
| `run_experiment.py` | Main orchestration |
