"""Mock-only regressions for capability-aware Ollama thinking requests."""
from __future__ import annotations

import ast
import asyncio
import copy
import logging
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

from broker.utils import llm_utils
from providers.llm_provider import LLMConfig as ProviderConfig
from providers.ollama import OllamaProvider


BASE_URL = "http://ollama.test:11434"


def _show_response(capabilities):
    response = MagicMock(status_code=200)
    response.json.return_value = {} if capabilities is None else {"capabilities": capabilities}
    return response


@pytest.fixture(autouse=True)
def _isolated_thinking_state(monkeypatch):
    """Use default run configuration; root conftest isolates process caches."""
    monkeypatch.setattr(llm_utils, "LLM_CONFIG", llm_utils.LLMConfig())


def test_default_disabled_adds_false_at_top_level_for_thinking_model(monkeypatch):
    monkeypatch.setattr(requests, "post", MagicMock(return_value=_show_response(["thinking"])))
    payload = {"model": "gemma4:12b", "options": {"num_ctx": 4096}}

    returned = llm_utils.apply_ollama_thinking(payload, base_url=BASE_URL)

    assert returned is payload
    assert payload["think"] is False
    assert "think" not in payload["options"]


@pytest.mark.parametrize(
    ("mode", "expected"),
    [("disabled", False), ("enabled", True), ("auto", None)],
)
def test_thinking_model_respects_all_modes(monkeypatch, mode, expected):
    monkeypatch.setattr(requests, "post", MagicMock(return_value=_show_response(["thinking"])))
    payload = {"model": "qwen3:8b", "options": {}}

    llm_utils.apply_ollama_thinking(payload, base_url=BASE_URL, thinking_mode=mode)

    if expected is None:
        assert "think" not in payload
    else:
        assert payload["think"] is expected


@pytest.mark.parametrize("mode", ["disabled", "enabled", "auto"])
def test_nonthinking_model_payload_is_byte_for_byte_unchanged(monkeypatch, mode):
    monkeypatch.setattr(requests, "post", MagicMock(return_value=_show_response(["completion"])))
    payload = {
        "model": "gemma3:4b",
        "prompt": "PROMPT",
        "stream": False,
        "format": None,
        "options": {"num_predict": 2048, "num_ctx": 4096},
    }
    before = copy.deepcopy(payload)

    llm_utils.apply_ollama_thinking(payload, base_url=BASE_URL, thinking_mode=mode)

    assert payload == before


def test_direct_nonthinking_posted_body_matches_prechange_request(monkeypatch):
    """Frozen pre-change default /generate body for gemma3:4b (c6473597)."""
    posted = []

    def post(url, **kwargs):
        if url.endswith("/api/show"):
            return _show_response(["completion"])
        posted.append(copy.deepcopy(kwargs["json"]))
        response = MagicMock(status_code=200)
        response.json.return_value = {"response": "ok"}
        return response

    monkeypatch.setattr(requests, "post", post)
    llm_utils._invoke_ollama_direct("gemma3:4b", "PROMPT", {}, False)

    assert posted == [{
        "model": "gemma3:4b", "prompt": "PROMPT", "stream": False, "format": None,
        "options": {"num_predict": 2048, "num_ctx": 4096},
    }]


@pytest.mark.parametrize("relative", [
    "examples/multi_agent/flood/paper3/launch_icc.py",
    "examples/multi_agent/flood/paper3/analysis/pa_prompt_calibration_test.py",
])
def test_direct_research_entrypoint_imports_helper_from_this_checkout(relative, tmp_path):
    """Import from an unrelated cwd, even if another WAGF checkout is installed."""
    root = Path(__file__).resolve().parents[2]
    script = root / relative
    code = "\n".join([
        "import inspect, pathlib, requests, runpy, sys",
        "def blocked(*args, **kwargs): raise AssertionError('unexpected HTTP request')",
        "requests.post = blocked",
        "runpy.run_path(sys.argv[1], run_name='thinking_import_check')",
        "from broker.utils.llm_utils import apply_ollama_thinking",
        "assert pathlib.Path(inspect.getfile(apply_ollama_thinking)).resolve() == pathlib.Path(sys.argv[2]).resolve()",
    ])
    completed = subprocess.run(
        [sys.executable, "-E", "-c", code, str(script), str(root / "broker/utils/llm_utils.py")],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_capability_lookup_is_one_request_per_endpoint_and_model_under_concurrency(monkeypatch):
    post_spy = MagicMock(return_value=_show_response(["thinking"])
                         )
    monkeypatch.setattr(requests, "post", post_spy)

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(
            lambda _: llm_utils.get_ollama_model_supports_thinking(
                "gemma4:12b", base_url=BASE_URL,
            ),
            range(24),
        ))

    assert results == [True] * 24
    post_spy.assert_called_once_with(
        f"{BASE_URL}/api/show", json={"model": "gemma4:12b"}, timeout=5,
    )


