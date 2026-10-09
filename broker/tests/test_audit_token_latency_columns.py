"""The audit row must carry what the provider actually reported.

Every released WAGF audit CSV has ``prompt_tokens`` / ``response_tokens`` /
``num_ctx`` / ``context_utilization`` equal to 0 on every row, even though
``broker/utils/llm_utils.py::_invoke_ollama_direct`` has parsed Ollama's
``prompt_eval_count`` / ``eval_count`` into an ``LLMStats`` since R5-C. The
measurement was taken and then thrown away one frame up, in the retry wrapper
``create_llm_invoke`` returns: its success path built a FRESH ``LLMStats``
carrying only the retry counters, so the guard in the governance retry loop
(``if llm_stats_obj.prompt_tokens > 0``) never fired and the keys never reached
the trace.

These tests pin the whole path end to end — fake HTTP response in, CSV row out
— rather than any one frame of it, because every frame in between looked
correct in isolation while the corpus read zero.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from broker.components.analytics.audit import trace_to_csv_row
from broker.components.governance.registry import SkillRegistry
from broker.core.skill_broker_engine import SkillBrokerEngine
from broker.interfaces.skill_types import (
    SkillDefinition, SkillProposal, ValidationResult,
)
from broker.utils.model_adapter import UnifiedAdapter


REPO_ROOT = Path(__file__).resolve().parents[2]

# What a real Ollama /api/generate reply looks like, trimmed to the fields the
# broker reads. Durations are nanoseconds, which is what Ollama emits.
OLLAMA_REPLY = {
    "model": "gemma3:4b",
    "response": '{"decision": 1}',
    "done": True,
    "prompt_eval_count": 123,
    "eval_count": 45,
    "total_duration": 2_000_000_000,
    "prompt_eval_duration": 500_000_000,
    "eval_duration": 1_000_000_000,
}


class _FakeResponse:
    status_code = 200
    text = ""

    def json(self):
        return dict(OLLAMA_REPLY)


# ---------------------------------------------------------------------------
# 1. One decision, one call: the numbers the server reported reach the row
# ---------------------------------------------------------------------------

VALID_SKILL = "increase_small"


class _Ctx:
    def build(self, agent_id, env_context=None, **kwargs):
        return {"agent_id": agent_id, "state": {}}

    def format_prompt(self, context):
        return "PROMPT"


class _Writer:
    def __init__(self):
        self.traces = []

    def write_trace(self, agent_type, trace, history):
        self.traces.append(trace)


def _engine():
    """A minimal engine whose validator approves, so the decision costs one call."""
    registry = SkillRegistry()
    registry.register(SkillDefinition(
        skill_id=VALID_SKILL, description=VALID_SKILL,
        eligible_agent_types=["*"], preconditions=[],
        institutional_constraints={}, allowed_state_changes=[],
        implementation_mapping=VALID_SKILL,
    ))
    registry.set_default_skill(VALID_SKILL)

    adapter = UnifiedAdapter.__new__(UnifiedAdapter)
    adapter.parse_output = lambda *_a, **_k: SkillProposal(
        skill_name=VALID_SKILL, agent_id="A1", reasoning={}, parse_layer="mock",
    )

    validator = MagicMock()
    validator.validate.side_effect = lambda *_a, **_k: ValidationResult(
        valid=True, validator_name="AgentValidator:ok", errors=[], metadata={})

    config = MagicMock()
    config.get_log_fields.return_value = []
    config.get_governance_retries.return_value = 3
    config.get_governance_max_reports.return_value = 3
    config.get_multi_skill_config.return_value = {}
    config.get_parsing_config.return_value = {}

    engine = SkillBrokerEngine(
        skill_registry=registry, model_adapter=adapter, validators=[validator],
        simulation_engine=None, context_builder=_Ctx(), config=config,
    )
    writer = _Writer()
    engine.audit_writer = writer
    return engine, writer


def _install_fake_ollama(monkeypatch):
    """Satisfy ``create_llm_invoke``'s langchain gate without langchain.

    `langchain-ollama` is an OPTIONAL runtime dependency and the "Tests (no
    LLM)" CI job deliberately does not install it, so a test that reaches
    `create_llm_invoke("gemma3:4b")` for real dies in the fixture with
    `RuntimeError: Cannot construct an LLM for model 'gemma3:4b'`.

    Stubbing it costs nothing in coverage: on the Ollama-direct path the
    constructed `ChatOllama` / `OllamaLLM` object is never touched again —
    `invoke` calls `_invoke_ollama_direct` and nothing else — so the import is
    a GATE, not a collaborator. Everything these tests assert on (parameter
    building, the `invoke` closure, its retry accounting, `_invoke_ollama_direct`,
    `_final_stats`) is the real code.

    Installed unconditionally, not only when the import would fail: a test that
    exercises one code path on CI and a different one on a developer box is how
    a green suite stops meaning anything. Same shape as
    `broker/tests/test_cloud_provider_routing.py::_install_fake_ollama`.
    """
    fake = ModuleType("langchain_ollama")

    class _FakeOllama:
        def __init__(self, model, **params):
            self.model = model
            self.params = params

    fake.ChatOllama = _FakeOllama
    fake.OllamaLLM = _FakeOllama
    monkeypatch.setitem(sys.modules, "langchain_ollama", fake)


@pytest.fixture()
def ollama_invoke(monkeypatch):
    """A real ``create_llm_invoke`` function whose HTTP call is faked."""
    import requests

    from broker.utils import llm_utils

    _install_fake_ollama(monkeypatch)
    capabilities = MagicMock(status_code=200)
    capabilities.json.return_value = {"capabilities": ["completion"]}

    def post(url, **kwargs):
        return capabilities if url.endswith("/api/show") else _FakeResponse()

    monkeypatch.setattr(requests, "post", post)
    # Pin the context window so the recorded num_ctx is predictable.
    monkeypatch.setattr(llm_utils.LLM_CONFIG, "num_ctx", 4096)
    return llm_utils.create_llm_invoke("gemma3:4b")


def test_ollama_token_counts_reach_the_audit_row(ollama_invoke):
    engine, writer = _engine()
    engine.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                        llm_invoke=ollama_invoke, agent_type="farmer")

    assert writer.traces, "the step wrote no audit trace"
    row = trace_to_csv_row(writer.traces[0])

    assert row["prompt_tokens"] == 123
    assert row["response_tokens"] == 45
    assert row["num_ctx"] == 4096
    assert row["context_utilization"] == pytest.approx(123 / 4096, rel=1e-3)


def test_the_row_records_latency_and_call_count(ollama_invoke):
    engine, writer = _engine()
    engine.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                        llm_invoke=ollama_invoke, agent_type="farmer")

    row = trace_to_csv_row(writer.traces[0])

    assert row["llm_latency_ms"] > 0, (
        "a call that reached the fake server took some measurable time; 0 here "
        "means the timing never left _invoke_ollama_direct"
    )
    assert row["llm_calls_total"] == 1
    assert row["prompt_tokens_total"] == 123
    assert row["response_tokens_total"] == 45
    # eval_count=45 over eval_duration=1e9 ns is exactly 45 tokens/second.
    assert row["tokens_per_second"] == pytest.approx(45.0, rel=1e-3)


def test_stats_survive_the_wrapper_without_an_engine(ollama_invoke):
    """The narrowest statement of the defect: one invoke, stats in the tuple."""
    _content, stats = ollama_invoke("PROMPT")

    assert stats.prompt_tokens == 123
    assert stats.response_tokens == 45
    assert stats.num_ctx == 4096
    assert stats.latency_ms > 0
    assert stats.calls == 1


def test_governance_retries_sum_the_totals_and_keep_the_last_attempt(ollama_invoke):
    """Three blocked attempts: per-call columns stay per-call, totals add up."""
    engine, writer = _engine()
    # Reject everything, so the decision exhausts its governance retries.
    engine.validators[0].validate.side_effect = lambda *_a, **_k: ValidationResult(
        valid=False, validator_name="AgentValidator:thinking_error",
        errors=["blocked"], metadata={"rules_hit": ["r1"], "level": "ERROR"})

    engine.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                        llm_invoke=ollama_invoke, agent_type="farmer")
    row = trace_to_csv_row(writer.traces[0])

    calls = row["llm_calls_total"]
    assert calls > 1, "a rejected decision should have retried"
    # Per-call columns describe ONE call, whatever the attempt count.
    assert row["prompt_tokens"] == 123
    assert row["num_ctx"] == 4096
    # Totals describe the decision.
    assert row["prompt_tokens_total"] == 123 * calls
    assert row["response_tokens_total"] == 45 * calls


# ---------------------------------------------------------------------------
# 2. A whole mock run carries the columns on every row
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_mock_run_writes_the_cost_columns_on_every_row(tmp_path):
    """End-to-end through the shipped flood runner with --model mock.

    A mock run has no provider to report tokens, so the token columns stay 0 —
    but `llm_calls_total` counts calls the framework itself made, so it must be
    >= 1 on every row, and every new column must be present in the header.
    """
    out = tmp_path / "flood_mock"
    proc = subprocess.run(
        [sys.executable, "examples/single_agent/run_flood.py",
         "--model", "mock", "--agents", "3", "--years", "2", "--seed", "42",
         "--governance-mode", "strict", "--output", str(out)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=600,
    )
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-4000:]

    csv_path = out / "household_governance_audit.csv"
    assert csv_path.exists(), f"no audit CSV at {csv_path}"
    with csv_path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert rows, "the mock run produced no audit rows"
    for column in ("prompt_tokens", "response_tokens", "num_ctx",
                   "context_utilization", "prompt_tokens_total",
                   "response_tokens_total", "llm_calls_total",
                   "llm_latency_ms", "tokens_per_second"):
        assert column in rows[0], f"{column} missing from the mock audit CSV"

    for i, row in enumerate(rows):
        assert int(row["llm_calls_total"]) >= 1, (
            f"row {i} claims {row['llm_calls_total']} LLM calls; every decision "
            f"row is produced by at least one invoke"
        )
        # The mock provider reports no timing, and must report it identically on
        # every run — the repo's mock byte-identity plane depends on it.
        assert float(row["llm_latency_ms"]) == 0.0
        assert float(row["tokens_per_second"]) == 0.0


# ---------------------------------------------------------------------------
# 2b. The six per-call numbers on a row come from ONE call
# ---------------------------------------------------------------------------

def test_a_failed_last_attempt_does_not_splice_its_latency_onto_earlier_tokens():
    """Regression. `llm_latency_ms` used to be written outside the
    `prompt_tokens > 0` branch, so a decision whose LAST attempt timed out
    published the PREVIOUS attempt's tokens beside the timeout's latency: a
    1200-token prompt, 40 tokens generated, 600 000 ms, 0.0 tok/s. Throughput
    computed per row was then wrong by two orders of magnitude, and the 0.0 —
    which this schema defines as "not measured" — sat next to a real
    `response_tokens`."""
    from broker.utils.llm_utils import LLMStats, accumulate_llm_stats

    total = {}
    good = LLMStats(retries=0, success=True, prompt_tokens=1200,
                    response_tokens=40, num_ctx=4096, context_utilization=0.293,
                    latency_ms=3200.0, tokens_per_second=12.5, calls=1,
                    prompt_tokens_total=1200, response_tokens_total=40)
    timed_out = LLMStats(retries=0, success=False, latency_ms=600000.0, calls=1)
    accumulate_llm_stats(total, good)
    accumulate_llm_stats(total, timed_out)

    assert total["prompt_tokens"] == 1200
    assert total["response_tokens"] == 40
    assert total["llm_latency_ms"] == 3200.0, (
        "latency must come from the same attempt as the tokens beside it"
    )
    assert total["tokens_per_second"] == 12.5
    # The failed attempt is still counted and still costs nothing in tokens.
    assert total["llm_calls_total"] == 2
    assert total["prompt_tokens_total"] == 1200


def test_the_peak_survives_a_narrower_last_attempt():
    """`prompt_tokens_peak` / `num_ctx_peak` exist because the LAST attempt is
    not always the WIDEST — the advisory pass runs before the governance retry
    loop and its prompt appends header + rule text. A fixture whose peak is also
    its last attempt would pass under a plain last-attempt implementation and
    prove nothing, so this one peaks in the middle."""
    from broker.utils.llm_utils import LLMStats, accumulate_llm_stats

    def _s(prompt_tokens, ctx=4096):
        return LLMStats(retries=0, success=True, prompt_tokens=prompt_tokens,
                        response_tokens=10, num_ctx=ctx,
                        context_utilization=prompt_tokens / ctx, calls=1,
                        prompt_tokens_total=prompt_tokens, response_tokens_total=10)

    total = {}
    for tokens in (900, 3900, 1100):
        accumulate_llm_stats(total, _s(tokens))

    assert total["prompt_tokens"] == 1100, "per-call columns follow the last call"
    assert total["prompt_tokens_peak"] == 3900, "the peak must not be overwritten"
    assert total["num_ctx_peak"] == 4096
    assert total["context_utilization_peak"] == pytest.approx(3900 / 4096, rel=1e-3)


def test_peak_prefers_the_wider_prompt_when_utilisation_is_unreported():
    """The cloud path reports `num_ctx=0`, so `context_utilization` is 0.0 on
    every call and a utilisation-only comparison lets the narrowest last attempt
    claim the peak."""
    from broker.utils.llm_utils import LLMStats, accumulate_llm_stats

    total = {}
    for tokens in (5000, 100):
        accumulate_llm_stats(total, LLMStats(
            retries=0, success=True, prompt_tokens=tokens, response_tokens=5,
            calls=1, prompt_tokens_total=tokens, response_tokens_total=5))

    assert total["prompt_tokens_peak"] == 5000


def test_the_context_budget_tripwire_fires_on_a_near_full_prompt(tmp_path, caplog):
    """The `[Audit:ContextBudget]` guard warns when a prompt approaches
    `num_ctx` — above ~100% the server drops the prompt HEAD and the
    instructions die first. It reads `prompt_tokens`, so it was inert for as
    long as that column was 0: no run before 2026-09-15 was ever checked. It has
    never had a test."""
    import logging

    from broker.components.analytics.audit import AuditConfig, GenericAuditWriter

    writer = GenericAuditWriter(
        AuditConfig(output_dir=str(tmp_path), experiment_name="ctx-budget"))
    trace = {
        "step_id": 1, "year": 2035, "agent_id": "A1",
        "approved_skill": {"skill_name": "x", "status": "APPROVED"},
        "llm_stats": {
            "llm_success": True, "prompt_tokens": 4000, "num_ctx": 4096,
            "prompt_tokens_peak": 4000, "num_ctx_peak": 4096,
        },
    }
    with caplog.at_level(logging.WARNING):
        writer.write_trace("household", dict(trace))
    assert any("[Audit:ContextBudget]" in r.message for r in caplog.records), (
        "a prompt at 98% of num_ctx must warn"
    )

    # And the peak is what it watches: a decision whose LAST attempt was small
    # but whose widest attempt nearly filled the window still warns.
    caplog.clear()
    mid_peak = dict(trace)
    mid_peak["step_id"] = 2
    mid_peak["llm_stats"] = {
        "llm_success": True, "prompt_tokens": 200, "num_ctx": 4096,
        "prompt_tokens_peak": 4050, "num_ctx_peak": 4096,
    }
    with caplog.at_level(logging.WARNING):
        writer.write_trace("renter", mid_peak)
    assert any("[Audit:ContextBudget]" in r.message for r in caplog.records), (
        "the tripwire must read the widest attempt, not the last one"
    )


def test_a_comfortable_prompt_does_not_warn(tmp_path, caplog):
    import logging

    from broker.components.analytics.audit import AuditConfig, GenericAuditWriter

    writer = GenericAuditWriter(
        AuditConfig(output_dir=str(tmp_path), experiment_name="ctx-ok"))
    with caplog.at_level(logging.WARNING):
        writer.write_trace("household", {
            "step_id": 1, "year": 2035, "agent_id": "A1",
            "approved_skill": {"skill_name": "x", "status": "APPROVED"},
            "llm_stats": {"llm_success": True, "prompt_tokens": 400,
                          "num_ctx": 4096},
        })
    assert not any("[Audit:ContextBudget]" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# 3. The columns do not leak into a trace that never measured them
# ---------------------------------------------------------------------------

def test_legacy_trace_without_the_keys_derives_no_new_columns():
    """A JSONL trace written before this change replays with its own columns."""
    legacy = {
        "step_id": 1, "year": 2035, "agent_id": "A1",
        "llm_stats": {"llm_retries": 0, "llm_success": True},
        "approved_skill": {"skill_name": "x", "status": "APPROVED"},
    }
    row = trace_to_csv_row(legacy)
    for column in ("prompt_tokens_total", "response_tokens_total",
                   "llm_calls_total", "llm_latency_ms", "tokens_per_second"):
        assert column not in row
    # The four pre-existing columns still default, exactly as before.
    assert row["prompt_tokens"] == 0
    assert row["num_ctx"] == 0


# ---------------------------------------------------------------------------
# 4. The constancy detector works on the branch this machine does not take
# ---------------------------------------------------------------------------

def _all_zero_csv(path: Path, rows: int = 60) -> Path:
    """A corpus of the exact shape the original bug produced."""
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["step_id", "agent_id", "prompt_tokens", "final_skill"])
        for i in range(rows):
            writer.writerow([i, f"A{i}", "0", "elevate"])
    return path


def test_the_csv_detector_flags_an_all_zero_token_column_without_pandas(tmp_path, monkeypatch):
    """`detect_audit_sentinels_in_csv` has two branches and only one of them
    runs on a machine with pandas — which is every machine this repo has been
    developed on. The `csv.DictReader` fallback yields STRINGS while the
    placeholder tables are typed, so `"0" in (0,)` was False and every numeric
    entry in the map was dead there: `mem_surprise`, `social_gossip_count`,
    `cog_surprise_value`, and the whole cost plane.

    That is this commit's own failure shape — a correctness fix living on the
    branch the author's machine cannot reach — so it is pinned by forcing the
    fallback rather than trusting the branch that happens to run here.
    """
    import builtins

    from broker.components.analytics import audit as audit_mod

    real_import = builtins.__import__

    def _no_pandas(name, *args, **kwargs):
        if name == "pandas":
            raise ImportError("forced: exercise the csv.DictReader fallback")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_pandas)

    warnings = audit_mod.detect_audit_sentinels_in_csv(
        str(_all_zero_csv(tmp_path / "all_zero.csv")))

    assert any("prompt_tokens" in w for w in warnings), (
        "an all-zero prompt_tokens column is the corpus this detector exists "
        f"to catch; the no-pandas branch reported {warnings!r}"
    )


def test_the_coercer_leaves_every_placeholder_in_the_map_as_itself():
    """The coercion must not retype a textual placeholder into something that
    stops matching — `""`, `"neutral"`, `"unobserved"`, `"personal"`."""
    from broker.components.analytics.audit import (
        _SUSPICIOUS_COLUMN_DEFAULTS, _coerce_cell,
    )

    for column, placeholders in _SUSPICIOUS_COLUMN_DEFAULTS.items():
        for placeholder in placeholders:
            cell = "" if placeholder == "" else str(placeholder)
            assert _coerce_cell(cell) == placeholder, (
                f"{column}: the CSV cell {cell!r} no longer matches its "
                f"placeholder {placeholder!r}"
            )


def test_the_coercer_leaves_genuine_text_alone():
    from broker.components.analytics.audit import _coerce_cell

    for text in ("N/A", "elevate", "H", "rule_a|rule_b", "unobserved"):
        assert _coerce_cell(text) == text
