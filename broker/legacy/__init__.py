"""
Legacy MCP Broker Engine (v1) - DEPRECATED

This module is preserved for backwards compatibility only.
For new experiments, use `broker.skill_broker_engine.SkillBrokerEngine` instead.

See examples/v1_mcp_flood/ for legacy usage examples.
"""
from .engine import BrokerEngine
from .types import (
    DecisionRequest, ValidationResult, ActionRequest,
    AdmissibleCommand, ExecutionResult, BrokerResult, OutcomeType
)

__all__ = [
    "BrokerEngine",
    "DecisionRequest", "ValidationResult", "ActionRequest",
    "AdmissibleCommand", "ExecutionResult", "BrokerResult", "OutcomeType"
]

# Mark as deprecated
import warnings
warnings.warn(
    "broker.legacy is deprecated. Use broker.SkillBrokerEngine for new experiments.",
    DeprecationWarning,
    stacklevel=2
)
