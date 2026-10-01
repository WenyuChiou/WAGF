"""Ollama-guard self-tests (review round 2 C1/C2, round 3 MUST 1b).

The root conftest.py's `pytest_collection_modifyitems` moves this module's
tests to the very end of the WHOLE run, after every other test in all three
roots (`examples/irrigation_abm/tests`, `tests/`, `broker/`) -- see
`_GUARD_SELFTEST_FILENAME` there, matched against this file's own name. The
same conftest also rejects `@pytest.mark.expected_ollama_guard_block`
anywhere except this file, so this is the only place these two tests below
are even allowed to exist as written.

Pytest runs a module's test functions in the order they are defined, so the
ordering between the two tests below is fixed by that, not by name:

1. `test_a_...`: `_unexpected_blocks` (the cumulative block log MINUS any
   deliberate, expected_ollama_guard_block-marked trip) must still be
   empty -- nothing else in the entire suite reached a live Ollama daemon
   (C2's "the full suite must record ZERO guard blocks"). This is the
   in-line half of that check; `conftest.py`'s `pytest_sessionfinish` is the
   other half, since it can see a block recorded by a fixture teardown that
   runs even AFTER this test's own body finishes (a module- or
   session-scoped finalizer), which this test cannot.
2. `test_b_...` / `test_c_...`: deliberately trip each of the guard's two
   event types and assert it still raises -- proving the audit hook
   installed in `pytest_configure` is still active after the full suite ran
   (C1's "self-tests that run after other tests and prove the guard is
   still active"). Both are marked `expected_ollama_guard_block` so the
   root conftest's auto-fail-on-block fixture does not ALSO fail them for
   the very block they are deliberately causing, and so their block does
   not count against test_a's (or `pytest_sessionfinish`'s) zero-blocks
   check.

ROUND 3: both trips fire a SYNTHETIC `sys.audit(...)` event directly,
instead of round 2's real `socket.connect()` / `subprocess.Popen(["ollama",
...])` calls. `sys.audit` only invokes registered hooks with whatever
arguments are given -- it never itself opens a socket or starts a process --
so even a REGRESSION that made the guard stop blocking for real could never
turn this file into the thing that actually reaches a live daemon or
launches the real `ollama` binary. That guarantee does not depend on the
guard working at all, which is the point of testing it this way.
"""
from __future__ import annotations

import sys

import pytest


def test_a_zero_guard_blocks_recorded_during_the_suite(request):
    """C2 / MUST 1b: once the daemon-reaching tests are fixed, the full
    suite must record ZERO unexpected ollama-guard blocks. Checked BEFORE
    this file's own deliberate trips below add to the (expected) log."""
    unexpected = request.config._wagf_ollama_guard_unexpected_blocks
    assert unexpected == [], (
        f"ollama-guard recorded {len(unexpected)} unexpected block(s) "
        f"somewhere in the suite (expected zero): {unexpected}"
    )


@pytest.mark.expected_ollama_guard_block
def test_b_guard_still_blocks_socket_connect_to_ollama_port(request):
    """C1: prove the socket.connect side of the guard is still installed
    and active after the entire suite has run. Synthetic event (round 3):
    no real socket is created or connected."""
    before = len(request.config._wagf_ollama_guard_all_blocks)

    with pytest.raises(RuntimeError, match="Blocked a connection"):
        sys.audit("socket.connect", None, ("127.0.0.1", 11434))

    after = len(request.config._wagf_ollama_guard_all_blocks)
    assert after == before + 1, "the deliberate trip above was not recorded"


@pytest.mark.expected_ollama_guard_block
def test_c_guard_still_blocks_subprocess_popen_of_ollama(request):
    """C1: prove the subprocess.Popen side of the guard is still installed
    and active after the entire suite has run. Synthetic event (round 3):
    no real process is created, and the argv named here (a bare "ollama")
    is never actually looked up on PATH -- `sys.audit` just calls the
    registered hooks with these arguments, nothing more."""
    before = len(request.config._wagf_ollama_guard_all_blocks)

    with pytest.raises(RuntimeError, match="Blocked launching an ollama process"):
        sys.audit("subprocess.Popen", "ollama", ["ollama", "--version"], None, None)

    after = len(request.config._wagf_ollama_guard_all_blocks)
    assert after == before + 1, "the deliberate trip above was not recorded"
