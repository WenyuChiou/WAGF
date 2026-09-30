"""Pytester regression test for conftest.py's MUST-1b backstop, running the
REAL root conftest.py (round 4, MUST 2).

An earlier version of this file used a small hand-built stand-in conftest
that only reproduced the general block-list / reorder-last / sessionfinish
PATTERN. Review round 4 correctly pointed out that such a test would keep
passing even if the REAL ``pytest_sessionfinish`` implementation were
deleted -- it never actually exercised the real code. This version instead
copies the real ``conftest.py`` text (self-contained: its only import
besides the standard library and ``pytest`` is a lazy, try/except-guarded
``from broker.utils.llm_utils import get_ollama_base_url`` inside
``_looks_like_an_ollama_url``, so nothing needs to be stripped for it to be
importable in an isolated sandbox with no ``broker`` package on its path)
and the real guard self-test file (``test_zz_ollama_guard_survives_full_suite.py``)
into a disposable pytest run, then adds the ONE extra ingredient needed to
reproduce round 4's MUST-1 bug: a session-scoped autouse fixture whose
finalizer fires during the reordered-to-last zz test's OWN teardown phase
(because session-scoped fixtures tear down at the very end of the run, when
``nextitem`` is ``None`` -- which is exactly zz's last test).

Uses ``runpytest_subprocess`` (a real, separate Python process): this outer
test's own process already has the REAL ollama-guard audit hook installed
(from this very session's conftest.py), and an in-process nested run would
have both hooks observing the same process's events, which is not what
this test is trying to isolate.
"""
from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REAL_CONFTEST_PATH = _REPO_ROOT / "conftest.py"
_REAL_ZZ_SELFTEST_PATH = _REPO_ROOT / "tests" / "test_zz_ollama_guard_survives_full_suite.py"

# A session-scoped autouse fixture whose finalizer records a block via a
# SYNTHETIC sys.audit event (never a real socket/process) strictly AFTER
# every test body in the session -- including the reordered-to-last zz
# file's own tests -- has already run. Appended to the copied real
# conftest.py's text for this one test only; not part of the real file.
_LATE_LEAKING_FIXTURE_SNIPPET = '''

import pytest as _pytest_for_late_leak_fixture
import sys as _sys_for_late_leak_fixture


@_pytest_for_late_leak_fixture.fixture(scope="session", autouse=True)
def _leaks_after_every_test_body_including_zz():
    yield
    # Synthetic event only (round 4 isolation rule): this must never be a
    # real socket.connect() or subprocess.Popen() call.
    try:
        _sys_for_late_leak_fixture.audit("socket.connect", None, ("127.0.0.1", 11434))
    except RuntimeError:
        pass  # the guard raised -- expected; the block is already recorded
'''


def _write_real_guard_plain_into(pytester, extra_conftest_text: str = ""):
    """Copy the REAL conftest.py (plus optional appended text, for a single
    test's own extra fixture) + the REAL zz self-test file into the
    pytester sandbox, at the exact relative paths the real guard's own
    _GUARD_SELFTEST_PATH computation expects (``<sandbox>/conftest.py`` and
    ``<sandbox>/tests/test_zz_ollama_guard_survives_full_suite.py``)."""
    conftest_text = _REAL_CONFTEST_PATH.read_text(encoding="utf-8")
    zz_text = _REAL_ZZ_SELFTEST_PATH.read_text(encoding="utf-8")

    pytester.makeconftest(conftest_text + extra_conftest_text)

    tests_dir = pytester.path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_zz_ollama_guard_survives_full_suite.py").write_text(
        zz_text, encoding="utf-8"
    )


def _write_real_guard_into(pytester):
    """``_write_real_guard_plain_into`` plus the session-fixture late leak
    used by the MUST-1/MUST-2 test below."""
    _write_real_guard_plain_into(pytester, _LATE_LEAKING_FIXTURE_SNIPPET)


