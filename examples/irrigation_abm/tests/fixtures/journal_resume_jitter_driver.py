"""Test-only driver for examples/irrigation_abm/tests/test_workers_resume_integration.py:
crash-resume (fixtures/journal_resume_driver.py) PLUS the hash-of-prompt +
0-20 ms jitter mock (../_hash_scripted_llm_harness.py), combined.

Not part of the production codebase. Run as a SEPARATE SUBPROCESS, same
reason journal_resume_driver.py's own docstring gives: a simulated hard
crash (os._exit) must not take the pytest process down with it.

Why a jitter mock for a crash-resume test at all: journal_resume_driver.py's
own invoke answers purely from a sha256 of the prompt, with no sleep, so at
workers>1 every call still completes in essentially submission order --
never exercising a genuinely different thread-completion order. This
driver's jitter gives workers=4 a real chance to interleave calls
differently from one invocation to the next, which is what this test
actually needs to show: that REPLAY is correct regardless of completion
order (broker/utils/llm_journal.py: answers are matched by
``(agent_type, prompt hash)``, never by arrival order, so a crashed-and-
resumed run must reproduce the source run's output no matter which thread
got to which agent first). This is a DIFFERENT property from the
submission-order SORT itself (``ExperimentRunner._run_agents_parallel``
returning results in submission order regardless of completion order),
which is already covered directly by tests/test_parallel_determinism.py
and is not what this driver's jitter is for.

Reuses both existing fixtures rather than re-implementing either:
  - journal_resume_driver.py supplies the crash hook (``_maybe_crash``,
    reading the captured runner's ``_llm_journal._current_step``) and the
    ``ExperimentBuilder.build`` patch that captures the runner reference.
  - _hash_scripted_llm_harness.py supplies ``HashScriptedLLM`` (as the
    module-level ``_llm`` instance): a pure function of the prompt text
    (sha256) plus a 0-20 ms jitter sleep (also derived from the hash).

Both are imported for their machinery; importing either runs its own
module-level ``create_llm_invoke`` monkeypatch as a side effect, and this
module's own assignment (below, combining the two) runs LAST, so it is the
one that actually wins regardless of import order. Only
journal_resume_driver's ``ExperimentBuilder.build`` patch needs to survive
untouched -- _hash_scripted_llm_harness.py never touches that method.

Env vars: same as journal_resume_driver.py --
  WAGF_TEST_CRASH_AT_STEP: the year (as an int) to crash during; "0" or
      unset means never crash.
  WAGF_TEST_CRASH_AFTER_CALLS_IN_STEP: how many live calls into that year to
      let through before exiting.
(WAGF_TEST_MOCK_MODE does not apply here -- the hash+jitter mock has no
random mode; it is always a pure function of the prompt text.)
"""
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = Path(__file__).resolve().parents[4]
for _p in (_TESTS_DIR, _REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import broker.utils.llm_utils as llm_utils_mod  # noqa: E402

import journal_resume_driver as _jrd  # noqa: E402 -- crash hook + builder patch
import _hash_scripted_llm_harness as _hjh  # noqa: E402 -- HashScriptedLLM (`_llm`)


def _hash_jitter_invoke_with_crash_hook(model, verbose=False, overrides=None):
    """Combines _hash_scripted_llm_harness's hash+jitter answer with
    journal_resume_driver's crash hook, called right before returning --
    the same placement journal_resume_driver.py's own invoke uses, so a
    simulated crash counts a live call toward the threshold only once its
    answer (and jitter sleep) has already happened, never before."""
    def invoke(prompt):
        content, stats = _hjh._llm(prompt)
        _jrd._maybe_crash()
        return content, stats
    return invoke


# Installed AFTER both imports above have run their own module-level
# monkeypatches (journal_resume_driver's plain-hash factory,
# _hash_scripted_llm_harness's jitter-but-no-crash-hook lambda) -- this is
# the one that actually takes effect.
llm_utils_mod.create_llm_invoke = _hash_jitter_invoke_with_crash_hook


if __name__ == "__main__":
    from examples.irrigation_abm.run_experiment import main
    main()
