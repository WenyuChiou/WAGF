"""Runnable Archetype-C (subprocess service model) coupling worked example.

PR-9 coupling-retrofit finding F2: ``docs/COUPLING_CONNECTORS.md`` described
archetype C ("service model: REST / subprocess") but shipped zero code and
zero worked example. This script is the worked example for the SUBPROCESS
half of that pattern (``broker.coupling.SubprocessModelConnector``); REST
stays documented-but-deferred (see COUPLING_CONNECTORS.md).

A single governed LLM agent reads a sensor reading produced by
``external_model.py`` (a real subprocess, called once per period over
JSON-on-stdin / JSON-on-stdout) and decides whether to log it as normal or
flag it as an anomaly. The reading itself has NOTHING to do with whether
``--model mock`` or a real LLM is used — the subprocess call always happens,
proving the connector's protocol end to end without a GPU.

Usage:
  python examples/coupling_examples/archetype_c_subprocess/run_archetype_c.py --model mock --years 4
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from broker.agents import AgentConfig, BaseAgent  # noqa: E402
from broker.agents.base import Skill  # noqa: E402
from broker.components.memory.engine import WindowMemoryEngine  # noqa: E402
from broker.coupling import (  # noqa: E402
    CouplingContract,
    CouplingViolation,
    InterfaceBundle,
    SubprocessModelConnector,
    VarSpec,
)
from broker.core.experiment import ExperimentBuilder  # noqa: E402
from broker.utils.llm_utils import LLMStats  # noqa: E402

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "config"
EXTERNAL_MODEL = HERE / "external_model.py"

# The AGENT's alert threshold, in sensor_unit: above this the scripted mock
# picks flag_anomaly. Read by _operator_mock below (review P2: it was declared
# and never used, with the mock string-matching "reading: 47.0" instead — a
# constant that documents an intent nothing enforces is worse than none).
ANOMALY_THRESHOLD = 40.0  # matches contract.md's alert threshold

# The CONNECTOR's event threshold — a different number for a different job,
# and the source of a real misdiagnosis (review P2). SubprocessModelConnector
# emits an Event only when the reading is STRICTLY ABOVE this, so with the
# default 0.0 a legal reading of exactly 0.0 (inside the contract's declared
# [0, 100]) produced NO event, and the bundle's `if events:` then left
# `reading` unset — a valid measurement reading as "the model said nothing".
# A read-only observation source must never filter: -1.0 sits below the
# contract's lo=0.0, so every in-contract reading emits, and an EMPTY event
# list now means what it should — the source genuinely produced nothing.
EMIT_EVERY_READING = -1.0

OPTIONS_TEXT = (
    "1. log_normal — record the reading as within normal range\n"
    "2. flag_anomaly — flag the reading as anomalous"
)


class ArchetypeCBundle(InterfaceBundle):
    """Projects the subprocess reply's ``reading`` into the flat env dict
    the prompt renders from. The default ``InterfaceBundle.run_pipeline``
    only surfaces event IDs/counts; a read-only archetype-C domain needs
    the payload itself."""

    def run_pipeline(self, base_env, events, operation_order, control_hold_policy="constant"):
        env: Dict[str, Any] = dict(base_env)
        env["_events"] = [e.event_id for e in events]
        env["_event_count"] = len(events)
        if not events:
            # Fail loud rather than leaving `reading` unset. With
            # EMIT_EVERY_READING the source emits for every in-contract value,
            # so an empty list here means the subprocess produced no reading
            # at all — and a prompt rendered with a blank `{reading}` is the
            # silent-default failure this whole layer exists to refuse.
            raise CouplingViolation(
                "ArchetypeCBundle: the subprocess source produced no event for "
                "this period, so there is no reading to put in the prompt "
                "(with event_threshold below the contract's lo, every valid "
                "reading emits — an empty list means no reading was produced)."
            )
        latest = events[-1].payload
        env["reading"] = latest["reading"]
        env["period_echo"] = latest["period_echo"]
        return env


def _build_contract() -> CouplingContract:
    return CouplingContract(
        observations=(
            VarSpec("reading", float, "sensor_unit", lo=0.0, hi=100.0),
            VarSpec("period_echo", int, "flag", lo=1, hi=10_000, consumer_of_record=False),
        ),
        decision_cadence="annual",
        solver_cadence="annual",
    )


def _decision_payload(decision: str, **fields: Any):
    payload = dict(fields)
    payload["decision"] = decision
    payload.setdefault("reasoning", f"scripted mock chose {decision}")
    return (
        f"<<<DECISION_START>>>\n{json.dumps(payload)}\n<<<DECISION_END>>>",
        LLMStats(),
    )


_READING_IN_PROMPT = re.compile(r"reading:\s*(-?\d+(?:\.\d+)?)")


def _operator_mock(prompt: str):
    """Scripted stand-in for the LLM: read the number the prompt actually
    carries and compare it to ANOMALY_THRESHOLD.

    (Review P2: this used to match the literal string ``"reading: 47.0"``, so
    it agreed with ANOMALY_THRESHOLD only by coincidence and would have gone
    on answering "normal" if external_model.py's spike moved to 62.0.)
    """
    match = _READING_IN_PROMPT.search(prompt)
    if match is None:
        raise CouplingViolation(
            "archetype-C scripted mock: the prompt carries no 'reading:' value, "
            "so the coupled observation never reached it — refusing to answer "
            "as though it had."
        )
    reading = float(match.group(1))
    if reading > ANOMALY_THRESHOLD:
        return _decision_payload(
            "flag_anomaly",
            reasoning=f"reading {reading} exceeds the alert threshold {ANOMALY_THRESHOLD}",
        )
    return _decision_payload(
        "log_normal",
        reasoning=f"reading {reading} is within the normal range (<= {ANOMALY_THRESHOLD})",
    )


def _install_scripted_mock(runner) -> None:
    runner._llm_cache["sensor_operator"] = _operator_mock


def _make_agent() -> BaseAgent:
    cfg = AgentConfig(
        name="SENSOR_OP",
        agent_type="sensor_operator",
        state_params=[],
        objectives=[],
        constraints=[],
        skills=[
            Skill("log_normal", "Log the reading as normal", None, "none"),
            Skill("flag_anomaly", "Flag the reading as anomalous", None, "none"),
        ],
    )
    return BaseAgent(cfg)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Archetype-C (subprocess) coupling worked example")
    ap.add_argument("--model", default="mock", help="LLM model or 'mock'")
    ap.add_argument("--years", type=int, default=4)
    ap.add_argument("--output", default=str(HERE / "results"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv)

    contract = _build_contract()
    connector = SubprocessModelConnector(
        [sys.executable, str(EXTERNAL_MODEL)],
        contract=contract,
        value_var="reading",
        event_threshold=EMIT_EVERY_READING,
        timeout_sec=10.0,
    )
    bundle = ArchetypeCBundle(event_src=connector)
    agents = {"SENSOR_OP": _make_agent()}

    def on_pre_year(year, env, all_agents):
        for agent in all_agents.values():
            agent.dynamic_state["reading"] = env.get("reading")
            agent.dynamic_state["options_text"] = OPTIONS_TEXT
        print(f"\n--- Period {year} --- reading={env.get('reading')} sensor_unit")

    def on_post_step(agent, result):
        appr = getattr(result, "approved_skill", None)
        skill_name = appr.skill_name if appr else "?"
        status = appr.approval_status if appr else getattr(result, "outcome", "N/A")
        print(f"  {agent.name}: {skill_name} ({status})")

    runner = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.years)
        .with_agents(agents)
        .with_coupling(contract, bundle, domain="archetype_c_subprocess")
        .with_governance("strict", str(CONFIG / "agent_types.yaml"))
        .with_skill_registry(str(CONFIG / "skill_registry.yaml"))
        .with_memory_engine(WindowMemoryEngine(window_size=3))
        .with_lifecycle_hooks(pre_year=on_pre_year, post_step=on_post_step)
        .with_exact_output(args.output)
        .with_workers(1)
        .with_seed(args.seed)
    ).build()

    if args.model.lower().startswith("mock"):
        _install_scripted_mock(runner)

    print(f"Archetype-C subprocess coupling run | model={args.model} years={args.years}")
    print("=" * 72)
    runner.run()

    # Surface the connector's per-call audit trail (exit code / wall time /
    # stderr tail) so the smoke test can be verified without opening raw
    # traces — the same "make the status visible" discipline
    # failure_mode_playbook.md asks every adapter to follow.
    prov = bundle.event_src.get_provenance()
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "coupling_audit_summary.json").write_text(
        json.dumps(prov, indent=2), encoding="utf-8"
    )
    print(f"\nDone. Audit + traces under: {args.output}")
    print(f"Last subprocess call: {prov.get('last_call_audit')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
