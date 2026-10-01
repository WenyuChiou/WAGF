"""Repository-wide pytest configuration.

This file sits at the common ancestor of every root this project's test
suite runs together (``examples/irrigation_abm/tests``, ``tests/``,
``broker/``), so it applies to all three -- unlike ``tests/conftest.py``,
which only covers ``tests/``.

GUARD, layer 1 (review round 3, MUST 1a): force ``OLLAMA_HOST`` itself.

``pytest_configure`` points ``OLLAMA_HOST`` at a dead loopback port
(``http://127.0.0.1:9``) for the WHOLE session, REGARDLESS of
``WAGF_ALLOW_OLLAMA_IN_TESTS`` (round 4, should-fix 4: round 3 left the
ORIGINAL value in place for the entire session once the flag was set, which
meant every OTHER, non-real_llm test also saw a real endpoint for as long
as the flag was set). ``pytest_unconfigure`` restores whatever value (or
absence) ``OLLAMA_HOST`` had before the session, and when the flag IS set,
the ``pytest_runtest_setup``/``pytest_runtest_teardown`` hookwrappers below
temporarily switch back to that original value for the duration of one
``real_llm`` test's own setup+call+teardown, then force the dead port right
back for whatever runs next. The Ollama CLI itself reads this variable to
find its daemon, and a CHILD process inherits its parent's environment by
default, so this one assignment closes every wrapper the layer-2 argv0
check below cannot see: ``shell=True``, ``cmd /c``, ``powershell -c``,
``os.system``, ``os.popen``, ``asyncio.create_subprocess_shell``, a
``.bat``/``.cmd`` script, ``wsl``/``bash -c``, or a child Python process
that builds its own Ollama call from scratch. It also covers a daemon
listening on a NON-default port, which the port-11434-specific checks below
do not.

KNOWN, ACCEPTED EDGE CASE (round 5): the restore/re-force above is scoped
to ONE item's own setup+call+teardown, keyed off THAT item's ``real_llm``
marker -- it has no concept of a MODULE- or SESSION-scoped fixture a
``real_llm`` test requested. If such a fixture's finalizer is deferred
(pytest defers a higher-scoped fixture's teardown until the last test that
needed it, or until the session ends) and that deferral lands during some
LATER, UNMARKED test's setup+call+teardown window, OLLAMA_HOST is back to
the dead port by then, so the finalizer's own Ollama access fails or trips
the layer-2 guard -- attributed to whatever unrelated test happened to be
running when the deferred teardown fired. This is FAIL-SAFE (a loud
failure/guard block, never a silent pass) and is a KNOWN trade-off, not a
bug: fixing it would mean tracking "is a real_llm fixture still alive"
independently of "is the CURRENT item real_llm", which no code here does
today. A module- or session-scoped fixture used by a ``real_llm`` test
should expect this and keep its OWN Ollama access inside the test items
themselves, not its teardown, if it needs to outlive a single item.

GUARD, layer 2 (review round 2, C1): ``sys.addaudithook``, kept as a second,
independent layer -- catches a direct call that ignores ``OLLAMA_HOST``
entirely (a hardcoded ``localhost:11434``, still present in
``providers/ollama.py``'s own default parameter outside this repo's
in-scope files) and gives each block a name and a location to record.

Round 1 tried layer 2 with a plain monkeypatch of ``socket.socket.connect``,
restored in a fixture's teardown. That does not survive: ``pytest-socket``
0.8.0 is installed and auto-loads as a pytest plugin (no explicit enabling
needed for its HOOKS to run, only for its own blocking feature), and its
``pytest_runtest_teardown`` hook calls ``_remove_restrictions()``
UNCONDITIONALLY after every single test item, which resets
``socket.socket.connect`` back to the value ``pytest_socket`` itself cached
at import time -- wiping out any other plugin's patch after the first test.
Confirmed directly against this environment's installed ``pytest_socket``
source before writing this fix.

The replacement is a ``sys.addaudithook`` installed in ``pytest_configure``.
Audit hooks, once added, cannot be removed by any code (there is no
``sys.removeaudithook``) -- no plugin, teardown hook, or accident can undo
this one for the life of the PROCESS, which is also why the hook checks a
``_session_active`` flag (set in ``pytest_configure``, cleared in
``pytest_unconfigure``) before doing anything: a second, later
``pytest.main()`` call in the same interpreter re-runs ``pytest_configure``
and turns the flag back on, but between sessions -- or if something other
than pytest keeps running in this interpreter afterward -- the hook must be
inert, not a stale leftover from a session that already ended. It watches
two audit events:

- ``"socket.connect"``: raised inside ``socket.socket.connect()`` /
  ``connect_ex()``, which is the single choke point ``requests``, ``httpx``,
  and ``urllib3`` all end up calling for a synchronous TCP connection.
- ``"subprocess.Popen"``: raised before the child process actually
  executes, with ``(executable, args, cwd, env)``. Blocks when either the
  resolved ``executable`` or the first argv token names an ``ollama``
  binary (``ollama`` / ``ollama.exe``). PLATFORM QUIRK, confirmed
  empirically on this host: on POSIX ``args`` is the list/tuple the caller
  passed and ``args[0]`` is the executable name directly; on WINDOWS,
  CPython's ``Popen._execute_child`` joins that list into the single
  command-line STRING it hands to ``CreateProcess`` before raising the
  event, so ``["ollama", "show", ...]`` shows up here as the string
  ``"ollama show ..."`` -- naively indexing ``[0]`` on that would check the
  single character ``"o"``, not ``"ollama"``, and silently let a real
  launch through. See ``_popen_argv0`` / ``_first_token_of_cmdline`` below.
  This layer does NOT cover a shell wrapper or a renamed binary -- that is
  layer 1's job, not this one's; do not read this check as "anything else
  that shells out to the CLI".

GAPS that remain even with both layers (documented, not silently assumed
away): CPython's Windows ``ProactorEventLoop`` (asyncio's default event
loop on Windows) can establish outgoing connections through IOCP without
ever calling the plain blocking ``socket.connect()``, so an asyncio-based
HTTP client running under the proactor loop may bypass the socket event
(nothing in this codebase's Ollama access is async today --
``OllamaProvider.ainvoke`` exists but is unused by any collected test).
Relying on ``HTTP_PROXY``/``HTTPS_PROXY`` for protection is NOT a third
layer here: most HTTP clients bypass the configured proxy for a loopback
destination by default, so a hardcoded ``localhost:11434`` would ignore the
proxy entirely and go straight to layer 2's socket check instead -- the
proxy env vars this repo's test-running instructions set are a caller-side
convention, not something this guard depends on. A call made through
``ctypes`` directly against the platform socket API bypasses Python's
``socket`` module (and therefore its audit event) completely. A renamed
``ollama`` binary defeats layer 2's name check, though layer 1 (forcing
``OLLAMA_HOST``) still redirects it if the renamed binary is still the real
Ollama CLI reading that variable. A CHILD PROCESS with ``localhost:11434``
hardcoded in ITS OWN source, ignoring whatever ``OLLAMA_HOST`` it inherited,
defeats BOTH layers at once: layer 1 only helps a caller that actually reads
the variable, and ``sys.addaudithook`` is per-process, not inherited by a
child interpreter, so layer 2's socket check does not exist there either.
There is no current caller shaped like this in this repository (every
in-repo Ollama call goes through ``get_ollama_base_url()`` or is caught by
layer 2 directly, in-process) -- documented as a gap in the DESIGN, not a
known live leak.

Both audit events are allowed ONLY when ``WAGF_ALLOW_OLLAMA_IN_TESTS=1`` is
set, and even then only during collection or inside a test marked
``@pytest.mark.real_llm`` (see ``tests/integration/test_real_llm_smoke.py``).
Without the flag, EVERY ``real_llm``-marked test is auto-skipped at
collection time (``pytest_collection_modifyitems`` below) with a clear
reason, whatever module it lives in -- a test does not need its own
skip-without-probing logic to get this safely, though
``test_real_llm_smoke.py`` also has one of its own (belt and suspenders,
and it predates this conftest-level mechanism).

Every block is recorded in three places: a per-test list, checked by an
autouse fixture right after the test body runs so the OFFENDING test fails
even if its own code (e.g. the manifest's model-digest ``try/except``)
swallows the exception the hook raised; a cumulative, never-cleared session
list, asserted (minus the guard self-test's OWN deliberate trips) empty by
a self-test that ``pytest_collection_modifyitems`` below reorders to run
after everything else; and an ``_unexpected_blocks`` list (everything
EXCEPT a deliberate trip from that self-test), asserted empty again in
``pytest_sessionfinish`` -- a hook that runs after every fixture teardown of
every scope, including a module- or session-scoped one that could add a
block AFTER the reordered-to-last self-test's own body already ran and
reported green, and regardless of whether some other mechanism (an
``xfail``, a fixture override) kept that block from surfacing as a normal
test failure. The ``expected_ollama_guard_block`` marker that exempts the
self-test's OWN deliberate trips is only valid in that one file; any other
use of it is a collection-time error (``pytest_collection_modifyitems``
below), so it cannot become an easy way to dodge the guard elsewhere.

DEFAULT NETWORK STUB (review round 2, C2): several pre-existing tests build
a real ``ExperimentRunner``/config with a non-mock, non-cloud-provider model
name (``gemma3:4b``, ``scripted-test``, or ``ExperimentConfig``'s own
``"gpt-4"`` default -- none of these start with "mock" or carry a
"provider:" prefix, so the reproducibility manifest's model-digest query
treats them as real Ollama models) and only mock the ONE call they are
actually testing -- leaving the OTHER of the digest query's
``requests.post`` / the modelfile-defaults call's ``subprocess.run`` to hit
a live daemon for real. Rather than hunt down and patch every such call
site (and every one written after today), every test gets BOTH replaced by
default: ``requests.post`` fails closed (a "daemon unreachable"
``ConnectionError``) for a URL that targets the CURRENT Ollama base URL or
port 11434 specifically -- any OTHER URL passes straight through to the
real ``requests.post``, so a test using ``requests`` for something
unrelated is unaffected; ``subprocess.run`` fails closed with
``FileNotFoundError`` the same way, but ONLY for a command whose argv0 is
an ``ollama`` binary -- any other command (git, etc.) also passes straight
through. A test mocking either function itself (to exercise
``capture_ollama_modelfile_defaults``'s OWN parsing, say) still works
exactly as before: its own patch simply overrides this default for its
``with`` block. A ``real_llm``-marked test is exempt from both stubs. Both
intercept BEFORE the real ``subprocess``/socket call, so they and the
audit-hook guard above cover two different layers of the same problem, not
one problem twice: a properly-stubbed test never reaches the guard at all.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytest_plugins = ["pytester"]  # enables the `pytester` fixture (regression test below)

OLLAMA_PORT = 11434
ALLOW_ENV_VAR = "WAGF_ALLOW_OLLAMA_IN_TESTS"
_OLLAMA_EXE_NAMES = {"ollama", "ollama.exe"}
_DEAD_OLLAMA_HOST = "http://127.0.0.1:9"
_EXPECTED_BLOCK_MARKER = "expected_ollama_guard_block"

# Filename of the self-test module pytest_collection_modifyitems moves to
# the end of the run, so it executes after every other test in all three
# roots (examples/irrigation_abm/tests, tests/, broker/). The
# expected_ollama_guard_block marker is only valid inside this one file.
_GUARD_SELFTEST_FILENAME = "test_zz_ollama_guard_survives_full_suite.py"

# EXACT resolved path of that file, always under this conftest.py's own
# "tests" directory (round 4, MUST 3): matching on this instead of a bare
# ``str.endswith(_GUARD_SELFTEST_FILENAME)`` closes the gap where a
# same-named file in a DIFFERENT directory (any of the other two collection
# roots, or a stray copy anywhere else) would otherwise also be treated as
# the guard self-test and could carry the exemption marker undetected.
_GUARD_SELFTEST_PATH = (Path(__file__).resolve().parent / "tests" / _GUARD_SELFTEST_FILENAME)

_hook_installed = False
_session_active = False
_in_collection = True
_current_test_is_real_llm = False
_current_test_expects_guard_block = False
_all_blocks: list[str] = []          # cumulative for the whole session
_unexpected_blocks: list[str] = []   # _all_blocks minus the zz file's own trips
_current_test_blocks: list[str] = []  # reset at each test's setup
_original_ollama_host = None
_ollama_host_forced = False


def _address_port(address):
    """Port from a socket address, or ``None`` if it has no port (e.g. an
    AF_UNIX path)."""
    if isinstance(address, tuple) and len(address) >= 2:
        return address[1]
    return None


def _is_ollama_executable(name) -> bool:
    if not name:
        return False
    return os.path.basename(str(name)).lower() in _OLLAMA_EXE_NAMES


def _is_guard_selftest(item) -> bool:
    """Whether ``item`` belongs to the ONE file the exemption marker is
    valid in.

    Compares the EXACT resolved path (round 4, MUST 3), not a
    ``str.endswith(_GUARD_SELFTEST_FILENAME)`` suffix match: the latter
    would also match a same-named file sitting in a DIFFERENT directory
    (either of the other two collection roots, or a stray copy anywhere
    else), silently letting it carry the ``expected_ollama_guard_block``
    exemption too. ``item.path`` (a ``pathlib.Path``, stable since pytest 7)
    is used directly; ``item.fspath`` (the older ``py.path.local``) is a
    fallback only for a pytest old enough not to have ``item.path`` at all.
    """
    try:
        path = item.path
    except AttributeError:
        path = Path(str(item.fspath))
    return path.resolve() == _GUARD_SELFTEST_PATH


def _first_token_of_cmdline(cmdline: str):
    """Best-effort first whitespace-separated token of a command-line
    string, unquoting a leading quoted path if present (e.g. a path
    containing a space, ``"C:\\Program Files\\Ollama\\ollama.exe" --version``)."""
    cmdline = cmdline.strip()
    if not cmdline:
        return None
    if cmdline.startswith('"'):
        end = cmdline.find('"', 1)
        if end != -1:
            return cmdline[1:end]
    return cmdline.split(None, 1)[0]


def _popen_argv0(popen_args):
    """The first argv token from a ``subprocess.Popen`` audit event's
    ``args`` element.

    On POSIX this is the list/tuple the caller passed, and ``[0]`` is enough
    -- confirmed empirically on this host. On WINDOWS, CPython's
    ``Popen._execute_child`` joins the list into the single command-line
    STRING it hands to ``CreateProcess`` before raising the audit event, so
    a caller passing ``["ollama", "--version"]`` (exactly how
    ``capture_ollama_modelfile_defaults`` calls it) shows up here as the
    string ``"ollama --version"`` -- confirmed empirically on this host
    with a debug hook before this function existed; naively indexing ``[0]``
    on that string would silently check the single character ``"o"``
    instead of ``"ollama"`` and let a real launch through.
    """
    if isinstance(popen_args, (list, tuple)):
        return popen_args[0] if popen_args else None
    if isinstance(popen_args, str):
        return _first_token_of_cmdline(popen_args)
    return None


def _ollama_access_allowed() -> bool:
    """Whether the CURRENT event may proceed instead of being blocked.

    Only true when the operator explicitly opted in (``WAGF_ALLOW_OLLAMA_IN_TESTS=1``),
    AND only during collection (a real_llm module's own skip-condition
    probe) or inside a test actually marked ``real_llm`` -- the flag alone
    does not blanket-disable the guard for the rest of the suite.
    """
    if os.environ.get(ALLOW_ENV_VAR) != "1":
        return False
    return _in_collection or _current_test_is_real_llm


def _record_block(description: str) -> None:
    _all_blocks.append(description)
    _current_test_blocks.append(description)
    if not _current_test_expects_guard_block:
        _unexpected_blocks.append(description)


def _audit_hook(event: str, args: tuple) -> None:
    if not _session_active:
        return  # inert outside an active pytest session (should-fix #1)
    if event == "socket.connect":
        _sock, address = args
        if _address_port(address) == OLLAMA_PORT and not _ollama_access_allowed():
            _record_block(f"socket.connect -> port {OLLAMA_PORT} (address={address!r})")
            raise RuntimeError(
                f"Blocked a connection to port {OLLAMA_PORT} (a live Ollama "
                f"daemon) during a test. Set {ALLOW_ENV_VAR}=1 and mark the "
                "test @pytest.mark.real_llm if it genuinely needs one."
            )
    elif event == "subprocess.Popen":
        executable, popen_args, _cwd, _env = args
        argv0 = _popen_argv0(popen_args)
        if (
            (_is_ollama_executable(executable) or _is_ollama_executable(argv0))
            and not _ollama_access_allowed()
        ):
            _record_block(
                f"subprocess.Popen -> ollama executable={executable!r} argv0={argv0!r}"
            )
            raise RuntimeError(
                f"Blocked launching an ollama process during a test. Set "
                f"{ALLOW_ENV_VAR}=1 and mark the test @pytest.mark.real_llm "
                "if it genuinely needs one."
            )


def _install_guard() -> None:
    global _hook_installed
    if not _hook_installed:
        sys.addaudithook(_audit_hook)
        _hook_installed = True


def pytest_configure(config):
    global _session_active, _original_ollama_host, _ollama_host_forced

    # Both markers this file uses (real_llm, expected_ollama_guard_block)
    # are registered in pyproject.toml's [tool.pytest.ini_options] markers
    # list -- the repo's one existing, discoverable place for this --
    # rather than re-declared here too.
    #
    # Installed here, BEFORE collection: a real_llm module's own
    # availability probe runs at import time (a module-level
    # pytest.mark.skipif condition), before any fixture -- autouse or not --
    # has a chance to run, so the guard must already be live by then.
    _install_guard()
    _session_active = True

    # Expose the SAME list objects the audit hook mutates, via the one
    # object every test can reach unambiguously: the session's `config`
    # (through the standard `request.config` fixture). NOT done via
    # `sys.modules["conftest"]` / `import conftest` -- this repo has a
    # SECOND file also named `conftest.py` (tests/conftest.py), so the bare
    # module name "conftest" in `sys.modules` belongs to whichever of the
    # two was imported last, not reliably this one.
    config._wagf_ollama_guard_all_blocks = _all_blocks
    config._wagf_ollama_guard_unexpected_blocks = _unexpected_blocks

    # MUST 1a / should-fix 4: ALWAYS force OLLAMA_HOST at a dead loopback
    # port at session start, whether or not the operator opted in -- see the
    # module docstring's "GUARD, layer 1" section. When
    # WAGF_ALLOW_OLLAMA_IN_TESTS=1, the ORIGINAL value is not left in place
    # for the whole session (round 3 did that, which meant every OTHER,
    # non-real_llm test also saw the real endpoint for as long as the flag
    # was set); instead the pytest_runtest_setup/pytest_runtest_teardown
    # wrappers below temporarily restore it only around a real_llm test's
    # own setup+call+teardown, then force the dead port right back.
    _original_ollama_host = os.environ.get("OLLAMA_HOST")
    os.environ["OLLAMA_HOST"] = _DEAD_OLLAMA_HOST
    _ollama_host_forced = True


def pytest_unconfigure(config):
    global _session_active, _ollama_host_forced
    if _ollama_host_forced:
        if _original_ollama_host is None:
            os.environ.pop("OLLAMA_HOST", None)
        else:
            os.environ["OLLAMA_HOST"] = _original_ollama_host
        _ollama_host_forced = False
    _session_active = False


def pytest_collection_finish(session):
    global _in_collection
    _in_collection = False


def pytest_collection_modifyitems(session, config, items):
    """Three independent, order-safe passes over the full item list (all
    three roots collected together):

    1. Reject (collection error) any ``expected_ollama_guard_block`` use
       outside the guard self-test file -- that marker exempts a test from
       the auto-fail-on-block fixture, so allowing it anywhere would make
       the guard trivially easy to silence.
    2. Auto-skip every ``real_llm``-marked test when the operator has not
       opted in, with a clear reason, regardless of which module defines it
       (should-fix: previously only test_real_llm_smoke.py skipped itself;
       a real_llm test anywhere else would run, hit the guard, and ERROR
       instead of skipping).
    3. Move the guard self-test module to the very end of the WHOLE run, so
       it proves the guard survived everything else, not just its own file.
    """
    for item in items:
        if item.get_closest_marker(_EXPECTED_BLOCK_MARKER) is not None and not _is_guard_selftest(item):
            raise pytest.UsageError(
                f"{item.nodeid}: @pytest.mark.{_EXPECTED_BLOCK_MARKER} is only "
                f"allowed in {_GUARD_SELFTEST_FILENAME}, not here. It exempts a "
                "test from the ollama-guard's auto-fail-on-block check, so it "
                "must not be used to silence a real leak."
            )

    if os.environ.get(ALLOW_ENV_VAR) != "1":
        skip_marker = pytest.mark.skip(
            reason=(
                f"{ALLOW_ENV_VAR} not set: real_llm tests are skipped "
                "without probing a live Ollama daemon (see conftest.py)"
            )
        )
        for item in items:
            if item.get_closest_marker("real_llm") is not None:
                item.add_marker(skip_marker)

    guard_items = [i for i in items if _is_guard_selftest(i)]
    if guard_items:
        other_items = [i for i in items if not _is_guard_selftest(i)]
        items[:] = other_items + guard_items


def _use_original_ollama_host_for_real_llm_test() -> None:
    """Should-fix 4: switch OLLAMA_HOST to the ORIGINAL value (not the dead
    port every other test sees) for the duration of one real_llm test."""
    if _original_ollama_host is None:
        os.environ.pop("OLLAMA_HOST", None)
    else:
        os.environ["OLLAMA_HOST"] = _original_ollama_host


def _use_dead_ollama_host_again() -> None:
    """Should-fix 4: switch OLLAMA_HOST back to the forced dead port after
    a real_llm test's own setup+call+teardown finished."""
    os.environ["OLLAMA_HOST"] = _DEAD_OLLAMA_HOST


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item):
    """A HOOKWRAPPER (should-fix 4): when ``WAGF_ALLOW_OLLAMA_IN_TESTS=1``
    and this item is ``real_llm``, OLLAMA_HOST must already read the
    ORIGINAL value by the time this item's own fixtures are set up (a
    fixture may itself need real Ollama access, e.g. to check
    connectivity), which means the switch has to happen BEFORE ``yield``
    here -- a plain (non-wrapper) implementation could run after the
    default fixture-setup implementation and restore it too late. It is
    switched back to the dead port only at the END of this item's teardown
    (see ``pytest_runtest_teardown`` below), so it stays the real value
    through setup, call, AND teardown, not just one of the three.
    """
    global _current_test_is_real_llm
    _current_test_is_real_llm = item.get_closest_marker("real_llm") is not None
    _current_test_blocks.clear()
    if _ollama_host_forced and _current_test_is_real_llm and os.environ.get(ALLOW_ENV_VAR) == "1":
        _use_original_ollama_host_for_real_llm_test()
    return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """A HOOKWRAPPER (round 4, MUST 1): ``_current_test_expects_guard_block``
    must be true ONLY while the guard self-test's OWN function body is
    executing -- NOT during setup or teardown of that same item.

    Why this matters: when the guard self-test module is reordered to the
    very end (as it always is), its LAST test is the last item in the whole
    session, so pytest tears down every STILL-ACTIVE fixture of every scope
    -- including a session-scoped one belonging to a completely different
    test earlier in the suite -- during THAT item's own teardown phase (see
    ``pytest_runtest_teardown`` below). A session-fixture finalizer that
    records a REAL, unexpected block would therefore fire while that last
    guard-self-test item's teardown is running. Before this fix, the
    "expected" flag was set for that item's ENTIRE lifecycle (setup, call,
    AND teardown) in ``pytest_runtest_setup``/``pytest_runtest_teardown``,
    so such a block was silently counted as an expected, deliberate trip --
    exactly the swallow this fix closes. Scoping the flag to the call phase
    only (this hookwrapper) means a block from ANY teardown, including the
    guard self-test's own, is always unexpected.

    Round 5, MUST A: the marker check alone is not enough, because a marker
    can be added to ANY item at runtime -- a ``trylast``-ordered
    ``pytest_collection_modifyitems`` implementation (which would run AFTER
    this file's own, so it never sees the addition to reject) running after
    collection, or an autouse fixture calling
    ``item.add_marker(...)``/``request.node.add_marker(...)`` during its own
    setup. Either would make ``get_closest_marker`` find the marker on a
    test this file never put it on, exempting that test's real block from
    ever being flagged. ``_is_guard_selftest(item)`` checks the item's
    EXACT resolved file path, which cannot be forged by adding a marker, so
    ANDing it in closes the bypass regardless of how the marker got there.
    """
    global _current_test_expects_guard_block
    _current_test_expects_guard_block = (
        _is_guard_selftest(item)
        and item.get_closest_marker(_EXPECTED_BLOCK_MARKER) is not None
    )
    try:
        return (yield)
    finally:
        _current_test_expects_guard_block = False


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item, nextitem):
    """A HOOKWRAPPER, not a plain hookimpl (should-fix): a plain
    ``pytest_runtest_teardown`` implementation runs at an unspecified point
    relative to the default implementation that actually invokes fixture
    finalizers, so resetting ``_current_test_is_real_llm`` there could flip
    it back to False WHILE a real_llm test's own fixture teardown (e.g.
    closing an OllamaProvider client) is still running -- blocking exactly
    the access the marker was supposed to allow. ``yield`` here waits for
    every other implementation, INCLUDING the one that runs fixture
    finalizers, to finish first; the reset happens strictly after.

    ``_current_test_expects_guard_block`` is NOT reset here (round 4): it is
    now scoped entirely to ``pytest_runtest_call`` above and is already
    ``False`` for the whole teardown phase, on purpose -- see that
    hookwrapper's docstring for why this item's own teardown must not be
    treated as an expected block either.

    Should-fix 4: if this item was a real_llm test that switched OLLAMA_HOST
    to the original value (in ``pytest_runtest_setup``), it is switched back
    to the forced dead port here, AFTER every fixture finalizer (including
    this item's own) has already run -- restoring it any earlier would
    block exactly the teardown access the marker was supposed to allow, the
    same reasoning as the ``_current_test_is_real_llm`` reset below.
    """
    try:
        return (yield)
    finally:
        global _current_test_is_real_llm
        if _ollama_host_forced and _current_test_is_real_llm:
            _use_dead_ollama_host_again()
        _current_test_is_real_llm = False