def test_capability_cache_keys_include_both_endpoint_and_model(monkeypatch):
    post_spy = MagicMock(return_value=_show_response(["thinking"]))
    monkeypatch.setattr(requests, "post", post_spy)

    assert llm_utils.get_ollama_model_supports_thinking("gemma4:12b", base_url=BASE_URL)
    assert llm_utils.get_ollama_model_supports_thinking("gemma4:12b", base_url=BASE_URL)
    assert llm_utils.get_ollama_model_supports_thinking("qwen3:8b", base_url=BASE_URL)
    assert llm_utils.get_ollama_model_supports_thinking(
        "gemma4:12b", base_url="http://other-ollama.test:11434",
    )

    assert post_spy.call_count == 3


@pytest.mark.parametrize(
    "failure",
    [
        requests.ConnectionError("daemon unavailable"),
        _show_response(None),
    ],
    ids=["request-failure", "missing-capabilities"],
)
def test_unknown_capability_warns_once_and_disabled_uses_family_fallback(
    monkeypatch, caplog, failure,
):
    if isinstance(failure, BaseException):
        post_spy = MagicMock(side_effect=failure)
    else:
        post_spy = MagicMock(return_value=failure)
    monkeypatch.setattr(requests, "post", post_spy)

    with caplog.at_level(logging.WARNING, logger=llm_utils.__name__):
        first = {"model": "gemma4:12b", "options": {}}
        second = {"model": "gemma4:12b", "options": {}}
        llm_utils.apply_ollama_thinking(first, base_url=BASE_URL)
        llm_utils.apply_ollama_thinking(second, base_url=BASE_URL)

    assert first["think"] is False
    assert second["think"] is False
    assert post_spy.call_count == (2 if isinstance(failure, BaseException) else 1)
    assert sum("capabilities unknown" in rec.getMessage() for rec in caplog.records) == 1


@pytest.mark.parametrize(
    "model",
    [
        "gemma4:12b",
        "registry.example/team/qwen3:8b",
        "deepseek-r1:8b",
        "gpt-oss:20b",
        "magistral-small:24b",
        "QWEN3.5:9b",
        "DeepSeek-V3.1:671b",
        "PHI4-REASONING:14b",
        "hf.co/unsloth/gemma-4-E4B-it-GGUF:Q4_K_M",
        "hf.co/team/custom-GEMMA4-model:latest",
        "hf.co/team/custom-QWEN3-model:latest",
    ],
)
def test_disabled_unknown_capability_falls_back_for_exact_known_families(monkeypatch, model):
    monkeypatch.setattr(requests, "post", MagicMock(side_effect=requests.ConnectionError("down")))
    payload = {"model": model, "options": {}}

    llm_utils.apply_ollama_thinking(payload, base_url=BASE_URL)

    assert payload["think"] is False


@pytest.mark.parametrize(
    "model",
    ["notgemma4:latest", "gemma40:latest", "myqwen3:8b", "deepseek-r10:8b", "gpt-ossified:7b"],
)
def test_disabled_unknown_capability_excludes_misleading_family_names(monkeypatch, model):
    monkeypatch.setattr(requests, "post", MagicMock(side_effect=requests.ConnectionError("down")))
    payload = {"model": model, "options": {}}

    llm_utils.apply_ollama_thinking(payload, base_url=BASE_URL)

    assert "think" not in payload


@pytest.mark.parametrize("mode", ["enabled", "auto"])
def test_unknown_capability_never_sends_opt_in_or_auto_flag(monkeypatch, mode):
    monkeypatch.setattr(requests, "post", MagicMock(side_effect=requests.ConnectionError("down")))
    payload = {"model": "gemma4:12b", "options": {}}

    llm_utils.apply_ollama_thinking(payload, base_url=BASE_URL, thinking_mode=mode)

    assert "think" not in payload


