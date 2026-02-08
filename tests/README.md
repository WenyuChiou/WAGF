# Framework Test Suite Reference

This directory contains the verification suite for the Water Agent Governance Framework. Each test file serves a specific role in ensuring the stability, universality, and reliability of the governance middleware.

## Test Categories

### 1. Core Governance & API Stability

- **`test_broker_core.py`** [NECESSARY]:  
  Ensures the `SkillBrokerEngine` correctly orchestrates the 6-step loop. Verifies support for both legacy (string) and modern (tuple) LLM invocation APIs, statistical collection, and proper validator integration.

### 2. Output Parsing & Robustness

- **`test_adapter_parsing.py`** [NECESSARY]:  
  Validates the multi-layer fallback parsing mechanism (JSON -> Keyword -> Regex -> Digit -> Default). Includes specific tests for DeepSeek `<think>` tag removal and ensuring the `parse_layer` is accurately tracked.

### 3. State & Environment Isolation

- **`test_tiered_environment.py`** [NECESSARY]:  
  Verifies that the `TieredEnvironment` correctly isolates state across Local, Social, and Global layers, ensuring data leaks are prevented and observations are strictly bounded.
- **`test_world_models.py`**:  
  Tests state mutation and persistence across simulation cycles to ensure physical invariants are maintained.

### 4. Semantic & Grounding Audit

- **`test_demographic_audit.py`**:  
  Specifically tests the `DemographicAudit` component to ensure that LLM reasoning is being scored against provided demographic anchors (Identity, Experience).
- **`verify_dynamic_context.py`**:  
  A verification script for the `ContextBuilder` pipeline, ensuring that custom providers can be injected and correctly modify the final prompt.

### 5. Connectivity & Smoke Tests

- **`connectivity_smoke_test.py`**:  
  A simple script to verify connection to local LLM providers (e.g., Ollama).

## Running Tests

All tests can be executed using `pytest` from the project root:

```bash
# Run all tests
python -m pytest tests/ -v

# Run core tests only
python -m pytest tests/test_broker_core.py tests/test_adapter_parsing.py
```

## Why are these tests necessary?

As a governance middleware, the framework's primary value is **trust**. These tests guarantee that:

1. Valid user intentions are never blocked by parsing errors.
2. Invalid LLM hallucinations are always caught by validators.
3. The framework remains domain-agnostic by testing with generic mocks.
