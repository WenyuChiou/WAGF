"""Scripted mock LLM driver for the flood WRR26-rerun smoke test.

The repo's generic ``--model mock`` (broker/utils/llm_utils.py,
``model.lower().startswith("mock")``) returns bare ``{"decision": N}`` with
no PMT labels at all -- by design, it proves the PIPELINE runs without ever
exercising governance (every thinking rule reads "" for a missing label and
never fires). That is fine for most smoke tests, but this task also needs a
retry to actually happen under mock (to render "one full retry message, full
and silent" and to show the rebuilt R1/R3/R4 rules actually fire), so this
driver monkeypatches ``broker.utils.llm_utils.create_llm_invoke`` with a
SCRIPTED function: deterministic per (agent, year) via a hash of the stable
prompt text, no network, no Ollama, no randomness beyond the run's own
draws, all derived from ``--seed`` (same as every other run; the flood
draws use per-(seed, year, household, purpose) streams, see
``run_flood._flood_random_stream``).

Not a pytest test file itself (no ``test_`` prefix, so it is not collected);
it is imported by ``test_prompt_rendering.py`` for the leading-blank-line
guard (P3-a) and is runnable standalone for ad hoc smoke runs:

    python examples/single_agent/tests/scripted_mock_driver.py \\
        --governance-mode strict --retry-feedback-mode full \\
        --agents 100 --years 10 --seed 42 --output <dir>

Never contacts Ollama: the only "LLM call" this process makes is the
in-process Python function below.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import broker.utils.llm_utils as llm_utils  # noqa: E402
from broker.utils.llm_utils import LLMStats  # noqa: E402

# IMPORTANT: ExperimentRunner.run(llm_invoke=...) IGNORES the callable passed
# in (broker/core/experiment_runner.py ~L724-734: "run(llm_invoke=...) is
# IGNORED"). The real per-decision invoke is built by
# ExperimentRunner.get_llm_invoke(agent_type), which does a LOCAL
# `from broker.utils.llm_utils import create_llm_invoke, ...` INSIDE the
# method body on every call -- so patching the MODULE-LEVEL
# broker.utils.llm_utils.create_llm_invoke (the raw, tuple-returning
# constructor; distinct from run_flood's own `create_llm_invoke` alias for
# `create_legacy_invoke`) is what actually reaches the simulation. Patching
# run_flood.create_llm_invoke is a dead end: nothing calls it.

# Keyed by a hash of rendered prompt TEXT, not literally by (agent_id,
# year) -- see _core's docstring (P3-13, opus review round 3) for why, and
# for the one assumption this relies on.
_ATTEMPTS: dict = {}


def _core(prompt: str) -> str:
    """The stable per-decision key this driver actually uses: everything
    from the persona sentence onward, which survives both the
    governance-retry wrapper (full mode re-sends the whole original prompt
    after its header) and silent mode (which re-sends the original prompt
    byte-for-byte).

    NOT literally keyed by (agent_id, year) (P3-13, opus review round 3):
    the rendered prompt text itself never shows either -- flood's template
    has no agent-id or year placeholder -- and the ONLY interface this
    function is called through is ``broker.utils.llm_utils.create_llm_invoke``'s
    contract, a single ``prompt: str`` argument with no agent/year context
    attached. Keying by the hash of this tail instead relies on one
    assumption: that two DIFFERENT (agent, year) decisions never render the
    exact same memory + trust + elevation-status text. In a 100-agent,
    10-year run this is true in practice (memory content alone almost
    always differs), but it is an assumption about the fixture's input
    distribution, not a guarantee the code enforces -- a real collision
    would silently merge two decisions' attempt counters. Acceptable for a
    SCRIPTED-mock smoke/regression driver (never a source of published
    numbers); would need re-deriving if this driver were ever used to
    produce anything load-bearing."""
    idx = prompt.find("You are a homeowner")
    return prompt[idx:] if idx >= 0 else prompt


def _menu_ids(prompt: str):
    """Numeric option ids actually offered this prompt, parsed from the
    rendered options_text (works for both the 4-option and 3-option,
    already-elevated menus)."""
    lines_section = prompt.split("Now, choose one of the following actions:", 1)
    tail = lines_section[1] if len(lines_section) > 1 else prompt
    tail = tail.split("Note:", 1)[0]
    return [int(m) for m in re.findall(r"^\s*(\d+)\.\s", tail, re.M)]


def _bucket(core: str, n: int) -> int:
    h = int(hashlib.sha256(core.encode("utf-8")).hexdigest(), 16)
    return h % n


def _payload(tp: str, cp: str, decision_id: int) -> str:
    body = json.dumps({
        "reasoning": "Scripted mock reasoning for the flood WRR26-rerun smoke test.",
        "threat_appraisal": {"label": tp, "reason": "Scripted threat reason for the smoke test."},
        "coping_appraisal": {"label": cp, "reason": "Scripted coping reason for the smoke test."},
        "decision": str(decision_id),
    }, indent=2)
    return f"<<<DECISION_START>>>\n{body}\n<<<DECISION_END>>>"


def reset_state() -> None:
    """Clear the per-decision attempt counter; call between independent
    test runs in the same process so one test's agents don't leak attempt
    counts into the next."""
    _ATTEMPTS.clear()


REFLECTION_LESSON = ("I learned that protecting my home before a flood matters more "
                     "than reacting after one.")


def _reflection_reply(prompt: str) -> str:
    """A scripted year-end reflection (flood design record item 7): a JSON
    object keyed by the household id, deterministic per (household, year).
    One bucket in four names a year in its first answer and is clean on the
    retry; bucket 2 makes a claim its own listed years contradict (the house
    was never damaged when a listed year had damage, or a flood comes every
    year when a listed year had none). That reply is stored with a report-only
    flag. The rest answer a clean lesson, so a smoke run shows the outcomes
    and flags the framework counts."""
    agent_id = re.search(r"^(.+?) Memories:", prompt, flags=re.M).group(1)
    year = re.search(r"\(Year (\d+)\)", prompt).group(1)
    retry = "### Correction" in prompt
    bucket = _bucket(f"{agent_id}|{year}", 4)
    listed = prompt.split("### Record", 1)[0]
    if bucket == 1 and not retry:
        lesson = f"In Year {year} I learned to watch the river closely."
    elif bucket == 2 and ("damage on my house" in listed or "severe enough to cause damage" in listed):
        lesson = "I learned that my house has never been damaged, so waiting is safe."
    elif bucket == 2:
        lesson = "I learned that a flood comes every year, so I must always be ready."
    else:
        lesson = REFLECTION_LESSON
    return json.dumps({agent_id: lesson})


def scripted_mock_invoke(prompt: str):
    """Tuple-returning invoke callable, matching what
    ``broker.utils.llm_utils.create_llm_invoke`` returns for every model:
    ``(content: str, stats: LLMStats)``."""
    if "You are a Reflection Assistant" in prompt:
        return _reflection_reply(prompt), LLMStats(retries=0, success=True)
    core = _core(prompt)
    key = hashlib.sha256(core.encode("utf-8")).hexdigest()
    attempt = _ATTEMPTS.get(key, 0)
    _ATTEMPTS[key] = attempt + 1

    elevated = "already elevated" in prompt
    ids = _menu_ids(prompt)
    if elevated:
        id_insurance, id_relocate, id_donothing = ids[0], ids[1], ids[2]
        id_elevate = None
    else:
        id_insurance, id_elevate, id_relocate, id_donothing = ids[0], ids[1], ids[2], ids[3]

    bucket = _bucket(core, 5)
    if bucket == 0 and not elevated:
        scenario = "viol_R1"       # threat H, coping M, do_nothing -- new R1
    elif bucket == 1 and not elevated:
        scenario = "viol_R4"       # threat L, coping M, elevate_house -- R4
    elif bucket == 2:
        scenario = "viol_R3"       # threat L, coping M, relocate -- R3
    elif bucket == 3 and not elevated and id_elevate is not None:
        scenario = "flood_elevate"  # threat H, coping H, elevate_house -- compliant
    else:
        scenario = "compliant_donothing"

    if scenario == "viol_R1":
        if attempt == 0:
            content = _payload("H", "M", id_donothing)
        else:
            content = _payload("H", "M", id_insurance)  # fix: any action but do_nothing
    elif scenario == "viol_R4":
        if attempt == 0:
            content = _payload("L", "M", id_elevate)
        else:
            content = _payload("L", "M", id_insurance)  # fix: any action but elevate_house
    elif scenario == "viol_R3":
        if attempt == 0:
            content = _payload("L", "M", id_relocate)
        else:
            content = _payload("L", "M", id_insurance)  # fix: any action but relocate
    elif scenario == "flood_elevate":
        content = _payload("H", "H", id_elevate)
    else:
        content = _payload("M", "M", id_donothing)

    return content, LLMStats(retries=0, success=True)


def _patched_create_llm_invoke(model: str, verbose: bool = False, overrides=None):
    if str(model).lower().startswith("mock"):
        return scripted_mock_invoke
    raise RuntimeError(
        "scripted_mock_driver only patches the mock path; "
        f"got model={model!r} -- refusing to fall through to a real LLM call."
    )


def patch_mock_llm():
    """Install the scripted mock as the module-level
    ``broker.utils.llm_utils.create_llm_invoke`` (see the module docstring
    for why that name, not ``run_flood``'s own alias). Call this before
    ``run_flood.run_parity_benchmark(model="mock", ...)``. Returns the
    PREVIOUS value, so a caller can put it back (see
    :func:`restore_mock_llm`); prefer :func:`run_scripted_mock`, which does
    this for you in a ``finally`` block."""
    previous = llm_utils.create_llm_invoke
    llm_utils.create_llm_invoke = _patched_create_llm_invoke
    return previous


def restore_mock_llm(previous) -> None:
    """Undo :func:`patch_mock_llm`. MUST be called (in a ``finally``, or a
    pytest fixture teardown) -- the module-level patch otherwise survives
    for the rest of the Python PROCESS and silently replaces every later
    call to ``broker.utils.llm_utils.create_llm_invoke`` for any OTHER
    model too, including a REAL one (opus review round 3, P2-1): confirmed
    by running this driver's own test ahead of
    ``broker/tests/test_audit_token_latency_columns.py`` and
    ``broker/tests/test_cloud_provider_routing.py`` in one pytest session
    before this fix existed -- both broke, because the cloud-provider /
    latency-column logic those tests exercise lives in the REAL
    ``create_llm_invoke``, which this driver had left permanently replaced.
    :func:`run_scripted_mock` always calls this for you; only call it
    yourself if you call :func:`patch_mock_llm` directly."""
    llm_utils.create_llm_invoke = previous


def run_scripted_mock(*, governance_mode: str, output: str, agents: int = 100,
                       years: int = 10, seed: int = 42, memory_seed: int = 42,
                       retry_feedback_mode: Optional[str] = None,
                       config_root: Optional[str] = None) -> None:
    """Patch the mock LLM, run one flood simulation through it, and ALWAYS
    restore the original ``create_llm_invoke`` afterward (even if the run
    itself raises) -- see :func:`restore_mock_llm` for why this matters.
    Importable directly from a test (see test_prompt_rendering.py); never
    contacts Ollama regardless of what ``--model`` the rest of the repo
    defaults to, because this always passes ``model="mock"``."""
    previous = patch_mock_llm()
    try:
        import examples.single_agent.run_flood as run_flood  # local import: patch first

        run_flood.run_parity_benchmark(
            model="mock",
            years=years,
            agents_count=agents,
            custom_output=output,
            verbose=False,
            memory_engine_type="window",
            workers=1,
            window_size=5,
            seed=seed,
            memory_seed=memory_seed,
            flood_mode="fixed",
            survey_mode=False,
            governance_mode=governance_mode,
            use_priority_schema=False,
            stress_test=None,
            memory_ranking_mode="legacy",
            initial_agents_path=None,
            shuffle_skills=False,
            default_skill=None,
            config_root=config_root,
            retry_feedback_mode=retry_feedback_mode,
        )
    finally:
        restore_mock_llm(previous)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--governance-mode", default="strict")
    parser.add_argument("--retry-feedback-mode", default=None)
    parser.add_argument("--agents", type=int, default=100)
    parser.add_argument("--years", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--memory-seed", type=int, default=42)
    parser.add_argument("--output", required=True)
    parser.add_argument("--config-root", default=None)
    args = parser.parse_args()

    run_scripted_mock(
        governance_mode=args.governance_mode,
        output=args.output,
        agents=args.agents,
        years=args.years,
        seed=args.seed,
        memory_seed=args.memory_seed,
        retry_feedback_mode=args.retry_feedback_mode,
        config_root=args.config_root,
    )


if __name__ == "__main__":
    main()
