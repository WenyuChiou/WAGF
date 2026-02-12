"""
Modular Experiment System - The "Puzzle" Architecture

Re-export shim: the actual classes live in experiment_runner.py and
experiment_builder.py.  All existing imports continue to work.
"""
from .experiment_runner import ExperimentConfig, ExperimentRunner  # noqa: F401
from .experiment_builder import ExperimentBuilder  # noqa: F401

__all__ = ["ExperimentConfig", "ExperimentRunner", "ExperimentBuilder"]
