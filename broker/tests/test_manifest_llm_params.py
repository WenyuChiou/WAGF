"""
Regression tests for the reproducibility manifest's resolved-LLM-params
fields (r19 G7/G8, verified 2026-09-23; hardened per Opus review the same
day: per-type model identity, multi-model keyed llm_model_defaults, cloud
provider gating, and a frozen request-body characterization test).

Gap recap: ``_collect_reproducibility_metadata`` recorded ``temperature`` /
``top_p`` from the module-level ``LLM_CONFIG`` singleton
(``broker/utils/llm_utils.py``), but the params actually sent per call come
from ``ExperimentRunner.get_llm_invoke`` merging
``AgentTypeConfig.get_llm_params(agent_type)`` as overrides into
``create_llm_invoke`` / ``_invoke_ollama_direct``. A flood run sending
temperature=0.8/top_p=0.9/top_k=40 and an irrigation run sending none of the
three (Ollama's own modelfile defaults then apply) both recorded null for
both fields; ``top_k`` was never recorded at all; and no Ollama ``seed`` is
sent, which the manifest never stated.

Fix adds three manifest keys, computed with the SAME merge the runner uses
(``broker.utils.llm_utils.resolve_ollama_params``, also used by
``create_llm_invoke`` itself; see that module for the shared helper):

- ``llm_params_resolved``: per-agent-type dict of the MERGED params actually
  sent (LLM_CONFIG's run-wide num_ctx/num_predict plus whatever that type
  overrode), plus "model" (the resolved model name for that type). A
  cloud-provider agent type records its raw overrides instead (that path
  never merges with LLM_CONFIG). Populated by ``ExperimentRunner.get_llm_invoke``.
- ``llm_model_defaults``: dict keyed by distinct model name, holding that
  model's own ``ollama show --modelfile`` PARAMETER lines. The mock model is
  omitted entirely; a cloud-provider model gets ``None`` paired with
  ``"not an Ollama model"`` in ``llm_model_defaults_error``.
- ``llm_sampling_seeded``: whether the Ollama request options include a
  ``seed`` key, read off the actual options builder rather than hardcoded.
  ``None`` (not ``False``) when every distinct model resolved is a
  cloud-provider model, since no Ollama request path was ever reached.

These tests use minimal in-memory mocks (``ExperimentRunner.__new__`` +
``MagicMock`` broker), the same pattern as
``test_silent_failure_fixes.py``'s F1/F3 tests: a full experiment run is not
needed to exercise this surgical contract.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from broker.core.experiment_runner import ExperimentRunner
from broker.utils import llm_utils


class _FakeAgentTypeConfig:
    """Minimal stand-in for ``AgentTypeConfig.get_llm_params``."""

    def __init__(self, llm_params_by_type: dict):
        self._by_type = llm_params_by_type

    def get_llm_params(self, agent_type: str) -> dict:
        # Real AgentTypeConfig.get_llm_params always returns a FRESH merged
        # dict (shared/global_config/agent-block union), never a shared
        # reference. Mirrored here so a caller popping "model" out of it
        # cannot leak between agent types or test cases.
        return dict(self._by_type.get(agent_type, {}))


def _make_runner(agent_config, model: str = "mock") -> ExperimentRunner:
    """Build a minimal ExperimentRunner for get_llm_invoke, without standing
    up real LLM / broker infrastructure (same pattern as
    test_silent_failure_fixes.py)."""
    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.config = MagicMock()
    runner.config.model = model
    runner.config.verbose = False
    runner._llm_cache = {}
    runner._llm_resolved_params = {}
    runner.broker = MagicMock()
    runner.broker.config = agent_config
    return runner


def _make_finalize_runner(tmp_path: Path, model: str = "mock", resolved=None) -> ExperimentRunner:
    """Build a minimal runner sufficient to call
    ``_collect_reproducibility_metadata()`` directly (same pattern as
    TestF3SummaryWriteIndependentOfManifestWrite in
    test_silent_failure_fixes.py)."""
    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.broker = MagicMock()
    runner.broker.model_adapter = MagicMock()
    runner.broker.model_adapter.config_path = None
    runner.memory_engine = MagicMock()
    runner.agents = {}
    runner.sim_engine = MagicMock()
    runner.config = MagicMock()
    runner.config.model = model
    runner.config.verbose = False
    runner.config.seed = 42
    runner.config.governance_profile = "strict"
    runner.config.output_dir = tmp_path
    runner._llm_resolved_params = resolved or {}
    return runner


@pytest.fixture(autouse=True)
def _fixed_llm_config(monkeypatch):
    """Pin LLM_CONFIG to a known state so assertions below do not depend on
    whichever agent_types.yaml happens to be on cwd when pytest runs (see
    llm_utils._load_global_config, which reads Path.cwd() / 'agent_types.yaml'
    at import time)."""
    fixed = llm_utils.LLMConfig(num_predict=999, num_ctx=1234)
    monkeypatch.setattr(llm_utils, "LLM_CONFIG", fixed)
    yield


# ─────────────────────────────────────────────────────────────────────
# (a) per-type sampling overrides appear in llm_params_resolved, with model
# ─────────────────────────────────────────────────────────────────────


class TestLLMParamsResolvedPerAgentType:
    def test_per_type_temperature_top_p_top_k_appear_resolved(self):
        """A per-type llm block setting temperature/top_p/top_k must show up
        verbatim in _llm_resolved_params (and therefore in the manifest's
        llm_params_resolved[<type>]), alongside the resolved model name."""
        agent_config = _FakeAgentTypeConfig({
            "household": {"temperature": 0.8, "top_p": 0.9, "top_k": 40},
        })
        runner = _make_runner(agent_config, model="mock")

        runner.get_llm_invoke("household")

        resolved = runner._llm_resolved_params["household"]
        assert resolved["temperature"] == 0.8
        assert resolved["top_p"] == 0.9
        assert resolved["top_k"] == 40
        # Base LLMConfig fields (from resolve_ollama_params) still present:
        # this is the MERGED dict, not only the overridden keys.
        assert resolved["num_predict"] == 999
        assert resolved["num_ctx"] == 1234
        # No per-type model override was given, so it falls back to the run
        # model (self.config.model).
        assert resolved["model"] == "mock"

    def test_resolved_dict_matches_the_shared_merge_helper_plus_model(self):
        """llm_params_resolved must be computed via resolve_ollama_params
        (not a re-derived, possibly-divergent copy of the merge), with
        "model" added on top."""
        overrides = {"temperature": 0.8, "top_p": 0.9, "top_k": 40}
        agent_config = _FakeAgentTypeConfig({"household": overrides})
        runner = _make_runner(agent_config, model="mock")

        runner.get_llm_invoke("household")

        expected = dict(llm_utils.resolve_ollama_params(overrides))
        expected["model"] = "mock"
        assert runner._llm_resolved_params["household"] == expected

    def test_only_agent_types_actually_invoked_are_recorded(self):
        """An agent type never passed to get_llm_invoke (e.g. a non-LLM
        decider) must not appear: this reports what was REALLY sent."""
        agent_config = _FakeAgentTypeConfig({
            "household": {"temperature": 0.8},
            "government": {"temperature": 0.2},
        })
        runner = _make_runner(agent_config, model="mock")

        runner.get_llm_invoke("household")

        assert "household" in runner._llm_resolved_params
        assert "government" not in runner._llm_resolved_params

    def test_per_type_model_override_recorded_per_agent_type(self):
        """llm_params.model overriding the CLI/run model for one agent type
        must be visible in that type's own resolved dict, distinct from a
        sibling type that stayed on the run's default model."""
        agent_config = _FakeAgentTypeConfig({
            "household": {},
            "government": {"model": "llama3.3:70b"},
        })
        runner = _make_runner(agent_config, model="mock")

        # get_llm_invoke's real Ollama-construction path is not under test
        # here (that's create_llm_invoke's own job, covered elsewhere); stub
        # it out so this test stays a pure resolved-params check.
        with patch.object(
            llm_utils, "create_llm_invoke", return_value=lambda p: ("{}", None),
        ):
            runner.get_llm_invoke("household")
            runner.get_llm_invoke("government")

        assert runner._llm_resolved_params["household"]["model"] == "mock"
        assert runner._llm_resolved_params["government"]["model"] == "llama3.3:70b"


