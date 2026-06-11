"""Pin cloud-provider routing without SDK, key, or network dependence."""
from __future__ import annotations

import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

from broker.utils import llm_utils
from providers import factory


def _install_fake_ollama(monkeypatch, constructed):
    fake = ModuleType("langchain_ollama")

    class _BaseFakeOllama:
        def __init__(self, model, **params):
            constructed.append((self.__class__.__name__, model, params))

    class ChatOllama(_BaseFakeOllama):
        pass

    class OllamaLLM(_BaseFakeOllama):
        pass

    fake.ChatOllama = ChatOllama
    fake.OllamaLLM = OllamaLLM
    monkeypatch.setitem(sys.modules, "langchain_ollama", fake)


@pytest.mark.parametrize("model", ["gemma3:4b", "llama3.2:3b", "gemma4:e4b"])
def test_ollama_style_names_with_colons_do_not_route_to_provider_factory(
    monkeypatch, model
):
    constructed = []
    _install_fake_ollama(monkeypatch, constructed)
    monkeypatch.setattr(llm_utils.LLM_CONFIG, "use_chat_api", False)
    monkeypatch.setattr(
        llm_utils,
        "create_provider_invoke",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("hijacked")
        ),
    )

    invoke = llm_utils.create_llm_invoke(model)

    assert callable(invoke)
    assert constructed and constructed[0][1] == model


@pytest.mark.parametrize("model", ["mock", "mock-linear-evap"])
def test_mock_models_bypass_factory_and_ollama(monkeypatch, model):
    fake = ModuleType("langchain_ollama")

    class _UnexpectedOllama:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("ollama touched")

    fake.ChatOllama = _UnexpectedOllama
    fake.OllamaLLM = _UnexpectedOllama
    monkeypatch.setitem(sys.modules, "langchain_ollama", fake)
    monkeypatch.setattr(
        llm_utils,
        "create_provider_invoke",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("factory touched")
        ),
    )

    invoke = llm_utils.create_llm_invoke(model)
    content, stats = invoke("Choose:\n1. do_thing\n2. other")

    assert json.loads(content)["decision"] == 1
    assert isinstance(stats, llm_utils.LLMStats)
    assert stats.success is True


@pytest.mark.parametrize(
    ("model", "provider_type", "model_name"),
    [
        ("claude:claude-sonnet-4-6", "claude", "claude-sonnet-4-6"),
        ("anthropic:claude-opus-4-6", "anthropic", "claude-opus-4-6"),
        ("openai:gpt-4.1-mini", "openai", "gpt-4.1-mini"),
        ("gemini:gemini-2.5-flash", "gemini", "gemini-2.5-flash"),
        ("azure:gpt-4o", "azure", "gpt-4o"),
    ],
)
def test_known_cloud_prefixes_route_to_provider_factory(
    monkeypatch, model, provider_type, model_name
):
    captured = {}

    def fake_create_provider_invoke(config, verbose=False):
        captured["config"] = config
        captured["verbose"] = verbose
        return lambda prompt: (f"stub:{prompt}", llm_utils.LLMStats())

    monkeypatch.setattr(llm_utils, "create_provider_invoke", fake_create_provider_invoke)

    invoke = llm_utils.create_llm_invoke(model, verbose=True)
    content, _stats = invoke("prompt")

    assert content == "stub:prompt"
    assert captured["verbose"] is True
    assert captured["config"]["type"] == provider_type
    assert captured["config"]["model"] == model_name


def test_cloud_route_merges_runtime_overrides(monkeypatch):
    captured = {}

    def fake_create_provider_invoke(config, verbose=False):
        captured["config"] = config
        return lambda _prompt: ("stub", llm_utils.LLMStats())

    monkeypatch.setattr(llm_utils, "create_provider_invoke", fake_create_provider_invoke)

    llm_utils.create_llm_invoke(
        "openai:gpt-4.1-mini",
        overrides={"temperature": 0.2},
    )

    # the override must MERGE, not replace — base routing keys survive
    assert captured["config"]["type"] == "openai"
    assert captured["config"]["model"] == "gpt-4.1-mini"
    assert captured["config"]["temperature"] == 0.2


