"""Twin-run check for Invariant 7: governance leaves no trace.

Runs a ``python -m broker.run`` case twice with the mock model:

* run A, the case as configured: rules block some answers, a retry or the
  default replaces them;
* run B, same config and seed: every agent proposes, each year, exactly the
  action (and its numbers) that ran for it in run A, so nothing is blocked.

It then compares, between the two runs, what the agents and the world could see:

* every memory write (``memory_log.jsonl``: line and metadata);
* every stored reflection (``reflection_log.jsonl``: its input and its lesson);
* per decision, from the raw traces: the first prompt (``input``), memory before
  and after, agent state before and after, the environment and the social fields;
* every action the world received (skill, execution mapping, numbers; the
  approval status is left out, because it differs by construction).

Any difference is a governance trace: the rules changed something an agent or
the world sees later. Zero differences pass. The check needs run A to have at
least one row where a default replaced a blocked answer and one row approved
after a retry (``--require any``: either one); without them it proves nothing
and says so (exit 3). It also
says so when a rule blocks an action in run B, because then run B is not the
"nothing was blocked" twin.

Usage::

    python -m broker.tools.check_governance_carryover <config.yaml> [--years N]
        [--agents N] [--seed S] [--output DIR] [--allow-module NAME]
        [--require both|any] [--json]

Exit codes: 0 pass, 1 differences found, 2 the case could not run, 3 not
enough governance in run A, or rules blocked run B.

Notes:

* Run B's decider is a registered decider (``broker/agents/deciders.py``) that
  replays run A's executed actions; the audit CSV of run B therefore names it in
  its decider columns. The audit CSVs are not compared: they record governance
  on purpose.
* Run B carries, on rows where the agent's own proposal ran in run A, that
  proposal's reasoning; on default rows it carries none.
* Both runs use one worker, so the order of memory writes is the same.
* Only an agent's first action of a period is replayed; a case with a second
  (composite) action fails on the world-input comparison rather than passing.
* A run A without traces or world calls, or whose memory_log.jsonl lists
  fewer lines than the memory gate counted writes, or a run B with a different
  row count, is reported as inconclusive: two empty files would otherwise
  compare equal. A case that writes no memory at all is fine.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import sys
import tempfile
from pathlib import Path

from broker.agents.deciders import DeciderRegistry, DeciderSpec, make_proposal
from broker.run import _entry

REPLAY_DECIDER = "governance_carryover_replay"
TRACE_FIELDS = ("input", "memory_pre", "memory_post", "state_before", "state_after",
                "environment_context", "social_audit")
REFLECTION_FIELDS = ("reflection_input", "summary")


class TwinError(Exception):
    """The case could not run (exit 2)."""


def _read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _audit_rows(output):
    paths = sorted(output.glob("*governance_audit.csv"))
    rows = []
    for path in paths:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def _decisions(output):
    rows = _read_jsonl(output / "raw" / "agent_traces.jsonl")
    if not rows:
        rows = [r for p in sorted((output / "raw").glob("*_traces.jsonl")) for r in _read_jsonl(p)]
    return [r for r in rows if "step_id" in r]


def _executed_by(world_calls, decisions):
    """(agent_id, year) -> (world call, reasoning) of what ran in run A.

    The reasoning is the agent's final proposal's when that proposal is what ran
    (approved, or a kept rejected proposal); a default carries none.
    """
    reasoning = {(r.get("agent_id"), r.get("year")): (r.get("skill_proposal") or {}).get("reasoning") or {}
                 for r in decisions}
    table = {}
    for call in world_calls:
        key = (call["agent_id"], call["year"])
        if key in table:
            continue  # a secondary skill: only the primary one is replayed
        own = call["_approval_status"] != "REJECTED_FALLBACK"
        table[key] = (call, reasoning.get(key, {}) if own else {})
    return table


def _replay_factory(table, missing):
    def factory(agent_type_config, runtime):
        agent_id = runtime.get("agent_id")
        agent_type = runtime.get("agent_type")
        runner = runtime.get("runner")

        def decide(prompt="", **_kwargs):
            year = getattr(runner, "_current_year", None)
            if (agent_id, year) not in table:
                # Raising here would only turn into a retry or an aborted row.
                missing.append(f"{agent_id} period {year}")
                return make_proposal(skill_name="", agent_id=agent_id, agent_type=agent_type,
                                     decider=REPLAY_DECIDER, path="replay_missing")
            call, reasoning = table[(agent_id, year)]
            params = dict(call["parameters"])
            magnitude = params.pop("magnitude_pct", None)
            fallback = bool(params.pop("magnitude_fallback", False))
            proposal, stats = make_proposal(
                skill_name=call["skill_name"], agent_id=agent_id, agent_type=agent_type,
                decider=REPLAY_DECIDER, path="replay", reasoning=reasoning)
            proposal = dataclasses.replace(
                proposal, magnitude_pct=magnitude,
                magnitude_fallback=fallback if magnitude is not None else False,
                parameters=params)
            return proposal, stats

        return decide

    return factory


def _world_parameters(parameters):
    """The action's numbers as compared. A default can carry ``magnitude_pct:
    None`` with ``magnitude_fallback``; with no number, neither is a number the
    world can act on, and no proposal can reproduce the pair, so both drop."""
    params = dict(parameters or {})
    if params.get("magnitude_pct") is None:
        params.pop("magnitude_pct", None)
        params.pop("magnitude_fallback", None)
    return params


def _run(argv, output, table=None):
    """Build and run the case into ``output``; return the world's inputs."""
    try:
        prepared = _entry.prepare(argv + ["--output", str(output)])
    except ValueError as exc:  # SlotError and RunError
        raise TwinError(str(exc)) from exc
    runner = prepared.runner
    engine = runner.broker.simulation_engine
    world_calls = []
    execute = engine.execute_skill

    def recording_execute(approved):
        world_calls.append({
            "agent_id": approved.agent_id, "year": getattr(runner, "_current_year", None),
            "skill_name": approved.skill_name, "execution_mapping": approved.execution_mapping,
            "parameters": _world_parameters(approved.parameters),
            "_approval_status": approved.approval_status,  # not compared: differs by design
        })
        return execute(approved)

    engine.execute_skill = recording_execute
    missing = []
    if table is not None:
        spec = DeciderSpec(REPLAY_DECIDER)
        runner.get_decider_spec = lambda agent_type: spec
        DeciderRegistry.register(REPLAY_DECIDER, _replay_factory(table, missing), replace=True)
    try:
        runner.run()
        if prepared.after_run is not None:
            prepared.after_run(prepared.ctx.output_dir)
    finally:
        if table is not None:
            DeciderRegistry.unregister(REPLAY_DECIDER)
    if missing:
        raise TwinError("run B asked for an action run A never executed: " + ", ".join(missing[:5]))
    gate = getattr(runner.memory_engine, "origin_gate", None)
    writes = sum(gate.counts.values()) if gate is not None else None
    return world_calls, writes


