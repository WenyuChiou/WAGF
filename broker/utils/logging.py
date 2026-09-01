import logging
import os

# Define a custom log format that matches the existing style but allows level control
LOG_FORMAT = "%(message)s"

def _has_handler_in_ancestry(logger: logging.Logger) -> bool:
    """True if a propagating ancestor of ``logger`` already owns a handler.

    Every ``setup_logger(__name__)`` call (audit.py, governance_auditor.py,
    reflection.py, ...) creates a dotted child of the shared "broker" logger
    (set up once, below, as ``logger = setup_logger("broker")``). Records
    logged on a child propagate to "broker" by default (``propagate=True``,
    unchanged here -- pytest's ``caplog`` relies on that propagation reaching
    the root logger). Before this guard, ``setup_logger`` also attached a
    fresh ``StreamHandler`` to every child, so each record printed twice:
    once from the child's own handler, once more from "broker"'s when the
    record propagated up. Skipping the child's own handler when an ancestor
    already has one keeps single-print output without touching propagation.

    This guard only looks UP the ancestry at call time, so a child
    configured *before* its parent would still attach its own handler --
    not reachable with the current call sites, since module import
    (line ~49 below) configures "broker" itself first, before any child
    logger's ``setup_logger(__name__)`` call can run. If
    ``logging.basicConfig`` ran first, or ``propagate`` gets set to
    ``False`` on an intermediate logger sometime after setup, a child with
    no handler of its own still renders through whichever ancestor
    handler its record reaches (the root logger's, if basicConfig owns
    it) using THAT handler's format -- not this module's ``LOG_FORMAT``.
    """
    node = logger.parent
    while node is not None:
        if node.handlers:
            return True
        if not node.propagate:
            break
        node = node.parent
    return False


def setup_logger(name: str, level: int = logging.INFO):
    """Setup a standard logger with a clean format."""
    logger = logging.getLogger(name)
    if not logger.handlers and not _has_handler_in_ancestry(logger):
        handler = logging.StreamHandler()
        formatter = logging.Formatter(LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Allow environment override for log level
    env_level = os.environ.get("BROKER_LOG_LEVEL")
    if env_level:
        level = getattr(logging, env_level.upper(), level)

    logger.setLevel(level)
    return logger

# Shared logger instance
logger = setup_logger("broker")
