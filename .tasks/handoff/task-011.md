# Task 011: Unified Gemini API Integration

## Goal

Implement a universal module interface to connect the `governed_broker_framework` to the Gemini Model API (Google AI Studio / Vertex AI). This will allow the framework to go beyond local provider (Ollama) and leverage high-parameter transformer models.

## Current Status

- [x] Research: Identify existing `plugins.py` or `components/` structures for model communication.
- [x] Design: Draft `UnifiedModelInterface` or `GeminiAPIPlugin` logic.
- [x] Logic: Implement `GeminiAPIPlugin` with standard request/response handling.
- [x] Features: Add API Key management, Model parameters (Temperature, Top-P), and Retry logic.

## Implementation Details

- **Base Interface**: Created `interfaces/llm_provider.py` (missing from repo) to provide `LLMProvider`, `LLMConfig`, and `LLMResponse`.
- **Gemini Provider**: Created `providers/gemini.py` using `google-generativeai`.
- **Factory Integration**: Updated `providers/factory.py` to enable `type: gemini` configuration.
- **Unified Bridge**: Added `create_provider_invoke` to `broker/utils/llm_utils.py` to allow the legacy broker engine to use the new providers.
- **Config Example**: Created `config/providers.yaml.example`.

## Next Steps

- [ ] **Verification**: User to set `GOOGLE_API_KEY` and run a small-scale simulation with `gemini-1.5-flash`.
- [ ] **Cleanup**: Merge `llm_utils.py` logic fully into the `providers/` architecture in future PRs.
