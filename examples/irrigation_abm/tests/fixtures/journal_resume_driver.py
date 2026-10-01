"""Test-only driver for the crash-resume journal integration tests
(examples/irrigation_abm/tests/test_llm_journal_resume.py).

Not part of the production codebase. Run as a SEPARATE SUBPROCESS (never
imported directly) so a simulated hard crash (``os._exit``) cannot take
the pytest process down with it, and so the test can run a DIFFERENT
``PYTHONHASHSEED`` per invocation.

What it does: monkeypatches ``broker.utils.llm_utils.create_llm_invoke``
(the factory ``ExperimentRunner.get_llm_invoke`` imports locally, so
patching the module attribute before that import executes redirects it)
to a small test invoke, then runs the real CLI entry point
(``examples.irrigation_abm.run_experiment.main``) with ``sys.argv``
exactly as passed on the command line.

The test invoke:
  - Recognises a batch-reflection prompt (broker/components/cognitive/
    reflection.py's ``generate_batch_reflection_prompt``: a
    "### Task Data to Process" section followed by one
    "<agent_id> Memories: ..." line per agent in the batch) and answers it
    with a JSON object mapping every agent_id in the batch to a short,
    letters-only token unique to that agent -- distinct from the decision
    reply shape, so a real test run exercises and journals BOTH call
    kinds, and the token lets a test verify the SAME per-agent text
    reached reflection_log.jsonl on both sides of a crash+resume.
  - Otherwise picks the decision either deterministically (sha256 of the
    prompt) or from an ``os.urandom``-seeded RNG, per
    ``WAGF_TEST_MOCK_MODE``.
  - About a third of the time (deterministic mode, decision prompts only)
    answers with a water_scarcity_assessment of H while picking an
    "increase" option, or L while picking a "decrease" option -- this
    trips the irrigation v3 strict profile's TR1 / TR3 thinking rules, so
    a real test run exercises governance retries (and the appraisal
    freeze) rather than the stock mock's single-option, no-retry path.
  - Optionally simulates a hard crash: once the run reaches a configured
    step (year) and a configured number of calls have been made within
    that step, it calls ``os._exit`` -- a true process kill, not a Python
    exception, so no cleanup/finally code runs, the same way a power loss
    or a Windows Update reboot would end the process. Reflection calls
    count toward this the same as decision calls.

Env vars:
  WAGF_TEST_MOCK_MODE: "hash" (default) or "random".
  WAGF_TEST_CRASH_AT_STEP: the year (as an int) to crash during; "0" or
      unset means never crash.
  WAGF_TEST_CRASH_AFTER_CALLS_IN_STEP: how many calls into that year to
      let through before exiting.
"""
import hashlib
import json
import os
import random as _random_mod
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import broker.core.experiment_builder as experiment_builder_mod  # noqa: E402
import broker.utils.llm_utils as llm_utils_mod  # noqa: E402
from broker.utils.llm_utils import LLMStats  # noqa: E402

_MOCK_MODE = os.environ.get("WAGF_TEST_MOCK_MODE", "hash")
_CRASH_AT_STEP = int(os.environ.get("WAGF_TEST_CRASH_AT_STEP", "0") or "0")
_CRASH_AFTER_CALLS = int(os.environ.get("WAGF_TEST_CRASH_AFTER_CALLS_IN_STEP", "0") or "0")

_runner_holder = {}
_crash_state = {"step": None, "count": 0}
_random_instance = _random_mod.Random(int.from_bytes(os.urandom(8), "big"))

_OPTION_RE = re.compile(r"(\d+)\.\s+([^\n]+)")

# Matches broker/components/cognitive/reflection.py
# (ReflectionEngine.generate_batch_reflection_prompt)'s "### Task Data to
# Process" section header followed by its first "<agent_id> Memories: "
# line -- used only to DETECT that a prompt is a batch-reflection prompt
# (one match is enough for that); every agent_id in the batch is then
# pulled separately via _REFLECTION_AGENT_LINE_RE, since one batch can
# (and typically does) carry more than one agent line.
_REFLECTION_MARKER_RE = re.compile(r"### Task Data to Process\n(.+?) Memories: ", re.DOTALL)
_REFLECTION_AGENT_LINE_RE = re.compile(r"^(\S+) Memories: ", re.MULTILINE)

