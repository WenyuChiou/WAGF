"""Public API for broker.components.analytics.

Re-exports the symbols currently consumed via deep imports across the
repository so callers have a shorter canonical import path. Existing deep
imports remain supported.
"""

from importlib import import_module

_EXPORT_MAP = {
    "AgentDriftReport": ("drift", "AgentDriftReport"),
    "AgentMetricsTracker": ("feedback", "AgentMetricsTracker"),
    "AuditConfig": ("audit", "AuditConfig"),
    "DriftAlert": ("drift", "DriftAlert"),
    "DriftDetector": ("drift", "DriftDetector"),
    "DriftReport": ("drift", "DriftReport"),
    "FeedbackDashboardProvider": ("feedback", "FeedbackDashboardProvider"),
    "GenericAuditWriter": ("audit", "GenericAuditWriter"),
    "InteractionHub": ("interaction", "InteractionHub"),
    "ObservableStateManager": ("observable", "ObservableStateManager"),
    "SafeExpressionEvaluator": ("feedback", "SafeExpressionEvaluator"),
    "create_drift_observables": ("observable", "create_drift_observables"),
    "create_flood_observables": ("observable", "create_flood_observables"),
    "create_rate_metric": ("observable", "create_rate_metric"),
    # Framework invariant enforcement — see broker/INVARIANTS.md Invariant 2.
    "detect_audit_sentinels": ("audit", "detect_audit_sentinels"),
    "detect_audit_sentinels_in_csv": ("audit", "detect_audit_sentinels_in_csv"),
}

__all__ = list(_EXPORT_MAP)


def __getattr__(name: str):
    if name not in _EXPORT_MAP:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _EXPORT_MAP[name]
    module = import_module(f"{__name__}.{module_name}")
    return getattr(module, attr_name)


def __dir__():
    return sorted(set(globals()) | set(__all__))
