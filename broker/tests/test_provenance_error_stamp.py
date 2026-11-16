"""A provenance hook that RAISES must be visible in the manifest (2026-11 review).

_collect_reproducibility_metadata wraps three provenance sources in
try/except and used to log failures at debug level only:

- 5.4 governance resolution: a failure part-way through left the later keys
  absent, which reads like an older runner rather than a broken one;
- 5.5 coupled-world provenance: an engine whose get_provenance() raised gave a
  manifest (and run_integrity.json) identical to an UNCOUPLED run;
- 7 crash-resume journal provenance: a resumed run whose journal provenance
  failed looked like a normal, never-resumed run.

Each now records `<source>_error` ("ExcType: message") and logs a warning, the
pattern 5.6 (coupling retrofit metadata) already used. Runs that never hit a
failure keep exactly their old key set.
"""
from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock

from broker.agents import AgentConfig, BaseAgent
from broker.core.experiment_runner import ExperimentConfig, ExperimentRunner


def _agent(agent_id: str = "a1") -> BaseAgent:
    return BaseAgent(AgentConfig(name=agent_id, agent_type="household", state_params=[],
                                 objectives=[], constraints=[], skills=[]))


def _broker(agent_config=None):
    broker = MagicMock()
    broker.log_prompt = False
    broker.model_adapter = MagicMock()
    broker.model_adapter.agent_config = agent_config
    broker._retry_feedback_mode = "full"   # JSON-safe (see test_llm_journal_runner_seam)
    return broker


class _Engine:
    """Plain class (a MagicMock would auto-vivify get_provenance)."""

    def advance_year(self):
        return {}


class _CoupledEngine(_Engine):
    def __init__(self, prov=None, exc=None):
        self._prov, self._exc = prov, exc

    def get_provenance(self):
        if self._exc is not None:
            raise self._exc
        return self._prov


def _metadata(tmp_path, sim_engine, agent_config=None, journal=None):
    runner = ExperimentRunner(broker=_broker(agent_config), sim_engine=sim_engine,
                              agents={"a1": _agent()},
                              config=ExperimentConfig(model="mock", num_years=1, output_dir=tmp_path))
    if journal is not None:
        runner._llm_journal = journal
    meta = runner._collect_reproducibility_metadata()
    json.dumps(meta, default=str)   # the error stamps must stay serialisable
    return meta


def _run_integrity_extra(tmp_path) -> dict:
    path = tmp_path / "run_integrity.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


# --- 5.5 coupled-world provenance -------------------------------------------

def test_raising_get_provenance_is_recorded_not_read_as_uncoupled(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="broker"):
        meta = _metadata(tmp_path, _CoupledEngine(exc=RuntimeError("model handle gone")))
    assert meta.get("coupling_provenance_error") == "RuntimeError: model handle gone"
    assert "coupling_provenance" not in meta
    assert "coupling provenance unavailable" in caplog.text
    assert "coupling_provenance_error" in json.dumps(_run_integrity_extra(tmp_path))


def test_working_get_provenance_unchanged(tmp_path):
    meta = _metadata(tmp_path, _CoupledEngine(prov={"model": "m", "contract": "c1"}))
    assert meta["coupling_provenance"] == {"model": "m", "contract": "c1"}
    assert "coupling_provenance_error" not in meta


def test_engine_without_hook_keeps_old_key_set(tmp_path):
    meta = _metadata(tmp_path, _Engine())
    assert not {"coupling_provenance", "coupling_provenance_error",
                "governance_resolution_error", "llm_journal_provenance_error"} & set(meta)


# --- 5.4 governance resolution ----------------------------------------------

def test_governance_resolution_failure_is_recorded(tmp_path, caplog):
    agent_cfg = MagicMock()
    agent_cfg.get.return_value = {"rules": 1}
    agent_cfg.get_thinking_rules.side_effect = KeyError("household")
    with caplog.at_level(logging.WARNING, logger="broker"):
        meta = _metadata(tmp_path, _Engine(), agent_config=agent_cfg)
    assert meta.get("governance_resolution_error") == "KeyError: 'household'"
    assert "governance_profile_resolved" in meta          # keys set before the failure stay
    assert "governance-resolution provenance incomplete" in caplog.text


# --- 7 crash-resume journal provenance --------------------------------------

def test_journal_provenance_failure_is_recorded(tmp_path, caplog):
    journal = MagicMock()
    journal.provenance_metadata.side_effect = OSError("source journal unreadable")
    with caplog.at_level(logging.WARNING, logger="broker"):
        meta = _metadata(tmp_path, _Engine(), journal=journal)
    assert meta.get("llm_journal_provenance_error") == "OSError: source journal unreadable"
    assert "llm_journal provenance unavailable" in caplog.text


def test_journal_without_resume_adds_no_key(tmp_path):
    journal = MagicMock()
    journal.provenance_metadata.return_value = None
    meta = _metadata(tmp_path, _Engine(), journal=journal)
    assert "llm_journal_provenance_error" not in meta
