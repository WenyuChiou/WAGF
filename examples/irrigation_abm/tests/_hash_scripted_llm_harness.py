"""Standalone subprocess harness: run examples/irrigation_abm/run_experiment.py
with a deterministic, hash-of-the-prompt mock LLM instead of the stock mock.

feat/v3-parallel-determinism (2026-09-30): the stock ``--model mock`` invoke
(``broker/utils/llm_utils.py``'s ``create_llm_invoke``) always answers
``{"decision": 1}`` and states no WSA/ACA label, so it never exercises
strict's TR1/TR3 thinking rules, the appraisal freeze, or more than one
format-retry shape. This harness answers each prompt with a response that is
a pure function of that prompt's own text (a sha256 hash), so completion
order can never change what a GIVEN prompt resolves to; only a per-prompt
sleep (0 to 20 ms, also derived from the hash) scrambles which thread
finishes first.

Not a pytest test module itself (its name does not match ``test_*.py``).
Invoked as its own subprocess by ``test_v3_workers_determinism.py``, one
process per run, so no process-global singleton (``GovernanceAuditor``,
``AgentTypeConfig``'s config cache) leaks between the workers=1/4/8
comparisons the way it would if those runs shared one in-process pytest
session.

Usage: python _hash_scripted_llm_harness.py <run_experiment.py CLI args>
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

import broker.utils.llm_utils as llm_utils  # noqa: E402
from broker.utils.llm_utils import LLMStats  # noqa: E402
from examples.irrigation_abm import run_experiment  # noqa: E402

_LABELS = ["VL", "L", "M", "H", "VH"]


class HashScriptedLLM:
    """A pure function of the prompt text: the same prompt in always gives
    the same answer out, regardless of which thread calls it or in what
    order. No shared mutable decision state, so no lock is needed (compare
    ``broker/utils/parsing/unified_adapter.py``'s thread-local parse-warning
    stash, which exists because its own state is per-call mutable)."""

    def __call__(self, prompt: str):
        digest = hashlib.sha256(prompt.encode("utf-8")).digest()
        h = int.from_bytes(digest[:8], "big")
        # 0 to 20 ms jitter, deterministic per prompt: scrambles thread
        # completion order (different agents and attempts sleep different
        # amounts) without relying on real randomness, so a failing run is
        # reproducible rather than flaky.
        time.sleep(((h >> 32) % 21) / 1000.0)
        stats = LLMStats(retries=0, success=True)

        if "You are a Reflection Assistant" in prompt:
            ids = re.findall(r"^(.+?) Memories:", prompt, flags=re.M)
            return (
                json.dumps({aid: "Noted for next year." for aid in ids}),
                stats,
            )

        wsa = _LABELS[h % 5]
        aca = _LABELS[(h // 5) % 5]
        menu = {
            m.group(2): int(m.group(1))
            for m in re.finditer(
                r"^(\d+)\. (Increase|Keep|Decrease) your request",
                prompt, flags=re.M,
            )
        }
        choices = list(menu) or ["Keep"]
        choice = choices[(h // 25) % len(choices)]
        decision = menu.get(choice, menu.get("Keep", 1))
        payload = {
            "reasoning": "Hash-scripted answer.",
            "water_scarcity_assessment": {"label": wsa, "reason": "Scripted."},
            "adaptive_capacity_assessment": {"label": aca, "reason": "Scripted."},
            "decision": decision,
        }
        return (
            "<<<DECISION_START>>>\n" + json.dumps(payload) + "\n<<<DECISION_END>>>",
            stats,
        )


_llm = HashScriptedLLM()
# Same two patch points proven by
# examples/irrigation_abm/tests/test_v3_governance.py's _run_main helper:
# direct module-attribute assignment here (not pytest's monkeypatch
# fixture) because this module runs as its own subprocess, not inside a
# pytest-managed test.
llm_utils.create_llm_invoke = lambda model, verbose=False, overrides=None: _llm
run_experiment.create_llm_invoke = lambda model, verbose=False: _llm


if __name__ == "__main__":
    run_experiment.main()
