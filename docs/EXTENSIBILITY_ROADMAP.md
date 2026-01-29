# Framework Extensibility Roadmap

## Current State (v0.2)

### ✅ Strengths

- **Multi-LLM Adapters**: `OllamaAdapter`, `OpenAIAdapter` support different providers
- **Skill-Based Abstraction**: Decouples decisions from implementations
- **Plugin Validators**: Easy to add new validation rules
- **YAML Configuration**: Skills defined in `skill_registry.yaml`

### ⚠️ Gaps for Multi-LLM Scenarios

| Gap                       | Impact                        | Priority |
| ------------------------- | ----------------------------- | -------- |
| No LLM Provider Interface | Hard to add Anthropic, Gemini | HIGH     |
| Hardcoded decision codes  | Limits extensibility          | MEDIUM   |
| No async support          | Performance bottleneck        | MEDIUM   |
| Single simulation type    | Need domain abstraction       | LOW      |

---

## Proposed Improvements

### 1. Abstract LLM Provider Interface

```python
# interfaces/llm_provider.py

from abc import ABC, abstractmethod
from typing import AsyncIterator

class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate completion."""
        pass

    @abstractmethod
    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """Stream completion."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass


class OllamaProvider(LLMProvider):
    def __init__(self, model: str, base_url: str = "http://localhost:11434"):
        self._model = model
        self._base_url = base_url

    async def generate(self, prompt: str, **kwargs) -> str:
        # Implementation
        pass


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str, api_key: str):
        self._model = model
        self._api_key = api_key


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str, api_key: str):
        self._model = model
        self._api_key = api_key


class GeminiProvider(LLMProvider):
    def __init__(self, model: str, project_id: str):
        self._model = model
        self._project_id = project_id
```

### 2. Provider Factory

```python
# broker/provider_factory.py

def create_provider(config: dict) -> LLMProvider:
    """Factory for LLM providers."""
    provider_type = config.get("type", "ollama")

    if provider_type == "ollama":
        return OllamaProvider(
            model=config["model"],
            base_url=config.get("base_url", "http://localhost:11434")
        )
    elif provider_type == "openai":
        return OpenAIProvider(
            model=config["model"],
            api_key=config["api_key"]
        )
    elif provider_type == "anthropic":
        return AnthropicProvider(
            model=config["model"],
            api_key=config["api_key"]
        )
    elif provider_type == "gemini":
        return GeminiProvider(
            model=config["model"],
            project_id=config["project_id"]
        )
    else:
        raise ValueError(f"Unknown provider: {provider_type}")
```

### 3. Multi-LLM Configuration

```yaml
# config/providers.yaml

providers:
  ollama-local:
    type: ollama
    model: llama3.2:3b
    base_url: http://localhost:11434

  openai-gpt4:
    type: openai
    model: gpt-4-turbo
    api_key: ${OPENAI_API_KEY}

  anthropic-claude:
    type: anthropic
    model: claude-3-sonnet
    api_key: ${ANTHROPIC_API_KEY}

  gemini-pro:
    type: gemini
    model: gemini-1.5-pro
    project_id: ${GCP_PROJECT_ID}

# Agent assignment
agent_providers:
  default: ollama-local
  high_stakes: openai-gpt4 # For critical decisions
  complex_reasoning: anthropic-claude
```

### 4. Domain Abstraction Layer

```python
# simulation/domain.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any

class SimulationDomain(ABC):
    """Abstract simulation domain."""

    @abstractmethod
    def get_skills(self) -> List[str]:
        """Return available skills in this domain."""
        pass

    @abstractmethod
    def get_prompt_template(self) -> str:
        """Return the decision prompt template."""
        pass

    @abstractmethod
    def get_validators(self) -> List["SkillValidator"]:
        """Return domain-specific validators."""
        pass


class FloodAdaptationDomain(SimulationDomain):
    def get_skills(self):
        return ["buy_insurance", "elevate_house", "relocate", "do_nothing"]

    def get_prompt_template(self):
        return FLOOD_PMT_PROMPT

    def get_validators(self):
        return [PMTConsistencyValidator(), AffordabilityValidator()]


class ClimateMigrationDomain(SimulationDomain):
    def get_skills(self):
        return ["migrate", "adapt_in_place", "seek_assistance", "wait"]

    def get_prompt_template(self):
        return CLIMATE_PROMPT

    def get_validators(self):
        return [MigrationValidator(), ResourceValidator()]
```

---

## Implementation Phases

### Phase 1: Provider Interface (Immediate)

- [ ] Create `interfaces/llm_provider.py`
- [ ] Create `broker/provider_factory.py`
- [ ] Add `config/providers.yaml` schema
- [ ] Update `SkillBrokerEngine` to use factory

### Phase 2: Async Support (1 week)

- [ ] Convert adapters to async
- [ ] Add batch processing
- [ ] Implement rate limiting

### Phase 3: Domain Abstraction (2 weeks)

- [ ] Create `SimulationDomain` interface
- [ ] Refactor `FloodAdaptation` as domain plugin
- [ ] Add example domain: `ClimateMigration`

### Phase 4: Advanced Features (Future)

- [ ] Multi-agent negotiation
- [ ] Inter-agent communication via Graphiti
- [ ] Hybrid LLM routing (local + cloud)

---

## Migration Guide

### From v0.2 to v0.3

```diff
- from broker.model_adapter import OllamaAdapter
+ from providers.llm_provider import OllamaProvider
+ from broker.provider_factory import create_provider

- adapter = OllamaAdapter()
- proposal = adapter.parse_output(raw, context)
+ provider = create_provider({"type": "ollama", "model": "llama3.2:3b"})
+ raw = await provider.generate(prompt)
+ proposal = parse_proposal(raw, context)
```

---

## File Structure (Proposed)

```
governed_broker_framework/
├── interfaces/
│   ├── __init__.py
│   ├── llm_provider.py      # NEW: Abstract LLM interface
│   └── simulation_domain.py # NEW: Domain abstraction
├── providers/                # NEW
│   ├── __init__.py
│   ├── ollama.py
│   ├── openai.py
│   ├── anthropic.py
│   └── gemini.py
├── broker/
│   ├── provider_factory.py  # NEW: Provider factory
│   ├── skill_broker_engine.py
│   └── ...
├── domains/                  # NEW
│   ├── __init__.py
│   ├── flood_adaptation/
│   └── climate_migration/
└── config/
    ├── providers.yaml       # NEW: Multi-LLM config
    └── ...
    └── ...
```

## Phase 21: Demographic & Audit Expansion (Completed)

- [x] **Demographic Grounding**: Injected real-world survey anchors (Income, Tenure, Flood Experience) into prompts.
- [x] **Universal Audit**: Implemented `DemographicAudit` to score LLM reasoning against grounded context.
- [x] **Finance Compatibility**: Verified that the new audit system works gracefully with non-flood domains (e.g., Finance).