# ─────────────────────────────────────────────────────────────────────
# (a2) cloud-provider agent types record raw overrides, not the Ollama merge
# ─────────────────────────────────────────────────────────────────────


class TestCloudProviderAgentType:
    def test_cloud_provider_model_records_raw_overrides_not_ollama_merge(self):
        """A per-type llm_params.model naming a cloud provider (e.g.
        gemini:pro) never reaches resolve_ollama_params: create_llm_invoke's
        own routing sends it straight to create_provider_invoke, whose config
        is {"type", "model"} updated with the RAW overrides dict, never
        LLM_CONFIG. llm_params_resolved must record exactly that, not a
        misleading Ollama-shaped merge with num_ctx/num_predict the provider
        path never looks at."""
        agent_config = _FakeAgentTypeConfig({
            "trader": {"model": "gemini:pro", "temperature": 0.3},
        })
        runner = _make_runner(agent_config, model="mock")

        with patch.object(
            llm_utils, "create_provider_invoke", return_value=lambda p: ("{}", None),
        ):
            runner.get_llm_invoke("trader")

        resolved = runner._llm_resolved_params["trader"]
        assert resolved == {"model": "gemini:pro", "temperature": 0.3}
        # Specifically must NOT contain the Ollama-only run-wide defaults.
        assert "num_predict" not in resolved
        assert "num_ctx" not in resolved


