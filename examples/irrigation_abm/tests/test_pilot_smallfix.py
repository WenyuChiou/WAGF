"""Focused regressions for the three small fixes found by the 15-year pilot."""
from __future__ import annotations

import json
from types import SimpleNamespace

from broker.components.cognitive.reflection import ReflectionEngine, run_checked_reflection
from examples.irrigation_abm.run_experiment import _effective_irrigation_llm_values


def test_reflection_input_is_logged_for_retry_and_stored_insight(tmp_path):
    reflection_log = tmp_path / "reflection_log.jsonl"
    checks_log = tmp_path / "reflection_checks.jsonl"
    engine = ReflectionEngine(output_path=str(reflection_log))
    replies = iter(["?", '{"A": "I learned to keep my request steady."}'])
    inputs = ["2029: you asked for 100 acre-ft.", "2030: you asked for 90 acre-ft."]

    result = run_checked_reflection(
        engine,
        prompt="PROMPT",
        agent_id="A",
        period=2030,
        llm_call=lambda _prompt: next(replies),
        reflection_input=inputs,
        log_path=checks_log,
    )
    engine.store_insight("A", result.last_insight)

    attempts = [json.loads(line) for line in checks_log.read_text(encoding="utf-8").splitlines()]
    stored = json.loads(reflection_log.read_text(encoding="utf-8"))
    assert [row["reflection_input"] for row in attempts] == [inputs, inputs]
    assert stored["reflection_input"] == inputs


def test_effective_num_ctx_prefers_the_agent_config_that_invoke_sends():
    config = SimpleNamespace(
        get_llm_params=lambda _agent_type: {"num_ctx": 8192, "num_predict": 4096}
    )

    values = _effective_irrigation_llm_values(
        config,
        tuned=SimpleNamespace(num_ctx=4096, num_predict=2048),
        num_ctx_override=None,
        num_predict_override=None,
    )

    assert values == {"num_ctx": 8192, "num_predict": 4096}


def test_effective_num_ctx_uses_cli_when_agent_config_has_no_value():
    config = SimpleNamespace(get_llm_params=lambda _agent_type: {})

    values = _effective_irrigation_llm_values(
        config,
        tuned=SimpleNamespace(num_ctx=4096, num_predict=2048),
        num_ctx_override=12288,
        num_predict_override=3072,
    )

    assert values == {"num_ctx": 12288, "num_predict": 3072}


def test_ollama_server_version_garbled_status_line_returns_null(monkeypatch):
    import http.client
    from unittest.mock import Mock
    from examples.irrigation_abm.run_experiment import _read_ollama_server_version
    reply = Mock(side_effect=http.client.BadStatusLine("garbled reply"))
    monkeypatch.setattr("urllib.request.urlopen", reply)
    assert _read_ollama_server_version("gemma3:4b") is None
    reply.assert_called_once()


def test_ollama_server_version_garbled_json_returns_null(monkeypatch):
    from io import BytesIO
    from examples.irrigation_abm.run_experiment import _read_ollama_server_version
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: BytesIO(b"garbled reply"))
    assert _read_ollama_server_version("gemma3:4b") is None


def test_manifest_num_predict_records_effective_4096_not_tuned_2048(monkeypatch, tmp_path):
    from broker.tests.test_manifest_llm_params import _make_finalize_runner
    from broker.utils.agent_config import AgentTypeConfig
    from broker.utils import llm_utils
    from examples.irrigation_abm.tests.test_beneficial_use_limit import CONFIG
    cfg = AgentTypeConfig.load(str(CONFIG))
    effective = _effective_irrigation_llm_values(
        cfg, tuned=SimpleNamespace(num_ctx=4096, num_predict=2048))
    monkeypatch.setattr(llm_utils.LLM_CONFIG, "num_predict", effective["num_predict"])
    runner = _make_finalize_runner(tmp_path)
    metadata = runner._collect_reproducibility_metadata()
    assert effective["num_predict"] == metadata["num_predict"] == 4096
