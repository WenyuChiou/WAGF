"""Request parameters the OpenAI and Anthropic providers send.

Current Claude models reject `temperature` (Opus 5.5) or accept only the
default (Sonnet 5.5, Haiku 5.5), and OpenAI's own API takes the token limit as
`max_completion_tokens`. These tests pin what goes on the wire, using fake
clients (no network, no key).
"""
import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("anthropic")
pytest.importorskip("openai")

from providers.factory import create_provider


class _FakeAnthropicMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(type="text", text='{"decision": "1"}'),
            ],
            model=kwargs["model"],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
            stop_reason="end_turn",
            id="msg_test",
        )


class _FakeAsyncAnthropicMessages(_FakeAnthropicMessages):
    async def create(self, **kwargs):  # type: ignore[override]
        return super().create(**kwargs)


class _FakeOpenAICompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content='{"decision": "1"}'),
                finish_reason="stop",
            )],
            model=kwargs["model"],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            id="chatcmpl_test",
        )


def _unwrap(provider):
    # create_provider wraps cloud providers in RateLimitedProvider.
    return getattr(provider, "base_provider", provider)


def _anthropic(config):
    provider = _unwrap(create_provider({"type": "anthropic", "api_key": "test", **config}))
    fake = _FakeAnthropicMessages()
    provider._client = SimpleNamespace(messages=fake)
    return provider, fake


def _openai(config):
    provider = _unwrap(create_provider({"type": "openai", "api_key": "test", **config}))
    fake = _FakeOpenAICompletions()
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    return provider, fake


def test_anthropic_unset_config_sends_no_temperature_and_a_large_cap():
    provider, fake = _anthropic({"model": "claude-haiku-5-5"})
    response = provider.invoke("prompt")
    sent = fake.calls[0]
    assert "temperature" not in sent
    assert sent["max_tokens"] == 16000
    assert sent["model"] == "claude-haiku-5-5"
    # Thinking blocks are skipped; only text is returned.
    assert response.content == '{"decision": "1"}'


def test_anthropic_explicit_values_are_sent_as_given():
    provider, fake = _anthropic(
        {"model": "claude-haiku-5-5", "temperature": 1.0, "max_tokens": 500})
    provider.invoke("prompt")
    assert fake.calls[0]["temperature"] == 1.0
    assert fake.calls[0]["max_tokens"] == 500


def test_anthropic_async_path_builds_the_same_request():
    provider = _unwrap(create_provider(
        {"type": "claude", "api_key": "test", "model": "claude-sonnet-5-5"}))
    fake = _FakeAsyncAnthropicMessages()
    provider._async_client = SimpleNamespace(messages=fake)
    asyncio.run(provider.ainvoke("prompt"))
    assert "temperature" not in fake.calls[0]
    assert fake.calls[0]["max_tokens"] == 16000


def test_openai_unset_config_sends_neither_temperature_nor_a_limit():
    provider, fake = _openai({"model": "some-openai-model"})
    provider.invoke("prompt")
    sent = fake.calls[0]
    assert "temperature" not in sent
    assert "max_tokens" not in sent
    assert "max_completion_tokens" not in sent


def test_openai_official_api_uses_max_completion_tokens():
    provider, fake = _openai(
        {"model": "some-openai-model", "max_tokens": 300, "temperature": 0.2})
    provider.invoke("prompt")
    sent = fake.calls[0]
    assert sent["max_completion_tokens"] == 300
    assert "max_tokens" not in sent
    assert sent["temperature"] == 0.2


def test_openai_compatible_server_keeps_max_tokens():
    provider, fake = _openai(
        {"model": "local-model", "max_tokens": 300, "base_url": "http://localhost:8000/v1"})
    provider.invoke("prompt")
    sent = fake.calls[0]
    assert sent["max_tokens"] == 300
    assert "max_completion_tokens" not in sent


def test_local_providers_keep_their_old_defaults():
    provider = _unwrap(create_provider({"type": "ollama", "model": "llama3.2:3b"}))
    assert provider.config.temperature == 0.7
    assert provider.config.max_tokens == 1024
