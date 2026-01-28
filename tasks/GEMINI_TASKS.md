# Gemini Tasks for Task-040

> **Date**: 2026-01-28
> **Priority**: HIGH
> **Context**: SA → MA Architecture Unification
> **Status**: ⚠️ REASSIGNED TO CODEX - See `CODEX_TASKS.md` for C3 and C4

---

## ~~Task-G1: Extract Memory Templates to Broker~~ → **REASSIGNED TO CODEX AS C3**

### Goal
Move MA memory templates to broker for SA/MA reuse.

### Files
- **Source**: `examples/multi_agent/memory/templates.py` (378 lines)
- **Target**: `broker/components/prompt_templates/memory_templates.py` (NEW)

### Reference Files (READ THESE FIRST)
```
examples/multi_agent/memory/templates.py         # Current templates
examples/multi_agent/generate_agents.py          # How templates are used
examples/multi_agent/data/agents_init.csv        # Agent data structure
```

### Requirements

1. **Create directory structure**:
```
broker/components/prompt_templates/
├── __init__.py
└── memory_templates.py
```

2. **Create MemoryTemplateProvider class**:
```python
"""
Memory template generation for agent initialization.
Moved from examples/multi_agent/memory/templates.py for SA/MA reuse.
"""
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class MemoryTemplate:
    """Generated memory with metadata."""
    content: str
    category: str  # flood_event, insurance_claim, etc.
    emotion: str = "neutral"  # major, minor, neutral
    source: str = "personal"  # personal, neighbor, community

class MemoryTemplateProvider:
    """
    Provides memory templates for different domains.

    Categories:
    - flood_event: Direct flood experience
    - insurance_claim: Insurance interactions
    - social_interaction: Neighbor discussions
    - government_notice: Government communications
    - adaptation_action: Past adaptation decisions
    - risk_awareness: Flood zone awareness
    """

    @staticmethod
    def flood_experience(profile: Dict[str, Any]) -> MemoryTemplate:
        """Generate flood experience memory from survey data."""
        if profile.get("flood_experience", False):
            freq = profile.get("flood_frequency", 1)
            recent = profile.get("recent_flood_text", "recently")
            content = f"I experienced flooding {freq} time(s). Last flood was {recent}."
            return MemoryTemplate(
                content=content,
                category="flood_event",
                emotion="major",
                source="personal"
            )
        return MemoryTemplate(
            content="I have not experienced significant flooding.",
            category="flood_event",
            emotion="neutral",
            source="personal"
        )

    @staticmethod
    def insurance_interaction(profile: Dict[str, Any]) -> MemoryTemplate:
        """Generate insurance memory from survey data."""
        ins_type = profile.get("insurance_type", "none")
        if ins_type and ins_type.lower() != "none":
            content = f"I have {ins_type} flood insurance coverage."
            emotion = "minor"
        else:
            content = "I do not currently have flood insurance."
            emotion = "neutral"
        return MemoryTemplate(
            content=content,
            category="insurance_claim",
            emotion=emotion,
            source="personal"
        )

    @staticmethod
    def social_interaction(profile: Dict[str, Any]) -> MemoryTemplate:
        """Generate social memory based on SC score."""
        sc_score = profile.get("sc_score", 3.0)
        if sc_score >= 4.0:
            content = "My neighbors and I frequently discuss flood preparedness."
        elif sc_score >= 3.0:
            content = "I occasionally talk with neighbors about flood risks."
        else:
            content = "I rarely discuss flood issues with my neighbors."
        return MemoryTemplate(
            content=content,
            category="social_interaction",
            emotion="neutral",
            source="neighbor"
        )

    @staticmethod
    def government_notice(profile: Dict[str, Any]) -> MemoryTemplate:
        """Generate government interaction memory."""
        sp_score = profile.get("sp_score", 3.0)
        if sp_score >= 4.0:
            content = "I have received helpful information from government about flood protection programs."
        elif sp_score >= 3.0:
            content = "I am aware of some government flood protection programs."
        else:
            content = "I have limited knowledge of government flood programs."
        return MemoryTemplate(
            content=content,
            category="government_notice",
            emotion="neutral",
            source="community"
        )

    @staticmethod
    def adaptation_action(profile: Dict[str, Any]) -> MemoryTemplate:
        """Generate past adaptation memory."""
        post_action = profile.get("post_flood_action", "")
        if post_action:
            content = f"After previous flooding, I {post_action}."
            emotion = "minor"
        else:
            content = "I have not taken major flood adaptation actions yet."
            emotion = "neutral"
        return MemoryTemplate(
            content=content,
            category="adaptation_action",
            emotion=emotion,
            source="personal"
        )

    @staticmethod
    def risk_awareness(profile: Dict[str, Any]) -> MemoryTemplate:
        """Generate flood zone awareness memory."""
        sfha_aware = profile.get("sfha_awareness", False)
        flood_zone = profile.get("flood_zone", "MEDIUM")
        if sfha_aware:
            content = f"I know my property is in a {flood_zone} risk flood zone (FEMA maps)."
            emotion = "minor" if flood_zone in ["HIGH", "VERY_HIGH"] else "neutral"
        else:
            content = "I am not certain about my official flood zone designation."
            emotion = "neutral"
        return MemoryTemplate(
            content=content,
            category="risk_awareness",
            emotion=emotion,
            source="community"
        )

    @classmethod
    def generate_all(cls, profile: Dict[str, Any]) -> List[MemoryTemplate]:
        """Generate all 6 memory templates for an agent profile."""
        return [
            cls.flood_experience(profile),
            cls.insurance_interaction(profile),
            cls.social_interaction(profile),
            cls.government_notice(profile),
            cls.adaptation_action(profile),
            cls.risk_awareness(profile),
        ]
```