# ─────────────────────────────────────────────────────────────────────
# (b) no per-type sampling keys -> absent from resolved dict;
#     llm_model_defaults is None for the mock model (no ollama call)
# ─────────────────────────────────────────────────────────────────────


class TestLLMParamsResolvedAbsentAndMockSkip:
    def test_no_per_type_sampling_keys_are_absent_not_null(self):
        """When the per-type llm block sets nothing, temperature/top_p/top_k
        must be ABSENT from the resolved dict (matching resolve_ollama_params'
        None-means-omit contract), not present as null."""
        agent_config = _FakeAgentTypeConfig({"household": {}})
        runner = _make_runner(agent_config, model="mock")

        runner.get_llm_invoke("household")

        resolved = runner._llm_resolved_params["household"]
        assert "temperature" not in resolved
        assert "top_p" not in resolved
        assert "top_k" not in resolved
        assert resolved == {"num_predict": 999, "num_ctx": 1234, "model": "mock"}

    def test_llm_model_defaults_is_none_for_mock_model_no_ollama_call(self, tmp_path):
        """The mock model never talks to Ollama: llm_model_defaults must be
        None, and capture_ollama_modelfile_defaults (the only path that would
        shell out to `ollama show`) must never be called. Spied directly
        rather than via a global subprocess.run patch, because
        _collect_reproducibility_metadata also shells out to `git` through
        subprocess internally (git status/rev-parse), which a blanket
        subprocess.run spy would also catch."""
        runner = _make_finalize_runner(tmp_path, model="mock")

        with patch(
            "broker.utils.llm_utils.capture_ollama_modelfile_defaults"
        ) as capture_spy:
            metadata = runner._collect_reproducibility_metadata()

        assert metadata["llm_model_defaults"] is None
        assert "llm_model_defaults_error" not in metadata
        capture_spy.assert_not_called()

    def test_llm_model_defaults_captured_for_real_model(self, tmp_path):
        """A non-mock model DOES call `ollama show <model> --modelfile` with
        the expected argv, and the PARAMETER lines are parsed into
        llm_model_defaults, keyed by model name."""
        runner = _make_finalize_runner(tmp_path, model="gemma3:4b")
        fake_modelfile = (
            "FROM /some/blob\n"
            "PARAMETER temperature 1\n"
            "PARAMETER top_k 64\n"
            "PARAMETER top_p 0.95\n"
        )
        fake_result = MagicMock(returncode=0, stdout=fake_modelfile, stderr="")

        with patch("subprocess.run", return_value=fake_result) as run_spy:
            metadata = runner._collect_reproducibility_metadata()

        # The exact argv used to fetch this model's modelfile must appear
        # among the calls (subprocess.run is also used internally for git
        # provenance, so we search call_args_list rather than assuming
        # position).
        ollama_calls = [
            c for c in run_spy.call_args_list
            if c.args and c.args[0] == ["ollama", "show", "gemma3:4b", "--modelfile"]
        ]
        assert len(ollama_calls) == 1

        assert metadata["llm_model_defaults"] == {
            "gemma3:4b": {"temperature": 1, "top_k": 64, "top_p": 0.95},
        }
        assert "llm_model_defaults_error" not in metadata

    def test_llm_model_defaults_failure_records_null_plus_warning(self, tmp_path):
        """Ollama absent / unreachable must record None + an error string,
        keyed by model name, never raise out of manifest collection."""
        runner = _make_finalize_runner(tmp_path, model="gemma3:4b")

        with patch("subprocess.run", side_effect=FileNotFoundError("no ollama")):
            metadata = runner._collect_reproducibility_metadata()

        assert metadata["llm_model_defaults"] == {"gemma3:4b": None}
        assert metadata["llm_model_defaults_error"] == {
            "gemma3:4b": "ollama executable not found on PATH",
        }

    def test_stop_parameter_is_always_a_list(self, tmp_path):
        """A modelfile with exactly one PARAMETER stop line must still
        produce a list under "stop", not a bare string."""
        runner = _make_finalize_runner(tmp_path, model="gemma3:4b")
        fake_modelfile = 'PARAMETER stop "<end_of_turn>"\nPARAMETER temperature 1\n'
        fake_result = MagicMock(returncode=0, stdout=fake_modelfile, stderr="")

        with patch("subprocess.run", return_value=fake_result):
            metadata = runner._collect_reproducibility_metadata()

        defaults = metadata["llm_model_defaults"]["gemma3:4b"]
        assert defaults["stop"] == ["<end_of_turn>"]
        assert isinstance(defaults["stop"], list)


