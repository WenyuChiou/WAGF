"""
Modular Experiment System - Supported backward-compatibility re-export shim.

The canonical implementations live in :mod:`broker.core.experiment_runner` and
:mod:`broker.core.experiment_builder`. Retained without deprecation warnings
for all existing runners and examples.
"""
from .experiment_runner import ExperimentConfig, ExperimentRunner  # noqa: F401
from .experiment_builder import ExperimentBuilder  # noqa: F401

__all__ = ["ExperimentConfig", "ExperimentRunner", "ExperimentBuilder"]