3. **Update original file with deprecation**:
```python
# examples/multi_agent/memory/templates.py
import warnings
warnings.warn(
    "Import from broker.components.prompt_templates.memory_templates instead",
    DeprecationWarning,
    stacklevel=2
)
from broker.components.prompt_templates.memory_templates import (
    MemoryTemplateProvider,
    MemoryTemplate,
)
# Keep existing functions for backward compatibility
```

4. **Create __init__.py**:
```python
# broker/components/prompt_templates/__init__.py
from .memory_templates import MemoryTemplateProvider, MemoryTemplate

__all__ = ["MemoryTemplateProvider", "MemoryTemplate"]
```

### Acceptance Criteria
- [ ] `broker/components/prompt_templates/` directory created
- [ ] `MemoryTemplateProvider` class implemented
- [ ] MA experiment imports work
- [ ] Backward compatibility maintained

### Verification Commands
```bash
# Test import from broker
python -c "from broker.components.prompt_templates import MemoryTemplateProvider; print('OK')"

# Test backward compatibility
python -c "from examples.multi_agent.memory.templates import MemoryTemplateProvider; print('OK')"
```

---

## ~~Task-G2: Add Parse Confidence Scoring~~ → **REASSIGNED TO CODEX AS C4**

### Goal
Add parsing quality metrics to SkillProposal for audit trail.

### Target File
`broker/utils/model_adapter.py` (NOT broker/adapters/)

### Reference Files (READ THESE FIRST)
```
broker/utils/model_adapter.py       # Main adapter (lines 209-688)
broker/interfaces/skill_types.py    # SkillProposal definition
broker/components/audit_writer.py   # How traces are written
```

### Requirements

1. **Add parse metadata tracking** (around line 230 in parse_output):
```python
# Initialize parse metadata
parse_metadata = {
    "parse_layer": "",           # Will be set to: "json", "keyword", "digit", "fallback"
    "parse_confidence": 0.0,     # 0.0-1.0
    "construct_completeness": 0.0,  # % of required constructs found
}
```

2. **Update confidence based on parse layer** (after each extraction method):
```python
# After JSON extraction succeeds (around line 400):
parse_metadata["parse_layer"] = "json"
parse_metadata["parse_confidence"] = 0.95

# After keyword extraction succeeds (around line 480):
parse_metadata["parse_layer"] = "keyword"
parse_metadata["parse_confidence"] = 0.70

# After digit extraction succeeds (around line 490):
parse_metadata["parse_layer"] = "digit"
parse_metadata["parse_confidence"] = 0.50

# Fallback (around line 580):
parse_metadata["parse_layer"] = "fallback"
parse_metadata["parse_confidence"] = 0.20
```

3. **Calculate construct completeness** (before returning SkillProposal):
```python
# Calculate construct completeness
required_constructs = ["TP_LABEL", "CP_LABEL", "decision"]  # From config
found_constructs = [c for c in required_constructs if c in reasoning or c.lower() in str(skill_name)]
parse_metadata["construct_completeness"] = len(found_constructs) / len(required_constructs)
```

4. **Add to reasoning dict**:
```python
# Add parse metadata to reasoning (before return)
reasoning["_parse_metadata"] = parse_metadata
```

5. **Ensure audit trace includes metadata** (check audit_writer.py):
The `_parse_metadata` field will be automatically included since it's in the reasoning dict.

### Test File
`tests/test_parse_confidence.py`

```python
import pytest
from broker.utils.model_adapter import UnifiedAdapter

def test_json_parse_confidence():
    adapter = UnifiedAdapter(agent_type="household")
    # Mock a JSON response
    raw_output = '<<<DECISION_START>>>{"decision": 2, "threat_appraisal": "H", "coping_appraisal": "M"}<<<DECISION_END>>>'
    context = {"agent_id": "test", "agent_type": "household"}

    result = adapter.parse_output(raw_output, context)

    assert result is not None
    assert result.reasoning.get("_parse_metadata", {}).get("parse_confidence", 0) >= 0.9
    assert result.reasoning.get("_parse_metadata", {}).get("parse_layer") == "json"

def test_construct_completeness():
    adapter = UnifiedAdapter(agent_type="household")
    raw_output = '<<<DECISION_START>>>{"decision": 2}<<<DECISION_END>>>'
    context = {"agent_id": "test", "agent_type": "household"}

    result = adapter.parse_output(raw_output, context)

    # Only decision found, missing TP_LABEL and CP_LABEL
    completeness = result.reasoning.get("_parse_metadata", {}).get("construct_completeness", 0)
    assert completeness < 1.0
```

### Acceptance Criteria
- [ ] `_parse_metadata` added to reasoning dict
- [ ] Confidence scores vary by parse method
- [ ] Construct completeness calculated
- [ ] Existing tests pass
- [ ] New tests pass

### Verification Commands
```bash
# Run unit tests
python -m pytest tests/test_parse_confidence.py -v

# Check existing tests still pass
python -m pytest tests/ -v --ignore=tests/integration
```

---

## Important Notes

1. **Do NOT modify** files in `examples/single_agent/` - experiments may be running
2. **Correct path**: `broker/utils/model_adapter.py` (NOT broker/adapters/)
3. **Test before commit**: Run `python -m pytest tests/ -v`
4. **Backward compatibility**: Existing audit logs should still work
