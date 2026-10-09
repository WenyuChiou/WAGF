"""CLI coverage for the irrigation runner's Ollama thinking override."""

import sys

from examples.irrigation_abm import run_experiment


def test_thinking_mode_defaults_to_inherited_framework_setting(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_experiment.py"])

    args = run_experiment.parse_args()

    assert args.thinking_mode is None


def test_thinking_mode_accepts_explicit_override(monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["run_experiment.py", "--thinking-mode", "enabled"]
    )

    args = run_experiment.parse_args()

    assert args.thinking_mode == "enabled"
