"""``WAGF_LLM_TIMEOUT`` raises a floor under the configured LLM timeout.

``LLMConfig.timeout`` (120 s) and ``timeout_large_model`` (600 s) come from
``agent_types.yaml``, which is hashed into ``config_hash`` in the
reproducibility manifest — so raising a timeout for one slow host by editing
that file makes every later run look like a config change. The env var lets
the host be given headroom without touching the file.

The rule is ``max(configured, env)``: the variable can only ever RAISE the
timeout, so setting it cannot silently shorten a run that the YAML says needs
600 s. A missing, unparseable or non-positive value is ignored.

These tests FAIL against the pre-change code, where ``get_timeout`` read the
dataclass fields and nothing else.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from broker.utils import llm_utils  # noqa: E402
from broker.utils.llm_utils import LLMConfig  # noqa: E402

SMALL_MODEL = "gemma3:4b"
LARGE_MODEL = "llama3.3:70b"

# Spelled out rather than imported from llm_utils, so that against code
# lacking the feature these tests fail on the BEHAVIOUR (120 where 600 was
# asked for) instead of erroring on a missing attribute. The constant itself
# is pinned by test_env_var_name_is_the_documented_one below.
ENV_VAR = "WAGF_LLM_TIMEOUT"


@pytest.fixture
def config() -> LLMConfig:
    """A config pinned to the documented defaults, so the test does not depend
    on whatever ``agent_types.yaml`` happens to say in the working tree."""
    return LLMConfig(timeout=120, timeout_large_model=600)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Every test starts with the variable unset and the warn-once memo clear,
    so one test's bad value cannot mute another's warning."""
    monkeypatch.delenv(ENV_VAR, raising=False)
    getattr(llm_utils, "_WARNED_BAD_TIMEOUT_VALUES", set()).clear()
    yield
    getattr(llm_utils, "_WARNED_BAD_TIMEOUT_VALUES", set()).clear()


def test_unset_returns_configured_timeout(config):
    assert config.get_timeout(SMALL_MODEL) == 120
    assert config.get_timeout(LARGE_MODEL) == 600


def test_env_raises_the_timeout(config, monkeypatch):
    monkeypatch.setenv(ENV_VAR, "600")
    assert config.get_timeout(SMALL_MODEL) == 600


def test_env_below_configured_is_ignored(config, monkeypatch):
    """max(), not override — a lower value must not shorten the timeout."""
    monkeypatch.setenv(ENV_VAR, "30")
    assert config.get_timeout(SMALL_MODEL) == 120
    assert config.get_timeout(LARGE_MODEL) == 600


def test_env_raises_large_model_too(config, monkeypatch):
    monkeypatch.setenv(ENV_VAR, "900")
    assert config.get_timeout(SMALL_MODEL) == 900
    assert config.get_timeout(LARGE_MODEL) == 900


@pytest.mark.parametrize(
    "bad",
    [
        "", "   ", "abc", "12s", "600,0", "None", "-1", "0", "-0.5", "nan", "inf",
        # Too large: a socket timeout above ~2_147_483 s raises a bare
        # OverflowError inside requests.post, before connecting, which the
        # catch-all turns into a failed call for EVERY call in the run.
        # 6000000 is the plausible extra-zeros typo on 600.
        "6000000", "1e12", "2147484", "86401",
    ],
)
def test_garbage_is_ignored_not_read_as_zero(config, monkeypatch, bad):
    """A typo must never become a 0-second timeout — that would turn every
    request into an instant failure and read as a model fault, not a shell
    one."""
    monkeypatch.setenv(ENV_VAR, bad)
    assert config.get_timeout(SMALL_MODEL) == 120
    assert config.get_timeout(LARGE_MODEL) == 600


def test_bad_value_is_logged_once_not_per_call(config, monkeypatch, caplog):
    """The env is read per call, so an unusable value must not emit one
    warning line per LLM invocation."""
    monkeypatch.setenv(ENV_VAR, "not-a-number")
    with caplog.at_level("WARNING", logger=llm_utils.__name__):
        for _ in range(5):
            config.get_timeout(SMALL_MODEL)
    warnings = [r for r in caplog.records if ENV_VAR in r.getMessage()]
    assert len(warnings) == 1, f"expected exactly one warning, got {len(warnings)}"
    assert "IGNORING" in warnings[0].getMessage()


def test_fractional_value_rounds_up(config, monkeypatch):
    """Rounding down would hand back less time than was asked for."""
    monkeypatch.setenv(ENV_VAR, "600.5")
    value = config.get_timeout(SMALL_MODEL)
    assert value == 601
    assert isinstance(value, int)


def test_env_is_read_per_call_not_cached_at_import(config, monkeypatch):
    """A value exported after import must take effect — this is why the read
    lives in get_timeout rather than in _load_global_config."""
    assert config.get_timeout(SMALL_MODEL) == 120
    monkeypatch.setenv(ENV_VAR, "300")
    assert config.get_timeout(SMALL_MODEL) == 300
    monkeypatch.delenv(ENV_VAR)
    assert config.get_timeout(SMALL_MODEL) == 120


