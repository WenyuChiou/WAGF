"""
Explainable AI (XAI) components.

- counterfactual.py: CounterfactualEngine (Phase 4A - Claude Code)
"""

from .counterfactual import (
    CounterfactualEngine,
    explain_blocked_action,
)
from ..types import CounterFactualStrategy

__all__ = [
    "CounterFactualStrategy",
    "CounterfactualEngine",
    "explain_blocked_action",
]