def pytest_sessionfinish(session, exitstatus):
    """Backstop for C2 (MUST 1b): assert zero UNEXPECTED blocks across the
    WHOLE session, at the point where every fixture teardown of every scope
    -- function, module, session -- has already run. The reordered-to-last
    self-test's own in-line assertion covers the common case; this hook
    covers what that test cannot see: a block recorded by a module- or
    session-scoped fixture's finalizer (which can run AFTER even a
    reordered-to-last test's own body), or one an ``xfail`` or a fixture
    override kept from surfacing as an ordinary test failure.
    """
    if _unexpected_blocks:
        session.exitstatus = 1
        print(
            f"\n[ollama-guard] {len(_unexpected_blocks)} unexpected block(s) "
            "recorded this session (session forced to fail):"
        )
        for b in _unexpected_blocks:
            print(f"  - {b}")


@pytest.fixture(autouse=True, scope="session")
def _ollama_guard_installed_for_session():
    """Autouse and session-scoped, as requested: guarantees the guard is
    installed for every test in the session even if something ran before
    pytest_configure (plugin ordering) skipped it. Installation is
    idempotent with pytest_configure above -- this cannot "turn off" the
    guard on exit because audit hooks cannot be removed; there is nothing
    for this fixture's teardown to undo (the ``_session_active`` flag, not
    this fixture, is what makes the hook inert again after the session).
    """
    _install_guard()
    yield


