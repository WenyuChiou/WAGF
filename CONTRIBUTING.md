# Contributing to WAGF

Thank you for your interest in contributing to the Water Agent Governance
Framework. This guide explains how to set up your development environment,
submit changes, and follow project conventions.

## Getting Started

### Prerequisites

- Python 3.10+
- Git
- (Optional) [Ollama](https://ollama.com/) for LLM integration tests

### Setup

```bash
git clone https://github.com/<your-fork>/water-agent-governance-framework.git
cd water-agent-governance-framework
pip install -r requirements.txt
pip install -e .
```

### Verify Installation

```bash
# Run quickstart (no Ollama required)
python examples/quickstart/01_barebone.py

# Run tests
pytest tests/core/ -v
```

## Development Workflow

1. **Fork** the repository on GitHub
2. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** — see [Code Conventions](#code-conventions) below
4. **Run tests** before committing:
   ```bash
   pytest tests/core/ -v --tb=short
   ```
5. **Commit** with a descriptive message (see [Commit Messages](#commit-messages))
6. **Push** and open a Pull Request against `main`

## Code Conventions

### Python Style

- Follow PEP 8 for formatting
- Use type hints for function signatures
- Use explicit `encoding='utf-8'` for all file I/O
- Wrap console output in try/except for encoding errors (Windows compatibility)

### File Organization

```
broker/                    # Framework core (do not add domain-specific code here)
  components/              # Context builders, memory engines, validators
  core/                    # ExperimentRunner, SkillBrokerEngine
  governance/              # Rule evaluation, identity/thinking rules
  interfaces/              # Protocols and type definitions
  utils/                   # Shared utilities (logging, config, LLM)
examples/                  # Domain-specific experiments
  quickstart/              # Tier 1-2 (minimal, no Ollama)
  minimal/                 # Tier 2.5 (template for new domains)
  multi_agent_simple/      # Tier 3 (multi-agent with phase ordering)
  ...
tests/                     # Test suites
  core/                    # Framework core tests
  conftest.py              # Shared fixtures
docs/                      # Documentation
  guides/                  # How-to guides
  references/              # Reference material
```

### Adding a New Domain Example

1. Copy `examples/minimal/` as your starting point
2. Modify `agent_types.yaml` (prompts, constructs, governance rules)
3. Modify `skill_registry.yaml` (domain-specific skills)
4. Write your simulation engine implementing `execute_skill(approved_skill)`
5. Add lifecycle hooks for environment-agent coupling
6. See [Experiment Design Guide](docs/guides/experiment_design_guide.md)

### Adding a Custom Memory Engine

```python
from broker.components.memory_registry import MemoryEngineRegistry
from broker.components.memory_engine import MemoryEngine

class MyEngine(MemoryEngine):
    def add_memory(self, agent_id, content, **kwargs): ...
    def get_memories(self, agent_id, **kwargs): ...

MemoryEngineRegistry.register("my_engine", MyEngine)
```

## Commit Messages

Use conventional commit format:

```
<type>: <short description>

<optional body explaining why>
```

Types:
- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation only
- `refactor:` — Code change that neither fixes a bug nor adds a feature
- `test:` — Adding or fixing tests
- `chore:` — Build process, CI, or tooling changes

Examples:
```
feat: add per-agent-type model names via llm_params.model
fix: prevent SkillProposal mutation during magnitude fallback
docs: add YAML configuration reference
test: add CognitiveCache persistence round-trip test
```

## Testing

### Running Tests

```bash
# Core framework tests (fast, no Ollama)
pytest tests/core/ -v

# Full suite (some tests may require domain-specific setup)
pytest tests/ -v --tb=short

# With coverage
pytest tests/core/ --cov=broker --cov-report=term-missing
```

### Writing Tests

- Place tests in `tests/` mirroring the source structure
- Use fixtures from `tests/conftest.py` (MockLLM, basic_agent, etc.)
- Mark slow tests with `@pytest.mark.slow`
- Mark integration tests with `@pytest.mark.integration`

## Reporting Issues

When reporting bugs, include:
1. Python version and OS
2. Steps to reproduce
3. Expected vs actual behavior
4. Full error traceback
5. YAML configuration (if relevant)

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE).