def _diff_lists(name, a, b, label, fields=None):
    found = []
    for index in range(max(len(a), len(b))):
        left = a[index] if index < len(a) else None
        right = b[index] if index < len(b) else None
        if left is None or right is None:
            found.append({"file": name, "where": label(left or right), "field": "(missing)",
                          "a": left is not None, "b": right is not None})
            continue
        keys = fields or sorted(k for k in set(left) | set(right) if not k.startswith("_"))
        for key in keys:
            if left.get(key) != right.get(key):
                found.append({"file": name, "where": label(left), "field": key,
                              "a": left.get(key), "b": right.get(key)})
    return found


def compare(out_a, out_b, calls_a, calls_b):
    """Every difference between the twins as ``{file, where, field, a, b}``."""
    who = lambda e: f"agent {e.get('agent_id')} period {e.get('period', e.get('year'))}"
    found = _diff_lists("memory_log.jsonl", _read_jsonl(out_a / "memory_log.jsonl"),
                        _read_jsonl(out_b / "memory_log.jsonl"), who)
    found += _diff_lists("reflection_log.jsonl", _read_jsonl(out_a / "reflection_log.jsonl"),
                         _read_jsonl(out_b / "reflection_log.jsonl"), who, REFLECTION_FIELDS)
    key = lambda r: (str(r.get("agent_id")), int(r.get("year") or 0))
    found += _diff_lists("raw traces", sorted(_decisions(out_a), key=key),
                         sorted(_decisions(out_b), key=key), who, TRACE_FIELDS)
    found += _diff_lists("world input", calls_a, calls_b,
                         lambda c: f"agent {c.get('agent_id')} period {c.get('year')}")
    return found


def governance_counts(output):
    """Default-applied rows and rows approved after a retry, from the audit CSV."""
    rows = _audit_rows(output)
    truthy = lambda v: str(v).strip().lower() in ("true", "1", "yes")
    defaults = sum(1 for r in rows if r.get("status") in ("REJECTED", "UNCERTAIN")
                   or truthy(r.get("fallback_activated")))
    retried = sum(1 for r in rows if r.get("status") == "APPROVED"
                  and (int(r.get("retry_count") or 0) + int(r.get("format_retries") or 0)) > 0)
    return {"rows": len(rows), "default_rows": defaults, "approved_after_retry_rows": retried}


