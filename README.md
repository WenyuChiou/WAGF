# Governed Broker Framework

**A governance middleware for LLM-driven Agent-Based Models (ABMs)**

Designed for single-domain agent simulations where LLM agents make decisions under governance constraints.

---

## Quick Start

```bash
# Install
pip install -e .

# Run flood adaptation example
cd examples/flood_adaptation
python run.py --model llama3.2:3b --num-agents 100 --num-years 10
```

---

## 📋 Framework Requirements

To use this framework, you must define:

| # | Element | Required | Description |
|---|---------|----------|-------------|
| 1 | **Domain Config** | ✅ | YAML configuration file |
| 2 | **State Schema** | ✅ | Agent state structure |
| 3 | **Action Catalog** | ✅ | Available actions |
| 4 | **Prompt Template** | ✅ | LLM prompt design |
| 5 | **Validators** | ⚠️ Optional | Domain validation rules |
| 6 | **Memory Rules** | ⚠️ Optional | Memory update logic |
| 7 | **Simulation Engine** | ✅ | State transition logic |

👉 **See [`docs/integration_guide.md`](docs/integration_guide.md) for complete details.**

---

## Architecture

![Architecture Diagram](docs/architecture_diagram.png)

### Three-Layer Design

| Layer | Responsibility | Key Rule |
|-------|---------------|----------|
| **LLM Agent** | Generate decisions from bounded context | READ-ONLY access |
| **Governed Broker** | Validate, retry, audit | NO STATE MUTATION |
| **Simulation Engine** | Execute decisions, update state | ALL CAUSALITY HERE |

### Information Flow

1. **①** Broker builds bounded context → LLM
2. **②** LLM produces structured JSON output → Broker
3. **③** Broker validates against domain rules
4. **④** Validated request → Engine
5. **⑤** Engine executes → State changes
6. **⑥** All steps audited to JSONL

---

## Repository Structure

```
governed_broker_framework/
├── broker/                    # Core governance layer
│   ├── engine.py              # Main broker orchestrator
│   ├── context_builder.py     # Builds bounded LLM context
│   ├── audit_writer.py        # JSONL audit logging
│   ├── replay.py              # Deterministic replay
│   └── types.py               # Core data types
│
├── interfaces/                # Cross-layer communication
│   ├── read_interface.py      # Read-only state access
│   ├── action_request_interface.py  # Action intent (④)
│   └── execution_interface.py # System-only execution (⑥)
│
├── validators/                # Validation plugins
│   └── base.py                # Base validators
│
├── config/                    # Domain configurations
│   └── domains/
│       └── flood_adaptation.yaml
│
├── examples/                  # Domain examples
│   └── flood_adaptation/      # PMT-based flood ABM
│       ├── prompts.py         # LLM prompt template
│       ├── validators.py      # PMT validators
│       ├── memory.py          # Memory manager
│       └── trust_update.py    # Trust dynamics
│
├── docs/                      # Documentation
│   ├── architecture.md
│   └── customization_guide.md
│
└── tests/                     # Unit tests
```

---

## Flood Adaptation Example

Simulates residents making flood adaptation decisions using Protection Motivation Theory (PMT).

### Actions
| Code | Action | Description |
|------|--------|-------------|
| 1 | Buy Insurance | Financial protection |
| 2 | Elevate House | Physical protection |
| 3 | Relocate | Permanent risk elimination |
| 4 | Do Nothing | No action |

### Validators
- **PMTConsistencyValidator**: High threat + High efficacy + Do Nothing = Inconsistent
- **FloodResponseValidator**: Flood occurred + Claims safe = Inconsistent

### Trust Dynamics
- 4-scenario insurance trust update
- Neighbor influence (social proof)

---

## Key Principles

1. **LLM is READ-ONLY**: Cannot modify state directly
2. **Broker validates, never mutates**: Governance only
3. **Engine owns causality**: All state changes
4. **Audit everything**: Reproducible traces
5. **Deterministic replay**: Same seed = Same result

---

## Configuration

See `config/domains/flood_adaptation.yaml` for complete domain configuration including:
- State schema
- Observable signals
- Action catalog
- Validator settings
- Audit policy

---

## License

MIT