def test_session_fixture_teardown_leak_flushed_during_zz_is_not_swallowed(pytester):
    """MUST 1 / MUST 2: the exact round-4 bug. A session-scoped fixture's
    finalizer runs during the LAST item's (zz's own last test's) teardown
    phase. Before the round-4 fix, ``_current_test_expects_guard_block`` was
    still ``True`` for that item's entire teardown (it was reset in
    ``pytest_runtest_teardown``, not scoped to the call phase alone), so
    this late, unrelated block was silently counted as one of zz's OWN
    deliberate trips and never reached ``_unexpected_blocks`` -- the session
    reported success. This test must FAIL on that (round 3) code and PASS
    once the call-phase-only scoping (``pytest_runtest_call`` hookwrapper)
    is in place.
    """
    _write_real_guard_into(pytester)
    pytester.makepyfile(
        test_a_ordinary="""
            def test_a_completely_unrelated_test():
                assert 1 + 1 == 2
        """,
    )

    result = pytester.runpytest_subprocess(
        "-p", "no:cacheprovider", "--timeout=60",
    )

    assert result.ret != 0, (
        "a block recorded by a session-fixture teardown that fires during "
        "the reordered-to-last zz test's OWN teardown must still fail the "
        "session -- it must never be swallowed as one of zz's expected, "
        "deliberate trips"
    )
    result.stdout.fnmatch_lines(["*ollama-guard*unexpected*"])


def test_control_without_the_late_leak_the_real_guard_passes_clean(pytester):
    """Control: the REAL conftest.py plus the REAL zz self-test, with no
    extra leaking fixture, must pass cleanly on its own -- proving the
    failure above comes from the injected late leak, not from some
    unrelated breakage in copying the real files into an isolated sandbox."""
    _write_real_guard_plain_into(pytester)
    pytester.makepyfile(
        test_a_ordinary="""
            def test_a_completely_unrelated_test():
                assert 1 + 1 == 2
        """,
    )

    result = pytester.runpytest_subprocess(
        "-p", "no:cacheprovider", "--timeout=60",
    )

    assert result.ret == 0, "the real guard with no injected leak must pass cleanly"


def test_marker_added_by_trylast_collection_hook_is_not_swallowed(pytester):
    """Round 5, MUST A, probe 1: a ``trylast``-ordered
    ``pytest_collection_modifyitems`` implementation, registered in a
    NESTED conftest.py so it always runs AFTER the real conftest.py's own
    (which has no explicit ordering), adds the exemption marker to an
    ORDINARY, non-zz test AFTER the real conftest's rejection check already
    ran and found nothing to reject. That test then trips a synthetic
    block and swallows the exception itself (mimicking the manifest's own
    ``except Exception`` pattern), so nothing about the test's own body
    would fail it. Before round 5, ``get_closest_marker`` alone found this
    runtime-added marker and exempted the block; the
    ``_is_guard_selftest(item) and ...`` condition must reject it
    regardless of the marker, because this test's file path is not the
    real zz file's.
    """
    _write_real_guard_plain_into(pytester)
    sneaky_dir = pytester.mkpydir("sneaky")
    (sneaky_dir / "conftest.py").write_text(
        "import pytest\n"
        "\n"
        "@pytest.hookimpl(trylast=True)\n"
        "def pytest_collection_modifyitems(session, config, items):\n"
        "    for item in items:\n"
        "        if item.name == 'test_ordinary_that_should_not_be_exempt':\n"
        "            item.add_marker(pytest.mark.expected_ollama_guard_block)\n",
        encoding="utf-8",
    )
    (sneaky_dir / "test_sneaky.py").write_text(
        "import sys\n"
        "\n"
        "def test_ordinary_that_should_not_be_exempt():\n"
        "    try:\n"
        "        sys.audit('socket.connect', None, ('127.0.0.1', 11434))\n"
        "    except RuntimeError:\n"
        "        pass  # swallowed, mimicking real leaky code under test\n",
        encoding="utf-8",
    )

    result = pytester.runpytest_subprocess("-p", "no:cacheprovider", "--timeout=60")

    assert result.ret != 0, (
        "a marker added at runtime by a trylast collection hook must not "
        "exempt the block it enabled -- the session must still fail"
    )


def test_marker_added_by_autouse_fixture_setup_is_not_swallowed(pytester):
    """Round 5, MUST A, probe 2: an autouse fixture calls
    ``request.node.add_marker(...)`` during ITS OWN setup -- long after
    collection (and the real conftest's rejection check there) has already
    finished. Same shape as probe 1 otherwise: the test swallows the
    guard's exception itself, so only the marker decides whether the block
    counts as expected.
    """
    _write_real_guard_plain_into(pytester)
    pytester.makepyfile(
        test_sneaky_fixture="""
            import sys
            import pytest

            @pytest.fixture(autouse=True)
            def _sneaky_marker_adder(request):
                request.node.add_marker(pytest.mark.expected_ollama_guard_block)
                yield

            def test_ordinary_that_should_not_be_exempt():
                try:
                    sys.audit("socket.connect", None, ("127.0.0.1", 11434))
                except RuntimeError:
                    pass  # swallowed, mimicking real leaky code under test
        """,
    )

    result = pytester.runpytest_subprocess("-p", "no:cacheprovider", "--timeout=60")

    assert result.ret != 0, (
        "a marker added at runtime by an autouse fixture's own setup must "
        "not exempt the block it enabled -- the session must still fail"
    )


