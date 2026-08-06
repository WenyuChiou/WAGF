"""Parse-reliability probe for a candidate model — TAE task 1 (framework feasibility).

Replays a REAL rendered irrigation prompt (taken verbatim from a completed run's
raw/irrigation_farmer_traces.jsonl `input` field) N times through the SAME two code
paths a live run uses:

    broker.utils.llm_utils.create_llm_invoke(model)      -> generation
    broker.utils.parsing.UnifiedAdapter.parse_output()   -> structured parse

and counts how often the parse yields (a) a skill and (b) the two construct labels
the paper's conditioning variable is built from.

This is NOT an experiment. It measures one thing only: whether a candidate model's
raw output is parseable by the frozen parser at a rate comparable to the anchor.
It does not vary the prompt, so it says nothing about behaviour, effect size, or
appraisal distribution.

Usage (from repo root):
    python SUBMISSION_2026/TAE/runs/probe_parse_reliability.py <model> <n>
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

TRACE = REPO / "SUBMISSION_2026/TAE/runs/smoke_gemma4_12b_a4y2/raw/irrigation_farmer_traces.jsonl"
CONFIG = REPO / "SUBMISSION_2026/TAE/runs/config_irrigation_modelsmoke/agent_types.yaml"


def load_prompt() -> str:
    for line in TRACE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("agent_id") and rec.get("input"):
            return rec["input"]
    raise SystemExit(f"no prompt found in {TRACE}")


def main() -> None:
    model = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20

    from broker.utils.llm_utils import create_llm_invoke
    from broker.utils.performance_tuner import get_optimal_config, apply_to_llm_config
    from broker.utils.parsing import UnifiedAdapter

    # Same tuner call the runner makes (run_experiment.py:670-671).
    apply_to_llm_config(get_optimal_config(model))
    from broker.utils.llm_utils import LLM_CONFIG
    print(f"model={model}  num_ctx={LLM_CONFIG.num_ctx}  num_predict={LLM_CONFIG.num_predict}")

    invoke = create_llm_invoke(model)
    adapter = UnifiedAdapter(agent_type="irrigation_farmer", config_path=str(CONFIG))
    prompt = load_prompt()
    print(f"prompt chars={len(prompt)}")

    ok_skill = ok_labels = 0
    lens = []
    failures = []
    t0 = time.time()
    for i in range(n):
        raw, _stats = invoke(prompt)
        lens.append(len(raw or ""))
        prop = adapter.parse_output(raw, {"agent_id": "Agent_000", "agent_type": "irrigation_farmer"})
        skill = getattr(prop, "skill_name", None) if prop else None
        reasoning = getattr(prop, "reasoning", {}) if prop else {}
        labels = {k: v for k, v in (reasoning or {}).items() if k.upper().endswith("_LABEL")}
        if skill:
            ok_skill += 1
        if len(labels) >= 2:
            ok_labels += 1
        else:
            failures.append((i, len(raw or ""), repr(raw or "")[:200]))
        print(f"  [{i:3d}] len={len(raw or ''):5d} skill={skill} labels={labels}")

    el = time.time() - t0
    print(f"\n{model}: n={n}  skill_parsed={ok_skill}/{n}  two_labels={ok_labels}/{n}")
    print(f"  raw len min/median/max = {min(lens)}/{sorted(lens)[len(lens)//2]}/{max(lens)}")
    print(f"  wall={el:.1f}s  mean={el / n:.1f}s per generation")
    if failures:
        print("  FAILURES:")
        for i, ln, head in failures:
            print(f"   [{i}] len={ln} {head}")


if __name__ == "__main__":
    main()
