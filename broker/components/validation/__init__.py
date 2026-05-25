"""Phase 6O-C — Generic readiness analysis package.

Contains the profile loader + threshold dataclasses + readiness
computation logic consumed by the `broker.tools.readiness_report` CLI.

All modules under this package are pure-functional and read-only with
respect to broker runtime state. They never mutate audit data, never
load YAML registries, and never instantiate validators. Their sole
input is a results-directory path produced by an experiment run, and
their sole output is a structured `ReadinessReport` dataclass plus an
optional JSON serialisation.
"""
from broker.components.validation.readiness_profile import (
    ReadinessProfile,
    ReadinessThresholds,
    load_readiness_profile,
)

__all__ = [
    "ReadinessProfile",
    "ReadinessThresholds",
    "load_readiness_profile",
]