@pytest.fixture(autouse=True)
def _fail_if_ollama_guard_blocked_during_test(request):
    """Fail THIS test if the audit hook recorded a block while it ran.

    Necessary because the code under test can itself swallow the hook's
    RuntimeError (the manifest's model-digest query catches ``Exception``
    and records "unavailable"), which would otherwise let an accidental
    live-daemon hit slide by as a normal pass. Exempted for a test that
    marks itself ``expected_ollama_guard_block`` (the guard self-tests
    below, which deliberately trip it and assert on that directly) -- and
    ONLY there, since ``pytest_collection_modifyitems`` above rejects that
    marker everywhere else at collection time.

    Round 5, MUST A: the exemption also requires ``_is_guard_selftest(request.node)``,
    the SAME AND-condition as ``pytest_runtest_call`` above and for the same
    reason -- a marker added at runtime (a ``trylast`` collection hook, or
    an autouse fixture calling ``request.node.add_marker(...)`` during its
    own setup) would otherwise let ANY test exempt itself from this check
    too, not just from the audit hook's gate.
    """
    yield
    if _is_guard_selftest(request.node) and request.node.get_closest_marker(_EXPECTED_BLOCK_MARKER) is not None:
        _current_test_blocks.clear()
        return
    if _current_test_blocks:
        blocks = list(_current_test_blocks)
        _current_test_blocks.clear()
        pytest.fail(
            f"ollama-guard blocked {len(blocks)} access attempt(s) during "
            f"this test: {blocks}",
            pytrace=False,
        )