# ─────────────────────────────────────────────────────────────────────
# (b2) multi-model + cloud-provider gating in llm_model_defaults
# ─────────────────────────────────────────────────────────────────────


class TestMultiModelAndCloudProviderGating:
    def test_distinct_models_from_resolved_params_each_captured_once(self, tmp_path):
        """Two agent types resolving to two DIFFERENT Ollama models each get
        their own ollama-show call and their own key in llm_model_defaults."""
        resolved = {
            "household": {"model": "gemma3:4b", "temperature": 0.8},
            "government": {"model": "gemma4:12b"},
        }
        runner = _make_finalize_runner(tmp_path, model="gemma3:4b", resolved=resolved)

        def _fake_run(argv, **kwargs):
            model = argv[2]
            body = f"PARAMETER temperature 1\nPARAMETER top_k 64\n# {model}\n"
            return MagicMock(returncode=0, stdout=body, stderr="")

        with patch("subprocess.run", side_effect=_fake_run) as run_spy:
            metadata = runner._collect_reproducibility_metadata()

        called_models = sorted(
            c.args[0][2] for c in run_spy.call_args_list
            if c.args and c.args[0][:2] == ["ollama", "show"]
        )
        assert called_models == ["gemma3:4b", "gemma4:12b"]
        assert set(metadata["llm_model_defaults"]) == {"gemma3:4b", "gemma4:12b"}

    def test_cloud_provider_model_gets_none_and_not_an_ollama_model_error(self, tmp_path):
        """A cloud-provider model in llm_params_resolved must get None in
        llm_model_defaults plus "not an Ollama model" in
        llm_model_defaults_error, WITHOUT ever calling `ollama show`."""
        resolved = {"trader": {"model": "gemini:pro", "temperature": 0.3}}
        runner = _make_finalize_runner(tmp_path, model="mock", resolved=resolved)

        with patch("broker.utils.llm_utils.capture_ollama_modelfile_defaults") as capture_spy:
            metadata = runner._collect_reproducibility_metadata()

        capture_spy.assert_not_called()
        assert metadata["llm_model_defaults"] == {"gemini:pro": None}
        assert metadata["llm_model_defaults_error"] == {"gemini:pro": "not an Ollama model"}

    def test_mixed_ollama_and_cloud_models_only_cloud_entry_errors(self, tmp_path):
        """A run using one Ollama model and one cloud model: the Ollama
        model's defaults are captured normally, the cloud model's are None
        plus the not-an-Ollama-model error, and exactly ONE ollama-show call
        is made (never for the cloud model). subprocess.run is also used
        internally for git provenance in this same method, so the count is
        checked against ollama-show calls specifically, not the raw total."""
        resolved = {
            "household": {"model": "gemma3:4b"},
            "trader": {"model": "gemini:pro"},
        }
        runner = _make_finalize_runner(tmp_path, model="mock", resolved=resolved)
        fake_result = MagicMock(
            returncode=0, stdout="PARAMETER temperature 1\n", stderr="",
        )

        with patch("subprocess.run", return_value=fake_result) as run_spy:
            metadata = runner._collect_reproducibility_metadata()

        ollama_calls = [
            c for c in run_spy.call_args_list
            if c.args and c.args[0][:2] == ["ollama", "show"]
        ]
        assert len(ollama_calls) == 1
        assert ollama_calls[0].args[0] == ["ollama", "show", "gemma3:4b", "--modelfile"]
        assert metadata["llm_model_defaults"] == {
            "gemma3:4b": {"temperature": 1},
            "gemini:pro": None,
        }
        assert metadata["llm_model_defaults_error"] == {"gemini:pro": "not an Ollama model"}


