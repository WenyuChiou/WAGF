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

### Enable the repo-tracked pre-commit hook

One-time setup, run once per clone:

```bash
git config core.hooksPath .githooks
```

This activates `.githooks/pre-commit`, a stdlib-only secret scanner that
blocks commits containing hardcoded API keys (Zotero, OpenAI, Anthropic,
GitHub PAT, AWS) on the staged diff. Full pattern catalogue + bypass
instructions in [`.githooks/README.md`](.githooks/README.md). The hook
does not block the working tree or git history — only what's staged.

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

1. Scaffold a new domain via `python -m broker.tools.scaffold_domain <domain-name>` (or invoke the `wagf-domain-builder` Claude Code skill which walks you through the same scaffold + the cognitive-framework choice)
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

### Post-Experiment Readiness Reports

After running an experiment, audit its output with the generic readiness
reporter. The CLI ships three profiles tuned to different lifecycle
stages — pick the one that matches what you're verifying:

```bash
# functional  — does the pipeline run? Lowest bar; used during
#               bring-up of a new domain. Checks approval rate and
#               format-retry rate only.
python -m broker.tools.readiness_report \
    --results examples/quickstart/results \
    --profile functional

# behavioral  — does the model produce diverse, coherent decisions?
#               Adds action-coverage + validator-firing diversity.
#               Use before reporting paper results.
python -m broker.tools.readiness_report \
    --results <your_run_dir> \
    --profile behavioral

# stress      — does governance correctly handle hard constraints,
#               retries, terminal outcomes? Adds terminal-rate bounds
#               and dead-validator detection. Use for harness-
#               engineering audits.
python -m broker.tools.readiness_report \
    --results <your_run_dir> \
    --profile stress
```

The reporter writes `<results>/readiness_report.json` alongside the
console summary (pass `--no-json` to skip). Exit codes: `0` = profile
passed, `1` = at least one threshold failed, `2` = CLI / input error.

**Important caveats**:

- **Small smokes do NOT cover action diversity.** A 3-agent × 2-year
  run cannot exercise every skill in the domain's registry.
  `behavioral` and `stress` profiles will fail on such runs. Use
  `functional` for smokes and the other profiles for larger
  multi-seed / multi-year runs.
- **Terminal rejections can be valid.** A governance-blocked
  decision is not necessarily a model failure — it may be the
  validator correctly enforcing a hard constraint (water-right
  ceiling, dose cooldown, etc.). The `expected_hard_block`
  terminal-outcome category distinguishes these from
  `recoverable_retry_failed` cases where the model ignored feasible
  alternatives.
- **Cross-domain runs may flag legitimately-inapplicable
  validators as dead.** The `stress` profile's default
  `max_dead_validators: 0` is strict; override via
  `--profile-yaml=<your_overrides.yaml>` and set a small int > 0
  if your audit spans multiple domains.

Override default thresholds by copying
`broker/components/validation/readiness_profile.yaml`, editing, and
passing `--profile-yaml=<path>` to the CLI.

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