def test_successful_nonthinking_capability_overrides_known_family_fallback(monkeypatch):
    monkeypatch.setattr(requests, "post", MagicMock(return_value=_show_response(["completion"])))
    payload = {"model": "gemma4:12b", "options": {}}

    llm_utils.apply_ollama_thinking(payload, base_url=BASE_URL, thinking_mode="disabled")

    assert "think" not in payload


@pytest.mark.parametrize("failure", [
    requests.ConnectionError("starting"), requests.Timeout("slow show"),
    requests.HTTPError("server error", response=MagicMock(status_code=503)),
])
def test_transient_capability_failure_retries_later_and_warns_once(monkeypatch, caplog, failure):
    post = MagicMock(side_effect=[failure, failure, _show_response(["thinking"])])
    monkeypatch.setattr(requests, "post", post)
    with caplog.at_level(logging.WARNING, logger=llm_utils.__name__):
        bodies = [{"model": "custom-reasoner:1b"} for _ in range(4)]
        for body in bodies:
            llm_utils.apply_ollama_thinking(body, base_url=BASE_URL)
    assert "think" not in bodies[0] and "think" not in bodies[1]
    assert bodies[2]["think"] is False and bodies[3]["think"] is False
    assert post.call_count == 3
    assert sum("capabilities unknown" in r.getMessage() for r in caplog.records) == 1


def test_transient_failure_then_success_second_request_disables_thinking(monkeypatch):
    post = MagicMock(side_effect=[requests.ConnectionError("starting"), _show_response(["thinking"])])
    monkeypatch.setattr(requests, "post", post)
    first, second = {"model": "custom-reasoner"}, {"model": "custom-reasoner"}
    llm_utils.apply_ollama_thinking(first, base_url=BASE_URL)
    llm_utils.apply_ollama_thinking(second, base_url=BASE_URL)
    assert "think" not in first
    assert second["think"] is False
    assert post.call_count == 2


def test_real_nonthinking_capability_answer_is_cached(monkeypatch):
    post = MagicMock(return_value=_show_response(["completion"]))
    monkeypatch.setattr(requests, "post", post)
    for _ in range(3):
        assert llm_utils.get_ollama_model_supports_thinking("gemma3:4b", base_url=BASE_URL) is False
    assert post.call_count == 1


@pytest.mark.parametrize("levels", [["low", "medium", "high"], [True], ["true"]])
@pytest.mark.parametrize("field", ["thinking", "thinking_levels"])
def test_disabled_without_false_level_warns_once_and_records_unenforceable(monkeypatch, caplog, levels, field):
    response = _show_response(["thinking"])
    response.json.return_value[field] = {"levels": levels} if field == "thinking" else levels
    monkeypatch.setattr(requests, "post", MagicMock(return_value=response))
    with caplog.at_level(logging.WARNING, logger=llm_utils.__name__):
        for _ in range(2):
            body = {"model": "gpt-oss:20b"}
            llm_utils.apply_ollama_thinking(body)
            assert "think" not in body
    entry = llm_utils.get_llm_thinking_metadata("gpt-oss:20b")["models"]["gpt-oss:20b"]
    assert entry["think_enforceable"] is False
    assert entry["model_supports_thinking"] is True
    assert entry["think_sent"] is False
    assert sum("cannot enforce disabled" in r.getMessage() for r in caplog.records) == 1


@pytest.mark.parametrize("levels", [[False, True], ["false", "true"]])
def test_boolean_thinking_levels_allow_disabled(monkeypatch, levels):
    response = _show_response(["thinking"])
    response.json.return_value["thinking"] = {"levels": levels}
    monkeypatch.setattr(requests, "post", MagicMock(return_value=response))
    body = {"model": "gemma4:e4b"}
    llm_utils.apply_ollama_thinking(body)
    assert body["think"] is False


def test_experiment_manifest_records_unenforceable_disabled(monkeypatch, tmp_path):
    from broker.core.experiment_runner import ExperimentConfig, ExperimentRunner

    response = _show_response(["thinking"])
    response.json.return_value["thinking"] = {"levels": ["low", "medium", "high"]}
    monkeypatch.setattr(requests, "post", MagicMock(return_value=response))
    monkeypatch.setattr(llm_utils, "capture_ollama_modelfile_defaults", lambda *a, **k: (None, "mocked"))
    runner = ExperimentRunner(
        broker=MagicMock(), sim_engine=None, agents={},
        config=ExperimentConfig(model="gpt-oss:20b", num_years=1, output_dir=tmp_path),
    )
    with llm_utils.capture_ollama_thinking(runner._llm_thinking_observations):
        llm_utils.apply_ollama_thinking({"model": "gpt-oss:20b"})
    metadata = runner._collect_reproducibility_metadata()
    entry = metadata["llm_thinking"]["models"]["gpt-oss:20b"]
    assert metadata["thinking_mode"] == "disabled"
    assert entry["think_enforceable"] is False
    assert entry["think_sent"] is False
    assert entry["think_value"] is None