def test_module_level_llm_config_honours_the_floor(monkeypatch):
    """The shared LLM_CONFIG instance — the one _invoke_ollama_direct uses —
    picks the floor up too, without being rebuilt."""
    before = llm_utils.LLM_CONFIG.get_timeout(SMALL_MODEL)
    monkeypatch.setenv(ENV_VAR, str(before + 500))
    assert llm_utils.LLM_CONFIG.get_timeout(SMALL_MODEL) == before + 500


def test_llm_config_construction_is_unchanged_by_the_env(monkeypatch):
    """The floor must not leak into the dataclass fields: `config_hash` and
    the manifest's other LLM_CONFIG fields still describe agent_types.yaml,
    not the shell."""
    baseline = llm_utils._load_global_config()
    monkeypatch.setenv(ENV_VAR, "999")
    fresh = llm_utils._load_global_config()
    # Compared against a no-env load rather than hardcoded 120/600, because
    # `_load_global_config` resolves `Path.cwd() / "agent_types.yaml"` and so
    # depends on where pytest was started. The claim under test is "the env
    # changes nothing here", which this states exactly.
    assert (fresh.timeout, fresh.timeout_large_model) == (
        baseline.timeout, baseline.timeout_large_model
    )
    assert fresh.timeout != 999
    assert fresh.timeout_large_model != 999


def test_env_var_name_is_the_documented_one():
    """The literal above and the module constant must not drift apart."""
    assert llm_utils.LLM_TIMEOUT_ENV_VAR == ENV_VAR


def test_the_ollama_call_uses_the_floored_timeout(config, monkeypatch):
    """End of the chain: `_invoke_ollama_direct` passes `get_timeout`'s result
    to `requests.post`. Without this, the floor could be correct and still
    never reach the socket."""
    import requests

    monkeypatch.setattr(llm_utils, "LLM_CONFIG", config)
    monkeypatch.setenv(ENV_VAR, "777")
    seen = {}

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"response": "ok", "prompt_eval_count": 1, "eval_count": 1}

    def fake_post(url, json=None, timeout=None):
        if url.endswith("/api/show"):
            class _Capabilities:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"capabilities": ["completion"]}

            return _Capabilities()
        seen["timeout"] = timeout
        return _Resp()

    # `_invoke_ollama_direct` imports requests inside the function, so the
    # patch has to land on the requests module itself, not on a name in
    # llm_utils.
    monkeypatch.setattr(requests, "post", fake_post)
    content, stats = llm_utils._invoke_ollama_direct(
        SMALL_MODEL, "prompt", {}, verbose=False
    )
    assert stats.success and content == "ok"
    assert seen["timeout"] == 777, (
        "get_timeout's floored value never reached requests.post"
    )


@pytest.mark.parametrize(
    "env_value, expected, expect_rejected",
    [
        (None, 120, False),          # nothing set
        ("777", 777, False),         # set and applied
        ("30", 120, False),          # set, read, below the configured floor
        ("6000000", 120, True),      # set and REJECTED (too large)
        ("abc", 120, True),          # set and REJECTED (unparseable)
    ],
)
def test_manifest_records_the_effective_timeout(
    monkeypatch, tmp_path, config, env_value, expected, expect_rejected
):
    """`_collect_reproducibility_metadata` must write the value the run
    ACTUALLY used, so a run given extra headroom is distinguishable from one
    that hit the default.

    Asserted on the returned metadata, not on the method's source text: a
    source-text check for "get_timeout" is satisfied by the explanatory
    comment above the line, so swapping the call for `LLM_CONFIG.timeout`
    would not fail it. It also cannot see the surrounding
    `except Exception: pass` swallowing the new key, which this can.
    """
    import requests
    from types import SimpleNamespace

    from broker.core.experiment_runner import ExperimentRunner

    monkeypatch.setattr(llm_utils, "LLM_CONFIG", config)
    if env_value is None:
        monkeypatch.delenv(ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(ENV_VAR, env_value)

    # Skip the /api/show model-digest probe — it is a live Ollama call.
    def _no_ollama(*a, **kw):
        raise requests.exceptions.ConnectionError("no ollama in tests")

    monkeypatch.setattr(requests, "post", _no_ollama)

    # Every block in _collect_reproducibility_metadata has its own try/except,
    # so a runner carrying only `.config` reaches the LLM-config block.
    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.config = SimpleNamespace(
        model=SMALL_MODEL,
        output_dir=tmp_path,
        seed=42,
        governance_profile="strict",
    )

    metadata = runner._collect_reproducibility_metadata()
    assert metadata["llm_timeout_seconds_effective"] == expected
    assert metadata["llm_timeout_env_raw"] == env_value
    assert metadata["llm_timeout_env_rejected"] is expect_rejected


def test_manifest_distinguishes_unset_from_rejected():
    """The pair of fields exists precisely to separate these two cases, which
    `llm_timeout_seconds_effective` alone renders identical."""
    import os

    from broker.utils.llm_utils import timeout_env_status

    os.environ.pop(ENV_VAR, None)
    assert timeout_env_status() == (None, False)

    os.environ[ENV_VAR] = "6000000"
    llm_utils._WARNED_BAD_TIMEOUT_VALUES.clear()
    try:
        raw, rejected = timeout_env_status()
        assert raw == "6000000" and rejected is True
    finally:
        os.environ.pop(ENV_VAR, None)
