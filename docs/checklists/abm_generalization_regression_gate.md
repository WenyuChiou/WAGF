# ABM Generalization Regression Gate

Run these before and after every major abstraction change.

## Required Commands

```bash
python providers/smoke.py --providers ollama
python -m pytest tests/test_provider_smoke.py tests/test_multi_skill.py tests/test_multi_skill_integration.py -q
python -m pytest tests/test_thinking_validator.py tests/test_rating_scales.py tests/test_agent_config_rating_scale.py -q
python -m pytest tests/test_response_format_builder.py tests/test_config_schema.py tests/test_context_types.py -q
```

## Pass Criteria

- Ollama status is `ready`
- No failures in selected pytest suites
- No new absolute-path or flood-only claims added to generic docs

## Manual Review Questions

1. Does the edited module still work when `multi_skill.enabled` is false?
2. Did this change move logic out of `broker/` or only rename it?
3. Did we preserve current flood and irrigation behavior?
4. Did we accidentally describe PMT as the only supported theory?