def test_nonnumeric_thinking_levels_do_not_invent_enabled_boolean(monkeypatch):
    response = _show_response(["thinking"])
    response.json.return_value["thinking_levels"] = ["low", "medium", "high"]
    monkeypatch.setattr(requests, "post", MagicMock(return_value=response))
    body = {"model": "gpt-oss:20b"}
    llm_utils.apply_ollama_thinking(body, thinking_mode="enabled")
    assert "think" not in body


@pytest.mark.parametrize("mode", [False, True, "off", "DISABLED", "invalid", None, 1, []])
def test_invalid_thinking_mode_rejected_at_config_construction(mode):
    with pytest.raises(ValueError, match="thinking_mode.*auto.*disabled.*enabled"):
        llm_utils.LLMConfig(thinking_mode=mode)


@pytest.mark.parametrize("yaml_value", ["off", "invalid", "null"])
def test_invalid_yaml_thinking_mode_fails_at_startup(monkeypatch, yaml_value):
    import yaml
    config = MagicMock()
    config.get.return_value = yaml.safe_load(f"llm:\n  thinking_mode: {yaml_value}\n")
    monkeypatch.setattr(llm_utils, "load_agent_config", MagicMock(return_value=config))
    monkeypatch.setattr(llm_utils.Path, "exists", MagicMock(return_value=True))
    with pytest.raises(ValueError, match="thinking_mode"):
        llm_utils._load_global_config()


@pytest.mark.parametrize("mode", ["auto", "enabled", "disabled"])
def test_qwen_no_think_suffix_only_in_disabled_mode(mode):
    prompt, retries = llm_utils.LLMConfig(thinking_mode=mode).apply_model_quirks("qwen3:8b", "PROMPT", 2)
    assert ("/no_think" in prompt) is (mode == "disabled")
    assert retries == 2


def test_get_think_flag_is_deprecated():
    with pytest.warns(DeprecationWarning, match="apply_ollama_thinking"):
        assert llm_utils.LLMConfig().get_think_flag() is False


def test_yaml_without_thinking_mode_loads_disabled_default(monkeypatch):
    config = MagicMock()
    config.get.return_value = {"llm": {}}
    monkeypatch.setattr(llm_utils, "load_agent_config", MagicMock(return_value=config))
    monkeypatch.setattr(llm_utils.Path, "exists", MagicMock(return_value=True))

    loaded = llm_utils._load_global_config()

    assert loaded.thinking_mode == "disabled"


def test_metadata_filters_stale_observations_and_reports_multiple_models(monkeypatch):
    endpoint = llm_utils.get_ollama_base_url()
    monkeypatch.setattr(
        llm_utils, "get_ollama_model_supports_thinking", lambda *a, **k: True,
    )
    llm_utils.apply_ollama_thinking(
        {"model": "gemma4:12b", "options": {}}, base_url=endpoint,
    )
    marker = llm_utils.ollama_thinking_sequence()
    llm_utils.apply_ollama_thinking(
        {"model": "qwen3:8b", "options": {}}, base_url=endpoint,
    )

    metadata = llm_utils.get_llm_thinking_metadata(
        ["gemma4:12b", "qwen3:8b"], since_sequence=marker,
    )

    assert metadata["models"]["gemma4:12b"] == {
        "mode": "disabled",
        "think_sent": None,
        "think_value": None,
        "model_supports_thinking": "unknown",
    }
    assert metadata["models"]["qwen3:8b"] == {
        "mode": "disabled",
        "think_sent": True,
        "think_value": False,
        "model_supports_thinking": True,
    }