_LETTERS = "abcdefghijklmnop"


def _letters_token(seed_material: str, length: int = 8) -> str:
    """A short, letters-only, deterministic token derived from
    ``seed_material`` (hash mode) -- distinguishable per agent/prompt so a
    test can verify the SAME text reached reflection_log.jsonl on both
    sides of a crash+resume, without any digit or punctuation that might
    confuse a naive "does this look like a decision reply" check.
    """
    digest = hashlib.sha256(seed_material.encode("utf-8")).hexdigest()
    return "".join(_LETTERS[int(c, 16) % len(_LETTERS)] for c in digest[:length])


def _random_letters_token(length: int = 8) -> str:
    return "".join(_random_instance.choice(_LETTERS) for _ in range(length))


def _reflection_reply(prompt: str) -> str:
    agent_ids = _REFLECTION_AGENT_LINE_RE.findall(prompt)
    reply = {}
    for agent_id in agent_ids:
        token = (
            _random_letters_token()
            if _MOCK_MODE == "random"
            else _letters_token(prompt + agent_id)
        )
        reply[agent_id] = f"I realized the test reflection token is {token}"
    return json.dumps(reply)


def _deterministic_mock_factory(model, verbose=False, overrides=None):
    def invoke(prompt):
        if _REFLECTION_MARKER_RE.search(prompt):
            content = _reflection_reply(prompt)
            _maybe_crash()
            return content, LLMStats(retries=0, success=True)

        options = _OPTION_RE.findall(prompt)
        if _MOCK_MODE == "random":
            bucket_source = _random_instance.random()
            idx = _random_instance.randrange(len(options)) if options else 0
            bucket = int(bucket_source * 3)
        else:
            digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            h = int(digest, 16)
            idx = (h % len(options)) if options else 0
            bucket = h % 3

        decision_id = int(options[idx][0]) if options else 1
        wsa, aca = "M", "M"
        if options:
            if bucket == 0:
                wsa = "H"
                target = next((oid for oid, text in options if "ncrease" in text), None)
                if target is not None:
                    decision_id = int(target)
            elif bucket == 1:
                wsa = "L"
                target = next((oid for oid, text in options if "ecrease" in text), None)
                if target is not None:
                    decision_id = int(target)

        content = json.dumps({
            "reasoning": "deterministic test reasoning for replay coverage",
            "water_scarcity_assessment": wsa,
            "adaptive_capacity_assessment": aca,
            "decision": decision_id,
        })

        _maybe_crash()
        return content, LLMStats(retries=0, success=True)

    return invoke


def _maybe_crash() -> None:
    """Simulated hard crash hook, shared by both the decision and the
    reflection reply paths in ``invoke`` above, each of which calls this
    right before returning its own content -- a reflection call counts
    toward the crash threshold exactly like a decision call does.
    """
    if not _CRASH_AT_STEP:
        return
    runner = _runner_holder.get("runner")
    journal = getattr(runner, "_llm_journal", None) if runner is not None else None
    current_step = getattr(journal, "_current_step", None) if journal is not None else None
    if current_step != _CRASH_AT_STEP:
        return
    if _crash_state["step"] != current_step:
        _crash_state["step"] = current_step
        _crash_state["count"] = 0
    _crash_state["count"] += 1
    if _crash_state["count"] >= _CRASH_AFTER_CALLS:
        sys.stderr.write(
            f"WAGF_TEST_CRASH: simulated hard crash at step "
            f"{current_step}, call {_crash_state['count']}\n"
        )
        sys.stderr.flush()
        os._exit(70)


llm_utils_mod.create_llm_invoke = _deterministic_mock_factory

_orig_build = experiment_builder_mod.ExperimentBuilder.build


def _patched_build(self):
    runner = _orig_build(self)
    _runner_holder["runner"] = runner
    return runner


experiment_builder_mod.ExperimentBuilder.build = _patched_build


if __name__ == "__main__":
    from examples.irrigation_abm.run_experiment import main
    main()