def check(config, *, years=None, agents=None, seed=None, output=None, allow_modules=(),
          require="both"):
    """Run the twins and return the report dict (see ``main`` for its exit code)."""
    base = Path(output) if output else Path(tempfile.mkdtemp(prefix="governance_carryover_"))
    out_a, out_b = base / "run_a", base / "run_b"
    for path in (out_a, out_b):
        if path.exists() and any(path.iterdir()):
            raise TwinError(f"output folder is not empty: {path}")
    argv = [str(config), "--model", "mock", "--workers", "1"]
    for flag, value in (("--years", years), ("--agents", agents), ("--seed", seed)):
        if value is not None:
            argv += [flag, str(value)]
    for name in allow_modules:
        argv += ["--allow-module", name]
    calls_a, writes_a = _run(argv, out_a)
    counts_a = governance_counts(out_a)
    report = {"config": str(config), "output": str(base), "run_a": counts_a}
    have = (counts_a["default_rows"] > 0, counts_a["approved_after_retry_rows"] > 0)
    if not (all(have) if require == "both" else any(have)):
        report.update(status="inconclusive", reason=(
            "run A needs at least one row where a default replaced a blocked answer "
            + ("and" if require == "both" else "or") + " one row approved after a retry; "
            "script the mock so some first answers break a rule"))
        return report
    calls_b, _ = _run(argv, out_b, _executed_by(calls_a, _decisions(out_a)))
    counts_b = governance_counts(out_b)
    report["run_b"] = counts_b
    if counts_b["default_rows"] or counts_b["approved_after_retry_rows"]:
        report.update(status="inconclusive", reason=(
            "rules blocked an action in run B that ran in run A (for example a default skill "
            "that itself breaks a rule), so run B is not the unblocked twin"))
        return report
    missing = _missing_evidence(out_a, counts_a, calls_a, writes_a)
    if counts_b["rows"] != counts_a["rows"]:
        missing.append(f"run A has {counts_a['rows']} audit rows and run B {counts_b['rows']}")
    if missing:
        # Comparing two empty lists would pass; that proves nothing.
        report.update(status="inconclusive", reason="; ".join(missing))
        return report
    differences = compare(out_a, out_b, calls_a, calls_b)
    report.update(status="pass" if not differences else "fail", differences=differences)
    return report


def _missing_evidence(out_a, counts_a, calls_a, writes_a):
    """What run A should hold for the comparison to mean anything, and does not."""
    missing = []
    decisions = len(_decisions(out_a))
    if decisions != counts_a["rows"]:
        missing.append(f"run A has {counts_a['rows']} audit rows but {decisions} decisions in raw traces")
    if writes_a is None:
        missing.append("run A's memory engine has no origin gate (is this a python -m broker.run case?)")
    elif len(_read_jsonl(out_a / "memory_log.jsonl")) != writes_a:
        # A case that writes no memory (runner_decision_line: false, no hooks
        # writing) logs nothing, and that is fine; a short log is not.
        missing.append(f"run A made {writes_a} memory writes but memory_log.jsonl lists "
                       f"{len(_read_jsonl(out_a / 'memory_log.jsonl'))}")
    if not calls_a:
        missing.append("the world received no action in run A")
    return missing


def _short(value, other=None, limit=160):
    """``value`` as JSON, cut to ``limit``; for two strings, around where they differ."""
    text = json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, str) and isinstance(other, str):
        at = next((i for i, (x, y) in enumerate(zip(value, other)) if x != y), min(len(value), len(other)))
        start = max(0, at - 40)
        text = ("..." if start else "") + json.dumps(value[start:start + limit], ensure_ascii=False)
    return text if len(text) <= limit + 10 else text[:limit] + "..."


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m broker.tools.check_governance_carryover",
        description="Run a broker.run case twice (rules blocking; executed actions proposed "
                    "directly) and compare what agents and the world saw.")
    parser.add_argument("config", help="the case's agent_types.yaml")
    parser.add_argument("--years", type=int)
    parser.add_argument("--agents", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--output", metavar="DIR", help="folder for run_a/ and run_b/ (default: a temp folder)")
    parser.add_argument("--allow-module", action="append", default=[], metavar="DOTTED.NAME")
    parser.add_argument("--require", choices=("both", "any"), default="both",
                        help="what run A must hold to prove anything: a default row and a row "
                             "approved after a retry (both, the default), or either (any)")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    try:
        report = check(args.config, years=args.years, agents=args.agents, seed=args.seed,
                       output=args.output, allow_modules=args.allow_module, require=args.require)
    except TwinError as exc:
        print(f"check_governance_carryover: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        a = report["run_a"]
        print(f"run A: {a['rows']} rows, {a['default_rows']} with a default, "
              f"{a['approved_after_retry_rows']} approved after a retry")
        if report["status"] == "inconclusive":
            print(f"INCONCLUSIVE: {report['reason']}")
        elif report["status"] == "pass":
            print("PASS: memory, reflection, prompts, state and world input are identical")
        else:
            print(f"FAIL: {len(report['differences'])} differences")
            for d in report["differences"][:20]:
                print(f"  {d['file']} | {d['where']} | {d['field']}: "
                      f"A={_short(d['a'], d['b'])} B={_short(d['b'], d['a'])}")
        print(f"outputs: {report['output']}")
    return {"pass": 0, "fail": 1, "inconclusive": 3}[report["status"]]


if __name__ == "__main__":
    sys.exit(main())