def test_real_llm_probe_reaches_original_host_not_the_dead_port(pytester, monkeypatch):
    """Round 5, MUST B: with the flag set, a real_llm test's OWN setup-time
    probe must reach whatever OLLAMA_HOST the operator originally set (here,
    a throwaway LOCAL listener standing in for a real daemon -- never the
    real Ollama binary or a real daemon), not the dead port every other
    test in the session sees.

    Uses a real TCP listener, not the real conftest.py's own
    _DEAD_OLLAMA_HOST, as the ONLY way to observe "did the connection
    attempt actually go here" from outside the nested subprocess: the
    listener's own accept() either returns (reached) or times out
    (unreached). The nested test calls the REAL
    ``broker.utils.llm_utils.get_ollama_base_url`` (resolvable inside the
    subprocess because ``pytester.popen`` puts this repo's root, the
    current working directory, on ``PYTHONPATH``) to build the address it
    connects to, exactly like the real smoke module's own probe does.

    Proxy env vars are deliberately CLEARED for this one nested run: `httpx`
    (which the real smoke module's ``OllamaProvider`` uses) honors
    ``HTTP_PROXY``/``HTTPS_PROXY` by default, and with ``NO_PROXY`` empty
    (this repo's own test-running convention) even a loopback destination
    would otherwise be routed through the dead proxy port instead of
    reaching this test's fake listener -- confirmed empirically while
    writing this test. That proxy behavior is unrelated to the conftest
    guard itself (see the module docstring's "GAPS" section: the guard
    never depended on the proxy vars either way).
    """
    import socket
    import threading

    fake_daemon = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    fake_daemon.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    fake_daemon.bind(("127.0.0.1", 0))
    fake_daemon.listen(1)
    fake_port = fake_daemon.getsockname()[1]

    reached = {"hit": False}

    def _accept_one():
        fake_daemon.settimeout(10)
        try:
            conn, _ = fake_daemon.accept()
            reached["hit"] = True
            conn.close()
        except OSError:
            pass

    acceptor = threading.Thread(target=_accept_one, daemon=True)
    acceptor.start()

    monkeypatch.setenv("WAGF_ALLOW_OLLAMA_IN_TESTS", "1")
    monkeypatch.setenv("OLLAMA_HOST", f"http://127.0.0.1:{fake_port}")
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("http_proxy", raising=False)
    monkeypatch.delenv("https_proxy", raising=False)
    # The `pytester` fixture chdir()'s the process into its own sandbox
    # directory, so `pytester.popen()`'s own `PYTHONPATH.insert(os.getcwd())`
    # points at the SANDBOX, not this repo -- and without this repo's root
    # explicitly on PYTHONPATH, `import broker...` inside the nested
    # subprocess falls through to whatever is on the system's default
    # sys.path instead (an editable install of a DIFFERENT checkout, on
    # this host -- confirmed empirically while writing this test). Setting
    # it explicitly makes the nested subprocess resolve `broker` from THIS
    # worktree, matching every other test in this repo.
    monkeypatch.setenv("PYTHONPATH", str(_REPO_ROOT))

    _write_real_guard_plain_into(pytester)
    pytester.makepyfile(
        test_probe="""
            import socket

            import pytest


            @pytest.mark.real_llm
            def test_probe_reaches_the_current_ollama_host():
                from broker.utils.llm_utils import get_ollama_base_url
                from urllib.parse import urlparse

                parsed = urlparse(get_ollama_base_url())
                assert parsed.port != 9, (
                    "the probe must see the ORIGINAL host during a real_llm "
                    "test's setup, not the forced dead port"
                )
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((parsed.hostname, parsed.port))
                s.close()
        """,
    )

    result = pytester.runpytest_subprocess("-p", "no:cacheprovider", "--timeout=30")

    acceptor.join(timeout=15)
    fake_daemon.close()

    # 4 passed: this probe test plus the real zz self-test's own 3 tests,
    # collected alongside it (_write_real_guard_plain_into always includes
    # the real zz file so the real conftest.py's reordering/backstop stay
    # exercised too). result.ret == 0 (implied by assert_outcomes with no
    # failures) already confirms nothing broke; reached["hit"] below is
    # this test's actual point.
    result.assert_outcomes(passed=4)
    assert reached["hit"], (
        "the real_llm test's probe never actually reached the fake daemon "
        "standing in for the original OLLAMA_HOST"
    )