# ─────────────────────────────────────────────────────────────────────
# (c) llm_sampling_seeded is False, derived from the options builder, and
#     None when every distinct model is a cloud provider
# ─────────────────────────────────────────────────────────────────────


class TestSamplingSeeded:
    def test_ollama_sampling_is_seeded_false_today(self):
        assert llm_utils.ollama_sampling_is_seeded() is False

    def test_ollama_sampling_is_seeded_reads_the_real_options_builder(self, monkeypatch):
        """Prove this is NOT a hardcoded False: if the options builder ever
        adds a seed key, ollama_sampling_is_seeded must see it, verified by
        monkeypatching the actual builder, not the seeded function itself."""
        original_builder = llm_utils._build_ollama_options

        def _with_seed(model, params):
            options = original_builder(model, params)
            options["seed"] = 42
            return options

        monkeypatch.setattr(llm_utils, "_build_ollama_options", _with_seed)

        assert llm_utils.ollama_sampling_is_seeded() is True

    def test_manifest_llm_sampling_seeded_is_false_for_mock(self, tmp_path):
        runner = _make_finalize_runner(tmp_path, model="mock")

        metadata = runner._collect_reproducibility_metadata()

        assert metadata["llm_sampling_seeded"] is False

    def test_manifest_llm_sampling_seeded_is_false_for_ollama_model(self, tmp_path):
        resolved = {"household": {"model": "gemma3:4b"}}
        runner = _make_finalize_runner(tmp_path, model="gemma3:4b", resolved=resolved)

        with patch("subprocess.run", side_effect=FileNotFoundError("no ollama")):
            metadata = runner._collect_reproducibility_metadata()

        assert metadata["llm_sampling_seeded"] is False

    def test_manifest_llm_sampling_seeded_is_none_when_only_cloud_models(self, tmp_path):
        """A run whose only resolved model is a cloud provider never reaches
        the Ollama request path at all, so "seeded" does not apply: None,
        not False (False would misleadingly imply an unseeded Ollama call
        happened)."""
        resolved = {"trader": {"model": "gemini:pro"}}
        runner = _make_finalize_runner(tmp_path, model="mock", resolved=resolved)

        metadata = runner._collect_reproducibility_metadata()

        assert metadata["llm_sampling_seeded"] is None


# ─────────────────────────────────────────────────────────────────────
# Backward compatibility: existing top-level temperature/top_p keys unchanged
# ─────────────────────────────────────────────────────────────────────


class TestBackwardCompatibleTopLevelFields:
    def test_legacy_temperature_top_p_still_present(self, tmp_path):
        """The pre-existing temperature/top_p keys (LLM_CONFIG singleton
        only) must still be present for anything reading them by name."""
        runner = _make_finalize_runner(tmp_path, model="mock")

        metadata = runner._collect_reproducibility_metadata()

        assert "temperature" in metadata
        assert "top_p" in metadata
        assert metadata["temperature"] == llm_utils.LLM_CONFIG.temperature
        assert metadata["top_p"] == llm_utils.LLM_CONFIG.top_p


# ─────────────────────────────────────────────────────────────────────
# Characterization: the exact JSON body _invoke_ollama_direct posts, frozen
# ─────────────────────────────────────────────────────────────────────