def test_concurrent_run_observers_keep_same_model_requests_separate(monkeypatch):
    """Two worker scopes using one model report their own outgoing fields."""
    monkeypatch.setattr(requests, "post", MagicMock(return_value=_show_response(["thinking"])))
    observers = [{}, {}]

    def invoke(index):
        with llm_utils.capture_ollama_thinking(observers[index]):
            llm_utils.apply_ollama_thinking(
                {"model": "gemma4:12b", "options": {}},
                thinking_mode=("disabled", "enabled")[index],
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(invoke, [0, 1]))
    records = [llm_utils.get_llm_thinking_metadata("gemma4:12b", observations=o)
               ["models"]["gemma4:12b"] for o in observers]
    assert [r["think_value"] for r in records] == [False, True]
    assert [r["mode"] for r in records] == ["disabled", "enabled"]
    assert llm_utils._OLLAMA_THINKING_OBSERVER.get() is None


def test_direct_broker_path_delegates_to_helper_and_posts_its_wire_flag(monkeypatch):
    helper_spy = MagicMock(side_effect=lambda body, **_: body.update(think=False) or body)
    monkeypatch.setattr(llm_utils, "apply_ollama_thinking", helper_spy)
    response = MagicMock(status_code=200)
    response.json.return_value = {"response": "ok", "prompt_eval_count": 1, "eval_count": 1}

    with patch("requests.post", return_value=response) as post_spy:
        llm_utils._invoke_ollama_direct("gemma4:12b", "PROMPT", {}, False)

    helper_spy.assert_called_once()
    sent = post_spy.call_args.kwargs["json"]
    assert sent["think"] is False
    assert "think" not in sent["options"]


def test_sync_provider_delegates_to_helper_and_posts_its_wire_flag(monkeypatch):
    helper_spy = MagicMock(side_effect=lambda body, **_: body.update(think=False) or body)
    monkeypatch.setattr("providers.ollama.apply_ollama_thinking", helper_spy)
    provider = OllamaProvider(ProviderConfig(model="gemma4:12b"), base_url=BASE_URL)
    response = MagicMock()
    response.json.return_value = {"response": "ok"}
    provider._client = MagicMock()
    provider._client.post.return_value = response

    provider.invoke("PROMPT")

    helper_spy.assert_called_once()
    assert helper_spy.call_args.kwargs == {"base_url": BASE_URL, "thinking_mode": None}
    assert provider._client.post.call_args.kwargs["json"]["think"] is False


def test_async_provider_delegates_to_helper_and_posts_its_wire_flag(monkeypatch):
    helper_spy = MagicMock(side_effect=lambda body, **_: body.update(think=True) or body)
    monkeypatch.setattr("providers.ollama.apply_ollama_thinking", helper_spy)
    provider = OllamaProvider(ProviderConfig(model="gemma4:12b"), base_url=BASE_URL)
    response = MagicMock()
    response.json.return_value = {"response": "ok"}
    provider._async_client = MagicMock()
    provider._async_client.post = AsyncMock(return_value=response)

    asyncio.run(provider.ainvoke("PROMPT", thinking_mode="enabled"))

    helper_spy.assert_called_once()
    assert helper_spy.call_args.kwargs == {"base_url": BASE_URL, "thinking_mode": "enabled"}
    assert provider._async_client.post.call_args.kwargs["json"]["think"] is True


def _static_ollama_builders(tree):
    """Find HTTP generate/chat bodies and imported Ollama Python-client calls."""
    modules, factories, methods = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.asname or alias.name for alias in node.names if alias.name == "ollama")
        elif isinstance(node, ast.ImportFrom) and node.module == "ollama":
            factories.update(alias.asname or alias.name for alias in node.names if alias.name in {"Client", "AsyncClient"})
            methods.update(alias.asname or alias.name for alias in node.names if alias.name in {"generate", "chat"})

    def factory(call):
        return isinstance(call, ast.Call) and (
            isinstance(call.func, ast.Name) and call.func.id in factories
            or isinstance(call.func, ast.Attribute) and call.func.attr in {"Client", "AsyncClient"}
            and isinstance(call.func.value, ast.Name) and call.func.value.id in modules
        )

    clients = set()
    urls = set()

    def endpoint(value):
        return any(
            isinstance(node, ast.Constant) and isinstance(node.value, str)
            and any(path in node.value for path in ("/api/generate", "/api/chat"))
            or isinstance(node, (ast.Name, ast.Attribute)) and ast.unparse(node) in urls
            for node in ast.walk(value)
        )

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if factory(node.value):
                clients.update(ast.dump(target) for target in targets)
            if endpoint(node.value):
                urls.update(ast.unparse(target) for target in targets)

    def client_target(value):
        # Compare expression shape independently of Store/Load context.
        if isinstance(value, ast.Name):
            return ast.dump(ast.Name(id=value.id, ctx=ast.Store())) in clients
        if isinstance(value, ast.Attribute):
            return ast.dump(ast.Attribute(value=value.value, attr=value.attr, ctx=ast.Store())) in clients
        return factory(value)

    class Inventory(ast.NodeVisitor):
        def __init__(self):
            self.functions, self.builders = [], set()

        def visit_FunctionDef(self, node):
            self.functions.append(node.name)
            self.generic_visit(node)
            self.functions.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def record(self):
            self.builders.add(self.functions[-1] if self.functions else "<module>")

        def visit_Call(self, node):
            target = node.func
            if isinstance(target, ast.Attribute) and target.attr in {"post", "request"}:
                position = 1 if target.attr == "request" else 0
                url = node.args[position] if len(node.args) > position else next(
                    (k.value for k in node.keywords if k.arg == "url"), None,
                )
                if url is not None and endpoint(url):
                    self.record()
            if (isinstance(target, ast.Name) and target.id in methods or
                isinstance(target, ast.Attribute) and target.attr in {"generate", "chat"}
                and (isinstance(target.value, ast.Name) and target.value.id in modules or client_target(target.value))):
                self.record()
            self.generic_visit(node)

    inventory = Inventory()
    inventory.visit(tree)
    return inventory.builders


