"""Regression tests for broker.utils.logging's handler-dedup guard.

Before ``_has_handler_in_ancestry`` (broker/utils/logging.py), every
``setup_logger(__name__)`` call attached its OWN ``StreamHandler`` to the
new logger -- even though nearly every one of those loggers is a dotted
child of the shared "broker" logger and therefore already propagates its
records up to "broker"'s handler. The result: a record logged by a child
printed twice -- once via the child's own handler, once more when the
record propagated to "broker". This file pins the fix: a child attaches
no handler of its own when a propagating ancestor already owns one, and a
record it logs renders exactly once.

Design notes (see the task report for the full write-up on how this was
falsified against the pre-fix code):

* Tests attach a handler to "broker" DIRECTLY (``logger.addHandler`` /
  the ``_attach_plain_stream_handler`` helper below) rather than reading
  whatever ``setup_logger("broker")`` produced at *module import* time --
  under pytest the ROOT logger can carry the logging plugin's own handler
  (and pytest reinstalls it fresh for each test phase), so trusting
  ``parent.handlers[0]`` or relying on import-time state is fragile.
  Attaching directly to "broker" also means the ancestry walk in
  ``_has_handler_in_ancestry`` short-circuits at "broker" itself and never
  needs to consult root at all, sidestepping that pytest behavior
  entirely.
* The "renders exactly once" test constructs BOTH "broker"'s handler and
  (pre-fix) the child's own handler as plain ``logging.StreamHandler()``
  with no explicit stream -- exactly how production code builds them --
  while ``sys.stderr`` is redirected to a shared StringIO. That's what
  makes a doubled write observable: a naive test that only attaches a
  capture handler to "broker" would pass against BOTH the old and new
  code, because the child's own (buggy) handler would default to the
  REAL ``sys.stderr``, a different destination than a hand-attached
  StringIO -- the two writes would never land in the same place to be
  counted.
"""
from __future__ import annotations

import contextlib
import io
import logging

import pytest

from broker.utils.logging import LOG_FORMAT, setup_logger

_BROKER = "broker"
_CHILD = "broker.test_dup_probe"


def _attach_plain_stream_handler(logger: logging.Logger, stream=None) -> logging.Handler:
    """Build a handler the same way ``broker.utils.logging.setup_logger``
    does (a bare ``logging.StreamHandler()`` + the module's ``LOG_FORMAT``)
    and attach it to ``logger``. With ``stream=None`` this reads whatever
    ``sys.stderr`` currently is at construction time -- matching
    production behavior, and safe to call inside a
    ``contextlib.redirect_stderr`` block to capture where it would really
    write.
    """
    handler = logging.StreamHandler(stream) if stream is not None else logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    return handler


@pytest.fixture
def isolated_broker_logger():
    """Give "broker" and one throwaway child logger a clean, restorable
    handler state for the duration of one test.

    Real production code already runs ``setup_logger("broker")`` at
    import time (broker/utils/logging.py's module-level ``logger =
    setup_logger("broker")``), so "broker" enters every test with a real
    handler already attached, built from whatever ``sys.stderr`` was at
    import time. This fixture saves that state and the throwaway child's
    state, clears both, and restores them verbatim in teardown so tests
    build their own handlers explicitly inside a known-clean state.
    """
    broker_log = logging.getLogger(_BROKER)
    child_log = logging.getLogger(_CHILD)
    saved_broker = list(broker_log.handlers)
    saved_child = list(child_log.handlers)
    broker_log.handlers = []
    child_log.handlers = []
    try:
        yield broker_log, child_log
    finally:
        broker_log.handlers = saved_broker
        child_log.handlers = saved_child


def test_child_logger_attaches_no_handler_when_ancestor_owns_one(isolated_broker_logger):
    """A dotted child must not get its own handler once its propagating
    ancestor ("broker") already owns one."""
    broker_log, _child_log = isolated_broker_logger
    _attach_plain_stream_handler(broker_log, stream=io.StringIO())
    assert broker_log.handlers, "precondition: 'broker' must own a handler"

    child = setup_logger(_CHILD)

    assert child.handlers == [], (
        "child logger attached its own handler even though a propagating "
        "ancestor ('broker') already owns one -- records would double-print"
    )


def test_child_logger_record_renders_exactly_once(isolated_broker_logger):
    """A record the child logs must reach a given destination exactly once.

    Both "broker"'s handler and (pre-fix) the child's own handler default
    to ``sys.stderr`` when built the way production code builds them --
    that shared destination is literally how the old bug showed up (a
    doubled console line). Constructing both while ``sys.stderr`` is
    redirected to a StringIO makes a doubled write directly observable.
    """
    broker_log, _child_log = isolated_broker_logger
    capture = io.StringIO()

    with contextlib.redirect_stderr(capture):
        _attach_plain_stream_handler(broker_log)  # bare -> picks up `capture`
        child = setup_logger(_CHILD)               # pre-fix: 2nd handler, also -> `capture`
        child.info("hello once")

    lines = [line for line in capture.getvalue().splitlines() if line]
    assert lines == ["hello once"], (
        f"expected the record to render exactly once, got: {lines!r}"
    )


def test_setup_logger_idempotent_same_name_adds_no_second_handler():
    """Calling setup_logger twice on the same name must not add a second
    handler to that logger.

    Uses its own private, non-"broker" namespace with the intermediate
    node's ``propagate`` forced off, so ``_has_handler_in_ancestry`` stops
    its walk before ever consulting the real root logger (which, under
    pytest, may carry the logging plugin's own handler) -- keeping this
    test deterministic regardless of that ambient state.
    """
    ns_name = "test_wagf_logging_idempotent_ns"
    name = f"{ns_name}.probe"
    ns_logger = logging.getLogger(ns_name)
    probe_logger = logging.getLogger(name)
    saved_ns_propagate = ns_logger.propagate
    saved_ns_handlers = list(ns_logger.handlers)
    saved_probe_handlers = list(probe_logger.handlers)
    ns_logger.propagate = False
    ns_logger.handlers = []
    probe_logger.handlers = []
    try:
        logger_a = setup_logger(name)
        handler_count_after_first_call = len(logger_a.handlers)
        assert handler_count_after_first_call == 1, (
            "sanity check: with no handler anywhere in its ancestry, the "
            "first setup_logger call must attach exactly one handler"
        )

        logger_b = setup_logger(name)

        assert logger_a is logger_b
        assert len(logger_b.handlers) == handler_count_after_first_call == 1
    finally:
        ns_logger.propagate = saved_ns_propagate
        ns_logger.handlers = saved_ns_handlers
        probe_logger.handlers = saved_probe_handlers