class TestOllamaRequestBodyCharacterization:
    """Freezes the exact JSON body ``_invoke_ollama_direct`` posts to Ollama
    for a small (temperature present/absent) x (top_k present/absent) x
    (thinking_mode auto/disabled) grid, as literal dicts computed once by
    hand-running the builder at HEAD. A future edit to
    ``_build_ollama_options`` / ``_invoke_ollama_direct`` that changes what
    actually goes out on the wire must trip this test.

    The expected dicts are NOT re-derived inside the test by calling the same
    builder: doing so would let a regression in the builder silently produce
    a matching "expected" value and pass anyway, defeating the point of a
    characterization test.
    """

    _MODEL = "test-model"  # No "8b"/"14b" substring, so _build_ollama_options'
    # num_ctx branch always takes the 4096 default, keeping the grid's
    # expected dicts independent of that unrelated branch.

    _CASES = [
        # (temperature_present, top_k_present, thinking_mode, expected_data)
        (False, False, "auto", {
            "model": "test-model", "prompt": "PROMPT", "stream": False, "format": None,
            "options": {"num_predict": 2048, "num_ctx": 4096},
        }),
        (False, False, "disabled", {
            "model": "test-model", "prompt": "PROMPT", "stream": False, "format": None,
            "options": {"num_predict": 2048, "num_ctx": 4096},
            "think": False,
        }),
        (False, True, "auto", {
            "model": "test-model", "prompt": "PROMPT", "stream": False, "format": None,
            "options": {"num_predict": 2048, "num_ctx": 4096, "top_k": 40},
        }),
        (False, True, "disabled", {
            "model": "test-model", "prompt": "PROMPT", "stream": False, "format": None,
            "options": {"num_predict": 2048, "num_ctx": 4096, "top_k": 40},
            "think": False,
        }),
        (True, False, "auto", {
            "model": "test-model", "prompt": "PROMPT", "stream": False, "format": None,
            "options": {"num_predict": 2048, "num_ctx": 4096, "temperature": 0.8},
        }),
        (True, False, "disabled", {
            "model": "test-model", "prompt": "PROMPT", "stream": False, "format": None,
            "options": {"num_predict": 2048, "num_ctx": 4096, "temperature": 0.8},
            "think": False,
        }),
        (True, True, "auto", {
            "model": "test-model", "prompt": "PROMPT", "stream": False, "format": None,
            "options": {"num_predict": 2048, "num_ctx": 4096, "temperature": 0.8, "top_k": 40},
        }),
        (True, True, "disabled", {
            "model": "test-model", "prompt": "PROMPT", "stream": False, "format": None,
            "options": {"num_predict": 2048, "num_ctx": 4096, "temperature": 0.8, "top_k": 40},
            "think": False,
        }),
    ]

    @pytest.mark.parametrize(
        "temperature_present,top_k_present,thinking_mode,expected_data",
        _CASES,
        ids=[
            f"temp={a},top_k={b},thinking={c}"
            for a, b, c, _ in _CASES
        ],
    )
    def test_posted_json_body_matches_frozen_expectation(
        self, monkeypatch, temperature_present, top_k_present, thinking_mode, expected_data,
    ):
        fixed = llm_utils.LLMConfig(thinking_mode=thinking_mode)
        monkeypatch.setattr(llm_utils, "LLM_CONFIG", fixed)

        params = {}
        if temperature_present:
            params["temperature"] = 0.8
        if top_k_present:
            params["top_k"] = 40

        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "response": "ok", "prompt_eval_count": 1, "eval_count": 1,
        }

        with patch("requests.post", return_value=fake_response) as post_spy:
            llm_utils._invoke_ollama_direct(self._MODEL, "PROMPT", params, False)

        assert post_spy.called
        posted_json = post_spy.call_args.kwargs["json"]
        assert posted_json == expected_data


# ─────────────────────────────────────────────────────────────────────
# model_digest: no live request for a mock or cloud-provider run, and
# OLLAMA_HOST-aware (not hardcoded localhost) for a real Ollama model.
#
# Bug: the digest query used to POST unconditionally to a hardcoded
# "http://localhost:11434/api/show", even for a mock run -- so every mock
# run and every test that reached finalize sent a live request for model
# "mock" to whatever Ollama daemon happened to be reachable, and a run
# pointed at a non-default OLLAMA_HOST silently queried localhost instead.
# Fixed in broker/core/experiment_runner.py::_collect_reproducibility_metadata
# (section 1) by reusing broker.utils.llm_utils.is_cloud_provider_model and
# the new get_ollama_base_url helper -- the SAME helper
# _invoke_ollama_direct uses for the run's real LLM calls.
# ─────────────────────────────────────────────────────────────────────