def _install_provider_module(monkeypatch, module_name, class_name, selected):
    # Review C1: evict any previously-imported REAL provider module first.
    # factory.create_provider resolves `from .anthropic import ...` through
    # sys.modules; if the real module is already cached (cloud SDK installed,
    # imported by an earlier test), the stub installed below would never be
    # seen and a live SDK client could be constructed. delitem + setitem
    # guarantees the stub wins; monkeypatch restores both on teardown.
    monkeypatch.delitem(sys.modules, module_name, raising=False)
    module = ModuleType(module_name)

    class StubProvider:
        def __init__(self, config, **kwargs):
            selected.append((class_name, config, kwargs))
            self.config = config

    StubProvider.__name__ = class_name
    setattr(module, class_name, StubProvider)
    monkeypatch.setitem(sys.modules, module_name, module)


@pytest.mark.parametrize(
    ("provider_type", "module_name", "class_name"),
    [
        ("anthropic", "providers.anthropic", "AnthropicProvider"),
        ("claude", "providers.anthropic", "AnthropicProvider"),
        ("openai", "providers.openai_provider", "OpenAIProvider"),
        ("azure", "providers.openai_provider", "OpenAIProvider"),
        ("gemini", "providers.gemini", "GeminiProvider"),
    ],
)
def test_factory_dispatches_to_expected_provider_class(
    monkeypatch, provider_type, module_name, class_name
):
    selected = []
    _install_provider_module(monkeypatch, module_name, class_name, selected)

    provider = factory.create_provider(
        {
            "type": provider_type,
            "model": "model-id",
            "max_retries": 0,
            "rpm_limit": 0,
        }
    )

    assert provider.__class__.__name__ == class_name
    assert selected[0][0] == class_name
    assert selected[0][1].model == "model-id"


def test_factory_rejects_unknown_provider_type():
    with pytest.raises(ValueError, match="Unknown provider type: foo"):
        factory.create_provider(
            {"type": "foo", "model": "bar", "max_retries": 0, "rpm_limit": 0}
        )


def test_create_provider_invoke_maps_success_without_usage_stats(monkeypatch):
    """O6 pin: cloud LLMStats drops provider usage.

    Until O6 maps real provider token usage into LLMStats, cloud calls report
    success with prompt_tokens/num_ctx at dataclass defaults. That leaves the
    audit context-budget tripwire (O1) inert for cloud models.
    """
    provider = SimpleNamespace(
        provider_name="openai",
        config=SimpleNamespace(model="gpt-4.1-mini"),
        invoke=lambda _prompt: SimpleNamespace(content="ok"),
    )
    monkeypatch.setattr("providers.factory.create_provider", lambda _config: provider)

    invoke = llm_utils.create_provider_invoke({"type": "openai", "model": "gpt"})
    content, stats = invoke("prompt")

    assert content == "ok"
    assert stats.success is True
    assert stats.prompt_tokens == 0
    assert stats.num_ctx == 0


@pytest.mark.parametrize("exc", [ConnectionError("offline"), RuntimeError("boom")])
def test_create_provider_invoke_maps_provider_errors(monkeypatch, exc):
    def raise_error(_prompt):
        raise exc

    provider = SimpleNamespace(
        provider_name="openai",
        config=SimpleNamespace(model="gpt-4.1-mini"),
        invoke=raise_error,
    )
    monkeypatch.setattr("providers.factory.create_provider", lambda _config: provider)

    invoke = llm_utils.create_provider_invoke({"type": "openai", "model": "gpt"})
    content, stats = invoke("prompt")

    assert content == ""
    assert stats.success is False
