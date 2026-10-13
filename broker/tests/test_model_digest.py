"""Launch-time model digest capture, with every network operation mocked."""
from __future__ import annotations

import http.client
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

from broker.core.experiment_runner import ExperimentRunner
from broker.utils import llm_utils


@pytest.fixture(autouse=True)
def _clear_show_cache():
    llm_utils._OLLAMA_SHOW_METADATA.clear()
    llm_utils._OLLAMA_THINKING_CAPABILITIES.clear()
    llm_utils._OLLAMA_THINKING_LEVELS.clear()


def _runner(model: str) -> ExperimentRunner:
    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.config = SimpleNamespace(model=model)
    return runner


@pytest.mark.parametrize("model", ["mock", "openai:gpt-5"])
def test_mock_and_cloud_digest_are_null_without_network_or_warning(model, caplog):
    runner = _runner(model)
    with caplog.at_level(logging.WARNING), patch("requests.post") as post, patch(
        "requests.get"
    ) as get:
        runner._capture_model_metadata_at_launch()

    assert runner._model_metadata_at_launch["model_digest"] is None
    post.assert_not_called()
    get.assert_not_called()
    assert "model digest is unavailable" not in caplog.text


def test_digest_uses_show_once_and_reuses_response_for_capabilities():
    runner = _runner("gemma3:4b")
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "digest": "sha256:abc",
        "capabilities": ["thinking"],
        "details": {"family": "gemma3", "parameter_size": "4B"},
    }
    response.raise_for_status.return_value = None

    with patch("requests.post", return_value=response) as post, patch("requests.get") as get:
        runner._capture_model_metadata_at_launch()
        assert llm_utils.get_ollama_model_supports_thinking("gemma3:4b") is True

    assert runner._model_metadata_at_launch["model_digest"] == "sha256:abc"
    assert post.call_count == 1
    get.assert_not_called()


def test_digest_falls_back_to_tags_when_show_has_no_digest():
    runner = _runner("gemma3:4b")
    show = MagicMock(status_code=200)
    show.json.return_value = {"modified_at": "not-a-digest", "capabilities": []}
    show.raise_for_status.return_value = None
    tags = MagicMock(status_code=200)
    tags.json.return_value = {
        "models": [{"name": "gemma3:4b", "digest": "sha256:from-tags"}]
    }
    tags.raise_for_status.return_value = None

    with patch("requests.post", return_value=show) as post, patch("requests.get", return_value=tags) as get:
        runner._capture_model_metadata_at_launch()

    assert runner._model_metadata_at_launch["model_digest"] == "sha256:from-tags"
    assert post.call_count == 1
    assert get.call_count == 1


def test_missing_digest_warns_once_at_launch(caplog):
    runner = _runner("gemma3:4b")
    show = MagicMock(status_code=200)
    show.json.return_value = {"capabilities": []}
    show.raise_for_status.return_value = None
    tags = MagicMock(status_code=200)
    tags.json.return_value = {"models": []}
    tags.raise_for_status.return_value = None

    with caplog.at_level(logging.WARNING), patch(
        "requests.post", return_value=show
    ), patch("requests.get", return_value=tags):
        runner._capture_model_metadata_at_launch()

    assert runner._model_metadata_at_launch["model_digest"] is None
    assert caplog.text.count("model digest is unavailable") == 1


def test_unreachable_local_service_warns_once_at_launch(caplog):
    runner = _runner("gemma3:4b")
    with caplog.at_level(logging.WARNING), patch(
        "requests.post", side_effect=requests.ConnectionError("offline")
    ):
        runner._capture_model_metadata_at_launch()

    assert runner._model_metadata_at_launch["model_digest"] is None
    assert caplog.text.count("model digest is unavailable") == 1


def test_http_exception_degrades_digest_to_null():
    runner = _runner("gemma3:4b")
    with patch("requests.post", side_effect=http.client.BadStatusLine("bad")):
        runner._capture_model_metadata_at_launch()

    assert runner._model_metadata_at_launch["model_digest"] is None