class TestModelDigestSkipsMockAndUsesOllamaHost:
    def test_mock_run_finalize_makes_no_http_request(self, tmp_path):
        """A mock run has no Ollama model at all; finalize must not send a
        single HTTP request while collecting the digest field."""
        runner = _make_finalize_runner(tmp_path, model="mock")

        with patch("requests.post") as post_spy, patch("requests.get") as get_spy:
            metadata = runner._collect_reproducibility_metadata()

        assert not post_spy.called
        assert not get_spy.called
        assert metadata["model_digest"] == "not_applicable_mock"

    def test_cloud_provider_run_finalize_makes_no_http_request(self, tmp_path):
        """A cloud-provider model (openai/gemini/anthropic/...) never talks
        to Ollama either; same no-HTTP guarantee as the mock case."""
        runner = _make_finalize_runner(tmp_path, model="gemini:pro")

        with patch("requests.post") as post_spy, patch("requests.get") as get_spy:
            metadata = runner._collect_reproducibility_metadata()

        assert not post_spy.called
        assert not get_spy.called
        assert metadata["model_digest"] == "not_applicable_cloud_provider"

    def test_non_string_model_finalize_records_unavailable_not_mock(self, tmp_path):
        """A model that is not even a string (no identity at all) must
        record "unavailable", never "not_applicable_mock" -- that label is
        reserved for a model this code POSITIVELY identified as mock."""
        runner = _make_finalize_runner(tmp_path, model=None)

        with patch("requests.post") as post_spy, patch("requests.get") as get_spy:
            metadata = runner._collect_reproducibility_metadata()

        assert not post_spy.called
        assert not get_spy.called
        assert metadata["model_digest"] == "unavailable"

    def test_real_model_finalize_uses_ollama_host(self, tmp_path, monkeypatch):
        """A real Ollama model's digest query must build its URL from
        OLLAMA_HOST (the same helper _invoke_ollama_direct uses), never a
        hardcoded localhost."""
        monkeypatch.setenv("OLLAMA_HOST", "http://10.20.30.40:5555")
        runner = _make_finalize_runner(tmp_path, model="gemma3:4b")

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = {"digest": "sha256:deadbeef", "details": {}}

        with patch("requests.post", return_value=fake_response) as post_spy, \
             patch(
                 "broker.utils.llm_utils.capture_ollama_modelfile_defaults",
                 return_value=(None, "stubbed for this test"),
             ):
            metadata = runner._collect_reproducibility_metadata()

        assert post_spy.called
        called_url = post_spy.call_args.args[0]
        assert called_url == "http://10.20.30.40:5555/api/show"
        assert metadata["model_digest"] == "sha256:deadbeef"

    def test_real_model_finalize_falls_back_to_default_host(self, tmp_path, monkeypatch):
        """Unset OLLAMA_HOST must fall back to the documented default
        (http://localhost:11434), not some other silent value."""
        monkeypatch.delenv("OLLAMA_HOST", raising=False)
        runner = _make_finalize_runner(tmp_path, model="gemma3:4b")

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = {"digest": "sha256:cafef00d", "details": {}}

        with patch("requests.post", return_value=fake_response) as post_spy, \
             patch(
                 "broker.utils.llm_utils.capture_ollama_modelfile_defaults",
                 return_value=(None, "stubbed for this test"),
             ):
            metadata = runner._collect_reproducibility_metadata()

        called_url = post_spy.call_args.args[0]
        assert called_url == "http://localhost:11434/api/show"
        assert metadata["model_digest"] == "sha256:cafef00d"


class TestInvokeOllamaDirectUsesOllamaHost:
    """_invoke_ollama_direct (the run's real LLM call path) must build its
    URL the same OLLAMA_HOST-aware way as the digest query above -- the two
    share broker.utils.llm_utils.get_ollama_base_url so they cannot drift
    apart again."""

    def test_invoke_ollama_direct_uses_ollama_host(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_HOST", "http://192.168.1.50:11500")

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = {
            "response": "ok", "prompt_eval_count": 1, "eval_count": 1,
        }

        with patch("requests.post", return_value=fake_response) as post_spy:
            llm_utils._invoke_ollama_direct("test-model", "PROMPT", {}, False)

        called_url = post_spy.call_args.args[0]
        assert called_url == "http://192.168.1.50:11500/api/generate"
