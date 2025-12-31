# Experiment Design Guide

This guide explains how to design new experiments using the Skill-Governed Framework.

## Quick Start

See `examples/flood_adaptation/run_skill_governed.py` for a complete working example.

---

## 6 Steps to Build an Experiment

### Step 1: Define Domain Types

```python
@dataclass
class Agent:
    id: str
    # Add your agent state fields
    has_insurance: bool = False
    elevated: bool = False

@dataclass  
class Environment:
    year: int = 0
    flood_event: bool = False
```

---

### Step 2: Define Skill Registry

Skills are abstract behaviors your agents can perform:

```python
SKILL_DEFINITIONS = {
    "buy_insurance": {
        "description": "Purchase flood insurance...",
        "preconditions": [],  # When can this skill be used?
        "constraints": {"annual": True},  # Usage limits
        "effects": {"has_insurance": True}  # State changes
    },
    "elevate_house": {
        "description": "Elevate your home...",
        "preconditions": [{"field": "elevated", "value": False}],
        "constraints": {"once_only": True},
        "effects": {"elevated": True}
    }
}
```

---

### Step 3: Build Context (Prompt)

```python
def build_context(agent: Agent, env: Environment) -> str:
    # Get available skills for this agent
    available = get_available_skills(agent)
    skills_text = "\n".join(f"- {k}: {v}" for k, v in available.items())
    
    return f"""You are a homeowner...
    
Available skills:
{skills_text}

Final Decision: [Choose {", ".join(available.keys())}]"""
```

---

### Step 4: Parse LLM Output

```python
def parse_llm_output(raw_output: str, agent: Agent) -> str:
    available = get_available_skills(agent)
    
    for line in raw_output.split('\n'):
        if "final decision" in line.lower():
            decision_text = line.split(":", 1)[-1].strip().lower()
            for skill_id in available.keys():
                if skill_id in decision_text:
                    return skill_id
    
    return "do_nothing"  # Fallback
```

---

### Step 5: Execute Skills (System-Only)

```python
def execute_skill(skill_name: str, agent: Agent) -> Dict:
    """Only the system calls this - LLM cannot execute directly."""
    if skill_name == "buy_insurance":
        agent.has_insurance = True
        return {"has_insurance": True}
    # ... other skills
```

---

### Step 6: Run Simulation Loop

```python
for year in range(1, num_years + 1):
    for agent in active_agents:
        # 1. Build context
        prompt = build_context(agent, env)
        
        # 2. Get LLM decision
        response = llm.invoke(prompt)
        
        # 3. Parse to skill
        skill = parse_llm_output(response.content, agent)
        
        # 4. Execute (system-only)
        execute_skill(skill, agent)
        
        # 5. Update memory
        agent.memory.append(f"Year {year}: Chose {skill}")
```

---

## Adding New Skills

1. Add to `SKILL_DEFINITIONS` dict
2. Update `execute_skill()` function
3. That's it - prompt automatically includes new skills

## Adding Validators (Optional)

```python
from validators import SkillValidator

class MyValidator(SkillValidator):
    @property
    def name(self) -> str:
        return "my_validator"
    
    def validate(self, proposal, context, registry) -> tuple:
        # Return (is_valid, rejection_reason)
        if some_condition:
            return False, "Reason for rejection"
        return True, None
```

---

## Key Principles

1. **LLM proposes, System disposes** - LLM only suggests skills, system validates and executes
2. **Skills are abstract** - Not tied to specific tools or implementations
3. **Context is read-only** - LLM cannot modify state, only observe it
4. **Execution is system-only** - State changes happen in `execute_skill()`