@pytest.mark.parametrize("source", [
    'def builder(): requests.post("http://host/api/chat", json={})',
    'import ollama\ndef builder(): ollama.chat(model="x")',
    'import ollama as o\ndef builder(): o.generate(model="x")',
    'from ollama import chat as send\ndef builder(): send(model="x")',
    'from ollama import Client\ndef builder():\n client=Client()\n client.generate(model="x")',
    'from ollama import AsyncClient as C\nasync def builder():\n client=C()\n await client.chat(model="x")',
    'import ollama\ndef builder(): ollama.Client().chat(model="x")',
    'from ollama import Client\nclass P:\n def builder(self):\n  self.client=Client()\n  self.client.chat(model="x")',
    'URL="http://host/api/chat"\ndef builder(): requests.post(URL, json={})',
])
def test_static_inventory_detects_chat_and_python_client_bypasses(source):
    assert _static_ollama_builders(ast.parse(source)) == {"builder"}


def test_all_static_ollama_generate_builders_route_through_shared_helper():
    """Guard every generate/chat HTTP and Ollama Python-client request builder."""
    root = Path(__file__).resolve().parents[2]
    discovered = {}
    trees = {}
    for source_root in (root / "broker", root / "providers", root / "examples"):
        for path in source_root.rglob("*.py"):
            if "tests" in path.parts:
                continue
            source = path.read_text(encoding="utf-8-sig")
            relative = path.relative_to(root).as_posix()
            tree = ast.parse(source, filename=str(path))
            builders = _static_ollama_builders(tree)
            if builders:
                discovered[relative] = builders
                trees[relative] = tree

    expected_builders = {
        "broker/utils/llm_utils.py": {"_invoke_ollama_direct"},
        "providers/ollama.py": {"invoke", "ainvoke"},
        "examples/multi_agent/flood/paper3/launch_icc.py": {"preload_model"},
        "examples/multi_agent/flood/paper3/run_cv.py": {"invoke"},
        "examples/multi_agent/flood/paper3/analysis/calibration_hooks.py": {"invoke"},
        "examples/multi_agent/flood/paper3/analysis/pa_prompt_calibration_test.py": {
            "_invoke_ollama",
        },
    }
    assert discovered == expected_builders

    missing_helper = []
    for relative, function_names in expected_builders.items():
        functions = [
            node for node in ast.walk(trees[relative])
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for function_name in function_names:
            candidates = [node for node in functions if node.name == function_name]
            calls_helper = any(
                isinstance(call, ast.Call)
                and (
                    isinstance(call.func, ast.Name)
                    and call.func.id == "apply_ollama_thinking"
                    or isinstance(call.func, ast.Attribute)
                    and call.func.attr == "apply_ollama_thinking"
                    or isinstance(call.func, ast.Attribute)
                    and call.func.attr == "to_thread"
                    and call.args
                    and isinstance(call.args[0], ast.Name)
                    and call.args[0].id == "apply_ollama_thinking"
                )
                for function in candidates
                for call in ast.walk(function)
            )
            if not candidates or not calls_helper:
                missing_helper.append(f"{relative}:{function_name}")

    assert missing_helper == []