def _looks_like_an_ollama_url(url) -> bool:
    """Whether ``url`` targets the current Ollama endpoint (should-fix:
    narrow the requests.post stub instead of intercepting every URL).

    Matches the PARSED host and port (round 4, should-fix 5) against the
    CURRENT effective base URL (``get_ollama_base_url()``, which honors
    ``OLLAMA_HOST`` -- including this file's own dead-port override), OR a
    URL that explicitly names port 11434 regardless of host (so a
    hardcoded ``localhost:11434`` that ignores ``OLLAMA_HOST`` is still
    caught). Comparing the RAW STRINGS with ``url.startswith(base)`` was
    wrong: with the base forced to ``http://127.0.0.1:9`` (the dead port
    this file forces by default), a completely unrelated
    ``http://127.0.0.1:9123/...`` also starts with that string ("9123"
    starts with "9"), so it was wrongly intercepted too. Anything that does
    not match either check (a test's own unrelated ``requests.post``
    target) passes through untouched.
    """
    if not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.port == OLLAMA_PORT:
        return True
    try:
        from broker.utils.llm_utils import get_ollama_base_url
        base = urlparse(get_ollama_base_url())
        return parsed.hostname == base.hostname and parsed.port == base.port
    except Exception:
        return False


def _make_selective_requests_post_stub(real_post):
    def _stub(url, *args, **kwargs):
        if _looks_like_an_ollama_url(url):
            import requests
            raise requests.exceptions.ConnectionError(
                "stubbed by the root conftest's default network fixture: no "
                "test in this suite may depend on a live Ollama daemon; "
                "patch requests.post locally if this test needs a specific "
                "response"
            )
        return real_post(url, *args, **kwargs)
    return _stub


def _make_selective_subprocess_run_stub(real_subprocess_run):
    """A ``subprocess.run`` replacement that only intercepts an ``ollama``
    command, passing every other command (git, etc.) straight through to
    the REAL ``subprocess.run``.

    Earlier version of this fixture replaced
    ``broker.utils.llm_utils.capture_ollama_modelfile_defaults`` directly,
    which broke every test that patches ``subprocess.run`` itself to
    exercise that function's OWN parsing of a fake modelfile (e.g.
    ``test_llm_model_defaults_captured_for_real_model`` and siblings) --
    replacing the function they were testing left their carefully-built
    fake output unused. Stubbing at the ``subprocess.run`` layer instead,
    and only for an ``ollama`` command, fixes the untested call sites (C2)
    without touching a test that already mocks this correctly: that test's
    own ``patch("subprocess.run", ...)`` simply takes over for its ``with``
    block, exactly as it did before this fixture existed.

    Raises ``FileNotFoundError``, matching the exact "ollama absent" shape
    ``capture_ollama_modelfile_defaults`` already handles
    (``except FileNotFoundError: return None, "ollama executable not found
    on PATH"`` -- see ``test_llm_model_defaults_failure_records_null_plus_warning``,
    which pins this exact behaviour). Also means the real
    ``subprocess.run``/``Popen`` is never reached for these calls, so the
    audit-hook guard never has anything to block or record here either --
    this stub and the guard cover two different layers of the same
    problem, not one problem twice.
    """
    def _stub(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args")
        if isinstance(cmd, (list, tuple)):
            argv0 = cmd[0] if cmd else None
        elif isinstance(cmd, str):
            argv0 = _first_token_of_cmdline(cmd)
        else:
            argv0 = None
        if _is_ollama_executable(argv0):
            raise FileNotFoundError(
                "[stubbed by the root conftest's default network fixture] "
                "no ollama binary in this test session"
            )
        return real_subprocess_run(*args, **kwargs)
    return _stub


@pytest.fixture(autouse=True)
def _default_stub_no_test_needs_a_live_daemon(request, monkeypatch):
    """Default network stub so NO test needs a live Ollama daemon, whatever
    model name it happens to construct a runner with (see the module
    docstring's "DEFAULT NETWORK STUB" section): an Ollama-targeted
    ``requests.post`` fails closed the same way an unreachable daemon
    would, and an ``ollama`` ``subprocess.run`` call fails closed the same
    way a missing binary would (any OTHER URL or command -- git, etc. -- is
    unaffected). A test that wants a specific response still overrides
    either locally, which applies on top of this default for that test
    only. A ``real_llm``-marked test is exempt: it intentionally wants the
    real functions.
    """
    if request.node.get_closest_marker("real_llm") is not None:
        return
    import subprocess as _subprocess_module
    import requests as _requests_module
    monkeypatch.setattr(
        _requests_module, "post",
        _make_selective_requests_post_stub(_requests_module.post),
    )
    monkeypatch.setattr(
        _subprocess_module, "run",
        _make_selective_subprocess_run_stub(_subprocess_module.run),
    )
